from common import *

def fmt(v,n=4):return f'{float(v):.{n}f}'
def mdtable(df,cols,heads=None):
    lines=['| '+' | '.join(heads or cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for _,r in df.iterrows():lines.append('| '+' | '.join('不适用' if pd.isna(r[c]) else fmt(r[c]) if isinstance(r[c],(float,np.floating)) else str(r[c]) for c in cols)+' |')
    return '\n'.join(lines)
def write(name,text):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

def main():
    acceptance=json.loads((OUT/'S0_replay_acceptance.json').read_text());assert acceptance['runs']==300
    screening=frame(OUT/'S1_screening_loss.csv');st=screening.groupby('scenario_id').mean(numeric_only=True)
    pools=frame(OUT/'S1_candidate_pool_oracle.csv');prefix=frame(OUT/'S1_prefix_recall.csv');ls=frame(OUT/'S1_ls_contribution.csv')
    structure=frame(OUT/'S1_greedy_structure.csv');rank=frame(OUT/'S1_same_stage_state_ranking.csv')
    ab=frame(OUT/'S1_start_ablation_summary.csv').set_index('method');decompdata=frame(OUT/'S1_regret_decomposition_scenarios.csv').drop(columns=['replicate'],errors='ignore')
    decompdata.to_csv(OUT/'S1_regret_decomposition_scenarios.csv',index=False);decomp=decompdata.set_index('scenario_id')
    original=frame(ROOT/'analysis/scenario_seed_summaries.csv');query=original[original.phase=='query_cap']
    greedy=query[query.method=='greedy_ils'].set_index('scenario_id');simple=query[query.method=='greedy_ls'].set_index('scenario_id')
    eps=cfg()['equivalence']['equivalence_kappa']
    costs=frame(OUT/'S2_online_comparison.csv').set_index('method');offline=json.loads((OUT/'S2_offline_cost/offline_cost_summary.json').read_text())
    execution=json.loads((OUT/'S2_execution_timing.json').read_text());components=frame(OUT/'S2_Proposed_components.csv')
    amort=frame(OUT/'S2_amortization.csv');full=frame(OUT/'S2_fresh_timing.csv')
    # Source summary first averages seeds within scenario, never treats 9m candidates as independent flood replicates.
    p=pools[pools.scope=='primary_source'];source=p.groupby(['source','scenario_id'],as_index=False).mean(numeric_only=True).drop(columns=['scenario_id','replicate']).groupby('source',as_index=False).mean(numeric_only=True)
    for threshold in ['0_1','0_5','1_5']:source[f'fraction_regret_le_{threshold}_pct']=source[f'count_regret_le_{threshold}_pct']/source.candidate_count
    source.to_csv(OUT/'S1_source_summary.csv',index=False)
    b=frame(OUT/'S1_budget_by_phase.csv');bt=b[b.scope=='phase_total'];matrix=bt.pivot_table(index=['scenario_id','replicate'],columns='phase',values='unique_queries',fill_value=0)
    assert len(matrix)==300 and np.all(matrix.sum(axis=1)==256)
    phase=[]
    for c in matrix.columns:
        sub=bt[bt.phase==c];phase.append({'phase':c,'mean_unique_queries':float(matrix[c].mean()),'mean_budget_share':float(matrix[c].mean()/256),
            'canonical_optimal_path_query_fraction':float(sub.canonical_optimal_path_queries.sum()/sub.unique_queries.sum())})
    phase=pd.DataFrame(phase);phase.to_csv(OUT/'S1_budget_phase_summary.csv',index=False)
    # Frozen observed-case ceiling; this is not a future-population power theorem.
    remaining=float(greedy.mean_regret_pct.mean());hits=int(sum(greedy.equivalent_hit_rate==1))
    same_starts=True
    for sid in range(3001,3031):
        for rep in range(10):
            c=json.loads((OUT/f'replay/scenario_{sid}/rep_{rep:02d}/start_controls.json').read_text())
            same_starts &= c[0]['initial_sequence']==c[1]['initial_sequence'] and float(c[0]['final_objective']).hex()==float(c[1]['final_objective']).hex()
    proxybetter=bool(ab.loc['proxy_pool_top1_ls','mean_scenario_regret_pct']<ab.loc['random_ls','mean_scenario_regret_pct'])
    proxyclaim=('代理均值第一条作为起点的回放均值低于随机起点；这是事后、固定代理的描述性比较。' if proxybetter else '本次事后回放没有显示代理起点的平均结果优于随机起点，因此不采用计划中预设的该优势表述。')
    mechanism=f'''候选池和筛选都有可见损失：池中最好候选的情景均值平均 regret 为 {fmt(st.pool_best_regret_pct.mean())}%，筛选后为 {fmt(st.screened_best_regret_pct.mean())}%，平均筛选损失 {fmt(st.screening_loss_pp.mean())} 个百分点。相比之下，Greedy-LS 平均为 {fmt(simple.mean_regret_pct.mean())}%。因此不能把问题完全归咎于筛选，也不能把候选池视为普遍接近精确最优的集合。

第一次局部修正前，最好完整序列的平均 regret 为 {fmt(ls.first_pre_ls_regret_pct.mean())}%；最终为 {fmt(ls.final_regret_pct.mean())}%。逐次 LS 调用内直接观察到的平均 regret 下降量合计为 {fmt(ls.direct_within_ls_reduction_pp.mean())} 个百分点。首次 LS 入口到最终结果还跨越后续候选补全，不能把全部差值都归为 LS 的独立因果贡献。最终序列也可以由 LS 生成到原候选池之外，所以这条链不是可相加的非负误差分解。'''
    prefixsummary=prefix.groupby('prefix_length',as_index=False)[['canonical_prefix_in_reserve','any_numerically_optimal_prefix_in_reserve']].mean()
    cases=[]
    for sid in [3026,3029,3004]:
        d=decomp.loc[sid];s=st.loc[sid];z=ls[ls.scenario_id==sid];pc=prefix[prefix.scenario_id==sid]
        localbudget=bt[bt.scenario_id==sid];prefixqueries=float(localbudget[localbudget.phase.str.startswith(('A_','B_'))].unique_queries.sum()/10)
        lsqueries=float(localbudget[localbudget.phase=='D_local_search'].unique_queries.sum()/10)
        sources=pools[(pools.scenario_id==sid)&(pools.scope=='primary_source')].groupby('source').best_oracle_regret_pct.mean()
        bestsource=sources.idxmin()
        cases.append(f'''### 情景 {sid}

十种子均值：池中最好 {fmt(d.pool_best_regret_pct)}%，筛选后最好 {fmt(d.screened_best_regret_pct)}%，首次 LS 前 {fmt(d.pre_ls_regret_pct)}%，最终 Proposed {fmt(d.final_regret_pct)}%；Greedy-ILS 为 {fmt(greedy.loc[sid,'mean_regret_pct'])}%。筛选损失为 {fmt(s.screening_loss_pp)} 个百分点，最终 Proposed 单次最差值 {fmt(z.final_regret_pct.max())}%。四条道路的条件最优前缀在 reserve 中的保留比例为 {100*pc[pc.prefix_length==4].canonical_prefix_in_reserve.mean():.1f}%。

该情景序列代理/oracle 排名 ρ 为 {fmt(s.pool_proxy_oracle_sequence_spearman)}。按来源池中最小 regret 的十种子平均，{bestsource} 最低，为 {fmt(sources.loc[bestsource])}%；这受来源配额影响，不是来源的独立因果优劣检验。前缀阶段平均首次查询 {fmt(prefixqueries,1)} 个唯一状态，局部修正阶段 {fmt(lsqueries,1)} 个。相应的每次父序列与局部移动均保留在该情景 replay 目录，可沿着预算轨迹核对损失在哪里出现、哪些移动挽回了它。本例用于说明上述全 30 情景统计，不参与重新选择算法或样本。
''')
    sourcecols=['source','best_oracle_regret_pct','count_regret_le_0_1_pct','count_regret_le_0_5_pct','count_regret_le_1_5_pct']
    report=f'''# S1 Proposed 失败机制诊断

本报告对既有 3001–3030 的 30 个情景、每情景十个 Proposed 种子做事后诊断。没有新洪水、代理重训或确认性算法重跑。回放仅访问已有精确表，且对全部 300 次运行验证了最终目标逐位一致、序列一致、逻辑请求数及唯一查询顺序/阶段/原因一致。原始文件 SHA256 未变，见 manifest.json 和 S0_replay_acceptance.json。

## 全部情景的核心发现

{mechanism}

依据：S1_screening_loss.csv、S1_ls_contribution.csv、S1_regret_decomposition_runs.csv。regret 的池中最小值是这个固定候选集合可实现的最好质量，不是对允许生成新邻居的整个搜索过程的下界。

## 候选来源与筛选

{mdtable(source,sourcecols,['候选首次注册来源','平均池内最好 regret %','regret≤0.1%平均条数','≤0.5%平均条数','≤1.5%平均条数'])}

来源按首次注册的 primary_source 互斥分组。配额不同，最小 regret 与近优条数不是等样本量下的来源优劣检验；各来源 candidate_count 和近优比例同时保存在 S1_source_summary.csv。带多个 source_tags 的非互斥统计也保存在 S1_candidate_pool_oracle.csv，不能把该组数量相加当作唯一候选数。每次回放保留全部 30,000 条序列及代理/真值评分，合计 900 万条，位于 replay/scenario_*/rep_*/candidate_pool_30000_with_oracle.csv.gz。

候选序列代理均值与 oracle 目标的情景平均 Spearman ρ，跨情景均值为 {fmt(st.pool_proxy_oracle_sequence_spearman.mean())}，范围 {fmt(st.pool_proxy_oracle_sequence_spearman.min())} 至 {fmt(st.pool_proxy_oracle_sequence_spearman.max())}。这是完整序列目标排序，不能叫同阶段状态排序。另行计算的同阶段状态 ρ 见 S1_same_stage_state_ranking.csv，按每情景、R1–R9 分组，未将所有状态当作独立洪水样本。

{mdtable(prefixsummary,['prefix_length','canonical_prefix_in_reserve','any_numerically_optimal_prefix_in_reserve'],['前缀长度','单一规范 DP 前缀召回率','任一数值等价最优前缀召回率'])}

保留前缀只指 reserve 中完整序列的实际前缀。第二个召回指标用该前缀下的最优后续 DP 目标校验，避免把不同但同优的排列误认作失败。依据 S1_prefix_recall.csv。

## 预算与局部修正

{mdtable(phase,['phase','mean_unique_queries','mean_budget_share','canonical_optimal_path_query_fraction'],['阶段','每运行平均唯一查询','预算占比','属于规范最优路径的查询比例'])}

每个状态仅归到本方法首次请求它的阶段，各阶段总和严格为 256。零查询阶段在平均中按零处理。只命中一条规范最优路径不代表其它查询无用。S1_budget_by_phase.csv 同时给出按阶段汇总和连续查询块的边界最好 regret；相同查询数下的免费缓存序列评价可能发生在块边界，因此该曲线是查询数口径的 incumbent 轨迹，不是阶段的因果收益分解。

停止原因取自未修改 local_search 函数的实际返回局部变量：达到调用目标预算，或连续两轮相对提升低于 0.1%/无可评邻居。它并非严格“零改进才停”。每次最多选五个父序列，实际不足五个时保留真实数量。每次 LS 的父序列、入口/出口目标、轮数和停止原因见 local_search_calls.json，逐个邻居结果见 local_move_history.csv.gz。

## 贪婪结构解释的限度

不加 LS 的纯贪婪平均 regret 为 {fmt(structure.pure_greedy_regret_pct.mean())}%，中位数 {fmt(structure.pure_greedy_regret_pct.median())}%，最大 {fmt(structure.pure_greedy_regret_pct.max())}%。加原 LS 后的 Greedy-LS 平均为 {fmt(simple.mean_regret_pct.mean())}%。这说明强结果依赖构造与局部修正的结合，不能只解释为纯贪婪本身几乎总是最优。

每情景穷尽 23,040 个相邻上下文的边际收益递减比较，即检查 Δe(S)≥Δe(S∪{{f}})。这里使用物理状态成本 C(S)，包括十路全部重开的 C(E)；零终态权重只作用于序列目标 J，不把物理 C(E) 置零。严格比较的通过比例跨情景平均为 {100*structure.strict_diminishing_fraction.mean():.2f}%，范围 {100*structure.strict_diminishing_fraction.min():.2f}%–{100*structure.strict_diminishing_fraction.max():.2f}%。仍有大量违例，因此不能宣称子模性或贪婪近似最优保证。按 κ 与状态成本尺度作宽松容差敏感性时，比例为 {100*structure.empirical_tolerance_diminishing_fraction.mean():.2f}%；该容差不是已校准的边际收益误差界，结构判断以严格比较为主。

共同 R0 成本占最优累计目标的比例平均为 {100*structure.common_R0_share_of_optimal_objective.mean():.2f}%。它在所有排序中相同，会影响百分比 regret 的尺度，但不改变同情景方法排名，也不能证明运营损失很小。规范 DP 排列的首次分歧与真正离开数值等价最优后续的首次分歧分别记录在 S1_greedy_structure.csv，避免把同优排列差异算成错误。

## 相同 LS 的起点回放

{mdtable(ab.reset_index(),['method','mean_scenario_regret_pct','median_scenario_regret_pct','P90_scenario_regret_pct','mean_unique_queries'],['起点控制','平均情景 regret %','中位数 %','P90 %','平均唯一查询'])}

{proxyclaim} 两种代理规则在 300/300 次运行中选择同一序列且得到相同结果：{same_starts}。因此它们不是两份独立支持，也不能据此识别去掉 reserve 的独立效果。这里没有重跑“保持整个 Proposed 其余过程不变、仅移除 reserve”的完整消融。代理起点仍弱于 UE 贪婪起点，而且回放需要原候选池，不能假定省掉了候选构造时间。依据 S1_start_ablation.csv 及 S1_start_ablation_summary.csv。

## 预先指定的三个案例

{''.join(cases)}

## S3 决策

本轮不开发 V2。证据显示候选池覆盖、筛选和后续预算利用均有局限，不能强行归为一个单一原因。代理起点加同一 LS 的事后回放优于完整 Proposed 的情景平均，提示结构与预算安排值得将来研究；这不是对具体组件因果作用的确认性证明。

Greedy-ILS 在 {hits}/30 个情景的全部种子达到经验数值等价命中，现有平均 regret 为 {fmt(remaining,6)}%。即使本样本全部达到参照目标，平均最多再降约 {fmt(remaining,6)} 个百分点。这个观测上界只适用于当前样本，不证明任何新盲测中不可能检出改善。扩大可恢复道路规模、实测成本与枚举不可行性属于未来独立研究，本轮不做。
'''
    write('S1_failure_mechanism_report.md',report)
    online=costs.reset_index()
    costreport=f'''# S2 计算成本与摊销

新测量对 30 个情景分别从空状态缓存枚举 1,024 个状态并做 DP，单进程和四进程各一遍。四进程按原 time-cap 的 CPU 分组，每核仅一进程，避免同核并发冲突。UE、DP 与输出写盘分别计时。每情景在线时间不包含输入加载、JIT 预热和写盘；与先前在线测量的范围一致，但这是不同批次，不是随机交错的严格计时试验。单进程与先前四工作进程的系统负载也不同，因此两种枚举模式分别报告。

{mdtable(online,['label','mean_online_seconds','median_online_seconds','P90_online_seconds','mean_scenario_regret_pct','mean_unique_queries'],['方法/执行模式','平均在线秒','中位秒','P90秒','平均情景 regret %','平均唯一状态'])}

完整枚举的全部测量成本与 DP 解保存在 S2_timing_raw，主表为 S2_fresh_timing.csv。串行平均 UE 阶段时间 {fmt(full[full['mode']=='serial'].ue_stage_seconds.mean())} 秒、平均 DP 时间 {fmt(full[full['mode']=='serial'].dp_seconds.mean(),6)} 秒。四进程枚举整个 30 情景批次的实测总墙钟时间为 {fmt(execution['parallel4_batch_including_setup_startup_and_output_seconds'])} 秒，包含进程启动、预热和输出。单进程在线时间总和为 {fmt(execution['serial_online_seconds_sum'])} 秒；串行曾因并行调度防冲突的技术修正而断点续算，保留已完成测量，不伪造连续批次总墙钟。

Proposed 的原时间组分项均值：候选构造（含推理）{fmt(components.candidate_seconds.mean())} 秒，其中推理 {fmt(components.surrogate_inference_seconds.mean())} 秒；已完整记录的 UE solver {fmt(components.physical_UE_seconds.mean())} 秒；其余在线开销 {fmt(components.other_online_seconds.mean())} 秒。不能重复加上已包含在候选构造中的推理。Proposed 只有每情景 r=0 的一份计时，种子稳定性来自原十种子查询组。其余 time-cap 方法的时间是给定上限内运行时间，不是达到固定质量所需时间。

## 离线成本

原 1,500+1,678 个训练状态的源文件哈希与训练 manifest 一致，3,178 个状态逐一在当前求解器 RG≤10⁻⁹ 下重新测量，未重新生成训练样本或训练任何模型。当前顺序制样总墙钟 {fmt(offline['current_sequential_UE_dataset_wall_seconds'])} 秒，逐状态调用时间之和 {fmt(offline['current_UE_state_call_seconds_sum'])} 秒，solver 内核时间之和 {fmt(offline['current_UE_solver_kernel_seconds_sum'])} 秒。

十成员历史训练分项计时合计 {fmt(offline['archived_ten_member_training_seconds_sum'])} 秒，配置另记录整个成员训练循环总计 {fmt(offline['archived_training_process_total_seconds'])} 秒，两者相差 {fmt(offline['archived_total_minus_member_sum_seconds'],6)} 秒。原脚本分别使用成员函数内和成员循环外的计时器，不能要求两个范围逐位相等。十个模型的 SHA256 均匹配冻结权重。其原硬件未从记录中确立，不能冒充本机重训实测。当前 UE 制样加历史训练循环总计的混合估计为 {fmt(offline['hybrid_current_UE_plus_archived_training_seconds'])} 秒；原始状态历史 elapsed 之和另为 {fmt(offline['archived_UE_state_elapsed_seconds_sum'])} 秒，属于不同求解器/精度及历史硬件上的聚合工作量，不能与当前墙钟混算。

制样计时曾在汇总检查时因误把两个历史计时范围视为相同而停止，第一遍 3,178 个已完成逐状态测量仍以 attempt1 文件保留；修正该检查后再完整测量一遍，使用这次完整记录的总墙钟，不依时间大小择优。没有修改训练数据或模型。

## 按时间计的交叉点

{mdtable(amort,['comparator','offline_cost_scope','offline_seconds','mean_comparator_minus_Proposed_seconds','finite_time_crossover','crossover_scenarios'],['参照','离线成本口径','离线秒','参照减Proposed在线秒','有正交叉点','场景数'])}

算式为 N≥T_offline/(T_reference−T_Proposed)，只有分母为正才有正交叉点。这里基于当前 30 情景的平均时间和两种明确成本口径，仅是算时交叉，不是同质量经济回本：枚举返回数值条件最优，而 Proposed 有非零 regret；时间组 UE-only 方法也在给定上限内产出更好决策。旧的 3,178/(1,024−256)≈4.14 只比较状态数，不能继续作为已验证的时间回本结论。75% 只描述相对完整 1,024 表的信息查询减少，不表示 75% 耗时减少；正文成本主张应改用本表，不把它作为实际节省证据。
'''
    write('S2_computational_cost_report.md',costreport)
    # Text-only manuscript integration drafts; never claim existing Word was edited.
    title='Budgeted High-Fidelity Evaluation of Road Reopening Sequences under Urban Flooding: An Auditable Comparison of Surrogate-Assisted and UE-Only Search'
    abstract=f'''We evaluate budgeted road reopening sequencing under static user equilibrium on the Sioux Falls benchmark. A prospectively frozen comparison used 30 new severe-flood scenarios and ten search seeds per stochastic method, with method-specific unique-state ledgers and post-freeze conditional dynamic-programming references. At 256 state queries, Proposed had mean scenario seed-mean regret 0.5481%, compared with 0.0510% for UE-Greedy-ILS; the added value of the fixed surrogate-assisted design was not established. Subsequent post-hoc replays reproduced all 300 Proposed objectives bit for bit. Candidate-pool minima averaged {fmt(st.pool_best_regret_pct.mean())}% regret, retained-set minima {fmt(st.screened_best_regret_pct.mean())}%, and first pre-correction decisions {fmt(ls.first_pre_ls_regret_pct.mean())}%; local correction recovered substantial quality. A proxy-first start with the same correction had post-hoc mean regret {fmt(ab.loc['proxy_pool_top1_ls','mean_scenario_regret_pct'])}%, while greedy starts remained stronger. Fresh full enumeration plus DP averaged {fmt(costs.loc['enum_serial','mean_online_seconds'])} s in serial execution and {fmt(costs.loc['enum_parallel4','mean_online_seconds'])} s per scenario in four-worker execution, compared with the archived fresh Proposed time {fmt(costs.loc['proposed','mean_online_seconds'])} s. The contribution is a reproducible budgeted comparison and diagnosis of an underperforming design, rather than a new UE sequencing principle or established surrogate superiority. Findings are conditional on ten preselected roads, equal durations, fixed demand and the synthetic connected-flood generator.'''
    methods='''The original comparison and subsequent diagnosis are distinct. The confirmatory comparison used 3001–3030, eight frozen methods, ten search seeds per stochastic method, independent query-cap and time-cap groups, RG≤10⁻⁹ and an empirically calibrated equivalence rule. All search outputs preceded full numerical tables and DP. The second round generated no scenarios and changed no model or method. It reconstructed missing candidate pools from frozen seeds, checked all Proposed final objectives bit for bit, then used the existing tables for post-hoc candidate, screening, prefix, budget and local-search diagnostics. The two proxy-first controls use the actual unchanged local-search routine and at most 256 method-specific states. Fresh UE solves in this second round were restricted to standalone enumeration timing and offline training-state cost measurement. Beam methods are documented adaptations without the original traffic-benefit bounds and pruning. The two aggregate flow/centrality features sum over initially closed roads, matching the frozen implementation.'''
    conclusion=f'''The independent comparison favors UE-only construction plus local correction over the fixed surrogate-assisted design in this ten-road benchmark. The subsequent diagnostics identify limitations in candidate coverage, screening and the use of a finite correction budget; they do not establish independent causal contributions of each component. A proxy-first start improved on the random-start control in post-hoc mean regret, but did not surpass greedy initialization. Complete enumeration is a practical small-instance numerical reference whose measured cost must accompany any query-saving claim. The remaining empirical mean improvement ceiling over UE-Greedy-ILS is approximately {fmt(remaining,6)} percentage points on these 30 scenarios, motivating no further algorithm development on the revealed set. Testing larger recovery sets and more operationally realistic models requires a separate study.'''
    write('manuscript/S4_重新定位与英文替换段落.md',f'''# Second-round manuscript integration draft

Status: draft_with_placeholders. These are supplied replacement passages, not a claim that the complete Word manuscript or all reviewer comments have been resolved. Final numbering and locations require integration. No Crocker & Boyles (2025) citation is introduced, pending the author verification requested in the plan.

## Proposed title

{title}

## Replace Abstract

{abstract}

## Replace the contribution list

The study contributes a method-specific state-information budget and reproducible information firewall; a frozen comparison against adaptive UE-only search with conditional numerical decision references; and transparent post-hoc diagnosis of candidate coverage, screening, correction and computational cost. Sequential UE restoration and subset dynamic programming are established structures, and generic surrogate model management is not claimed as a new principle. The particular surrogate-assisted design did not demonstrate added decision value over the strongest UE-only controls.

## Methods addition

{methods}

## Results integration

Keep original ten-scenario findings as archived original-study results, with numerical reconciliation in SI. Place the new 30-scenario Table R2 and seed plot in the main text. Add the S1 stage figure and concise numerical findings from S1_failure_mechanism_report.md, and the fresh cost table from S2_online_comparison.csv. Label all round-2 diagnosis and proxy-start controls post hoc. Keep full phase ledgers, oracle scores, structural tests and training-cost provenance in SI/source data.

## Discussion replacement

The new comparison supports the concern that the original diagnostic baselines were too weak to establish the value of surrogate complexity. Most revealed cases leave little regret to improve beyond UE-Greedy-ILS, but the observed-case ceiling is not proof that a new method could never show an advantage elsewhere. The candidate pool itself is imperfect and screening increases the best available regret; the unchanged local correction repairs much of this loss and can create sequences absent from the pool. Two proxy-first controls coincide, so they do not independently identify a structural-reserve effect. Diminishing-return tests show many exceptions and provide no submodularity guarantee. The cost evidence replaces the former state-count break-even argument and does not assume offline costs are amortized merely because a model is reusable.

## Conclusion replacement

{conclusion}

## Limitations addition

Search-seed variation does not cover surrogate retraining randomness. Beam comparators are adaptations rather than full reproductions. Post-hoc diagnosis is restricted to the revealed scenarios and uses oracle information unavailable during the original methods. Timing comparisons use different batches on the same hardware, serial and four-worker regimes are distinct, and historical training hardware is not established. All optimality statements refer to the numerical conditional table for ten preselected roads. No city transfer, disconnection model, heterogeneous duration or larger-road-set experiment was performed in this round.

## Supplemental provenance

Retain the 2001–2030 engineering invalidation timeline and hashes, separately from 3001–3030. The round-2 manifest verifies that no original code, result or numerical table changed. Correct remaining-closed to initially closed for the two aggregate features without modifying inputs or weights.
''')
    shared=f'''The completed frozen comparison covers 30 new scenarios, 1,590 query-cap runs and 660 separate fresh time-cap runs. Proposed mean scenario regret at 256 queries is 0.5481%, versus 0.0510% for UE-Greedy-ILS. Added superiority of the fixed surrogate design was not established. All 300 Proposed runs were subsequently reproduced bit for bit in table-only post-hoc replays. Pool minima averaged {fmt(st.pool_best_regret_pct.mean())}% regret, retained-set minima {fmt(st.screened_best_regret_pct.mean())}%, and first pre-LS decisions {fmt(ls.first_pre_ls_regret_pct.mean())}%. Proxy-first plus unchanged LS achieved post-hoc mean regret {fmt(ab.loc['proxy_pool_top1_ls','mean_scenario_regret_pct'])}%, compared with {fmt(ab.loc['random_ls','mean_scenario_regret_pct'])}% for the archived random-start control and {fmt(ab.loc['greedy_ls','mean_scenario_regret_pct'])}% for greedy initialization. These diagnostic differences do not separately identify causal component effects.'''
    write('manuscript/Reviewer1_4.1_4.3_4.5_5.1_回复草稿.md',f'''# Reviewer 1 response draft

Readiness: draft_with_placeholders. Actual experiments and supplied passages are complete; full Word integration and final page/line numbering are pending. This file contains only this reviewer's selected comments.

## Comment 4.1

We agree that the original comparisons did not establish the added value of surrogate complexity. {shared} We therefore supply replacements for the title, Abstract, contribution statement, Discussion and Conclusion that remove superiority and stable-tail claims. We do not develop a new method on this revealed set. Even a zero-regret replacement could improve the observed UE-Greedy-ILS mean by at most about {fmt(remaining,6)} percentage points; this is an observed-case ceiling and saturation concern, not a claim of statistical impossibility in future validation. The Methods description also corrects the two flow/centrality aggregates to initially closed roads without changing the frozen model.

## Comment 4.3

Full fresh enumeration of all 1,024 states plus DP was measured for every scenario in serial and four-worker execution. Mean per-scenario online times were {fmt(costs.loc['enum_serial','mean_online_seconds'])} s and {fmt(costs.loc['enum_parallel4','mean_online_seconds'])} s, respectively; the archived Proposed fresh B=256 time was {fmt(costs.loc['proposed','mean_online_seconds'])} s. UE and DP components, complete batch wall time and concurrency differences are reported separately. All 3,178 original training states were re-evaluated only to measure current solver cost, taking {fmt(offline['current_sequential_UE_dataset_wall_seconds'])} s sequentially. The archived outer training-loop timer adds {fmt(offline['archived_training_process_total_seconds'])} s (member timers sum to {fmt(offline['archived_ten_member_training_seconds_sum'])} s), with matching model hashes but unestablished original hardware. The resulting {fmt(offline['hybrid_current_UE_plus_archived_training_seconds'])} s is a hybrid estimate, not a same-hardware retraining benchmark. The supplied cost discussion replaces the state-count break-even claim; 75% fewer table-state queries is not presented as 75% elapsed-time saving. The arithmetic time crossovers do not compare equal decision quality.

## Comment 4.5

The new post-hoc controls keep the actual original local-search routine and method-specific cap, changing only initialization. Both proxy-first rules selected the same sequence in every case, so their coincident results do not isolate the effect of removing structural reserve from the complete method. We explicitly leave full ensemble simplification and a controlled whole-method reserve removal unresolved rather than claim those experiments were done. We provide all candidate oracle scores, prefix recall, phase budgets, correction inputs and accepted improvements. The supplied component interpretation is correspondingly restricted.

## Comment 5.1

The proposed positioning acknowledges that UE-based restoration sequencing, Bellman/subset optimization and surrogate model management are established. The contribution is narrowed to an auditable budgeted evaluation protocol, its comparative evidence and the diagnosed limits of one design. The experiments favor simpler UE-only alternatives here; potential surrogate value at larger recovery-set sizes remains future work and has not been demonstrated by the present ten-road study.

Proposed replacement Conclusion:

*{conclusion}*
''')
    write('manuscript/Reviewer2_1_6_回复草稿.md',f'''# Reviewer 2 response draft

Readiness: draft_with_placeholders. Full manuscript integration and final locations remain pending. This response is standalone and contains no other reviewer's comments.

## Comment 1

We agree that combining established surrogate models, candidate generation, subset optimization and local correction does not by itself establish a fundamentally new optimizer. {shared} The supplied revised title and contribution statement therefore position the work as an auditable budgeted comparative evaluation and a transparent diagnosis of a design that did not outperform its strongest UE-only alternatives. We remove claims that sequential congestion-aware restoration, subset DP or generic surrogate coupling are independently novel. Component and scaling limits are explicit, and no larger-network or larger-recovery-set result is claimed.

## Comment 6

SA is a prespecified formal comparator in the new 30-scenario experiment. Original permutation SA and SA-restart each receive ten fixed seeds, alongside ten-seed Proposed and other UE-only controls. Both equal query caps and separate fresh-cache time caps are reported, with real query counts when methods stop early. The original single-run ten-scenario result is retained separately as historical evidence. The new sample does not establish a stable tail advantage for Proposed, and the supplied Abstract and Conclusion remove that claim. Seed variation concerns search randomness, not surrogate retraining. Full raw outcomes and ledgers are supplied so that mean, median, tail behavior and numerical-equivalence rates remain independently checkable.
''')
    baseline=(ROOT/'inputs/manuscript_baseline_extracted.txt').read_text(encoding='utf-8')
    oldabstract=baseline.split('\nAbstract\n',1)[1].split('\nKeywords:',1)[0]
    write('manuscript/S4_证据与修改对应表.md',f'''# S4 证据与改稿对应

此表为作者内部整合记录，文本草稿状态为 draft_with_placeholders；原 Word 没有被覆盖。

| 原论断或段落 | 本轮证据 | 文本处理 | 位置 |
| --- | --- | --- | --- |
| 代理复杂结构的增益 | 新 30 情景强 UE-only 比较不支持整体优势 | 替换为预算化可审计比较与设计诊断，明确负结果 | Title Abstract contributions Discussion Conclusion |
| 稳定尾部优势 | 十种子结果和新情景尾部未复现原方向 | 删除强论断，保留历史结果作为历史 | Abstract Results Discussion |
| 筛选和局部修正价值 | 池/保留集/入口/最终 oracle 与实际轨迹 | 简述主要差距；完整来源和预算表放 SI | Results and S1 report |
| reserve 和 ensemble 独立作用 | 两个新起点完全相同；未做全方法去 reserve 或简化 ensemble | 明确未识别，不宣称已解决全部组件因果证据 | Discussion response |
| 75% 节省与 4.14 情景回本 | fresh 枚举、DP、离线制样和训练记录 | 移除已验证耗时节省/回本措辞，报告有条件时间交叉 | Cost results and S2 report |
| 贪婪强的原因 | 纯贪婪与 Greedy-LS 差别、边际收益违例 | 不写子模保证或纯贪婪几乎总最优 | Discussion SI |
| 特征 remaining-closed 命名 | 冻结代码使用 initial_closed | 改描述，不改模型或特征 | Methods and reply |

最短正文证据链为：独立强对照负结果 → 可核对的事后损失诊断 → 直接成本参照 → 限定贡献。全部来源计数、逐次轨迹、结构敏感性与技术恢复记录放 SI/数据包，不重复塞入正文。原十情景保留独立历史标签，不与新样本合并。

Abstract 原文 {len(oldabstract.split())} 词，新拟稿 {len(abstract.split())} 词。新稿替换旧主张而非在旧优势论断后简单追加免责声明。Abstract 介绍边界，Results 给数值，Discussion 解释，Conclusion 收束；回复引用的结论与同份替换段落生成自相同字符串。
''')
    summary={'status':'ROUND2_ANALYSIS_AND_DRAFTS_COMPLETE','post_hoc':True,'replays':300,'bitwise_replay_pass_rate':1.,'new_scenarios':0,'surrogate_retraining':False,
        'mean_pool_best_regret_pct':float(st.pool_best_regret_pct.mean()),'mean_screened_best_regret_pct':float(st.screened_best_regret_pct.mean()),
        'mean_screening_loss_pp':float(st.screening_loss_pp.mean()),'mean_pre_ls_regret_pct':float(ls.first_pre_ls_regret_pct.mean()),'mean_final_regret_pct':float(ls.final_regret_pct.mean()),
        'mean_direct_LS_reduction_pp':float(ls.direct_within_ls_reduction_pp.mean()),'mean_sequence_spearman':float(st.pool_proxy_oracle_sequence_spearman.mean()),
        'mean_strict_diminishing_fraction':float(structure.strict_diminishing_fraction.mean()),'mean_pure_greedy_regret_pct':float(structure.pure_greedy_regret_pct.mean()),
        'proxy_start_controls_identical_all_runs':bool(same_starts),'observed_Greedy_ILS_improvement_ceiling_pp':remaining,
        'serial_enumeration_mean_seconds':float(costs.loc['enum_serial','mean_online_seconds']),'parallel4_enumeration_mean_seconds':float(costs.loc['enum_parallel4','mean_online_seconds']),
        'offline_cost':offline,'full_word_manuscript_integrated':False,'unperformed_component_tests':['full method with reserve removed but otherwise unchanged','ensemble simplification','larger recovery-set evaluation']}
    dump(OUT/'round2_summary.json',summary)
    overview=f'''# 4.1 第二轮结果总览

已按进一步计划完成 S0、S1、S2 和 S3。S4 的重新定位、正文替换和分审稿人回复已提供文本草稿，尚未整合进完整 Word。全部诊断均为既有 3001–3030 的事后分析；原实验和 analysis/ 文件保持不变，没有新情景、重训、调参或 V2 开发。

## 先看这些结论

1. 300/300 次 Proposed 回放的最终目标逐位一致，序列、请求数及查询顺序/阶段/原因均一致；九百万候选评分及全部中间记录已保存。
2. 池中最好候选的平均 regret 为 {fmt(st.pool_best_regret_pct.mean())}%，筛选后为 {fmt(st.screened_best_regret_pct.mean())}%，平均筛选损失 {fmt(st.screening_loss_pp.mean())} 个百分点。池覆盖和筛选均有局限，不能强行归于一个原因。
3. 首次 LS 前平均 regret 为 {fmt(ls.first_pre_ls_regret_pct.mean())}%，最终 {fmt(ls.final_regret_pct.mean())}%。LS 挽回很多损失，但完整方案仍弱于贪婪起点。代理第一条+原 LS 的事后结果为 {fmt(ab.loc['proxy_pool_top1_ls','mean_scenario_regret_pct'])}%，Random-LS 为 {fmt(ab.loc['random_ls','mean_scenario_regret_pct'])}%，Greedy-LS 为 {fmt(ab.loc['greedy_ls','mean_scenario_regret_pct'])}%。两个代理起点控制完全相同，不能充当两份独立消融证据。
4. 纯贪婪平均 regret 为 {fmt(structure.pure_greedy_regret_pct.mean())}%，严格边际收益递减比例约 {100*structure.strict_diminishing_fraction.mean():.2f}%。Greedy+LS 的强结果不能直接归结为纯贪婪近乎总是最优或子模性保证。
5. 完整枚举+DP 平均在线时间：单进程 {fmt(costs.loc['enum_serial','mean_online_seconds'])} 秒；四进程时每情景 {fmt(costs.loc['enum_parallel4','mean_online_seconds'])} 秒。Proposed 原独立时间组为 {fmt(costs.loc['proposed','mean_online_seconds'])} 秒。批次与并行负载不同，均已分别标注。
6. 当前求解器重新测量 3,178 个原训练状态耗时 {fmt(offline['current_sequential_UE_dataset_wall_seconds'])} 秒；历史十成员分项合计 {fmt(offline['archived_ten_member_training_seconds_sum'])} 秒、外层训练循环 {fmt(offline['archived_training_process_total_seconds'])} 秒，权重哈希匹配。当前制样与外层循环相加得到 {fmt(offline['hybrid_current_UE_plus_archived_training_seconds'])} 秒，是跨测量背景的混合估计，不是本机重训结果。时间交叉点见 S2_amortization.csv；原 4.14 个情景的状态数回本不能作为时间结论。

## 文件导航

- S1_failure_mechanism_report.md：完整失败机制报告，含 3026、3029、3004 三案例及所有统计口径。
- S2_computational_cost_report.md：串行/并行实测、离线成本、分项成本与时间交叉点。
- S1_*.csv、S2_*.csv：完整分析表。
- replay/：300 次重建候选池、中间序列、LS 调用、查询记录和事后起点控制。
- S2_timing_raw/、S2_offline_cost/：新计时状态结果、原训练记录与来源校验。
- figures/：两张图的 PDF/SVG/TIFF/PNG。
- manuscript/：重新定位和回复草稿；不冒充完整 Word 已改。
- manifest.json：运行前原文件 SHA256；completion_check.json：运行后完整性验收。

观察到的 Greedy-ILS 均值剩余可改进上限约为 {fmt(remaining,6)} 个百分点，限于本样本，并不等于未来任何盲测都无法检出改善。未完成全方法去 reserve、简化 ensemble 或更大恢复集实验，回复中不会声称这些已做。
'''
    write('00_第二轮结果总览.md',overview)
    verify_manifest();print('Wrote complete S1/S2 reports, observed-case decision and isolated response/repositioning drafts.',flush=True)
if __name__=='__main__':main()
