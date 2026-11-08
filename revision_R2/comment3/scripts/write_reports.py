from common import *
import re
def mdtable(rows,headers):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(str(x).replace('|',',') for x in row)+' |' for row in rows)
def main():
 man=js(OUT/'run_manifest.json');ue=js(OUT/'audit/UE_execution_validation.json');data=js(OUT/'raw/analysis_all_conditions.json');lookup={r['variant_id']:r for r in data};sids=[1006,1003,1008];summary=js(OUT/'raw/DP_summaries.json');f=read(OUT/'Table_R2C3_all10_feasibility.csv');dpchecks=read(OUT/'audit/independent_DP_checks.csv');replay=read(OUT/'audit/CRN_baseline_replay.csv')
 def number(v,n=6):return f'{v:.{n}f}' if v is not None else 'NA'
 depths=[lookup[f'{sid}_depth_{h}'] for sid in sids for h in [.95,1.,1.05]];corr=[lookup[f'{sid}_correlation_{level}'] for sid in sids for level in [3.,6.]]
 depthtable=mdtable([[r['scenario_id'],r['level'],r['validity_status'],number(r['J_star']),number(r['mean_stage_ATT_min'],3),'→'.join(map(str,r['sequence'])) if r['sequence'] else 'NO FINITE UE',number(r['complete_Kendall_tau'],6),number(r['fixed_original_optimal_transfer_regret_pct'])] for r in depths],['Scenario','Depth multiplier','Validity','J*','Mean-stage ATT (min)','Conditional optimal order','Full Kendall τ','Frozen-order transfer regret (%)'])
 corrtable=mdtable([[r['scenario_id'],number(r['original_lambda_km'],6),r['level'],r['closed_symmetric_difference_n'],number(r['portfolio_Jaccard']),r['common_roads_n'],r['comparable_common_pairs'],number(r['J_star']),number(r['mean_stage_ATT_min'],3),number(r['common_subsequence_Kendall_tau'])] for r in corr],['Scenario','Original λ (km)','New λ (km)','Closed-set symmetric difference','E Jaccard','Shared roads','Shared pairs','J*','Mean-stage ATT (min)','Shared-road τ'])
 rawreview=(BASE/'评审员2意见_提取.txt').read_text(encoding='utf-8-sig');comment=rawreview.split('3. The study generates')[1].split('4. The study preselects')[0];comment='The study generates '+comment.strip()
 (OUT/'Response_R2_Comment3_draft_EN.md').write_text(f'''# Reviewer 2, Comment 3

**Reviewer comment**

> {comment}

**Response**

We agree that the static synthetic flood model does not resolve the temporal evolution or operational uncertainty of real floods. We completed a paired input-sensitivity experiment on the ten original frozen floods, retaining adverse and infeasible cases. The analyses test the conditional static benchmark, not the robustness of a real-time flood recovery policy.

The severe-field generator draws target counts of 8–12 closed and 20–28 wet physical roads and a Gaussian correlation length of 3–6 km, with a smooth local storm-centre component. It ranks latent scores, skips candidate closures that would disconnect the network, and assigns depths by rank with fixed noise. The final benchmark additionally requires at least ten closures and excludes duplicate depth vectors, closure masks and combined scenario identities. The 0.30 m closure threshold and these parameter ranges are synthetic benchmark design choices, not city-specific hydrological calibration or new safety standards. By default, passable wet roads change speed/free-flow time only; their capacity remains unchanged, whereas closed roads have zero capacity. This limitation bounds the traffic interpretation.

Before varying correlation, we replayed all 12 original draws from seed2026080701, including the two rejected draws. All ten accepted depth vectors matched within 1e-12, all closure masks matched exactly, the generation metadata matched, and the independently traced random-number consumption matched the original generator. Correlation endpoints3 and6km then reused each draw's standard normals, counts, storm centre, scale and amplitude, and rank-specific depth noise. They did not use fresh independent random draws. Connectivity protection remained active in this branch, so its outputs cannot estimate disconnection probabilities.

All ten scenarios were audited without UE under depth multipliers0.90,0.95,1.00,1.05,1.10, thresholds0.28,0.30,0.32m and the original/endpoint correlation lengths. No condition had fewer than ten initially closed roads. Depth+5% made scenarios1002 and1008 OD-unreachable; depth+10% made all ten OD-unreachable. Threshold0.28m made seven scenarios unreachable, with36–46 inaccessible positive-demand OD pairs per affected scenario. The other three threshold0.28 cases and all ten threshold0.32 cases retained exactly the baseline traffic transformations. We did not delete OD, reopen roads to repair connectivity, assign fictitious finite costs, or compute DP for disconnected conditions. The unchanged threshold cases reused existing high-precision costs.

The representative scenarios were fixed in advance as1006,1003 and1008, respectively the lowest, fifth-ranked and highest original conditional objective. We completed five legal ±5% depth tables and six paired correlation conditions, one of which was identical to its baseline and reused that table. Thus10,240 new unique UE states were solved, alongside3,072 unique reused baseline states. All new solves met RG≤1e-9, with independent AON checks and103 independent Dijkstra checks. Exact subset DP is conditional on these numerical state costs; RG is not a rigorous TSTT error bound. The offline1,024-state references are not budget-limited online algorithm runs, and no surrogate or original Full optimizer was rerun.

**Depth sensitivity in the fixed recovery sets**

{depthtable}

Three of the five feasible depth perturbations changed the selected optimal permutation. In1006 at−5%, the first road changed from5 to9 and transferring the frozen original optimal order incurred0.619773% regret, or1.598557 model-implied mean-stage minutes per trip. In1003 at+5%, roads17 and28 exchanged positions, with0.082329% transfer regret and0.806706min. In1008 at−5%, only the last two roads exchanged positions, with0.001125% regret and0.025409min. These are regrets of a frozen conditional optimal ordering under the new same-set costs, not measurements of the proposed search algorithm. Scenario1008 at+5% has no finite fixed-demand UE solution and was not replaced.

**Paired spatial-correlation sensitivity**

{corrtable}

Across the ten floods,19 of20 endpoint conditions changed the closure set. Five of six representative endpoint conditions changed the ten-road recovery set. For these changed sets, the reported τ compares only shared-road subsequences, using the explicit pair counts above; full-order τ, first-road-change indicators and original-policy oracle regret are not assigned. Scenario1003 at6km retained the exact physical traffic state and optimal order. Conditional costs vary markedly, for example mean-stage ATT in1006 is242.068min at3km and1966.604min at6km versus311.944min originally, but these are different disaster inputs and recovery sets, not algorithm gains or causal policy effects. The extreme static BPR values are retained and must not be read as observed travel times.

These results show both local ordering changes within the admissible domain and exits from that domain. The model still omits flood evolution and drainage, uncertain safety-based reopening, evolving demand and traveller responses, unserved-demand objectives for disconnected networks, engineering repair durations and multiple crews. No joint observed flood-depth/traffic validation was added. Completing the selected ten interventions is not full network recovery. The sample units remain ten original synthetic floods and three fixed representatives; parameter variants do not create independent floods, and no significance claim is made.

**PROPOSED INSERTION, pending master integration**

*Methods should describe the conditional generator and CRN replay, Results should summarize the feasible ordering changes and disconnected cases, and Discussion should delimit static connected-network applicability. Detailed conditions, pair counts and costs should be retained in supplementary tables. These insertions and figures are supplied separately; they have not been merged into the manuscript. Final table/figure numbering and page/line references remain pending the final merged master.*
''',encoding='utf-8')
 (OUT/'Manuscript_insertions_R2_Comment3_EN.md').write_text('''# PROPOSED INSERTION — not yet merged into the manuscript

Final section/table/figure numbering and page/line references must be assigned after master integration. The following are replacements or compressed additions for the relevant paragraphs, not a claim that the master has already been revised.

## Methods, replacement/clarification for synthetic-flood generation

Severe synthetic fields used target counts of8–12 closed and20–28 wet physical roads, Gaussian correlation lengths of3–6km, and a smooth local storm-centre term. Closures were selected in latent-score order subject to connectivity; rank-specific depths and noise were then assigned. Final scenarios required at least ten closures and distinct rounded-depth vectors, closure masks and combined identities. These are benchmark design parameters, not hydrologically calibrated city estimates. At the baseline threshold0.30m, passable wet roads modify free-flow travel time while retaining original capacity. We performed paired one-factor sensitivity checks using the original ten fields and unchanged OD. Correlation endpoints reused the original random factors after exact replay of all12 original draws. Complete1024-state numerical UE tables and conditional subset-DP references were evaluated only for the three prespecified representative floods under admissible conditions. Existing baseline tables were reused where traffic transformations were identical.

## Methods, mathematical clarification for Supplement

For a fixed ten-road set E, C(S)=TSTT_UE(S)/TSTT0_raw−1. Define W(∅)=0 and W(S)=min over e∈S of [W(S∖{e})+C(S∖{e})]. Then J*=W(E)/10. Each transition charges the pre-completion state; hence S0–S9 have weight1/10 and S10 has zero objective weight. This recurrence is exact for the finite numerical state-cost table because cost depends on the recovered set. It is not an assertion about infinitely converged UE or general traffic path independence. ATT_min=0.6TSTT_raw/Q, with Q=360600 and raw time unit0.01h; these values are model-implied mean stage travel times per trip.

## Results, concise proposed paragraph

Input perturbations changed both admissibility and conditional optimal order. A5% depth increase made two of ten floods OD-unreachable; a10% increase made all ten unreachable. Lowering the illustrative threshold from0.30 to0.28m made seven floods unreachable, while0.32m preserved all baseline traffic states. No finite UE objective was assigned to disconnected cases. Among five feasible ±5% depth perturbations in the three fixed representatives, three optimal permutations changed; the largest frozen-order transfer regret was0.619773% (1.598557 model-implied mean-stage minutes per trip). Paired3/6km correlation changes altered recovery sets in five of six representative conditions, so those comparisons use shared-road subsequences rather than full-order regret. Detailed admissibility, numerical costs and comparable pair counts should accompany the supplied sensitivity figures in the Supplement.

## Discussion, proposed bounded replacement

The benchmark conditions on a static connected network, a fixed OD matrix and a selected ten-road set. Small depth or closure-rule changes can exit this feasible domain; the present UE/DP objective cannot value unserved demand after disconnection. Correlation sensitivity also mixes changes in impacted locations and recovery sets. It does not establish probabilistic flood risk, algorithmic superiority or causal policy gains. Flood evolution, drainage, uncertain safe reopening, evolving demand, engineering durations and parallel crews require broader models and observed joint hydraulic/traffic validation. Selected-road completion does not imply restoration of all damaged roads or removal of all wet-road effects.

## Author-only allocation and integration check

Methods replaces the generator clarification; Results keeps the feasible-domain boundary and one transfer magnitude. Full parameter grids, random factors, state-cost diagnostics, all orders and first-road alternatives belong in the Supplement/source data. Discussion replaces a broad static-flood applicability statement. Original paragraph word-count deltas cannot be assigned until the actual merged master paragraphs are selected. No master file, existing caption or formal response was overwritten.
''',encoding='utf-8')
 transfer=read(OUT/'Table_R2C3_policy_transfer.csv');changed=transfer[transfer.status.eq('COMPARABLE_SAME_E')&transfer.transfer_regret_pct.gt(1e-12)]
 first=read(OUT/'raw/DP_first_road_alternatives.csv');qa=js(OUT/'final_validation.json') if (OUT/'final_validation.json').exists() else None
 status=qa['status'] if qa else 'FINAL_QA_PENDING'
 report=f'''# Reviewer 2 Comment 3 补充模拟中文技术与验收报告

验收状态：**{status}**。本轮实际运行，非模拟计划。此状态仅针对获授权的条件敏感性实验；不表示模型已可处理断网或真实动态洪灾。新输出全部位于本目录，未修改主稿和任何旧科学文件。英文回复与正文插入文字仍为待合并草稿。

## 1. 权威来源与实验冻结

使用本地4.2验收RG≤1e-9路径列生成/配对UE求解器及原十场景1024状态表。公开仓库RG5e-4旧表未作为数值参照。原物理数据、选路bit顺序、冻结flow/betweenness、生成器、映射、求解器及版本来源见audit/input_audit.md和audit/source_sha256.json。原Git HEAD为{man['git']['HEAD']}，branch={man['git']['branch']}。全部旧源前后SHA验收见audit/source_preservation.csv。

干燥分母TSTT0_raw={T0:.17g}，Q={Q:.0f}，38物理道路/76有向弧，528正需求OD；BPRα=.15、β=4。raw时间单位0.01小时，TSTT_veh_h=.01×raw，ATT_min=.6×raw/Q。新水深和阈值始终重算完整映射，开放湿路容量因子1，只改变速度/FFT，关闭容量因子0。单施工链、10路等工期，计入S0—S9，S10只报告。没有重训代理或重跑Full/其他正式搜索。

在首个新UE之前封存run_manifest.json及其SHA绑定，锁定1006/1003/1008代表与所有变体、恢复集合和全部请求状态；水深±10%仅预审，没有自动扩展UE。实际新UE预算{man['new_unique_states']}/13000。不可行条件不替换场景、不删OD、不强行赋有限值。

## 2. 原始随机数重放

原seed2026080701；共12次draw，10接受、2因关闭道路不足10拒绝。使用原generate_final_holdout函数直接重放，并从相同RNG起始状态独立抽取基本随机量。12/12随机数消耗后状态相同，10/10原水深最大绝对误差{replay.baseline_max_depth_error.max():.3g}≤1e-12，关闭mask精确一致，draw索引、原λ、关闭/湿路目标、暴雨中心与尺度匹配。全部latent标准正态、storm幅度和排名位置噪声保留在raw/replayed_random_factors.json。相关端点仅换协方差Cholesky，使用相同随机量与原连通闭路保护；不是换种子，也不是改CSV的λ标签。相关分支因条件连通生成而不能估计断网概率。

## 3. 全十情景预审与负面结果

共110行（每情景5水深+3阈值+3相关长度，含明确的重复基线列），其中91合法、19条件因OD不可达退出固定需求UE可行域。参数变体不是新增独立洪水样本。

{mdtable(read(OUT/'Table_R2C3_feasibility_summary.csv').values.tolist(),['因素','水平','状态','情景数'])}

水深+5%不可达为1002、1008；+10%全十不可达。阈值0.28不可达为1001、1002、1004、1005、1006、1008、1010，各36—46个正OD不可达；0.28其余1003/1007/1009及0.32全部场景的物理交通状态与原表完全一致。低于10路的情况本轮没有观察到。19条件的986条未服务OD条件记录见raw/unreachable_OD.csv；同一OD可能在不同条件重复，986不是986个独立OD。没有对这些条件发起UE，也没有伪造J*。

## 4. 水深对最优排序的影响

{depthtable}

六个非基线代表水深条件中五个合法，1008+5%未求解。所有五个合法条件仍使用原十路集合，因此可做完整Kendall和原冻结最优序列转移评价。三种排序发生变化，其中只有1006−5%的首路改变（5→9）。1003+5%为17/28相邻交换；1008−5%为最后14/7交换。五个合法条件的闭路拓扑均未改变，但开放湿路速度和成本改变，严格没有据“mask相同”复用状态。

{mdtable([[r.variant_id,number(r.transfer_regret_pct),number(r.absolute_ATT_gap_min)] for r in changed.itertuples()],['条件','原冻结最优排序transfer regret %','绝对ATT差 min'])}

百分比分母是扰动后同E的条件J*，绝对差=.6×T0_raw/Q×ΔJ，不是同一洪水与另一洪水J*之差。这里迁移的是原条件DP排序，不是Full算法输出。近似tie与各首路受限最优差保留在raw/DP_first_road_alternatives.csv；1006−5%的最优首路相对另一最佳首路差约0.111639目标单位，未事后调整tie规则。

## 5. 空间相关对关闭位置、集合及排序的影响

{corrtable}

全部十场景×两个端点的20条件中，19个关闭集合改变；代表六条件中五个十路集合改变。共同道路为3—9条，只有3—36个可比道路对。不同E时完整Kendall、首路改变和旧策略oracle regret全部留空/NOT_COMPARABLE；只报告共享道路子序列。1003 λ6的物理场交通状态与基准完全相同，使用原1024表，目标和排序相同。跨条件J*或ATT是不同灾害输入的描述性比较，不能称算法提升、参数的因果效应或真实政策收益。

## 6. 计算数量、精度与缓存

24张逻辑完整表=5张新水深表+5张新相关表+14张只读复用表。逻辑表共有24576行状态，去重后13312个唯一物理交通状态，其中新UE10240、4.2复用3072。实际不同的十路决策问题为原3个+新10个。相同物理状态只计费一次，重复基线列不算新增仿真。

新UE全部10240/10240成功，没有数值求解失败或精度降级。最大RG={ue['max_RG']:.16g}；全部独立AON最大RG={ue['max_independent_AON_RG']:.16g}；103次独立heap-Dijkstra最大RG={ue['max_Dijkstra_RG']:.16g}；最大节点守恒误差{ue['max_conservation_error']:.16g}。每个新状态独立NumPy BPR重算TSTT，记录flow、迭代数、耗时与528正OD可达。RG不是TSTT严格误差界。

真实新UE solver耗时{ue['solver_seconds']:.3f}秒，整个单核单进程UE执行{ue['wall_seconds_this_process']:.3f}秒；不与Proposed在线B=256计时混称。缓存仅cache/sensitivity_states.sqlite3，未打开旧SQLite进行读写；旧权威数据仅CSV只读。有效状态key包括active、FFT、BPR系数、容量、OD hash、求解器双SHA、RG、最大迭代与原干燥分母。每条logical_state_mapping另绑定scenario/draw/factor/level、完整38维深度hash、所有变换hash和恢复道路ID；raw字段可完整重建上下文。跨集合共享仅由严格相同的有效物理状态key判定，而非集合标签或旧mask-only缓存。

## 7. 独立数学与图形QA

每表正向subset-DP、反向DP及显式路径求和一致，最大误差{dpchecks.max_error.max():.16g}≤1e-12。m1—7穷举、终态极大哨兵、初态加Δ影响Δ/m共28项通过。DP的“精确”仅针对数值成本表。原始DP逐mask值、前驱、倒推值和路径权重均保存。

两图各提供PDF、SVG、600dpi PNG，并实际目检。PDF实际最小字体7.2pt；6面板图几何对齐门槛1.5pt，通过。初次图形审计发现不可达标签跨网格线，已移到图区外并重新导出、重审；不是更改任何数值。所有缺失点均注明不可求解，不以0代替。最终自动图形日志见audit/figure_automated_QA.json，人工记录见audit/figure_visual_review.json。

## 8. 科学边界与未解决事项

本轮已完成所有固定代表、合法分支、负面记录和质量核查。断网条件不能由本模型给出有限UE/DP排序，这是模型边界，不是为通过验收而删除失败场景。静态合成场没有城市水文校准，不表示动态排水、需求演化、驾驶员反应、安全开放、真实工程工期、多施工队或真实洪灾的概率分布。开放湿路未缩容量；极端BPR时间原样保留。完成10路并非全网络恢复。不对n3显著性推断，不把变体当独立样本，不用新离线DP证明代理优势。

未完成的仅是正式主稿/Supplement合并、最终表图编号和页行号；本轮未授权整合，英文两文件均标PROPOSED INSERTION。正文建议与既有需求、工期和集合敏感性一致，回复不泄露另一审稿人的编号。

## 9. 复现与结果索引

数值环境为E:/ProgramData/Anaconda3/envs/rag_demo/python.exe，并只读使用原4.1 runtime_deps；全部新增numba/matplotlib缓存隔离在本目录runtime_cache。使用scripts/reproduce_r2c3.py --offline-only可复核现有结果，不新增UE。正式完整阶段执行日志与命令见scripts/及logs；run_manifest已冻结，不应手工重建或覆盖。

核心表为Table_R2C3_all10_feasibility.csv、Table_R2C3_depth_and_threshold.csv、Table_R2C3_spatial_correlation.csv、Table_R2C3_conditional_DP.csv、Table_R2C3_policy_transfer.csv；全部原始状态、随机因素、流量SQLite和DP记录在raw及cache。最终状态和逐项验收见final_validation.json，文件SHA及大小见output_manifest.csv。无压缩包。
'''
 (OUT/'Comment_R2_3_results_report_CN.md').write_text(report,encoding='utf-8')
 index='''# 结果文件索引

所有路径相对于本目录。主要交付如下。

| 文件 | 内容 |
| --- | --- |
| Comment_R2_3_results_report_CN.md | 完整中文技术与验收报告，含负面条件与限制 |
| final_validation.json | 最终PASS/PARTIAL/FAIL与逐条自动检查 |
| Response_R2_Comment3_draft_EN.md | 独立英文回复草稿，主稿未合并 |
| Manuscript_insertions_R2_Comment3_EN.md | Methods/Results/Discussion拟插入或替换文字 |
| Table_R2C3_all10_feasibility.csv | 110条件完整拓扑/OD/恢复集合预审 |
| Table_R2C3_depth_and_threshold.csv | 全10情景的水深与阈值合法性，代表DP/迁移结果 |
| Table_R2C3_spatial_correlation.csv | 全10情景配对原λ/3/6km，集合与共享排序诊断 |
| Table_R2C3_conditional_DP.csv | 24张完整逻辑表的条件最优值与排序 |
| Table_R2C3_policy_transfer.csv | 同E的原冻结DP路径转移，不同E和不可行保留NOT_COMPARABLE |
| figures/ | 两张图PDF、SVG、600dpi PNG与英文图注 |
| raw/variant_physical_fields.csv | 每个条件38路完整水深、速度、FFT与容量变换 |
| raw/replayed_random_factors.json | 全12draw配对RNG状态、latent/中心/幅度/噪声 |
| raw/unreachable_OD.csv | 19条件986条不可达OD条件记录，非986独立OD |
| raw/logical_state_mapping.csv | 24576逻辑状态与完整上下文/有效状态key |
| raw/unique_state_requests.csv | 13312物理唯一请求及新/复用来源 |
| raw/new_UE_query_log.csv | 10240新UE精度、守恒、单位、迭代与真实耗时 |
| raw/all_unique_state_costs.csv | 13312唯一权威/新成本，完整精度 |
| raw/DP_all_states.csv | 每表1024mask的成本、前驱、正反DP与路径权重 |
| raw/DP_optimal_trajectories.csv | S0—S10完整最优路径，终态权重0 |
| raw/DP_first_road_alternatives.csv | 首路固定时最优目标和近tie记录 |
| cache/sensitivity_states.sqlite3 | 本轮隔离UE记录及76弧流量二进制 |
| audit/ | 输入SHA、封存、原重放、数值/图形/来源未变QA |
| tests/small_DP_exhaustive_and_sentinel.csv | m1—7独立穷举/哨兵/初态位移检查 |
| logs/UE_attempts.jsonl | 逐次UE原始运行日志 |
| run_manifest_preflight.json, run_manifest.json | 第一次新UE前实验设计与状态预算冻结 |
| scripts/reproduce_r2c3.py | 离线复核入口；不自动追加任何实验 |
| output_manifest.csv, output_manifest.sha256 | 全交付SHA/大小与清单自身哈希 |

本轮已停止于此意见。主稿整合及正式页行号待作者后续决定。未生成ZIP。
'''
 (OUT/'README_文件索引.md').write_text(index,encoding='utf-8')
 # Editorial spacing only; mathematical identifiers and raw numeric data unchanged.
 for name in ['Response_R2_Comment3_draft_EN.md','Manuscript_insertions_R2_Comment3_EN.md']:
  target=OUT/name;text=target.read_text(encoding='utf-8')
  substitutions={'of8':'of 8','and20':'and 20','of3':'of 3','threshold0.30m':'threshold 0.30 m','seed2026080701':'seed 2026080701','endpoints3 and6km':'endpoints 3 and 6 km','multipliers0.90,0.95,1.00,1.05,1.10':'multipliers 0.90, 0.95, 1.00, 1.05, 1.10','thresholds0.28,0.30,0.32m':'thresholds 0.28, 0.30, 0.32 m','Depth+5%':'Depth +5%','depth+10%':'depth +10%','scenarios1002 and1008':'scenarios 1002 and 1008','Threshold0.28m':'Threshold 0.28 m','with36–46':'with 36–46','threshold0.28':'threshold 0.28','threshold0.32':'threshold 0.32','as1006,1003 and1008':'as 1006, 1003 and 1008','Thus10,240':'Thus 10,240','alongside3,072':'alongside 3,072','and103':'and 103','offline1,024':'offline 1,024','In1006':'In 1006','at−5%':'at −5%','from5 to9':'from 5 to 9','incurred0.619773%':'incurred 0.619773%','or1.598557':'or 1.598557','In1003':'In 1003','at+5%':'at +5%','roads17 and28':'roads 17 and 28','with0.082329%':'with 0.082329%','and0.806706min':'and 0.806706 min','In1008':'In 1008','at−5%':'at −5%','with0.001125%':'with 0.001125%','and0.025409min':'and 0.025409 min','Scenario1008':'Scenario 1008','floods,19 of20':'floods, 19 of 20','Scenario1003 at6km':'Scenario 1003 at 6 km','in1006 is242.068min at3km and1966.604min at6km versus311.944min':'in 1006 is 242.068 min at 3 km and 1966.604 min at 6 km versus 311.944 min','all12':'all 12','Complete1024':'Complete 1024','A5%':'A 5%','a10%':'a 10%','from0.30 to0.28m':'from 0.30 to 0.28 m','while0.32m':'while 0.32 m','was0.619773% (1.598557':'was 0.619773% (1.598557','Paired3/6km':'Paired 3/6 km','range0.30':'range 0.30','3–6km':'3–6 km','weight1/10':'weight 1/10','unit0.01h':'unit 0.01 h'}
  for a,b in substitutions.items():text=text.replace(a,b)
  target.write_text(text,encoding='utf-8')
 print('Reports written',status)
if __name__=='__main__':main()
