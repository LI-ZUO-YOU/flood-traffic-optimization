"""G2 offline mathematical, frozen-filter and archival-queue audit only.

No model/checkpoint loading, inference, traffic solver, new flood or search.
Frozen modules are imported under non-main names. Only pure screening, queue
construction, state hashing, mask and DP functions are invoked; never their
main(), BudgetedSearch.__init__/run/local_search/evaluate_mask, or UEInterface.
"""
from __future__ import annotations
import argparse
import ast
import collections
import csv
import hashlib
import importlib.abc
import importlib.util
import inspect
import itertools
import json
import math
import platform
import sys
import time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd

TOL=1e-12
PURE_MATH_SEED=2026103107
DP_SCENARIOS=(1001,1002)
Q_ORDER=(1,5,10,3,8,2,7,4,6,9)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(2**20),b''):h.update(x)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,data,fields=None):
    fields=fields or list(dict.fromkeys(k for r in data for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v for k,v in r.items()})
def link(p,label=None,line=None):return f'[{label or Path(p).name}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
class NoInferenceImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='torch' or fullname.startswith('torch.') or fullname=='models' or fullname.startswith('models.'):
            raise RuntimeError('FORBIDDEN_MODEL_OR_SOLVER_IMPORT '+fullname)
        return None
def mask_for(seq,roads):
    mapping={r:i for i,r in enumerate(roads)}
    return sum(1<<mapping[r] for r in seq)
def sequence_masks(seq,roads):return [mask_for(seq[:k],roads) for k in range(len(roads))]
def independent_dp(costs,m,roads=None):
    roads=list(range(m)) if roads is None else roads
    full=(1<<m)-1;value={0:float(costs[0])};pred={}
    for size in range(1,m+1):
        for s in range(1,full+1):
            if s.bit_count()!=size:continue
            prev,road,bit=min((value[s^(1<<i)],int(roads[i]),i) for i in range(m) if s&(1<<i))
            value[s]=prev+(0 if s==full else float(costs[s]));pred[s]=bit
    seq=[];s=full
    while s:bit=pred[s];seq.append(roads[bit]);s^=1<<bit
    return value[full]/m,tuple(reversed(seq))

def independent_primary(frame,roads,audit,seed):
    f=frame.sort_values(['proxy_rank','candidate_id']).reset_index(drop=True)
    seq=f[[f'road_{i:02d}' for i in range(1,11)]].to_numpy(dtype=int)
    positions=np.empty_like(seq)
    for j,r in enumerate(roads):positions[:,j]=np.argmax(seq==r,axis=1)
    orient=np.column_stack([positions[:,i]<positions[:,j] for i in range(10) for j in range(i+1,10)])
    selected=[];used=set();channels=[];scores=[];reasons=[]
    def add(i,ch,score,reason):
        selected.append(int(i));used.add(int(i));channels.append(ch);scores.append(float(score));reasons.append(reason)
    for i in range(15):add(i,'proxy_top',f.iloc[i]['proxy_rank'],'lowest ensemble-mean proxy objective')
    eligible=f[f.proxy_rank<=int(.30*len(f))].sort_values(['ensemble_disagreement','proxy_objective_mean','candidate_id'],ascending=[False,True,True])
    for i in eligible.index:
        if i not in used:add(i,'ensemble_disagreement',f.iloc[i]['ensemble_disagreement'],'highest member disagreement within proxy top 30%')
        if channels.count('ensemble_disagreement')==10:break
    distances=np.ones(len(f))
    for i in selected:distances=np.minimum(distances,np.count_nonzero(orient!=orient[i],axis=1)/45)
    available=f.proxy_rank.to_numpy()<=int(.5*len(f));available[selected]=False
    for _ in range(15):
        valid=np.flatnonzero(available);best=distances[valid].max();tied=valid[np.isclose(distances[valid],best)]
        tf=f.iloc[tied];i=int(tied[np.lexsort((tf.candidate_id.to_numpy(),tf.proxy_objective_mean.to_numpy()))[0]])
        add(i,'sequence_diversity',distances[i],'max-min Kendall distance within proxy top 50%')
        available[i]=False;distances=np.minimum(distances,np.count_nonzero(orient!=orient[i],axis=1)/45)
    selected_audit=audit[audit.physical_link_id.isin(roads)]
    rules=[('combined_desc',['combined_score','physical_flow','physical_link_id'],[False,False,True]),
           ('flow_desc',['physical_flow','betweenness','physical_link_id'],[False,False,True]),
           ('betweenness_desc',['betweenness','physical_flow','physical_link_id'],[False,False,True]),
           ('depth_desc',['depth_m','physical_flow','physical_link_id'],[False,False,True]),
           ('depth_asc',['depth_m','physical_flow','physical_link_id'],[True,False,True])]
    for name,cols,asc in rules:
        ref=selected_audit.sort_values(cols,ascending=asc).physical_link_id.astype(int).tolist()
        for suffix,order in [('',ref),('_reverse',list(reversed(ref)))]:
            pos={r:i for i,r in enumerate(order)};ref_o=np.array([pos[roads[i]]<pos[roads[j]] for i in range(10) for j in range(i+1,10)])
            d=np.count_nonzero(orient!=ref_o,axis=1)/45;available=np.ones(len(f),dtype=bool);available[list(used)]=False
            tied=np.flatnonzero(available&np.isclose(d,d[available].min()))
            tf=f.iloc[tied];i=int(tied[np.lexsort((tf.candidate_id.to_numpy(),tf.proxy_objective_mean.to_numpy()))[0]])
            add(i,'heuristic',d[i],f'nearest pool sequence to frozen rule {name+suffix}')
    random_indices=np.random.default_rng(seed).permutation(f.index[f.primary_source=='random'].to_numpy())
    for i in random_indices:
        if i not in used:add(i,'random',channels.count('random')+1,'fixed-seed uniform draw from random-source pool')
        if channels.count('random')==10:break
    result=f.iloc[selected].copy();result['channel']=channels
    result['channel_rank']=result.groupby('channel',sort=False).cumcount()+1
    result['screen_order']=np.arange(1,61);result['channel_selection_score']=scores;result['selection_reason']=reasons
    return result

