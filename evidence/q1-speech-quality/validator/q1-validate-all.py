"""Actual A2 Q1 envelope, separate prepare and evaluate phases; not a fake scorer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--phase', choices=('prepare', 'evaluate'), required=True)
    args = p.parse_args()
    root = args.root
    src, build = root / 'source', root / 'build'
    out = root / 'results' / args.phase
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((src / 'source-manifest.json').read_text())
    sys.path.insert(0, str(src))
    from campaign import runtime_identity
    from speech_quality import current_identity, read

    def sha(path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                h.update(data)
        return h.hexdigest()

    class CommandFailure(Exception):pass

    record = {'validator_sha256':sha(Path(__file__)), 'status': 'INCONCLUSIVE', 'scope': 'Q1 harness validation, not runtime promotion or performance',
              'phase': args.phase, 'tested_commit': manifest['commit'], 'commands': [],
              'physical_device': 3, 'logical_device': 0}

    def save():
        (out / 'validation.json').write_text(json.dumps(record, indent=2) + '\n')

    def verify():
        for name, digest in manifest['files'].items():
            if sha(src / name) != digest:
                raise ValueError('frozen source differs: ' + name)

    def run(name, argv, timeout=2400, allowed=(0,)):
        verify()
        print('START', name, flush=True)
        began = time.monotonic()
        with (out / (name + '.log')).open('wb') as log:
            process = subprocess.Popen(list(map(str, argv)), cwd=src, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            timed_out = False
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGINT)
                try:
                    code = process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
        record['commands'].append({'name': name, 'argv': list(map(str, argv)), 'cwd': str(src),
                                   'exit': code, 'timed_out': timed_out,
                                   'wall_seconds': time.monotonic() - began})
        save()
        print('END', name, 'exit', code, flush=True)
        if timed_out:raise ValueError('required command timed out: ' + name)
        if code not in allowed:raise CommandFailure('required command failed: ' + name)

    py = sys.executable
    reference, model = Path('/work/reference'), Path('/model')
    try:
        verify()
        record['environment_before'] = runtime_identity(model, reference)
        if args.phase == 'prepare':
            run('cpu-suite', [py, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
            run('configure', ['cmake', '-S', src, '-B', build,
                             '-DPython3_EXECUTABLE=' + py, '-DCMAKE_BUILD_TYPE=Release'])
            run('build', ['cmake', '--build', build, '-j', '2'])
            run('ownership', [py, src / 'test_native_state.py', '-v'])
        else:
            freeze = root / 'freeze.json'
            boundary = root / 'generation.json'
            generated = root / 'generated'
            scores = root / 'scores'
            run('freeze', [py, src / 'speech_quality.py', 'freeze', '--models-root', '/work/quality-models',
                '--native-build', build, '--reference-root', reference, '--model', model,
                '--workload', '/work/c007/source/data/heldout-32.jsonl', '--score-all', '--output', freeze])
            run('compatibility', [py, '/work/q1-compatibility-generic.py', '--source', src, '--freeze', freeze,
                '--wav', '/work/c007/results/heldout/r1-reference/c4/00000.wav',
                '--output', root / 'compatibility.json'])
            run('generation', [py, src / 'speech_quality.py', 'generate', '--freeze', freeze,
                '--boundary', boundary, '--run', generated, '--concurrencies', '4', '16',
                '--requests', '32', '--repetitions', '1'], allowed=(0, 1))
            # A candidate failure is preserved. This evaluator delivery can pass only
            # if complete real scores exist and its negative contracts also pass.
            run('quality-score', [py, src / 'speech_quality.py', 'score', '--freeze', freeze,
                '--boundary', boundary, '--run', generated, '--output', scores], allowed=(0, 1), timeout=2400)
            result = read(scores / 'assessment.json')
            if (result.get('relative_quality') == 'INCONCLUSIVE' or not result.get('groups')
                    or result.get('identity_unchanged') is not True):
                raise ValueError('actual evaluator coverage incomplete: ' + str(result))
            if result.get('scored_pairs')!=64 or result.get('score_all') is not True:
                raise ValueError('required full independent scoring coverage missing')
            record['candidate_relative_quality'] = result
            run('negative-controls', [py, '/work/q1-negative-controls-generic.py', '--source', src, '--freeze', freeze,
                '--scores', scores, '--output', root / 'negative-controls.json'])
            if current_identity(read(freeze)) != read(freeze)['identity']:
                raise ValueError('frozen identity changed')
        record['binaries'] = {p.name: sha(p) for p in list(build.glob('_qtts_native*.so')) + [build / 'qtts']}
        record['environment_after'] = runtime_identity(model, reference)
        verify()
        if record['environment_before'] != record['environment_after']:
            raise ValueError('TTS environment drift')
        record['status'] = 'PASS'
    except CommandFailure as error:
        record.update(status='FAIL', error=str(error))
    except Exception as error:
        record.update(status='INCONCLUSIVE', error=f'{type(error).__name__}: {error}')
    finally:
        record['log_sha256'] = {p.name: sha(p) for p in out.glob('*.log')}
        save()
        print('VALIDATION', record['status'], record.get('error', ''), flush=True)
    return 0 if record['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
