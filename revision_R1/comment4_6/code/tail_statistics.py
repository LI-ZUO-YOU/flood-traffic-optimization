from load_frozen_results import *

def legacy(out):
 out=Path(out);require_gate(out,'G0');d=tables(out);raw=d['S2_original_paths_revalued.csv'];x=raw[raw.path_label.isin(LEGACY_METHODS)].copy();x=x.sort_values(['precision_tier','path_label','scenario_id']);base=out/'01_legacy10'
 csv(base/'legacy10_per_scenario.csv',x);summary=[];ordered=[];loso=[];checks=[]
 reference=d['S2_old10_regret_summary.csv'].set_index(['method','precision_tier'])
 for (method,tier),g in x.groupby(['path_label','precision_tier'],sort=True):
  g=g.sort_values(['regret_pct','scenario_id']);vals=g.regret_pct.to_numpy();meta=order90(vals);p90=scenario_quantile(vals,unit='scenario');assert abs(p90-meta['P90_manual'])<1e-13
  row={'method':method,'precision_tier':tier,'independent_scenarios':10,'runs_per_scenario':1,'historical_only':True,'mean_regret_pct':vals.mean(),'median_regret_pct':q(vals,.5),'P90_regret_pct':p90,'max_regret_pct':vals.max(),'seed_SD':'NA: one archived path per scenario'};summary.append(row)
  for field in ['mean_regret_pct','median_regret_pct','P90_regret_pct','max_regret_pct']:
   diff=row[field]-reference.loc[(method,tier),field];assert abs(diff)<=1e-8
   checks.append({'source':'4.2 S2_old10_regret_summary.csv','method':method,'precision_tier':tier,'metric':field,'recomputed':row[field],'archived':reference.loc[(method,tier),field],'absolute_error':abs(diff),'tolerance_pp':1e-8,'status':'PASS'})
  for rank,r in enumerate(g.itertuples(),1):
   weight=.9 if rank==9 else .1 if rank==10 else 0.
   ordered.append({'method':method,'precision_tier':tier,'rank_ascending':rank,'scenario_id':r.scenario_id,'regret_pct':r.regret_pct,'P90_weight':weight,'P90_component_pp':weight*r.regret_pct,'full10_P90_pct':p90,'source':'fixed historical path, not a new algorithm run'})
 for tier in PRECISIONS:
  p=x[x.precision_tier==tier].pivot(index='scenario_id',columns='path_label',values='regret_pct').sort_index()
  fullA=scenario_quantile(p.Proposed_B256,unit='scenario');fullB=scenario_quantile(p.SA_original_fixed_seed,unit='scenario')
  for sid in range(1001,1011):
   keep=p.loc[p.index!=sid];a=scenario_quantile(keep.Proposed_B256,unit='scenario');b=scenario_quantile(keep.SA_original_fixed_seed,unit='scenario')
   loso.append({'precision_tier':tier,'omitted_scenario_for_sensitivity_only':sid,'remaining_scenarios':9,'full10_Proposed_P90_pct':fullA,'full10_SA_P90_pct':fullB,'full10_delta_P90_pp':fullA-fullB,'LOSO9_Proposed_P90_pct':a,'LOSO9_SA_P90_pct':b,'LOSO9_delta_P90_pp':a-b,'change_from_full10_delta_pp':a-b-(fullA-fullB),'primary_result_retains_all10':True})
 csv(base/'legacy10_quantiles.csv',summary);csv(base/'legacy10_P90_order_statistics.csv',ordered);csv(base/'legacy10_LOSO.csv',loso);csv(out/'00_audit/legacy10_anchor_checks.csv',checks)
 dump(out/'00_audit/S1_gate.json',{'status':'PASS','at':now(),'historical_rows':40,'method_precision_quantile_rows':4,'order_statistic_rows':40,'LOSO_rows':20,'source_anchor_checks':len(checks),'original_paths_same_between_precision_tiers':True,'historical_SA_single_fixed_seed_only':True,'new_UE_or_optimization':0})
 print('S1 legacy10 PASS: all16 numeric anchors reproduced',flush=True)