def independent_reserve(frame,primary_ids):
    f=frame.copy();split=f.sequence.str.split('|');f['prefix_2']=split.map(lambda a:'|'.join(a[:2]));f['prefix_3']=split.map(lambda a:'|'.join(a[:3]))
    minrank=f.groupby('prefix_2',sort=True).proxy_rank.min().sort_values(kind='mergesort').head(10)
    selected=[];position_rows=[]
    for p2_rank,p2 in enumerate(minrank.index,1):
        part=f[f.prefix_2==p2]
        for p3,p3f in part.groupby('prefix_3',sort=True):
            for source,g in p3f.groupby('primary_source',sort=True):
                g=g.sort_values(['proxy_rank','candidate_id'],kind='mergesort').reset_index(drop=True)
                q=min(10,len(g));positions=np.unique(np.round(np.linspace(0,len(g)-1,q)).astype(int))
                for qi,position in enumerate(positions,1):
                    r=g.iloc[int(position)].to_dict();r.update(prefix_2_cluster_rank=p2_rank,source_quantile_index=qi,source_quantile_total=len(positions))
                    position_rows.append({'scenario_id':int(r['scenario_id']),'prefix_2':p2,'prefix_3':p3,'primary_source':source,
                       'group_n':len(g),'q':q,'quantile_index':qi,'selected_zero_based_position':int(position),'candidate_id':r['candidate_id'],
                       'excluded_as_primary':r['candidate_id'] in primary_ids})
                    if r['candidate_id'] not in primary_ids:selected.append(r)
    result=pd.DataFrame(selected).drop_duplicates('candidate_id').copy()
    result['screening_tier']='structural_reserve';result['channel']='hierarchical_prefix_reserve';result['channel_rank']=np.arange(1,len(result)+1)
    return result,position_rows,minrank

