"""Accepted table/solver/context checks after prospective freeze, before any UE."""
from common55 import *
def main():
 m=js(OUT/'run_manifest.json');checks=[];s0=read(REV/'reviewer_4_2/00_protocol_and_input_audit/S0_input_manifest.csv')
 def ck(name,ok,actual='',expected=''):
  checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 for name in ['ue_solver.py','path_ue.py']:
  p=BASE/'code'/name;rows=s0[s0.absolute_path.str.replace('\\','/',regex=False).str.endswith('/code/'+name)]
  ck('4_2_accepted_solver_'+name,len(rows)>0 and sha(p) in rows.sha256.tolist(),sha(p),rows.sha256.tolist())
 rows=[]
 for sid in range(1001,1011):
  p=REV/f'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables/scenario_{sid}_path_solver_1e9_1024_states.csv.gz';f=read(p).sort_values('subset_mask')
  ck('accepted_states_'+str(sid),len(f)==1024 and f.subset_mask.tolist()==list(range(1024)) and f.converged.all() and f.relative_gap.max()<=TARGET and np.isfinite(f.tstt).all() and (f.tstt>0).all(),dict(rows=len(f),max_RG=float(f.relative_gap.max())),dict(rows=1024,RG='<=1e-9'))
  ck('normalization_'+str(sid),np.allclose(f.loss,f.tstt/T0-1,rtol=1e-13,atol=1e-12),float(abs(f.loss-(f.tstt/T0-1)).max()),'rounding only')
  rows.append(dict(scenario_id=sid,path=str(p),sha256=sha(p),rows=len(f),fields=json.dumps(f.columns.tolist()),max_RG=float(f.relative_gap.max()),solver=json.dumps(f.solver.unique().tolist())))
 env52=js(REPO/'revision_R1/comment5_2/audit/environment_UE.json');ck('5_2_same_frozen_solver_model_OD_context',m['solver_version']==env52['frozen_solver_version'],m['solver_version'],env52['frozen_solver_version'])
 save(OUT/'audit/accepted_state_table_inventory.csv',rows);status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL';dump(OUT/'audit/pre_solve_validation.json',dict(status=status,checks=checks,new_UE_started=False));print('PRE_SOLVE',status,len(checks),'checks')
 if status!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
