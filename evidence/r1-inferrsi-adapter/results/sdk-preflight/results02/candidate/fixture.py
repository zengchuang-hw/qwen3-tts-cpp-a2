import json,os,pathlib,sys
out=pathlib.Path(os.environ['INFERRSI_RESULT_PATH'])
with pathlib.Path(sys.argv[2]).open('a') as log:log.write(sys.argv[1]+'\n')
out.write_text(json.dumps({'metrics':{'value':100 if sys.argv[1]=='A' else 120}}))
