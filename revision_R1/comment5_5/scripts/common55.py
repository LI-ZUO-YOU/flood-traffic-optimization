from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parents[1];REPO=OUT.parents[1]
REV=Path('E:/jcr2区意见/返稿');BASE=REV/'4.1专项返修_20261026'
HOME=Path('E:/jcr2区意见/老家/sci-jcr2区交付/第四周工作')
SEL=HOME/'day2_candidate_screening_v1.0'
NETROOT=BASE/'source_snapshot/code/model_backend'
PHYS=BASE/'inputs/historical_1001_1010.csv'
PRE=SEL/'frozen_inputs/v2_surrogate/preprocessor_v2.json'
T0=7480225.3449211195;Q=360600.;TARGET=1e-9;MAX_OUTER=20000
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def read(p):return pd.read_csv(p,float_precision='round_trip')
def save(p,rows):
 f=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);f.to_csv(p,index=False,float_format='%.17g');return f
def pmask(roads):return sum(1<<(int(r)-1) for r in roads)
def restored(mask):return [i+1 for i in range(38) if int(mask)&(1<<i)]
def submask(roads,mask):return pmask([r for i,r in enumerate(roads) if mask&(1<<i)])
def close(a,b,tol=1e-12):return abs(float(a)-float(b))<=tol*max(1.,abs(float(a)),abs(float(b)))
