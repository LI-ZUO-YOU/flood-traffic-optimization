"""Export complete diagnostic flow vectors from the new cache, without UE calls."""
from pathlib import Path
import csv, gzip, json
from experiment52 import OUT, FROZEN, IsolatedSolver, np

def main():
 solver=IsolatedSolver();count=0
 fields=['cache_key','scenario_id','rho','subset_mask','arc_id','physical_link_id','from_node','to_node','flow','capacity','vc','free_flow_time_raw','congested_time_raw','bpr_multiplier','TSTT_contribution_raw','TSTT_contribution_veh_h']
 with gzip.open(OUT/'raw/all_new_UE_open_arc_flows.csv.gz','wt',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for raw,blob in solver.connection.execute('SELECT payload,flow FROM states ORDER BY cache_key'):
   r=json.loads(raw);sid=int(r['scenario_id']);rho=float(r['rho']);mask=int(r['subset_mask'])
   roads=[] if sid==0 else next(p['roads'] for p in FROZEN if p['scenario_id']==sid)
   x=np.frombuffer(blob,dtype='<f8');active,fft,coef=solver.net.state_arrays(solver.physical_for(sid),roads,mask)
   cost=fft+coef*x**4
   for i in np.flatnonzero(active):
    link=solver.net.links.iloc[i];contribution=float(x[i]*cost[i])
    w.writerow(dict(cache_key=r['cache_key'],scenario_id=sid,rho=format(rho,'.2f'),subset_mask=mask,arc_id=int(link.arc_id),physical_link_id=int(link.physical_link_id),from_node=int(link.from_node),to_node=int(link.to_node),flow=format(float(x[i]),'.17g'),capacity=format(float(solver.net.cap[i]),'.17g'),vc=format(float(x[i]/solver.net.cap[i]),'.17g'),free_flow_time_raw=format(float(fft[i]),'.17g'),congested_time_raw=format(float(cost[i]),'.17g'),bpr_multiplier=format(float(cost[i]/fft[i]),'.17g'),TSTT_contribution_raw=format(contribution,'.17g'),TSTT_contribution_veh_h=format(contribution*.01,'.17g')))
    count+=1
 solver.close();print(json.dumps(dict(open_arc_rows=count,UE_solves=0,source='new isolated SQLite flow blobs only')),flush=True)
if __name__=='__main__':main()
