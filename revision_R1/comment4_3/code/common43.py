from __future__ import annotations
from pathlib import Path
import os,sys,json,hashlib,time,datetime,platform
OUT=Path(__file__).resolve().parents[1]
ROOT=Path(r'E:\jcr2区意见\返稿\4.1专项返修_20261026\正式模拟_v2')
OLD=ROOT/'analysis_round2'
PLAN=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\Downloads\Reviewer1_4.3_计算效率与成本核算实施方案.md')
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib')}.items():os.environ[k]=v
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'code'))
import numpy as np,pandas as pd,psutil
import experiment as ex
CFG=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
CORE=0;FOUR_CORES=[0,2,4,6]
METHODS=['proposed','sa_original','greedy_ils','ue_bibeam','enum_serial']
STOCHASTIC=['proposed','sa_original','greedy_ils']
for f in ['00_protocol_and_input_audit','01_complexity','02_serial_B256','03_enum_within_scenario_4core','04_cold_start','05_offline_cost','06_analysis','07_manuscript_and_response','logs']:(OUT/f).mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def csv(p,x):
 d=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
 d.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def scenario(sid):
 d=pd.read_csv(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');ph=d[d.scenario_id==sid].sort_values('physical_link_id')
 roads,audit=ex.select_roads(ph);saved=js(ROOT/'inputs/new_validation/selected_roads.json')[str(sid)]
 assert list(roads)==saved['roads'];return ph,roads,audit
def warm(net):
 d=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=d[d.scenario_id==246].sort_values('physical_link_id');roads,_=ex.select_roads(ph)
 rr=net.solve(ph,roads,0,1e-9);assert rr['relative_gap']<=1e-9
def pin(core=CORE):psutil.Process().cpu_affinity([core])
def verify_sources():
 m=js(OUT/'00_protocol_and_input_audit/S0_manifest.json')
 for p,h in m['files_sha256'].items():assert sha(p)==h,'Source changed '+p
 return len(m['files_sha256'])
def core_masks():
 import ctypes as C
 class U(C.Union):_fields_=[('reserved',C.c_ulonglong*2)]
 class I(C.Structure):_fields_=[('mask',C.c_size_t),('relationship',C.c_int),('u',U)]
 size=C.c_ulong(0);fn=C.windll.kernel32.GetLogicalProcessorInformation;fn(None,C.byref(size));buf=C.create_string_buffer(size.value)
 if not fn(buf,C.byref(size)):raise OSError('Cannot query physical processor topology')
 result=[]
 for start in range(0,size.value,C.sizeof(I)):
  item=I.from_buffer_copy(buf.raw[start:start+C.sizeof(I)])
  if item.relationship==0:result.append([i for i in range(64) if item.mask&(1<<i)])
 return result

def validate_frozen(q,sid,method,rep,candidate_report):
 # References are opened only after timing/search has ended.
 oldrep=rep if method in STOCHASTIC else 0
 base=ROOT/f'runs/query_cap/scenario_{sid}/{method}/rep_{oldrep:02d}'
 r=js(base/'result.json');l=frame(base/'logical_query_ledger.csv.gz');events=frame(base/'all_query_events.csv.gz')
 checks={'objective_bitwise_equal':float(q.best).hex()==float(r['best_objective']).hex(),'sequence_equal':list(q.best_seq)==r['best_sequence'],
  'actual_queries_equal':q.used==r['actual_queries'],'logical_request_count_equal':q.requests==r['logical_requests'],
  'unique_query_order_phase_reason_equal':[(x['subset_mask'],x['phase'],x['reason']) for x in q.rows]==list(zip(l.subset_mask,l.phase,l.reason.fillna(''))),
  'all_logical_request_events_equal':list(q.events)==list(events.itertuples(index=False,name=None))}
 if method=='proposed':checks['candidate_order_SHA_equal']=candidate_report['candidate_order_sha256']==r['candidate_order_sha256']
 checks['all_pass']=all(checks.values())
 return checks,r

class TimedNetwork(ex.Network):
 def __init__(self,*a,**kw):super().__init__(*a,**kw);self.wall=0.;self.calls=0
 def solve(self,*a,**kw):
  start=time.perf_counter()
  try:return super().solve(*a,**kw)
  finally:self.wall+=time.perf_counter()-start;self.calls+=1

BASE_CORRECTION=ex.SharedCorrection
class TimingCorrection(BASE_CORRECTION):
 def local_search(self,*a,**kw):
  timer=TIMERS;ue0=timer['network'].wall;start=time.perf_counter()
  try:return super().local_search(*a,**kw)
  finally:
   elapsed=time.perf_counter()-start;timer['LS_inclusive']+=elapsed;timer['LS_UE']+=timer['network'].wall-ue0;timer['LS_calls']+=1
TIMERS={}

def execute_one(sid,method,rep,folder,cold=False):
 pin();setup=time.perf_counter();ph,roads,audit=scenario(sid);net=TimedNetwork(ex.MODEL)
 predictor=ex.api.SurrogateV2(ex.SOURCE/'surrogate/final_ensemble') if method=='proposed' else None
 setup_wall=time.perf_counter()-setup
 net.wall=0.;net.calls=0
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 process=psutil.Process();cpu_before=process.cpu_times();start_stamp=now()
 candidate=0.;infer=0.;candidate_report={};dp_wall=0.;q=None
 TIMERS.clear();TIMERS.update({'network':net,'LS_inclusive':0.,'LS_UE':0.,'LS_calls':0})
 original_cls=ex.SharedCorrection;ex.SharedCorrection=TimingCorrection
 try:
  start=time.perf_counter()
  if method=='enum_serial':
   rows=[net.solve(ph,roads,m,1e-9) for m in range(1024)];after_UE=time.perf_counter();costs={r['subset_mask']:r['loss'] for r in rows}
   d0=time.perf_counter();value,sequence=ex.exact_dp(costs,roads);dp_wall=time.perf_counter()-d0
  else:
   store=ex.PhysicalStore(net,ph,roads,db=None,target=1e-9);assert len(store.cache)==0
   q=ex.QueryOracle(store,budget=256,time_limit=None);screened=None
   if method=='proposed':
    c0=time.perf_counter();screened,candidate_report=ex.build_candidates(ph,roads,audit,sid,rep,predictor);candidate=time.perf_counter()-c0
    infer=candidate_report['surrogate_inference_seconds']
   ex.run_method(method,q,roads,sid,rep,screened,CFG['selected_configurations'].get(method))
   value=q.best;sequence=q.best_seq;rows=q.rows
  end=time.perf_counter();online=end-start
 finally:ex.SharedCorrection=original_cls
 end_stamp=now();cpu_after=process.cpu_times();uewall=net.wall
 ls_exclusive=max(0.,TIMERS['LS_inclusive']-TIMERS['LS_UE'])
 other=online-candidate-uewall-ls_exclusive-dp_wall
 assert other>=-1e-6
 # Exporting files and comparing the old reference are outside the online timer.
 logstart=time.perf_counter()
 sol=js(ROOT/f'exact/scenario_{sid}/exact_solution.json')
 if method=='enum_serial':
  checks={'objective_bitwise_equal':float(value).hex()==float(sol['exact_objective']).hex(),'sequence_equal':list(sequence)==sol['sequence'],
   'all1024_masks':set(r['subset_mask'] for r in rows)==set(range(1024))}
  checks['all_pass']=all(checks.values());unique=1024;logical=1024
  csv(folder/'all_1024_states.csv.gz',rows)
 else:
  checks,r=validate_frozen(q,sid,method,rep,candidate_report);unique=q.used;logical=q.requests
  q.save(folder,method,rep,sid,{'fresh_state_cache':True,'cpu_core':CORE,'query_cap':256,'wall_clock_cap':None,
    'timing_note':'result.json wall_seconds includes post-timer checks; authoritative online time is timing.json',**candidate_report})
 assert max(r['relative_gap'] for r in rows)<=1e-9 and all(r['converged'] for r in rows)
 assert net.calls==unique
 logwall=time.perf_counter()-logstart
 # Record seed components exactly as in the original frozen formulas.
 seeds={
  'proposed':{'candidate_seed':2026080702+sid+1000000*rep,'screening_seed':2026080703+sid+1000000*rep},
  'sa_original':{'algorithm_seed':2026081000+sid+1000000*rep},
  'greedy_ils':{'algorithm_seed':2026102603+sid+1000000*rep}}
 result={'scenario_id':sid,'method':method,'replicate':rep,'original_seed_index':rep if method in STOCHASTIC else None,'seed_values':seeds.get(method,{}),
  'repeat_id':rep,'unique_UE_queries':unique,'logical_requests':logical,'query_cap':256 if q is not None else 1024,'wall_clock_cap':None,
  'natural_early_stop':q is not None and unique<256,'UE_solver_wall':uewall,'UE_kernel_wall_nested':sum(r['solver_seconds'] for r in rows),
  'candidate_wall_inclusive':candidate,'candidate_wall_excluding_inference':max(0,candidate-infer),'inference_wall_nested_in_candidate':infer,
  'LS_wall_inclusive_of_UE':TIMERS['LS_inclusive'],'LS_UE_wall_nested':TIMERS['LS_UE'],'LS_wall_excluding_UE':ls_exclusive,
  'other_wall':max(0,other),'DP_wall':dp_wall,'total_online_wall':online,'setup_input_model_wall_excluded':setup_wall,'export_wall_excluded':logwall,
  'cpu_user_seconds':cpu_after.user-cpu_before.user,'cpu_system_seconds':cpu_after.system-cpu_before.system,
  'target_value':value,'target_hex':float(value).hex(),'sequence':list(sequence),'regret_pct':max(0,100*(value-sol['exact_objective'])/sol['exact_objective']),
  'numerical_failures':0,'max_actual_RG':max(r['relative_gap'] for r in rows),'cpu_core':CORE,'process_id':os.getpid(),
  'started_Asia_Shanghai':start_stamp,'finished_Asia_Shanghai':end_stamp,'bitwise_gate':checks,'candidate_report':candidate_report,
  'fresh_physical_cache':True,'single_process_primary':True,'threads':1,'cold_process_supplement':cold,
  'measurement_wrapper_sha256':sha(Path(__file__))}
 dump(folder/'timing.json',result)
 if not checks['all_pass']:
  dump(OUT/'logs/STOP_bitwise_gate_failure.json',result)
  raise RuntimeError(f'Bitwise reproducibility gate failed: {sid} {method} rep{rep}')
 return result
