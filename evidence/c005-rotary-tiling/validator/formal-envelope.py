"""Frozen C005 seven-cohort acceptance envelope; no model/source mutation."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

root=Path('/work/c005-formal')
src=Path('/work/c005-selected/source')
build=Path('/work/c005-selected/build')
manifest=json.loads(Path('/work/c005-selected/source-manifest.json').read_text())
sys.path.insert(0,str(src))
from campaign import runtime_identity, source_identity

def write(name,value):
    (root/name).write_text(json.dumps(value,indent=2)+'\n')

def verify():
    for f,h in manifest['files'].items():
        if hashlib.sha256((src/f).read_bytes()).hexdigest()!=h:
            raise ValueError('source differs: '+f)

root.mkdir(exist_ok=False)
verify()
identity=source_identity(src,build)
environment=runtime_identity(Path('/model'),Path('/work/reference'))
command=[sys.executable,str(src/'campaign.py'),'--reference-root','/work/reference','--native-build',str(build),
    '--model','/model','--workload','/work/reference/evidence/campaign-20261017/plan/workload-128.jsonl',
    '--predictor-rope','paired','--rotary-head-tile','auto','--audio-delivery','inline',
    '--reference-engine','upstream','--concurrencies','1','2','4','8','16','32','64',
    '--requests','128','--repetitions','3','--benchmark-timeout','1200','--output',str(root/'results')]
plan={'scope':'full matched upstream AB/BA/AB, seven C,128 timed per cohort', 'tested_commit':manifest['commit'],
    'source_manifest':manifest,'binaries':identity['binaries'],'environment_before':environment,'command':command,
    'required_throughput_min_ratio_strictly_greater_than':1.05,'required_p95_max_ratio_at_most':1.05,
    'relative_quality':'exact actual PCM; changed/missing audio cannot PASS','physical_device':3,'logical_device':0,
    'formal_coverage':True,'max_campaign_seconds':6900,
    'envelope_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
write('plan.json',plan)
record={'execution':'INCONCLUSIVE','assessment':'INCONCLUSIVE','commands':[]}
try:
    with (root/'campaign.log').open('wb') as log:
        process=subprocess.Popen(command,cwd=src,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code=process.wait(timeout=6900)
        except subprocess.TimeoutExpired:
            record['deadline_exceeded']=True
            # SIGINT lets campaign's finally stop and wait its separately-owned
            # server group, and interrupts its benchmark child in this group.
            os.killpg(process.pid,signal.SIGINT)
            try:
                code=process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                code=process.wait()
    record['commands'].append({'argv':command,'exit':code})
    if code!=0:
        raise ValueError('campaign did not finish cleanly')
    record['execution']='COMPLETED'
    verify()
    if source_identity(src,build)!=identity or runtime_identity(Path('/model'),Path('/work/reference'))!=environment:
        raise ValueError('source, binary, environment or model drifted')
    assess=[sys.executable,str(src/'assess.py'),'--run',str(root/'results'),'--output',str(root/'results/assessment.json')]
    with (root/'assessment.log').open('wb') as log:
        result=subprocess.run(assess,cwd=src,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    record['commands'].append({'argv':assess,'exit':result.returncode})
    verdict=json.loads((root/'results/assessment.json').read_text())['status']
    if result.returncode!={'PASS':0,'FAIL':1,'INCONCLUSIVE':2}[verdict]:
        raise ValueError('assessor exit and verdict disagree')
    record['assessment']=verdict
    record['environment_after']=runtime_identity(Path('/model'),Path('/work/reference'))
    if record['environment_after'] != environment:
        raise ValueError('environment changed during assessment')
    verify()
except Exception as error:
    record['assessment']='INCONCLUSIVE'
    record['error']=f'{type(error).__name__}: {error}'
finally:
    write('envelope-result.json',record)
    print(json.dumps(record),flush=True)
sys.exit({'PASS':0,'FAIL':1,'INCONCLUSIVE':2}[record['assessment']])