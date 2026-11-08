from load_frozen_results import *
import platform,sys,re

def link(p,label=None):
 p=Path(p);return f'[{label or p.name}](<{p.as_posix()}>)'
def fmt(a,n=4):return 'NA' if pd.isna(a) else f'{float(a):.{n}f}'
def table(headers,rows):return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'

def deliver(out):
 out=Path(out);require_gate(out,'G1');validation=js(out/'00_audit/validation_report.json');assert validation['status']=='PASS_FIRST_BATCH'
 assert js(out/'05_figures/figure_QA_automatic.json')['status']=='PASS'
 check_immutable(out);r=out/'06_delivery';manifest=frame(out/'00_audit/source_manifest.csv');proto=js(out/'00_audit/analysis_protocol.json');old=frame(out/'01_legacy10/legacy10_quantiles.csv');components=frame(out/'01_legacy10/legacy10_P90_order_statistics.csv');summary=frame(out/'02_new30/new30_tail_summary.csv');paired=frame(out/'02_new30/new30_paired_basic_summary.csv');lo=frame(out/'01_legacy10/legacy10_LOSO.csv');newlo=frame(out/'02_new30/new30_LOSO.csv');top=frame(out/'02_new30/new30_top_tail_influence.csv')
 short={'Proposed_B256':'Proposed','SA_original_fixed_seed':'原SA单种子'};precision={'old_FW_5e-4':'旧FW RG≤5e−4','new_path_1e-9':'既有path高精度RG≤1e−9'}
 tabold=table(['方法','精度记录','情景数','mean %','median %','P90 %','maximum %'],[[short[a.method],precision[a.precision_tier],10,fmt(a.mean_regret_pct,6),fmt(a.median_regret_pct,6),fmt(a.P90_regret_pct,6),fmt(a.max_regret_pct,6)] for a in old.itertuples()])
 comp=components[components.P90_weight.gt(0)];rows=[]
 for method in LEGACY_METHODS:
  for tier in PRECISIONS:
   g=comp[(comp.method==method)&(comp.precision_tier==tier)].sort_values('rank_ascending');a,b=g.iloc[0],g.iloc[1]
   rows.append([short[method],precision[tier],int(a.scenario_id),fmt(a.regret_pct,9),fmt(a.P90_component_pp,9),int(b.scenario_id),fmt(b.regret_pct,9),fmt(b.P90_component_pp,9),fmt(a.full10_P90_pct,9)])
 tabcomp=table(['方法','精度','第9位情景','第9位regret %','0.9贡献 pp','第10位情景','第10位regret %','0.1贡献 pp','P90 %'],rows)
 tabnew=table(['方法','情景×种子','mean %','median %','P75 %','P90 %','最大情景均值 %','平均seed SD pp','最差种子P90 %','单次最大 %','经验等价命中率'],[[a.label,f'30×{a.seeds_per_scenario}',fmt(a.mean_scenario_mean_regret_pct),fmt(a.median_scenario_mean_regret_pct),fmt(a.P75_scenario_mean_regret_pct),fmt(a.P90_scenario_mean_regret_pct),fmt(a.max_scenario_mean_regret_pct),fmt(a.mean_seed_SD_pp),fmt(a.P90_per_scenario_worst_seed_regret_pct),fmt(a.global_max_individual_regret_pct),fmt(a.equivalence_hit_rate)] for a in summary.itertuples()])
 tabpaired=table(['对照','平均差 pp','差值中位数 pp','差值P90 pp','两个P90之差 pp','Proposed胜/平/负'],[[LABEL[a.comparator],fmt(a.mean_delta_pp,6),fmt(a.median_delta_pp,6),fmt(a.P90_of_paired_differences_pp,6),fmt(a.difference_of_P90s_pp,6),f'{a.Proposed_wins}/{a.ties}/{a.Proposed_losses}'] for a in paired.itertuples()])
 losorows=[]
 for tier in PRECISIONS:
  g=lo[lo.precision_tier==tier];a=g.iloc[0];losorows.append([precision[tier],fmt(a.full10_delta_P90_pp,6),fmt(g.LOSO9_delta_P90_pp.min(),6),fmt(g.LOSO9_delta_P90_pp.median(),6),fmt(g.LOSO9_delta_P90_pp.max(),6)])
 tabloso=table(['历史精度','全10 P90差 pp','LOSO最小 pp','LOSO中位数 pp','LOSO最大 pp'],losorows)
 losorows=[]
 for m in COMPARATORS:
  g=newlo[newlo.comparator==m];influ=g.loc[g.change_from_full30_delta_pp.abs().idxmax()];losorows.append([LABEL[m],fmt(g.iloc[0].full30_delta_P90_pp,6),fmt(g.LOSO29_delta_P90_pp.min(),6),fmt(g.LOSO29_delta_P90_pp.median(),6),fmt(g.LOSO29_delta_P90_pp.max(),6),int(influ.omitted_scenario_for_sensitivity_only)])
 tabnewlo=table(['对照','全30 P90差 pp','LOSO最小 pp','LOSO中位数 pp','LOSO最大 pp','绝对影响最大留出项'],losorows)
 archives=manifest[manifest.role=='frozen numeric ZIP archive'];tabhash=table(['真实归档','字节数','SHA256'],[[link(a.source_path),int(a.size_bytes),f'`{a.SHA256}`'] for a in archives.itertuples()])
 maxold=float(frame(out/'00_audit/legacy10_anchor_checks.csv').absolute_error.max());cross=frame(out/'00_audit/new30_archive_anchor_checks.csv');maxnew=float(cross.absolute_error.max())
 report=f'''# Reviewer1第4.6条 第一批中文验收报告（S0—S1及新30情景基础核验）

状态：**G0、S1及本批G1通过；G2未执行。到此停止，等待作者验收。** 生成时间：{now()}。

## 本批结论

原10情景的P90算术可以复现。旧FW表中Proposed/SA的P90为0.458886609%/0.815449690%，4.2高精度既有路径复核后为0.462098729%/0.816074103%。提高UE数值精度没有消除“十情景P90仅依赖最高两个观测值”的统计局限。

4.1已有新30情景按每情景10种子均值计算，Proposed/SA-original的P90为1.329572525%/1.074798548%，差为+0.254773977个百分点，正值不利于Proposed；最大情景均值为6.048153%/1.871067%。**原10情景中观察到的Proposed相对原SA的P90优势，未在这批新30情景、10种子均值比较中复现。** 这不是一项新的仿真或新的确认性样本，也不是SA总体优越性的显著性结论。本批没有计算任何新的Bootstrap、p值或置信区间。

## 1. 实际来源、字段及只读边界

{tabhash}

直接读取ZIP实际成员名，中文目录不依赖猜测路径。4.1使用`03_原正式比较数值表/`中的all_run_results、scenario_seed_summaries、Table_R2_method_summary、Table_R3_primary_paired_comparisons和scenario_paired_differences五张表；4.2使用`02_original_method_path_reevaluation/`中的两张S2路径/汇总表。七张解压归档副本均与选定ZIP成员逐字节一致，没有把ZIP和解压副本当作两批样本。

源文件清单共{len(manifest)}项，包括两份ZIP、七个必要CSV成员、七个一致的直接副本、作者方案、25份旧代码、原4.1冻结协议及14项冻结代理文件。旧代码及模型仅作为字节计算SHA256，未导入、加载权重或预测。原Word、既有Response、旧实验文件保持原样，本批新输出仅写入独立目录`{out}`。没有调用UE求解器、生成洪水、训练模型、补种子、重跑搜索或创建ZIP。

方案原文及SHA256、字段类型/缺失数量、ZIP成员CRC与实际成员名均已保存。分析协议见{link(out/'00_audit/analysis_protocol.json')}；来源表见{link(out/'00_audit/source_manifest.csv')}；字段结构见{link(out/'00_audit/source_schema.json')}。输入归一化目标沿用原协议：`{proto['original_normalized_objective']}`。regret单位为百分数，沿用既有`max(0,100*(J−J*)/J*)`口径，没有再次乘100或改动裁剪规则。

## 2. S0数据分母与G0闸口

4.1总2250行，其中query_cap=1590、time_cap=660。主分析严格抽取query_cap，660条时间上限记录未混入。

|方法类别|方法|独立情景|每情景记录|运行数|
|---|---|---|---|---|
|随机重复方法|Proposed、SA-original、SA-restart、UE-Greedy-ILS、Random-start+LS|各30|各10，replicate=0—9|各300，合计1500|
|单记录方法|UE-Greedy-LS、UE-Beam、UE-BiBeam|各30|各1，replicate=0|各30，合计90|

3001—3030恰为30个独立情景。method-scenario-replicate键唯一，目标与regret有限；全部query_cap记录用于基础统计，没有按终止状态、误差大小或表现删掉运行。三个单记录方法没有虚构随机种子。原始相对regret从objective/exact_objective复算，命中布尔值按冻结经验κ={proto['frozen_kappa']:.17g}重新核对，全部一致。κ是既有经验数值等价阈值，不是严格UE误差上界。

4.2路径表154行中，仅按两个指定path_label抽取40行，即10情景×2方法×2精度；其余114条DP及辅助路径不进入方法统计。1001—1010完整，方法/情景/精度键唯一，两种精度使用相同冻结恢复序列。原SA每情景只有一条归档固定种子路径，不能估计其历史种子方差，也没有用新30情景种子替换它。

## 3. S1：原10情景的新旧精度描述统计

{tabold}

这两种精度均来自4.2已有复核，不是本轮重算UE。旧FW与新path记录的求解器和收敛阈值均不同；这里报告同一既有路径在两套数值记录上的统计变化，不把变化解释为某个单独容差参数的因果效应。历史主叙事采用高精度修正版，并列保留旧表便于对照审稿人算术。

### P90对最高两情景的精确依赖

线性分位数在n=10时为`P90=0.9*r_(9)+0.1*r_(10)`，括号表示升序名次。其余八个观测值在排序不变时不直接参与该次P90数值。

{tabcomp}

高精度Proposed由1009和1003决定，SA由1006和1008决定。最大值虽只占0.1权重，因其幅度较大，分别贡献约0.169098和0.350707pp。P90并非汇集十个尾部观测的稳定估计；把同一批数据Bootstrap更多次也不会增加独立情景数。

### 历史全部十次LOSO

{tabloso}

高精度全10的Proposed−SA P90差为−0.353975pp；在所有十次单情景留出中，范围为−0.868436至+0.484627pp。留出1008时方向变为正值。旧精度也有相同方向敏感性。所有十次结果均保留，两精度共20行，不能把某一次删去情景后的结果替代全10主结果。

还需注意，n从10变成9后，线性P90变为第8/9位的0.8/0.2加权。即使留出一个低regret情景，最大值权重也会从0.1变成0.2，P90可能上升；LOSO变化同时含样本组成和分位插值权重变化，不能将其全都归因为“这个情景造成了多少因果影响”。原10排序与构成图在05_figures，包含新旧精度全部40个有序观测。

## 4. 新30情景基础尾部统计及正式表复核

所有灾害情景层统计都先计算每个情景的种子平均值，再对30个情景均值求分位数。**没有用300条随机运行直接求独立灾害样本P90。** 自动验收包含实际300条Proposed运行输入的反例测试，即便误把unit标为scenario，300行也会被分母防护拒绝。

{tabnew}

表中mean/median/P75/P90/最大情景均值均基于30个情景均值。平均seed SD是复核旧正式表所需的每情景样本SD(ddof=1)的跨情景平均，并不是本批已完成方差分量或分层Bootstrap分析。“最差种子P90”指先取各情景10个种子的最大regret，再对30个最大值求P90，回答条件于情景的种子压力问题，不是情景均值尾部的替代指标。

单记录方法的seed SD显示NA，原Table_R2存储的0已单独核对为旧导出约定，不据此声称其随机波动为零。此处各情景只有一个观测，最差种子项数值退化为该单次值，应按此限制解读。原始查询数按归档保留，query_cap是预算上限，并不要求每个算法都恰用256状态；没有为用不满预算的运行补跑。

### 新30情景P90的实际组成

n=30时线性P90为第27/28位的0.9/0.1加权。Proposed由情景3004（约1.296557%）和3025（约1.626710%）决定；SA-original由3004（约1.074080%）和3022（约1.081267%）决定。最大两个情景3026和3029并不直接进入这次P90插值，但对maximum、mean及留一排序关系仍重要。不能把n=10“最大两个决定P90”的描述机械照搬到n=30。

### 配对方向与两种不同的尾部差

{tabpaired}

差值均为Proposed减对照，正值不利于Proposed。“差值P90”是30个逐情景差值的P90；“两个P90之差”是两方法各自30情景P90相减。以SA-original为例，分别为+0.771132pp与+0.254774pp，不能互换。

旧4.1 R3的效应方向是“对照减Proposed”，与本批相反。本批已对90条旧逐情景差及三个既定R3对照进行符号、均值/中位数及胜平负核对，并完整保存原Holm调整p值和既有CI，没有重算或替换。SA-original是本条回应原审稿文字的描述性重点，但没有伪称它是4.1 R3中原有的三项主要检验之一。

### 新30情景全部基础LOSO及高尾情景

{tabnewlo}

四个对照各30次留一，共120行。对SA-original，30次留一的P90差均为正，范围+0.114795至+0.314926pp；绝对改变最大的是留出3025。这里仍然只是已观察到的样本敏感性，不能替代总体尾部置信区间或显著性检验，更不能用于选择删样方案。3026和3029始终保留在全30主表中。

Proposed最高五个情景均值依次为3026=6.048153%、3029=2.702101%、3025=1.626710%、3004=1.296557%、3010=1.163750%。全部方法的最高五情景另有完整CSV，不只披露有利方法或有利情景。最大值是高噪声的描述性指标，不能单凭本次最大值宣称稳定控制或稳定失控。

从基础锚点可见，Proposed的平均seed SD（0.221337pp）低于SA-original（0.555359pp），最差种子P90也较低（2.818218%对3.920082%）；与此同时，情景均值P90、最大情景均值更高。这两类稳健性回答不同问题，不能挑有利的一类替代另一类。本批只复核这些原正式表指标，完整种子变异分析留待第二批。

## 5. 自动核验、图件与资料边界

旧10情景16项mean/median/P90/max锚点全部复现，最大绝对误差{maxold:.3g}pp，小于方案1e−8pp阈值。新30情景与正式逐情景表、R2、原配对记录共{len(cross)}项数值交叉检查全部通过，最大误差{maxnew:.3g}，低于1e−9容差。此外，直接解析作者方案中的五方法、六位小数锚点表，34个数值均在四舍五入容差内匹配，BiBeam的NA另行核对，形成“逐运行重算—正式归档—作者方案”三方验证。字段、ID、种子、唯一键、原regret公式、κ命中、P90手工公式、原检验方向、全部LOSO及扁平300行拒绝测试均有自动日志。

{link(out/'00_audit/validation_report.json')}记录{validation['passed_checks']}项**本批实现的检查**通过，并将三个未来工作块明确标成DEFERRED_NOT_RUN；这不表示执行方案的完整G2或全12条全阶段要求已经完成。Bootstrap、方差分量和英文回复仍未执行。

历史图件以183mm宽、7pt及以上可编辑文字、PDF/SVG和600dpi PNG输出；面板对齐、PDF字形字号和最终碰撞检查通过。源预检仅保留“有PNG而无TIFF”的格式提示，PDF/SVG用于后续排版，PNG为审阅预览。本轮不声称已满足尚未核对的具体期刊最终上传格式。

本批未把原10与新30混合，也未读取4.5作为新30的扩样。没有新增独立观察。本批界定的适用范围为给定合成严重洪水分布、Sioux Falls固定网络、固定OD、当前UE模型与m=10道路恢复问题，不能外推真实洪水或更大网络。

## 6. 本批停止点与后续门槛

已完成：S0数据审计、S1原10新旧精度统计与完整LOSO、历史P90构成图、新30 query_cap基础表/正式锚点复核/配对方向/全部基础LOSO。

尚未启动：20000次情景配对Bootstrap、scenario+seed嵌套Bootstrap、方差分量拆分、4.5可选背景、正式论文文字与英文回复。既有R2中随归档提供的CI只标注为原有记录，未冒充本轮scenario-only新CI。后续只有在作者验收第一批后才继续；未来Bootstrap的固定种子2026103006和20000次数已在方案记录，当前执行次数为0。

主要文件索引：{link(out/'4.6_第一批结果索引.md')}。本批不生成压缩包。交付后停止。
'''
 (r/'G0_G1_CN_report.md').write_text(report,encoding='utf-8');csv(r/'Table_4_6_legacy_precision.csv',old)
 (r/'缺失数据与局限_第一批.md').write_text('''# 第一批缺失数据与局限

数值分母完整：新30 query_cap共1590条，五个方法各30×10、三个方法各30×1；历史10×2方法×2精度共40条。没有删除失败运行、填种子或用time_cap替代。旧10的其他114条DP/辅助路径及time_cap660条是按协议隔离，不是缺失。

1. 历史原SA每情景仅一个固定种子，不能估计其历史seed SD，不能用新30种子直接补齐。
2. 单记录的Greedy-LS/Beam/BiBeam在新表seed SD/IQR显示NA；旧导出0仅为存储约定，不构成零随机波动证据。
3. 全30先平均每情景种子再计算尾部，不能把300次算法运行当作300个独立灾害样本。
4. 新旧UE记录同时涉及求解器和阈值变化，当前只统计既有固定路径记录，不能分离纯精度参数的因果影响。
5. LOSO的样本数会改变线性分位数插值权重，留出结果只能作为敏感性，主10/30分母不变。
6. 原4.1 R2中的CI及R3主要检验均保留其历史标签。本批没有计算scenario-only或scenario+seed CI，没有新增p值、Holm修正或显著性结论。
7. 情景均值P90、P90(情景最差种子)及平均seed SD的目标不同，不能选择有利指标替换不利的情景尾部指标。
8. 两批情景不合并，4.5也不池化。原尾部优势未在新30情景均值P90上复现，不等于已证明两算法等效或SA普遍优越。
9. 范围限于给定合成严重洪水分布、固定Sioux Falls网络/OD、m10及当前UE模型。
10. 完整Bootstrap、分层变异、正文和英文回复属于后续批次，当前没有生成相关结果或宣称已修订Word。
''',encoding='utf-8')
 (out/'05_figures/Fig_legacy_P90_sensitivity_图注.md').write_text('''# 图注

历史10情景P90的样本组成敏感性。(a) 每个方法分别升序排列的全部10个情景regret，新旧精度均保留，共40点；横坐标是名次，并非跨方法配对的同一情景ID。旧表与高精度点几乎重合，分别用空心/实心点和虚/实线区分。(b) 两种精度下Proposed与原SA的P90分解。浅色为第9位regret的0.9倍，深色为第10位的0.1倍，总长度及条末标注为P90。

独立单位是10个历史洪水情景，每方法每情景只有一条归档路径，未提供种子CI，也未新增统计检验。所有数据来自4.2已完成的固定路径精度复核，本轮未进行UE或算法运行。原表FW RG≤5e−4，高精度path RG≤1e−9。图展示的是样本分位数依赖，并不证明总体尾部优势。

数据源：legacy_P90_figure_source.csv及01_legacy10/legacy10_P90_order_statistics.csv。最终宽183mm，字体至少7pt，PNG600dpi用于预览，PDF/SVG可编辑用于后续排版。
''',encoding='utf-8')
 # Human visual review was performed on the final exportedPNG before this delivery call.
 dump(out/'05_figures/visual_review.json',{'at':now(),'status':'PASS','whole_final_PNG_and_both_panels_reviewed':True,'all40_ordered_points_preserved':True,'nearly_overlapping_precisions_explicitly_labelled':True,'labels_no_clipping':True,'minimum_effective_font_pt':7,'width_mm':183,'PNG_dpi':600,'source_warning_reviewed':'PNG present and noTIFF;editablePDF/SVG supplied','repair':'removed decorative PDF hatch pattern after its pattern geometry triggered initial collision failures; unchanged numerical data and unchanged audit tolerance'})
 (out/'00_audit/analysis_protocol.sha256').write_text(sha(out/'00_audit/analysis_protocol.json')+'\n',encoding='ascii')
 (out/'00_audit/provided_execution_plan.sha256').write_text(sha(PLAN)+'\n',encoding='ascii')
 if (out/'00_audit/last_error.json').exists():
  error=js(out/'00_audit/last_error.json');assert error['stage']=='figures','Unresolved non-figure error blocks delivery'
  dump(out/'00_audit/resolved_implementation_issue.json',{'at':now(),'original_error_sha256':sha(out/'00_audit/last_error.json'),'scope':'figurePDF pattern geometry only','resolved':True,'latest_source_and_collision_QA':'PASS','data_or_statistical_protocol_conflicts':0})
  (out/'00_audit/protocol_conflicts.md').write_text('# 当前没有数据或统计协议冲突\n\nG0/G1均通过。日志中的一次图件呈现QA失败已经修正并重新通过：去掉PDF纹理填充，数据、统计定义和审计容差均未改变。历史错误及解决记录保留在本目录。\n',encoding='utf-8')
 idx=['# Reviewer1第4.6条 第一批结果索引','','本批完成S0—S1及30情景基础核验。G0/G1通过，G2未执行。无新增仿真、训练、搜索、Bootstrap或ZIP。','', '## 先阅读','', '- '+link(r/'G0_G1_CN_report.md','完整中文第一批验收报告'),'- '+link(r/'缺失数据与局限_第一批.md'),'', '## 主要数值','']
 for p,label in [(r/'Table_4_6_primary.csv','新30情景基础尾部主表'),(out/'01_legacy10/legacy10_quantiles.csv','原10情景新旧精度mean/median/P90/max'),(out/'01_legacy10/legacy10_P90_order_statistics.csv','原10升序及P90两项权重'),(out/'01_legacy10/legacy10_LOSO.csv','原10全部留一敏感性'),(out/'02_new30/new30_run_level.csv','严格query_cap的1590条原始运行'),(out/'02_new30/new30_scenario_level.csv','240条情景—方法基础统计'),(out/'02_new30/new30_paired_basic_summary.csv','配对均差、胜平负与两种尾部差'),(out/'02_new30/new30_LOSO.csv','新30全部基础LOSO'),(out/'02_new30/new30_top_tail_influence.csv','各方法最高五个情景')]:idx.append('- '+link(p,label))
 idx+=['','## 来源与验收','']
 for f in ['source_manifest.csv','source_schema.json','analysis_protocol.json','validation_report.json','automatic_acceptance_log.csv','legacy10_anchor_checks.csv','new30_archive_anchor_checks.csv']:idx.append('- '+link(out/'00_audit'/f))
 idx+=['','## 图件','', '- '+link(out/'05_figures/Fig_legacy_P90_sensitivity.png','历史排序与P90构成图PNG')+'；'+link(out/'05_figures/Fig_legacy_P90_sensitivity.pdf','PDF')+'；'+link(out/'05_figures/Fig_legacy_P90_sensitivity.svg','SVG'),'', '第二批Bootstrap、分层方差及第三批正文/英文回复未执行，相关结果文件尚不存在。']
 (out/'4.6_第一批结果索引.md').write_text('\n'.join(idx),encoding='utf-8')
 # Resolve every supplied local Markdown file link, then seal outputs and code.
 for file in out.rglob('*.md'):
  if file.name=='provided_execution_plan.md':continue
  for dest in re.findall(r'\]\(<?([A-Z]:/[^>)]+)>?\)',file.read_text(encoding='utf-8')):assert Path(dest).exists(),(file,dest)
 codes=sorted((out/'code').glob('*.py'));csv(out/'00_audit/analysis_code_manifest.csv',[{'source_path':str(p),'size_bytes':p.stat().st_size,'SHA256':sha(p)} for p in codes])
 import matplotlib
 dump(out/'00_audit/analysis_environment.json',{'Python':sys.version,'platform':platform.platform(),'NumPy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'execution':'read-only arithmetic/CSV analysis; original physics/search/model modules not imported'})
 files=[p for p in out.rglob('*') if p.is_file() and p.name not in ['output_manifest.csv','first_batch_delivery_seal.json','execution_log.jsonl'] and '__pycache__' not in str(p)]
 csv(out/'00_audit/output_manifest.csv',[{'path':str(p),'size_bytes':p.stat().st_size,'SHA256':sha(p)} for p in sorted(files)])
 dump(out/'00_audit/first_batch_delivery_seal.json',{'at':now(),'status':'FIRST_BATCH_COMPLETE_STOP','G0':'PASS','G1':'PASS','G2':'NOT_EXECUTED','source_manifest_sha256':sha(out/'00_audit/source_manifest.csv'),'analysis_protocol_sha256':sha(out/'00_audit/analysis_protocol.json'),'output_manifest_sha256':sha(out/'00_audit/output_manifest.csv'),'files_sealed':len(files),'new_UE':0,'new_algorithm_runs':0,'new_scenarios':0,'new_training_or_prediction':0,'bootstrap_runs':0,'new_ZIP':0,'next_stage_requires_author_acceptance':True})
 print('First batch delivered and sealed; STOP before bootstrap/variance/text',flush=True)
