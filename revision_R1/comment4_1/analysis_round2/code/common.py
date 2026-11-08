from __future__ import annotations
import os,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parent
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.environ['NUMBA_CACHE_DIR']=str(OUT/'runtime_cache/numba')
os.environ['MPLCONFIGDIR']=str(OUT/'runtime_cache/matplotlib')
sys.path.insert(0,str(ROOT/'code'))
import experiment as ex
import numpy as np,pandas as pd
import json,hashlib,time,datetime,sqlite3

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cfg():return json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
def frame(p,**kw):return pd.read_csv(p,float_precision='round_trip',**kw)
def state_rows(sid):
    # Read-only connection preserves original state values bit for bit.
    db=ROOT/f'runs/shared_physical_cache/scenario_{sid}.sqlite'
    con=sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True)
    try:rows={int(k):json.loads(v) for k,v in con.execute('SELECT mask,payload FROM states')}
    finally:con.close()
    assert set(rows)==set(range(1024))
    tab=frame(ROOT/f'exact/scenario_{sid}/all_1024_states.csv.gz')
    for r in tab.itertuples(index=False):assert float(r.loss).hex()==float(rows[int(r.subset_mask)]['loss']).hex()
    return rows
class TableStore:
    def __init__(self,rows):self.data=rows
    def request(self,mask):return dict(self.data[int(mask)]),True
def data(sid):
    ph=pd.read_csv(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv')
    ph=ph[ph.scenario_id==sid].sort_values('physical_link_id')
    roads,audit=ex.select_roads(ph)
    sol=json.loads((ROOT/f'exact/scenario_{sid}/exact_solution.json').read_text(encoding='utf-8'))
    assert list(roads)==sol['roads']
    return ph,roads,audit,sol
def objective(seq,roads,costs):return float(np.mean([costs[m] for m in ex.masks(seq,roads)]))
def regret(j,star):return max(0.,100*(j-star)/star)
def verify_manifest():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in m['original_files_sha256'].items():assert sha(ROOT/name)==h,'Original file changed: '+name
    return m

