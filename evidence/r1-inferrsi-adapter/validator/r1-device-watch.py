"""Host-side read-only device witness for the dedicated native Q1 child."""
import argparse
import json
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
args.output.mkdir(exist_ok=False)
record = {'status': 'INCONCLUSIVE', 'scope': 'device/PID observation only, not timing evidence', 'attempts': []}
for attempt in range(180):
    snapshot = subprocess.check_output(['npu-smi', 'info'], text=True)
    (args.output / ('npu-%03d.log' % attempt)).write_text(snapshot)
    for line in snapshot.splitlines():
        columns = line.split('|')
        if len(columns) < 4 or columns[1].split() != ['3', '0'] or not columns[2].strip().isdigit():
            continue
        pid = int(columns[2].strip())
        try:
            argv = Path('/proc/%s/cmdline' % pid).read_bytes().replace(b'\0', b' ').decode()
            status = Path('/proc/%s/status' % pid).read_text()
        except (FileNotFoundError, PermissionError):
            continue
        if '/work/r1-attempt02/source-git/serve.py' not in argv:
            continue
        namespace = next((line for line in status.splitlines() if line.startswith('NSpid:')), None)
        record.update(status='MAPPED', physical_device=3, host_pid=pid, nspid=namespace,
                      argv=argv, observation_unix_ns=time.time_ns(), snapshot='npu-%03d.log' % attempt)
        record['attempts'].append({'attempt': attempt, 'match': True})
        record['docker_top'] = subprocess.check_output(
            ['docker', 'top', 'zc-qwen3-tts-cpp-20261019', '-eo', 'pid,ppid,args'], text=True)
        break
    if record['status'] == 'MAPPED':
        break
    record['attempts'].append({'attempt': attempt, 'match': False})
    end=args.root/'results/validation.json'
    if end.is_file() and json.loads(end.read_text()).get('status') in ('PASS','FAIL'):
        break
    time.sleep(5)
(args.output / 'witness.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
