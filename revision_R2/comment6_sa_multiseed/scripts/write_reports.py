from common import *
def mdtable(df,cols,dec=6):
 def fmt(v):
  if isinstance(v,(float,np.floating)):return f'{v:.{dec}f}'
  return str(v)
 return '| '+' | '.join(cols.values())+' |\n| '+' | '.join('---' for _ in cols)+' |\n'+'\n'.join('| '+' | '.join(fmt(r[k]) for k in cols)+' |' for _,r in df.iterrows())
def put(name,text):(OUT/name).write_text(text.strip()+'\n',encoding='utf-8')
def main():
 f=read(OUT/'raw/SA_all100_runs.csv');per=read(OUT/'Table_R2C6_holdout_per_scenario.csv');rep=read(OUT/'Table_R2C6_per_replicate.csv');cmp=read(OUT/'Table_R2C6_comparison_to_Proposed.csv');overall=read(OUT/'Table_R2C6_scenario_level_overall.csv');context=read(OUT/'Table_R2C6_existing_new30_context.csv');a=js(OUT/'analysis_summary.json');ex=js(OUT/'audit/execution_validation.json');man=js(OUT/'run_manifest.json');env=js(OUT/'audit/environment.json');freeze=js(OUT/'audit/prospective_freeze.json');hits=read(OUT/'Table_R2C6_observed_numerical_hit_sequences.csv')
 sa=overall.iloc[0];single=overall.iloc[1];prop=overall.iloc[2];r0=rep.iloc[0];status=js(OUT/'final_validation.json')['status'] if (OUT/'final_validation.json').exists() else 'QA_PENDING';validation=js(OUT/'final_validation.json') if (OUT/'final_validation.json').exists() else {};protected=len(js(OUT/'audit/source_protection_before.json')['files']);numchecks=str(validation.get('checks_passed','待'))+'/'+str(validation.get('checks_total','待'));different=hits[~hits.matches_canonical_DP];threshold15=int(f.within_1_5_pct.sum());threshold3=int(f.within_3_pct.sum())
 table_cn=mdtable(per,dict(scenario_id='情景',mean_regret_pct='均值(%)',median_regret_pct='中位数(%)',P90_regret_pct='P90(%)',maximum_regret_pct='最大(%)',SD_regret_pp='种子SD(pp)',conditional_optimal_hits='命中/10',mean_queries='平均查询'))
 table_en=mdtable(per,dict(scenario_id='Scenario',mean_regret_pct='Mean (%)',median_regret_pct='Median (%)',P90_regret_pct='P90 (%)',maximum_regret_pct='Max (%)',conditional_optimal_hits='Hits / 10',mean_queries='Mean queries'))
 overall_cn=mdtable(overall,dict(cohort='统计向量',mean_regret_pct='Mean(%)',median_regret_pct='Median(%)',P90_regret_pct='P90(%)',maximum_regret_pct='最大(%)'))
 rep_cn=mdtable(rep,dict(replicate='重复组',mean_regret_pct='均值(%)',median_regret_pct='中位数(%)',P90_regret_pct='P90(%)',maximum_regret_pct='最大(%)',conditional_optimal_hit_count='命中/10',queries_total='查询总数'))
 context_en=mdtable(context,dict(method='Method',independent_scenarios='Scenarios',mean_scenario_mean_regret_pct='Mean (%)',median_scenario_mean_regret_pct='Median (%)',P90_scenario_mean_regret_pct='P90 (%)',maximum_scenario_mean_regret_pct='Max scenario mean (%)'))
 proposedtable=mdtable(cmp,dict(scenario_id='情景',Proposed_frozen_regret_pct='Proposed冻结路径(%)',SA_mean_regret_pct='SA十种子均值(%)',SA_mean_minus_Proposed_regret_pp='SA−Proposed(pp)',SA_runs_better='SA较低次数',SA_runs_tied='容差平次数',SA_runs_worse='SA较高次数'))
 put('Comment_R2_6_SA_multiseed_results_CN.md',f'''
# Reviewer 2 Comment 6：SA多随机种子补充实验及中文验收报告

本轮状态：**{status}**。100/100次高精度SA独立搜索已实际完成；旧精度复现180/180项通过，最终自动验收{numchecks}项通过。新增真实UE=0、DP重算=0、Full重跑=0、SA-restart重跑=0、代理训练=0。全部负面和不变结果保留；本轮结束，不合并主稿、不开展其他审稿任务。

## 1. 结论与证据边界

以10个情景为统计单位，先在情景内平均10种子，SA的均值Regret为{sa.mean_regret_pct:.6f}%，中位数{sa.median_regret_pct:.6f}%；原Proposed单个B256冻结路径高精度重评分别为{prop.mean_regret_pct:.6f}%和{prop.median_regret_pct:.6f}%。但SA场景均值向量的P90为{sa.P90_regret_pct:.6f}%，高于Proposed的{prop.P90_regret_pct:.6f}%。SA单次最差Regret为{a['individual_max_regret_pct']:.6f}%，高于Proposed单个路径向量最大值{prop.maximum_regret_pct:.6f}%。不能声称任何一方总体支配另一方，论文应收缩Proposed整体优于强基线的表述。

SA共{a['SA_total_numerical_hits']}/100次达到冻结数值容差内的条件最优目标，严格浮点相等仅{a['SA_total_strict_zero']}/100次。Proposed对应4/10个数值命中，严格浮点相等2/10；命中条件完全相同。这100次是10个洪水情景内的随机技术重复，不是100个独立洪水样本。

原种子在高精度下重跑仍命中6/10，十组重复的命中数为{a['hit_count_range_by_replicate'][0]}—{a['hit_count_range_by_replicate'][1]}/10；6/10出现{int(rep.conditional_optimal_hit_count.eq(6).sum())}/10组。因此原种子命中数处于观测范围内；但原种子组平均Regret为{single.mean_regret_pct:.6f}%，为十组中最高，不能把“命中数常见”推广为“所有性能指标均典型”。

这是原holdout已被查看后的post-study稳定性补充，不是新盲测。不做显著性检验、不增加置信区间、不进行事后种子或算法选择，也不报告best-of-10作为单次B256结果。

## 2. 算法身份、复现阻断门与冻结

正式SA来自本地投稿包v2.2：`{SA_SOURCE}`；SHA256 `{man['SA_source_sha256']}`。与本地v2.0/v2.1及4.1原样快照分别做SHA交叉核对。配置ID742ec3e18494；原开发情景246/247/249，未在1001—1010调参。参数保持初温比0.0025、冷却0.995、相邻交换概率0.7、插入概率0.15、停滞1000个proposal、每次独立唯一状态预算256。

原函数122—186行搜索体通过AST原样执行，保留初始化、邻域、接受概率、以当前目标计算温度、对被预算拒绝proposal仍递增iteration、最优更新和停滞终止；仅隔离原函数187行起搜索后DP计算，并返回运行局部变量供只读审计。未改源文件。AST SHA `{man['search_AST_sha256']}`。接口与日志记录包装不消费额外随机数。

旧精度表`{OLD_TABLE}`上，原十场景/原种子完整重放：最终目标与原JSON完全相等（最大差0），最终顺序、查询状态访问次序、迭代、接受标记和计费全部通过180项检查。历史CSV浮点序列化对账门槛为事先设定8eps×max(1,|归档值|)，没有为结果事后放宽；最终目标本身零误差。旧1006的229次、1009的209次用量也重现。详见`audit/legacy_replay_validation.json`和逐项CSV。

正式100次前冻结manifest及种子：`seed=2026081000+scenario_id+100000×replicate`；replicate=0为原始种子，1—9为九个新固定种子。100个种子一一不同。冻结时间UTC `{man['created_utc']}`；manifest SHA `{freeze['run_manifest_sha256']}`。所有正式完成时间均晚于冻结。未删除失败情景、替换种子或改参数。

## 3. 高精度oracle、目标和单位

使用4.2已验收10张各1024状态表，mask完整、RG≤1e-9、有限值、物理道路bit序、solver源SHA、归一化和既有DP路径目标均核对。完整状态表由后端只读持有；搜索只能获得已合法计费mask的标量成本，禁止全表遍历、长度、slice和未授权读取。每次搜索新建oracle及RNG；无跨运行热启动或预算共享。整条序列若超出剩余预算，原子拒绝且不返回成本，不计部分状态。

`C(S)=TSTT(S)/TSTT0−1`，`J=(1/10)Σ[k=0..9] C(S_k)`；终态S10只在搜索完成后做轨迹核查，权重0，未向SA暴露。TSTT0原始单位值为{T0:.17g}、总OD需求Q={Q:.0f}；一次性换算TSTT(veh·h)=0.01×raw TSTT，ATT(min)=0.6×raw TSTT/Q。`ΔATT_mean_stage=ATT0×(J−J*)`，ATT0={ATT0:.12f}分钟/次。这是等工期模型隐含的平均阶段出行时间差，不是真实累计恢复工期或清障施工时长。

Regret%=100(J−J*)/J*；数值命中`abs(J−J*)≤1e-9×max(1,abs(J*))`，SA与Proposed共用。原始带符号Regret保留，最小{a['individual_min_regret_pct']:.17g}%是浮点舍入，未截断成0。J*及DP路径仅在搜索返回后用于评价；只读核对已有J*，本轮不计算DP。

命中判定针对条件最优目标而非某一条归档路径。观测到{len(hits)}种命中序列，其中{len(different)}种不同于其情景的归档DP序列；详见`Table_R2C6_observed_numerical_hit_sequences.csv`。这不构成对严格数学多解的完整证明，也不要求所有数值命中顺序逐位相同。

## 4. 全部逐情景结果

{table_cn}

P90采用NumPy linear，SD为ddof=1；极小负值显示为−0.000000仅为未裁剪舍入。完整表另含≤1.5%、≤3%计数、查询最小/最大值、绝对阶段ATT差的均值/SD/中位数/P90/最大值。所有运行合计≤1.5%为{threshold15}/100、≤3%为{threshold3}/100；这些是技术运行计数，不是新增独立样本。

### 同一情景与Proposed的匹配比较

{proposedtable}

SA情景均值较低3个、较高7个；SA的总体均值优势受1003的Proposed较大损失影响，不能推广为逐情景优势。100个种子与各自情景固定Proposed比较为较低43、数值平26、较高31，亦不当作100个独立样本作检验。

匹配的是同一洪水、原十路集合、目标、HP参照和B≤256上限。原Full档案运行上限实际为512，但本比较只读取`budget_snapshots_pre_reference.csv`预存B256顺序，并验证该顺序在≤256时已完成、路径状态属于前256唯一状态；未使用512最终结果。重要限制：SA本轮在HP反馈下搜索；Proposed是原低精度反馈选定的冻结路径，仅作HP重评。两者不能称作都在同一HP反馈下重跑。Proposed只有一个冻结候选/筛选种子实现；给定其队列的搜索条件确定性，不等于已估计其十种子方差，该SD留空。

### 情景级汇总和逐重复组

{overall_cn}

第一行P90/最大值作用于10个“情景内种子均值”；绝不是100次单运行的P90/最大值。SA最差单运行{a['individual_max_regret_pct']:.6f}%另行报告。

{rep_cn}

1008原种子为单次最差，1001亦存在约3.465%的劣势种子；图中全部可见。未删除、隐藏或挑选其余种子。情景间和种子间离散度见原始表，不以单个异常概括所有情景。

## 5. 预算与耗时

73次用满256唯一状态，27次原停滞规则退出。实际用量{a['min_actual_queries']}—{a['max_actual_queries']}，均值{a['mean_actual_queries']:.2f}，合计{int(f.queries_charged.sum())}次“每方法/每次运行特定”的逻辑计费；不能跨种子共享计费或强制补满。该合计不是新增真实UE次数。

100次sealed lookup搜索合计墙钟{ex['total_search_wall_s']:.6f}s、CPU {ex['total_search_CPU_s']:.6f}s；含日志导出总墙钟{ex['wall_with_exports_s']:.6f}s。计时包括只读oracle和被动内存日志，不含真实在线UE求解、既有1024表生成、文件落盘后的审计。不能把它宣称为在线UE执行速度或与Proposed的完整成本优势。

## 6. 独立保留的新30情景证据

{context_en}

此表来源4.1/4.6已验收query_cap的3001—3030，每方法300次（30个独立情景×10种子），SA-original和SA-restart分开，未与本轮合并n=40或n=400。保留原R1 κ命中定义及正式检验，不用本轮命中阈值覆盖旧表。原30情景SA包装采用共享QueryOracle、proposal上限200000及原参数，种子间距1000000；本轮执行原函数搜索体，种子间距100000，不声称两批字节完全相同，也不把30情景结果充当本轮100次。此处Mean/Median/P90/Max均对30个情景均值计算。各批目标均依赖自己的洪水和条件道路集合，不能混为同一经验分布。

## 7. 数值、文件与图形验收

独立验收器`validate_final.py`逐条检查完整实际访问账本、全proposal的预算原子拒绝与缓存计费，重加100条11阶段轨迹、单位、Regret和ΔATT，重算逐情景/逐重复组/匹配表，并核对预先冻结种子、脚本及源SHA。没有通过重跑100次搜索来“检验”输出。`audit/R42_source_authority_binding.csv`额外逐项匹配4.2历史manifest中的网络、OD、BPR、两份solver和十张HP表SHA；由原OD独立重加Q=360600，并核对原10阶段及终态零权重常量。

前后共{protected}个已存在文件逐项SHA保护，涵盖4.1—5.5、旧回复/主稿、已验收R2资料、原始表与旧缓存；相关运行库和旧__pycache__排除项在来源清单生成脚本明确。SHA只读验证不修改其内容。最终逐项清单`audit/source_protection_final.csv`；manifest中的关键输入与执行脚本额外绑定。Git HEAD和分支保持原值。

两张图同时导出PDF/600dpi PNG/可编辑文字SVG，字体≥7pt，自动字体/碰撞/绘图源审计通过。最终PDF实际渲染为图像并与PNG逐张目检，完整保留劣势种子，无裁切、乱码或标注遮挡。计费散点无抖动，同坐标点有透明度叠加，计数请以CSV为准。通用绘图检查的TIFF缺失仅为建议警告，本协议要求的PDF/PNG/SVG完整。

环境：{env['executable']}；Python {env['python'].split('|')[0].strip()}、NumPy {env['numpy']}、pandas {env['pandas']}。完整命令、解释器和时间证据见`logs/reproduction_commands.md`、`audit/environment.json`、`run_manifest.json`与逐运行result.json。最终状态和审计明细以`final_validation.json`及`QA_validation.md`为准。

## 8. 交付和停止边界

主要CSV、两张图、独立审计及英文回复/正文建议均已放在本目录，文件索引`README_文件索引.md`。回复和正文是待作者合并草稿，没有改动主稿或旧回复；正式表图编号/页码/行号待最终合并核定，不捏造已落实状态。本轮计算与审计完成后停止。
''')
 put('Response_R2_Comment6_draft_EN.md',f'''
# Reviewer 2, Comment 6 — response draft

**Draft status:** the supplementary computations and audit are complete; the manuscript text below remains a PROPOSED INSERTION. PAGE/LINE TO BE FINALIZED after author-approved merging. No master manuscript or previous response has been overwritten. Local QA status: {status}.

**Comment.** The component-oriented comparators do not adequately establish performance relative to established combinatorial search; SA obtained a zero median and six conditional-objective hits in the original ten cases, but used only one fixed seed per case. The reviewer requests SA as a formal baseline and repeated seeds for a fair assessment of robustness.

**Response.** We agree that a single SA realization cannot establish random-seed robustness, and that the original results do not justify an overall superiority claim for the proposed method. We have completed an additional 100 actual SA searches: ten independent, prespecified seeds for each original flood scenario 1001–1010. We propose presenting SA as a formal comparator in the revised baseline table, with its post-study status stated explicitly. These are technical repetitions within ten previously examined scenarios, not 100 independent flood scenarios or a new blind holdout.

**Algorithm identity and controls.** We recovered the locally frozen SA source and configuration 742ec3e18494, selected originally on development scenarios 246, 247 and 249. The initial-temperature ratio (0.0025), cooling rate (0.995), adjacent-swap probability (0.7), insertion probability (0.15), 1000-proposal stagnation stop and all search statements were retained. Before the high-precision extension, the original seed for all ten cases reproduced the archived old-precision search histories, accepted moves, state-access order, final sequences and charging records (180/180 checks); the final archived objectives were reproduced exactly. The source search body was executed unchanged; only its post-search DP call was excluded. No tuning, DP recalculation, model retraining or new UE solution was performed.

The mapping `seed=2026081000+scenario_id+100000*replicate`, for replicates 0–9, and all analysis rules were locked before the first high-precision run. Replicate 0 retains the original seed. All 100 seeds and runs were retained without selection. Each run starts a fresh RNG and query ledger, has an independent cap of 256 distinct restored-subset states, and receives only requested costs from the accepted RG≤1e-9 state tables. The archived conditional DP value is attached after search and is never a stopping signal. Repeated masks are not charged again; an unaffordable whole-sequence request is rejected atomically. No best-of-ten solution is treated as a single B=256 run.

**Results.** The complete per-scenario distributions are:

{table_en}

Regret is `100(J−J*)/J*`. Hits mean `abs(J−J*)≤1e-9 max(1,abs(J*))`, using the same criterion for SA and the frozen Proposed paths, rather than requiring the identical archived DP order. There were {a['SA_total_numerical_hits']}/100 numerical conditional-objective hits ({a['SA_total_strict_zero']}/100 strict floating-point equalities). At most ten seeds are technical replications within each scenario. P90 uses the NumPy linear quantile; seed SD uses ddof=1 and is supplied in the CSV. The individual-run maximum was {a['individual_max_regret_pct']:.6f}%; all adverse seeds remain in the tables and figure.

For overall summaries, we first averaged the ten SA regrets within each scenario and then summarized the ten scenario means. Their mean, median and P90 were {sa.mean_regret_pct:.6f}%, {sa.median_regret_pct:.6f}% and {sa.P90_regret_pct:.6f}%, respectively. The corresponding frozen Proposed-path values were {prop.mean_regret_pct:.6f}%, {prop.median_regret_pct:.6f}% and {prop.P90_regret_pct:.6f}%. The maximum of the SA scenario means was {sa.maximum_regret_pct:.6f}%; this is distinct from the maximum of 100 individual SA runs ({a['individual_max_regret_pct']:.6f}%). The Proposed-path maximum was {prop.maximum_regret_pct:.6f}%. SA had a lower mean regret in three individual scenarios and a higher mean in seven; its aggregate mean benefited particularly from scenario 1003. Therefore neither the favorable SA mean/median nor the favorable Proposed P90 supports an overall dominance claim.

Across the ten replicate groups, each containing one prespecified seed per original scenario, the numerical-hit count ranged from 4/10 to 7/10; six hits occurred in five groups. The original-seed high-precision rerun yielded 6/10, but its mean regret ({single.mean_regret_pct:.6f}%) was the highest of the ten groups. Thus its hit count is within the observed range, while its entire performance profile cannot be described as representative. The historical low-precision 6/10 result and the present high-precision result are kept separate: changing UE precision can change the acceptance trajectory, so their difference is not a pure seed effect.

**Fair comparison and limitations.** The comparison matches flood scenario, original ten-road decision set, objective, high-precision reference and the per-run cap B=256. The original Full archive extends to 512 states, but only its independently stored B=256 snapshot and the first 256 charged states are used here; the final 512-state solution is not substituted. Proposed is one frozen old-feedback path re-evaluated with the accepted high-precision costs, whereas SA searches using high-precision feedback. We disclose this asymmetry rather than claiming that both algorithms were rerun with identical feedback precision. We do not estimate a ten-seed variance for Proposed from its single frozen realization. The numerical-hit count for these frozen paths is 4/10, including 2/10 strict floating-point equalities. The available data do not establish which method would dominate in a fully symmetric high-precision, multi-seed rerun, which is outside this supplement.

SA used 196–256 unique states per run (mean {a['mean_actual_queries']:.2f}); 73 runs exhausted 256 and 27 stopped under the unchanged stagnation rule. The cap is matched, not necessarily the actual consumption. The 100 runs used {int(f.queries_charged.sum())} logical state charges in total but zero new physical UE solves. The total lookup-search wall time was {ex['total_search_wall_s']:.6f} s and CPU time {ex['total_search_CPU_s']:.6f} s, including passive in-memory audit instrumentation. These are sealed lookup timings, exclude the precomputed table cost and do not estimate online high-precision UE runtime.

**Separate existing evidence.** The previously accepted 3001–3030 ten-seed study is reported separately, with SA-original, SA-restart and Proposed each retaining their own 300 runs:

{context_en}

These summaries use the thirty scenario means. They are not pooled with scenarios 1001–1010, and do not turn this experiment into forty common-distribution scenarios or four hundred independent SA samples. The earlier shared-oracle wrapper, proposal limit and seed spacing differ from the recovered original search kernel used here; its frozen equivalence rule and formal analyses are preserved. No SA-restart search was added in the present task.

**Proposed manuscript action.** Add the explicit SA definition, frozen parameter/seed table, full ten-seed distributions and query counts to Methods and Supplement; replace broad superiority claims with the qualified comparisons above; retain all unfavorable outcomes and distinguish model-implied mean stage travel time from actual repair duration. Suggested text and table/figure placements are provided in `Manuscript_insertions_R2C6_EN.md`. These actions are pending author merging; final table/figure numbers and PAGE/LINE TO BE FINALIZED. The numerical evidence, raw trajectories and read-only source audit are already delivered.
''')
 put('Manuscript_insertions_R2C6_EN.md',f'''
# Reviewer 2 Comment 6 — PROPOSED INSERTION

Not merged into the main manuscript. PAGE/LINE TO BE FINALIZED after final integration. The table and figure labels below are local supplement identifiers; they do not replace existing R11–R16, Table 15–18 or S17–S19 numbers.

## Methods — formal SA comparator and evaluation protocol

The post-study simulated annealing (SA) comparator was additionally evaluated using ten prespecified seeds for each original scenario (1001–1010), retaining its previously frozen configuration (initial-temperature ratio 0.0025, cooling 0.995, adjacent-swap probability 0.7, insertion probability 0.15 and stagnation limit 1000 proposals). The seed was `2026081000+scenario_id+100000r`, r=0,…,9; r=0 retained the original seed. Each run had a separate cap of B=256 unique restored-subset cost queries and no cross-run warm start. Accepted high-precision (RG≤1e-9) archived costs were exposed through an on-demand, read-only oracle, with repeated states charged once per run and infeasible budget requests rejected atomically. No new UE solves were needed. Search did not access reference values or the full state table. For a ten-road sequence, `J=(1/10)Σ(k=0,…,9)[TSTT(S_k)/TSTT0−1]`; the fully restored state has zero weight. Archived conditional DP references were used only after search. A numerical conditional-objective hit satisfies `|J−J*|≤1e-9 max(1,|J*|)`.

We report within-scenario seed distributions and then summarize the ten scenario means; seeds are technical repetitions rather than additional flood scenarios. P90 uses the linear sample quantile and seed SD uses ddof=1. For comparison, the original Proposed B=256 frozen sequence was re-evaluated on the same high-precision costs. SA used high-precision search feedback, whereas Proposed retained its originally selected low-precision-feedback path; only one Proposed realization was available, and no seed variance was inferred for it. Results from the distinct thirty-scenario cohort (3001–3030) remain separate.

## Results — replace any broad dominance statement

Across the ten original scenarios, the mean, median and P90 of the ten-seed scenario-mean SA regrets were {sa.mean_regret_pct:.6f}%, {sa.median_regret_pct:.6f}% and {sa.P90_regret_pct:.6f}%, compared with {prop.mean_regret_pct:.6f}%, {prop.median_regret_pct:.6f}% and {prop.P90_regret_pct:.6f}% for the frozen Proposed paths. SA reached the numerical conditional-optimal target in {a['SA_total_numerical_hits']}/100 runs, with replicate-group hit counts of 4–7 out of ten. The original-seed high-precision rerun achieved six hits but had the highest mean regret among the ten replicate groups. The worst individual SA regret was {a['individual_max_regret_pct']:.6f}%, distinct from the maximum scenario-mean regret of {sa.maximum_regret_pct:.6f}%. The frozen Proposed-path maximum was {prop.maximum_regret_pct:.6f}%. SA used 196–256 unique states per run (mean {a['mean_actual_queries']:.2f}); 27 runs stopped before exhausting the cap. These results support competitive SA performance and seed-dependent trade-offs, rather than overall superiority of the proposed method.

## Discussion — limitations and positioning

The supplement evaluates seed stability after the original holdout had been examined, and is not an additional blind validation. Ten seeds improve the description of algorithmic variability within a scenario, but do not increase the number of independent flood scenarios beyond ten. The available comparison also has a feedback-precision asymmetry: SA was rerun using high-precision costs, whereas Proposed was evaluated by high-precision revaluation of its original B=256 path. Consequently, this evidence cannot establish general algorithmic dominance or a symmetric high-precision multi-seed comparison. The established SA baseline should remain visible alongside component ablations. The contribution of the proposed framework should be framed around its auditable budget allocation and prefix-search behavior, with competitive UE-only baselines and their favorable results explicitly retained. Lookup timings do not represent online UE cost, and equal-duration mean stage loss does not specify real repair duration.

## Supplement — full distribution table (local ID R2C6-S1)

{table_en}

Table note: each row contains ten separate B≤256 runs. Hits use the stated objective tolerance and do not require the archived DP sequence to be identical. Tiny negative raw regrets are retained numerical roundoff. SD, threshold counts, ATT differences and all seeds appear in the CSV. `ΔATT_mean_stage=0.6*TSTT0/Q*(J−J*)` in minutes per trip; TSTT0={T0:.17g} raw units and Q={Q:.0f}; the 0.01 h scaling is applied once. This is model-implied mean stage travel time, not accumulated calendar restoration time. No best-of-ten same-budget result is used.

Recommended additional local tables: R2C6-S2 = `Table_R2C6_per_replicate.csv`; R2C6-S3 = `Table_R2C6_comparison_to_Proposed.csv`; R2C6-S4 = `Table_R2C6_existing_new30_context.csv`. The latter is a different cohort and must not be pooled. Final numbering is pending.

Recommended local figures: R2C6-F1 = `Figure_R2C6_SA_seed_stability`; R2C6-F2 = `Figure_R2C6_budget_and_regret`. Use the supplied English captions. All 100 adverse/favorable seeds are plotted; overlapping budget points are not distinct visible sample counts. No manuscript figure or table number has yet been assigned.
''')
 put('logs/reproduction_commands.md',fr'''
# 执行与复核命令记录

实际解释器：`{env['executable']}`；执行目录`{OUT}`。依赖由只读既有`{BASE/'runtime_deps'}`加载；缓存仅写本任务runtime_cache。命令采用PowerShell，以下为已实际执行阶段对应的可审查命令，不声称保留了不存在的完整终端transcript。

```powershell
$taskDir = '{OUT}'
$taskPython = '{env['executable']}'
& $taskPython -X utf8 -B "$taskDir\scripts\replay_legacy.py"
& $taskPython -X utf8 -B "$taskDir\scripts\prepare_run.py"
& $taskPython -X utf8 -B "$taskDir\scripts\run_sa100.py"
& $taskPython -X utf8 -B "$taskDir\scripts\analyze.py"
& $taskPython -X utf8 -B "$taskDir\scripts\plot_figures.py"
& $taskPython -X utf8 -B "$taskDir\scripts\figure_qa.py"
& $taskPython -X utf8 -B "$taskDir\scripts\render_final_figures.py"
& $taskPython -X utf8 -B "$taskDir\scripts\record_visual_review.py"
& $taskPython -X utf8 -B "$taskDir\scripts\write_reports.py"
& $taskPython -X utf8 -B "$taskDir\scripts\validate_final.py"
& $taskPython -X utf8 -B "$taskDir\scripts\polish_captions.py"
& $taskPython -X utf8 -B "$taskDir\scripts\figure_qa.py"
& $taskPython -X utf8 -B "$taskDir\scripts\write_reports.py"
& $taskPython -X utf8 -B "$taskDir\scripts\seal_outputs.py"
```

前三个是已完成的正式阶段，不要原地重新执行；prepare_run和run_sa100都有存在性保护，会拒绝覆盖现有manifest/100行正式结果。仅需复核时运行validate_final即可，其不调用搜索、UE或DP。analyze只从现有100次产物重聚合；曾追加“观测命中路径与已有DP路径比对”表，没有重复SA。一次命令行渲染尝试因Python括号语法错误未运行，随后使用render_final_figures.py成功导出，未影响科学结果。

实际运行时间证据：manifest事前冻结UTC {man['created_utc']}；各次完成UTC见SA_all100_runs.csv与每次result.json；运行进度logs/run_progress.json；执行汇总audit/execution_validation.json。不能把100个完成时间当作逐命令完整起止transcript。最终审计另存stdout和带时间的JSON。最终审计共运行两次：先完成28项核心检查，再补充4.2历史网络/OD/BPR/solver/表及常量的独立绑定检查，完成29项；均未重复SA搜索。图注只作排版空格修订，PDF/PNG/SVG未重画，并复跑图形自动审计。

数据重现需保留原文件路径及source_inventory所列归档。当前环境NumPy {env['numpy']}、pandas {env['pandas']}；旧精度重放保留原加载方式。不得改用HP表或不同CSV解析来伪装旧结果复现。
''')
 put('README_文件索引.md',f'''
# Reviewer 2 Comment 6 文件索引

状态：**{status}**；100次SA完成，新增真实UE/DP/训练均为0。主要结论请先读中文报告；本目录无压缩包。

|用途|文件|内容与统计单位|
|---|---|---|
|中文技术与验收报告|[Comment_R2_6_SA_multiseed_results_CN.md](Comment_R2_6_SA_multiseed_results_CN.md)|结果、预算、来源、限制和阶段结论|
|最终自动验收|[QA_validation.md](QA_validation.md)、[final_validation.json](final_validation.json)|独立数值、源文件、预算和图形验收|
|100次原始结果|[raw/SA_all100_runs.csv](raw/SA_all100_runs.csv)|每次种子、顺序、目标、命中、查询数、停止原因、查表耗时|
|逐情景分布|[Table_R2C6_holdout_per_scenario.csv](Table_R2C6_holdout_per_scenario.csv)|10行；每行十种子，不把100次当100独立情景|
|逐重复组|[Table_R2C6_per_replicate.csv](Table_R2C6_per_replicate.csv)|10组、每组10情景；原种子为replicate0|
|匹配Proposed|[Table_R2C6_comparison_to_Proposed.csv](Table_R2C6_comparison_to_Proposed.csv)|同一原十路集合、同一HP参考及B256上限；反馈精度不对称|
|情景级总体|[Table_R2C6_scenario_level_overall.csv](Table_R2C6_scenario_level_overall.csv)|SA先在情景内取均值，再汇总10个情景|
|独立旧30证据|[Table_R2C6_existing_new30_context.csv](Table_R2C6_existing_new30_context.csv)|3001—3030，SA-original/SA-restart/Proposed分开，不合并|
|观测命中路径|[Table_R2C6_observed_numerical_hit_sequences.csv](Table_R2C6_observed_numerical_hit_sequences.csv)|数值命中不要求路径等于归档DP；不是重算DP|
|逐阶段轨迹|[raw/SA_trajectories.csv](raw/SA_trajectories.csv)|1100行，终态权重0且仅搜索后评价|
|完整实际访问账本|[raw/SA_query_ledger_all.csv](raw/SA_query_ledger_all.csv)|约98MB，含缓存重复读取；new_charge区分唯一计费|
|唯一状态账本|[raw/SA_unique_query_ledger.csv](raw/SA_unique_query_ledger.csv)|每次独立唯一状态计费，总计{int(f.queries_charged.sum())}|
|全proposal|raw/SA_proposals_all.csv.gz|含预算拒绝，不只记录有返回值的序列|
|逐次归档|raw/runs/scenario_1001…1010/rep_00…09/|result.json含最终RNG状态；原source_history与unique_query_ledger|
|旧精度复现|raw/old_replay/、raw/legacy_replay_results.csv、audit/legacy_replay_*.csv/json|180项通过，最终目标差0|
|源代码身份与保护|audit/source_inventory.md、SA_definition_binding.json、source_protection_before.json、source_protection_final.csv、R42_source_authority_binding.csv|原文件前后SHA、4.2历史网络/OD/solver/HP表绑定及B256快照|
|事前冻结|[run_manifest.json](run_manifest.json)、seeds_frozen.csv、audit/prospective_freeze.json|首次HP搜索前锁定100种子和规则|
|图1|[figures/Figure_R2C6_SA_seed_stability.png](figures/Figure_R2C6_SA_seed_stability.png)|全部100种子分布、原种子旧/新精度与Proposed固定点；同名PDF/SVG|
|图2|[figures/Figure_R2C6_budget_and_regret.png](figures/Figure_R2C6_budget_and_regret.png)|实际查询量与Regret；同名PDF/SVG|
|图注与图形QA|figures/Figure_captions_EN.md、audit/figure_*、audit/*collision*|英文图注、实际PDF渲染和逐图视觉验收|
|英文回复草稿|[Response_R2_Comment6_draft_EN.md](Response_R2_Comment6_draft_EN.md)|正式SA比较与限制；主稿尚未合并|
|正文插入建议|[Manuscript_insertions_R2C6_EN.md](Manuscript_insertions_R2C6_EN.md)|Methods/Results/Discussion/Supplement；编号/页行待定|
|代码、命令、环境|scripts/、[logs/reproduction_commands.md](logs/reproduction_commands.md)、audit/environment.json|原样搜索体与只读复核脚本|
|成果SHA清单|output_manifest.csv、output_manifest.sha256.json|含原始CSV和报告；清单不自哈希、不纳入runtime_cache|

计算范围在本批结束；未重训代理、未改原算法、未执行Full/SA-restart/UE/DP，未更改4.1—5.5或旧回复/主稿。正式页码/行号须最终合并后填写。
''')
 print('Reports written; QA status',status,flush=True)
if __name__=='__main__':main()
