"""Read-only S4 analysis contract. No UE solve, search, scenario generation or fitting."""
from common45 import *
from s3_prepare import CONTROL,NEW,RUNS,REF,DELIVERY,EXPECTED,core_check
S4=OUT/'09_S4_mechanism_robustness'
METHODS=VARIANTS+['Greedy-ILS']
MODELS=['Ensemble','Single MLP','Ridge','HGB']
MODEL_VARIANTS={'Ensemble':'F0_FULL','Single MLP':'F6_SINGLE_MLP','Ridge':'F7_RIDGE','HGB':'F8_TREE'}

def path(sid,variant,rep):return RUNS/f'scenario_{sid}/{variant}/seed_{rep:02d}'
def ref(sid):return js(REF/f'scenario_{sid}/conditional_DP.json')
def costs(sid):
 d=frame(REF/f'scenario_{sid}/all_states_RG1e-9.csv.gz');return d.set_index('subset_mask').reindex(range(1024)).loss.to_numpy(float)
def sequences(series):return np.asarray([list(map(int,s.split('|'))) for s in series],dtype=np.int16)
def mask_matrix(seq,roads):
 bits=np.full(39,-1,dtype=np.int16)
 for i,r in enumerate(roads):bits[r]=i
 masks=np.zeros((len(seq),10),dtype=np.int16);mask=np.zeros(len(seq),dtype=np.int16)
 for j in range(9):mask=mask | (1<<bits[seq[:,j]]);masks[:,j+1]=mask
 return masks
def score(seq,roads,values):return values[mask_matrix(seq,roads)].mean(axis=1)
def regret(J,sid):return 100*(np.asarray(J)-ref(sid)['objective'])/ref(sid)['objective']
def sign_J(a,b,sid):
 d=a-b;tol=KAPPA*max(1,abs(ref(sid)['objective']))
 return 'tie' if abs(d)<=tol else 'win' if d<0 else 'loss'
def quant(x,p):return float(np.quantile(np.asarray(x,float),p,method='linear'))
def metric_rows():return frame(DELIVERY/'all_successful_runs_regret_and_cost.csv')

def immutable_check():
 core_check()
 for p,e in js(CONTROL/'S3_deployment_freeze.json')['files'].items():assert sha(p)==e['sha256'],p
 for p,h in js(CONTROL/'all_new_inputs_frozen.json')['files'].items():assert sha(p)==h,p
 seal=js(CONTROL/'all_330_method_outputs_frozen.json');assert seal['passed']==330 and seal['failed']==0
 for name,h in seal['files'].items():
  assert sha(name)==h
  for f,e in js(name)['files'].items():assert sha(Path(name).parent/f)==e['sha256']
 assert js(DELIVERY/'validation.json')['status']=='PASS'

def install_no_compute_guard():
 def denied(*a,**kw):raise RuntimeError('S4 FORBIDS optimization, fresh UE, generation, fitting and backpropagation')
 for attr in ['run_method','proposed','correction_baseline','sa','beam']:setattr(E,attr,denied)
 E.Network.solve=denied;E.PhysicalStore.request=denied
 import candidate_factory as cf
 cf.build=denied
 from sklearn.linear_model import Ridge
 from sklearn.ensemble import HistGradientBoostingRegressor
 Ridge.fit=denied;HistGradientBoostingRegressor.fit=denied
 import torch
 torch.set_num_threads(1);torch.autograd.backward=denied
 return {'UE_solves':0,'optimization_runs':0,'new_scenarios':0,'training_or_tuning_runs':0}

def prepare():
 require_new_output(S4);pin();immutable_check()
 for folder in ['00_audit','01_statistics','02_case5102','03_phases_costs','04_prediction_diagnostics','05_figures','06_report_response']: (S4/folder).mkdir()
 dump(S4/'00_audit/analysis_contract.json',{'at':now(),'frozen_v2_sha256':EXPECTED,'independent_unit':'scenario n10;3 seeds per method per scenario are technical repeats','main_cohort':'all5101-5110, no exclusions','sensitivity':'all10 symmetric leave-one-scenario-out summaries; no omission replaces the full-cohort result','differences':'regret_variant minus regret_F0 in percentage points; negative favors variant','ties':'abs(seed-mean J difference)<=kappa*max(1,abs(referenceJ))','seed_dispersion':'sample SD ddof1, min/max/range, descriptive P90 of3 seeds','inference':'descriptive only; no p values or confirmatory significance','state_error':'same1024 states per scenario, actual system mean(exp(log_prediction)-1); cost/log MAE,RMSE,R2 and Spearman; errors by restored count','common_pool':'each frozen F0 pool at each of3 seeds,4 frozen scorers; no new generation, no UE correction/search. Equal25/0/15/10/10 score-only primary selection, labels attached only afterwards','candidate_metrics':'Spearman and topK10/60/300 oracle availability; true top1percent recall; no best-model selection','mechanism':'direct logged facts vs source-rule deductions vs untested causal interpretation explicitly separate','allowed_diagnostic_reference':'conditional first-road values from existing state table, not a new algorithm run','forbidden':['new UE','new scenarios','optimization replays','training','tuning','900 retrospective runs','archives']})
 ops=install_no_compute_guard();dump(S4/'00_audit/no_new_computation_policy.json',ops)
 files=[]
 for folder in [CONTROL,NEW,REF,DELIVERY]:
  for p in folder.rglob('*'):
   if p.is_file() and p.suffix in ['.json','.csv','.gz']:files.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'role':'sealed S3 source'})
 csv(S4/'00_audit/input_manifest.csv',files)
 return ops
