"""Actual A2-host CPU fixture checks for the pinned runner; no NPU imports."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inferrsi-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if os.name!='posix':
        raise ValueError('Linux process-group checks require the A2 host/container')
    sys.path.insert(0,str(args.inferrsi_root/'src'))
    from inferrsi.runspec import RunSpec
    from inferrsi.harness.runner import run_experiment
    assert subprocess.check_output(['git','-C',str(args.inferrsi_root),'rev-parse','HEAD'],text=True).strip()=='bd5e356ac9267362c80f27adba61d76e047583c7'
    assert not subprocess.check_output(['git','-C',str(args.inferrsi_root),'status','--porcelain'],text=True).strip()
    args.output.mkdir(parents=True,exist_ok=False)
    baseline,candidate=args.output/'baseline',args.output/'candidate'
    helper='''import json,os,pathlib,sys,time
sys.path.insert(0,sys.argv[1])
from inferrsi.infra.processes import launch_server
out=pathlib.Path(os.environ['INFERRSI_RESULT_PATH'])
with (out.parent/'server.log').open('wb') as log:
 process,ownership=launch_server([sys.executable,str(pathlib.Path(__file__).with_name('server.py')),str(out.parent/'pids.json')],pathlib.Path.cwd(),None,log)
 (out.parent/'ownership.json').write_text(json.dumps(ownership))
 while True:time.sleep(1)
'''
    server='''import json,os,pathlib,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(3600)'])
pathlib.Path(sys.argv[1]).write_text(json.dumps({'server':os.getpid(),'child':child.pid,'group':os.getpgrp()}))
while True:time.sleep(1)
'''
    benchmark='''import json,os,pathlib,sys
out=pathlib.Path(os.environ['INFERRSI_RESULT_PATH'])
with pathlib.Path(sys.argv[2]).open('a') as log:log.write(sys.argv[1]+'\\n')
out.write_text(json.dumps({'metrics':{'value':100 if sys.argv[1]=='A' else 120}}))
'''
    for repo in (baseline,candidate):
        repo.mkdir()
        for name,text in [('fixture.py',benchmark),('helper.py',helper),('server.py',server)]:
            (repo/name).write_text(text)
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=zengchuang','-c','user.email=zengchuang3@huawei.com',
            'commit','-q','-s','-m','Create isolated CPU process fixtures','-m','Agent-assisted-by: Codex (validation)'],check=True)
    ledger=args.output/'order.log'
    common=dict(repo=str(baseline),candidate_repo=str(candidate),repo_type='qwen3_tts_cpp',backend='cpu',
        scenario='cpu_fixture_only',metric_key='metrics.value',metric_unit='synthetic',comparison_scope='CPU fixture; no inference',
        direction='maximize',min_improvement_pct=5,output_dir=str(args.output/'runs'))
    spec=RunSpec(**common,baseline_command=(sys.executable,str(baseline/'fixture.py'),'A',str(ledger)),
        candidate_command=(sys.executable,str(candidate/'fixture.py'),'B',str(ledger)),
        validation_command=(sys.executable,'-c','pass'),repetitions=3,max_minutes=2)
    normal=run_experiment(spec,{'scope':'actual CPU subprocess; all numbers synthetic'})
    evaluation=json.loads((normal/'evaluation.json').read_text())
    assert evaluation['verdict']=='PASS',evaluation
    assert ledger.read_text().splitlines()==['A','B','B','A','A','B'],ledger.read_text()
    timeout=RunSpec(**common,baseline_command=(sys.executable,str(baseline/'helper.py'),str(args.inferrsi_root/'src')),
        candidate_command=(sys.executable,str(candidate/'helper.py'),str(args.inferrsi_root/'src')),
        validation_command=(sys.executable,'-c','pass'),repetitions=1,max_minutes=.05)
    timed=run_experiment(timeout,{'scope':'expected hard timeout; no accelerator runtime'})
    failed=json.loads((timed/'evaluation.json').read_text())
    assert failed['verdict']=='INCONCLUSIVE',failed
    trial=timed/'baseline/trial-001'
    ownership=json.loads((trial/'ownership.json').read_text())
    pids=json.loads((trial/'pids.json').read_text())
    execution=json.loads((trial/'execution.json').read_text())
    assert ownership['mode']=='inferrsi_trial_group' and ownership['server_start_new_session'] is False,ownership
    assert pids['group']==ownership['process_group_id'],(pids,ownership)
    assert execution['status']=='timeout' and execution['returncode']==-9,execution
    def live(pid):
        path=Path(f'/proc/{pid}/stat')
        return path.exists() and path.read_text().rsplit(')',1)[1].split()[0]!='Z'
    deadline=time.monotonic()+5
    while any(live(pid) for pid in (pids['server'],pids['child'])) and time.monotonic()<deadline:
        time.sleep(.05)
    assert not any(live(pid) for pid in (pids['server'],pids['child'])),pids
    result={'status':'PASS','scope':'A2-host CPU subprocess order/source and hard-timeout ownership only; no NPU',
        'normal_fixture_run':str(normal),'normal_fixture_primary_verdict':evaluation['verdict'],
        'order':['A','B','B','A','A','B'],'timeout_fixture_run':str(timed),'expected_timeout_verdict':failed['verdict'],
        'actual_timeout_exit':execution['returncode'],'ownership':ownership,'pids':pids,'owned_workers_live_after_timeout':[]}
    (args.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()