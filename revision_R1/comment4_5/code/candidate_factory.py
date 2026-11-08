"""Frozen component adapters. No UE labels or reference data are accepted here."""
from common45 import *
from predictor_adapters import predictor,subset_states
import itertools
from collections import Counter

SINGLE={'F6_SINGLE_MLP','F7_RIDGE','F8_TREE'}
MUTATION_ATTEMPTS=50000
RANDOM_ATTEMPTS=1000000

def prefixes(f):
 f=f.copy();s=f.sequence.str.split('|')
 f['prefix_2']=s.map(lambda x:'|'.join(x[:2]));f['prefix_3']=s.map(lambda x:'|'.join(x[:3]))
 return f

def fill_uniform(reg,roads,n,source,r,counter,detail='independent_uniform_permutation'):
 added=0
 for attempt in range(RANDOM_ATTEMPTS):
  ok,counter=E.gen.add_unique(reg,tuple(map(int,r.permutation(roads))),source,detail,counter);added+=ok
  if added==n:return counter
 raise RuntimeError(f'Uniform quota failed: {source} {added}/{n}')

def single_prefix(reg,roads,policy,r,second,counter):
 added=0
 for prefix in itertools.permutations(roads,4):
  for seq,detail in [(E.gen.complete_by_policy(prefix,roads,policy),'all_ordered_prefix4_single_dp_tail'),(E.gen.random_completion(prefix,roads,second),'all_ordered_prefix4_second_substream_random_tail'),(E.gen.random_completion(prefix,roads,r),'all_ordered_prefix4_random_tail')]:
   ok,counter=E.gen.add_unique(reg,seq,'prefix_stratified',detail,counter);added+=ok
 return fill_uniform(reg,roads,16000-added,'prefix_stratified',r,counter,'supplemental_random_tail') if added<16000 else counter

def single_mutations(reg,bases,roads,n,source,r,fallback,counter,twice):
 added=0;attempts=0
 # DP base itself is part of the DP source; GA/local starts with mutations.
 if source=='proxy_subset_dp':
  ok,counter=E.gen.add_unique(reg,bases[0],source,'single_policy_base',counter);added+=ok
 while added<n and attempts<MUTATION_ATTEMPTS:
  seq=E.gen.mutate(bases[attempts%len(bases)],r);attempts+=1
  if r.random()<twice:seq=E.gen.mutate(seq,r)
  ok,counter=E.gen.add_unique(reg,seq,source,'single_model_swap_insert',counter);added+=ok
 missing=n-added
 if missing:counter=fill_uniform(reg,roads,missing,source,fallback,counter,'predeclared_source_specific_random_completion')
 return counter,{'source':source,'mutation_attempts':attempts,'random_completion_count':missing}

def screen(pool,roads,audit,sid,rep,variant):
 if variant=='F9_NO_SURROGATE':
  order=rng(sid,rep,variant,'primary60').permutation(len(pool))[:60]
  primary=pool.iloc[order].copy();primary['channel']='random';primary['channel_rank']=range(1,61);primary['screen_order']=range(1,61)
 else:
  module=E.primary
  if variant=='F3_NO_DISAG' or variant in SINGLE:
   module=E.load_module('ablation_primary_no_disag',E.FORMAL/'screen_primary.py')
   module.CHANNEL_QUOTAS={'proxy_top':25,'ensemble_disagreement':0,'sequence_diversity':15,'heuristic':10,'random':10}
  primary=module.select_scenario(pool,list(roads),audit,np.random.default_rng(2026080703+sid+1000000*rep))
 primary=prefixes(primary);primary['screening_tier']='primary_shortlist'
 if variant=='F1_NO_RESERVE':
  # All pool entries remain eligible in flat rank order, without reserve sampling.
  flat=prefixes(pool[~pool.candidate_id.isin(primary.candidate_id)]);flat['screening_tier']='flat_pool';flat['channel']='flat_proxy_order';flat['channel_rank']=flat.proxy_rank
  reserve=flat.iloc[:0].copy();combined=pd.concat([primary,flat],ignore_index=True,sort=False)
 else:
  reserve=E.reserve.structural_reserve(pool,set(primary.candidate_id))
  if variant=='F9_NO_SURROGATE':reserve['reserve_rule']='top10 random-prefix2 clusters; source-wise random-order quantiles; true UE prefix ranking retained'
  combined=pd.concat([primary,reserve],ignore_index=True,sort=False)
 combined=combined.sort_values(['screening_tier','channel','channel_rank','candidate_id'],kind='mergesort').reset_index(drop=True)
 return combined,primary,reserve

