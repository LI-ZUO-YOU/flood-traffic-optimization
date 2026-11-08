"""Ten required acceptance checks, using recorded executions and independent reconstruction."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from common45 import *
from verify_batch import verify_run,check_manifest
from run_sealed import load_table
import unittest

class Acceptance(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.smoke=OUT/'02_smoke_old_scenarios';cls.dev=OUT/'01_freeze_and_regression/development_v2';cls.repeat=OUT/'01_freeze_and_regression/reproducibility_v2'
 def paths(self):return sorted(self.smoke.glob('scenario_*/*/seed_00'))
 def test_baseline_bitwise_replay(self):
  for sid in [3001,3002,3003]:self.assertEqual(verify_run(self.smoke/f'scenario_{sid}/F0_FULL/seed_00',True)['baseline_bitwise'],'PASS')
 def test_variants_budget_and_cache(self):
  self.assertEqual(len(self.paths()),30)
  for p in self.paths():self.assertEqual(verify_run(p)['all_checks'],'PASS')
 def test_all_30k_candidates_unique(self):
  for p in self.paths():
   f=frame(p/'candidate_pool.csv.gz');self.assertEqual(f.sequence.nunique(),30000);self.assertEqual(f.candidate_id.nunique(),30000)
 def test_no_reserve_flat_fallback(self):
  for sid in [3001,3002,3003]:
   f=frame(self.smoke/f'scenario_{sid}/F1_NO_RESERVE/seed_00/screened_candidates.csv.gz');self.assertFalse((f.screening_tier=='structural_reserve').any());self.assertEqual(len(f),30000);self.assertEqual(f.prefix_2.nunique(),90)
 def test_no_disagreement_seats(self):
  for p in self.paths():
   if p.parent.name in ['F3_NO_DISAG','F6_SINGLE_MLP','F7_RIDGE','F8_TREE']:
    f=frame(p/'screened_candidates.csv.gz');d=f[f.screening_tier=='primary_shortlist'].channel.value_counts().to_dict();self.assertEqual(d,{'proxy_top':25,'sequence_diversity':15,'heuristic':10,'random':10})
 def test_predictor_training_firewall(self):
  v=js(OUT/'01_freeze_and_regression/simple_models/training_firewall_validation.json');self.assertEqual(v['status'],'PASS');self.assertFalse(v['retrospective_or_new_scenario_labels_used']);self.assertEqual(v['actual_training_ids'],list(range(1,61))+list(range(201,261)))
  manifest=js(OUT/'protocol/freeze_manifest.json')
  for name,entry in manifest['files'].items():self.assertEqual(sha(name),entry['sha256'])
 def test_phase_attribution_identity(self):
  for p in self.paths():
   ph=frame(p/'phase_query_efficiency.csv');r=js(p/'result.json');self.assertEqual(int(ph.unique_queries_phase.sum()),r['actual_queries']);self.assertTrue(pd.isna(ph.iloc[0].delta_best_J_phase));self.assertEqual(int(ph.incumbent_updates_phase.sum()),len(frame(p/'incumbent_improvement_trace.csv')))
 def test_reference_firewall(self):
  for p in self.paths():
   check_manifest(p);v=js(p/'firewall.json');self.assertEqual(v['unexpected_denials'],0);self.assertEqual(len(v['probe_denials']),1);self.assertFalse(v['full_reference_in_worker']);self.assertLessEqual(js(p/'broker_validation.json')['released_unique_states'],256)
 def test_dp_reconstruction(self):
  for sid in [3001,3002,3003]:
   for variant in VARIANTS:check_manifest(self.smoke/f'scenario_{sid}/{variant}/seed_00')
   table=load_table(sid);costs=np.array([table[i]['loss'] for i in range(1024)]);roads=public_scenario(sid)[1]
   a,seq=E.exact_dp(costs,roads);policy=E.gen.successor_policy(costs,list(roads));other=E.gen.complete_by_policy((),list(roads),policy)
   b=float(np.mean(costs[E.masks(other,roads)]));c=float(np.mean(costs[E.masks(seq,roads)]))
   self.assertAlmostEqual(a,b,places=10);self.assertAlmostEqual(a,c,places=10);self.assertEqual(len(costs),1024);self.assertLess(abs(a-b)/max(abs(a),1),KAPPA)
 def test_reproducible_hashes(self):
  for variant in ['F0_FULL','F9_NO_SURROGATE']:
   a=self.dev/f'scenario_246/{variant}/seed_00';b=self.repeat/f'scenario_246/{variant}/seed_00';x=js(a/'result.json');y=js(b/'result.json')
   for k in ['candidate_order_sha256','best_sequence','best_objective','actual_queries','logical_requests']:self.assertEqual(x[k],y[k])
   for name in ['candidate_pool.csv.gz','screened_candidates.csv.gz']:self.assertEqual(sha(a/name),sha(b/name))
   pd.testing.assert_frame_equal(frame(a/'all_query_events.csv.gz'),frame(b/'all_query_events.csv.gz'),check_exact=True)

if __name__=='__main__':unittest.main(verbosity=2)
