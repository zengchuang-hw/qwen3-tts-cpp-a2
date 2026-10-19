"""CPU contract fixtures; no accelerator or real performance claim."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rsi
import assess


class InferRsiAdapterContracts(unittest.TestCase):
    def test_nonfinite_deadlines_are_rejected_before_sdk_or_hardware(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in (float('nan'),float('inf'),-1,0):
                args=SimpleNamespace(**{name:Path(temp) for name in (
                    'reference_root','candidate_root','native_build','model','workload','inferrsi_root')},
                    primary_concurrency=4,concurrencies=[4],requests=4,repetitions=1,
                    readiness_timeout=value,benchmark_timeout=10,physical_device=3)
                with self.assertRaises(ValueError):rsi.normalize(args)
                with self.assertRaisesRegex(ValueError,'deadline'):
                    rsi.run_campaign(SimpleNamespace(max_minutes=value))

    def test_generic_primary_pass_never_overrides_tts_gates(self):
        generic={'verdict':'PASS'}
        for tts,expected in [({'status':'FAIL'},'FAIL'),({'status':'INCONCLUSIVE'},'INCONCLUSIVE'),
            ({},'INCONCLUSIVE'),({'status':'FAIL','formal_coverage':False,'relative_quality':'PASS_EXACT_PCM'},'INCONCLUSIVE'),({'status':'PASS','formal_coverage':False,'relative_quality':'PASS_EXACT_PCM'},'INCONCLUSIVE'),
            ({'status':'PASS','formal_coverage':True},'INCONCLUSIVE'),
            ({'status':'PASS','formal_coverage':True,'relative_quality':'PASS_EXACT_PCM'},'PASS')]:
            with self.subTest(tts=tts):self.assertEqual(rsi.aggregate(generic,tts)['status'],expected)
        self.assertEqual(rsi.aggregate({'verdict':'INCONCLUSIVE'},
            {'status':'PASS','formal_coverage':True,'relative_quality':'PASS_EXACT_PCM'})['status'],'INCONCLUSIVE')
        self.assertEqual(rsi.aggregate({'verdict':'INCONCLUSIVE'},
            {'status':'FAIL','formal_coverage':True,'relative_quality':'PASS_EXACT_PCM'})['status'],'FAIL')
        self.assertEqual(rsi.aggregate({'verdict':'FAIL'}, {'status':'INCONCLUSIVE'})['status'],'FAIL')
        self.assertNotIn('torch',sys.modules)
        self.assertNotIn('torch_npu',sys.modules)

    def test_library_pin_dirty_source_and_wrong_import_path_reject(self):
        root=Path(tempfile.gettempdir())/'fixture-inferrsi'
        with patch.object(rsi,'git',return_value='wrong'):
            with self.assertRaises(ValueError):rsi.pinned_library(root)
        with patch.object(rsi,'git',side_effect=[rsi.INFER_RSI_SHA,' M runspec.py']):
            with self.assertRaises(ValueError):rsi.pinned_library(root)
        fake=SimpleNamespace(__file__=str(root.parent/'different'/'sdk.py'))
        with patch.object(rsi,'git',side_effect=[rsi.INFER_RSI_SHA,'']), \
             patch.object(rsi.importlib,'import_module',return_value=fake):
            with self.assertRaises(ValueError):rsi.pinned_library(root)

    def test_explicit_trial_paths_are_used_and_aliases_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);view=root/'view';view.mkdir()
            names=['r1-reference','r1-native']
            (view/'runspec.json').write_text(json.dumps({'repetitions':1,'requests':4,'concurrencies':[4],
                'workload_sha256':'fixture','formal_coverage':False}))
            (view/'campaign.json').write_text(json.dumps({'status':'INCONCLUSIVE','completed':names}))
            folders={name:root/'actual'/name for name in names}
            for path in folders.values():
                path.mkdir(parents=True)
                (path/'lifecycle.json').write_text(json.dumps({'status':'COMPLETED','server_exit':0,
                    'cohorts':[{'concurrency':4,'exit':0}]}))
            def audit(path,*unused):
                self.assertIn(path.parent,{p.resolve() for p in folders.values()})
                return ({'throughput_frames_s':200. if path.parent.name.endswith('native') else 100.,
                         'ttfa_p95_ms':1.},{0:'fixture-pcm'})
            with patch.object(assess,'audit_cohort',side_effect=audit):
                result=assess.assess(view,trial_directories=folders)
            self.assertEqual(result['status'],'INCONCLUSIVE')
            self.assertEqual(result['relative_quality'],'PASS_EXACT_PCM')
            with self.assertRaises(assess.EvidenceViolation):
                assess.assess(view,trial_directories={name:folders[names[0]] for name in names})
            with self.assertRaises(ValueError):assess.assess(view,trial_directories={})

    def test_result_path_requires_real_supervised_runner_context(self):
        with tempfile.TemporaryDirectory() as temp:
            args=SimpleNamespace(output=Path(temp)/'result.json',inferrsi_root=Path(temp))
            with patch.object(rsi,'pinned_library',return_value=object()), \
                 patch.dict(rsi.os.environ,{},clear=True):
                with self.assertRaisesRegex(ValueError,'runner-owned'):rsi.run_trial(args)


if __name__=='__main__':
    unittest.main()
