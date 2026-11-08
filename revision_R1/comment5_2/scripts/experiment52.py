"""Prospectively frozen demand sensitivity; imports the accepted solver read-only.

No surrogate model is imported. No original optimizer or UECache is instantiated.
Every newly solved state starts cold and is stored only in this experiment's DB.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
for k,v in {'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1','NUMBA_CACHE_DIR':str(OUT/'runtime_cache/numba'),'MPLCONFIGDIR':str(OUT/'runtime_cache/matplotlib'),'PYTHONDONTWRITEBYTECODE':'1'}.items():os.environ[k]=v
sys.dont_write_bytecode=True
BASE=Path('E:/jcr2区意见/返稿/4.1专项返修_20261026')
REV=BASE.parent
sys.path.insert(0,str(BASE/'runtime_deps'))
sys.path.insert(0,str(BASE/'code'))
import argparse, csv, hashlib, itertools, json, math, platform, re, sqlite3, subprocess, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import numba, psutil, scipy
from ue_solver import Network, LEGACY_BASELINE, aon, impedance
from path_ue import solve_paths

MAN=json.loads((OUT/'run_manifest.json').read_text(encoding='utf-8'))
TARGET=float(MAN['UE_tolerance']);MAX_OUTER=int(MAN['max_outer'])
PHYS=BASE/'inputs/historical_1001_1010.csv'
NETROOT=BASE/'source_snapshot/code/model_backend'
REFROOT=REV/'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables'
FROZEN=json.loads((OUT/'audit/frozen_paths.json').read_text(encoding='utf-8'))
psutil.Process().cpu_affinity([0])

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 Path(p).parent.mkdir(parents=True,exist_ok=True)
 Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)),encoding='utf-8')
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def write(p,x):
 f=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
 f.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest_obj(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def seqstr(s):return '|'.join(map(str,s))
def masks(seq,roads):
 assert len(seq)==len(roads) and set(seq)==set(roads)
 bits={r:1<<i for i,r in enumerate(roads)};ans=[0];mask=0
 for r in seq:mask|=bits[r];ans.append(mask)
 return ans
def dp(cost,roads):
 m=len(roads);n=1<<m;v=np.full(n,np.inf);v[0]=float(cost[0]);sequences=[None]*n;sequences[0]=()
 parent=np.full(n,-1,int);last=np.full(n,-1,int)
 for mask in range(1,n):
  choices=[]
  for i,r in enumerate(roads):
   if mask&(1<<i):
    pred=mask^(1<<i);val=float(v[pred]+(0. if mask==n-1 else cost[mask]))
    choices.append((val,sequences[pred]+(int(r),),pred,int(r)))
  val,seq,pred,r=min(choices)
  v[mask]=val;sequences[mask]=seq;parent[mask]=pred;last[mask]=r
 return dict(Jstar=float(v[-1]/m),sequence=sequences[-1],V=v,parent=parent,last=last)
def independent_backward_dp(cost,m):
 n=1<<m;v=np.zeros(n)
 for mask in range(n-2,-1,-1):v[mask]=float(cost[mask])+min(float(v[mask|(1<<i)]) for i in range(m) if not(mask&(1<<i)))
 return float(v[0]/m)
def kendall(a,b):
 rank={r:i for i,r in enumerate(b)};inv=sum(rank[a[i]]>rank[a[j]] for i in range(len(a)) for j in range(i+1,len(a)))
 return 1.-2*inv/(len(a)*(len(a)-1)/2)
def addcheck(rows,name,ok,actual,expected,evidence=''):
 rows.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected,evidence=evidence))
def freeze_assert():
 f=js(OUT/'audit/prospective_freeze.json')
 assert sha(OUT/'run_manifest.json')==f['run_manifest_sha256']
 assert sha(OUT/'audit/frozen_paths.json')==f['frozen_paths_sha256']
 assert sha(OUT/'source_sha256.json')==f['sources_sha256_manifest_sha256']

class IsolatedSolver:
 def __init__(self):
  freeze_assert();self.net=Network(NETROOT);self.original_od=self.net.od.copy();self.physical=frame(PHYS)
  self.version=digest_obj({'ue_solver':sha(BASE/'code/ue_solver.py'),'path_ue':sha(BASE/'code/path_ue.py'),'links':sha(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/directed_links.csv'),'OD':sha(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/od_long.csv'),'tol':TARGET,'max_outer':MAX_OUTER})
  self.OD_hash=hashlib.sha256(self.original_od.astype('<f8').tobytes()).hexdigest()
  self.connection=sqlite3.connect(OUT/'cache/demand_isolated_states.sqlite3')
  self.connection.execute('CREATE TABLE IF NOT EXISTS states (cache_key TEXT PRIMARY KEY, context TEXT NOT NULL, payload TEXT NOT NULL, flow BLOB NOT NULL)')
  self.new_solves=0;self.hits=0;self.failures=0
 def physical_for(self,sid):
  if sid==0:
   p=self.physical[self.physical.scenario_id==1001].copy();p['depth_m']=0.;p['is_closed']=0;p['free_flow_time_multiplier']=1.;p['speed_ratio']=1.;p['capacity_factor']=1.
   return p.sort_values('physical_link_id')
  return self.physical[self.physical.scenario_id==sid].sort_values('physical_link_id').copy()
 def context(self,sid,rho,roads,mask):
  p=self.physical_for(sid)
  # Infinity is a valid closed-road sentinel. Hash raw IEEE arrays rather than
  # serializing Infinity as non-standard JSON.
  phys=np.column_stack([p.physical_link_id,p.depth_m,p.is_closed,p.free_flow_time_multiplier,p.capacity_factor]).astype('<f8')
  return dict(scenario_id=int(sid),rho=format(float(rho),'.2f'),UE_tolerance=format(TARGET,'.17g'),solver_sha256=self.version,model_sha256=self.version,physical_state_sha256=hashlib.sha256(phys.tobytes()).hexdigest(),road_bit_order_sha256=digest_obj(list(map(int,roads))),subset_mask=int(mask),OD_sha256=self.OD_hash)
 def key(self,sid,rho,roads,mask):return digest_obj(self.context(sid,rho,roads,mask))
 def get_cached(self,sid,rho,roads,mask):
  key=self.key(sid,rho,roads,mask);row=self.connection.execute('SELECT payload,flow FROM states WHERE cache_key=?',(key,)).fetchone()
  if row is None:return None
  self.hits+=1;return json.loads(row[0]),np.frombuffer(row[1],dtype='<f8').copy()
 def reachability(self,active,od):
  reach=np.eye(24,dtype=bool)
  reach[self.net.tail[active],self.net.head[active]]=True
  for k in range(24):reach|=reach[:,k,None]&reach[k,None,:]
  wanted=od>0
  return int(np.count_nonzero(wanted)),int(np.count_nonzero(wanted&~reach))
 def solve(self,sid,rho,roads,mask):
  found=self.get_cached(sid,rho,roads,mask)
  if found:return found
  p=self.physical_for(sid);active,fft,coef=self.net.state_arrays(p,roads,mask)
  assert np.all(p.loc[p.is_closed==0,'capacity_factor'].to_numpy(float)==1.)
  od=np.ascontiguousarray(self.original_od*float(rho))
  pairs,unreachable=self.reachability(active,od)
  if pairs!=528 or unreachable:raise RuntimeError(f'Unreachable positive OD: {sid} {rho} {mask} {unreachable}')
  started=time.perf_counter();x,tstt,gap,it,ok=solve_paths(self.net.tail,self.net.head,active,self.net.adj,self.net.degree,od,fft,coef,TARGET,MAX_OUTER)
  seconds=time.perf_counter()-started;cost=impedance(x,fft,coef,active)
  independent_tstt=float(np.dot(x[active],cost[active]));_,sp=aon(cost,self.net.tail,self.net.head,active,self.net.adj,self.net.degree,od)
  independent_gap=max(0.,(independent_tstt-float(sp))/max(independent_tstt,1e-100))
  balance=np.bincount(self.net.tail,weights=x,minlength=24)-np.bincount(self.net.head,weights=x,minlength=24)
  error=float(np.max(np.abs(balance-(od.sum(axis=1)-od.sum(axis=0)))))
  valid=bool(ok and np.isfinite(tstt) and np.isfinite(x).all() and np.isfinite(cost[active]).all() and gap<=TARGET and independent_gap<=TARGET*(1+1e-6) and error<=1e-5 and np.min(x)>=-1e-6 and np.max(np.abs(x[~active]),initial=0.)<1e-6 and abs(independent_tstt-tstt)<=max(1.,abs(tstt))*1e-12)
  context=self.context(sid,rho,roads,mask);key=digest_obj(context)
  payload=dict(**context,cache_key=key,Q=float(od.sum()),tstt_raw=float(tstt),tstt_raw_independent=independent_tstt,ue_gap=float(gap),independent_ue_gap=independent_gap,iterations=int(it),converged=bool(ok),reachable_positive_OD_pairs=pairs,unreachable_positive_OD_pairs=unreachable,flow_balance_max_abs=error,solver_seconds=seconds,open_directed_arcs=int(active.sum()),validation_passed=valid,source_version=self.version,solver='accepted_path_column_generation_pairwise',warm_start=False)
  with (OUT/'logs/UE_attempts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(payload,ensure_ascii=False,allow_nan=False)+'\n')
  if not valid:
   self.failures+=1;dump(OUT/'logs/UE_FAILURE.json',payload);raise RuntimeError('UE state failed convergence/finite/reachability/conservation acceptance')
  self.connection.execute('INSERT INTO states VALUES (?,?,?,?)',(key,canonical(context),json.dumps(payload,ensure_ascii=False,allow_nan=False),x.astype('<f8').tobytes()))
  self.connection.commit();self.new_solves+=1
  return payload,x
 def statistics(self):
  records=[json.loads(r[0]) for r in self.connection.execute('SELECT payload FROM states')]
  return dict(unique_valid_states=len(records),dry_states=sum(r['scenario_id']==0 for r in records),scenario_states=sum(r['scenario_id']!=0 for r in records),converged=sum(r['converged'] for r in records),max_RG=max((r['ue_gap'] for r in records),default=0),max_independent_RG=max((r['independent_ue_gap'] for r in records),default=0),max_flow_balance_error=max((r['flow_balance_max_abs'] for r in records),default=0),new_solves_this_process=self.new_solves,cache_hits_this_process=self.hits,failures_this_process=self.failures,solver_seconds=sum(r['solver_seconds'] for r in records))
 def close(self):self.connection.commit();self.connection.close()

def stage_row(solver,sid,rho,roads,seq,method,stage,mask):
 r,x=solver.solve(sid,rho,roads,mask)
 dry=js(OUT/'raw/dry_baselines.json')[format(rho,'.2f')]
 p=solver.physical_for(sid);active,fft,coef=solver.net.state_arrays(p,roads,mask);cost=impedance(x,fft,coef,active)
 tstt=float(r['tstt_raw']);source='new isolated demand UE'
 archived=None;relative_difference=None
 if rho==1.:
  archive=frame(REFROOT/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz').set_index('subset_mask')
  archived=float(archive.loc[mask,'tstt']);relative_difference=abs(tstt-archived)/abs(archived)
  if relative_difference>MAN['validation_thresholds']['archive_same_solver_state_relative_check']:raise RuntimeError(f'Unexplained rho1 state mismatch {sid}/{mask}: {relative_difference}')
  tstt=archived;source='accepted 4.2 archived cost; independent diagnostic flow re-solve separately recorded'
 vc=x[active]/solver.net.cap[active];mult=cost[active]/fft[active];contributions=x[active]*cost[active];indices=np.flatnonzero(active);top=indices[np.argsort(-contributions,kind='stable')[:5]]
 return dict(scenario_id=sid,method=method,rho=rho,stage=stage,subset_mask=mask,restored_physical_links=seqstr(seq[:stage]),objective_weight=0. if stage==10 else .1,Q=r['Q'],tstt_raw=tstt,tstt_veh_h=tstt*.01,att_hours=tstt*.01/r['Q'],att_minutes=tstt*.6/r['Q'],tstt_ratio_to_dry=tstt/dry['tstt_raw'],normalized_excess=tstt/dry['tstt_raw']-1.,dry_TSTT_raw=dry['tstt_raw'],ue_gap=r['ue_gap'],iterations=r['iterations'],converged=r['converged'],reachable_positive_OD_pairs=r['reachable_positive_OD_pairs'],unreachable_positive_OD_pairs=0,max_vc=float(max(vc)),p95_vc=float(np.quantile(vc,.95)),n_vc_gt_1=int(sum(vc>1)),n_vc_gt_2=int(sum(vc>2)),max_bpr_multiplier=float(max(mult)),top_5_links_by_tstt_contribution=json.dumps([dict(arc_id=int(solver.net.links.iloc[i].arc_id),physical_link_id=int(solver.net.pid[i]+1),contribution_veh_h=float(x[i]*cost[i]*.01)) for i in top],separators=(',',':')),diagnostic_tstt_raw=r['tstt_raw'],archived_tstt_raw=archived,archive_diagnostic_relative_difference=relative_difference,flow_balance_max_abs=r['flow_balance_max_abs'],source_version=r['source_version'],metric_source=source,cache_key=r['cache_key'])

def summarize(stages):
 f=pd.DataFrame(stages);rows=[]
 for (sid,method,rho),g in f.groupby(['scenario_id','method','rho'],sort=True):
  g=g.sort_values('stage');assert list(g.stage)==list(range(11));weighted=g[g.stage<10];terminal=g[g.stage==10].iloc[0]
  rows.append(dict(scenario_id=int(sid),method=method,rho=float(rho),Q=float(g.Q.iloc[0]),J_rho=float(weighted.normalized_excess.mean()),mean_stage_TSTT_raw=float(weighted.tstt_raw.mean()),mean_stage_TSTT_veh_h=float(weighted.tstt_veh_h.mean()),mean_stage_ATT_hours=float(weighted.att_hours.mean()),mean_stage_ATT_minutes=float(weighted.att_minutes.mean()),mean_ATT_amplification_vs_dry=float(weighted.tstt_ratio_to_dry.mean()),max_stage_ATT_hours=float(g.att_hours.max()),max_weighted_stage_ATT_hours=float(weighted.att_hours.max()),initial_ATT_hours=float(g[g.stage==0].att_hours.iloc[0]),terminal_ATT_hours=float(terminal.att_hours),terminal_TSTT_veh_h=float(terminal.tstt_veh_h),terminal_TSTT_ratio_to_dry=float(terminal.tstt_ratio_to_dry),terminal_excess_TSTT_veh_h=float(terminal.tstt_veh_h-terminal.dry_TSTT_raw*.01),dry_TSTT_raw=float(terminal.dry_TSTT_raw),included_stages='S0..S9, ten equal objective weights',terminal_objective_weight=0.,sequence=seqstr(next(r['sequence'] for r in FROZEN if r['scenario_id']==sid and r['method']==method)) if method!='exact_DP_demand_specific' else None))
 return pd.DataFrame(rows)

def audit_A():
 freeze_assert();checks=[];solver=IsolatedSolver();net=solver.net
 raw=Path('E:/jcr2区意见/老家/sci-jcr2区交付/第一周工作/SiouxFalls_UE_flood_models/data_src/SiouxFalls_flood_benchmark/raw')
 extra=[raw/'SiouxFalls_net.tntp',raw/'SiouxFalls_trips.tntp',BASE/'code/ue_solver.py',BASE/'code/path_ue.py']
 dump(OUT/'audit/additional_sources_before.json',[dict(path=str(p),sha256=sha(p),size_bytes=p.stat().st_size) for p in extra])
 vals=[]
 for line in (raw/'SiouxFalls_net.tntp').read_text(encoding='utf-8-sig').splitlines():
  if re.match(r'^\s*\d+\s+\d+\s+',line):vals.append(list(map(float,line.rstrip().rstrip(';').split())))
 vals=np.array(vals);L=net.links.sort_values(['from_node','to_node']);rawdf=pd.DataFrame(vals[:,[0,1,2,4,5,6]],columns=['from_node','to_node','capacity','free_flow_time','bpr_alpha','bpr_beta']).sort_values(['from_node','to_node'])
 addcheck(checks,'raw_TNTP_network_matches_processed',np.array_equal(rawdf.to_numpy(),L[['from_node','to_node','capacity','free_flow_time','bpr_alpha','bpr_beta']].to_numpy()),len(vals),76,str(raw/'SiouxFalls_net.tntp'))
 od=np.zeros((24,24));origin=None
 for line in (raw/'SiouxFalls_trips.tntp').read_text(encoding='utf-8-sig').splitlines():
  match=re.search(r'Origin\s+(\d+)',line)
  if match:origin=int(match.group(1))-1
  elif origin is not None:
   for d,q in re.findall(r'(\d+)\s*:\s*([\d.]+)',line):od[origin,int(d)-1]=float(q)
 addcheck(checks,'raw_TNTP_OD_matches_processed',np.array_equal(od,net.od),float(od.sum()),360600.,str(raw/'SiouxFalls_trips.tntp'))
 addcheck(checks,'528_positive_ODs_and_360600_total',np.count_nonzero(od)==528 and od.sum()==360600.,dict(positive_pairs=int(np.count_nonzero(od)),Q=float(od.sum())),dict(positive_pairs=528,Q=360600))
 addcheck(checks,'BPR_parameters_unchanged',np.all(net.links.bpr_alpha==.15) and np.all(net.links.bpr_beta==4),dict(alpha=list(map(float,np.unique(net.links.bpr_alpha))),beta=list(map(float,np.unique(net.links.bpr_beta)))),dict(alpha=[.15],beta=[4.]))
 readme=OUT.parents[1]/'data/network_reference/README_SiouxFalls_source.md';text=readme.read_text(encoding='utf-8')
 addcheck(checks,'archived_primary_time_unit_documentation','0.01 hours' in text and 'approximate hourly flows' in text,dict(time='0.01 hours/raw unit',demand='0.1 of original daily flow; approximate hourly loading',stage_duration='not specified as 1 hour'),True,str(readme))
 # Raw cache implementation inspection, never instantiate its SQLite object.
 oldapi=(BASE/'source_snapshot/code/final_pipeline/interfaces_week3.py').read_text(encoding='utf-8')
 snippet=oldapi[oldapi.index('def get_state_hash'):oldapi.index('def get_state_hash')+550]
 addcheck(checks,'legacy_cache_rho_risk_documented','rho' not in snippet and 'demand' not in snippet,snippet,'No rho or OD in original key; original cache not reused')
 keys=[solver.key(1001,r,FROZEN[0]['roads'],0) for r in [1.,.75,.5]]
 memory=sqlite3.connect(':memory:');memory.execute('CREATE TABLE cache(k TEXT PRIMARY KEY,v TEXT)');memory.execute('INSERT INTO cache VALUES (?,?)',(keys[0],'rho1'))
 nohit=memory.execute('SELECT v FROM cache WHERE k=?',(keys[1],)).fetchone() is None and memory.execute('SELECT v FROM cache WHERE k=?',(keys[2],)).fetchone() is None
 memory.close();basecontext=solver.context(1001,1.,FROZEN[0]['roads'],0)
 mutations=[]
 for field in ['scenario_id','UE_tolerance','model_sha256','physical_state_sha256','road_bit_order_sha256','OD_sha256','subset_mask']:
  c=dict(basecontext);c[field]=str(c[field])+'_different';mutations.append(digest_obj(c))
 addcheck(checks,'demand_cache_no_cross_hit_unit_test',len(set(keys+mutations))==10 and nohit,dict(distinct_keys=len(set(keys+mutations)),cross_rho_misses=nohit),dict(distinct_keys=10,cross_rho_misses=True))
 cache_tests=[]
 for m in range(1,7):
  roads=list(range(1,m+1));cost=np.array([2.+i.bit_count()*.07+(i*17%23)/100 for i in range(1<<m)])
  r=dp(cost,roads);brute=min(sum(cost[k] for k in masks(seq,roads)[:-1])/m for seq in itertools.permutations(roads));alter=cost.copy();alter[-1]=1e12;shift=cost.copy();shift[0]+=.375
  for name,a,b in [('brute_vs_DP',r['Jstar'],brute),('terminal_zero_weight',r['Jstar'],dp(alter,roads)['Jstar']),('empty_shift',dp(shift,roads)['Jstar']-r['Jstar'],.375/m)]:
   cache_tests.append(dict(m=m,test=name,actual=a,expected=b,abs_difference=abs(a-b),pass_check=abs(a-b)<=1e-12))
 write(OUT/'tests/objective_and_DP_tests.csv',cache_tests)
 addcheck(checks,'weighted_m_states_terminal_zero_tests',all(r['pass_check'] for r in cache_tests),len(cache_tests),18)
 reach=[]
 for sid in range(1001,1011):
  roads=next(r['roads'] for r in FROZEN if r['scenario_id']==sid);active,_,_=net.state_arrays(solver.physical_for(sid),roads,0);n,u=solver.reachability(active,od)
  reach.append(dict(scenario_id=sid,subset_mask=0,positive_OD_pairs=n,unreachable=u,all_later_subsets_reachable_by_edge_addition=u==0))
 write(OUT/'audit/all10_initial_reachability.csv',reach)
 addcheck(checks,'all10_start_states_reachable',all(r['unreachable']==0 and r['positive_OD_pairs']==528 for r in reach),reach,'all 528 positive ODs reachable; restoration only adds directed arcs')
 dry={}
 for rho in [1.,.75,.5]:
  print(f'A dry UE rho={rho:.2f}',flush=True);r,x=solver.solve(0,rho,[],0)
  dry[format(rho,'.2f')]=dict(**r,tstt_veh_h=r['tstt_raw']*.01,att_hours=r['tstt_raw']*.01/r['Q'],att_minutes=r['tstt_raw']*.6/r['Q'])
 dump(OUT/'raw/dry_baselines.json',dry);write(OUT/'raw/dry_baselines.csv',list(dry.values()))
 baseline=dry['1.00'];relative=abs(baseline['tstt_raw']-LEGACY_BASELINE)/LEGACY_BASELINE
 addcheck(checks,'dry_rho1_unit_anchor',relative<=MAN['validation_thresholds']['archive_same_solver_state_relative_check'],dict(tstt_raw=baseline['tstt_raw'],tstt_veh_h=baseline['tstt_veh_h'],ATT_minutes=baseline['att_minutes'],reference_raw=LEGACY_BASELINE,relative_difference=relative),dict(reference_veh_h=74802.2534492112,approx_ATT_minutes=12.4463,relative_tolerance=2.816128890834728e-7))
 addcheck(checks,'separate_dry_normalizers',len(set(r['tstt_raw'] for r in dry.values()))==3,{k:v['tstt_raw'] for k,v in dry.items()},'three independently solved dry baselines')
 solutions=[]
 old=js(REV/'reviewer_4_2/00_protocol_and_input_audit/source_records/archive/exact_dp_solution.json')['scenarios']
 oldstates=frame(REFROOT/'original_FW_5e4_10240_states.csv')
 for sid in range(1001,1011):
  roads=old[str(sid)]['candidate_roads'];hi=frame(REFROOT/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz').sort_values('subset_mask');lo=oldstates[oldstates.scenario_id==sid].sort_values('subset_mask')
  assert list(hi.subset_mask)==list(range(1024)) and list(lo.subset_mask)==list(range(1024))
  h=dp(hi.tstt.to_numpy()/LEGACY_BASELINE-1,roads);l=dp(lo.tstt.to_numpy()/LEGACY_BASELINE-1,roads)
  saved=js(BASE/f'development/legacy_precision/scenario_{sid}/exact_solution.json')
  ht=abs(h['Jstar']-saved['new_table_objective']);lt=abs(l['Jstar']-old[str(sid)]['exact_objective'])
  solutions.append(dict(scenario_id=sid,roads=seqstr(roads),original_Jstar=l['Jstar'],accepted_4_2_Jstar=h['Jstar'],old_UE_tolerance=.0005,new_UE_tolerance=TARGET,original_DP_sequence=seqstr(l['sequence']),accepted_4_2_DP_sequence=seqstr(h['sequence']),same_reference_sequence=tuple(h['sequence'])==tuple(l['sequence']),max_archived_RG=float(hi.relative_gap.max()),accepted_rows=len(hi),old_abs_reconciliation=lt,new_abs_reconciliation=ht,source_sha256=sha(REFROOT/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz')))
  addcheck(checks,f'original_and_accepted_DP_{sid}',lt<=1e-12*max(1.,abs(l['Jstar'])) and ht<=1e-12*max(1.,abs(h['Jstar'])) and hi.converged.all() and hi.relative_gap.max()<=TARGET,dict(old_diff=lt,new_diff=ht,rows=len(hi)),dict(relative_tolerance=1e-12,rows=1024))
 write(OUT/'audit/rho1_original_and_accepted_DP_reconciliation.csv',solutions)
 env=dict(python_executable=sys.executable,python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,numba=numba.__version__,scipy=scipy.__version__,CPU_affinity=psutil.Process().cpu_affinity(),frozen_solver_version=solver.version,NUMBA_CACHE_DIR=os.environ['NUMBA_CACHE_DIR'],threads=1)
 dump(OUT/'audit/environment_UE.json',env)
 validation=dict(stage='A',status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',checks_passed=sum(c['status']=='PASS' for c in checks),checks_total=len(checks),checks=checks,Greedy_original_paths='NOT_AVAILABLE_FOR_1001_1010',dry_baselines=dry,old_cache_opened=False,solver_statistics=solver.statistics())
 dump(OUT/'unit_validation.json',validation)
 report=f'''# Sioux Falls单位、数据与缓存审计

阶段A结论：{validation['status']}，{validation['checks_passed']}/{validation['checks_total']}。

## 源数据和单位

原TNTP网络的76条弧、BPR alpha=0.15/beta=4、自由流时间和容量与已验收processed CSV逐值一致；原TNTP的24×24 OD与CSV逐值一致。528个正OD，总量360600。源README明确时间为0.01 hour/unit，OD为原日需求的0.1，可视为近似小时加载量；并非实测时段交通量，不能把恢复阶段自动等同于1小时。容量与OD在同一基准加载时段下共同解释，保持原网络参数不变，未把容量再乘100或把时间重复换算。

求解器tstt为sum(flow×TNTP time)，换算veh·h仅乘0.01；ATT=tstt×0.01/Q，分钟再乘60。rho=1新干燥基准为{baseline['tstt_raw']:.15g} raw、{baseline['tstt_veh_h']:.15g} veh·h、ATT={baseline['att_minutes']:.12g} min，与原基准的相对差为{relative:.12g}，保留真实偏差。

## 版本与缓存

使用4.2已经验收的path-column solver，RG≤1e-9、最多20000 outer，冷启动，原函数不改。原FW表RG≤5e-4与新表分开对账，不以新值覆盖旧表；原始成本和新4.2成本的数值差异包括求解器实现变化。未读取旧SQLite缓存，也未实例化旧UEInterface。

旧哈希缺rho和需求；新缓存复合上下文含scenario、rho、tolerance、求解器/模型SHA、物理状态、道路bit顺序、mask、OD SHA。内存缓存测试确认不同rho不会交叉命中，干燥网络也逐rho独立求解。所有新SQLite/Numba缓存仅在本实验输出目录。

## 连通、状态与方案

十个初始场景的528正OD均有有向路径，恢复操作只增加开放弧；每个实际求解状态仍再次做有向可达检查。目标只含S0—S9，S10显示但权重0；单元测试覆盖m1—6穷举、终态哨兵及初态Δ/m。

保留原full_method和rho1 exact_DP路径。4.1 Greedy正式结果属于3001—3030，未找到1001—1010同情景的已验收Greedy路径，故不借用或重新跑优化填补。

代表场景按原始Jstar排序的第1、5、10名固定为{MAN['representative_scenarios']}。当前只完成A，不将后续实验写为完成。原文件保护见source_sha256.json。
'''
 (OUT/'unit_audit.md').write_text(report,encoding='utf-8');solver.close()
 print(json.dumps(dict(phase='A',status=validation['status'],checks_passed=validation['checks_passed'],checks_total=validation['checks_total'],baseline=baseline['tstt_veh_h'],ATT_minutes=baseline['att_minutes'],relative_difference=relative),ensure_ascii=False),flush=True)
 if validation['status']!='PASS':raise RuntimeError('Phase A gate failed; B/C/D not allowed')

def phases_BC(phase):
 assert js(OUT/'unit_validation.json')['status']=='PASS'
 solver=IsolatedSolver();rhos=[1.] if phase=='B' else [1.,.75,.5];rows=[]
 for rho in rhos:
  for p in FROZEN:
   sid=p['scenario_id'];roads=p['roads'];seq=p['sequence']
   print(f'{phase} rho={rho:.2f} scenario={sid} method={p["method"]}',flush=True)
   for stage,mask in enumerate(masks(seq,roads)):rows.append(stage_row(solver,sid,rho,roads,seq,p['method'],stage,mask))
  write(OUT/f'raw/{phase}_stage_metrics_checkpoint.csv',rows)
 write(OUT/('raw/original_rho1_stage_metrics.csv' if phase=='B' else 'stage_metrics_all10.csv'),rows)
 summary=summarize(rows);write(OUT/('raw/original_rho1_summary.csv' if phase=='B' else 'demand_sensitivity_all10.csv'),summary)
 stats=solver.statistics();dump(OUT/f'audit/{phase}_execution.json',dict(status='PASS',rows=len(rows),paths=len(summary),statistics=stats));solver.close()
 print(json.dumps(dict(phase=phase,status='PASS',stage_rows=len(rows),path_rows=len(summary),statistics=stats),ensure_ascii=False),flush=True)

def phase_D():
 assert js(OUT/'audit/C_execution.json')['status']=='PASS'
 solver=IsolatedSolver();allrows=[];policies=[];extra_stages=[];drys=js(OUT/'raw/dry_baselines.json')
 for sid in MAN['representative_scenarios']:
  paths=[p for p in FROZEN if p['scenario_id']==sid];roads=paths[0]['roads'];origDP=next(p['sequence'] for p in paths if p['method']=='exact_DP_original_rho1')
  for rho in [.75,.5]:
   print(f'D full table scenario={sid} rho={rho:.2f}',flush=True);states=[];cost=[]
   t0=drys[format(rho,'.2f')]['tstt_raw']
   for mask in range(1024):
    row,x=solver.solve(sid,rho,roads,mask);cost.append(row['tstt_raw']/t0-1.)
    states.append(dict(scenario_id=sid,rho=rho,subset_mask=mask,restored_count=mask.bit_count(),restored_physical_links=seqstr([r for i,r in enumerate(roads) if mask&(1<<i)]),**{k:row[k] for k in ['cache_key','Q','tstt_raw','ue_gap','independent_ue_gap','iterations','converged','reachable_positive_OD_pairs','unreachable_positive_OD_pairs','flow_balance_max_abs','source_version']},tstt_veh_h=row['tstt_raw']*.01,att_hours=row['tstt_raw']*.01/row['Q'],dry_TSTT_raw=t0,C_rho=cost[-1],terminal_objective_weight=0 if mask==1023 else 1))
    if (mask+1)%128==0:print(f'  {mask+1}/1024; new UE process={solver.new_solves}',flush=True)
   solution=dp(cost,roads);star=solution['Jstar'];independent=independent_backward_dp(cost,10)
   assert abs(star-independent)<=1e-12*max(1.,abs(star))
   for r in states:
    mask=r['subset_mask'];r.update(dp_V=float(solution['V'][mask]),dp_predecessor_mask=int(solution['parent'][mask]),dp_last_road=int(solution['last'][mask]))
   write(OUT/f'raw/scenario_{sid}_rho_{rho:.2f}_1024_states.csv',states)
   dump(OUT/f'raw/scenario_{sid}_rho_{rho:.2f}_DP.json',dict(scenario_id=sid,rho=rho,Jstar=star,independent_backward_Jstar=independent,sequence=solution['sequence'],roads=roads,tie_rule='Strict floating minimum, then lexicographic complete physical-road sequence',all_masks=1024,new_UE_table_max_unique_budget=1024,terminal_weight=0,source='new isolated full table plus same-rho previously solved states',first3_changed_vs_original_DP=tuple(solution['sequence'][:3])!=tuple(origDP[:3]),kendall_tau_vs_original_DP=kendall(solution['sequence'],origDP)))
   allrows.extend(states)
   newpath=dict(scenario_id=sid,method='exact_DP_demand_specific',roads=roads,sequence=solution['sequence'])
   for p in paths+[newpath]:
    seq=p['sequence'];ms=masks(seq,roads);value=sum(cost[m] for m in ms[:-1])/10;delta=value-star
    policies.append(dict(scenario_id=sid,rho=rho,method=p['method'],sequence=seqstr(seq),demand_specific_DP_sequence=seqstr(solution['sequence']),original_DP_rho1_sequence=seqstr(origDP),J_method=value,Jstar_rho=star,delta_J=delta,regret_pct=100*delta/star,delta_mean_stage_TSTT_veh_h=delta*t0*.01,delta_mean_trip_minutes=delta*t0*.6/(rho*360600),mean_stage_TSTT_veh_h=(value+1)*t0*.01,mean_stage_ATT_hours=(value+1)*t0*.01/(rho*360600),first3_changed_vs_new_DP=tuple(seq[:3])!=tuple(solution['sequence'][:3]),kendall_tau_vs_new_DP=kendall(seq,solution['sequence']),new_DP_first3_changed_vs_original_DP=tuple(solution['sequence'][:3])!=tuple(origDP[:3]),new_DP_kendall_tau_vs_original_DP=kendall(solution['sequence'],origDP),dry_TSTT_raw=t0,Q=rho*360600,sensitivity_type='post-hoc fixed-path transfer and demand-conditional DP',surrogate_reoptimized=False))
   for stage,mask in enumerate(masks(newpath['sequence'],roads)):extra_stages.append(stage_row(solver,sid,rho,roads,newpath['sequence'],newpath['method'],stage,mask))
   write(OUT/'demand_dp_six_tables.csv',allrows);write(OUT/'demand_dp_policy_comparison.csv',policies);write(OUT/'raw/demand_specific_DP_stage_metrics.csv',extra_stages)
 stats=solver.statistics();dump(OUT/'audit/D_execution.json',dict(status='PASS',tables=len(MAN['representative_scenarios'])*2,states=len(allrows),policies=len(policies),statistics=stats));solver.close()
 print(json.dumps(dict(phase='D',status='PASS',tables=6,states=len(allrows),policy_rows=len(policies),statistics=stats),ensure_ascii=False),flush=True)

def bottlenecks():
 solver=IsolatedSolver();stage=frame(OUT/'stage_metrics_all10.csv');extra=frame(OUT/'raw/demand_specific_DP_stage_metrics.csv');allstage=pd.concat([stage,extra],ignore_index=True)
 selected=allstage[allstage.scenario_id.isin(MAN['representative_scenarios']) & allstage.stage.isin(MAN['diagnostic_stages'])]
 rows=[]
 for r in selected.itertuples(index=False):
  roads=next(p['roads'] for p in FROZEN if p['scenario_id']==r.scenario_id)
  cached=solver.get_cached(r.scenario_id,r.rho,roads,r.subset_mask)
  if cached is None:raise RuntimeError('Flow missing from new diagnostic cache; no hidden new solve allowed')
  payload,x=cached;active,fft,coef=solver.net.state_arrays(solver.physical_for(r.scenario_id),roads,r.subset_mask);cost=impedance(x,fft,coef,active)
  for i in np.flatnonzero(active):
   link=solver.net.links.iloc[i]
   rows.append(dict(scenario_id=int(r.scenario_id),rho=float(r.rho),method=r.method,stage=int(r.stage),subset_mask=int(r.subset_mask),arc_id=int(link.arc_id),physical_link_id=int(link.physical_link_id),from_node=int(link.from_node),to_node=int(link.to_node),flow=float(x[i]),capacity=float(solver.net.cap[i]),vc=float(x[i]/solver.net.cap[i]),free_flow_time_raw=float(fft[i]),free_flow_minutes=float(fft[i]*.6),congested_time_raw=float(cost[i]),congested_minutes=float(cost[i]*.6),bpr_multiplier=float(cost[i]/fft[i]),flow_times_congested_time_raw=float(x[i]*cost[i]),TSTT_contribution_veh_h=float(x[i]*cost[i]*.01),TSTT_share=float(x[i]*cost[i]/payload['tstt_raw']),open_arc=True,cache_key=payload['cache_key'],source_version=payload['source_version']))
 write(OUT/'bottleneck_links.csv',rows);write(OUT/'raw/representative_diagnostic_stage_metrics.csv',selected)
 records=[json.loads(r[0]) for r in solver.connection.execute('SELECT payload FROM states')]
 write(OUT/'raw/all_new_UE_state_metadata.csv',records)
 dump(OUT/'audit/final_solver_statistics.json',solver.statistics());solver.close()
 print(json.dumps(dict(phase='bottlenecks',open_arc_rows=len(rows),diagnostic_states_with_method_labels=len(selected)),ensure_ascii=False),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['A','B','C','D','bottlenecks','all'],required=True);args=ap.parse_args()
 todo=['A','B','C','D','bottlenecks'] if args.phase=='all' else [args.phase]
 for stage in todo:
  if stage=='A':audit_A()
  elif stage in ['B','C']:phases_BC(stage)
  elif stage=='D':phase_D()
  else:bottlenecks()
if __name__=='__main__':main()
