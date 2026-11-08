"""Read-only archived-state arithmetic. No UE, proxy or search-algorithm imports."""
from pathlib import Path
import sys, json, hashlib, time, itertools, math, platform
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parents[1]
REV=Path('E:/jcr2区意见/返稿');BASE=REV/'4.1专项返修_20261026';P52=OUT.parent/'comment5_2'
CHECKS=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def save(name,rows):
    df=pd.DataFrame(rows);df.to_csv(OUT/name,index=False,float_format='%.17g');return df
def check(name,passed,actual=None,expected=None,evidence=''):
    row=dict(check=name,status='PASS' if bool(passed) else 'FAIL',actual=actual,expected=expected,evidence=str(evidence));CHECKS.append(row)
    if not passed:
        dump(OUT/'audit/numerical_checks.json',CHECKS)
        raise RuntimeError(f'CRITICAL_MISMATCH {name}: {actual} expected {expected}')
def close(a,b,tol=1e-12):return abs(float(a)-float(b))<=tol*max(1.,abs(float(a)),abs(float(b)))
def forward(c,d,roads):
    """Two distinct sequence labels/state; rank1 is second best including exact ties."""
    n=len(roads);N=1<<n
    val=np.full((N,2),np.inf);pred=np.full((N,2),-1,dtype=int);prank=pred.copy();val[0,0]=0.
    ordered=sorted(range(n),key=lambda i:roads[i])
    for s in range(1,N):
        choices=[]
        for bit in ordered:
            if s&(1<<bit):
                before=s^(1<<bit)
                for rank in (0,1):
                    if np.isfinite(val[before,rank]):
                        choices.append((float(val[before,rank]+d[bit]*c[before]),roads[bit],rank,bit))
        choices.sort()
        for rank,(v,_,r,bit) in enumerate(choices[:2]):val[s,rank]=v;pred[s,rank]=bit;prank[s,rank]=r
    def path(rank):
        s=N-1;seq=[]
        while s:
            bit=int(pred[s,rank]);seq.append(roads[bit]);oldrank=rank;rank=int(prank[s,oldrank]);s^=1<<bit
        return seq[::-1]
    return val,pred,prank,path(0),path(1) if n>1 else []
def reverse(c,d):
    n=len(d);end=(1<<n)-1;z=np.full(end+1,np.inf);z[end]=0.
    for s in range(end-1,-1,-1):
        z[s]=min(float(d[i]*c[s]+z[s|(1<<i)]) for i in range(n) if not s&(1<<i))
    return z
def eval_path(seq,roads,c,d):
    b={e:i for i,e in enumerate(roads)};s=0;total=0.;rows=[]
    for k,e in enumerate(seq):
        duration=float(d[b[e]]);v=duration*float(c[s]);rows.append((k,s,e,duration,float(c[s]),v));total+=v;s|=1<<b[e]
    rows.append((len(seq),s,None,0.,float(c[s]),0.));return total/sum(d),rows
def tau(a,b):
    ranks={e:i for i,e in enumerate(b)};inv=sum(ranks[a[i]]>ranks[a[j]] for i in range(len(a)) for j in range(i+1,len(a)))
    return 1-4*inv/(len(a)*(len(a)-1))
