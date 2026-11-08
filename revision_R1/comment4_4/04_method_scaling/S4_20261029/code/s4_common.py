from pathlib import Path
import sys,os,time,json,hashlib,math,csv as csvmod,traceback
SCALE=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(SCALE/'code'))
from common44 import *
OUT=Path(__file__).resolve().parents[1]
os.environ['NUMBA_CACHE_DIR']=str(OUT/'runtime_cache/numba')
os.environ['MPLCONFIGDIR']=str(OUT/'runtime_cache/matplotlib')
from search_adapter44 import install
from components44 import build
A=install()
CFG=js(ROOT/'protocol/frozen_protocol.json')
KAPPA=CFG['equivalence']['equivalence_kappa']
FOUR=[0,2,4,6]
for d in ['00_lock','optimization','enum_serial','enum_4core','analysis','manuscript','logs']:(OUT/d).mkdir(parents=True,exist_ok=True)
class TaskLimit(BaseException):pass
def protocol():return js(OUT/'00_lock/S4_frozen_protocol.json')
def verify_s4():
 verify()
 for p,h in js(OUT/'00_lock/S4_source_manifest.json')['sha256'].items():assert sha(p)==h,'Frozen S4 source changed '+p
 return True
def warm(net):
 ph=frame(ROOT/'inputs/historical_201_260.csv');ph=ph[ph.scenario_id==246].sort_values('physical_link_id');roads,_=select_roads(ph,10)
 r=net.solve(ph,roads,0,1e-9);assert r['relative_gap']<=1e-9
 return ph,roads
def seq_string(s):return '|'.join(map(str,s)) if s is not None else ''
def epsilon(j):return KAPPA*max(1.,abs(float(j)))
class TimedNetwork(frozen.Network):
 def __init__(self,folder,deadline=None):
  super().__init__(frozen.MODEL);self.folder=Path(folder);self.deadline=deadline;self.wall=0.;self.calls=0;self.attempts=0
  self.handle=(self.folder/'physical_UE_journal.csv').open('w',encoding='utf-8',newline='',buffering=1)
  self.writer=None
 def solve(self,*args,**kwargs):
  if self.deadline and time.perf_counter()>self.deadline:raise TaskLimit('TASK_TIME_LIMIT')
  t=time.perf_counter();self.attempts+=1
  try:r=super().solve(*args,**kwargs)
  except BaseException as e:
   self.wall+=time.perf_counter()-t
   dump(self.folder/'UE_failure.json',{'mask':int(args[2]),'error':str(e),'attempt':self.attempts,'time':now()});raise
  self.wall+=time.perf_counter()-t;self.calls+=1
  if self.writer is None:self.writer=csvmod.DictWriter(self.handle,fieldnames=list(r));self.writer.writeheader()
  self.writer.writerow(r)
  if not r['converged'] or r['relative_gap']>1e-9:raise RuntimeError('UE_RG_GATE_FAILURE')
  if self.deadline and time.perf_counter()>self.deadline:raise TaskLimit('TASK_TIME_LIMIT_AFTER_UE')
  return r
 def close(self):self.handle.close()
def exact_dp(costs,roads):
 # Full-sequence lexicographic tie break at identical floating sums, independently implemented.
 n=len(roads);full=(1<<n)-1;dp=[0.]*(full+1);seq=[()]*(full+1);dp[0]=float(costs[0])
 for mask in range(1,full+1):
  best=None
  for i,r in enumerate(roads):
   if mask&(1<<i):
    prev=mask^(1<<i);candidate=(dp[prev],seq[prev]+(int(r),))
    if best is None or candidate<best:best=candidate
  dp[mask]=best[0]+(0. if mask==full else float(costs[mask]));seq[mask]=best[1]
 return dp[full]/n,seq[full]
