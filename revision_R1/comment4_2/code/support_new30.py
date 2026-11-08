from common42 import *

def main():
 reported=frame(FORMAL/'analysis/selected_objective_precision_stability.csv');assert len(reported)==1620
 rows=[];states=[];details=[];refinedstates=[]
 for sid in range(3001,3031):
  root=FORMAL/f'exact/scenario_{sid}';sol=js(root/'exact_solution.json');roads=tuple(sol['roads'])
  d=frame(root/'all_1024_states.csv.gz').sort_values('subset_mask');repeat=frame(FORMAL/f'analysis_round2/S2_timing_raw/serial/scenario_{sid}/all_fresh_1024_states.csv.gz').sort_values('subset_mask')
  assert set(d.subset_mask)==set(repeat.subset_mask)==set(range(1024)) and d.subset_mask.is_unique and repeat.subset_mask.is_unique
  assert d.converged.all() and d.relative_gap.le(1e-9).all() and d.tolerance.eq(1e-9).all() and d.solver.eq('path_column_generation_pairwise').all()
  assert repeat.converged.all() and repeat.relative_gap.le(1e-9).all() and repeat.tolerance.eq(1e-9).all()
  assert np.allclose(d.loss,d.tstt/T0-1,rtol=1e-14,atol=1e-12)
  costs=dict(zip(d.subset_mask,d.loss));star,s,_,_=dp(d.loss.to_numpy(),roads)
  assert abs(star-sol['exact_objective'])<=128*np.finfo(float).eps*max(1,abs(star))
  a=frame(root/'selected_path_stability.csv');assert a.subset_mask.is_unique and a.refined_gap.le(1e-11).all()
  primary=dict(zip(d.subset_mask,d.tstt));refined={}
  for r in a.itertuples(index=False):
   assert float(r.tstt_primary).hex()==float(primary[r.subset_mask]).hex()
   refined[int(r.subset_mask)]=r.tstt_refined/T0-1
   refinedstates.append({'scenario_id':sid,'subset_mask':r.subset_mask,'tstt_primary':r.tstt_primary,'tstt_refined':r.tstt_refined,
     'actual_refined_RG':r.refined_gap,'relative_TSTT_change':abs(r.tstt_refined-r.tstt_primary)/abs(r.tstt_refined),'iterations_and_retry_history_available':False})
  wanted=[('primary_DP_path',0,sol['sequence'],sol['exact_objective'])]
  for f in sorted((FORMAL/f'runs/query_cap/scenario_{sid}').glob('*/rep_*/result.json')):
   j=js(f);wanted.append((j['method'],int(j['replicate']),j['best_sequence'],j['best_objective']))
  mine=[]
  for method,rep,savedseq,savedobj in wanted:
   p=tuple(savedseq);mm=masks(p,roads);assert set(mm)<=set(refined)
   j9=obj(p,roads,costs);j11=obj(p,roads,refined)
   old=reported[(reported.scenario_id==sid)&(reported.method==method)&(reported.replicate==rep)];assert len(old)==1;old=old.iloc[0]
   machine=128*np.finfo(float).eps*max(1,abs(j9),abs(j11))
   assert abs(j9-savedobj)<=machine and abs(j9-old.primary_objective)<=machine and abs(j11-old.refined_objective)<=machine
   assert abs(old.frozen_epsilon-epsilon(star))<=machine
   change=abs(j11-j9);ok=change<=epsilon(star)
   assert ok==old.within_frozen_objective_epsilon
   item={'scenario_id':sid,'method':method,'replicate':rep,'sequence':txt(p),'primary_objective_recomputed':j9,'refined_objective_recomputed':j11,
    'absolute_objective_change':change,'frozen_epsilon':epsilon(star),'change_over_frozen_epsilon':change/epsilon(star),'within_frozen_objective_epsilon':ok,
    'reported_primary_difference':j9-old.primary_objective,'reported_refined_difference':j11-old.refined_objective,'path_legal':True}
   details.append(item);mine.append(item)
  changes=np.array([r['absolute_objective_change'] for r in mine])
  rows.append({'scenario_id':sid,'supporting_only':True,'primary_state_count':1024,'refined_selected_state_count':len(a),'fixed_paths':len(mine),
    'primary_max_RG':d.relative_gap.max(),'refined_selected_max_RG':a.refined_gap.max(),'all_paths_legal':True,'epsilon_pass_count':sum(r['within_frozen_objective_epsilon'] for r in mine),
    'mean_objective_change':changes.mean(),'max_objective_change':changes.max(),'max_change_over_epsilon':max(r['change_over_frozen_epsilon'] for r in mine),
    'independent_DP_reproduced':True,'full_primary_state_validation':True,'full_1e11_table_validation':False,
    'fresh_repeat_max_relative_TSTT_difference':float(max(abs(d.tstt.to_numpy()-repeat.tstt.to_numpy())/abs(d.tstt.to_numpy())))})
  for r in d.itertuples(index=False):states.append({'scenario_id':sid,'subset_mask':r.subset_mask,'actual_RG':r.relative_gap,'tolerance':r.tolerance,'converged':r.converged,'solver':r.solver})
 csv(S4/'S4_new30_precision_summary.csv',rows);csv(S4/'S4_selected_paths_independent_recheck.csv',details);csv(S4/'S4_primary_30720_state_validation.csv',states);csv(S4/'S4_selected_refinement_state_validation.csv',refinedstates)
 dump(S4/'S4_acceptance.json',{'status':'PASS','supporting_only':True,'primary_states_checked':len(states),'fixed_paths_independently_recomputed':len(details),
    'selected_strict_states_checked':len(refinedstates),'paths_within_frozen_epsilon':sum(x['within_frozen_objective_epsilon'] for x in details),
    'mean_absolute_objective_change':float(np.mean([x['absolute_objective_change'] for x in details])),
    'max_absolute_objective_change':max(x['absolute_objective_change'] for x in details),'max_change_over_frozen_epsilon':max(x['change_over_frozen_epsilon'] for x in details),
    'not_a_new_blind_test':True,'no_new_UE_solves':True,'full_1e11_state_table_not_claimed':True})
 print('S4 PASS',len(states),'primary states,',len(details),'fixed paths,',len(refinedstates),'selected strict states',flush=True)

if __name__=='__main__':main()
