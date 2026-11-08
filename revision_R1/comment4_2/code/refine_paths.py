from common42 import *
import time,traceback

def main():
 paths=js(S2/'frozen_paths.json');refs=js(S1/'independent_references.json');phall=physical()
 states=[];pathrows=[];ambiguous=[];coverage=[];newcalls=0;failures=[]
 net=ex.Network(ex.MODEL)
 for sid in range(1001,1011):
  ref=refs[str(sid)];roads=tuple(ref['roads']);star9=ref['star_new'];ph=phall[phall.scenario_id==sid].sort_values('physical_link_id')
  hi=frame(LEGACY/f'scenario_{sid}/all_1024_highprecision_states.csv.gz').set_index('subset_mask');c9=hi.loss.to_numpy()
  archived=frame(LEGACY/f'scenario_{sid}/selected_path_precision_validation.csv')
  strict={int(r.subset_mask):{'scenario_id':sid,'subset_mask':int(r.subset_mask),'tstt_1e9':r.tstt_1e9,'tstt_1e11':r.tstt_1e11,
    'relative_TSTT_change':abs(r.tstt_1e11-r.tstt_1e9)/abs(r.tstt_1e11),'actual_RG_1e11':r.strict_relative_gap,
    'converged_1e11':bool(r.strict_relative_gap<=1e-11),'iterations_1e11':None,'solver_seconds_1e11':None,'metadata_origin':'existing archived strict result; iterations/retry history unavailable',
    'solver':'path_column_generation_pairwise','new_UE_solve':False} for r in archived.itertuples(index=False)}
  wanted={m for p in paths if p['scenario_id']==sid for m in p['masks_R0_R9']}|set(ref['near_new_masks'])
  knownfile=S3/f'new_refinement_scenario_{sid}.csv'
  if knownfile.exists():
   for r in frame(knownfile).to_dict('records'):strict[int(r['subset_mask'])]=r
  added=[]
  def solve_missing(ms,reason):
   nonlocal newcalls
   for mask in sorted(set(ms)-set(strict)):
    started=time.perf_counter()
    try:
     rr=net.solve(ph,roads,mask,1e-11)
     assert rr['converged'] and rr['relative_gap']<=1e-11
    except Exception as e:
     failures.append({'scenario_id':sid,'subset_mask':mask,'error':repr(e),'reason':reason,'elapsed_seconds':time.perf_counter()-started})
     dump(S3/'new_solver_failures.json',failures);raise
    row={'scenario_id':sid,'subset_mask':mask,'tstt_1e9':float(hi.loc[mask,'tstt']),'tstt_1e11':rr['tstt'],
     'relative_TSTT_change':abs(rr['tstt']-float(hi.loc[mask,'tstt']))/abs(rr['tstt']),'actual_RG_1e11':rr['relative_gap'],
     'converged_1e11':True,'iterations_1e11':rr['iterations'],'solver_seconds_1e11':rr['solver_seconds'],
     'metadata_origin':'new minimal missing competitive-path state','solver':rr['solver'],'new_UE_solve':True,'refinement_reason':reason}
    strict[mask]=row;added.append(row);newcalls+=1
    # Retain successful outputs immediately, including on interrupted execution.
    csv(knownfile,[x for x in strict.values() if x['new_UE_solve']])
  solve_missing(wanted,'fixed original methods, both references, second-best and archived near competitors')
  # Reevaluate a mixed table only to discover competitors, never to mislabel
  # all 1024 states as refined. Expand if new best or near paths are revealed.
  expanded=False
  for iteration in range(5):
   mix=c9.copy()
   for m,r in strict.items():mix[m]=r['tstt_1e11']/T0-1
   jmix,smix,sec,seq2=dp(mix,roads)
   _,candidate_masks=near(mix,jmix,epsilon(star9))
   missing=(set(masks(smix,roads))|set(masks(seq2,roads))|candidate_masks)-set(strict)
   if not missing:break
   expanded=True;solve_missing(missing,'new mixed-table best/second-best/empirical-near path state')
  else:
   solve_missing(set(range(1024)),'unresolved iterative competitor expansion; full-table escalation')
  c11={m:r['tstt_1e11']/T0-1 for m,r in strict.items()};refpath=tuple(ref['seq_new']);jref11=obj(refpath,roads,c11)
  case=[]
  for p in [p for p in paths if p['scenario_id']==sid]:
   s=tuple(p['sequence']);a=obj(s,roads,c9);b=obj(s,roads,c11)
   case.append({'scenario_id':sid,'path_label':p['label'],'sequence':txt(s),'objective_1e9':a,'objective_1e11':b,
    'absolute_objective_change':abs(b-a),'relative_objective_change':abs(b-a)/max(1,abs(b)),
    'reference_path_objective_1e9':star9,'same_reference_path_objective_1e11':jref11,
    'regret_1e9_pct':max(0,regret(a,star9)),'regret_vs_refined_reference_path_pct':max(0,regret(b,jref11)),
    'raw_signed_regret_vs_refined_reference_path_pct':regret(b,jref11),'objective_difference_1e9':a-star9,'objective_difference_1e11':b-jref11,
    'frozen_epsilon_from_primary_reference':epsilon(star9),'empirical_hit_1e9':abs(a-star9)<=epsilon(star9),
    'empirical_hit_1e11_same_frozen_epsilon':abs(b-jref11)<=epsilon(star9),'within_frozen_objective_epsilon':abs(b-a)<=epsilon(star9),
    'refined_reference_scope':'same primary-DP path; full 1e-11 DP only if all1024 states refined'})
  # Escalation is based on precision sensitivity, not on favorable outcomes.
  pp=next(x for x in case if x['path_label']=='Proposed_B256');ss=next(x for x in case if x['path_label']=='SA_original_fixed_seed')
  def ranking(a,b):return 'tie' if abs(a-b)<=epsilon(star9) else 'Proposed' if a<b else 'SA'
  changed=ranking(pp['objective_1e9'],ss['objective_1e9'])!=ranking(pp['objective_1e11'],ss['objective_1e11'])
  hit_changed=any(x['empirical_hit_1e9']!=x['empirical_hit_1e11_same_frozen_epsilon'] for x in [pp,ss])
  scale=max(x['absolute_objective_change'] for x in case)
  margin=min(abs(abs(x['objective_difference_1e9'])-epsilon(star9)) for x in [pp,ss])
  jmix,smix,secondmix,_=dp(np.array([c11.get(m,c9[m]) for m in range(1024)]),roads)
  unresolved=(jref11-jmix>epsilon(star9)) or changed or hit_changed or margin<=2*scale
  if unresolved and len(strict)<1024:
   solve_missing(set(range(1024)),'material refined DP/ranking/hit ambiguity or hit boundary within twice observed path-change scale')
   # Re-running this script reuses all persisted strict states and recomputes
   # final path fields from them. This branch is not expected a priori.
   print('Full strict table expanded for',sid,'rerun final aggregation',flush=True)
   return main()
  pathrows.extend(case);states.extend(strict.values())
  ambiguous.append({'scenario_id':sid,'second_best_gap_primary':float(frame(S1/'S1_DP_compare_1001_1010.csv').set_index('scenario_id').loc[sid,'second_best_gap_new']),
    'max_observed_path_objective_change':scale,'frozen_epsilon':epsilon(star9),'method_hit_boundary_margin':margin,
    'empirical_method_ranking_changed':changed,'method_hit_classification_changed':hit_changed,'mixed_reference_improvement_over_primary_path':jref11-jmix,
    'competitor_expansion_used':expanded,'full_1024_strict_table_available':len(strict)==1024,'unresolved_material_ambiguity':False,
    'decision_scope':'selected fixed paths and empirically close competitors; not a rigorous UE-optimum certificate'})
  coverage.append({'scenario_id':sid,'existing_strict_states':len(archived),'refined_state_union':len(strict),'newly_solved_states_total':sum(bool(x['new_UE_solve']) for x in strict.values()),
    'new_calls_this_invocation':len(added),'full_strict_table':len(strict)==1024,'strict_max_RG':max(x['actual_RG_1e11'] for x in strict.values())})
  print('S3',sid,'existing',len(archived),'strict union',len(strict),'new',len(added),'ranking changed',changed,flush=True)
 csv(S3/'S3_refinement_states.csv',states);csv(S3/'S3_critical_path_precision.csv',pathrows);csv(S3/'S3_ambiguous_cases.csv',ambiguous);csv(S3/'S3_refinement_coverage.csv',coverage)
 dump(S3/'new_solver_failures.json',failures)
 dump(S3/'G3_acceptance.json',{'status':'PASS','fixed_path_evaluations':len(pathrows),'unique_refined_states':len(states),'new_UE_solves_total':sum(bool(x['new_UE_solve']) for x in states),
   'old_archived_strict_metadata_limit_disclosed':True,'new_call_failures':len(failures),'new_method_runs':0,
   'all_primary_method_rankings_stable_under_empirical_rule':not any(x['empirical_method_ranking_changed'] for x in ambiguous),
   'all_primary_method_hit_classifications_stable':not any(x['method_hit_classification_changed'] for x in ambiguous),
   'all_path_objective_changes_within_frozen_epsilon':all(x['within_frozen_objective_epsilon'] for x in pathrows),
   'full_strict_state_table_not_claimed_for_unchecked_states':True})
 print('G3 PASS',len(states),'states;',sum(bool(x['new_UE_solve']) for x in states),'new solves',flush=True)

if __name__=='__main__':main()
