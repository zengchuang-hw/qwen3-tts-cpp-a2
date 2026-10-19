import json,os,pathlib,sys,time
sys.path.insert(0,sys.argv[1])
from inferrsi.infra.processes import launch_server
out=pathlib.Path(os.environ['INFERRSI_RESULT_PATH'])
with (out.parent/'server.log').open('wb') as log:
 process,ownership=launch_server([sys.executable,str(pathlib.Path(__file__).with_name('server.py')),str(out.parent/'pids.json')],pathlib.Path.cwd(),None,log)
 (out.parent/'ownership.json').write_text(json.dumps(ownership))
 while True:time.sleep(1)
