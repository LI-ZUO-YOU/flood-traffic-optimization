"""Revision-only experiment. Frozen research functions are imported unmodified.

Search algorithms see only QueryOracle.request(mask), never a complete cost table.
The complete state table and exact DP are a separate post-freeze stage.
"""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
from pathlib import Path
import argparse,csv,gzip,hashlib,importlib.util,itertools,json,math,sqlite3,sys,time
from types import SimpleNamespace
from collections import Counter
import numpy as np
import pandas as pd
from ue_solver import Network, LEGACY_BASELINE

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_snapshot'
FORMAL=SOURCE/'code/final_pipeline'
MODEL=SOURCE/'code/model_backend'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def load_module(name,path):
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
original=load_module('revision_frozen_full',FORMAL/'run_full_method_live_ue.py')
gen=load_module('revision_frozen_candidates',FORMAL/'generate_candidate_pool.py')
primary=load_module('revision_frozen_primary',FORMAL/'screen_primary.py')
reserve=load_module('revision_frozen_reserve',FORMAL/'screen_structural_reserve.py')
api=load_module('revision_frozen_api',FORMAL/'interfaces_week3.py')
legacy_sa=load_module('revision_original_sa',SOURCE/'legacy_sa/run_permutation_sa.py')

def select_roads(physical):
    pre=json.loads((SOURCE/'surrogate/final_ensemble/preprocessor_v2.json').read_text(encoding='utf-8'))
    audit=physical.sort_values('physical_link_id').copy()
    audit['physical_flow']=pre['baseline_flow'];audit['betweenness']=pre['betweenness']
    closed=audit[audit.is_closed==1].copy();n=len(closed)
    if n<10:raise ValueError('Fewer than ten closed roads')
    for col in ['physical_flow','betweenness']:
        closed[col+'_score']=(n-closed[col].rank(ascending=False,method='min'))/(n-1)
    closed['combined_score']=.5*closed.physical_flow_score+.5*closed.betweenness_score
    closed=closed.sort_values(['combined_score','physical_flow','betweenness','physical_link_id'],ascending=[False,False,False,True],kind='mergesort')
    audit=audit.merge(closed[['physical_link_id','physical_flow_score','betweenness_score','combined_score']],on='physical_link_id',how='left')
    return tuple(closed.head(10).physical_link_id.astype(int)),audit

def build_candidates(physical,roads,audit,sid,rep,predictor):
    seed=2026080702+sid+1000000*rep;start=time.perf_counter();rng=np.random.default_rng(seed)
    start_infer=time.perf_counter()
    member_loss=gen.subset_member_losses(predictor,physical.depth_m.to_numpy(float),physical.is_closed.to_numpy(np.uint8),list(roads))
    inference_seconds=time.perf_counter()-start_infer
    objective=gen.ProxyObjective(member_loss,list(roads));mean_policy=gen.successor_policy(member_loss.mean(axis=1),list(roads))
    member_policies=[gen.successor_policy(member_loss[:,i],list(roads)) for i in range(10)]
    registry={};counter=0
    counter=gen.fill_prefix_stratified(registry,list(roads),mean_policy,member_policies,rng,counter)
    counter=gen.fill_proxy_dp(registry,list(roads),member_loss,mean_policy,rng,counter)
    counter=gen.fill_diversity(registry,list(roads),seed,counter)
    counter=gen.fill_random(registry,list(roads),rng,counter)
    gen.fill_ga_local_from_registry(registry,objective,list(roads),rng,counter)
    assert len(registry)==30000
    frame=pd.DataFrame([gen.candidate_row(sid,seq,metadata,objective) for seq,metadata in registry.items()])
    frame=frame.sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').reset_index(drop=True);frame['proxy_rank']=np.arange(1,len(frame)+1)
    shortlist=primary.select_scenario(frame,list(roads),audit,np.random.default_rng(2026080703+sid+1000000*rep))
    shortlist['screening_tier']='primary_shortlist'
    shortlist['prefix_2']=shortlist.sequence.str.split('|').map(lambda v:'|'.join(v[:2]))
    shortlist['prefix_3']=shortlist.sequence.str.split('|').map(lambda v:'|'.join(v[:3]))
    r=reserve.structural_reserve(frame,set(shortlist.candidate_id));screened=pd.concat([shortlist,r],ignore_index=True,sort=False)
    screened=screened.sort_values(['screening_tier','channel','channel_rank','candidate_id'],kind='mergesort').reset_index(drop=True)
    report={'candidate_seed':seed,'screening_seed':2026080703+sid+1000000*rep,'candidate_count':len(frame),'source_counts':dict(Counter(frame.primary_source)),
            'candidate_order_sha256':hashlib.sha256('\n'.join(frame.candidate_id).encode()).hexdigest(),'candidate_construction_seconds':time.perf_counter()-start,'surrogate_inference_seconds':inference_seconds,
            'primary_count':len(shortlist),'reserve_count':len(r),'model_training_randomness_repeated':False}
    return screened,report

