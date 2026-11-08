from common43 import *
import math

def flat(r):
 v={k:x for k,x in r.items() if isinstance(x,(str,int,float,bool)) or x is None}
 v['sequence']='|'.join(map(str,r['sequence']));v['seed_values_json']=json.dumps(r.get('seed_values',{}),ensure_ascii=False)
 v['seed']=r.get('seed_values',{}).get('algorithm_seed',r.get('seed_values',{}).get('candidate_seed'))
 v['candidate_seed']=r.get('seed_values',{}).get('candidate_seed');v['screening_seed']=r.get('seed_values',{}).get('screening_seed')
 v['bitwise_gate_pass']=r['bitwise_gate']['all_pass'];return v

def main():
 assert js(OUT/'logs/serial_batch_completion.json')['tasks']==450
 assert js(OUT/'logs/parallel_enum_completion.json')['tasks']==90
 verify_sources();rows=[];checks=[];components=[];enumeration=[]
 for p in sorted((OUT/'02_serial_B256/runs').glob('scenario_*/*/repeat_*/timing.json')):
  r=js(p);rows.append(flat(r));checks.append({'scenario_id':r['scenario_id'],'method':r['method'],'repeat_id':r['repeat_id'],**r['bitwise_gate']})
  assert r['bitwise_gate']['all_pass'] and r['fresh_physical_cache'] and r['threads']==1 and r['single_process_primary'] and r['cpu_core']==CORE
  assert r['wall_clock_cap'] is None
  nonoverlap=r['candidate_wall_excluding_inference']+r['inference_wall_nested_in_candidate']+r['UE_solver_wall']+r['LS_wall_excluding_UE']+r['other_wall']+r['DP_wall']
  assert abs(nonoverlap-r['total_online_wall'])<1e-6
  components.append({'scenario_id':r['scenario_id'],'method':r['method'],'repeat_id':r['repeat_id'],
    'candidate_construction_screening_excluding_inference':r['candidate_wall_excluding_inference'],'surrogate_inference':r['inference_wall_nested_in_candidate'],
    'UE_network_calls':r['UE_solver_wall'],'LS_computation_excluding_UE':r['LS_wall_excluding_UE'],'DP':r['DP_wall'],'other':r['other_wall'],'total_online_wall':r['total_online_wall'],
    'candidate_inclusive_nested_diagnostic':r['candidate_wall_inclusive'],'UE_kernel_nested_diagnostic':r['UE_kernel_wall_nested'],'LS_including_UE_nested_diagnostic':r['LS_wall_inclusive_of_UE']})
  if r['method']=='enum_serial':enumeration.append(flat(r))
 d=pd.DataFrame(rows);assert len(d)==450
 query=d[d.method!='enum_serial'];csv(OUT/'02_serial_B256/S2_fresh_B256_raw.csv',query)
 csv(OUT/'02_serial_B256/S2_full_enumeration_raw.csv',enumeration);csv(OUT/'02_serial_B256/S2_bitwise_acceptance.csv',checks)
 csv(OUT/'02_serial_B256/S2_component_breakdown.csv',components)
 noise=d[['scenario_id','method','repeat_id','total_online_wall','cpu_user_seconds','cpu_system_seconds']].copy()
 noise['process_CPU_seconds_over_online_wall']=(noise.cpu_user_seconds+noise.cpu_system_seconds)/noise.total_online_wall
 noise['low_CPU_share_descriptive_flag']=noise.process_CPU_seconds_over_online_wall<.85
 noise['excluded_from_main_analysis']=False
 csv(OUT/'02_serial_B256/S2_system_noise_diagnostics.csv',noise)
 par=[flat(js(p)) for p in sorted((OUT/'03_enum_within_scenario_4core/runs').glob('scenario_*/repeat_*/timing.json'))]
 assert len(par)==90 and all(r['bitwise_gate_pass'] for r in par)
 pdf=pd.DataFrame(par);csv(OUT/'03_enum_within_scenario_4core/S2_enum4within_raw.csv',pdf)
 state_checks=[]
 for mode,parent,pattern in [('serial',OUT/'02_serial_B256/runs','scenario_*/enum_serial/repeat_*/all_1024_states.csv.gz'),
                             ('within_scenario4core',OUT/'03_enum_within_scenario_4core/runs','scenario_*/repeat_*/all_1024_states.csv.gz')]:
  for file in sorted(parent.glob(pattern)):
   sid=int(next(s for s in file.parts if s.startswith('scenario_')).split('_')[1]);repeat=int(file.parent.name.split('_')[1])
   actual=frame(file).sort_values('subset_mask');expected=frame(ROOT/f'exact/scenario_{sid}/all_1024_states.csv.gz').sort_values('subset_mask')
   assert len(actual)==len(expected)==1024 and actual.subset_mask.to_list()==expected.subset_mask.to_list()
   tstt_bits=actual.tstt.to_numpy().view(np.uint64)==expected.tstt.to_numpy().view(np.uint64)
   loss_bits=actual.loss.to_numpy().view(np.uint64)==expected.loss.to_numpy().view(np.uint64)
   state_checks.append({'scenario_id':sid,'repeat_id':repeat,'mode':mode,'states':1024,'TSTT_bitwise_equal_states':int(sum(tstt_bits)),
     'loss_bitwise_equal_states':int(sum(loss_bits)),'max_abs_TSTT_difference':float(max(abs(actual.tstt.to_numpy()-expected.tstt.to_numpy()))),
     'all_states_within_actual_RG1e9':bool(actual.relative_gap.le(1e-9).all())})
 csv(OUT/'06_analysis/S2_full_enumeration_state_table_agreement.csv',state_checks)
 assert len(state_checks)==180 and all(r['TSTT_bitwise_equal_states']==1024 and r['loss_bitwise_equal_states']==1024 for r in state_checks)
 # Same scenario is the statistical unit. Repeated seeds/noise are nested.
 allruns=pd.concat([d,pdf],ignore_index=True)
 scenario=allruns.groupby(['method','scenario_id'],as_index=False).agg(
  mean_online_wall=('total_online_wall','mean'),median_online_wall=('total_online_wall','median'),min_repeat_wall=('total_online_wall','min'),max_repeat_wall=('total_online_wall','max'),
  mean_regret_pct=('regret_pct','mean'),mean_UE_queries=('unique_UE_queries','mean'),repeat_count=('repeat_id','size'))
 assert scenario.repeat_count.eq(3).all()
 csv(OUT/'06_analysis/S2_scenario_means.csv',scenario)
 summaries=[]
 for method,g in scenario.groupby('method'):
  summaries.append({'method':method,'scenarios':30,'repeats_per_scenario':3,'cores':4 if method=='enum_within_scenario_4core' else 1,
    'mean_online_wall':g.mean_online_wall.mean(),'median_scenario_online_wall':g.mean_online_wall.median(),'P90_scenario_online_wall':np.quantile(g.mean_online_wall,.9),
    'mean_scenario_regret_pct':g.mean_regret_pct.mean(),'median_scenario_regret_pct':g.mean_regret_pct.median(),'P90_scenario_regret_pct':np.quantile(g.mean_regret_pct,.9),
    'max_scenario_regret_pct':g.mean_regret_pct.max(),'mean_UE_queries':g.mean_UE_queries.mean()})
 csv(OUT/'06_analysis/S2_method_summary.csv',summaries)
 wide=scenario.pivot(index='scenario_id',columns='method',values='mean_online_wall')
 rng=np.random.default_rng(20261028043);idx=rng.integers(0,30,size=(20000,30));paired=[];rawpaired=[]
 for comparator in [m for m in wide.columns if m!='proposed']:
  delta=(wide[comparator]-wide.proposed).to_numpy();boot=delta[idx].mean(axis=1);lo,hi=np.quantile(boot,[.025,.975])
  paired.append({'comparator':comparator,'reference':'proposed','scenarios':30,'mean_time_difference_comparator_minus_Proposed':delta.mean(),
    'median_time_difference':np.median(delta),'P90_time_difference':np.quantile(delta,.9),'CI95_mean_low':lo,'CI95_mean_high':hi,
    'cases_Proposed_faster':int(sum(delta>0)),'cases_Proposed_slower':int(sum(delta<0)),'ratio_of_mean_comparator_to_Proposed':wide[comparator].mean()/wide.proposed.mean(),
    'resource_note':'4 cores vs1; separate operational configuration' if comparator=='enum_within_scenario_4core' else 'matched1-core policy'})
  for sid,val in zip(wide.index,delta):rawpaired.append({'scenario_id':sid,'comparator':comparator,'comparator_minus_Proposed_seconds':val,
    'Proposed_mean_seconds':wide.loc[sid,'proposed'],'comparator_mean_seconds':wide.loc[sid,comparator]})
 csv(OUT/'06_analysis/S2_paired_time_comparisons.csv',paired);csv(OUT/'06_analysis/S2_scenario_paired_time_differences.csv',rawpaired)
 # Preserved mean is primary. Median-of-three is a descriptive sensitivity,
 # never a fastest-run selection or a reason to drop a flagged observation.
 med=allruns.groupby(['scenario_id','method']).total_online_wall.median().unstack('method')
 sens=[]
 for row in paired:
  comparator=row['comparator'];delta_med=med[comparator]-med.proposed
  sens.append({'comparator':comparator,'mean_paired_difference_using_repeat_means':row['mean_time_difference_comparator_minus_Proposed'],
    'mean_paired_difference_using_repeat_medians':delta_med.mean(),'same_direction':bool(np.sign(delta_med.mean())==np.sign(row['mean_time_difference_comparator_minus_Proposed'])),
    'cases_Proposed_faster_using_repeat_median':int(sum(delta_med>0)),'observations_removed':0,'scope':'secondary descriptive sensitivity; primary remains mean of all3'})
 csv(OUT/'06_analysis/S2_repeat_median_sensitivity.csv',sens)
 dump(OUT/'02_serial_B256/S2_noise_summary.json',{'flagged_primary_runs':int(noise.low_CPU_share_descriptive_flag.sum()),'total_primary_runs':450,
   'minimum_process_CPU_over_wall':float(noise.process_CPU_seconds_over_online_wall.min()),'threshold':.85,'runs_excluded':0,
   'meaning':'descriptive scheduling/blocking variability indicator, not proof of a particular external process or frequency cause',
   'median_sensitivity_all_directions_unchanged':all(x['same_direction'] for x in sens)})
 delta=wide.enum_serial-wide.enum_within_scenario_4core
 csv(OUT/'06_analysis/S2_enumeration_parallel_comparison.csv',[{'scenario_id':sid,'serial_mean_wall':wide.loc[sid,'enum_serial'],
    'four_core_mean_wall':wide.loc[sid,'enum_within_scenario_4core'],'serial_minus_four_core_seconds':delta.loc[sid],
    'serial_to_four_core_latency_ratio':wide.loc[sid,'enum_serial']/wide.loc[sid,'enum_within_scenario_4core']} for sid in wide.index])
 comp=pd.DataFrame(components);cm=comp.groupby(['method','scenario_id'],as_index=False).mean(numeric_only=True).groupby('method',as_index=False).mean(numeric_only=True)
 csv(OUT/'06_analysis/S2_component_summary.csv',cm.drop(columns=['scenario_id','repeat_id']))
 offline=js(OUT/'05_offline_cost/offline_summary.json');C=offline['same_host_measured_component_sum']
 train=frame(OUT/'05_offline_cost/S3_temporary_training_members.csv')
 original_train_path=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第二周工作\v2_day2_huber_ensemble\ensemble_training_summary.csv')
 original_train=frame(original_train_path);tj=train.merge(original_train,on='member_id',suffixes=('_new','_old'))
 checks_train=[]
 for x in tj.itertuples(index=False):checks_train.append({'member_id':x.member_id,'temporary_model_SHA256':x.model_hash_sha256_new,'original_model_SHA256':x.model_hash_sha256_old,
   'checkpoint_file_bitwise_identical':x.model_hash_sha256_new==x.model_hash_sha256_old,'epochs_completed_equal':x.epochs_completed_new==x.epochs_completed_old,
   'best_epoch_equal':x.best_epoch_new==x.best_epoch_old,'temporary_models_used_for_search':False})
 assert len(checks_train)==10 and all(x['checkpoint_file_bitwise_identical'] and x['epochs_completed_equal'] and x['best_epoch_equal'] for x in checks_train)
 csv(OUT/'05_offline_cost/S3_training_replication_identity.csv',checks_train)
 dump(OUT/'05_offline_cost/temporary_training_replication_acceptance.json',{'status':'PASS','identical_checkpoint_SHA256':10,'identical_completed_epochs':10,'identical_best_epochs':10,'official_models_not_overwritten':True,'temporary_models_never_used_in_search':True})
 crossings=[];curves=[]
 for row in paired:
  mean=row['mean_time_difference_comparator_minus_Proposed'];lo=row['CI95_mean_low'];hi=row['CI95_mean_high']
  crosses=math.ceil(C/mean) if mean>0 else None
  crossings.append({'comparator':row['comparator'],'offline_cost_component_estimate':C,'mean_online_saving_comparator_minus_Proposed':mean,
    'arithmetic_mean_crossover_scenarios':crosses,'crossover_from_CI_high_saving':math.ceil(C/hi) if hi>0 else None,
    'crossover_from_CI_low_saving':math.ceil(C/lo) if lo>0 else None,'finite_crossover_supported_by_positive_CI_low':lo>0,
    'no_finite_positive_mean_crossover':mean<=0,'cost_scope':'same-host measured components using original labels; not confirmed end-to-end new-label training',
    'quality_matched_comparison':False,'resources':'four-core comparator vs single-core Proposed' if row['comparator']=='enum_within_scenario_4core' else 'single-core both'})
  ctime=wide[row['comparator']].mean();ptime=wide.proposed.mean()
  for N in [1,5,10,20,30,50,100,200,500]:curves.append({'comparator':row['comparator'],'N':N,'Proposed_total_component_model':C+N*ptime,'comparator_total_online_model':N*ctime,
    'Proposed_minus_comparator_model':C-N*mean,'includes_research_diagnostics':False,'comparator_setup_excluded_in_this_formula':True})
 csv(OUT/'05_offline_cost/S3_amortization_scenarios.csv',crossings);csv(OUT/'05_offline_cost/S3_cost_curves.csv',curves)
 # Expose the extra operational pool startup intercept, rather than hiding it.
 pool=js(OUT/'03_enum_within_scenario_4core/pool_setup.json')['setup_seconds_including_process_start_and_JIT_warm']
 csv(OUT/'05_offline_cost/S3_pool_startup_sensitivity.csv',[{'N':N,'Proposed_component_cost':C+N*wide.proposed.mean(),
    'enum4_cost_including_pool_startup':pool+N*wide.enum_within_scenario_4core.mean(),'pool_startup_seconds':pool} for N in [1,5,10,30,100]])
 research=[
 {'activity':'4.1 confirmatory searches','count':2250,'unit':'algorithm runs, query and historical time-cap groups','elapsed_wall':None,'role':'research validation','note':'not2250 independent flood scenarios; includes shared cache; not extra deployment cost'},
 {'activity':'4.1 full primary tables','count':30720,'unit':'state rows','elapsed_wall':None,'role':'research reference','note':'may reuse search states, do not add as extra physical solves'},
 {'activity':'4.1 round2 replay','count':300,'unit':'deterministic table-only replays','elapsed_wall':None,'role':'research diagnosis','note':'zero fresh UE solves'},
 {'activity':'4.1 round2 isolated enumeration batches','count':61440,'unit':'actual production UE solves','elapsed_wall':None,'role':'research timing','note':'serial and four-scenario concurrent modes; prior batch boundaries differ'},
 {'activity':'4.1 round2 training-state cost passes','count':6356,'unit':'actual UE solves over3178 distinct training states','elapsed_wall':None,'role':'research timing','note':'two complete passes retained; not unique additional training data'},
 {'activity':'4.2 minimal missing strict states','count':41,'unit':'actual UE solves','elapsed_wall':None,'role':'research precision audit','note':'153strict states reused, no algorithm rerun'},
 {'activity':'4.3 primary serial run set','count':450,'unit':'controlled timing tasks','elapsed_wall':js(OUT/'logs/serial_batch_completion.json')['elapsed_this_invocation_seconds'],'role':'research timing','note':'includes90enumeration tasks and360B256 algorithm tasks'},
 {'activity':'4.3 within-scenario4core enumeration','count':90,'unit':'one-scenario timing tasks','elapsed_wall':js(OUT/'logs/parallel_enum_completion.json')['complete_batch_wall_seconds'],'role':'research timing','note':'4coreswithin one scenario; not4 simultaneous scenarios'},
 {'activity':'4.3 cold process checks','count':5,'unit':'fixed-scenario process supplements','elapsed_wall':frame(OUT/'04_cold_start/S2_cold_start_raw.csv').process_launch_through_exports_wall.sum(),'role':'research timing','note':'one prescribed scenario only, not a new12s cap experiment'},
 {'activity':'4.3 offline timing replication','count':3178,'unit':'unique original training states plus ten temporary members','elapsed_wall':offline['observed_workflow_wall'],'role':'cost-component measurement','note':'current labels timed; model training uses archived labels, official weights unchanged'}]
 csv(OUT/'05_offline_cost/S3_research_cost_ledger.csv',research)
 # Schedule interval audit: no two primary online tasks overlap.
 intervals=sorted([(datetime.datetime.fromisoformat(r['started_Asia_Shanghai']),datetime.datetime.fromisoformat(r['finished_Asia_Shanghai'])) for r in rows])
 assert all(intervals[i][0]>=intervals[i-1][1] for i in range(1,len(intervals)))
 dump(OUT/'06_analysis/analysis_summary.json',{'primary_tasks':450,'B256_algorithm_tasks':360,'serial_enum_tasks':90,'within_scenario4core_enum_tasks':90,
    'all_bitwise_gates_pass':True,'all_primary_intervals_nonoverlapping':True,'all_primary_on_one_core':True,'stochastic_rep_indices':[0,1,2],
    'all_components_add_without_nested_double_count':True,'offline_component_estimate':C,'new_fixed12s_experiment':False,
    'pool_startup_seconds':pool,'serial_enum_mean_wall':wide.enum_serial.mean(),'four_core_enum_mean_wall':wide.enum_within_scenario_4core.mean(),
    'Proposed_mean_wall':wide.proposed.mean(),'scenario_statistical_units':30,'bootstrap_resamples':20000,'means':summaries,'paired':paired})
 verify_sources();print(pd.DataFrame(summaries).to_string(index=False),flush=True);print('Cost analysis complete.',flush=True)

if __name__=='__main__':main()
