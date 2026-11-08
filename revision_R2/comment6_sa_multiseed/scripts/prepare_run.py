from common import *
from sa_kernel import EVIDENCE,LEGACY
import shutil,platform
def main():
 init();assert not (OUT/'run_manifest.json').exists(),'Already frozen'
 assert js(OUT/'audit/legacy_replay_validation.json')['status']=='PASS','Legacy replay must pass first'
 config=js(SA_ARCHIVE/'sa_configuration_freeze.json');cfg=LEGACY.SAConfig(**config['selected_configuration']);assert LEGACY.config_key(cfg)==config['selected_config_id']=='742ec3e18494';assert config['budget']==256 and config['development_scenarios']==[246,247,249]
 assert sha(SA_SOURCE)==sha(SA_SNAPSHOT)=='3da1b9ff7c6b53f8153d49796d4e80d3ea991561c45ffe76bc32293606295272'
 critical=[SA_SOURCE,SA_SNAPSHOT,SA_ARCHIVE/'sa_configuration_freeze.json',SA_ARCHIVE/'sa_configuration_freeze_hash.txt',OLD_TABLE,R42/'completion_check.json',R42/'00_protocol_and_input_audit/S0_input_manifest.csv',R42/'01_legacy_ue_state_comparison/independent_references.json',R42/'02_original_method_path_reevaluation/frozen_paths.json',R42/'02_original_method_path_reevaluation/S2_original_paths_revalued.csv',NEW30/'new30_run_level.csv',NEW30/'new30_scenario_level.csv',REV/'revision_4_6_tail_inference/00_audit/archived_Table_R2_method_summary.csv',FORMAL/'code/experiment.py',FORMAL/'source_snapshot/config/final_protocol_v1.1.json',Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer2_Comment6_SA多种子最小补充_Codex指令.md')]
 critical += [TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz' for sid in range(1001,1011)]
 critical += list(SA_ARCHIVE.rglob('*.json'))+list(SA_ARCHIVE.rglob('*.csv'))
 critical += [FULL/f'scenario_{sid}'/n for sid in range(1001,1011) for n in ['budget_snapshots_pre_reference.csv','budget_usage_pre_reference.json','ue_state_audit_log.csv.gz']]
 paths=set(critical)
 for root in [REPO,REV]:
  for directory,dirs,files in os.walk(root):
   p=Path(directory);dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','runtime_deps','runtime_cache'] and (p/d).resolve()!=OUT.resolve()]
   if p.resolve()==OUT.resolve():dirs[:]=[];continue
   paths.update(p/n for n in files)
 records=[]
 for i,p in enumerate(sorted(paths,key=str)):
  records.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
  if i%10000==0:print('Source snapshot',i,'/',len(paths),flush=True)
 dump(OUT/'audit/source_protection_before.json',dict(files=records,git=gitstate(),critical=[dict(path=str(p),sha256=sha(p)) for p in critical]));checks=[]
 def ck(label,ok,actual=None,expected=None):
  checks.append(dict(check=label,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
  if not ok:dump(OUT/'audit/input_validation.json',dict(status='PREFLIGHT_BLOCKED',checks=checks));raise RuntimeError('PREFLIGHT_BLOCKED '+label)
 ck('4.2_accepted',js(R42/'completion_check.json')['G1']=='PASS')
 source=read(R42/'00_protocol_and_input_audit/S0_input_manifest.csv')
 for name in ['ue_solver.py','path_ue.py']:
  r=source[source.absolute_path.str.endswith('\\'+name)].iloc[0];ck('solver_authority_'+name,sha(r.absolute_path)==r.sha256)
 refs=references();frozen=js(R42/'02_original_method_path_reevaluation/frozen_paths.json');reval=read(R42/'02_original_method_path_reevaluation/S2_original_paths_revalued.csv');proposed=[];high=[];seeds=[]
 for sid in range(1001,1011):
  t=hp(sid);E=roads(sid);ck(f'{sid}_1024_masks',t.subset_mask.tolist()==list(range(1024)));ck(f'{sid}_RG',t.relative_gap.le(1e-9).all(),float(t.relative_gap.max()),1e-9);ck(f'{sid}_finite',np.isfinite(t[['tstt','loss']]).all().all());ck(f'{sid}_normalizer',np.allclose(t.loss,t.tstt/T0-1,rtol=0,atol=1e-12))
  archived=refs[str(sid)];bits=[E.index(r) for r in archived['seq_new']];Jknown=sequence_value(bits,t.loss.to_numpy(float));ck(f'{sid}_reference_path_value_without_DP',abs(Jknown-archived['star_new'])<=1e-12,Jknown,archived['star_new'])
  p=next(r for r in frozen if r['scenario_id']==sid and r['label']=='Proposed_B256');ck(f'{sid}_road_bit_order',p['roads']==E)
  budgetfile=FULL/f'scenario_{sid}/budget_snapshots_pre_reference.csv';snap=read(budgetfile);b=snap[snap.ue_budget.eq(256)].iloc[0];seq=list(map(int,b.best_sequence.split('|')));ck(f'{sid}_B256_snapshot_frozen_path',seq==p['sequence'] and int(b.best_completion_budget)<=256)
  audit=read(FULL/f'scenario_{sid}/ue_state_audit_log.csv.gz');prefix=audit[audit.ue_calls_after.le(256)];charged=prefix[~prefix.cache_hit.astype(bool)];ck(f'{sid}_Proposed_prefix256_unique',charged.subset_mask.nunique()==256,len(charged),256)
  ms=masks([E.index(r) for r in seq]);ck(f'{sid}_Proposed_output_authorized',set(ms)<=set(charged.subset_mask.astype(int)))
  J=sequence_value([E.index(r) for r in seq],t.loss.to_numpy(float));old=reval[(reval.scenario_id==sid)&reval.path_label.eq('Proposed_B256')&reval.precision_tier.eq('new_path_1e-9')].iloc[0];ck(f'{sid}_Proposed_highprecision_reeval',abs(J-old.objective)<=1e-12)
  proposed.append(dict(scenario_id=sid,original_frozen_sequence=seq,J_Proposed_highprecision=J,J_star_highprecision=archived['star_new'],regret_pct=100*(J-archived['star_new'])/archived['star_new'],numerical_hit=abs(J-archived['star_new'])<=eps(archived['star_new']),strict_float_zero=J==archived['star_new'],old_published_hit=p['old_reported_hit'],R42_empirical_hit=bool(old.numerically_equivalent_hit),queries_B256_snapshot=256,best_completion_budget=int(b.best_completion_budget),original_full_archive_maximum_budget=js(FULL/f'scenario_{sid}/budget_usage_pre_reference.json')['maximum_budget'],source_B256_snapshot=str(budgetfile),source_B256_snapshot_sha256=sha(budgetfile),source_reevaluation='original lowprecision-chosen B256 path re-evaluated on accepted highprecision table; not rerun under changed feedback',original_runs=1,within_scenario_seed_SD=None,determinism_scope='one frozen candidate/screening seed realization and frozen deterministic search conditional on that queue; no ten-seed Proposed holdout run'))
  tablefile=TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz';high.append(dict(scenario_id=sid,table=str(tablefile),sha256=sha(tablefile),road_bit_order=E,J_star=archived['star_new'],max_RG=float(t.relative_gap.max())))
  for rep in range(10):seeds.append(dict(scenario_id=sid,replicate=rep,seed=2026081000+sid+100000*rep,B=256,precision='accepted_path_solver_RG1e-9',seed_role='original frozen seed' if rep==0 else 'fixed supplementary seed'))
 ck('100_seeds_unique',len(seeds)==len(set(s['seed'] for s in seeds))==100)
 n30=read(NEW30/'new30_run_level.csv');ck('new30_querycap_only',n30.phase.eq('query_cap').all() and set(n30.scenario_id)==set(range(3001,3031)));context=[]
 for method in ['proposed','sa_original','sa_restart']:
  g=n30[n30.method.eq(method)];ck('new30_'+method+'_300',len(g)==300 and g.queries.le(256).all() and all(set(sub.replicate)==set(range(10)) for _,sub in g.groupby('scenario_id')))
  context.append(dict(method=method,scenario_ids='3001-3030',independent_scenarios=30,runs=len(g),budget_cap=256,mean_actual_queries=float(g.queries.mean()),seed_mapping='2026081000+scenario_id+1000000*replicate for SA variants',source_code=str(FORMAL/'code/experiment.py'),source_code_sha256=sha(FORMAL/'code/experiment.py'),implementation_relation='R1 shared QueryOracle wrapper, bounded proposal loop and incumbent handling; original SA parameters reused; not claimed byte-identical to original prefix kernel',reuse_as_current_holdout_runs=False))
 save(OUT/'audit/Proposed_frozen_B256_highprecision.csv',[{**p,'original_frozen_sequence':canonical(p['original_frozen_sequence'])} for p in proposed]);save(OUT/'audit/new30_source_scope.csv',context);save(OUT/'seeds_frozen.csv',seeds);dump(OUT/'audit/input_validation.json',dict(status='PASS',checks=checks));dump(OUT/'audit/SA_definition_binding.json',dict(original_source=str(SA_SOURCE),source_sha256=sha(SA_SOURCE),snapshot_sha256=sha(SA_SNAPSHOT),configuration=config,search_AST=EVIDENCE,original_read_loader='unmodified tables_by_scenario pd.read_csv default for historical replay; explicit round_trip for accepted HP tables',no_previous_strictly_reusable_holdout_multiseed_runs=True))
 # Preserve original files in this new namespace for inspection only.
 shutil.copy2(SA_SOURCE,OUT/'raw/original_logs/run_permutation_sa_original_readonly_copy.py');shutil.copy2(SA_ARCHIVE/'sa_configuration_freeze.json',OUT/'raw/original_logs/sa_configuration_freeze_original.json')
 (OUT/'audit/source_inventory.md').write_text('# 权威来源与版本盘点\n\n原SA来自本地投稿包v2.2，与4.1原样快照和v2.0/v2.1源码SHA一致。选定config742ec3e18494只在246/247/249开发；本轮不运行网格调参。原源码搜索段以AST原样执行，函数尾部DP不执行。原十场景旧精度180项账本/轨迹复现通过。\n\n4.2权威1024表、原选路bit顺序、OD/BPR/solver双SHA、归一化及参考路径值核对通过；仅检查已有J*与已有路径，不重算DP。\n\n原Proposed档案整个运行到512，但本轮仅用封存的B256快照及前256唯一状态，未使用512结果。固定路径作高精度重评，不是高精度反馈重跑；Proposed只有每情景1个原冻结候选/筛选种子实现，不能捏造其十种子SD。\n\n新30的原SA/SA-restart/Proposed各300次、独立B256；场景3001—3030、seed间隔1000000，与本轮1001—1010、seed间隔100000区分。4.2/4.6只有原SA路径的重评，并非本轮高精度多种子搜索可复用记录。\n\n全部旧源SHA见source_protection_before.json；详细来源见SA_definition_binding.json和new30_source_scope.csv。',encoding='utf-8')
 scripts=[dict(path=str(p),sha256=sha(p)) for p in sorted((OUT/'scripts').glob('*.py'))]
 manifest=dict(status='FROZEN_BEFORE_FIRST_HIGHPRECISION_SA_RUN',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),git=gitstate(),SA_source_sha256=sha(SA_SOURCE),configuration=config['selected_configuration'],config_id=config['selected_config_id'],scenario_ids=list(range(1001,1011)),runs=seeds,B=256,seed_rule='2026081000+scenario_id+100000*replicate; replicate0 original',TSTT0_raw=T0,Q=Q,hit_rule='abs(J-Jstar)<=1e-9*max(1,abs(Jstar)); same for SA and Proposed; report strict float zero separately; existing frozen R1 empirical tests unchanged',regret_rule='100*(J-Jstar)/Jstar; retain raw signed roundoff; no clipping',quantiles='NumPy linear; sampleSD ddof1; first aggregate seeds within scenario, then ten scenarios',no_best_of10_same_budget=True,highprecision_tables=high,critical_sources=js(OUT/'audit/source_protection_before.json')['critical'],frozen_scripts=scripts,seeds_sha256=sha(OUT/'seeds_frozen.csv'),search_AST_sha256=EVIDENCE['search_body_AST_sha256'],new_real_UE_calls=0,DP_recalculations=0,original_Full_reruns=0,SA_restart_reruns=0,highprecision_historical_feedback_asymmetry='SA rerun on HP oracle; Proposed original lowprecision-selected B256 path reevaluated on same HP costs; do not claim both were rerun under identical HP feedback',timing_scope='sealed lookup search CPU and wall only; no online UE timing or offline state-table generation cost included')
 dump(OUT/'run_manifest.json',manifest);dump(OUT/'audit/prospective_freeze.json',dict(run_manifest_sha256=sha(OUT/'run_manifest.json'),highprecision_SA_runs_before_freeze=0));dump(OUT/'audit/environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform()));print('Frozen100 seeds and original SA; source audit PASS',len(records),flush=True)
if __name__=='__main__':main()
