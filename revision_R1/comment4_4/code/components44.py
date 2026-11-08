from common44 import *
import itertools,math
import methods_generalized as adapt
gen=adapt.gen
class DimensionalFailure(RuntimeError):pass
def balanced_prefixes(roads,rng):
 n=len(roads)
 bases=list(itertools.permutations(range(1,n),3))
 for k in rng.permutation(len(bases)):
  base=(0,)+bases[int(k)];offset=int(rng.integers(n))
  for t in range(n):yield tuple(roads[(v+t+offset)%n] for v in base)
def adapted_prefix(registry,roads,mean_policy,member_policies,rng,counter,stats):
 target=16000;added=0;prefix_rows=[];attempts=0
 for index,prefix in enumerate(balanced_prefixes(roads,rng)):
  used=0
  # Preserve original mean/member/random completion ordering and member rotation.
  candidates=[(gen.complete_by_policy(prefix,roads,mean_policy),'balanced_prefix4_mean_dp_tail'),
   (gen.complete_by_policy(prefix,roads,member_policies[index%10]),'balanced_prefix4_member_dp_tail'),
   (gen.random_completion(prefix,roads,rng),'balanced_prefix4_random_tail')]
  for seq,detail in candidates:
   attempts+=1;ok,counter=gen.add_unique(registry,seq,'prefix_stratified',detail,counter);added+=int(ok);used+=1
   if added==target:break
  prefix_rows.append({'prefix_index':index,'prefix':'|'.join(map(str,prefix)),'attempted_tails':used,'cumulative_unique_source':added})
  if added==target:break
 if added!=target:raise DimensionalFailure('All balanced prefix4 orbits exhausted without quota')
 stats['prefix_rows']=prefix_rows;stats['prefix4_visited']=len(prefix_rows);stats['prefix_tail_attempts']=attempts
 return counter

