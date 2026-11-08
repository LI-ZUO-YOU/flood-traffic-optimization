from s4_common import *
import shutil,platform
def main():
 p=OUT/'00_lock/S4_frozen_protocol.json'
 if p.exists():raise FileExistsError('S4 protocol already frozen')
 assert js(SCALE/'completion_check.json')['m14_all_component_runs_pass']
 import itertools
 dpchecks=[]
 for n in [2,3,4,5]:
  roads=tuple(range(1,n+1));costs={i:float((i*17+3)%23) for i in range(1<<n)}
  value,seq=exact_dp(costs,roads)
  brute=min((sum(costs[mask] for mask in A.masks(s,roads))/n,s) for s in itertools.permutations(roads))
  assert value==brute[0] and seq==brute[1]
  dpchecks.append({'synthetic_unit_m':n,'DP_value':value,'exhaustive_value':brute[0],'sequence':seq_string(seq),'passed':True,'UE_calls':0,'scope':'pure DP unit verification, not traffic experiment'})
 csv(OUT/'00_lock/S4_DP_independent_unit_check.csv',dpchecks)
 verify()
 for p0,h in js(SCALE/'00_lock/frozen_future_search_adapter.json')['source_sha256'].items():assert sha(p0)==h
 supp=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\Downloads\4.4_S4补充实施细则.md');shutil.copy2(supp,OUT/'00_lock'/supp.name)
 summary=frame(SCALE/'03_component_scaling/S3_scaling_summary.csv');base=float(summary[summary.m==14].iloc[0].candidate_wall_scenario_mean)
 rules=[('candidate_count','30000'),('source_quotas','16000/5000/4000/3000/2000'),('prefix_m10','original exhaustive 5040 prefixes'),('prefix_m12_m14','same S3 cyclic balanced orbit sampling; partial last prefix'),('primary_channels','15/10/15/10/10; total60'),('reserve_prefix2','10'),('reserve_quantiles_per_source_prefix3','max10'),('seed_share','0.55/0.50/0.50'),('LS_early_window','positions1-5'),('LS_parents','5'),('LS_stop','2 rounds with relative gain<0.001'),('checkpoints','64/128/256; missing complete sequence recorded'),('B','256 unique states, all initialization included'),('SA_temperature_cooling','0.0025/0.995; original natural stop1000'),('Greedy_ILS_perturb_swaps','2'),('Beam_initial_width','2; original progressive multipliers1/2/4/8/16'),('target_objective','mean R0..R(m-1), terminal zero'),('normalizer',str(frozen.LEGACY_BASELINE)),('UE_target','1e-9, unchanged4.2 path solver; no flow warm starts'),('equivalence_kappa',str(KAPPA)),('task_cap_s',str(10*base))]
 csv(OUT/'00_lock/S4_parameter_rules.csv',[{'parameter':k,'rule_m10_m12_m14':v,'changed_after_freeze':False} for k,v in rules])
 jobs=[];methods=['proposed','greedy_ils','ue_bibeam','sa_original']
 for rep in range(3):
  for ix,(sid,m) in enumerate((s,m) for s in range(4401,4407) for m in [10,12,14]):
   offset=(ix+rep)%4
   for method in methods[offset:]+methods[:offset]:
    if method=='ue_bibeam' and rep>0:continue
    jobs.append({'task_index':len(jobs)+1,'scenario_id':sid,'m':m,'method':method,'replicate':rep})
 assert len(jobs)==180;csv(OUT/'00_lock/S4_optimization_schedule.csv',jobs)
 enums=[{'task_index':i+1,'scenario_id':sid,'m':m} for i,(sid,m) in enumerate((s,m) for s in range(4401,4407) for m in [10,12,14])];csv(OUT/'00_lock/S4_enumeration_schedule.csv',enums)
 spec={'frozen_at':now(),'supplement_SHA256':sha(supp),'scenario_ids':list(range(4401,4407)),'m':[10,12,14],'optimization_tasks':180,'full_tables_per_resource':18,'full_states_per_resource':129024,'method_replicates':{'proposed':[0,1,2],'greedy_ils':[0,1,2],'sa_original':[0,1,2],'ue_bibeam':[0]},'B':256,
 'source_code':'S3 components44 and frozen search_adapter44, no strategy modifications','seed_rules':CFG['seeds'],'UE_target':1e-9,'kappa':KAPPA,'max_task_seconds':10*base,'cap_baseline_definition':'S3 m14 arithmetic mean over6 scenario means, each3repeats','cap_baseline_seconds':base,
 'cap_scope':'all measured optimization tasks and each full serial/4core enumeration+DP task. Startup/JIT/input loads/export excluded; no tiling/restarts to evade cap. If full single-core table censored, 4core table may independently supply exact reference; single-core time remains censored.',
 'solver_failure_policy':'stop affected task, keep successful journal and scenario, no retry/looser tolerance/substitution; remaining tasks attempted','RSS_limit_bytes':js(SCALE/'00_lock/frozen_scaling_protocol.json')['max_RSS_bytes'],
 'information_firewall':'ALL180 optimization output folders hashed before any full-state reference solves; inference and output only after search. Full references never read by optimizer.',
 'timing':'one computing process CPU0, library threads1, warm-code/fresh physical cache per run. Parent monitor onCPU8. Separate 4core stage, one scenario at a time, 4 disjoint contiguous mask chunks onCPUs0,2,4,6; cold-pool startup excluded and separately recorded.',
 'reference_selection':'prefer complete valid serial table, otherwise complete valid4core table; all overlaps bitwise checked. Incomplete tables never exact. No reference=>only shared best-observed gap, no exact regret/hit.',
 'comparison':'aggregate stochastic repeats inside each scenario; n6 descriptive only. Pairwise J differences tied if abs<=kappa*max(1,abs(Jexact)); count W/T/L for Proposed. Report failures and complete-case denominators, no p-values or CI.',
 'interpretation_rules_verbatim':['若 m=12 或14 Proposed相对Greedy胜加平不少于负，只能写更大规模上出现有利迹象，6个探索性情景需要独立验证，不推翻4.1/4.3。','若仍劣于Greedy或双向beam，写在已检验规模m≤14内没有证据表明代理引导优于UE-only搜索；若对两对照方向混合，逐对照明确报告而不混成全面优势。','无论结果如何报告m14完整枚举与Proposed时间差；被删失的单核只报告实测下界，不能当完整耗时。','SiouxFalls连通模型m≤15是必要上界，更大m需更大网络，列未来工作。'],
 'no_retraining_or_retuning':True,'platform':platform.platform(),'python':sys.version,'numeric_archive_only':True}
 dump(p,spec);(OUT/'00_lock/S4_frozen_protocol.sha256').write_text(sha(p))
 files=[supp,p,SCALE/'00_lock/S0_frozen_manifest.json',SCALE/'00_lock/frozen_future_search_adapter.json',SCALE/'02_scenarios/S2_scaling_scenarios_manifest.json',SCALE/'02_scenarios/extended_severity_physical.csv',SCALE/'03_component_scaling/S3_scaling_summary.csv']
 files+=list((OUT/'code').glob('*.py'));files+=list((SCALE/'code').glob('*.py'))
 files+=list((OUT/'00_lock').glob('*.csv'))
 dump(OUT/'00_lock/S4_source_manifest.json',{'frozen_at':now(),'sha256':{str(x):sha(x) for x in sorted(set(files))}})
 print(json.dumps({'status':'FROZEN','optimization_tasks':180,'serial_enum_tasks':18,'parallel_enum_tasks':18,'seconds_cap':10*base,'files':len(set(files))}),flush=True)
if __name__=='__main__':main()
