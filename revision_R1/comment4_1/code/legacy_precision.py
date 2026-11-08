from experiment import *
from concurrent.futures import ProcessPoolExecutor

PUBLIC=Path(r'E:\jcr2区意见\urban-flood-road-reopening-reproducibility-v1.0-public')
def one(sid):
    data=pd.read_csv(ROOT/'inputs/historical_1001_1010.csv');ph=data[data.scenario_id==sid].sort_values('physical_link_id')
    saved=json.loads((PUBLIC/'results/exact_reference_and_regret/08_exact_reference_after_method_freeze/exact_dp_solution.json').read_text(encoding='utf-8'))['scenarios'][str(sid)]
    roads=saved['candidate_roads'];net=Network(MODEL);store=PhysicalStore(net,ph,roads,ROOT/f'development/legacy_precision/{sid}.sqlite')
    rows=[store.request(m)[0] for m in range(1024)];costs={r['subset_mask']:r['loss'] for r in rows};jstar,seq=exact_dp(costs,roads)
    out=ROOT/f'development/legacy_precision/scenario_{sid}';out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'all_1024_highprecision_states.csv.gz',index=False,compression='gzip')
    detail=pd.read_csv(PUBLIC/'results/exact_reference_and_regret/09_regret_evaluation/method_regret_detailed.csv');detail=detail[detail.scenario_id==sid].copy()
    oldsequence=tuple(saved['optimal_sequence']);refined=[];validation_masks=set(masks(seq,roads)+masks(oldsequence,roads))
    def objective(sequence):return sum(costs[m] for m in masks(sequence,roads))/10
    for r in detail.itertuples(index=False):
        sequence=tuple(map(int,r.method_sequence.split('|')));j=objective(sequence)
        refined.append({'scenario_id':sid,'method':r.method,'budget':int(r.ue_budget),'old_objective':r.method_objective,'new_objective':j,'old_exact':r.exact_objective,'new_exact':jstar,'old_regret_pct':r.relative_regret_pct,'new_regret_pct':100*(j-jstar)/jstar})
        if r.ue_budget==256 and r.method=='full_method':validation_masks.update(masks(sequence,roads))
    saresult=pd.read_csv(PUBLIC/'results/poststudy_permutation_SA/final_once_only/sa_final_results.csv');sarow=saresult[saresult.scenario_id==sid].iloc[0]
    sasequence=tuple(roads[i] for i in json.loads(sarow.best_sequence_bits));saj=objective(sasequence);validation_masks.update(masks(sasequence,roads))
    refined.append({'scenario_id':sid,'method':'sa_original_poststudy','budget':256,'old_objective':sarow.best_objective,'new_objective':saj,'old_exact':sarow.exact_objective,'new_exact':jstar,'old_regret_pct':sarow.relative_regret_pct,'new_regret_pct':100*(saj-jstar)/jstar})
    pd.DataFrame(refined).to_csv(out/'recomputed_frozen_decisions.csv',index=False)
    validation=[]
    for mask in sorted(validation_masks):
        strict=net.solve(ph,roads,mask,1e-11);base=store.cache[mask]
        validation.append({'scenario_id':sid,'subset_mask':mask,'tstt_1e9':base['tstt'],'tstt_1e11':strict['tstt'],'relative_difference':abs(strict['tstt']-base['tstt'])/strict['tstt'],'strict_relative_gap':strict['relative_gap']})
    pd.DataFrame(validation).to_csv(out/'selected_path_precision_validation.csv',index=False)
    dump(out/'exact_solution.json',{'scenario_id':sid,'roads':roads,'old_exact_sequence':oldsequence,'highprecision_exact_sequence':seq,'sequence_changed':list(seq)!=list(oldsequence),'old_table_objective':saved['exact_objective'],'new_table_objective':jstar,'old_sequence_on_new_table':objective(oldsequence),'max_path_validation_relative_difference':max(r['relative_difference'] for r in validation)})
    store.close();print('legacy precision completed',sid,flush=True);return sid

if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=4) as pool:list(pool.map(one,range(1001,1011)))
    allrows=pd.concat([pd.read_csv(ROOT/f'development/legacy_precision/scenario_{s}/recomputed_frozen_decisions.csv') for s in range(1001,1011)],ignore_index=True)
    allrows.to_csv(ROOT/'development/legacy_precision/all_recomputed_decisions.csv',index=False)
