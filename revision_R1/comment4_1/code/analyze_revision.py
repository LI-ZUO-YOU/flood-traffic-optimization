"""Post-freeze analysis. All hypotheses/aggregation follow frozen_protocol.json."""
from experiment import *
from math import comb
import ast

LABELS={'proposed':'Proposed','sa_original':'Permutation SA (original)','sa_restart':'SA-restart','greedy_ls':'UE-Greedy-LS','greedy_ils':'UE-Greedy-ILS','random_ls':'Random-start + shared LS','ue_beam':'UE-Beam','ue_bibeam':'UE-Bidirectional Beam'}
ORDER=list(LABELS)
def quantile(a,q):return float(np.quantile(a,q,method='linear'))
def bootstrap_effect(values,reps=100000,seed=2026102703):
    values=np.asarray(values,float);rng=np.random.default_rng(seed)
    ix=rng.integers(0,len(values),(reps,len(values)));samples=values[ix]
    return {'mean_ci_low':quantile(samples.mean(axis=1),.025),'mean_ci_high':quantile(samples.mean(axis=1),.975),'median_ci_low':quantile(np.median(samples,axis=1),.025),'median_ci_high':quantile(np.median(samples,axis=1),.975)}
def sign_p(wins,losses):
    n=wins+losses
    return sum(comb(n,k) for k in range(wins,n+1))/2**n if n else 1.0
def nested_tail(arrays,reps=10000,seed=2026102704):
    rng=np.random.default_rng(seed);n=len(arrays);p90=[];worst=[]
    for j in range(reps):
        chosen=rng.integers(0,n,n);means=[];maxima=[]
        for i in chosen:
            a=np.asarray(arrays[i],float);draw=a[rng.integers(0,len(a),len(a))]
            means.append(draw.mean());maxima.append(draw.max())
        p90.append(np.quantile(means,.9,method='linear'));worst.append(np.quantile(maxima,.9,method='linear'))
    return {'p90_scenario_mean_ci_low':quantile(p90,.025),'p90_scenario_mean_ci_high':quantile(p90,.975),'p90_scenario_worst_ci_low':quantile(worst,.025),'p90_scenario_worst_ci_high':quantile(worst,.975)}

