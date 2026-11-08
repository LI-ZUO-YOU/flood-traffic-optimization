from common import *
import sqlite3,time,heapq,platform
import psutil,numba
from ue_solver import Network,impedance,aon
from path_ue import solve_paths
def independent_sp(cost,net,active):
 graph=[[] for _ in range(24)]
 for e in np.flatnonzero(active):graph[int(net.tail[e])].append((int(net.head[e]),float(cost[e])))
 sp=0.
 for origin in range(24):
  d=[float('inf')]*24;d[origin]=0.;heap=[(0.,origin)]
  while heap:
   value,u=heapq.heappop(heap)
   if value!=d[u]:continue
   for v,w in graph[u]:
    candidate=value+w
    if candidate<d[v]:d[v]=candidate;heapq.heappush(heap,(candidate,v))
  for v in range(24):
   if net.od[origin,v]>0:sp+=float(net.od[origin,v])*d[v]
 return sp
def main():
 init();man=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json')
 assert man['status']=='FROZEN_BEFORE_FIRST_NEW_UE' and man['new_unique_states']<=13000
 assert sha(OUT/'run_manifest.json')==freeze['run_manifest_sha256']
 for path,key in [('raw/unique_state_requests.csv','unique_requests_sha256'),('raw/logical_state_mapping.csv','logical_mapping_sha256'),('raw/variant_physical_fields.csv','physical_fields_sha256')]:assert sha(OUT/path)==man[key]
 for r in man['critical_sources']+man['frozen_scripts']:assert sha(r['path'])==r['sha256'],r['path']
 psutil.Process().cpu_affinity([0]);net=Network(NETROOT);tasks=read(OUT/'raw/unique_state_requests.csv');fields=read(OUT/'raw/variant_physical_fields.csv');groups={vid:g.sort_values('physical_link_id') for vid,g in fields.groupby('variant_id')};plans={r['variant_id']:r for r in man['table_plan']}
 con=sqlite3.connect(OUT/'cache/sensitivity_states.sqlite3');con.execute('CREATE TABLE IF NOT EXISTS states (state_key TEXT PRIMARY KEY,payload TEXT,flow BLOB)');con.commit()
 dump(OUT/'audit/UE_environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,pandas=pd.__version__,numba=numba.__version__,platform=platform.platform(),CPU_affinity=psutil.Process().cpu_affinity(),threads=1,path_ue_sha256=sha(BASE/'code/path_ue.py'),ue_solver_sha256=sha(BASE/'code/ue_solver.py'),independent_runner_sha256=sha(__file__)))
 start=time.perf_counter();new_count=0;hits=0
 for task in tasks[tasks.source.eq('new_UE')].itertuples():
  if con.execute('SELECT 1 FROM states WHERE state_key=?',(task.state_key,)).fetchone():hits+=1;continue
  p=groups[task.variant_id];E=plans[task.variant_id]['road_bit_order'];key,active,fft,coef=state_context(p,E,int(task.subset_mask),net);assert key==task.state_key
  reach=np.eye(24,dtype=bool);reach[net.tail[active],net.head[active]]=True
  for k in range(24):reach|=reach[:,k,None]&reach[k,None,:]
  if np.any((net.od>0)&~reach):raise RuntimeError('UNREACHABLE_OD stop; no finite cost written')
  began=time.perf_counter();x,tstt,gap,it,ok=solve_paths(net.tail,net.head,active,net.adj,net.degree,net.od,fft,coef,TARGET,MAX_OUTER);seconds=time.perf_counter()-began
  cost=impedance(x,fft,coef,active);numpy_cost=fft[active]+coef[active]*np.power(x[active],4);tstt2=float(np.dot(x[active],numpy_cost));_,sp=aon(cost,net.tail,net.head,active,net.adj,net.degree,net.od);rg=max(0.,(tstt2-float(sp))/tstt2)
  balance=np.bincount(net.tail,weights=x,minlength=24)-np.bincount(net.head,weights=x,minlength=24);err=float(np.max(abs(balance-(net.od.sum(axis=1)-net.od.sum(axis=0)))))
  sample=new_count%100==0;heapsp=independent_sp(cost,net,active) if sample else None;heapgap=max(0.,(tstt2-heapsp)/tstt2) if sample else None
  valid=bool(ok and np.isfinite(tstt) and tstt>0 and np.isfinite(x).all() and np.isfinite(numpy_cost).all() and gap<=TARGET and rg<=TARGET*(1+1e-6) and err<=1e-5 and np.min(x)>=-1e-6 and np.max(abs(x[~active]),initial=0.)<=1e-6 and abs(tstt2-tstt)<=1e-12*max(1.,abs(tstt)) and (not sample or heapgap<=TARGET*(1+1e-6)))
  payload=dict(state_key=key,variant_id=task.variant_id,scenario_id=int(task.scenario_id),subset_mask=int(task.subset_mask),restored_ids=task.restored_ids,physical_depth_sha256=task.physical_depth_sha256,full_mapping_sha256=task.full_mapping_sha256,tstt_raw=float(tstt),TSTT_veh_h=.01*float(tstt),ATT_min=.6*float(tstt)/Q,loss=float(tstt/T0-1),ue_gap=float(gap),numpy_tstt=tstt2,independent_AON_RG=rg,independent_Dijkstra_RG=heapgap,sampled_independent_Dijkstra=sample,iterations=int(it),converged=bool(ok),flow_balance_max_abs=err,positive_OD_reachable=528,solver_seconds=seconds,validation_passed=valid,timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with (OUT/'logs/UE_attempts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(payload,ensure_ascii=False,allow_nan=False)+'\n')
  if not valid:
   dump(OUT/'logs/FAILED_state.json',payload);con.close();raise RuntimeError('UE precision QA failed; no relaxed fallback')
  con.execute('INSERT INTO states VALUES (?,?,?)',(key,canonical(payload),x.astype('<f8').tobytes()));con.commit();new_count+=1
  if new_count%100==0:
   progress=dict(completed=con.execute('SELECT COUNT(*) FROM states').fetchone()[0],planned=man['new_unique_states'],last_variant=task.variant_id,wall_seconds=time.perf_counter()-start)
   dump(OUT/'logs/UE_progress.json',progress);print(canonical(progress),flush=True)
 records=[json.loads(r[0]) for r in con.execute('SELECT payload FROM states ORDER BY state_key')];con.close();save(OUT/'raw/new_UE_query_log.csv',records)
 checks=dict(status='PASS' if len(records)==man['new_unique_states'] else 'PARTIAL',planned_new_states=man['new_unique_states'],new_states_succeeded=len(records),new_UE_calls_this_process=new_count,cache_hits_this_process=hits,max_RG=max(r['ue_gap'] for r in records),max_independent_AON_RG=max(r['independent_AON_RG'] for r in records),max_Dijkstra_RG=max(r['independent_Dijkstra_RG'] for r in records if r['sampled_independent_Dijkstra']),independent_Dijkstra_samples=sum(r['sampled_independent_Dijkstra'] for r in records),max_conservation_error=max(r['flow_balance_max_abs'] for r in records),solver_seconds=sum(r['solver_seconds'] for r in records),wall_seconds_this_process=time.perf_counter()-start)
 dump(OUT/'audit/UE_execution_validation.json',checks);print(canonical(checks),flush=True)
if __name__=='__main__':main()
