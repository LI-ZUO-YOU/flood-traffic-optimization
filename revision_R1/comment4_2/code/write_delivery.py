from common42 import *
import shutil,zipfile,re,ast,io,csv as csvmod

def write(p,t):Path(p).write_text(t,encoding='utf-8')
def md(d):
 cols=list(d.columns);out=['| '+' | '.join(map(str,cols))+' |','| '+' | '.join(['---']*len(cols))+' |']
 for row in d.itertuples(index=False,name=None):
  out.append('| '+' | '.join((f'{v:.10g}' if isinstance(v,float) else str(v)).replace('|',' / ') for v in row)+' |')
 return '\n'.join(out)
def sig(x):return f'{float(x):.17g}'

def main():
 old=old_states();assert np.allclose(old.normalized_tstt,old.tstt/T0,rtol=1e-14,atol=1e-12)
 refs=frame(S1/'S1_DP_compare_1001_1010.csv');summary=frame(S2/'S2_old10_regret_summary.csv');ev=frame(S2/'S2_original_paths_revalued.csv')
 strict=frame(S3/'S3_critical_path_precision.csv');st=frame(S3/'S3_refinement_states.csv');amb=frame(S3/'S3_ambiguous_cases.csv')
 state=frame(S1/'S1_state_precision_comparison.csv');rank=frame(S2/'S2_scenario_method_rankings.csv');hit=frame(S2/'S2_hit_classification_change.csv')
 g3=js(S3/'G3_acceptance.json');g4=js(S4/'S4_acceptance.json')
 # A numeric main-text table, with separate equality definitions.
 table=[]
 for r in refs.itertuples(index=False):
  row={'scenario_id':r.scenario_id,'Jstar_old':r.Jstar_old,'Jstar_new':r.Jstar_new,'DP_sequence_equal':r.sequence_equal,'DP_objective_levels_within_empirical_epsilon':r.objective_equal_within_frozen_tolerance}
  for label,short in [('Proposed_B256','Proposed'),('SA_original_fixed_seed','SA')]:
   for tier,suffix in [('old_FW_5e-4','old'),('new_path_1e-9','new')]:
    x=ev[(ev.scenario_id==r.scenario_id)&(ev.path_label==label)&(ev.precision_tier==tier)].iloc[0]
    row[f'{short}_regret_{suffix}_pct']=x.regret_pct;row[f'{short}_historical_1e9_hit_{suffix}']=x.historical_absolute_1e9_hit;row[f'{short}_empirical_hit_{suffix}']=x.numerically_equivalent_hit
  rr=rank[rank.scenario_id==r.scenario_id].iloc[0];row['method_rank_old']=rr.rank_empirical_equivalence_old;row['method_rank_new']=rr.rank_empirical_equivalence_new
  table.append(row)
 csv(S5/'Table_4_2_Numerical_convergence_sensitivity.csv',table)
 # Preserve actual original state records, not regenerated coarse outputs.
 raw=S1/'source_state_tables';raw.mkdir(exist_ok=True)
 shutil.copy2(AUD/'source_records/archive/subset_ue_costs.csv',raw/'original_FW_5e4_10240_states.csv')
 for sid in range(1001,1011):shutil.copy2(LEGACY/f'scenario_{sid}/all_1024_highprecision_states.csv.gz',raw/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz')
 rawnew=S4/'source_state_tables';rawnew.mkdir(exist_ok=True)
 roadrows=[]
 for sid,item in saved_solutions().items():
  for bit,road in enumerate(item['candidate_roads']):roadrows.append({'scenario_id':int(sid),'mask_bit_index':bit,'physical_road_id':road})
 for sid in range(3001,3031):
  shutil.copy2(FORMAL/f'exact/scenario_{sid}/all_1024_states.csv.gz',rawnew/f'scenario_{sid}_primary_1e9_1024_states.csv.gz')
  for bit,road in enumerate(js(FORMAL/f'exact/scenario_{sid}/exact_solution.json')['roads']):roadrows.append({'scenario_id':sid,'mask_bit_index':bit,'physical_road_id':road})
 csv(AUD/'S0_road_mask_mapping_40scenarios.csv',roadrows)
 csv(AUD/'S0_numeric_constants.csv',[{'name':k,'value':v} for k,v in {'dry_baseline_TSTT':T0,'empirical_kappa':KAPPA,'old_RG':5e-4,'primary_RG':1e-9,'strict_RG':1e-11,'scored_stages':10,'terminal_R10_weight':0,'stage_R0_R9_weight':.1}.items()])
 # Strict summary is a path-reference sensitivity check, not full-table DP at1e-11.
 mainstrict=strict[strict.path_label.isin(['Proposed_B256','SA_original_fixed_seed'])]
 ssum=[]
 for label,g in mainstrict.groupby('path_label'):
  ssum.append({'method':label,'precision_scope':'1e-11 fixed paths against refined primary-reference path','scenarios':10,
    'mean_regret_pct':g.regret_vs_refined_reference_path_pct.mean(),'median_regret_pct':g.regret_vs_refined_reference_path_pct.median(),
    'P90_regret_pct':np.quantile(g.regret_vs_refined_reference_path_pct,.9),'max_regret_pct':g.regret_vs_refined_reference_path_pct.max(),
    'empirical_hit_count':int(g.empirical_hit_1e11_same_frozen_epsilon.sum())})
 csv(S3/'S3_original_methods_refined_path_summary.csv',ssum)
 c1004=[]
 for tier in ['old_FW_5e-4','new_path_1e-9']:
  s=ev[(ev.scenario_id==1004)&(ev.path_label=='SA_original_fixed_seed')&(ev.precision_tier==tier)].iloc[0]
  c1004.append({'precision':tier,'reference':s.reference_objective,'SA_objective':s.objective,'SA_minus_reference':s.strict_objective_difference,
    'regret_pct':s.regret_pct,'empirical_epsilon':s.frozen_epsilon,'empirically_equivalent':s.numerically_equivalent_hit,'strictly_equal_float':s.bitwise_objective_equal})
 s=strict[(strict.scenario_id==1004)&(strict.path_label=='SA_original_fixed_seed')].iloc[0]
 c1004.append({'precision':'1e-11 selected paths; reference is refined primary-DP path','reference':s.same_reference_path_objective_1e11,
  'SA_objective':s.objective_1e11,'SA_minus_reference':s.objective_difference_1e11,'regret_pct':s.regret_vs_refined_reference_path_pct,
  'empirical_epsilon':s.frozen_epsilon_from_primary_reference,'empirically_equivalent':s.empirical_hit_1e11_same_frozen_epsilon,
  'strictly_equal_float':float(s.objective_1e11).hex()==float(s.same_reference_path_objective_1e11).hex()})
 csv(S2/'S2_case1004_precision_values.csv',c1004)
 lines=['| 精度与参考范围 | 参考目标 | SA目标 | SA−参考 | regret % | 经验等价 |','| --- | --- | --- | --- | --- | --- |']
 for x in c1004:lines.append('| '+' | '.join([x['precision'],sig(x['reference']),sig(x['SA_objective']),sig(x['SA_minus_reference']),sig(x['regret_pct']),str(x['empirically_equivalent'])])+' |')
 write(S2/'S2_case1004_precision_note.md','''# 1004 原固定种子 SA 的极小目标差

SA 取原始单次运行 seed=2026082004，路径为 `5|27|33|30|35|7|21|2|32|20`。Proposed 与原/新 DP 参考路径均为 `5|27|33|30|35|21|7|2|32|20`。仅交换第六、七路就涉及不同状态成本，不能因 regret 很小而把两条序列视为完全相同。

'''+ '\n'.join(lines)+f'''

旧稿约 0.000089% 的原值确认为 {sig(c1004[0]['regret_pct'])}%。新 1e-9 表的值为 {sig(c1004[1]['regret_pct'])}%，相对于更严格复核过的同一参考路径为 {sig(c1004[2]['regret_pct'])}%。它发生了数值变化，不能写成“原极小差值不变”。三个范围中 SA 均未达到严格浮点目标相等，也均不在冻结经验容差内，不能四舍五入成 0 后称为命中。

1e-11 一行仅重评同一批固定路径，其参考不是“全 1024 状态 1e-11 DP 已认证最优”。高精度 DP 第二优路径正是该 SA 路径，其与最优差值约 0.00029817，大于本例关键路径观察到的 1e-9/1e-11 目标变化尺度。经验容差和这个观察尺度都不是数学 UE 误差界。
''')
 write(S3/'S3_stability_decision.md',f'''# 关键路径精度判定

复用原先 153 个严格精度状态，仅为固定方法路径、两档参考、次优路径及历史近优竞争路径补算缺失状态。共保存 {len(st)} 个不同情景/mask，其中新求解 {g3['new_UE_solves_total']} 个，包含 {int(st.terminal_state_zero_objective_weight.sum())} 个全恢复终态的零权重检查。所有新增状态的实际 RG≤1e-11，新增求解失败为 {g3['new_call_failures']}；原归档未保存的迭代/重试历史仍明确为缺失，没有补造。

共 {len(strict)} 条有标签固定路径接受重评，其中 Proposed/SA 主路径20条。最大状态相对 TSTT 变化为 {sig(st.relative_TSTT_change.max())}，最大路径目标绝对变化为 {sig(strict.absolute_objective_change.max())}，最大变化/冻结 epsilon 比为 {sig((strict.absolute_objective_change/strict.frozen_epsilon_from_primary_reference).max())}。状态误差和路径目标变化不混用。

每个 1e-9 表内，在经验 epsilon 范围中穷尽检查的近优完整排列数均为1。严格目标采用一致的完整道路 ID 字典序裁决；该容差只用于近并列诊断，不用于改变最小值。次优路径另行纳入严格复核。主方法在经验规则下的排名及命中均未改变，无未解决的实质排序/命中歧义，未触发全表升级。

补充检查使用原 1e-9 成本和已严格复核状态形成混合表，只用于发现尚未覆盖的竞争路径；它没有替代全 1e-11 状态表。所有状态并未全量重新计算至 1e-11。由此可报告“所选固定路径与所查竞争路径稳定”，不能据此证明所有潜在排序的真实 UE 成本排序稳定，也不能把经验 epsilon 或二倍观察变化尺度当作未检查状态的可靠误差界。
''')

 # Compact manuscript replacements and separate response to this comment only.
 meth=f'We evaluated numerical sensitivity on the ten original scenarios without rerunning either optimizer. The archived 1,024-state tables per scenario used link-based Frank-Wolfe assignment at RG ≤ 5 × 10⁻⁴. We independently reconstructed these references and compared them with existing route-column/pairwise tables at RG ≤ 10⁻⁹, preserving the physical states, OD demand, BPR parameters, road mapping, objective and dry-network normalizer. Because the assignment implementation also changed, this comparison is not attributed solely to the stopping threshold. Fixed original method paths, reference paths and competing paths were additionally checked at RG ≤ 10⁻¹¹ using the same high-precision solver. Numerical equivalence uses the previously frozen empirical rule |J_a − J_b| ≤ κ max(1, |J_reference|), with κ = {KAPPA:.12g}; neither RG nor κ is a rigorous bound on TSTT error. Subset DP is exact for its numerically evaluated conditional state-cost table.'
 res='All ten original optimal sequences and all Proposed-versus-SA scenario rankings were unchanged between the archived and high-precision tables, although the numerical objective levels changed beyond the empirical equivalence tolerance in every scenario. Proposed median/P90/maximum regret changed from 0.038077%/0.458887%/1.691636% to 0.038361%/0.462099%/1.690983%. The corresponding SA values changed from 0%/0.815450%/3.511664% to 0%/0.816074%/3.507069%, with objective-hit counts remaining four and six, respectively. In scenario 1004, SA regret increased from 0.0000889277% to 0.000214324% and remained outside the empirical equivalence tolerance. The selected-path 10⁻¹¹ checks preserved the main hit and ranking classifications; they do not constitute a full-table or continuous-UE optimality certificate.'
 write(S5/'S5_正文替换段落与中文核对.md',f'''# 4.2 正文替换段落与中文核对

状态为 draft_with_placeholders。本轮完成数值分析并提供替换文字，尚未整合完整 Word 或修订最终页码。Methods 与原十情景 Results 的拟替换位置明确，最终位置为 AUTHOR_INPUT_NEEDED。

## Methods 拟替换段

{meth}

## 原十情景 Results 拟替换段

{res}

## 正文表

使用 Table_4_2_Numerical_convergence_sensitivity.csv。拟表题为 Numerical convergence sensitivity of conditional references，最终编号待全文整合，当前不编造 Table R 或最终页码。

## 中文核对

十个 DP 序列不变，但十个目标层级均变化并超过经验容差；二者并不矛盾。regret 有小幅改变，逐情景、汇总和1004极小差值均如实列出。原 SA 固定种子未替换，4/10 与6/10命中不变。高精度主表有全量10,240状态，1e-11只覆盖194个所选/竞争状态。新30情景的30,720主状态与1,620路径另列支持证据，不叫新的盲测。

## 正文与补充材料分配

| 结果 | 类别 | 放置与动作 |
| --- | --- | --- |
| 旧/新表主方法 regret、目标层级变化和条件性质 | qualification | 替换原精度说明与原十情景结果，不叠加所有诊断数字 |
| 逐情景主结果和两类命中定义 | necessary_support | 正文一张数值表 |
| 逐mask变化、次优与近并列诊断 | provenance_detail | SI/source data |
| 1004极小差值与1e-11覆盖边界 | qualification | 正文一句，完整数值留SI |
| 新30情景精度复核 | robustness | 支持性附录，不代替原十情景 |
| FW与path求解器设置差异 | provenance_detail | Methods简述及详细设置表 |

新增 Methods 段 {len(meth.split())} 词、Results 段 {len(res.split())} 词。原 Word 本轮仅做用语审计，实际替换前后字数及修订颜色需在整合时核对，不虚构压缩字数。S5_exactness_wording_audit.csv 中的13处匹配按上下文处理，讨论离散DP本身时可保留exact，不能把数值表最优写成无限精度UE认证。
''')
 pdf=Path(r'E:\微信存储\xwechat_files\wxid_x5h5gu0ixjjx21_e4e5\msg\file\2026-10\Review of Surrogate_Guided_Road_Reopening.pdf')
 import pymupdf
 doc=pymupdf.open(pdf);full='\n'.join(p.get_text() for p in doc)
 comment=full.split('4.2 Exactness is conditional on an approximate numerical cost table')[1].split('4.3 The computational reference')[0].strip()
 for a,b in [('\x1c','fi'),('\x1d','fl'),('\x1b','ff'),('\x1e','ffi')]:comment=comment.replace(a,b)
 write(S5/'Reviewer1_Comment4.2_回复草稿.md',f'''# Reviewer 1 Comment 4.2 response draft

Readiness is draft_with_placeholders. Analyses are complete and verifiable in the accompanying tables. Proposed manuscript replacements have not been integrated into the full Word manuscript. Final manuscript and SI locations are AUTHOR_INPUT_NEEDED.

## Original comment

Exactness is conditional on an approximate numerical cost table

{comment}

## Response

We agree that exact subset optimization of a numerical state table does not certify the optimum for infinitely converged UE costs. We independently paired all 10,240 original states with the existing high-precision states for scenarios 1001–1010, checked their masks, physical conditions, road mapping, normalization and achieved gaps, and rebuilt both sets of DP references. We preserved the original Proposed B=256 paths and original single-seed SA outputs. No optimizer or surrogate was rerun.

The archived tables use FW at RG ≤ 5 × 10⁻⁴, whereas the high-precision tables use route-column/pairwise assignment at RG ≤ 10⁻⁹. We explicitly disclose the different assignment implementation and its settings, so the archived-to-new comparison is not presented as a stopping-tolerance-only experiment. All ten reference sequences were unchanged. Their objective levels did change beyond the frozen empirical equivalence tolerance in every case, and we do not call those cost levels numerically identical.

Proposed median, P90 and maximum regret changed from 0.038077%, 0.458887% and 1.691636% to 0.038361%, 0.462099% and 1.690983%. The corresponding SA values changed from 0%, 0.815450% and 3.511664% to 0%, 0.816074% and 3.507069%. All scenario-paired method rankings were preserved, with three Proposed wins, five SA wins and two ties under either the historical absolute 10⁻⁹ threshold or the frozen empirical equivalence rule. Hit counts remained four and six. The historical per-run Proposed flags are retained; the original SA CSV contains no per-run hit boolean, so its historical-threshold classification is explicitly reconstructed rather than described as an archived flag.

Scenario 1004 is reported separately with unrounded values. Its original SA regret was {sig(c1004[0]['regret_pct'])}%, changing to {sig(c1004[1]['regret_pct'])}% on the high-precision table. The SA-minus-reference objective difference was {sig(c1004[0]['SA_minus_reference'])} originally and {sig(c1004[1]['SA_minus_reference'])} at 10⁻⁹. It remains outside the frozen empirical tolerance, including after selected-path 10⁻¹¹ refinement, and is not rounded to zero or called a strict hit.

For the same-solver 10⁻⁹-to-10⁻¹¹ sensitivity check we reused 153 archived strict states and solved only 41 missing competitive/path or zero-weight terminal checks, yielding 194 unique states and 77 labelled fixed-path evaluations. The largest path objective change was {sig(strict.absolute_objective_change.max())}, or {sig((strict.absolute_objective_change/strict.frozen_epsilon_from_primary_reference).max())} times the frozen epsilon. Main method rankings and hit classifications were unchanged. We included the two tables' second-best paths and checked close competitors, but did not recompute every state at 10⁻¹¹. These results support selected-path stability, not a formal bound on every unexamined competitor or a continuous-UE optimum certificate. Missing iteration and retry metadata in archived strict CSVs are disclosed; complete metadata are retained for the 41 new calls.

As supporting evidence only, we independently checked all 30,720 primary states and recomputed all 1,620 archived selected-path objectives for the previously revealed 30-scenario comparison. All paths were legal and all changes stayed within the frozen empirical objective tolerance. This is a retrospective numerical check, not another blind validation sample.

The supplied Methods replacement is quoted below. Exact optimality language is restricted to the numerically evaluated conditional table, and neither RG nor the empirical κ is described as a rigorous TSTT error bound. The original manuscript terminology audit and proposed replacements are supplied; final Word integration and final locations remain pending.

*{meth}*

## 中文核对

原十情景为主分析，目标值与regret的变化完整保留；1004的SA仍非命中。1e-11仅验证固定/竞争路径，不宣称已对全部状态提供数学认证。新30情景只为支持性复核。正文和回复为待整合草稿，不声称完整Word已改。
''')
 # Keep reviewer source provenance separate from the reviewer-facing prose.
 dump(S5/'review_source_provenance.json',{'path':str(pdf),'sha256':sha(pdf),'comment':'4.2 only','extraction_note':'PDF line wraps retained; known ligature encoding control characters expanded for readability'})

 write(OUT/'final_CN_report.md',f'''# 审稿人1第4.2条数值精度核验报告

本轮已完成 S0–S4 数值核验，以及 S5 的正文替换、单条审稿回复和原稿用语审计草稿。原始文件与已冻结方法输出未改，没有新洪水、重训或优化运行。最终 Word 合并、红色修订及页码尚未完成，不能把本报告视为完整论文已返修。

## 核心判定

**排序与命中稳定，数值目标和regret并非不变。** 原十情景20套成本表各含1,024状态，全部可配对并满足其实际 RG 标准。十个 DP 最优序列均相同，原稿 Proposed 和单种子SA的胜/平/负保持3/2/5，目标命中保持4/10、6/10。

但十个最优目标的绝对变化为 {refs.abs_change.min():.10g} 至 {refs.abs_change.max():.10g}，全部超过冻结经验 epsilon。逐状态相对 TSTT 变化均值为 {100*state.relative_TSTT_change.mean():.8g}%，最大为 {100*state.relative_TSTT_change.max():.8g}%。这些数值不能解读成RG给出的误差界。旧表为FW、新表为path solver，差异包含数值实现变化，不能全部归因于RG阈值。

## 原十情景主方法汇总

{md(summary[['method','precision_tier','mean_regret_pct','median_regret_pct','P90_regret_pct','max_regret_pct','historical_1e9_hit_count','empirical_hit_count']])}

regret单位为%。每个方法每个情景只取原固定路径，不取后来多种子的最好值。统计单位为十个情景。P90采用线性插值。历史绝对1e-9命中、冻结经验等价命中和序列命中均另列，未混淆。

## 1004 极小差值

SA 的旧 regret 为 {sig(c1004[0]['regret_pct'])}%，新表为 {sig(c1004[1]['regret_pct'])}%，严格路径复核为 {sig(c1004[2]['regret_pct'])}%。三档均不属于经验等价命中，更不是严格目标相等。详见 02_original_method_path_reevaluation/S2_case1004_precision_note.md 和对应高有效位数 CSV。

## 更严格精度与竞争路径

复用153个已有状态，补算41个，最终194个不同状态用于77条有标签固定路径复核，包含次优路径及历史近优竞争者。全部新增状态 RG≤1e-11，新增失败0。每个1e-9表在经验epsilon以内的近优排列数均为1；原/新DP使用严格最小值和一致字典序，不将epsilon用于改变最小值。

最大相对状态TSTT变化为 {sig(st.relative_TSTT_change.max())}，最大路径目标绝对变化 {sig(strict.absolute_objective_change.max())}，最大变化/epsilon为 {sig((strict.absolute_objective_change/strict.frozen_epsilon_from_primary_reference).max())}。未发现需要全表升级才能解释的主方法排序或命中歧义。没有把整个1024状态表全部算到1e-11，因此不宣称所有竞争序列均有严格认证。旧严格记录未存的迭代/重试字段保留缺失，新调用的实际迭代、RG和时间完整保存。

## 新30情景的支持性复核

逐状态检查30720个1e-9主表状态，并与独立fresh serial结果核对；独立重算1620条选定路径。所选严格复核状态有1651个，路径目标变化最大 {sig(g4['max_absolute_objective_change'])}，最大变化/epsilon为 {sig(g4['max_change_over_frozen_epsilon'])}，1620/1620通过。没有将1651个严格状态说成30720个全状态严格表，也没有把这批已分析情景说成新的盲测。

## 文件导航

- 00_protocol_and_input_audit：源文件哈希、逐情景盘点、逐状态物理配对、求解器设置差异及G0。
- 01_legacy_ue_state_comparison：10240条状态差异、十情景统计、两套独立DP、次优和近并列诊断，source_state_tables保留真实原成本表副本。
- 02_original_method_path_reevaluation：原始固定路径、两档计分、逐情景排序、命中变化与1004专项。
- 03_selected_path_refinement：194个严格状态、77条路径、41个新调用的原始元数据与范围判定。
- 04_new30_supporting_evidence：新30情景的逐状态与路径独立检查。
- 05_manuscript_and_response：正文数值表、13处exact用语审计、待整合正文和审稿回复。

## 主张边界与待整合项

可写“给定数值状态表的条件精确参考”，不能写“已认证无限精度连续UE真实全局最优”。RG是赋值收敛指标，κ是此前冻结的经验系数；二者不是TSTT误差上界。S5文字已据此统一，但原Word仅审计未修改，所有最终页码/行号均待作者在全文整合后提供。

按用户要求仅生成数值结果ZIP，不再打包整套材料。数值包包含主要结果表、状态数据、逐路径数值和文件索引；代码、报告和回复草稿留在本目录。
''')
 # Compact evidence mapping is internal, not a second reviewer's response.
 csv(S5/'S5_evidence_mapping.csv',[
  {'item':'legacy paired full state tables','status':'VERIFIED_DONE','evidence':'S0_data_inventory.csv; S1_state_precision_comparison.csv','manuscript_integration':'pending'},
  {'item':'independent DP and fixed paths','status':'VERIFIED_DONE','evidence':'S1_DP_compare_1001_1010.csv; S2_original_paths_revalued.csv','manuscript_integration':'pending'},
  {'item':'case1004 and strict refinement','status':'VERIFIED_DONE','evidence':'S2_case1004_precision_values.csv; S3_critical_path_precision.csv','manuscript_integration':'pending'},
  {'item':'new30 supporting check','status':'VERIFIED_DONE','evidence':'S4_new30_precision_summary.csv','manuscript_integration':'pending SI'},
  {'item':'wording audit and replacement paragraphs','status':'DRAFT_WITH_PLACEHOLDERS','evidence':'S5_exactness_wording_audit.csv; S5_正文替换段落与中文核对.md','manuscript_integration':'Word not edited'}])
 # Final independent assertions on documented scientific scope.
 assert len(state)==10240 and len(refs)==10 and refs.sequence_equal.all() and not refs.objective_equal_within_frozen_tolerance.any()
 assert not rank.ranking_changed_empirical_rule.any() and not hit.changed_at_frozen_empirical_threshold.any()
 assert len(st)==194 and int(st.new_UE_solve.sum())==41 and st.actual_RG_1e11.le(1e-11).all()
 assert int(st.loc[st.new_UE_solve,'iterations_1e11'].isna().sum())==0
 assert g4['primary_states_checked']==30720 and g4['fixed_paths_independently_recomputed']==1620
 reply=(S5/'Reviewer1_Comment4.2_回复草稿.md').read_text(encoding='utf-8');assert '*'+meth+'*' in reply
 assert not re.search(r'Reviewer\s*2|R2\.',reply,re.I)
 source_count=verify_sources()
 for f in (OUT/'code').glob('*.py'):ast.parse(f.read_text(encoding='utf-8'),filename=str(f))
 g0=js(AUD/'G0_acceptance.json');g0.setdefault('initial_source_manifest_files',g0['source_manifest_files']);g0['source_manifest_files']=source_count;dump(AUD/'G0_acceptance.json',g0)
 dump(OUT/'completion_check.json',{'status':'NUMERICAL_AUDIT_PASS_TEXT_DRAFTS_PENDING_WORD_INTEGRATION','G0':'PASS','G1':'PASS','G2':'PASS','G3':'PASS','S4':'PASS',
   'legacy_old_states':10240,'legacy_new_states':10240,'legacy_DP_sequences_equal':10,'old_new_objective_levels_within_empirical_tolerance':0,
   'original_fixed_method_paths':20,'legacy_strict_states':194,'new_UE_solves':41,'new_UE_failures':0,
   'supporting_primary_states':30720,'supporting_selected_paths':1620,'source_files_hash_rechecked':source_count,
   'solver_implementation_difference_disclosed':True,'historical_strict_metadata_gaps_disclosed':True,
   'algorithms_rerun':0,'surrogate_retraining':False,'new_flood_scenarios':0,'full_1e11_table_claimed':False,'continuous_UE_optimum_certified':False,
   'reply_quote_consistency':'PASS','reviewer_isolation':'PASS','exactness_wording_matches_audited':13,'full_Word_manuscript_modified':False,
   'response_readiness':'draft_with_placeholders','pending':'Integrate supplied passages/table into full manuscript; apply contextual exactness edits; render redline and clean Word; supply final page and line references'})
 # Only numerical files are archived. All prose/code stay outside the ZIP.
 target=OUT/'4.2数值结果_原十情景与支持性核验_20261028.zip'
 numeric=[f for folder in [S1,S2,S3,S4] for f in folder.rglob('*') if f.is_file() and (f.name.endswith('.csv') or f.name.endswith('.csv.gz'))]
 numeric += [S5/'Table_4_2_Numerical_convergence_sensitivity.csv',AUD/'S0_data_inventory.csv',AUD/'S0_state_physical_pairing.csv',AUD/'S0_equivalence_calibration_60pairs.csv',AUD/'S0_calibration_RG_scope.csv',AUD/'S0_road_mask_mapping_40scenarios.csv',AUD/'S0_numeric_constants.csv']
 numeric=sorted(set(numeric));index=io.StringIO(newline='');writer=csvmod.writer(index);writer.writerow(['file','bytes','SHA256'])
 for f in numeric:writer.writerow([f.relative_to(OUT).as_posix(),f.stat().st_size,sha(f)])
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in numeric:z.write(f,f.relative_to(OUT).as_posix())
  z.writestr('00_数值文件索引.csv',index.getvalue().encode('utf-8-sig'))
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None and all(n.endswith(('.csv','.csv.gz')) for n in z.namelist())
 dump(OUT/'numeric_package_integrity.json',{'archive':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'file_count':len(numeric)+1,'CRC':'PASS','numerical_CSV_only':True})
 # A standard full-artifact checksum list remains outside the numeric ZIP.
 allfiles=sorted(f for f in OUT.rglob('*') if f.is_file() and 'runtime_cache' not in f.parts and '__pycache__' not in f.parts and f.name!='checksums.sha256')
 write(OUT/'checksums.sha256','\n'.join(sha(f)+'  '+f.relative_to(OUT).as_posix() for f in allfiles)+'\n')
 print('4.2 DELIVERY COMPLETE',target,'bytes',target.stat().st_size,'files',len(numeric)+1,flush=True)

if __name__=='__main__':main()
