"""Search subprocess: scalar RPC only; no full-cost table in its address space."""
from common45 import *
import argparse,traceback
from candidate_factory import build
from search_adapter import LedgerOracle,run_search,save_ledgers

class RPCStore:
 def request(self,mask):
  print(json.dumps({'op':'request','mask':int(mask)}),flush=True)
  reply=json.loads(sys.stdin.readline())
  if 'error' in reply:raise RuntimeError(reply['error'])
  return reply['row'],False

def install_firewall(path,variant):
 denied=[];reads=[];root=str(ROOT).lower().replace('\\','/')
 allowed_root=[root+'/code/',root+'/source_snapshot/']
 forbidden=[root+'/exact/',root+'/runs/',root+'/analysis',root+'/development/',str(HOME).lower().replace('\\','/'),'reviewer_4_2','reviewer_4_3','revision_4_4_scaling']
 out=str(OUT).lower().replace('\\','/')
 def audit(event,args):
  if event!='open':return
  try:name=os.path.abspath(os.fsdecode(args[0])).lower().replace('\\','/')
  except (TypeError,ValueError):return
  mode=args[1];flags=args[2] or 0
  writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
  bad=any(x in name for x in forbidden)
  if name.startswith(root+'/') and not any(name.startswith(p) for p in allowed_root):bad=True
  if name.startswith(out+'/'):
   public=out+'/00_audit/public_inputs/'
   simple=out+'/01_freeze_and_regression/simple_models/'
   local=str(path).lower().replace('\\','/')+'/'
   allowed=[out+'/code/',public,simple,local,out+'/protocol/']
   if not any(name.startswith(x) for x in allowed):bad=True
  if variant=='F9_NO_SURROGATE' and ('/surrogate/' in name or name.endswith('.joblib')):bad=True
  if bad:
   denied.append({'event':event,'path':name,'mode':str(mode),'writing':writing});raise PermissionError('Sealed search reference/model firewall denied access')
  if '/surrogate/' in name or name.endswith('.joblib'):reads.append(name)
 sys.addaudithook(audit)
 return denied,reads

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scenario',type=int,required=True);p.add_argument('--variant',choices=VARIANTS,required=True);p.add_argument('--seed',type=int,default=0);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 require_new_output(a.output);pin();denied,modelreads=install_firewall(a.output,a.variant)
 # A deliberate access probe must be denied before any search. Other denials are fatal.
 try:open(ROOT/f'exact/scenario_{a.scenario}/all_1024_states.csv.gz','rb')
 except PermissionError:pass
 else:raise AssertionError('Firewall probe failed')
 E.Network.solve=lambda *x,**kw:(_ for _ in ()).throw(RuntimeError('Live UE forbidden in sealed replay'))
 try:
  roads,pool,screened,report=build(a.scenario,a.seed,a.variant)
  csv(a.output/'candidate_pool.csv.gz',pool);csv(a.output/'screened_candidates.csv.gz',screened)
  dump(a.output/'candidate_freeze.json',{**report,'candidate_file_sha256':sha(a.output/'candidate_pool.csv.gz'),'screened_file_sha256':sha(a.output/'screened_candidates.csv.gz'),'at':now(),'reference_unavailable_to_search':True})
  q=LedgerOracle(RPCStore(),a.scenario,a.variant,a.seed);engine=run_search(q,roads,a.scenario,a.seed,a.variant,screened)
  q.save(a.output,'proposed',a.seed,a.scenario,{'variant_id':a.variant,**report,'backend':'sealed_lookup_replay','live_UE_calls':0,'replay_time_not_online_UE_benchmark':True,'roads':roads})
  save_ledgers(a.output,q,engine)
  assert len(denied)==1,'Unexpected forbidden access attempt'
  assert a.variant!='F9_NO_SURROGATE' or len(modelreads)==0
  dump(a.output/'firewall.json',{'probe_denials':denied,'unexpected_denials':0,'model_reads':sorted(set(modelreads)),'full_reference_in_worker':False,'scalar_budget':256,'live_UE_calls':0})
  dump(a.output/'validation.json',{'status':'PASS','candidate_count':len(pool),'primary_count':report['primary_count'],'unique_queries':q.used,'phase_identity':True,'firewall_probe_denied':True,'at':now()})
  files={str(f.relative_to(a.output)):{'sha256':sha(f),'bytes':f.stat().st_size} for f in a.output.iterdir() if f.is_file()}
  dump(a.output/'pre_reference_manifest.json',{'at':now(),'files':files,'reference_only_after_this_manifest':True})
  print(json.dumps({'op':'complete','scenario':a.scenario,'variant':a.variant,'output':str(a.output)}),flush=True)
 except Exception as e:
  dump(a.output/'validation.json',{'status':'FAIL','error':repr(e),'traceback':traceback.format_exc(),'denied':denied,'at':now()});raise

if __name__=='__main__':main()
