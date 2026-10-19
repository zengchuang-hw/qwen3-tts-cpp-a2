import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

base = Path('/work/p1-readme-final')
out = base/'validation'
out.mkdir(exist_ok=False)
source = base/'source'
inputs = base/'inputs'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
identity = {'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'python':sys.version, 'python_executable':sys.executable,
            'platform':platform.platform(), 'container_hostname':platform.node(),
            'pid':os.getpid(), 'source_manifest_sha256':digest(source/'source-manifest.json'),
            'input_manifest_sha256':digest(inputs/'input-manifest.json'),
            'runner_sha256':digest(Path(__file__)),
            'packages':{name:importlib.metadata.version(name) for name in ('torch','torch_npu','qwen-tts','transformers')},
            'scope':'CPU/content checks executed on A2; no fresh NPU inference or WAV-byte audit'}
(out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
manifest=json.loads((inputs/'input-manifest.json').read_text())
original=[]
for name, sha in manifest['files'].items():
    old=Path('/work/c005-formal/results')/Path(name).relative_to('formal')
    uploaded=inputs/name
    assert json.loads(old.read_text()) == json.loads(uploaded.read_text()),name
    original.append({'path':str(old),'raw_sha256':digest(old),'committed_input_sha256':sha,
                     'json_equal':True,'byte_equal':digest(old)==sha})
(out/'original-c005-crosscheck.json').write_text(json.dumps(original,indent=2)+'\n')
commands=[('cpu',[sys.executable,'-m','unittest','discover','-s','tests','-v']),
          ('content',[sys.executable,str(inputs/'validator.py'),'--source',str(source),
                      '--inputs',str(inputs),'--output',str(out/'content.json')])]
records=[]
for label,argv in commands:
    with (out/f'{label}.log').open('w') as log:
        result=subprocess.run(argv,cwd=source,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    (out/f'{label}.exit').write_text(str(result.returncode)+'\n')
    records.append({'name':label,'argv':argv,'cwd':str(source),'exit':result.returncode})
summary={'status':'PASS' if all(v['exit']==0 for v in records) else 'FAIL',
         'commands':records,'tested_commit':json.loads((source/'source-manifest.json').read_text())['commit'],
         'original_c005_files_crosschecked':len(original),'fresh_npu_inference':False}
(out/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
