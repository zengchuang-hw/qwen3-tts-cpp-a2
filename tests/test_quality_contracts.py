"""Negative Q1 evidence contracts; synthetic data never claims speech quality."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from quality_core import (ASR_NEW_TOKENS, MODEL_REVISIONS, PROTOCOL, audit_boundary, audit_score,
                          compare_group, edit_distance, units, windows)
from speech_quality import assets, environment, workload_rows


def record():
    return {'status': 'SCORED', 'protocol': PROTOCOL, 'models': MODEL_REVISIONS.copy(),
            'lock_sha256': 'lock', 'pcm_sha256': 'pcm', 'language': 'English', 'samples_16k': 16000,
            'pcm_bytes': 48000,
            'asr': [{'start': 0, 'end': 16000, 'prefix': [50258, 50259, 50359, 50363],
                     'generated_tokens': [5, 50257], 'eos_token_id': 50257, 'transcript': 'actual transcript'}],
            'speaker': [{'start': 0, 'end': 16000, 'real_samples': 16000,
                         'embedding': [1.0] + [0.0] * 511}]}


class QualityContracts(unittest.TestCase):
    def test_different_pre_freeze_dependency_versions_are_unqualified(self):
        with patch('speech_quality.importlib.metadata.version', return_value='unqualified'):
            with self.assertRaisesRegex(ValueError, 'requalification needed'):
                environment()

    def test_old_audio_and_mismatched_generation_boundary_never_pass(self):
        lock = {'frozen_unix_ns': 10}
        boundary = {'status': 'STARTED', 'protocol': PROTOCOL, 'lock_sha256': 'L',
                    'run': 'new-run', 'started_unix_ns': 20}
        terminal = {'lock_sha256': 'L', 'boundary_sha256': 'B',
                    'identity_unchanged': True, 'finished_unix_ns': 30}
        audit_boundary(lock, boundary, terminal, 'L', 'B', 'new-run', 21)
        for mtime in (1, 19):
            with self.assertRaises(ValueError):
                audit_boundary(lock, boundary, terminal, 'L', 'B', 'new-run', mtime)
        for key, value in (('lock_sha256', 'other'), ('identity_unchanged', False), ('finished_unix_ns', 10)):
            changed = {**terminal, key: value}
            with self.assertRaises(ValueError):
                audit_boundary(lock, boundary, changed, 'L', 'B', 'new-run', 21)
        with self.assertRaises(ValueError):
            audit_boundary(lock, boundary, terminal, 'L', 'B', 'old-run', 21)

    def test_control_import_rejects_accelerator_dependency(self):
        script = '''
import importlib.abc, sys
class NoRuntime(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path, target=None):
  if fullname.split('.')[0] in ('torch','torch_npu','transformers','numpy','scipy'):
   raise AssertionError('eager inference dependency: '+fullname)
sys.meta_path.insert(0,NoRuntime())
import quality_core, speech_quality, speech_scorer
'''
        subprocess.run([sys.executable, '-c', script], check=True,
                       cwd=Path(__file__).resolve().parents[1])

    def test_balanced_windows_cover_long_and_short_audio(self):
        self.assertEqual(windows(96001, 96000), [(0, 48000), (48000, 96001)])
        for samples in (1, 15999, 16000, 480001, 2077001):
            bounds = windows(samples, 480000)
            self.assertEqual(bounds[0][0], 0)
            self.assertEqual(bounds[-1][1], samples)
            self.assertTrue(all(0 < b - a <= 480000 for a, b in bounds))
            self.assertTrue(all(a[1] == b[0] for a, b in zip(bounds, bounds[1:])))
        for samples in (0, -1, True, 1.0):
            with self.assertRaises(ValueError):
                windows(samples, 10)

    def test_language_units_and_independent_error_counts(self):
        self.assertEqual(units("Ｔｅｓｔ, don't_32!", 'English'), ['test', "don't", '32'])
        self.assertEqual(units('你好，Ａ２！', 'Chinese'), ['你', '好', 'a', '2'])
        self.assertEqual(edit_distance(['a', 'b', 'c'], ['a', 'x', 'd', 'c']), 2)

    def test_missing_fake_scores_and_nonfinite_embeddings_are_rejected(self):
        original = record()
        self.assertEqual(audit_score(original, 'pcm', 'English', 'lock')[0], 'actual transcript')
        mutations = [lambda r: r.update(status='PASS'), lambda r: r.update(lock_sha256='other'),
                     lambda r: r.update(models={}), lambda r: r.update(pcm_sha256='other'),
                     lambda r: r.update(pcm_bytes=48002),
                     lambda r: r['asr'][0].update(prefix=[50258, 50260, 50359, 50363]),
                     lambda r: r['asr'].clear(), lambda r: r['speaker'].clear(),
                     lambda r: r['asr'][0].update(end=15999),
                     lambda r: r['asr'][0].update(transcript=''),
                     lambda r: r['asr'][0].update(generated_tokens=[5]),
                     lambda r: r['asr'][0].update(generated_tokens=[6] * ASR_NEW_TOKENS),
                     lambda r: r['speaker'][0].update(real_samples=1),
                     lambda r: r['speaker'][0].update(embedding=[0.0] * 512),
                     lambda r: r['speaker'][0]['embedding'].__setitem__(0, float('nan'))]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            with self.subTest(changed=changed.keys()), self.assertRaises((ValueError, KeyError)):
                audit_score(changed, 'pcm', 'English', 'lock')
        with self.assertRaises((ValueError, KeyError)):
            audit_score({'status': 'PASS', 'wer': 0, 'cosine': 1}, 'pcm', 'English', 'lock')

    def test_inclusive_asr_boundary_and_speaker_failure_are_independent(self):
        row = {'text': ' '.join(['word'] * 100), 'reference_transcript': ' '.join(['word'] * 100),
               'candidate_transcript': ' '.join(['word'] * 99), 'exact_pcm': False,
               'reference_embedding': [1.0] + [0.0] * 511,
               'candidate_embedding': [1.0] + [0.0] * 511}
        result = compare_group([row], 'English')
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['error_rate_delta'], .01)
        row['candidate_transcript'] = ' '.join(['word'] * 98)
        self.assertEqual(compare_group([row], 'English')['status'], 'FAIL')
        row['candidate_transcript'] = row['reference_transcript']
        row['candidate_embedding'] = [0.0, 1.0] + [0.0] * 510
        self.assertEqual(compare_group([row], 'English')['status'], 'FAIL')

    def test_model_pin_and_partial_asset_definition_rejected_before_loading(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root / 'data/q1-models.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'models.json'
            for mutate in (lambda rows: rows[0].update(revision='wrong'),
                           lambda rows: rows[0].update(files=[])):
                changed = copy.deepcopy(expected)
                mutate(changed)
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'definition differs'):
                    assets(Path(directory), path)

    def test_ground_truth_uses_explicit_benchmark_input_and_language(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'workload.jsonl'
            path.write_text(json.dumps({'input': '真实文本', 'language': 'Chinese'}), encoding='utf-8')
            self.assertEqual(workload_rows(path)[0]['input'], '真实文本')
            path.write_text(json.dumps({'text': 'wrong schema', 'language': 'English'}))
            with self.assertRaises(ValueError):
                workload_rows(path)


if __name__ == '__main__':
    unittest.main()
