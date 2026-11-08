"""Fresh-cache live deployment around immutable v2 candidate/search definitions."""
from s3_prepare import *
import candidate_factory as CF
from predictor_adapters import predictor,subset_states
from search_adapter import LedgerOracle,InstrumentedCorrection,run_search,save_ledgers
import traceback

STATE={'phase':'setup','variant':None,'path':None,'model_reads':[],'denials':[]}

class PredictionAudit:
 def __init__(self,model):self.model=model;self.calls=0
 def predict_members(self,states):self.calls+=1;return self.model.predict_members(states)

def install_guard():
 def hook(event,args):
  if event!='open' or STATE['phase']!='online':return
  try:p=os.path.abspath(os.fsdecode(args[0])).lower().replace('\\','/')
  except (TypeError,ValueError):return
  root=str(ROOT).lower().replace('\\','/');out=str(OUT).lower().replace('\\','/')
  forbidden=(p.startswith(root+'/') and not p.startswith((root+'/code/',root+'/source_snapshot/')))
  forbidden=forbidden or str(HOME).lower().replace('\\','/') in p or '/revision_4_4_scaling/' in p or '/reviewer_4_2/' in p or '/reviewer_4_3/' in p
  allowed=[out+'/code/',out+'/protocol/',out+'/00_audit/public_inputs/',out+'/01_freeze_and_regression/simple_models/',out+'/runtime_cache/']
  if STATE['path']:allowed.append(str(STATE['path']).lower().replace('\\','/')+'/')
  if p.startswith(out+'/') and not any(p.startswith(x) for x in allowed):forbidden=True
  model='/surrogate/' in p or p.endswith('.joblib')
  if model:
   STATE['model_reads'].append(p)
   if STATE['variant']=='F9_NO_SURROGATE' or STATE['variant']=='Greedy-ILS':forbidden=True
  if forbidden:
   STATE['denials'].append({'path':p,'mode':str(args[1]),'at':now()});raise PermissionError('S3 live search information firewall')
 sys.addaudithook(hook)

class FreshTimedStore(E.PhysicalStore):
 def __init__(self,net,physical,roads):
  super().__init__(net,physical,roads,target=1e-9);self.network_seconds=0.0;self.last_network_seconds=0.0
 def request(self,mask):
  before=time.perf_counter();answer=super().request(mask);elapsed=time.perf_counter()-before
  self.last_network_seconds=0.0 if answer[1] else elapsed
  if not answer[1]:self.network_seconds+=elapsed
  return answer

class LiveOracle(LedgerOracle):
 def __init__(self,store,sid,variant,rep,roads,pool=None):
  super().__init__(store,sid,variant,rep);self.store_stats=store;self.roads=roads;self.observed_sequences=set();self.complete_history=[];self.blocks=[];self.last_phase=None;self.peak_rss=psutil.Process().memory_info().rss
  self.candidate_ids={} if pool is None else dict(zip(pool.sequence,pool.candidate_id))
 def request(self,mask,phase='search',reason=''):
  if phase!=self.last_phase:
   if self.blocks:self.blocks[-1].update(end_queries=self.used,end_best_J=self.best)
   self.blocks.append({'phase':phase,'start_queries':self.used,'start_best_J':self.best});self.last_phase=phase
  hit=int(mask) in self.known;row=super().request(mask,phase,reason);log=self.request_rows[-1]
  log.update(solver_seconds=0.0 if hit else float(row['solver_seconds']),historical_solver_seconds=None,UE_network_call_seconds=0.0 if hit else self.store_stats.last_network_seconds)
  if self.requests%64==0:self.peak_rss=max(self.peak_rss,psutil.Process().memory_info().rss)
  return row
 def observe(self,sequence,value):
  before=self.best;fresh=tuple(sequence) not in self.observed_sequences;super().observe(sequence,value)
  if fresh:
   self.observed_sequences.add(tuple(sequence));seq='|'.join(map(str,sequence));last=self.request_rows[-10:]
   assert len(last)==10 and [x['mask'] for x in last]==E.masks(sequence,self.roads)
   cid=self.candidate_ids.get(seq,E.original.sequence_id(sequence));sid=E.original.sequence_id(sequence)
   for x in last:
    if x['sequence_id'] is None:x['sequence_id']=sid;x['candidate_id']=cid
   self.complete_history.append({'sequence_id':sid,'candidate_id':cid,'sequence':seq,'phase':last[-1]['phase'],'completion_budget':self.used,'complete_J':float(value),'incumbent_before':before,'incumbent_after':self.best,'new_unique_UE_states':sum(not x['cache_hit'] for x in last),'incumbent_update':before is None or self.best<before,'final_is_incumbent':False})

