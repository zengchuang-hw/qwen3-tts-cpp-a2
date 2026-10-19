"""Preserve every Q1 attempt and real outputs; exclude public weights/binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--base', type=Path, default=Path('/work'))
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
args.output.mkdir(exist_ok=False)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


metadata, media, attempts = [], [], []
for number in range(1, 6):
    root = args.base / ('q1-attempt%02d' % number)
    outcomes = {phase: json.loads((root / 'results' / phase / 'validation.json').read_text())
                for phase in ('prepare', 'evaluate') if (root / 'results' / phase / 'validation.json').is_file()}
    attempts.append({'number': number, 'path': str(root), 'phase_outcomes': outcomes})
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if not path.is_file() or 'build' in relative.parts or '__pycache__' in relative.parts:
            continue
        if path.suffix in ('.wav', '.pcm'):
            media.append(path)
        elif path.suffix in ('.json', '.jsonl', '.log', '.txt', '.exit', '.py', '.cpp', '.h', '.md', '.yml'):
            metadata.append(path)
followup=args.base/'q1-attempt05/followup-validation.json'
if not followup.is_file():raise ValueError('final follow-up absent; do not archive live results')
attempts[-1]['followup_outcome']=json.loads(followup.read_text())
if attempts[-1]['followup_outcome']['status']!='PASS':raise ValueError('final harness qualification not PASS')
for pattern in ('q1-*.py', 'q1-*.log', 'q1-*.exit'):
    metadata.extend(path for path in args.base.glob(pattern) if path.is_file())
metadata.extend((args.base / 'quality-models' / 'asset-manifest.json',))
for root in args.base.glob('q1-device-witness*'):
    if root.is_dir():
        metadata.extend(path for path in root.rglob('*') if path.is_file() and path.suffix in ('.log', '.json'))
    elif root.is_file() and root.suffix == '.json':
        metadata.append(root)
archives = []
for kind, paths in (('metadata', sorted(set(metadata))), ('media', sorted(set(media)))):
    target = args.output / (kind + '.tar')
    with tarfile.open(target, 'x') as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(args.base)))
    archives.append({'kind': kind, 'path': str(target), 'bytes': target.stat().st_size,
                     'sha256': sha(target), 'files': len(paths),
                     'host_path': str(target).replace('/work', '/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019', 1)})
result = {'status': 'ARCHIVED', 'scope': 'Q1 tooling qualification only; candidate quality can remain INCONCLUSIVE',
          'attempts': attempts, 'archives': archives,
          'media': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in sorted(set(media))],
          'validators': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                         for path in sorted(set(metadata)) if path.parent == args.base and path.suffix == '.py']}
(args.output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'archives': archives}, indent=2), flush=True)
