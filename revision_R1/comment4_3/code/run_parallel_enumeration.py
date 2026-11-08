"""Separate phase: one scenario, four disjoint state chunks, four physical cores."""
from common43 import *
import concurrent.futures,multiprocessing
NET=None;SCENARIOS=None;BARRIER=None

def initialize(barrier,pool_key):
 global NET,SCENARIOS,BARRIER
 BARRIER=barrier
 index=(multiprocessing.current_process()._identity[0]-1)%4
 psutil.Process().cpu_affinity([FOUR_CORES[index]])
 NET=ex.Network(ex.MODEL);warm(NET)
 allph=pd.read_csv(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');SCENARIOS={}
 for sid,g in allph.groupby('scenario_id'):
  ph=g.sort_values('physical_link_id');roads,_=ex.select_roads(ph);SCENARIOS[int(sid)]=(ph,roads)
 dump(OUT/f'03_enum_within_scenario_4core/{pool_key}/worker_ready_{os.getpid()}.json',{'pid':os.getpid(),'cpu':FOUR_CORES[index],'at':now()})
 BARRIER.wait(timeout=180)

def probe(i):return os.getpid()

def chunk(sid,index):
 psutil.Process().cpu_affinity([FOUR_CORES[index]])
 ph,roads=SCENARIOS[sid]
 # Four submissions must occupy four separate workers before any UE solve.
 BARRIER.wait(timeout=180)
 start=time.perf_counter()
 result=[NET.solve(ph,roads,m,1e-9) for m in range(index*256,(index+1)*256)]
 return {'states':result,'worker_wall':time.perf_counter()-start,'cpu':FOUR_CORES[index],'pid':os.getpid(),'chunk_index':index}

def main():
 assert js(OUT/'logs/serial_batch_completion.json')['status']=='COMPLETE'
 verify_sources();pin()
 target=OUT/'03_enum_within_scenario_4core'
 # This is a separate resource configuration, never part of single-core means.
 protocol={'started':now(),'source_sha256':sha(Path(__file__)),'UE_processes':4,'CPUs':FOUR_CORES,'scenario_concurrency':1,'chunks':'mask0:255,256:511,512:767,768:1023',
  'repeats':3,'online_scope':'dispatch, process synchronization, UE execution, state return and DP included; shared warm-pool initialization and all input loading excluded and separately recorded'}
 dump(target/'parallel_execution_protocol.json',protocol)
 ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(4);pool_key=f'pool_{int(time.time())}_{os.getpid()}'
 batchstart=time.perf_counter();setupstart=time.perf_counter()
 with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=ctx,initializer=initialize,initargs=(barrier,pool_key)) as pool:
  list(pool.map(probe,range(4)));setup=time.perf_counter()-setupstart
  ready=list((target/pool_key).glob('worker_ready_*.json'));assert len(ready)==4
  workerlist=[js(p) for p in ready];assert {x['cpu'] for x in workerlist}==set(FOUR_CORES)
  dump(target/'pool_setup.json',{'setup_seconds_including_process_start_and_JIT_warm':setup,'workers':workerlist,'primary_serial_batch_already_complete':True})
  completed=[]
  for repeat in range(3):
   for sid in range(3001,3031):
    folder=target/f'runs/scenario_{sid}/repeat_{repeat:02d}';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'timing.json').exists():completed.append(js(folder/'timing.json'));continue
    # No scientific process other than this controller and its four workers.
    allowed={os.getpid()}|{x['pid'] for x in workerlist}
    others=[p.info for p in psutil.process_iter(['pid','name']) if 'python' in (p.info['name'] or '').lower() and p.pid not in allowed]
    if others:raise RuntimeError('Concurrent Python scientific process during parallel enumeration')
    dump(OUT/'logs/current_parallel_enum_task.json',{'scenario_id':sid,'repeat':repeat,'completed':len(completed),'total':90,'at':now()})
    stamp=now();start=time.perf_counter();futures=[pool.submit(chunk,sid,i) for i in range(4)];chunks=[f.result() for f in futures]
    ue_end=time.perf_counter();states=sorted([r for c in chunks for r in c['states']],key=lambda x:x['subset_mask'])
    assert len(states)==1024 and set(r['subset_mask'] for r in states)==set(range(1024))
    # Road mapping was loaded before timing in the controller.
    roads=CONTROLLER_ROADS[sid]
    d0=time.perf_counter();value,sequence=ex.exact_dp({r['subset_mask']:r['loss'] for r in states},roads);end=time.perf_counter()
    sol=js(ROOT/f'exact/scenario_{sid}/exact_solution.json')
    checks={'objective_bitwise_equal':float(value).hex()==float(sol['exact_objective']).hex(),'sequence_equal':list(sequence)==sol['sequence'],
      'four_distinct_UE_worker_processes':len({c['pid'] for c in chunks})==4,'four_distinct_physical_cores':{c['cpu'] for c in chunks}==set(FOUR_CORES)}
    checks['all_pass']=all(checks.values());assert checks['all_pass']
    assert all(r['converged'] and r['relative_gap']<=1e-9 for r in states)
    result={'scenario_id':sid,'method':'enum_within_scenario_4core','repeat_id':repeat,'unique_UE_queries':1024,'total_online_wall':end-start,
      'UE_parallel_wall_including_IPC':ue_end-start,'DP_wall':end-d0,'assembly_and_controller_wall':d0-ue_end,
      'UE_kernel_work_sum_not_wall':sum(r['solver_seconds'] for r in states),'worker_walls':[c['worker_wall'] for c in chunks],
      'worker_processes':[c['pid'] for c in chunks],'cores':FOUR_CORES,'processes':4,'threads_per_worker':1,
      'target_value':value,'target_hex':float(value).hex(),'sequence':list(sequence),'regret_pct':max(0,100*(value-sol['exact_objective'])/sol['exact_objective']),
      'max_actual_RG':max(r['relative_gap'] for r in states),'bitwise_gate':checks,'started_Asia_Shanghai':stamp,'finished_Asia_Shanghai':now(),
      'pool_setup_wall_excluded':setup,'fresh_independent_state_solves':True,'source_sha256':sha(Path(__file__))}
    csv(folder/'all_1024_states.csv.gz',states);dump(folder/'timing.json',result);completed.append(result)
    print(f"ENUM4 {len(completed)}/90 sid={sid} repeat={repeat} wall={result['total_online_wall']:.4f} bitwise=PASS",flush=True)
 dump(OUT/'logs/parallel_enum_completion.json',{'status':'COMPLETE','tasks':len(completed),'pool_startup_seconds':setup,'complete_batch_wall_seconds':time.perf_counter()-batchstart,'at':now()})
 verify_sources()

CONTROLLER_ROADS={}
if __name__=='__main__':
 d=pd.read_csv(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv')
 CONTROLLER_ROADS={int(sid):ex.select_roads(g.sort_values('physical_link_id'))[0] for sid,g in d.groupby('scenario_id')}
 main()