def run_baseline(q,roads,sid,rep):
 old=E.SharedCorrection;capture={}
 def factory(*a,**kw):capture['engine']=InstrumentedCorrection(*a,**kw);return capture['engine']
 E.SharedCorrection=factory
 try:E.run_method('greedy_ils',q,roads,sid,rep,config=CFG.get('selected_configurations',{}).get('greedy_ils'))
 finally:E.SharedCorrection=old
 return capture['engine']

def run_task(net,model_cache,sid,variant,rep):
 path=RUNS/f'scenario_{sid}/{variant}/seed_{rep:02d}';require_new_output(path)
 STATE.update(phase='online',variant=variant,path=path,model_reads=[],denials=[])
 q=None;store=None;engine=None;pool=None;screened=None;report={};success=False;timing={};error=None
 try:
  t=time.perf_counter();ph,roads,audit=public_scenario(sid);timing['initial_input_load_seconds']=time.perf_counter()-t
  t=time.perf_counter()
  if variant in {'F9_NO_SURROGATE','Greedy-ILS'}:model=None
  else:
   key=variant if variant in CF.SINGLE else 'F0_FULL'
   if key not in model_cache:
    model_cache[key]=predictor(key)
    dev,droads,_=public_scenario(246);model_cache[key].predict_members(subset_states(dev,droads))
   model=model_cache[key]
  timing['model_load_and_development_inference_warmup_seconds']=time.perf_counter()-t
  prediction_audit=None if model is None else PredictionAudit(model)
  old_predictor=CF.predictor;old_public=CF.public_scenario
  CF.predictor=lambda v:prediction_audit;CF.public_scenario=lambda s:(ph,roads,audit)
  online_start=time.perf_counter();candidate_start=online_start
  try:
   if variant!='Greedy-ILS':roads,pool,screened,report=CF.build(sid,rep,variant)
  finally:CF.predictor=old_predictor;CF.public_scenario=old_public
  candidate_end=time.perf_counter();store=FreshTimedStore(net,ph,roads);q=LiveOracle(store,sid,variant,rep,roads,pool)
  old_ls=InstrumentedCorrection.local_search
  def measured_ls(self,target_calls):
   ue_before=store.network_seconds;t=time.perf_counter()
   try:return old_ls(self,target_calls)
   finally:
    if self.ls_calls:
     elapsed=time.perf_counter()-t;du=store.network_seconds-ue_before;self.ls_calls[-1].update(UE_network_call_seconds=du,non_UE_seconds=max(0.0,elapsed-du))
  InstrumentedCorrection.local_search=measured_ls
  try:engine=run_baseline(q,roads,sid,rep) if variant=='Greedy-ILS' else run_search(q,roads,sid,rep,variant,screened)
  finally:InstrumentedCorrection.local_search=old_ls
  end=time.perf_counter();ls_non=sum(x.get('non_UE_seconds',0) for x in engine.ls_calls)
  timing.update(fresh_online_seconds=end-online_start,candidate_prepare_seconds=candidate_end-candidate_start,search_including_UE_seconds=end-candidate_end,surrogate_inference_seconds=report.get('surrogate_inference_seconds',0.0),UE_network_call_seconds=store.network_seconds,UE_kernel_seconds=store.solve_seconds,LS_non_UE_seconds=ls_non,search_other_bookkeeping_seconds=max(0.0,end-candidate_end-store.network_seconds-ls_non),peak_RSS_bytes=q.peak_rss)
  report['surrogate_inference_calls']=prediction_audit.calls if prediction_audit else 0
  assert q.used<=256 and store.solves==q.used and store.connection is None
  assert not STATE['denials']
  if variant in {'F9_NO_SURROGATE','Greedy-ILS'}:assert not STATE['model_reads'] and model is None
  if variant=='F3_NO_DISAG':assert report['primary_channels'].get('ensemble_disagreement',0)==0 and report['primary_channels']['proxy_top']==25
  if variant=='F1_NO_RESERVE':assert report['reserve_count']==0 and report['flat_eligible_count']==29940
  success=True
 except Exception as e:error={'error':repr(e),'traceback':traceback.format_exc()}
 finally:
  STATE['phase']='export'
  if q is not None and q.best is not None:
   # No complete reference has been created or read; all data below are method-visible queries.
   extra={'variant_id':variant,'roads':roads,'backend':'fresh_live_UE','live_UE_calls':store.solves,'fresh_cache':True,'cpu_core':0,'threads':1,'time_cap_seconds':None,'status':'PASS' if success else 'FAIL','model_file_reads':sorted(set(STATE['model_reads'])),'reference_access_denials':STATE['denials'],**report,**timing}
   q.save(path,'greedy_ils' if variant=='Greedy-ILS' else 'proposed',rep,sid,extra)
   if engine is not None:
    if q.blocks:q.blocks[-1].update(end_queries=q.used,end_best_J=q.best)
    engine.phase_blocks=q.blocks;engine.complete_rows=q.complete_history
    for x in engine.complete_rows:x['final_is_incumbent']=x['sequence']=='|'.join(map(str,q.best_seq))
    save_ledgers(path,q,engine)
   else:csv(path/'partial_request_ledger.csv.gz',q.request_rows)
  elif store is not None:csv(path/'partial_physical_states.csv.gz',list(store.cache.values()))
  if pool is not None:
   csv(path/'candidate_pool.csv.gz',pool);csv(path/'screened_candidates.csv.gz',screened)
   prefix_fallback=int((pool.source_detail=='supplemental_random_tail').sum())
   logs=[{'source':'prefix_stratified','random_completion_count':prefix_fallback,'count_kind':'accepted supplemental candidates'}]+report.get('fallback_log',[])
   csv(path/'source_fallback_records.csv',logs)
  dump(path/'timing.json',{**timing,'scope':'fresh-cache live online; input/model warmup and disk exports excluded; nested fields must not be added twice','training_seconds_in_online':0.0,'training_cost_separately_reported':True})
  dump(path/'validation.json',{'status':'PASS' if success else 'FAIL','scenario_id':sid,'variant_id':variant,'seed_index':rep,'actual_queries':q.used if q else 0,'at':now(),'v2_protocol_sha256':EXPECTED,'no_reference_access':not STATE['denials'],'model_file_reads':sorted(set(STATE['model_reads'])),'failure':error})
  dump(path/'pre_reference_manifest.json',{'at':now(),'status':'PASS' if success else 'FAIL','scenario_id':sid,'variant_id':variant,'seed_index':rep,'files':{f.name:{'sha256':sha(f),'bytes':f.stat().st_size} for f in path.iterdir() if f.is_file()},'v2_protocol_sha256':EXPECTED,'reference_created_or_read':False})
  if store:store.close()
 return success,path

