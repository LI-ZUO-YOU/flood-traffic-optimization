"""Batch2 CLI preserves all first-batch sources, scripts and sealed reports."""
from batch2_common import *
import argparse,traceback

def main():
 a=argparse.ArgumentParser();a.add_argument('--out',required=True,type=Path);a.add_argument('--stage',required=True,choices=['preflight','compute','validate','figures','delivery']);arg=a.parse_args();out=arg.out
 try:
  if arg.stage=='preflight':preflight(out)
  elif arg.stage=='compute':
   from clustered_bootstrap import run as boot
   from variance_components import run as variance
   from batch2_influence import run as influence
   boot(out);variance(out);influence(out)
  elif arg.stage=='validate':
   from test_batch2 import validate
   validate(out)
  elif arg.stage=='figures':
   from batch2_figures import render
   render(out)
  elif arg.stage=='delivery':
   from batch2_report import deliver
   deliver(out)
  log={'at':now(),'stage':arg.stage,'status':'PASS'}
 except Exception as e:
  folder=locations(out)['audit'];folder.mkdir(parents=True,exist_ok=True);log={'at':now(),'stage':arg.stage,'status':'FAIL','message':str(e),'traceback':traceback.format_exc()};dump(folder/'latest_error.json',log)
  with (folder/'execution_log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(log,ensure_ascii=False)+'\n')
  raise
 with (locations(out)['audit']/'execution_log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(log,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