def main():
    manifest=json.loads((OUT/'run_manifest.json').read_text(encoding='utf-8'))
    for r in manifest['critical_sources']:check('input_hash_'+Path(r['path']).name,sha(r['path'])==r['sha256'],sha(r['path']),r['sha256'],r['path'])
    for r in manifest['audit_code']:check('frozen_audit_code_'+Path(r['path']).name,sha(r['path'])==r['sha256'],sha(r['path']),r['sha256'])
    T0=manifest['original_dry_TSTT_raw'];Q=manifest['Q'];factor=.6*T0/Q
    oldpaths=json.loads((REV/'reviewer_4_2/02_original_method_path_reevaluation/frozen_paths.json').read_text(encoding='utf-8'))
    olddp=json.loads((REV/'reviewer_4_2/00_protocol_and_input_audit/source_records/archive/exact_dp_solution.json').read_text(encoding='utf-8'))['scenarios']
    physical=pd.read_csv(BASE/'inputs/historical_1001_1010.csv')
    s0=pd.read_csv(REV/'reviewer_4_2/00_protocol_and_input_audit/S0_input_manifest.csv')
    physicalhash=sha(BASE/'inputs/historical_1001_1010.csv')
    expected=s0.loc[s0.data_role=='historical physical inputs','sha256'].iloc[0]
    check('original_scenario_hash_4_2',physicalhash==expected,physicalhash,expected)
    odpath=BASE/'source_snapshot/code/model_backend/data_src/SiouxFalls_flood_benchmark/processed/od_long.csv'
    od=pd.read_csv(odpath);check('OD_Q_360600',od.demand.sum()==Q,float(od.demand.sum()),Q);check('positive_OD_528',(od.demand>0).sum()==528,int((od.demand>0).sum()),528)
    p52val=json.loads((P52/'final_validation.json').read_text(encoding='utf-8'));check('5_2_previously_accepted',p52val['status']=='PASS',p52val['status'],'PASS')
    # Frozen deterministic synthetic tests: no stochastic fitting or traffic calculations.
    tests=[]
    for n in range(1,8):
        N=1<<n;roads=list(range(101,101+n));c=np.array([1+(s*13%31)/17+(N-s)/N for s in range(N)],dtype=float);d=np.array([.5+(i%4)*.25 for i in range(n)])
        v,_,_,seq,_=forward(c,d,roads);enum=min(eval_path(p,roads,c,d)[0] for p in itertools.permutations(roads));rv=reverse(c,d)[0]/sum(d);actual=v[-1,0]/sum(d)
        tests.append(dict(test='exhaustive_m_'+str(n),m=n,expected=enum,actual=actual,absolute_difference=abs(actual-enum),reverse_value=rv,pass_check=close(actual,enum) and close(actual,rv)))
        check('exhaustive_m_'+str(n),tests[-1]['pass_check'],actual,enum)
        sentinel=c.copy();sentinel[-1]=1e30;new=forward(sentinel,d,roads)[0][-1,0]/sum(d)
        tests.append(dict(test='terminal_sentinel_m_'+str(n),m=n,expected=actual,actual=new,absolute_difference=abs(new-actual),pass_check=new==actual));check('terminal_zero_weight_m_'+str(n),new==actual,new,actual)
        uniform=np.ones(n);orig=forward(c,uniform,roads)[0][-1,0]/n;shift=c.copy();shift[0]+=2.75;new=forward(shift,uniform,roads)[0][-1,0]/n
        tests.append(dict(test='initial_cost_shift_m_'+str(n),m=n,expected=2.75/n,actual=new-orig,absolute_difference=abs(new-orig-2.75/n),pass_check=close(new-orig,2.75/n)));check('initial_shift_m_'+str(n),close(new-orig,2.75/n),new-orig,2.75/n)
    save('audit/deterministic_DP_tests.csv',tests)
    costs={};tables={};policies={};auditrows=[];unitrows=[];uniforms={};source_rows=[]
    p52stage=pd.read_csv(P52/'stage_metrics_all10.csv')
    for sid in range(1001,1011):
        pr=[r for r in oldpaths if r['scenario_id']==sid];roads=pr[0]['roads']
        cfg=[c for c in manifest['configs'] if c['scenario_id']==sid][0];check(f'road_bit_map_{sid}',roads==cfg['roads_original_bit_order'],roads,cfg['roads_original_bit_order'])
        check(f'old_DP_road_map_{sid}',roads==olddp[str(sid)]['candidate_roads'],roads,olddp[str(sid)]['candidate_roads'])
        path=REV/f'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables/scenario_{sid}_path_solver_1e9_1024_states.csv.gz'
        t=pd.read_csv(path).sort_values('subset_mask');c=t.loss.to_numpy(float)
        check(f'state_masks_complete_{sid}',len(t)==1024 and t.subset_mask.tolist()==list(range(1024)),len(t),1024,path)
        check(f'finite_positive_tstt_{sid}',np.isfinite(t.tstt).all() and (t.tstt>0).all() and np.isfinite(c).all(),float(t.tstt.min()),'>0')
        check(f'RG_convergence_{sid}',t.converged.astype(str).str.lower().eq('true').all() and t.relative_gap.max()<=1e-9,float(t.relative_gap.max()),'<=1e-9')
        normalized=t.tstt.to_numpy(float)/T0-1
        check(f'normalization_original_T0_{sid}',np.allclose(c,normalized,rtol=1e-13,atol=1e-12),float(np.max(abs(c-normalized))),'<1e-12+relative')
        selected=physical[(physical.scenario_id==sid)&physical.physical_link_id.isin(roads)]
        check(f'recoverable_roads_closed_{sid}',len(selected)==10 and selected.is_closed.eq(1).all(),int(selected.is_closed.sum()),10)
        policies[sid]={'full_method':next(r['sequence'] for r in pr if r['label']=='Proposed_B256'),'exact_DP_original_rho1':olddp[str(sid)]['optimal_sequence'],'permutation_SA_original_descriptive':next(r['sequence'] for r in pr if r['label']=='SA_original_fixed_seed')}
        for name,seq in policies[sid].items():check(f'fixed_sequence_{sid}_{name}',len(seq)==10 and set(seq)==set(roads),seq,'permutation of original E')
        for r in pr:
            _,stages=eval_path(r['sequence'],roads,c,np.ones(10));check(f'archive_masks_{sid}_{r["label"]}',[s[1] for s in stages[:-1]]==r['masks_R0_R9'],[s[1] for s in stages[:-1]],r['masks_R0_R9'])
        on52=p52stage[(p52stage.scenario_id==sid)&p52stage.rho.eq(1)]
        discrepancy=max(abs(float(r.tstt_raw)-float(t.iloc[int(r.subset_mask)].tstt))/float(t.iloc[int(r.subset_mask)].tstt) for r in on52.itertuples())
        check(f'5_2_archived_cost_agreement_{sid}',discrepancy<1e-14,discrepancy,'<1e-14')
        source_rows.extend(dict(scenario_id=sid,subset_mask=int(r.subset_mask),tstt_raw=float(r.tstt),cost=float(r.loss),relative_gap=float(r.relative_gap),source_path=str(path),source_sha256=sha(path)) for r in t.itertuples())
        costs[sid]=c;tables[sid]=t
        auditrows.append(dict(scenario_id=sid,state_rows=len(t),mask_min=0,mask_max=1023,max_RG=float(t.relative_gap.max()),all_converged=True,normalization_max_abs_difference=float(np.max(abs(c-normalized))),road_bit_order=json.dumps(roads),source_path=str(path),sha256=sha(path),fields=json.dumps(t.columns.tolist()),comparison_5_2_max_relative=discrepancy))
    save('audit/highprecision_state_table_audit.csv',auditrows);save('raw/authoritative_state_costs.csv',source_rows)
    result=[];stage_rows=[];dp_rows=[];arrays=[];dpsummary=[];absolute=[]
    for cfg in manifest['configs']:
        sid=cfg['scenario_id'];roads=cfg['roads_original_bit_order'];d=np.array(cfg['durations_original_bit_order']);c=costs[sid];D=float(sum(d));key=cfg['config_id']
        check('duration_positive_total_'+key,np.all(d>0) and D==10.,D,10.)
        start=time.perf_counter();v,p,r,seq,seq2=forward(c,d,roads);forwardtime=time.perf_counter()-start
        start=time.perf_counter();z=reverse(c,d);reversetime=time.perf_counter()-start;star=float(v[-1,0]/D);second=float(v[-1,1]/D)
        check('DP_reverse_'+key,close(star,z[0]/D),star,float(z[0]/D));check('positive_oracle_'+key,star>0,star,'>0')
        scored=eval_path(seq,roads,c,d)[0];check('DP_path_value_'+key,close(star,scored),scored,star)
        check('second_best_distinct_'+key,seq2!=seq and close(eval_path(seq2,roads,c,d)[0],second),second,'second distinct sequence objective')
        if cfg['level']=='uniform':
            original=json.loads((BASE/f'development/legacy_precision/scenario_{sid}/exact_solution.json').read_text(encoding='utf-8'))
            check(f'uniform_accepted_objective_{sid}',close(star,original['new_table_objective']),star,original['new_table_objective'])
            oldvalue=eval_path(policies[sid]['exact_DP_original_rho1'],roads,c,d)[0];check(f'uniform_original_path_optimal_{sid}',close(star,oldvalue),oldvalue,star)
            uniforms[sid]=seq
        uniform=uniforms[sid];gap=second-star;near=gap<=1e-12*max(1.,abs(star))
        common=dict(config_id=key,scenario_id=sid,level=cfg['level'],allocation=cfg['allocation'],D=D,J_star=star,oracle_sequence=json.dumps(seq),oracle_first_road=seq[0],oracle_first3=json.dumps(seq[:3]),second_sequence=json.dumps(seq2),second_J=second,second_best_gap=gap,near_tie=near,first_road_changed=seq[0]!=uniform[0],first3_order_changed=seq[:3]!=uniform[:3],full_order_changed=seq!=uniform,kendall_tau_vs_uniform=tau(seq,uniform),prefix3_set_overlap=len(set(seq[:3])&set(uniform[:3]))/3,prefix5_set_overlap=len(set(seq[:5])&set(uniform[:5]))/5,forward_seconds=forwardtime,reverse_seconds=reversetime,forward_reverse_abs_difference=abs(star-z[0]/D))
        # Near tie can affect late swaps only; report independently constrained first-road alternatives.
        first_objectives={roads[i]:float((d[i]*c[0]+z[1<<i])/D) for i in range(10)}
        alternative=min(value for e,value in first_objectives.items() if e!=seq[0]);common['first_road_alternative_gap']=alternative-star
        common['first_road_near_tie']=alternative-star<=1e-12*max(1.,abs(star))
        dpsummary.append(common)
        for mask in range(1024):
            arrays.append(dict(config_id=key,scenario_id=sid,subset_mask=mask,W_best=float(v[mask,0]),W_second=float(v[mask,1]) if np.isfinite(v[mask,1]) else None,pred_bit_best=int(p[mask,0]),pred_bit_second=int(p[mask,1]),pred_rank_best=int(r[mask,0]),pred_rank_second=int(r[mask,1]),reverse_remaining_cost=float(z[mask])))
        for name,path in {**policies[sid],'duration_aware_exact_DP_oracle':seq}.items():
            J,stages=eval_path(path,roads,c,d);delta=J-star
            check('policy_dominance_'+key+'_'+name,delta>=-1e-12*max(1.,abs(star)),delta,'>= floating tolerance')
            regret=100*delta/star;deltaATT=factor*delta
            row={**common,'policy':name,'sequence':json.dumps(path),'J_policy':J,'regret_pct':regret,'weighted_average_stage_ATT_minutes':factor*(1+J),'delta_ATT_minutes':deltaATT,'delta_weighted_mean_TSTT_veh_h':.01*T0*delta,'oracle_average_stage_ATT_minutes':factor*(1+star),'comparison_type':'post-study descriptive fixed SA' if name.startswith('permutation_SA') else 'frozen policy transfer vs offline full-information oracle'}
            result.append(row)
            for k,mask,e,duration,C,weighted in stages:
                stage_rows.append(dict(config_id=key,scenario_id=sid,level=cfg['level'],allocation=cfg['allocation'],policy=name,stage=k,subset_mask=mask,next_road=e,duration_weight=duration,normalized_time_weight=duration/D,C=C,weighted_C=weighted,tstt_raw=float(tables[sid].iloc[mask].tstt),stage_ATT_minutes=.6*float(tables[sid].iloc[mask].tstt)/Q))
            recompute=sum(s[5] for s in stages)/D
            physical_att=sum(s[3]*.6*float(tables[sid].iloc[s[1]].tstt)/Q for s in stages)/D
            check('stage_reconciliation_'+key+'_'+name,close(recompute,J) and close(physical_att,factor*(1+J)) and stages[-1][3]==0.,max(abs(recompute-J),abs(physical_att-factor*(1+J))),'stage objective, physical ATT and S10 zero')
            if cfg['level']=='uniform' and name!='duration_aware_exact_DP_oracle':absolute.append(row)
        print('DP',key,'PASS',flush=True)
    df=save('Table_duration_robustness.csv',result);save('raw/stage_time_weights_all_policies.csv',stage_rows);save('raw/DP_state_values_and_predecessors.csv',arrays);dp=save('raw/DP_optimal_sequences_and_crosschecks.csv',dpsummary);save('Table_original_absolute_regret.csv',absolute)
    # Scenario first: 3 allocations are sensitivity repetitions, not independent floods.
    summary=[]
    for (sid,level,policy),group in df.groupby(['scenario_id','level','policy'],sort=False):
        row=dict(scenario_id=int(sid),level=level,policy=policy,allocations=len(group),regret_mean=float(group.regret_pct.mean()),regret_median=float(group.regret_pct.median()),regret_min=float(group.regret_pct.min()),regret_max=float(group.regret_pct.max()),delta_ATT_minutes_mean=float(group.delta_ATT_minutes.mean()),delta_ATT_minutes_min=float(group.delta_ATT_minutes.min()),delta_ATT_minutes_max=float(group.delta_ATT_minutes.max()),J_star_mean=float(group.J_star.mean()),J_policy_mean=float(group.J_policy.mean()),oracle_first_road_change_count=int(group.first_road_changed.sum()),oracle_full_order_change_count=int(group.full_order_changed.sum()))
        summary.append(row)
    summary=save('Table_duration_summary.csv',summary)
    overall=[]
    for (level,policy),g in summary.groupby(['level','policy'],sort=False):
        graw=df[(df.level==level)&(df.policy==policy)]
        overall.append(dict(level=level,policy=policy,independent_scenarios=len(g),configurations=len(graw),scenario_mean_regret_mean=float(g.regret_mean.mean()),scenario_mean_regret_median=float(g.regret_mean.median()),scenario_mean_regret_min=float(g.regret_mean.min()),scenario_mean_regret_max=float(g.regret_mean.max()),configuration_regret_max=float(graw.regret_pct.max()),scenario_mean_delta_ATT_mean=float(g.delta_ATT_minutes_mean.mean()),scenario_mean_delta_ATT_median=float(g.delta_ATT_minutes_mean.median()),scenario_mean_delta_ATT_min=float(g.delta_ATT_minutes_mean.min()),scenario_mean_delta_ATT_max=float(g.delta_ATT_minutes_mean.max()),configuration_delta_ATT_max=float(graw.delta_ATT_minutes.max())))
    save('Table_duration_summary_across_scenarios.csv',overall)
    byassignment=[]
    for (level,allocation,policy),g in df.groupby(['level','allocation','policy'],sort=False):
        byassignment.append(dict(level=level,allocation=allocation,policy=policy,independent_scenarios=len(g),regret_mean=float(g.regret_pct.mean()),regret_median=float(g.regret_pct.median()),regret_max=float(g.regret_pct.max()),delta_ATT_minutes_mean=float(g.delta_ATT_minutes.mean()),delta_ATT_minutes_max=float(g.delta_ATT_minutes.max())))
    save('Table_by_assignment.csv',byassignment)
    changes=[]
    for (level,allocation),g in dp.groupby(['level','allocation'],sort=False):changes.append(dict(level=level,allocation=allocation,independent_scenarios=len(g),first_road_changed=int(g.first_road_changed.sum()),first3_changed=int(g.first3_order_changed.sum()),full_order_changed=int(g.full_order_changed.sum()),first_change_fraction=float(g.first_road_changed.mean()),full_order_change_fraction=float(g.full_order_changed.mean()),near_tie_count=int(g.near_tie.sum()),first_road_near_tie_count=int(g.first_road_near_tie.sum()),minimum_first_road_alternative_gap=float(g.first_road_alternative_gap.min())))
    save('Table_policy_changes.csv',changes)
    thresholds=[]
    for sid in range(1001,1011):
        star=float(dp[(dp.scenario_id==sid)&(dp.level=='uniform')].J_star.iloc[0])
        for pct in [.0381,1.,1.5,3.]:thresholds.append(dict(scenario_id=sid,illustrative_regret_pct=pct,uniform_J_star=star,implied_delta_ATT_minutes=factor*star*pct/100,implied_delta_weighted_mean_TSTT_veh_h=.01*T0*star*pct/100,interpretation='Numerical threshold converted per scenario, not operational acceptance limit; 0.0381% historical median is not a common observed effect'))
    save('Table_threshold_absolute_interpretation.csv',thresholds)
    dry52=pd.read_csv(P52/'raw/dry_baselines.csv')
    dump(OUT/'audit/numerical_checks.json',CHECKS)
    dump(OUT/'audit/experiment_execution.json',dict(status='PASS',checks_passed=len(CHECKS),configurations=70,new_heterogeneous=60,forward_reverse_passed=70,independent_flood_scenarios=10,new_UE_calls=0,proxy_predictions=0,model_training=0,original_search_reruns=0,environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform()),normalization_T0=T0,model_ATT_factor_minutes=factor,max_crosscheck_abs=float(dp.forward_reverse_abs_difference.max()),script_sha256=sha(__file__)))
    print('NUMERICAL PASS',len(CHECKS),'checks; 70/70 DP; 0 UE calls',flush=True)
if __name__=='__main__':main()
