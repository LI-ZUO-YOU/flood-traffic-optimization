"""Sequential dispatch only; all optimization rules come from the frozen adapter files."""
from common45 import *
from run_sealed import execute
import argparse

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true',required=True);p.parse_args()
 pin();manifest=js(OUT/'protocol/freeze_manifest.json')
 for name,row in manifest['files'].items():assert sha(name)==row['sha256'],name
 assert js(OUT/'01_freeze_and_regression/F0_bitwise_v2/validation.json')['runs']==3
 for sid in [3001,3002,3003]:
  for variant in VARIANTS[1:]:
   path=OUT/f'02_smoke_old_scenarios/scenario_{sid}/{variant}/seed_00'
   r=execute(sid,variant,0,path)
   print(json.dumps({'event':'smoke_complete','scenario_id':sid,'variant':variant,'queries':r['actual_queries'],'at':now()}),flush=True)
 for variant in ['F0_FULL','F9_NO_SURROGATE']:
  execute(246,variant,0,OUT/f'01_freeze_and_regression/reproducibility_v2/scenario_246/{variant}/seed_00')
  print(json.dumps({'event':'reproducibility_complete','variant':variant,'at':now()}),flush=True)
 dump(OUT/'02_smoke_old_scenarios/dispatch_complete.json',{'at':now(),'smoke':30,'reproducibility':2,'single_compute_task':True,'live_UE_solves':0,'dispatcher_sha256':sha(Path(__file__))})

if __name__=='__main__':main()