def main():
    cfg=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
    assert (ROOT/'protocol/all_method_outputs_frozen.json').exists()
    freeze=json.loads((ROOT/'protocol/all_method_outputs_frozen.json').read_text(encoding='utf-8'))
    for name,h in freeze['files'].items():assert digest(ROOT/name)==h
    kappa=cfg['equivalence']['equivalence_kappa'];rows=[];audit=[];checkpoints=[];solutions={};costmaps={}
    for sid in cfg['scenario_ids']:
        directory=ROOT/f'exact/scenario_{sid}';sol=json.loads((directory/'exact_solution.json').read_text(encoding='utf-8'));solutions[sid]=sol
        tab=pd.read_csv(directory/'all_1024_states.csv.gz');assert len(tab)==1024 and set(tab.subset_mask)==set(range(1024))
        assert tab.converged.all() and max(tab.relative_gap)<=cfg['primary_relative_gap']
        assert np.isfinite(tab.tstt).all() and (tab.tstt>0).all() and np.isfinite(tab.loss).all()
        costs={int(r.subset_mask):float(r.loss) for r in tab.itertuples(index=False)};costmaps[sid]=costs;roads=sol['roads']
        # Independent backwards Bellman recurrence, distinct from production DP.
        v=np.zeros(1024)
        for mask in range(1022,-1,-1):
            v[mask]=costs[mask]+min(v[mask|(1<<i)] for i in range(10) if mask&(1<<i)==0)
        assert abs(v[0]/10-sol['exact_objective'])<=1e-9*max(1,abs(sol['exact_objective']))
        jstar=sol['exact_objective'];eps=kappa*max(1,abs(jstar))
        for phase in ['query_cap','time_cap']:
            for path in (ROOT/f'runs/{phase}/scenario_{sid}').glob('*/rep_*/result.json'):
                r=json.loads(path.read_text(encoding='utf-8'));seq=tuple(r['best_sequence']);assert len(seq)==10 and set(seq)==set(roads)
                ms=masks(seq,roads);objective=float(np.mean([costs[m] for m in ms]));error=abs(objective-r['best_objective'])
                assert error<=eps,(sid,r['method'],error,eps)
                ledger=pd.read_csv(path.parent/'logical_query_ledger.csv.gz');assert len(ledger)==r['actual_queries'] and ledger.subset_mask.nunique()==len(ledger)
                assert set(ms)<=set(ledger.subset_mask)
                assert max(ledger.relative_gap)<=cfg['primary_relative_gap']
                assert list(ledger.query_index)==list(range(1,len(ledger)+1))
                if phase=='query_cap':assert len(ledger)<=256
                else:assert len(ledger)<=1023
                for l in ledger.itertuples(index=False):assert abs(l.loss-costs[int(l.subset_mask)])<=eps
                # Reconstruct information visible at each incumbent and checkpoint,
                # rather than trusting only the final scalar or stored snapshots.
                history=pd.read_csv(path.parent/'incumbent_history.csv')
                assert len(history)>0 and history.query_count.is_monotonic_increasing
                assert history.elapsed_seconds.is_monotonic_increasing
                last=float('inf');history_error=0.0
                for h in history.itertuples(index=False):
                    hseq=tuple(ast.literal_eval(h.sequence));hms=masks(hseq,roads)
                    assert len(hseq)==10 and set(hseq)==set(roads)
                    assert set(hms)<=set(ledger.iloc[:int(h.query_count)].subset_mask)
                    hj=float(np.mean([costs[v] for v in hms]));history_error=max(history_error,abs(hj-h.objective))
                    assert abs(hj-h.objective)<=eps and h.objective<=last+1e-12
                    last=h.objective
                assert abs(history.objective.min()-r['best_objective'])<=1e-12
                events=pd.read_csv(path.parent/'all_query_events.csv.gz',usecols=['request_index','subset_mask','logical_cache_hit','unique_queries_after'])
                assert len(events)<=r['logical_requests']<=len(events)+1
                first=~events.subset_mask.duplicated();counts=first.cumsum().to_numpy()
                assert np.array_equal(counts,events.unique_queries_after.to_numpy())
                assert np.array_equal(events.loc[first,'subset_mask'].to_numpy(),ledger.subset_mask.to_numpy())
                assert np.array_equal((~first).to_numpy(),events.logical_cache_hit.to_numpy())
                for b,value in r['snapshots'].items():
                    visible=history[history.query_count<=int(b)].objective
                    if len(visible):assert value is not None and abs(float(visible.min())-value)<=1e-12
                    else:assert value is None
                regret=100*(objective-jstar)/jstar;assert regret>=-1e-8
                row={'scenario_id':sid,'phase':phase,'method':r['method'],'label':LABELS[r['method']],'replicate':r['replicate'],'objective':objective,'exact_objective':jstar,
                    'relative_regret_pct':max(0.0,regret),'numerical_equivalent_hit':abs(objective-jstar)<=eps,'within_1_5_pct':regret<=1.5,'within_3_pct':regret<=3,
                    'queries':r['actual_queries'],'physical_requested_states':r['actual_queries']+len(r.get('late_results_discarded',[])),'logical_requests':r['logical_requests'],
                    'search_wall_seconds':r['wall_seconds'],'online_total_seconds':r.get('online_total_seconds',r['wall_seconds']),
                    'fresh_end_to_end_seconds':r.get('fresh_end_to_end_seconds',r['wall_seconds']),'time_cap_seconds':r.get('time_cap_seconds'),
                    'candidate_seconds':r.get('candidate_construction_seconds',0.0),'surrogate_inference_seconds':r.get('surrogate_inference_seconds',0.0),
                    'physical_UE_seconds':r['physical_UE_seconds'],'cpu_core':r.get('cpu_core'),'late_results_discarded':len(r.get('late_results_discarded',[])),
                    'deadline_overrun_seconds':max(0.0,r['wall_seconds']-r['time_cap_seconds']) if phase=='time_cap' else 0.0,
                    'UE_seconds_scope':'visible state solves only; discarded final solve time is included in wall time but not this component',
                    'equivalence_objective_epsilon':eps,'termination':r['termination'],'source_file':str(path.relative_to(ROOT))}
                rows.append(row);audit.append({'scenario_id':sid,'phase':phase,'method':r['method'],'replicate':r['replicate'],'objective_reconstruction_error':error,'maximum_history_reconstruction_error':history_error,'ledger_unique_states':len(ledger),'request_events_verified':len(events),'incumbents_verified':len(history),'pass':True})
                if phase=='query_cap':
                    for b,value in r['snapshots'].items():
                        if value is not None:checkpoints.append({'scenario_id':sid,'method':r['method'],'replicate':r['replicate'],'budget':int(b),'objective':value,'relative_regret_pct':max(0,100*(value-jstar)/jstar)})
    df=pd.DataFrame(rows);df.to_csv(ROOT/'analysis/all_run_results.csv',index=False)
    pd.DataFrame(audit).to_csv(ROOT/'analysis/independent_integrity_checks.csv',index=False)
    cp=pd.DataFrame(checkpoints);cp.to_csv(ROOT/'analysis/anytime_run_results.csv',index=False)
    groups=[]
    for (phase,sid,m),g in df.groupby(['phase','scenario_id','method']):
        a=g.relative_regret_pct.to_numpy();groups.append({'phase':phase,'scenario_id':int(sid),'method':m,'label':LABELS[m],'replicates':len(g),'mean_regret_pct':float(a.mean()),'median_regret_pct':float(np.median(a)),
             'seed_std_regret_pct':float(a.std(ddof=1)) if len(a)>1 else 0.0,'min_regret_pct':float(a.min()),'max_regret_pct':float(a.max()),'seed_IQR_pct':quantile(a,.75)-quantile(a,.25),
             'equivalent_hit_rate':float(g.numerical_equivalent_hit.mean()),'within_1_5_rate':float(g.within_1_5_pct.mean()),'within_3_rate':float(g.within_3_pct.mean()),
             'mean_queries':float(g.queries.mean()),'mean_wall_seconds':float(g.fresh_end_to_end_seconds.mean()),'mean_online_seconds_shared_cache':float(g.online_total_seconds.mean()),
             'mean_candidate_seconds':float(g.candidate_seconds.mean()),'mean_UE_seconds':float(g.physical_UE_seconds.mean())})
    scenario=pd.DataFrame(groups);scenario.to_csv(ROOT/'analysis/scenario_seed_summaries.csv',index=False)
    summaries=[]
    for (phase,m),g in scenario.groupby(['phase','method']):
        a=g.mean_regret_pct.to_numpy();arrays=[df[(df.phase==phase)&(df.method==m)&(df.scenario_id==sid)].relative_regret_pct.to_numpy() for sid in g.scenario_id]
        tail=nested_tail(arrays) if phase=='query_cap' else {}
        summaries.append({'phase':phase,'method':m,'label':LABELS[m],'independent_scenarios':len(g),'runs':int(g.replicates.sum()),'replicates_per_scenario':int(g.replicates.iloc[0]),
            'mean_scenario_mean_regret_pct':float(a.mean()),'median_scenario_mean_regret_pct':float(np.median(a)),'P90_scenario_mean_regret_pct':quantile(a,.9),'max_scenario_mean_regret_pct':float(a.max()),
            'P90_scenario_worst_seed_regret_pct':quantile(g.max_regret_pct,.9),'max_single_run_regret_pct':float(g.max_regret_pct.max()),'mean_seed_std_pct':float(g.seed_std_regret_pct.mean()),
            'equivalent_objective_hit_rate':float(g.equivalent_hit_rate.mean()),'within_1_5_rate':float(g.within_1_5_rate.mean()),'within_3_rate':float(g.within_3_rate.mean()),
            'mean_queries':float(g.mean_queries.mean()),'mean_fresh_wall_seconds':float(g.mean_wall_seconds.mean()) if phase=='time_cap' else None,
            'mean_execution_seconds_shared_cache':float(g.mean_online_seconds_shared_cache.mean()) if phase=='query_cap' else None,**tail})
    summary=pd.DataFrame(summaries);summary.to_csv(ROOT/'analysis/Table_R2_method_summary.csv',index=False)
    df[df.phase=='time_cap'][['scenario_id','method','replicate','time_cap_seconds','fresh_end_to_end_seconds','queries','physical_requested_states','late_results_discarded','deadline_overrun_seconds','candidate_seconds','surrogate_inference_seconds','physical_UE_seconds','UE_seconds_scope']].to_csv(ROOT/'analysis/Table_R4_fresh_timing_details.csv',index=False)
    pivot=scenario[scenario.phase=='query_cap'].pivot(index='scenario_id',columns='method',values='mean_regret_pct').sort_index()
    paired=[];diffrows=[]
    for m in ['sa_restart','greedy_ils','ue_bibeam']:
        diff=(pivot[m]-pivot.proposed).to_numpy();ids=pivot.index.to_numpy()
        eps=np.array([100*kappa*max(1,abs(solutions[int(s)]['exact_objective']))/abs(solutions[int(s)]['exact_objective']) for s in ids])
        wins=int(sum(diff>eps));losses=int(sum(diff< -eps));ties=len(diff)-wins-losses
        paired.append({'comparator':m,'label':LABELS[m],'independent_scenarios':len(diff),'effect_definition':'comparator mean regret minus Proposed mean regret, percentage points','mean_paired_improvement_pp':float(diff.mean()),'median_paired_improvement_pp':float(np.median(diff)),
            'proposed_wins':wins,'ties_by_empirical_epsilon':ties,'proposed_losses':losses,'one_sided_exact_sign_p':sign_p(wins,losses),**bootstrap_effect(diff)})
        diffrows.extend({'scenario_id':int(s),'comparator':m,'paired_difference_pp':float(d),'equivalence_tolerance_pp':float(e)} for s,d,e in zip(ids,diff,eps))
    ordered=sorted(range(len(paired)),key=lambda i:paired[i]['one_sided_exact_sign_p']);last=0.0
    for rank,i in enumerate(ordered):last=max(last,min(1,(len(paired)-rank)*paired[i]['one_sided_exact_sign_p']));paired[i]['holm_adjusted_sign_p']=last
    pd.DataFrame(paired).to_csv(ROOT/'analysis/Table_R3_primary_paired_comparisons.csv',index=False)
    pd.DataFrame(diffrows).to_csv(ROOT/'analysis/scenario_paired_differences.csv',index=False)
    cp.groupby(['method','scenario_id','budget'],as_index=False).relative_regret_pct.mean().to_csv(ROOT/'analysis/anytime_scenario_means.csv',index=False)
    mechanism=[]
    descriptions={
        'proposed':'Original 30000-candidate generation, screening, structural reserve and UE correction; only prespecified seed replication added',
        'sa_original':'Original move sampling, current-objective temperature scale, proposal-wise cooling and no-new-state stall stop; unified scalar UE oracle',
        'sa_restart':'Original SA neighborhoods and acceptance plus development-selected restart stall and useful residual-budget neighborhood evaluations',
        'greedy_ls':'New deterministic UE greedy initialization followed by the actual original local_search function',
        'greedy_ils':'UE greedy initialization, two-swap incumbent perturbations and the actual original local_search function',
        'random_ls':'New random permutation initialization followed by the actual original local_search function; no surrogate',
        'ue_beam':'Forward subset labels and dominance with fixed progressive widening; no original-paper bounds or pruning',
        'ue_bibeam':'Forward/backward subset labels, compatible joins and fixed progressive widening; no original-paper bounds or pruning'}
    for m in ORDER:
        if m in ['proposed','sa_original']:parameter_source='preserved original configuration; source replay verified'
        elif m in ['greedy_ls','random_ls']:parameter_source='new control with fixed initialization rule and unchanged shared local correction; no parameter grid'
        else:parameter_source='development scenarios 246,247,249 only'
        configuration=cfg['selected_configurations'].get(m,{})
        if m=='sa_original':configuration={'temperature_ratio':.0025,'cooling':.995,'adjacent_probability':.7,'insertion_probability':.15,'max_stalled_proposals':1000}
        mechanism.append({'method':m,'label':LABELS[m],'surrogate_required':m=='proposed','query_cap':256,'random_replicates_per_scenario':10 if m in cfg['random_methods'] else 1,
                          'parameter_source':parameter_source,'mechanism':descriptions[m],
                          'configuration':json.dumps(configuration,sort_keys=True)})
    pd.DataFrame(mechanism).to_csv(ROOT/'analysis/Table_R1_algorithm_mechanisms.csv',index=False)
    report={'status':'ANALYSIS_COMPLETE','scenario_count':30,'query_cap_runs':int(sum(df.phase=='query_cap')),'time_cap_runs':int(sum(df.phase=='time_cap')),'all_run_integrity_checks_passed':True,
         'source_protocol_sha256':digest(ROOT/'protocol/frozen_protocol.json'),'method_output_freeze_sha256':digest(ROOT/'protocol/all_method_outputs_frozen.json'),
         'primary_equivalence_kappa':kappa,'maximum_selected_path_refinement_relative_tstt_difference':max(s['selected_path_refinement_max_relative_tstt_difference'] for s in solutions.values()),
         'time_group_discarded_late_solves':int(df[df.phase=='time_cap'].late_results_discarded.sum()),
         'time_group_maximum_recorded_deadline_overrun_seconds':float(df[df.phase=='time_cap'].deadline_overrun_seconds.max()),
         'query_group_logical_unique_state_requests':int(df[df.phase=='query_cap'].queries.sum()),
         'time_group_physical_state_solves_including_late':int(df[df.phase=='time_cap'].physical_requested_states.sum()),
         'primary_paired_comparisons':paired,'query_cap_summary':summary[summary.phase=='query_cap'].where(pd.notna(summary),None).to_dict('records'),
         'time_cap_summary':summary[summary.phase=='time_cap'].where(pd.notna(summary),None).to_dict('records')}
    # pandas float columns retain NaN under where(None); JSON null conversion is explicit.
    report=json.loads(json.dumps(report,default=lambda x:float(x),allow_nan=True).replace('NaN','null'))
    dump(ROOT/'analysis/analysis_summary.json',report)
    print('All numerical, ledger and DP checks passed. Analysis complete.',flush=True)

if __name__=='__main__':main()
