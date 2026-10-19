"""Pinned InferRSI library adapter; CLI-only configuration, stdlib control path."""
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from campaign import source_identity, runtime_identity, trial, write
from serve import load_reference
from assess import assess, audit_cohort, EvidenceViolation

INFER_RSI_SHA='bd5e356ac9267362c80f27adba61d76e047583c7'
MODEL_SHA='0c0e3051f131929182e2c023b9537f8b1c68adfe'


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.PIPE,timeout=20).strip()


def pinned_library(root):
    root=root.resolve()
    if git(root,'rev-parse','HEAD')!=INFER_RSI_SHA or git(root,'status','--porcelain'):
        raise ValueError('InferRSI must be the exact clean qualified Git revision')
    previous=list(sys.path)
    try:
        sys.path.insert(0,str(root/'src'))
        modules=[importlib.import_module(name) for name in ('inferrsi.runspec','inferrsi.harness.runner','inferrsi.infra.processes')]
        if any(not Path(module.__file__).resolve().is_relative_to(root/'src') for module in modules):
            raise ValueError('InferRSI imported from a different checkout')
        return SimpleNamespace(RunSpec=modules[0].RunSpec,run_experiment=modules[1].run_experiment,processes=modules[2])
    finally:
        sys.path[:]=previous


def common(parser):
    for name in ('reference-root','native-build','model','workload','inferrsi-root'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--candidate-root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--predictor-rope',choices=['native','paired'],default='native')
    parser.add_argument('--rotary-head-tile',choices=['4','8','16','auto'],default='4')
    parser.add_argument('--audio-delivery',choices=['buffered','inline'],default='buffered')
    parser.add_argument('--concurrencies',nargs='+',type=int,default=[1,2,4,8,16,32,64])
    parser.add_argument('--requests',type=int,default=128)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--primary-concurrency',type=int,default=64)
    parser.add_argument('--physical-device',type=int,default=3)
    parser.add_argument('--port',type=int,default=8199)
    parser.add_argument('--readiness-timeout',type=float,default=900)
    parser.add_argument('--benchmark-timeout',type=float,default=3600)


def normalize(args):
    for name in ('reference_root','candidate_root','native_build','model','workload','inferrsi_root'):
        setattr(args,name,getattr(args,name).resolve())
    if (args.primary_concurrency not in args.concurrencies or min(args.concurrencies)<1
        or max(args.concurrencies)>64 or len(set(args.concurrencies))!=len(args.concurrencies)
        or min(args.requests,args.repetitions)<=0
        or not all(math.isfinite(value) and value>0 for value in (args.readiness_timeout,args.benchmark_timeout))
        or args.physical_device<0):
        raise ValueError('invalid cohort, primary metric or time/device bounds')
    args.reference_engine='upstream'
    return args


def command_options(args):
    command=[]
    for name in ('reference_root','candidate_root','native_build','model','workload','inferrsi_root',
                 'predictor_rope','rotary_head_tile','audio_delivery','requests','repetitions',
                 'primary_concurrency','physical_device','port','readiness_timeout','benchmark_timeout'):
        command+=['--'+name.replace('_','-'),str(getattr(args,name))]
    return command+['--concurrencies',*map(str,args.concurrencies)]


def tts_spec(args):
    return {'reference_engine':'upstream','concurrencies':args.concurrencies,'requests':args.requests,
        'repetitions':args.repetitions,'workload_sha256':hashlib.sha256(args.workload.read_bytes()).hexdigest(),
        'formal_coverage':args.requests==128 and args.repetitions>=3
        and sorted(args.concurrencies)==[1,2,4,8,16,32,64]}


def aggregate(generic,tts):
    """The one-metric report can never override the authoritative TTS gates."""
    gv=generic.get('verdict','INCONCLUSIVE')
    tv=tts.get('status','INCONCLUSIVE')
    if tts.get('formal_coverage') is False and tts.get('relative_quality')=='PASS_EXACT_PCM':
        status='INCONCLUSIVE'
    elif 'FAIL' in (gv,tv):
        status='FAIL'
    elif 'INCONCLUSIVE' in (gv,tv) or gv not in {'PASS','FAIL'} or tv not in {'PASS','FAIL'}:
        status='INCONCLUSIVE'
    elif tts.get('formal_coverage') is not True or tts.get('relative_quality')!='PASS_EXACT_PCM':
        status='INCONCLUSIVE'
    else:
        status='PASS'
    return {'status':status,'scope':'authoritative seven-cohort TTS acceptance; generic report is primary-cohort only',
        'generic_primary_verdict':gv,'tts_verdict':tv,'formal_coverage':tts.get('formal_coverage',False)}


def run_trial(args):
    sdk=pinned_library(args.inferrsi_root)
    output=args.output.resolve()
    environment_path=os.environ.get('INFERRSI_RESULT_PATH')
    if not environment_path or Path(environment_path).resolve()!=output or output.exists():
        raise ValueError('trial requires its fresh runner-owned result path')
    if os.name!='posix' or os.getpgrp()!=os.getpid():
        raise ValueError('Ascend trial must be launched directly as the Linux runner group leader')
    if os.environ.get('ASCEND_RT_VISIBLE_DEVICES')!=str(args.physical_device):
        raise ValueError('physical device declaration differs from runtime visibility')
    load_reference(args.reference_root)
    source=source_identity(args.candidate_root,args.native_build)
    environment=runtime_identity(args.model,args.reference_root)
    args.candidate_identity=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    target=output.parent/'tts'
    trial(args,args.arm,target,supervision=sdk.processes)
    if source_identity(args.candidate_root,args.native_build)!=source or runtime_identity(args.model,args.reference_root)!=environment:
        raise ValueError('trial source, binary, model or environment changed')
    metrics,_=audit_cohort(target/f'c{args.primary_concurrency}',args.requests,args.primary_concurrency,
                         hashlib.sha256(args.workload.read_bytes()).hexdigest())
    write(target/'adapter-identity.json',{'source':source,'environment':environment,'infer_rsi_revision':INFER_RSI_SHA})
    write(output,{'execution':'COMPLETED','arm':args.arm,'artifacts':str(target),'primary_concurrency':args.primary_concurrency,
                  'metrics':{'throughput_frames_s':metrics['throughput_frames_s']}})
    return 0


def validate_trials(args):
    output=args.output.resolve()
    env=os.environ.get('INFERRSI_RESULT_PATH')
    if not env or Path(env).resolve()!=output or output.parent.name!='validation' or output.exists():
        raise ValueError('validation requires the runner-owned fresh validation/result.json')
    root=output.parent.parent
    view=output.parent/'tts-validation'
    view.mkdir(exist_ok=False)
    identities=[]
    folders={}
    try:
        for repetition in range(1,args.repetitions+1):
            for label,arm in (('baseline','reference'),('candidate','native')):
                actual=root/label/f'trial-{repetition:03d}'
                result=json.loads((actual/'result.json').read_text())
                target=(actual/'tts').resolve()
                if (result['execution']!='COMPLETED' or result['arm']!=arm
                    or result['primary_concurrency']!=args.primary_concurrency
                    or Path(result['artifacts']).resolve()!=target or not target.is_relative_to(root.resolve())):
                    raise EvidenceViolation('trial output identity or artifact path differs')
                folders[f'r{repetition}-{arm}']=target
                identities.append(json.loads((target/'adapter-identity.json').read_text()))
        if any(identity!=identities[0] for identity in identities):
            raise ValueError('source/binary/runtime identities differ across trials')
        spec=tts_spec(args)
        write(view/'runspec.json',spec)
        write(view/'campaign.json',{'status':'INCONCLUSIVE','completed':list(folders)})
        write(view/'actual-trial-directories.json',{name:str(path) for name,path in folders.items()})
        assessment=assess(view,trial_directories=folders)
    except EvidenceViolation as error:
        assessment={'status':'FAIL','error':str(error)}
    except (OSError,ValueError,KeyError,TypeError) as error:
        assessment={'status':'INCONCLUSIVE','error':f'{type(error).__name__}: {error}'}
    write(output,assessment)
    print(json.dumps(assessment),flush=True)
    # This supplied validation command proves actual PCM/complete trials only.
    # TTS performance/coverage status remains separate and authoritative.
    return 0 if assessment.get('relative_quality')=='PASS_EXACT_PCM' else 1 if assessment['status']=='FAIL' else 2


def run_campaign(args):
    if not math.isfinite(args.max_minutes) or args.max_minutes<=0:
        raise ValueError('finite positive runner deadline required')
    sdk=pinned_library(args.inferrsi_root)
    args.output_root=args.output_root.resolve()
    if any(args.output_root.is_relative_to(root) or args.native_build.is_relative_to(root)
           for root in (args.reference_root,args.candidate_root)):
        raise ValueError('outputs and build must be outside source checkouts')
    if git(args.candidate_root,'status','--porcelain'):
        raise ValueError('candidate checkout must be clean and committed')
    load_reference(args.reference_root)
    script=args.candidate_root/'rsi.py'
    if not script.is_file():
        raise ValueError('adapter must exist in the candidate checkout')
    base=[sys.executable,str(script),'trial',*command_options(args)]
    validation=[sys.executable,str(script),'validate',*command_options(args),'--output','{result}']
    spec=sdk.RunSpec(repo=str(args.reference_root),candidate_repo=str(args.candidate_root),repo_type='qwen3_tts_cpp',
        backend='ascend',scenario='tts.streaming',mode='code',baseline_command=tuple(base+['--arm','reference','--output','{result}']),
        candidate_command=tuple(base+['--arm','native','--output','{result}']),validation_command=tuple(validation),
        metric_key='metrics.throughput_frames_s',metric_unit='codec_frames/s',comparison_scope=f'http_e2e_C{args.primary_concurrency}',
        direction='maximize',repetitions=args.repetitions,min_improvement_pct=5.0,max_minutes=args.max_minutes,
        workload_id=hashlib.sha256(args.workload.read_bytes()).hexdigest(),model='Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
        model_revision=MODEL_SHA,agent='codex',device_ids=(str(args.physical_device),),device='Ascend910B3',
        executor='local',revision=git(args.candidate_root,'rev-parse','HEAD'),output_dir=str(args.output_root))
    spec.validate()
    if args.dry_run:
        print(json.dumps({'execution':'NOT_RUN','infer_rsi_revision':INFER_RSI_SHA,'runspec':spec.to_dict()},indent=2))
        return 0
    if os.name!='posix':
        raise ValueError('actual Ascend experiments require the prepared Linux host')
    before=runtime_identity(args.model,args.reference_root)
    source=source_identity(args.candidate_root,args.native_build)
    directory=sdk.run_experiment(spec,{'runtime':before,'infer_rsi_revision':INFER_RSI_SHA,'candidate':source})
    generic=json.loads((directory/'evaluation.json').read_text())
    tts_file=directory/'validation/result.json'
    tts=json.loads(tts_file.read_text()) if tts_file.is_file() else {'status':'INCONCLUSIVE','error':'TTS validation unavailable'}
    result=aggregate(generic,tts)
    if runtime_identity(args.model,args.reference_root)!=before or source_identity(args.candidate_root,args.native_build)!=source:
        result.update(status='FAIL' if result['status']=='FAIL' else 'INCONCLUSIVE',
                      error='campaign source/binary/environment drift')
    result.update(infer_rsi_revision=INFER_RSI_SHA,run_directory=str(directory),primary_concurrency=args.primary_concurrency)
    write(directory/'tts-final.json',result)
    print(json.dumps(result,indent=2),flush=True)
    return {'PASS':0,'FAIL':1,'INCONCLUSIVE':2}[result['status']]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    run=sub.add_parser('run');common(run)
    run.add_argument('--output-root',type=Path,required=True)
    run.add_argument('--max-minutes',type=float,default=120)
    run.add_argument('--dry-run',action='store_true')
    child=sub.add_parser('trial');common(child)
    child.add_argument('--arm',choices=['reference','native'],required=True)
    child.add_argument('--output',type=Path,required=True)
    check=sub.add_parser('validate');common(check)
    check.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        args=normalize(args)
        return {'run':run_campaign,'trial':run_trial,'validate':validate_trials}[args.action](args)
    except EvidenceViolation as error:
        print(json.dumps({'status':'FAIL','error':str(error)}),file=sys.stderr,flush=True)
        return 1
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'INCONCLUSIVE','error':f'{type(error).__name__}: {error}'}),file=sys.stderr,flush=True)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
