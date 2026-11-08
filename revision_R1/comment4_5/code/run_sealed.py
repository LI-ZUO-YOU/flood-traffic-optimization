"""Single-task parent broker. Full tables are never sent to a search subprocess."""
from common45 import *
import argparse,subprocess,sqlite3

def load_table(sid):
 if sid in [246,247,249]:
  db=ROOT/f'development/highprecision_{sid}.sqlite'
  with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:rows={int(m):json.loads(s) for m,s in c.execute('SELECT mask,payload FROM states')}
 else:rows={int(r['subset_mask']):r for r in frame(ROOT/f'exact/scenario_{sid}/all_1024_states.csv.gz').to_dict('records')}
 assert set(rows)==set(range(1024))
 return rows

def execute(sid,variant,rep,path):
 if path.exists():raise FileExistsError(path)
 pin();table=load_table(sid);known=set();audit=[];started=time.perf_counter()
 errpath=path.parent/(path.name+'_worker_stderr.log');errpath.parent.mkdir(parents=True,exist_ok=True)
 with errpath.open('w',encoding='utf-8') as err:
  proc=subprocess.Popen([sys.executable,str(OUT/'code/sealed_worker.py'),'--scenario',str(sid),'--variant',variant,'--seed',str(rep),'--output',str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',env=os.environ.copy())
  try:
   for line in proc.stdout:
    msg=json.loads(line)
    if msg.get('op')=='request':
     m=msg['mask'];assert isinstance(m,int) and 0<=m<1024
     if m not in known and len(known)>=256:reply={'error':'broker unique-state cap'}
     else:
      known.add(m);row=dict(table[m]);row['historical_solver_seconds']=row.get('solver_seconds');row['solver_seconds']=0.0;reply={'row':row}
     audit.append({'request_index':len(audit)+1,'mask':m,'unique_released':len(known),'elapsed':time.perf_counter()-started})
     proc.stdin.write(json.dumps(reply,ensure_ascii=False,allow_nan=False)+'\n');proc.stdin.flush()
    elif msg.get('op')!='complete':raise RuntimeError('Invalid worker protocol')
   rc=proc.wait()
  except BaseException:
   proc.kill();proc.wait();raise
 csv(path/'broker_access.csv.gz',audit)
 dump(path/'broker_validation.json',{'status':'PASS' if rc==0 else 'FAIL','returncode':rc,'released_unique_states':len(known),'full_table_location':'parent only','worker_scalar_request_count':len(audit),'live_UE_calls':0,'at':now()})
 if rc:raise RuntimeError(f'Worker failed; see {path}/validation.json and {errpath}')
 return js(path/'result.json')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scenarios',type=int,nargs='+',required=True);p.add_argument('--variants',nargs='+',default=['all']);p.add_argument('--seeds',type=int,nargs='+',default=[0]);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 variants=VARIANTS if a.variants==['all'] else a.variants
 assert set(variants)<=set(VARIANTS)
 for sid in a.scenarios:
  assert sid in [246,247,249] or 3001<=sid<=3030, 'First-batch sealed data only'
  for variant in variants:
   for rep in a.seeds:
    path=a.output/f'scenario_{sid}'/variant/f'seed_{rep:02d}'
    r=execute(sid,variant,rep,path)
    print(json.dumps({'scenario':sid,'variant':variant,'seed':rep,'queries':r['actual_queries'],'status':'PASS'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
