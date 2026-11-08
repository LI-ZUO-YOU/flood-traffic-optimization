from __future__ import annotations
from pathlib import Path
import os,sys,json,hashlib,datetime
OUT=Path(__file__).resolve().parents[1]
BASE=Path(r'E:\jcr2区意见\返稿\4.1专项返修_20261026')
FORMAL=BASE/'正式模拟_v2'
PUB=Path(r'E:\jcr2区意见\urban-flood-road-reopening-reproducibility-v1.0-public')
ARCHIVE=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第四周工作\day4_exact_reference_regret_v1.0.zip')
LEGACY=BASE/'development/legacy_precision'
PLAN=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\Downloads\Reviewer1_4.2_数值精度实施操作流程.md')
for key,value in {'NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib'),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[key]=value
sys.dont_write_bytecode=True
sys.path.insert(0,str(BASE/'code'))
import numpy as np,pandas as pd
from numba import njit
import experiment as ex
T0=ex.LEGACY_BASELINE
FOLDERS=['00_protocol_and_input_audit','01_legacy_ue_state_comparison','02_original_method_path_reevaluation','03_selected_path_refinement','04_new30_supporting_evidence','05_manuscript_and_response']
for s in FOLDERS:(OUT/s).mkdir(parents=True,exist_ok=True)
AUD=OUT/FOLDERS[0];S1=OUT/FOLDERS[1];S2=OUT/FOLDERS[2];S3=OUT/FOLDERS[3];S4=OUT/FOLDERS[4];S5=OUT/FOLDERS[5]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 Path(p).parent.mkdir(parents=True,exist_ok=True)
 Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def csv(p,x):
 d=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
 d.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def seq(s):return tuple(map(int,str(s).split('|')))
def txt(s):return '|'.join(map(str,s))
def masks(s,roads):
 assert len(s)==len(roads)==10 and set(s)==set(roads)
 bits={r:1<<i for i,r in enumerate(roads)};m=0;res=[0]
 for r in s[:9]:m|=bits[r];res.append(m)
 return res
def obj(s,roads,cost):return float(sum(float(cost[m]) for m in masks(s,roads))/10)
def epsilon(star):return KAPPA*max(1,abs(star))
def equivalent(a,b,star):return abs(a-b)<=epsilon(star)
def regret(a,star):return 100*(a-star)/star
def old_states():return frame(AUD/'source_records/archive/subset_ue_costs.csv')
def saved_solutions():return js(AUD/'source_records/archive/exact_dp_solution.json')['scenarios']
def physical():return pd.read_csv(BASE/'inputs/historical_1001_1010.csv')
PROTOCOL=js(FORMAL/'protocol/frozen_protocol.json')
KAPPA=PROTOCOL['equivalence']['equivalence_kappa']
assert PROTOCOL['equivalence']['equivalence_rule']=='abs(Ja-Jb) <= kappa*max(1,abs(Jreference)); empirically calibrated, not a rigorous UE error bound'

def dp(c,roads):
 """Top two distinct permutations. Strict floating ties use full road-ID lex order."""
 c=np.asarray(c,float);best=[None]*1024;best[0]=[(float(c[0]),())]
 for m in range(1,1024):
  entries=[]
  for i,r in enumerate(roads):
   if m&(1<<i):
    for value,path in best[m^(1<<i)]:entries.append((value+(0. if m==1023 else float(c[m])),path+(int(r),)))
  entries.sort(key=lambda z:(z[0],z[1]));best[m]=entries[:2]
 return best[1023][0][0]/10,best[1023][0][1],best[1023][1][0]/10,best[1023][1][1]

def backward(c):
 v=np.zeros(1024)
 for m in range(1022,-1,-1):v[m]=c[m]+min(v[m|(1<<i)] for i in range(10) if not m&(1<<i))
 return v

@njit(cache=True)
def near_paths(mask,acc,c,v,bound,touched):
 # Enumerate only prefixes whose optimal completion can fit the fixed band.
 # A roundoff guard is used only for pruning, never for accepting a leaf.
 if acc+v[mask]>bound+1e-10*max(1.,abs(bound)):return 0
 if mask==1023:
  if acc<=bound:
   touched[mask]=1;return 1
  return 0
 total=0
 for i in range(10):
  if not mask&(1<<i):total+=near_paths(mask|(1<<i),acc+c[mask],c,v,bound,touched)
 if total>0:touched[mask]=1
 return total

def near(c,star,tol):
 c=np.asarray(c,float);v=backward(c);touched=np.zeros(1024,np.uint8)
 count=near_paths(0,0.,c,v,10*(star+tol),touched)
 return int(count),set(map(int,np.flatnonzero(touched)))

def verify_sources():
 d=frame(AUD/'S0_input_manifest.csv')
 for r in d.itertuples(index=False):assert sha(r.absolute_path)==r.sha256,'Source modified '+r.absolute_path
 return len(d)
