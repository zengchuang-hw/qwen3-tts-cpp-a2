import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assess_stress import compare, Incomplete, Violation, digest, WORKLOAD_SHA256


class StressEvidenceContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.left,self.right=self.root/'reference',self.root/'candidate'
        for root in (self.left,self.right):
            root.mkdir()
            rows=[]
            for cycle in range(2):
                completions=[]
                cancellations=[]
                for identifier in range(16):
                    generation=int(identifier in {1,5,9,13})
                    pcm=bytes((1+cycle,0))*1920
                    name=f'{cycle}-{identifier}-g{generation}.wav'
                    with wave.open(str(root/name),'wb') as audio:
                        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(pcm)
                    completions.append({'id':identifier,'generation':generation,'file':name,'frames':1,
                        'finish_reason':'stop','pcm_bytes':len(pcm),'pcm_sha256':digest(pcm),
                        'chunks':[{'bytes':len(pcm),'sha256':digest(pcm)}]})
                    if generation:
                        prefix=bytes((1,0))*3840
                        name=f'{cycle}-{identifier}-g0.pcm'
                        (root/name).write_bytes(prefix)
                        cancellations.append({'id':identifier,'generation':0,'status':'CANCELLED','file':name,
                            'pcm_bytes':len(prefix),'pcm_sha256':digest(prefix)})
                rows.append({'cycle':cycle,'warmup':False,'completions':completions,'cancellations':cancellations,
                    'state_after':[],'memory':{'allocated':1024,'reserved':2048},'structure':{'capacity':512}})
            (root/'stress.json').write_text(json.dumps({'execution':'COMPLETED','measured_cycles':2,'warmup_cycles':0,
                'slots':16,'workload_sha256':WORKLOAD_SHA256,'cycles':rows}))
        self.original=json.loads((self.right/'stress.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def run_compare(self):
        return compare(self.left,self.right,cycles=2,warmup=0)

    def change(self, mutate):
        data=copy.deepcopy(self.original)
        mutate(data)
        (self.right/'stress.json').write_text(json.dumps(data))

    def test_actual_audio_and_reuse_match_in_bounded_fixture(self):
        report=self.run_compare()
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['matched_complete_outputs'],32)
        self.assertEqual(report['cancelled_prefixes_per_arm'],8)
        self.assertEqual(report['performance'],'NOT_EVALUATED')

    def test_cancelled_or_duplicate_generation_cannot_be_success(self):
        mutations=[
            lambda x:x['cycles'][0]['cancellations'][0].update(status='PASS'),
            lambda x:x['cycles'][0]['completions'].append(x['cycles'][0]['completions'][0]),
            lambda x:x['cycles'][0]['completions'][0].update(finish_reason='length'),
            lambda x:x['cycles'][0].update(state_after=[7]),
            lambda x:x.update(execution='FAILED',failure_kind='contract',error='state mismatch'),
            lambda x:x['cycles'][0]['completions'][0].update(frames=2),
            lambda x:x['cycles'][0]['completions'][0]['chunks'].clear(),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.change(mutate)
                with self.assertRaises(Violation):self.run_compare()

    def test_missing_and_tampered_audio_or_coverage_never_pass(self):
        file=self.right/'0-0-g0.wav'
        original=file.read_bytes()
        file.rename(self.right/'missing.wav')
        with self.assertRaises(FileNotFoundError):self.run_compare()
        (self.right/'missing.wav').rename(file)
        file.write_bytes(original[:-2])
        with self.assertRaises(Violation):self.run_compare()
        file.write_bytes(original)
        self.change(lambda x:x['cycles'].pop())
        with self.assertRaises(Incomplete):self.run_compare()
        self.change(lambda x:x['cycles'][0]['completions'][0].update(file='../reference/0-0-g0.wav'))
        with self.assertRaises(Violation):self.run_compare()

    def test_memory_or_structure_evidence_preserves_three_verdicts(self):
        self.change(lambda x:x['cycles'][1]['memory'].update(allocated=128*1024*1024))
        self.assertEqual(self.run_compare()['status'],'FAIL')
        self.change(lambda x:x['cycles'][1]['structure'].update(capacity=1024))
        self.assertEqual(self.run_compare()['status'],'INCONCLUSIVE')
        self.change(lambda x:x['cycles'][1].pop('memory'))
        with self.assertRaises(KeyError):self.run_compare()


if __name__=='__main__':
    unittest.main()