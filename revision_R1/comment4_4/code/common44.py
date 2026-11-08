from __future__ import annotations
from pathlib import Path
import os,sys,json,hashlib,time,datetime
OUT=Path(__file__).resolve().parents[1]
ROOT=Path(r'E:\jcr2区意见\返稿\4.1专项返修_20261026\正式模拟_v2')
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib')}.items():os.environ[k]=v
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'code'))
import numpy as np,pandas as pd,psutil
import experiment as frozen
for f in ['00_lock','01_code_audit','02_scenarios','03_component_scaling','04_method_scaling','05_analysis','06_manuscript_response','logs']:(OUT/f).mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def csv(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 (x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)).to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def pin():psutil.Process().cpu_affinity([0])
def verify():
 m=js(OUT/'00_lock/S0_frozen_manifest.json')
 for p,h in m['sha256'].items():assert sha(p)==h,'Frozen input changed '+p
 return len(m['sha256'])
def select_roads(ph,m):
 pre=js(frozen.SOURCE/'surrogate/final_ensemble/preprocessor_v2.json')
 audit=ph.sort_values('physical_link_id').copy();audit['physical_flow']=pre['baseline_flow'];audit['betweenness']=pre['betweenness']
 closed=audit[audit.is_closed==1].copy();n=len(closed)
 if n<m:raise ValueError(f'{m} roads requested, {n} initially closed')
 for c in ['physical_flow','betweenness']:closed[c+'_score']=(n-closed[c].rank(ascending=False,method='min'))/(n-1)
 closed['combined_score']=.5*closed.physical_flow_score+.5*closed.betweenness_score
 closed=closed.sort_values(['combined_score','physical_flow','betweenness','physical_link_id'],ascending=[False,False,False,True],kind='mergesort')
 audit=audit.merge(closed[['physical_link_id','physical_flow_score','betweenness_score','combined_score']],on='physical_link_id',how='left')
 return tuple(closed.head(m).physical_link_id.astype(int)),audit
def connected(ph):
 adj={i:[] for i in range(1,25)}
 for r in ph.itertuples():
  if not r.is_closed:adj[r.physical_from].append(r.physical_to);adj[r.physical_to].append(r.physical_from)
 seen={1};stack=[1]
 while stack:
  for v in adj[stack.pop()]:
   if v not in seen:seen.add(v);stack.append(v)
 return len(seen)==24
def physical(sid,m):
 ph=frame(OUT/'02_scenarios/extended_severity_physical.csv');ph=ph[ph.scenario_id==sid].sort_values('physical_link_id').copy()
 fixture=False
 if m==16:
  fixture=True
  # Explicitly nonphysical, disconnected feature fixture. Never passed to a UE solver.
  extras=ph[ph.is_closed==0].physical_link_id.astype(int).tolist()[:2]
  ph.loc[ph.physical_link_id.isin(extras),['depth_m','is_closed','is_wet']]=[.4,1,1]
 roads,audit=select_roads(ph,m)
 return ph,roads,audit,fixture
