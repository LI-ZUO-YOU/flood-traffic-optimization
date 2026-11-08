from common44 import *
import math,zipfile,statistics
def main():
 completion=js(OUT/'logs/component_batch_completion.json');assert completion['tasks']==90
 limits=js(OUT/'00_lock/calibrated_resource_limits.json');protocol=js(OUT/'00_lock/frozen_scaling_protocol.json')
 records=[];policies=[];balance=[];cold=[]
 calibration=[]
 for rep in range(3):
  folder=OUT/f'03_component_scaling/calibration/repeat_{rep:02d}';mon=js(folder/'parent_monitor.json');r=js(folder/'result.json')
  calibration.append({'repeat':rep,'scenario_id':3001,'m':10,'candidate_seed_index':0,'candidate_wall':r['candidate_wall'],'sampled_online_RSS_available':mon['peak_online_sampled_RSS_bytes']>0,'sampled_online_RSS_bytes':mon['peak_online_sampled_RSS_bytes'] if mon['peak_online_sampled_RSS_bytes']>0 else None,'lifetime_kernel_peak_wset_bytes':r['worker_peak_wset'],'monitor_samples':mon['monitor_samples'],'used_for_time_calibration_only':True})
 csv(OUT/'03_component_scaling/S3_calibration_runs.csv',calibration)
 csv(OUT/'00_lock/S0_resource_limits.csv',[{'available_RAM_at_freeze_bytes':protocol['available_RAM_at_freeze'],'max_RSS_bytes':protocol['max_RSS_bytes'],'m10_calibration_median_s':statistics.median(x['candidate_wall'] for x in calibration),'time_limit_factor':10,'max_preprocessing_s':limits['max_preprocessing_seconds']}])
 for sid in range(4401,4407):
  for m in [8,10,12,14,16]:
   for rep in range(3):
    folder=OUT/f'03_component_scaling/runs/scenario_{sid}/m_{m:02d}/repeat_{rep:02d}';mon=js(folder/'parent_monitor.json');ready=js(folder/'ready.json') if (folder/'ready.json').exists() else {}
    successful=mon['completed'];res=js(folder/'result.json') if successful else js(folder/'progress.json') if (folder/'progress.json').exists() else {}
    error=js(folder/'failure.json') if (folder/'failure.json').exists() else {}
    row={'scenario_id':sid,'m':m,'repeat':rep,'status':'PASS' if successful else 'SCALING_FAILURE','failure_reason':mon['resource_stop'] or error.get('reason',''),'last_stage':res.get('stage',mon['observed_stage']),
     'subsets':1<<m,'all_prefix4':math.perm(m,4),'candidate_target':30000,'candidate_count':res.get('candidate_count') if successful else None,'preprocessing_wall':res.get('candidate_wall') if successful else None,'time_right_censored':not successful and mon['resource_stop']=='PREPROCESS_TIME_LIMIT',
     'observed_partial_elapsed':mon['elapsed_since_ready_including_exports'] if not successful else None,'last_progress_elapsed':res.get('elapsed_partial'),'preprocessing_time_limit':limits['max_preprocessing_seconds'],
     'peak_RSS_MiB':mon['peak_online_sampled_RSS_bytes']/2**20,'peak_process_tree_RSS_MiB':mon['peak_process_tree_RSS_bytes']/2**20,'RSS_baseline_MiB':ready.get('RSS_baseline',0)/2**20,'peak_increment_MiB':max(0,mon['peak_online_sampled_RSS_bytes']-ready.get('RSS_baseline',0))/2**20,
     'model_load_wall':ready.get('model_load_wall'),'startup_and_warm_wall':ready.get('imports_input_model_warm_wall'),'policy_calls_completed':res.get('policy_calls',0),'policy_wall_completed':res.get('policy_wall',0),
     'prefix4_visited':res.get('prefix4_visited'),'prefix4_visited_fraction':res.get('prefix_visited_fraction'),'prefix_source_prefix4_unique':res.get('prefix_source_prefix4_unique'),'pool_prefix4_unique':res.get('pool_prefix4_unique'),
     'prefix_tail_registry_attempts':res.get('prefix_tail_attempts'),'inference_batch_size':res.get('inference_batch_size'),'prediction_matrix_bytes':res.get('prediction_matrix_bytes'),'candidate_table_bytes':res.get('candidate_file_bytes'),
     'physical_fixture':m==16,'eligibility_class':'disconnected_feature_fixture_no_UE' if m==16 else 'extended_severity_connected_14','new_UE_calls':0,'workers':1,'CPU_core':0,'compute_threads':1}
    row.update(res.get('components',{}));row['primary_count']=res.get('primary_count');row['reserve_count']=res.get('reserve_count')
    if successful:
     names=['mask_and_restored_state_build_wall','feature_transform_wall','ensemble_forward_wall','initial_policies_wall','prefix_generation_wall','proxy_DP_source_inclusive_wall','diversity_source_wall','random_source_wall','GA_local_source_wall','candidate_evaluation_sort_wall','primary_screening_wall','reserve_and_final_sort_wall']
     row['other_bookkeeping_and_progress_log_wall']=res['candidate_wall']-sum(res['components'][c] for c in names)
     assert row['other_bookkeeping_and_progress_log_wall']>=-1e-6
    records.append(row)
    cold.append({'scenario_id':sid,'m':m,'repeat':rep,'model_load_wall':ready.get('model_load_wall'),'imports_input_model_warm_wall':ready.get('imports_input_model_warm_wall'),'prewarm_wall':ready.get('prewarm_wall'),'scope':'fresh process with existing disk/import caches; excluded from online preparation'})
    if successful:
     assert res['policy_calls']==89,res['policy_calls']
     assert res['source_counts']==protocol['source_quotas']
     assert res['surrogate_shape']==[1<<m,10]
     for p in frame(folder/'DP_policy_timings.csv').to_dict('records'):policies.append({'scenario_id':sid,'m':m,'repeat':rep,**p})
     if (folder/'prefix_sampling_trace.csv.gz').exists():
      tr=frame(folder/'prefix_sampling_trace.csv.gz');prefixes=[list(map(int,x.split('|'))) for x in tr.prefix]
      _,roads,_,_=physical(sid,m)
      for pos in range(4):
       counts=[sum(p[pos]==r for p in prefixes) for r in roads]
       balance.append({'scenario_id':sid,'m':m,'repeat':rep,'position':pos+1,'drawn_prefix_count':len(tr),'min_per_road':min(counts),'max_per_road':max(counts),'max_minus_min':max(counts)-min(counts),'perfect_balance_full_orbit':True,'partial_last_orbit':len(tr)%m!=0,'last_prefix_tails_registered':int(tr.iloc[-1].attempted_tails),'three_tail_constructed_total':3*len(tr)})
 d=pd.DataFrame(records);csv(OUT/'03_component_scaling/S3_component_profile_raw.csv',d);csv(OUT/'03_component_scaling/S3_policy_profile_raw.csv',policies);csv(OUT/'03_component_scaling/S3_prefix_position_balance.csv',balance);csv(OUT/'03_component_scaling/S3_cold_loading.csv',cold)
 scenario=[]
 for (sid,m),g in d.groupby(['scenario_id','m']):
  successes=g[g.status=='PASS'];row={'scenario_id':sid,'m':m,'planned_repeats':3,'completed_repeats':len(successes),'failed_repeats':3-len(successes),'physical_fixture':m==16,'candidate_wall_mean':successes.preprocessing_wall.mean() if len(successes) else None,'candidate_wall_min':successes.preprocessing_wall.min() if len(successes) else None,'candidate_wall_max':successes.preprocessing_wall.max() if len(successes) else None,'sampled_peak_RSS_mean_MiB':g.peak_RSS_MiB.mean(),'sampled_peak_RSS_max_MiB':g.peak_RSS_MiB.max(),'mean_prefix_coverage_fraction':successes.prefix4_visited_fraction.mean() if len(successes) else None}
  for c in ['mask_and_restored_state_build_wall','feature_transform_wall','ensemble_forward_wall','initial_policies_wall','prefix_generation_wall','proxy_DP_source_inclusive_wall','diversity_source_wall','random_source_wall','GA_local_source_wall','candidate_evaluation_sort_wall','primary_screening_wall','reserve_and_final_sort_wall']:
   if c in successes:row[c+'_mean']=successes[c].mean() if len(successes) else None
  scenario.append(row)
 s=pd.DataFrame(scenario);csv(OUT/'05_analysis/S3_scenario_means.csv',s)
 summary=[]
 for m,g in d.groupby('m'):
  sm=s[(s.m==m)&(s.completed_repeats==3)];row={'m':m,'subsets':2**m,'planned_scenarios':6,'planned_runs':18,'completed_runs':int((g.status=='PASS').sum()),'failed_runs':int((g.status!='PASS').sum()),'all_three_repeats_complete_scenarios':len(sm),'candidate_wall_scenario_mean':sm.candidate_wall_mean.mean() if len(sm) else None,'candidate_wall_scenario_min':sm.candidate_wall_mean.min() if len(sm) else None,'candidate_wall_scenario_max':sm.candidate_wall_mean.max() if len(sm) else None,'sampled_peak_RSS_scenario_mean_MiB':s[s.m==m].sampled_peak_RSS_mean_MiB.mean(),'sampled_peak_RSS_max_MiB':g.peak_RSS_MiB.max(),'mean_prefix_coverage_fraction':sm.mean_prefix_coverage_fraction.mean() if len(sm) else None,'preprocessing_limit_s':limits['max_preprocessing_seconds'],'memory_for_incomplete_runs_is_lower_bound':bool((g.status!='PASS').any()),'physical_fixture':m==16}
  row['mean_reserve_count']=g.loc[g.status=='PASS','reserve_count'].mean() if (g.status=='PASS').any() else None
  row['mean_completed_policy_wall']=g.loc[g.status=='PASS','policy_wall_completed'].mean() if (g.status=='PASS').any() else None
  summary.append(row)
 summary=pd.DataFrame(summary);csv(OUT/'03_component_scaling/S3_scaling_summary.csv',summary)
 # Verified call count: initial mean + 10 members, then 10 members + 4 SD + 64 mixtures. The mean is reused, not recomputed.
 cx=frame(OUT/'05_analysis/S1_complexity_table.csv');cx['policy_calls']=89;csv(OUT/'05_analysis/S1_complexity_table.csv',cx)
 (OUT/'05_analysis/S1_complexity_proof.md').write_text('''# 复杂度与实现核对

设恢复道路数 m，成员数 K=10，输入 d=120，候选数 N=30000，唯一 UE 预算 B=256。网络大小固定，C_NN 与 T_UE 分别是成员推理与一次 UE 的成本。

全排列 m! 不等于 UE 求解次数。完整高精度参考最多需要 2^m 个不同状态；单次子集 DP 访问 m·2^(m−1) 个前驱候选，时间 O(m·2^m)，空间 O(2^m)。DP 只对数值评估的状态成本表条件精确，不能作为无限精度 UE 的证明。

全量代理预测时间 O(K·2^m·C_NN)。原状态构建扫描每个 mask 的 m 位，时间 O(m·2^m)；状态字典和38维 restored 数组的存储 O(38·2^m)。原 transform 建立 Python 行列表，再转换为 float32 特征矩阵，额外 O(d·2^m)，会出现临时双份数组。预测矩阵 float64 为 8K·2^m 字节。批次保持整个 2^m，未用分块或按需推理掩盖峰值。

源程序初始 mean + 10 member policies 共11次 DP。proxy 来源重复10 member、4 SD、64混合，共78次新 DP；原 mean 被复用。因此实际共89次 DP。setup 中初始理论表误计为90，最终表依源码及所有完成运行的计数校正为89，运行代码未因此修改。多份 successor 字典同时留存，峰值空间为 O(H·2^m)，H 为同时留存的 policy 数；Python dict 的实际字节远大于紧凑数值数组。

原版全部四路有序前缀 P(m,4)=m(m−1)(m−2)(m−3)，每种三类 tail 的构造尝试为3P(m,4)，完整 tail 遍历还依赖 m。由于全覆盖主循环没有配额上界检查，m增大时原16k来源配额会溢出，固定30k断言无法作为可扩展性证明。补充意见采用固定16k来源和循环轨道均衡抽样，m>10明确是 size-adapted Proposed，四前缀覆盖率随规模下降。其成本不是原全覆盖算法的无改动扩展。

候选生成/缓存/评估至少 O(N·m·K)，候选排序 O(N log N)。原目标缓存包括序列 tuple 和 K 维成员值，实际候选表 O(N·(m+K))。Primary 的 Kendall orientation 有 N·m(m−1)/2 个布尔项，时间/空间含 O(N·m²)；固定选60条并不使前置全池筛选成为常数。结构 reserve 对源/前缀的排序分组仍需遍历候选池。

UE主项 B·T_UE，不包括候选准备和搜索管理。固定前5位 swap/insertion 加相邻交换，邻域数 O(m)，单个邻域的状态/账本处理依赖序列长度；固定B不意味着端到端常数成本。Greedy初始化含R0需 m(m+1)/2 个状态，占预算比例随m增长。

原图24节点38无向物理道路，保持所有节点连通需至少23条道路，故初始关闭最多15条；恢复集合来自初始关闭集合，因此同一物理设定下m≤15。这只是必要上界。m16仅是明确断连的输入特征计算夹具，禁止求UE、报告决策质量或作为原洪水恢复实例。

本批不计算新UE，不计算m12/m14 regret或目标命中。m8组件即使成功也不能推出B256下算法优势，因为256等于全部状态数。第一批结果之后按计划评估第二批S4，不把规划中129024状态写成已算。
''',encoding='utf-8')
 gate={'m10_logic_gate':True,'extended_scenarios_frozen':6,'component_runs_planned':90,'component_runs_completed':int((d.status=='PASS').sum()),'component_runs_failed':int((d.status!='PASS').sum()),'new_UE_solves':0,'S4_executed':False,'S4_pending_stage_assessment':True,'m14_all_component_runs_pass':bool((d[d.m==14].status=='PASS').all()),'no_significance_tests':True,'model_retrained':False,'source_files_unchanged':verify(),'runtime_wrapper_unchanged':completion['implementation_unchanged'],'readiness':'FIRST_BATCH_COMPLETE_SECOND_BATCH_NOT_STARTED','manuscript_word_modified':False}
 dump(OUT/'completion_check.json',gate)
 print(summary.to_string(index=False),flush=True)
if __name__=='__main__':main()
