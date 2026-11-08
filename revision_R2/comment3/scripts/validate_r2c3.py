from common import *
import sqlite3
def main():
 init();checks=[]
 def ck(name,ok,actual=None,expected=None):checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 source=js(OUT/'audit/source_sha256.json');pres=[]
 for i,r in enumerate(source['files']):
  p=Path(r['path']);actual=sha(p) if p.exists() else 'MISSING';pres.append(dict(path=str(p),before_sha256=r['sha256'],after_sha256=actual,unchanged=actual==r['sha256']))
  if i%10000==0:print('Source verification',i,'/',len(source['files']),flush=True)
 save(OUT/'audit/source_preservation.csv',pres);ck('all_old_sources_unchanged',all(r['unchanged'] for r in pres),sum(r['unchanged'] for r in pres),len(pres));ck('old_Git_HEAD_and_branch',gitstate()==source['git'],gitstate(),source['git'])
 man=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json');ck('manifest_not_changed',sha(OUT/'run_manifest.json')==freeze['run_manifest_sha256'],sha(OUT/'run_manifest.json'),freeze['run_manifest_sha256']);ck('first_new_UE_after_manifest_freeze',freeze['new_UE_calls_before_freeze']==0,freeze['new_UE_calls_before_freeze'],0)
 for p,key in [('raw/unique_state_requests.csv','unique_requests_sha256'),('raw/logical_state_mapping.csv','logical_mapping_sha256'),('raw/variant_physical_fields.csv','physical_fields_sha256')]:ck('frozen_'+key,sha(OUT/p)==man[key],sha(OUT/p),man[key])
 for r in man['frozen_scripts']:ck('frozen_script_'+Path(r['path']).name,sha(r['path'])==r['sha256'],sha(r['path']),r['sha256'])
 ck('original_4.2_input_audit',js(OUT/'audit/input_validation.json')['status']=='PASS');rep=read(OUT/'audit/CRN_baseline_replay.csv');ck('all_12_CRN_draws_verified',len(rep)==12 and rep.pass_.all(),int(rep.pass_.sum()),12);ck('ten_accepted_replayed',rep.scenario_id.notna().sum()==10,int(rep.scenario_id.notna().sum()),10)
 authority=read(R42/'00_protocol_and_input_audit/S0_input_manifest.csv');binding=[]
 for name in ['ue_solver.py','path_ue.py']:
  r=authority[authority.absolute_path.str.endswith('\\'+name)].iloc[0];actual=sha(BASE/'code'/name);binding.append(dict(path=str(BASE/'code'/name),accepted_4_2_sha256=r.sha256,current_sha256=actual,unchanged=actual==r.sha256));ck('accepted_4.2_solver_'+name,actual==r.sha256,actual,r.sha256)
 dump(OUT/'audit/solver_authority_binding.json',binding)
 f=read(OUT/'Table_R2C3_all10_feasibility.csv');ck('all10_all11_conditions',len(f)==110 and all(len(g)==11 for _,g in f.groupby('scenario_id')),len(f),110);ck('representatives_fixed',man['representatives']==[1006,1003,1008],man['representatives'],[1006,1003,1008]);ck('new_UE_budget',man['new_unique_states']<=13000,man['new_unique_states'],13000)
 netdir=NETROOT/'data_src/SiouxFalls_flood_benchmark/processed';links=read(netdir/'directed_links.csv');od=read(netdir/'od_long.csv')
 ck('computed_network_size',len(links)==76 and links.physical_link_id.nunique()==38,[len(links),links.physical_link_id.nunique()],[76,38])
 ck('computed_OD_demand_and_count',float(od.demand.sum())==Q and int(od.demand.gt(0).sum())==528,[float(od.demand.sum()),int(od.demand.gt(0).sum())],[Q,528])
 ck('computed_original_BPR_constants',links.bpr_alpha.eq(.15).all() and links.bpr_beta.eq(4).all())
 baseline=read(OUT/'audit/baseline_recomputed.csv').sort_values('J_star').scenario_id.tolist();ck('representative_original_objective_ranks',[baseline[0],baseline[4],baseline[-1]]==[1006,1003,1008],[baseline[0],baseline[4],baseline[-1]],[1006,1003,1008])
 fields=read(OUT/'raw/variant_physical_fields.csv');ck('every_variant_38_physical_IDs',all(g.sort_values('physical_link_id').physical_link_id.tolist()==list(range(1,39)) for _,g in fields.groupby('variant_id')))
 portfolio_checks=[]
 for plan in man['table_plan']:
  if not plan['n_logical_states']:continue
  p=fields[fields.variant_id.eq(plan['variant_id'])];E=plan['road_bit_order'];portfolio_checks.append(len(E)==10 and len(set(E))==10 and set(E)<=set(p.loc[p.is_closed.eq(1),'physical_link_id']))
 ck('all_requested_portfolios_legal',all(portfolio_checks),sum(portfolio_checks),len(portfolio_checks))
 ue=read(OUT/'raw/new_UE_query_log.csv');exe=js(OUT/'audit/UE_execution_validation.json');ck('new_states_complete',len(ue)==man['new_unique_states'] and ue.state_key.nunique()==len(ue),len(ue),man['new_unique_states']);ck('UE_all_RG',ue.ue_gap.le(TARGET).all(),float(ue.ue_gap.max()),TARGET);ck('independent_AON_all',ue.independent_AON_RG.le(TARGET*(1+1e-6)).all(),float(ue.independent_AON_RG.max()),TARGET);ck('independent_Dijkstra_sample',ue.independent_Dijkstra_RG.dropna().le(TARGET*(1+1e-6)).all(),int(ue.independent_Dijkstra_RG.notna().sum()),'>=1');ck('UE_conservation',ue.flow_balance_max_abs.le(1e-5).all(),float(ue.flow_balance_max_abs.max()),1e-5);ck('UE_finiteness_and_validation',ue.validation_passed.all() and np.isfinite(ue.tstt_raw).all());ck('units_raw_to_veh_h',np.allclose(ue.TSTT_veh_h,.01*ue.tstt_raw,rtol=1e-14,atol=1e-12));ck('units_ATT_min',np.allclose(ue.ATT_min,.6*ue.tstt_raw/Q,rtol=1e-14,atol=1e-12))
 ck('actual_UE_timestamp_after_prospective_freeze',pd.to_datetime(ue.timestamp_utc).min()>=pd.to_datetime(man['created_utc']),str(pd.to_datetime(ue.timestamp_utc).min()),man['created_utc'])
 dpc=read(OUT/'audit/independent_DP_checks.csv');small=read(OUT/'tests/small_DP_exhaustive_and_sentinel.csv');ck('24_complete_DP_tables',len(dpc)==man['valid_tables'] and dpc.pass_.all(),len(dpc),man['valid_tables']);ck('independent_DP_tolerance',dpc.max_error.le(1e-12).all(),float(dpc.max_error.max()),1e-12);ck('m1_to7_enumeration_and_sentinel',len(small)==28 and small.pass_.all(),int(small.pass_.sum()),28)
 states=read(OUT/'raw/DP_all_states.csv');tr=read(OUT/'raw/DP_optimal_trajectories.csv');transfer=read(OUT/'Table_R2C3_policy_transfer.csv');summ=read(OUT/'Table_R2C3_conditional_DP.csv');plans={r['variant_id']:r for r in man['table_plan']}
 mapping=read(OUT/'raw/logical_state_mapping.csv');costs=read(OUT/'raw/all_unique_state_costs.csv').set_index('state_key');newkeys=set(ue.state_key)
 for vid,g in states.groupby('variant_id'):
  ck(vid+'_1024_masks',len(g)==1024 and sorted(g.subset_mask)==list(range(1024)),len(g),1024)
  p=tr[tr.variant_id.eq(vid)];s=summ[summ.variant_id.eq(vid)].iloc[0];ck(vid+'_terminal_zero_weight',p.loc[p.stage.eq(10),'weight'].iloc[0]==0. and p.loc[p.stage.lt(10),'weight'].sum()==1.)
  j=float(np.dot(p.loss,p.weight));ck(vid+'_explicit_objective',abs(j-s.J_star)<=1e-12,j,float(s.J_star))
  mapped=mapping[mapping.variant_id.eq(vid)].sort_values('subset_mask');g=g.sort_values('subset_mask');ck(vid+'_state_key_and_cost',g.state_key.tolist()==mapped.state_key.tolist() and np.allclose(g.tstt_raw,[costs.loc[k,'tstt_raw'] for k in mapped.state_key],rtol=0,atol=0))
  ck(vid+'_mean_stage_units',abs(.6*T0*(1+s.J_star)/Q-s.mean_stage_ATT_min)<=1e-9)
 for row in transfer.itertuples():
  comparable=row.status=='COMPARABLE_SAME_E'
  if not comparable:ck(row.variant_id+'_no_false_regret',pd.isna(row.transfer_regret_pct) and pd.isna(row.complete_Kendall_tau))
  else:ck(row.variant_id+'_nonnegative_transfer',row.transfer_regret_pct>=-1e-12)
 bad=f[~f.validity_status.eq('VALID')];ck('invalid_conditions_not_solved',not set(bad.variant_id)&set(summ.variant_id),len(bad),0)
 requests=read(OUT/'raw/unique_state_requests.csv');ck('cache_matches_only_new_namespace',newkeys==set(requests.loc[requests.source.eq('new_UE'),'state_key']))
 ck('103_independent_samples',exe['independent_Dijkstra_samples']>=100,exe['independent_Dijkstra_samples'],'>=100')
 con=sqlite3.connect(f'file:{(OUT/"cache/sensitivity_states.sqlite3").as_posix()}?mode=ro',uri=True);ck('SQLite_integrity',con.execute('PRAGMA integrity_check').fetchone()[0]=='ok');con.close()
 figqa=js(OUT/'audit/figure_automated_QA.json');ck('figure_automated_QA',all(r['returncode']==0 for r in figqa),figqa,0)
 visual=js(OUT/'audit/figure_visual_review.json') if (OUT/'audit/figure_visual_review.json').exists() else {'status':'PENDING'};ck('figures_actual_visual_QA',visual['status']=='PASS',visual['status'],'PASS')
 if visual['status']=='PASS':
  ck('visual_QA_binds_final_figure_files',all(sha(r['path'])==r['sha256'] for r in visual['files']))
 required=['Response_R2_Comment3_draft_EN.md','Manuscript_insertions_R2_Comment3_EN.md','Comment_R2_3_results_report_CN.md','README_文件索引.md'];ck('requested_reports_present',all((OUT/p).is_file() for p in required),required,True)
 for name in required[:2]:
  text=(OUT/name).read_text(encoding='utf-8') if (OUT/name).exists() else '';ck(name+'_no_false_master_completion','We have revised' not in text and 'PROPOSED INSERTION' in text);ck(name+'_reviewer_isolation','Reviewer 1' not in text and 'Comment 5.' not in text)
 passed=all(r['status']=='PASS' for r in checks);status='PASS' if passed else 'PARTIAL'
 final=dict(status=status,scope='Authorized conditional flood-input sensitivity and QA only',checks_passed=sum(r['status']=='PASS' for r in checks),checks_total=len(checks),old_source_files_checked=len(pres),old_sources_unchanged=all(r['unchanged'] for r in pres),all_preflight_conditions=110,valid_conditions=int(f.validity_status.eq('VALID').sum()),infeasible_conditions=int((~f.validity_status.eq('VALID')).sum()),unique_new_UE=len(ue),reused_unique_4_2=man['reused_unique_states'],complete_logical_tables=len(dpc),representative_invalid_tables=man['invalid_tables'],no_flood_evolution_or_disconnected_UE_capability_claim=True,no_significance_claim=True,original_Full_reruns=0,surrogate_training=0,main_manuscript_modified=False,main_integration='PENDING',checks=checks)
 dump(OUT/'final_validation.json',final);print(status,final['checks_passed'],'/',len(checks),flush=True)
 files=[p for p in OUT.rglob('*') if p.is_file() and not any(x in p.relative_to(OUT).parts for x in ['runtime_cache','__pycache__']) and p.name not in ['output_manifest.csv','output_manifest.sha256']]
 save(OUT/'output_manifest.csv',[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files,key=str)]);(OUT/'output_manifest.sha256').write_text(sha(OUT/'output_manifest.csv')+'  output_manifest.csv\n',encoding='utf-8')
if __name__=='__main__':main()
