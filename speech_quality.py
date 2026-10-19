"""Freeze, generate and score independent Q1 evidence. Configuration is CLI-only."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from assess import EvidenceViolation, audit_cohort
from campaign import runtime_identity, source_identity
from quality_core import (MODEL_REVISIONS, PROTOCOL, audit_boundary, audit_score, compare_group, sha256)
from serve import load_reference

ROOT = Path(__file__).resolve().parent
EXPECTED_PACKAGES = {'torch': '2.10.0+cpu', 'transformers': '4.57.3', 'tokenizers': '0.22.2',
                     'numpy': '2.5.3', 'scipy': '1.18.1', 'librosa': '1.0.0',
                     'safetensors': '0.8.0', 'huggingface-hub': '0.36.2'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_new(path, record):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def environment():
    packages = {name: importlib.metadata.version(name) for name in EXPECTED_PACKAGES}
    if packages != EXPECTED_PACKAGES or sys.version_info[:3] != (3, 12, 13):
        raise ValueError('Q1 requires the prior RFC17 Python/package versions; requalification needed')
    return {'python': sys.version, 'platform': platform.platform(),
            'packages': packages}


def workload_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows or any(not isinstance(row.get('input'), str) or not row['input'].strip()
                       or row.get('language') not in ('English', 'Chinese') for row in rows):
        raise ValueError('explicit English/Chinese input texts are required')
    return rows


def assets(root, model_lock):
    expected = read(model_lock)
    definition_sha = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if definition_sha != '4bdae625949473d344c016c85f4b64497be3a3d529b0eab6383f646c760bc40b':
        raise ValueError('Q1 complete public asset definition differs')
    if {row['model']: row['revision'] for row in expected} != MODEL_REVISIONS or len(expected) != 2:
        raise ValueError('Q1 model revisions differ')
    result = []
    for model in expected:
        directory = root / (model['model'].replace('/', '--') + '-' + model['revision'][:12])
        files = []
        for item in model['files']:
            name = item['rfilename']
            if model['model'] == 'openai/whisper-small' and name == 'pytorch_model.bin':
                continue
            if Path(name).name != name:
                raise ValueError('model asset escapes root')
            path = directory / name
            if path.stat().st_size != item['size']:
                raise ValueError('model asset size differs: ' + str(path))
            digest = sha256(path)
            if item['lfs'] is not None:
                if digest != item['lfs']['sha256']:
                    raise ValueError('model weight SHA256 differs')
            else:
                data = path.read_bytes()
                blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                if blob != item['blobId']:
                    raise ValueError('model asset Git blob differs')
            files.append({'file': name, 'bytes': path.stat().st_size, 'sha256': digest})
        result.append({'model': model['model'], 'revision': model['revision'],
                       'path': str(directory.resolve()), 'files': files})
    return result


def current_identity(lock):
    return {'assets': assets(Path(lock['models_root']), Path(lock['model_lock'])),
            'environment': environment(),
            'source': source_identity(ROOT, Path(lock['native_build'])),
            'runtime': runtime_identity(Path(lock['model']), Path(lock['reference_root'])),
            'workload_sha256': sha256(lock['workload']),
            'model_lock_sha256': sha256(lock['model_lock'])}


def checked_lock(path):
    lock = read(path)
    if lock['protocol'] != PROTOCOL or lock['status'] != 'PREGEN_FROZEN':
        raise ValueError('Q1 pre-generation lock is missing')
    load_reference(Path(lock['reference_root']))
    if current_identity(lock) != lock['identity']:
        raise ValueError('source, model, workload or environment changed since freeze')
    return lock


def freeze(args):
    lock = {'status': 'PREGEN_FROZEN', 'protocol': PROTOCOL,
            **{name: str(getattr(args, name).resolve()) for name in (
                'models_root', 'model_lock', 'native_build', 'model', 'reference_root', 'workload')},
            'predictor_rope': args.predictor_rope, 'rotary_head_tile': args.rotary_head_tile,
            'audio_delivery': args.audio_delivery}
    load_reference(Path(lock['reference_root']))
    workload_rows(lock['workload'])
    lock['identity'] = current_identity(lock)
    lock['frozen_unix_ns'] = time.time_ns()
    write_new(args.output, lock)
    return {'status': 'PREGEN_FROZEN', 'lock_sha256': sha256(args.output)}


def generate(args):
    lock = checked_lock(args.freeze)
    if args.run.exists():
        raise ValueError('generation output must not exist')
    command = [sys.executable, str(ROOT / 'campaign.py'), '--reference-root', lock['reference_root'],
               '--native-build', lock['native_build'], '--model', lock['model'],
               '--workload', lock['workload'], '--output', str(args.run.resolve()),
               '--predictor-rope', lock['predictor_rope'], '--rotary-head-tile', lock['rotary_head_tile'],
               '--audio-delivery', lock['audio_delivery'], '--requests', str(args.requests),
               '--repetitions', str(args.repetitions), '--concurrencies', *map(str, args.concurrencies),
               '--port', str(args.port)]
    boundary = {'status': 'STARTED', 'protocol': PROTOCOL, 'lock_sha256': sha256(args.freeze),
                'run': str(args.run.resolve()), 'command': command,
                'requests': args.requests, 'repetitions': args.repetitions,
                'concurrencies': args.concurrencies, 'started_unix_ns': time.time_ns()}
    if boundary['started_unix_ns'] <= lock['frozen_unix_ns']:
        raise ValueError('clock order does not establish pre-generation freeze')
    write_new(args.boundary, boundary)
    # Keep STARTED immutable; a separate terminal record includes the true exit.
    with Path(str(args.boundary) + '.log').open('xb') as log:
        # Campaign owns its server groups and enforces readiness/benchmark/close
        # bounds. Killing only this parent at an outer deadline would orphan them.
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log)
    terminal = {**boundary, 'status': 'COMPLETED' if result.returncode == 0 else 'FAIL',
                'actual_exit': result.returncode, 'finished_unix_ns': time.time_ns(),
                'identity_unchanged': current_identity(lock) == lock['identity'],
                'boundary_sha256': sha256(args.boundary)}
    write_new(str(args.boundary) + '.terminal.json', terminal)
    return terminal


def score(args):
    lock = checked_lock(args.freeze)
    boundary, terminal = read(args.boundary), read(str(args.boundary) + '.terminal.json')
    digest = sha256(args.freeze)
    audit_boundary(lock, boundary, terminal, digest, sha256(args.boundary), str(args.run.resolve()),
                   (args.run / 'runspec.json').stat().st_mtime_ns)
    spec = read(args.run / 'runspec.json')
    if (spec['workload_sha256'] != lock['identity']['workload_sha256']
            or spec['reference_engine'] != 'upstream'
            or spec['requests'] != boundary['requests'] or spec['repetitions'] != boundary['repetitions']
            or spec['concurrencies'] != boundary['concurrencies']
            or read(args.run / 'identity.json') != lock['identity']['source']
            or read(args.run / 'environment-identity.json') != lock['identity']['runtime']
            or any(spec[key] != lock[key] for key in ('predictor_rope', 'rotary_head_tile', 'audio_delivery'))):
        raise ValueError('generated campaign is outside the frozen source/workload scope')
    workload = workload_rows(lock['workload'])
    if len(workload) < spec['requests']:
        raise ValueError('Q1 requires explicit non-repeated workload coverage')
    args.output.mkdir(parents=True, exist_ok=False)
    # Dependencies are imported only after all control/identity checks pass.
    from speech_scorer import SpeechScorer
    scorer = None
    summaries, pairs, observed_failure = [], [], terminal['actual_exit'] != 0
    args.observed_execution_failure = observed_failure
    for repetition in range(1, spec['repetitions'] + 1):
        roots = {arm: args.run / f'r{repetition}-{arm}' for arm in ('reference', 'native')}
        for root in roots.values():
            life = read(root / 'lifecycle.json')
            if life['server_exit'] is None:
                raise ValueError('actual server exit evidence missing')
            observed_failure |= life['server_exit'] != 0 or life['status'] != 'COMPLETED'
            args.observed_execution_failure |= observed_failure
            if sorted(c['concurrency'] for c in life['cohorts']) != sorted(spec['concurrencies']):
                raise ValueError('server cohort coverage incomplete')
            observed_failure |= any(c['exit'] != 0 for c in life['cohorts'])
        for concurrency in spec['concurrencies']:
            hashes = {arm: audit_cohort(root / f'c{concurrency}', spec['requests'], concurrency,
                                        spec['workload_sha256'])[1] for arm, root in roots.items()}
            for root in roots.values():
                actual = read(root / f'c{concurrency}' / 'results.json')['requests']
                if any(row['input'] != workload[row['index']]['input'] for row in actual):
                    raise EvidenceViolation('recorded generation input differs from frozen ground truth')
            inexact = [i for i in range(spec['requests']) if hashes['reference'][i] != hashes['native'][i]]
            if not inexact:
                summaries.append({'repetition': repetition, 'concurrency': concurrency,
                                  'exact_pcm': spec['requests'], 'status': 'PASS_EXACT_PCM'})
                continue
            if scorer is None:
                scorer = SpeechScorer(lock['identity']['assets'], digest)
                write_new(args.output / 'scorer-identity.json', scorer.identity)
            groups = {}
            for index in range(spec['requests']):
                item = workload[index]
                language = item.get('language')
                if language not in ('English', 'Chinese'):
                    raise ValueError('unsupported workload language')
                exact = index not in inexact
                records = {}
                for arm in ('reference', 'native'):
                    if arm == 'native' and exact:
                        records[arm] = records['reference']
                        continue
                    record = scorer.score(roots[arm] / f'c{concurrency}' / f'{index:05d}.wav', language)
                    audit_score(record, hashes[arm][index], language, digest)
                    records[arm] = record
                    key = f"{record['pcm_sha256']}-{language}.json"
                    if not (args.output / key).exists():
                        write_new(args.output / key, record)
                ref_text, ref_embedding = audit_score(records['reference'], hashes['reference'][index], language, digest)
                cand_text, cand_embedding = audit_score(records['native'], hashes['native'][index], language, digest)
                row = {'repetition': repetition, 'concurrency': concurrency, 'index': index,
                       'text': item['input'], 'language': language, 'exact_pcm': exact,
                       'reference_pcm_sha256': hashes['reference'][index],
                       'candidate_pcm_sha256': hashes['native'][index],
                       'reference_transcript': ref_text, 'candidate_transcript': cand_text,
                       'reference_embedding': ref_embedding, 'candidate_embedding': cand_embedding}
                groups.setdefault(language, []).append(row)
                pairs.append(row)
                write_new(args.output / f'r{repetition}-c{concurrency}-{index:05d}.json', row)
            for language, rows in groups.items():
                result = compare_group(rows, language)
                result.update(repetition=repetition, concurrency=concurrency,
                              exact_pcm=sum(row['exact_pcm'] for row in rows))
                summaries.append(result)
                observed_failure |= result['status'] == 'FAIL'
    unchanged = current_identity(lock) == lock['identity']
    if not unchanged:
        raise ValueError('source/environment/assets changed while scoring')
    return {'status': 'FAIL' if observed_failure else 'PASS', 'protocol': PROTOCOL,
            'scope': 'Q1 relative quality only; no performance or subjective-quality acceptance',
            'lock_sha256': digest, 'boundary_sha256': sha256(args.boundary),
            'groups': summaries, 'scored_pairs': len(pairs), 'identity_unchanged': unchanged,
            'generation_actual_exit': terminal['actual_exit']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    f = sub.add_parser('freeze')
    for name in ('models-root', 'native-build', 'model', 'reference-root', 'workload', 'output'):
        f.add_argument('--' + name, type=Path, required=True)
    f.add_argument('--model-lock', type=Path, default=ROOT / 'data/q1-models.json')
    f.add_argument('--predictor-rope', choices=['native', 'paired'], default='paired')
    f.add_argument('--rotary-head-tile', choices=['4', '8', '16', 'auto'], default='auto')
    f.add_argument('--audio-delivery', choices=['buffered', 'inline'], default='inline')
    g = sub.add_parser('generate')
    for name in ('freeze', 'boundary', 'run'):
        g.add_argument('--' + name, type=Path, required=True)
    g.add_argument('--concurrencies', type=int, nargs='+', default=[4, 16])
    g.add_argument('--requests', type=int, default=32)
    g.add_argument('--repetitions', type=int, default=1)
    g.add_argument('--port', type=int, default=8199)
    s = sub.add_parser('score')
    for name in ('freeze', 'boundary', 'run', 'output'):
        s.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'generate' and (args.requests < 1 or args.repetitions < 1
            or not args.concurrencies or len(set(args.concurrencies)) != len(args.concurrencies)
            or min(args.concurrencies) < 1 or max(args.concurrencies) > 64):
        parser.error('invalid generation bounds')
    try:
        result = globals()[args.action](args)
    except EvidenceViolation as error:
        result = {'status': 'FAIL', 'error': f'{type(error).__name__}: {error}'}
    except Exception as error:
        result = {'status': 'FAIL' if getattr(args, 'observed_execution_failure', False) else 'INCONCLUSIVE',
                  'relative_quality': 'INCONCLUSIVE', 'error': f'{type(error).__name__}: {error}'}
    if args.action == 'score':
        args.output.mkdir(parents=True, exist_ok=True)
        write_new(args.output / 'assessment.json', result)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
    return 0 if result['status'] in ('PASS', 'PREGEN_FROZEN', 'COMPLETED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
