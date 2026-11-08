"""Independent output audit. Never calls SA, DP, UE or any model inference."""
from common import *
import csv,gzip,math,traceback,collections
checks=[]
def ck(name,ok,actual=None,expected=None):
 checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 if not ok:print('FAIL',name,str(actual)[:200],str(expected)[:200],flush=True)
def near(a,b,tol=1e-12):return abs(float(a)-float(b))<=tol
def require(ok,msg):
 if not ok:raise ValueError(msg)
def audit():
 manifest=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json');old=js(OUT/'audit/source_protection_before.json')
 ck('manifest_still_frozen',sha(OUT/'run_manifest.json')==freeze['run_manifest_sha256'])
 ck('seedfile_frozen',sha(OUT/'seeds_frozen.csv')==manifest['seeds_sha256'])
 ck('Git_identity_unchanged',gitstate()==old['git'],gitstate(),old['git'])
 ck('critical_sources_and_execution_scripts',all(sha(r['path'])==r['sha256'] for r in manifest['critical_sources']+manifest['frozen_scripts']))
 for v in ['v2.0','v2.1','v2.2']:
  p=ARCHIVE_ROOT/f'初稿/Frontiers_Submission_Package_P1_{v}/reproducibility/p1_revision_tools/run_permutation_sa.py'
  ck('SA_source_crossversion_'+v,sha(p)==manifest['SA_source_sha256'],sha(p),manifest['SA_source_sha256'])
 legacy=js(OUT/'audit/legacy_replay_validation.json')
 ck('old_precision_gate',legacy['status']=='PASS' and legacy['checks_passed']==legacy['checks_total']==180 and legacy['max_objective_error']==0,legacy)
 ck('input_gate',js(OUT/'audit/input_validation.json')['status']=='PASS')
 # Explicit historical authority binding, beyond the current before/after SHA.
 authoritative=read(R42/'00_protocol_and_input_audit/S0_input_manifest.csv');binding=[]
 selected=authoritative[authoritative.data_role.eq('frozen network, OD, BPR input') | authoritative.absolute_path.str.endswith('\\ue_solver.py') | authoritative.absolute_path.str.endswith('\\path_ue.py')]
 for row in selected.itertuples():
  current=sha(row.absolute_path);binding.append(dict(role=row.data_role,path=row.absolute_path,authoritative_R42_sha256=row.sha256,current_sha256=current,status='PASS' if current==row.sha256 else 'FAIL'))
 for table in manifest['highprecision_tables']:
  sourcehash=table['sha256'];matches=authoritative[authoritative.sha256.eq(sourcehash)];binding.append(dict(role='accepted HP1024 table '+str(table['scenario_id']),path=table['table'],authoritative_R42_sha256=sourcehash if len(matches) else 'MISSING',current_sha256=sha(table['table']),status='PASS' if len(matches) and sha(table['table'])==sourcehash else 'FAIL'))
 constants=read(R42/'00_protocol_and_input_audit/S0_numeric_constants.csv').set_index('name').value
 odrow=selected[selected.absolute_path.str.endswith('\\od_long.csv')].iloc[0];odsum=float(read(odrow.absolute_path).demand.sum())
 save(OUT/'audit/R42_source_authority_binding.csv',binding)
 ck('R42_network_OD_BPR_solver_tables_and_unit_constants',len(selected)>=8 and all(r['status']=='PASS' for r in binding) and constants['dry_baseline_TSTT']==T0 and constants['scored_stages']==10 and constants['terminal_R10_weight']==0 and odsum==Q,dict(files=len(binding),TSTT0=T0,Q_recomputed=odsum,stages=10,terminal_weight=0))
 fire=js(OUT/'audit/firewall_tests.json');ck('oracle_access_firewall',all(r['pass_'] for r in fire),fire)
 execution=js(OUT/'audit/execution_validation.json');ck('100_actual_searches_UE0_DP0',execution['status']=='PASS' and execution['highprecision_SA_runs']==100 and execution['new_real_UE_calls']==execution['DP_recalculations']==0)
 f=read(OUT/'raw/SA_all100_runs.csv');seeds=read(OUT/'seeds_frozen.csv');idx=['scenario_id','replicate'];f=f.sort_values(idx)
 ck('100_complete_cases',len(f)==100 and set(f.scenario_id)==set(range(1001,1011)) and all(set(g.replicate)==set(range(10)) for _,g in f.groupby('scenario_id')))
 ck('100_unique_prespecified_seeds',f.seed.nunique()==100 and (f.seed==2026081000+f.scenario_id+100000*f.replicate).all() and f[idx+['seed']].equals(seeds.sort_values(idx)[idx+['seed']]))
 ck('freeze_before_all_completions',pd.to_datetime(f.completed_utc,format='ISO8601',utc=True).min()>pd.Timestamp(manifest['created_utc']))
 ck('budget_bounds',f.queries_charged.between(10,256).all(),[int(f.queries_charged.min()),int(f.queries_charged.max())],[196,256])
 refs=references();tables={sid:hp(sid) for sid in range(1001,1011)};losses={sid:t.loss.to_numpy(float) for sid,t in tables.items()};runs={(int(r.scenario_id),int(r.replicate)):r for r in f.itertuples()}
 unit=read(OUT/'raw/SA_unique_query_ledger.csv');tr=read(OUT/'raw/SA_trajectories.csv');stats={};maxJerror=maxRegerror=maxATTerror=0.
 for key,r in runs.items():
  sid,rep=key;bits=json.loads(r.best_sequence_bits);seq=json.loads(r.best_sequence);requested=json.loads(r.requested_masks);folder=OUT/f'raw/runs/scenario_{sid}/rep_{rep:02d}';saved=js(folder/'result.json');h=read(folder/'source_history.csv');u=unit[(unit.scenario_id==sid)&(unit.replicate==rep)];t=tr[(tr.scenario_id==sid)&(tr.replicate==rep)].sort_values('stage');E=roads(sid)
  require(sorted(bits)==list(range(10)) and seq==[E[b] for b in bits],f'Invalid permutation {key}')
  require(len(requested)==len(set(requested))==r.queries_charged and requested==u.subset_mask.tolist() and set(masks(bits))<=set(requested),f'Query set {key}')
  require(u.logical_query_index.tolist()==list(range(1,r.queries_charged+1)),f'Ledger counter {key}')
  require(len(t)==11 and t.stage.tolist()==list(range(11)) and t.subset_mask.tolist()==masks(bits)+[1023],f'11 stages {key}')
  require(t.weight.tolist()==[.1]*10+[0.] and not bool(t.visible_to_search.iloc[-1]) and t.post_search_evaluation.all(),f'Terminal exclusion {key}')
  require(np.array_equal(t.loss.to_numpy(),losses[sid][t.subset_mask.to_numpy(int)]),f'Stage costs {key}')
  require(np.allclose(t.TSTT_veh_h,.01*t.tstt_raw,rtol=0,atol=1e-7) and np.allclose(t.ATT_min,.6*t.tstt_raw/Q,rtol=0,atol=1e-10),f'Units {key}')
  J=math.fsum(t.loss.iloc[:10])/10;star=refs[str(sid)]['star_new'];reg=100*(r.J_SA-star)/star;delta=ATT0*(r.J_SA-star)
  maxJerror=max(maxJerror,abs(J-r.J_SA));maxRegerror=max(maxRegerror,abs(reg-r.regret_pct));maxATTerror=max(maxATTerror,abs(delta-r.delta_ATT_min))
  require(near(J,r.J_SA) and r.J_star_highprecision==star and r.J_SA>=star-eps(star),f'Objective/ref {key}')
  require(near(reg,r.regret_pct) and near(delta,r.delta_ATT_min) and near(r.mean_stage_ATT_min,float(t.ATT_min.iloc[:10].mean()),1e-9),f'Score/ATT {key}')
  require(bool(r.exact_hit)==(abs(r.J_SA-star)<=eps(star)) and bool(r.strict_float_zero)==(r.J_SA==star),f'Hit definition {key}')
  require(r.accepted_moves==int(h.accepted.iloc[1:].sum()) and near(h.best_objective.iloc[-1],r.J_SA) and h.queried_states.iloc[-1]==r.queries_charged,f'Original history {key}')
  require(saved['seed']==r.seed and saved['requested_masks']==requested and saved['best_sequence']==seq and saved['RNG_final_state']['bit_generator']=='PCG64',f'Per-run export {key}')
  require((r.queries_charged==256 and r.stopping_reason=='unique_budget_exhausted') or (r.queries_charged<256 and r.stalled>=1000 and r.stopping_reason=='stalled_1000'),f'Source stop {key}')
  stats[key]={'seen':set(),'order':[],'accesses':0,'calls':0,'feasible':0,'rejected':0,'last_call':0,'last_seq':None,'stalled':0,'read_call_counts':collections.Counter()}
 ck('100_permutations_authorized_stages_units_and_history',True)
 ck('stage_objective_reconciliation_1e12',maxJerror<=1e-12,maxJerror,1e-12)
 ck('regret_and_absolute_ATT_reconciliation',maxRegerror<=1e-12 and maxATTerror<=1e-12,[maxRegerror,maxATTerror])
 # Real backing-store accesses, including repeats: no inference from total counts.
 total_reads=0
 with (OUT/'raw/SA_query_ledger_all.csv').open(encoding='utf-8',newline='') as source:
  for row in csv.DictReader(source):
   sid=int(row['scenario_id']);rep=int(row['replicate']);key=(sid,rep);s=stats[key];r=runs[key];mask=int(row['subset_mask']);new=int(row['new_charge']);call=int(row['sequence_call'])
   require(0<=mask<1024 and int(row['seed'])==r.seed,f'Access identity {key}')
   require(int(row['access_index'])==s['accesses']+1 and call>=s['last_call'],f'Access order {key}')
   require(float(row['loss'])==losses[sid][mask],f'Access value {key}')
   require(new==int(mask not in s['seen']),f'Duplicate charge {key}')
   if new:s['seen'].add(mask);s['order'].append(mask)
   require(int(row['charged_after'])==len(s['seen'])<=256,f'Budget access {key}')
   require(row['read_kind']==('new_state_ledger_value' if new else 'objective_or_cached_value'),f'Read kind {key}')
   s['read_call_counts'][call]+=1;s['accesses']+=1;s['last_call']=call;total_reads+=1
 for key,s in stats.items():
  r=runs[key];require(s['order']==json.loads(r.requested_masks) and s['accesses']==r.actual_cost_reads,f'Backing ledger end {key}');s['seen']=set();s['order']=[]
 ck('every_real_cost_read_authorized_charged_once_and_exact',True,total_reads)
 # Reconstruct authorization/cost of proposals without regenerating any proposal.
 with gzip.open(OUT/'raw/SA_proposals_all.csv.gz','rt',encoding='utf-8',newline='') as source:
  for row in csv.DictReader(source):
   sid=int(row['scenario_id']);rep=int(row['replicate']);key=(sid,rep);s=stats[key];r=runs[key];call=int(row['call_index']);iteration=int(row['iteration']);bits=list(map(int,row['sequence_bits'].split('-')));ms=masks(bits);new=set(ms)-s['seen'];before=len(s['seen']);feasible=before+len(new)<=256
   require(sorted(bits)==list(range(10)) and int(row['seed'])==r.seed and call==s['calls']+1 and iteration==call-1,f'Proposal identity/order {key}')
   require(int(row['unique_before'])==before and int(row['missing_states_before'])==len(new) and (row['budget_feasible']=='True')==feasible,f'Atomic precheck {key}')
   if feasible:
    for mask in ms:
     if mask not in s['seen']:s['seen'].add(mask);s['order'].append(mask)
    require(float(row['objective'])==float(np.mean(losses[sid][ms])),f'Proposal objective {key}')
    require(int(row['new_queries'])==len(new) and s['read_call_counts'][call]==10+len(new),f'Proposal real reads {key}')
    s['feasible']+=1;s['last_seq']=bits
   else:
    require(row['objective']=='' and int(row['new_queries'])==0 and s['read_call_counts'][call]==0,f'Rejected proposal leaked/cost {key}');s['rejected']+=1
   require(int(row['unique_after'])==len(s['seen']),f'Post budget {key}')
   if iteration>0:s['stalled']=0 if feasible and len(new)>0 else s['stalled']+1
   s['calls']+=1
 for key,s in stats.items():
  r=runs[key];require(s['order']==json.loads(r.requested_masks) and s['calls']==r.proposals+1 and s['feasible']==r.sequence_evaluations and s['rejected']==r.budget_rejected_proposals and s['stalled']==r.stalled,f'Proposal totals/stall {key}')
 ck('every_proposal_atomic_budget_cached_cost_and_stop_reconstructed',True,sum(s['calls'] for s in stats.values()))
 per=read(OUT/'Table_R2C6_holdout_per_scenario.csv');rep=read(OUT/'Table_R2C6_per_replicate.csv');cmp=read(OUT/'Table_R2C6_comparison_to_Proposed.csv');P=read(OUT/'audit/Proposed_frozen_B256_highprecision.csv').set_index('scenario_id')
 def dist(row,x,suffix='_regret_pct'):
  for field,val in [('mean',np.mean(x)),('median',np.median(x)),('P90',np.quantile(x,.9,method='linear')),('maximum',np.max(x)),('minimum',np.min(x))]:require(near(row[field+suffix],val),f'Statistic {field} {row.name}')
 for _,row in per.iterrows():
  g=f[f.scenario_id.eq(row.scenario_id)];dist(row,g.regret_pct);require(near(row.SD_regret_pp,g.regret_pct.std(ddof=1)) and int(row.conditional_optimal_hits)==int(g.exact_hit.sum()) and row.hit_denominator==10 and near(row.mean_queries,g.queries_charged.mean()),'Scenario metrics')
  require(near(row.mean_delta_ATT_min,g.delta_ATT_min.mean()) and near(row.SD_delta_ATT_min,g.delta_ATT_min.std(ddof=1)),'ATT mean/SD')
 for _,row in rep.iterrows():
  g=f[f.replicate.eq(row.replicate)];dist(row,g.regret_pct);require(row.scenarios==10 and row.queries_total==g.queries_charged.sum() and row.conditional_optimal_hit_count==g.exact_hit.sum(),'Replicate metrics')
 for _,row in cmp.iterrows():
  sid=int(row.scenario_id);g=f[f.scenario_id.eq(sid)];p=P.loc[sid];bits=[roads(sid).index(v) for v in json.loads(p.original_frozen_sequence)];J=math.fsum(losses[sid][m] for m in masks(bits))/10
  require(near(J,p.J_Proposed_highprecision) and row.Proposed_B256_queries==256 and row.Proposed_archive_maximum_budget==512 and row.Proposed_best_completion_budget<=256,'Proposed256 distinction')
  require(near(row.SA_mean_minus_Proposed_regret_pp,g.regret_pct.mean()-p.regret_pct) and pd.isna(row.Proposed_seed_SD) and row.Proposed_original_runs==1,'Proposed uncertainty')
  require(bool(p.numerical_hit)==(abs(p.J_Proposed_highprecision-p.J_star_highprecision)<=eps(p.J_star_highprecision)),'Same hit rule Proposed')
 overall=read(OUT/'Table_R2C6_scenario_level_overall.csv')
 for _,row in overall.iterrows():
  x=per.mean_regret_pct if row.cohort=='SA_scenario_means_over10seeds' else f[f.replicate.eq(0)].regret_pct if row.cohort=='SA_original_seed_reexecuted_HP' else P.regret_pct
  dist(row,x);require(row.independent_scenarios==10 and row.unit=='scenario','Scenario sampling unit')
 ck('all_scenario_replicate_and_Proposed_tables_independently_recomputed',True)
 new=read(NEW30/'new30_run_level.csv');ss=read(NEW30/'new30_scenario_level.csv');context=read(OUT/'Table_R2C6_existing_new30_context.csv')
 for _,row in context.iterrows():
  g=new[new.method.eq(row.method)];s=ss[ss.method.eq(row.method)];require(len(g)==300 and len(s)==30 and set(g.scenario_id)==set(range(3001,3031)) and g.queries.le(256).all() and row.independent_scenarios==30,'new30 scope')
  require(near(row.mean_scenario_mean_regret_pct,s.mean_regret_pct.mean()) and near(row.P90_scenario_mean_regret_pct,np.quantile(s.mean_regret_pct,.9,method='linear')),'new30 statistics')
 ck('separate_new30_context_not_pooled',True)
 auto=js(OUT/'audit/figure_automated_QA.json');visual=js(OUT/'audit/figure_visual_review.json')
 ck('figure_font_collision_dpi_and_source_QA',all(v['returncode']==0 for v in auto),auto)
 ck('final_PDFs_and_PNGs_visually_checked',visual['status']=='PASS' and all(r['visually_checked_final_PDF_and_PNG'] and sha(OUT/f"figures/{r['name']}.pdf")==r['pdf_sha256'] and sha(OUT/f"figures/{r['name']}.png")==r['png_sha256'] and sha(OUT/f"figures/{r['name']}.svg")==r['svg_sha256'] and r['editable_svg_text_elements']>0 for r in visual['figures']))
 required=['README_文件索引.md','Response_R2_Comment6_draft_EN.md','Manuscript_insertions_R2C6_EN.md','Comment_R2_6_SA_multiseed_results_CN.md','logs/reproduction_commands.md']
 ck('required_reports_exist',all((OUT/p).is_file() for p in required))
 reply=(OUT/'Response_R2_Comment6_draft_EN.md').read_text(encoding='utf-8');insert=(OUT/'Manuscript_insertions_R2C6_EN.md').read_text(encoding='utf-8')
 ck('draft_action_and_page_status_truthful','PROPOSED INSERTION' in insert and 'PAGE/LINE TO BE FINALIZED' in reply and 'have revised the manuscript' not in reply.lower() and 'old-feedback' in reply and 'not pooled' in reply and 'post-study' in reply)
 # Full pre-existing source snapshot, after every computation and figure/report export.
 protected=[]
 for i,r in enumerate(old['files']):
  p=Path(r['path']);exists=p.is_file();actual=sha(p) if exists else None;protected.append(dict(path=str(p),sha256_before=r['sha256'],sha256_after=actual,bytes_before=r['bytes'],bytes_after=p.stat().st_size if exists else None,status='PASS' if actual==r['sha256'] else 'FAIL'))
  if i%10000==0:print('Read-only source rehash',i,'/',len(old['files']),flush=True)
 save(OUT/'audit/source_protection_final.csv',protected)
 ck('all_preexisting_file_hashes_unchanged',all(r['status']=='PASS' for r in protected),len(protected))
 ck('Git_identity_still_unchanged',gitstate()==old['git'])
 dump(OUT/'audit/independent_ledger_audit.json',dict(status='PASS',actual_backing_cost_reads=total_reads,total_proposal_calls=sum(s['calls'] for s in stats.values()),unique_queries=int(f.queries_charged.sum()),runs_checked=100,max_stage_objective_abs_error=maxJerror,max_regret_abs_error=maxRegerror,max_delta_ATT_abs_error=maxATTerror,no_search_rerun=True,DP_calculations=0,UE_calls=0))
