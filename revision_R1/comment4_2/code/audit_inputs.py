from common42 import *
import zipfile,shutil,re,inspect

def main():
 target=AUD/'source_records/archive';target.mkdir(parents=True,exist_ok=True)
 members=['08_exact_reference_after_method_freeze/subset_ue_costs.csv','08_exact_reference_after_method_freeze/exact_dp_solution.json',
 '08_exact_reference_after_method_freeze/exact_dp_path.csv','08_exact_reference_after_method_freeze/verification_report.json',
 '09_regret_evaluation/method_regret_detailed.csv','09_regret_evaluation/method_objective_independent_recheck.csv',
 'frozen_inputs/final_protocol_v1.1.json','frozen_inputs/final_scenarios.json','frozen_inputs/final_scenarios_physical_links.csv',
 'audit_scripts/week4_day4_calculate_regret.py','frozen_inputs/formal_code/interfaces_week3.py','frozen_inputs/formal_code/run_exact_reference_after_method_freeze.py']
 extracted=[]
 with zipfile.ZipFile(ARCHIVE) as z:
  for suffix in members:
   name=next(n for n in z.namelist() if n.endswith('/'+suffix));b=z.read(name);p=target/Path(suffix).name;p.write_bytes(b)
   extracted.append({'zip_member':name,'member_sha256':hashlib.sha256(b).hexdigest(),'extracted_path':str(p),'same_as_member':sha(p)==hashlib.sha256(b).hexdigest()})
 dump(AUD/'archive_member_provenance.json',extracted)
 shutil.copy2(PLAN,AUD/PLAN.name)
 oldproto=js(target/'final_protocol_v1.1.json');assert oldproto['optimization_scope']['baseline_tstt']==T0
 saved=saved_solutions();metadata=js(target/'final_scenarios.json')
 # Data were read with the original pandas parser in both existing computations.
 a=pd.read_csv(target/'final_scenarios_physical_links.csv').sort_values(['scenario_id','physical_link_id']).reset_index(drop=True)
 b=physical().sort_values(['scenario_id','physical_link_id']).reset_index(drop=True)
 assert a.equals(b),'Archived scenario inputs do not equal high-precision inputs'
 old=old_states();inventory=[]
 for sid in range(1001,1011):
  roads=saved[str(sid)]['candidate_roads'];sm=next(x for x in metadata['scenarios'] if x['scenario_id']==sid)
  assert roads==sm['selected_recoverable_roads']
  ph=b[b.scenario_id==sid].sort_values('physical_link_id');assert len(ph)==38
  assert all(r in set(ph.loc[ph.is_closed==1,'physical_link_id']) for r in roads)
  assert np.all(ph.loc[ph.is_closed==0,'capacity_factor']==1.)
  strict=frame(LEGACY/f'scenario_{sid}/selected_path_precision_validation.csv')
  assert strict.subset_mask.is_unique and strict.strict_relative_gap.le(1e-11).all()
  high=frame(LEGACY/f'scenario_{sid}/all_1024_highprecision_states.csv.gz')
  hs=js(LEGACY/f'scenario_{sid}/exact_solution.json');assert hs['roads']==roads
  for label,d,threshold in [('archived_FW_5e-4',old[old.scenario_id==sid].copy(),5e-4),('path_solver_1e-9',high,1e-9)]:
   assert set(d.subset_mask)==set(range(1024)) and d.subset_mask.is_unique
   assert d.converged.all() and d.relative_gap.le(threshold).all()
   recal=d.tstt/T0-1;assert np.allclose(d.loss,recal,rtol=1e-14,atol=1e-12)
   if label.startswith('archived'):
    for row in d.itertuples(index=False):
     restored=[r for i,r in enumerate(roads) if row.subset_mask&(1<<i)]
     actual=[] if pd.isna(row.restored_links) else list(map(int,re.split(r'[;|]',str(row.restored_links))))
     assert len(restored)==int(row.restored_count) and set(restored)==set(actual)
     restore=np.zeros(38);restore[np.array(restored,dtype=int)-1]=1
     expected=ex.api.get_state_hash(ph.depth_m.to_numpy(),ph.is_closed.to_numpy(),restore)
     assert expected==row.state_hash
   else:
    assert d.tolerance.eq(1e-9).all() and d.solver.eq('path_column_generation_pairwise').all()
   inventory.append({'scenario_id':sid,'precision_tier':label,'state_count':len(d),'missing_masks':0,'duplicate_masks':0,'max_actual_RG':float(d.relative_gap.max()),
      'failed_states':int(sum(~d.converged)),'road_mapping_consistent':True,'scenario_inputs_bitwise_equal_after_original_parser':True,
      'baseline_TSTT':T0,'baseline_normalization_consistent':True})
  ref=high.set_index('subset_mask')
  assert all(float(ref.loc[int(r.subset_mask),'tstt']).hex()==float(r.tstt_1e9).hex() for r in strict.itertuples(index=False))
  inventory.append({'scenario_id':sid,'precision_tier':'archived_selected_paths_1e-11','state_count':len(strict),'missing_masks':None,'duplicate_masks':0,
      'max_actual_RG':float(strict.strict_relative_gap.max()),'failed_states':0,'road_mapping_consistent':True,'baseline_TSTT':T0,
      'baseline_normalization_consistent':True,'iterations_available':False,'failed_states_note':'Only retained converged results; execution failure/retry history was not archived'})
 csv(AUD/'S0_data_inventory.csv',inventory)
 # File manifest covers actually used source data/code, never cached conclusions.
 sources=[(ARCHIVE,'original 10-state-table archive'),(PLAN,'user supplied implementation plan'),(BASE/'inputs/historical_1001_1010.csv','historical physical inputs'),
 (FORMAL/'protocol/frozen_protocol.json','frozen empirical equivalence rule'),(FORMAL/'analysis/selected_objective_precision_stability.csv','new30 saved path objectives'),
 (FORMAL/'analysis/all_run_results.csv','new30 frozen algorithm records')]
 sources += [(p,'original archive extracted source') for p in target.iterdir()]
 sources += [(p,'legacy precision raw source') for p in LEGACY.glob('scenario_*/*') if p.is_file()]
 sources += [(p,'fixed original poststudy SA record') for p in (PUB/'results/poststudy_permutation_SA/final_once_only').rglob('*') if p.is_file()]
 sources += [(BASE/'code'/n,'high-precision solver or generation implementation') for n in ['ue_solver.py','path_ue.py','experiment.py','legacy_precision.py']]
 sources += [(p,'frozen network, OD, BPR input') for p in (ex.MODEL/'data_src/SiouxFalls_flood_benchmark/processed').glob('*.csv')]
 sources += [(ex.MODEL/'models/ue_static.py','original FW implementation'),(ex.MODEL/'models/flood_scenario.py','original state mapping implementation')] if (ex.MODEL/'models/flood_scenario.py').exists() else [(ex.MODEL/'models/ue_static.py','original FW implementation')]
 for sid in range(3001,3031):
  sources += [(FORMAL/f'exact/scenario_{sid}'/n,'new30 numerical raw evidence') for n in ['all_1024_states.csv.gz','selected_path_stability.csv','exact_solution.json']]
  sources += [(FORMAL/f'analysis_round2/S2_timing_raw/serial/scenario_{sid}/all_fresh_1024_states.csv.gz','independent fresh high-precision repeat')]
 sources += [(p,'new30 fixed method path') for p in (FORMAL/'runs/query_cap').glob('scenario_*/*/rep_*/result.json')]
 records=[];seen=set()
 for path,role in sources:
  if str(path) in seen:continue
  seen.add(str(path));st=path.stat()
  relative=os.path.relpath(path,OUT) if path.drive.lower()==OUT.drive.lower() else path.as_posix()
  records.append({'relative_path':relative,'absolute_path':str(path),'bytes':st.st_size,'sha256':sha(path),'data_role':role,
       'filesystem_mtime_local':datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),'version_date_note':'Filesystem time is provenance only, not experiment date'})
 csv(AUD/'S0_input_manifest.csv',records)
 dump(AUD/'execution_protocol.json',{'created_date_Asia_Shanghai':'2026-10-28','main_scenarios':list(range(1001,1011)),'supporting_scenarios':list(range(3001,3031)),
   'path_policy':'Original Proposed B256 and original single-seed SA only; no optimization/retraining or new flood generation',
   'baseline':T0,'old_RG':5e-4,'new_RG':1e-9,'refined_RG':1e-11,'kappa':KAPPA,'equivalence_rule':PROTOCOL['equivalence']['equivalence_rule'],
   'dp_tie_rule':'strict floating objective first, then full sequence lexicographic physical-road IDs; original published sequence separately retained',
   'selected_refinement_policy':'Reuse all existing strict states. Inspect all paths within frozen empirical objective epsilon of the 1e-9 DP using exact combinatorial traversal; refine missing states in that union plus frozen methods, old/new references and second-best path. Escalate to full table if materially different refined ordering or hit classification is unresolved. Empirical bands are not error certificates.',
   'solver_comparison':'Archived FW vs path-column solver changes both numerical implementation and tolerance. Explicitly report this confounding. No claim of a tolerance-only archived comparison; 1e-9 vs 1e-11 uses same solver.',
   'old_state_hash_semantics':'SHA256 of concatenated round(depth,9) and restored 38-vector float64; does not encode tolerance, closed flags, solver, OD or baseline. Those inputs are checked separately.',
   'existing_strict_metadata_limit':'Strict selected-state CSVs contain TSTT and actual RG but not iterations, timing or retry history; retain these as unavailable, do not invent or rerun only to fill metadata.',
   'new_UE_allowed':'Only missing high-precision states or missing/ambiguous critical competitive states; save complete new call metadata',
   'archive_policy':'Numeric results only, per user standing instruction'})
 (AUD/'S0_gap_report.md').write_text('''# S0 数据缺口核查

G0 通过。原十情景的旧 FW 状态表共 10,240 行，真正的 1e-9 高精度状态表共 10,240 行，mask、物理场景、道路映射与干网基准已逐项核对。旧表 SHA 与压缩包成员一致，未将其冒称高精度表。

已有 1e-11 关键路径 CSV 全部存在，实际 RG 可核验，但迭代数、求解用时和曾经的失败/重试历史未保存。这些字段将明确留空，不能把“保存成功结果中失败为零”写成“从未发生求解失败”。对新补算则保存完整元数据。

旧表使用 FW，新表使用 path-column-generation/pairwise 求解器。物理状态、静态 BPR/OD/基准均不变，但数值算法和停止设置不同，旧/新差值不被描述为仅收敛阈值的因果效应。同一求解器的 1e-9/1e-11 检查另列。

旧 state_hash 不包含全部求解设置，已另外检查真实场景、mask道路映射、归一化和原始网络/OD。S0_input_manifest.csv 保存来源文件 SHA；文件修改时间仅供追溯，不代替实验日期。
''',encoding='utf-8')
 dump(AUD/'G0_acceptance.json',{'status':'PASS','legacy_old_states':10240,'legacy_new_states':10240,'strict_selected_states':sum(x['state_count'] for x in inventory if x['precision_tier']=='archived_selected_paths_1e-11'),
    'source_manifest_files':len(records),'physical_inputs_equal':True,'solver_implementation_changed_and_disclosed':True,'missing_strict_iteration_and_retry_metadata_disclosed':True})
 print('G0 PASS',len(records),'source files; existing strict states',sum(x['state_count'] for x in inventory if x['precision_tier']=='archived_selected_paths_1e-11'),flush=True)

if __name__=='__main__':main()
