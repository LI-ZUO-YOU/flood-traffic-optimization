from batch2_common import *

def run(out):
 gate(out);p=locations(out);_,arrays=inputs(out);means={m:a.mean(axis=1) for m,a in arrays.items()};idx=np.load(p['audit']/'outer_scenario_indices.npy',allow_pickle=False)
 counts=(idx[:,:,None]==np.arange(30)[None,None,:]).sum(axis=1);csv(p['bootstrap']/'draw_scenario_multiplicities.csv',pd.DataFrame(counts,columns=[f'count_{sid}' for sid in IDS]).assign(bootstrap_id=np.arange(1,B+1)))
 # All30 symmetric leave-one-out sensitivities. These never replace full30 estimates.
 rows=[]
 for m in METHODS:
  full=summarize(means[m])
  for j,sid in enumerate(IDS):
   keep=np.arange(30)!=j;ss=summarize(means[m][keep]);r={'method':m,'omitted_scenario_for_sensitivity_only':sid,'remaining_scenarios':29,'primary_retains_all30':True}
   for metric in full:r['full30_'+metric]=full[metric];r['LOSO29_'+metric]=ss[metric];r['change_'+metric]=ss[metric]-full[metric]
   if m in COMPARATORS:
    r['full30_delta_P90_pp']=q(means['proposed'],.9)-full['P90_regret_pct'];r['LOSO29_delta_P90_pp']=q(means['proposed'][keep],.9)-ss['P90_regret_pct']
   rows.append(r)
 csv(p['bootstrap']/'all30_LOSO_methods_mean_P90_max.csv',rows)
 high=js(p['audit']/'batch2_execution_contract.json')['high_tail_scenarios_fixed_from_first_batch'];highids=[r['scenario_id'] for r in high];conditional=[];attribution=[];rawcon=[]
 for scheme in SCHEMES:
  suffix='scenario_only' if scheme=='scenario-only' else 'scenario_seed';a=np.load(p['audit']/f'sampled_scenario_values_{suffix}.npy',allow_pickle=False)
  if scheme=='scenario-only':method=frame(p['bootstrap']/'method_bootstrap_distributions.csv');pair=frame(p['bootstrap']/'paired_cluster_bootstrap.csv')
  else:method=frame(p['variance']/'nested_bootstrap_method_distributions.csv');pair=frame(p['variance']/'nested_bootstrap_paired_distributions.csv')
  for mi,m in enumerate(METHODS):
   order=np.argsort(a[:,mi,:],axis=1,kind='stable');lower=idx[np.arange(B),order[:,26]];upper=idx[np.arange(B),order[:,27]];maximum=idx[np.arange(B),order[:,-1]]
   rawcon.append(pd.DataFrame({'bootstrap_id':np.arange(1,B+1),'scheme':scheme,'method':m,'P90_lower_rank27_scenario':IDS[lower],'P90_upper_rank28_scenario':IDS[upper],'max_selected_scenario':IDS[maximum]}))
   for sid in IDS:
    case=sid-3001;weighted=.9*(lower==case)+.1*(upper==case)
    attribution.append({'scheme':scheme,'method':m,'scenario_id':sid,'P90_any_selected_slot_frequency':float(((lower==case)|(upper==case)).mean()),'P90_mean_selected_slot_weight':float(weighted.mean()),'max_selected_frequency':float((maximum==case).mean()),'interpretation':'empirical resample order-stat attribution,not causal; stable sampled-order tie resolution'})
  for sid in highids:
   num=counts[:,sid-3001]
   for bucket in ['0','1','2','>=3']:
    take=num>=3 if bucket=='>=3' else num==int(bucket);n=int(take.sum());assert n>0
    def add(values,entity,metric):
     z=np.asarray(values,float)[take];lo,hi=np.quantile(z,[.025,.975],method='linear')
     conditional.append({'scheme':scheme,'conditioning_scenario_id':sid,'occurrence_bucket':bucket,'conditional_draws':n,'fraction_of_all20000_draws':n/B,'entity':entity,'metric':metric,'conditional_mean':z.mean(),'conditional_median':np.median(z),'conditional_quantile025':lo,'conditional_quantile975':hi,'conditional_width':hi-lo,'interpretation':'conditional resampling range only,NOT confidence interval; main includes all30 and all20000 draws'})
    for m in METHODS:
     g=method[method.method==m].sort_values('bootstrap_id')
     for metric in ['P90_regret_pct','max_regret_pct']:add(g[metric],m,metric)
    for m in COMPARATORS:
     g=pair[pair.comparator==m].sort_values('bootstrap_id')
     for metric in ['delta_mean_pp','delta_P90_pp']:add(g[metric],'Proposed-minus-'+m,metric)
 csv(p['bootstrap']/'bootstrap_order_statistic_contributors.csv',pd.concat(rawcon,ignore_index=True));csv(p['bootstrap']/'scenario_order_stat_attribution.csv',attribution);csv(p['bootstrap']/'high_tail_conditional_resampling_ranges.csv',conditional)
 # Copy existing frozen top5 as descriptive evidence; no posthoc cutoffs or scenario removal.
 csv(p['bootstrap']/'all_method_top5_frozen_first_batch.csv',frame(Path(out)/'02_new30/new30_top_tail_influence.csv'))
 print('High-tail inclusion, order-stat attribution and symmetricLOSO complete',flush=True)
