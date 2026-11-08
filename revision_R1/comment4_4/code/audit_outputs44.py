from common44 import *
def main():
 assert js(OUT/'logs/component_batch_completion.json')['tasks']==90
 cfg=js(OUT/'00_lock/frozen_scaling_protocol.json');rows=[]
 for folder in sorted((OUT/'03_component_scaling/runs').glob('scenario_*/m_*/repeat_*')):
  mon=js(folder/'parent_monitor.json')
  if not mon['completed']:continue
  r=js(folder/'result.json');pool=frame(folder/'candidate_pool.csv.gz');screen=frame(folder/'screened_candidates.csv.gz');sid=r['scenario_id'];m=r['m']
  ph,roads,_,fixture=physical(sid,m);sequences=[tuple(map(int,s.split('|'))) for s in pool.sequence]
  result={'scenario_id':sid,'m':m,'repeat':r['replicate'],'exact_30000':len(pool)==30000,'all_unique_sequences':len(set(sequences))==30000,'all_unique_ids':pool.candidate_id.nunique()==30000,'permutations_of_frozen_roads':all(len(s)==m and set(s)==set(roads) for s in sequences),'source_quota_equal':dict(pool.primary_source.value_counts())==cfg['source_quotas'],'candidate_ids_correct':all(cid==hashlib.sha256(f"{sid}|{'|'.join(map(str,s))}".encode()).hexdigest() for cid,s in zip(pool.candidate_id,sequences)),
   'candidate_order_SHA_equal':hashlib.sha256('\n'.join(pool.candidate_id).encode()).hexdigest()==r['candidate_order_sha256'],'rank_sort_correct':pool.candidate_id.tolist()==pool.sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').candidate_id.tolist(),'rank_numbers_correct':pool.proxy_rank.tolist()==list(range(1,30001)),
   'finite_proxy_values':bool(np.isfinite(pool[['proxy_objective_mean','ensemble_disagreement']+[f'member_{k:02d}_objective' for k in range(1,11)]].to_numpy()).all()),'primary_60':int((screen.screening_tier=='primary_shortlist').sum())==60,'screen_ids_unique':screen.candidate_id.nunique()==len(screen),'screen_subset_of_pool':set(screen.candidate_id)<=set(pool.candidate_id),'all_10_reserve_prefix2_groups':set(screen[screen.screening_tier=='structural_reserve'].prefix_2_cluster_rank.dropna().astype(int))==set(range(1,11)),
   '89_policies':r['policy_calls']==89,'correct_prediction_shape':r['surrogate_shape']==[2**m,10],'zero_new_UE':r['new_UE_calls']==0,'correct_fixture_label':r['feature_only_fixture']==(m==16),'CPU_0_one_thread':js(folder/'ready.json')['core']==0 and js(folder/'ready.json')['threads']==1}
  if m>10:
   tr=frame(folder/'prefix_sampling_trace.csv.gz');prefixes=[tuple(map(int,p.split('|'))) for p in tr.prefix];balanced=True
   for pos in range(4):
    counts=[sum(p[pos]==road for p in prefixes) for road in roads];balanced &= max(counts)-min(counts)<=1
   result.update({'prefix_position_counts_differ_at_most_one':balanced,'prefix_draws_unique':len(set(prefixes))==len(prefixes),'prefix_draws_valid':all(len(set(p))==4 and set(p)<=set(roads) for p in prefixes),'prefix_trace_counts_match':len(tr)==r['prefix4_visited']})
  else:result['exhaustive_prefix4_coverage']=r['prefix4_visited']==__import__('math').perm(m,4)
  result['all_pass']=all(v for k,v in result.items() if k not in ['scenario_id','m','repeat'])
  rows.append(result);assert result['all_pass'],result
 csv(OUT/'01_code_audit/S3_independent_output_audit.csv',rows)
 reg=frame(OUT/'01_code_audit/S0_m10_regression_gate.csv');assert len(reg)==12 and reg.all_pass.all()
 for p,h in js(OUT/'00_lock/frozen_component_implementation.json')['sha256'].items():assert sha(p)==h
 scenarios=frame(OUT/'02_scenarios/extended_severity_physical.csv')
 assert set(scenarios.scenario_id)==set(range(4401,4407))
 for sid,ph in scenarios.groupby('scenario_id'):
  assert len(ph)==38 and ph.is_closed.sum()==14 and connected(ph)
  ranked,_=select_roads(ph,14)
  for m in [8,10,12,14]:assert select_roads(ph,m)[0]==ranked[:m]
 acceptance={'status':'PASS','all_successful_pools_audited':len(rows),'all_90_tasks_retained':len(list((OUT/'03_component_scaling/runs').glob('scenario_*/m_*/repeat_*')))==90,'all_m10_regressions':12,'source_files_unchanged':verify(),'frozen_runtime_unchanged':True,'same_14_closed_network_for_nested_physical_m':True,'m16_only_feature_fixture':True,'no_UE_in_S3':True,'independent_audit_finished':now()}
 dump(OUT/'01_code_audit/final_output_acceptance.json',acceptance);print(json.dumps(acceptance),flush=True)
if __name__=='__main__':main()
