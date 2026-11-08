from s4_common import *

def run():
 phase_rows=[];runs=[];quality=[];provenance=[]
 for r in metric_rows().itertuples():
  sid=int(r.scenario_id);v=r.variant_id;rep=int(r.seed_index);p=path(sid,v,rep);rq=frame(p/'request_ledger.csv.gz');u=frame(p/'logical_query_ledger.csv.gz');h=frame(p/'complete_sequence_history.csv.gz');ls=frame(p/'local_search_calls.csv');moves=frame(p/'local_search_moves.csv.gz');blocks=frame(p/'phase_blocks.csv');result=js(p/'result.json')
  fresh=~rq['mask'].duplicated();assert np.array_equal(rq.cache_hit.to_numpy(bool),~fresh.to_numpy())
  assert int(fresh.sum())==len(u)==r.unique_UE_queries and h.sequence_id.nunique()==len(h)
  assert rq.loc[fresh,'mask'].tolist()==u.subset_mask.tolist();assert rq.loc[fresh,'phase'].tolist()==u.phase.tolist()
  assert abs(rq.solver_seconds.sum()-r.UE_kernel_seconds)<=1e-8*max(1,r.UE_kernel_seconds)
  h['initial_establishment']=h.incumbent_update & h.incumbent_before.isna()
  h['strict_improvement']=h.incumbent_before.notna() & (h.incumbent_after<h.incumbent_before)
  assert int(h.initial_establishment.sum())==1
  best=None
  for x in h.itertuples():
   assert (pd.isna(x.incumbent_before) and best is None) or x.incumbent_before==best
   best=x.complete_J if best is None else min(best,x.complete_J);assert best==x.incumbent_after
  assert best==r.J
  final_masks=set(E.masks(result['best_sequence'],result['roads']));dp_masks=set(E.masks(ref(sid)['sequence'],result['roads']))
  for x in u.itertuples():provenance.append({'scenario_id':sid,'variant_id':v,'seed_index':rep,'mask':x.subset_mask,'first_phase':x.phase,'query_index':x.query_index,'on_final_path':x.subset_mask in final_masks,'on_selected_DP_path':x.subset_mask in dp_masks,'interpretation':'posthoc compatibility; not marginal value or wasted-query test'})
  for phase in rq.phase.drop_duplicates():
   first=rq[fresh & (rq.phase==phase)];c=h[h.phase==phase];bl=blocks[blocks.phase==phase];defined=bl.start_best_J.notna() & bl.end_best_J.notna() if len(bl) else pd.Series([],dtype=bool)
   boundary=float((bl.start_best_J-bl.end_best_J).sum()) if len(bl) and defined.all() else None
   strict=c[c.strict_improvement];delta=float((strict.incumbent_before-strict.incumbent_after).sum())
   phase_rows.append({'scenario_id':sid,'variant_id':v,'seed_index':rep,'phase':phase,'first_seen_UE_states':len(first),'all_requests':int((rq.phase==phase).sum()),'cache_hit_requests':int(((rq.phase==phase)&rq.cache_hit).sum()),'complete_unique_sequences':len(c),'initial_incumbent_establishments':int(c.initial_establishment.sum()),'strict_incumbent_improvements':int(c.strict_improvement.sum()),'incumbent_updates_including_initial':int(c.incumbent_update.sum()),'phase_boundary_delta_J':boundary,'sum_of_defined_strict_deltas_J':delta,'defined_strict_delta_regret_pp':100*delta/ref(sid)['objective'],'first_seen_states_on_final_path':int(first['mask'].isin(final_masks).sum()),'first_seen_states_on_selected_DP_path':int(first['mask'].isin(dp_masks).sum()),'UE_budget_share':len(first)/256,'strict_delta_per_first_seen_state':delta/len(first) if len(first) else None,'zero_new_state_complete_sequences':int((c.new_unique_UE_states==0).sum()),'interpretation':'observed accounting, not causal stage contribution'})
  # Local-move rows can repeat a child generated from multiple parents; never sum their historical new_ue_calls.
  unique_moves=moves.child_sequence_id.nunique() if len(moves) else 0;D=h[h.phase=='D_local_search'];assert unique_moves==len(D)
  residual=r.fresh_online_seconds-r.candidate_prepare_seconds-r.UE_network_call_seconds-r.LS_non_UE_seconds-r.search_other_bookkeeping_seconds
  assert abs(residual)<1e-7
  runs.append({'scenario_id':sid,'variant_id':v,'seed_index':rep,'unique_UE_states':len(u),'budget_utilization':len(u)/256,'all_requests':len(rq),'cache_hits':int(rq.cache_hit.sum()),'logical_cache_hit_fraction':float(rq.cache_hit.mean()),'complete_unique_sequences':len(h),'cache_only_complete_sequences':int((h.new_unique_UE_states==0).sum()),'strict_incumbent_improvements':int(h.strict_improvement.sum()),'complete_sequences_per_unique_UE_state':len(h)/len(u),'strict_improvements_per100_unique_UE_states':100*h.strict_improvement.sum()/len(u),'local_move_metadata_rows':len(moves),'unique_LS_children':unique_moves,'duplicate_local_move_metadata_rows':len(moves)-unique_moves,'fresh_online_seconds':r.fresh_online_seconds,'candidate_prepare_seconds':r.candidate_prepare_seconds,'surrogate_inference_seconds_nested':r.surrogate_inference_seconds,'UE_network_call_seconds':r.UE_network_call_seconds,'UE_kernel_seconds_nested':r.UE_kernel_seconds,'LS_non_UE_seconds':r.LS_non_UE_seconds,'search_other_bookkeeping_seconds':r.search_other_bookkeeping_seconds,'search_management_total_seconds':r.LS_non_UE_seconds+r.search_other_bookkeeping_seconds,'component_sum_residual_seconds':residual,'sampled_peak_process_RSS_bytes':r.peak_RSS_bytes})
  before=float(ls.iloc[0].best_J_before);after=float(ls.iloc[0].best_J_after)
  completed_before=int(D.index[0]) if int(ls.iloc[0].completed_sequences)>0 else None
  quality.append({'scenario_id':sid,'variant_id':v,'seed_index':rep,'first_LS_before_J':before,'first_LS_after_J':after,'first_LS_before_regret_pct':float(regret(before,sid)),'first_LS_after_regret_pct':float(regret(after,sid)),'first_LS_delta_J':before-after,'first_LS_delta_regret_pp':100*(before-after)/ref(sid)['objective'],'LS_total_observed_delta_J':float(ls.improvement.sum()),'LS_total_observed_delta_regret_pp':100*ls.improvement.sum()/ref(sid)['objective'],'final_regret_pct':r.regret_pct,'completed_before_first_LS':completed_before,'completed_before_first_LS_count_rule':'complete-history ordinal of first LS child, not query-budget inequality; NA if first call had no children','LS_calls':len(ls)})
 phase=pd.DataFrame(phase_rows);run=pd.DataFrame(runs);qual=pd.DataFrame(quality)
 assert phase.groupby(['scenario_id','variant_id','seed_index']).first_seen_UE_states.sum().eq(256).all()
 assert phase.groupby(['scenario_id','variant_id','seed_index']).first_seen_states_on_final_path.sum().eq(10).all()
 csv(S4/'03_phases_costs/phase_accounting_all_runs.csv',phase);csv(S4/'03_phases_costs/run_budget_cache_management.csv',run);csv(S4/'03_phases_costs/first_LS_quality_all_runs.csv',qual);csv(S4/'03_phases_costs/queried_state_path_provenance.csv.gz',provenance)
 numeric=['first_seen_UE_states','all_requests','cache_hit_requests','complete_unique_sequences','initial_incumbent_establishments','strict_incumbent_improvements','sum_of_defined_strict_deltas_J','defined_strict_delta_regret_pp','first_seen_states_on_final_path','UE_budget_share']
 sc=phase.groupby(['scenario_id','variant_id','phase'])[numeric].sum()/3
 # Each method has exactly3 runs. Missing phases represent0 occurrences, not lost observations.
 allph=phase.phase.unique();full=pd.MultiIndex.from_product([range(5101,5111),METHODS,allph],names=['scenario_id','variant_id','phase'])
 sc=sc.reindex(full,fill_value=0).reset_index();csv(S4/'03_phases_costs/phase_scenario_seed_means.csv',sc)
 csv(S4/'03_phases_costs/phase_method_means_n10.csv',sc.groupby(['variant_id','phase'])[numeric].mean().reset_index())
 timecols=['fresh_online_seconds','candidate_prepare_seconds','surrogate_inference_seconds_nested','UE_network_call_seconds','UE_kernel_seconds_nested','LS_non_UE_seconds','search_other_bookkeeping_seconds','search_management_total_seconds','complete_sequences_per_unique_UE_state','cache_only_complete_sequences','duplicate_local_move_metadata_rows']
 ts=run.groupby(['scenario_id','variant_id'])[timecols].mean().reset_index();csv(S4/'03_phases_costs/time_components_scenario_means.csv',ts)
 tm=ts.groupby('variant_id')[timecols].mean().reindex(METHODS).reset_index();csv(S4/'03_phases_costs/Table_time_decomposition.csv',tm)
 qs=qual.groupby(['scenario_id','variant_id']).mean(numeric_only=True).reset_index();csv(S4/'03_phases_costs/LS_quality_scenario_seed_means.csv',qs);csv(S4/'03_phases_costs/LS_quality_method_means.csv',qs.groupby('variant_id').mean(numeric_only=True).reset_index())
 dump(S4/'03_phases_costs/validation.json',{'status':'PASS','runs':330,'all_phase_sums_256':True,'cache_misses_equal_unique_states':True,'unique_final_path_states_each_run':10,'all_final_J_reconstructed':True,'duplicate_local_move_rows_total':int(run.duplicate_local_move_metadata_rows.sum()),'duplicate_move_fields_never_used_for_UE_billing':True,'initial_solution_not_counted_as_strict_improvement':True})
 print('S4 phase/cost accounting PASS',flush=True)
