from common import *
from sa_kernel import *
def main():
 init();assert sha(SA_SOURCE)==sha(SA_SNAPSHOT),'Original source conflict'
 config_record=js(SA_ARCHIVE/'sa_configuration_freeze.json');config=LEGACY.SAConfig(**config_record['selected_configuration']);assert LEGACY.config_key(config)==config_record['selected_config_id']=='742ec3e18494'
 # Preserve the original loader exactly. It used pandas' default CSV parser,
 # not round_trip. No alternate table/seed/precision is selected after replay.
 old=LEGACY.tables_by_scenario(OLD_TABLE);checks=[];results=[];numeric=[]
 for sid in range(1001,1011):
  out=execute(sid,old[sid],config,2026081000+sid);archive=SA_ARCHIVE/f'final_once_only/scenario_{sid}';expected=js(archive/'result.json');h=pd.read_csv(archive/'sa_history.csv');l=pd.read_csv(archive/'logical_ue_query_ledger.csv');nh=pd.DataFrame(out['history']);nl=pd.DataFrame(out['ledger'])
  def ck(label,ok,actual=None,expect=None):checks.append(dict(scenario_id=sid,check=label,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expect))
  ck('best_sequence_bits',out['best_sequence_bits']==expected['best_sequence_bits'],out['best_sequence_bits'],expected['best_sequence_bits']);ck('queries',out['queries_charged']==expected['queried_states'],out['queries_charged'],expected['queried_states']);ck('proposals',out['proposals']==expected['iterations_completed'],out['proposals'],expected['iterations_completed']);ck('accepted',out['accepted_moves']==expected['accepted_moves'])
  tolerance=8*np.finfo(float).eps*max(1.,abs(expected['best_objective']));err=abs(out['J_SA']-expected['best_objective']);ck('objective_serialization_8eps',err<=tolerance,err,tolerance)
  ck('complete_new_mask_access_order',nl.subset_mask.tolist()==l.subset_mask.tolist());ck('complete_ledger_iteration',nl.iteration.tolist()==l.iteration.tolist());ck('complete_ledger_charging_index',nl.logical_query_index.tolist()==l.logical_query_index.tolist());ck('history_rows',len(nh)==len(h),len(nh),len(h))
  for col in ['iteration','sequence_bits','accepted','improved_best','queried_states']:ck('history_'+col,nh[col].tolist()==h[col].tolist())
  for col in ['temperature','candidate_objective','current_objective','best_objective']:
   a=nh[col].to_numpy(float);b=h[col].to_numpy(float);both=np.isfinite(a)&np.isfinite(b);tol=8*np.finfo(float).eps*np.maximum(1.,abs(b[both]));delta=abs(a[both]-b[both]);ok=bool(np.array_equal(np.isnan(a),np.isnan(b)) and np.all(delta<=tol));ck('history_numeric_'+col,ok,float(delta.max(initial=0)),float(tol.max(initial=0)));numeric.append(dict(scenario_id=sid,column=col,max_absolute_error=float(delta.max(initial=0)),bitwise_finite_equal=bool(np.array_equal(a[both],b[both])),serialization_tolerance='8eps*max(1,abs(archived)); fixed before replay',pass_=ok))
  save(OUT/f'raw/old_replay/scenario_{sid}_history.csv',nh);save(OUT/f'raw/old_replay/scenario_{sid}_ledger.csv',nl);dump(OUT/f'raw/old_replay/scenario_{sid}_result.json',{k:v for k,v in out.items() if k not in ['history','ledger','sequence_calls','cost_reads']});results.append({k:v for k,v in out.items() if k not in ['history','ledger','sequence_calls','cost_reads','RNG_final_state','requested_masks']})
 save(OUT/'audit/legacy_replay_checks.csv',checks);save(OUT/'audit/legacy_replay_numeric.csv',numeric);save(OUT/'raw/legacy_replay_results.csv',[{**r,'best_sequence_bits':canonical(r['best_sequence_bits'])} for r in results]);dump(OUT/'audit/search_AST_binding.json',EVIDENCE);dump(OUT/'audit/firewall_tests.json',firewall_tests());ok=all(r['status']=='PASS' for r in checks);dump(OUT/'audit/legacy_replay_validation.json',dict(status='PASS' if ok else 'FAIL',scenarios=10,checks_passed=sum(r['status']=='PASS' for r in checks),checks_total=len(checks),history_and_ledger_fully_compared=True,DP_recalculated=False,real_UE_calls=0,objective_numeric_policy='8eps relative to max(1, archived), fixed before run for decimal/float64 serialization; trajectories and masks exact',max_objective_error=max(r['actual'] for r in checks if r['check']=='objective_serialization_8eps')))
 print('Legacy gate',ok,sum(r['status']=='PASS' for r in checks),'/',len(checks),flush=True)
 if not ok:raise RuntimeError('Original replay failed; high-precision extension BLOCKED')
if __name__=='__main__':main()
