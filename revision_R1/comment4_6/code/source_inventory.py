from load_frozen_results import *

def audit(out,source41,source42):
 out=Path(out).resolve();a=out/'00_audit';assert not (a/'analysis_protocol.json').exists(),'Refuse replacing a frozen4.6 protocol'
 for folder in ['00_audit','01_legacy10','02_new30','03_variance','04_optional_45','05_figures','06_delivery']:(out/folder).mkdir(parents=True,exist_ok=True)
 spec={'at':now(),'scope':'first batch S0-S1 plus new30 foundation and all30 basic LOSO only','source41':str(Path(source41).resolve()),'source42':str(Path(source42).resolve()),'provided_plan':str(PLAN),'provided_plan_sha256':sha(PLAN),'author_request_precedence':['No bootstrap this batch','No new UE/scenarios/training/optimizer or seed runs','No English response or manuscript text this batch','Stop after first-batch delivery','No new ZIP per prior user instruction'],'legacy10':{'IDs':list(range(1001,1011)),'methods':LEGACY_METHODS,'precisions':PRECISIONS,'role':'historical observations, fixed existing paths; not independent confirmatory sample','SA_seed':'one archived fixed seed per scenario; no valid within-scenario seed variance estimate'},'new30':{'IDs':list(range(3001,3031)),'phase':'query_cap','source_total_rows':2250,'retained_rows':1590,'excluded_time_cap_rows':660,'stochastic_methods':STOCH,'replicates':list(range(10)),'single_run_methods':DETERM,'single_replicate':0,'unit':'independent scenario; average existing seeds within scenario first'},'statistics':{'regret_pct':'retain archived max(0,100*(J-Jstar)/Jstar), normalized mean R0..R9 loss objective; no rescaling or new clipping rule','quantiles':'NumPy method=linear','P90_n10':'0.9*r_sorted[8]+0.1*r_sorted[9]','P90_n30':'0.9*r_sorted[26]+0.1*r_sorted[27]','seed_SD':'ddof1; NA for one-run methods; archived0 audited as storage convention only','pair_sign':'Proposed minus comparator; positive is unfavorable to Proposed','equivalence':'original empirical kappa rule, not new threshold or rigorous UE error bound','primary_test_policy':'preserve original4.1 R3; no new p tests or replacement Holm adjustment','LOSO':'all10 legacy omissions separately per precision, all30 new omissions; primary sample never replaced'},'future_gated':{'bootstrap_seed':2026103006,'bootstrap_repetitions':20000,'scenario_only_and_nested':'not executed or implemented in this batch; require author acceptance','variance_decomposition':'deferred','optional45':'deferred, no pooled40','manuscript_and_response':'deferred'},'forbidden_operations':['UE solve','scenario generation','optimization replay','model fitting or prediction','new seeds','new ZIP']}
 dump(a/'analysis_protocol.json',spec);(a/'provided_execution_plan.md').write_bytes(PLAN.read_bytes());records=[];schemas={};ziprows=[]
 def record(p,role,rows=None,member='',b=None):
  p=Path(p);records.append({'source_path':str(p),'zip_member':member,'size_bytes':len(b) if b is not None else p.stat().st_size,'SHA256':sha_bytes(b) if b is not None else sha(p),'rows':rows,'role':role,'frozen_status':'read-only original; hash checked before and after'})
 record(PLAN,'author supplied execution plan')
 for source,required in [(source41,REQUIRED41),(source42,REQUIRED42)]:
  source=Path(source).resolve()
  if source.is_file():
   record(source,'frozen numeric ZIP archive')
   with zipfile.ZipFile(source) as z:
    assert z.testzip() is None,'ZIP CRC validation failed'
    ziprows += [{'source_path':str(source),'zip_member':i.filename,'size_bytes':i.file_size,'compressed_bytes':i.compress_size,'CRC32':f'{i.CRC:08x}'} for i in z.infolist()]
  for name in required:
   b,member,d=read_asset(source,name);record(source,'frozen source CSV',len(d),member,b)
   schemas[name]={'source':str(source),'actual_member':member,'rows':len(d),'columns':[{'name':c,'dtype':str(d[c].dtype),'missing':int(d[c].isna().sum())} for c in d],'phase_counts':d.phase.value_counts().to_dict() if 'phase' in d else None,'method_counts':d.method.value_counts().to_dict() if 'method' in d else None,'all_columns_preserved':True}
 # Code/weights are hashed as inert bytes; never imported or deserialized.
 for root in [BASE41/'code',BASE42/'code']:
  for p in sorted(root.glob('*.py')):record(p,'archived analysis/experiment code, hash only, not executed')
 config=BASE41/'protocol/frozen_protocol.json';record(config,'original4.1 numerical equivalence and normalized objective definition')
 for p in sorted((BASE41/'source_snapshot/surrogate/final_ensemble').rglob('*')):
  if p.is_file() and p.suffix in ['.pt','.json']:record(p,'frozen surrogate asset; hash only, not loaded')
 # Direct archived copies must exactly match ZIP member bytes, not become a second sample.
 links=[]
 direct41=BASE41/'analysis';direct42=BASE42/'02_original_method_path_reevaluation'
 for source,required,root in [(source41,REQUIRED41,direct41),(source42,REQUIRED42,direct42)]:
  for name in required:
   p=root/name;b,member,d=read_asset(source,name)
   if p.is_file():
    assert sha(p)==sha_bytes(b),(p,'direct archive differs from selected ZIP')
    record(p,'direct archived copy; byte-identical to ZIP, not separately analysed',len(d));links.append({'direct_path':str(p),'ZIP_source':str(source),'zip_member':member,'byte_identical':True})
 csv(a/'source_manifest.csv',records);dump(a/'source_schema.json',schemas);csv(a/'zip_member_inventory.csv',ziprows);csv(a/'archive_direct_copy_identity.csv',links)
 d=tables(out);runs=d['all_run_results.csv'];assert len(runs)==2250 and runs.phase.value_counts().to_dict()=={'query_cap':1590,'time_cap':660}
 x=runs[runs.phase=='query_cap'].copy();assert set(x.scenario_id)==set(range(3001,3031)) and set(x.method)==set(METHODS)
 assert not x.duplicated(['phase','scenario_id','method','replicate']).any()
 cfg=js(config);kappa=cfg['equivalence']['equivalence_kappa'];spec['frozen_kappa']=kappa;spec['original_normalized_objective']=cfg['objective'];spec['original_source_protocol_sha256']=sha(config)
 counts=[]
 for method in METHODS:
  g=x[x.method==method];n=10 if method in STOCH else 1
  assert len(g)==30*n and g.groupby('scenario_id').size().eq(n).all()
  assert all(set(h.replicate)==set(range(n)) for _,h in g.groupby('scenario_id'))
  counts.append({'method':method,'scenarios':30,'seeds_per_scenario':n,'runs':len(g),'role':'stochastic ten fixed seeds' if n==10 else 'one recorded deterministic run, not ten pseudo-repeats'})
 for col in ['relative_regret_pct','objective','exact_objective','equivalence_objective_epsilon','queries']:assert np.isfinite(x[col]).all(),col
 assert x.exact_objective.gt(0).all() and x.relative_regret_pct.ge(0).all()
 refs=x.groupby('scenario_id').exact_objective.agg(['min','max']);assert (refs['min']==refs['max']).all()
 expected_eps=kappa*np.maximum(1,abs(x.exact_objective));assert np.allclose(x.equivalence_objective_epsilon,expected_eps,atol=1e-15,rtol=1e-13)
 calculated=np.maximum(0,100*(x.objective-x.exact_objective)/x.exact_objective);assert np.max(abs(calculated-x.relative_regret_pct))<=1e-12
 hit=abs(x.objective-x.exact_objective)<=expected_eps;assert np.array_equal(hit,x.numerical_equivalent_hit)
 old=d['S2_original_paths_revalued.csv'];selected=old[old.path_label.isin(LEGACY_METHODS)];assert len(selected)==40
 assert set(selected.scenario_id)==set(range(1001,1011)) and set(selected.precision_tier)==set(PRECISIONS)
 assert not selected.duplicated(['scenario_id','path_label','precision_tier']).any()
 assert selected.groupby(['path_label','precision_tier']).size().eq(10).all()
 assert np.isfinite(selected[['objective','reference_objective','regret_pct']]).all().all()
 assert np.max(abs(np.maximum(0,100*(selected.objective-selected.reference_objective)/selected.reference_objective)-selected.regret_pct))<1e-12
 assert selected.groupby(['scenario_id','path_label']).sequence.nunique().eq(1).all(),'A fixed original path changed between precision tiers'
 sa=selected[selected.path_label=='SA_original_fixed_seed'];assert sa.original_seed.notna().all() and sa.groupby('scenario_id').original_seed.nunique().eq(1).all()
 summary=d['scenario_seed_summaries.csv'];assert len(summary[summary.phase=='query_cap'])==240
 R2=d['Table_R2_method_summary.csv'];assert len(R2[R2.phase=='query_cap'])==8
 dump(a/'analysis_protocol.json',spec);csv(a/'method_replicate_integrity.csv',counts)
 dump(a/'G0_gate.json',{'status':'PASS','at':now(),'all_source_CRCs_valid':True,'source_rows':2250,'query_cap_rows':1590,'time_cap_excluded':660,'independent_new_scenarios':30,'historical_method_precision_rows':40,'other_historical_path_rows_not_selected':len(old)-40,'frozen_kappa':kappa,'regret_unit':'percent','algorithm_imports_or_runs':0,'model_reads':'hash bytes only; no deserialization or predictions'})
 check_immutable(out);print('S0 G0 PASS: 1590 query_cap rows; 40 legacy method/precision rows',flush=True)
