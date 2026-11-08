"""S3 non-tuning checks and original-generator deployment. Frozen v2 is read-only."""
from common45 import *
EXPECTED='dc7602d9d6819805b0fc402f77bd1e96fc742c11fb2c2444b41db82dd176808e'
CONTROL=OUT/'03_S3_control'
NEW=OUT/'03_new_scenarios'
RUNS=OUT/'04_method_runs_pre_reference'
REF=OUT/'05_reference_after_freeze'
DELIVERY=OUT/'08_S3_delivery'

def core_check():
 assert sha(OUT/'protocol/frozen_protocol.json')==EXPECTED
 for p,e in js(OUT/'protocol/freeze_manifest.json')['files'].items():assert sha(p)==e['sha256'],p

def preflight():
 require_new_output(CONTROL);core_check();verify_sources();rows=[]
 for sid in [3001,3002,3003]:
  base=OUT/f'02_smoke_old_scenarios/scenario_{sid}'
  f=frame(base/'F3_NO_DISAG/seed_00/screened_candidates.csv.gz');p=f[f.screening_tier=='primary_shortlist']
  assert p.channel.value_counts().to_dict()=={'proxy_top':25,'sequence_diversity':15,'heuristic':10,'random':10}
  f=frame(base/'F1_NO_RESERVE/seed_00/screened_candidates.csv.gz');q=frame(base/'F1_NO_RESERVE/seed_00/request_ledger.csv.gz')
  assert len(f)==30000 and not (f.screening_tier=='structural_reserve').any() and (q.reason.str.contains('flat_proxy_order')).any()
  for variant in ['F6_SINGLE_MLP','F7_RIDGE','F8_TREE']:
   r=js(base/f'{variant}/seed_00/result.json');pool=frame(base/f'{variant}/seed_00/candidate_pool.csv.gz')
   assert {x['source'] for x in r['fallback_log']}=={'proxy_subset_dp','proxy_ga_local'}
   for x in r['fallback_log']:
    assert x['random_completion_count']>=0 and x['mutation_attempts']<=50000
    rows.append({'scenario_id':sid,'variant_id':variant,**x})
   rows.append({'scenario_id':sid,'variant_id':variant,'source':'prefix_stratified','mutation_attempts':None,'random_completion_count':int((pool.source_detail=='supplemental_random_tail').sum()),'count_provenance':'source_detail in frozen pool; count of accepted supplemental candidates'})
  r=js(base/'F9_NO_SURROGATE/seed_00/result.json');fw=js(base/'F9_NO_SURROGATE/seed_00/firewall.json');pool=frame(base/'F9_NO_SURROGATE/seed_00/candidate_pool.csv.gz')
  assert not fw['model_reads'] and not r['surrogate_loaded'] and r['proxy_dp_policies']==0 and pool.proxy_objective_mean.isna().all()
 csv(CONTROL/'preflight_fallback_records.csv',rows)
 dump(CONTROL/'preflight_validation.json',{'status':'PASS','at':now(),'v2_sha256':EXPECTED,'F3_no_disagreement_seats':True,'F1_flat_mechanism':True,'F6_F8_fallback_records':True,'F9_no_model_or_predictions':True,'new_optimization_or_tuning_runs':0,'original_files_unchanged':True,'user_authorization':'S0-S2 accepted; execute S3 only,330 tasks, then Chinese report and numbers'})