def build(sid,rep,variant):
 started=time.perf_counter();ph,roads,audit=public_scenario(sid);model=predictor(variant);fallback=[]
 seed=2026080702+sid+1000000*rep
 if variant in {'F0_FULL','F1_NO_RESERVE','F3_NO_DISAG'}:
  capture={};old=E.primary.select_scenario
  class PoolReady(Exception):pass
  def wrapped(pool,*a,**kw):
   capture['pool']=pool.copy()
   if variant!='F0_FULL':raise PoolReady()
   return old(pool,*a,**kw)
  E.primary.select_scenario=wrapped
  old_infer=E.gen.subset_member_losses
  def measured_infer(*a,**kw):
   t=time.perf_counter();result=old_infer(*a,**kw);capture['inference_seconds']=time.perf_counter()-t;return result
  E.gen.subset_member_losses=measured_infer
  try:
   try:screened,report=E.build_candidates(ph,roads,audit,sid,rep,model)
   except PoolReady:report={'candidate_seed':seed,'screening_seed':2026080703+sid+1000000*rep,'surrogate_inference_seconds':capture['inference_seconds']}
  finally:
   E.primary.select_scenario=old;E.gen.subset_member_losses=old_infer
  pool=capture['pool']
  if variant!='F0_FULL':screened,primary,reserve=screen(pool,roads,audit,sid,rep,variant)
  else:primary=screened[screened.screening_tier=='primary_shortlist'];reserve=screened[screened.screening_tier=='structural_reserve']
 else:
  reg={};counter=0;r=np.random.default_rng(seed);roads_list=list(roads);infer_start=time.perf_counter()
  if model is None:member_loss=None;objective=None;policy=None;member_policies=None;inference_seconds=0.0
  else:
   member_loss=np.exp(model.predict_members(subset_states(ph,roads)))-1.0
   expected=(1024,1 if variant in SINGLE else 10)
   assert member_loss.shape==expected and np.isfinite(member_loss).all(), 'Invalid surrogate matrix'
   inference_seconds=time.perf_counter()-infer_start
   objective=E.gen.ProxyObjective(member_loss,roads_list)
   policy=None;member_policies=None
   if variant not in {'F5_RANDOM_POOL'}:
    policy=E.gen.successor_policy(member_loss.mean(axis=1),roads_list)
    if variant not in SINGLE:member_policies=[E.gen.successor_policy(member_loss[:,i],roads_list) for i in range(10)]
  if variant in {'F5_RANDOM_POOL','F9_NO_SURROGATE'}:
   counter=fill_uniform(reg,roads_list,30000,'random',rng(sid,rep,variant,'random_pool'),counter)
  else:
   if variant=='F2_NO_PREFIX':counter=fill_uniform(reg,roads_list,16000,'prefix_replaced_random',rng(sid,rep,variant,'prefix_replacement'),counter)
   elif variant in SINGLE:counter=single_prefix(reg,roads_list,policy,r,rng(sid,rep,variant,'second_prefix_tail'),counter)
   else:counter=E.gen.fill_prefix_stratified(reg,roads_list,policy,member_policies,r,counter)
   if variant=='F4_NO_PROXY_SOURCES':counter=fill_uniform(reg,roads_list,4000,'replacement_for_proxy_dp',rng(sid,rep,variant,'dp_replacement'),counter)
   elif variant in SINGLE:
    base=E.gen.complete_by_policy((),roads_list,policy)
    counter,log=single_mutations(reg,[base],roads_list,4000,'proxy_subset_dp',r,rng(sid,rep,variant,'dp_fallback'),counter,.65);fallback.append(log)
   else:counter=E.gen.fill_proxy_dp(reg,roads_list,member_loss,policy,r,counter)
   counter=E.gen.fill_diversity(reg,roads_list,seed,counter)
   counter=E.gen.fill_random(reg,roads_list,r,counter)
   if variant=='F4_NO_PROXY_SOURCES':counter=fill_uniform(reg,roads_list,3000,'replacement_for_proxy_ga',rng(sid,rep,variant,'ga_replacement'),counter)
   elif variant in SINGLE:
    bases=[seq for _,seq in sorted((objective.evaluate(seq)[0],seq) for seq in reg)[:2500]]
    counter,log=single_mutations(reg,bases,roads_list,3000,'proxy_ga_local',r,rng(sid,rep,variant,'ga_fallback'),counter,.35);fallback.append(log)
   else:counter=E.gen.fill_ga_local_from_registry(reg,objective,roads_list,r,counter)
  rows=[]
  for seq,meta in reg.items():
   if member_loss is not None and variant not in SINGLE:row=E.gen.candidate_row(sid,seq,meta,objective)
   else:
    row={'scenario_id':sid,'candidate_id':hashlib.sha256(f"{sid}|{'|'.join(map(str,seq))}".encode()).hexdigest(),'sequence':'|'.join(map(str,seq)),'primary_source':meta['primary_source'],'source_detail':meta['source_detail'],'source_tags':'|'.join(sorted(meta['source_tags'])),'generation_order':meta['generation_order'],'proxy_objective_mean':np.nan,'ensemble_disagreement':np.nan}
    row.update({f'road_{i:02d}':v for i,v in enumerate(seq,1)})
    if objective is not None:row['proxy_objective_mean']=objective.evaluate(seq)[0];row['member_01_objective']=row['proxy_objective_mean']
   rows.append(row)
  pool=pd.DataFrame(rows)
  if model is None:pool=pool.iloc[rng(sid,rep,variant,'random_priority').permutation(len(pool))].reset_index(drop=True)
  else:pool=pool.sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').reset_index(drop=True)
  pool['proxy_rank']=np.arange(1,len(pool)+1)
  screened,primary,reserve=screen(pool,roads,audit,sid,rep,variant)
  report={'candidate_seed':seed,'screening_seed':2026080703+sid+1000000*rep,'surrogate_inference_seconds':inference_seconds}
 assert len(pool)==pool.sequence.nunique()==pool.candidate_id.nunique()==30000
 assert len(primary)==primary.sequence.nunique()==60
 assert all(set(E.original.parse_sequence(s))==set(roads) for s in pool.sequence)
 report.update({'variant_id':variant,'candidate_count':len(pool),'source_counts':dict(Counter(pool.primary_source)),'candidate_order_sha256':hashlib.sha256('\n'.join(pool.candidate_id).encode()).hexdigest(),'primary_count':len(primary),'reserve_count':len(reserve),'flat_eligible_count':len(screened)-60 if variant=='F1_NO_RESERVE' else 0,'primary_channels':dict(Counter(primary.channel)),'prefix4_coverage':pool.sequence.str.split('|').map(lambda x:tuple(x[:4])).nunique(),'candidate_construction_seconds':time.perf_counter()-started,'fallback_log':fallback,'rank_basis':'fixed_seed_random_ordinal' if model is None else 'surrogate_objective','surrogate_loaded':model is not None,'proxy_dp_policies':0 if variant in {'F5_RANDOM_POOL','F9_NO_SURROGATE'} else 1 if variant in SINGLE else 11 if variant=='F4_NO_PROXY_SOURCES' else 89})
 return roads,pool,screened,report
