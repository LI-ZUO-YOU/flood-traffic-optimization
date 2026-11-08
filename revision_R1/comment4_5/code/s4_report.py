from s4_common import *

def link(p,label=None):
 p=Path(p);return f'[{label or p.name}](<{p.as_posix()}>)'
def f(x,n=4):return '未观测' if pd.isna(x) else f'{float(x):.{n}f}'
def md(headers,rows):
 return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def write(name,s):
 p=S4/'06_report_response'/name;p.write_text(s,encoding='utf-8');return p

DEFS={'F0_FULL':'完整冻结流程','F1_NO_RESERVE':'无Reserve，flat替代','F2_NO_PREFIX':'移除前缀分层候选源','F3_NO_DISAG':'无disagreement席位','F4_NO_PROXY_SOURCES':'移除代理DP及GA候选源','F5_RANDOM_POOL':'随机30k候选池，仍使用代理','F6_SINGLE_MLP':'固定member01单MLP','F7_RIDGE':'冻结Ridge','F8_TREE':'冻结HGB','F9_NO_SURROGATE':'完全无代理，保留真实UE修正','Greedy-ILS':'原UE-only强基线'}
SHORT={v:v.split('_')[0] for v in METHODS};SHORT['Greedy-ILS']='Greedy-ILS'

