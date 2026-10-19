"""Audit immutable Q1 outputs and rerun the corrected raw-record controls on A2."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/work/q1-attempt05')
SRC = ROOT / 'source'
sys.path.insert(0, str(SRC))
from assess import audit_cohort
from quality_core import audit_boundary, audit_score, sha256, summarize_group
from speech_quality import checked_lock, current_identity, read, workload_rows

lock = checked_lock(ROOT / 'freeze.json')
lock_sha = sha256(ROOT / 'freeze.json')
boundary = read(ROOT / 'generation.json')
terminal = read(ROOT / 'generation.json.terminal.json')
audit_boundary(lock, boundary, terminal, lock_sha, sha256(ROOT / 'generation.json'),
               str(ROOT / 'generated'), (ROOT / 'generated/runspec.json').stat().st_mtime_ns)
if terminal['actual_exit'] != 0 or terminal['identity_unchanged'] is not True:
    raise ValueError('new generation did not complete cleanly')
source_manifest = read(SRC / 'source-manifest.json')
for name, expected in source_manifest['files'].items():
    if sha256(SRC / name) != expected:
        raise ValueError('canonical tested source changed')
assessment = read(ROOT / 'scores/assessment.json')
spec = read(ROOT / 'generated/runspec.json')
workload = workload_rows(lock['workload'])
groups, counts, rejected = [], {'SCORED': 0, 'INCONCLUSIVE': 0}, []
for concurrency in (4, 16):
    pcm = {}
    for arm in ('reference', 'native'):
        trial = ROOT / ('generated/r1-' + arm)
        life = read(trial / 'lifecycle.json')
        if life['server_exit'] != 0 or life['status'] != 'COMPLETED' or any(c['exit'] != 0 for c in life['cohorts']):
            raise ValueError('actual server/benchmark exit failed')
        pcm[arm] = audit_cohort(trial / ('c%d' % concurrency), 32, concurrency, spec['workload_sha256'])[1]
    languages = {}
    for index in range(32):
        pair = read(ROOT / ('scores/r1-c%d-%05d.json' % (concurrency, index)))
        if pair['index'] != index or pair['text'] != workload[index]['input'] or pair['language'] != workload[index]['language']:
            raise ValueError('per-pair input coverage differs')
        if pair['exact_pcm'] != (pcm['reference'][index] == pcm['native'][index]):
            raise ValueError('actual exactness differs')
        errors = []
        for arm in ('reference', 'native'):
            raw_path = ROOT / 'scores' / pair['score_files'][arm]
            raw = read(raw_path)
            if raw['pcm_sha256'] != pcm[arm][index] or raw['lock_sha256'] != lock_sha:
                raise ValueError('actual raw model output identity differs')
            try:
                transcript, embedding = audit_score(raw, pcm[arm][index], pair['language'], lock_sha)
            except (ValueError, KeyError, TypeError) as error:
                errors.append(str(error))
            else:
                label = 'candidate' if arm == 'native' else 'reference'
                if pair.get(label + '_transcript') != transcript or pair.get(label + '_embedding') != embedding:
                    raise ValueError('pair differs from real tokens/embeddings')
        if (pair['status'] == 'INCONCLUSIVE') != bool(errors):
            raise ValueError('incomplete model output was silently accepted or omitted')
        counts[pair['status']] += 1
        if errors:
            rejected.append({'concurrency': concurrency, 'index': index, 'errors': errors})
        languages.setdefault(pair['language'], []).append(pair)
    for language, rows in languages.items():
        group = summarize_group(rows, language)
        group.update(repetition=1, concurrency=concurrency, exact_pcm=sum(row['exact_pcm'] for row in rows))
        groups.append(group)
if groups != assessment['groups'] or counts['SCORED'] != assessment['scored_pairs'] or counts['INCONCLUSIVE'] != assessment['inconclusive_pairs'] or assessment['attempted_pairs'] != 64:
    raise ValueError('aggregate or coverage differs from raw model outputs')
controls = read(ROOT / 'negative-controls-corrected.json')
if controls['status'] != 'PASS' or len(controls['controls']) != 10 or any(row['status'] != 'REJECTED' for row in controls['controls']):
    raise ValueError('required actual-score rejection controls failed')
if (ROOT / 'negative-controls-corrected.exit').read_text().strip() != '0':
    raise ValueError('corrected checker actual exit was not zero')
with (ROOT / 'followup-cpu.log').open('xb') as log:
    cpu = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=SRC, stdout=log, stderr=log)
if cpu.returncode != 0 or current_identity(lock) != lock['identity']:
    raise ValueError('CPU contracts or frozen identity changed')
witness = read('/work/q1-device-witness05/witness.json')
native_life = read(ROOT / 'generated/r1-native/lifecycle.json')
if witness['status'] != 'MAPPED' or int(witness['nspid'].split()[-1]) != native_life['server_pid']:
    raise ValueError('physical NPU3 witness does not match the actual native lifecycle')
record = {'status': 'PASS', 'scope': 'Q1 evaluator completeness, real outputs and rejection contracts only; no runtime promotion',
    'tested_commit': source_manifest['commit'], 'freeze_sha256': lock_sha,
    'original_envelope': {'status': read(ROOT / 'results/evaluate/validation.json')['status'],
        'sha256': sha256(ROOT / 'results/evaluate/validation.json'),
        'reason': 'negative-control selector mistakenly chose a pair summary labelled SCORED; unchanged original FAIL'},
    'correction': 'select actual raw records requiring pcm_sha256/asr/speaker; all ten control mutations unchanged',
    'corrected_checker_sha256': sha256(Path('/work/q1-negative-controls-corrected.py')),
    'corrected_controls_sha256': sha256(ROOT / 'negative-controls-corrected.json'),
    'corrected_checker_actual_exit': 0, 'cpu_actual_exit': cpu.returncode,
    'attempted_pairs': 64, 'scored_pairs': counts['SCORED'], 'inconclusive_pairs': counts['INCONCLUSIVE'],
    'candidate_relative_quality': assessment['relative_quality'], 'groups': groups, 'rejected_records': rejected,
    'all_128_timed_requests_complete': True, 'all_64_timed_pairs_exact_PCM': True,
    'physical_device': 3, 'host_pid': witness['host_pid'], 'container_pid': native_life['server_pid'],
    'source_model_runtime_binaries_assets_unchanged': True, 'validator_sha256': sha256(Path(__file__))}
with (ROOT / 'followup-validation.json').open('x') as stream:
    stream.write(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
