from pathlib import Path
import os,sys,json,time,hashlib,datetime
OUT=Path(__file__).resolve().parents[1]
ROOT=Path(r'E:\jcr2区意见\返稿\4.1专项返修_20261026\正式模拟_v2')
HOME=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第二周工作')
PLAN=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\Downloads\Reviewer1_4.5_组件消融与简化代理_可执行实施方案.md')
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba')}.items():os.environ[k]=v
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'code'))
import numpy as np,pandas as pd,psutil
import experiment as E
CFG=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
KAPPA=CFG['equivalence']['equivalence_kappa']
VARIANTS=['F0_FULL','F1_NO_RESERVE','F2_NO_PREFIX','F3_NO_DISAG','F4_NO_PROXY_SOURCES','F5_RANDOM_POOL','F6_SINGLE_MLP','F7_RIDGE','F8_TREE','F9_NO_SURROGATE']

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),encoding='utf-8')
def csv(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);df=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
 df.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g',compression={'method':'gzip','mtime':0} if p.name.endswith('.gz') else None)
def frame(p,**kw):return pd.read_csv(p,float_precision='round_trip',**kw)
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def pin():psutil.Process().cpu_affinity([0])
def sub_seed(sid,rep,variant,op):return int.from_bytes(hashlib.sha256(f'{sid}|{rep}|{variant}|{op}'.encode()).digest()[:8],'little')
def rng(sid,rep,variant,op):return np.random.default_rng(sub_seed(sid,rep,variant,op))
def verify_sources():
 for r in frame(OUT/'00_audit/source_manifest.csv').to_dict('records'):assert sha(r['path'])==r['sha256'],'Source hash changed '+r['path']
def public_scenario(sid):
 ph=frame(OUT/f'00_audit/public_inputs/scenario_{sid}.csv');meta=js(OUT/f'00_audit/public_inputs/scenario_{sid}.json')
 return ph,tuple(meta['roads']),frame(OUT/f'00_audit/public_inputs/road_audit_{sid}.csv')
def require_new_output(p):
 p=Path(p)
 if p.exists():raise FileExistsError('Refuse overwriting '+str(p))
 p.mkdir(parents=True)