def run_all():
 core_check();assert not REF.exists();pin();install_guard()
 net=E.Network(E.MODEL);dev,roads,_=public_scenario(246);t=time.perf_counter();net.solve(dev,roads,0,1e-9)
 dump(CONTROL/'UE_development_warmup.json',{'scenario':246,'mask':0,'target':1e-9,'seconds':time.perf_counter()-t,'excluded_from_online':True,'new_scenario_UE_before_online':False,'CPU_affinity':psutil.Process().cpu_affinity()})
 cache={};methods=VARIANTS+['Greedy-ILS'];rows=[]
 for i,sid in enumerate(range(5101,5111)):
  for rep in range(3):
   offset=(i+rep)%len(methods);order=methods[offset:]+methods[:offset]
   for variant in order:
    core_check();ok,path=run_task(net,cache,sid,variant,rep);rows.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,'status':'PASS' if ok else 'FAIL','path':str(path),'at':now()})
    csv(CONTROL/'task_index.csv',rows);dump(CONTROL/'progress.json',{'stage':'online','attempted':len(rows),'planned':330,'passed':sum(x['status']=='PASS' for x in rows),'failed':sum(x['status']=='FAIL' for x in rows),'current':rows[-1],'at':now()})
    print(json.dumps({'event':'task_complete',**rows[-1],'completed':len(rows),'planned':330},ensure_ascii=False),flush=True)
 assert len(rows)==330
 manifests=[Path(x['path'])/'pre_reference_manifest.json' for x in rows]
 dump(CONTROL/'all_330_method_outputs_frozen.json',{'status':'ALL_TASK_RECORDS_FROZEN_BEFORE_REFERENCE','at':now(),'task_records':330,'passed':sum(x['status']=='PASS' for x in rows),'failed':sum(x['status']=='FAIL' for x in rows),'v2_protocol_sha256':EXPECTED,'files':{str(p):sha(p) for p in manifests},'no_task_or_scenario_replacement':True})
 STATE['phase']='reference'
 return rows,net
