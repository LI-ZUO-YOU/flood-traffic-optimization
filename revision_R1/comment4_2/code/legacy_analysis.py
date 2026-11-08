from common42 import *

def main():
 old=old_states();saved=saved_solutions()
 detail=frame(AUD/'source_records/archive/method_regret_detailed.csv')
 sa=frame(PUB/'results/poststudy_permutation_SA/final_once_only/sa_final_results.csv')
 comparisons=[];summaries=[];dprows=[];paths=[];evaluations=[];reference={};hits=[];rankings=[];nearstate=[]
 for sid in range(1001,1011):
  roads=tuple(saved[str(sid)]['candidate_roads']);lo=old[old.scenario_id==sid].sort_values('subset_mask').reset_index(drop=True)
  hi=frame(LEGACY/f'scenario_{sid}/all_1024_highprecision_states.csv.gz').sort_values('subset_mask').reset_index(drop=True)
  c0=lo.loss.to_numpy();c9=hi.loss.to_numpy();star0,s0,second0,sp0=dp(c0,roads);star9,s9,second9,sp9=dp(c9,roads)
  published=tuple(saved[str(sid)]['optimal_sequence']);prior9=tuple(js(LEGACY/f'scenario_{sid}/exact_solution.json')['highprecision_exact_sequence'])
  assert abs(star0-saved[str(sid)]['exact_objective'])<1e-10 and abs(star9-obj(prior9,roads,c9))<1e-10
  assert abs(obj(s0,roads,c0)-star0)<1e-10 and abs(obj(s9,roads,c9)-star9)<1e-10
  for oldr,newr in zip(lo.itertuples(index=False),hi.itertuples(index=False)):
   assert oldr.subset_mask==newr.subset_mask
   dt=newr.tstt-oldr.tstt
   comparisons.append({'scenario_id':sid,'subset_mask':oldr.subset_mask,'restored_count':int(oldr.subset_mask).bit_count(),'old_state_hash':oldr.state_hash,
    'tstt_old_FW_5e4':oldr.tstt,'tstt_new_path_1e9':newr.tstt,'delta_TSTT':dt,'relative_TSTT_change':abs(dt)/max(abs(newr.tstt),1e-100),
    'C_old':oldr.loss,'C_new':newr.loss,'delta_C':newr.loss-oldr.loss,'old_RG':oldr.relative_gap,'new_RG':newr.relative_gap,
    'old_iterations':oldr.iterations,'new_iterations':newr.iterations,'old_converged':oldr.converged,'new_converged':newr.converged,
    'solver_and_tolerance_both_differ':True})
  delta=abs(hi.tstt.to_numpy()-lo.tstt.to_numpy())/abs(hi.tstt.to_numpy())
  summaries.append({'scenario_id':sid,'states':1024,'mean_relative_TSTT_change':float(delta.mean()),
    **{f'P{n}_relative_TSTT_change':float(np.quantile(delta,n/100)) for n in [50,90,99]},'max_relative_TSTT_change':float(delta.max()),
    'old_max_RG':float(lo.relative_gap.max()),'new_max_RG':float(hi.relative_gap.max()),'old_max_iterations':int(lo.iterations.max()),'new_max_iterations':int(hi.iterations.max()),
    'max_abs_C_change':float(max(abs(c9-c0))),'old_solver':'FW','new_solver':'path_column_generation_pairwise'})
  count0,mask0=near(c0,star0,epsilon(star0));count9,mask9=near(c9,star9,epsilon(star9))
  for tier,ms in [('old',mask0),('new',mask9)]:
   for m in sorted(ms):nearstate.append({'scenario_id':sid,'tier':tier,'subset_mask':m,'scope':'all paths within frozen empirical epsilon on this numerical table; not an error bound'})
  dprows.append({'scenario_id':sid,'Jstar_old':star0,'Jstar_new':star9,'abs_change':abs(star9-star0),'rel_change':abs(star9-star0)/abs(star9),
    'sequence_old':txt(s0),'sequence_new':txt(s9),'sequence_equal':s0==s9,'published_old_sequence':txt(published),'archived_highprecision_sequence':txt(prior9),
    'reconstructed_old_matches_published_sequence':s0==published,'reconstructed_new_matches_archived_sequence':s9==prior9,
    'old_published_path_regret_on_new_pct':max(0,regret(obj(published,roads,c9),star9)),
    'objective_equal_within_frozen_tolerance':equivalent(star0,star9,star9),
    'second_best_gap_old':second0-star0,'second_best_gap_new':second9-star9,
    'second_best_sequence_old':txt(sp0),'second_best_sequence_new':txt(sp9),
    'path_count_within_empirical_epsilon_old':count0,'path_count_within_empirical_epsilon_new':count9,
    'epsilon_old':epsilon(star0),'epsilon_new':epsilon(star9)})
  dr=detail[(detail.scenario_id==sid)&(detail.ue_budget==256)&(detail.method=='full_method')].iloc[0]
  sr=sa[sa.scenario_id==sid].iloc[0];sseq=tuple(roads[i] for i in json.loads(sr.best_sequence_bits))
  origsa=js(PUB/f'results/poststudy_permutation_SA/final_once_only/scenario_{sid}/result.json')
  assert int(sr.seed)==origsa['seed'] and list(json.loads(sr.best_sequence_bits))==origsa['best_sequence_bits']
  wanted=[('Proposed_B256',seq(dr.method_sequence),dr.method_objective,dr.relative_regret_pct,bool(dr.exact_objective_hit),None),
    ('SA_original_fixed_seed',sseq,sr.best_objective,sr.relative_regret_pct,None,int(sr.seed)),
    ('published_old_DP_path',published,None,None,None,None),('canonical_old_DP_path',s0,None,None,None,None),
    ('canonical_new_DP_path',s9,None,None,None,None),('second_best_old_DP_path',sp0,None,None,None,None),('second_best_new_DP_path',sp9,None,None,None,None)]
  for row in detail[(detail.scenario_id==sid)&(detail.ue_budget==256)&(detail.method!='full_method')&(detail.relative_regret_pct<=1.5)].itertuples(index=False):
   wanted.append(('archived_competitor_'+row.method,seq(row.method_sequence),row.method_objective,row.relative_regret_pct,bool(row.exact_objective_hit),None))
  for label,s,reported,reportedreg,oldhit,seed in wanted:
   ms=masks(s,roads);paths.append({'scenario_id':sid,'label':label,'sequence':list(s),'roads':list(roads),'masks_R0_R9':ms,'old_reported_objective':reported,'old_reported_regret_pct':reportedreg,'old_reported_hit':oldhit,'original_seed':seed,
    'old_hit_provenance':'No per-run hit boolean in original SA CSV; historical threshold classification independently reconstructed' if label=='SA_original_fixed_seed' else 'Archived per-run flag where available'})
   for tier,c,star,dpseq in [('old_FW_5e-4',c0,star0,s0),('new_path_1e-9',c9,star9,s9)]:
    value=obj(s,roads,c);dif=value-star
    if tier=='old_FW_5e-4' and reported is not None:
     assert abs(value-reported)<=1e-9,(sid,label,value,reported)
     assert abs(max(0,regret(value,saved[str(sid)]['exact_objective']))-max(0,float(reportedreg)))<1e-9
    evaluations.append({'scenario_id':sid,'path_label':label,'precision_tier':tier,'sequence':txt(s),'original_seed':seed,'objective':value,'reference_objective':star,
     'strict_objective_difference':dif,'absolute_objective_difference':abs(dif),'regret_pct':max(0,regret(value,star)),'raw_signed_regret_pct':regret(value,star),
     'sequence_hit_canonical_DP':s==dpseq,'sequence_hit_original_published_DP':s==published,
     'bitwise_objective_equal':float(value).hex()==float(star).hex(),'historical_absolute_1e9_hit':abs(dif)<=1e-9,
     'numerically_equivalent_hit':abs(dif)<=epsilon(star),'frozen_epsilon':epsilon(star),'old_recorded_hit':oldhit if tier=='old_FW_5e-4' else None,
     'old_recorded_objective':reported if tier=='old_FW_5e-4' else None,'old_recorded_regret_pct':reportedreg if tier=='old_FW_5e-4' else None,
     'old_hit_provenance':'No per-run hit boolean in original SA CSV; reconstructed historical rule separately' if label=='SA_original_fixed_seed' else 'Archived per-run flag where available'})
  reference[str(sid)]={'roads':list(roads),'star_old':star0,'star_new':star9,'seq_old':list(s0),'seq_new':list(s9),'near_new_masks':sorted(mask9),'near_old_masks':sorted(mask0),'near_new_path_count':count9}
  print('S1/S2 independently rebuilt',sid,'DP sequence equal',s0==s9,'near paths',count9,flush=True)
 csv(S1/'S1_state_precision_comparison.csv',comparisons);csv(S1/'S1_scenario_precision_summary.csv',summaries);csv(S1/'S1_DP_compare_1001_1010.csv',dprows)
 csv(S1/'S1_empirical_near_optimal_path_state_union.csv',nearstate)
 dump(S2/'frozen_paths.json',paths);dump(S1/'independent_references.json',reference);csv(S2/'S2_original_paths_revalued.csv',evaluations)
 ev=pd.DataFrame(evaluations)
 for sid in range(1001,1011):
  g=ev[ev.scenario_id==sid];rank={'scenario_id':sid}
  for tier,suffix in [('old_FW_5e-4','old'),('new_path_1e-9','new')]:
   pp=g[(g.path_label=='Proposed_B256')&(g.precision_tier==tier)].iloc[0]
   ss=g[(g.path_label=='SA_original_fixed_seed')&(g.precision_tier==tier)].iloc[0]
   d=pp.objective-ss.objective
   rank.update({f'Proposed_objective_{suffix}':pp.objective,f'SA_objective_{suffix}':ss.objective,f'Proposed_minus_SA_{suffix}':d,
    f'rank_historical_1e9_{suffix}':'tie' if abs(d)<=1e-9 else 'Proposed_better' if d<0 else 'SA_better',
    f'rank_empirical_equivalence_{suffix}':'tie' if abs(d)<=pp.frozen_epsilon else 'Proposed_better' if d<0 else 'SA_better'})
  rank['ranking_changed_historical_rule']=rank['rank_historical_1e9_old']!=rank['rank_historical_1e9_new']
  rank['ranking_changed_empirical_rule']=rank['rank_empirical_equivalence_old']!=rank['rank_empirical_equivalence_new'];rankings.append(rank)
  for label in ['Proposed_B256','SA_original_fixed_seed']:
   a=g[(g.path_label==label)&(g.precision_tier=='old_FW_5e-4')].iloc[0];b=g[(g.path_label==label)&(g.precision_tier=='new_path_1e-9')].iloc[0]
   hits.append({'scenario_id':sid,'path_label':label,'old_historical_hit':a.old_recorded_hit,'old_recomputed_historical_hit':a.historical_absolute_1e9_hit,
    'new_historical_threshold_hit':b.historical_absolute_1e9_hit,'old_empirical_hit':a.numerically_equivalent_hit,'new_empirical_hit':b.numerically_equivalent_hit,
    'changed_at_historical_threshold':a.historical_absolute_1e9_hit!=b.historical_absolute_1e9_hit,'changed_at_frozen_empirical_threshold':a.numerically_equivalent_hit!=b.numerically_equivalent_hit})
 csv(S2/'S2_scenario_method_rankings.csv',rankings);csv(S2/'S2_hit_classification_change.csv',hits)
 out=[]
 for (method,tier),g in ev[ev.path_label.isin(['Proposed_B256','SA_original_fixed_seed'])].groupby(['path_label','precision_tier']):
  out.append({'method':method,'precision_tier':tier,'scenarios':10,'mean_regret_pct':g.regret_pct.mean(),'median_regret_pct':g.regret_pct.median(),
   'P90_regret_pct':np.quantile(g.regret_pct,.9),'max_regret_pct':g.regret_pct.max(),'historical_1e9_hit_count':int(g.historical_absolute_1e9_hit.sum()),
   'empirical_hit_count':int(g.numerically_equivalent_hit.sum()),'canonical_sequence_hit_count':int(g.sequence_hit_canonical_DP.sum())})
 csv(S2/'S2_old10_regret_summary.csv',out)
 csv(S2/'S2_case1004_all_path_values.csv',ev[ev.scenario_id==1004])
 dump(S1/'G1_acceptance.json',{'status':'PASS','states_compared':len(comparisons),'DP_tables_independently_rebuilt':20,'canonical_sequence_changed_scenarios':sum(not r['sequence_equal'] for r in dprows),
   'numerical_equality_not_inferred_from_sequence_identity':True})
 dump(S2/'G2_acceptance.json',{'status':'PASS','frozen_original_method_paths':20,'all_reported_legacy_objectives_reproduced_at_absolute_1e9':True,
   'all_reported_legacy_regrets_reproduced':True,'old_seed_records_verified':10,'algorithm_runs':0})
 print(pd.DataFrame(out).to_string(index=False),flush=True)
 print('G1/G2 PASS',flush=True)

if __name__=='__main__':main()
