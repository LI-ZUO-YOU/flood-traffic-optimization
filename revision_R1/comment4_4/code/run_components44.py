from common44 import *
import subprocess,statistics,math
def run(sid,m,rep,folder,limit=None):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 if (folder/'parent_monitor.json').exists():return js(folder/'parent_monitor.json')
 log=(folder/'worker.log').open('w',encoding='utf-8');p=subprocess.Popen([sys.executable,str(OUT/'code/profile_worker44.py'),str(sid),str(m),str(rep),str(folder)],stdout=log,stderr=subprocess.STDOUT)
 started=time.perf_counter();peak=0;onlinepeak=0;onlinefirst=None;reason=None;stage=None;samples=0;pollcpu=0
 ramlimit=js(OUT/'00_lock/frozen_scaling_protocol.json')['max_RSS_bytes']
 while p.poll() is None:
  try:
   process=psutil.Process(p.pid);rss=sum(x.memory_info().rss for x in [process]+process.children(recursive=True));peak=max(peak,rss);samples+=1
  except psutil.NoSuchProcess:break
  ready=folder/'ready.json';progress=folder/'progress.json'
  if ready.exists():
   if onlinefirst is None:onlinefirst=js(ready)['online_started_perf_counter']
   onlinepeak=max(onlinepeak,rss)
  if progress.exists():
   try:stage=js(progress)['stage']
   except (ValueError,PermissionError):pass
  if rss>ramlimit:reason='RSS_LIMIT'
  elif limit and onlinefirst and time.perf_counter()-onlinefirst>limit and stage not in ['complete','export_complete']:reason='PREPROCESS_TIME_LIMIT'
  elif not onlinefirst and time.perf_counter()-started>180:reason='WORKER_STARTUP_TIMEOUT'
  if reason:
   # Verified exact owned process. No unrelated process termination.
   for child in process.children(recursive=True):child.kill()
   process.kill();break
  time.sleep(.05)
 code=p.wait();log.close();record={'scenario_id':sid,'m':m,'replicate':rep,'exit_code':code,'resource_stop':reason,'observed_stage':stage,'peak_process_tree_RSS_bytes':peak,'peak_online_sampled_RSS_bytes':onlinepeak,'monitor_samples':samples,'monitor_interval_s':.05,'parent_wall':time.perf_counter()-started,'preprocessing_limit':limit,'RSS_limit_bytes':ramlimit,'new_UE_calls':0,'completed':(folder/'result.json').exists() and code==0,'worker_dir':str(folder)}
 if onlinefirst:record['elapsed_since_ready_including_exports']=time.perf_counter()-onlinefirst
 if (folder/'result.json').exists():record['candidate_wall']=js(folder/'result.json')['candidate_wall']
 dump(folder/'parent_monitor.json',record)
 print(json.dumps(record,ensure_ascii=False),flush=True)
 return record
def main():
 assert js(OUT/'01_code_audit/regression_acceptance.json')['status']=='PASS'
 verify();psutil.Process().cpu_affinity([2])
 implementation=OUT/'00_lock/frozen_component_implementation.json'
 hashes={str(p):sha(p) for p in (OUT/'code').glob('*.py')}
 if implementation.exists():
  for p,h in js(implementation)['sha256'].items():assert sha(p)==h,'Implementation changed '+p
 else:dump(implementation,{'frozen_at':now(),'before_calibration_and_extended_results':True,'sha256':hashes,'scenario_manifest_SHA':sha(OUT/'02_scenarios/S2_scaling_scenarios_manifest.json')})
 others=[{'pid':p.pid,'name':p.info['name']} for p in psutil.process_iter(['name']) if p.pid!=os.getpid() and (p.info['name'] or '').lower().startswith('python')]
 assert not others,('Other Python jobs active',others)
 cal=[]
 for r in range(3):cal.append(run(3001,10,0,OUT/f'03_component_scaling/calibration/repeat_{r:02d}'))
 assert all(x['completed'] for x in cal),'Calibration failed'
 limit=10*statistics.median(x['candidate_wall'] for x in cal)
 resource=OUT/'00_lock/calibrated_resource_limits.json'
 data={'frozen_at':now(),'m10_calibration_wall_seconds':[x['candidate_wall'] for x in cal],'max_preprocessing_seconds':limit,'factor':10,'before_extended_component_results':True,'scope':'candidate preparation only; export excluded from deadline; process tree RSS limit independently enforced'}
 if resource.exists():assert js(resource)['max_preprocessing_seconds']==limit
 else:dump(resource,data)
 schedule=[];sizes=[8,10,12,14,16]
 for rep in range(3):
  for i,sid in enumerate(range(4401,4407)):
   offset=(i+rep)%5
   for m in sizes[offset:]+sizes[:offset]:schedule.append({'task_index':len(schedule),'scenario_id':sid,'m':m,'replicate':rep})
 csv(OUT/'00_lock/frozen_component_schedule.csv',schedule)
 records=[]
 for task in schedule:
  folder=OUT/f"03_component_scaling/runs/scenario_{task['scenario_id']}/m_{task['m']:02d}/repeat_{task['replicate']:02d}"
  dump(OUT/'logs/current_component_task.json',{'started':now(),**task,'total_tasks':len(schedule),'limit_seconds':limit})
  records.append(run(task['scenario_id'],task['m'],task['replicate'],folder,limit))
  csv(OUT/'03_component_scaling/S3_memory_profile.csv',records)
 for p,h in js(implementation)['sha256'].items():assert sha(p)==h,'Implementation changed '+p
 dump(OUT/'logs/component_batch_completion.json',{'finished':now(),'tasks':len(records),'completed':sum(x['completed'] for x in records),'resource_failures':sum(x['resource_stop'] is not None for x in records),'new_UE_calls':0,'source_files_verified':verify(),'implementation_unchanged':True})
if __name__=='__main__':main()
