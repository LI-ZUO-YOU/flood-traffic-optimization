from __future__ import annotations
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
from experiment import *
import platform,importlib.metadata,concurrent.futures

def precision():
    network=Network(MODEL);data=pd.read_csv(ROOT/'inputs/historical_201_260.csv');rows=[]
    rng=np.random.default_rng(2026102601)
    for sid in [246,247,249]:
        physical=data[data.scenario_id==sid].sort_values('physical_link_id');roads,_=select_roads(physical)
        chosen=sorted({0,1,3,7,15,31,63,127,255,511,1023,*map(int,rng.choice(1024,9,replace=False))})
        for mask in chosen:
            for tol in [1e-7,1e-9,1e-11]:
                r=network.solve(physical,roads,mask,tol);rows.append({'scenario_id':sid,**r})
            pd.DataFrame(rows).to_csv(ROOT/'development/precision_stability.csv',index=False)
        print('precision completed',sid,flush=True)
    df=pd.DataFrame(rows);pairs=[]
    for (sid,mask),g in df.groupby(['scenario_id','subset_mask']):
        a=g[g.tolerance==1e-9].iloc[0];b=g[g.tolerance==1e-11].iloc[0]
        pairs.append({'scenario_id':int(sid),'subset_mask':int(mask),'relative_tstt_difference':float(abs(a.tstt-b.tstt)/b.tstt),'absolute_normalized_loss_difference':float(abs(a.loss-b.loss))})
    pd.DataFrame(pairs).to_csv(ROOT/'development/precision_pair_differences.csv',index=False)
    kappa=max(1e-7,10*max(r['relative_tstt_difference'] for r in pairs))
    report={'primary_relative_gap':1e-9,'validation_relative_gap':1e-11,'development_states':len(pairs),'max_relative_tstt_difference':max(r['relative_tstt_difference'] for r in pairs),
            'equivalence_kappa':kappa,'equivalence_rule':'abs(Ja-Jb) <= kappa*max(1,abs(Jreference)); empirically calibrated, not a rigorous UE error bound',
            'unit':'fraction of normalized objective, not percent','max_observed_relative_gap':float(df.relative_gap.max()),'all_converged':True}
    dump(ROOT/'development/precision_protocol.json',report);return report

def tune_one(sid):
    import torch;torch.set_num_threads(1)
    data=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=data[data.scenario_id==sid].sort_values('physical_link_id');roads,audit=select_roads(ph)
    net=Network(MODEL);store=PhysicalStore(net,ph,roads,ROOT/f'development/highprecision_{sid}.sqlite',1e-9)
    rows=[]
    configurations=[]
    for temperature in [.0025,.01]:
        for cooling in [.985,.995]:
            configurations.append(('sa_restart',{'temperature_ratio':temperature,'cooling':cooling,'restart_stall':100}))
    for swaps in [2,3]:configurations.append(('greedy_ils',{'perturb_swaps':swaps}))
    for width in [2,4,8]:
        for method in ['ue_beam','ue_bibeam']:configurations.append((method,{'width':width}))
    for method,cfg in configurations:
        reps=range(3) if method in ['sa_restart','greedy_ils'] else [0]
        for rep in reps:
            q=QueryOracle(store);extra=run_method(method,q,roads,sid,rep,config=cfg)
            rows.append({'scenario_id':sid,'method':method,'replicate':rep,'configuration':json.dumps(cfg,sort_keys=True),'objective':q.best,'queries':q.used})
    # Proposed is checked for engineering feasibility only. These scenarios are
    # in its historical training pool and cannot support comparative conclusions.
    predictor=api.SurrogateV2(SOURCE/'surrogate/final_ensemble');sc,cr=build_candidates(ph,roads,audit,sid,0,predictor)
    q=QueryOracle(store);run_method('proposed',q,roads,sid,0,sc);q.save(ROOT/f'development/proposed_engineering_only/{sid}','proposed',0,sid,{'engineering_only_training_scenario':True,**cr})
    # Development reference can be used for tuning; new validation references cannot.
    costs={m:store.request(m)[0]['loss'] for m in range(1024)};jstar,seq=exact_dp(costs,roads)
    for r in rows:r['exact_objective']=jstar;r['regret_pct']=100*(r['objective']-jstar)/jstar
    pd.DataFrame(rows).to_csv(ROOT/f'development/tuning_{sid}.csv',index=False);store.close()
    print('tuning completed',sid,'config runs',len(rows),flush=True);return sid

def replay():
    # Historical final table is isolated to software regression of the unchanged
    # Proposed scheduling. It is never used to select new baseline parameters.
    public=Path(r'E:\jcr2区意见\urban-flood-road-reopening-reproducibility-v1.0-public')
    states=pd.read_csv(public/'results/exact_reference_and_regret/08_exact_reference_after_method_freeze/subset_ue_costs.csv')
    solution=json.loads((public/'results/exact_reference_and_regret/08_exact_reference_after_method_freeze/exact_dp_solution.json').read_text(encoding='utf-8'))['scenarios']['1001']
    class RegressionStore:
        def __init__(self):self.rows={int(r.subset_mask):r._asdict() for r in states[states.scenario_id==1001].itertuples(index=False)}
        def request(self,m):return self.rows[m],True
    screened=pd.read_csv(public/'results/candidate_generation_and_screening/04_structural_screening/screened_candidates.csv');screened=screened[screened.scenario_id==1001]
    q=QueryOracle(RegressionStore());run_method('proposed',q,solution['candidate_roads'],1001,0,screened)
    archived=pd.read_csv(public/'results/query_ledgers_and_method_outputs/06_full_method/scenario_1001/budget_snapshots_pre_reference.csv')
    checks=[]
    for b in [64,128,256]:
        observed=min(t['objective'] for t in q.trace if t['query_count']<=b);expected=float(archived[archived.ue_budget==b].best_ue_objective.iloc[0]);assert abs(observed-expected)<1e-10
        checks.append({'budget':b,'expected':expected,'observed':observed})
    dump(ROOT/'development/proposed_legacy_replay.json',{'status':'pass','scope':'historical-table software replay only, no UE solves or tuning','checks':checks})

