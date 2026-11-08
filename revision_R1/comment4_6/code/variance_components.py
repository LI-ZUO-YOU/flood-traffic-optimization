from batch2_common import *

def run(out):
 gate(out);p=locations(out);_,arrays=inputs(out);rows=[];summary=[]
 for m,a in arrays.items():
  means=a.mean(axis=1);stochastic=m in STOCH
  sd=a.std(axis=1,ddof=1) if stochastic else np.full(30,np.nan)
  for i,sid in enumerate(IDS):rows.append({'scenario_id':sid,'method':m,'seeds_recorded':a.shape[1],'scenario_mean_regret_pct':means[i],'seed_mean_regret_pct':means[i],'seed_SD_pp':sd[i],'seed_variance_pp2':sd[i]**2,'seed_median_regret_pct':q(a[i],.5),'seed_IQR_pp':q(a[i],.75)-q(a[i],.25) if stochastic else None,'seed_range_pp':float(np.ptp(a[i])) if stochastic else None,'seed_min_regret_pct':a[i].min(),'worst_seed_regret_pct':a[i].max(),'seed_variability_status':'estimated from10 technical repeats' if stochastic else 'NA,one archived deterministic value'})
  observed=float(means.var(ddof=1));within=float(np.mean(sd**2)) if stochastic else None;uncorrected=observed-within/10 if stochastic else None;between=max(0,uncorrected) if stochastic else None
  summary.append({'method':m,'label':LABEL[m],'independent_scenarios':30,'technical_repeats_per_scenario':a.shape[1],'mean_scenario_mean_regret_pct':means.mean(),'SD_scenario_means_pp':np.sqrt(observed),'observed_between_variance_pp2':observed,'IQR_scenario_means_pp':q(means,.75)-q(means,.25),'P90_scenario_mean_regret_pct':q(means,.9),'max_scenario_mean_regret_pct':means.max(),'mean_seed_SD_pp':float(sd.mean()) if stochastic else None,'median_seed_SD_pp':float(np.median(sd)) if stochastic else None,'max_seed_SD_pp':float(sd.max()) if stochastic else None,'within_variance_pp2':within,'RMS_seed_SD_pp':np.sqrt(within) if stochastic else None,'between_component_untruncated_pp2':uncorrected,'between_component_pp2':between,'truncation_applied':bool(uncorrected<0) if stochastic else None,'corrected_between_SD_pp':np.sqrt(between) if stochastic else None,'rough_total_single_run_variance_pp2':between+within if stochastic else None,'rough_total_single_run_SD_pp':np.sqrt(between+within) if stochastic else None,'within_fraction_of_rough_total':within/(between+within) if stochastic and between+within>0 else None,'decomposition_status':'descriptive random-effects approximation,not causal' if stochastic else 'not estimated; do not set within variance to0'})
 csv(p['variance']/'seed_dispersion_by_scenario.csv',rows);csv(p['variance']/'variance_components.csv',summary);csv(p['delivery']/'Table_4_6_scenario_seed_variation.csv',summary)
 (p['variance']/'variance_decomposition_notes.md').write_text('''# 描述性方差分解口径

独立单位为30个洪水情景，每个随机方法的10个种子是给定情景内的技术重复。每情景均值先取10种子平均。observed_between=Var_s(情景均值)，within=mean_s Var_r(种子regret)，方差均用ddof=1。均值seed SD=mean_s sqrt(Var_r)，不等于sqrt(within)；后者为RMS seed SD。方差单位pp²，SD单位pp。

仅对十种子齐全的五个随机方法计算可选修正between_component=max(0,observed_between-within/10)，并同时保存截断前值及截断标记。粗略单次运行变异近似为between_component+within。这依赖将情景条件均值与种子噪声分开的抽样解释，不是无假设或因果物理机制分解，也不保证种子噪声同方差。不能把SD和方差直接相加。

确定性单记录方法的情景间统计可计算，但没有重复信息估计其seed SD或within。相应字段为NA，不人为生成十份观测。

scenario-only固定每情景原十种子均值，重抽样30情景。scenario+seed在同一外层情景索引下，对每个抽中位置和每个随机方法独立重抽10种子再求均值；同一情景被抽中多次时其内部种子也独立抽。两个区间的目标不同，双层区间不保证总比单层宽，不能据宽窄选择更有利方法。
''',encoding='utf-8')
 print('S3 variance and conditional seed dispersion complete',flush=True)