def freeze_deployment():
 core_check();files={}
 for name in ['s3_prepare.py','s3_live.py','s3_finish.py','s3_run.py']:
  p=OUT/'code'/name;files[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
 for p in sorted(E.MODEL.rglob('*.py')):files[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
 for name in ['physical_links.csv','directed_links.csv','od_long.csv']:
  p=E.MODEL/'data_src/SiouxFalls_flood_benchmark/processed'/name;files[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
 dump(CONTROL/'S3_deployment_freeze.json',{'at':now(),'v2_protocol_sha256':EXPECTED,'frozen_definitions_modified':False,'files':files,'scope':'330 fresh-cache live UE tasks, then full1024-state references and requested descriptive CSV only','primary_order':'scenario ascending; seed0/1/2; cyclic rotation of eleven methods by (scenario_index+seed_index) modulo11','execution':'single process CPU0 threads1; no concurrent scientific tasks; no time cap','online_scope':'candidate preparation+search bookkeeping+fresh UE calls; input/model loading, development warm-up and disk exports separately measured and excluded','preloaded_model_reuse':'read-only frozen predictor object; equivalent calls and weights; F9 receives None and cannot read model files or invoke predictions','reference_rule':'all330 task records frozen before first new-scenario complete-state enumeration; reference recomputes all1024 states independently, no optimization rerun','failures':'retain all failed tasks and partial ledgers; no replacement scenarios/seeds/models; explicit denominators','later_analyses_not_in_this_batch':['900 retrospective runs','common-pool model scoring diagnostics','bootstrap/significance tests','manuscript or English response','retuning or third-batch expansion']})

def generate():
 assert (CONTROL/'S3_deployment_freeze.json').is_file();core_check()
 gen=E.load_module('s3_original_holdout_generator',E.FORMAL/'generate_final_holdout.py')
 spec=js(E.SOURCE/'config/final_protocol_v1.1.json');spec['status']='FROZEN_BEFORE_FINAL_SCENARIO_GENERATION'
 spec['final_scenario_generation'].update(formal_final_scenario_count=10,scenario_id_range=[5101,5110],scenario_seed=2026102905,severity='severe')
 protocol=CONTROL/'scenario_generator_protocol.json';dump(protocol,spec);hp=CONTROL/'scenario_generator_protocol.sha256';hp.write_text(sha(protocol)+'\n',encoding='ascii')
 prior=[ROOT/'inputs'/n for n in ['historical_1_120.csv','historical_network_source.csv','historical_201_260.csv','historical_121_160.csv','historical_1001_1010.csv','engineering_batch_2001_2030.csv']]
 prior.append(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv')
 s4=OUT.parent/'revision_4_4_scaling/04_method_scaling/S4_20261029/analysis/S4_frozen_physical_inputs.csv'
 s4f=frame(s4);assert set(range(4401,4407))<=set(s4f.scenario_id.astype(int))
 s4f=s4f.drop_duplicates(['scenario_id','physical_link_id']);assert all(len(g)==38 for _,g in s4f.groupby('scenario_id'))
 # Original physical-only S4 export; no optimization labels are passed to generator.
 s4copy=CONTROL/'dedup_4401_4406_physical.csv';csv(s4copy,s4f);prior.append(s4copy)
 assert all(p.is_file() for p in prior)
 old=sys.argv;sys.argv=['generate_final_holdout','--protocol',str(protocol),'--protocol-hash-file',str(hp),'--model-root',str(E.MODEL),'--output-dir',str(NEW)]
 for p in prior:sys.argv+=['--prior-scenario-file',str(p)]
 try:gen.main()
 finally:sys.argv=old
 # Preserve the original generator output and its hashes; public exports use round-trip floats.
 data=frame(NEW/'final_scenarios_physical_links.csv');roads_meta={}
 for sid,ph in data.groupby('scenario_id',sort=True):
  ph=ph.sort_values('physical_link_id');roads,audit=E.select_roads(ph)
  assert len(roads)==10 and all(ph.set_index('physical_link_id').loc[r,'is_closed']==1 for r in roads)
  csv(NEW/f'road_selection_{sid}.csv',audit)
  for name,f in [(f'scenario_{sid}.csv',ph),(f'road_audit_{sid}.csv',audit)]:
   target=OUT/'00_audit/public_inputs'/name;assert not target.exists();csv(target,f)
  target=OUT/f'00_audit/public_inputs/scenario_{sid}.json';assert not target.exists();dump(target,{'scenario_id':int(sid),'roads':roads,'labels_present':False})
  roads_meta[str(sid)]={'roads':roads,'closed_count':int(ph.is_closed.sum())}
 dump(NEW/'selected_roads.json',roads_meta)
 files=list(NEW.glob('*'))+[OUT/'00_audit/public_inputs'/f'{prefix}{sid}.{ext}' for sid in range(5101,5111) for prefix,ext in [('scenario_','csv'),('scenario_','json'),('road_audit_','csv')]]
 dump(CONTROL/'all_new_inputs_frozen.json',{'at':now(),'v2_protocol_sha256':EXPECTED,'deployment_freeze_sha256':sha(CONTROL/'S3_deployment_freeze.json'),'files':{str(p):sha(p) for p in files if p.is_file()},'scenario_ids':list(range(5101,5111)),'before_all_optimization':True})
 print(json.dumps({'event':'generation_complete','accepted':10,'seed':2026102905,'at':now()}),flush=True)
