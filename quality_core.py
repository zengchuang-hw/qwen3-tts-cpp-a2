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
PREFIX = {'English': [50258, 50259, 50359, 50363], 'Chinese': [50258, 50260, 50359, 50363]}


def audit_boundary(lock, boundary, terminal, lock_sha, boundary_sha, run, runspec_mtime_ns):
    if (boundary['status'] != 'STARTED' or boundary['protocol'] != PROTOCOL
            or boundary['lock_sha256'] != lock_sha or terminal['boundary_sha256'] != boundary_sha
            or terminal['identity_unchanged'] is not True or terminal['lock_sha256'] != lock_sha
            or boundary['run'] != run
            or not lock['frozen_unix_ns'] < boundary['started_unix_ns'] < terminal['finished_unix_ns']
            or runspec_mtime_ns < boundary['started_unix_ns']):
        raise ValueError('missing or inconsistent pre-generation boundary')


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
    if record.get('status') != 'SCORED':
        raise ValueError('scorer incomplete: ' + record.get('error', 'no complete raw score'))
    if (record['protocol'] != PROTOCOL or record['lock_sha256'] != lock_sha
            or record['pcm_sha256'] != pcm_sha or record['language'] != language
            or record['models'] != MODEL_REVISIONS):
        raise ValueError('score identity, source lock or scope differs')
    samples = record['samples_16k']
    pcm_bytes = record['pcm_bytes']
    if type(pcm_bytes) is not int or pcm_bytes <= 0 or pcm_bytes % 2 or samples != (pcm_bytes + 2) // 3:
        raise ValueError('resampled sample count does not cover the complete PCM')
    rows = record['asr']
    bounds = windows(samples, ASR_MAX)
    if len(rows) != len(bounds):
        raise ValueError('ASR coverage incomplete')
    transcripts = []
    for row, (start, end) in zip(rows, bounds):
        tokens = row['generated_tokens']
        if isinstance(tokens, list) and len(tokens) >= ASR_NEW_TOKENS:
            raise ValueError(f'ASR window {start}:{end} reached {ASR_NEW_TOKENS} new-token limit')
        if ((row['start'], row['end']) != (start, end) or not row['transcript'].strip()
                or not isinstance(tokens, list) or not tokens
                or any(type(token) is not int or not 0 <= token < 51865 for token in tokens)
                or row.get('prefix') != PREFIX[language] or row['eos_token_id'] != 50257
                or tokens.count(50257) != 1 or tokens[-1] != 50257):
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


def summarize_group(rows, language):
    """Never calculate acceptance on a selected subset of attempted outputs."""
    if not rows:
        raise ValueError('empty quality group')
    missing = [row['index'] for row in rows if row.get('status') != 'SCORED']
    if missing:
        return {'status': 'INCONCLUSIVE', 'language': language, 'utterances': len(rows),
                'scored_utterances': len(rows) - len(missing), 'inconclusive_indices': missing,
                'reason': 'incomplete independent scores; no subset error-rate acceptance'}
    return compare_group(rows, language)
