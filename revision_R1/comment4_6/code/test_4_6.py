from load_frozen_results import *
import argparse,sys

def validate(out,strict=True):
 out=Path(out);require_gate(out,'G1');checks=[]
 def passed(name,evidence):checks.append({'name':name,'status':'PASS','evidence':evidence})
 check_immutable(out);passed('source_hashes_after_analysis','all archives, required member bytes, direct copies, protocol, original code and weight bytes unchanged')
 t=tables(out);raw=t['all_run_results.csv'];run=frame(out/'02_new30/new30_run_level.csv');assert len(raw)==2250 and len(run)==1590 and run.phase.eq('query_cap').all();passed('phase_firewall','2250=1590 query_cap+660 time_cap; only1590 retained')
 for method in METHODS:
  g=run[run.method==method];n=10 if method in STOCH else 1;assert len(g)==30*n and g.groupby('scenario_id').size().eq(n).all()
 passed('replication_and_uniqueness','five methods30x10, three30x1; keys checked inG0')
 legacy=frame(out/'01_legacy10/legacy10_quantiles.csv');anchors=frame(out/'00_audit/legacy10_anchor_checks.csv');assert len(legacy)==4 and len(anchors)==16 and anchors.absolute_error.le(1e-8).all();passed('legacy_precision_anchors','4 combinations,16 source-exact summary checks within1e-8 pp')
 anchors=frame(out/'00_audit/new30_archive_anchor_checks.csv');assert anchors.absolute_error.le(1e-9).all();passed('new30_archive_anchors',f'{len(anchors)} numeric checks within1e-9, including each scenario summary and archivedR2/R3 effects')
 # Third-way check against the six-decimal anchors in the author's supplied plan.
 planchecks=[];names={'Proposed':'proposed','SA-original':'sa_original','SA-restart':'sa_restart','UE-Greedy-ILS':'greedy_ils','UE-BiBeam':'ue_bibeam'}
 su=frame(out/'02_new30/new30_tail_summary.csv').set_index('method')
 fields=['mean_scenario_mean_regret_pct','median_scenario_mean_regret_pct','P90_scenario_mean_regret_pct','max_scenario_mean_regret_pct','P90_per_scenario_worst_seed_regret_pct','global_max_individual_regret_pct','mean_seed_SD_pp']
 for line in PLAN.read_text(encoding='utf-8-sig').splitlines():
  if not line.startswith('|'):continue
  cells=[s.strip() for s in line.strip().strip('|').split('|')]
  if cells[0] not in names or len(cells)!=8:continue
  method=names[cells[0]]
  for field,cell in zip(fields,cells[1:]):
   value=su.loc[method,field]
   if cell.startswith('不适用'):assert pd.isna(value);continue
   expected=float(cell);err=abs(value-expected);assert err<=5.01e-7,(method,field,value,expected)
   planchecks.append({'method':method,'metric':field,'protocol_rounded_anchor':expected,'recomputed_unrounded':value,'absolute_error':err,'rounding_tolerance_pp':5.01e-7,'status':'PASS'})
 assert len(planchecks)==34
 csv(out/'00_audit/provided_plan_rounded_anchor_checks.csv',planchecks);passed('third_way_plan_anchors','all34 rounded numeric anchors match provided execution plan; singletonSD NA verified separately')
 for filename,n,rank in [('01_legacy10/legacy10_P90_order_statistics.csv',10,9),('02_new30/new30_P90_order_statistics.csv',30,27)]:
  d=frame(out/filename);cols=['method','precision_tier'] if n==10 else ['method']
  for _,g in d.groupby(cols):
   assert len(g)==n and set(g.loc[g.P90_weight.gt(0),'rank_ascending'])=={rank,rank+1}
   expected=g.P90_component_pp.sum();assert abs(expected-g.iloc[0].get('full10_P90_pct',g.iloc[0].get('full30_P90_pct')))<1e-12
 passed('linear_order_stat_formula','legacy ranks9/10, new30 ranks27/28; weights0.9/0.1')
 # Explicit negative tests using actual300-row Proposed data, not a synthetic P90.
 vals=run[run.method=='proposed'].relative_regret_pct
 for unit in ['run','scenario']:
  rejected=False
  try:scenario_quantile(vals,unit=unit)
  except ValueError:rejected=True
  assert rejected,f'300-run flat calculation was accepted with unit={unit}'
 passed('reject_flat300_P90','both unit=run and disguised unit=scenario reject actual300 raw Proposed rows')
 sc=frame(out/'02_new30/new30_scenario_level.csv');assert len(sc)==240 and not sc.duplicated(['scenario_id','method']).any();assert sc.loc[sc.method.isin(DETERM),'seed_SD_regret_pp'].isna().all()
 for _,g in run.groupby(['scenario_id','method']):
  m=g.method.iloc[0];sid=g.scenario_id.iloc[0];s=sc[(sc.method==m)&(sc.scenario_id==sid)].iloc[0];assert abs(s.mean_regret_pct-g.relative_regret_pct.mean())<1e-12
  if m in STOCH:assert abs(s.seed_SD_regret_pp-g.relative_regret_pct.std(ddof=1))<1e-12
 passed('scenario_aggregation_and_SD','240 scenario-method records; ddof1 for ten-seed methods; singletonSD NA')
 pair=frame(out/'02_new30/new30_paired_scenarios.csv');ps=frame(out/'02_new30/new30_paired_basic_summary.csv')
 for row in ps.itertuples():
  g=pair[pair.comparator==row.comparator];assert len(g)==30;delta=g.Proposed_scenario_mean_regret_pct-g.comparator_scenario_mean_regret_pct
  assert np.max(abs(delta-g.delta_Proposed_minus_comparator_pp))<1e-12
  assert abs(q(delta,.9)-row.P90_of_paired_differences_pp)<1e-12
  assert abs(scenario_quantile(g.Proposed_scenario_mean_regret_pct,unit='scenario')-scenario_quantile(g.comparator_scenario_mean_regret_pct,unit='scenario')-row.difference_of_P90s_pp)<1e-12
 passed('difference_sign_and_distinct_quantiles','positive=unfavorable toProposed; quantile-of-differences and difference-of-quantiles separate')
 oldlo=frame(out/'01_legacy10/legacy10_LOSO.csv');newlo=frame(out/'02_new30/new30_LOSO.csv');assert len(oldlo)==20 and len(newlo)==120
 for _,g in newlo.groupby('comparator'):assert set(g.omitted_scenario_for_sensitivity_only)==set(range(3001,3031)) and g.primary_retains_all30.all()
 passed('all_LOSO_omissions_retained','20 legacy rows=2precisionx10;120 new rows=4comparatorsx30')
 # Frozen primary p values and CIs are copied, not rerun by analysis code.
 frozen=frame(out/'00_audit/archived_Table_R3_primary_paired_comparisons.csv');assert frozen.equals(t['Table_R3_primary_paired_comparisons.csv']);passed('original_primary_tests_preserved','full archived R3 retained including Holm-adjusted p values')
 assert not any((out/f).exists() for f in ['02_new30/paired_cluster_bootstrap.csv','03_variance/variance_components.csv','06_delivery/Reviewer1_4.6_英文回复草稿.md']);assert not list(out.rglob('*.zip'))
 assert not any(name in sys.modules for name in ['experiment','torch','sklearn','candidate_factory','ue_provider'])
 passed('batch_scope_and_no_simulation_imports','0 bootstrap, variance decompositions, optimizer/UE/model imports, English drafts or ZIPs')
 checks += [{'name':'paired_cluster_and_nested_bootstrap','status':'DEFERRED_NOT_RUN','evidence':'requires author acceptance of first batch; frozen future seed2026103006,B20000'},{'name':'variance_components_and_seed_bootstrap','status':'DEFERRED_NOT_RUN','evidence':'only existing baseline seedSD was verified this batch; no new decomposition'},{'name':'manuscript_and_English_response','status':'DEFERRED_NOT_RUN','evidence':'requires second-batchG2; not an incomplete first-batch gate'}]
 dump(out/'00_audit/validation_report.json',{'status':'PASS_FIRST_BATCH','G0':'PASS','S1':'PASS','G1':'PASS','G2':'NOT_EXECUTED','at':now(),'checks':checks,'passed_checks':sum(c['status']=='PASS' for c in checks),'deferred_checks':sum(c['status'].startswith('DEFERRED') for c in checks),'new_UE':0,'new_optimization_runs':0,'new_scenarios':0,'training_or_prediction_runs':0,'bootstrap_runs':0,'new_archives':0,'stop_after_first_batch':True})
 csv(out/'00_audit/automatic_acceptance_log.csv',checks);print(f'First-batch validation PASS: {sum(c["status"]=="PASS" for c in checks)} checks;3 future items gated',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--strict',action='store_true');a=p.parse_args();validate(a.out,a.strict)
