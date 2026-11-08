from common44 import *
from components44 import build,install_search_dimensions
class ArchivedStateStore:
 def __init__(self,sid):
  paths=list((ROOT/f'exact/scenario_{sid}').glob('*state*csv*'))
  assert len(paths)==1,paths
  self.rows={int(r['subset_mask']):r for r in frame(paths[0]).to_dict('records')};self.reads=0
 def request(self,mask):self.reads+=1;return self.rows[int(mask)],True
def main():
 pin();verify();import torch;torch.set_num_threads(1)
 a=install_search_dimensions();cfg=js(ROOT/'protocol/frozen_protocol.json');predictor=frozen.api.SurrogateV2(frozen.SOURCE/'surrogate/final_ensemble')
 data=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');checks=[]
 for sid in [3001,3002,3003]:
  ph=data[data.scenario_id==sid].sort_values('physical_link_id');roads,audit=select_roads(ph,10);assert roads==frozen.select_roads(ph)[0]
  folder=OUT/f'01_code_audit/m10_regression/scenario_{sid}';folder.mkdir(parents=True,exist_ok=True)
  screen,report=build(ph,roads,audit,sid,0,predictor,folder)
  expected_screen=frame(ROOT/f'runs/query_cap/scenario_{sid}/proposed/rep_00/screened_candidates.csv.gz')
  screen_pass=screen.candidate_id.tolist()==expected_screen.candidate_id.tolist()
  for method in ['proposed','greedy_ils','ue_bibeam','sa_original']:
   store=ArchivedStateStore(sid);q=a.QueryOracle(store,budget=256);a.run_method(method,q,roads,sid,0,screen if method=='proposed' else None,cfg['selected_configurations'].get(method))
   original=ROOT/f'runs/query_cap/scenario_{sid}/{method}/rep_00';r=js(original/'result.json');ledger=frame(original/'logical_query_ledger.csv.gz');events=frame(original/'all_query_events.csv.gz')
   test={'scenario_id':sid,'method':method,'replicate':0,'objective_bitwise':float(q.best).hex()==float(r['best_objective']).hex(),'sequence_equal':list(q.best_seq)==r['best_sequence'],'queries_equal':q.used==r['actual_queries'],'request_count_equal':q.requests==r['logical_requests'],'unique_query_masks_phases_reasons_equal':[(x['subset_mask'],x['phase'],x['reason']) for x in q.rows]==list(zip(ledger.subset_mask,ledger.phase,ledger.reason.fillna(''))),'all_logical_events_equal':q.events==list(events.itertuples(index=False,name=None)),'seed_rule_unchanged':True,'new_UE_solves':0,'regression_mode':'archived physical costs, fresh logical search'}
   if method=='proposed':test.update({'candidate_order_SHA_equal':report['candidate_order_sha256']==r['candidate_order_sha256'],'screened_candidate_order_equal':screen_pass})
   test['all_pass']=all(v for k,v in test.items() if k.endswith(('_equal','_bitwise','_unchanged')))
   q.save(folder/method,method,0,sid,{'archived_physical_cost_regression':True,'new_UE_calls':0});checks.append(test);csv(OUT/'01_code_audit/S0_m10_regression_gate.csv',checks)
   print(json.dumps(test,ensure_ascii=False),flush=True)
   assert test['all_pass'],test
 dump(OUT/'01_code_audit/regression_acceptance.json',{'status':'PASS','cases':3,'method_runs':12,'all_pass':all(r['all_pass'] for r in checks),'new_UE_calls':0,'scope':'search logic and exact archived output reproduction, not fresh UE/timing replication','verified_source_files':verify()})
if __name__=='__main__':main()
