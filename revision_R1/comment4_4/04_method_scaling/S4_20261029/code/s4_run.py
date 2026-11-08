from s4_common import *
import subprocess
def other_python(allowed):
 return [p.info for p in psutil.process_iter(['name','pid']) if 'python' in (p.info['name'] or '').lower() and p.pid not in allowed]
def run(job,kind):
 sid=int(job['scenario_id']);m=int(job['m']);method=job.get('method',kind);rep=int(job.get('replicate',0))
 folder=OUT/(f'optimization/scenario_{sid}/m_{m:02d}/{method}/rep_{rep:02d}' if kind=='optimization' else f'{kind}/scenario_{sid}/m_{m:02d}')
 folder.mkdir(parents=True,exist_ok=True)
 if (folder/'monitor.json').exists():return js(folder/'monitor.json')
 assert not other_python({os.getpid()}),'Other Python job active before task'
 args=[str(OUT/'code/s4_parallel_job.py'),str(sid),str(m),str(folder)] if kind=='enum_4core' else [str(OUT/'code/s4_worker.py'),kind,str(sid),str(m),method,str(rep),str(folder)]
 log=(folder/'worker.log').open('w',encoding='utf-8');p=subprocess.Popen([sys.executable,*args],stdout=log,stderr=subprocess.STDOUT)
 begun=time.perf_counter();peak=0;peakonline=0;peakexport=0;start=None;stop=None;reason=None;samples=0;last_other_check=0.;known_pids={p.pid};cfg=protocol()
 while p.poll() is None:
  try:
   proc=psutil.Process(p.pid);tree=[proc]+proc.children(recursive=True);known_pids|={x.pid for x in tree};rss=0
   for x in tree:
    try:rss+=x.memory_info().rss
    except psutil.NoSuchProcess:pass
  except psutil.NoSuchProcess:break
  peak=max(peak,rss);samples+=1
  try:
   if start is None and (folder/'ready.json').exists():start=js(folder/'ready.json')['started_perf_counter']
   if stop is None and (folder/'timing_stopped.json').exists():stop=js(folder/'timing_stopped.json')['stopped_perf_counter']
  except (ValueError,PermissionError):pass
  if start is not None and stop is None:peakonline=max(peakonline,rss)
  if stop is not None:peakexport=max(peakexport,rss)
  if time.perf_counter()-last_other_check>3:
   others=other_python({os.getpid()}|known_pids);last_other_check=time.perf_counter()
   if others:reason='CONCURRENT_PYTHON_TASK'
  if rss>cfg['RSS_limit_bytes']:reason='RSS_LIMIT'
  if start is not None and stop is None and time.perf_counter()-start>cfg['max_task_seconds']+.25:reason='TASK_TIME_LIMIT_HARD_STOP'
  if start is None and time.perf_counter()-begun>240:reason='STARTUP_TIMEOUT'
  if reason:
   # Only this owned process tree is terminated; no filesystem cleanup or unrelated process control.
   owned_children=proc.children(recursive=True)
   for child in owned_children:
    try:child.kill()
    except psutil.NoSuchProcess:pass
   try:proc.kill()
   except psutil.NoSuchProcess:pass
   psutil.wait_procs(owned_children,timeout=5)
   break
  time.sleep(.05)
 code=p.wait();log.close();timing=js(folder/'timing.json') if (folder/'timing.json').exists() else None
 record={'scenario_id':sid,'m':m,'method':method,'replicate':rep,'kind':kind,'status':timing['status'] if timing else 'SCALING_FAILURE','resource_stop':reason,'exit_code':code,'parent_wall_including_setup_export':time.perf_counter()-begun,'peak_process_tree_RSS_bytes':peak,'peak_online_process_tree_RSS_bytes':peakonline if peakonline else None,'peak_export_RSS_bytes':peakexport if peakexport else None,'monitor_samples':samples,'sampling_nominal_s':.05,'elapsed_to_hard_stop_since_ready':time.perf_counter()-start if start and reason else None,'online_wall':timing['online_wall'] if timing else None,'UE_queries':timing['UE_queries'] if timing else None,'worker_dir':str(folder),'owned_process_ids':sorted(known_pids),'task_cap_s':cfg['max_task_seconds']}
 if reason or code:record['status']='SCALING_FAILURE'
 dump(folder/'monitor.json',record);print(json.dumps({k:record[k] for k in ['scenario_id','m','method','replicate','status','resource_stop','online_wall','UE_queries']},ensure_ascii=False),flush=True)
 return record
def main():
 psutil.Process().cpu_affinity([8]);verify_s4();assert not other_python({os.getpid()})
 schedule=frame(OUT/'00_lock/S4_optimization_schedule.csv').to_dict('records');optimization=[]
 for j in schedule:
  dump(OUT/'logs/current_task.json',{'phase':'optimization','total':180,**j,'at':now()});optimization.append(run(j,'optimization'));csv(OUT/'analysis/S4_optimization_execution_status.csv',optimization)
 verify_s4();freeze=OUT/'00_lock/optimization_outputs_freeze.json'
 files=[p for p in (OUT/'optimization').rglob('*') if p.is_file()]
 hashes={str(p):sha(p) for p in files}
 if freeze.exists():assert js(freeze)['sha256']==hashes
 else:dump(freeze,{'frozen_at':now(),'optimization_tasks':180,'failures_retained':sum(r['status']!='PASS' for r in optimization),'before_any_full_table_solve':True,'sha256':hashes})
 print('ALL180_OPTIMIZATION_OUTPUTS_FROZEN_BEFORE_ENUMERATION',flush=True)
 enum=frame(OUT/'00_lock/S4_enumeration_schedule.csv').to_dict('records')
 for kind in ['enum_serial','enum_4core']:
  rows=[]
  for j in enum:
   dump(OUT/'logs/current_task.json',{'phase':kind,'total':18,**j,'at':now()});rows.append(run(j,kind));csv(OUT/f'analysis/S4_{kind}_execution_status.csv',rows)
  dump(OUT/f'logs/{kind}_completion.json',{'tasks':18,'completed':sum(r['status']=='PASS' for r in rows),'failures_retained':sum(r['status']!='PASS' for r in rows),'at':now()})
 for p,h in js(freeze)['sha256'].items():assert sha(p)==h,'Optimization output changed after freeze'
 verify_s4();dump(OUT/'logs/S4_computation_complete.json',{'optimization_tasks':180,'serial_tables_attempted':18,'parallel_tables_attempted':18,'all_sources_unchanged':True,'at':now()})
 print('S4_ALL_COMPUTATION_PHASES_FINISHED',flush=True)
if __name__=='__main__':main()