class LimitReached(Exception):pass

class PhysicalStore:
    def __init__(self,network,physical,roads,db=None,target=1e-9):
        self.net=network;self.physical=physical;self.roads=roads;self.target=target;self.cache={};self.solves=0;self.solve_seconds=0.0
        self.connection=None
        if db:
            Path(db).parent.mkdir(parents=True,exist_ok=True);self.connection=sqlite3.connect(db,timeout=60)
            self.connection.execute('CREATE TABLE IF NOT EXISTS states(mask INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
            self.cache={int(m):json.loads(v) for m,v in self.connection.execute('SELECT mask,payload FROM states')}
    def request(self,mask):
        # Only this scalar lookup is offered to the logical oracle. No table API.
        if mask in self.cache:return self.cache[mask],True
        row=self.net.solve(self.physical,self.roads,mask,self.target);self.cache[mask]=row;self.solves+=1;self.solve_seconds+=row['solver_seconds']
        if self.connection:
            self.connection.execute('INSERT INTO states(mask,payload) VALUES(?,?)',(int(mask),json.dumps(row)))
            if self.solves%16==0:self.connection.commit()
        return row,False
    def close(self):
        if self.connection:self.connection.commit();self.connection.close()

class QueryOracle:
    def __init__(self,store,budget=256,time_limit=None):
        self.__store=store;self.budget=budget;self.deadline=time.perf_counter()+time_limit if time_limit is not None else None
        self.known={};self.rows=[];self.events=[];self.requests=0;self.best=None;self.best_seq=None;self.trace=[];self.started=time.perf_counter()
        self.physical_seconds=0.0;self.cache_hits=0;self.termination='completed';self.late_results=[]
    @property
    def used(self):return len(self.known)
    def check(self):
        if self.deadline is not None and time.perf_counter()>=self.deadline:raise LimitReached('elapsed_time_cap')
    def request(self,mask,phase='search',reason=''):
        self.check();mask=int(mask);self.requests+=1
        hit=mask in self.known
        if not hit:
            if self.used>=self.budget:raise LimitReached('unique_state_cap')
            row,physicalhit=self.__store.request(mask)
            if self.deadline is not None and time.perf_counter()>=self.deadline:
                self.late_results.append({'subset_mask':mask,'requested_before_deadline':True,'visible_to_search':False,'overrun_seconds':time.perf_counter()-self.deadline})
                raise LimitReached('elapsed_time_cap_late_result_discarded')
            self.known[mask]=dict(row);self.cache_hits+=int(physicalhit)
            if not physicalhit:self.physical_seconds+=row['solver_seconds']
            self.rows.append({**row,'query_index':self.used,'phase':phase,'reason':reason,'physical_cache_hit':physicalhit,'incumbent_objective':self.best,'incumbent_sequence':self.best_seq})
        self.events.append((self.requests,mask,hit,self.used,phase))
        return self.known[mask]
    def can(self,masks):return len(set(masks)-set(self.known))<=self.budget-self.used
    def observe(self,sequence,value):
        if self.best is None or value<self.best:
            self.best=float(value);self.best_seq=tuple(map(int,sequence));self.trace.append({'query_count':self.used,'objective':self.best,'sequence':self.best_seq,'elapsed_seconds':time.perf_counter()-self.started})
    def save(self,path,method,rep,sid,extra=None):
        elapsed=time.perf_counter()-self.started
        path=Path(path);path.mkdir(parents=True,exist_ok=True)
        pd.DataFrame(self.rows).to_csv(path/'logical_query_ledger.csv.gz',index=False,compression='gzip')
        pd.DataFrame(self.events,columns=['request_index','subset_mask','logical_cache_hit','unique_queries_after','phase']).to_csv(path/'all_query_events.csv.gz',index=False,compression='gzip')
        pd.DataFrame(self.trace).to_csv(path/'incumbent_history.csv',index=False)
        result={'scenario_id':sid,'method':method,'replicate':rep,'actual_queries':self.used,'logical_requests':self.requests,'physical_cache_hits':self.cache_hits,
                'best_objective':self.best,'best_sequence':self.best_seq,'wall_seconds':elapsed,'physical_UE_seconds':self.physical_seconds,'late_results_discarded':self.late_results,
                'termination':self.termination,'snapshots':{str(b):min((t['objective'] for t in self.trace if t['query_count']<=b),default=None) for b in [64,128,256]},**(extra or {})}
        dump(path/'result.json',result);return result

class SharedCorrection(original.BudgetedSearch):
    """Reuses the frozen local_search implementation, not a rewritten analogue."""
    def __init__(self,oracle,roads,sid,screened=None):
        self.oracle=oracle;self.roads=tuple(roads);self.sid=sid;self.road_to_bit={r:i for i,r in enumerate(roads)}
        self.args=SimpleNamespace(max_budget=oracle.budget);self.calls=0;self.requests=0;self.cache_hits=0;self.physical_cache_hits=0
        cols=['candidate_id','sequence','seq_tuple','screening_tier','channel','primary_source','proxy_rank','proxy_objective_mean','prefix_2','prefix_3']
        self.screened=screened.copy() if screened is not None else pd.DataFrame(columns=cols)
        if screened is not None:self.screened['seq_tuple']=self.screened.sequence.map(original.parse_sequence)
        self.reserve=self.screened[self.screened.screening_tier=='structural_reserve'].copy();self.primary=self.screened[self.screened.screening_tier=='primary_shortlist'].copy()
        self.state_by_hash={};self.state_rows=[];self.result_rows=[];self.local_rows=[];self.result_by_sequence={};self.seed_attempted=set();self.local_attempted=set();self._seed_queue=[]
        self.started=time.perf_counter()
    def state_hash(self,mask):return f'{self.sid}:{int(mask)}'
    def evaluate_mask(self,mask,phase,reason,sequence=None):
        self.oracle.check();row=self.oracle.request(mask,phase,reason);key=self.state_hash(mask)
        self.state_by_hash[key]=row;self.calls=self.oracle.used;self.requests=self.oracle.requests
        return row
    def evaluate_sequence(self,*args,**kwargs):
        self.oracle.check();result=super().evaluate_sequence(*args,**kwargs)
        if result is not None:self.oracle.observe(args[0],result['ue_objective'])
        return result

def masks(sequence,roads):
    mapping={r:i for i,r in enumerate(roads)};result=[0];mask=0
    for road in sequence[:9]:mask|=1<<mapping[road];result.append(mask)
    return result
def evaluate(oracle,seq,roads,phase='sequence'):
    ms=masks(seq,roads)
    if not oracle.can(ms):return None
    value=float(np.mean([oracle.request(m,phase)['loss'] for m in ms]))
    oracle.observe(seq,value);return float(value)

def proposed(oracle,roads,sid,screened):
    engine=SharedCorrection(oracle,roads,sid,screened)
    prefixes=engine.evaluate_prefix2();ranked=engine.prefix2_scores(prefixes)
    engine.evaluate_prefix3_for(ranked[:4],'B_prefix3_initial');engine.build_seed_queue();engine.run_interval(64,.55)
    engine.evaluate_prefix3_for(ranked[4:],'B_prefix3_remaining');engine.build_seed_queue();engine.run_interval(128,.5);engine.run_interval(256,.5)
    return engine

def greedy(oracle,roads):
    oracle.request(0,'greedy');mask=0;seq=[]
    while len(seq)<9:
        options=[]
        for i,r in enumerate(roads):
            if mask&(1<<i)==0:
                child=mask|(1<<i);options.append((oracle.request(child,'greedy')['loss'],r,child))
        _,r,mask=min(options);seq.append(r)
    seq.extend(r for r in roads if r not in seq);evaluate(oracle,tuple(seq),roads,'greedy_complete');return tuple(seq)

def mutate(seq,rng,swaps=1):
    child=list(seq)
    for k in range(swaps):
        i,j=sorted(map(int,rng.choice(10,2,replace=False)));child[i],child[j]=child[j],child[i]
    return tuple(child)

def correction_baseline(oracle,roads,sid,rep,mode='greedy_ls',swaps=2):
    rng=np.random.default_rng(2026102603+sid+1000000*rep)
    engine=SharedCorrection(oracle,roads,sid)
    if mode.startswith('greedy'):seed=greedy(oracle,roads)
    else:seed=tuple(rng.permutation(roads).tolist())
    engine.evaluate_sequence(seed,'initial_start','shared_correction_start')
    for target in [64,128,256] if oracle.budget==256 else [oracle.budget]:
        engine.local_search(target)
        if mode in ['greedy_ls','random_ls']:continue
        stalls=0
        while oracle.used<target and stalls<500:
            oracle.check();parent=oracle.best_seq
            child=mutate(parent,rng,swaps);needed=engine.missing_count(child)
            if needed>target-oracle.used:stalls+=1;continue
            before=oracle.used;engine.evaluate_sequence(child,'restart','perturbed_incumbent');engine.local_search(target)
            stalls=stalls+1 if before==oracle.used else 0
    return engine

def sa(oracle,roads,sid,rep,restart=False,config=None):
    cfg={'temperature_ratio':.0025,'cooling':.995,'restart_stall':100,**(config or {})}
    rng=np.random.default_rng(2026081000+sid+1000000*rep)
    current=tuple(rng.permutation(roads).tolist());value=evaluate(oracle,current,roads,'sa_initial')
    source_config=legacy_sa.SAConfig(cfg['temperature_ratio'],cfg['cooling'],.7,.15,1000)
    t=0;stalled=0;restarts=0;proposals=0
    while proposals<200000:
        oracle.check();proposals+=1;t+=1
        child=legacy_sa.propose(current,rng,source_config)
        before=oracle.used;new=evaluate(oracle,child,roads,'sa_move')
        if new is not None:
            temperature=cfg['temperature_ratio']*max(abs(value),1.0)*cfg['cooling']**t
            if new<=value or float(rng.random())<math.exp((value-new)/max(temperature,1e-15)):current,value=child,new
        stalled=stalled+1 if before==oracle.used else 0
        if oracle.used>=oracle.budget:break
        if not restart and stalled>=1000:oracle.termination='natural_stall_1000';break
        if restart and stalled>=cfg['restart_stall']:
            restarts+=1;stalled=0;t=0
            candidate=tuple(rng.permutation(roads).tolist());new=evaluate(oracle,candidate,roads,'sa_restart')
            if new is not None:current,value=candidate,new
        if restart and proposals>5000 and oracle.budget-oracle.used<10:
            # Useful one-state finishing moves are genuine neighborhood evaluations.
            found=False
            for candidate,_,_,_ in original.BudgetedSearch.move_neighbors(tuple(oracle.best_seq)):
                needed=len(set(masks(candidate,roads))-set(oracle.known))
                if 0<needed<=oracle.budget-oracle.used:
                    evaluate(oracle,candidate,roads,'sa_final_neighborhood');found=True;break
            if not found:oracle.termination='no_complete_move_fits_residual_budget';break
    return {'proposals':proposals,'restarts':restarts}

def beam(oracle,roads,sid,width=4,bidirectional=False):
    incumbent=greedy(oracle,roads)
    # Forward labels charge source-state cost. Backward labels charge predecessor.
    # They sum without duplicate charging at a joining subset. No monotonicity bound.
    forward={0:(0.0,())};backward={1023:(0.0,())};forward_seen=dict(forward);backward_seen=dict(backward)
    turn=0
    while forward or (bidirectional and backward):
        oracle.check();isback=bidirectional and turn%2==1;turn+=1
        front=backward if isback else forward
        children={}
        for mask,(g,path) in sorted(front.items(),key=lambda kv:(kv[1][0],kv[0])):
            for i,r in enumerate(roads):
                if bool(mask&(1<<i))!=isback:continue
                child=mask^(1<<i)
                if isback:
                    if child not in oracle.known and oracle.used>=oracle.budget:continue
                    cost=oracle.request(child,'beam_backward')['loss'];candidate=(g+cost,(r,)+path)
                else:
                    cost=oracle.request(mask,'beam_forward')['loss'];candidate=(g+cost,path+(r,))
                    if child!=1023:
                        if child not in oracle.known and oracle.used>=oracle.budget:continue
                        oracle.request(child,'beam_forward')
                if child not in children or candidate<children[child]:children[child]=candidate
                opposite=forward_seen if isback else backward_seen
                if child in opposite:
                    otherg,otherpath=opposite[child]
                    seq=otherpath+candidate[1] if isback else candidate[1]+otherpath
                    if len(seq)==10 and len(set(seq))==10:evaluate(oracle,seq,roads,'beam_join')
                if (not isback and child==1023) or (isback and child==0):evaluate(oracle,candidate[1],roads,'beam_complete')
        if not children:break
        frontnew=dict(sorted(children.items(),key=lambda kv:(kv[1][0],kv[0]))[:width])
        if isback:backward=frontnew;backward_seen.update(frontnew)
        else:forward=frontnew;forward_seen.update(frontnew)
        if bidirectional:
            # When fronts have crossed, evaluate compatible complete joins with at
            # most one connecting road. This mirrors subset separability, not the
            # original paper's traffic-benefit upper/lower-bound pruning.
            for fm,(fg,fp) in forward_seen.items():
                for bm,(bg,bp) in backward_seen.items():
                    if fm&bm!=fm:continue
                    missing=[r for i,r in enumerate(roads) if bm&(1<<i) and fm&(1<<i)==0]
                    if len(missing)<=1:evaluate(oracle,fp+tuple(missing)+bp,roads,'beam_bridge')
        if not isback and (1023 in frontnew):break
        if isback and 0 in frontnew:break
        if oracle.used>=oracle.budget:break
    return {'beam_width':width,'bidirectional':bidirectional,'proven_bounds_or_original_branch_pruning_used':False}

def exact_dp(costs,roads):
    dp={0:costs[0]};seq={0:()}
    for mask in range(1,1024):
        value,road,prev=min((dp[mask^(1<<i)],r,mask^(1<<i)) for i,r in enumerate(roads) if mask&(1<<i))
        dp[mask]=value+(0 if mask==1023 else costs[mask]);seq[mask]=seq[prev]+(road,)
    return dp[1023]/10,seq[1023]

def run_method(method,oracle,roads,sid,rep,screened=None,config=None):
    details={}
    try:
        if method=='proposed':engine=proposed(oracle,roads,sid,screened)
        elif method in ['sa_original','sa_restart']:details=sa(oracle,roads,sid,rep,method=='sa_restart',config)
        elif method in ['greedy_ls','greedy_ils','random_ls']:engine=correction_baseline(oracle,roads,sid,rep,method,(config or {}).get('perturb_swaps',2))
        elif method in ['ue_beam','ue_bibeam']:
            width=(config or {}).get('width',4);rounds=[]
            for multiplier in [1,2,4,8,16]:
                before=oracle.used;details=beam(oracle,roads,sid,width*multiplier,method=='ue_bibeam');rounds.append(details)
                if oracle.used>=oracle.budget or before==oracle.used:break
            details={'progressive_width_rounds':rounds}
        else:raise ValueError(method)
    except LimitReached as e:oracle.termination=str(e)
    if oracle.best is None:raise RuntimeError(f'{method} returned no complete feasible sequence')
    assert oracle.used<=oracle.budget
    return details
