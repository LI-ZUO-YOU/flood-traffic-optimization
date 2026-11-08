from s4_common import *
def main():
 kind=sys.argv[1];sid=int(sys.argv[2]);m=int(sys.argv[3]);method=sys.argv[4];rep=int(sys.argv[5]);folder=Path(sys.argv[6]);folder.mkdir(parents=True,exist_ok=True)
 pin();ph,roads,audit,fixture=physical(sid,m);assert not fixture and connected(ph)
 setup=time.perf_counter();wn=frozen.Network(frozen.MODEL);dev,devroads=warm(wn);del wn
 predictor=None
 if method=='proposed':
  import torch
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  predictor=frozen.api.SurrogateV2(frozen.SOURCE/'surrogate/final_ensemble')
  A.gen.subset_member_losses(predictor,dev.depth_m.to_numpy(float),dev.is_closed.to_numpy(np.uint8),list(devroads))
 setupwall=time.perf_counter()-setup;net=TimedNetwork(folder);q=None;stats={};ls={'inclusive':0.,'UE_nested':0.,'calls':0};greedy=[];last_engine=[]
 base=A.SharedCorrection;original_greedy=A.greedy
 class TimedCorrection(base):
  def __init__(self,*args,**kw):super().__init__(*args,**kw);last_engine.append(self)
  def local_search(self,*args,**kw):
   t=time.perf_counter();u=net.wall
   try:return super().local_search(*args,**kw)
   finally:ls['inclusive']+=time.perf_counter()-t;ls['UE_nested']+=net.wall-u;ls['calls']+=1
 def timed_greedy(*args,**kw):
  t=time.perf_counter();before=args[0].used;r=original_greedy(*args,**kw);greedy.append({'before':before,'after':args[0].used,'wall':time.perf_counter()-t});return r
 A.SharedCorrection=TimedCorrection;A.greedy=timed_greedy
 start=time.perf_counter();net.deadline=start+protocol()['max_task_seconds'];cpu0=psutil.Process().cpu_times();began=now()
 dump(folder/'ready.json',{'started_perf_counter':start,'started_at':began,'pid':os.getpid(),'core':0,'threads':1,'setup_and_prewarm_excluded_s':setupwall,'RSS_baseline_bytes':psutil.Process().memory_info().rss,'fresh_physical_cache':True,'read_full_reference_before_search':False})
 value=None;sequence=None;status='PASS';error=None;dpwall=0.;candidatewall=0.;details={};rows=[]
 try:
  if kind=='optimization':
   store=A.PhysicalStore(net,ph,roads,db=None,target=1e-9);assert not store.cache;q=A.QueryOracle(store,budget=256,time_limit=None)
   def check():
    if time.perf_counter()>net.deadline:raise TaskLimit('TASK_TIME_LIMIT')
   q.check=check
   screen=None
   if method=='proposed':
    t=time.perf_counter();screen,stats=build(ph,roads,audit,sid,rep,predictor,folder=None);candidatewall=time.perf_counter()-t
   details=A.run_method(method,q,roads,sid,rep,screen,CFG['selected_configurations'].get(method));value=q.best;sequence=q.best_seq;rows=q.rows
   assert q.used<=256 and q.cache_hits==0 and q.used==net.calls
   if method in ['greedy_ils','ue_bibeam']:assert greedy[0]['after']==m*(m+1)//2
  elif kind=='enum_serial':
   rows=[net.solve(ph,roads,mask,1e-9) for mask in range(1<<m)]
   t=time.perf_counter();value,sequence=exact_dp({r['subset_mask']:r['loss'] for r in rows},roads);dpwall=time.perf_counter()-t
  else:raise ValueError(kind)
  if time.perf_counter()>net.deadline:raise TaskLimit('TASK_TIME_LIMIT_AT_END')
 except BaseException as e:
  status='SCALING_FAILURE';error={'type':type(e).__name__,'reason':str(e),'traceback':traceback.format_exc()}
  if q is not None:value=q.best;sequence=q.best_seq;rows=q.rows
 stop=time.perf_counter();cpu1=psutil.Process().cpu_times();net.close()
 dump(folder/'timing_stopped.json',{'stopped_perf_counter':stop,'online_seconds':stop-start,'status':status,'finished_at':now()})
 result={'scenario_id':sid,'m':m,'method':method,'replicate':rep,'status':status,'error':error,'target_objective':value,'target_hex':float(value).hex() if value is not None else None,'sequence':list(sequence) if sequence is not None else None,
  'UE_queries':q.used if q is not None else net.calls,'UE_attempts':net.attempts,'actual_physical_calls':net.calls,'logical_requests':q.requests if q is not None else net.calls,'physical_cache_hits':q.cache_hits if q is not None else 0,
  'online_wall':stop-start,'candidate_wall_inclusive':candidatewall,'inference_wall_nested':stats.get('surrogate_inference_seconds',0.),'proxy_DP_wall_nested':stats.get('policy_wall',0.),'reference_DP_wall':dpwall,
  'UE_wall':net.wall,'LS_wall_inclusive':ls['inclusive'],'LS_UE_wall_nested':ls['UE_nested'],'LS_wall_excluding_UE':max(0.,ls['inclusive']-ls['UE_nested']),
  'CPU_work_seconds':cpu1.user+cpu1.system-cpu0.user-cpu0.system,'greedy_initial_query_count':greedy[0]['after'] if greedy else None,'greedy_initial_wall':greedy[0]['wall'] if greedy else None,
  'greedy_calls':len(greedy),'LS_unique_queries':sum(r['phase']=='D_local_search' for r in q.rows) if q else None,'LS_new_query_fraction':sum(r['phase']=='D_local_search' for r in q.rows)/q.used if q and q.used else None,
  'started_at':began,'finished_at':now(),'core':0,'processes':1,'threads':1,'cap_seconds':protocol()['max_task_seconds'],'B':256 if q else 1<<m,'B_over_full_states':256/(1<<m) if q else 1.,'seed_index':rep,'natural_termination':q.termination if q is not None else None,
  'setup_and_prewarm_excluded_s':setupwall,'max_RG':max([r['relative_gap'] for r in rows],default=None),'complete_reference':kind=='enum_serial' and status=='PASS' and net.calls==1<<m,
  'search_details':details,'frozen_input_and_code_unchanged':True}
 result['candidate_wall_excluding_inference_and_DP']=max(0.,candidatewall-result['inference_wall_nested']-result['proxy_DP_wall_nested'])
 result['other_search_and_journal_wall']=result['online_wall']-candidatewall-net.wall-result['LS_wall_excluding_UE']-dpwall
 assert result['other_search_and_journal_wall']>=-1e-6
 # S3 hashes are inspected only after the new search and timing have ended.
 if method=='proposed' and status=='PASS':
  old=js(SCALE/f'03_component_scaling/runs/scenario_{sid}/m_{m:02d}/repeat_{rep:02d}/result.json')
  gate={'candidate_order_SHA':stats['candidate_order_sha256']==old['candidate_order_sha256'],'surrogate_matrix_SHA':stats['surrogate_matrix_SHA']==old['surrogate_matrix_SHA'],'source_quotas':stats['source_counts']==old['source_counts']}
  result['S3_reproduction_gate']=gate
  if not all(gate.values()):result['status']='REPRODUCTION_GATE_FAILURE';result['error']={'reason':str(gate)}
 if stats:
  stats.pop('prefix_rows',None);result['candidate_report']=stats
 if q is not None:
  q.save(folder,method,rep,sid,{'authoritative_online_seconds':result['online_wall'],'S4_status':result['status'],'no_full_reference_read':True})
  if last_engine:
   e=last_engine[-1]
   csv(folder/'complete_sequence_evaluations.csv.gz',e.result_rows);csv(folder/'local_search_evaluations.csv.gz',e.local_rows)
  csv(folder/'UE_query_phase_counts.csv',[{'phase':p,'unique_queries':sum(r['phase']==p for r in q.rows)} for p in dict.fromkeys(r['phase'] for r in q.rows)])
 else:
  journal=frame(folder/'physical_UE_journal.csv');csv(folder/'all_states.csv.gz',journal)
 dump(folder/'timing.json',result);A.SharedCorrection=base;A.greedy=original_greedy
 print(json.dumps({k:result[k] for k in ['scenario_id','m','method','replicate','status','online_wall','UE_queries','max_RG']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
