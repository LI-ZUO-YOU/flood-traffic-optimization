"""Read frozen CSV/JSON bytes only. No optimization/UE/model code is imported."""
from pathlib import Path
import io,json,hashlib,zipfile,datetime
import numpy as np
import pandas as pd
PLAN=Path(r'C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer1_4.6_尾部稳健性与分层不确定性_Codex执行方案.md')
BASE41=Path(r'E:/jcr2区意见/返稿/4.1专项返修_20261026/正式模拟_v2')
BASE42=Path(r'E:/jcr2区意见/返稿/reviewer_4_2')
STOCH=['proposed','sa_original','sa_restart','greedy_ils','random_ls']
DETERM=['greedy_ls','ue_beam','ue_bibeam']
METHODS=STOCH+DETERM
COMPARATORS=['sa_original','sa_restart','greedy_ils','ue_bibeam']
LABEL={'proposed':'Proposed','sa_original':'SA-original','sa_restart':'SA-restart','greedy_ils':'UE-Greedy-ILS','random_ls':'Random-start + shared LS','greedy_ls':'UE-Greedy-LS','ue_beam':'UE-Beam','ue_bibeam':'UE-BiBeam'}
LEGACY_METHODS=['Proposed_B256','SA_original_fixed_seed']
PRECISIONS=['old_FW_5e-4','new_path_1e-9']
REQUIRED41=['all_run_results.csv','scenario_seed_summaries.csv','Table_R2_method_summary.csv','Table_R3_primary_paired_comparisons.csv','scenario_paired_differences.csv']
REQUIRED42=['S2_original_paths_revalued.csv','S2_old10_regret_summary.csv']

def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda a:a.item() if isinstance(a,np.generic) else str(a)),encoding='utf-8')
def csv(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);d=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
 d.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def frame(p):return pd.read_csv(p,encoding='utf-8-sig',float_precision='round_trip',low_memory=False)
def read_asset(source,basename):
 p=Path(source)
 if p.is_file():
  assert zipfile.is_zipfile(p),f'Not a ZIP archive: {p}'
  with zipfile.ZipFile(p) as z:
   candidates=[n for n in z.namelist() if Path(n).name==basename and not n.endswith('/')]
   assert len(candidates)==1,('Ambiguous/missing ZIP member',p,basename,candidates)
   member=candidates[0];b=z.read(member)
 else:
  assert p.is_dir(),f'Missing source: {p}'
  candidates=[f for f in p.rglob(basename) if f.is_file()];assert len(candidates)==1,(p,basename,candidates)
  f=candidates[0];member=f.relative_to(p).as_posix();b=f.read_bytes()
 return b,member,pd.read_csv(io.BytesIO(b),encoding='utf-8-sig',float_precision='round_trip',low_memory=False)
def sources(out):
 spec=js(Path(out)/'00_audit/analysis_protocol.json');return Path(spec['source41']),Path(spec['source42'])
def tables(out):
 a,b=sources(out)
 return {n:read_asset(a,n)[2] for n in REQUIRED41}|{n:read_asset(b,n)[2] for n in REQUIRED42}
def require_gate(out,stage):assert js(Path(out)/'00_audit'/f'{stage}_gate.json')['status']=='PASS',f'{stage} gate not passed'
def check_immutable(out):
 for row in frame(Path(out)/'00_audit/source_manifest.csv').to_dict('records'):
  p=Path(row['source_path'])
  if isinstance(row['zip_member'],str) and row['zip_member']:
   if p.is_file():
    with zipfile.ZipFile(p) as z:h=sha_bytes(z.read(row['zip_member']))
   else:h=sha(p/row['zip_member'])
  else:h=sha(p)
  assert h==row['SHA256'],f'Source changed: {p} {row["zip_member"]}'

def scenario_quantile(values,*,unit):
 if unit!='scenario':raise ValueError('P90 requires scenario-level units; run-level rows are not independent flood samples')
 a=np.asarray(values,float);assert a.ndim==1 and np.isfinite(a).all() and len(a)>1
 if len(a) not in [9,10,29,30]:raise ValueError('Unexpected scenario count; flat300-run quantiles are prohibited')
 return float(np.quantile(a,.9,method='linear'))
def q(values,p):return float(np.quantile(np.asarray(values,float),p,method='linear'))
def order90(values):
 a=np.sort(np.asarray(values,float));h=(len(a)-1)*.9;lo=int(np.floor(h));hi=int(np.ceil(h));w=h-lo
 return {'n':len(a),'lower_rank_1based':lo+1,'upper_rank_1based':hi+1,'lower_weight':1-w,'upper_weight':w,'lower_value':float(a[lo]),'upper_value':float(a[hi]),'P90_manual':float((1-w)*a[lo]+w*a[hi])}
