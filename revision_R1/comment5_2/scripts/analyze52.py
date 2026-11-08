"""Independent arithmetic and DP checks; no traffic solver or model imports."""
from pathlib import Path
import hashlib, json, math
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1]
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def write(p,f):f.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def textseq(s):return list(map(int,str(s).split('|')))
def make_masks(seq,roads):
 bits={r:1<<i for i,r in enumerate(roads)};mask=0;ans=[0]
 for r in seq:mask|=bits[r];ans.append(mask)
 return ans
def main():
 manifest=js(OUT/'run_manifest.json');stage=frame(OUT/'stage_metrics_all10.csv');summary=frame(OUT/'demand_sensitivity_all10.csv');tables=frame(OUT/'demand_dp_six_tables.csv');policies=frame(OUT/'demand_dp_policy_comparison.csv');links=frame(OUT/'bottleneck_links.csv');meta=frame(OUT/'raw/all_new_UE_state_metadata.csv');dry=frame(OUT/'raw/dry_baselines.csv');frozen=js(OUT/'audit/frozen_paths.json');checks=[]
 def check(name,ok,actual,expected):checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 check('660_all10_stage_rows',len(stage)==660,len(stage),660)
 check('60_fixed_path_demand_results',len(summary)==60,len(summary),60)
 check('6144_full_table_states',len(tables)==6144,len(tables),6144)
 check('18_conditional_policy_comparisons',len(policies)==18,len(policies),18)
 check('all_new_states_strict_1e9',meta.converged.all() and meta.validation_passed.all() and meta.ue_gap.max()<=1e-9 and meta.independent_ue_gap.max()<=1e-9,dict(states=len(meta),max_RG=float(meta.ue_gap.max()),max_independent_RG=float(meta.independent_ue_gap.max())),dict(RG=1e-9))
 check('all_new_states_finite_reachable_conservative',np.isfinite(meta[['tstt_raw','ue_gap','independent_ue_gap','flow_balance_max_abs']]).all().all() and (meta.reachable_positive_OD_pairs==528).all() and (meta.unreachable_positive_OD_pairs==0).all() and meta.flow_balance_max_abs.max()<=1e-5,dict(max_flow_balance=float(meta.flow_balance_max_abs.max()),unreachable=int(meta.unreachable_positive_OD_pairs.sum())),dict(max_flow_balance=1e-5,unreachable=0))
 check('all_new_keys_unique_and_context_isolated',meta.cache_key.nunique()==len(meta) and not meta.duplicated(['scenario_id','rho','UE_tolerance','subset_mask','solver_sha256','physical_state_sha256','road_bit_order_sha256','OD_sha256']).any(),int(meta.cache_key.nunique()),len(meta))
 key_sets={r:set(meta[meta.rho==r].cache_key) for r in [1.,.75,.5]}
 check('rho_namespaces_disjoint',not(key_sets[1.]&key_sets[.75] or key_sets[1.]&key_sets[.5] or key_sets[.75]&key_sets[.5]),[len(key_sets[r]) for r in [1.,.75,.5]],'disjoint sets')
 check('archived_costs_and_new_flow_solves_reconciled',stage[stage.rho==1].archive_diagnostic_relative_difference.max()<=manifest['validation_thresholds']['archive_same_solver_state_relative_check'],float(stage.archive_diagnostic_relative_difference.max()),manifest['validation_thresholds']['archive_same_solver_state_relative_check'])
 check('stage_physical_units_no_double_conversion',np.allclose(stage.tstt_veh_h,stage.tstt_raw*.01,rtol=1e-14,atol=1e-10) and np.allclose(stage.att_minutes,stage.tstt_raw*.6/stage.Q,rtol=1e-14),True,True)
 drymap={float(r.rho):r for r in dry.itertuples(index=False)}
 for (sid,method,rho),group in stage.groupby(['scenario_id','method','rho']):
  group=group.sort_values('stage');fr=next(p for p in frozen if p['scenario_id']==sid and p['method']==method);summaryrow=summary[(summary.scenario_id==sid)&(summary.method==method)&(summary.rho==rho)].iloc[0]
  check(f'path_and_objective_{sid}_{method}_{rho}',list(group.stage)==list(range(11)) and list(group.subset_mask)==make_masks(fr['sequence'],fr['roads']) and np.array_equal(group.objective_weight.to_numpy(),[.1]*10+[0.]) and abs(summaryrow.J_rho-float((group.iloc[:10].tstt_raw/drymap[rho].tstt_raw-1).mean()))<=1e-12*max(1.,abs(summaryrow.J_rho)) and np.allclose(group.dry_TSTT_raw,drymap[rho].tstt_raw,rtol=0,atol=1e-8) and np.allclose(group.Q,360600*rho,rtol=0,atol=1e-10),'same frozen path, ten weighted states, separate dry denominator',True)
 dprows=[]
 for (sid,rho),group in tables.groupby(['scenario_id','rho']):
  group=group.sort_values('subset_mask');c=group.C_rho.to_numpy();value=np.zeros(1024)
  for mask in range(1022,-1,-1):value[mask]=c[mask]+min(value[mask|(1<<i)] for i in range(10) if not(mask&(1<<i)))
  independent=float(value[0]/10);saved=js(OUT/f'raw/scenario_{sid}_rho_{rho:.2f}_DP.json');diff=abs(independent-saved['Jstar']);roads=saved['roads'];seq=saved['sequence'];masks=make_masks(seq,roads)
  forward_sum=float(sum(c[m] for m in masks[:-1])/10)
  pointer=[];m=1023
  while m:
   row=group.iloc[m];pointer.append(int(row.dp_last_road));pred=int(row.dp_predecessor_mask)
   assert pred<m and pred>=0;m=pred
  pointer=list(reversed(pointer));complete=list(group.subset_mask)==list(range(1024)) and group.subset_mask.nunique()==1024
  c_ok=np.allclose(group.C_rho,group.tstt_raw/drymap[rho].tstt_raw-1,rtol=1e-14,atol=1e-14)
  ok=complete and diff<=1e-12*max(1.,abs(independent)) and abs(forward_sum-independent)<=1e-12*max(1.,abs(independent)) and pointer==seq and c_ok
  check(f'independent_DP_table_{sid}_{rho}',ok,dict(rows=len(group),Jstar=independent,diff=diff,predecessors_match=pointer==seq),dict(rows=1024,relative_tolerance=1e-12))
  dprows.append(dict(scenario_id=int(sid),rho=float(rho),independent_Jstar=independent,archived_new_Jstar=saved['Jstar'],abs_difference=diff,complete_masks=complete,predecessor_sequence_matches=pointer==seq,status='PASS' if ok else 'FAIL'))
  for p in policies[(policies.scenario_id==sid)&(policies.rho==rho)].itertuples(index=False):
   ss=textseq(p.sequence);pathvalue=sum(c[m] for m in make_masks(ss,roads)[:-1])/10;delta=pathvalue-independent
   check(f'absolute_policy_gap_{sid}_{rho}_{p.method}',abs(pathvalue-p.J_method)<=1e-12*max(1.,abs(pathvalue)) and np.isclose(p.delta_mean_stage_TSTT_veh_h,delta*drymap[rho].tstt_raw*.01,rtol=1e-11,atol=1e-7) and np.isclose(p.delta_mean_trip_minutes,delta*drymap[rho].tstt_raw*.6/(rho*360600),rtol=1e-11,atol=1e-9),dict(delta_J=p.delta_J,ATT_gap_minutes=p.delta_mean_trip_minutes),'independent cost sum and physical conversion')
 write(OUT/'audit/independent_DP_validation.csv',pd.DataFrame(dprows))
 check('all_bottleneck_arcs_open_finite',links.open_arc.all() and np.isfinite(links[['flow','capacity','vc','free_flow_time_raw','congested_time_raw','TSTT_contribution_veh_h']]).all().all() and (links.capacity>0).all(),len(links),'open directed arcs only')
 check('v_over_c_and_BPR',np.allclose(links.vc,links.flow/links.capacity,rtol=1e-14) and np.allclose(links.bpr_multiplier,1+.15*links.vc**4,rtol=1e-13),float(links.bpr_multiplier.max()),'unchanged alpha=0.15, beta=4')
 decomp=[];top=[]
 for (sid,rho,method,st,mask),g in links.groupby(['scenario_id','rho','method','stage','subset_mask']):
  total=g.TSTT_contribution_veh_h.sum();free=(g.flow*g.free_flow_time_raw*.01).sum();topp=g.nlargest(5,'TSTT_contribution_veh_h')
  decomp.append(dict(scenario_id=int(sid),rho=float(rho),method=method,stage=int(st),subset_mask=int(mask),open_arcs=len(g),TSTT_veh_h=float(total),free_flow_component_veh_h=float(free),BPR_congestion_component_veh_h=float(total-free),BPR_congestion_share=float((total-free)/total),top5_TSTT_share=float(topp.TSTT_contribution_veh_h.sum()/total),max_vc=float(g.vc.max()),p95_vc=float(g.vc.quantile(.95)),n_vc_gt1=int((g.vc>1).sum()),n_vc_gt2=int((g.vc>2).sum()),max_bpr_multiplier=float(g.bpr_multiplier.max())))
  for rank,r in enumerate(topp.itertuples(index=False),1):top.append(dict(scenario_id=int(sid),rho=float(rho),method=method,stage=int(st),rank=rank,arc_id=r.arc_id,physical_link_id=r.physical_link_id,flow=r.flow,capacity=r.capacity,vc=r.vc,congested_minutes=r.congested_minutes,TSTT_share=r.TSTT_share,TSTT_contribution_veh_h=r.TSTT_contribution_veh_h))
 write(OUT/'raw/bottleneck_stage_decomposition.csv',pd.DataFrame(decomp));write(OUT/'raw/top5_bottleneck_links.csv',pd.DataFrame(top))
 write(OUT/'Table_representative_initial_bottlenecks.csv',pd.DataFrame(decomp).query("method=='full_method' and stage==0"))
 aggregates=summary.groupby(['method','rho'],as_index=False).agg(n_scenarios=('scenario_id','nunique'),mean_ATT_hours=('mean_stage_ATT_hours','mean'),median_ATT_hours=('mean_stage_ATT_hours','median'),minimum_ATT_hours=('mean_stage_ATT_hours','min'),maximum_ATT_hours=('mean_stage_ATT_hours','max'),maximum_initial_ATT_hours=('initial_ATT_hours','max'),mean_terminal_ATT_minutes=('terminal_ATT_hours',lambda a:float(a.mean()*60)),maximum_terminal_ATT_minutes=('terminal_ATT_hours',lambda a:float(a.max()*60)),mean_normalized_loss=('J_rho','mean'))
 write(OUT/'Table_all10_demand_summary.csv',aggregates)
 old=frame(OUT/'audit/rho1_original_and_accepted_DP_reconciliation.csv');legacy=7480225.3449211195
 old['original_mean_stage_TSTT_veh_h']=(1+old.original_Jstar)*legacy*.01;old['original_mean_stage_ATT_hours']=old.original_mean_stage_TSTT_veh_h/360600
 write(OUT/'Table_original_and_highprecision_units.csv',old)
 phys=frame(Path('E:/jcr2区意见/返稿/4.1专项返修_20261026/inputs/historical_1001_1010.csv'))
 terminal=[]
 for sid,g in phys.groupby('scenario_id'):
  roads=next(p['roads'] for p in frozen if p['scenario_id']==sid);closed=set(map(int,g[g.is_closed==1].physical_link_id));residual=sorted(closed-set(roads));wet=g[(g.is_closed==0)&(g.free_flow_time_multiplier>1.)]
  for r in summary[(summary.scenario_id==sid)&(summary.method=='exact_DP_original_rho1')].itertuples(index=False):terminal.append(dict(scenario_id=int(sid),rho=float(r.rho),initial_closed_roads=len(closed),repaired_roads=10,residual_closed_roads=len(residual),residual_closed_ids='|'.join(map(str,residual)),unrepaired_passable_wet_roads=len(wet),terminal_ATT_minutes=r.terminal_ATT_hours*60,terminal_TSTT_veh_h=r.terminal_TSTT_veh_h,terminal_dry_ratio=r.terminal_TSTT_ratio_to_dry,terminal_objective_weight=0))
 write(OUT/'Table_terminal_residual.csv',pd.DataFrame(terminal))
 changes=policies[policies.method=='exact_DP_demand_specific'].copy()
 for method,label in [('full_method','frozen_full'),('exact_DP_original_rho1','frozen_DP')]:
  p=policies[policies.method==method][['scenario_id','rho','regret_pct','delta_mean_trip_minutes','delta_mean_stage_TSTT_veh_h']].rename(columns={k:label+'_'+k for k in ['regret_pct','delta_mean_trip_minutes','delta_mean_stage_TSTT_veh_h']});changes=changes.merge(p,on=['scenario_id','rho'],validate='one_to_one')
 write(OUT/'Table_demand_DP_changes.csv',changes)
 # Verify actual used code/data against the already accepted 4.2 source manifest.
 prior=frame(Path('E:/jcr2区意见/返稿/reviewer_4_2/00_protocol_and_input_audit/S0_input_manifest.csv'))
 used=[Path('E:/jcr2区意见/返稿/4.1专项返修_20261026/code/ue_solver.py'),Path('E:/jcr2区意见/返稿/4.1专项返修_20261026/code/path_ue.py')]
 used += [Path('E:/jcr2区意见/返稿/4.1专项返修_20261026/source_snapshot/code/model_backend/data_src/SiouxFalls_flood_benchmark/processed')/n for n in ['directed_links.csv','od_long.csv']]
 for p in used:
  match=prior[prior.absolute_path==str(p)]
  check('matches_accepted_4_2_SHA_'+p.name,len(match)==1 and sha(p)==match.sha256.iloc[0],sha(p),match.sha256.iloc[0] if len(match) else 'not found')
 frozen_code=js(OUT/'audit/experiment_code_before_BCD.json')
 check('experiment_code_unchanged_since_BCD_freeze',sha(frozen_code['path'])==frozen_code['sha256'],sha(frozen_code['path']),frozen_code['sha256'])
 result=dict(status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',checks_passed=sum(c['status']=='PASS' for c in checks),checks_total=len(checks),checks=checks)
 (OUT/'audit/analysis_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False),flush=True)
 if result['status']!='PASS':raise RuntimeError([c for c in checks if c['status']=='FAIL'])
if __name__=='__main__':main()
