from common import *
import sqlite3,itertools
from scipy.stats import kendalltau
def reverse_dp(c,E):
 B=np.zeros(len(c))
 for s in range(len(c)-2,-1,-1):B[s]=float(c[s]+min(B[s|(1<<i)] for i in range(len(E)) if not s&(1<<i)))
 return float(B[0]/len(E)),B
def top_two(c,E):
 paths=[None]*len(c);paths[0]=[(0.,())]
 for s in range(1,len(c)):
  candidates=[]
  for i,r in enumerate(E):
   if s&(1<<i):
    prev=s^(1<<i)
    for val,seq in paths[prev]:candidates.append((float(val+c[prev]),seq+(int(r),)))
  paths[s]=sorted(candidates,key=lambda x:(x[0],x[1]))[:2]
 return [(val/len(E),list(seq)) for val,seq in paths[-1]]
def small_tests():
 rows=[]
 for m in range(1,8):
  E=list(range(1,m+1));c=np.array([((mask*7907+11)%97)/31 for mask in range(1<<m)],float);j,seq,_,_=forward_dp(c,E);rev,_=reverse_dp(c,E);two=top_two(c,E);allpaths=sorted((pathvalue(s,E,c),tuple(s)) for s in itertools.permutations(E));sent=c.copy();sent[-1]=1e100;shift=c.copy();shift[0]+=7.
  tests=[('exhaustive',j,allpaths[0][0]),('reverse',rev,j),('sentinel',forward_dp(sent,E)[0],j),('initial_shift',forward_dp(shift,E)[0]-j,7./m)]
  if m>1:tests.append(('second_best_sequence',two[1][0],allpaths[1][0]))
  for label,actual,expected in tests:rows.append(dict(m=m,test=label,actual=actual,expected=expected,error=abs(actual-expected),pass_=abs(actual-expected)<=1e-12))
 save(OUT/'tests/small_DP_checks.csv',rows);assert all(r['pass_'] for r in rows)
