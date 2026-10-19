"""Exact rotary tiling checks and warmed graph-chain L1 timing; never E2E."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--iterations', type=int, default=32)
    p.add_argument('--chain', type=int, default=32)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if min(args.iterations, args.chain) < 1 or args.repetitions < 3:
        p.error('positive iterations/chain and at least three timings required')
    import torch
    import torch_npu
    from predictor_rope import paired_rotary
    torch.npu.set_device(0)
    torch.manual_seed(20261019)
    checks, timings = [], []
    with torch.inference_mode():
        for width in (64, 128):
            for batch in (1, 4, 16, 32, 64):
                for length in (1, 2):
                    for shared in (True, False):
                        q = torch.randn(batch, length, 16, width, device='npu:0', dtype=torch.bfloat16)
                        k = torch.randn(batch, length, 8, width, device='npu:0', dtype=torch.bfloat16)
                        angle = torch.randn(1 if shared else batch, length, width // 2, device='npu:0')
                        c = torch.cat((angle.cos(), angle.cos()), -1).bfloat16()
                        s = torch.cat((angle.sin(), angle.sin()), -1).bfloat16()
                        def native():
                            return tuple(torch_npu.npu_rotary_mul(t, c.unsqueeze(2), s.unsqueeze(2)) for t in (q, k))
                        cases = [('native', native)] + [(str(tile), lambda tile=tile: paired_rotary(q, k, c, s, head_tile=tile))
                                                       for tile in (4, 8, 16)]
                        frozen = [t.clone() for t in (q, k, c, s)]
                        for label, fn in cases:
                            for value, original in zip((q, k, c, s), frozen):
                                value.copy_(original)
                            for _ in range(3):
                                fn()
                            torch.npu.synchronize()
                            stream = torch.npu.Stream()
                            stream.wait_stream(torch.npu.current_stream())
                            graph = torch.npu.NPUGraph()
                            with torch.npu.graph(graph, stream=stream):
                                observed = fn()
                            torch.npu.current_stream().wait_stream(stream)
                            torch.npu.synchronize()
                            try:
                                for update in (0, 1):
                                    if update:
                                        q.add_(.125)
                                        k.add_(-.125)
                                        c.mul_(.875)
                                        s.mul_(.875)
                                    graph.replay()
                                    reference = native()
                                    exact = all(torch.equal(a, b) for a, b in zip(reference, observed))
                                    checks.append({'batch': batch, 'length': length, 'width': width, 'shared': shared,
                                                   'variant': label, 'updated_inputs': bool(update), 'exact': exact})
                                    if not exact:
                                        raise ValueError('rotary output differs from native: ' + str(checks[-1]))
                            finally:
                                graph.reset()
                            if width != 128 or not shared:
                                continue
                            # Chain many calls in one graph to amortize Python
                            # replay dispatch. Retain all outputs to avoid dead
                            # allocations being mistaken for measured work.
                            stream = torch.npu.Stream()
                            stream.wait_stream(torch.npu.current_stream())
                            graph = torch.npu.NPUGraph()
                            with torch.npu.graph(graph, stream=stream):
                                held = [fn() for _ in range(args.chain)]
                            torch.npu.current_stream().wait_stream(stream)
                            torch.npu.synchronize()
                            values = []
                            try:
                                for _ in range(10):
                                    graph.replay()
                                torch.npu.synchronize()
                                for _ in range(args.repetitions):
                                    begin, end = torch.npu.Event(enable_timing=True), torch.npu.Event(enable_timing=True)
                                    begin.record()
                                    for _ in range(args.iterations):
                                        graph.replay()
                                    end.record()
                                    end.synchronize()
                                    values.append(begin.elapsed_time(end) * 1000 / (args.iterations * args.chain))
                            finally:
                                graph.reset()
                            timings.append({'batch': batch, 'length': length, 'width': width, 'shared': shared,
                                            'variant': label, 'pair_us': values, 'mean_pair_us': statistics.mean(values),
                                            'sample_sd_us': statistics.stdev(values)})
    result = {'status': 'PASS', 'scope': 'L0 exact pointwise outputs and hot-input L1 graph chains only; no E2E claim',
              'checks': checks, 'timings': timings, 'iterations': args.iterations, 'chain': args.chain,
              'repetitions': args.repetitions,
              'operator_source_sha256': hashlib.sha256(Path(__file__).with_name('predictor_rope.py').read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'exact_checks': len(checks), 'timing_groups': len(timings)}), flush=True)


if __name__ == '__main__':
    main()
