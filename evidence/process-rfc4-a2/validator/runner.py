"""Run the process RFC's bounded CPU/content validation on the actual A2 host."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

root = Path('/work/policy-review-6119f1a')
source, results = root / 'source', root / 'results'
results.mkdir(exist_ok=False)
manifest = json.loads((root / 'source-manifest.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source():
    actual = {name: digest(source / name) for name in manifest['files']}
    if actual != manifest['files']:
        raise ValueError('actual synchronized source differs from recorded tested content')
    return hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()


record = {
    'status': 'INCONCLUSIVE',
    'scope': 'CPU control tests and process-document checks executed on A2; no NPU inference/performance claim',
    'tested_commit': manifest['git_commit'],
    'host': '8.92.7.131', 'container': 'zc-qwen3-tts-cpp-20261019',
    'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
    'npu_inference_executed': False,
    'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'environment': {k: os.environ.get(k) for k in ('ASCEND_RT_VISIBLE_DEVICES', 'ASCEND_HOME_PATH', 'OMP_NUM_THREADS')},
    'commands': [],
}
exit_code = 1
try:
    record['source_before_sha256'] = verify_source()
    for name, command in (
        ('cpu-suite', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('syntax', [sys.executable, '-m', 'compileall', '-q', '.']),
    ):
        with (results / (name + '.log')).open('wb') as log:
            result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        record['commands'].append({'name': name, 'argv': command, 'cwd': str(source),
                                   'exit': result.returncode, 'log': name + '.log'})
        if result.returncode:
            raise ValueError(name + ' failed')
    checked = []
    for name in ('AGENTS.md', 'README.md', '.github/pull_request_template.md', 'docs/pr-review-checklist.md'):
        path = source / name
        for target in re.findall(r'\[[^\]]+\]\(([^)\n]+)\)', path.read_text(encoding='utf-8')):
            if target.startswith(('https://', 'http://', '#')):
                continue
            resolved = (path.parent / target.split('#', 1)[0]).resolve()
            if not resolved.is_relative_to(source) or not resolved.is_file():
                raise ValueError(f'broken/outside local link: {name}: {target}')
            checked.append({'file': name, 'target': target})
    (results / 'local-links.json').write_text(json.dumps({'status': 'PASS', 'links': checked}, indent=2) + '\n')
    record['local_links'] = {'status': 'PASS', 'count': len(checked), 'evidence': 'local-links.json'}
    record['source_after_sha256'] = verify_source()
    if record['source_before_sha256'] != record['source_after_sha256']:
        raise ValueError('source changed during validation')
    record['status'] = 'PASS'
    exit_code = 0
except Exception as error:
    record.update(status='FAIL', error=f'{type(error).__name__}: {error}')
finally:
    record['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record['runner_exit'] = exit_code
    record['log_sha256'] = {p.name: digest(p) for p in results.iterdir() if p.is_file()}
    (results / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
sys.exit(exit_code)
