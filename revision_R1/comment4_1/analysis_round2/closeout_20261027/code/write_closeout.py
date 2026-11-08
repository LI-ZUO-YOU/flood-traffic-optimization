"""Compose evidence-grounded closing reports from completed trace audits."""
import sys,json,re,zipfile,ast
from pathlib import Path
P=Path(__file__).resolve().parents[1];ROUND=P.parent
sys.path.insert(0,str(ROUND/'code'))
from common import frame,dump,sha,verify_manifest

def write(name,text):
    f=P/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8')
def md(d):
    cols=list(d.columns)
    lines=['| '+' | '.join(map(str,cols))+' |','| '+' | '.join(['---']*len(cols))+' |']
    for row in d.itertuples(index=False,name=None):
        vals=[f'{x:.4f}' if isinstance(x,float) else str(x) for x in row]
        lines.append('| '+' | '.join(v.replace('|',' / ') for v in vals)+' |')
    return '\n'.join(lines)

def main():
    run=frame(P/'case_run_summary.csv');pre=frame(P/'case_prefix_survival.csv');phase=frame(P/'case_phase_queries.csv')
    paths=frame(P/'case_target_paths.csv');ev=frame(P/'case_sequence_events.csv');gate=frame(P/'case_primary_seed_gate.csv')
    budget=frame(P/'start_budget_audit.csv');alias=frame(P/'proxy_alias_identity_300.csv')
    claim=json.loads((P/'final_opinion_numeric_recheck.json').read_text(encoding='utf-8'))
    fair=json.loads((P/'LS_code_fairness.json').read_text(encoding='utf-8'))
    assert len(run)==20 and len(alias)==300 and len(budget)==630
    assert alias[['same_initial_sequence','same_final_objective_bitwise_and_sequence','same_all_request_events','same_unique_query_order_phase_reason']].all().all()
    summary=run.groupby('scenario_id',as_index=False)[['pool_best_regret_pct','screened_best_regret_pct','first_pre_LS_regret_pct','final_regret_pct','direct_within_LS_reduction_pp','LS_unique_queries']].mean()
    write('01_3026与3029逐阶段核查.md',f'''# 3026、3029 逐阶段失败核查

这是对两个指定失败案例各十次既有回放的事后轨迹核查。没有新情景、没有方法重跑、没有新 UE 求解。表格均先在情景内汇总十种子，不将两例的二十次运行当作二十个独立洪水样本。

## 首先区分三种证据

候选池的 oracle 最小值只约束该固定集合，不约束能生成新排列的 LS。这里的“最优兼容前缀”表示固定该有序前缀、允许用原 1,024 状态表及 DP 选择其余道路后，可以达到数值等价最优；它不表示池中已经存在具有这个前缀的最优完整排列。两个案例的规范 DP 完整排列在原池中均未出现，但前四路前缀在每个池中均存在。

查询的“最优路径兼容”则只表示某个恢复子集能够出现在至少一条数值等价最优路径上，既不固定该子集的到达顺序，也不表示该查询实际改善了决策。不能把不在一条规范路径上的查询都称为浪费。

## 总体数值

{md(summary)}

各列单位为 regret % 或百分点，LS_unique_queries 是 LS 阶段首次获知的唯一状态数。完整逐种子数据见 case_run_summary.csv。

## 3026 的损失链

规范最优序列为 `29|19|14|17|15|28|26|13|12|24`，纯 UE 贪婪恰好得到同一序列。原池每次都覆盖其前 1–4 路前缀，但原池最好完整序列平均仍为 0.2555% regret。

筛选后，primary 在 10/10 次保留最优首路 29，但最优二路、三路、四路前缀只分别出现在 3/10、1/10、1/10 次。reserve 连最优首路 29 都未保留，前 1–4 路的最优兼容前缀均为 0/10。

更具体的问题位于补全队列的准入规则。build_seed_queue 只从 reserve 的前三路前缀建立 p3_rank，随后仅接纳 p3 位于该排名表的 primary 候选。因而 primary 并非只要保留就一定能够被在线补全。在本例，primary 中仍有最优兼容前缀的序列，全部未通过这个前三路条件，实际补全阶段也未访问这些序列，见 case_primary_seed_gate.csv。

实际 C 阶段十次共补全 590 条不同运行内候选，全部以 `28|14` 开头，只分布在 `28|14|17` 与 `28|14|29` 两个三路前缀。平均每次用于 C 的新状态为 103.0，LS 为 99.4。固定第一路为 28，即使后续允许用 oracle DP 最优完成，最低 regret 也已为 6.048153%。最终十次全部停在 `28|14|17|19|15|29|26|13|12|24`，恰好达到这一“固定首路”的条件界限。因此剩余误差主要来自无法有效改变早期构造，而不是末段排列仍未排好。

LS 并非完全没有尝试首路 29。十次运行分别评价了 5–6 条以 29 开头的完整邻居，其最好 regret 均为 7.677638%，反而高于 6.048153%。这些不利的完整邻居未成为更好的父序列，未形成继续改进到最优早期前缀的轨迹。这里只能据此说明已执行的邻域与父序列选择没有跨越这个障碍，不能宣称已证明局部最优，也不能证明改变邻域后一定成功。

直接 LS 改善平均仅 0.006229 个百分点。平均 494.2 条不同完整 LS 序列中，只有 0.9 条刷新全局 incumbent；99.4 个 LS 新状态中，98.9 个归属到当次未刷新 incumbent 的完整序列。这个比例描述低即时改善率，不是无价值信息的严格定义。

## 3029 的损失链

规范最优序列为 `26|15|16|28|18|9|6|2|7|14`，纯 UE 贪婪同样得到它。原池十次全部覆盖最优前四路前缀，最好完整序列平均 regret 为 0.5896%。

primary 每次保留首路 26，但最优二路前缀只保留 1/10，三路与四路均未保留。reserve 前 1–4 路最优兼容前缀均为 0/10。primary 中具有最优兼容首路的候选也全部未通过 reserve 的 p3 准入，见 case_primary_seed_gate.csv。

十次 C 阶段共补全 639 条序列，全部以 `28|16` 开头，仅有 `28|16|15`、`28|16|2` 两种三路前缀。这个二路前缀即使允许最优后续完成，最低 regret 也为 16.710063%。平均实际首次 LS 入口为 20.522890%，说明候选准入及队列优先级在进入 LS 之前已把预算集中在较差的早期分支。筛选集合中 oracle 最好的候选十次都来自 primary，却十次均未被在线完整评价。

本例 LS 能显著修复，平均直接降低 17.820789 个百分点，最终平均为 2.702101%。但全部最终解仍从道路 28 开始。固定首路 28 的最优后续 regret 为 2.313856%，其中 seed 9 达到了这个固定首路界限，其余运行尚有后段误差。只有 seeds 1、5 曾完整评价以最优首路 26 开头的邻居，各自最好 regret 为 6.643480%、6.903774%，未优于各自最终解。

每运行平均 105.0 个新状态用于 C，103.0 用于 LS。LS 平均评价 646.2 条不同完整序列，11.5 条刷新 incumbent；100.4 个 LS 新状态归属于当次未刷新 incumbent 的完整序列。它表明许多调用用于探索而非即时更新，但不能据此抹去已发生的 17.820789 个百分点改善。

## 预算证据和停止条件

{md(phase.groupby(['scenario_id','phase'],as_index=False)[['unique_queries','any_numeric_optimal_path_compatible_queries','queries_state_best_regret_le_1_5pct','completed_unique_sequences','incumbent_improving_sequences']].mean())}

每个运行各阶段唯一查询之和严格为 256。最优路径兼容性通过前向与后向子集 DP 计算，完整逐状态界见 case_state_conditional_bounds.csv。该判定比“是否命中一条规范路径”宽松；即便如此，也不能将互相兼容的单独子集直接拼成已知的好序列。case_LS_calls.csv 保留了每次 LS 的入口、出口、轮数和实际停止原因，包括达到目标预算时零轮的调用，不能把所有记录都解释为实际开展了一轮搜索。

## 核查结论

两个案例均存在池质量、筛选及补全队列准入的连锁损失。最具体的新发现是 primary 与 reserve 的 p3 耦合，以及实际补全对单一二路前缀的集中。3026 还表现为已执行邻域无法有效改变首路；3029 则能修复大量损失但未稳定找到好首路。以上是可重建的设计缺陷与轨迹描述，不是删除 reserve 的全流程因果消融。本轮保留这些边界，不据此继续开发或调参。
''')

    # Aggregate initialization and query counts by scenario before across-scenario summary.
    bg=budget.groupby(['method','scenario_id'],as_index=False)[['initial_regret_pct','final_regret_pct','initialization_unique_queries','LS_new_unique_queries','actual_unique_queries']].mean()
    table=bg.groupby('method',as_index=False).mean(numeric_only=True).drop(columns='scenario_id')
    table.to_csv(P/'start_initialization_and_budget_summary.csv',index=False,encoding='utf-8-sig')
    write('02_起点消融公平性与合并说明.md',f'''# 起点消融的代码公平性和重复项合并

## 可以核实的部分

1. Greedy-LS、Random-LS 使用 experiment.correction_baseline，代理起点控制使用既有 replay_diagnostics 中的初始化代码。它们实例化同一个 SharedCorrection，直接继承原 BudgetedSearch.local_search；没有另写一个近似 LS。代理轨迹采集子类只在调用前后记录，并通过 super 调用原函数。
2. 邻域完全相同。包含所有相邻交换，以及起始位置在前五位的非相邻交换和插入。后两种并非遍历任意起始位置的完整邻域，不应简写为“无限制全交换和全插入”。
3. 规则相同。每轮使用当前已评价完整序列中最多五个最好父序列，按缺失状态数、是否相邻交换、位置和父序列目标排序邻居。所有已评价序列保留，全局 incumbent 只在目标严格更小时更新；它不是 SA 式的概率接受。
4. 停止条件相同。每次调用到达目标，或连续两轮最佳目标相对提升小于 0.001 / 无可评邻居即停。计数在下次 local_search 调用时重置。统一调用目标为 64、128、256。
5. 总预算相同。各方法具有独立逻辑缓存，首次获知的状态计入同一 256 上限，重复状态免费。贪婪构造固定耗用 55 个唯一状态，代理和随机初始完整序列各耗用 10 个；这些都已包含在总预算，没有给贪婪起点免费 UE。

代码出处、行号和函数 SHA256 见 LS_code_fairness.json，原函数片段见 code/source_excerpt_*.txt。核验覆盖全部 30 条确定性 Greedy-LS、300 条 Random-LS 和 300 条合并后的代理控制查询账本，没有新运行优化器。

## “完全相同”不适用于入口信息

统一函数和总预算不等于仅替换排列、其余信息全部相同。贪婪构造在进入 LS 前已知道 55 个状态，代理/随机只知道初始路径的 10 个状态；贪婪剩余名义上限为 201，代理/随机为 246。三者缓存内容与邻居代价排序因此不同。

还须明确实现细节。SharedCorrection.state_by_hash 记录通过该引擎访问的状态；greedy 构造直接访问 QueryOracle。进入 LS 时，贪婪的额外已知状态已在 QueryOracle 中，但只有初始路径状态登记在引擎的 state_by_hash；后续再访问构造已知状态时仍免费。原 missing_count 使用引擎登记表，因此可能保守高估一个尚未通过引擎访问的候选所需新查询，并影响次序或可容纳判断。该实现对所有起点使用同一函数，但入口历史不同。这里如实记录，不修改冻结实现或重算结果。

因此，可以称为“同一 LS 机制、同一包含初始化成本的总状态预算下的起点策略比较”；不能称为“完全匹配 LS 入口缓存、相同 LS 可用预算、仅有初始排列不同的严格因果消融”。候选生成时间也没有在这张查询预算表中重新计时，不能把代理起点控制当作低耗时替代方案。

## 从初始化到最终质量

{md(table)}

regret 单位为 %，查询均为唯一状态数。先情景内汇总，再跨 30 情景平均。Greedy 为确定性每情景一次，代理/随机为每情景十种子；独立单位均为 30 个情景。十种子不是十次代理重训。

代理初始完整序列平均 regret 约 39.3227%，纯贪婪约 0.4585%。两种初始化的质量差距是真实描述，但不能由本表分离初始化排列、已有状态与后续预算分配的各自贡献。强 LS 大幅修复了代理和随机起点的错误，却没有消除贪婪策略在本批问题上的优势。

## 重复项的核验和合并

两项代理控制不仅汇总指标相同。300/300 次初始序列相同，全部请求事件的请求序号、子集、命中标记、累计唯一查询和阶段完全相同，唯一查询顺序/阶段/原因相同，最终目标逐位相同且最终序列相同。详见 proxy_alias_identity_300.csv。

最终展示表 start_ablation_merged_summary.csv 仅保留三项，UE-Greedy + LS、Proxy Top-1 + LS、Random-start + LS。原两个别名及原始文件继续保留用于追溯，不再把它们当作两项独立消融，也未删除证据。

## 未完成的组件问题

整套 Proposed 仅删除 reserve 的匹配预算消融、十成员 ensemble 换单模型的消融、以及更大恢复规模实验仍未进行。以上核查不替代它们。停止本轮算法开发的理由是现有设定与已揭示样本不足以支持代理的独立优势，而不是认定这些组件在所有场景都无效。
''')

    method_paragraph='The initialization controls use the same inherited local-search implementation, neighborhood, parent selection, stopping rule and cumulative targets of 64, 128 and 256 unique states. Initialization is charged to the common total cap. Greedy construction reveals 55 states, whereas proxy and random initialization reveal ten; the entry caches and remaining allowances therefore differ. The comparison evaluates initialization strategies under a common total state budget, rather than isolating the causal effect of an initial permutation. The two proxy labels have identical starts, complete request paths and final outcomes in all 300 runs and are reported as one control.'
    results_paragraph='Post-hoc trace inspection of scenarios 3026 and 3029 identified a coupling between primary candidates and structural-reserve prefixes. Primary candidates enter the completion queue only when their three-road prefix is represented in the reserve. All completed candidates in these cases shared one two-road prefix per scenario, despite optimal-compatible prefixes remaining in some primary sets. Local search repaired substantial error in 3029 but barely improved 3026. These traces identify a design limitation without establishing the causal benefit of removing the reserve.'
    write('manuscript/正文收尾替换建议.md',f'''# 正文收尾替换建议

状态为 draft_with_placeholders。以下是待合并段落，不声称完整 Word 已修改。拟替换位置为上一轮 Methods 起点控制说明、Results 诊断简述；最终页码和行号为 AUTHOR_INPUT_NEEDED。

## Methods 替换段

{method_paragraph}

## Results 诊断简述替换段

{results_paragraph}

## 中文核对

局部搜索函数、邻域、停止规则与总预算已代码核实，但入口信息不同，不能写成严格只换排列。两个代理名称已合并解释。两个案例的 p3 准入耦合有实际代码和轨迹支持，尚未完成移除 reserve 的全流程因果实验。正文仅保留关键解释，其余逐阶段数字和代码溯源放补充材料。

## 证据分配与压缩记录

| 内容 | 类别 | 放置 | 操作 |
| --- | --- | --- | --- |
| 公用 LS 和入口缓存差异 | qualification | Methods 简述及 SI | 替换已有宽泛“同一 LS 起点消融”说明 |
| 两个代理名称完全重复 | provenance_detail | 方法表脚注、SI | 合并四行表为三行，保留原别名数据 |
| 两例 p3 队列门槛 | edge_case | Results 上述短段与 SI | 替换已有笼统失败解释 |
| 逐阶段查询与 first-road 轨迹 | provenance_detail | SI/source data | 不逐项叠加到正文 |
| 代理独立优势不成立 | core_discovery | 原主结果与结论 | 保留，未因事后分析而改变 |

短证据链为强基线比较、匹配机制及入口边界、失败轨迹、受限结论。原完整 Word 段落未在本轮修改，实际正文前后字数差待整合时核对；不编造压缩字数。新 Methods 段约 {len(method_paragraph.split())} 个英文词，新 Results 段约 {len(results_paragraph.split())} 个英文词。详细数字以 CSV 为唯一完整数值位置，不重复铺陈于正文、图注和结论。
''')
    # Update separate reviewer drafts only in this closing directory.
    r1=(ROUND/'manuscript/Reviewer1_4.1_4.3_4.5_5.1_回复草稿.md').read_text(encoding='utf-8')
    replacement='The closing code audit confirms that greedy, proxy and random initialization use the same inherited local-search function, neighborhoods, parent selection, stopping rule and cumulative query targets. All initialization queries count toward the 256-state cap. Greedy construction uses 55 states and proxy or random initialization ten, so entry information and the remaining LS allowance are not identical. We therefore describe a common-total-budget strategy comparison, not a strict permutation-only causal ablation. The two proxy labels have identical starts, all request events, unique query order and final outcomes in all 300 runs; the closing display merges them. Trace audits of scenarios 3026 and 3029 also show that primary candidates require a reserve-represented three-road prefix to enter the completion queue. This excluded retained optimal-compatible prefixes, while all completed candidates concentrated on one two-road prefix in each case. This is evidence of a design limitation, not a full-method reserve-removal experiment. Full ensemble simplification and controlled whole-method reserve removal remain unresolved.'
    r1=re.sub(r'(## Comment 4\.5\n\n).*?(\n\n## Comment 5\.1)',lambda m:m[1]+replacement+m[2],r1,flags=re.S)
    r1=r1.replace('Full manuscript integration and final numbering are pending.','Full manuscript integration and final numbering are pending. Closing audit evidence is in the separately supplied closeout files; final manuscript page and line locations are AUTHOR_INPUT_NEEDED.')
    write('manuscript/Reviewer1_收尾更新草稿.md',r1)
    r2=(ROUND/'manuscript/Reviewer2_1_6_回复草稿.md').read_text(encoding='utf-8')
    sentence=' The code audit verifies a shared LS implementation and a common total cap including initialization. Because greedy construction reveals more states than proxy or random initialization, these are strategy comparisons with different entry information, not strict permutation-only causal effects. Both proxy labels have identical complete request paths in all 300 runs and are consolidated into one control.'
    r2=r2.replace('These diagnostic differences do not separately identify causal component effects.','These diagnostic differences do not separately identify causal component effects.'+sentence)
    write('manuscript/Reviewer2_收尾更新草稿.md',r2)
    for a,b in [('Reviewer1_收尾更新草稿.md',r'Reviewer\s*2'),('Reviewer2_收尾更新草稿.md',r'Reviewer\s*1')]:
        assert not re.search(b,(P/'manuscript'/a).read_text(encoding='utf-8'),re.I)
    conclusion=(ROUND/'manuscript/S4_重新定位与英文替换段落.md').read_text(encoding='utf-8').split('## Conclusion replacement\n\n')[1].split('\n\n## ')[0].strip()
    assert '*'+conclusion+'*' in r1
    write('03_最后意见复算与验收.md',f'''# 最后意见复算与收尾验收

本次仅执行最后意见建议的两项低成本核查，两项均有可复查数据与代码，未重跑第三轮优化、未调参、未重训、UE 新求解为零。

## 文档数字核对

正筛选损失 {claim['screening_loss_positive_runs']}/300，超过 1 个百分点 {claim['screening_loss_gt1pp_runs']}/300，超过 5 个百分点 {claim['screening_loss_gt5pp_runs']}/300；序列 Spearman 为负 {claim['negative_sequence_spearman_runs']}/300；reserve 与 primary 的并集优于 primary {claim['reserve_union_better_than_primary_runs']}/300。原文数字均复算一致。

最终均值优于首次 LS 入口的情景为 {claim['final_better_than_first_pre_LS_scenarios']}/30，优于筛选集 oracle 均值 {claim['final_better_than_screened_best_scenarios']}/30，优于池 oracle 均值 {claim['final_better_than_pool_best_scenarios']}/30。这里比较的是各情景十种子均值，不表示每个单独种子均满足。

首次 LS 入口至最终平均下降 {claim['first_pre_LS_to_final_mean_reduction_pp']:.6f} 个百分点，但它跨越后续补全和 LS，不应全归于 LS。逐次 LS 调用内直接下降合计的均值仍为上一轮 6.188173 个百分点。筛选损失与最终 regret 的情景层面 Pearson r 为 {claim['screening_final_Pearson_r']:.6f}，仅为事后描述，不建立唯一原因或因果效应。

四进程的每情景时长在 {claim['parallel_slower_than_serial_cases']}/30 个案例均更长，均值增加 {claim['parallel_mean_duration_increase_pct']:.4f}%。此处指单个情景的延迟，不等于整个 30 情景批次更慢。原记录单进程在线时长总和 501.9935 秒，四进程完整批次墙钟 144.8482 秒；范围不同，且单进程整批因技术恢复缺少一次连续墙钟，不计算严格吞吐加速比，也不猜测原因。正文默认展示单进程枚举延迟，四进程作为另列运行模式。

## 两项收尾工作

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 3026、3029 前缀、队列、预算、LS 核查 | VERIFIED_DONE | 01 报告及 case_*.csv |
| LS 实现、邻域、停止与总预算核验 | VERIFIED_DONE | 02 报告、LS_code_fairness.json、start_budget_audit.csv |
| 两个代理起点逐请求去重 | VERIFIED_DONE | 300 条 alias 核验及三行合并汇总表 |
| 最后意见数值复算 | VERIFIED_DONE | final_opinion_numeric_recheck.json |
| 证明代理辅助独立优势 | 未获支持 | 保留原确认性结果，不用事后诊断改写 |
| 完整去 reserve / 单模型消融 | 未进行 | 不能由当前表格替代 |
| 完整 Word 整合、最终页码行号 | 待完成 | 此轮仅交付收尾替换/回复草稿 |

## 收尾决定

停止在已揭示的十路问题上继续优化原 Proposed，不开发 V2。当前证据支持收缩为预算约束下的比较评估和适用边界研究，并明确承认强 UE-only 方法更具竞争力。是否满足目标期刊创新性要求仍须独立判断，不把本次技术验收等同于期刊验收。新的强组件改造或更大规模验证，应作为单独设计的后续研究。
''')
    write('00_收尾总览.md','''# 4.1 收尾结果

已完成“4.1最后意见”建议的两项核查。原确认性结果、上一轮分析和既有完整 ZIP 均未改动。本目录是最后的增补材料，不是第三轮优化实验。

- 两个失败案例的近优前缀损失与预算去向，见 `01_3026与3029逐阶段核查.md`。新定位到 primary 必须满足 reserve 三路前缀准入的耦合，以及补全集中在单一二路前缀。
- 局部搜索的同函数、邻域、停止及总预算已核实，入口缓存与剩余额度不同，不能声称严格只换排列，见 `02_起点消融公平性与合并说明.md`。
- 两项代理控制在全部 300 次运行中连完整请求轨迹都相同，展示时合并。最终数值表为 `start_ablation_merged_summary.csv`，初始化质量和预算另见 `start_initialization_and_budget_summary.csv`。
- 最后意见数字复算、LS 贡献口径及并行延迟/吞吐区别，见 `03_最后意见复算与验收.md`。
- `manuscript/` 提供短替换段及分审稿人更新草稿，尚未合并完整 Word。原回复和旧表格原样保留，本次新草稿优先用于后续整合。

本轮算法开发到此结束。代理的独立优化优势仍未获得支持，去 reserve 和单模型全流程消融仍未完成；不会把重复控制当作额外证据。

所有数值与轨迹均读取既有文件和状态表，UE 新求解为零。CSV 可用 Excel 打开。`code/` 包含本次核查和报告生成程序、原函数片段；`prior_round2_sha256.json` 记录收尾前文件哈希。压缩包仅含此目录及其核验清单，原第二轮 2.22 GB 完整结果包继续保留，需深挖时配合使用。
''')

    # Final acceptance and immutable-data recheck; never rerun optimization.
    assert phase.groupby(['scenario_id','replicate']).unique_queries.sum().eq(256).all()
    assert gate.of_these_with_p3_in_reserve.eq(0).all() and gate.of_these_actually_completed_in_C.eq(0).all()
    assert run.C_distinct_first_roads.eq(1).all()
    prior=json.loads((P/'prior_round2_sha256.json').read_text(encoding='utf-8'))
    for path,h in prior.items():assert sha(ROUND/path)==h
    old=verify_manifest()
    for f in (P/'code').glob('*.py'):ast.parse(f.read_text(encoding='utf-8'),filename=str(f))
    dump(P/'completion_check.json',{'status':'PASS','failure_case_runs_audited':20,'proxy_duplicate_pairs_full_request_match':300,
        'query_cap_start_control_ledgers_audited':630,'initialization_charged_to_cap':True,'same_LS_function_and_policy':True,
        'identical_LS_entry_information':False,'strict_permutation_only_causal_effect_claimed':False,'UE_solves':0,'optimization_runs':0,
        'new_scenarios':0,'retrained_models':0,'original_frozen_files_unchanged':len(old['original_files_sha256']),
        'previous_round2_files_unchanged':len(prior),'algorithm_development':'closed for this revealed ten-road benchmark',
        'reply_readiness':'draft_with_placeholders','full_word_manuscript_integrated':False,'reviewer_separation':'PASS','quoted_conclusion_consistency':'PASS'})
    target=P/'4.1最后收尾材料_20261027.zip'
    paths0=[f for f in P.rglob('*') if f.is_file() and f!=target and f.name not in ['delivery_files_sha256.json','package_integrity.json'] and '__pycache__' not in f.parts]
    dump(P/'delivery_files_sha256.json',{'files':{f.relative_to(P).as_posix():{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(paths0)},'self_and_archive_checksum_excluded':True})
    paths0.append(P/'delivery_files_sha256.json')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in paths0:z.write(f,'closeout_20261027/'+f.relative_to(P).as_posix())
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    dump(P/'package_integrity.json',{'archive':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'file_count':len(paths0),'CRC':'PASS'})
    print('Closeout reporting and ZIP complete',target,target.stat().st_size,flush=True)

if __name__=='__main__':main()
