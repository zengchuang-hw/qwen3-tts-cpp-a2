"""Audit bounded cancellation/reuse evidence from actual audio; stdlib only."""
import argparse
import hashlib
import json
from pathlib import Path
import wave


WORKLOAD_SHA256 = "5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7"


class Incomplete(Exception):
    pass


class Violation(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def contained(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise Violation('audio path escapes its own trial')
    return path


def audit(root, cycles=16, warmup=2):
    data = json.loads((root / 'stress.json').read_text())
    if data['workload_sha256'] != WORKLOAD_SHA256:
        raise Violation('stress workload is outside the frozen contract')
    if data['execution'] == 'FAILED' and data.get('failure_kind') in {'contract','cleanup'}:
        raise Violation('recorded stress contract or cleanup failure: '+data.get('error',data.get('cleanup_error','')))
    if data['execution'] != 'COMPLETED':
        raise Incomplete('stress process did not complete')
    if (data['measured_cycles'], data['warmup_cycles'], data['slots']) != (cycles, warmup, 16):
        raise Violation('stress configuration differs from frozen contract')
    rows = data['cycles']
    if len(rows) != cycles + warmup or {r['cycle'] for r in rows} != set(range(cycles + warmup)):
        raise Incomplete('cycle coverage is incomplete')
    outputs, cancelled, paths, measured = {}, {}, set(), []
    for row in rows:
        index = row['cycle']
        if row['warmup'] != (index < warmup) or row['state_after'] != []:
            raise Violation('warmup label or drained state differs')
        expected = {(i, int(i in {1, 5, 9, 13})) for i in range(16)}
        records = row['completions']
        if len(records) != 16 or {(r['id'], r['generation']) for r in records} != expected:
            raise Violation('complete generations are missing, duplicated or unexpected')
        for record in records:
            if record['finish_reason'] != 'stop' or record['frames'] < 1:
                raise Violation('truncated/failed output is not complete generation')
            path = contained(root, record['file'])
            if path in paths:
                raise Violation('distinct generations alias the same audio file')
            paths.add(path)
            with wave.open(str(path), 'rb') as audio:
                if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
                    raise Violation('unexpected WAV format')
                pcm = audio.readframes(audio.getnframes())
                if len(pcm) != audio.getnframes() * 2:
                    raise Violation('truncated WAV')
            if (not pcm or not any(pcm) or len(pcm) != record['pcm_bytes'] or digest(pcm) != record['pcm_sha256']
                    or len(pcm) != record['frames'] * 1920 * 2):
                raise Violation('actual WAV, declared PCM or codec frames differ')
            offset = 0
            for chunk in record['chunks']:
                size = chunk['bytes']
                if size < 2 or size % 2 or offset + size > len(pcm):
                    raise Violation('invalid stream chunk coverage')
                if digest(pcm[offset:offset + size]) != chunk['sha256']:
                    raise Violation('actual WAV differs from emitted chunk')
                offset += size
            if offset != len(pcm):
                raise Violation('stream does not reconstruct complete PCM')
            if index >= warmup:
                outputs[(index, record['id'], record['generation'])] = (digest(pcm), record['frames'], str(path))
        records = row['cancellations']
        if len(records) != 4 or {(r['id'], r['generation']) for r in records} != {(i, 0) for i in (1, 5, 9, 13)}:
            raise Violation('cancellation/reuse coverage differs')
        for record in records:
            if record['status'] != 'CANCELLED':
                raise Violation('cancelled prefix must not be declared a successful generation')
            path = contained(root, record['file'])
            if path in paths:
                raise Violation('cancelled and complete artifacts alias')
            paths.add(path)
            pcm = path.read_bytes()
            if len(pcm) != 2 * 1920 * 2 or record['pcm_bytes'] != len(pcm) or digest(pcm) != record['pcm_sha256']:
                raise Violation('actual two-frame cancellation prefix differs')
            if index >= warmup:
                cancelled[(index, record['id'])] = digest(pcm)
        memory = row['memory']
        if any(type(memory[k]) is not int or memory[k] < 0 for k in ('allocated', 'reserved')):
            raise Violation('invalid memory sample')
        if index >= warmup:
            measured.append(row)
    structures = {json.dumps(row['structure'], sort_keys=True) for row in measured}
    growth = max(row['memory']['allocated'] for row in measured) - min(row['memory']['allocated'] for row in measured)
    memory_status = 'INCONCLUSIVE' if len(structures) != 1 else 'FAIL' if growth > 64 * 1024 * 1024 else 'PASS'
    return {'outputs': outputs, 'cancelled': cancelled, 'memory': memory_status,
            'allocated_range_bytes': growth, 'workload_sha256': data['workload_sha256']}


def compare(reference, candidate, cycles=16, warmup=2):
    if reference.resolve() == candidate.resolve():
        raise Violation('candidate aliases reference trial')
    left, right = audit(reference, cycles, warmup), audit(candidate, cycles, warmup)
    if left['workload_sha256'] != right['workload_sha256']:
        raise Violation('stress inputs differ')
    if left['outputs'].keys() != right['outputs'].keys():
        raise Violation('paired complete generation coverage differs')
    for key in left['outputs']:
        a, b = left['outputs'][key], right['outputs'][key]
        if a[2] == b[2]:
            raise Violation('paired trials alias the same WAV')
        if a[:2] != b[:2]:
            raise Violation('paired complete PCM differs')
    memory = [left['memory'], right['memory']]
    status = 'FAIL' if 'FAIL' in memory else 'INCONCLUSIVE' if 'INCONCLUSIVE' in memory else 'PASS'
    return {'status': status, 'scope': 'bounded direct-core cancellation/reuse; not HTTP disconnect or production soak',
            'measured_cycles':cycles, 'warmup_cycles':warmup, 'matched_complete_outputs': len(left['outputs']), 'cancelled_prefixes_per_arm': len(left['cancelled']),
            'prefixes_exact_diagnostic': left['cancelled'] == right['cancelled'],
            'memory': {'reference': left['memory'], 'candidate': right['memory'],
                       'reference_allocated_range_bytes': left['allocated_range_bytes'],
                       'candidate_allocated_range_bytes': right['allocated_range_bytes']},
            'performance': 'NOT_EVALUATED'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cycles', type=int, default=16)
    p.add_argument('--warmup-cycles', type=int, default=2)
    args = p.parse_args()
    if args.cycles < 1 or args.warmup_cycles < 0:
        p.error('positive measured cycles and nonnegative warmup required')
    try:
        result = compare(args.reference, args.candidate, args.cycles, args.warmup_cycles)
    except Violation as error:
        result = {'status': 'FAIL', 'error': str(error)}
    except (Incomplete, OSError, ValueError, KeyError, TypeError, wave.Error) as error:
        result = {'status': 'INCONCLUSIVE', 'error': f'{type(error).__name__}: {error}'}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return {'PASS': 0, 'FAIL': 1, 'INCONCLUSIVE': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())