def build(physical,roads,audit,sid,rep,predictor,folder=None):
 start=time.perf_counter();stats={'m':len(roads),'scenario_id':sid,'replicate':rep,'stage':'start','policy_calls':0,'policy_wall':0.,'DP_by_phase':{},'components':{},'new_UE_calls':0}
 def progress(stage):
  stats['stage']=stage;stats['elapsed_partial']=time.perf_counter()-start
  if folder:dump(Path(folder)/'progress.json',{k:v for k,v in stats.items() if k!='prefix_rows'})
 seed=2026080702+sid+1000000*rep;rng=np.random.default_rng(seed);stats['candidate_seed']=seed;stats['screening_seed']=2026080703+sid+1000000*rep
 dp=gen.successor_policy;pred=predictor.predict_members;transform=predictor.transform
 phase='initial';transform_wall=0.;predict_wall=0.;dp_rows=[]
 def timed_transform(states):
  nonlocal transform_wall
  t=time.perf_counter();x=transform(states);transform_wall+=time.perf_counter()-t;return x
 def timed_predict(states):
  nonlocal predict_wall
  t=time.perf_counter();x=pred(states);predict_wall+=time.perf_counter()-t;return x
 def timed_dp(cost,r):
  t=time.perf_counter();p=dp(cost,r);duration=time.perf_counter()-t
  stats['policy_calls']+=1;stats['policy_wall']+=duration;dp_rows.append({'policy_index':stats['policy_calls'],'phase':phase,'wall':duration})
  if stats['policy_calls']%10==0:progress('DP_'+phase)
  return p
 gen.successor_policy=timed_dp;predictor.predict_members=timed_predict;predictor.transform=timed_transform
 try:
  progress('full_surrogate_state_matrix');t=time.perf_counter()
  member_loss=gen.subset_member_losses(predictor,physical.depth_m.to_numpy(float),physical.is_closed.to_numpy(np.uint8),list(roads))
  state_total=time.perf_counter()-t
  stats['components'].update({'mask_and_restored_state_build_wall':max(0,state_total-predict_wall),'feature_transform_wall':transform_wall,'ensemble_forward_wall':max(0,predict_wall-transform_wall),'subset_all_inclusive_wall':state_total})
  stats.update({'surrogate_shape':list(member_loss.shape),'inference_batch_size':1<<len(roads),'prediction_matrix_bytes':member_loss.nbytes})
  objective=gen.ProxyObjective(member_loss,list(roads));progress('initial_DP_policies');t=time.perf_counter()
  phase='mean';mean=gen.successor_policy(member_loss.mean(axis=1),list(roads));phase='initial_member';members=[gen.successor_policy(member_loss[:,i],list(roads)) for i in range(10)]
  stats['components']['initial_policies_wall']=time.perf_counter()-t
  registry={};counter=0;progress('prefix_candidates');t=time.perf_counter()
  if len(roads)<=10:
   counter=gen.fill_prefix_stratified(registry,list(roads),mean,members,rng,counter)
   stats['prefix4_visited']=math.perm(len(roads),4);stats['prefix_tail_attempts']=3*math.perm(len(roads),4)
  else:counter=adapted_prefix(registry,list(roads),mean,members,rng,counter,stats)
  stats['components']['prefix_generation_wall']=time.perf_counter()-t
  progress('proxy_DP_source');t=time.perf_counter();phase='proxy_source_10_members_4_SD_64_mixtures'
  counter=gen.fill_proxy_dp(registry,list(roads),member_loss,mean,rng,counter)
  stats['components']['proxy_DP_source_inclusive_wall']=time.perf_counter()-t
  for name,fn,args in [('diversity',gen.fill_diversity,(seed,)),('random',gen.fill_random,(rng,))]:
   progress(name+'_source');t=time.perf_counter();counter=fn(registry,list(roads),*args,counter);stats['components'][name+'_source_wall']=time.perf_counter()-t
  progress('GA_local_source');t=time.perf_counter();gen.fill_ga_local_from_registry(registry,objective,list(roads),rng,counter);stats['components']['GA_local_source_wall']=time.perf_counter()-t
  assert len(registry)==30000
  progress('candidate_evaluation_frame');t=time.perf_counter()
  pool=pd.DataFrame([gen.candidate_row(sid,s,meta,objective) for s,meta in registry.items()]);pool=pool.sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').reset_index(drop=True);pool['proxy_rank']=np.arange(1,len(pool)+1)
  stats['components']['candidate_evaluation_sort_wall']=time.perf_counter()-t
  progress('primary_screening');t=time.perf_counter();short=adapt.primary.select_scenario(pool,list(roads),audit,np.random.default_rng(stats['screening_seed']));stats['components']['primary_screening_wall']=time.perf_counter()-t
  short['screening_tier']='primary_shortlist';short['prefix_2']=short.sequence.str.split('|').map(lambda v:'|'.join(v[:2]));short['prefix_3']=short.sequence.str.split('|').map(lambda v:'|'.join(v[:3]))
  progress('structural_reserve');t=time.perf_counter();res=adapt.reserve.structural_reserve(pool,set(short.candidate_id));screen=pd.concat([short,res],ignore_index=True,sort=False);screen=screen.sort_values(['screening_tier','channel','channel_rank','candidate_id'],kind='mergesort').reset_index(drop=True);stats['components']['reserve_and_final_sort_wall']=time.perf_counter()-t
  end=time.perf_counter();stats.update({'status':'PASS','stage':'complete','candidate_count':len(pool),'primary_count':len(short),'reserve_count':len(res),'source_counts':dict(pool.primary_source.value_counts()),'candidate_wall':end-start,'surrogate_inference_seconds':predict_wall,'candidate_order_sha256':hashlib.sha256('\n'.join(pool.candidate_id).encode()).hexdigest(),'surrogate_matrix_SHA':hashlib.sha256(member_loss.tobytes()).hexdigest()})
  stats['pool_prefix4_unique']=pool.sequence.str.split('|').map(lambda s:tuple(s[:4])).nunique();stats['prefix_source_prefix4_unique']=pool.loc[pool.primary_source=='prefix_stratified','sequence'].str.split('|').map(lambda s:tuple(s[:4])).nunique();stats['prefix_visited_fraction']=stats['prefix4_visited']/math.perm(len(roads),4)
  stats['DP_by_phase']={p:{'calls':sum(r['phase']==p for r in dp_rows),'wall':sum(r['wall'] for r in dp_rows if r['phase']==p)} for p in dict.fromkeys(r['phase'] for r in dp_rows)}
  progress('complete')
  if folder:
   folder=Path(folder);export=time.perf_counter();csv(folder/'candidate_pool.csv.gz',pool);csv(folder/'screened_candidates.csv.gz',screen);csv(folder/'DP_policy_timings.csv',dp_rows)
   if stats.get('prefix_rows'):csv(folder/'prefix_sampling_trace.csv.gz',stats.pop('prefix_rows'))
   stats['candidate_file_bytes']=(folder/'candidate_pool.csv.gz').stat().st_size;stats['export_wall_excluded']=time.perf_counter()-export
   progress('export_complete')
  return screen,stats
 finally:gen.successor_policy=dp;predictor.predict_members=pred;predictor.transform=transform

def install_search_dimensions():
 # Frozen correction local_search inherited unchanged. Only masks and one-state fill generalized.
 adapt.build_candidates=lambda ph,roads,audit,sid,rep,predictor:build(ph,roads,audit,sid,rep,predictor)
 return adapt