def run():
 R=S4/'06_report_response';su=frame(S4/'01_statistics/full10_descriptive_summary.csv').set_index('variant_id').reindex(METHODS);influence=frame(S4/'01_statistics/5102_influence_no_exclusion.csv').set_index('variant_id');sc=frame(S4/'01_statistics/scenario_seed_statistics.csv');case=frame(S4/'02_case5102/5102_run_path_summary.csv');stage=frame(S4/'02_case5102/5102_stage_firstroad_counts.csv');timeDF=frame(S4/'03_phases_costs/Table_time_decomposition.csv').set_index('variant_id').reindex(METHODS);phase=frame(S4/'03_phases_costs/phase_method_means_n10.csv');quality=frame(S4/'03_phases_costs/LS_quality_method_means.csv').set_index('variant_id');budget=frame(S4/'03_phases_costs/run_budget_cache_management.csv');er=frame(S4/'04_prediction_diagnostics/state_error_model_means_n10.csv');pm=frame(S4/'04_prediction_diagnostics/common_pool_metrics_model_means_n10.csv').set_index('model');pq=frame(S4/'04_prediction_diagnostics/common_pool_quality_model_means_n10.csv');cond=frame(S4/'02_case5102/conditional_first_road_reference.csv').set_index('first_road')
 tab1=md(['方法','组件定义','平均regret %','中位数 %','P90 %','Δ对F0 pp','胜/平/负','在线秒'],[[SHORT[v],DEFS[v],f(r.mean_regret_pct),f(r.median_scenario_mean_regret_pct),f(r.P90_scenario_mean_regret_pct),f(r.mean_delta_vs_F0_pp),f'{int(r.scenario_wins)}/{int(r.scenario_ties)}/{int(r.scenario_losses)}',f(r.mean_online_seconds,3)] for v,r in su.iterrows()])
 tab2=md(['方法','候选准备 s','UE网络调用 s','LS管理 s','其他搜索管理 s','合计 s'],[[SHORT[v],f(r.candidate_prepare_seconds,3),f(r.UE_network_call_seconds,3),f(r.LS_non_UE_seconds,3),f(r.search_other_bookkeeping_seconds,3),f(r.fresh_online_seconds,3)] for v,r in timeDF.iterrows()])
 tab3=md(['方法','最大情景均值 %','最大单种子 %','平均种子SD pp','最大种子SD pp','全部LOSO均差范围 pp'],[[SHORT[v],f(r.max_scenario_mean_regret_pct),f(r.max_individual_seed_regret_pct),f(r.mean_within_scenario_seed_SD_pp),f(r.max_within_scenario_seed_SD_pp),f'{f(r.LOSO_delta_min_pp)} 至 {f(r.LOSO_delta_max_pp)}'] for v,r in su.iterrows()])
 casetab=md(['方法','种子','首个完整J','首次LS前regret %','首次LS后regret %','首路18首次完成预算','最终首路','最终regret %'],[[SHORT[r.variant_id],r.seed_index,f(r.first_complete_J,6),f(r.first_LS_before_regret_pct),f(r.first_LS_after_regret_pct),int(r.road18_first_complete_budget) if pd.notna(r.road18_first_complete_budget) else '未完成',r.final_sequence.split('|')[0],f(r.final_regret_pct,6)] for r in case.itertuples()])
 predrows=[];predrecords=[]
 for name in MODELS:
  a=er[(er.model==name)&(er.scale=='cost')].iloc[0];b=er[(er.model==name)&(er.scale=='log_ratio')].iloc[0];c=pq[(pq.model==name)&(pq.selection=='common_Primary60_25_0_15_10_10')].iloc[0]
  predrows.append([name,f(a.MAE,3),f(a.RMSE,3),f(a.R2,3),f(b.R2,3),f(pm.loc[name,'Spearman_candidate_J'],3),f(c.best_true_regret_pct,3)])
  predrecords.append({'model':name,'cost_MAE':a.MAE,'cost_RMSE':a.RMSE,'cost_R2':a.R2,'log_R2':b.R2,'common_pool_Spearman':pm.loc[name,'Spearman_candidate_J'],'common_primary60_best_regret_pct':c.best_true_regret_pct})
 predtab=md(['冻结模型','状态cost MAE','状态cost RMSE','状态cost R²','状态log R²','共同池Spearman','共同Primary60最佳regret %'],predrows)
 phrows=[]
 for v in METHODS:
  g=phase[phase.variant_id==v].set_index('phase');q=quality.loc[v];r=budget[budget.variant_id==v]
  get=lambda phase,col:float(g.loc[phase,col])
  phrows.append([SHORT[v],f(get('A_prefix2','first_seen_UE_states'),2),f(get('B_prefix3_initial','first_seen_UE_states')+get('B_prefix3_remaining','first_seen_UE_states'),2),f(get('C_true_ue_reranking','first_seen_UE_states'),2),f(get('D_local_search','first_seen_UE_states'),2),f(r.complete_unique_sequences.mean(),2),f(r.strict_incumbent_improvements.mean(),2),f(q.first_LS_before_regret_pct),f(q.first_LS_after_regret_pct)])
 phtab=md(['方法','A首见UE','B首见UE','C首见UE','LS首见UE','唯一完整序列','严格改善次','首次LS前 %','首次LS后 %'],phrows)
 notes='''主分母是全部10个新情景5101—5110，每个方法每个情景先平均三个冻结种子，再跨情景等权汇总。中位数、P90、最大情景均值均基于这10个情景均值，P90使用线性插值；种子SD为每情景三个种子的样本SD（ddof=1）。三个种子不当作三个独立情景。Δ=变体regret−F0 regret，单位为百分点，负值有利于变体。胜/平/负比较情景平均原始J，平局阈值为κ×max(1,|J*|)，κ沿用冻结4.1/v2协议。F0自身的0/10/0仅为一致性锚点。所有分析为描述性，不给出显著性或普遍优越性声明。'''
 write('正文表格与建议中文正文.md',f'''# Reviewer1 4.5 正文表格与建议文字

以下为可供作者整合的草稿，本轮没有修改投稿正文。表号、图号和页码待作者插入后填写。

## 组件消融主表

{tab1}
{notes}

F1采用冻结flat替代机制，不能理解为仅删除一个容器而其他可达候选集合完全相同。F3把disagreement的10个席位补到proxy_top，F6—F8使用统一25/0/15/10/10席位及冻结补足规则；F9同时把候选池改为随机30k并随机化代理优先级，A/B仍保留真实UE排序，C/D/LS不变。因此这些是冻结流程变体比较，不能把所有最终差异完全归因于一个独立组件。

## 计算时间分解表

{tab2}
单位秒，先平均三个种子再平均10个情景。候选准备包含代理推断及候选生成/筛选，UE网络调用包含求解和调用开销，LS管理排除UE调用，其他搜索管理为剩余搜索记账。四项互斥且逐运行相加等于真实在线总耗时。代理推断与UE内核分别是前两项的嵌套计时，不能再次相加。输入加载、模型加载与开发预热、输出写盘及历史训练费用不在此在线范围内。

## 建议中文正文

在十个预先冻结的新严重洪水情景上，每个流程变体采用三个固定种子和256个唯一UE状态预算，共完成300次组件消融及30次Greedy-ILS对照。完整F0的平均regret为1.3093%，中位数为0.2628%。F1、F5及F9的平均regret分别为0.6693%、0.5606%及0.9290%，但分别仅在2、2及4个情景优于F0。均值与逐情景胜负的差异与5102的较大影响一致，不能据此认定复杂组件普遍无效。5102始终保留在主分析中，全部十种留一分析另行作为敏感性结果报告。

F6、F7和F8的平均regret为0.3120%、0.3244%和0.3364%，Greedy-ILS为0.2299%。这些观察未建立十成员ensemble或完整代理流程相对简化代理和UE-only强基线的整体优势。5102日志显示，候选池中存在首路18序列并不保证其进入Reserve或获得完整UE评价；F0两个种子最终停在首路29，另一个种子在后期LS中转向首路18。该案例揭示了候选门控、已缓存状态和有限查询预算之间可能存在的相互作用，其因果强度和普遍性尚未由本实验识别。

共同状态误差与共同候选池排序诊断进一步区分了预测拟合和决策排序。四种冻结模型的候选J平均Spearman相关分别为0.259、0.225、0.246和0.199。简化模型并非在所有预测或排序指标上一致领先，预测精度也不能直接替代完整流程中的优化质量。上述结果支持报告组件作用的情景依赖性与真实搜索成本，而不足以证明每个组件具有可分离、稳定的独立增益。
''')
 report=f'''# Reviewer1 第4.5条 S4 机制与鲁棒性中文验收报告

生成时间：{now()}。状态：完成用户指定S4分析，等待作者评估是否需要额外补强。本轮没有执行900次旧情景回放，没有补跑优化或生成压缩包。

## 结论及验收范围

S4基于已封存的S3 330/330次成功运行及10/10张完整高精度UE表完成。保留全部5101—5110，不修改任何方法、种子、参数或模型。冻结v2 SHA256为`{EXPECTED}`。所有方法输出封存早于完整参考计算的历史记录仍有效，S4事后参照只用于解释和评价，不回流到任何优化流程。

最重要的更正是：**5102的F0并非三个种子同样失败**。种子0和2最终regret为13.671259%和13.816433%，首路29；种子1在后期LS中转向首路18，最终regret为0.075854%。本轮把失败路径与恢复路径分开，不能把5102解释为所有组件、所有种子普遍失效。

{tab1}
{notes}

## 5102：从候选保留到实际评价

条件DP参考J*={ref(5102)['objective']:.14f}，一条最优序列为`{'|'.join(map(str,ref(5102)['sequence']))}`。仅用现有状态表作条件递推，限定首路29的最优J={cond.loc[29,'conditional_optimum_J']:.14f}，regret={cond.loc[29,'conditional_optimum_regret_pct']:.6f}%；首路18可达到全局条件DP最优。道路29并不等于“无效道路”，而是在该情景中限制第一步为29会形成一个可量化的质量下界。F0种子0最终J等于该首路29条件最优值。

**直接日志证据**：三个F0原始30k池分别有2513、2553、2474条首路18序列，其最小代理排名为9017、9047、9017；首路29计数为2494、2536、2517，最小代理排名6962、6975、6986。F0 Primary60中首路18计数0/4/0，首路29计数1/2/0。种子1的四条首路18来自random三条及sequence_diversity一条。Reserve中首路18和29均为零，三个种子的C阶段完整序列全部以16开头。Primary60中“存在”不能当作“已经得到UE完整评价”。

**有序前缀与缓存证据**：F0的A阶段十个有序二路前缀为16|10、16|11、10|16、16|14、10|11、16|20、11|16、16|29、11|10、10|14；没有首路18或29。由真实UE前缀分数排序，先扩展16|29、16|14、10|14、11|10，其余随后扩展。集合缓存不区分道路恢复顺序，但候选队列使用有序prefix3，两者不能混为一谈。完整A请求表保留缓存命中，包括16|10与10|16共用的二路集合。

**从源码规则可确定的推论**：disagreement仅在代理前30%（排名≤9000）中选取，所以该情景F0首路18不具备这一渠道的资格。不能因此说所有渠道均排除了18，因为种子1的多样性和随机渠道实际保留了四条。C队列要求相应有序prefix3在Reserve构造的可用前缀集合中；这四条的prefix3均不在其中，日志也显示未在C阶段完成。这是“保留进Primary但没有转化为C评价”的具体门槛。

三个F0首个完整序列的预算均为46，J分别为92.35355386567618、90.80756834927790、91.66543863964216。第一次首路29完整评价均发生在预算54、D_local_search阶段。种子0和2从未查询单路18状态，也未完成任何首路18序列；种子1在首见UE查询239查询单路18，预算240完成`18|11|10|16|29|20|26|14|6|4`，J=64.00050778302612，随后改善到63.92912523405662。其首路18完整评价共66条。这些均来自原始账本，没有进行轨迹回放。

该次恢复的唯一已记录父边为`29|11|10|16|18|20|26|14|6|4`到`18|11|10|16|29|20|26|14|6|4`，移动为arbitrary_swap，交换位置1与5。也就是说，18在这一父解中先被保留在第5位，随后与首位29交换；这是原LS实际完成的评价，不是S4推演出的修复序列。

{casetab}

F1三个种子的首次LS前regret均为88.4449%，明显高于F0约42%，但最终均为0.075854%，首路18。这说明在该案例中，较好初始完整解并不足以保证较好最终解。F1在预算206—208完成首条首路18序列。F6与F7最终也以18开头，不过首次完整序列都以14开头，且其单路18预测同样并非最优；不能把它们的恢复归结为“准确预测了道路18”。F9保留真实UE排序，在A阶段已查询道路18，首个完整序列即以18开头。Greedy-ILS的第一个完整序列在预算55已达到DP参考值。F3虽然改变了Primary渠道，但5102三个种子的状态请求、理由、缓存命中和完整序列评价轨迹均与F0完全相同，见轨迹一致性核验JSON。

**有限机制解释，不能当作已证实因果**：原LS优先排序按候选缺失状态数、相邻交换优先级、位置和父解目标值决定。在第一次LS入口处，F0三个种子的首路29邻居最小缺失状态数均为1，首路18邻居分别至少缺失6、5、2个状态，静态队列中首次出现的排名分别为276、294、108；第三次LS入口处，首路18最少缺失5、3、5个状态。此静态入口清单与已观测路径支持“缓存覆盖和预算优先级可能影响可达搜索方向”的解释，但入口之后缺失数和父节点会动态改变。没有反事实补跑，不能声称只调整某个门槛就必然修复失败，也不能把静态排名当成实际完整LS轮次排名。父子谱系文件保留首条记录边，并标记同一子序列的重复父节点元数据。

主要证据：{link(S4/'02_case5102/5102_run_path_summary.csv')}、{link(S4/'02_case5102/5102_stage_firstroad_counts.csv')}、{link(S4/'02_case5102/5102_primary18_29_gate.csv')}、{link(S4/'02_case5102/5102_ordered_prefix_requests.csv')}、{link(S4/'02_case5102/5102_incumbent_trace.csv')}、{link(S4/'02_case5102/5102_parent_lineages.csv.gz')}、{link(S4/'02_case5102/5102_static_LS_entry_opportunities.csv')}。候选池逐条真实目标由既有表事后标注，未提供给原筛选器。

## 全体十情景鲁棒性与5102影响

{tab3}

F0的5102平均regret=9.187849%，给全体平均值贡献0.918785个百分点，占十情景regret总和约70.17%。这既不能忽略，也不意味着5102应被剔除。全体主结果F0=1.309337%，保留5102。

F1相对F0全体均差−0.640055pp，而其逐情景差中位数+0.178621pp，胜/平/负2/2/6；F5均差−0.748720pp，中位数+0.048197pp，2/0/8；F9均差−0.380316pp，中位数+0.669607pp，4/0/6。作为十种对称留一敏感性中的一种，留出5102时三者均差分别为+0.301272、+0.086076、+0.592589pp。F4也出现这一方向改变。这里只描述影响，不用九情景替代十情景主结论。

F6、F7、F8在全部十种留一情况下平均差仍小于0，范围如表；这说明相对F0的该组均值差不完全由5102决定，但仍不能当作模型普遍优越、显著差异或可归因于纯预测器的因果结论。其逐情景胜平负分别4/0/6、5/2/3、4/1/5，简化模型参数与模型身份在见新情景结果前已冻结，本轮没有据此重新选择模型。Greedy-ILS平均regret及耗时均低于F0，本实验不支持完整代理流程相对UE-only强基线具有整体优势。

完整逐情景均值/均差、种子中位数/P90/最大值/SD/极差/IQR和配对种子胜负见{link(S4/'01_statistics/scenario_seed_statistics.csv')}；所有10×11=110条LOSO见{link(S4/'01_statistics/LOSO_all10_omissions.csv')}。另按冻结v2的种子2026102906进行10000次情景配对自助抽样，95%百分位区间单独保存在{link(S4/'01_statistics/frozen_v2_descriptive_paired_bootstrap.csv')}，仅作描述性不确定性，不据区间是否跨零宣布显著性。无需事后挑选留出项或阈值。

## 阶段UE、完整序列与LS效率

{phtab}

表中A/B/C/LS是冻结流程阶段。Greedy-ILS另有greedy、greedy_complete、restart等阶段，因此该行前四列不构成完整预算；全部阶段长表保留这些记录。每个方法实际预算均256，330次预算利用率100%。每个状态只由首次出现阶段计一次UE费用；同一状态后续多次被不同序列请求仅计缓存命中。完整序列评价以complete_sequence_history中唯一sequence_id为准。首次建立可行incumbent单独计数，不算严格改善。严格改善按有限的before/after目标差判断，非κ平局标准，微小浮点改善可被记录，原始J供复核。

F0阶段平均首见UE分别A={phase[(phase.variant_id=='F0_FULL')&(phase.phase=='A_prefix2')].iloc[0].first_seen_UE_states:.2f}，B合计42.13，C=101.90，LS=100.57。F0每次运行平均完成752.77条唯一完整序列，平均625.33条不需新增UE状态，每个唯一UE状态对应2.9405条完整序列；这些高缓存复用率不等于获得相同数量的独立UE信息。F1约7.7305条完整序列/UE状态，但搜索管理开销也更高。全组移动日志中存在{int(budget.duplicate_local_move_metadata_rows.sum())}条重复子序列元数据，这些没有作为新评价或新增UE再次收费。

F0首次LS前/后平均regret为13.705898%/5.368309%，各次LS目标下降折算的总regret降低为12.261312pp。各阶段改善是观测归属，不是独立因果贡献：A/B常在尚无完整incumbent时查询有用前缀，不能因“当时没有incumbent改善”就认为查询无效。最终路径/选定DP路径状态的首见阶段也已输出，只表示事后路径兼容性，不能把不在这两条路径上的查询都称为浪费。

阶段账本：{link(S4/'03_phases_costs/phase_accounting_all_runs.csv')}；运行级预算与缓存：{link(S4/'03_phases_costs/run_budget_cache_management.csv')}；首次LS质量：{link(S4/'03_phases_costs/first_LS_quality_all_runs.csv')}；路径状态来源：{link(S4/'03_phases_costs/queried_state_path_provenance.csv.gz')}。缺少可分配到每个A/B/C区块的独立墙钟计时，因此本轮不从请求时间戳拼造阶段总管理时间；运行级搜索管理与逐次LS计时是已有实测证据。

## 共同状态预测与共同候选池排序

{predtab}

每个情景对四模型使用同一1024状态，cost=exp(log预测)−1，ensemble先变换各成员再平均，log量为log(平均exp预测)，没有误用成员log预测的简单均值。表内状态误差先按情景计算再平均十情景，不把40960预测行作为独立样本。按恢复道路数分层误差另存，避免用中间恢复状态数量较多的全状态均值替代早期前缀质量。Single MLP严格等于冻结ensemble的member01预测，未择优挑成员；十个成员的cost误差全部保存。

共同候选池为每情景三个冻结F0 30k池，共30池。只重评分，不重新生成候选、求解UE或执行局部搜索。按纯分数top10/60/300和统一Primary60配额25/0/15/10/10分别诊断，真实目标在选择完成后才附加。ensemble共同Primary60与原S3 F3实际Primary候选/渠道在全部30池完全一致，ensemble复算目标与封存分数误差小于1e−10，实际排序沿用封存值消除浮点重排。共同Primary60最佳regret表示“这个已固定集合中最好的序列可获得多少”，不是优化运行的最终regret；共同池本身由F0构造，结论有生成分布的条件性。

共同池平均Spearman相关ensemble=0.258791、single=0.225036、Ridge=0.245515、HGB=0.198678，均不足以单靠全池相关证明顶端决策准确。5102三种子平均相关分别0.011312、−0.034550、0.142847、−0.083534。道路18真实单路状态cost=109.376193，为十路最低；四模型预测其名次分别6、8、5、7，ensemble把16预测为最低。所有模型都有该前缀局部误排，F6/F7仍能通过后续流程找到18，进一步限制“一个状态预测排名决定最终成败”的说法。cost尺度平均R²均可为负，说明相对每情景常数基准存在明显失配，不用较高的状态Spearman掩盖幅度误差，也不据本次测试重新训练或校准模型。

预测及模型诊断见{link(S4/'04_prediction_diagnostics/common_state_errors_by_scenario.csv')}、{link(S4/'04_prediction_diagnostics/state_errors_by_restored_count.csv')}、{link(S4/'04_prediction_diagnostics/common_pool_topK_primary_quality.csv')}、{link(S4/'04_prediction_diagnostics/5102_firstroad_ranking.csv')}、{link(S4/'04_prediction_diagnostics/5102_singleton_prediction_ranking.csv')}。共同池逐条预测和真实目标保存在该目录30个`common_F0_pool_*_scores.csv.gz`文件。

## 实测时间与离线训练成本

{tab2}

F0候选准备约7.046s，其中代理推断嵌套计时约0.0408s；不能把候选准备都归为神经网络推断。F1准备更省但其他搜索管理更贵，合计与F0接近。F9约7.850s，Greedy-ILS约5.394s。S3真实在线计时单进程CPU0、各数值库单线程、一次一个任务，每次方法任务从空物理缓存开始；在线UE调用是新鲜实际求解，与早期sealed lookup replay完全区分。本轮共同状态预测的计时仅为事后诊断推断时间，不当作正式在线耗时，也不把历史UE秒数加到lookup耗时中。

历史4.3测量十成员训练外层21.5322s，member01训练函数约1.9307s，内部计时嵌套，不重复相加。该次旧标签3178状态生成测量58.7836s及各组件和80.4004s仅作历史部署成本背景，**不是本轮从新标签到新模型的端到端训练**。本轮训练次数为0。第一批固定Ridge/HGB训练费用分别0.02792s/0.79894s，共享数据加载0.10100s、特征变换0.09910s单列，不给每个模型重复累计。在线不摊入训练，也不宣称离线零成本。已归档训练费用及出处在03_phases_costs中。进程RSS是包含此前已加载模型的常驻进程总量，不当作方法独占内存。

## 图件、文字及数据完整性

已生成四张可编辑PDF/SVG、600dpi PNG及源CSV。图1为5102机制，图2为全体10情景及全部留一敏感性，图3为四冻结预测器诊断，图4为真实在线成本分解。图注单列，解释原始种子曲线、均值、范围及非因果边界。源代码预检、实际面板对齐、PDF字形字号与碰撞检查在05_figures中，最终视觉检查记录单列。

英文回复是Reviewer1 4.5单条的**草稿**，含表图号、页码位置占位；本轮未修改投稿正文，也未声称已经在具体页码插入。作者整合正文和确认编号后再发出。没有建立“所有组件无效”或“代理相对UE-only整体更优”的结论。

原330次目标与真实在线分项的完整源CSV：{link(DELIVERY/'all_successful_runs_regret_and_cost.csv')}。本轮无数值失败或缺少情景，因果识别与缺少阶段墙钟等证据限制见{link(R/'缺失数据与证据边界.md')}。文件目录见{link(S4/'主要结果文件索引.md')}。
'''
 write('S4_中文验收报告.md',report)
 write('5102_逐路径中文证据说明.md',report[report.index('## 5102：'):report.index('## 全体十情景鲁棒性')])
 write('缺失数据与证据边界.md','''# 缺失数据与证据边界

正式数值分母完整：10/10情景、330/330优化输出、10240/10240既有参考状态。本轮没有剔除、替换、补跑或新情景。数值缺失为0，不表示机制证据无边界。

|项目|实际情况|处理|
|---|---|---|
|单路18/首路18评价未出现|F0 5102种子0和2确实未查询/未完成|记为“未观测”，不是文件缺失；不填0目标、不补算优化|
|Primary/Reserve没有目标标签|原筛选时依规没有真实目标|S4仅用已封存表事后附加，清楚区分原始决策信息与事后证据|
|首次完整序列之前的incumbent改善|incumbent尚未建立|初次建立单列；相应阶段边界目标下降不可定义，保留NA而非任意零改善|
|恢复数0或10分层的R²/相关|各情景只有一个状态，分母或方差不可定义|按数学定义保留NA，不当作原始数据缺失或方法失败，不填为0或1|
|阶段管理总墙钟|无独立A/B/C区块墙钟计时|报告运行级四项互斥分解和逐次LS实测；不由稀疏请求时间戳拼造区块时间|
|局部移动重复子序列|同一子序列可能有多个父节点元数据|按唯一完整序列计评价，按首次mask计UE，谱系标记歧义|
|LS入口清单|可重建入口的父解/已知mask并列出一步邻居缺失数|仅静态规则诊断，不作为完整动态轮次重放或因果反事实|
|未完成/不可达反事实序列|没有原在线决策轨迹|不补跑，不声称具体更改能必然修复5102|
|完整1024状态误差分布|按状态均匀，恢复数中间层占比大|同时输出恢复数分层指标；状态和候选不当作独立情景|
|共同池排序|F0生成分布，三冻结种子|解释限定在该共同池；不替代F6—F8原生候选流程或新在线实验|
|模型选择|所有模型身份和参数先前冻结|本轮四模型及十成员全部报告，不选择表现更好的模型、不训练/校准|
|种子不确定性|每情景三个技术重复|以10情景为主分母，报告种子SD/极差及全部LOSO；自助区间仅描述性|
|历史训练成本|来自4.3和第一批S0—S2|明确历史来源，嵌套计时不重复加，不声称本轮重新测量端到端训练|
|方法独占内存|仅有整个持久进程RSS|不作独占内存或部署增量内存比较|
|正文页码/表图编号|未实际整合正文|回复草稿保留明确占位，待作者定位|
|900次retrospective|依用户本轮范围不执行|不是正式新情景数值丢失，不据此调参|

主结果始终保留5102。所有留一结果只作敏感性。没有显著性声明，没有把单案例推广为普遍规律，没有证明所有组件无效，也没有建立代理流程相对UE-only强基线的整体优势。
''')
 write('S4_中文结论与主张边界.md','''# 可用于修改论文的中文结论

冻结的匹配UE预算实验显示，各组件改变的是候选可达性、状态复用和后续搜索路径，结果具有情景依赖性。完整F0不能在本组十个新情景中建立对单MLP、Ridge、HGB或Greedy-ILS的整体优势；也不能从几个变体较低的全体平均regret推导所有复杂组件无效。

Reserve与候选来源方面，F1、F5在多数情景不及F0，却受5102较大质量差影响而获得较低总体均值。F9在6/10情景不及F0，说明代理相关流程可能在若干情景有用，但F9也同时改变候选生成和排序，所以不能单独量化“纯预测器净价值”。disagreement消融F3在9/10情景与F0相当，在5102全部实际查询轨迹相同；这只能限定为在本预算、冻结补位方式和观测情景中的有限边际证据。

5102揭示一个具体的候选保留到查询之间的脱节：首路18存在于池中，甚至可能进入Primary，却没有进入Reserve支持的有序前缀队列。两个种子最终首路29，另一个种子靠后期LS恢复。已有日志支持门控和有限预算搜索路径相互作用的解释，但不能识别唯一原因或证明反事实修复。

共同状态误差、共同池排序和最终regret需要分开报告。较低预测误差并不自动意味着更好的顶端候选或最终序列，十成员ensemble也没有在全部指标上优于简单代理。已有UE局部搜索显示明确的观测改善，但改善次数和查询归属不能直接当作阶段独立因果贡献。

建议收缩“每个组件独立有效”和“代理相对强UE-only基线总体占优”等未获支持的表述，保留完整流程作为一个已冻结系统，并如实报告稳健性、成本及失败边界。当前不依据这些结果改架构、改模型或补跑优化。
''')
 # Export compact main tables as exact numerical CSV, not Markdown rounding only.
 csv(R/'Table_main_ablation.csv',su.reset_index().assign(component_definition=[DEFS[v] for v in METHODS]));csv(R/'Table_online_time_decomposition.csv',timeDF.reset_index());csv(R/'Table_common_prediction_diagnostics.csv',predrecords)
 response(su,notes)
 captions()
 index=['# S4 主要结果文件索引','',f'主目录：`{S4}`。无压缩包。全部主结果保留10个情景，330次原运行均未重跑。','', '## 首先阅读','']
 for n in ['S4_中文验收报告.md','正文表格与建议中文正文.md','Reviewer1_4.5_英文回复草稿.md','5102_逐路径中文证据说明.md','缺失数据与证据边界.md']:index.append('- '+link(R/n))
 index+=['','## 主要数值','']
 for p in [R/'Table_main_ablation.csv',S4/'01_statistics/scenario_seed_statistics.csv',S4/'01_statistics/LOSO_all10_omissions.csv',S4/'01_statistics/5102_influence_no_exclusion.csv',S4/'02_case5102/5102_run_path_summary.csv',S4/'03_phases_costs/phase_accounting_all_runs.csv',S4/'03_phases_costs/first_LS_quality_all_runs.csv',R/'Table_online_time_decomposition.csv',S4/'04_prediction_diagnostics/common_state_errors_by_scenario.csv',S4/'04_prediction_diagnostics/common_pool_topK_primary_quality.csv',DELIVERY/'all_successful_runs_regret_and_cost.csv']:index.append('- '+link(p))
 index+=['','## 图件','']
 for name in ['Fig1_5102_mechanism','Fig2_full10_LOSO','Fig3_frozen_predictors','Fig4_online_time']:
  index.append('- '+link(S4/'05_figures'/(name+'.png'))+'；'+link(S4/'05_figures'/(name+'.pdf'))+'；'+link(S4/'05_figures'/(name+'.svg')))
 index+=['','## 全部文件','', '每个文件的字节数及SHA256另见00_audit/S4_output_manifest.csv。CSV.gz为单文件gzip数据，不是交付压缩包；用于保存既有大量逐候选、逐状态记录。','']
 for folder in ['01_statistics','02_case5102','03_phases_costs','04_prediction_diagnostics']:
  index.append('### '+folder+'\n')
  index += ['- '+link(p) for p in sorted((S4/folder).iterdir()) if p.is_file()]
 (S4/'主要结果文件索引.md').write_text('\n'.join(index),encoding='utf-8')
 dump(R/'response_status.json',{'comment':'Reviewer1 4.5','status':'draft_with_placeholders','manuscript_integrated':False,'open_items':['author assigns final table and figure numbers','author inserts text and checks page/line locations'],'unsupported_claims_removed':True,'no_other_reviewer_cross_reference':True})
 print('S4 report and bounded English draft written',flush=True)

