"""Archive both R1 source epochs and actual SDK experiments without aliasing media."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
base = Path('/work')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


metadata, media, attempts = [], [], []
for number in (1, 2):
    root = base / ('r1-attempt%02d' % number)
    validation = json.loads((root / 'results/validation.json').read_text())
    if validation['status'] != 'PASS':
        raise ValueError('R1 required checks not finished PASS')
    attempts.append({'root': str(root), 'validation': validation})
    metadata.extend((root / 'source-manifest.json', root / 'cpu-validation.py'))
    for path in (root / 'results').rglob('*'):
        if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts:
            continue
        if path.suffix in ('.wav', '.pcm'):
            media.append(path)
        elif path.suffix in ('.json', '.jsonl', '.log', '.txt', '.exit', '.py', '.md'):
            metadata.append(path)
for pattern in ('r1-*.py', 'r1-*.log', 'r1-*.exit'):
    metadata.extend(path for path in base.glob(pattern) if path.is_file())
preflight = base / 'r1-sdk-preflight'
for path in (preflight / 'results02').rglob('*'):
    if path.is_file() and '.git' not in path.parts and '__pycache__' not in path.parts and path.suffix in ('.json', '.jsonl', '.log', '.txt', '.py', '.md'):
        metadata.append(path)
metadata.append(preflight / 'source/rsi_cpu_validation.py')
witness = base / 'r1-device-witness02'
record = json.loads((witness / 'witness.json').read_text())
if record['status'] != 'MAPPED':
    raise ValueError('actual native device witness unavailable')
final = attempts[-1]['validation']
experiment = Path(final['actual_runner_directory'])
life = json.loads((experiment / 'candidate/trial-001/tts/lifecycle.json').read_text())
if int(record['nspid'].split()[-1]) != life['server_pid']:
    raise ValueError('device witness differs from actual runner lifecycle')
metadata.extend(path for path in witness.rglob('*') if path.is_file())
args.output.mkdir(exist_ok=False)
archives = []
for kind, paths in (('metadata', sorted(set(metadata))), ('media', sorted(set(media)))):
    archive_path = args.output / (kind + '.tar')
    with tarfile.open(archive_path, 'x') as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(base)))
    archives.append({'kind': kind, 'path': str(archive_path), 'bytes': archive_path.stat().st_size,
                     'files': len(paths), 'sha256': sha(archive_path),
                     'host_path': str(archive_path).replace('/work', '/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019', 1)})
manifest = {'status': 'ARCHIVED', 'scope': 'actual pinned InferRSI adapter qualification; no new formal speed acceptance',
    'attempts': attempts, 'archives': archives, 'device_witness': record,
    'media': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in sorted(set(media))],
    'validators': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                   for path in sorted(set(metadata)) if path.suffix == '.py']}
(args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'status': manifest['status'], 'archives': archives}, indent=2), flush=True)
