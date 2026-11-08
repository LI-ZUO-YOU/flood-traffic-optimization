from common43 import *
import zipfile,re,math,io,csv as csvmod,ast,shutil

def md(d):
 columns=list(d.columns);out=['| '+' | '.join(map(str,columns))+' |','| '+' | '.join(['---']*len(columns))+' |']
 for row in d.itertuples(index=False,name=None):out.append('| '+' | '.join(('不适用' if isinstance(x,float) and math.isnan(x) else f'{x:.6g}' if isinstance(x,float) else str(x)).replace('|',' / ') for x in row)+' |')
 return '\n'.join(out)
def write(p,t):Path(p).write_text(t,encoding='utf-8')

def main():
 A=OUT/'06_analysis';M=OUT/'07_manuscript_and_response';O=OUT/'05_offline_cost'
 summary=js(A/'analysis_summary.json');methods=frame(A/'S2_method_summary.csv').set_index('method');pairs=frame(A/'S2_paired_time_comparisons.csv').set_index('comparator')
 offline=js(O/'offline_summary.json');cross=frame(O/'S3_amortization_scenarios.csv');components=frame(A/'S2_component_summary.csv').set_index('method')
 noise=js(OUT/'02_serial_B256/S2_noise_summary.json');trainrep=js(O/'temporary_training_replication_acceptance.json')
 assert trainrep['identical_checkpoint_SHA256']==10 and noise['median_sensitivity_all_directions_unchanged']
 assert js(OUT/'logs/offline_completion.json')['status']=='COMPLETE'
 p=methods.loc['proposed'];enum=methods.loc['enum_serial'];e4=methods.loc['enum_within_scenario_4core'];sa=methods.loc['sa_original'];greedy=methods.loc['greedy_ils'];beam=methods.loc['ue_bibeam']
 C=offline['same_host_measured_component_sum'];c=components.loc['proposed']
 write(O/'S3_training_timing_provenance.md',f'''# 离线成本计时来源

本轮在与主实验相同的CPU0、单进程、计算线程限制为1的条件下，测量3178个原训练状态的当前RG1e-9求解成本，并在独立临时目录调用原始十成员训练函数。训练函数、原bootstrap、初始化种子、预处理数值、早停及原始训练标签均保留。临时模型不用于任何4.1或4.3决策，也不覆盖正式冻结模型。

当前状态制样成本为 {offline['current_state_generation_wall']:.6f} 秒；特征和bootstrap处理 {offline['preprocessing_wall']:.6f} 秒；原标签十成员完整函数循环耗时 {offline['temporary_original_label_training_outer_wall']:.6f} 秒。成员内部计时总和 {offline['current_training_member_internal_sum']:.6f} 秒是外层循环的嵌套指标，不再次累加。

加上数据读取后，当前同机器分项估计为 {C:.6f} 秒。这个值使用“当前高精度标签生成成本测量＋原标签训练时间”，不是把新求解标签直接送入训练的单次端到端部署计时。新标签可能改变模型收敛及早停，因此不能把分项之和冒充完整新标签训练实测。当前实际工作流墙钟 {offline['observed_workflow_wall']:.6f} 秒还包括开发状态预热等研究步骤，也不等同于日常部署成本。

此前52.325225秒是上一轮3178状态的当前求解器制样测量；17.767865秒是历史训练外层循环，硬件记录不充分；70.093091秒为跨背景相加的历史混合估计。三者原样保留，未改称同一次训练耗时。本次同机组件测量取代其作为主要成本假设，但仍明确是分项估计。

每成员epoch、最佳epoch、源种子、真实内部计时、函数总计时和临时检查点hash见 S3_temporary_training_members.csv。十个临时检查点与原冻结文件SHA全部一致，完成epoch和最佳epoch也全部一致，详见 S3_training_replication_identity.csv。研究开发、调参和诊断另建 S3_research_cost_ledger.csv，历史未记录的墙钟留空，不把并发工作量之和写成真实总墙钟。
''')
 write(O/'S3_amortization_assumptions.md',f'''# 时间回本模型假设

部署分项估计 C_offline={C:.10g} 秒。采用 C_Proposed(N)=C_offline+N×平均Proposed在线时间，比较方为N×平均比较方在线时间。只有平均差 t_comparator−t_Proposed>0 才定义 ceil(C_offline/平均差)。95%范围基于30个情景配对均值的bootstrap，条件于当前分项成本估计，并不包含未来训练费用的不确定性。

{md(cross[['comparator','mean_online_saving_comparator_minus_Proposed','arithmetic_mean_crossover_scenarios','crossover_from_CI_high_saving','crossover_from_CI_low_saving','no_finite_positive_mean_crossover']])}

若某差值均值非正，报告当前成本模型下不存在有限正时间回本点；不能给负回本数或改挑有利情景。若置信下限非正，回本范围的上端不应有限化。不同方法决策质量不同，时间交叉不等于同质量的经济回报。

四核枚举使用额外核心，其池启动成本为 {summary['pool_startup_seconds']:.6f} 秒，已在 S3_pool_startup_sensitivity.csv 另加截距，未混入单核主计时。原70.093/(16.733−11.215)约13个情景只保留为历史说明，不能当作本次实测回本，更不能继续使用4.14个情景的状态数算式宣称时间回本。
''')

 # Short replacements; all context-specific final page locations remain explicit.
 intro='For ten recoverable roads, the permutation space contains 10! orders, but stage costs depend only on the restored subset. Caching limits distinct high-fidelity evaluations to 2¹⁰ states, followed by subset dynamic programming. Complete subset evaluation and DP therefore provide the relevant small-instance computational reference.'
 meth='We timed the unchanged frozen methods on scenarios 3001–3030 using their original seed indices 0, 1 and 2; deterministic methods and enumeration were repeated three times. Every primary task ran alone in one process on the same physical core, with computational library threads limited to one and a fresh physical state cache. The query cap was 256 without a wall-clock cutoff; complete enumeration evaluated all 1,024 states. JIT and framework code were prewarmed on development data. Online time includes candidate processing, search, UE and DP but excludes initial input/model loading and disk exports. Nested inference and UE-within-local-search times were not added twice. Every method outcome and query trajectory matched its corresponding frozen run bit for bit. Separately, we timed four-core enumeration within one scenario, with disjoint state chunks and pool startup reported separately.'
 res=f'Under the matched single-core protocol, mean online times were {p.mean_online_wall:.4f} s for Proposed, {sa.mean_online_wall:.4f} s for original SA, {greedy.mean_online_wall:.4f} s for UE-Greedy-ILS, {beam.mean_online_wall:.4f} s for adapted bidirectional beam, and {enum.mean_online_wall:.4f} s for full enumeration plus DP. Four-core within-scenario enumeration averaged {e4.mean_online_wall:.4f} s, a separate resource configuration. The corresponding mean scenario regrets were {p.mean_scenario_regret_pct:.4f}%, {sa.mean_scenario_regret_pct:.4f}%, {greedy.mean_scenario_regret_pct:.4f}%, {beam.mean_scenario_regret_pct:.4f}% and zero for enumeration. Paired time differences and uncertainty are reported by scenario. These timings do not turn a 75% query reduction into a 75% time saving, and time advantages cannot establish decision superiority.'
 disc=f'The 1,024 state solves for a fixed scenario are independent and can be distributed across cores, whereas the frozen surrogate-assisted implementation issues adaptive UE queries sequentially. We therefore report single-core and within-scenario four-core references separately. Current-machine offline components sum to {C:.4f} s, combining measured high-precision state-generation cost with original-label training cost. This is a component estimate, not an end-to-end retraining run using newly generated labels. Mean time crossovers are conditional on that estimate, model reuse and a positive online time saving; they are not quality-matched cost-effectiveness results. Research development and numerical audits are reported separately.'
 write(M/'S4_正文替换与中文核对.md',f'''# 4.3 正文替换与中文核对

状态为 draft_with_placeholders。本文仅提供可审阅的替换段落、表格与补充材料说明，未合并完整 Word，最终页码及行号为 AUTHOR_INPUT_NEEDED。

## Introduction 计算参照替换

{intro}

## Methods 计时协议替换

{meth}

## Results 在线成本替换

{res}

## Discussion 成本边界替换

{disc}

## 中文核对

主实验严格单核串行，450次都通过数值和轨迹闸口；随机取原前三种子，没有新种子挑选。单情景内部四核枚举不是四情景同时并发，其90次结果单列。原4.1耗时限额组仅作历史补充，不用其中约600次查询的结果冒充B256。未做新的固定12秒实验。当前离线训练复现使用原标签和原函数，仅作为临时成本测量；正式模型未替换。

## 证据分配与删改记录

| 结果 | 作用 | 放置与操作 |
| --- | --- | --- |
| m!、2^m、DP复杂度 | 核心参照修正 | 替换Introduction/Methods夸大的逐排列UE计费叙述 |
| 统一B256单核计时和质量 | 核心成本证据 | Results主表及情景配对区间 |
| 单情景四核枚举 | 改变资源比较解释 | Results明确单列，不能埋入SI或混入单核均值 |
| 各阶段原始嵌套时间与冷启动 | 实现与稳健性细节 | SI/source data，不重复主表全部数值 |
| 离线分项和回本假设 | 结论边界 | Discussion简述，完整曲线及研究台账留SI |

建议替换而非把旧4.14回本及不配对旧计时保留后再追加新数字。当前段落分别为 {len(intro.split())}、{len(meth.split())}、{len(res.split())}、{len(disc.split())} 英文词。实际Word整段前后字数、重复主张和修订标记仍需全文整合时核查，未虚构已经完成。
''')
 # A standalone response to one comment, preserving its original wording.
 pdf=Path(r'E:\微信存储\xwechat_files\wxid_x5h5gu0ixjjx21_e4e5\msg\file\2026-10\Review of Surrogate_Guided_Road_Reopening.pdf')
 import pymupdf
 doc=pymupdf.open(pdf);text='\n'.join(page.get_text() for page in doc)
 original=text.split('4.3 The computational reference should exploit subset structure')[1].split('4.4 The architecture retains an exponential scaling bottleneck')[0].strip()
 for a,b in [('\x1c','fi'),('\x1d','fl'),('\x1b','ff'),('\x1e','ffi')]:original=original.replace(a,b)
 original=re.sub(r'(?m)^\s*3\s*$','',original).replace('210 states','2^10 states').replace('O(m2m)','O(m·2^m)')
 crosslines=[]
 for r in cross.itertuples(index=False):
  outcome='no finite positive mean crossover' if r.no_finite_positive_mean_crossover else f'arithmetic mean crossover at {int(r.arithmetic_mean_crossover_scenarios)} scenarios'
  crosslines.append(f"For {r.comparator}, the paired mean comparator-minus-Proposed time is {r.mean_online_saving_comparator_minus_Proposed:.4f} s, giving {outcome} under the stated component-cost model.")
 reply=f'''# Reviewer 1 Comment 4.3 response draft

Readiness is draft_with_placeholders. The computations and supplied replacements are complete; final manuscript integration, supplementary numbering and page/line locations remain AUTHOR_INPUT_NEEDED.

## Original comment

The computational reference should exploit subset structure

{original}

## Response

We agree that the relevant high-fidelity reference is cached subset evaluation followed by DP, not independent UE evaluation of all permutations. For ten roads there are 1,024 states and 5,120 single-road predecessor candidates, with O(m2^m) DP time and O(2^m) storage. Our measured reference retains all 1,024 states, including the zero-weight terminal state. The 75% value is restricted to the reduction from 1,024 to 256 unique queries and is not described as a measured time saving.

We completed 450 isolated primary timing tasks on the same physical core, using fresh physical caches, one active computational thread, unchanged RG≤10⁻⁹ path assignment and no wall-clock cutoff. Original SA, UE-Greedy-ILS and Proposed use the first three original frozen seed indices; adapted bidirectional beam and enumeration each have three repetitions per scenario. All 360 method runs matched the corresponding 4.1 frozen objectives bit for bit, the final permutations, actual queries and logical trajectories. The 90 serial enumeration references also matched their frozen DP objectives and sequences. Setup and exports are separately recorded; surrogate inference is nested within candidate processing and UE is nested within LS, so neither is counted twice in the additive components.

{res}

The independent state solves also allow within-scenario parallel enumeration. We therefore performed 90 additional measurements with four workers on four distinct physical cores, one scenario at a time, which is different from running four scenarios concurrently. State dispatch, returned values and DP are included in online wall time; the warm pool startup of {summary['pool_startup_seconds']:.4f} s is recorded separately. These timings are explicitly labelled as a four-core comparator rather than mixed with the single-core experiment. Five prespecified fresh-Python-process supplements on scenario 3001 document import, input/model loading and first-use compiled-cache overhead; they are not used to generalize cold latency across scenarios.

We separately measured current-hardware cost for all 3,178 original training states and reproduced the original ten-member training functions, seeds, bootstrap, preprocessing and labels in a temporary directory. Official model files were unchanged and the temporary models were not used for decisions. The measured component sum is {C:.4f} s. Because the new high-precision generated labels were not substituted into the original-label training replication, this is a same-host component estimate, not a single end-to-end new-label training wall time. The prior 52.325 s label-cost measurement, historical 17.768 s training loop and 70.093 s mixed estimate remain identified by their distinct provenance.

{' '.join(crosslines)} Timing confidence ranges use paired scenario means, with seeds nested within scenarios. These crossover calculations assume reuse and different methods have different decision quality, so they are not equal-quality economic comparisons. Research development, tuning and diagnostic work are reported in a separate ledger; missing historical elapsed times are not invented. The old 4.14-state-count break-even argument is replaced by this conditional time accounting.

No new fixed 12 s experiment was added. The prior scenario-specific time-cap group is retained only as a separately labelled supplement and never substituted for B=256 timings. No flood generator, optimizer, formal model weights or search parameters were changed for speed. All ten temporary checkpoint files and epoch selections matched the original training records exactly. Residual system variability is disclosed, including {noise['flagged_primary_runs']} primary observations with process CPU time below 85% of online wall time. None was removed. The median-of-three sensitivity retains the same paired time-difference directions in all comparisons, as documented separately.

The supplied Methods replacement is

*{meth}*

## 中文核对

主要新增证据为同批、单核、独立空缓存B256计时。四核枚举采用情景内部并行并单列资源。所有不利结果与实际自然停止均保留。回本只在正节时与明确离线成本假设下定义，原混合估计不改称真实端到端训练。原完整Word尚未整合。
'''
 write(M/'Reviewer1_Comment4.3_回复草稿.md',reply)
 assert not re.search(r'Reviewer\s*2|R2\.',reply,re.I) and '*'+meth+'*' in reply
 # Numeric master table used by the prose, without invented manuscript numbering.
 csv(M/'Table_4_3_Fresh_state_timing_and_decision_quality.csv',methods.reset_index())
 write(OUT/'final_CN_report.md',f'''# 审稿人1第4.3条计算效率与成本核算

已完成S0–S5的计时、成本核算及英文替换/回复草稿。原冻结算法、权重、场景和历史账本未改；尚未合并完整Word稿件，不能视为完整论文已提交返修。

## 本次新增证据的范围

主实验450次，全部单进程、单物理核、计算线程限制为1，任一时刻只执行一个主任务。随机算法严格使用原4.1前三种子，确定性方法重复3次；全部目标、最终序列、查询数及逻辑轨迹通过逐位一致闸口。所有查询预算方法均为B256且没有墙钟截断，自然提前停止按实际数保留。

另有单情景内部四核枚举90次，不与旧的“四情景同时并发”混淆。全部完整枚举值和序列与冻结参考逐位一致。冷启动补充固定情景3001、rep0各方法一次；未做新固定12秒组。

## 主要计时和质量结果

{md(methods.reset_index()[['method','cores','mean_online_wall','median_scenario_online_wall','P90_scenario_online_wall','mean_scenario_regret_pct','mean_UE_queries']])}

表中耗时单位为秒，regret单位为%。先情景内平均3次，再跨30情景汇总。本轮采用原预设前三个种子的计时只是既有算法的运行成本复现，不叫独立新泛化验证。完整枚举用1024状态；其余B256。四核组使用额外资源，单列显示。

## 情景配对差及不确定性

{md(pairs.reset_index()[['comparator','mean_time_difference_comparator_minus_Proposed','CI95_mean_low','CI95_mean_high','cases_Proposed_faster','cases_Proposed_slower']])}

差值为比较方减Proposed，正数代表Proposed更快，负数代表比较方更快。区间为30个情景均值的配对bootstrap20,000次，重复种子是嵌套测量，不当作90个独立情景。区间为描述性名义95%范围，不作为新的确认性算法优越性检验。

有 {noise['flagged_primary_runs']}/450 次主计时的进程CPU工作时间占比低于0.85，最低为 {noise['minimum_process_CPU_over_wall']:.6f}，作为残余调度/阻塞噪声标记。该指标不能确定具体后台程序或频率原因，未据此删除或重测运行。以每情景三次中位数替代三次均值的描述性敏感性表中，所有配对时间差方向保持一致。没有把单任务调度说成操作系统绝对无背景活动。

## 分项与离线成本

Proposed候选构造/筛选排除推理后均值 {c.candidate_construction_screening_excluding_inference:.6f} 秒，推理 {c.surrogate_inference:.6f} 秒，UE网络调用 {c.UE_network_calls:.6f} 秒，LS排除UE后的计算 {c.LS_computation_excluding_UE:.6f} 秒，其他 {c.other:.6f} 秒。嵌套诊断指标保留原始值，但不再累加。DP分项仅指完整高保真参考的DP，Proposed内部代理subset-DP已包含在候选处理时长中。

当前硬件部署分项估计为 {C:.6f} 秒。其完整来源见05_offline_cost，原标签临时训练与新高精度标签制样成本分别实测，不冒充一个新标签到模型的端到端训练计时。研究成本另外记录，历史缺失墙钟保留空白。以下回本只是在该成本假设下的算术模型，不等同于决策质量匹配或经济回报。

{md(cross[['comparator','mean_online_saving_comparator_minus_Proposed','arithmetic_mean_crossover_scenarios','no_finite_positive_mean_crossover']])}

若配对差均值非正，不存在有限正时间回本点。若置信下限非正，上端回本范围不设有限值。四核池启动和小批量敏感性另表。75%只保留为查询数减少，4.14只作为旧的状态数算式，不作时间结论。

## 计算参照与边界

十路有10!个排列，但至多2^10种状态。实际DP前驱候选5120，时间O(m2^m)、空间O(2^m)。全状态枚举能在多核内并行，自适应Proposed本实现串行查询，这个对Proposed可能不利的资源差异完整报告。主计时排除初始加载、JIT预热和磁盘导出，其耗时另列；OS原电源方案保留，未把CPU频率锁为常数。

## 文件导航

- 00_protocol_and_input_audit：预冻结协议、方法/种子/顺序、原资料SHA及限制。
- 02_serial_B256：450次原始时间、360次查询预算算法账本、90次单核全状态表、分项和中期验收。
- 03_enum_within_scenario_4core：90次单情景四核枚举状态、进程/核绑定、池启动记录。
- 04_cold_start：预设单情景冷进程补充，不混入主表。
- 05_offline_cost：3178状态、原训练函数临时复现、回本曲线、研究成本台账；临时模型不参与决策。
- 06_analysis：情景均值、配对差、bootstrap区间及完整方法汇总。
- 07_manuscript_and_response：英文正文替换、正文数值表和单条审稿回复草稿。

按用户要求，最终仅将CSV及CSV.GZ数值结果打包，报告、代码、回复和临时模型留在目录，不再打包整套材料。
''')
 # Final gates and source immutability, including all added offline sources.
 source_count=verify_sources();offmanifest=js(O/'offline_input_freeze.json')
 for path,h in offmanifest['source_hashes'].items():assert sha(path)==h
 assert summary['all_primary_intervals_nonoverlapping'] and summary['all_primary_on_one_core'] and summary['all_components_add_without_nested_double_count']
 assert not summary['new_fixed12s_experiment']
 for f in (OUT/'code').glob('*.py'):ast.parse(f.read_text(encoding='utf-8'),filename=str(f))
 dump(OUT/'completion_check.json',{'status':'COMPUTATIONAL_COST_AUDIT_COMPLETE_WORD_INTEGRATION_PENDING','primary_single_process_tasks':450,'B256_method_tasks':360,
    'primary_full_enumeration_tasks':90,'within_scenario4core_tasks':90,'cold_process_cases':5,'all_bitwise_gates':'PASS','original_rep_indices':[0,1,2],
    'primary_task_overlap':'NONE','primary_CPU':CORE,'new_fixed12s_group':False,'fresh_state_cache_each_task':True,'same_UE_RG':1e-9,
    'nested_component_double_count':'NONE','source_hashes_rechecked':source_count,'formal_models_unchanged':True,'temporary_training_only':True,
    'offline_cost_scope':'same-host measured component estimate; original labels retained','end_to_end_new_label_training_claimed':False,
    'full_enumeration_tables_bitwise_checked':180,'full_enumeration_state_pairs_bitwise_checked':184320,
    'temporary_checkpoint_SHA256_identical_to_original':10,'primary_noise_flags_retained':noise['flagged_primary_runs'],'median_sensitivity_directions_stable':True,
    'full_Word_manuscript_modified':False,'reply_readiness':'draft_with_placeholders','reviewer_isolation':'PASS','quoted_replacement_consistency':'PASS'})
 # CSV-only delivery. The full scientific raw timing numerics are included;
 # temporary checkpoint binaries, prose and source code are not archived.
 archive=OUT/'4.3数值结果_单核串行与情景内四核_20261028.zip'
 dirs=['02_serial_B256','03_enum_within_scenario_4core','04_cold_start','05_offline_cost','06_analysis']
 files=sorted(set(f for folder in dirs for f in (OUT/folder).rglob('*') if f.is_file() and (f.name.endswith('.csv') or f.name.endswith('.csv.gz'))))
 files.append(M/'Table_4_3_Fresh_state_timing_and_decision_quality.csv')
 index=io.StringIO(newline='');writer=csvmod.writer(index);writer.writerow(['file','bytes','SHA256'])
 for f in files:writer.writerow([f.relative_to(OUT).as_posix(),f.stat().st_size,sha(f)])
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for f in files:z.write(f,f.relative_to(OUT).as_posix())
  z.writestr('00_数值文件索引.csv',index.getvalue().encode('utf-8-sig'))
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(n.endswith(('.csv','.csv.gz')) for n in z.namelist())
 dump(OUT/'numeric_package_integrity.json',{'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'files':len(files)+1,'CRC':'PASS','numeric_only':True})
 filelist=sorted(f for f in OUT.rglob('*') if f.is_file() and 'runtime_cache' not in f.parts and '__pycache__' not in f.parts and f.name!='checksums.sha256')
 write(OUT/'checksums.sha256','\n'.join(sha(f)+'  '+f.relative_to(OUT).as_posix() for f in filelist)+'\n')
 print('FINAL4.3 COMPLETE',archive,'bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