def new30(out):
 out=Path(out);require_gate(out,'S1');src=tables(out);raw=src['all_run_results.csv'];x=raw[raw.phase=='query_cap'].copy();base=out/'02_new30';csv(base/'new30_run_level.csv',x);groups=[];crosschecks=[]
 oldsc=src['scenario_seed_summaries.csv'];oldsc=oldsc[oldsc.phase=='query_cap'].set_index(['scenario_id','method'])
 def compare(source,method,sid,metric,value,archived,tol=1e-9):
  assert np.isfinite(value) and np.isfinite(archived)
  diff=abs(value-archived);assert diff<=tol,(source,method,sid,metric,value,archived,diff)
  crosschecks.append({'source_table':source,'method':method,'scenario_id':sid,'metric':metric,'recomputed':value,'archived':archived,'absolute_error':diff,'tolerance':tol,'status':'PASS'})
 for (sid,m),g in x.groupby(['scenario_id','method'],sort=True):
  vals=g.relative_regret_pct.to_numpy();n=len(vals);row={'scenario_id':sid,'method':m,'label':LABEL[m],'independent_scenario':True,'seeds_recorded':n,'seed_indices':'|'.join(map(str,sorted(g.replicate))),'mean_regret_pct':vals.mean(),'median_seed_regret_pct':q(vals,.5),'seed_SD_regret_pp':float(vals.std(ddof=1)) if n>1 else None,'min_seed_regret_pct':vals.min(),'max_seed_regret_pct':vals.max(),'seed_IQR_pp':q(vals,.75)-q(vals,.25) if n>1 else None,'equivalence_hit_rate':g.numerical_equivalent_hit.mean(),'reference_J':g.exact_objective.iloc[0],'mean_J':g.objective.mean(),'equivalence_epsilon_J':g.equivalence_objective_epsilon.iloc[0],'within_1_5_rate':g.within_1_5_pct.mean(),'within_3_rate':g.within_3_pct.mean(),'mean_queries':g.queries.mean(),'archived_mean_shared_cache_online_seconds':g.online_total_seconds.mean()}
  groups.append(row);a=oldsc.loc[(sid,m)]
  for new,old in [('mean_regret_pct','mean_regret_pct'),('median_seed_regret_pct','median_regret_pct'),('min_seed_regret_pct','min_regret_pct'),('max_seed_regret_pct','max_regret_pct'),('equivalence_hit_rate','equivalent_hit_rate'),('within_1_5_rate','within_1_5_rate'),('within_3_rate','within_3_rate'),('mean_queries','mean_queries'),('archived_mean_shared_cache_online_seconds','mean_online_seconds_shared_cache')]:compare('scenario_seed_summaries.csv',m,sid,new,row[new],a[old])
  # The frozen export encoded one-run SD/IQR as0. Check that convention, then label them NA in4.6.
  compare('scenario_seed_summaries.csv',m,sid,'seed_SD_archived_compatibility',row['seed_SD_regret_pp'] if n>1 else 0.,a.seed_std_regret_pct)
  compare('scenario_seed_summaries.csv',m,sid,'seed_IQR_archived_compatibility',row['seed_IQR_pp'] if n>1 else 0.,a.seed_IQR_pct)
  assert a.replicates==n
 sc=pd.DataFrame(groups);csv(base/'new30_scenario_level.csv',sc);summary=[];orderrows=[];tail=[]
 R2=src['Table_R2_method_summary.csv'];R2=R2[R2.phase=='query_cap'].set_index('method')
 for m in METHODS:
  g=sc[sc.method==m];vals=g.mean_regret_pct.to_numpy();meta=order90(vals);p90=scenario_quantile(vals,unit='scenario');assert abs(meta['P90_manual']-p90)<1e-13
  row={'method':m,'label':LABEL[m],'independent_scenarios':30,'seeds_per_scenario':10 if m in STOCH else 1,'runs':int(g.seeds_recorded.sum()),'mean_scenario_mean_regret_pct':vals.mean(),'median_scenario_mean_regret_pct':q(vals,.5),'P75_scenario_mean_regret_pct':q(vals,.75),'P90_scenario_mean_regret_pct':p90,'max_scenario_mean_regret_pct':vals.max(),'mean_seed_SD_pp':g.seed_SD_regret_pp.mean() if m in STOCH else None,'P90_per_scenario_worst_seed_regret_pct':scenario_quantile(g.max_seed_regret_pct,unit='scenario'),'global_max_individual_regret_pct':g.max_seed_regret_pct.max(),'equivalence_hit_rate':g.equivalence_hit_rate.mean(),'mean_queries':g.mean_queries.mean(),'archived_mean_shared_cache_online_seconds':g.archived_mean_shared_cache_online_seconds.mean(),'seed_variability_status':'ten frozen seeds; mean sample SD' if m in STOCH else 'NA: one recorded run per scenario'};summary.append(row)
  a=R2.loc[m]
  for new,old in [('mean_scenario_mean_regret_pct','mean_scenario_mean_regret_pct'),('median_scenario_mean_regret_pct','median_scenario_mean_regret_pct'),('P90_scenario_mean_regret_pct','P90_scenario_mean_regret_pct'),('max_scenario_mean_regret_pct','max_scenario_mean_regret_pct'),('P90_per_scenario_worst_seed_regret_pct','P90_scenario_worst_seed_regret_pct'),('global_max_individual_regret_pct','max_single_run_regret_pct'),('equivalence_hit_rate','equivalent_objective_hit_rate'),('mean_queries','mean_queries'),('archived_mean_shared_cache_online_seconds','mean_execution_seconds_shared_cache')]:compare('Table_R2_method_summary.csv',m,None,new,row[new],a[old])
  compare('Table_R2_method_summary.csv',m,None,'mean_seed_SD_archived_compatibility',row['mean_seed_SD_pp'] if m in STOCH else 0.,a.mean_seed_std_pct)
  assert a.independent_scenarios==30 and a.runs==row['runs'] and a.replicates_per_scenario==row['seeds_per_scenario']
  for col,runcol in [('within_1_5_rate','within_1_5_rate'),('within_3_rate','within_3_rate')]:compare('Table_R2_method_summary.csv',m,None,col,g[runcol].mean(),a[col])
  ordered=g.sort_values(['mean_regret_pct','scenario_id'])
  for rank,r in enumerate(ordered.itertuples(),1):
   weight=.9 if rank==27 else .1 if rank==28 else 0.
   orderrows.append({'method':m,'rank_ascending':rank,'scenario_id':r.scenario_id,'scenario_mean_regret_pct':r.mean_regret_pct,'P90_weight':weight,'P90_component_pp':weight*r.mean_regret_pct,'full30_P90_pct':p90})
  for rank,r in enumerate(g.sort_values(['mean_regret_pct','scenario_id'],ascending=[False,True]).head(5).itertuples(),1):tail.append({'method':m,'rank_descending':rank,'scenario_id':r.scenario_id,'scenario_mean_regret_pct':r.mean_regret_pct,'worst_seed_regret_pct':r.max_seed_regret_pct,'seed_SD_pp':r.seed_SD_regret_pp,'retained_in_primary':True})
 su=pd.DataFrame(summary).set_index('method');pairs=[];pairsummary=[];loso=[]
 p=sc[sc.method=='proposed'].set_index('scenario_id').sort_index();kappa=js(out/'00_audit/analysis_protocol.json')['frozen_kappa']
 for m in COMPARATORS:
  c=sc[sc.method==m].set_index('scenario_id').sort_index();assert p.index.equals(c.index)
  delta=p.mean_regret_pct.to_numpy()-c.mean_regret_pct.to_numpy();tol=(100*kappa*np.maximum(1,abs(p.reference_J))/abs(p.reference_J)).to_numpy();sign=np.where(abs(delta)<=tol,'tie',np.where(delta<0,'Proposed_win','Proposed_loss'))
  for sid,dd,ss,tt in zip(p.index,delta,sign,tol):pairs.append({'scenario_id':sid,'comparator':m,'Proposed_scenario_mean_regret_pct':p.loc[sid,'mean_regret_pct'],'comparator_scenario_mean_regret_pct':c.loc[sid,'mean_regret_pct'],'delta_Proposed_minus_comparator_pp':dd,'frozen_equivalence_tolerance_pp':tt,'win_tie_loss':ss})
  fullA=scenario_quantile(p.mean_regret_pct,unit='scenario');fullB=scenario_quantile(c.mean_regret_pct,unit='scenario')
  pairsummary.append({'comparator':m,'independent_paired_scenarios':30,'mean_delta_pp':delta.mean(),'median_delta_pp':q(delta,.5),'P90_of_paired_differences_pp':q(delta,.9),'difference_of_P90s_pp':fullA-fullB,'Proposed_P90_pct':fullA,'comparator_P90_pct':fullB,'Proposed_wins':int((sign=='Proposed_win').sum()),'ties':int((sign=='tie').sum()),'Proposed_losses':int((sign=='Proposed_loss').sum()),'positive_is_unfavorable_to_Proposed':True,'inference':'descriptive only; no new p value or CI'})
  for sid in range(3001,3031):
   aa=p.loc[p.index!=sid,'mean_regret_pct'];bb=c.loc[c.index!=sid,'mean_regret_pct'];pa=scenario_quantile(aa,unit='scenario');pb=scenario_quantile(bb,unit='scenario')
   loso.append({'comparator':m,'omitted_scenario_for_sensitivity_only':sid,'remaining_scenarios':29,'full30_Proposed_P90_pct':fullA,'full30_comparator_P90_pct':fullB,'full30_delta_P90_pp':fullA-fullB,'LOSO29_Proposed_P90_pct':pa,'LOSO29_comparator_P90_pct':pb,'LOSO29_delta_P90_pp':pa-pb,'change_from_full30_delta_pp':pa-pb-(fullA-fullB),'primary_retains_all30':True})
 # Check archived primary pair directions without rerunning or replacing its tests/CIs.
 pp=pd.DataFrame(pairs);r3=src['Table_R3_primary_paired_comparisons.csv'];oldpaired=src['scenario_paired_differences.csv']
 for row in oldpaired.itertuples():
  new=pp[(pp.scenario_id==row.scenario_id)&(pp.comparator==row.comparator)].iloc[0]
  compare('scenario_paired_differences.csv',row.comparator,row.scenario_id,'direction_reversed_for4.6',-new.delta_Proposed_minus_comparator_pp,row.paired_difference_pp)
  compare('scenario_paired_differences.csv',row.comparator,row.scenario_id,'unchanged_equivalence_tolerance_pp',new.frozen_equivalence_tolerance_pp,row.equivalence_tolerance_pp)
 ps=pd.DataFrame(pairsummary).set_index('comparator')
 for row in r3.itertuples():
  a=ps.loc[row.comparator];compare('Table_R3_primary_paired_comparisons.csv',row.comparator,None,'mean_effect_sign_reversed',-a.mean_delta_pp,row.mean_paired_improvement_pp);compare('Table_R3_primary_paired_comparisons.csv',row.comparator,None,'median_effect_sign_reversed',-a.median_delta_pp,row.median_paired_improvement_pp)
  assert (a.Proposed_wins,a.ties,a.Proposed_losses)==(row.proposed_wins,row.ties_by_empirical_epsilon,row.proposed_losses)
 csv(base/'new30_tail_summary.csv',su.reset_index());csv(base/'new30_paired_scenarios.csv',pairs);csv(base/'new30_paired_basic_summary.csv',ps.reset_index());csv(base/'new30_LOSO.csv',loso);csv(base/'new30_P90_order_statistics.csv',orderrows);csv(base/'new30_top_tail_influence.csv',tail);csv(out/'00_audit/new30_archive_anchor_checks.csv',crosschecks)
 # Preserve the entire frozen summary and original tests, including their existing intervals, as historical copies only.
 for name in ['Table_R2_method_summary.csv','Table_R3_primary_paired_comparisons.csv','scenario_paired_differences.csv']:csv(out/'00_audit'/('archived_'+name),src[name])
 csv(out/'06_delivery/Table_4_6_primary.csv',su.reset_index());csv(out/'06_delivery/Table_4_6_basic_paired_comparisons.csv',ps.reset_index())
 dump(out/'00_audit/G1_gate.json',{'status':'PASS','at':now(),'scope':'S0+S1+new30 baseline verification only','legacy_anchors':16,'new30_numeric_archive_crosschecks':len(crosschecks),'new30_scenario_method_rows':len(sc),'new30_methods':8,'paired_scenario_rows':len(pairs),'LOSO_rows':len(loso),'original_R3_tests_unchanged':True,'archived_CIs':'copied as frozen historical values, not recalculated or relabelled scenario-only','deterministic_SD_display':'NA; archived0 verified as old export convention','bootstrap_executions':0,'variance_decompositions':0,'no_new_experiments':True})
 print('S2 foundation G1 PASS: all frozen30-scenario summary anchors reproduced',flush=True)
