from pathlib import Path
import os,sys,json,hashlib,datetime,subprocess
OUT=Path(__file__).resolve().parents[1];REPO=OUT.parents[1]
REV=Path('E:/jcr2区意见/返稿');BASE=REV/'4.1专项返修_20261026';FORMAL=BASE/'正式模拟_v2'
ARCHIVE_ROOT=Path('E:/jcr2区意见/老家/sci-jcr2区交付')
SA_SOURCE=ARCHIVE_ROOT/'初稿/Frontiers_Submission_Package_P1_v2.2/reproducibility/p1_revision_tools/run_permutation_sa.py'
SA_SNAPSHOT=FORMAL/'source_snapshot/legacy_sa/run_permutation_sa.py'
SA_ARCHIVE=ARCHIVE_ROOT/'第四周工作/P1_poststudy_permutation_SA_v1.0'
OLD_TABLE=ARCHIVE_ROOT/'第四周工作/day4_exact_reference_regret_v1.0/08_exact_reference_after_method_freeze/subset_ue_costs.csv'
R42=REV/'reviewer_4_2';TABLES=R42/'01_legacy_ue_state_comparison/source_state_tables'
NEW30=REV/'revision_4_6_tail_inference/02_new30';FULL=ARCHIVE_ROOT/'第四周工作/day3_live_ue_methods_v1.0/06_full_method'
T0=7480225.3449211195;Q=360600.;ATT0=.6*T0/Q;BUDGET=256;HIT_RTOL=1e-9
sys.dont_write_bytecode=True
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib'),'PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[k]=v
sys.path.insert(0,str(BASE/'runtime_deps'))
import numpy as np,pandas as pd
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def read(p):return pd.read_csv(p,float_precision='round_trip')
def save(p,rows):
 f=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);Path(p).parent.mkdir(parents=True,exist_ok=True);f.to_csv(p,index=False,float_format='%.17g');return f
def init():
 for d in ['audit','raw','figures','logs','tests','runtime_cache','raw/original_logs','raw/runs']: (OUT/d).mkdir(parents=True,exist_ok=True)
def gitstate():return {k:subprocess.check_output(['git','-C',str(REPO)]+args,text=True).strip() for k,args in [('HEAD',['rev-parse','HEAD']),('branch',['branch','--show-current'])]}
def hp(sid):return read(TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz').sort_values('subset_mask')
def references():return js(R42/'01_legacy_ue_state_comparison/independent_references.json')
def roads(sid):return list(references()[str(sid)]['roads'])
def masks(bits):
 m=0;out=[0]
 for bit in bits[:-1]:m|=1<<int(bit);out.append(m)
 return out
def sequence_value(bits,loss):return float(np.mean([loss[m] for m in masks(bits)]))
def eps(J):return HIT_RTOL*max(1.,abs(float(J)))
