from s4_common import *
import zipfile,re,shutil
def md(d):
 cols=list(d.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
 for rr in d.itertuples(index=False,name=None):lines.append('| '+' | '.join('未获得' if pd.isna(v) else f'{v:.6g}' if isinstance(v,float) else str(v) for v in rr)+' |')
 return '\n'.join(lines)
def write(p,t):Path(p).write_text(t,encoding='utf-8')
def main():
 gate=js(OUT/'completion_check.json');assert gate['all_output_audits_passed'];verify_s4()
 d=frame(OUT/'analysis/S4_scale_method_runs.csv');s=frame(OUT/'analysis/S4_scenario_means.csv');summary=frame(OUT/'analysis/S4_method_summary_by_m.csv');wins=frame(OUT/'analysis/S4_win_tie_loss_by_m.csv');enums=frame(OUT/'analysis/S4_enumeration_costs.csv');refs=frame(OUT/'analysis/S4_exact_reference_by_m.csv');times=frame(OUT/'analysis/S4_fresh_runtime_by_m.csv')
 display=summary[['m','method','completed_scenarios','conditional_reference_scenarios','mean_scenario_regret_pct','median_scenario_regret_pct','max_scenario_mean_regret_pct','scenario_mean_online_wall_mean','scenario_mean_UE_queries_mean','scenario_mean_peak_online_RSS_MiB_mean']].copy()
 display.columns=['m','方法','完成情景数','完整参照情景数','平均regret_pct','情景regret中位数_pct','最大情景均值regret_pct','平均在线秒','平均UE查询数','平均采样RSS_MiB'];csv(OUT/'analysis/Table_4_4_S4_main_results.csv',display)
 costsummary=[]
 for m in [10,12,14]:
  prop=s[(s.m==m)&(s.method=='proposed')&s.all_repeats_pass]
  for method in ['enum_serial','enum_4core']:
   es=enums[(enums.m==m)&(enums.method==method)];ee=es[es.full_valid_reference];pmean=prop.online_wall_mean.mean() if len(prop) else None
   relevant=times[(times.m==m)&(times.reference_method==method)].copy();lb=[]
   for rr in relevant.itertuples(index=False):
    lb.append(rr.enum_online_wall_s if rr.enum_completed else rr.enum_completion_wall_lower_bound_s)
   all6=len(prop)==6 and len(lb)==6 and all(pd.notna(x) for x in lb)
   meanbound=float(np.mean(lb)) if all6 else None;complete=len(ee)==6
   costsummary.append({'m':m,'enumeration':method,'complete_tables':len(ee),'failed_tables':6-len(ee),'Proposed_scenarios':len(prop),'Proposed_mean_online_s':pmean,'mean_enumeration_online_s':ee.online_wall.mean() if complete else None,'mean_enumeration_completion_wall_lower_bound_s':meanbound if all6 and not complete else None,'ratio_of_mean_enum_to_mean_Proposed':ee.online_wall.mean()/pmean if complete and len(prop)==6 else None,'ratio_of_mean_enum_to_mean_Proposed_lower_bound':meanbound/pmean if all6 and not complete else None,'Proposed_wall_saving_pct':100*(1-pmean/ee.online_wall.mean()) if complete and len(prop)==6 else None,'Proposed_wall_saving_lower_bound_pct':100*(1-pmean/meanbound) if all6 and not complete else None,'scope':'mean of all6 scenarios or explicit lower bound; never average only successful enum tasks as all6'})
 costsummary=pd.DataFrame(costsummary);csv(OUT/'analysis/S4_enumeration_Proposed_cost_summary.csv',costsummary)
 interpretation=[];english=[]
 for m in [10,12,14]:
  for comparator in ['greedy_ils','ue_bibeam','sa_original']:
   r=wins[(wins.m==m)&(wins.comparator==comparator)].iloc[0];n=int(r.paired_scenarios);w=int(r.wins);t=int(r.ties);l=int(r.losses)
   if n<6:cn=f'm={m} 对{comparator}只有{n}/6个完整参照配对，胜/平/负为{w}/{t}/{l}，不据此作完整六情景质量结论。';en=f'For m={m}, only {n}/6 scenario pairs had complete numerical references for comparison with {comparator}; wins/ties/losses were {w}/{t}/{l}. No six-scenario quality conclusion is supported.'
   elif m>=12 and comparator=='greedy_ils' and w+t>=l:cn=f'm={m} 对Greedy-ILS为{w}/{t}/{l}，满足预先规定的有利迹象条件。仅可称六个探索性情景中出现有利迹象，需要独立验证，不能推翻4.1/4.3。';en=f'At m={m}, Proposed had {w}/{t}/{l} wins/ties/losses against Greedy-ILS. This meets the predeclared exploratory indication rule and requires independent validation; it does not overturn the earlier evaluations.'
   elif w+t<l and comparator in ['greedy_ils','ue_bibeam']:cn=f'm={m} 对{comparator}为{w}/{t}/{l}，在这个已检验规模未显示对该UE-only搜索的净优势。';en=f'At m={m}, wins/ties/losses against {comparator} were {w}/{t}/{l}, providing no evidence of a net advantage over this UE-only comparator at the tested size.'
   else:cn=f'm={m} 对{comparator}为{w}/{t}/{l}，只作逐对照描述，不推导总体优势。';en=f'At m={m}, wins/ties/losses against {comparator} were {w}/{t}/{l}; this is a descriptive comparison rather than a general superiority claim.'
   interpretation.append(cn);english.append(en)
 textinterp='\n\n'.join(interpretation)
 envfail=d[d.failure_class=='environment_interference'];envnote=f'另有{len(envfail)}次正式计时内的未知并发Python干扰，任务按保护规则中止，保留部分状态，不能解释为算法本身的规模失败。此类缺失不补零，也不在完整参照产生后补跑或用不同种子替代；相应配对须报告不完整分母。' if len(envfail) else '正式计时内未记录并发环境干扰。'
 interruption=js(OUT/'logs/premeasurement_interruption_audit.json') if (OUT/'logs/premeasurement_interruption_audit.json').exists() else None
 startup_note='一次Proposed启动在ready与正式计时之前因未知并发Python进程被保护规则终止，原monitor/log完整归档，确认没有该情景UE账本或目标后，继续相同任务和种子。该启动不是在线计时观测，不替换任何已测结果。未知进程已退出，未终止其他任务；不对其具体来源或先前影响作推断。' if interruption else '未记录正式计时前的并发启动中断。'
 write(OUT/'analysis/S4_preregistered_interpretation_application.md','# 预冻结解读规则的逐项应用\n\n'+textinterp+'\n\n各比较可能方向不同，必须同时报告。六个情景非新的确认性盲测，没有显著性检验。\n')
 # Extract only this reviewer's Comment4.4; never mix another reviewer's correspondence.
 pdf=Path(r'E:\微信存储\xwechat_files\wxid_x5h5gu0ixjjx21_e4e5\msg\file\2026-10\Review of Surrogate_Guided_Road_Reopening.pdf')
 import pymupdf
 doc=pymupdf.open(pdf);review='\n'.join(p.get_text() for p in doc);doc.close()
 original=review.split('4.4 The architecture retains an exponential scaling bottleneck',1)[1].split('4.5 ',1)[0]
 original='The architecture retains an exponential scaling bottleneck'+original
 for x,y in [('\x1c','fi'),('\x1d','fl'),('\x1b','ff'),('\x1e','ffi')]:original=original.replace(x,y)
 original=re.sub(r'(?m)^\s*[34]\s*$','',original).strip()
 meth='We evaluated six prospectively frozen extended-severity flood inputs on the fixed Sioux Falls network, with 14 initially closed roads and nested recovery sets of 10, 12 and 14 roads. The model weights, 30,000-candidate quotas, shortlist, reserve and correction parameters were fixed. For m≥12, cyclic balanced sampling replaced exhaustive four-road prefix coverage, yielding approximately 45% and 22% coverage; this version is explicitly termed size-adapted Proposed. Proposed, original permutation SA and Greedy-ILS used seed indices 0, 1 and 2, while adapted bidirectional beam was deterministic. Every optimizer received a fresh cache and a cap of 256 unique UE states, including initialization. All optimization outputs were frozen before full-state enumeration. Primary tasks ran sequentially on one physical core, with separate four-core within-scenario enumeration. UE solves used the same path solver and RG≤10⁻⁹. A prospectively frozen 128.8196 s task limit applied to optimization and complete enumeration, with failures retained.'
 boundary='The full-state surrogate and subset-DP architecture retains exponential dependence on the recovery-set size. Fixing the candidate count does not remove this dependence, and reduced prefix coverage is an algorithm adaptation. These six extended-severity inputs provide exploratory evidence on one fixed network, with no significance tests. They do not establish cross-network scalability or overturn the earlier comparison. On the connected 24-node, 38-road benchmark, m≤15 is a necessary topological upper bound; larger recovery sets require larger networks or a different problem definition. Selective subset evaluation and bounded-width search remain future extensions.'
 result_sentences=[]
 for m in [10,12,14]:
  g=summary[summary.m==m].set_index('method');parts=[]
  for method in ['proposed','greedy_ils','ue_bibeam','sa_original']:
   rr=g.loc[method];parts.append(f"{method} {rr.mean_scenario_regret_pct:.4f}% (n={int(rr.conditional_reference_scenarios)})" if pd.notna(rr.mean_scenario_regret_pct) else f'{method} unavailable')
  result_sentences.append(f"At m={m}, mean scenario regrets were "+', '.join(parts)+'.')
 results=' '.join(result_sentences)
 costlines=[]
 for rr in costsummary[costsummary.m==14].itertuples(index=False):
  if pd.notna(rr.Proposed_wall_saving_pct):costlines.append(f"At m=14, the mean time saving relative to {rr.enumeration} was {rr.Proposed_wall_saving_pct:.2f}%, with an enumeration/Proposed ratio of {rr.ratio_of_mean_enum_to_mean_Proposed:.3f}.")
  elif pd.notna(rr.Proposed_wall_saving_lower_bound_pct):costlines.append(f"At m=14, censored {rr.enumeration} runs imply a mean time-saving lower bound of {rr.Proposed_wall_saving_lower_bound_pct:.2f}% and a time-ratio lower bound of {rr.ratio_of_mean_enum_to_mean_Proposed_lower_bound:.3f}; these are not completed enumeration timings.")
  else:costlines.append(f"At m=14, a six-scenario complete time comparison with {rr.enumeration} was unavailable under the frozen resource rule; individual observations and failures are retained.")
 costtext=' '.join(costlines)
 write(OUT/'manuscript/4.4_正文替换与中文核对.md',f'''# 4.4正文替换草稿与中文核对

状态为draft_with_placeholders。原Word未修改。以下是拟替换段落，全文段落位置、删改压缩和最终页行需整合时核对，不声称已写入正文。

## Methods replacement draft

{meth}

## Results replacement draft

{results} {costtext}

## Scope and limitation replacement draft

{boundary}

## 中文核对

{textinterp}

完整枚举单核完成{gate['serial_tables_complete']}/18，四核完成{gate['parallel_tables_complete']}/18，可用条件精确参照{gate['conditional_references_available']}/18。超时或失败不删情景，不能把部分表或共同best-known称为exact。数值等价阈值沿用4.2经验κ，不是数学误差上界，未新增m14的RG1e-11精度实验。固定B对应25%/6.25%/1.5625%的状态比例，m变化也改变目标与代理输入分布，不能把所有效果变化归因于规模。

## Evidence placement and compression record

指数复杂度和范围边界为qualification，正文保留简短替换。规模质量/成本是necessary_support，主结果表保留关键对照，逐次账本、种子、时间上限、分项与失败归档为provenance_detail，放SI/数据。替换而非追加既有scalability段落。原段落字数与最终修订标记需全文整合，不虚构完成。

AUTHOR_INPUT_NEEDED为最终正文/SI表号及页行。已有独立输出表可核对，原Word红字/clean副本尚未生成。
''')
 reply=f'''# Reviewer 1 Comment4.4 response draft

Readiness is draft_with_placeholders. Computational evidence is supplied. Full manuscript integration, supplementary numbering and final page/line locations remain AUTHOR_INPUT_NEEDED. No submission-ready claim is made.

## Original comment

{original}

## Response

We agree that the architecture retains exponential dependence on the number of restoration candidates. Predicting every subset requires 2^m states, while each subset-DP policy takes O(m·2^m) time and O(2^m) space. The implemented preparation also repeats 89 DP computations and retains multiple policies. Candidate screening has additional sequence-length and Kendall-orientation costs. A fixed UE budget therefore does not imply constant total runtime or a polynomial algorithm.

We completed a frozen scaling experiment on six extended-severity flood inputs with nested m=10,12,14 recovery sets. There were {gate['optimization_passed']} completed optimizations out of 180 planned runs, with all failures retained. Weights, budget and correction parameters were fixed. The size-adapted implementation retains 30,000 candidates and fixed source quotas; m≥12 no longer enumerates all four-road prefixes, with approximately 45%/22% sampled-prefix coverage at m=12 and m=14. The original m=10 behavior passed its prior regression gate, and every completed new Proposed run reproduced its frozen component-stage candidate ordering and proxy matrix.

{results}

{' '.join(english)}

{costtext}

Optimization outputs were hashed before any full-state reference calculation. Complete reference tables were obtained for {gate['conditional_references_available']}/18 scenario-size pairs under the frozen resource policy, with {gate['serial_tables_complete']}/18 serial and {gate['parallel_tables_complete']}/18 four-core enumerations completed. Overlapping serial/parallel states matched bit for bit. Missing complete tables are explicitly distinguished from best-observed solutions, and censored timings are not reported as completed totals. Regret is conditional on the finite RG-converged numerical table, and empirical numerical equivalence is not a rigorous UE error certificate.

The proposed scope replacement is

*{boundary}*

The proposed Methods and Results replacements and complete numerical tables accompany this draft. AUTHOR_INPUT_NEEDED remains for their final manuscript and SI locations. The experiment is exploratory, retains unfavorable comparator results and includes no significance tests.
'''
 assert 'Reviewer 2' not in reply and 'R2.' not in reply
 write(OUT/'manuscript/Reviewer1_Comment4.4_回复草稿.md',reply)
 report=f'''# 4.4 S4数值模拟与中文核对

更新于2026年10月29日。6个既定扩展强灾情景4401至4406，m10/12/14，共180次优化均已尝试。完成{gate['optimization_passed']}，失败保留{gate['optimization_failed_retained']}。单核完整枚举完成{gate['serial_tables_complete']}/18，情景内四核完成{gate['parallel_tables_complete']}/18，可用完整条件参照{gate['conditional_references_available']}/18。原模型、正式权重、第一批源码与结果未覆盖。

{envnote}

## 主结果

{md(display)}

每个随机方法先平均3个固定种子，再在完整情景上作描述性均值、中位数和最大值；表中最大regret是情景均值的最大值，各单种子值见逐次表。Beam每情景每规模仅1次确定性运行。缺失参照/资源失败的分母逐项列出，空白不是0。不同分母的总均值不能直接排名，算法比较以逐情景配对为准，时间与质量配对的分母可能不同，均分别给出。没有显著性检验。数值等价命中使用沿用的经验κ={KAPPA:.17g}，不是精确0 regret判据。

## 配对解读

{textinterp}

## m14及枚举成本

{md(costsummary)}

时间比采用相同6情景的均值之比。完整单核/四核配置分开，四核不与单核混合。发生超时时，完整耗时只知大于128.819619278秒，不能用超时实测当作完整总耗时；相应节省只能报告下界。原资源规则没有为了得到完整表而临时放宽。

## 计费、数值和信息防火墙

全部180项预定优化先运行或记录中止并哈希封存，之后才开始完整状态计算。每次优化重建独立PhysicalStore，无物理缓存复用，唯一查询上限256。Greedy初始化55/78/105状态已计入预算；D_local_search、restart与其他phase的新增状态分别列出，不能把总剩余预算全叫LS消耗。64/128检查点若无完整解则留空。SA按原自然停止保留实际计数。Proposed所有成功运行均核对S3候选/代理矩阵哈希，无新增调参或训练。

UE使用4.2同一个path_column_generation_pairwise求解器，RG≤1e-9、固定干态TSTT归一化。每个状态cold assignment。完整条件DP使用R0至R(m−1)的m项均值，终态不计。独立DP与最终序列数值重算经过核验；单核/四核重叠状态逐位一致，共{gate['table_overlap_bitwise_rows']}个mask配对。完整表不存在时只提供共同best-observed差距，不提供exact regret或hit。

## 计时与内存口径

所有主计时一个计算进程CPU0、计算线程1，一次只跑一个任务。父进程在CPU8监测，未执行额外UE。四核阶段每次仅一个情景，四个独立mask块分别在CPU0/2/4/6，池启动/JIT单独记录并排除在线计时。单任务上限在取得S4结果前按S3 m14平均准备时间12.8819619278秒×10冻结，包含完整枚举。没有通过切块重启同一单核表绕过该上限。

在线包含候选、UE、搜索管理和条件DP；输入加载/JIT/CSV导出排除。候选包含推理和89个proxy DP，LS包含UE，分项均提供扣除嵌套项的列，不能重复累加。为了保留失败现场，每个完成UE写入轻量CSV journal，其写入成本包含在在线/管理计时中。候选覆盖率和hash统计也包含测量开销。局部搜索沿用原邻域，任意交换和插入的出发位限定前5位，相邻交换仍覆盖整个序列，不能将其简写为所有移动都仅在前5位内。没有锁CPU频率或保证OS绝对空闲，不按速度删重或补跑。报告CPU工作时间与墙钟供检查。

{startup_note}

峰值RSS是名义50ms采样的计算进程树观测最大值，分别给在线和整个生命周期窗口；含解释器、模型及临时Python对象，不是纯代理矩阵大小。四核RSS为协调器加四个worker，求和可能重复计算共享DLL页，不等同于系统唯一物理RAM或PSS。采样最大值不保证捕捉连续瞬时峰值；超时任务内存仅为已观测范围。四核在线包含worker物理输入重建、调度和返回开销，bulk网络加载、池启动及JIT在计时前，分项不是纯UE内核耗时。四个mask块采用冻结的连续区间划分，没有优化负载均衡。物理journal保留已完成但可能在截止后返回的状态；这些行不能将超时任务改记为完成。

## 结论范围与材料状态

这是6个扩展严重洪水输入的探索性配对规模测试，闭路数由原8至12扩为14，训练主要针对m10。固定B对应25%/6.25%/1.5625%，前缀抽样、目标长度和分布同时改变，不能作纯规模因果推断。SiouxFalls连通24节点38道路给出m≤15的必要上界，m16不进入S4；更大m需更大网络或改变问题，按需子集和受限宽度搜索仅为未来工作。无论是否出现局部有利迹象，均不撤销4.1/4.3原有证据。

表格和逐次账本已经完成，英文正文替换与Reviewer1单独回复在manuscript目录，均是draft_with_placeholders。原Word未改，最终页行/表号及红字/clean全文整合尚未完成。

阅读优先为Table_4_4_S4_main_results.csv、S4_win_tie_loss_by_m.csv、S4_enumeration_Proposed_cost_summary.csv，再看S4_scale_method_runs.csv及逐次目录。数值压缩包只含CSV/CSV.GZ，不再打包代码、模型或稿件材料。
'''
 write(OUT/'final_CN_report.md',report)
 write(OUT/'README_数值结果阅读.md','先看final_CN_report.md。analysis目录包含逐次运行、情景均值、按规模汇总、配对差、胜平负、完整参照和时间比。optimization保留180个独立账本；enum_serial和enum_4core保留完整或部分状态及原始日志。00_lock保留冻结协议与补充细则。数字压缩包只含CSV/CSV.GZ；各资源失败和缺失参照保持原样，不补0。原Word未改，稿件替换与回复为待整合草稿。\n')
 csv(OUT/'analysis/S4_frozen_physical_inputs.csv',frame(SCALE/'02_scenarios/extended_severity_physical.csv'))
 selections=[]
 for sid in range(4401,4407):
  for m in [10,12,14]:
   _,roads,_,_=physical(sid,m);selections.append({'scenario_id':sid,'m':m,'nested_recoverable_roads':seq_string(roads),'score_reference_closed_roads':14})
 csv(OUT/'analysis/S4_nested_road_sets.csv',selections)
 if interruption:
  archived=Path(interruption['all_original_attempt_files_retained']);mon=js(archived/'monitor.json')
  csv(OUT/'analysis/S4_pre_timing_interruptions.csv',[{'scenario_id':4405,'m':10,'method':'proposed','replicate':1,'reason':mon['resource_stop'],'startup_elapsed_s':mon['parent_wall_including_setup_export'],'online_timing_started':False,'experiment_UE_rows':0,'same_scheduled_task_resumed':True,'original_files_retained':str(archived),'included_in_online_averages':False}])
 paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name.endswith(('.csv','.csv.gz')) and p.name!='numerical_files_index.csv')
 csv(OUT/'analysis/numerical_files_index.csv',[{'relative_path':str(p.relative_to(OUT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]);paths.append(OUT/'analysis/numerical_files_index.csv')
 package=OUT/'4.4_S4数值结果_优化与完整参照_20261029.zip'
 with zipfile.ZipFile(package,'w',allowZip64=True) as z:
  for p in paths:z.write(p,str(p.relative_to(OUT)).replace('\\','/'),compress_type=zipfile.ZIP_STORED if p.name.endswith('.gz') else zipfile.ZIP_DEFLATED,compresslevel=6)
 with zipfile.ZipFile(package) as z:assert z.testzip() is None and all(x.endswith(('.csv','.csv.gz')) for x in z.namelist())
 integrity={'path':str(package),'bytes':package.stat().st_size,'files':len(paths),'SHA256':sha(package),'CRC':'PASS','numeric_only':True};dump(OUT/'numeric_package_integrity.json',integrity)
 write(SCALE/'4.4_S4_结果入口_20261029.md',f'# 4.4最新S4结果\n\n第一批报告和completion_check是阶段历史快照，保留原样。第二批结果在 `{OUT}`。\n\n中文报告 `{OUT / "final_CN_report.md"}`。主数值表 `{OUT / "analysis/Table_4_4_S4_main_results.csv"}`。数值压缩包 `{package}`。\n\n优化完成{gate["optimization_passed"]}/180；完整条件参照{gate["conditional_references_available"]}/18。资源失败和缺失保持可见。Word整合仍未完成。\n')
 gate.update({'numeric_package_CRC':'PASS','numerical_files':len(paths),'reviewer_quote_extracted':True,'reviewer_isolation':'PASS','Word_integration_pending':True,'readiness':'draft_with_placeholders','final_at':now()});dump(OUT/'completion_check.json',gate)
 manifest={str(p.relative_to(OUT)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file() and 'runtime_cache' not in p.parts and '__pycache__' not in p.parts and p.name not in ['manifest.json','checksums.sha256']}
 dump(OUT/'manifest.json',{'at':now(),'files':manifest});write(OUT/'checksums.sha256','\n'.join(f"{v['sha256']}  {k}" for k,v in sorted(manifest.items()))+'\n')
 print(json.dumps(integrity,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
