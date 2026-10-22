"""Complete-model development probe; timings are diagnostic, not acceptance."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import wave

from serve import load_reference


class ProbeEmitError(RuntimeError):
    """Intentional callback failure; never a completed speech request."""


def codec_batch_size(text):
    """Bound the codec batch knob exactly as serve.py does."""
    value = int(text)
    if not 1 <= value <= 8:
        raise argparse.ArgumentTypeError("codec batch size must be within [1,8]")
    return value


def pinned_codec_batch_size(engine, size):
    """The upstream reference arm keeps its frozen codec batch of 4."""
    if engine == "reference" and size != 4:
        raise ValueError("the pinned reference engine keeps codec batch size 4")
    return size


class StepWitness:
    def __init__(self, core):
        self.core = core
        self.inside = False

    def __getattr__(self, name):
        return getattr(self.core, name)

    def step(self, *args):
        self.inside = True
        try:
            return self.core.step(*args)
        finally:
            self.inside = False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-root", type=Path, required=True)
    p.add_argument("--native-build", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--engine", choices=["reference", "native"], required=True)
    p.add_argument("--workload", type=Path, required=True)
    p.add_argument("--indices", default="0,1,64,65")
    p.add_argument("--slots", type=int, default=4)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cancel-and-reuse", action="store_true")
    p.add_argument("--predictor-rope", choices=["native", "paired"], default="native")
    p.add_argument("--rotary-head-tile", choices=["4", "8", "16", "auto"], default="4")
    p.add_argument("--codec-batch-size", type=codec_batch_size, default=4, metavar="N")
    p.add_argument("--audio-delivery", choices=["buffered", "inline"], default="buffered")
    p.add_argument("--verify-inline", action="store_true")
    p.add_argument("--fail-emit", action="store_true", help="Test intentional callback exception propagation/cleanup")
    args = p.parse_args()
    try:
        pinned_codec_batch_size(args.engine, args.codec_batch_size)
    except ValueError as error:
        p.error(str(error))
    if (args.verify_inline or args.fail_emit) and (args.engine != "native" or args.audio_delivery != "inline"):
        p.error("callback witnesses require native inline delivery")
    args.output.mkdir(parents=True, exist_ok=False)
    load_reference(args.reference_root)
    sys.path.insert(0, str(args.native_build.resolve()))
    import torch
    import torch_npu  # noqa: F401
    from qwen3_tts_engine.continuous import ContinuousModel

    if args.engine == "native":
        from graph_model import NativeModel
        model = NativeModel(str(args.model), "npu:0", max_slots=args.slots,
                            codec_batch_size=args.codec_batch_size,
                            predictor_rope=args.predictor_rope, audio_delivery=args.audio_delivery,
                            rotary_head_tile=args.rotary_head_tile)
    else:
        model = ContinuousModel(
            str(args.model), "npu:0", max_slots=args.slots, pack_qkv=True,
            rms_norm="native", pack_mlp=True, fused_swiglu=True,
            native_gqa=True, text_only_rope=True, native_rope=True,
            native_rope_scope="predictor", triton_talker_rope=True,
            native_kv_update=True, triton_kv_update=True,
            incremental_codec=True, batch_prefill=True, graph_prefill=True,
            bucket_prefill=True, prewarm_prefill=True, direct_prompt=True,
            triton_snake=True, cache_codec_codebooks=True,
            # Pinned baseline value: the upstream reference arm is never moved
            # off 4, so a "vs reference" statement keeps meaning the same thing.
            codec_batch_size=4, triton_cdf=True, graph_embeddings=True,
            graph_sampling=True, prewarm_codec=True,
        )
    rows = [json.loads(line) for line in args.workload.read_text().splitlines() if line.strip()]
    inputs = []
    for index in map(int, args.indices.split(",")):
        payload = dict(rows[index])
        payload.setdefault("instructions", "")
        inputs.append((index, payload))
    if len(inputs) > args.slots:
        raise ValueError("probe inputs must fit the slot arena")
    first = {}
    chunks = {}
    records = []
    witness = None
    if args.verify_inline or args.fail_emit:
        witness = StepWitness(model.core)
        model.core = witness
    callback_checks = []
    rejected_mutations = []
    owner_thread = threading.get_ident()
    start = time.perf_counter()

    def emit(identifier, pcm, rate):
        if rate != 24000 or not pcm:
            raise ValueError("invalid audio chunk")
        if witness is not None:
            check = witness.inside and threading.get_ident() == owner_thread
            callback_checks.append(check)
            if not check:
                raise ValueError("callback was deferred beyond core.step or moved threads")
            if not rejected_mutations:
                for name, action in (("cancel", lambda: witness.core.cancel([])),
                                     ("step", lambda: witness.core.step()),
                                     ("close", lambda: witness.core.close())):
                    try:
                        action()
                    except RuntimeError as error:
                        if "during step" not in str(error):
                            raise
                        rejected_mutations.append(name)
                    else:
                        raise ValueError("callback mutation/reentry was allowed: " + name)
            if args.fail_emit:
                raise ProbeEmitError("intentional audio callback failure")
        first.setdefault(identifier, time.perf_counter() - start)
        chunks.setdefault(identifier, bytearray()).extend(pcm)

    try:
        for tick in range(2050):
            submissions = inputs if tick == 0 else []
            cancelled = [inputs[1][0]] if args.cancel_and_reuse and tick == 6 else []
            if args.cancel_and_reuse and tick == 7:
                extra = dict(rows[2], instructions="")
                submissions = [(2, extra)]
            for identifier, result in model.tick(submissions, emit, cancelled):
                pcm = result["pcm"]
                if result["finish_reason"] != "stop" or not pcm:
                    raise ValueError(f"request {identifier} incomplete: {result['finish_reason']}")
                if bytes(chunks[identifier]) != pcm:
                    raise ValueError("streamed audio differs from final audio")
                path = args.output / f"{identifier:05d}.wav"
                with wave.open(str(path), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(24000)
                    wav.writeframes(pcm)
                records.append({"id": identifier, "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                                "pcm_bytes": len(pcm), "frames": result["codec_frames"],
                                "first_audio_seconds": first[identifier],
                                "elapsed_seconds": time.perf_counter() - start,
                                "finish_reason": result["finish_reason"]})
            if not model.states:
                break
        else:
            raise RuntimeError("native probe did not finish within the frame bound")
        expected = {item[0] for item in inputs}
        if args.cancel_and_reuse:
            expected.remove(inputs[1][0])
            expected.add(2)
        if {r["id"] for r in records} != expected:
            raise ValueError("missing or unexpected completion")
        torch.npu.synchronize()
        result = {"status": "INCONCLUSIVE", "scope": "development complete-model probe",
                  "engine": args.engine, "records": records,
                  "wall_seconds": time.perf_counter() - start,
                  "cancel_and_reuse": args.cancel_and_reuse,
                  "quality": "NOT_SCORED", "performance_acceptance": "NOT_EVALUATED",
                  "audio_delivery": args.audio_delivery if args.engine == "native" else "reference",
                  "callback_checks": callback_checks,
                  "rejected_callback_mutations": rejected_mutations}
        (args.output / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        if args.fail_emit:
            raise ValueError("intentional callback error did not propagate")
    except ProbeEmitError:
        if not args.fail_emit or not callback_checks or not all(callback_checks):
            raise
        # The exception has unwound the native step guard. Cancel must now be
        # legal; no partially delivered request is counted as successful.
        model.core.cancel(model.core.identifiers())
        if model.states:
            raise ValueError("failed callback left live requests after cleanup")
        result = {"status": "PASS", "scope": "intentional callback exception propagation and cleanup only",
                  "completed_requests": 0, "callback_checks": callback_checks,
                  "rejected_callback_mutations": rejected_mutations}
        (args.output / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        model.close()


if __name__ == "__main__":
    main()
