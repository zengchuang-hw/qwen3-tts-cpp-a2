"""Diagnostic CPU/NPU trace of a warmed native frame graph; never a benchmark."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from serve import load_reference


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-root", type=Path, required=True)
    p.add_argument("--native-build", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--workload", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--steps", type=int, default=16)
    p.add_argument("--slots", type=int, default=4)
    p.add_argument("--profile-index", type=int, help="Repeat one fixed input to keep the diagnostic batch populated")
    p.add_argument("--predictor-rope", choices=["native", "paired"], default="native")
    args = p.parse_args()
    if not 1 <= args.steps <= 16 or args.slots not in (1, 2, 4, 8, 16, 32, 64):
        p.error("steps must be 1..16 and slots a power of two in 1..64")
    load_reference(args.reference_root)
    sys.path.insert(0, str(args.native_build.resolve()))
    import torch
    import torch_npu
    from graph_model import NativeModel

    args.output.mkdir(parents=True, exist_ok=False)
    data = args.workload.read_bytes()
    rows = [dict(json.loads(line), instructions="") for line in data.splitlines() if line.strip()]
    if args.profile_index is not None and not 0 <= args.profile_index < len(rows):
        p.error("profile-index is outside the workload")
    indices = ([args.profile_index] * args.slots if args.profile_index is not None
               else ([2, 64, 65, 66] if args.slots == 4 else list(range(args.slots))))
    if len(rows) <= max(indices):
        p.error("insufficient workload entries")
    model = NativeModel(str(args.model), "npu:0", max_slots=args.slots,
                        predictor_rope=args.predictor_rope, prewarm_decode=True)
    try:
        model.tick([(identifier, rows[index]) for identifier, index in enumerate(indices)])
        for _ in range(7):
            model.tick()
        torch.npu.synchronize()
        active_before = len(model.states)
        active_counts = []
        with torch_npu.profiler.profile(
            activities=[torch_npu.profiler.ProfilerActivity.CPU, torch_npu.profiler.ProfilerActivity.NPU],
            record_shapes=False,
            on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(str(args.output)),
        ):
            for _ in range(args.steps):
                with torch.profiler.record_function("qtts_native_frame"):
                    model.tick()
                active_counts.append(len(model.states))
            torch.npu.synchronize()
        summary = {"status": "DIAGNOSTIC_ONLY", "scope": "profiled frame/codec execution; not service performance",
                   "workload_sha256": hashlib.sha256(data).hexdigest(), "steps": args.steps,
                   "requested_slots": args.slots, "input_indices": indices,
                   "diagnostic_repeated_input": args.profile_index is not None,
                   "active_before": active_before, "active_per_step": active_counts,
                   "active_requests": len(model.states), "decode_shapes": sorted(model.native_decodes),
                   "reference_revision": "b4451682abac651f26046f8d27467de3f007e1e7"}
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    finally:
        model.close()


if __name__ == "__main__":
    main()
