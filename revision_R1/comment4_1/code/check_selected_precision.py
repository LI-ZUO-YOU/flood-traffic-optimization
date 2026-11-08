"""Post-freeze objective stability using already computed stronger-tolerance paths."""
from experiment import *
def main():
    cfg=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'));kappa=cfg['equivalence']['equivalence_kappa'];rows=[]
    for sid in cfg['scenario_ids']:
        base=ROOT/f'exact/scenario_{sid}';sol=json.loads((base/'exact_solution.json').read_text(encoding='utf-8'));roads=sol['roads']
        a=pd.read_csv(base/'selected_path_stability.csv');ref={int(r.subset_mask):r.tstt_refined/LEGACY_BASELINE-1 for r in a.itertuples(index=False)}
        jref=float(np.mean([ref[m] for m in masks(sol['sequence'],roads)]));eps=kappa*max(1,abs(sol['exact_objective']))
        rows.append({'scenario_id':sid,'method':'primary_DP_path','replicate':0,'primary_objective':sol['exact_objective'],'refined_objective':jref,'absolute_objective_change':abs(jref-sol['exact_objective']),'frozen_epsilon':eps,'within_frozen_objective_epsilon':abs(jref-sol['exact_objective'])<=eps})
        for p in (ROOT/f'runs/query_cap/scenario_{sid}').glob('*/rep_*/result.json'):
            r=json.loads(p.read_text(encoding='utf-8'));j=float(np.mean([ref[m] for m in masks(r['best_sequence'],roads)]))
            rows.append({'scenario_id':sid,'method':r['method'],'replicate':r['replicate'],'primary_objective':r['best_objective'],'refined_objective':j,
                'absolute_objective_change':abs(j-r['best_objective']),'frozen_epsilon':eps,'within_frozen_objective_epsilon':abs(j-r['best_objective'])<=eps})
    df=pd.DataFrame(rows);df.to_csv(ROOT/'analysis/selected_objective_precision_stability.csv',index=False)
    result={'paths':len(df),'all_within_frozen_objective_epsilon':bool(df.within_frozen_objective_epsilon.all()),'max_change_over_frozen_objective_epsilon':float((df.absolute_objective_change/df.frozen_epsilon).max()),
        'reason':'post-freeze diagnostic: some selected-state relative TSTT changes exceeded the development calibration maximum; primary thresholds and algorithm outputs remain unchanged'}
    dump(ROOT/'analysis/selected_objective_precision_stability.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
