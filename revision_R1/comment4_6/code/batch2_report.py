from batch2_common import *
import platform,re

def link(p,label=None):
 p=Path(p);return f'[{label or p.name}](<{p.as_posix()}>)'
def f(x,n=4):return 'NA' if pd.isna(x) else f'{float(x):.{n}f}'
def md(headers,rows):return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def interval(row):return '['+f(row.percentile95_low)+', '+f(row.percentile95_high)+']'

def deliver(out):
 gate(out);verify_first_batch(out);p=locations(out);check=js(p['audit']/'G2_validation_report.json');assert check['status']=='PASS_S2_S3';assert js(p['figures']/'automatic_QA.json')['status']=='PASS'
 ps=frame(p['delivery']/'Table_4_6_tail_uncertainty.csv');ms=frame(p['delivery']/'Table_4_6_method_uncertainty.csv');vc=frame(p['variance']/'variance_components.csv');sd=frame(p['variance']/'seed_dispersion_by_scenario.csv');base=frame(Path(out)/'02_new30/new30_tail_summary.csv');cond=frame(p['bootstrap']/'high_tail_conditional_resampling_ranges.csv');attr=frame(p['bootstrap']/'scenario_order_stat_attribution.csv');loso=frame(p['bootstrap']/'all30_LOSO_methods_mean_P90_max.csv')
 rows=[]
 for m in COMPARATORS:
  for metric,display in [('delta_mean_pp','均值差'),('delta_P90_pp','两个P90之差')]:
   a=ps[(ps.comparator==m)&(ps.metric==metric)&(ps.scheme=='scenario-only')].iloc[0];b=ps[(ps.comparator==m)&(ps.metric==metric)&(ps.scheme=='scenario+seed')].iloc[0]
   rows.append([LABEL[m],display,f(a.estimate_full30),interval(a),f(a.interval_width),interval(b),f(b.interval_width)])
 tab=md(['Proposed减对照','统计量','全30估计 pp','scenario-only 95%区间','宽度 pp','scenario+seed 95%区间','宽度 pp'],rows)
 rows=[]
 for m in COMPARATORS:
  a=ps[(ps.comparator==m)&(ps.metric=='P90_of_paired_differences_pp')&(ps.scheme=='scenario-only')].iloc[0];b=ps[(ps.comparator==m)&(ps.metric=='P90_of_paired_differences_pp')&(ps.scheme=='scenario+seed')].iloc[0]
  rows.append([LABEL[m],f(a.estimate_full30),interval(a),interval(b)])
 diftab=md(['对照','P90(逐情景配对差) pp','scenario-only 95%区间','scenario+seed 95%区间'],rows)
 variance=md(['方法','情景均值SD pp','平均seed SD pp','RMS seed SD pp','within pp²','observed-between pp²','修正between pp²','粗略单次总方差 pp²'],[[r.label,f(r.SD_scenario_means_pp),f(r.mean_seed_SD_pp),f(r.RMS_seed_SD_pp),f(r.within_variance_pp2),f(r.observed_between_variance_pp2),f(r.between_component_pp2),f(r.rough_total_single_run_variance_pp2)] for r in vc.itertuples()])
 condrows=[]
 for sid in [3026,3029]:
  for bucket in ['0','1','2','>=3']:
   a=cond[(cond.conditioning_scenario_id==sid)&(cond.occurrence_bucket==bucket)&(cond.entity=='proposed')&(cond.scheme=='scenario-only')&(cond.metric=='P90_regret_pct')].iloc[0]
   condrows.append([sid,bucket,int(a.conditional_draws),f(100*a.fraction_of_all20000_draws,2),f(a.conditional_median),f'[{f(a.conditional_quantile025)}, {f(a.conditional_quantile975)}]'])
 condtab=md(['情景','入样次数','重复数','占20000次 %','Proposed P90条件中位数 %','条件2.5%—97.5%范围 %'],condrows)
 impactrows=[]
 for sid in [3026,3029,3025,3004,3010]:
  a=loso[(loso.method=='proposed')&(loso.omitted_scenario_for_sensitivity_only==sid)].iloc[0];impactrows.append([sid,f(a.LOSO29_mean_regret_pct),f(a.LOSO29_P90_regret_pct),f(a.LOSO29_max_regret_pct)])
 impacttab=md(['仅作LOSO的留出情景','Proposed剩余29均值 %','剩余29 P90 %','剩余29最大情景均值 %'],impactrows)
 # Compact reviewer-facing method intervals, all eight frozen methods are retained.
 methrows=[]
 for m in METHODS:
  a=ms[(ms.method==m)&(ms.metric=='P90_regret_pct')&(ms.scheme=='scenario-only')].iloc[0];b=ms[(ms.method==m)&(ms.metric=='P90_regret_pct')&(ms.scheme=='scenario+seed')].iloc[0]
  methrows.append([LABEL[m],f(a.estimate_full30),interval(a),interval(b)])
 methtab=md(['方法','全30情景均值P90 %','scenario-only 95%区间','scenario+seed 95%区间'],methrows)
 report=f'''# Reviewer1第4.6条 第二批S2—S3中文验收报告

状态：**S2—S3及本批G2核验通过；交付后停止。** 生成时间：{now()}。

## 结论先行

严格复用4.1的3001—3030情景、query_cap1590条冻结记录。固定统计种子2026103006，两套分析分别20000次，未新增UE、搜索、模型训练或洪水情景。独立样本量仍为30；20,000次重抽样不是20,000个新灾害样本，也不能把10种子当作10个独立洪水。

原10情景中观察到的Proposed相对SA-original的P90优势，未在新30情景均值P90上复现。Proposed−SA-original全30点估计：均值差+0.2054pp，P90之差+0.2548pp。两套均值差和P90差的95%描述性Bootstrap区间均跨零；不能证明稳定尾部优势，也不能据跨零宣称两方法等效。相对Greedy-ILS的差值和两套区间均位于正方向，观察对Proposed不利，仍不将此事后分析改写为新的确认性显著性检验。

Proposed的情景均值SD为1.2076pp，高于SA-original的0.5150pp，而平均情景内seed SD为0.2213pp，低于0.5554pp。两类稳健性不同，必须同时报告，不能以较低种子波动替代较差的跨情景尾部。

## 1. 协议承接、来源及只读核查

第一批冻结分析协议SHA256为`{sha(Path(out)/'00_audit/analysis_protocol.json')}`。本批依照作者已验收并允许执行S2—S3的指令，以独立第二批执行记录承接原协议中未来阶段的门槛，不修改第一批JSON、报告、代码或原4.1正式检验。计算前核查第一批全部65个封存文件和57项原始来源记录，全部一致。两份源ZIP、必要CSV、原分析代码与权重字节哈希在计算后再次核对。

第一批的“Bootstrap未执行”是当时状态，保留不覆盖；本批执行状态与随机流说明见{link(p['audit']/'batch2_execution_contract.json')}及{link(p['audit']/'precomputation_freeze.json')}。科学计算代码在第一次重抽样之前另存哈希。4.1原2250行仍按既有规则仅选query_cap1590条，time_cap660条不参与。随机方法五个，各30×10；单记录确定性方法三个，各30×1。没有因regret、终止状态或区间结果删除、替换或补跑。

## 2. 固定重抽样实现与估计对象

**scenario-only**：每方法先取每情景既有10种子均值（单记录方法保留其一条值）；在30情景ID上有放回抽30次。所有八个方法共用同一套20000×30外层索引，比较保留情景配对。

**scenario+seed**：完整复用上述外层索引，再对每个抽中的情景位置、每个随机方法，独立有放回抽10个已有种子，重新求该情景位置的均值。不同方法不强制配对种子；同一情景被抽中多次时，内部种子也按出现位置独立抽。确定性方法不抽种子，使用原单值；其两套分布和区间应完全相同，自动验收已确认。

随机流只有冻结种子2026103006：NumPy default_rng/PCG64先一次生成外层整数索引，再继续同一随机流生成形状20000×5×30×10的内部种子索引，方法顺序固定。内部索引先以默认int64抽取，再无损存为uint8；未另挑种子或据结果换随机流。原始外层/内部索引、RNG状态、重抽后的情景均值矩阵均保存，能逐数重建CSV，无需任何UE或搜索。验收中的RNG重建仅验证同一实现，不作为另一批独立样本。

分位数与百分位区间均使用NumPy `method='linear'`。所有区间为20000个统计量的第2.5/97.5百分位数，给出宽度。主点估计始终使用原全30情景，不以Bootstrap分布均值替换、偏差校正或优化原点估计。本条4.6是不确定性的事后描述分析，不是新增预注册确认性比较，不替换4.1 R3的Holm校正p值。

## 3. 四个固定对照的均值差与两个P90之差

{tab}

单位pp为regret百分点。全部差值定义为Proposed减对照，正值不利于Proposed。两套区间并列，不根据哪一个更有利选择展示。对SA-original、SA-restart和BiBeam，均值差和P90差的区间跨零；这是精度不足或相容范围较广的描述，不能推出统计等效。对Greedy-ILS，当前描述性差值区间不跨零且方向不利于Proposed，但没有据此新增或替代确认性检验。

### 严格区分P90之差与配对差的P90

`ΔP90=Q90(Proposed的30情景均值)−Q90(对照的30情景均值)`。

`Q90(d)=Q90(30个逐情景的Proposed−对照差值)`。

{diftab}

以SA-original为例，两个P90之差为+0.2548pp，而配对差的P90为+0.7711pp。后者区间为正与前者跨零并不矛盾，它们回答不同问题。绝不把Q90(d)的区间替换成ΔP90的区间，或选择较有利的一种作为原尾部结论。本批附加导出的delta_median_pp是两个边际中位数之差，不是第一批的配对差中位数；该字段也不用于替换原R3中位数检验。

## 4. 全部方法的情景层尾部区间

{methtab}

逐方法mean、median、P90和maximum的点估计、分布SD及百分位区间全部保存在{link(p['delivery']/'Table_4_6_method_uncertainty.csv')}，没有只展示Proposed或筛选较有利方法。新表保留八种方法，即使正文图聚焦预先指定的Proposed及四对照。

对maximum的Bootstrap输出只宜视为经验重抽样范围。普通经验Bootstrap不能在scenario-only中生成超过已观测最大情景均值的新尾部，其上端不应解释为总体极端值的可靠上界，也不证明真实洪水最大损失受控。双层种子重抽样可能超过原情景均值最大值，但仍来自十个已观察种子的有限支持，不能解决新灾害外推问题。

## 5. 情景间与种子内变异及方差分量

{variance}

对于五个完整十种子随机方法，计算：

- `within=mean_s Var_r(r_sr)`，各情景内样本方差用ddof=1。
- `observed_between=Var_s(mean_r r_sr)`，情景间样本方差也用ddof=1。
- `between_component=max(0, observed_between−within/10)`，截断前值与截断标记均保留。本组五方法均未触发0截断。
- 粗略单次运行方差近似`between_component+within`。这是依赖抽样解释的描述性随机效应近似，不是无假设的物理机制或因果分解；不假定所有洪水情景内噪声都同方差。

方差单位pp²，SD单位pp，二者不直接相加。平均seed SD为`mean_s sqrt(Var_r)`，RMS seed SD为`sqrt(mean_s Var_r)`，一般不相同。例如Proposed为0.2213与0.6299pp，SA-original为0.5554与1.0027pp。不能误把平均SD平方当作within方差。

单记录方法只估计情景间差异。其within、seed SD和修正between等字段为NA，不用0伪装已估计的零种子变异，也没有复制十份数据。

逐情景240条种子离散度记录包含均值、median、SD、方差、IQR、极差和最差种子；完整见{link(p['variance']/'seed_dispersion_by_scenario.csv')}。三个确定性方法的种子离散度为NA。Proposed与SA-original种子指标和情景指标方向不同，是需要如实保留的结果。双层CI通常在本组更宽，但两套目标不同，有限样本下并不保证每个统计量的双层区间都更宽；不以宽窄作为选方法的标准。

## 6. 3026、3029及全部高尾情景影响

全30主结果保留全部情景：Proposed mean=0.548065%，P90=1.329573%，最大情景均值=6.048153%。其高尾前五个情景按第一批已经冻结的顺序为3026、3029、3025、3004、3010；本批不重新挑选高尾名单。

原样本P90直接由第27/28位3004和3025的均值插值，最大两情景3026和3029不直接进入该插值。不能从这一点推断它们对尾部不确定性无影响：重抽样中可被多次抽到，从而改变第27/28位或最大值。scenario-only中3026被选到P90两个插值位置之一的频率为7.65%，3029为28.785%；最大值位置被选为3026的频率为64.185%，这是本次重抽样频率，不是总体洪水概率或因果贡献。

### 对称留一敏感性，主分母不变

{impacttab}

这些是原协议规定的敏感性定义，不是删除数据后的新主结论。全部八方法、每个情景留一共240行均保存；四对照第一批已有的120条P90配对LOSO仍原样保留。n从30变29会改变分位插值权重，所以留一变化不宜解读为某一情景的独立因果效应。Proposed对SA-original的全30 P90差+0.254774pp，在第一批全部30种LOSO中仍为正，范围+0.114795至+0.314926pp。

### 正式Bootstrap中的入样次数与尾部范围

下表只是将同一套20000次正式Bootstrap按某情景出现次数0/1/2/≥3分组，未重新抽样、删去或替换原始情景；每个分组条件下的百分位范围**不是置信区间**，不替代主表全20000次区间。

{condtab}

例如3026在1530次重抽样中出现≥3次，这组Proposed P90的条件中位数为3.0367%，条件2.5/97.5范围约[1.6522,6.0482]；出现0次的7163次重抽样中，相应中位数约1.1770%，范围[0.4603,1.7342]。这说明既有高尾样本的入样组成与重抽样上尾密切相关，但不能隔离为3026的纯因果效应，因为其他情景组成也随之变化。

scenario-only中只要3026至少入样一次，Proposed重抽样最大情景均值就是6.048153%；未入样时最大值较低。双层中3004的少数差种子可能多次被抽中并提升情景均值，因此不照搬这一scenario-only的必然关系。3026本身十种子regret完全一致、seed SD为0，是跨情景困难而非本情景种子波动的例子；3004的Proposed seed SD约3.2291pp、SA-original约3.2874pp，显示另一些情景的条件种子不确定性很大。3029也同时保留其种子波动和较高均值。

全部五个高尾情景、两套方案、八方法P90/最大值及四对照差值的条件范围均输出，不仅报告3026/3029或有利分组。按插值名次归因使用稳定排序，值相同情景可有同名次替代，因此贡献频率仅为经验排序诊断，不作“有用/无用情景”判断。

## 7. 自动核验、图件、可重建性与完整性

本批{len(check['checks'])}项自动检查通过，包括：原输入和第一批全体封存哈希、query_cap与种子分母、固定随机流索引精确重建、重复入样情景的独立内部抽样、所有方法共同外层索引、确定性两方案完全相同、每次重抽样的统计量/差值/P90手工式、全部95%区间端点与宽度、方差分量单位和公式、全部LOSO与条件分组无丢失、原R3正式检验未变。

每套方法分布160000行，配对分布80000行；两套合计480000行原始Bootstrap统计。每套20000次重复只是一份重抽样分布，不能按CSV行数当作独立洪水数。外层索引.npy/CSV、内部索引.npy、重抽后的20000×8×30情景均值矩阵，以及RNG状态和轴定义均保存；NPY是独立数值文件，不是ZIP材料包。重建说明另列，不需要UE、训练或优化模块。

三张图及其源CSV已完成PDF字号、碰撞和面板对齐检查，并逐图查看PNG。数据未因显示便利被裁去；ECDF/情景散点图展示预先指定五方法的全部30个情景，方差图展示全部五随机方法。图件源预检的格式/不确定性提示已人工复核：已供600dpi PNG及可编辑PDF/SVG；描述性SD/方差条不冒充CI，区间图明确给出百分位线段。

验收日志：{link(p['audit']/'G2_validation_report.json')}、{link(p['audit']/'automatic_acceptance_log.csv')}。第一批代码、原始结果和原Word/Response保持不变，本批只新增第二批代码、数据和报告。

## 8. 范围限制及停止点

这是对4.1同一批已有30情景的事后描述性不确定性补充，不是另一批确认性仿真。历史10、新30和4.5的情景没有合并，未读取4.5以改变样本或阈值。结论仅限于给定合成严重洪水分布、固定Sioux Falls网络、固定OD、当前UE模型和m=10恢复问题。

本批不提供新的显著性声明，不把区间跨零解释为等效，不将较低平均seed SD推广成灾害尾部优势，也不以当前区间挑选最有利指标。4.1已有正式主要检验及Holm调整p值仍作为原有记录保留。G2通过后仍按本轮指令停止，不修改Word、不写正式英文Response、不自动进入S4/S5。

主要交付索引：{link(Path(out)/'4.6_第二批结果索引.md')}。后续是否补充或进行正文/回复整合，等待作者另行决定。
'''
 (p['delivery']/'S2_S3_CN_report.md').write_text(report,encoding='utf-8')
 # Exact wide numeric views for convenient inspection, all effects retained.
 for d,key,name in [(ps,'comparator','Table_4_6_comparison_CIs_wide.csv'),(ms,'method','Table_4_6_method_CIs_wide.csv')]:
  z=d.pivot(index=[key,'metric','estimate_full30'],columns='scheme',values=['percentile95_low','percentile95_high','interval_width']);z.columns=['__'.join(c) for c in z.columns];csv(p['delivery']/name,z.reset_index())
 notes='''# 第二批缺失数据、统计与外推限制

数据完整，仍是30情景、1590条query_cap记录。没有补种子、删除高尾情景或改变方法。确定性方法的within/seed SD等NA反映单记录限制；Proposed3026等随机方法的实测零SD保留为0，两者不能混淆。

scenario-only固定已观察十种子均值，仅重抽情景。scenario+seed额外重抽已有种子，属于辅助敏感性目标。两方案共用情景索引而不强制跨方法种子配对。同一情景被抽中两次时，两位置内部独立抽样。每套20000次并不新增洪水信息。

所有区间为描述性百分位区间，无BCa、学生化、参数分布拟合或事后指标/置信水平选择。非线性P90可能偏斜、有离散跳变及有限样本偏差；不以bootstrap均值更换主点估计。跨零不意味着等效，不跨零也不重定义4.1主要检验。

经验Bootstrap的maximum受有限支持限制，scenario-only上端不能超过观测样本最大值，因此相关百分位只能作经验重抽样范围，不作为总体极端损失可靠上界。按高尾情景入样次数分组的百分位范围是条件分布，不是新的CI；不同分组同时改变其他情景组成，不能作纯因果解释。

between校正依赖描述性方差模型解释并可被截断，未验证所有情景种子噪声同方差；已同时保存未截断值、标记与原方差。平均seed SD不等于RMS seed SD。单记录方法不估计零随机波动。

P90之差与配对差的P90保持不同字段；新增delta_median_pp为两个边际中位数之差，不是原R3的配对差中位数，不替代原检验。所有四个固定对照、两种方案均保留，无有利结果筛选。

原10情景P90优势在新30情景均值尾部未复现。适用范围仅为当前合成严重洪水分布、Sioux Falls、固定OD、m10、当前UE模型。未合并历史10或4.5样本，未外推真实洪水/大网络。本轮未改Word或正式英文Response。
'''
 (p['delivery']/'缺失数据与局限_第二批.md').write_text(notes,encoding='utf-8')
 metric_dict={'mean_regret_pct':'mean of30 sampled scenario means,percent','median_regret_pct':'Q50 of30 sampled scenario means,linear','P90_regret_pct':'Q90 of30 sampled scenario means,linear','max_regret_pct':'max of30 sampled scenario means; empirical resampling range, not reliable population endpoint CI','delta_mean_pp':'mean(Proposed)-mean(comparator)','delta_median_pp':'Q50(Proposed)-Q50(comparator),NOT median of paired differences; not used to replace historical R3 median effect','delta_P90_pp':'Q90(Proposed)-Q90(comparator)','P90_of_paired_differences_pp':'Q90(Proposed sampled scenario mean - matched comparator sampled scenario mean)','estimate_full30':'point estimate on original30 means, shared across both schemes','percentile95_low/high':'2.5/97.5 quantiles of20000 statistics,linear','bootstrap_distribution_mean':'descriptive mean of bootstrap statistic distribution,not a bias-corrected replacement estimate','conditional_quantile025/975':'conditional resampling range only,NOT a confidence interval'}
 dump(p['audit']/'bootstrap_metric_dictionary.json',metric_dict)
 (p['audit']/'重建说明.md').write_text('''# 第二批Bootstrap重建说明

1. 从第一批02_new30/new30_run_level.csv读取1590行，按method/scenario_id/replicate排序，五随机方法形成30×10数组，三个确定性方法形成30×1。
2. outer_scenario_indices.npy为20000×30的0基索引，映射到3001—3030。所有方法和两种方案共用。outer_scenario_ids.csv为等价实际ID。
3. nested_seed_indices.npy为20000×5×30×10，轴依次为重复、固定随机方法顺序、外层出现位置、内部种子抽取。uint8无损存0—9。方法顺序见batch2_execution_contract.json。重复出现的相同情景使用不同位置的内层索引。
4. sampled_scenario_values_scenario_only.npy和sampled_scenario_values_scenario_seed.npy为20000×8×30，方法顺序同METHODS。前者索引原情景种子均值，后者按内层选种子求均值，确定性方法始终单值。
5. 每行30值求mean/median/P90/max，分位数method=linear。配对指标按同一重复逐方法差值计算，百分位区间为20000个统计量的2.5/97.5分位数。各字段定义见bootstrap_metric_dictionary.json。
6. 如重建RNG，只初始化default_rng(2026103006)，先默认int64抽20000×30外层索引，再继续抽20000×5×30×10内部索引。初始/外层后/内部后PCG64状态已保存。复核可精确重现，不需原模拟代码、权重或UE。

原始分布CSV采用17位有效数字，完整保存；重建样本与所有区间端点已经逐数验收。本轮不应再运行preflight或覆盖现有第二批冻结。统计种子选择不是新增算法种子或新洪水样本。
''',encoding='utf-8')
 captions(p)
 dump(p['figures']/'visual_review.json',{'at':now(),'status':'PASS','reviewed_final_PNGs':['Fig_new30_tails a,b','Fig_scenario_vs_seed a,b','Fig_bootstrap_intervals a,b'],'all_points_or_intervals_visible':True,'final_width_mm':183,'PNG_dpi':600,'PDF_font_min_pt':7,'alignment_and_collision':'PASS,unchanged1.5pt tolerance','reviewed_source_warnings':['PNG supplied,TIFF not requested;editable PDF/SVG supplied','ECDF/dispersion panels are descriptive raw/SD quantities,not omitted CIs;interval panel has explicit95% percentile lines'],'plot_repair':'variance method labels changed to horizontal layout after initial overlap; no numeric or compute code changed'})
 # Preserve the first index and add a current-stage index linking both accepted batches.
 index=['# Reviewer1第4.6条 第二批S2—S3结果索引','','G2通过。全部主结果n=30，每套Bootstrap20000次，固定种子2026103006。无新仿真/训练/搜索/ZIP，未改Word和正式英文Response。','', '## 先阅读','', '- '+link(p['delivery']/'S2_S3_CN_report.md','完整中文第二批验收报告'),'- '+link(p['delivery']/'缺失数据与局限_第二批.md'),'', '## 核心统计','']
 for filename,label in [('Table_4_6_comparison_CIs_wide.csv','四对照均值/尾部差及两套区间宽表'),('Table_4_6_tail_uncertainty.csv','逐对照完整区间长表'),('Table_4_6_method_CIs_wide.csv','全部方法mean/median/P90/max区间宽表'),('Table_4_6_scenario_seed_variation.csv','情景与种子变异及方差分量')]:index.append('- '+link(p['delivery']/filename,label))
 index+=['','## 原始分布与影响诊断','']
 for filename in ['method_bootstrap_distributions.csv','paired_cluster_bootstrap.csv','all30_LOSO_methods_mean_P90_max.csv','high_tail_conditional_resampling_ranges.csv','scenario_order_stat_attribution.csv']:index.append('- '+link(p['bootstrap']/filename))
 for filename in ['nested_bootstrap_method_distributions.csv','nested_bootstrap_paired_distributions.csv','seed_dispersion_by_scenario.csv','variance_components.csv','scenario_only_vs_nested_intervals.csv']:index.append('- '+link(p['variance']/filename))
 index+=['','## 图件','']
 for name in ['Fig_new30_tails','Fig_scenario_vs_seed','Fig_bootstrap_intervals']:index.append('- '+link(p['figures']/(name+'.png'))+'；'+link(p['figures']/(name+'.pdf'))+'；'+link(p['figures']/(name+'.svg')))
 index+=['','## 验收、索引与复现','', '- '+link(p['audit']/'G2_validation_report.json'),'- '+link(p['audit']/'automatic_acceptance_log.csv'),'- '+link(p['audit']/'重建说明.md'),'- '+link(p['audit']/'resampling_array_schema.json'),'- '+link(Path(out)/'4.6_第一批结果索引.md','第一批封存结果索引（保留原样）'),'','所有新增文件及哈希见00_audit/batch2/output_manifest.csv。当前批次已停止，不自动进入4.5扩样背景或正文/英文回复工作。']
 (Path(out)/'4.6_第二批结果索引.md').write_text('\n'.join(index),encoding='utf-8')
 (Path(out)/'4.6_结果索引.md').write_text('# Reviewer1第4.6条 当前结果索引\n\n- '+link(Path(out)/'4.6_第一批结果索引.md','第一批S0—S1及基础统计')+'\n- '+link(Path(out)/'4.6_第二批结果索引.md','第二批S2—S3及完整Bootstrap/方差分析')+'\n\n当前状态：第二批G2通过，等待作者验收。Word与正式英文Response未修改。\n',encoding='utf-8')
 # Original schema failure and plot failure were implementation diagnostics, not changed data/protocol.
 if (p['audit']/'latest_error.json').exists():dump(p['audit']/'resolved_implementation_notes.json',{'at':now(),'unresolved_conflicts':0,'resolved':['preflight all-zero ancillary column exported asint instead offloat; values exact, original hashes unchanged','figure label collision corrected by horizontal method labels','report-local filename variable renamed to avoid shadowing formatter; numerical outputs unchanged'],'latest_failed_event_sha256':sha(p['audit']/'latest_error.json'),'final_data_validation':'PASS_S2_S3','final_plot_validation':'PASS'})
 for file in [p['delivery']/'S2_S3_CN_report.md',Path(out)/'4.6_第二批结果索引.md',Path(out)/'4.6_结果索引.md']:
  for dest in re.findall(r'\]\(<?([A-Z]:/[^>)]+)>?\)',file.read_text(encoding='utf-8')):assert Path(dest).exists(),(file,dest)
 verify_first_batch(out);gate(out)
 import matplotlib
 dump(p['audit']/'analysis_environment.json',{'Python':sys.version,'NumPy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'platform':platform.platform(),'forbidden_scientific_modules_imported':[]})
 code=[Path(__file__).parent/n for n in ['batch2_common.py','clustered_bootstrap.py','variance_components.py','batch2_influence.py','test_batch2.py','run_4_6_batch2.py','batch2_figures.py','batch2_report.py']];csv(p['audit']/'final_code_manifest.csv',[{'path':str(f),'SHA256':sha(f),'size_bytes':f.stat().st_size} for f in code])
 files=[]
 for folder in [p['audit'],p['bootstrap'],p['variance'],p['figures']]:files += [f for f in folder.rglob('*') if f.is_file() and f.name not in ['output_manifest.csv','batch2_delivery_seal.json','execution_log.jsonl']]
 files += [p['delivery']/n for n in ['S2_S3_CN_report.md','Table_4_6_tail_uncertainty.csv','Table_4_6_method_uncertainty.csv','Table_4_6_scenario_seed_variation.csv','Table_4_6_comparison_CIs_wide.csv','Table_4_6_method_CIs_wide.csv','缺失数据与局限_第二批.md']]+code+[Path(out)/'4.6_第二批结果索引.md',Path(out)/'4.6_结果索引.md']
 files=sorted(set(files));csv(p['audit']/'output_manifest.csv',[{'path':str(f),'SHA256':sha(f),'size_bytes':f.stat().st_size} for f in files])
 dump(p['audit']/'batch2_delivery_seal.json',{'at':now(),'status':'S2_S3_COMPLETE_STOP','G2':'PASS','first_batch_seal_sha256':sha(Path(out)/'00_audit/first_batch_delivery_seal.json'),'first_batch_files_unchanged':True,'execution_contract_sha256':sha(p['audit']/'batch2_execution_contract.json'),'output_manifest_sha256':sha(p['audit']/'output_manifest.csv'),'sealed_files':len(files),'seed':SEED,'B_each_scheme':B,'independent_scenarios':30,'source_query_cap_rows':1590,'new_UE':0,'new_search':0,'new_training':0,'new_scenarios':0,'new_ZIP':0,'Word_changed':False,'formal_English_Response_changed':False,'next_stage':'await author acceptance'})
 print(f'S2/S3 delivery sealed ({len(files)} files), STOP',flush=True)

def captions(p):
 (p['figures']/'图注与来源.md').write_text('''# 第二批图注

Fig_new30_tails. 新30个冻结洪水情景的regret分布。(a) 经验累计分布。(b) 同一批30个情景均值的全部观测，垂直偏移按情景ID固定，仅用于避免重叠，不增加样本；3026、3029依第一批既有高尾名单突出标注。每个随机方法先取10种子平均，BiBeam只有单记录。展示的是预先指定Proposed及四个对照，全部八方法完整数值另存。无置信带、无新检验、无样本排除。源表为第一批new30_scenario_level.csv，图源副本同目录。

Fig_scenario_vs_seed. 独立洪水情景与情景内技术重复的不同变异。(a) 情景均值的样本SD与每情景种子样本SD的平均值，单位pp。(b) 修正between与mean within方差分量，单位pp²。仅展示所有五个十种子随机方法，确定性方法没有内层方差估计，故不伪造零值。Random+LS是Random-start + shared LS的显示简称。条形是描述性点估计，不是CI；mean seed SD不等于RMS seed SD，方差分解非因果。源表variance_components.csv。

Fig_bootstrap_intervals. 固定四对照的情景配对描述性95%百分位Bootstrap区间。(a) mean(Proposed)−mean(comparator)。(b) P90(Proposed)−P90(comparator)，不是配对差值的P90。点为原全30情景点估计，线为各20000次统计量的2.5/97.5分位数；蓝色scenario-only固定原10种子均值，橙色scenario+seed还独立重抽每个入样情景位置的已有种子。两套共用外层索引，确定性方法不作种子抽样。n仍是30独立洪水情景，非300条独立样本；正差不利于Proposed。没有显著性星号、p值或等效声明。源表Table_4_6_tail_uncertainty.csv。

三图最终宽183mm，所有PDF字形至少7pt，可编辑PDF/SVG及600dpiPNG。未将描绘SD或经验分布的图误标为CI；相关区间均为事后描述性分析，不替代4.1主要检验。
''',encoding='utf-8')
