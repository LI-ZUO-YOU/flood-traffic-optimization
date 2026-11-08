from s4_common import *

def run():
 pred=frame(S4/'04_prediction_diagnostics/common_state_predictions.csv.gz');ph,roads,_=public_scenario(5102);rows=[]
 for name in MODELS:
  d=pred[(pred.scenario_id==5102)&(pred.model==name)&(pred.restored_count==1)].copy();d['true_rank_among_singletons']=d.true_cost.rank(method='min');d['predicted_rank_among_singletons']=d.predicted_cost.rank(method='min')
  for x in d.itertuples():rows.append({'model':name,'road':roads[int(x.mask).bit_length()-1],'mask':x.mask,'true_cost':x.true_cost,'predicted_cost':x.predicted_cost,'true_singleton_rank':x.true_rank_among_singletons,'predicted_singleton_rank':x.predicted_rank_among_singletons})
 csv(S4/'04_prediction_diagnostics/5102_singleton_prediction_ranking.csv',rows)
 pm=frame(S4/'04_prediction_diagnostics/common_pool_metrics_scenario_means.csv');csv(S4/'04_prediction_diagnostics/common_pool_metrics_model_means_n10.csv',pm.groupby('model')[['Spearman_candidate_J','cost_MAE_candidate_J','pool_best_true_regret_pct']].mean().reset_index())
 # Compact stage table retains methods without a given phase as explicit zeros.
 p=frame(S4/'03_phases_costs/phase_method_means_n10.csv');rows=[]
 for v in METHODS:
  g=p[p.variant_id==v];r={'variant_id':v}
  for col in ['first_seen_UE_states','complete_unique_sequences','strict_incumbent_improvements']:
   for x in g.itertuples():r[x.phase+'__'+col]=getattr(x,col)
  rows.append(r)
 csv(S4/'03_phases_costs/Table_phase_accounting.csv',rows)
 src=[]
 for v in ['F0_FULL','F1_NO_RESERVE','F3_NO_DISAG','F6_SINGLE_MLP','F7_RIDGE','F9_NO_SURROGATE']:
  for rep in range(3):
   p=path(5102,v,rep);pool=frame(p/'candidate_pool.csv.gz');sc=frame(p/'screened_candidates.csv.gz');h=frame(p/'complete_sequence_history.csv.gz')
   for road in [18,29]:
    d=pool[pool.sequence.str.startswith(str(road)+'|')]
    for source,g in d.groupby('primary_source'):
     src.append({'variant_id':v,'seed_index':rep,'first_road':road,'primary_source':source,'pool_count':len(g),'primary_count':int(g.candidate_id.isin(sc.loc[sc.screening_tier=='primary_shortlist','candidate_id']).sum()),'reserve_count':int(g.candidate_id.isin(sc.loc[sc.screening_tier=='structural_reserve','candidate_id']).sum()),'completed_C':int(g.sequence.isin(h.loc[h.phase=='C_true_ue_reranking','sequence']).sum())})
 csv(S4/'02_case5102/5102_candidate_source_retention.csv',src)
 # Training records are historical evidence, never measured anew or combined with S4 inference.
 historical=frame(CONTROL/'historical_4_3_offline_cost_context.csv');csv(S4/'03_phases_costs/prior_4_3_offline_components.csv',historical.assign(provenance='prior4.3 experiment, not S3/S4 retraining'))
 csv(S4/'03_phases_costs/prior_4_3_member_training_costs.csv',frame(CONTROL/'historical_4_3_member_training_costs.csv'));csv(S4/'03_phases_costs/fixed_first_batch_Ridge_HGB_training_costs.csv',frame(DELIVERY/'fixed_surrogate_training_costs.csv'))
 print('S4 supplementary audit tables PASS',flush=True)

if __name__=='__main__':
 pin();install_no_compute_guard();run()
