"""P1 documentation audit; CPU metadata replay, not fresh NPU/WAV validation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics as stats

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--inputs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
load = lambda path: json.loads(path.read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = load(args.source/'source-manifest.json')
for name, digest in manifest['files'].items():
    assert sha(args.source/name) == digest, name
inputs = load(args.inputs/'input-manifest.json')
for name, digest in inputs['files'].items():
    assert sha(args.inputs/name) == digest, name
assert sha(Path(__file__)) == inputs['validator_sha256']
root = args.inputs/'formal'
a = load(root/'assessment.json')
assert a['status'] == 'PASS' and a['formal_coverage'] is True
assert [c['concurrency'] for c in a['cohorts']] == [1, 2, 4, 8, 16, 32, 64]
spec = load(root/'runspec.json')
assert spec['requests'] == 128 and spec['repetitions'] == 3
assert spec['workload_sha256'] == '5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7'

def percentile(v):
    v = sorted(v)
    x = (len(v)-1)*.95
    lo = int(x)
    return v[lo] + (v[min(lo+1, len(v)-1)]-v[lo])*(x-lo)

actual = {}
hashes = {}
timed = 0
for trial in range(1, 4):
    for arm in ('reference', 'native'):
        folder = root/f'r{trial}-{arm}'
        life = load(folder/'lifecycle.json')
        assert life['status'] == 'COMPLETED' and life['server_exit'] == 0
        assert sorted(v['concurrency'] for v in life['cohorts']) == [1,2,4,8,16,32,64]
        assert all(v['exit'] == 0 for v in life['cohorts'])
        for c in a['cohorts']:
            concurrency = c['concurrency']
            data = load(folder/f'c{concurrency}'/'results.json')
            cohort_spec = load(folder/f'c{concurrency}'/'runspec.json')
            assert cohort_spec['workload_sha256'] == spec['workload_sha256']
            assert cohort_spec['concurrency'] == concurrency and cohort_spec['requests'] == 128
            assert cohort_spec['frame_rate'] == 12.5 and cohort_spec['sample_rate'] == 24000
            rows = data['requests']
            assert sorted(v['index'] for v in rows) == list(range(128))
            for row in rows:
                assert row['success'] is True
                assert row['terminal']['finish_reason'] == 'stop'
                assert row['terminal']['type'] == 'speech.audio.done'
                assert row['pcm_bytes'] > 0 and len(row['pcm_sha256']) == 64
                assert math.isclose(row['pcm_bytes']/48000, row['audio_seconds'])
            metrics = {
                'throughput_frames_s': sum(v['audio_seconds'] for v in rows)*12.5/data['metrics']['wall_seconds'],
                'ttfa_p95_ms': percentile([v['ttfa_seconds']*1000 for v in rows]),
            }
            for key, value in metrics.items():
                assert math.isclose(value, data['metrics'][key], rel_tol=1e-8)
                assert math.isclose(value, c[arm][trial-1][key], rel_tol=1e-8)
            actual[trial, arm, concurrency] = metrics
            hashes[trial, arm, concurrency] = {v['index']: v['pcm_sha256'] for v in rows}
            timed += len(rows)

table = []
for c in a['cohorts']:
    concurrency = c['concurrency']
    r = [actual[t,'reference',concurrency] for t in range(1,4)]
    n = [actual[t,'native',concurrency] for t in range(1,4)]
    assert all(hashes[t,'reference',concurrency] == hashes[t,'native',concurrency] for t in range(1,4))
    gain = min(v['throughput_frames_s'] for v in n)/max(v['throughput_frames_s'] for v in r)-1
    change = max(v['ttfa_p95_ms'] for v in n)/min(v['ttfa_p95_ms'] for v in r)-1
    assert gain > .05 and change <= .05
    assert math.isclose(gain+1, c['min_native_vs_max_reference_throughput'])
    assert math.isclose(change+1, c['max_native_vs_min_reference_ttfa_p95'])
    tp = lambda x: f"{stats.mean(v['throughput_frames_s'] for v in x):.2f} ± {stats.stdev(v['throughput_frames_s'] for v in x):.2f}"
    p95 = lambda x: f"{stats.mean(v['ttfa_p95_ms'] for v in x):.2f}"
    table.append(f'| {concurrency} | {tp(r)} | {tp(n)} | {gain*100:+.2f}% | {p95(r)} | {p95(n)} | {change*100:+.2f}% |')
readme = (args.source/'README.md').read_text(encoding='utf-8')
assert re.findall(r'^\| \d+ \|.*$', readme, re.M) == table
for required in ('one physical Ascend 910B3', 'mean of three per-trial p95s',
                 'min(candidate throughput) / max(reference throughput) - 1',
                 'max(candidate p95) / min(reference p95) - 1',
                 '547270db4d41602f868dddb0f8c406858c17d29c',
                 'b4451682abac651f26046f8d27467de3f007e1e7',
                 '0c0e3051f131929182e2c023b9537f8b1c68adfe',
                 '5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7',
                 'No new performance run', 'eight nonexact C16', 'remains blocked',
                 'not independent speech quality', '--rotary-head-tile auto',
                 '64 English/Ryan + 64 Chinese/Vivian'):
    assert required in readme, required
tracked = set(inputs['tracked_paths'])
for target in re.findall(r'\]\(([^)]+)\)', readme):
    if '://' in target or target.startswith('#'):
        continue
    name = target.split('#')[0].rstrip('/')
    assert name in tracked or any(v.startswith(name+'/') for v in tracked), target
assert timed == 5376
report = {'status': 'PASS', 'scope': __doc__, 'tested_commit': manifest['commit'],
          'source_files': len(manifest['files']), 'input_files': len(inputs['files']),
          'timed_records_recomputed': timed, 'paired_recorded_pcm_hashes': timed//2,
          'table_rows': table, 'fresh_npu_inference': False, 'fresh_wav_byte_audit': False}
args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
