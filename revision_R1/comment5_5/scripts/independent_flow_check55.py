"""Independent NumPy BPR/conservation and heap-Dijkstra checks; never calls UE."""
from common55 import *
import sqlite3,heapq
def shortest_total(times,tail,head,active,od):
 graph=[[] for _ in range(24)]
 for i in np.flatnonzero(active):graph[int(tail[i])].append((int(head[i]),float(times[i])))
 total=0.
 for origin in range(24):
  d=[float('inf')]*24;d[origin]=0.;queue=[(0.,origin)]
  while queue:
   v,u=heapq.heappop(queue)
   if v!=d[u]:continue
   for end,t in graph[u]:
    new=v+t
    if new<d[end]:d[end]=new;heapq.heappush(queue,(new,end))
  total+=sum(float(od[origin,j])*d[j] for j in range(24) if od[origin,j]>0)
 return total
def main():
 net=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/directed_links.csv');odframe=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/od_long.csv');ph=read(PHYS);od=np.zeros((24,24))
 for r in odframe.itertuples():od[int(r.origin)-1,int(r.destination)-1]+=float(r.demand)
 tail=net.from_node.to_numpy(int)-1;head=net.to_node.to_numpy(int)-1;pid=net.physical_link_id.to_numpy(int)-1;capacity=net.capacity.to_numpy(float);basefft=net.free_flow_time.to_numpy(float);alpha=net.bpr_alpha.to_numpy(float);beta=net.bpr_beta.to_numpy(float)
 static={sid:ph[ph.scenario_id.eq(sid)].sort_values('physical_link_id') for sid in range(1001,1011)}
 db=OUT/'cache/portfolio_states.sqlite3';conn=sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True);checks=[];samples=[]
 for payload,blob in conn.execute('SELECT payload,flow FROM states ORDER BY scenario_id,restored_physical_mask'):
  r=json.loads(payload);sid=int(r['scenario_id']);mask=int(r['restored_physical_mask']);s=static[sid];closed=s.is_closed.to_numpy(bool).copy();mult=s.free_flow_time_multiplier.to_numpy(float).copy()
  for e in restored(mask):closed[e-1]=False;mult[e-1]=1.
  active=~closed[pid];x=np.frombuffer(blob,dtype='<f8');times=np.zeros(76);times[active]=(basefft*mult[pid])[active]*(1+alpha[active]*(x[active]/capacity[active])**beta[active]);total=float(np.dot(x,times));relative=abs(total-r['tstt_raw'])/r['tstt_raw']
  balance=np.bincount(tail,weights=x,minlength=24)-np.bincount(head,weights=x,minlength=24);balanceerror=float(max(abs(balance-(od.sum(axis=1)-od.sum(axis=0)))));closedflow=float(np.max(abs(x[~active]),initial=0.));minimum=float(x.min());valid=relative<=1e-12 and balanceerror<=1e-5 and closedflow<=1e-6 and minimum>=-1e-6
  checks.append(dict(scenario_id=sid,restored_physical_mask=mask,state_key=r['state_key'],tstt_archived_raw=r['tstt_raw'],tstt_numpy_BPR_raw=total,tstt_relative_difference=relative,balance_max_abs=balanceerror,closed_arc_flow_max_abs=closedflow,minimum_flow=minimum,pass_check=valid))
  if r['independent_python_sample']:
   sp=shortest_total(times,tail,head,active,od);gap=max(0.,(total-sp)/total);ok=gap<=TARGET*(1+1e-6)
   samples.append(dict(scenario_id=sid,restored_physical_mask=mask,tstt_numpy_raw=total,SPTT_heap_Dijkstra_raw=sp,independent_RG=gap,pass_check=ok))
 conn.close();df=save(OUT/'audit/independent_flow_validation.csv',checks);sf=save(OUT/'audit/independent_AON_samples.csv',samples);status='PASS' if df.pass_check.all() and sf.pass_check.all() else 'FAIL'
 dump(OUT/'audit/independent_flow_validation.json',dict(status=status,new_state_flow_vectors_checked=len(df),heap_Dijkstra_samples=len(sf),max_TSTT_relative_difference=float(df.tstt_relative_difference.max()),max_balance_error=float(df.balance_max_abs.max()),max_sample_RG=float(sf.independent_RG.max()),solver_calls=0,cache_mode='read-only URI; only new5.5 DB'))
 print('INDEPENDENT_FLOW',status,len(df),'flow vectors;',len(sf),'heap-Dijkstra samples')
 if status!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
