"""Five prespecified cold-Python-process supplements, not new wall-clock caps."""
import time
PROCESS_ENTRY=time.perf_counter()
from common43 import *
import subprocess

def child(method):
 pin()
 if method=='proposed':
  import torch
  torch.set_num_threads(1)
 from threadpoolctl import threadpool_limits
 with threadpool_limits(limits=1):
  imported=time.perf_counter()-PROCESS_ENTRY
  folder=OUT/f'04_cold_start/{method}'
  result=execute_one(3001,method,0,folder,cold=True)
  dump(folder/'cold_child_components.json',{'import_and_policy_seconds':imported,'child_total_to_outputs_seconds':time.perf_counter()-PROCESS_ENTRY,
    'warm_code_disk_cache':True,'UE_state_cache_fresh':True,'model_and_input_loading_included_in_cold_process':True,
    'setup_input_model_seconds':result['setup_input_model_wall_excluded'],'online_seconds':result['total_online_wall'],
    'export_and_reference_check_seconds':result['export_wall_excluded'],'bitwise_gate':result['bitwise_gate'],'method':method,'scenario_id':3001,'seed_index':0})

def main():
 assert js(OUT/'logs/serial_batch_completion.json')['status']=='COMPLETE'
 verify_sources();pin();rows=[]
 for method in METHODS:
  folder=OUT/f'04_cold_start/{method}';summary=folder/'cold_parent_wall.json'
  if summary.exists():rows.append(js(summary));continue
  start=time.perf_counter()
  p=subprocess.run([sys.executable,str(Path(__file__)),'--child',method],capture_output=True,text=True,encoding='utf-8',errors='replace')
  wall=time.perf_counter()-start
  if p.returncode:
   dump(OUT/'logs/cold_child_failure.json',{'method':method,'stdout':p.stdout,'stderr':p.stderr,'returncode':p.returncode});raise RuntimeError('Cold child failed')
  c=js(folder/'cold_child_components.json')
  r={'method':method,'scenario_id':3001,'seed_index':0,'process_launch_through_exports_wall':wall,**c}
  dump(summary,r);rows.append(r);print('COLD',method,'complete process wall',wall,flush=True)
 csv(OUT/'04_cold_start/S2_cold_start_raw.csv',[{k:v for k,v in r.items() if k!='bitwise_gate'} for r in rows])
 dump(OUT/'logs/cold_completion.json',{'status':'COMPLETE','cases':5,'scope':'one fixed scenario, seed0, fresh Python process; disk compiled code cache warm; includes exports and source checks, not directly comparable with online-only primary time'})
 verify_sources()

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2])
 else:main()
