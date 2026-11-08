from experiment import *
import unittest
from scipy.sparse.csgraph import shortest_path
from scipy.sparse import csr_matrix
from path_ue import solve_paths

class FakeStore:
    def __init__(self):self.requests=[]
    def request(self,mask):
        self.requests.append(mask)
        return {'subset_mask':mask,'loss':float(10-bin(mask).count('1')),'tstt':100.0,'relative_gap':0.0,'iterations':1,'solver_seconds':0.0},False

class RevisionChecks(unittest.TestCase):
    def test_logical_budget_is_method_specific(self):
        store=FakeStore();a=QueryOracle(store,2);b=QueryOracle(store,2)
        a.request(0);a.request(0);a.request(1);b.request(0)
        self.assertEqual(a.used,2);self.assertEqual(b.used,1)
        self.assertEqual(store.requests,[0,1,0])
        with self.assertRaises(LimitReached):a.request(2)
        self.assertNotIn(2,a.known)
    def test_local_correction_is_actual_frozen_function(self):
        self.assertIs(SharedCorrection.local_search,original.BudgetedSearch.local_search)
        self.assertIs(SharedCorrection.move_neighbors,original.BudgetedSearch.move_neighbors)
    def test_terminal_has_zero_weight(self):
        roads=tuple(range(1,11));weights=list(range(1,11))
        costs={mask:sum(w for i,w in enumerate(weights) if mask&(1<<i)==0) for mask in range(1024)}
        costs[1023]=123456789
        j,seq=exact_dp(costs,roads)
        self.assertAlmostEqual(j,22.0);self.assertEqual(seq,tuple(range(10,0,-1)))
    def test_greedy_uses_55_states_and_only_required_prefixes(self):
        q=QueryOracle(FakeStore(),256);seq=greedy(q,tuple(range(1,11)))
        self.assertEqual(q.used,55);self.assertNotIn(1023,q.known);self.assertEqual(len(set(seq)),10)
    def test_every_baseline_returns_budget_feasible_solution(self):
        for method in ['sa_original','sa_restart','greedy_ls','greedy_ils','random_ls','ue_beam','ue_bibeam']:
            q=QueryOracle(FakeStore(),256);run_method(method,q,tuple(range(1,11)),246,0)
            self.assertLessEqual(q.used,256);self.assertEqual(len(set(q.best_seq)),10)
            self.assertTrue(set(masks(q.best_seq,tuple(range(1,11))))<=set(q.known))
    def test_gap_against_independent_scipy_shortest_paths(self):
        data=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=data[data.scenario_id==246].sort_values('physical_link_id');roads,_=select_roads(ph);net=Network(MODEL)
        active,fft,coef=net.state_arrays(ph,roads,495)
        x,tstt,gap,it,ok=solve_paths(net.tail,net.head,active,net.adj,net.degree,net.od,fft,coef,1e-9)
        cost=fft+coef*x**4
        graph=csr_matrix((cost[active],(net.tail[active],net.head[active])),shape=(24,24))
        dist=shortest_path(graph,directed=True,method='D');sp=float((net.od*dist).sum());independent=max(0,(float((x[active]*cost[active]).sum())-sp)/tstt)
        self.assertTrue(ok);self.assertLess(independent,1e-9);self.assertAlmostEqual(gap,independent,places=12)
        balance=np.bincount(net.tail,weights=x,minlength=24)-np.bincount(net.head,weights=x,minlength=24)
        self.assertLess(max(abs(balance-(net.od.sum(1)-net.od.sum(0)))),1e-5)
        self.assertTrue(np.all(x[~active]==0))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RevisionChecks)
    with (ROOT/'development/unit_test_log.txt').open('w',encoding='utf-8') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    dump(ROOT/'development/unit_test_result.json',{'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful()})
    if not result.wasSuccessful():raise SystemExit(1)
    print('All',result.testsRun,'revision integrity checks passed',flush=True)
