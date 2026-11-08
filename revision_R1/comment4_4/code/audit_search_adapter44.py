from common44 import *
from search_adapter44 import install,propose
from regression44 import ArchivedStateStore
def main():
 assert js(OUT/'logs/component_batch_completion.json')['tasks']==90
 a=install();cfg=js(ROOT/'protocol/frozen_protocol.json');data=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');checks=[]
 for sid in [3001,3002,3003]:
  ph=data[data.scenario_id==sid].sort_values('physical_link_id');roads,_=select_roads(ph,10);q=a.QueryOracle(ArchivedStateStore(sid));a.run_method('sa_original',q,roads,sid,0,config=cfg['selected_configurations'].get('sa_original'))
  base=ROOT/f'runs/query_cap/scenario_{sid}/sa_original/rep_00';r=js(base/'result.json');events=frame(base/'all_query_events.csv.gz');ledger=frame(base/'logical_query_ledger.csv.gz')
  row={'scenario_id':sid,'m':10,'objective_bitwise':float(q.best).hex()==float(r['best_objective']).hex(),'sequence_equal':list(q.best_seq)==r['best_sequence'],'all_requests_equal':q.events==list(events.itertuples(index=False,name=None)),'ledger_equal':[(x['subset_mask'],x['phase'],x['reason']) for x in q.rows]==list(zip(ledger.subset_mask,ledger.phase,ledger.reason.fillna(''))),'new_UE_calls':0};row['all_pass']=all(row[k] for k in ['objective_bitwise','sequence_equal','all_requests_equal','ledger_equal']);checks.append(row);assert row['all_pass']
 csv(OUT/'01_code_audit/S0_nested_SA_m10_regression.csv',checks)
 checks2=[];conf=frozen.legacy_sa.SAConfig(.0025,.995,.7,.15,1000)
 for m in [12,14]:
  start=tuple(range(m));seq=start;rng=np.random.default_rng(2026102904);moved=set()
  for i in range(1000):
   child=propose(seq,rng,conf);assert len(child)==m and set(child)==set(start)
   moved.update(j for j,(x,y) in enumerate(zip(seq,child)) if x!=y);seq=child
  row={'m':m,'proposals':1000,'all_positions_changed_at_least_once':moved==set(range(m)),'new_UE_calls':0};checks2.append(row);assert row['all_positions_changed_at_least_once']
 csv(OUT/'01_code_audit/S0_nested_SA_dimension_check.csv',checks2)
 p=frozen.SOURCE/'legacy_sa/run_permutation_sa.py';audit=frame(OUT/'01_code_audit/S0_code_assumption_audit.csv')
 additions=[]
 for no,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
  if 'N_ROADS' in line:additions.append({'file':str(p),'line':no,'assumption':'N_ROADS=10 in nested original SA','source_text':line.strip(),'handling':'search_adapter44.propose uses len(sequence), same RNG operation order; original module and source unchanged; old table/DP convenience functions not used','original_modified':False})
 csv(OUT/'01_code_audit/S0_code_assumption_audit.csv',pd.concat([audit,pd.DataFrame(additions)],ignore_index=True))
 dump(OUT/'00_lock/frozen_future_search_adapter.json',{'frozen_at':now(),'before_any_extended_scale_UE_or_quality_results':True,'reason':'nested original SA propose used module-global N_ROADS=10, which m10-only tests cannot reveal','entry_point':'search_adapter44.install','source_sha256':{str(p):sha(p) for p in [OUT/'code/search_adapter44.py',OUT/'code/methods_generalized.py',OUT/'code/candidate_generalized.py',OUT/'code/components44.py']},'SA_m10_replays_pass':3,'m12_m14_proposal_dimension_checks':True,'new_UE_calls':0,'component_timing_code_unchanged':True})
 print('Nested SA dimensional adapter PASS, archived m10 trajectories identical, no UE called',flush=True)
if __name__=='__main__':main()