def independent_queue(screened,roads,costs,known):
    reserve=screened[screened.screening_tier=='structural_reserve'];primary=screened[screened.screening_tier=='primary_shortlist']
    p3scores=[]
    for p3 in reserve.prefix_3.dropna().astype(str).unique():
        prefix=tuple(map(int,p3.split('|')));masks=[mask_for(prefix[:k],roads) for k in (1,2,3)]
        if masks[2] not in known:continue
        p3scores.append((sum(float(costs[s]) for s in masks),p3))
    p3rank={p3:i for i,(_,p3) in enumerate(sorted(p3scores),1)}
    sources=sorted(reserve.primary_source.dropna().astype(str).unique());sr={s:i for i,s in enumerate(sources)}
    qr={q:i for i,q in enumerate(Q_ORDER)};result=[]
    for r in reserve.to_dict('records'):
        p3=r['prefix_3']
        if p3 not in p3rank:continue
        q=int(r['source_quantile_index']);rotation=(sr[r['primary_source']]-p3rank[p3])%max(1,len(sources))
        result.append({'sequence':tuple(map(int,r['sequence'].split('|'))),'candidate_id':r['candidate_id'],
                       'reason':'structural_reserve_stratified','sort':(p3rank[p3],qr.get(q,99),rotation,int(r['proxy_rank'])),
                       'p3_rank':p3rank[p3],'quantile_priority':qr.get(q,99),'rotated_source_rank':rotation,'proxy_rank':int(r['proxy_rank'])})
    cp={'proxy_top':0,'ensemble_disagreement':1,'sequence_diversity':2,'heuristic':3,'random':4}
    for r in primary.to_dict('records'):
        p3=r['prefix_3']
        if p3 not in p3rank:continue
        result.append({'sequence':tuple(map(int,r['sequence'].split('|'))),'candidate_id':r['candidate_id'],
                       'reason':'primary_shortlist_channel','sort':(p3rank[p3],cp.get(r['channel'],9),50,int(r['proxy_rank'])),
                       'p3_rank':p3rank[p3],'quantile_priority':'NA_PRIMARY_CHANNEL_PRIORITY',
                       'rotated_source_rank':'NA_PRIMARY_CONSTANT_50','proxy_rank':int(r['proxy_rank'])})
    result.sort(key=lambda r:r['sort']);seen=set();unique=[]
    for r in result:
        if r['sequence'] not in seen:seen.add(r['sequence']);unique.append(r)
    return unique,sorted(p3scores)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',required=True,choices=['G2'])
    ap.add_argument('--root',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--offline-only',required=True,action='store_true');args=ap.parse_args()
    out=args.out.resolve();root=args.root.resolve();dest=out/'02_math';dest.mkdir(exist_ok=True)
    home=root.parent/'老家/sci-jcr2区交付';formal=home/'第三周工作/day7_final_method_protocol_freeze_v1.1'
    day2=home/'第四周工作/day2_candidate_screening_v1.0';day3=home/'第四周工作/day3_live_ue_methods_v1.0'
    day4=home/'第四周工作/day4_exact_reference_regret_v1.0';g0=out/'00_audit';g1=out/'01_training'
    start=time.perf_counter();checks=[];sources={};events=[];limitations=[];mapping=[]
    protected=[p for base in [g0,g1,out/'author_adjudications'] for p in base.rglob('*') if p.is_file()]
    protected += [p for p in (out/'tools').glob('*.py') if p.name!='r47_math_check.py']
    seal={p:sha(p) for p in protected}
    frozen={str(Path(r['path']).resolve()):r['sha256'] for r in rows(g0/'source_manifest.csv')}
    bindings=[]
    for base in [day2,day3,day4,formal]:
        manifest=base/('formal_code_manifest.json' if base==formal else 'artifact_manifest.json')
        obj=load(manifest);files=obj.get('files',{})
        if isinstance(files,list):files={r['path']:r['sha256'] for r in files}
        for rel,v in files.items():
            h=v.get('sha256') if isinstance(v,dict) else v
            bindings.append((str((base/rel).resolve()),h,str(manifest)))
    expected={p:(h,record) for p,h,record in bindings}
    def log(event,**data):
        r={'utc':datetime.now(timezone.utc).isoformat(),'event':event,**data};events.append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
        (dest/'G2_automatic_log.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in events)+'\n',encoding='utf-8')
    def use(p,role):
        p=Path(p).resolve();h=sha(p);prior=frozen.get(str(p));bound=expected.get(str(p))
        sources[p]={'path':str(p),'sha256_before':h,'bytes':p.stat().st_size,'role':role,
                    'G0_expected_SHA':prior or '', 'actual_execution_manifest_SHA':bound[0] if bound else '',
                    'binding_record':bound[1] if bound else '', 'provenance':'G0_frozen' if prior else 'G2_additional_archived_asset'}
        if prior and h!=prior:raise RuntimeError('CRITICAL_MISMATCH_SOURCE_G0_SHA '+str(p))
        if bound and h!=bound[0]:raise RuntimeError('CRITICAL_MISMATCH_EXECUTION_MANIFEST_SHA '+str(p))
        return p
    def check(name,ok,actual,expected_value,detail='',critical=True):
        checks.append({'check':name,'status':'PASS' if ok else 'FAIL','actual':actual,'expected':expected_value,'detail':detail})
        if not ok and critical:raise RuntimeError('CRITICAL_MISMATCH '+name+': '+str(actual))
    def locate(m,symbol,formula,variables,index_range,constant):
        obj=m
        for part in symbol.split('.'):obj=getattr(obj,part)
        lines,n=inspect.getsourcelines(obj);path=Path(inspect.getsourcefile(obj)).resolve()
        mapping.append({'formula':formula,'source_path':str(path),'source_sha256':sha(path),'symbol':symbol,
                        'line':n,'end_line':n+len(lines)-1,'variables':variables,'index_range':index_range,'constant':constant})
    adjudication=out/'author_adjudications/20261031_G1_G1R_进入G2_作者阶段性裁定.md'
    log('start',stage='G2',inference=0,UE=0,pure_math_seed=PURE_MATH_SEED,DP_scenarios=list(DP_SCENARIOS))
    all_proxy=[];all_recon=[];all_q=[];all_positions=[];all_prefix=[];all_seed=[];all_obj=[];dp_rows=[];summary=[]
    fatal=None
    try:
        for p in [g0/'source_manifest.csv',g0/'manifest_binding_checks.csv',g0/'version_conflicts.csv',g0/'g0_validation.json',
                  g1/'G1_validation.json',g1/'G1_R_numeric_trace/G1_R_validation.json',adjudication,
                  Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer1_4.7_方法可复现性与公式核查_Codex实施方案.md')]:use(p,'prior_accepted_evidence_or_author_adjudication')
        check('G1_historical_status_preserved',load(g1/'G1_validation.json')['status']=='FAIL_NUMERIC_RECONCILIATION_PENDING',load(g1/'G1_validation.json')['status'],'FAIL_NUMERIC_RECONCILIATION_PENDING')
        check('G1R_accepted_numeric_evidence',load(g1/'G1_R_numeric_trace/G1_R_validation.json')['numerical_cause_reproduced_for_selected_three'],True,True)
        source_paths={n:use(formal/'formal_code'/n,'actual_v1_1_source') for n in ['generate_candidate_pool.py','screen_primary.py','screen_structural_reserve.py','run_full_method_live_ue.py','interfaces_week3.py','run_exact_reference_after_method_freeze.py','run_final_full_method_live_ue.py']}
        for base in [day2,day3,day4]:use(base/'artifact_manifest.json','original_execution_hash_manifest')
        use(formal/'formal_code_manifest.json','original_formal_code_hash_manifest')
        generation=load(use(day2/'02_candidate_pool/generation_freeze_record.json','actual_generation_binding'))
        use(day2/'day2_execution_record.json','actual_execution_record');use(day3/'day3_run_config.json','actual_search_entry_binding')
        actual_gen=use(day2/'02_candidate_pool/scripts/generate_candidate_pool.py','actual_DAY2_generator')
        actual_primary=use(day2/'03_primary_screening/scripts/screen_primary.py','actual_DAY2_primary_source')
        check('actual_generator_SHA_matches_formal_and_freeze',sha(actual_gen)==sha(source_paths['generate_candidate_pool.py'])==generation['generator_script_sha256'],sha(actual_gen),generation['generator_script_sha256'])
        check('actual_primary_SHA_matches_formal',sha(actual_primary)==sha(source_paths['screen_primary.py']),sha(actual_primary),sha(source_paths['screen_primary.py']))
        pool_path=use(day2/'02_candidate_pool/candidate_pool.csv.gz','frozen_candidate_member_objective_arrays')
        p_path=use(day2/'03_primary_screening/screened_candidates.csv','frozen_primary60')
        s_path=use(day2/'04_structural_screening/screened_candidates.csv','frozen_combined_primary_and_reserve')
        r_path=use(day2/'04_structural_screening/structural_reserve.csv.gz','frozen_structural_reserve')
        metadata_path=use(day2/'01_road_selection/final_scenarios.json','fixed_recoverable_road_sets')
        audit_path=use(day2/'01_road_selection/candidate_road_selection_audit.csv','frozen_heuristic_road_inputs')
        physical_path=use(day2/'frozen_inputs/day1_final_scenarios_physical_links.csv','original_physical_state_hash_inputs')
        configs={}
        for folder in ['02_candidate_pool','03_primary_screening','04_structural_screening']:
            fn='candidate_generation_config.json' if folder=='02_candidate_pool' else 'screening_config.json'
            configs[folder]=load(use(day2/folder/fn,'frozen_seed_rule_and_input_bindings'))
        cfg=load(day3/'day3_run_config.json')
        check('candidate_pool_actual_search_input_SHA',sha(pool_path)==cfg['candidate_pool_sha256']==generation['candidate_pool_sha256'],sha(pool_path),cfg['candidate_pool_sha256'])
        check('screened_actual_search_input_SHA',sha(s_path)==cfg['screened_candidates_sha256'],sha(s_path),cfg['screened_candidates_sha256'])
        sys.meta_path.insert(0,NoInferenceImports())
        gen=module(source_paths['generate_candidate_pool.py'],'r47_G2_gen_math_only')
        primary=module(source_paths['screen_primary.py'],'r47_G2_primary_only')
        reserve=module(source_paths['screen_structural_reserve.py'],'r47_G2_reserve_only')
        search=module(source_paths['run_full_method_live_ue.py'],'r47_G2_queue_only')
        api=module(source_paths['interfaces_week3.py'],'r47_G2_hash_only')
        dp=module(source_paths['run_exact_reference_after_method_freeze.py'],'r47_G2_DP_only')
        for m,sym,formula,variables,indices,constant in [
           (gen,'subset_member_losses','predicted state cost exp(yhat)-1','member_loss,predictor.predict_members','mask=0..1023,j=1..10','shape=(1024,10)'),
           (gen,'ProxyObjective.evaluate','P_j=(1/m)sum_k predicted state cost','masks,member_objective','k=0..9','sequence[:9], masks=[0]'),
           (gen,'candidate_row','mu=mean_j(P_j); D=sampleSD_j(P_j)','members,proxy_mean','j=1..10','ddof=1'),
           (primary,'select_scenario','ordered Primary60 channel selection','proxy_rank,selected_ids,channel','five channels','15/10/15/10/10; floor(.30N),floor(.50N)'),
           (reserve,'structural_reserve','prefix2 minima and subgroup quantile positions','prefix2_order,positions','prefix2=top10; q<=10','unique(round(linspace(0,n-1,q)))'),
           (search,'BudgetedSearch.prefix2_scores','C(S1)+C(S2)','prefix,score','ordered p2','tuple(score,prefix)'),
           (search,'BudgetedSearch.build_seed_queue','p3 sum and lexicographic queue keys','p3_rank,q,rotated_source','ordered p3,source','Q=[1,5,10,3,8,2,7,4,6,9]; primary constant50'),
           (search,'BudgetedSearch.masks_for_sequence','m weighted stage masks','masks,current','k=0..9','terminal excluded'),
           (search,'BudgetedSearch.evaluate_sequence','J=mean(stage_losses)','objective,stage_losses','R0..R9','np.mean'),
           (dp,'exact_dp','V(empty)=C(empty); V(S)=min V(S-e)+1[S!=E]C(S)','dp,costs,full','mask=0..1023','J*=dp[1023]/10')]:locate(m,sym,formula,variables,indices,constant)
        call_sites=[]
        for path in sorted((formal/'formal_code').glob('*.py')):
            use(path,'formal_entry_set_call_graph_source');tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('evaluate_proxy_sequence','evaluate_ue_sequence'):
                    call_sites.append({'path':str(path),'line':node.lineno,'call':ast.unparse(node.func)})
        table(dest/'legacy_11_state_formal_call_sites.csv',call_sites,['path','line','call'])
        check('legacy_11_state_helpers_not_formally_called',not call_sites,len(call_sites),0)
        check('frozen_quantile_priority',list(search.QUANTILE_PRIORITY)==list(Q_ORDER),list(search.QUANTILE_PRIORITY),list(Q_ORDER))
        # Stored per-sequence/member targets exist; raw per-state logits were not serialized.
        limitations.append({'item':'1024x10 state-level raw log predictions/loss matrix','status':'NOT_LOCATED_NO_NEW_INFERENCE',
                            'limit':'Numerical mu/D reaggregation uses all frozen member_j_objective columns. Per-stage exp(yhat)-1 and P_j construction are source/call-path verified, not independently replayed from missing state logits.'})
        pool=pd.read_csv(pool_path);literal=pd.read_csv(pool_path,float_precision='round_trip')
        primary_archive=pd.read_csv(p_path);combined_archive=pd.read_csv(s_path);reserve_archive=pd.read_csv(r_path)
        meta=load(metadata_path);roads_by={int(r['scenario_id']):list(map(int,r['selected_recoverable_roads'])) for r in meta['scenarios']}
        audit=pd.read_csv(audit_path);physical=pd.read_csv(physical_path)
        check('frozen_10_scenario_30000_each',pool.groupby('scenario_id').size().to_dict()=={s:30000 for s in roads_by},pool.groupby('scenario_id').size().to_dict(),{s:30000 for s in roads_by})
        member_cols=[f'member_{i:02d}_objective' for i in range(1,11)]
        # Same aggregation as candidate_row, with round-trip CSV decoding and contiguous rows.
        members=np.ascontiguousarray(literal[member_cols].to_numpy(dtype=float))
        mu=members.mean(axis=1);dis=members.std(axis=1,ddof=1)
        err_mu=np.abs(mu-literal.proxy_objective_mean.to_numpy());err_dis=np.abs(dis-literal.ensemble_disagreement.to_numpy())
        pd.DataFrame({'scenario_id':literal.scenario_id,'candidate_id':literal.candidate_id,
                      'mu_recomputed':mu,'mu_archive':literal.proxy_objective_mean,'mu_abs_error':err_mu,
                      'D_recomputed_ddof1':dis,'D_archive':literal.ensemble_disagreement,'D_abs_error':err_dis,
                      'K':10,'status':np.where((err_mu<=TOL)&(err_dis<=TOL),'PASS','FAIL'),
                      'scope':'frozen sequence-member objectives; raw state logits unavailable'}).to_csv(dest/'proxy_disagreement_formula_check.csv',index=False,encoding='utf-8-sig')
        check('all_300000_proxy_mean_and_D',bool(((err_mu<=TOL)&(err_dis<=TOL)).all()),{'max_mean_error':float(err_mu.max()),'max_D_error':float(err_dis.max())},'absolute errors<=1e-12')
        # No numerical updates of ranking inputs: use the actual reader path for original filtering.
        for sid in sorted(roads_by):
            frame=pool[pool.scenario_id==sid].copy();roads=roads_by[sid]
            check(f'{sid}_valid_fixed_road_permutations',all(len(set(v.split('|')))==10 and set(map(int,v.split('|')))==set(roads) for v in frame.sequence),True,True)
            ranked=frame.sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort')
            check(f'{sid}_proxy_rank_order',ranked.proxy_rank.tolist()==list(range(1,30001)),True,True)
            raw=primary_archive[primary_archive.scenario_id==sid].sort_values('screen_order')
            seed=int(configs['03_primary_screening']['random_seed_base'])+sid
            replay=independent_primary(frame,roads,audit[audit.scenario_id==sid],seed)
            frozen_replay=primary.select_scenario(frame,roads,audit[audit.scenario_id==sid],np.random.default_rng(seed))
            ids_ok=replay.candidate_id.tolist()==raw.candidate_id.tolist()==frozen_replay.candidate_id.tolist()
            check(f'{sid}_Primary60_exact_order',ids_ok,ids_ok,True)
            for i,(r,a) in enumerate(zip(replay.to_dict('records'),raw.to_dict('records')),1):
                ok=all(r[k]==a[k] for k in ['candidate_id','sequence','channel','channel_rank','screen_order','proxy_rank'])
                all_recon.append({'scenario_id':sid,'tier':'Primary60','order':i,'candidate_id_rebuilt':r['candidate_id'],
                                  'candidate_id_archived':a['candidate_id'],'channel':r['channel'],'channel_rank':r['channel_rank'],
                                  'proxy_rank':r['proxy_rank'],'status':'PASS' if ok else 'FAIL'})
                check(f'{sid}_Primary_row_{i}',ok,ok,True)
            rebuilt,pos_rows,p2min=independent_reserve(frame,set(raw.candidate_id))
            source_reserve=reserve.structural_reserve(frame,set(raw.candidate_id))
            ar=reserve_archive[reserve_archive.scenario_id==sid].sort_values('channel_rank')
            check(f'{sid}_Reserve_exact_order',rebuilt.candidate_id.tolist()==ar.candidate_id.tolist()==source_reserve.candidate_id.tolist(),True,True)
            all_positions.extend(pos_rows)
            for i,(r,a) in enumerate(zip(rebuilt.to_dict('records'),ar.to_dict('records')),1):
                ok=all(r[k]==a[k] for k in ['candidate_id','sequence','channel_rank','proxy_rank','prefix_2','prefix_3','prefix_2_cluster_rank','source_quantile_index','source_quantile_total','primary_source'])
                all_recon.append({'scenario_id':sid,'tier':'StructuralReserve_top10_prefix2','order':i,
                                  'candidate_id_rebuilt':r['candidate_id'],'candidate_id_archived':a['candidate_id'],
                                  'prefix_2':r['prefix_2'],'prefix_3':r['prefix_3'],'proxy_rank':r['proxy_rank'],
                                  'quantile_index':r['source_quantile_index'],'status':'PASS' if ok else 'FAIL'})
            check(f'{sid}_Reserve_all_metadata',all(r['status']=='PASS' for r in all_recon if r['scenario_id']==sid),True,True)
            screened=combined_archive[combined_archive.scenario_id==sid].copy();screened['seq_tuple']=screened.sequence.map(search.parse_sequence)
            log_path=use(day3/f'06_full_method/scenario_{sid}/ue_state_audit_log.csv.gz','actual_frozen_query_ledger')
            result_path=use(day3/f'06_full_method/scenario_{sid}/ue_reranking_results.csv','actual_frozen_sequence_evaluations')
            use(day3/f'06_full_method/scenario_{sid}/full_method_output_freeze.json','actual_method_output_seal')
            ledger=pd.read_csv(log_path,float_precision='round_trip');results=pd.read_csv(result_path,float_precision='round_trip')
            events=ledger.to_dict('records');costs={int(r['subset_mask']):float(r['loss']) for r in events}
            engine=search.BudgetedSearch.__new__(search.BudgetedSearch)
            engine.roads=tuple(roads);engine.road_to_bit={r:i for i,r in enumerate(roads)};engine.sid=sid
            engine.physical=physical[physical.scenario_id==sid].sort_values('physical_link_id').reset_index(drop=True);engine.api=api
            engine.screened=screened;engine.reserve=screened[screened.screening_tier=='structural_reserve'];engine.primary=screened[screened.screening_tier=='primary_shortlist']
            # These methods only read archived states and construct sort keys. No UE method exists on this audit object.
            for mask,h in ledger[['subset_mask','state_hash']].drop_duplicates().itertuples(index=False,name=None):
                check(f'{sid}_state_hash_mask_{int(mask)}',engine.state_hash(int(mask))==h,engine.state_hash(int(mask)),h)
            p1_end=int(np.flatnonzero(ledger.phase.to_numpy()=='B_prefix3_initial')[-1]);p2_end=int(np.flatnonzero(ledger.phase.to_numpy()=='B_prefix3_remaining')[-1])
            queue_versions={};prefix_scores={}
            for stage,end in [('initial_after_prefix3',p1_end),('expanded_after_prefix3',p2_end)]:
                known=set(int(r['subset_mask']) for r in events[:end+1]);engine.state_by_hash={engine.state_hash(mask):{'loss':costs[mask]} for mask in known}
                engine.build_seed_queue();independent,p3_scores=independent_queue(screened,roads,costs,known)
                exact=(len(independent)==len(engine._seed_queue) and all(a['sequence']==b['sequence'] and a['reason']==b['reason'] and a['sort']==b['sort'] for a,b in zip(independent,engine._seed_queue)))
                check(f'{sid}_{stage}_queue_full_order',exact,len(independent),len(engine._seed_queue))
                queue_versions[stage]=independent
                for rank,r in enumerate(independent,1):all_q.append({'scenario_id':sid,'queue_snapshot':stage,'queue_position':rank,
                    'candidate_id':r['candidate_id'],'sequence':'|'.join(map(str,r['sequence'])),'reason':r['reason'],'sort_key':r['sort'],
                    'p3_rank':r['p3_rank'],'quantile_priority':r['quantile_priority'],'rotated_source_rank':r['rotated_source_rank'],'proxy_rank':r['proxy_rank'],
                    'source_function_position':rank,'status':'PASS' if exact else 'FAIL'})
                for rank,(score,p3) in enumerate(p3_scores,1):all_prefix.append({'scenario_id':sid,'queue_snapshot':stage,'prefix_3':p3,'true_ordered_prefix_score':score,'p3_rank':rank})
            # Recover actual fixed sequence evaluations directly from request blocks, not by running search.
            by_sequence_id={str(r['sequence_id']):r for r in results.to_dict('records')}
            known=set();completed=set();attempted=set();seen_D={64:False,128:False,256:False,512:False};pos=0
            starts={64:int(events[p1_end]['ue_calls_after']),128:int(events[p2_end]['ue_calls_after']),256:128,512:256}
            cutoffs={t:starts[t]+int((t-starts[t])*(.55 if t==64 else .5)) for t in starts}
            masks_cache={r['sequence']:sequence_masks(r['sequence'],roads) for q in queue_versions.values() for r in q}
            while pos<len(events):
                e=events[pos];phase=e['phase']
                if phase in ('C_true_ue_reranking','D_local_search') and str(e['reason']).endswith(':R0'):
                    block=events[pos:pos+10];record=by_sequence_id[str(e['sequence_id'])];seq=tuple(map(int,record['sequence'].split('|')))
                    ms=search.BudgetedSearch.masks_for_sequence(engine,seq)
                    block_ok=(len(block)==10 and [int(r['subset_mask']) for r in block]==ms and all(str(r['sequence_id'])==str(e['sequence_id']) for r in block))
                    check(f'{sid}_sequence_block_{pos}',block_ok,block_ok,True)
                    val=float(np.mean([float(r['loss']) for r in block]));err=abs(val-float(record['ue_objective']))
                    all_obj.append({'scenario_id':sid,'sequence_id':e['sequence_id'],'first_request_index':e['request_index'],'phase':phase,
                                    'weighted_states':len(ms),'terminal_included':1023 in ms,'objective_recomputed':val,'objective_archived':record['ue_objective'],'abs_error':err,'status':'PASS' if err<=TOL else 'FAIL'})
                    check(f'{sid}_sequence_objective_{pos}',err<=TOL,err,TOL)
                    before=int(e['ue_calls_after'])-(0 if bool(e['cache_hit']) else 1)
                    target=64 if pos<p2_end else (128 if before<128 else 256 if before<256 else 512)
                    if phase=='D_local_search':seen_D[target]=True
                    else:
                        q=queue_versions['initial_after_prefix3' if pos<p2_end else 'expanded_after_prefix3']
                        def first_fit(balance):
                            if balance<0:return None
                            for r in q:
                                s=r['sequence']
                                if s in attempted or s in completed:continue
                                if sum(m not in known for m in masks_cache[s])<=balance:return r
                            return None
                        chosen=None;mode='seed_share_cutoff'
                        if not seen_D[target] and before<cutoffs[target]:chosen=first_fit(cutoffs[target]-before)
                        if chosen is None:chosen=first_fit(target-before);mode='remaining_interval_budget'
                        ok=chosen is not None and chosen['sequence']==seq and chosen['reason']==record['evaluation_reason']
                        all_seed.append({'scenario_id':sid,'request_index':e['request_index'],'sequence_id':e['sequence_id'],'interval_target':target,'calls_before':before,
                                         'mode':mode,'seed_share_cutoff':cutoffs[target],'selected_candidate_id':record['candidate_id'],
                                         'expected_sequence':'|'.join(map(str,chosen['sequence'])) if chosen else 'NONE','actual_sequence':record['sequence'],'status':'PASS' if ok else 'FAIL'})
                        check(f'{sid}_actual_first_fit_seed_{pos}',ok,record['sequence'],'first eligible fitting queue entry')
                        attempted.add(seq)
                    for b in block:known.add(int(b['subset_mask']))
                    completed.add(seq);pos+=10
                else:known.add(int(e['subset_mask']));pos+=1
            summary.append({'scenario_id':sid,'pool_candidates':len(frame),'Primary60':len(raw),'Reserve_candidates':len(ar),
                            'prefix2_clusters':len(p2min),'queue_initial':len(queue_versions['initial_after_prefix3']),
                            'queue_expanded':len(queue_versions['expanded_after_prefix3']),'sequence_evaluations':len(results),
                            'seed_evaluations_checked':sum(r['scenario_id']==sid for r in all_seed)})
            log('scenario_rebuilt',**summary[-1])
        # DP: generic recurrence vs complete permutations; dyadic costs avoid an arbitrary numerical-scale issue.
        rng=np.random.default_rng(PURE_MATH_SEED)
        for m in range(1,7):
            for case in range(3):
                c=rng.integers(1,100,size=1<<m).astype(float)/16
                best=min(sum(c[s] for s in sequence_masks(seq,list(range(m))))/m for seq in itertools.permutations(range(m)))
                actual,_=independent_dp(c,m)
                for test,value,expected_value in [('exhaustive_vs_DP',actual,best),
                    ('terminal_sentinel',independent_dp(np.array([1e100 if i==(1<<m)-1 else v for i,v in enumerate(c)]),m)[0],actual),
                    ('initial_cost_delta',independent_dp(np.array([v+.375 if i==0 else v for i,v in enumerate(c)]),m)[0]-actual,.375/m)]:
                    error=abs(value-expected_value);dp_rows.append({'case_type':'pure_math','m':m,'case':case,'test':test,'expected':expected_value,'actual':value,'abs_error':error,'tolerance':TOL,'status':'PASS' if error<=TOL else 'FAIL','input_seed':PURE_MATH_SEED,'input_cost_sha256':hashlib.sha256(c.tobytes()).hexdigest()})
                    check(f'DP_m{m}_case{case}_{test}',error<=TOL,error,TOL)
        reference_dir=day4/'08_exact_reference_after_method_freeze'
        costs_path=use(reference_dir/'subset_ue_costs.csv','archived_complete_UE_state_table_read_only')
        solution_path=use(reference_dir/'exact_dp_solution.json','frozen_conditional_DP_reference')
        path_path=use(reference_dir/'exact_dp_path.csv','frozen_DP_stage_weights')
        cost_table=pd.read_csv(costs_path,float_precision='round_trip');solutions=load(solution_path)['scenarios'];path_table=pd.read_csv(path_path,float_precision='round_trip')
        for sid in DP_SCENARIOS:
            frame=cost_table[cost_table.scenario_id==sid].copy();roads=roads_by[sid]
            check(f'{sid}_DP_state_index',len(frame)==1024 and set(frame.subset_mask)==set(range(1024)),len(frame),1024)
            check(f'{sid}_DP_state_masks_and_counts',all(int(r.restored_count)==int(r.subset_mask).bit_count() and set(map(int,str(r.restored_links).split(';')))==set(roads[i] for i in range(10) if int(r.subset_mask)&(1<<i)) if pd.notna(r.restored_links) else int(r.subset_mask)==0 for r in frame.itertuples()),True,True)
            error=float(np.max(np.abs(frame.loss.to_numpy()-(frame.tstt.to_numpy()/api.BASELINE_TSTT-1))))
            check(f'{sid}_DP_units_TSTT_baseline_excess',error<=TOL,error,TOL)
            costs=dict(zip(frame.subset_mask.astype(int),frame.loss.astype(float)))
            generic,seq=independent_dp(costs,10,roads);frozen_dp,stages=dp.exact_dp(frame,roads);expected_value=float(solutions[str(sid)]['exact_objective'])
            for test,actual in [('independent_DP_vs_archive',generic),('frozen_DP_function_vs_archive',frozen_dp['exact_objective'])]:
                error=abs(actual-expected_value);dp_rows.append({'case_type':'archived_m10','scenario_id':sid,'m':10,'test':test,'expected':expected_value,'actual':actual,'abs_error':error,'tolerance':TOL,'status':'PASS' if error<=TOL else 'FAIL','source':str(costs_path),'source_sha256':sha(costs_path)})
                check(f'{sid}_{test}',error<=TOL,error,TOL)
            check(f'{sid}_DP_sequence_reference',list(seq)==solutions[str(sid)]['optimal_sequence']==frozen_dp['optimal_sequence'],list(seq),solutions[str(sid)]['optimal_sequence'])
            oldpath=path_table[path_table.scenario_id==sid]
            check(f'{sid}_DP_terminal_weight_zero',oldpath.stage_weight.tolist()==[.1]*10+[0.0],oldpath.stage_weight.tolist(),[.1]*10+[0.0])
        log('DP_tests_complete',rows=len(dp_rows),model_inference=0,UE=0)
    except Exception as e:
        fatal=str(e)
        import traceback
        (dest/'scientific_issue_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        log('stopped_on_issue',reason=fatal)
    finally:
        table(dest/'primary_reserve_reconstruction_checks.csv',all_recon,['scenario_id','tier','order','candidate_id_rebuilt','candidate_id_archived','channel','channel_rank','prefix_2','prefix_3','proxy_rank','quantile_index','status'])
        table(dest/'queue_reconstruction_checks.csv',all_q,['scenario_id','queue_snapshot','queue_position','candidate_id','sequence','reason','sort_key','p3_rank','quantile_priority','rotated_source_rank','proxy_rank','source_function_position','status'])
        table(dest/'quantile_position_reconstruction.csv',all_positions)
        table(dest/'prefix3_score_reconstruction.csv',all_prefix)
        table(dest/'actual_seed_first_fit_checks.csv',all_seed)
        table(dest/'archived_sequence_objective_checks.csv',all_obj)
        table(dest/'dp_test_results.csv',dp_rows)
        table(dest/'algorithm_to_equation_map.csv',mapping)
        table(dest/'scenario_reconstruction_summary.csv',summary)
        unchanged=[{'path':str(p),'sha256_before':h,'sha256_after':sha(p),'unchanged':h==sha(p)} for p,h in seal.items()]
        table(dest/'prior_G0_G1_G1R_immutability.csv',unchanged)
        intact=all(r['unchanged'] for r in unchanged)
        checks.append({'check':'prior_G0_G1_G1R_and_adjudication_unchanged','status':'PASS' if intact else 'FAIL','actual':sum(r['unchanged'] for r in unchanged),'expected':len(unchanged),'detail':''})
        for p,r in sources.items():r['sha256_after']=sha(p);r['unchanged']=r['sha256_after']==r['sha256_before']
        table(dest/'G2_source_manifest.csv',list(sources.values()))
        source_intact=all(r['unchanged'] for r in sources.values())
        checks.append({'check':'used_original_sources_unchanged','status':'PASS' if source_intact else 'FAIL','actual':sum(r['unchanged'] for r in sources.values()),'expected':len(sources),'detail':''})
        failed=[r for r in checks if r['status']=='FAIL']
        status='CRITICAL_MISMATCH_STOP' if fatal or failed else 'PASS_WITH_STATE_LOG_ARCHIVE_LIMITATION'
        validation={'stage':'G2','status':status,'fatal_stop':fatal,'checks_total':len(checks),'checks_passed':len(checks)-len(failed),
                    'failed_checks':failed,'checks':checks,'limitations':limitations,'source_count':len(sources),
                    'proxy_candidate_rows':len(literal) if 'literal' in locals() else 0,'primary_reserve_rows':len(all_recon),
                    'queue_rows':len(all_q),'actual_seed_checks':len(all_seed),'archived_sequence_objective_checks':len(all_obj),
                    'DP_test_rows':len(dp_rows),'pure_math_seed':PURE_MATH_SEED,'archived_DP_scenarios':list(DP_SCENARIOS),
                    'tolerances':{'floating_absolute':TOL,'DP_absolute':TOL,'discrete_ids_order_masks_quantiles':'exact equality'},
                    'operations':{'model_inference':0,'checkpoint_loads':0,'UE_solves':0,'new_floods':0,'training':0,'formal_search_runs':0,
                                  'pure_frozen_screening_reconstructions':len(summary),'pure_queue_reconstructions':2*len(summary)},
                    'original_G1_status':load(g1/'G1_validation.json')['status'],'historical_acceptances_modified':False,
                    'G3_G4':'NOT_RUN','must_stop_after_G2':True,'elapsed_seconds':round(time.perf_counter()-start,3),
                    'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'platform':platform.platform()},
                    'script':str(Path(__file__).resolve()),'script_sha256':sha(Path(__file__))}
        dump(dest/'G2_validation.json',validation);table(dest/'G2_automatic_checks.csv',checks)
        # A separate report builder only formats already computed results.
        from r47_math_reporting import build_reports
        build_reports(out,dest,validation,summary,limitations,mapping,adjudication)
        log('finished',status=status,passed=validation['checks_passed'],total=validation['checks_total'])
        outputs=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='G2_output_SHA256.csv']
        for p in [Path(__file__).resolve(),out/'tools/r47_math_reporting.py',adjudication]:outputs.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
        table(dest/'G2_output_SHA256.csv',outputs)
    return 1 if fatal or failed else 0

if __name__=='__main__':raise SystemExit(main())
