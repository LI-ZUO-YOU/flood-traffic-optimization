from common43 import *

def main():
 verify_sources();pin();import torch;torch.set_num_threads(1)
 from threadpoolctl import threadpool_limits,threadpool_info
 with threadpool_limits(limits=1):
  net=ex.Network(ex.MODEL);warmstart=time.perf_counter();warm(net)
  # Touch the frozen prediction implementation on development data only.
  pred=ex.api.SurrogateV2(ex.SOURCE/'surrogate/final_ensemble')
  d=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=d[d.scenario_id==246].sort_values('physical_link_id');roads,audit=ex.select_roads(ph)
  pred.predict_members([{'depth_m':ph.depth_m.to_numpy(),'initial_closed':ph.is_closed.to_numpy(),'restored':np.zeros(38,dtype=int)}])
  dump(OUT/'logs/serial_preheat.json',{'seconds':time.perf_counter()-warmstart,'development_scenario':246,'threads':threadpool_info(),'pid':os.getpid(),'affinity':psutil.Process().cpu_affinity(),'started':now()})
  schedule=frame(OUT/'00_protocol_and_input_audit/frozen_serial_schedule.csv');batchstart=time.perf_counter();done=[]
  for task in schedule.itertuples(index=False):
   folder=OUT/f'02_serial_B256/runs/scenario_{task.scenario_id}/{task.method}/repeat_{task.replicate:02d}'
   path=folder/'timing.json'
   if path.exists():
    r=js(path);assert r['bitwise_gate']['all_pass'];done.append(r);continue
   # No other Python scientific process is allowed during primary tasks.
   others=[]
   for p in psutil.process_iter(['pid','name','cmdline']):
    if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower():others.append(p.info)
   if others:
    dump(OUT/'logs/blocked_by_other_python.json',{'at':now(),'processes':others});raise RuntimeError('Other Python process detected; refusing concurrent primary timing')
   dump(OUT/'logs/current_serial_task.json',{'task':task._asdict(),'completed':len(done),'total':len(schedule),'at':now()})
   r=execute_one(int(task.scenario_id),task.method,int(task.replicate),folder);done.append(r)
   print(f"SERIAL {len(done)}/450 sid={task.scenario_id} {task.method} rep={task.replicate} seconds={r['total_online_wall']:.4f} queries={r['unique_UE_queries']} bitwise=PASS",flush=True)
  dump(OUT/'logs/serial_batch_completion.json',{'status':'COMPLETE','tasks':len(done),'elapsed_this_invocation_seconds':time.perf_counter()-batchstart,'at':now()})
  verify_sources()

if __name__=='__main__':main()
