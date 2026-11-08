"""Only prospectively registered NEW physical states, accepted frozen UE solver."""
from pathlib import Path
import os,sys
OUT=Path(__file__).resolve().parents[1]
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib'),'PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[k]=v
sys.dont_write_bytecode=True
BASE=Path('E:/jcr2区意见/返稿/4.1专项返修_20261026')
sys.path.insert(0,str(BASE/'runtime_deps'));sys.path.insert(0,str(BASE/'code'))
from common55 import *
import sqlite3,time,heapq,datetime,platform
import psutil,numba
from ue_solver import Network,impedance,aon
from path_ue import solve_paths
def pure_python_SPTT(cost,net,active):
 """Independent heap-Dijkstra, not the compiled AON stopping implementation."""
 graph=[[] for _ in range(24)]
 for e in np.flatnonzero(active):graph[int(net.tail[e])].append((int(net.head[e]),float(cost[e])))
 total=0.
 for origin in range(24):
  dist=[float('inf')]*24;dist[origin]=0.;queue=[(0.,origin)]
  while queue:
   value,u=heapq.heappop(queue)
   if value!=dist[u]:continue
   for v,w in graph[u]:
    candidate=value+w
    if candidate<dist[v]:dist[v]=candidate;heapq.heappush(queue,(candidate,v))
  total+=sum(float(net.od[origin,d])*dist[d] for d in range(24) if net.od[origin,d]>0)
 return total
