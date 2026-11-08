from __future__ import annotations
from experiment import *
import argparse,concurrent.futures,multiprocessing,psutil

def frozen():
    p=ROOT/'protocol/frozen_protocol.json';cfg=json.loads(p.read_text(encoding='utf-8'))
    assert digest(p)==(ROOT/'protocol/frozen_protocol.sha256').read_text().strip()
    for name,expected in cfg['source_hashes'].items():assert digest(ROOT/name)==expected,f'Frozen source changed: {name}'
    return cfg
def pin():
    allowed=psutil.Process().cpu_affinity();cores=[c for c in allowed if c%2==0][:4]
    index=(multiprocessing.current_process()._identity or [1])[0]-1
    core=cores[index%len(cores)];psutil.Process().cpu_affinity([core]);return core
def warm(net):
    ph=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=ph[ph.scenario_id==246].sort_values('physical_link_id');roads,_=select_roads(ph);net.solve(ph,roads,0)
def status(sid,phase,details):dump(ROOT/f'logs/status_{phase}_{sid}.json',{'scenario_id':sid,'phase':phase,'monotonic_time':time.perf_counter(),**details})
def scenario(sid):
    data=pd.read_csv(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');physical=data[data.scenario_id==sid].sort_values('physical_link_id')
    roads,audit=select_roads(physical)
    saved=json.loads((ROOT/'inputs/new_validation/selected_roads.json').read_text(encoding='utf-8'))[str(sid)];assert list(roads)==saved['roads']
    return physical,roads,audit

def generate():
    cfg=frozen();output=ROOT/'inputs/new_validation'
    historical=ROOT/'inputs/historical_121_160.csv'
    if not historical.exists():
        raise RuntimeError('New validation generation blocked: historical 121-160 flood inputs are required for the predeclared deduplication gate; provide them before generation.')
    olddiagnostic=pd.read_csv(historical)
    assert set(olddiagnostic.scenario_id.astype(int))==set(range(121,161))
    assert {'scenario_id','physical_link_id','depth_m','is_closed'}<=set(olddiagnostic.columns)
    if output.exists():raise FileExistsError('Do not regenerate a seen validation set')
    # Call the exact original generator main, with a revision-specific protocol.
    spec=json.loads((SOURCE/'config/final_protocol_v1.1.json').read_text(encoding='utf-8'))
    spec['status']='FROZEN_BEFORE_FINAL_SCENARIO_GENERATION';spec['final_scenario_generation'].update({'formal_final_scenario_count':30,'scenario_id_range':[3001,3030],'scenario_seed':cfg['scenario_seed'],'severity':'severe'})
    generator_protocol=ROOT/'protocol/scenario_protocol.json';dump(generator_protocol,spec)
    (ROOT/'protocol/scenario_protocol.sha256').write_text(digest(generator_protocol)+'\n',encoding='ascii')
    generator=load_module('revision_frozen_generator',FORMAL/'generate_final_holdout.py')
    old=sys.argv;sys.argv=['generate_final_holdout','--protocol',str(generator_protocol),'--protocol-hash-file',str(ROOT/'protocol/scenario_protocol.sha256'),'--model-root',str(MODEL),'--output-dir',str(output)]
    for name in ['historical_1_120.csv','historical_network_source.csv','historical_201_260.csv','historical_121_160.csv','historical_1001_1010.csv','engineering_batch_2001_2030.csv']:sys.argv+=['--prior-scenario-file',str(ROOT/'inputs'/name)]
    try:generator.main()
    finally:sys.argv=old
    data=pd.read_csv(output/'final_scenarios_physical_links.csv');roads={}
    for sid,g in data.groupby('scenario_id'):
        selected,audit=select_roads(g);roads[str(sid)]={'roads':selected,'closed_count':int(g.is_closed.sum())};audit.to_csv(output/f'road_selection_{sid}.csv',index=False)
    dump(output/'selected_roads.json',roads);dump(output/'revision_input_freeze.json',{'revision_protocol_sha256':digest(ROOT/'protocol/frozen_protocol.json'),'files':{p.name:digest(p) for p in output.iterdir() if p.is_file()}})

def query_case(sid):
    cfg=frozen();core=pin();import torch;torch.set_num_threads(1)
    ph,roads,audit=scenario(sid);net=Network(MODEL);warm(net);predictor=api.SurrogateV2(SOURCE/'surrogate/final_ensemble')
    store=PhysicalStore(net,ph,roads,ROOT/f'runs/shared_physical_cache/scenario_{sid}.sqlite')
    order=['proposed','sa_original','sa_restart','greedy_ils','random_ls','greedy_ls','ue_beam','ue_bibeam']
    for rep in range(10):
        screened=None;candidate_report={}
        for method in order:
            if method in cfg['deterministic_methods'] and rep>0:continue
            out=ROOT/f'runs/query_cap/scenario_{sid}/{method}/rep_{rep:02d}'
            if (out/'result.json').exists():continue
            status(sid,'query',{'method':method,'replicate':rep,'cpu_core':core,'physical_states':len(store.cache)})
            start=time.perf_counter()
            if method=='proposed':
                screened,candidate_report=build_candidates(ph,roads,audit,sid,rep,predictor)
                out.mkdir(parents=True,exist_ok=True);screened.drop(columns=['seq_tuple'],errors='ignore').to_csv(out/'screened_candidates.csv.gz',index=False,compression='gzip')
            q=QueryOracle(store);details=run_method(method,q,roads,sid,rep,screened,cfg['selected_configurations'].get(method))
            extra={'online_total_seconds':time.perf_counter()-start,'timing_mode':'shared physical cache; not a standalone speedup estimate','cpu_core':core,'roads':roads,**details}
            if method=='proposed':extra.update(candidate_report)
            q.save(out,method,rep,sid,extra)
            store.connection.commit()
    store.close();status(sid,'query',{'status':'complete','cpu_core':core});return sid

def time_case(sid):
    cfg=frozen();core=pin();import torch;torch.set_num_threads(1)
    ph,roads,audit=scenario(sid);net=Network(MODEL);warm(net);predictor=api.SurrogateV2(SOURCE/'surrogate/final_ensemble')
    base=ROOT/f'runs/time_cap/scenario_{sid}'
    reference=base/'proposed/rep_00/result.json'
    if reference.exists():ref=json.loads(reference.read_text(encoding='utf-8'));cap=ref['fresh_end_to_end_seconds']
    else:
        status(sid,'time',{'method':'proposed_reference','replicate':0,'cpu_core':core})
        fresh=PhysicalStore(net,ph,roads);q=QueryOracle(fresh);start=time.perf_counter();sc,cr=build_candidates(ph,roads,audit,sid,0,predictor)
        run_method('proposed',q,roads,sid,0,sc);cap=time.perf_counter()-start
        q.save(reference.parent,'proposed',0,sid,{'fresh_end_to_end_seconds':cap,'cpu_core':core,'fresh_cache':True,'time_cap_seconds':cap,'timing_mode':'isolated logical CPU, cold state cache; JIT/model setup prewarmed on development input',**cr})
        fresh.close()
    for method in ['sa_restart','greedy_ils','ue_bibeam']:
        for rep in range(10) if method!='ue_bibeam' else [0]:
            out=base/method/f'rep_{rep:02d}'
            if (out/'result.json').exists():continue
            status(sid,'time',{'method':method,'replicate':rep,'cpu_core':core,'cap_seconds':cap})
            fresh=PhysicalStore(net,ph,roads);q=QueryOracle(fresh,1023,cap)
            details=run_method(method,q,roads,sid,rep,config=cfg['selected_configurations'].get(method))
            q.save(out,method,rep,sid,{'fresh_cache':True,'cpu_core':core,'time_cap_seconds':cap,'query_cap':1023,'timing_mode':'fresh state cache, independent elapsed-time cap; same per-scenario CPU as Proposed reference',**details});fresh.close()
    status(sid,'time',{'status':'complete','cpu_core':core,'cap_seconds':cap});return sid

def freeze_outputs():
    cfg=frozen();files=[]
    for sid in cfg['scenario_ids']:
        for phase,methods in [('query_cap',cfg['random_methods']+cfg['deterministic_methods']),('time_cap',['proposed','sa_restart','greedy_ils','ue_bibeam'])]:
            for method in methods:
                reps=range(10) if (phase=='query_cap' and method in cfg['random_methods']) or (phase=='time_cap' and method in ['sa_restart','greedy_ils']) else [0]
                for rep in reps:
                    folder=ROOT/f'runs/{phase}/scenario_{sid}/{method}/rep_{rep:02d}'
                    for name in ['result.json','logical_query_ledger.csv.gz','all_query_events.csv.gz','incumbent_history.csv']:
                        p=folder/name;assert p.is_file(),f'Missing output {p}';files.append(p)
    target=ROOT/'protocol/all_method_outputs_frozen.json'
    if target.exists():raise FileExistsError(target)
    dump(target,{'revision_protocol_sha256':digest(ROOT/'protocol/frozen_protocol.json'),'status':'ALL_SEARCH_OUTPUTS_FROZEN_BEFORE_EXACT_REFERENCE','files':{str(p.relative_to(ROOT)):digest(p) for p in files}})
    print('ALL SEARCH OUTPUTS FROZEN',len(files),flush=True)

def exact_case(sid):
    cfg=frozen();assert (ROOT/'protocol/all_method_outputs_frozen.json').exists();pin()
    ph,roads,_=scenario(sid);net=Network(MODEL);warm(net);store=PhysicalStore(net,ph,roads,ROOT/f'runs/shared_physical_cache/scenario_{sid}.sqlite')
    prior=len(store.cache);rows=[store.request(m)[0] for m in range(1024)];costs={r['subset_mask']:r['loss'] for r in rows};value,sequence=exact_dp(costs,roads)
    target=ROOT/f'exact/scenario_{sid}';target.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(target/'all_1024_states.csv.gz',index=False,compression='gzip')
    # Fixed stronger-tolerance validation of the DP path and union of B256 choices.
    validation_masks=set(masks(sequence,roads))
    for p in (ROOT/f'runs/query_cap/scenario_{sid}').glob('*/rep_*/result.json'):
        r=json.loads(p.read_text(encoding='utf-8'));validation_masks.update(masks(r['best_sequence'],roads))
    validation=[]
    for mask in sorted(validation_masks):
        refined=net.solve(ph,roads,mask,1e-11);base=store.cache[mask]
        validation.append({'subset_mask':mask,'tstt_primary':base['tstt'],'tstt_refined':refined['tstt'],'relative_difference':abs(base['tstt']-refined['tstt'])/refined['tstt'],'refined_gap':refined['relative_gap']})
    pd.DataFrame(validation).to_csv(target/'selected_path_stability.csv',index=False)
    dump(target/'exact_solution.json',{'scenario_id':sid,'roads':roads,'exact_objective':value,'sequence':sequence,'conditional_table_optimum':True,'primary_relative_gap':cfg['primary_relative_gap'],
        'states_known_after_all_searches':prior,'postfreeze_new_physical_solves':1024-prior,'all_states_converged':all(r['converged'] for r in rows),'max_relative_gap':max(r['relative_gap'] for r in rows),
        'selected_path_refinement_max_relative_tstt_difference':max(r['relative_difference'] for r in validation),'freeze_sha256':digest(ROOT/'protocol/all_method_outputs_frozen.json')})
    store.close();status(sid,'exact',{'status':'complete'});return sid

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','query','time','freeze_outputs','exact']);parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if args.stage=='generate':generate()
    elif args.stage=='freeze_outputs':freeze_outputs()
    else:
        fn={'query':query_case,'time':time_case,'exact':exact_case}[args.stage]
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(fn,s):s for s in range(3001,3031)}
            for f in concurrent.futures.as_completed(futures):print(args.stage,'completed',f.result(),flush=True)
