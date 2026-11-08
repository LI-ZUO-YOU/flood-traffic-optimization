from s4_common import *
import concurrent.futures,multiprocessing
BARRIER=None
def initialize(barrier,folder):
 global BARRIER
 BARRIER=barrier;idx=(multiprocessing.current_process()._identity[0]-1)%4;psutil.Process().cpu_affinity([FOUR[idx]])
 net=frozen.Network(frozen.MODEL);warm(net)
 dump(Path(folder)/f'worker_ready_{os.getpid()}.json',{'pid':os.getpid(),'core':FOUR[idx],'at':now()})
 BARRIER.wait(timeout=180)
def probe(x):return os.getpid()
def chunk(sid,m,index,folder,deadline):
 psutil.Process().cpu_affinity([FOUR[index]]);ph,roads,_,_=physical(sid,m);target=Path(folder)/f'chunk_{index}';target.mkdir(exist_ok=True)
 net=TimedNetwork(target,deadline);BARRIER.wait(timeout=180);start=time.perf_counter();rows=[];error=None
 try:
  n=(1<<m)//4
  for mask in range(index*n,(index+1)*n):rows.append(net.solve(ph,roads,mask,1e-9))
 except BaseException as e:error={'type':type(e).__name__,'reason':str(e),'traceback':traceback.format_exc()}
 finally:net.close()
 return {'rows':rows,'index':index,'core':FOUR[index],'pid':os.getpid(),'wall':time.perf_counter()-start,'UE_wall':net.wall,'calls':net.calls,'error':error}
def main():
 sid=int(sys.argv[1]);m=int(sys.argv[2]);folder=Path(sys.argv[3]);folder.mkdir(parents=True,exist_ok=True);pin()
 assert js(OUT/'00_lock/optimization_outputs_freeze.json')['optimization_tasks']==180
 ph,roads,_,_=physical(sid,m);ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(4);setup=time.perf_counter()
 with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=ctx,initializer=initialize,initargs=(barrier,str(folder))) as pool:
  list(pool.map(probe,range(4)));setupwall=time.perf_counter()-setup
  workers=[js(p) for p in folder.glob('worker_ready_*.json')];assert len(workers)==4 and {w['core'] for w in workers}==set(FOUR)
  start=time.perf_counter();deadline=start+protocol()['max_task_seconds'];began=now()
  dump(folder/'ready.json',{'started_perf_counter':start,'started_at':began,'pid':os.getpid(),'workers':workers,'cores':FOUR,'threads_each':1,'pool_setup_excluded_s':setupwall,'RSS_baseline_bytes':sum(psutil.Process(w['pid']).memory_info().rss for w in workers)+psutil.Process().memory_info().rss})
  futures=[pool.submit(chunk,sid,m,i,str(folder),deadline) for i in range(4)];chunks=[f.result() for f in futures];returned=time.perf_counter()
  states=sorted([r for c in chunks for r in c['rows']],key=lambda r:r['subset_mask']);value=None;seq=None;dpwall=0.
  full=len(states)==1<<m and {r['subset_mask'] for r in states}==set(range(1<<m)) and not any(c['error'] for c in chunks)
  if full:
   t=time.perf_counter();value,seq=exact_dp({r['subset_mask']:r['loss'] for r in states},roads);dpwall=time.perf_counter()-t
  stop=time.perf_counter();status='PASS' if full and stop<=deadline else 'SCALING_FAILURE'
  dump(folder/'timing_stopped.json',{'stopped_perf_counter':stop,'online_seconds':stop-start,'status':status,'finished_at':now()})
  csv(folder/'all_states.csv.gz',states)
  result={'scenario_id':sid,'m':m,'method':'enum_4core','replicate':0,'status':status,'online_wall':stop-start,'UE_parallel_wall_including_IPC':returned-start,'reference_DP_wall':dpwall,'assembly_and_controller_wall':stop-returned-dpwall,'UE_work_sum_not_wall':sum(c['UE_wall'] for c in chunks),'UE_queries':sum(c['calls'] for c in chunks),'actual_physical_calls':sum(c['calls'] for c in chunks),'target_objective':value,'sequence':list(seq) if seq else None,'target_hex':float(value).hex() if value is not None else None,'complete_reference':status=='PASS' and full,'max_RG':max([r['relative_gap'] for r in states],default=None),'cores':FOUR,'processes':4,'threads':1,'started_at':began,'finished_at':now(),'pool_setup_excluded_s':setupwall,'worker_details':[{k:v for k,v in c.items() if k!='rows'} for c in chunks],'cap_seconds':protocol()['max_task_seconds'],'fresh_state_solves':True}
  dump(folder/'timing.json',result)
 print(json.dumps({k:result[k] for k in ['scenario_id','m','status','online_wall','UE_queries','complete_reference']}),flush=True)
if __name__=='__main__':main()
