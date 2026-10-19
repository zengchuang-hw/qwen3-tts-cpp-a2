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
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "assess.py"
SPEC = importlib.util.spec_from_file_location("qtts_assess", SOURCE)
assess = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assess)


def load_script(name):
    spec = importlib.util.spec_from_file_location("qtts_" + name, SOURCE.with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve = load_script("serve")
with patch.dict(sys.modules, {"serve": serve}):
    campaign = load_script("campaign")


class NativeEvidenceContracts(unittest.TestCase):
    def test_frozen_rotary_policy_boundaries_without_accelerator(self):
        from rotary_policy import resolve_head_tile
        for batch in (1, 4, 8, 15):
            self.assertEqual(resolve_head_tile("auto", batch, 1, 128), 4)
        for batch in (16, 32, 64):
            for length in (1, 2):
                self.assertEqual(resolve_head_tile("auto", batch, length, 128), 16)
                self.assertEqual(resolve_head_tile("auto", batch, length, 64), 4)
        self.assertEqual(resolve_head_tile("auto", 64, 3, 128), 4)
        for tile in (4, 8, 16):
            self.assertEqual(resolve_head_tile(str(tile), 64, 2, 128), tile)
        with self.assertRaises(ValueError):
            resolve_head_tile("32", 16, 1, 128)

    def test_native_control_command_does_not_inherit_candidate_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = root / "evidence/campaign-20261017/plan/continuous-direct-prompt-command.json"
            command.parent.mkdir(parents=True)
            command.write_text(json.dumps(["python", "-m", "qwen3_tts_engine.server", "--model", "old", "--port", "1"]))
            args = SimpleNamespace(reference_root=root, model=root / "model", port=8199,
                                   native_build=root / "build", predictor_rope="paired",
                                   reference_engine="native-buffered", audio_delivery="inline", rotary_head_tile="auto")
            control = campaign.server_command(args, "reference")
            candidate = campaign.server_command(args, "native")
            self.assertEqual(control[control.index("--audio-delivery") + 1], "buffered")
            self.assertEqual(candidate[candidate.index("--audio-delivery") + 1], "inline")
            args.reference_engine = "native-tile4"
            control = campaign.server_command(args, "reference")
            self.assertEqual(control[control.index("--audio-delivery") + 1], "inline")
            self.assertEqual(control[control.index("--rotary-head-tile") + 1], "4")
            self.assertEqual(candidate[candidate.index("--rotary-head-tile") + 1], "auto")
            args.reference_engine = "upstream"
            upstream = campaign.server_command(args, "reference")
            self.assertNotIn("--audio-delivery", upstream)
            self.assertIn("qwen3_tts_engine.server", upstream)

    def test_full_native_control_cannot_become_upstream_performance_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cs = [1, 2, 4, 8, 16, 32, 64]
            names = [f"r{r}-{arm}" for r in range(1, 4) for arm in ("reference", "native")]
            (root / "runspec.json").write_text(json.dumps({"repetitions": 3, "requests": 128,
                "concurrencies": cs, "workload_sha256": "fixture", "formal_coverage": True,
                "reference_engine": "native-buffered"}))
            (root / "campaign.json").write_text(json.dumps({"status": "INCONCLUSIVE", "completed": names}))
            for name in names:
                (root / name).mkdir()
                (root / name / "lifecycle.json").write_text(json.dumps({"status": "COMPLETED", "server_exit": 0,
                    "cohorts": [{"concurrency": c, "exit": 0} for c in cs]}))

            def metrics(path, *unused):
                candidate = "-native" in str(path)
                return ({"throughput_frames_s": 200. if candidate else 100.,
                         "ttfa_p95_ms": 1. if candidate else 2.}, {0: "same-pcm"})

            with patch.object(assess, "audit_cohort", side_effect=metrics):
                result = assess.assess(root)
            self.assertEqual(result["status"], "INCONCLUSIVE")
            self.assertEqual(result["performance"], "INCONCLUSIVE")
            self.assertFalse(result["formal_coverage"])
    def test_public_request_bound_is_checked_before_native_admission(self):
        serve.validate_native_limit({"max_new_tokens": 2048}, 2048)
        for payload in ({"max_new_tokens": 4096}, {"max_new_tokens": 1}, {}):
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "native arena"):
                serve.validate_native_limit(payload, 1024)

    def test_environment_and_model_identity_detect_actual_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model, reference, cann = root / "model", root / "reference", root / "cann"
            model.mkdir()
            install = cann / "aarch64-linux/ascend_toolkit_install.info"
            install.parent.mkdir(parents=True)
            install.write_text("test-cann")
            records = []
            for index in range(11):
                name = f"asset-{index}.bin"
                data = bytes([index])
                (model / name).write_bytes(data)
                records.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": 1})
            manifest = reference / "evidence/campaign-20261017/results/model-audit.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"files": records}))
            with patch.object(campaign.importlib.metadata, "version", return_value="fixture"), \
                    patch.object(campaign.subprocess, "check_output", return_value="libc6=14\n") as dpkg, \
                    patch.dict(campaign.os.environ, {"ASCEND_HOME_PATH": str(cann)}):
                first = campaign.runtime_identity(model, reference)
                dpkg.return_value = "libc6=15\n"
                self.assertNotEqual(first, campaign.runtime_identity(model, reference))
                (model / "asset-0.bin").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "model asset differs"):
                    campaign.runtime_identity(model, reference)

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
