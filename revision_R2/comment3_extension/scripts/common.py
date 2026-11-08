from pathlib import Path
import os,sys,json,hashlib,datetime,subprocess
OUT=Path(__file__).resolve().parents[1];REPO=OUT.parents[1]
REV=Path('E:/jcr2区意见/返稿');BASE=REV/'4.1专项返修_20261026'
ARCHIVE_ROOT=Path('E:/jcr2区意见/老家/sci-jcr2区交付/第四周工作')
GEN=ARCHIVE_ROOT/'day1_final_untouched_scenarios_v1.0/frozen_inputs/generate_final_holdout.py'
NETROOT=BASE/'source_snapshot/code/model_backend'
PHYS=BASE/'inputs/historical_1001_1010.csv'
PRE=ARCHIVE_ROOT/'day2_candidate_screening_v1.0/frozen_inputs/v2_surrogate/preprocessor_v2.json'
DATA=REPO/'data/final_holdout_scenarios'
SEL=ARCHIVE_ROOT/'day2_candidate_screening_v1.0/01_road_selection'
R42=REV/'reviewer_4_2';TABLES=R42/'01_legacy_ue_state_comparison/source_state_tables'
T0=7480225.3449211195;Q=360600.;TARGET=1e-9;MAX_OUTER=20000
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib'),'PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[k]=v
sys.dont_write_bytecode=True
sys.path.insert(0,str(BASE/'runtime_deps'));sys.path.insert(0,str(BASE/'code'));sys.path.insert(0,str(NETROOT))
import numpy as np,pandas as pd
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def dump(p,x):
 Path(p).parent.mkdir(parents=True,exist_ok=True)
 Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def read(p):return pd.read_csv(p,float_precision='round_trip')
def save(p,x):
 f=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);Path(p).parent.mkdir(parents=True,exist_ok=True);f.to_csv(p,index=False,float_format='%.17g');return f
def gitstate():return {k:subprocess.check_output(['git','-C',str(REPO)]+args,text=True).strip() for k,args in [('HEAD',['rev-parse','HEAD']),('branch',['branch','--show-current'])]}
def init():
 for d in ['audit','cache','raw','figures','logs','tests','runtime_cache']: (OUT/d).mkdir(parents=True,exist_ok=True)
def originals():return {int(s['scenario_id']):s['selected_recoverable_roads'] for s in js(SEL/'final_scenarios.json')['scenarios']}
def pmask(roads):return sum(1<<(int(r)-1) for r in roads)
def physicalmask(roads,mask):return pmask([r for i,r in enumerate(roads) if mask&(1<<i)])
def oldtable(sid):return read(TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz')
def selection(p):
 pre=js(PRE);f=p[p.is_closed.eq(1)].copy();n=len(f)
 if n<10:return []
 f['flow']=np.asarray(pre['baseline_flow'])[f.physical_link_id.to_numpy(int)-1];f['between']=np.asarray(pre['betweenness'])[f.physical_link_id.to_numpy(int)-1]
 f['score']=.5*((n-f.flow.rank(method='min',ascending=False))/(n-1)+(n-f.between.rank(method='min',ascending=False))/(n-1))
 return f.sort_values(['score','flow','between','physical_link_id'],ascending=[False,False,False,True],kind='mergesort').head(10).physical_link_id.astype(int).tolist()
def reachability(p):
 links=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/directed_links.csv');od=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/od_long.csv');active=~p.is_closed.to_numpy(bool)[links.physical_link_id.to_numpy(int)-1]
 u=links.from_node.to_numpy(int)-1;v=links.to_node.to_numpy(int)-1;reach=np.eye(24,dtype=bool);reach[u[active],v[active]]=True
 for k in range(24):reach|=reach[:,k,None]&reach[k,None,:]
 positive=od[od.demand>0];bad=positive.loc[~reach[positive.origin.to_numpy(int)-1,positive.destination.to_numpy(int)-1]]
 weak=reach|reach.T
 for k in range(24):weak|=weak[:,k,None]&weak[k,None,:]
 return dict(OD_reachable=len(bad)==0,reachable_OD=528-len(bad),unreachable_OD=len(bad),physical_connected=bool(weak.all())),bad
def state_arrays(p,roads,mask,net):return net.state_arrays(p,roads,mask)
def state_context(p,roads,mask,net):
 active,fft,coef=state_arrays(p,roads,mask,net)
 # Effective physical traffic state is the dedup key. Provenance (draw/factor/depth/
 # restoration set) is stored separately in every logical-state mapping row.
 key=digest(dict(active=active.astype(int).tolist(),fft=fft.tolist(),coef=coef.tolist(),capacity=net.cap.tolist(),OD_sha256=hashlib.sha256(net.od.astype('<f8').tobytes()).hexdigest(),BPR_alpha=.15,beta=4,solver_sha=sha(BASE/'code/path_ue.py'),network_solver_sha=sha(BASE/'code/ue_solver.py'),RG=TARGET,max_outer=MAX_OUTER,dry_denominator=T0))
 return key,active,fft,coef
def forward_dp(c,roads):
 n=1<<len(roads);V=np.full(n,np.inf);V[0]=0.;paths=[()]*n;prev=np.full(n,-1,int)
 for s in range(1,n):
  choices=[(float(V[s^(1<<i)]+c[s^(1<<i)]),paths[s^(1<<i)]+(int(r),),s^(1<<i)) for i,r in enumerate(roads) if s&(1<<i)]
  value,path,parent=min(choices,key=lambda x:(x[0],x[1]));V[s]=value;paths[s]=path;prev[s]=parent
 return float(V[-1]/len(roads)),list(paths[-1]),V,prev
def pathvalue(seq,roads,c):
 b={r:1<<i for i,r in enumerate(roads)};s=0;val=0.
 for r in seq:val+=float(c[s]);s|=b[r]
 return val/len(roads)

PARENT=REPO/'revision_R2/comment3'
ATT0=.6*T0/Q
