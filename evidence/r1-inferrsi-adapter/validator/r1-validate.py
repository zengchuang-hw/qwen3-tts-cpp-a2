"""R1 A2 envelope: CPU ownership fixtures, real short NPU trial, legacy replay."""
import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    root=args.root;src=root/'source-git';build=root/'build';out=root/'results';sdk=root/'inferrsi'
    out.mkdir(exist_ok=False)
    manifest=json.loads((root/'source-manifest.json').read_text())
    sys.path.insert(0,str(src))
    from campaign import runtime_identity
    record={'status':'INCONCLUSIVE','scope':'pinned InferRSI Harness, actual CPU cleanup fixtures and NPU C4 smoke; no full speed acceptance',
        'tested_commit':manifest['commit'],'commands':[]}
    py=sys.executable
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def save():(out/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
    def verify():
        assert subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()==manifest['commit']
        assert not subprocess.check_output(['git','-C',str(src),'status','--porcelain'],text=True).strip()
        for f,h in manifest['files'].items():
            if sha(src/f)!=h:raise ValueError('source differs: '+f)
    def run(name,argv,allowed=(0,),timeout=1200):
        verify();print('START',name,flush=True);began=time.monotonic()
        with (out/(name+'.log')).open('wb') as log:
            process=subprocess.run(argv,cwd=src,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        record['commands'].append({'name':name,'argv':list(map(str,argv)),'cwd':str(src),'exit':process.returncode,
            'wall_seconds':time.monotonic()-began});save();print('END',name,'exit',process.returncode,flush=True)
        if process.returncode not in allowed:raise ValueError(name+' required outcome differs')
    reference,model=Path('/work/reference'),Path('/model')
    try:
        verify();record['environment_before']=runtime_identity(model,reference)
        run('cpu-suite',[py,'-m','unittest','discover','-s','tests','-v'])
        run('configure',['cmake','-S',str(src),'-B',str(build),'-DPython3_EXECUTABLE='+py,'-DCMAKE_BUILD_TYPE=Release'])
        run('build',['cmake','--build',str(build),'-j','2'])
        record['binaries']={p.name:sha(p) for p in list(build.glob('_qtts_native*.so'))+[build/'qtts']}
        run('ownership',[py,str(src/'test_native_state.py'),'-v'])
        run('runner-cpu-contracts',[py,str(root/'cpu-validation.py'),'--inferrsi-root',str(sdk),
            '--output',str(out/'runner-cpu')])
        cpu=json.loads((out/'runner-cpu/validation.json').read_text())
        if cpu['status']!='PASS' or cpu['owned_workers_live_after_timeout']!=[]:
            raise ValueError('owned CPU timeout or order contract failed')
        common=[py,str(src/'rsi.py'),'run','--inferrsi-root',str(sdk),'--reference-root',str(reference),
            '--candidate-root',str(src),'--native-build',str(build),'--model',str(model),
            '--workload',str(reference/'evidence/campaign-20261017/plan/workload-128.jsonl'),
            '--predictor-rope','paired','--rotary-head-tile','auto','--audio-delivery','inline',
            '--requests','4','--repetitions','1','--primary-concurrency','4','--physical-device','3',
            '--max-minutes','10','--output-root',str(out/'runs'),'--concurrencies','4']
        run('dry-plan',[*common,'--dry-run'])
        run('rsi-npu-smoke',common,allowed=(2,))
        directories=list((out/'runs').iterdir())
        if len(directories)!=1:raise ValueError('expected exactly one new actual runner experiment')
        directory=directories[0]
        final=json.loads((directory/'tts-final.json').read_text())
        generic=json.loads((directory/'evaluation.json').read_text())
        tts=json.loads((directory/'validation/result.json').read_text())
        if final['status']!='INCONCLUSIVE' or tts['relative_quality']!='PASS_EXACT_PCM' or tts['formal_coverage'] is not False:
            raise ValueError('smoke quality or whole-target coverage semantics differ')
        if not generic['source_integrity']['verified']:
            raise ValueError('actual source snapshot unavailable or changed')
        for label in ('baseline','candidate'):
            life=json.loads((directory/label/'trial-001/tts/lifecycle.json').read_text())
            own=life['process_ownership']
            if life['server_exit']!=0 or own['mode']!='inferrsi_trial_group' or own['server_start_new_session'] is not False:
                raise ValueError('actual model server ownership or exit differs')
            if life['cleanup']['status']!='completed' or life['cleanup']['remaining_pids']:
                raise ValueError('model server cleanup left owned workers')
        record['actual_runner_directory']=str(directory)
        record['smoke']=final
        record['legacy_replays']=[]
        for name,path in [('c002',Path('/work/formal-c002-01')),('c005',Path('/work/c005-formal/results'))]:
            old=json.loads((path/'assessment.json').read_text());expected={'PASS':0,'FAIL':1,'INCONCLUSIVE':2}[old['status']]
            output=out/('replay-'+name+'.json')
            run('replay-'+name,[py,str(src/'assess.py'),'--run',str(path),'--output',str(output)],allowed=(expected,))
            new=json.loads(output.read_text())
            keys=('status','formal_coverage','cohorts','performance','relative_quality')
            if any(old[key]!=new[key] for key in keys):raise ValueError('legacy outcome changed: '+name)
            record['legacy_replays'].append({'campaign':name,'actual_exit':expected,'verdict':new['status'],
                'scope':'replay only, not new NPU measurement','old_sha256':sha(path/'assessment.json'),'new_sha256':sha(output)})
        verify();record['environment_after']=runtime_identity(model,reference)
        if record['environment_before']!=record['environment_after']:raise ValueError('model/runtime drift')
        record['status']='PASS'
    except Exception as error:
        record.update(status='FAIL',error=f'{type(error).__name__}: {error}')
    finally:
        record['log_sha256']={p.name:sha(p) for p in out.glob('*.log')}
        save();print('VALIDATION',record['status'],record.get('error',''),flush=True)
    return 0 if record['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())