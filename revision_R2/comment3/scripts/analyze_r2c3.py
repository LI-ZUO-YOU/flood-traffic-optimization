from common import *
from scipy.stats import kendalltau
def serial(row):return {k:canonical(v) if isinstance(v,(list,dict)) else v for k,v in row.items()}
def main():
 meta=js(OUT/'raw/variant_metadata.json');summ={r['variant_id']:r for r in js(OUT/'raw/DP_summaries.json')};base_refs=js(R42/'01_legacy_ue_state_comparison/independent_references.json');E0=originals();dpcost=read(OUT/'raw/DP_all_states.csv');rows=[];transfer=[]
 for r in meta:
  sid=r['scenario_id'];baseline=base_refs[str(sid)];oldseq=baseline['seq_new'];oldJ=baseline['star_new'];E=r['road_bit_order'];same=set(E)==set(E0[sid]);row={**r,'baseline_J_star':oldJ,'baseline_sequence':oldseq,'baseline_E':E0[sid],'J_star':None,'sequence':None,'mean_stage_ATT_min':None,'S0_ATT_min':None,'S10_ATT_min':None,'DP_status':'NOT_REQUESTED_NONREPRESENTATIVE' if sid not in [1006,1003,1008] else 'NOT_REQUESTED_STRESS_ONLY' if r['factor']=='depth' and r['level'] in [.9,1.1] else r['validity_status'],'complete_Kendall_tau':None,'common_subsequence_Kendall_tau':None,'common_roads_n':len(set(E)&set(E0[sid])),'comparable_common_pairs':len(set(E)&set(E0[sid]))*(len(set(E)&set(E0[sid]))-1)//2,'first_road_changed':None,'first3_changed':None,'first3_set_overlap':None,'portfolio_Jaccard':len(set(E)&set(E0[sid]))/len(set(E)|set(E0[sid])) if E else 0.,'fixed_original_optimal_transfer_regret_pct':None}
  if r['variant_id'] in summ:
   s=summ[r['variant_id']];row.update(s);row['DP_status']='COMPLETE_NUMERICAL_CONDITIONAL_DP';seq=s['sequence'];shared=set(seq)&set(oldseq);a=[v for v in oldseq if v in shared];b=[v for v in seq if v in shared]
   tau=float(kendalltau(list(range(len(a))),[b.index(v) for v in a]).statistic) if len(a)>=2 else None;row['common_subsequence_Kendall_tau']=tau;row['first3_set_overlap']=len(set(oldseq[:3])&set(seq[:3]))
   if same:
    row['complete_Kendall_tau']=tau;row['first_road_changed']=oldseq[0]!=seq[0];row['first3_changed']=oldseq[:3]!=seq[:3]
    c=dpcost[dpcost.variant_id.eq(r['variant_id'])].sort_values('subset_mask').loss.to_numpy(float);jtransfer=pathvalue(oldseq,E,c);delta=jtransfer-s['J_star'];regret=100*delta/s['J_star'];row['fixed_original_optimal_transfer_regret_pct']=regret
    transfer.append(dict(variant_id=r['variant_id'],scenario_id=sid,factor=r['factor'],level=r['level'],status='COMPARABLE_SAME_E',frozen_original_sequence=oldseq,new_optimal_sequence=seq,new_J_star=s['J_star'],transferred_J=jtransfer,delta_J=delta,transfer_regret_pct=regret,absolute_ATT_gap_min=.6*T0/Q*delta,denominator='new same-E conditional J*',complete_Kendall_tau=tau))
   else:transfer.append(dict(variant_id=r['variant_id'],scenario_id=sid,factor=r['factor'],level=r['level'],status='NOT_COMPARABLE_PORTFOLIO_CHANGED',frozen_original_sequence=oldseq,new_optimal_sequence=seq,new_J_star=s['J_star'],transferred_J=None,delta_J=None,transfer_regret_pct=None,absolute_ATT_gap_min=None,denominator='NOT_COMPARABLE_DIFFERENT_E',complete_Kendall_tau=None))
  elif sid in [1006,1003,1008] and r['validity_status']!='VALID':transfer.append(dict(variant_id=r['variant_id'],scenario_id=sid,factor=r['factor'],level=r['level'],status='NOT_COMPARABLE_'+r['validity_status'],reason=r['invalid_reason']))
  rows.append(row)
 save(OUT/'Table_R2C3_depth_and_threshold.csv',[serial(r) for r in rows if r['factor'] in ['depth','threshold']]);save(OUT/'Table_R2C3_spatial_correlation.csv',[serial(r) for r in rows if r['factor']=='correlation']);save(OUT/'Table_R2C3_conditional_DP.csv',[serial(r) for r in rows if r['variant_id'] in summ]);save(OUT/'Table_R2C3_policy_transfer.csv',[serial(r) for r in transfer]);dump(OUT/'raw/analysis_all_conditions.json',rows)
 save(OUT/'Table_R2C3_feasibility_summary.csv',pd.DataFrame([{k:r[k] for k in ['factor','level','validity_status']} for r in rows]).groupby(['factor','level','validity_status'],dropna=False).size().rename('n_scenarios').reset_index())
 print('Analysis complete: all',len(rows),'conditions retained; DP',len(summ),flush=True)
if __name__=='__main__':main()
