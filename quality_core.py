"""RFC Q1 contracts and metrics. This module has no inference dependencies."""

import hashlib
import math
from pathlib import Path
import re
import unicodedata

MODEL_REVISIONS = {
    'openai/whisper-small': '973afd24965f72e36ca33b3055d56a652f456b4d',
    'microsoft/wavlm-base-plus-sv': 'feb593a6c23c1cc3d9510425c29b0a14d2b07b1e',
}
PROTOCOL = 'Q1-balanced-v1'
ASR_MAX = 30 * 16000
SPEAKER_MAX = 6 * 16000
ASR_NEW_TOKENS = 444


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def windows(samples, maximum):
    if type(samples) is not int or type(maximum) is not int or min(samples, maximum) < 1:
        raise ValueError('positive integer sample bounds required')
    count = (samples + maximum - 1) // maximum
    return [(i * samples // count, (i + 1) * samples // count) for i in range(count)]


def units(text, language):
    if not isinstance(text, str):
        raise ValueError('actual transcript text required')
    text = unicodedata.normalize('NFKC', text).casefold()
    if language == 'English':
        # Unicode alphanumeric words, with internal ASCII apostrophes.
        return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text)
    if language == 'Chinese':
        return [char for char in text if char.isalnum()]
    raise ValueError('Q1 supports only English and Chinese')


def edit_distance(reference, candidate):
    previous = list(range(len(candidate) + 1))
    for i, word in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(candidate, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (word != other)))
        previous = current
    return previous[-1]


def normalized(vector):
    if not isinstance(vector, list) or not vector or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in vector):
        raise ValueError('finite embedding vector required')
    norm = math.sqrt(math.fsum(v * v for v in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError('nonzero finite embedding norm required')
    return [v / norm for v in vector]


def pooled_embedding(rows, samples):
    bounds = windows(samples, SPEAKER_MAX)
    if len(rows) != len(bounds):
        raise ValueError('speaker coverage incomplete')
    vectors = []
    for row, (start, end) in zip(rows, bounds):
        if (row['start'], row['end']) != (start, end) or len(row['embedding']) != 512:
            raise ValueError('speaker bounds or embedding dimension differs')
        if row.get('real_samples') != end - start:
            raise ValueError('speaker real sample coverage differs')
        vectors.append(normalized(row['embedding']))
    return normalized([math.fsum(v[i] * (b - a) for v, (a, b) in zip(vectors, bounds)) / samples
                       for i in range(512)])


def audit_score(record, pcm_sha, language, lock_sha):
    if (record['protocol'] != PROTOCOL or record['lock_sha256'] != lock_sha
            or record['pcm_sha256'] != pcm_sha or record['language'] != language
            or record['status'] != 'SCORED' or record['models'] != MODEL_REVISIONS):
        raise ValueError('score identity, source lock or scope differs')
    samples = record['samples_16k']
    rows = record['asr']
    bounds = windows(samples, ASR_MAX)
    if len(rows) != len(bounds):
        raise ValueError('ASR coverage incomplete')
    transcripts = []
    for row, (start, end) in zip(rows, bounds):
        tokens = row['generated_tokens']
        if ((row['start'], row['end']) != (start, end) or not row['transcript'].strip()
                or not isinstance(tokens, list) or not tokens or len(tokens) >= ASR_NEW_TOKENS
                or any(type(token) is not int or token < 0 for token in tokens)
                or len(row.get('prefix', [])) != 4
                or row['eos_token_id'] not in tokens or tokens[-1] != row['eos_token_id']):
            raise ValueError('ASR transcript, EOS or coverage incomplete')
        transcripts.append(row['transcript'])
    text = ' '.join(transcripts)
    if not units(text, language):
        raise ValueError('ASR transcript has no scoring units')
    return text, pooled_embedding(record['speaker'], samples)


def compare_group(rows, language):
    """Recompute metrics from transcripts/vectors, never accept supplied scores."""
    if not rows:
        raise ValueError('empty quality group')
    total = baseline = candidate = 0
    cosines = []
    for row in rows:
        target = units(row['text'], language)
        if not target:
            raise ValueError('empty ground truth')
        total += len(target)
        baseline += edit_distance(target, units(row['reference_transcript'], language))
        candidate += edit_distance(target, units(row['candidate_transcript'], language))
        if not row['exact_pcm']:
            left, right = normalized(row['reference_embedding']), normalized(row['candidate_embedding'])
            if len(left) != 512 or len(right) != 512:
                raise ValueError('speaker dimension differs')
            cosines.append(max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right)))))
    # Integer arithmetic preserves the exact inclusive one-percentage-point gate.
    asr_pass = (candidate - baseline) * 100 <= total
    speaker_pass = all(value >= .98 for value in cosines)
    return {'language': language, 'utterances': len(rows), 'ground_truth_units': total,
            'reference_errors': baseline, 'candidate_errors': candidate,
            'reference_error_rate': baseline / total, 'candidate_error_rate': candidate / total,
            'error_rate_delta': (candidate - baseline) / total,
            'speaker_cosines': cosines, 'speaker_min': min(cosines) if cosines else None,
            'speaker_mean': math.fsum(cosines) / len(cosines) if cosines else None,
            'status': 'PASS' if asr_pass and speaker_pass else 'FAIL'}
