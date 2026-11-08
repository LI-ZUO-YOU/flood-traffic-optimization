from common import *
import sqlite3,itertools
def reverse_dp(c,roads):
 n=1<<len(roads);B=np.zeros(n);choice=np.full(n,-1,int)
 for s in range(n-2,-1,-1):
  value,i=min((float(c[s]+B[s|(1<<i)]),i) for i in range(len(roads)) if not s&(1<<i));B[s]=value;choice[s]=i
 return float(B[0]/len(roads)),B,choice
def tests():
 rows=[]
 for m in range(1,8):
  roads=list(range(1,m+1));n=1<<m;c=np.array([((i*7919+17)%101)/37 for i in range(n)],float)
  j,seq,_,_=forward_dp(c,roads);b,_,_=reverse_dp(c,roads);brute=min(pathvalue(s,roads,c) for s in itertools.permutations(roads));d=c.copy();d[-1]=1e100;sentinel=forward_dp(d,roads)[0];d=c.copy();d[0]+=7.;shift=forward_dp(d,roads)[0]-j
  for name,actual,expected in [('exhaustive',j,brute),('reverse',b,j),('terminal_sentinel',sentinel,j),('initial_shift',shift,7./m)]:rows.append(dict(m=m,test=name,actual=actual,expected=expected,error=abs(actual-expected),pass_=abs(actual-expected)<=1e-12))
 save(OUT/'tests/small_DP_exhaustive_and_sentinel.csv',rows);assert all(r['pass_'] for r in rows)
def main():
 tests();man=js(OUT/'run_manifest.json');plans=js(OUT/'raw/table_plan.json');mapping=read(OUT/'raw/logical_state_mapping.csv');requests=read(OUT/'raw/unique_state_requests.csv');con=sqlite3.connect(f'file:{(OUT/"cache/sensitivity_states.sqlite3").as_posix()}?mode=ro',uri=True)
 new={key:json.loads(payload) for key,payload in con.execute('SELECT state_key,payload FROM states')};con.close();assert len(new)==man['new_unique_states']
 costs={};raw=[]
 for task in requests.itertuples():
  r=new[task.state_key] if task.source=='new_UE' else dict(tstt_raw=float(task.tstt_raw),loss=float(task.tstt_raw/T0-1),ue_gap=float(task.ue_gap))
  costs[task.state_key]=r;raw.append(dict(state_key=task.state_key,source=task.source,**{k:r[k] for k in ['tstt_raw','loss','ue_gap']}))
 save(OUT/'raw/all_unique_state_costs.csv',raw);summaries=[];state_dp=[];trajectories=[];firstrows=[];checks=[]
 for plan in plans:
  if not plan['n_logical_states']:continue
  vid=plan['variant_id'];g=mapping[mapping.variant_id.eq(vid)].sort_values('subset_mask');assert g.subset_mask.tolist()==list(range(1024));E=plan['road_bit_order'];tstt=np.array([costs[k]['tstt_raw'] for k in g.state_key]);c=tstt/T0-1
  j,seq,V,prev=forward_dp(c,E);b,B,ch=reverse_dp(c,E);explicit=pathvalue(seq,E,c);err=max(abs(j-b),abs(j-explicit));assert err<=1e-12,(vid,err)
  checks.append(dict(variant_id=vid,test='forward_reverse_explicit',forward=j,reverse=b,explicit=explicit,max_error=err,pass_=True))
  weights=np.zeros(1024);s=0
  for stage,r in enumerate(seq):
   trajectories.append(dict(variant_id=vid,scenario_id=plan['scenario_id'],stage=stage,subset_mask=s,next_road=r,tstt_raw=float(tstt[s]),TSTT_veh_h=.01*float(tstt[s]),ATT_min=.6*float(tstt[s])/Q,loss=float(c[s]),weight=.1));weights[s]=.1;s|=1<<E.index(r)
  trajectories.append(dict(variant_id=vid,scenario_id=plan['scenario_id'],stage=10,subset_mask=1023,next_road=None,tstt_raw=float(tstt[-1]),TSTT_veh_h=.01*float(tstt[-1]),ATT_min=.6*float(tstt[-1])/Q,loss=float(c[-1]),weight=0.))
  firstvals=sorted(((float(c[0]+B[1<<i])/10,int(r)) for i,r in enumerate(E)))
  for value,r in firstvals:firstrows.append(dict(variant_id=vid,first_road=r,best_objective_given_first=value,gap_to_best=j-value if False else value-j,within_1e12_absolute=abs(value-j)<=1e-12))
  summaries.append(dict(variant_id=vid,scenario_id=plan['scenario_id'],factor=plan['factor'],level=plan['level'],road_bit_order=E,J_star=j,sequence=seq,mean_stage_TSTT_raw=T0*(1+j),mean_stage_TSTT_veh_h=.01*T0*(1+j),mean_stage_ATT_min=.6*T0*(1+j)/Q,S0_ATT_min=.6*tstt[0]/Q,S10_ATT_min=.6*tstt[-1]/Q,first_road=seq[0],n_states=1024,new_state_mapping_count=int(g.source.eq('new_UE').sum()),reused_state_mapping_count=int(g.source.eq('accepted_4_2').sum()),first_alternative_gap=firstvals[1][0]-firstvals[0][0],near_optimal_first_roads=[r for value,r in firstvals if abs(value-j)<=1e-12],max_RG=max(costs[k]['ue_gap'] for k in g.state_key),validation_error=err))
  for mask in range(1024):state_dp.append(dict(variant_id=vid,subset_mask=mask,state_key=g.state_key.iloc[mask],tstt_raw=float(tstt[mask]),loss=float(c[mask]),V_forward=float(V[mask]),predecessor=int(prev[mask]),B_reverse=float(B[mask]),chosen_addition_index=int(ch[mask]),on_optimal_path_weight=float(weights[mask])))
 dump(OUT/'raw/DP_summaries.json',summaries);save(OUT/'raw/DP_all_states.csv',state_dp);save(OUT/'raw/DP_optimal_trajectories.csv',trajectories);save(OUT/'raw/DP_first_road_alternatives.csv',firstrows);save(OUT/'audit/independent_DP_checks.csv',checks)
 print('DP validated',len(summaries),'complete tables',flush=True)
if __name__=='__main__':main()