def main():
 man=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json')
 if sha(OUT/'run_manifest.json')!=freeze['run_manifest_sha256'] or sha(OUT/'unique_requested_states.csv')!=freeze['requested_states_sha256']:raise RuntimeError('Freeze identity mismatch')
 for r in man['critical_sources']+man['frozen_code']:
  if sha(r['path'])!=r['sha256']:raise RuntimeError('Frozen source/code changed '+r['path'])
 psutil.Process().cpu_affinity([0]);net=Network(NETROOT);physical=read(PHYS);tasks=read(OUT/'unique_requested_states.csv');new=tasks[tasks.source.eq('new_UE')]
 version=digest(dict(ue_solver=sha(BASE/'code/ue_solver.py'),path_ue=sha(BASE/'code/path_ue.py'),links=sha(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/directed_links.csv'),OD=sha(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/od_long.csv'),tol=TARGET,max_outer=MAX_OUTER))
 assert version==man['solver_version'] and len(net.links)==76 and float(net.od.sum())==Q
 ODhash=hashlib.sha256(net.od.astype('<f8').tobytes()).hexdigest();contexts={}
 for sid in range(1001,1011):
  p=physical[physical.scenario_id.eq(sid)].sort_values('physical_link_id');arr=np.column_stack([p.physical_link_id,p.depth_m,p.is_closed,p.free_flow_time_multiplier,p.capacity_factor]).astype('<f8')
  contexts[sid]=dict(scenario_id=sid,physical_scenario_sha256=hashlib.sha256(arr.tobytes()).hexdigest(),OD_array_sha256=ODhash,rho=1.,Q=Q,solver_version=version,UE_tolerance=TARGET,max_outer=MAX_OUTER)
 con=sqlite3.connect(OUT/'cache/portfolio_states.sqlite3');con.execute('CREATE TABLE IF NOT EXISTS states (state_key TEXT PRIMARY KEY,scenario_id INTEGER,restored_physical_mask INTEGER,context TEXT,payload TEXT,flow BLOB,UNIQUE(scenario_id,restored_physical_mask))');con.commit()
 dump(OUT/'audit/UE_environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,pandas=pd.__version__,numba=numba.__version__,platform=platform.platform(),CPU_affinity=psutil.Process().cpu_affinity(),threads=1,solver_version=version,original_solver_files_unmodified=True,NUMBA_CACHE_DIR=os.environ['NUMBA_CACHE_DIR']))
 attempts=0;hits=0;startall=time.perf_counter()
 for index,task in enumerate(new.itertuples()):
  sid=int(task.scenario_id);physicalmask=int(task.restored_physical_mask);ctx={**contexts[sid],'restored_physical_mask':physicalmask};key=digest(ctx)
  cached=con.execute('SELECT payload FROM states WHERE state_key=?',(key,)).fetchone()
  if cached:
   rec=json.loads(cached[0]);assert rec['validation_passed'] and rec['ue_gap']<=TARGET;hits+=1;continue
  p=physical[physical.scenario_id.eq(sid)].sort_values('physical_link_id');R=restored(physicalmask)
  assert set(R)<=set(p.loc[p.is_closed.eq(1),'physical_link_id'].astype(int))
  active,fft,coef=net.state_arrays(p,R,(1<<len(R))-1)
  reach=np.eye(24,dtype=bool);reach[net.tail[active],net.head[active]]=True
  for k in range(24):reach|=reach[:,k,None]&reach[k,None,:]
  unreachable=int(np.count_nonzero((net.od>0)&~reach))
  if unreachable:raise RuntimeError('Positive OD unreachable, stop before solve')
  started=time.perf_counter();x,tstt,gap,it,ok=solve_paths(net.tail,net.head,active,net.adj,net.degree,net.od,fft,coef,TARGET,MAX_OUTER);seconds=time.perf_counter()-started;attempts+=1
  cost=impedance(x,fft,coef,active);independent_tstt=float(np.dot(x[active],cost[active]));_,sp=aon(cost,net.tail,net.head,active,net.adj,net.degree,net.od);gap2=max(0.,(independent_tstt-float(sp))/max(independent_tstt,1e-100))
  balance=np.bincount(net.tail,weights=x,minlength=24)-np.bincount(net.head,weights=x,minlength=24);balance_error=float(max(abs(balance-(net.od.sum(axis=1)-net.od.sum(axis=0)))))
  sample=index%100==0 or bool(task.uses_allclosed_counterfactual);python_sp=pure_python_SPTT(cost,net,active) if sample else None;python_gap=max(0.,(independent_tstt-python_sp)/independent_tstt) if sample and independent_tstt>0 else None
  valid=bool(ok and np.isfinite(tstt) and tstt>0 and np.isfinite(x).all() and np.isfinite(cost[active]).all() and gap<=TARGET and gap2<=TARGET*(1+1e-6) and balance_error<=1e-5 and np.min(x)>=-1e-6 and np.max(abs(x[~active]),initial=0.)<1e-6 and abs(independent_tstt-tstt)<=max(1.,abs(tstt))*1e-12 and (not sample or python_gap<=TARGET*(1+1e-6)))
  payload=dict(**ctx,state_key=key,task_id=int(task.task_id),restored_ids=R,tstt_raw=float(tstt),tstt_independent_raw=independent_tstt,ue_gap=float(gap),independent_aon_gap=gap2,python_dijkstra_SPTT=python_sp,python_dijkstra_gap=python_gap,independent_python_sample=sample,iterations=int(it),converged=bool(ok),reachable_positive_OD_pairs=528,unreachable_positive_OD_pairs=unreachable,flow_balance_max_abs=balance_error,solver_seconds=seconds,cold_start=True,open_directed_arcs=int(active.sum()),validation_passed=valid,uses_DP=bool(task.uses_DP),uses_allclosed_counterfactual=bool(task.uses_allclosed_counterfactual),timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  with (OUT/'logs/UE_attempts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(payload,ensure_ascii=False,allow_nan=False)+'\n')
  if not valid:
   dump(OUT/'logs/FAILED_state.json',payload);con.close();raise RuntimeError('UE_VALIDATION_FAILED; failed state not stored; no relaxed precision')
  con.execute('INSERT INTO states VALUES (?,?,?,?,?,?)',(key,sid,physicalmask,canonical(ctx),json.dumps(payload,ensure_ascii=False,allow_nan=False),x.astype('<f8').tobytes()));con.commit()
  if attempts%25==0:
   progress=dict(completed_new_states=con.execute('SELECT COUNT(*) FROM states').fetchone()[0],planned_new_states=len(new),last_scenario=sid,last_physical_mask=physicalmask,elapsed_seconds=time.perf_counter()-startall,new_solves_this_process=attempts,cache_hits_this_process=hits)
   dump(OUT/'logs/UE_progress.json',progress);print(json.dumps(progress),flush=True)
 records=[json.loads(r[0]) for r in con.execute('SELECT payload FROM states ORDER BY scenario_id,restored_physical_mask')];con.close()
 save(OUT/'raw/UE_query_log.csv',[{**r,'restored_ids':json.dumps(r['restored_ids'])} for r in records])
 meta=dict(status='PASS' if len(records)==man['new_states_total'] else 'PARTIAL',planned_new_states=man['new_states_total'],new_states_succeeded=len(records),new_DP_states=sum(r['uses_DP'] for r in records),new_counterfactual_only_states=sum(not r['uses_DP'] for r in records),failures=0,max_RG=max(r['ue_gap'] for r in records),max_independent_aon_RG=max(r['independent_aon_gap'] for r in records),max_python_dijkstra_RG=max(r['python_dijkstra_gap'] for r in records if r['independent_python_sample']),python_dijkstra_samples=sum(r['independent_python_sample'] for r in records),max_conservation_error=max(r['flow_balance_max_abs'] for r in records),solver_seconds=sum(r['solver_seconds'] for r in records),wall_seconds_this_process=time.perf_counter()-startall,physical_cache_hits_this_process=hits,new_UE_calls_this_process=attempts)
 dump(OUT/'audit/UE_execution_validation.json',meta);print(json.dumps(meta),flush=True)
if __name__=='__main__':main()
