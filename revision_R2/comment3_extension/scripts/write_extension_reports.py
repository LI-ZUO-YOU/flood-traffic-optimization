from common import *
def mdtable(rows,headers):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(str(x).replace('|',',') for x in row)+' |' for row in rows)
def main():
 table=read(OUT/'Table_R2C3_all10_depth_DP.csv');summary=read(OUT/'Table_R2C3_depth_summary.csv');bounds=read(OUT/'Table_R2C3_threshold_invariance.csv');glob=read(OUT/'Table_R2C3_threshold_global_intersection.csv').iloc[0];ue=js(OUT/'audit/UE_execution_validation.json');man=js(OUT/'run_manifest.json');tqa=js(OUT/'audit/threshold_invariance_validation.json');gqa=js(OUT/'audit/global_threshold_validation.json');dpqa=js(OUT/'audit/DP_analysis_validation.json');final=js(OUT/'final_validation.json') if (OUT/'final_validation.json').exists() else None;status=final['status'] if final else 'FINAL_QA_PENDING'
 def n(x,k=6):return f'{float(x):.{k}f}'
 headers=['Depth multiplier','Complete order changed','First road changed','Ordered first3 changed','First3 set changed','Mean τ','Median τ','τ range','Mean transfer regret (%)','Median','P90','Maximum','Mean ATT gap (min)','Median','Maximum']
 summtable=mdtable([[r.rho_depth,int(r.full_sequence_changed_count),int(r.first_road_changed_count),int(r.first3_order_changed_count),int(r.first3_set_changed_count),n(r.Kendall_tau_mean),n(r.Kendall_tau_median),f'{r.Kendall_tau_minimum:.6f} to {r.Kendall_tau_maximum:.6f}',n(r.transfer_regret_pct_mean),n(r.transfer_regret_pct_median),n(r.transfer_regret_pct_P90),n(r.transfer_regret_pct_maximum),n(r.transfer_delta_ATT_min_mean),n(r.transfer_delta_ATT_min_median),n(r.transfer_delta_ATT_min_maximum)] for r in summary.itertuples()],headers)
 boundtable=mdtable([[r.scenario_id,f'{r.h_open_max_m:.17g}',r.lower_boundary_road_ids,f'{r.h_closed_min_m:.17g}',r.upper_boundary_road_ids,int(r.lower_excluded_unreachable_OD),int(r.above_upper_unreachable_OD)] for r in bounds.itertuples()],['Scenario','Excluded lower endpoint (m)','Road IDs','Included upper endpoint (m)','Road IDs','Unreachable OD at lower equality','Unreachable OD just above upper'])
 detail=mdtable([[r.scenario_id,r.rho_depth,n(r.Jstar),n(r.mean_stage_ATT_min,3),json.loads(r.optimal_sequence),bool(r.full_sequence_changed),bool(r.first_road_changed),bool(r.first3_order_changed),bool(r.first3_set_changed),n(r.Kendall_tau),n(r.transfer_regret_pct),n(r.transfer_delta_ATT_min)] for r in table[table.rho_depth.ne(1.)].itertuples()],['Scenario','Depth','J*','Mean-stage ATT min','Optimal order','Order changed','First changed','First3 order changed','First3 set changed','τ','DP transfer regret %','ATT gap min'])
 oldcomment=(BASE/'评审员2意见_提取.txt').read_text(encoding='utf-8-sig').split('3. The study generates')[1].split('4. The study preselects')[0];oldcomment='The study generates '+oldcomment.strip()
 near=table[table.rho_depth.ne(1.)];firstchanges=near[near.first_road_changed];worst=near.sort_values('transfer_regret_pct',ascending=False).iloc[0]
 reply=f'''# Reviewer 2, Comment 3, additional depth and threshold evidence

**Reviewer comment**

> {oldcomment}

**Response**

We extended the depth analysis from the three representative floods to all ten original frozen scenarios. At multipliers0.90 and0.95, all initial closure masks, the original ten-road recovery sets and all528 positive-demand OD reachabilities were preserved. We recomputed the complete flood-to-speed/free-flow-time mapping, rather than scaling travel costs. Seventeen missing1024-state tables required17408 new UE solves; the three accepted0.95 tables were reused after full physical-input, road-bit-order, OD, solver-version, tolerance and cost-identity checks. All new states met RG≤1e-9. These are offline conditional exact subset-DP references, not new runs of the original surrogate-assisted search.

The severe synthetic benchmark used target counts of 8–12 closed and 20–28 wet physical roads and a 3–6 km correlation range, with the final holdout requiring at least ten closures and distinct field identities. The 0.30 m threshold and these ranges are benchmark design choices, not city-specific hydrological calibration. The original connectivity constraint and separated closed/open depth assignment explain the structural threshold interval below.

**All-scenario paired depth results**

{summtable}

Counts use ten original floods at each multiplier. These P90 values are descriptive quantiles of ten scenarios and do not establish population tail reliability. The same ten floods contribute at both levels, so20 conditions are not20 independent floods. Full ordering, first-road, ordered-prefix and prefix-set changes are reported separately; unchanged orders are retained. Kendall τ uses all45 road pairs because the recovery set is fixed. Transfer regret compares the frozen original conditional DP ordering with the new same-set conditional optimum, with the new J* as denominator. Absolute gaps are model-implied mean stage minutes per trip, not accumulated repair-period losses. The largest observed transfer regret is{worst.transfer_regret_pct:.6f}% in scenario{int(worst.scenario_id)} at multiplier{worst.rho_depth:.2f}, corresponding to{worst.transfer_delta_ATT_min:.6f}min. This is input sensitivity of a frozen conditional ordering, not an algorithm-performance gain. The source tables retain complete orders, positive/zero gaps, near-tie diagnostics and all ten scenarios.

**Exact threshold invariance**

With fixed original depths and the implemented rule closed_e iff d_e≥h_c, the largest interval preserving a scenario's original closure mask is max_open_depth<h_c≤min_closed_depth. The lower endpoint is excluded, and the upper is included. Independent recomputation gives the common interval

**{glob.h_open_max_global_m:.17g} < h_c ≤ {glob.h_closed_min_global_m:.17g}m.**

{boundtable}

We tested equality and adjacent representable floating values at both boundaries using np.nextafter. At each scenario's own excluded lower endpoint, the first added closure made one or more positive-demand OD pairs unreachable in all ten scenarios. Just above each scenario's upper endpoint, one original closure reopened and all528 positive-demand OD pairs remained reachable. These are graph checks only, with no UE. They do not make the invariant-mask interval a maximal connectivity interval, and they do not imply that every threshold below the common lower bound disconnects all scenarios. Global-intersection endpoints were separately checked across all ten scenarios.

For five within-interval threshold choices per scenario, we checked all38-road transformations and all1024 recovered-subset active, free-flow-time, effective-capacity and BPR inputs. All51200 comparisons were identical. In this implementation, threshold enters the speed mapping only through the closure gate; with unchanged gate outputs, passable speed depends only on fixed depth and capacity remains unchanged. Therefore all same-set UE cost inputs and conditional DP outputs are identical without any additional UE solve. This second task used zero UE calls. The broad interval is a structural consequence of selecting connected closures before assigning separated closed/open depth ranges, not evidence of a real-world safety margin or hydrodynamic robustness.

The earlier fixed0.28m what-if remains infeasible in seven of ten scenarios; the other three are unchanged. That result is consistent with the scenario-specific bounds and must not be generalized to every lower threshold. The accepted paired3/6km correlation experiment is unchanged:19 of20 endpoint conditions changed the closure set, and five of six representative conditions changed the recovery set. Those changed-set comparisons remain limited to shared-road subsequences, without full-order oracle regret.

These analyses address static input sensitivity while retaining the original limitations. They do not model flood evolution, drainage, changing travel demand, uncertain safe opening, engineering repair times, multiple crews or unserved-demand objectives in disconnected networks. Passable wet roads retain original capacity under the default mapping. The numerical optima are conditional on a fixed ten-road set and the RG≤1e-9 state costs; RG is not a rigorous TSTT error bound. No surrogate retraining, new flood scenario, original Full rerun or significance claim was introduced. Completion of the selected ten interventions is not full network recovery.

**PROPOSED INSERTION — PAGE/LINE TO BE FINALIZED**

*The supplied Methods, Results and Discussion text and two new supplementary figure drafts are proposed for integration. The original accepted sensitivity figures and manuscript have not been overwritten. Formal figure/table numbering and page/line references must be assigned after the final master merge.*
'''
 (OUT/'Response_R2_Comment3_extension_draft_EN.md').write_text(reply,encoding='utf-8')
 r9=summary[summary.rho_depth.eq(.9)].iloc[0];r95=summary[summary.rho_depth.eq(.95)].iloc[0]
 inserts=f'''# PROPOSED INSERTION — PAGE/LINE TO BE FINALIZED

The master manuscript and accepted prior figures remain unchanged. Replace or compress the relevant sensitivity paragraph rather than appending the full audit narrative. Final supplementary figure/table numbers remain to be assigned.

## Methods, proposed depth-sensitivity clarification

The two depth reductions0.90 and0.95 were evaluated on all ten original flood fields with the same ten-road sets, OD, BPR parameters and equal-duration single-chain objective. Each condition used a complete1024-state UE table at RG≤1e-9 and exact subset DP of that numerical table; three accepted tables were reused after full model-identity checks. The frozen original conditional DP sequence was evaluated under each new same-set cost table. Transfer regret used the new conditional optimum as denominator, and minute differences used0.6TSTT0_raw/Q times the objective difference. The original ten scenarios, not the20 parameter conditions, define the sample units.

## Results, proposed concise replacement

Depth reduction to0.90 changed the optimal order in{int(r9.full_sequence_changed_count)}/10 scenarios and the first road in{int(r9.first_road_changed_count)}/10; at0.95 the corresponding counts were{int(r95.full_sequence_changed_count)}/10 and{int(r95.first_road_changed_count)}/10. Mean original-DP transfer regret was{r9.transfer_regret_pct_mean:.6f}% and{r95.transfer_regret_pct_mean:.6f}%, respectively (P90 {r9.transfer_regret_pct_P90:.6f}% and{r95.transfer_regret_pct_P90:.6f}%). Unchanged cases and prefix-level changes are retained in the supplementary table. For fixed original depths, the shared closure-mask invariant interval is{glob.h_open_max_global_m:.12f}<h_c≤{glob.h_closed_min_global_m:.12f}m, with an excluded lower and included upper endpoint. Complete within-interval UE inputs were identical without new UE solves; endpoint graph checks and the prior seven infeasible0.28m cases delimit the connected benchmark's scope.

## Methods/Supplement, threshold proof

For each scenario, define L=max of depths on originally open roads and U=min on originally closed roads. Since closed_e⇔d_e≥h_c, retaining every original classification requires L<h_c≤U. The common interval is max_s L_s<h_c≤min_s U_s. When classifications are unchanged, threshold does not otherwise enter the open-road speed polynomial, free-flow-time transform or default capacity factors. For each recovered subset of the original ten roads, active arcs, free-flow times, effective capacities, BPR coefficients and OD are therefore identical. All1024 input states were also checked under five interior/boundary choices for every scenario. These tests did not invoke UE.

## Discussion/Limitations, proposed replacement

The unchanged-mask interval is a property of this synthetic construction, which first selects connected closures and then assigns depths from separated closed/open ranges. It is not a measured hydraulic or road-safety tolerance. A changed closure set may remain connected, and preserving connectivity does not imply identical costs or policy rankings. The static benchmark cannot evaluate disconnected fixed-demand conditions through finite TSTT, nor does it represent time-varying flood/traffic processes or validate actual operational reopening rules. Depth-driven ordering changes are conditional input sensitivities, not evidence that one search algorithm improves over another. The accepted paired correlation analysis, with its changed recovery sets and shared-road comparisons, remains unchanged.

## Author-only integration note

The Results counts and feasible-domain qualification are central interpretation limits. Detailed all-scenario orders, near ties, mean/median/P90/max, boundary road IDs, failed OD pairs and source hashes belong in the Supplement/source data. Original paragraph word-count deltas require selection of the actual merged-master paragraphs. No source manuscript was changed in this task.
'''
 (OUT/'Manuscript_R2C3_extension_insertions_EN.md').write_text(inserts,encoding='utf-8')
 report=f'''# Reviewer 2 Comment 3 第二轮补充实验中文技术报告

最终验收状态：**{status}**。自动验收{final['checks_passed'] if final else '待完成'}/{final['checks_total'] if final else '待完成'}项；旧来源{final['old_source_files_checked'] if final else '待复核'}文件前后SHA核对。仅执行本轮两项任务。新洪水0、代理训练0、Full/UE-only搜索重跑0。父R2C3及4.1—5.5保持只读，本轮不合并正式主稿。

## 1. 权威输入与封存

使用4.2已验收双SHA solver、T0_raw={T0:.17g}、Q=360600、RG≤1e-9、max_outer=20000，原38路深度、76有向弧和原十路bit顺序。全部30个含基准条件预审重映射，20个扰动均保持原关闭mask、原十路集合和528正需求OD可达。R2C3三张0.95表已逐状态验证完整物理身份、OD/模型/solver/RG/分母及既有CSV与只读SQLite成本/流量长度，3072项通过。父目录全部交付SHA清单已复核。

首次新UE前封存run_manifest.json与请求状态SHA，预计和实际均为17408个新状态，17张新增表，未超过18500上限。全部30张逻辑表共30720状态=17408新UE+3072父0.95复用+10240原4.2基准；实际20张扰动表完整，未选情景/改参数。未进行可选的Full序列诊断，核心分析专用于原条件DP排序迁移。

## 2. 全十情景定量汇总

{summtable}

各倍率均以10个原合成情景为单位，不把20条件视为20独立样本。P90为NumPy linear分位数，仅描述当前10场景样本；不证明总体尾部可靠性，不作显著性推断。完整排序、第一路、前三有序与前三集合分别计数；Kendall基于同一十路集合的45对道路。迁移regret分母为新J*>0，绝对分钟差=(J_transfer−Jstar)×{ATT0:.17g}。模型隐含平均阶段单次出行时间不是十小时恢复周期累计损失。所有不变、增减与近tie保留。

## 3. 全部扰动结果与路径

{detail}

基准十行和完整双精度数据见Table_R2C3_all10_depth_DP.csv。最坏原DP迁移regret为{worst.transfer_regret_pct:.9f}%，发生在{int(worst.scenario_id)}、rho={worst.rho_depth:.2f}，对应绝对平均阶段ATT差{worst.transfer_delta_ATT_min:.9f}分钟。该数值是固定条件最优排序对输入变化的迁移结果，不是Proposed重跑性能。新J*/ATT相对原输入的变化不能称为算法带来的改善。

20个扰动中，次优全序列落在near_tie_threshold内的条件数为{int(near.second_best_within_near_tie.sum())}，替代首路落在该阈值内的条件数为{int(near.alternative_first_within_near_tie.sum())}。阈值严格按1e-12×max(1,|Jstar|)，仅报告诊断，未改变严格浮点最优值+物理道路全序列字典序tie-break。逐首路受限最优差、第二优全序列/间隔见raw与主CSV；不得把微小差值解读为已证实的运营优劣。

## 4. 精确阈值区间与边界

{boundtable}

十场景公共区间：**{glob.h_open_max_global_m:.17g}<h_c≤{glob.h_closed_min_global_m:.17g}米**，12位小数为({glob.h_open_max_global_m:.12f},{glob.h_closed_min_global_m:.12f}]。来源为原深度文件17位精度重新计算，非复制预期值；极值所属情景/道路见Table_R2C3_threshold_global_intersection.csv，左右基准裕量见逐场景表。

判据closed⇔depth≥threshold导致左端等号不属于不变区间，右端等号属于；np.nextafter测试验证了这一点。每场景自身左边界首次新增关闭后，10/10出现OD不可达；自身右边界向上一个float后均开放一条原关闭道路、仍528正OD可达。公共交集端点另做40个跨情景映射/可达性检查：{canonical(gqa['conditions'])}。

上述mask不变区间不等于最大连通区间。不能把“某情景自身L处断网”写成“所有低于公共L的阈值均使全部情景断网”。原0.28阈值的7/10不可行结果仍保留，另外三个因0.28落在其自身不变区间而未变。右侧越界可仍连通，但不代表成本和排序不变，也不代表对极深开放道路的速度关系进行了实证验证。

## 5. 阈值任务零UE证明

实际映射的阈值仅影响closed门控，速度多项式在开放部分只依赖固定水深；默认开放道路capacity_factor=1、关闭=0。对mask不变条件，38路speed/FFT/capacity完全相同。以相同原十路集合恢复后，各子集active、FFT、有效容量、BPR系数、OD和分母也相同。

每情景测试区间中点、0.30、0.32、nextafter(L,+∞)、U，共50组、51200个恢复状态输入比较，全部按数组精确相等通过。80个本地边界测试及40个公共交集测试保留翻转物理道路与可达OD。任务B新UE调用严格为0，没有为区间证明重复求解状态表。宽区间是先连通选闭路再分组赋分离深度范围的合成机制产物，不能称作真实水动力稳健性或安全裕度。

## 6. 数值、缓存与独立DP

17408/17408新UE成功；最大RG={ue['max_RG']:.16g}，全状态独立AON最大{ue['max_independent_AON_RG']:.16g}；{ue['independent_Dijkstra_samples']}次独立Dijkstra抽查最大{ue['max_Dijkstra_RG']:.16g}；最大守恒误差{ue['max_conservation_error']:.16g}。每个新状态保存76弧flow、迭代、全部OD可达、NumPy BPR复算与身份key。RG不是TSTT误差严格界。solver真实耗时{ue['solver_seconds']:.3f}秒，单进程单核执行墙钟{ue['wall_seconds_this_process']:.3f}秒，不与B=256在线搜索计时混用。

缓存只写本目录cache/depth_extension_states.sqlite3；完整有效网络/OD/BPR/solver/RG/max_outer/T0的key与38维深度hash、变换hash、恢复物理道路集合绑定。旧SQLite仅父目录mode=ro读取，其他旧成本只读CSV。不是mask-only缓存。sources/manifest/bit顺序与复用检查见audit。

30张含原基准的完整表由正向DP、独立反向DP、显式S0—S9求和、前驱回溯与全序列k-best交叉核验，最大误差{dpqa['max_DP_error']:.16g}≤1e-12。m1—7穷举/第二优/终态哨兵/初始平移共{dpqa['small_tests']}项通过。终态S10零权重但真实成本仍保留；并非全网络恢复。DP精确仅针对数值状态表，不是无限精度UE最优性的证明。

## 7. 新图、回复与结论边界

新增两张Supplement图，原R2C3两图SHA未变：全10场景×两倍率排序变化矩阵；逐场景左开右闭阈值区间与0.30基准。每图PDF/600dpiPNG/SVG，字体≥7pt，实际逐图目检及字体/碰撞/几何检查。零差和不变条件不隐藏。首次最终验收在合法ISO时间戳整秒/微秒混合解析处中止；只修正验收程序解析格式，不改日志、数值或冻结脚本，不新增UE。修复记录见audit/validation_attempt1_timestamp_parse_error.md，最终以final_validation.json为准。

英文回复独立回答本意见，沿用父实验0.28的7/10不可达和CRN λ端点19/20关闭集合变化、代表5/6恢复集合变化的已验收结论，没有新空间相关实验。不得合并不同E的完整Kendall/regret。新增水深/阈值证据支持在最终QA通过后关闭本意见的“补充实验与数值审计”部分；本报告状态为PASS时建议作者验收实验完成。静态合成、条件连通、固定OD、容量映射、真实水文/交通联合校准缺失及动态恢复局限仍须保留，不能据此声称现实策略已验证。正式主稿合并、图表编号与PAGE/LINE TO BE FINALIZED仍待后续。

## 8. 文件与复现

核心文件为四张Table_R2C3_*.csv、完整原始状态/路径、两图、英文回复与插入建议、final_validation.json/QA_validation.md。见README_文件索引.md。全部交付SHA在output_manifest.csv；原文件前后保护见audit/source_preservation.csv。所有新增内容只在extension目录，无ZIP。

实际数值使用E:/ProgramData/Anaconda3/envs/rag_demo/python.exe -X utf8 -B运行scripts，加载原runtime_deps只读依赖，新的numba/matplotlib缓存均隔离。本轮阶段命令见logs/execution_commands.md；scripts/reproduce_extension.py --offline-only仅重做小DP和验收，不增加UE、不重生成洪水、不重训代理、不自动进入其他审稿意见。
'''
 (OUT/'Comment_R2_3_extension_results_CN.md').write_text(report,encoding='utf-8')
 # Local prose typography only, no data changes or scientific-rule edits.
 for name in ['Response_R2_Comment3_extension_draft_EN.md','Manuscript_R2C3_extension_insertions_EN.md']:
  p=OUT/name;text=p.read_text(encoding='utf-8')
  for a,b in {'multipliers0.90 and0.95':'multipliers 0.90 and 0.95','all528':'all 528','missing1024':'missing 1,024','required17408':'required 17,408','accepted0.95':'accepted 0.95','so20':'so 20','not20':'not 20','all45':'all 45','is'+n(worst.transfer_regret_pct)+'%':'is '+n(worst.transfer_regret_pct)+'%','scenario'+str(int(worst.scenario_id)):'scenario '+str(int(worst.scenario_id)),'multiplier'+f'{worst.rho_depth:.2f}':'multiplier '+f'{worst.rho_depth:.2f}','to'+n(worst.transfer_delta_ATT_min)+'min':'to '+n(worst.transfer_delta_ATT_min)+' min','all38':'all 38','all1024':'all 1,024','All51200':'All 51,200','fixed0.28m':'fixed 0.28 m','paired3/6km':'paired 3/6 km',':19 of20':': 19 of 20','original0.30m':'original 0.30 m','reductions0.90 and0.95':'reductions 0.90 and 0.95','complete1024':'complete 1,024','times0.6':'times 0.6','the20':'the 20','to0.90':'to 0.90','at0.95':'at 0.95','infeasible0.28m':'infeasible 0.28 m','scenarios and20':'scenarios and 20','29537m':'29537 m','reductions0.90':'reductions 0.90','all10':'all 10','under0.95':'under 0.95','used0.6':'used 0.6','in8/10':'in 8/10','in1/10':'in 1/10','were5/10':'were 5/10','and1/10':'and 1/10','was0.178732%':'was 0.178732%','and0.068710%':'and 0.068710%','and0.112072%':'and 0.112072%','interval is0.288427267383<h_c≤0.392461952492m':'interval is approximately (0.288427267383, 0.392461952492] m','All1024':'All 1,024'}.items():text=text.replace(a,b)
  p.write_text(text,encoding='utf-8')
 (OUT/'README_文件索引.md').write_text('''# 第二轮结果文件索引

所有路径相对于本extension目录。原comment3目录只读。

| 文件 | 内容 |
| --- | --- |
| Comment_R2_3_extension_results_CN.md | 完整中文技术、负面/不变结果与验收边界 |
| Table_R2C3_all10_depth_DP.csv | 全十场景×0.90/0.95/1.0，J*/ATT/全序列/前缀/Kendall/迁移与near-tie |
| Table_R2C3_depth_summary.csv | 两倍率分别以10原情景汇总，均值/中位/P90/最大/变化数 |
| Table_R2C3_threshold_invariance.csv | 每情景17位精度左开右闭区间、极值道路、裕量、越界可达性 |
| Table_R2C3_threshold_global_intersection.csv | 十情景公共区间及极值所属来源 |
| Response_R2_Comment3_extension_draft_EN.md | 英文独立回复草稿，待主稿合并 |
| Manuscript_R2C3_extension_insertions_EN.md | Methods/Results/Discussion/Limitations/Supplement建议 |
| figures/ | 两张新增图PDF、600dpi PNG、SVG及图注 |
| raw/state_tables/ | 每条件1024状态CSV，含17新/3父复用/10原基准 |
| raw/UE_all_logical_states.csv | 全30720逻辑状态成本、来源与RG |
| raw/unique_state_costs.csv | 严格物理身份去重的权威成本 |
| raw/DP_all_states.csv, raw/DP_paths.csv | 正反DP、前驱与S0—S10路径/权重 |
| raw/first_road_alternatives.csv | 逐首路受限最佳值与near-tie诊断 |
| raw/variant_physical_fields.csv | 30条件完整38路映射 |
| raw/logical_state_mapping.csv | 深度、变换、恢复集合、状态key与来源绑定 |
| raw/new_UE_query_log.csv | 17408新UE逐项精度/守恒/迭代/耗时 |
| raw/threshold_boundary_tests.csv | 80本地端点与内部条件测试 |
| raw/global_threshold_boundary_tests.csv | 公共区间40端点测试 |
| raw/threshold_all1024_input_comparisons.csv | 50条件×1024状态成本输入精确相等检查，零UE |
| raw/threshold_boundary_unreachable_OD.csv | 本地边界未服务OD及需求 |
| cache/depth_extension_states.sqlite3 | 新缓存、76弧flow及日志，旧缓存未写入 |
| audit/ | 全来源SHA、复用身份、manifest绑定、独立DP、图形及原文件保护 |
| tests/small_DP_checks.csv | 小m穷举/次优/哨兵/初态位移 |
| logs/ | 新UE尝试与实际阶段命令 |
| run_manifest.json | 第一次新UE前冻结设计/物理状态/参数/预算 |
| final_validation.json, QA_validation.md | 最终状态及全部验收项 |
| output_manifest.csv, output_manifest.sha256 | 完整交付SHA与清单自身hash |

复核入口 scripts/reproduce_extension.py --offline-only。正文未合并，页行号待最终主稿，不生成ZIP。
''',encoding='utf-8')
 print('Reports generated:',status)
if __name__=='__main__':main()
