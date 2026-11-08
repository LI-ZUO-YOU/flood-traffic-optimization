from s4_common import *
def load_states(folder):
 folder=Path(folder)
 paths=list(folder.rglob('physical_UE_journal.csv'));parts=[]
 for p in paths:
  if p.stat().st_size:
   try:parts.append(frame(p))
   except pd.errors.EmptyDataError:pass
 if parts:return pd.concat(parts,ignore_index=True)
 return frame(folder/'all_states.csv.gz') if (folder/'all_states.csv.gz').exists() else pd.DataFrame()
def main():
 assert js(OUT/'logs/S4_computation_complete.json')['all_sources_unchanged'];verify_s4()
 freeze=js(OUT/'00_lock/optimization_outputs_freeze.json')
 for p,h in freeze['sha256'].items():assert sha(p)==h,'Optimization output changed '+p
 refs=[];agreements=[];refmaps={};enumrows=[];audit=[];nested_tables={};parallel_workers=[]
 for sid in range(4401,4407):
  for m in [10,12,14]:
   ph,roads,_,_=physical(sid,m);valid=[];tables={}
   for kind in ['enum_serial','enum_4core']:
    folder=OUT/f'{kind}/scenario_{sid}/m_{m:02d}';mon=js(folder/'monitor.json');r=js(folder/'timing.json') if (folder/'timing.json').exists() else {};table=load_states(folder);tables[kind]=table
    count=len(table);nested_tables[(sid,m,kind)]=table
    allrg=bool(count and table.converged.all() and (table.relative_gap<=1e-9).all() and np.isfinite(table[['tstt','loss']].to_numpy()).all())
    full=count==1<<m and set(table.subset_mask)==set(range(1<<m)) and table.subset_mask.nunique()==1<<m
    complete=mon['status']=='PASS' and r.get('complete_reference',False) and full and allrg
    cap=protocol()['max_task_seconds'];error_context=str(mon.get('resource_stop',''))+str(r.get('error',''))+str(r.get('worker_details',''))
    time_limit='TIME_LIMIT' in error_context or (mon['status']!='PASS' and r.get('online_wall',0)>=cap and not list(folder.rglob('UE_failure.json')))
    row={'scenario_id':sid,'m':m,'method':kind,'status':mon['status'],'full_valid_reference':complete,'completed_states':count,'all_recorded_states_pass_RG':allrg,'online_wall':r.get('online_wall'),'online_wall_censored':mon['status']!='PASS','completion_wall_lower_bound_s':cap if time_limit else None,
     'failure_reason':mon.get('resource_stop') or str(r.get('error','')),'target_objective':r.get('target_objective'),'DP_wall':r.get('reference_DP_wall'),'pool_setup_excluded_s':r.get('pool_setup_excluded_s'),'peak_online_RSS_MiB':mon['peak_online_process_tree_RSS_bytes']/2**20 if mon['peak_online_process_tree_RSS_bytes'] is not None else None,'peak_lifetime_RSS_MiB':mon['peak_process_tree_RSS_bytes']/2**20,'max_RG':float(table.relative_gap.max()) if count else None}
    row['resource_time_limit_applied']=time_limit
    if mon['status']!='PASS' and not row['failure_reason']:row['failure_reason']='TASK_TIME_LIMIT_IN_PARALLEL_WORKERS' if time_limit else str([x.get('error') for x in r.get('worker_details',[]) if x.get('error')]) or 'See retained worker log'
    if kind=='enum_4core':
     detail={x['index']:x for x in r.get('worker_details',[])}
     for index in range(4):
      x=detail.get(index,{});p=folder/f'chunk_{index}/physical_UE_journal.csv';nrows=len(frame(p)) if p.exists() and p.stat().st_size else 0
      parallel_workers.append({'scenario_id':sid,'m':m,'chunk':index,'core':FOUR[index],'worker_PID':x.get('pid'),'completed_physical_journal_states':nrows,'returned_state_calls':x.get('calls'),'worker_wall':x.get('wall'),'UE_wall':x.get('UE_wall'),'worker_error':str(x.get('error','')),'partial_or_censored':mon['status']!='PASS'})
    enumrows.append(row)
    assert allrg or count==0,'Recorded UE rows failed convergence'
    if complete:
     costs=dict(zip(table.subset_mask.astype(int),table.loss));value,seq=exact_dp(costs,roads);independent,seq2=A.exact_dp(costs,roads)
     assert float(value).hex()==float(r['target_objective']).hex()==float(independent).hex()
     path_value=float(np.mean([costs[x] for x in A.masks(seq,roads)]));assert abs(path_value-value)<=epsilon(value)
     assert value>0
     valid.append((kind,value,seq,costs))
     audit.append({'scenario_id':sid,'m':m,'audit':'independent_DP_reference','method':kind,'count':count,'passed':True})
   left=tables['enum_serial'];right=tables['enum_4core']
   if len(left) and len(right):
    overlap=left[['subset_mask','tstt','loss']].merge(right[['subset_mask','tstt','loss']],on='subset_mask',suffixes=('_serial','_4core'),validate='one_to_one')
    tstt_equal=all(float(x).hex()==float(y).hex() for x,y in zip(overlap.tstt_serial,overlap.tstt_4core));loss_equal=all(float(x).hex()==float(y).hex() for x,y in zip(overlap.loss_serial,overlap.loss_4core));assert tstt_equal and loss_equal
    agreements.append({'scenario_id':sid,'m':m,'overlapping_masks':len(overlap),'serial_rows':len(left),'parallel_rows':len(right),'TSTT_bitwise_equal':tstt_equal,'loss_bitwise_equal':loss_equal})
   if valid:
    chosen=next((r for r in valid if r[0]=='enum_serial'),valid[0]);kind,value,seq,costs=chosen;refmaps[(sid,m)]=(value,costs)
    refs.append({'scenario_id':sid,'m':m,'has_full_conditional_reference':True,'reference_source':kind,'exact_objective':value,'target_hex':float(value).hex(),'sequence':seq_string(seq),'states':1<<m,'epsilon_abs':epsilon(value),'DP_exactness_scope':'finite high-precision state cost table, not infinite-precision UE','UE_target':1e-9})
   else:refs.append({'scenario_id':sid,'m':m,'has_full_conditional_reference':False,'reference_source':None,'exact_objective':None,'states':None,'epsilon_abs':None,'reason':'no complete valid table within frozen resource limits'})
 nested=[]
 for sid in range(4401,4407):
  for smaller,larger in [(10,12),(12,14),(10,14)]:
   for kind in ['enum_serial','enum_4core']:
    lo=nested_tables[(sid,smaller,kind)];hi=nested_tables[(sid,larger,kind)]
    if len(lo) and len(hi):
     ov=lo[['subset_mask','tstt','loss']].merge(hi[hi.subset_mask<(1<<smaller)][['subset_mask','tstt','loss']],on='subset_mask',suffixes=('_small','_large'),validate='one_to_one')
     eq=all(float(a).hex()==float(b).hex() for a,b in zip(ov.tstt_small,ov.tstt_large)) and all(float(a).hex()==float(b).hex() for a,b in zip(ov.loss_small,ov.loss_large));assert eq,'Nested physical state changed across m'
     nested.append({'scenario_id':sid,'smaller_m':smaller,'larger_m':larger,'resource':kind,'overlapping_masks':len(ov),'physical_TSTT_loss_bitwise_equal':eq})
 csv(OUT/'analysis/S4_nested_state_consistency.csv',nested)
 csv(OUT/'analysis/S4_parallel_worker_profile.csv',parallel_workers)
 csv(OUT/'analysis/S4_exact_reference_by_m.csv',refs);csv(OUT/'analysis/S4_full_table_agreement.csv',agreements);csv(OUT/'analysis/S4_enumeration_costs.csv',enumrows)
 runs=[];phase_rows=[]
 schedule=frame(OUT/'00_lock/S4_optimization_schedule.csv')
 for job in schedule.to_dict('records'):
  sid=int(job['scenario_id']);m=int(job['m']);method=job['method'];rep=int(job['replicate']);folder=OUT/f'optimization/scenario_{sid}/m_{m:02d}/{method}/rep_{rep:02d}';mon=js(folder/'monitor.json');r=js(folder/'timing.json') if (folder/'timing.json').exists() else {};table=load_states(folder)
  row={**job,'status':mon['status'],'failure_reason':mon.get('resource_stop') or str(r.get('error','')),'objective':r.get('target_objective'),'sequence':seq_string(r.get('sequence')),'UE_queries':r.get('UE_queries',len(table)),'physical_UE_calls':r.get('actual_physical_calls',len(table)),'logical_requests':r.get('logical_requests'),'online_wall':r.get('online_wall'),'time_censored':mon['status']!='PASS','resource_cap_s':protocol()['max_task_seconds'],
   'candidate_wall_inclusive':r.get('candidate_wall_inclusive'),'inference_wall_nested':r.get('inference_wall_nested'),'proxy_DP_wall_nested':r.get('proxy_DP_wall_nested'),'candidate_wall_excluding_inference_and_DP':r.get('candidate_wall_excluding_inference_and_DP'),'UE_wall':r.get('UE_wall'),'LS_wall_inclusive':r.get('LS_wall_inclusive'),'LS_wall_excluding_UE':r.get('LS_wall_excluding_UE'),'other_search_and_journal_wall':r.get('other_search_and_journal_wall'),
   'greedy_initial_queries':r.get('greedy_initial_query_count'),'greedy_initial_wall':r.get('greedy_initial_wall'),'LS_unique_queries':r.get('LS_unique_queries'),'max_RG':r.get('max_RG'),'CPU_work_seconds':r.get('CPU_work_seconds'),
   'peak_online_RSS_MiB':mon['peak_online_process_tree_RSS_bytes']/2**20 if mon['peak_online_process_tree_RSS_bytes'] is not None else None,'peak_lifetime_RSS_MiB':mon['peak_process_tree_RSS_bytes']/2**20,'B_over_full_states':256/(1<<m),'has_full_reference':(sid,m) in refmaps,'conditional_regret_pct':None,'numerically_equivalent_hit':None,'setup_and_prewarm_excluded_s':r.get('setup_and_prewarm_excluded_s'),'SA_natural_termination':r.get('natural_termination'),'scope':'extended-severity exploratory paired scaling stress test'}
  row['failure_class']='environment_interference' if mon.get('resource_stop')=='CONCURRENT_PYTHON_TASK' else 'task_resource_cap' if mon.get('resource_stop') or 'TIME_LIMIT' in str(r.get('error','')) else 'UE_solver_or_task_error' if mon['status']!='PASS' else None
  row['query_count_scope']='logical and physical complete run counts' if r else 'completed physical journal states, lower bound including unknown in-flight request; logical count unavailable'
  if len(table):assert table.converged.all() and (table.relative_gap<=1e-9).all() and table.subset_mask.nunique()==len(table)
  if row['status']=='PASS':
   ledger=frame(folder/'logical_query_ledger.csv.gz');events=frame(folder/'all_query_events.csv.gz');seq=tuple(r['sequence']);_,roads,_,_=physical(sid,m)
   assert len(seq)==m and set(seq)==set(roads) and len(ledger)<=256 and len(ledger)==r['UE_queries']==r['actual_physical_calls'] and r['physical_cache_hits']==0
   costs=dict(zip(ledger.subset_mask.astype(int),ledger.loss));recomputed=float(np.mean([costs[x] for x in A.masks(seq,roads)]));assert recomputed.hex()==float(row['objective']).hex()
   rejected=r['logical_requests']-len(events)
   assert rejected in [0,1] and (not rejected or r['natural_termination']=='unique_state_cap')
   assert int(events.unique_queries_after.max())==len(ledger)
   row['budget_rejected_request_not_in_accepted_events']=rejected
   if method in ['greedy_ils','ue_bibeam']:assert r['greedy_initial_query_count']==m*(m+1)//2
   if method=='proposed':assert all(r['S3_reproduction_gate'].values()) and r['candidate_report']['candidate_count']==30000
   if (sid,m) in refmaps:
    reference,fullcosts=refmaps[(sid,m)];assert abs(row['objective']-reference)>=0
    assert row['objective']>=reference-epsilon(reference)
    row['conditional_regret_pct']=max(0.,100*(row['objective']-reference)/reference);row['numerically_equivalent_hit']=abs(row['objective']-reference)<=epsilon(reference)
    assert all(float(x).hex()==float(fullcosts[int(mask)]).hex() for mask,x in zip(ledger.subset_mask,ledger.loss))
   audit.append({'scenario_id':sid,'m':m,'method':method,'replicate':rep,'audit':'objective_query_budget_initialization_and_S3_gate','passed':True,'count':len(ledger)})
   for phase,g in ledger.groupby('phase'):phase_rows.append({'scenario_id':sid,'m':m,'method':method,'replicate':rep,'phase':phase,'unique_queries':len(g)})
  candidate=r.get('candidate_report',{});row['candidate_count']=candidate.get('candidate_count',0);row['prefix4_visited']=candidate.get('prefix4_visited');row['prefix4_coverage']=candidate.get('prefix_visited_fraction');row['policy_calls']=candidate.get('policy_calls',0)
  row['all_source_pool_prefix4_unique']=candidate.get('pool_prefix4_unique');row['prefix_source_prefix4_unique']=candidate.get('prefix_source_prefix4_unique')
  row['all_source_pool_prefix4_coverage']=candidate['pool_prefix4_unique']/math.perm(m,4) if candidate.get('pool_prefix4_unique') is not None else None
  runs.append(row)
 d=pd.DataFrame(runs)
 for (sid,m),g in d.groupby(['scenario_id','m']):
  known=g.objective.dropna()
  if len(known):
   best=float(known.min());d.loc[g.index,'common_best_observed_objective']=best;d.loc[g.index,'gap_to_common_best_observed_pct']=100*(g.objective-best)/best
 csv(OUT/'analysis/S4_scale_method_runs.csv',d);csv(OUT/'analysis/S4_query_phase_counts.csv',phase_rows);csv(OUT/'analysis/S4_numerical_output_audit.csv',audit)
 scenario=[]
 for (sid,m,method),g in d.groupby(['scenario_id','m','method']):
  ok=g[g.status=='PASS'];required=1 if method=='ue_bibeam' else 3
  row={'scenario_id':sid,'m':m,'method':method,'planned_repeats':required,'completed_repeats':len(ok),'all_repeats_pass':len(ok)==required,'exact_reference_available':(sid,m) in refmaps,'B_over_full_states':256/(1<<m),'objective_mean':ok.objective.mean() if len(ok) else None,'regret_mean_pct':ok.conditional_regret_pct.mean() if ok.conditional_regret_pct.notna().any() else None,'regret_median_seed_pct':ok.conditional_regret_pct.median() if ok.conditional_regret_pct.notna().any() else None,'regret_max_seed_pct':ok.conditional_regret_pct.max() if ok.conditional_regret_pct.notna().any() else None,'hits':int(ok.numerically_equivalent_hit.fillna(False).sum()),'hit_fraction':ok.numerically_equivalent_hit.mean() if ok.numerically_equivalent_hit.notna().any() else None}
  for c in ['online_wall','UE_queries','physical_UE_calls','candidate_wall_inclusive','inference_wall_nested','proxy_DP_wall_nested','candidate_wall_excluding_inference_and_DP','UE_wall','LS_wall_excluding_UE','greedy_initial_queries','greedy_initial_wall','LS_unique_queries','peak_online_RSS_MiB','prefix4_coverage']:
   row[c+'_mean']=ok[c].mean() if len(ok) else None
  scenario.append(row)
 s=pd.DataFrame(scenario);csv(OUT/'analysis/S4_scenario_means.csv',s)
 summaries=[]
 for (m,method),g in s.groupby(['m','method']):
  ok=g[g.all_repeats_pass];numeric=ok[ok.exact_reference_available]
  row={'m':m,'method':method,'planned_scenarios':6,'completed_scenarios':len(ok),'conditional_reference_scenarios':len(numeric),'B_over_full_states':256/(1<<int(m)),'mean_scenario_regret_pct':numeric.regret_mean_pct.mean() if len(numeric) else None,'median_scenario_regret_pct':numeric.regret_mean_pct.median() if len(numeric) else None,'max_scenario_mean_regret_pct':numeric.regret_mean_pct.max() if len(numeric) else None,'mean_hit_fraction':numeric.hit_fraction.mean() if len(numeric) else None}
  for c in ['online_wall_mean','UE_queries_mean','candidate_wall_inclusive_mean','inference_wall_nested_mean','proxy_DP_wall_nested_mean','UE_wall_mean','LS_wall_excluding_UE_mean','greedy_initial_queries_mean','greedy_initial_wall_mean','LS_unique_queries_mean','peak_online_RSS_MiB_mean','prefix4_coverage_mean']:
   row['scenario_mean_'+c]=ok[c].mean() if len(ok) else None
  row['median_scenario_online_wall']=ok.online_wall_mean.median() if len(ok) else None;row['max_scenario_mean_online_wall']=ok.online_wall_mean.max() if len(ok) else None
  summaries.append(row)
 csv(OUT/'analysis/S4_method_summary_by_m.csv',summaries)
 tidy=[]
 for (m,method),g in s.groupby(['m','method']):
  ok=g[g.all_repeats_pass]
  for metric in ['regret_mean_pct','hit_fraction','online_wall_mean','UE_queries_mean','peak_online_RSS_MiB_mean','candidate_wall_inclusive_mean','inference_wall_nested_mean','proxy_DP_wall_nested_mean','UE_wall_mean','LS_wall_excluding_UE_mean','greedy_initial_queries_mean','greedy_initial_wall_mean','LS_unique_queries_mean']:
   vals=ok[metric].dropna()
   tidy.append({'m':m,'method':method,'metric':metric,'scenario_count':len(vals),'mean':vals.mean() if len(vals) else None,'median':vals.median() if len(vals) else None,'maximum':vals.max() if len(vals) else None,'minimum':vals.min() if len(vals) else None,'replicate_unit':'scenario mean over prescribed technical seeds, not pooled seeds'})
 csv(OUT/'analysis/S4_all_metrics_descriptive_summary.csv',tidy)
 paired=[];counts=[]
 for m in [10,12,14]:
  for comparator in ['greedy_ils','ue_bibeam','sa_original']:
   pairs=[];timepairs=[]
   for sid in range(4401,4407):
    pg=s[(s.scenario_id==sid)&(s.m==m)&(s.method=='proposed')].iloc[0];cg=s[(s.scenario_id==sid)&(s.m==m)&(s.method==comparator)].iloc[0]
    complete=bool(pg.all_repeats_pass and cg.all_repeats_pass and (sid,m) in refmaps)
    row={'scenario_id':sid,'m':m,'comparator':comparator,'eligible_pair':complete,'Proposed_regret_mean_pct':pg.regret_mean_pct,'comparator_regret_mean_pct':cg.regret_mean_pct,'regret_difference_Proposed_minus_comparator_pp':pg.regret_mean_pct-cg.regret_mean_pct if complete else None,'wall_difference_Proposed_minus_comparator_s':pg.online_wall_mean-cg.online_wall_mean if pg.all_repeats_pass and cg.all_repeats_pass else None,'outcome':None}
    if complete:
     delta=pg.objective_mean-cg.objective_mean;eps=epsilon(refmaps[(sid,m)][0]);row['outcome']='tie' if abs(delta)<=eps else 'win' if delta<0 else 'loss';pairs.append(row)
    if pg.all_repeats_pass and cg.all_repeats_pass:timepairs.append({'Proposed':pg.online_wall_mean,'comparator':cg.online_wall_mean,'difference':row['wall_difference_Proposed_minus_comparator_s']})
    paired.append(row)
   diffs=[x['regret_difference_Proposed_minus_comparator_pp'] for x in pairs]
   counts.append({'m':m,'comparator':comparator,'paired_scenarios':len(pairs),'wins':sum(x['outcome']=='win' for x in pairs),'ties':sum(x['outcome']=='tie' for x in pairs),'losses':sum(x['outcome']=='loss' for x in pairs),'mean_paired_regret_difference_pp':float(np.mean(diffs)) if diffs else None,'median_paired_regret_difference_pp':float(np.median(diffs)) if diffs else None,'max_paired_regret_difference_pp':float(np.max(diffs)) if diffs else None,'win_plus_tie_at_least_loss':sum(x['outcome'] in ['win','tie'] for x in pairs)>=sum(x['outcome']=='loss' for x in pairs) if pairs else None,'paired_time_scenarios':len(timepairs),'mean_paired_time_difference_s':float(np.mean([x['difference'] for x in timepairs])) if timepairs else None,'mean_Proposed_on_common_time_cases_s':float(np.mean([x['Proposed'] for x in timepairs])) if timepairs else None,'mean_comparator_on_common_time_cases_s':float(np.mean([x['comparator'] for x in timepairs])) if timepairs else None,'statistical_scope':'descriptive six exploratory scenarios, no hypothesis tests'})
 csv(OUT/'analysis/S4_paired_regret_by_m.csv',paired);csv(OUT/'analysis/S4_win_tie_loss_by_m.csv',counts)
 costs=[];ed=pd.DataFrame(enumrows)
 for sid in range(4401,4407):
  for m in [10,12,14]:
   p=s[(s.scenario_id==sid)&(s.m==m)&(s.method=='proposed')].iloc[0]
   for method in ['enum_serial','enum_4core']:
    e=ed[(ed.scenario_id==sid)&(ed.m==m)&(ed.method==method)].iloc[0];complete=bool(e.full_valid_reference and p.all_repeats_pass);bound=e.completion_wall_lower_bound_s
    costs.append({'scenario_id':sid,'m':m,'reference_method':method,'Proposed_online_mean_s':p.online_wall_mean,'enum_completed':bool(e.full_valid_reference),'enum_online_wall_s':e.online_wall if e.full_valid_reference else None,'enum_completion_wall_lower_bound_s':bound,'enum_over_Proposed_ratio':e.online_wall/p.online_wall_mean if complete else None,'enum_over_Proposed_lower_bound':bound/p.online_wall_mean if p.all_repeats_pass and pd.notna(bound) else None,'Proposed_wall_saving_pct':100*(1-p.online_wall_mean/e.online_wall) if complete else None,'Proposed_wall_saving_lower_bound_pct':100*(1-p.online_wall_mean/bound) if p.all_repeats_pass and pd.notna(bound) else None,'different_core_resources':method=='enum_4core'})
 csv(OUT/'analysis/S4_fresh_runtime_by_m.csv',costs)
 gate={'status':'S4_COMPUTATIONS_AND_DESCRIPTIVE_ANALYSIS_COMPLETE','optimization_planned':180,'optimization_passed':int((d.status=='PASS').sum()),'optimization_failed_retained':int((d.status!='PASS').sum()),'serial_tables_complete':int(ed[ed.method=='enum_serial'].full_valid_reference.sum()),'parallel_tables_complete':int(ed[ed.method=='enum_4core'].full_valid_reference.sum()),'conditional_references_available':len(refmaps),'planned_conditional_references':18,'all_RG_rows_pass':True,'table_overlap_bitwise_rows':sum(r['overlapping_masks'] for r in agreements),'all_output_audits_passed':True,'S3_candidate_matrix_reproduction':int(((d.method=='proposed')&(d.status=='PASS')).sum()),'no_significance_tests':True,'first_batch_and_formal_sources_unchanged':verify_s4(),'all_optimization_frozen_before_reference':True,'manuscript_Word_modified':False,'readiness':'draft_with_placeholders','at':now()}
 gate['UE_solver_failure_records_retained']=len(list(OUT.rglob('UE_failure.json')))
 gate['RG_statement_scope']='all recorded converged state rows; any failed calls separately retained'
 gate['nested_physical_states_bitwise_pairs']=sum(r['overlapping_masks'] for r in nested)
 dump(OUT/'completion_check.json',gate);print(json.dumps(gate,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