def main():
 try:audit()
 except Exception as e:
  ck('audit_completed_without_exception',False,str(e));(OUT/'logs/final_validation_exception.txt').write_text(traceback.format_exc(),encoding='utf-8');print(traceback.format_exc(),flush=True)
 status='PASS' if all(r['status']=='PASS' for r in checks) else 'FAIL'
 result=dict(status=status,checks_passed=sum(r['status']=='PASS' for r in checks),checks_total=len(checks),checks=checks,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),limitations=['post-study original10, not blind holdout','SA HP feedback vs Proposed frozen old-feedback path HP re-evaluation','Proposed only one frozen realization; no ten-seed variance estimate','only10 independent flood cases;100 technical seed runs','lookup CPU/wall excludes online UE and table construction','no master manuscript merged or final page/line assigned'],new_real_UE_calls=0,DP_recalculations=0,additional_searches_during_validation=0)
 dump(OUT/'final_validation.json',result)
 text='# Reviewer 2 Comment 6 最终自动验收\n\n状态：**'+status+'**；'+str(result['checks_passed'])+'/'+str(len(checks))+'项检查通过。\n\n|检查|状态|\n|---|---|\n'+'\n'.join('|'+r['check']+'|'+r['status']+'|' for r in checks)+'\n\n完整值、容差和证据见final_validation.json；逐访问/逐proposal独立验收见audit/independent_ledger_audit.json；旧文件逐项前后SHA见audit/source_protection_final.csv。\n\n验收仅核查现有100次产物，没有补跑SA、UE、DP、模型训练。PASS表示本轮限定计算和审计完成，不消除后验分析、精度反馈不对称、Proposed仅一个冻结实现和小情景样本的限制。\n'
 (OUT/'QA_validation.md').write_text(text,encoding='utf-8');print(status,result['checks_passed'],len(checks),flush=True)
 if status!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