def response(su,notes):
 comment='''4.5 The component-level evidence is incomplete

The no-local-search ablation supports UE local correction within the complete workflow. It does not separately identify the value of prefix stratification, the reserve, ensemble disagreement, candidate-source mixtures, or a ten-member ensemble. The authors appropriately refrain from claiming independent contributions for every channel, but the architecture remains more complex than the evidence presently justifies.

Matched-budget ablations should include removal of the reserve, random or heuristic candidate generation followed by the same UE correction, and a single or simpler surrogate followed by the same search. Tracking useful states and improvements by search phase would show whether gains arise from better initial candidates, more informative UE queries, or ordinary local optimization. The current experiment also does not establish that the network is preferable to inexpensive regression or tree-based surrogates.'''
 text=f'''# Reviewer1 Comment4.5 response draft

**Status for the author.** This is a bounded response draft based on completed S3/S4 evidence. No manuscript insertion has been made in this analysis batch. Replace the explicit location and numbering placeholders after integrating the accompanying text, tables and figures. This draft must not be sent with placeholders retained.

## Reviewer comment

{comment}

## Response

We agree that evidence for UE local correction does not identify the independent value of every component. We therefore completed a frozen matched-budget experiment with ten workflow variants and a Greedy-ILS comparator on ten new severe-flood scenarios, using three fixed seeds per scenario. The300 ablation runs and30 comparator runs all used B=256 unique UE states. Method outputs were sealed before the complete1024-state UE tables and conditional dynamic-programming references were constructed. No failed scenario was removed, and no variant, parameter, seed or model was changed in response to these results. The accompanying analysis uses these sealed observations only.

The variants remove the reserve with its predefined flat replacement (F1), prefix-stratified generation (F2), disagreement seats with predefined quota replacement (F3), or proxy-based DP/GA sources (F4). F5 uses a random30,000-sequence pool but retains surrogate screening. F6–F8 use the fixed member01 MLP, Ridge or histogram gradient boosting, respectively. Crucially, F9 uses no surrogate predictions or model access. It replaces proxy-dependent generation and priority with fixed-seed random alternatives while retaining actual UE prefix ranking and the same inherited complete-sequence correction and local search. These are workflow comparisons. F1 changes candidate eligibility through the frozen replacement, and F9 changes both generation and ranking, so neither difference is an isolated causal estimate of a single scoring component.

All ten scenarios remain in the primary analysis. Mean regret was1.3093% for F0,0.6693% for F1,0.5606% for F5 and0.9290% for F9, but the corresponding scenario-level wins/ties/losses against F0 were2/2/6,2/0/8 and4/0/6. We report medians, P90, maxima and seed dispersion alongside means. We also report all ten symmetric leave-one-scenario-out summaries, rather than selecting an exclusion. Scenario5102 accounts for approximately70.17% of the sum of F0 scenario regrets. Omitting it for sensitivity alone changes the F1, F5 and F9 mean differences from−0.6401,−0.7487 and−0.3803 percentage points to+0.3013,+0.0861 and+0.5926. This sensitivity does not replace the full-cohort results or justify removing5102.

The mean regrets for the fixed single MLP, Ridge and HGB workflows were0.3120%,0.3244% and0.3364%, compared with0.2299% for Greedy-ILS. These observations do not establish an overall advantage of the ten-member ensemble or complete surrogate-guided workflow over inexpensive predictors or the strong UE-only comparator. They also do not demonstrate that every component is ineffective. We make no confirmatory significance claim; the independent descriptive unit is the scenario, with seeds averaged within scenario.

The5102 audit distinguishes two unsuccessful F0 paths from one recovery. Each frozen F0 pool contained approximately2500 sequences beginning with road18. None entered the reserve. Seed1 retained four such sequences in Primary60, but their ordered three-road prefixes were absent from the reserve-supported seed queue and none received a C-stage complete evaluation. All C-stage sequences began with road16. Seeds0 and2 never queried the singleton18 state and terminated with road29 first, at13.6713% and13.8164% regret. Seed1 queried singleton18 at unique query239, completed its first18-first sequence at budget240 and ended at0.07585% regret. F1 started with worse first-LS quality in this scenario yet recovered to the same near-optimal final value for all three seeds. F3 had exactly the same observed state-query and complete-sequence trajectories as F0 in this scenario. These are direct logged facts. Static LS-entry inventories are consistent with an interaction between candidate gating, cached states and finite-budget move priorities, but we have not run counterfactual searches and do not claim a uniquely identified cause or a general failure mechanism across scenarios.

Phase accounting now bills each state only at its first occurrence and counts each complete sequence once. Initial incumbent establishment is separated from subsequent strict improvements. Duplicate parent–child metadata are not billed as new UE calls or complete evaluations. For F0, mean regret immediately before and after the first LS was13.7059% and5.3683%. Such observed improvements do not identify independent causal phase contributions, and an early prefix query can be useful before a complete incumbent exists.

We additionally evaluated all four frozen predictors on the same1024 states per scenario and rescored the same30 frozen F0 candidate pools without new candidate generation or UE correction. Mean candidate-objective Spearman correlations were0.259,0.225,0.246 and0.199 for ensemble, single MLP, Ridge and HGB. Prediction errors on both cost and log-ratio scales, restored-count strata, top-K quality and a common60-seat diagnostic are reported separately. These diagnostics distinguish fit, ranking and final search performance; they were not used for fitting, tuning or model selection. In particular, the single MLP was fixed as member01 before observing these scenarios.

Measured fresh online times averaged13.222s for F0,7.850s for F9 and5.394s for Greedy-ILS. We separate candidate preparation, live UE calls, LS management and other search management, and report historical training costs separately. Nested inference and UE-kernel timers are not added twice. Lookup replay time and current posthoc inference time are not presented as live UE solving time.

Proposed manuscript locations after author integration: [PAGE/LINE TO BE FILLED], [TABLE NUMBER TO BE ASSIGNED], [FIGURE NUMBERS TO BE ASSIGNED] and [SUPPLEMENT LOCATION TO BE FILLED]. The proposed replacement conclusion is:

*The frozen matched-budget comparisons reveal scenario-dependent effects of candidate construction, selection and subsequent UE correction. They do not establish separable benefits for every component, a general need for a ten-member ensemble, or an overall advantage over a strong UE-only baseline. The5102 audit identifies an observed gap between candidate availability and actual evaluation, while the causal strength and generality of this mechanism remain unresolved.*

## 中文核对与发送前待办

回复仅覆盖4.5，不引用其他审稿人的问题。所有结果来自已封存S3及本轮只读诊断；未声称补跑或修改算法。5102保持主分母10/10。F0两个失败种子与一个恢复种子分开。F9保留真实UE排序，非完全随机优化。F5仍用代理。F3、F6—F8的席位补足和F1的flat替代需要与正文定义一致。英文没有宣称已插入具体正文页码，定位占位需要作者整合后填写。

主表及全部原始数值见同目录与主要结果索引。草稿有意不使用“所有组件无效”“统计显著”“代理对强UE-only整体占优”等不被证据支持的表述。
'''
 # Keep numbers readable without modifying the quoted reviewer comment.
 import re
 before,body=text.split('## Response',1)
 body=re.sub(r'(?<=[a-z])(?=\d)', ' ',body)
 body=re.sub(r'(?<=\d)(?=[a-z])', ' ',body)
 body=re.sub(r',(?=[0-9−+])', ', ',body)
 body=re.sub(r'(?<=[a-z])(?=[−+])', ' ',body)
 body=body.replace('F6–F8','F6 to F8').replace('parent–child','parent and child').replace('its first 18-first sequence','its first complete sequence beginning with road 18')
 write('Reviewer1_4.5_英文回复草稿.md',before+'## Response'+body)

