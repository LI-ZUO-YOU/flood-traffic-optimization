"""Independent after-freeze verification; never imported by search workers."""
from common45 import *
from run_sealed import load_table
import argparse

def check_manifest(path):
 m=js(path/'pre_reference_manifest.json')
 for name,v in m['files'].items():assert sha(path/name)==v['sha256'],f'Run file changed: {path/name}'

def verify_run(path,baseline=False):
 check_manifest(path);r=js(path/'result.json');sid=r['scenario_id'];variant=r['variant_id'];roads=tuple(r['roads'])
 req=frame(path/'request_ledger.csv.gz');unq=frame(path/'logical_query_ledger.csv.gz');events=frame(path/'all_query_events.csv.gz');pool=frame(path/'candidate_pool.csv.gz');scr=frame(path/'screened_candidates.csv.gz');complete=frame(path/'complete_sequence_history.csv.gz');phase=frame(path/'phase_query_efficiency.csv')
 table=load_table(sid)
 assert len(unq)==r['actual_queries']<=256 and int(unq.iloc[0].subset_mask)==0
 assert unq.subset_mask.nunique()==len(unq) and req['mask'].between(0,1023).all()
 assert len(pool)==pool.sequence.nunique()==pool.candidate_id.nunique()==30000
 primary=scr[scr.screening_tier=='primary_shortlist'];assert len(primary)==primary.candidate_id.nunique()==60
 assert all(len(s:=E.original.parse_sequence(x))==10 and set(s)==set(roads) for x in pool.sequence)
 original={'prefix_stratified':16000,'random':5000,'proxy_subset_dp':4000,'proxy_ga_local':3000,'sequence_diversity':2000}
 expected=original.copy()
 if variant=='F2_NO_PREFIX':expected['prefix_replaced_random']=expected.pop('prefix_stratified')
 if variant=='F4_NO_PROXY_SOURCES':expected['replacement_for_proxy_dp']=expected.pop('proxy_subset_dp');expected['replacement_for_proxy_ga']=expected.pop('proxy_ga_local')
 if variant in {'F5_RANDOM_POOL','F9_NO_SURROGATE'}:expected={'random':30000}
 assert pool.primary_source.value_counts().to_dict()==expected
 seen={};first_phase={}
 for x in req.itertuples():
  assert bool(x.cache_hit)==(x.mask in seen)
  if x.mask not in seen:seen[x.mask]=len(seen)+1;first_phase[x.mask]=x.phase
  assert x.unique_query_index==seen[x.mask] and x.first_seen_phase==first_phase[x.mask]
  assert float(x.state_cost).hex()==float(table[x.mask]['loss']).hex()
 assert len(seen)==len(unq) and int(phase.unique_queries_phase.sum())==len(unq)
 assert unq.phase.value_counts().to_dict()==dict(zip(phase.phase,phase.unique_queries_phase))
 def reconstruct(seq):return float(np.mean([table[m]['loss'] for m in E.masks(seq,roads)]))
 assert reconstruct(r['best_sequence']).hex()==float(r['best_objective']).hex()
 for c in complete.itertuples():assert reconstruct(E.original.parse_sequence(c.sequence)).hex()==float(c.complete_J).hex()
 best=None
 for c in complete.itertuples():
  before=None if pd.isna(c.incumbent_before) else c.incumbent_before
  assert before==best
  best=c.complete_J if best is None else min(best,c.complete_J)
  assert best==c.incumbent_after
 assert best==r['best_objective']
 fw=js(path/'firewall.json');assert fw['unexpected_denials']==0 and len(fw['probe_denials'])==1 and not fw['full_reference_in_worker']
 if variant=='F9_NO_SURROGATE':assert not fw['model_reads'] and not r['surrogate_loaded'] and r['proxy_dp_policies']==0 and pool.proxy_objective_mean.isna().all()
 if variant=='F1_NO_RESERVE':assert not (scr.screening_tier=='structural_reserve').any() and r['flat_eligible_count']==29940
 if variant in {'F3_NO_DISAG','F6_SINGLE_MLP','F7_RIDGE','F8_TREE'}:assert primary.channel.value_counts().to_dict()=={'proxy_top':25,'sequence_diversity':15,'heuristic':10,'random':10}
 result={'scenario_id':sid,'variant_id':variant,'seed_index':r['replicate'],'J':r['best_objective'],'J_hex':float(r['best_objective']).hex(),'best_sequence':'|'.join(map(str,r['best_sequence'])),'unique_queries':r['actual_queries'],'logical_requests':r['logical_requests'],'candidate_count':len(pool),'primary_count':len(primary),'reserve_count':r['reserve_count'],'prefix4_coverage':r['prefix4_coverage'],'candidate_order_sha256':r['candidate_order_sha256'],'all_checks':'PASS','backend':'sealed_lookup_replay','new_UE_solves':0}
 if baseline:
  old=ROOT/f'runs/query_cap/scenario_{sid}/proposed/rep_{r["replicate"]:02d}'
  o=js(old/'result.json');assert r['best_sequence']==o['best_sequence'];assert float(r['best_objective']).hex()==float(o['best_objective']).hex();assert r['candidate_order_sha256']==o['candidate_order_sha256']
  oldunq=frame(old/'logical_query_ledger.csv.gz');oldevents=frame(old/'all_query_events.csv.gz')
  for col in ['subset_mask','query_index','phase','reason']:assert unq[col].tolist()==oldunq[col].tolist(),col
  for col in ['loss','tstt','relative_gap']:assert [float(v).hex() for v in unq[col]]==[float(v).hex() for v in oldunq[col]],col
  pd.testing.assert_frame_equal(events,oldevents,check_dtype=False,check_exact=True)
  oldpool=frame(ROOT/f'analysis_round2/replay/scenario_{sid}/rep_{r["replicate"]:02d}/candidate_pool_30000_with_oracle.csv.gz')
  oldscr=frame(ROOT/f'analysis_round2/replay/scenario_{sid}/rep_{r["replicate"]:02d}/screened_replayed.csv.gz')
  # Old pool annotation may be written in a different row order. Candidate ID fixes correspondence.
  for current,previous,label in [(pool,oldpool,'pool'),(scr,oldscr,'screened')]:
   assert current.candidate_id.tolist()==previous.candidate_id.tolist(),label+' order'
   for col in ['sequence','primary_source','proxy_rank','channel','channel_rank','screening_tier','prefix_2','prefix_3']:
    if col in current and col in previous:assert current[col].fillna('').tolist()==previous[col].fillna('').tolist(),label+':'+col
   for col in ['proxy_objective_mean','ensemble_disagreement']:
    if col in previous:assert [float(x).hex() for x in current[col]]==[float(x).hex() for x in previous[col]],label+':'+col
  result['baseline_bitwise']='PASS'
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',action='store_true');a=p.parse_args()
 rows=[]
 for path in sorted(a.runs.glob('scenario_*/*/seed_*')):
  if path.is_dir():rows.append(verify_run(path,a.baseline or (path.parent.name=='F0_FULL' and int(path.parent.parent.name.split('_')[-1])>=3001)))
 csv(a.output/'verified_runs.csv',rows);dump(a.output/'validation.json',{'status':'PASS','runs':len(rows),'all_baseline_runs_bitwise':True,'at':now()})
 print(json.dumps({'status':'PASS','runs':len(rows)}))

if __name__=='__main__':main()
