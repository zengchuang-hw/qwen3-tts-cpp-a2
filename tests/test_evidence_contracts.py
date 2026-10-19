"""Native-engine evidence contracts; synthetic data is not accelerator evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import sys


SOURCE = Path(__file__).resolve().parents[1] / "assess.py"
SPEC = importlib.util.spec_from_file_location("qtts_assess", SOURCE)
assess = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assess)


class NativeEvidenceContracts(unittest.TestCase):
    def fixture(self, root):
        def write(path, value):
            path.write_text(json.dumps(value))
        write(root / "runspec.json", {"repetitions": 1, "requests": 2, "concurrencies": [1],
                                      "workload_sha256": "fixture", "formal_coverage": False})
        write(root / "campaign.json", {"status": "INCONCLUSIVE", "completed": ["r1-reference", "r1-native"]})
        for arm, wall, ttfa in (("reference", 1., .1), ("native", .8, .05)):
            trial = root / f"r1-{arm}"
            cohort = trial / "c1"
            cohort.mkdir(parents=True)
            write(trial / "lifecycle.json", {"status": "COMPLETED", "server_exit": 0,
                                             "cohorts": [{"concurrency": 1, "exit": 0}]})
            write(cohort / "runspec.json", {"requests": 2, "concurrency": 1, "frame_rate": 12.5,
                                           "sample_rate": 24000, "workload_sha256": "fixture"})
            pcm = b"\x01\x00" * 2400
            rows = []
            for index in range(2):
                with wave.open(str(cohort / f"{index:05d}.wav"), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(24000)
                    audio.writeframes(pcm)
                rows.append({"index": index, "success": True, "terminal": {
                    "type": "speech.audio.done", "finish_reason": "stop"},
                    "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "pcm_bytes": len(pcm),
                    "audio_seconds": .1, "ttfa_seconds": ttfa, "elapsed_seconds": .5,
                    "chunks": [{"bytes": len(pcm), "seconds": ttfa}]})
            write(cohort / "results.json", {"requests": rows, "metrics": {
                "wall_seconds": wall, "throughput_frames_s": 2.5 / wall,
                "ttfa_p50_ms": ttfa * 1000, "ttfa_p95_ms": ttfa * 1000, "rtf_mean": 5.}})

    def test_small_exact_probe_cannot_become_formal_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = assess.assess(root)
            self.assertEqual(result["status"], "INCONCLUSIVE")
            self.assertEqual(result["relative_quality"], "PASS_EXACT_PCM")

    def test_incomplete_or_failed_lifecycle_rejects_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            path = root / "r1-native/lifecycle.json"
            value = json.loads(path.read_text())
            value["server_exit"] = -9
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "lifecycle"):
                assess.assess(root)

    def test_audio_tampering_truncation_and_aggregate_forgery_reject(self):
        for mutation in ("audio", "length", "metric"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root)
                cohort = root / "r1-native/c1"
                path = cohort / "results.json"
                value = json.loads(path.read_text())
                if mutation == "audio":
                    value["requests"][0]["pcm_sha256"] = "tampered"
                elif mutation == "length":
                    value["requests"][0]["terminal"]["finish_reason"] = "length"
                else:
                    value["metrics"]["throughput_frames_s"] = 1e9
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    assess.assess(root)


if __name__ == "__main__":
    unittest.main()