def main():
 small_tests();man=js(OUT/'run_manifest.json');mapping=read(OUT/'raw/logical_state_mapping.csv');tasks=read(OUT/'raw/unique_state_requests.csv');plans=man['table_plan'];con=sqlite3.connect(f'file:{(OUT/"cache/depth_extension_states.sqlite3").as_posix()}?mode=ro',uri=True);new={k:json.loads(p) for k,p in con.execute('SELECT state_key,payload FROM states')};con.close();assert len(new)==man['new_unique_states']
 values={};unique=[]
 for task in tasks.itertuples():
  r=new[task.state_key] if task.source=='new_UE' else dict(tstt_raw=float(task.tstt_raw),ue_gap=float(task.ue_gap))
  values[task.state_key]=r;unique.append(dict(state_key=task.state_key,source=task.source,tstt_raw=r['tstt_raw'],ue_gap=r['ue_gap'],loss=float(r['tstt_raw']/T0-1)))
 save(OUT/'raw/unique_state_costs.csv',unique)
 original=js(R42/'01_legacy_ue_state_comparison/independent_references.json');results=[];DP=[];paths=[];checks=[];first=[];rawcosts=[]
 for plan in plans:
  vid=plan['variant_id'];sid=plan['scenario_id'];rho=plan['level'];E=plan['road_bit_order'];g=mapping[mapping.variant_id.eq(vid)].sort_values('subset_mask');assert g.subset_mask.tolist()==list(range(1024));t=np.array([values[k]['tstt_raw'] for k in g.state_key]);c=t/T0-1
  j,seq,V,prev=forward_dp(c,E);jr,B=reverse_dp(c,E);kbest=top_two(c,E);exp=pathvalue(seq,E,c);top1=kbest[0][0];error=max(abs(j-jr),abs(j-exp),abs(j-top1));assert error<=1e-12,(vid,error)
  # Recover the sequence independently from the forward predecessor mask chain.
  reconstructed=[];s=1023
  while s:
   parent=int(prev[s]);bit=s^parent;reconstructed.append(E[bit.bit_length()-1]);s=parent
  reconstructed.reverse();assert reconstructed==seq
  baseline=original[str(sid)];oldseq=baseline['seq_new'];oldJ=baseline['star_new'];jtransfer=pathvalue(oldseq,E,c);delta=jtransfer-j;regret=100*delta/j if j>0 else None
  assert j>0,'Jstar<=0: special denominator explanation required; do not divide'
  tau=float(kendalltau(range(10),[seq.index(v) for v in oldseq]).statistic);near=1e-12*max(1.,abs(j));alternatives=[]
  for i,r in enumerate(E):
   value=float((c[0]+B[1<<i])/10);alternatives.append((value,int(r)));first.append(dict(variant_id=vid,first_road=int(r),best_J_if_first=value,gap_to_chosen_J=value-j,chosen_first=r==seq[0],near_tie_threshold=near,within_near_tie_diagnostic=abs(value-j)<=near))
  alt=min(value for value,r in alternatives if r!=seq[0]);secondgap=kbest[1][0]-j
  path_masks=[];s=0
  for stage,r in enumerate(seq):
   path_masks.append(s);paths.append(dict(variant_id=vid,scenario_id=sid,rho_depth=rho,stage=stage,subset_mask=s,next_road=r,tstt_raw=t[s],TSTT_veh_h=.01*t[s],ATT_min=.6*t[s]/Q,loss=c[s],weight=.1));s|=1<<E.index(r)
  paths.append(dict(variant_id=vid,scenario_id=sid,rho_depth=rho,stage=10,subset_mask=1023,next_road=None,tstt_raw=t[-1],TSTT_veh_h=.01*t[-1],ATT_min=.6*t[-1]/Q,loss=c[-1],weight=0.))
  ATTstage=float(np.mean(t[path_masks])*.6/Q);checkATT=ATT0*(1+j);assert abs(ATTstage-checkATT)<=1e-9
  row=dict(variant_id=vid,scenario_id=sid,rho_depth=rho,Jstar=j,mean_stage_TSTT_raw=float(np.mean(t[path_masks])),mean_stage_TSTT_veh_h=float(np.mean(t[path_masks])*.01),mean_stage_ATT_min=ATTstage,S0_ATT_min=float(.6*t[0]/Q),S10_ATT_min=float(.6*t[-1]/Q),baseline_Jstar=oldJ,baseline_ATT_min=ATT0*(1+oldJ),Jstar_change_from_original=j-oldJ,Jstar_change_pct=100*(j-oldJ)/oldJ,ATT_change_from_original_min=ATTstage-ATT0*(1+oldJ),original_DP_sequence=oldseq,road_bit_order=E,optimal_sequence=seq,full_sequence_changed=seq!=oldseq,first_road=seq[0],baseline_first_road=oldseq[0],first_road_changed=seq[0]!=oldseq[0],first3_order=seq[:3],baseline_first3_order=oldseq[:3],first3_order_changed=seq[:3]!=oldseq[:3],first3_set_changed=set(seq[:3])!=set(oldseq[:3]),Kendall_tau=tau,J_transfer_original_DP=jtransfer,transfer_regret_pct=regret,transfer_delta_J=delta,transfer_delta_ATT_min=ATT0*delta,near_tie_threshold=near,min_alternative_first_J=alt,min_alternative_first_gap=alt-j,second_best_J=kbest[1][0],second_best_sequence=kbest[1][1],second_best_gap=secondgap,second_best_within_near_tie=abs(secondgap)<=near,alternative_first_within_near_tie=abs(alt-j)<=near,source_tables='new_UE' if g.source.eq('new_UE').any() else 'accepted_R2C3' if g.source.eq('accepted_R2C3').any() else 'accepted_4_2',n_states=1024,achieved_max_RG=max(values[k]['ue_gap'] for k in g.state_key),validity_status='VALID',portfolio_comparability='SAME_ORIGINAL_E')
  if rho==1.:assert abs(j-oldJ)<=1e-12 and seq==oldseq,(sid,j,seq,oldseq)
  results.append(row);checks.append(dict(variant_id=vid,J_forward=j,J_reverse=jr,J_explicit=exp,J_kbest=top1,max_error=error,predecessor_sequence_equal=True,mean_stage_ATT_explicit=ATTstage,mean_stage_ATT_formula=checkATT,ATT_error=abs(ATTstage-checkATT),pass_=True))
  for mask in range(1024):
   DP.append(dict(variant_id=vid,scenario_id=sid,rho_depth=rho,subset_mask=mask,state_key=g.state_key.iloc[mask],tstt_raw=t[mask],loss=c[mask],V_forward=V[mask],predecessor=int(prev[mask]),B_reverse=B[mask],path_weight=.1 if mask in path_masks else 0.));rawcosts.append(dict(variant_id=vid,scenario_id=sid,rho_depth=rho,subset_mask=mask,state_key=g.state_key.iloc[mask],source=g.source.iloc[mask],tstt_raw=t[mask],TSTT_veh_h=.01*t[mask],ATT_min=.6*t[mask]/Q,loss=c[mask],ue_gap=values[g.state_key.iloc[mask]]['ue_gap']))
 dump(OUT/'raw/all10_depth_results.json',results);save(OUT/'Table_R2C3_all10_depth_DP.csv',[{k:canonical(v) if isinstance(v,list) else v for k,v in r.items()} for r in results]);save(OUT/'raw/DP_all_states.csv',DP);save(OUT/'raw/DP_paths.csv',paths);save(OUT/'raw/UE_all_logical_states.csv',rawcosts);save(OUT/'raw/first_road_alternatives.csv',first);save(OUT/'audit/independent_DP_checks.csv',checks)
 stats=[]
 for rho in [.90,.95]:
  g=[r for r in results if r['rho_depth']==rho];row=dict(rho_depth=rho,n_independent_scenarios=10,n_parameter_conditions=10,full_sequence_changed_count=sum(r['full_sequence_changed'] for r in g),first_road_changed_count=sum(r['first_road_changed'] for r in g),first3_order_changed_count=sum(r['first3_order_changed'] for r in g),first3_set_changed_count=sum(r['first3_set_changed'] for r in g),near_tie_second_best_count=sum(r['second_best_within_near_tie'] for r in g),near_tie_alternative_first_count=sum(r['alternative_first_within_near_tie'] for r in g))
  for metric in ['Jstar','mean_stage_ATT_min','Jstar_change_from_original','ATT_change_from_original_min','Kendall_tau','transfer_regret_pct','transfer_delta_ATT_min']:
   a=np.array([r[metric] for r in g]);row.update({metric+'_'+label:float(value) for label,value in [('mean',a.mean()),('median',np.median(a)),('P90',np.quantile(a,.90,method='linear')),('maximum',a.max()),('minimum',a.min())]})
  stats.append(row)
 save(OUT/'Table_R2C3_depth_summary.csv',stats);dump(OUT/'audit/DP_analysis_validation.json',dict(status='PASS',logical_tables=30,perturbed_tables=20,baseline_tables=10,max_DP_error=max(r['max_error'] for r in checks),max_ATT_error=max(r['ATT_error'] for r in checks),DP_tolerance=1e-12,small_tests=len(read(OUT/'tests/small_DP_checks.csv')),tie_rule='Strict floating objective then lexicographic full physical-road sequence',near_tie='diagnostic only; not used for optimization'))
 print('All10 depth analysis complete',len(results),'tables',flush=True)
if __name__=='__main__':main()
