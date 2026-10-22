"""C009 cross-campaign comparison: per-(cohort, index) audio identity and throughput.

Compares codec4 against codec8 for both arms. Every number is recomputed from the
per-request records and the retained WAV files; the reported metrics field is only
cross-checked, never trusted.
"""

import hashlib
import json
from pathlib import Path

D = Path("/work/c009/results")
ARMS = {"r1-native": "inline", "r1-reference": "buffered"}
COHORTS = (16, 32, 64)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(tag, arm, cohort):
    root = D / tag / arm / f"c{cohort}"
    results = json.loads((root / "results.json").read_text())
    metrics = results["metrics"]
    requests = sorted(results["requests"], key=lambda r: r["index"])
    audio_total = sum(r["audio_seconds"] for r in requests)
    recomputed = audio_total * 12.5 / metrics["wall_seconds"]
    return {
        "root": root,
        "metrics": metrics,
        "requests": requests,
        "audio_total_seconds": audio_total,
        "recomputed_throughput": recomputed,
        "reported_throughput": metrics["throughput_frames_s"],
        "throughput_delta": recomputed - metrics["throughput_frames_s"],
        "stops": sum(1 for r in requests if r["terminal"].get("finish_reason") == "stop"),
        "successes": sum(1 for r in requests if r["success"]),
    }


def main():
    report = {"generated_by": "evidence/c009-codec-batch/validator/c009_compare.py",
              "arms": {}, "defects": []}
    for arm, delivery in ARMS.items():
        arm_report = {"delivery": delivery, "cohorts": {}}
        for cohort in COHORTS:
            four, eight = load("codec4", arm, cohort), load("codec8", arm, cohort)
            if len(four["requests"]) != 128 or len(eight["requests"]) != 128:
                report["defects"].append(f"{arm} c{cohort}: request count differs from 128")
            pcm_mismatch, wav_mismatch, frame_mismatch, detail = [], [], [], []
            for a, b in zip(four["requests"], eight["requests"]):
                if a["index"] != b["index"]:
                    report["defects"].append(f"{arm} c{cohort}: index alignment broken")
                    break
                frames_a = a["terminal"].get("codec_frames")
                frames_b = b["terminal"].get("codec_frames")
                if pcm := (a["pcm_sha256"] != b["pcm_sha256"]):
                    pcm_mismatch.append(a["index"])
                if frames_a != frames_b:
                    frame_mismatch.append(a["index"])
                if sha256_file(four["root"] / f"{a['index']:05d}.wav") != \
                        sha256_file(eight["root"] / f"{b['index']:05d}.wav"):
                    wav_mismatch.append(a["index"])
                if pcm or frames_a != frames_b:
                    detail.append({"index": a["index"], "codec_frames": [frames_a, frames_b],
                                   "audio_seconds": [a["audio_seconds"], b["audio_seconds"]],
                                   "pcm_sha256": [a["pcm_sha256"], b["pcm_sha256"]]})
            ratio = eight["recomputed_throughput"] / four["recomputed_throughput"]
            arm_report["cohorts"][f"c{cohort}"] = {
                "requests": [len(four["requests"]), len(eight["requests"])],
                "stops": [four["stops"], eight["stops"]],
                "successes": [four["successes"], eight["successes"]],
                "pcm_sha256_matched": 128 - len(pcm_mismatch),
                "pcm_sha256_mismatch_indices": pcm_mismatch,
                "codec_frames_matched": 128 - len(frame_mismatch),
                "codec_frames_mismatch_indices": frame_mismatch,
                "wav_sha256_matched": 128 - len(wav_mismatch),
                "wav_sha256_mismatch_indices": wav_mismatch,
                "mismatch_detail": detail[:12],
                "wall_seconds": [four["metrics"]["wall_seconds"], eight["metrics"]["wall_seconds"]],
                "audio_total_seconds": [four["audio_total_seconds"], eight["audio_total_seconds"]],
                "recomputed_throughput": [four["recomputed_throughput"], eight["recomputed_throughput"]],
                "reported_throughput": [four["reported_throughput"], eight["reported_throughput"]],
                "throughput_recompute_delta": [four["throughput_delta"], eight["throughput_delta"]],
                "ratio_8_over_4": ratio,
            }
            for tag, item in (("codec4", four), ("codec8", eight)):
                if abs(item["throughput_delta"]) > 1e-6:
                    report["defects"].append(
                        f"{tag} {arm} c{cohort}: recomputed {item['recomputed_throughput']:.4f} "
                        f"!= reported {item['reported_throughput']:.4f}")
        report["arms"][arm] = arm_report
    out = Path("/work/c009/results/comparison.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    for arm, a in report["arms"].items():
        print("==", arm, a["delivery"])
        for c, v in a["cohorts"].items():
            print(" ", c, "pcm", v["pcm_sha256_matched"], "/128",
                  "frames", v["codec_frames_matched"], "/128",
                  "wav", v["wav_sha256_matched"], "/128",
                  "ratio", round(v["ratio_8_over_4"], 6),
                  "stops", v["stops"], "succ", v["successes"])
    print("defects:", report["defects"][:5], "count", len(report["defects"]))
    print("written:", out)


if __name__ == "__main__":
    main()