def freeze():
    files=sorted(list((ROOT/'code').glob('*.py'))+list(SOURCE.rglob('*.py'))+list((SOURCE/'surrogate').rglob('*.pt'))+[SOURCE/'surrogate/final_ensemble/preprocessor_v2.json'])
    tuned=pd.concat([pd.read_csv(ROOT/f'development/tuning_{s}.csv') for s in [246,247,249]],ignore_index=True)
    selected={};summaries=[]
    for (method,cfg),g in tuned.groupby(['method','configuration']):
        summaries.append({'method':method,'configuration':cfg,'mean_regret':float(g.regret_pct.mean()),'median_regret':float(g.regret_pct.median()),'maximum_regret':float(g.regret_pct.max())})
    for method in ['sa_restart','greedy_ils','ue_beam','ue_bibeam']:
        best=min((r for r in summaries if r['method']==method),key=lambda r:(r['mean_regret'],r['median_regret'],r['maximum_regret'],r['configuration']));selected[method]=json.loads(best['configuration'])
    pd.DataFrame(summaries).to_csv(ROOT/'development/configuration_grid_summary.csv',index=False)
    precision=json.loads((ROOT/'development/precision_protocol.json').read_text(encoding='utf-8'))
    protocol={
      'status':'FROZEN_BEFORE_NEW_VALIDATION_GENERATION','created_local_date':'2026-10-27','revision_version':'v2_original_SA_source_restored_before_validation','scope':'R1 comment 4.1 with a prerequisite numerical precision bridge, not a claim to resolve all of 4.2',
      'scenario_ids':list(range(3001,3031)),'scenario_seed':2026102702,'scenario_count':30,'replicates':10,'primary_budget':256,'anytime_checkpoints':[64,128,256],
      'budget_512_scope':'not part of this new confirmatory comparison; original frozen B512 results remain historical evidence',
      'primary_relative_gap':1e-9,'equivalence':precision,
      'objective':'mean(TSTT(Sk)/7480225.3449211195 - 1 for k=0..9), R10 weight=0',
      'proposed':'unchanged original functions, 30000 candidates, 60 primary plus reserve, unchanged frozen weights/features; only candidate/screen seed replication added',
      'seeds':{'candidate':'2026080702 + scenario_id + 1000000*r','screen':'2026080703 + scenario_id + 1000000*r','sa':'2026081000 + scenario_id + 1000000*r','correction_restart':'2026102603 + scenario_id + 1000000*r','r':'0..9'},
      'random_methods':['proposed','sa_original','sa_restart','greedy_ils','random_ls'],'deterministic_methods':['greedy_ls','ue_beam','ue_bibeam'],
      'primary_comparisons':['proposed vs sa_restart','proposed vs greedy_ils','proposed vs ue_bibeam'],
      'selected_configurations':selected,'tuning_scenarios':[246,247,249],'tuning_seed_replicates':3,'never_optimize_on_121_160':True,
      'time_cap_experiment':{'reference':'fresh-cache Proposed B256 replicate 0 on each scenario','comparison_methods':['sa_restart','greedy_ils','ue_bibeam'],'stochastic_replicates':10,'deterministic_replicates':1,'independent_query_cap':1023,'late_solver_result':'discarded if returned after cap, overrun recorded','fresh_proposed_seed_scope':'one prescribed reference seed per scenario; seed stability claims come from the 10-seed query-cap experiment','cpu_affinity':'separate even logical CPUs; each scenario uses the same CPU for every timing method'},
      'statistics':{'unit':'flood scenario, not algorithm replicate','primary_effect':'scenario mean comparator regret minus scenario mean Proposed regret','bootstrap':'100000 paired scenario resamples','secondary_tail':'nested scenario/seed bootstrap 10000 resamples','test':'one-sided exact sign test with empirical-equivalence ties, Holm across three primary comparisons','P90':'NumPy linear interpolation; descriptive secondary endpoint'},
      'M3_adaptation':'UE forward and bidirectional subset beam searches with exact partial labels and dominance; no replication claim for Gokalp traffic-benefit bounds, branch pruning or adaptive-beam implementation; no bound correctness assumed',
      'execution_order':['freeze all numerical and search configurations','generate all new scenarios','freeze road sets','run all query and time-cap methods','freeze ALL validation outputs','only then complete 1024-state tables and exact DP','analyze without method retuning'],
      'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in files},
      'environment':{'python':platform.python_version(),'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','torch','numba','matplotlib']}}
    }
    path=ROOT/'protocol/frozen_protocol.json'
    if path.exists():raise FileExistsError('Protocol already frozen; do not overwrite')
    dump(path,protocol);(ROOT/'protocol/frozen_protocol.sha256').write_text(digest(path)+'\n',encoding='ascii')
    print('PROTOCOL FROZEN',digest(path),selected,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['precision','tune','replay','freeze']);args=p.parse_args()
    if args.stage=='precision':precision()
    elif args.stage=='replay':replay()
    elif args.stage=='freeze':freeze()
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:list(pool.map(tune_one,[246,247,249]))
