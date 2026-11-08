"""Historical-table software equivalence only. Not baseline tuning."""
from experiment import *

if __name__=='__main__':
    public=Path(r'E:\jcr2区意见\urban-flood-road-reopening-reproducibility-v1.0-public')
    allstates=pd.read_csv(public/'results/exact_reference_and_regret/08_exact_reference_after_method_freeze/subset_ue_costs.csv')
    solutions=json.loads((public/'results/exact_reference_and_regret/08_exact_reference_after_method_freeze/exact_dp_solution.json').read_text(encoding='utf-8'))['scenarios']
    checks=[]
    for sid in range(1001,1011):
        rows={int(r.subset_mask):r._asdict() for r in allstates[allstates.scenario_id==sid].itertuples(index=False)}
        roads=solutions[str(sid)]['candidate_roads'];loss={m:r['loss'] for m,r in rows.items()}
        source,_,_=legacy_sa.run_sa(sid,loss,legacy_sa.SAConfig(.0025,.995,.7,.15),seed=2026081000+sid)
        class RegressionStore:
            def request(self,m):return rows[m],True
        oracle=QueryOracle(RegressionStore());run_method('sa_original',oracle,roads,sid,0)
        seq=tuple(roads[i] for i in source['best_sequence_bits'])
        assert oracle.used==source['queried_states'],(sid,oracle.used,source['queried_states'])
        assert abs(oracle.best-source['best_objective'])<1e-11
        assert oracle.best_seq==seq
        checks.append({'scenario_id':sid,'same_objective':True,'same_sequence':True,'same_query_count':True,'queries':oracle.used})
    dump(ROOT/'development/original_SA_compatibility.json',{'status':'pass','scope':'all ten historical tables, source-faithful software regression only; never used to tune new comparators','checks':checks})
    print('Original SA compatibility passed on all ten historical tables',flush=True)
