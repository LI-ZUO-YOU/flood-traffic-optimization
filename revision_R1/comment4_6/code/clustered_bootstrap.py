from batch2_common import *

def run(out):
 gate(out);p=locations(out);_,arrays=inputs(out);means={m:a.mean(axis=1) for m,a in arrays.items()};rng=np.random.default_rng(SEED)
 dump(p['audit']/'RNG_initial_state.json',rng.bit_generator.state)
 idx=rng.integers(0,30,size=(B,30));dump(p['audit']/'RNG_after_outer_state.json',rng.bit_generator.state)
 np.save(p['audit']/'outer_scenario_indices.npy',idx,allow_pickle=False)
 csv(p['audit']/'outer_scenario_ids.csv',pd.DataFrame(IDS[idx],columns=[f'position_{i+1:02d}' for i in range(30)]).assign(bootstrap_id=np.arange(1,B+1)))
 # Fixed second draw, independently for each stochastic method and sampled occurrence.
 inner=rng.integers(0,10,size=(B,len(STOCH),30,10)).astype(np.uint8)
 np.save(p['audit']/'nested_seed_indices.npy',inner,allow_pickle=False);dump(p['audit']/'RNG_after_inner_state.json',rng.bit_generator.state)
 dump(p['audit']/'resampling_array_schema.json',{'outer_shape':list(idx.shape),'outer_dtype':str(idx.dtype),'outer_values':'0..29 mapped to3001..3030','inner_shape':list(inner.shape),'inner_dtype':str(inner.dtype),'inner_values':'0..9 are archived seed indices; lossless cast after default-int64 RNG draw','axis_order':js(p['audit']/'batch2_execution_contract.json')['inner_axis_order'],'outer_sha256':sha(p['audit']/'outer_scenario_indices.npy'),'inner_sha256':sha(p['audit']/'nested_seed_indices.npy'),'first_scenario_draw':IDS[idx[0]].tolist(),'seed':SEED,'B':B})
 # Both schemes use exactly the same paired outer indices. No new physical inputs are generated.
 allsummary=[];pairsummary=[];allraw=[];pairraw=[]
 for scheme in SCHEMES:
  sampled={}
  for m in METHODS:
   if scheme=='scenario-only' or m in DETERM:sampled[m]=means[m][idx]
   else:
    j=STOCH.index(m);selected=arrays[m][idx]
    sampled[m]=np.take_along_axis(selected,inner[:,j,:,:].astype(np.int64),axis=2).mean(axis=2)
  stats={m:summarize(a) for m,a in sampled.items()}
  for m in METHODS:
   point=summarize(means[m]);df=pd.DataFrame({'bootstrap_id':np.arange(1,B+1),'scheme':scheme,'method':m,**stats[m]});allraw.append(df)
   for metric,a in stats[m].items():allsummary.append(interval_row(a,point[metric],scheme=scheme,method=m,metric=metric,unit='percent regret'))
  for m in COMPARATORS:
   ds={'delta_mean_pp':stats['proposed']['mean_regret_pct']-stats[m]['mean_regret_pct'],'delta_median_pp':stats['proposed']['median_regret_pct']-stats[m]['median_regret_pct'],'delta_P90_pp':stats['proposed']['P90_regret_pct']-stats[m]['P90_regret_pct'],'P90_of_paired_differences_pp':np.quantile(sampled['proposed']-sampled[m],.9,axis=1,method='linear')}
   base={'delta_mean_pp':means['proposed'].mean()-means[m].mean(),'delta_median_pp':q(means['proposed'],.5)-q(means[m],.5),'delta_P90_pp':q(means['proposed'],.9)-q(means[m],.9),'P90_of_paired_differences_pp':q(means['proposed']-means[m],.9)}
   pairraw.append(pd.DataFrame({'bootstrap_id':np.arange(1,B+1),'scheme':scheme,'comparator':m,**ds}))
   for metric,a in ds.items():pairsummary.append(interval_row(a,base[metric],scheme=scheme,comparator=m,metric=metric,unit='percentage points; positive unfavorable to Proposed'))
  np.save(p['audit']/('sampled_scenario_values_'+('scenario_only' if scheme=='scenario-only' else 'scenario_seed')+'.npy'),np.stack([sampled[m] for m in METHODS],axis=1),allow_pickle=False)
  print(f'{scheme}: {B} paired bootstrap replicates calculated',flush=True)
 methoddata=pd.concat(allraw,ignore_index=True);pairdata=pd.concat(pairraw,ignore_index=True);ms=pd.DataFrame(allsummary);ps=pd.DataFrame(pairsummary)
 csv(p['bootstrap']/'method_bootstrap_distributions.csv',methoddata[methoddata.scheme=='scenario-only']);csv(p['bootstrap']/'paired_cluster_bootstrap.csv',pairdata[pairdata.scheme=='scenario-only']);csv(p['bootstrap']/'method_bootstrap_summary.csv',ms[ms.scheme=='scenario-only']);csv(p['bootstrap']/'paired_cluster_bootstrap_summary.csv',ps[ps.scheme=='scenario-only'])
 csv(p['variance']/'nested_bootstrap_method_distributions.csv',methoddata[methoddata.scheme=='scenario+seed']);csv(p['variance']/'nested_bootstrap_paired_distributions.csv',pairdata[pairdata.scheme=='scenario+seed']);csv(p['variance']/'nested_bootstrap_method_summary.csv',ms[ms.scheme=='scenario+seed']);csv(p['variance']/'nested_bootstrap_summary.csv',ps[ps.scheme=='scenario+seed'])
 csv(p['delivery']/'Table_4_6_tail_uncertainty.csv',ps);csv(p['delivery']/'Table_4_6_method_uncertainty.csv',ms)
 compare=ps[ps.metric.isin(['delta_mean_pp','delta_P90_pp','P90_of_paired_differences_pp'])].pivot(index=['comparator','metric','estimate_full30'],columns='scheme',values=['percentile95_low','percentile95_high','interval_width']);compare.columns=['__'.join(c) for c in compare.columns];csv(p['variance']/'scenario_only_vs_nested_intervals.csv',compare.reset_index())
 dump(p['audit']/'bootstrap_compute_complete.json',{'status':'PASS_COMPUTED_PENDING_VALIDATION','at':now(),'B_per_scheme':B,'seed':SEED,'method_distributions_rows_per_scheme':B*len(METHODS),'paired_distributions_rows_per_scheme':B*len(COMPARATORS),'independent_scenarios':30,'same_outer_across_methods_and_schemes':True,'new_UE_or_search':0})
