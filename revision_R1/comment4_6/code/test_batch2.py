from batch2_common import *

def validate(out):
 gate(out);p=locations(out);verify_first_batch(out);x,arrays=inputs(out);checks=[]
 def passed(name,evidence):checks.append({'name':name,'status':'PASS','evidence':evidence})
 passed('first_batch_and_sources_immutable','all65 first-batch sealed files and57 original-source hash entries unchanged')
 for row in frame(p['audit']/'second_batch_input_manifest.csv').itertuples():assert sha(row.path)==row.SHA256
 passed('input_phase_and_units','1590 query_cap only;30 scenario IDs;5 methods30x10 and3 methods30x1; finite/unique')
 idx=np.load(p['audit']/'outer_scenario_indices.npy',allow_pickle=False);inner=np.load(p['audit']/'nested_seed_indices.npy',allow_pickle=False)
 rng=np.random.default_rng(SEED);assert np.array_equal(idx,rng.integers(0,30,size=(B,30)));assert np.array_equal(inner,rng.integers(0,10,size=(B,5,30,10)).astype(np.uint8))
 assert idx.shape==(B,30) and inner.shape==(B,5,30,10) and idx.min()>=0 and idx.max()<30 and inner.max()<10
 passed('fixed_RNG_reconstruction','PCG64 seed2026103006,20000 outer draws and exact continued-state inner indices reproduced; verification only')
 assert not np.array_equal(inner[:,0],inner[:,1]);i,j=np.argwhere(idx[0,:,None]==idx[0,None,:])[1];duplicates=[(a,b) for a in range(30) for b in range(a+1,30) if idx[0,a]==idx[0,b]];assert duplicates
 a,b=duplicates[0];assert not np.array_equal(inner[0,:,a,:],inner[0,:,b,:])
 passed('independent_inner_technical_resampling','separate stochastic-method streams and separate draws for repeated sampled occurrences;deterministic no inner axis')
 sampled={s:np.load(p['audit']/('sampled_scenario_values_'+('scenario_only' if s=='scenario-only' else 'scenario_seed')+'.npy'),allow_pickle=False) for s in SCHEMES}
 for scheme in SCHEMES:
  for mi,m in enumerate(METHODS):
   a=sampled[scheme][:,mi,:]
   if scheme=='scenario-only' or m in DETERM:expected=arrays[m].mean(axis=1)[idx]
   else:expected=np.take_along_axis(arrays[m][idx],inner[:,STOCH.index(m)].astype(np.int64),axis=2).mean(axis=2)
   assert np.array_equal(a,expected)
   order=np.sort(a,axis=1);manual=.9*order[:,26]+.1*order[:,27];assert np.max(abs(manual-np.quantile(a,.9,axis=1,method='linear')))<1e-12
 passed('all_methods_share_same_paired_outer_indices','all320000 resampled method vectors reconstructed; all P90s use ranks27/28 of30 scenario means')
 for m in DETERM:
  mi=METHODS.index(m);assert np.array_equal(sampled[SCHEMES[0]][:,mi,:],sampled[SCHEMES[1]][:,mi,:])
 passed('deterministic_no_pseudo_seeds','identical scalar scenario values in both schemes; no invented ten seed observations')
 for scheme in SCHEMES:
  if scheme=='scenario-only':mf=p['bootstrap']/'method_bootstrap_distributions.csv';pf=p['bootstrap']/'paired_cluster_bootstrap.csv'
  else:mf=p['variance']/'nested_bootstrap_method_distributions.csv';pf=p['variance']/'nested_bootstrap_paired_distributions.csv'
  method=frame(mf);pair=frame(pf);assert len(method)==B*8 and len(pair)==B*4
  for mi,m in enumerate(METHODS):
   g=method[method.method==m].sort_values('bootstrap_id');assert g.bootstrap_id.tolist()==list(range(1,B+1))
   independent=summarize(sampled[scheme][:,mi,:])
   for metric,values in independent.items():assert np.array_equal(values,g[metric].to_numpy())
  for m in COMPARATORS:
   a=method[method.method=='proposed'].sort_values('bootstrap_id');b=method[method.method==m].sort_values('bootstrap_id');g=pair[pair.comparator==m].sort_values('bootstrap_id')
   assert np.max(abs(g.delta_mean_pp-(a.mean_regret_pct.to_numpy()-b.mean_regret_pct.to_numpy())))<1e-14
   assert np.max(abs(g.delta_P90_pp-(a.P90_regret_pct.to_numpy()-b.P90_regret_pct.to_numpy())))<1e-14
   mi=METHODS.index(m);expected=np.quantile(sampled[scheme][:,0,:]-sampled[scheme][:,mi,:],.9,axis=1,method='linear');assert np.array_equal(expected,g.P90_of_paired_differences_pp.to_numpy())
 passed('all_raw_distributions_and_effect_definitions','every draw checked;difference-of-P90s and P90-of-differences separate;positive unfavorable to Proposed')
 ms=frame(p['delivery']/'Table_4_6_method_uncertainty.csv');ps=frame(p['delivery']/'Table_4_6_tail_uncertainty.csv')
 for summary,entity,files in [(ms,'method',[p['bootstrap']/'method_bootstrap_distributions.csv',p['variance']/'nested_bootstrap_method_distributions.csv']),(ps,'comparator',[p['bootstrap']/'paired_cluster_bootstrap.csv',p['variance']/'nested_bootstrap_paired_distributions.csv'])]:
  for scheme,filename in zip(SCHEMES,files):
   data=frame(filename)
   for row in summary[summary.scheme==scheme].itertuples():
    vals=data.loc[data[entity]==getattr(row,entity),row.metric].to_numpy();lo,hi=np.quantile(vals,[.025,.975],method='linear');assert abs(lo-row.percentile95_low)<1e-14 and abs(hi-row.percentile95_high)<1e-14 and abs(hi-lo-row.interval_width)<1e-14
 passed('all_95_percentile_intervals','all endpoints/widths independently checked against20000 saved draws,linear method;no p values')
 vc=frame(p['variance']/'variance_components.csv');sd=frame(p['variance']/'seed_dispersion_by_scenario.csv');assert len(sd)==240
 for m,a in arrays.items():
  row=vc[vc.method==m].iloc[0];observed=a.mean(axis=1).var(ddof=1);assert abs(observed-row.observed_between_variance_pp2)<1e-13
  if m in STOCH:
   w=a.var(axis=1,ddof=1).mean();b=max(0,observed-w/10);assert abs(w-row.within_variance_pp2)<1e-13 and abs(b-row.between_component_pp2)<1e-13 and abs(w+b-row.rough_total_single_run_variance_pp2)<1e-13
  else:assert pd.isna(row.within_variance_pp2) and pd.isna(row.mean_seed_SD_pp) and pd.isna(row.between_component_pp2)
 passed('variance_definitions_and_units','ddof1 within and between;meanSD distinct fromsqrt(mean variance);corrected component and truncation reported;singleton NA')
 counts=frame(p['bootstrap']/'draw_scenario_multiplicities.csv');assert counts[[f'count_{s}' for s in IDS]].sum(axis=1).eq(30).all()
 cond=frame(p['bootstrap']/'high_tail_conditional_resampling_ranges.csv');c=cond.groupby(['scheme','conditioning_scenario_id','entity','metric']).conditional_draws.sum();assert c.eq(B).all() and cond.interpretation.str.contains('NOT confidence interval').all()
 loso=frame(p['bootstrap']/'all30_LOSO_methods_mean_P90_max.csv');assert len(loso)==240 and loso.primary_retains_all30.all()
 passed('complete_influence_no_primary_exclusions','all30x8 LOSO records;full20000 draws partitioned without dropping high cases;conditional ranges not CIs')
 frozen=frame(Path(out)/'00_audit/archived_Table_R3_primary_paired_comparisons.csv');assert frozen.equals(tables(out)['Table_R3_primary_paired_comparisons.csv'])
 assert not any(k in sys.modules for k in ['experiment','torch','sklearn','ue_provider','candidate_factory'])
 assert not list(Path(out).rglob('*.zip')) and not (p['delivery']/'Reviewer1_4.6_英文回复草稿.md').exists()
 passed('primary_tests_and_scope','originalR3 including Holm p values unchanged;no UE/model/search imports,Word/Response orZIP')
 dump(p['audit']/'G2_validation_report.json',{'status':'PASS_S2_S3','at':now(),'seed':SEED,'B_per_scheme':B,'independent_scenarios':30,'runs':1590,'checks':checks,'new_UE':0,'new_algorithms':0,'new_training':0,'new_scenarios':0,'statistical_bootstrap_schemes':2,'original_primary_tests_unchanged':True,'stop_after_delivery':True})
 csv(p['audit']/'automatic_acceptance_log.csv',checks);print(f'S2/S3 G2 PASS: {len(checks)} automated checks',flush=True)
