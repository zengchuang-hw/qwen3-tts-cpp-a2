"""Mutate real A2 model outputs; require Q1 to reject each invalid record."""
import argparse
import copy
import json
from pathlib import Path
import sys


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--freeze', type=Path, required=True)
p.add_argument('--scores', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--source', type=Path, required=True)
args = p.parse_args()
sys.path.insert(0, str(args.source))
from quality_core import ASR_NEW_TOKENS, audit_score, compare_group, sha256

records = []
for path in args.scores.glob('*.json'):
    row = json.loads(path.read_text())
    if row.get('status') == 'SCORED' and all(key in row for key in ('pcm_sha256','asr','speaker')):
        records.append((path, row))
if not records:
    raise ValueError('no real independent scores available for negative controls')
path, original = records[0]
digest = sha256(args.freeze)
audit_score(original, original['pcm_sha256'], original['language'], digest)
controls = [
    ('missing-window', lambda row: row['asr'].pop()),
    ('wrong-PCM', lambda row: row.update(pcm_sha256='0' * 64)),
    ('wrong-model', lambda row: row.update(models={})),
    ('wrong-lock', lambda row: row.update(lock_sha256='0' * 64)),
    ('truncated-ASR', lambda row: row['asr'][0].update(generated_tokens=[2])),
    ('token-limit', lambda row: row['asr'][0].update(generated_tokens=[row['asr'][0]['eos_token_id']] * ASR_NEW_TOKENS)),
    ('NaN-embedding', lambda row: row['speaker'][0]['embedding'].__setitem__(0, float('nan'))),
    ('speaker-coverage', lambda row: row['speaker'][0].update(real_samples=0)),
]
results = []
for name, mutate in controls:
    changed = copy.deepcopy(original)
    mutate(changed)
    try:
        audit_score(changed, original['pcm_sha256'], original['language'], digest)
    except (ValueError, KeyError, TypeError) as error:
        results.append({'control': name, 'status': 'REJECTED', 'error': str(error)})
    else:
        raise ValueError('invalid real record accepted: ' + name)
pairs = [json.loads(p.read_text()) for p in args.scores.glob('r*-c*-*.json')]
pairs = [row for row in pairs if row.get('status')=='SCORED' and 'candidate_embedding' in row]
if not pairs:
    raise ValueError('real score pairs missing')
row = copy.deepcopy(pairs[0])
row['exact_pcm'] = False
row['candidate_transcript'] = row['text'] + ' unrelated inserted words' * 50
if compare_group([row], row['language'])['status'] != 'FAIL':
    raise ValueError('large ASR regression accepted')
results.append({'control': 'large-ASR-regression', 'status': 'REJECTED'})
row['candidate_transcript'] = row['reference_transcript']
row['candidate_embedding'] = [-v for v in row['reference_embedding']]
if compare_group([row], row['language'])['status'] != 'FAIL':
    raise ValueError('opposite speaker vector accepted')
results.append({'control': 'opposite-speaker-vector', 'status': 'REJECTED'})
with args.output.open('x') as stream:
    stream.write(json.dumps({'status': 'PASS', 'scope': 'evaluator rejection contracts, not candidate quality',
        'source_score': str(path), 'source_score_sha256': sha256(path), 'controls': results}, indent=2) + '\n')
print('PASS', len(results), 'actual-score negative controls', flush=True)

