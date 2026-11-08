"""Read-only trace/code audit. No UE solves and no optimization runs."""
import sys, json, inspect, hashlib, shutil, ast
from pathlib import Path
CLOSE=Path(__file__).resolve().parents[1]
ROUND=CLOSE.parent
sys.path.insert(0,str(ROUND/'code'))
from common import *
from analyze_round2 import backward,prefix_best

def csv(name,rows):
    pd.DataFrame(rows).to_csv(CLOSE/name,index=False,encoding='utf-8-sig')
def seq(s):return tuple(map(int,str(s).split('|')))
def txt(s):return '|'.join(map(str,s))
def forbid(*a,**kw):raise RuntimeError('Closeout is table-only; UE solving prohibited')

def run():
    CLOSE.mkdir(exist_ok=True)
    ex.Network.solve=forbid
    verify_manifest()
    # A new child directory preserves all previously delivered round-2 files.
    frozen={p.relative_to(ROUND).as_posix():sha(p) for p in ROUND.rglob('*') if p.is_file() and CLOSE not in p.parents and 'runtime_cache' not in p.parts and '__pycache__' not in p.parts}
    dump(CLOSE/'prior_round2_sha256.json',frozen)
    plan=Path(r'E:\jcr2区意见\返稿\4.1最后意见.txt')
    shutil.copy2(plan,CLOSE/plan.name)
    dump(CLOSE/'request_source.json',{'source':str(plan),'sha256':sha(plan),'scope':'Two low-cost closing audits; no new optimization, retraining or UE solves'})

    prefixrows=[];phaserows=[];runrows=[];pathrows=[];eventrows=[];lscalls=[];statebounds=[];gaterows=[];firstroadrows=[]
    kappa=cfg()['equivalence']['equivalence_kappa']
    for sid in [3026,3029]:
        _,roads,_,sol=data(sid);rr=state_rows(sid);costs={m:r['loss'] for m,r in rr.items()}
        star=sol['exact_objective'];v=backward(costs);f=np.full(1024,np.inf);f[0]=0
        for m in range(1023):
            for i in range(10):
                if not m&(1<<i):
                    child=m|(1<<i);f[child]=min(f[child],f[m]+costs[m])
        assert abs(v[0]/10-star)<1e-8
        through=np.maximum(0,100*((f+v)/10-star)/star)
        optimal={m for m in range(1024) if (f[m]+v[m])/10-star<=kappa*max(1,abs(star))}
        for m in range(1024):statebounds.append({'scenario_id':sid,'subset_mask':m,'restored_count':m.bit_count(),'best_complete_regret_through_state_pct':through[m],'numerically_optimal_path_compatible':m in optimal})
        canonical=tuple(sol['sequence']);eps=kappa*max(1,abs(star))
        for rep in range(10):
            base=ROUND/f'replay/scenario_{sid}/rep_{rep:02d}'
            pool=frame(base/'candidate_pool_30000_with_oracle.csv.gz');screen=frame(base/'screened_replayed.csv.gz')
            hist=frame(base/'complete_sequence_history.csv.gz');ledger=frame(base/'logical_query_ledger_replayed.csv.gz')
            calls=json.loads((base/'local_search_calls.json').read_text(encoding='utf-8'))
            poolseq=[seq(s) for s in pool.sequence];histseq=[seq(s) for s in hist.sequence]
            ids=set(screen.candidate_id);primary=set(screen.loc[screen.screening_tier=='primary_shortlist','candidate_id']);res=screen[screen.screening_tier=='structural_reserve']
            selected=pool[pool.candidate_id.isin(ids)]
            groupseq={'pool':poolseq,'primary':[s for s,i in zip(poolseq,pool.candidate_id) if i in primary],
                      'reserve':[seq(s) for s in res.sequence],'screened_union':[s for s,i in zip(poolseq,pool.candidate_id) if i in ids],
                      'completed_C':[s for s,p in zip(histseq,hist.evaluation_phase) if p=='C_true_ue_reranking'],
                      'completed_LS':[s for s,p in zip(histseq,hist.evaluation_phase) if p=='D_local_search'],'all_completed':histseq}
            for g,ss in groupseq.items():
                for k in [1,2,3,4]:
                    ps=set(s[:k] for s in ss)
                    js=[prefix_best(p,roads,costs,v) for p in ps]
                    rg=[regret(j,star) for j in js]
                    prefixrows.append({'scenario_id':sid,'replicate':rep,'set':g,'prefix_length':k,'unique_prefixes':len(ps),
                        'canonical_optimal_prefix':txt(canonical[:k]),'canonical_prefix_present':canonical[:k] in ps,
                        'numerically_optimal_prefix_count':sum(abs(j-star)<=eps for j in js),
                        'best_conditional_regret_pct':min(rg) if rg else None,
                        **{f'prefix_count_conditional_regret_le_{str(t).replace(".","_")}pct':sum(r<=t for r in rg) for t in [.1,.5,1.5]}})
            # Fully evaluated sequences in their recorded order; charged calls are
            # counted once here, never summed from duplicate parent/move records.
            best=None;hist_improved=[]
            for no,(s,row) in enumerate(zip(histseq,hist.itertuples(index=False)),1):
                improvement=best is None or row.ue_objective<best
                reduction=0 if best is None else max(0,100*(best-row.ue_objective)/star)
                eventrows.append({'scenario_id':sid,'replicate':rep,'event':no,'phase':row.evaluation_phase,'sequence':txt(s),
                    'regret_pct':regret(row.ue_objective,star),'new_state_queries':row.new_ue_calls,'completion_budget':row.completion_budget,
                    'new_incumbent':improvement,'incumbent_reduction_pp':reduction,
                    'first_road':s[0],'prefix_2':txt(s[:2]),'prefix_3':txt(s[:3])})
                hist_improved.append(improvement);best=row.ue_objective if best is None else min(best,row.ue_objective)
            hist['new_incumbent']=hist_improved
            optfirst=hist[[s[0]==canonical[0] for s in histseq]]
            firstroadrows.append({'scenario_id':sid,'replicate':rep,'optimal_first_road':canonical[0],
                'completed_sequences_with_optimal_first_road':len(optfirst),
                'best_full_regret_with_optimal_first_road_pct':regret(optfirst.ue_objective.min(),star) if len(optfirst) else None})
            for k in [1,2,3,4]:
                pp=screen[screen.screening_tier=='primary_shortlist']
                wanted=pp[pp.sequence.map(lambda s:abs(prefix_best(seq(s)[:k],roads,costs,v)-star)<=eps)]
                eligible=wanted[wanted.prefix_3.isin(set(res.prefix_3))]
                gaterows.append({'scenario_id':sid,'replicate':rep,'optimal_prefix_length':k,
                    'primary_candidates_with_numerically_optimal_prefix':len(wanted),
                    'of_these_with_p3_in_reserve':len(eligible),
                    'of_these_actually_completed_in_C':int(wanted.sequence.isin(set(hist.loc[hist.evaluation_phase=='C_true_ue_reranking','sequence'])).sum())})
            for phase,g in ledger.groupby('phase',sort=False):
                gh=hist[hist.evaluation_phase==phase];ms=g.subset_mask.astype(int)
                phaserows.append({'scenario_id':sid,'replicate':rep,'phase':phase,'unique_queries':len(g),
                    'any_numeric_optimal_path_compatible_queries':int(ms.isin(optimal).sum()),
                    **{f'queries_state_best_regret_le_{str(t).replace(".","_")}pct':int(sum(through[m]<=t for m in ms)) for t in [.1,.5,1.5]},
                    'completed_unique_sequences':len(gh),'incumbent_improving_sequences':int(gh.new_incumbent.sum()),
                    'charged_queries_on_completed_non_improving_sequences':int(gh.loc[~gh.new_incumbent,'new_ue_calls'].sum()),
                    'best_completed_regret_pct':regret(gh.ue_objective.min(),star) if len(gh) else None})
            # Literal source ordering of reserve p2 scores. Ordered prefixes,
            # subset states and conditional optimal continuations are distinct.
            p2s=set(seq(s) for s in res.prefix_2)
            def score(p):
                bits={r:1<<i for i,r in enumerate(roads)};m=0;value=0
                for r in p:m|=bits[r];value+=costs[m]
                return value
            ranked=sorted(p2s,key=lambda p:(score(p),txt(p)))
            targets=[('canonical_DP',canonical),('pool_oracle_best',seq(pool.loc[pool.oracle_objective.idxmin(),'sequence'])),
                     ('screened_oracle_best',seq(selected.loc[selected.oracle_objective.idxmin(),'sequence'])),
                     ('best_completed_C',seq(hist.loc[hist[hist.evaluation_phase=='C_true_ue_reranking'].ue_objective.idxmin(),'sequence'])),
                     ('final_Proposed',seq(hist.loc[hist.ue_objective.idxmin(),'sequence']))]
            for label,s in targets:
                subset=pool[pool.sequence==txt(s)];p3=txt(s[:3]);p2=s[:2]
                reasons=ledger[ledger.reason.fillna('').str.startswith('prefix3:'+p3+':')]
                done=hist[hist.sequence==txt(s)]
                pathrows.append({'scenario_id':sid,'replicate':rep,'target':label,'sequence':txt(s),
                    'oracle_regret_pct':regret(objective(s,roads,costs),star),'proxy_rank':int(subset.proxy_rank.iloc[0]) if len(subset) else None,
                    'in_pool':bool(len(subset)),'in_primary':txt(s) in set(screen.loc[screen.screening_tier=='primary_shortlist','sequence']),
                    'in_reserve':txt(s) in set(res.sequence),'p2_in_reserve':p2 in p2s,
                    'reserve_p2_true_partial_rank':ranked.index(p2)+1 if p2 in ranked else None,
                    'p3_in_reserve':p3 in set(res.prefix_3),
                    'p3_first_unique_state_query_phase':str(reasons.phase.iloc[0]) if len(reasons) else 'no unique request with this literal p3 reason (state may be cached)',
                    'completed_online':bool(len(done)),'completion_phase':str(done.evaluation_phase.iloc[0]) if len(done) else '',
                    'queried_states_on_path':len(set(ex.masks(s,roads))&set(ledger.subset_mask))})
            first=calls[0];last=calls[-1]
            for c in calls:lscalls.append({'scenario_id':sid,'replicate':rep,'call_index':c['call_index'],'target':c['target_calls'],
                'queries_before':c['queries_before'],'queries_after':c['queries_after'],'pre_regret_pct':regret(c['best_before'],star),
                'post_regret_pct':regret(c['best_after'],star),'direct_reduction_pp':100*(c['best_before']-c['best_after'])/star,
                'stop_reason':c['stop_reason'],'rounds':c['round_no'],'last_round_evaluated':c['evaluated']})
            cr=hist[hist.evaluation_phase=='C_true_ue_reranking'];ls=hist[hist.evaluation_phase=='D_local_search']
            lq=ledger[ledger.phase=='D_local_search']
            runrows.append({'scenario_id':sid,'replicate':rep,'C_sequences':len(cr),'LS_sequences':len(ls),'C_distinct_first_roads':cr.sequence.map(lambda s:seq(s)[0]).nunique(),
                'C_first_road_values':'|'.join(map(str,sorted({seq(s)[0] for s in cr.sequence}))),
                'pool_best_regret_pct':float(pool.oracle_regret_pct.min()),'screened_best_regret_pct':float(selected.oracle_regret_pct.min()),
                'first_pre_LS_regret_pct':regret(first['best_before'],star),'final_regret_pct':regret(best,star),
                'direct_within_LS_reduction_pp':sum(100*(c['best_before']-c['best_after'])/star for c in calls),
                'LS_unique_queries':len(lq),'LS_incumbent_improving_sequences':int(ls.new_incumbent.sum()),
                'LS_charged_queries_on_non_improving_completions':int(ls.loc[~ls.new_incumbent,'new_ue_calls'].sum()),
                'final_sequence':txt(seq(hist.loc[hist.ue_objective.idxmin(),'sequence']))})
        print('Audited failure case',sid,flush=True)
    for name,rows in [('case_prefix_survival.csv',prefixrows),('case_phase_queries.csv',phaserows),('case_run_summary.csv',runrows),
                      ('case_target_paths.csv',pathrows),('case_sequence_events.csv',eventrows),('case_LS_calls.csv',lscalls),('case_state_conditional_bounds.csv',statebounds),
                      ('case_primary_seed_gate.csv',gaterows),('case_optimal_first_road_trials.csv',firstroadrows)]:csv(name,rows)

    # Audit implementation identity and every saved proxy-control path.
    assert ex.SharedCorrection.local_search is ex.original.BudgetedSearch.local_search
    assert ex.SharedCorrection.move_neighbors is ex.original.BudgetedSearch.move_neighbors
    assert ex.SharedCorrection.missing_count is ex.original.BudgetedSearch.missing_count
    from replay_diagnostics import InstrumentedCorrection
    assert InstrumentedCorrection.__mro__[1] is ex.SharedCorrection
    aliases=[];budgetrows=[]
    for sid in range(3001,3031):
        for rep in range(10):
            base=ROUND/f'replay/scenario_{sid}/rep_{rep:02d}'
            a=base/'proxy_pool_top1_ls';b=base/'primary_top1_ls'
            ra=json.loads((a/'result.json').read_text(encoding='utf-8'));rb=json.loads((b/'result.json').read_text(encoding='utf-8'))
            sameinit=ra['initial_sequence']==rb['initial_sequence']
            samefinal=float(ra['best_objective']).hex()==float(rb['best_objective']).hex() and ra['best_sequence']==rb['best_sequence']
            qa=frame(a/'all_query_events.csv.gz');qb=frame(b/'all_query_events.csv.gz')
            sameevents=qa.equals(qb)
            la=frame(a/'logical_query_ledger.csv.gz');lb=frame(b/'logical_query_ledger.csv.gz')
            sameledger=la[['subset_mask','query_index','phase','reason']].equals(lb[['subset_mask','query_index','phase','reason']])
            assert sameinit and samefinal and sameevents and sameledger
            aliases.append({'scenario_id':sid,'replicate':rep,'same_initial_sequence':sameinit,'same_final_objective_bitwise_and_sequence':samefinal,
                            'same_all_request_events':sameevents,'same_unique_query_order_phase_reason':sameledger,'logical_requests':len(qa),'unique_queries':len(la)})
            for method,folder in [('proxy_top1_ls',a),('random_ls',ROOT/f'runs/query_cap/scenario_{sid}/random_ls/rep_{rep:02d}')]+([('greedy_ls',ROOT/f'runs/query_cap/scenario_{sid}/greedy_ls/rep_00')] if rep==0 else []):
                r=json.loads((folder/'result.json').read_text(encoding='utf-8'));l=frame(folder/'logical_query_ledger.csv.gz')
                assert l.subset_mask.nunique()==len(l)==r['actual_queries']<=256
                if method=='greedy_ls':assert len(l[l.phase=='greedy'])==55
                else:assert len(l[l.phase=='initial_start'])==10
                initial=frame(folder/'incumbent_history.csv').iloc[0]
                star=json.loads((ROOT/f'exact/scenario_{sid}/exact_solution.json').read_text(encoding='utf-8'))['exact_objective']
                budgetrows.append({'scenario_id':sid,'replicate':rep,'method':method,'cap':256,'actual_unique_queries':len(l),
                    'initialization_unique_queries':int(sum(l.phase!='D_local_search')),'LS_new_unique_queries':int(sum(l.phase=='D_local_search')),
                    'initialization_in_total_budget':True,'own_query_cache':True,'initial_regret_pct':regret(initial.objective,star),
                    'initial_sequence':initial.sequence,'final_regret_pct':regret(r['best_objective'],star)})
    csv('proxy_alias_identity_300.csv',aliases);csv('start_budget_audit.csv',budgetrows)
    summary=frame(ROUND/'S1_start_ablation_summary.csv');merged=summary[summary.method!='primary_top1_ls'].copy()
    merged['display_name']=merged.method.map({'greedy_ls':'UE-Greedy + original LS','proxy_pool_top1_ls':'Proxy Top-1 + original LS (both proxy aliases merged)','random_ls':'Random-start + original LS'})
    merged['independent_scenario_units']=30
    merged['seeds_per_scenario']=merged.method.map({'greedy_ls':1,'proxy_pool_top1_ls':10,'random_ls':10})
    merged.to_csv(CLOSE/'start_ablation_merged_summary.csv',index=False,encoding='utf-8-sig')
    source={}
    for label,fn in [('local_search',ex.original.BudgetedSearch.local_search),('move_neighbors',ex.original.BudgetedSearch.move_neighbors),
                     ('missing_count',ex.original.BudgetedSearch.missing_count),('evaluate_sequence',ex.original.BudgetedSearch.evaluate_sequence),
                     ('baseline_initialization_and_dispatch',ex.correction_baseline),('proxy_initialization_and_dispatch',__import__('replay_diagnostics').one_case)]:
        body=inspect.getsource(fn);path=Path(inspect.getsourcefile(fn));lines,line=inspect.getsourcelines(fn)
        source[label]={'source_file':str(path),'file_sha256':sha(path),'start_line':line,'end_line':line+len(lines)-1,'function_source_sha256':hashlib.sha256(body.encode()).hexdigest()}
        (CLOSE/f'code/source_excerpt_{label}.txt').write_text(body,encoding='utf-8')
    dump(CLOSE/'LS_code_fairness.json',{'same_inherited_local_search_function':True,'same_neighborhood_function':True,'same_missing_count_function':True,
        'same_targets':[64,128,256],'same_unique_state_cap':256,'initialization_charged':True,'greedy_construction_unique_queries':55,'proxy_and_random_initialization_queries':10,
        'parents':'up to five best evaluated complete sequences','neighbors':'adjacent swaps; nonadjacent swaps with source position 0..4; insertion with source position 0..4',
        'acceptance':'all evaluated complete sequences remain available; best five parent set is refreshed each round; global incumbent is strict objective improvement',
        'stall_rule':'two rounds with relative best-objective improvement below 0.001, or no evaluable neighbors; resets on each local_search invocation',
        'neighbor_priority':'missing_count, adjacent-before-other, source position, target position, parent objective; stable order afterwards',
        'strict_pure_initial_sequence_effect_identified':False,
        'caveat':'Greedy initialization also acquires 55 charged states vs 10 for proxy/random. SharedCorrection.state_by_hash initially records evaluated seed-path states; additional construction-known states remain in QueryOracle and are reused when subsequently requested. missing_count uses the engine state registry, so initialization-dependent state history also affects neighbor priority and conservative fit checks. Matched routine and total cap are verified; identical LS-entry information, available budget and cache are not claimed.',
        'proxy_controls_duplicate_runs_verified':300,'sources':source})

    # Recheck numeric claims in the supplied final-opinion document without
    # treating those claims as ground truth.
    d=frame(ROUND/'S1_screening_loss.csv');dc=frame(ROUND/'S1_regret_decomposition_scenarios.csv')
    claim={'screening_loss_positive_runs':int(sum(d.screening_loss_pp>0)),
           'screening_loss_gt1pp_runs':int(sum(d.screening_loss_pp>1)),
           'screening_loss_gt5pp_runs':int(sum(d.screening_loss_pp>5)),
           'negative_sequence_spearman_runs':int(sum(d.pool_proxy_oracle_sequence_spearman<0)),
           'reserve_union_better_than_primary_runs':int(sum(d.screened_best_regret_pct<d.primary_best_regret_pct)),
           'final_better_than_first_pre_LS_scenarios':int(sum(dc.final_regret_pct<dc.pre_ls_regret_pct)),
           'final_better_than_screened_best_scenarios':int(sum(dc.final_regret_pct<dc.screened_best_regret_pct)),
           'final_better_than_pool_best_scenarios':int(sum(dc.final_regret_pct<dc.pool_best_regret_pct)),
           'first_pre_LS_to_final_mean_reduction_pp':float((dc.pre_ls_regret_pct-dc.final_regret_pct).mean()),
           'screening_final_Pearson_r':float(d.groupby('scenario_id').screening_loss_pp.mean().corr(dc.set_index('scenario_id').final_regret_pct))}
    tm=frame(ROUND/'S2_fresh_timing.csv').pivot(index='scenario_id',columns='mode',values='end_to_end_seconds')
    claim['parallel_slower_than_serial_cases']=int(sum(tm.parallel4>tm.serial))
    claim['parallel_mean_duration_increase_pct']=float(100*(tm.parallel4.mean()/tm.serial.mean()-1))
    dump(CLOSE/'final_opinion_numeric_recheck.json',claim)
    for p,h in frozen.items():assert sha(ROUND/p)==h,'Previously delivered file changed '+p
    verify_manifest()
    print(json.dumps(claim,ensure_ascii=False,indent=2),flush=True)
    print('Closeout numerical/code audit complete. UE solves=0; original and round-2 outputs unchanged.',flush=True)

if __name__=='__main__':run()