def captions():
 write('S4_图注与源数据.md',f'''# S4 图注与源数据

**Figure1. Observed candidate gating and search paths in scenario5102.** (a) Counts of F0 sequences starting with road18 in each frozen pool, Primary60, Reserve, completed C evaluations, completed LS evaluations and final output, for all three seeds. Cell shade encodes log(1+count); printed counts are exact. Stages are not a nested funnel because LS creates new sequences. (b) Logged incumbent regret against unique UE budget for all F0 seeds and seed0 of F1 and Greedy-ILS. No incumbent curve is drawn before a complete sequence exists. F0 seed0/2 curves overlap in part. F3 has identical observed trajectories to F0 in this case and is not overplotted. Other control seeds remain in the numerical audit. (c) Seed-mean regret before/after the first LS and at termination for the seven requested methods. Horizontal final error bars denote the minimum and maximum of three seeds, not confidence intervals. (d) Logged position of road18 in the F0 incumbent; position1 is at the top. All panels describe one scenario and do not estimate an independent component effect or counterfactual repair. Source:02_case5102 stage counts, run summary and incumbent trace.

**Figure2. Full-cohort differences and all leave-one-scenario-out sensitivities.** (a) All ten scenario differences in seed-mean regret between each alternative and F0. Negative values favor the alternative. Orange identifies5102; black diamonds give the full-ten mean. (b) All ten leave-one-scenario-out mean differences, each based on nine scenarios, with omission of5102 highlighted. Black diamonds remain the full-ten means. These omissions are sensitivities only and never replace the main ten-scenario analysis. Point offsets are deterministic display offsets, not additional measurements. The three seeds are averaged within each scenario; no significance test is shown. Source:01_statistics/scenario_seed_statistics.csv and LOSO_all10_omissions.csv.

**Figure3. Common-state prediction and common-pool ranking by four frozen predictors.** (a) Log-ratio R² computed separately on the same1024 UE states for each of ten scenarios. Ensemble log prediction is the logarithm of the mean exponentiated member predictions, consistent with deployed mean-cost scoring. (b) Spearman correlation between predicted and reference candidate objectives on the same frozen F0 pools, averaged over three seeds within each scenario. Orange identifies5102 and black diamonds denote the ten-scenario mean. All scenarios are shown, including negative R² or negative correlations. States and candidates are correlated observations, not independent replicates. These are read-only diagnostics and do not involve new generation, UE search, fitting or model selection. Source:04_prediction_diagnostics/common_state_errors_by_scenario.csv and common_pool_metrics_scenario_means.csv.

**Figure4. Measured fresh online time decomposition.** Bars are means of three seeds within scenario followed by equal weighting of all ten scenarios. Mutually exclusive components are candidate preparation, live UE network calls, LS management excluding UE and other search management. Points show all ten scenario mean total times. Source timings are S3 single-process, single-thread, CPU0 measurements with a fresh physical cache for each method task. Candidate preparation includes inference, and live UE network calls include kernel solving; their nested timers are not stacked again. Historical training, input/model loading, warm-up and disk export are outside this online scope and are separately documented. Neither sealed lookup replay nor S4 posthoc scoring is presented as live UE time. Source:03_phases_costs/Table_time_decomposition.csv and time_components_scenario_means.csv.

所有最终图为183mm宽，PDF/SVG文字可编辑，PNG600dpi。报告中的预览为PNG；最终排版使用PDF/SVG。没有截断异常点、缩小情景分母或挑选代表种子以替代完整数值。图1b只为控制曲线减少重叠而展示F1/Greedy种子0，全部三个种子及其他对照均在图1c与CSV中报告。
''')

if __name__=='__main__':run()
