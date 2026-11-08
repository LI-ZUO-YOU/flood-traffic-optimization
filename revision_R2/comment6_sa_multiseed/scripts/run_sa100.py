from common import *
from sa_kernel import *
import csv,gzip
def main():
 init();man=js(OUT/'run_manifest.json');freeze=js(OUT/'audit/prospective_freeze.json');assert man['status']=='FROZEN_BEFORE_FIRST_HIGHPRECISION_SA_RUN' and sha(OUT/'run_manifest.json')==freeze['run_manifest_sha256'];assert not (OUT/'raw/SA_all100_runs.csv').exists(),'Do not silently repeat formal searches'
 assert js(OUT/'audit/input_validation.json')['status']==js(OUT/'audit/legacy_replay_validation.json')['status']=='PASS'
 for r in man['critical_sources']+man['frozen_scripts']:assert sha(r['path'])==r['sha256'],r['path']
 assert sha(OUT/'seeds_frozen.csv')==man['seeds_sha256'] and EVIDENCE['search_body_AST_sha256']==man['search_AST_sha256']
 config=LEGACY.SAConfig(**man['configuration']);results=[];unique=[];trajectories=[];start=time.perf_counter()
 accessfile=(OUT/'raw/SA_query_ledger_all.csv').open('w',encoding='utf-8',newline='');accesswriter=csv.DictWriter(accessfile,fieldnames=['scenario_id','replicate','seed','access_index','sequence_call','iteration','subset_mask','new_charge','charged_after','loss','read_kind']);accesswriter.writeheader()
 callsfile=gzip.open(OUT/'raw/SA_proposals_all.csv.gz','wt',encoding='utf-8',newline='');callswriter=csv.DictWriter(callsfile,fieldnames=['scenario_id','replicate','seed','call_index','iteration','sequence_bits','missing_states_before','unique_before','unique_after','budget_feasible','objective','new_queries']);callswriter.writeheader()
 for case in man['runs']:
  sid=case['scenario_id'];rep=case['replicate'];seed=case['seed'];t=hp(sid);E=roads(sid);out=execute(sid,t.loss.to_numpy(float),config,seed)
  # All reference/trajectory information is added only after execute returns.
  Jstar=references()[str(sid)]['star_new'];J=out['J_SA'];regret=100*(J-Jstar)/Jstar;bits=out['best_sequence_bits'];seq=[E[i] for i in bits];epsJ=eps(Jstar);known=set(out['requested_masks']);path=masks(bits)+[1023]
  assert out['queries_charged']<=256 and set(path[:-1])<=known
  independent=float(sum(float(t.loss.iloc[m]) for m in path[:-1])/10);assert abs(independent-J)<=1e-12 and J>=Jstar-epsJ
  for stage,mask in enumerate(path):trajectories.append(dict(scenario_id=sid,replicate=rep,seed=seed,stage=stage,subset_mask=mask,restored_roads=canonical(seq[:stage]),loss=float(t.loss.iloc[mask]),tstt_raw=float(t.tstt.iloc[mask]),TSTT_veh_h=.01*float(t.tstt.iloc[mask]),ATT_min=.6*float(t.tstt.iloc[mask])/Q,weight=.1 if stage<10 else 0.,visible_to_search=mask in known,post_search_evaluation=True,charged_during_search=int(mask in known)))
  result={k:v for k,v in out.items() if k not in ['history','ledger','sequence_calls','cost_reads','RNG_final_state']};result.update(replicate=rep,B=256,best_sequence=seq,J_star_highprecision=Jstar,regret_pct=regret,raw_signed_regret_pct=regret,exact_hit=abs(J-Jstar)<=epsJ,hit_tolerance_J=epsJ,strict_float_zero=J==Jstar,within_1_5_pct=regret<=1.5,within_3_pct=regret<=3.,delta_ATT_min=ATT0*(J-Jstar),mean_stage_ATT_min=ATT0*(1+J),logical_state_uses=out['sequence_evaluations']*10,duplicate_logical_state_uses=out['sequence_evaluations']*10-out['queries_charged'],precision='RG<=1e-9 accepted path solver',timing_scope='sealed lookup SA search only; not online UE or table construction',source_table_sha256=sha(TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz'),completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  results.append(result);folder=OUT/f'raw/runs/scenario_{sid}/rep_{rep:02d}';folder.mkdir(parents=True,exist_ok=True);dump(folder/'result.json',{**result,'RNG_final_state':out['RNG_final_state']});save(folder/'source_history.csv',out['history']);save(folder/'unique_query_ledger.csv',out['ledger'])
  prefix=dict(scenario_id=sid,replicate=rep,seed=seed)
  for r in out['ledger']:unique.append({**prefix,**r})
  for r in out['cost_reads']:accesswriter.writerow({**prefix,**r})
  for r in out['sequence_calls']:callswriter.writerow({**prefix,**r})
  progress=dict(completed_runs=len(results),planned_runs=100,last_scenario=sid,last_replicate=rep,elapsed_with_exports_s=time.perf_counter()-start);dump(OUT/'logs/run_progress.json',progress)
  if len(results)%10==0:print(canonical(progress),flush=True)
 accessfile.close();callsfile.close();save(OUT/'raw/SA_unique_query_ledger.csv',unique);save(OUT/'raw/SA_trajectories.csv',trajectories);save(OUT/'raw/SA_all100_runs.csv',[{k:canonical(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in results]);dump(OUT/'audit/execution_validation.json',dict(status='PASS',highprecision_SA_runs=len(results),old_precision_replay_runs=10,new_real_UE_calls=0,DP_recalculations=0,total_search_wall_s=sum(r['runtime_s'] for r in results),total_search_CPU_s=sum(r['search_CPU_s'] for r in results),wall_with_exports_s=time.perf_counter()-start,all_unique_query_counts=[r['queries_charged'] for r in results],all_results_retained=True,reference_only_added_after_kernel_returns=True));print('Executed100 source-faithful HP SA searches; realUE=0 DP=0',flush=True)
if __name__=='__main__':main()
