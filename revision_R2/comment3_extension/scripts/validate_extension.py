from common import *
import sqlite3
def main():
 init();checks=[]
 def ck(name,ok,actual=None,expected=None):checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 snapshot=js(OUT/'audit/source_sha256.json');pres=[]
 for i,r in enumerate(snapshot['files']):
  p=Path(r['path']);after=sha(p) if p.is_file() else 'MISSING';pres.append(dict(path=str(p),before_sha256=r['sha256'],after_sha256=after,unchanged=after==r['sha256']))
  if i%10000==0:print('Old-source verification',i,'/',len(snapshot['files']),flush=True)
 save(OUT/'audit/source_preservation.csv',pres);ck('all_old_sources_unchanged',all(r['unchanged'] for r in pres),sum(r['unchanged'] for r in pres),len(pres));ck('Git_HEAD_branch_unchanged',gitstate()==snapshot['git'],gitstate(),snapshot['git'])
 ck('parent_still_PASS',js(PARENT/'final_validation.json')['status']=='PASS')
 authority=js(OUT/'audit/accepted_parent_critical_binding.json');ck('parent32_critical_source_identities',len(authority)==32 and all(r['unchanged'] and sha(r['path'])==r['accepted_sha256'] for r in authority))
 for r in read(PARENT/'output_manifest.csv').itertuples():ck('parent_preserved_'+r.path,sha(PARENT/r.path)==r.sha256)
 man=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json');ck('prospective_manifest_unchanged',sha(OUT/'run_manifest.json')==freeze['run_manifest_sha256'])
 for name,key in [('raw/logical_state_mapping.csv','logical_mapping_sha256'),('raw/unique_state_requests.csv','unique_requests_sha256'),('raw/variant_physical_fields.csv','physical_fields_sha256')]:ck(key,sha(OUT/name)==man[key])
 for r in man['frozen_scripts']:ck('frozen_script_'+Path(r['path']).name,sha(r['path'])==r['sha256'])
 ck('fixed_design',man['scenario_ids']==list(range(1001,1011)) and man['depth_multipliers']==[.9,.95] and man['RG']==1e-9 and man['max_outer']==20000 and man['T0_raw']==T0 and man['Q']==Q)
 ck('input_preflight_PASS',js(OUT/'audit/input_validation.json')['status']=='PASS')
 re=read(OUT/'audit/R2C3_reuse_identity_checks.csv');ck('parent3_3072_complete_identity',len(re)==3072 and re.full_context_and_cost_match.all(),int(re.full_context_and_cost_match.sum()),3072)
 ue=read(OUT/'raw/new_UE_query_log.csv');ck('17_new_tables_complete',len(ue)==17408==man['new_unique_states'],len(ue),17408);ck('within_budget',len(ue)<=18500,len(ue),18500);ck('new_UE_keys_unique',ue.state_key.nunique()==len(ue));ck('all_new_RG',ue.ue_gap.le(TARGET).all(),float(ue.ue_gap.max()),TARGET);ck('all_new_independent_AON',ue.independent_AON_RG.le(TARGET*(1+1e-6)).all(),float(ue.independent_AON_RG.max()),TARGET);ck('independent_Dijkstra_samples',ue.independent_Dijkstra_RG.notna().sum()>=170 and ue.independent_Dijkstra_RG.dropna().le(TARGET*(1+1e-6)).all(),int(ue.independent_Dijkstra_RG.notna().sum()),'>=170');ck('new_conservation',ue.flow_balance_max_abs.le(1e-5).all(),float(ue.flow_balance_max_abs.max()),1e-5);ck('new_finite_valid',ue.validation_passed.all() and np.isfinite(ue.tstt_raw).all());ck('actual_first_UE_after_freeze',pd.to_datetime(ue.timestamp_utc,format='ISO8601').min()>=pd.to_datetime(man['created_utc']));ck('UE_minutes_unit',np.allclose(ue.ATT_min,.6*ue.tstt_raw/Q,rtol=1e-14,atol=1e-12));ck('UE_veh_h_unit',np.allclose(ue.TSTT_veh_h,.01*ue.tstt_raw,rtol=1e-14,atol=1e-12));ck('ATT0_protocol_constant',ATT0==12.446298410850448,ATT0,12.446298410850448)
 con=sqlite3.connect(f'file:{(OUT/"cache/depth_extension_states.sqlite3").as_posix()}?mode=ro',uri=True);ck('new_SQLite_integrity',con.execute('PRAGMA integrity_check').fetchone()[0]=='ok');lengths=con.execute('SELECT COUNT(*),MIN(length(flow)),MAX(length(flow)) FROM states').fetchone();con.close();ck('all_new_flow_vectors_saved',lengths==(17408,608,608),list(lengths),[17408,608,608])
 raw=read(OUT/'raw/UE_all_logical_states.csv');dp=read(OUT/'raw/DP_all_states.csv');paths=read(OUT/'raw/DP_paths.csv');table=read(OUT/'Table_R2C3_all10_depth_DP.csv');ind=read(OUT/'audit/independent_DP_checks.csv');small=read(OUT/'tests/small_DP_checks.csv');E0=originals();refs=js(R42/'01_legacy_ue_state_comparison/independent_references.json')
 exported=list((OUT/'raw/state_tables').glob('*_1024_states.csv'));ck('per_condition_cost_table_files',len(exported)==30 and all(len(read(p))==1024 for p in exported),len(exported),30)
 ck('30_rows_20perturbed_10baseline',len(table)==30 and table[table.rho_depth.ne(1)].shape[0]==20 and set(table.scenario_id)==set(range(1001,1011)))
 ck('all_DP_check_tolerances',len(ind)==30 and ind.max_error.le(1e-12).all() and ind.pass_.all(),float(ind.max_error.max()),1e-12);ck('small_exhaustive_sentinel_shift_kbest',len(small)==34 and small.pass_.all(),int(small.pass_.sum()),34)
 for row in table.itertuples():
  vid=row.variant_id;E=json.loads(row.road_bit_order);seq=json.loads(row.optimal_sequence);oldseq=refs[str(row.scenario_id)]['seq_new'];g=raw[raw.variant_id.eq(vid)].sort_values('subset_mask');state=dp[dp.variant_id.eq(vid)].sort_values('subset_mask');traj=paths[paths.variant_id.eq(vid)].sort_values('stage')
  ck(vid+'_complete1024_and_E',g.subset_mask.tolist()==list(range(1024)) and E==E0[row.scenario_id] and set(seq)==set(E));c=g.loss.to_numpy(float);j=pathvalue(seq,E,c);jt=pathvalue(oldseq,E,c);ck(vid+'_explicit_J',abs(j-row.Jstar)<=1e-12,j,float(row.Jstar));ck(vid+'_transfer_J',abs(jt-row.J_transfer_original_DP)<=1e-12);ck(vid+'_regret_positive_denominator',row.Jstar>0 and row.transfer_regret_pct>=-1e-12 and abs(100*(jt-row.Jstar)/row.Jstar-row.transfer_regret_pct)<=1e-12);ck(vid+'_delta_minutes',abs(ATT0*(jt-row.Jstar)-row.transfer_delta_ATT_min)<=1e-9);ck(vid+'_mean_ATT_two_paths',abs(float(np.dot(traj.ATT_min,traj.weight))-row.mean_stage_ATT_min)<=1e-9 and abs(ATT0*(1+row.Jstar)-row.mean_stage_ATT_min)<=1e-9)
  ck(vid+'_S10_zero_weight',traj.loc[traj.stage.eq(10),'weight'].iloc[0]==0. and traj.loc[traj.stage.lt(10),'weight'].sum()==1.)
  ck(vid+'_near_tie_diagnostic_only',row.near_tie_threshold==1e-12*max(1.,abs(row.Jstar)) and row.second_best_gap>=-1e-12)
  ck(vid+'_DP_cost_mapping',g.state_key.tolist()==state.state_key.tolist() and np.array_equal(g.tstt_raw,state.tstt_raw))
 stats=read(OUT/'Table_R2C3_depth_summary.csv')
 for rho in [.9,.95]:
  sub=table[table.rho_depth.eq(rho)];r=stats[stats.rho_depth.eq(rho)].iloc[0]
  for col in ['full_sequence_changed','first_road_changed','first3_order_changed','first3_set_changed']:ck(f'{rho}_summary_{col}',int(sub[col].sum())==int(r[col+'_count']))
  for metric in ['Jstar','mean_stage_ATT_min','Jstar_change_from_original','ATT_change_from_original_min','Kendall_tau','transfer_regret_pct','transfer_delta_ATT_min']:
   a=sub[metric].to_numpy();values=dict(mean=a.mean(),median=np.median(a),P90=np.quantile(a,.9,method='linear'),maximum=a.max(),minimum=a.min());ck(f'{rho}_summary_{metric}',all(abs(float(r[metric+'_'+label])-float(v))<=1e-12 for label,v in values.items()))
 threshold=read(OUT/'Table_R2C3_threshold_invariance.csv');glob=read(OUT/'Table_R2C3_threshold_global_intersection.csv').iloc[0];physical=read(PHYS);tqa=js(OUT/'audit/threshold_invariance_validation.json');tt=read(OUT/'raw/threshold_boundary_tests.csv');tc=read(OUT/'raw/threshold_all1024_input_comparisons.csv')
 globalqa=js(OUT/'audit/global_threshold_validation.json');gt=read(OUT/'raw/global_threshold_boundary_tests.csv');ck('global40_zero_UE_boundary_checks',globalqa['new_UE_calls']==0 and len(gt)==40 and gt.pass_.all(),int(gt.pass_.sum()),40)
 ck('TaskB_zero_UE',tqa['new_UE_calls']==0 and man['threshold_task_new_UE']==0 and ue.variant_id.str.contains('_depth_').all());ck('80_boundary_tests',len(tt)==80 and tt.pass_.all(),int(tt.pass_.sum()),80);ck('51200_input_comparisons',len(tc)==50 and tc.all_inputs_equal.all() and tc.states_compared.sum()==51200,int(tc.states_compared.sum()),51200)
 for row in threshold.itertuples():
  p=physical[physical.scenario_id.eq(row.scenario_id)];L=float(p.loc[p.is_closed.eq(0),'depth_m'].max());U=float(p.loc[p.is_closed.eq(1),'depth_m'].min());ck(f'{row.scenario_id}_analytic_threshold_extrema',L==row.h_open_max_m and U==row.h_closed_min_m and row.lower_open and row.upper_closed)
  q=tt[tt.scenario_id.eq(row.scenario_id)].set_index('test');ck(f'{row.scenario_id}_strict_open_closed_endpoints',not q.loc['lower_excluded','mask_equal'] and q.loc['lower_nextafter_inside','mask_equal'] and q.loc['upper_included','mask_equal'] and not q.loc['above_upper_nextafter','mask_equal'])
 ck('global_intersection_exact',float(threshold.h_open_max_m.max())==glob.h_open_max_global_m and float(threshold.h_closed_min_m.min())==glob.h_closed_min_global_m and glob.lower_open and glob.upper_closed)
 figqa=js(OUT/'audit/figure_automated_QA.json');ck('figures_automatic',all(r['returncode']==0 for r in figqa));visual=js(OUT/'audit/figure_visual_review.json');ck('figures_actual_visual_review',visual['status']=='PASS' and all(sha(r['path'])==r['sha256'] for r in visual['files']))
 for name in ['Comment_R2_3_extension_results_CN.md','Response_R2_Comment3_extension_draft_EN.md','Manuscript_R2C3_extension_insertions_EN.md','README_文件索引.md']:ck(name+'_exists',(OUT/name).is_file())
 for name in ['Response_R2_Comment3_extension_draft_EN.md','Manuscript_R2C3_extension_insertions_EN.md']:
  text=(OUT/name).read_text(encoding='utf-8');ck(name+'_proposed_not_merged','PAGE/LINE TO BE FINALIZED' in text and 'We have revised' not in text and 'Reviewer 1' not in text)
 allok=all(c['status']=='PASS' for c in checks);status='PASS' if allok else 'PARTIAL'
 final=dict(status=status,scope='All10 paired depth reduction DP and exact threshold-input invariance; not real-flood validation',checks_passed=sum(c['status']=='PASS' for c in checks),checks_total=len(checks),old_source_files_checked=len(pres),old_source_files_unchanged=sum(r['unchanged'] for r in pres),parent_R2C3_unchanged=all(r['unchanged'] for r in pres if str(PARENT) in r['path']),new_UE_states=len(ue),new_tables=17,parent_tables_reused=3,perturbed_tables=20,baseline_tables=10,TaskB_new_UE=0,original_Full_or_baseline_search_reruns=0,surrogate_training=0,new_flood_scenarios=0,main_manuscript_modified=False,main_integration='PENDING',checks=checks)
 dump(OUT/'final_validation.json',final)
 (OUT/'QA_validation.md').write_text(f"# 最终验收\n\n状态 **{status}**，{final['checks_passed']}/{len(checks)}项通过。\n\n原来源{len(pres)}项前后SHA核对；父R2C3只读保护。17张新表17408状态、3张原0.95表复用；20扰动表及10基准表完整DP。阈值任务0 UE、80边界映射测试、51200个恢复状态输入比较。两张新图已PDF/SVG/600dpi导出并逐图目检。\n\nPASS仅指授权实验与QA，不指现实洪灾或动态交通已验证。主稿/最终图号/页行号未合并。详情见final_validation.json与audit目录。\n",encoding='utf-8')
 print(status,final['checks_passed'],'/',len(checks),flush=True)
if __name__=='__main__':main()
