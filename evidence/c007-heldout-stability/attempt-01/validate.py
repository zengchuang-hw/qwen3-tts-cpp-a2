"""C007 frozen quality/state envelope; all settings are CLI or internal evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    root=args.root
    src,build,out=root/'source',root/'build',root/'results'
    out.mkdir(exist_ok=False)
    manifest=json.loads((root/'source-manifest.json').read_text())
    sys.path.insert(0,str(src))
    from campaign import runtime_identity
    record={'status':'INCONCLUSIVE','scope':'held-out exact PCM and bounded direct-state stress; no new performance acceptance',
        'tested_commit':manifest['commit'],'physical_device':3,'logical_device':0,'commands':[]}
    py=sys.executable
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def save():
        (out/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
    def verify():
        for name,expected in manifest['files'].items():
            if sha(src/name)!=expected:
                raise ValueError('frozen source differs: '+name)
    class ContractFailure(Exception):pass
    def run(name,argv,timeout=1200,allowed=(0,)):
        verify()
        began=time.monotonic()
        print('START',name,flush=True)
        with (out/(name+'.log')).open('wb') as log:
            process=subprocess.Popen(argv,cwd=src,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            timed_out=False
            try:
                code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out=True
                os.killpg(process.pid,signal.SIGINT)
                try:code=process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);code=process.wait()
        row={'name':name,'argv':list(map(str,argv)),'cwd':str(src),'exit':code,
             'timed_out':timed_out,'wall_seconds':time.monotonic()-began}
        record['commands'].append(row);save()
        print('END',name,'exit',code,flush=True)
        if timed_out:raise ValueError(name+' timed out; required evidence incomplete')
        if code not in allowed:raise ContractFailure(name+' required exit differs: '+str(code))
    reference,model=Path('/work/reference'),Path('/model')
    try:
        verify()
        record['environment_before']=runtime_identity(model,reference)
        run('cpu-suite',[py,'-m','unittest','discover','-s','tests','-v'])
        run('configure',['cmake','-S',str(src),'-B',str(build),'-DPython3_EXECUTABLE='+py,'-DCMAKE_BUILD_TYPE=Release'])
        run('build',['cmake','--build',str(build),'-j','2'])
        record['binaries']={p.name:sha(p) for p in list(build.glob('_qtts_native*.so'))+[build/'qtts']}
        run('ownership',[py,str(src/'test_native_state.py'),'-v'])
        heldout=src/'data/heldout-32.jsonl'
        if sha(heldout)!='51ee03d4ed7d893045c64ea8944a5edc2dd59fc93a202f0419bced624ff49d0d':
            raise ValueError('held-out asset differs from prior RFC13 freeze')
        common=['--reference-root',str(reference),'--native-build',str(build),'--model',str(model)]
        candidate=['--predictor-rope','paired','--rotary-head-tile','auto','--audio-delivery','inline']
        run('heldout',[py,str(src/'campaign.py'),*common,'--workload',str(heldout),*candidate,
            '--concurrencies','4','16','--requests','32','--repetitions','1','--output',str(out/'heldout')])
        run('heldout-assessment',[py,str(src/'assess.py'),'--run',str(out/'heldout'),
            '--output',str(out/'heldout/assessment.json')],allowed=(0,1,2))
        assessment=json.loads((out/'heldout/assessment.json').read_text())
        if 'relative_quality' not in assessment or len(assessment.get('cohorts',[]))!=2:
            raise ValueError('held-out quality/coverage evidence is incomplete')
        if assessment['relative_quality']!='PASS_EXACT_PCM':
            raise ContractFailure('held-out complete exact audio gate failed')
        record['heldout_quality']='PASS_EXACT_PCM'
        record['heldout_performance']='NOT_ACCEPTANCE; all short-cohort metrics/verdict retained separately'
        workload=reference/'evidence/campaign-20261017/plan/workload-128.jsonl'
        for arm in ('reference','native'):
            run('stress-'+arm,[py,str(src/'stress_probe.py'),*common,'--workload',str(workload),
                '--engine',arm,*candidate,'--cycles','16','--warmup-cycles','2','--output',str(out/('stress-'+arm))])
        run('stress-assessment',[py,str(src/'assess_stress.py'),'--reference',str(out/'stress-reference'),
            '--candidate',str(out/'stress-native'),'--cycles','16','--warmup-cycles','2','--output',str(out/'stress-assessment.json')],allowed=(0,1,2))
        stress=json.loads((out/'stress-assessment.json').read_text())
        if stress.get('status')=='FAIL':
            raise ContractFailure('bounded stress gate failed: '+str(stress))
        if stress.get('status')!='PASS':
            raise ValueError('bounded stress evidence is incomplete: '+str(stress))
        if stress['matched_complete_outputs']!=256 or stress['cancelled_prefixes_per_arm']!=64:
            raise ValueError('bounded stress coverage differs')
        record['stress']=stress
        verify()
        record['environment_after']=runtime_identity(model,reference)
        if record['environment_before']!=record['environment_after']:
            raise ValueError('runtime/model identity drift')
        record['status']='PASS'
    except ContractFailure as error:
        record.update(status='FAIL',error=str(error))
    except Exception as error:
        record.update(status='INCONCLUSIVE',error=f'{type(error).__name__}: {error}')
    finally:
        record['log_sha256']={p.name:sha(p) for p in out.glob('*.log')}
        save();print('VALIDATION',record['status'],record.get('error',''),flush=True)
    return {'PASS':0,'FAIL':1,'INCONCLUSIVE':2}[record['status']]


if __name__=='__main__':
    raise SystemExit(main())