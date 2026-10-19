import json,os,pathlib,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(3600)'])
pathlib.Path(sys.argv[1]).write_text(json.dumps({'server':os.getpid(),'child':child.pid,'group':os.getpgrp()}))
while True:time.sleep(1)
