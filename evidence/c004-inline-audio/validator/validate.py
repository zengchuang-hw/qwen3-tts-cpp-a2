import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

root = Path('/work/c004')
src, build, out = root / 'source', root / 'build', root / 'results'
out.mkdir(exist_ok=False)
manifest = json.loads((root / 'source-manifest.json').read_text())
sys.path.insert(0, str(src))
from campaign import runtime_identity

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_source():
    for name, expected in manifest['files'].items():
        if sha(src / name) != expected:
            raise ValueError('source identity mismatch: ' + name)

record = {'status': 'INCONCLUSIVE', 'tested_commit': manifest['commit'],
          'scope': 'inline callbacks, full-generation parity and bounded causal pilot; not upstream performance acceptance',
          'physical_device': 3, 'logical_device': 0, 'commands': []}
py = sys.executable
reference, model = Path('/work/reference'), Path('/model')
workload = reference / 'evidence/campaign-20261017/plan/workload-128.jsonl'

def run(name, command, timeout=1200):
    verify_source()
    print('START', name, flush=True)
    began = time.monotonic()
    with (out / (name + '.log')).open('wb') as log:
        result = subprocess.run(command, cwd=src, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    record['commands'].append({'name': name, 'argv': list(map(str, command)),
        'cwd': str(src), 'exit': result.returncode, 'wall_seconds': time.monotonic() - began})
    (out / 'progress.json').write_text(json.dumps(record, indent=2) + '\n')
    print('END', name, 'exit', result.returncode, flush=True)
    if result.returncode:
        raise ValueError(name + ' failed')

try:
    verify_source()
    record['environment_before'] = runtime_identity(model, reference)
    run('cpu-suite', [py, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    run('configure', ['cmake', '-S', str(src), '-B', str(build), '-DPython3_EXECUTABLE=' + py,
                      '-DCMAKE_BUILD_TYPE=Release'])
    run('build', ['cmake', '--build', str(build), '-j', '2'])
    record['binaries'] = {p.name: sha(p) for p in list(build.glob('_qtts_native*.so')) + [build / 'qtts']}
    run('ownership', [py, str(src / 'test_native_state.py'), '-v'])
    run('rotary', [py, str(src / 'rope_probe.py'), '--output', str(out / 'rotary.json')])
    common = ['--reference-root', str(reference), '--native-build', str(build), '--model', str(model),
              '--workload', str(workload)]
    for cancelled in (False, True):
        suffix = '-cancel' if cancelled else ''
        for arm in ('reference', 'native'):
            target = out / (arm + suffix)
            command = [py, str(src / 'probe.py'), *common, '--engine', arm, '--output', str(target),
                       '--predictor-rope', 'paired']
            if arm == 'native':
                command += ['--audio-delivery', 'inline', '--verify-inline']
            if cancelled:
                command.append('--cancel-and-reuse')
            run(arm + suffix, command)
        left = out / ('reference' + suffix)
        right = out / ('native' + suffix)
        comparisons = []
        for path in sorted(left.glob('*.wav')):
            other = right / path.name
            def pcm(p):
                with wave.open(str(p), 'rb') as audio:
                    if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
                        raise ValueError('wrong audio format')
                    return audio.readframes(audio.getnframes())
            a, b = pcm(path), pcm(other)
            if not a or a != b:
                raise ValueError('complete WAV differs: ' + str(other))
            comparisons.append({'file': path.name, 'pcm_sha256': hashlib.sha256(a).hexdigest(), 'bytes': len(a)})
        if len(comparisons) != 4 or len(list(right.glob('*.wav'))) != 4:
            raise ValueError('probe coverage differs')
        record['comparison' + suffix] = {'status': 'PASS', 'scope': 'four complete PCM waveforms', 'rows': comparisons}
    run('cli', [str(build / 'qtts'), '--reference-root', str(reference), '--model', str(model),
                '--workload', str(workload), '--slots', '4', '--requests', '4',
                '--predictor-rope', 'paired', '--output', str(out / 'cli')])
    if len(list((out / 'cli').glob('*.wav'))) != 4:
        raise ValueError('CLI did not retain four WAVs')
    run('emit-error', [py, str(src / 'probe.py'), *common, '--engine', 'native',
        '--predictor-rope', 'paired', '--audio-delivery', 'inline', '--verify-inline', '--fail-emit',
        '--output', str(out / 'emit-error')])
    error_probe = json.loads((out / 'emit-error/probe.json').read_text())
    if error_probe['status'] != 'PASS' or error_probe['completed_requests'] != 0:
        raise ValueError('intentional callback propagation/cleanup failed')
    run('causal-pilot', [py, str(src / 'campaign.py'), *common,
        '--predictor-rope', 'paired', '--audio-delivery', 'inline', '--reference-engine', 'native-buffered',
        '--concurrencies', '4', '16', '32', '64', '--requests', '128', '--repetitions', '1',
        '--output', str(out / 'causal-pilot')], timeout=2400)
    from assess import assess
    assessment = assess(out / 'causal-pilot')
    (out / 'causal-pilot/assessment.json').write_text(json.dumps(assessment, indent=2) + '\n')
    if assessment['status'] != 'INCONCLUSIVE' or assessment['relative_quality'] != 'PASS_EXACT_PCM':
        raise ValueError('causal pilot integrity/quality or scope differs')
    nonreg = []
    for row in assessment['cohorts']:
        control, candidate = row['reference'][0], row['native'][0]
        ratio = candidate['throughput_frames_s'] / control['throughput_frames_s']
        ttfa = candidate['ttfa_p95_ms'] / control['ttfa_p95_ms']
        nonreg.append({'concurrency': row['concurrency'], 'throughput_ratio': ratio, 'p95_ratio': ttfa,
                       'pass': ratio >= .95 and ttfa <= 1.05})
    record['causal_pilot_nonregression'] = nonreg
    if not all(row['pass'] for row in nonreg):
        raise ValueError('causal pilot violates frozen per-iteration nonregression gate')
    verify_source()
    record['environment_after'] = runtime_identity(model, reference)
    if record['environment_before'] != record['environment_after']:
        raise ValueError('runtime/model environment changed')
    record['status'] = 'PASS'
except Exception as error:
    record['status'] = 'FAIL'
    record['error'] = f'{type(error).__name__}: {error}'
finally:
    record['log_sha256'] = {p.name: sha(p) for p in out.glob('*.log')}
    (out / 'validation.json').write_text(json.dumps(record, indent=2) + '\n')
    print('VALIDATION', record['status'], record.get('error', ''), flush=True)
sys.exit(0 if record['status'] == 'PASS' else 1)
