from s4_common import *

def run():
 df=metric_rows();assert len(df)==330;assert set(df.scenario_id)==set(range(5101,5111))
 rows=[];pairs=[]
 for (sid,v),g in df.groupby(['scenario_id','variant_id'],sort=True):
  assert sorted(g.seed_index)==[0,1,2]
  base=df[(df.scenario_id==sid)&(df.variant_id=='F0_FULL')].set_index('seed_index')
  d=np.array([r.regret_pct-base.loc[r.seed_index,'regret_pct'] for r in g.itertuples()])
  signs=[sign_J(r.J,base.loc[r.seed_index,'J'],sid) for r in g.itertuples()]
  for r,s,delta in zip(g.itertuples(),signs,d):pairs.append({'scenario_id':sid,'variant_id':v,'seed_index':r.seed_index,'regret_pct':r.regret_pct,'F0_regret_pct':base.loc[r.seed_index,'regret_pct'],'delta_pp':delta,'seed_pair_win_tie_loss':s})
  x=g.regret_pct.to_numpy();J=g.J.mean();bJ=base.J.mean()
  rows.append({'scenario_id':sid,'variant_id':v,'n_seeds':3,'mean_J':J,'F0_mean_J':bJ,'mean_regret_pct':x.mean(),'median_seed_regret_pct':quant(x,.5),'P90_seed_regret_pct':quant(x,.9),'max_seed_regret_pct':x.max(),'min_seed_regret_pct':x.min(),'seed_SD_regret_pp':float(np.std(x,ddof=1)),'seed_range_regret_pp':x.max()-x.min(),'seed_IQR_regret_pp':quant(x,.75)-quant(x,.25),'mean_delta_vs_F0_pp':d.mean(),'median_seed_delta_pp':quant(d,.5),'seed_SD_delta_pp':float(np.std(d,ddof=1)),'paired_seed_wins':signs.count('win'),'paired_seed_ties':signs.count('tie'),'paired_seed_losses':signs.count('loss'),'scenario_win_tie_loss':sign_J(J,bJ,sid),'mean_online_seconds':g.fresh_online_seconds.mean()})
 sc=pd.DataFrame(rows);csv(S4/'01_statistics/scenario_seed_statistics.csv',sc);csv(S4/'01_statistics/all_seed_pairwise_differences.csv',pairs)
 summaries=[];loso=[];influence=[]
 for v in METHODS:
  g=sc[sc.variant_id==v];x=g.mean_regret_pct.to_numpy();d=g.mean_delta_vs_F0_pp.to_numpy();full=float(d.mean());wins=g.scenario_win_tie_loss.value_counts()
  summaries.append({'variant_id':v,'n_scenarios':len(g),'seeds_each':3,'mean_regret_pct':x.mean(),'median_scenario_mean_regret_pct':quant(x,.5),'P90_scenario_mean_regret_pct':quant(x,.9),'max_scenario_mean_regret_pct':x.max(),'max_individual_seed_regret_pct':df[df.variant_id==v].regret_pct.max(),'mean_delta_vs_F0_pp':full,'median_delta_vs_F0_pp':quant(d,.5),'scenario_wins':int(wins.get('win',0)),'scenario_ties':int(wins.get('tie',0)),'scenario_losses':int(wins.get('loss',0)),'mean_within_scenario_seed_SD_pp':g.seed_SD_regret_pp.mean(),'max_within_scenario_seed_SD_pp':g.seed_SD_regret_pp.max(),'mean_online_seconds':g.mean_online_seconds.mean()})
  for omitted in range(5101,5111):
   other=g[g.scenario_id!=omitted];delta=other.mean_delta_vs_F0_pp.mean();sgn=other.scenario_win_tie_loss.value_counts()
   loso.append({'variant_id':v,'omitted_scenario_for_sensitivity_only':omitted,'n_remaining':9,'full10_mean_regret_pct':x.mean(),'LOSO9_mean_regret_pct':other.mean_regret_pct.mean(),'full10_mean_delta_pp':full,'LOSO9_mean_delta_pp':delta,'LOSO9_median_regret_pct':other.mean_regret_pct.median(),'LOSO9_P90_regret_pct':other.mean_regret_pct.quantile(.9),'LOSO9_max_regret_pct':other.mean_regret_pct.max(),'scenario_wins':int(sgn.get('win',0)),'scenario_ties':int(sgn.get('tie',0)),'scenario_losses':int(sgn.get('loss',0)),'mean_delta_raw_sign_changed':bool(full*delta<0 and abs(full)>1e-12 and abs(delta)>1e-12),'primary_result_is_full10':True})
  case=g[g.scenario_id==5102].iloc[0];other=g[g.scenario_id!=5102]
  influence.append({'variant_id':v,'main_n':10,'main_mean_regret_pct':x.mean(),'case5102_mean_regret_pct':case.mean_regret_pct,'case5102_contribution_to_main_mean_pp':case.mean_regret_pct/10,'case5102_share_of_sum_regrets_pct':100*case.mean_regret_pct/x.sum() if x.sum()!=0 else np.nan,'main_mean_delta_vs_F0_pp':full,'case5102_delta_vs_F0_pp':case.mean_delta_vs_F0_pp,'case5102_delta_contribution_to_main_mean_pp':case.mean_delta_vs_F0_pp/10,'LOSO9_without5102_mean_regret_pct':other.mean_regret_pct.mean(),'LOSO9_without5102_mean_delta_pp':other.mean_delta_vs_F0_pp.mean(),'interpretation':'sensitivity only;5102 retained in primary estimate'})
 summary=pd.DataFrame(summaries);lo=pd.DataFrame(loso)
 for v in METHODS:
  mask=summary.variant_id==v;summary.loc[mask,'LOSO_delta_min_pp']=lo[lo.variant_id==v].LOSO9_mean_delta_pp.min();summary.loc[mask,'LOSO_delta_max_pp']=lo[lo.variant_id==v].LOSO9_mean_delta_pp.max();summary.loc[mask,'LOSO_sign_flip_omissions']=int(lo[lo.variant_id==v].mean_delta_raw_sign_changed.sum())
 csv(S4/'01_statistics/full10_descriptive_summary.csv',summary);csv(S4/'01_statistics/LOSO_all10_omissions.csv',lo);csv(S4/'01_statistics/5102_influence_no_exclusion.csv',influence)
 # Frozen v2 descriptive paired scenario bootstrap, shared resamples across methods.
 index=np.random.default_rng(2026102906).integers(0,10,size=(10000,10));boot=[]
 for v in METHODS:
  g=sc[sc.variant_id==v].sort_values('scenario_id')
  for col in ['mean_regret_pct','mean_delta_vs_F0_pp']:
   a=g[col].to_numpy();sample=a[index].mean(axis=1)
   boot.append({'variant_id':v,'metric':col,'estimate_full10':a.mean(),'descriptive_percentile95_low':quant(sample,.025),'descriptive_percentile95_high':quant(sample,.975),'scenario_resamples':10000,'seed':2026102906,'independent_units':10,'interpretation':'descriptive uncertainty, no significance declaration or model selection'})
 csv(S4/'01_statistics/frozen_v2_descriptive_paired_bootstrap.csv',boot)
 # Verify the main result was not changed by sensitivity analysis.
 old=frame(DELIVERY/'descriptive_summary.csv').set_index('variant_id')
 for r in summary.itertuples():assert abs(r.mean_regret_pct-old.loc[r.variant_id,'mean_scenario_regret_pct'])<1e-12
 dump(S4/'01_statistics/validation.json',{'status':'PASS','main_scenarios':10,'individual_runs':330,'scenario_method_rows':len(sc),'LOSO_rows':len(lo),'5102_retained_in_primary':True,'statistical_tests':0})
 print('S4 statistics PASS',flush=True)
