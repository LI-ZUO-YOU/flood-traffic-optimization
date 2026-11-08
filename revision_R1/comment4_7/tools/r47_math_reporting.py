"""Format G2 computed audits. No experiment/model/solver code."""
from pathlib import Path
import csv
import json

def link(p,label=None,line=None):return f'[{label or Path(p).name}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'

def build_reports(out,dest,v,summary,limitations,mapping,adjudication):
    def evidence(symbol):
        r=next((x for x in mapping if x['symbol']==symbol),None)
        return link(r['source_path'],symbol,r['line']) if r else 'NOT_LOCATED_BEFORE_STOP'
    definitions=r'''# G2 数学定义、条件DP归纳证明与英文引用草稿

本文件为独立审计说明，不是已合入投稿Word、Supplement或正式Response的文字。

## 1. 代理序列目标与disagreement

固定恢复道路集合 $E$，$|E|=m=10$。恢复顺序为
$\pi=(\pi_1,\ldots,\pi_m)$，$S_0=\varnothing$，
$S_k(\pi)=\{\pi_1,\ldots,\pi_k\}$。
成员 $j=1,\ldots,K$ 的预测 $\hat y_j(x(S))$ 对应
$\log(TSTT(S)/TSTT_0)$，因此预测状态超额成本为

$$\widehat C_j(S)=\exp\{\hat y_j(x(S))\}-1.$$

原正式候选生成器定义

$$P_j(\pi)=\frac1m\sum_{k=0}^{m-1}\widehat C_j(S_k(\pi)),$$
$$\mu_P(\pi)=\frac1K\sum_{j=1}^K P_j(\pi),\qquad
D(\pi)=\sqrt{\frac1{K-1}\sum_{j=1}^K[P_j(\pi)-\mu_P(\pi)]^2},\quad K=10.$$

包括空集 $S_0$，不包括全恢复终态 $S_m=E$。代码的 `masks=[0]` 加
`sequence[:9]` 恰好得到10个有权重状态。`ddof=1` 是成员序列目标的样本SD，
不是各状态SD的平均，不是失效概率，也不是校准后的尾部风险。

本批用冻结池中每条序列的10个 `member_XX_objective` 数值重新计算
$\mu_P,D$，没有调用模型。逐状态原始log预测/1024×10预测状态矩阵未找到，
因此 $\widehat C_j$ 的反变换及每个 $P_j$ 的逐状态构造有源码/执行链证据，
不能声称本批从原log数组数值重算了这些中间量。完整限制见G2_缺失证据与限制.md。

## 2. 有序前缀与无序状态

`prefix2`、`prefix3`保留恢复先后顺序；mask只标记已恢复集合。
例如 $(a,b,c)$ 和 $(b,a,c)$ 在第3步到达同一集合，
可共享 $C(\{a,b,c\})$ 的UE状态缓存，但其前缀评分分别包含
$C(\{a\})$ 和 $C(\{b\})$，一般不同。不能把两个有序前缀合并成同一排序记录。

prefix2真实评分为 $C(S_1)+C(S_2)$；prefix3真实评分为
$C(S_1)+C(S_2)+C(S_3)$。这些是前缀排序分数，不是完整序列平均目标；
共同 $C(S_0)$ 无需加入前缀排序。

## 3. 给定状态表的条件subset-DP

固定恢复集合 $E$ 及其全部已归档数值状态成本
$C(S)=TSTT_{UE}(S)/TSTT_0-1$。该表的每个成本取决于已恢复集合，
与到达该集合的恢复操作顺序无关。这里使用的是当前模型中
“网络状态由恢复集合决定”的建模条件，**不是一般UE迭代算法、交通均衡或动态交通的路径无关性定理**。

$$V(\varnothing)=C(\varnothing),$$
$$V(S)=\min_{e\in S}V(S\setminus\{e\})+
\mathbf1_{\{S\ne E\}}C(S),\qquad\varnothing\ne S\subseteq E,$$
$$V(E)=\min_{e\in E}V(E\setminus\{e\}),\qquad J^*=V(E)/m.$$

归纳证明：空集路径只有起始状态，累计成本为 $C(\varnothing)$。
假定所有小于 $|S|$ 的子集最小累计值已求出。任意到达非空 $S$ 的恢复路径，
其最后操作必为恢复某个 $e\in S$，前一状态为 $S\setminus\{e\}$。
当前状态成本在所有到达该集合的路径上相同，若 $S\ne E$ 则加入 $C(S)$，
若 $S=E$ 则末态权重为零。遍历可能的最后操作并取最小值，恰得上述递推。
由归纳可得 $V(E)$ 是包括空集、排除末态的最小累计状态成本，除以 $m$ 即序列目标。

这个证明与离散DP只能说明**相对给定数值UE状态表、固定恢复集合的条件精确最优**。
不证明无限精度UE真值的最优，也不证明恢复集合选择、异质维修时长或多班组问题的全局最优。
本次归档m10表来自历史RG=5e-4设置，不能把它写成4.2的1e-9表。

## 4. 可供后续审稿回复引用的英文数学段落

For a fixed recoverable-road set $E$ of size $m$, let
$S_k(\pi)=\{\pi_1,\ldots,\pi_k\}$ and $S_0=\varnothing$.
Member $j$ predicts the log TSTT ratio. Its sequence objective is
$P_j(\pi)=m^{-1}\sum_{k=0}^{m-1}[\exp\{\hat y_j(x(S_k))\}-1]$.
The ensemble score is the mean of the $K=10$ member sequence objectives,
and sequence-level disagreement is their sample standard deviation with
denominator $K-1$. The initial state contributes to the objective; the
fully restored terminal state has zero weight.

Conditional on the fixed numerical state-cost table $C(S)$, define
$V(\varnothing)=C(\varnothing)$ and
$V(S)=\min_{e\in S}V(S\setminus\{e\})+\mathbf1_{\{S\ne E\}}C(S)$.
Any path reaching $S$ has a final recovered road $e$ and predecessor
$S\setminus\{e\}$. Because the modeled network state and the tabulated cost
are determined by the restored subset, the current cost is the same for
all paths reaching that subset. Induction over $|S|$ therefore establishes
the recurrence, including the zero terminal-state weight, and
$J^*=V(E)/m$. Exactness is conditional on this numerical table and fixed
recoverable set, rather than a claim of infinite-precision UE or global
optimality over recoverable-set selection.

These paragraphs are audit drafts only. They do not assert that any manuscript
or response has already been edited, or that missing raw state-log arrays
have been reconstructed.
'''
    definitions+='\n## 5. 冻结源码定位\n\n'
    for sym in ['subset_member_losses','ProxyObjective.evaluate','candidate_row','BudgetedSearch.masks_for_sequence','BudgetedSearch.evaluate_sequence','exact_dp']:
        definitions+='- '+evidence(sym)+'\n'
    (dest/'definitions_and_induction.md').write_text(definitions,encoding='utf-8')
    queue='''# G2 Primary、Structural Reserve与真实UE队列规则

## Primary60

候选先按(proxy_rank,candidate_id)升序排列。proxy_rank由原池生成时的
(proxy_objective_mean,candidate_id)升序得到，排名从1开始。
固定五渠道顺序与配额：proxy_top15 → ensemble_disagreement10 → sequence_diversity15 → heuristic10 → random10。
跨渠道候选ID不重复，先选渠道保留其名额，后选渠道跳过已入选者继续填满。

disagreement只允许proxy_rank≤int(0.30*N)=floor(0.30N)，N=30000时边界为9000。
在该集合按(-D,proxy_objective_mean,candidate_id)排序。不能从全部30000条无条件挑最高SD。
diversity边界为floor(0.50N)=15000，按与所有既选序列的最小归一化Kendall距离作max-min；
每轮用原np.isclose判定距离并列，再按(proxy_objective_mean,candidate_id)破同分。
距离分母为10条道路的45对相对顺序。

heuristic依combined、flow、betweenness、depth降序和depth升序五规则及其各自反向规则，
从未选池候选中找Kendall最近者，同分按代理均值、ID。
random仅在primary_source=random的5000条原候选中，以原seed-base2026080703+scenario_id
对原索引作np.random.default_rng(...).permutation，再跳过此前入选者取10条。
这是离线重建冻结筛选，不是重新生成候选或重新搜索。

## Structural Reserve：10个prefix2簇，不是10条序列

按有序prefix2分组，每簇取最小proxy_rank。原groupby默认按prefix字符串排序，
再对最小排名作稳定mergesort，取前10簇；不能替换为簇均值或真实UE排序。
在所选簇中按prefix3字符串升序、primary_source字符串升序遍历分组，
每组按(proxy_rank,candidate_id)稳定排序。

对n条候选取q=min(10,n)，执行原NumPy表达式
`positions=np.unique(np.round(np.linspace(0,n-1,q)).astype(int))`。
这是零基位置，不是模型输出分布的概率分位数。
NumPy round保留原实现（包括半整数到偶数），不替换为十进制四舍五入。
去重后位置按升序，其source_quantile_index从1开始；再移除Primary已选ID。
channel_rank是在移除Primary后按保留顺序编号。

## 队列：有序prefix3真实分数和两套不同排序键

prefix2真实分数为C(S1)+C(S2)，按(score,prefix2字符串)排序。
原run先为真实prefix2排名前4簇查询prefix3集合，构建初始队列；
64预算阶段后再处理其余簇并重建队列。
构建时只看当时已观测的状态缓存；不同prefix3共享mask，可能使未显式查询的有序前缀也已具备其R3状态。
不能简单把初始队列写成“只有4簇”。

对具备R3状态的每个有序prefix3，计算C(S1)+C(S2)+C(S3)，
按(score,prefix3字符串)排序，p3_rank从1开始。
source_rank是当前Reserve各primary_source字符串升序后的零基编号。
量化索引优先次序为[1,5,10,3,8,2,7,4,6,9]，对应quantile_priority为0..9。

Reserve键为
`(p3_rank, quantile_priority, (source_rank-p3_rank)%n_sources, proxy_rank)`。
Primary进入队列使用不同键：
`(p3_rank, channel_priority, 50, proxy_rank)`，
channel_priority依proxy_top/disagreement/diversity/heuristic/random为0/1/2/3/4。
两类记录放在同一列表按键排序，最后按完整序列去重；不能将Primary的channel_priority称为Reserve quantile_priority。

## 离线对照的范围

本批从原日志分别恢复两次队列构建时的已观测状态集合，独立重建完整键序，
并与原build_seed_queue纯构建方法逐条对比。没有初始化UEInterface，没有运行BudgetedSearch.run、local_search或run_interval。
对实际C阶段从既有请求账本恢复已评价序列、已有状态与预算余量，核对首个可容纳候选。
这验证记录中的队列选择一致性，不生成任何新序列、搜索轨迹或UE值。
'''
    queue+='\n## 源码行号\n\n'+'\n'.join('- '+evidence(s) for s in ['select_scenario','structural_reserve','BudgetedSearch.prefix2_scores','BudgetedSearch.build_seed_queue'])+'\n'
    (dest/'queue_priority_rule.md').write_text(queue,encoding='utf-8')
    report=['# Reviewer 1第4.7条 S2/G2 中文验收报告','',f'状态：**{v["status"]}**。自动检查{v["checks_passed"]}/{v["checks_total"]}通过。','',
       '## 1. 作者裁定与原始记录保护','',
       f'本批依据新建的 {link(adjudication)} 进入G2。G1的42/43历史记录及FAIL_NUMERIC_RECONCILIATION_PENDING未修改；G1-R仅直接解释3成员，另外7成员未开展A/B推断。G0/G1/G1-R原输出、原审计程序与冻结来源均作前后哈希核对。','',
       '## 2. 代理数学与全池数值核验','',
       '实际第四周生成器/Primary源码由原执行manifest、generation freeze及Day3实际输入哈希共同绑定到v1.1。没有改用旧冻结目录或当前GitHub副本。源码确认exp(log预测)-1、K=10、空集至第9次恢复共10个有权重状态，以及对10个成员序列目标作ddof=1样本SD。旧11状态序列均值helper的正式调用检查单列。','',
       f'候选检查覆盖{v["proxy_candidate_rows"]}条；proxy_disagreement_formula_check.csv逐候选记录冻结成员目标、均值/SD复算误差及结果。候选池每情景30000条，共10情景。','',
       '**证据边界：**本机归档保存了每序列10个成员目标，可独立复算ensemble mean与sequence-level SD；未找到对应1024×10逐状态原始log预测/成本矩阵。反变换及逐状态到P_j的组合方式有绑定源码证据，但本批未从缺失中间数组数值重算P_j，也未新推断补齐。此项保留证据限制，不伪称全部中间量重建。','',
       '## 3. Primary、Reserve和队列重建','',
       '|情景|候选池|Primary|Reserve序列|prefix2簇|初始队列|扩展队列|原序列评价|实际种子核对|',
       '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in summary:report.append('|'+ '|'.join(str(r[k]) for k in ['scenario_id','pool_candidates','Primary60','Reserve_candidates','prefix2_clusters','queue_initial','queue_expanded','sequence_evaluations','seed_evaluations_checked'])+'|')
    report+=['',
       'Primary使用独立重建及原select_scenario两条路径对照已封存Primary60；Reserve按原NumPy round/unique/linspace位置规则重建并与冻结源函数和原Reserve对照。逐候选结果和全部量化位置分别输出。没有根据结果改变tie-break、渠道配额、seed或取整。','',
       '队列分别重建初始/扩展两次快照，保留p3_rank、quantile_priority、rotated_source_rank、proxy_rank及Primary专用channel_priority/常数50的区别。完整队列不是全部候选都实际评价；实际评价还受已有结果、cache和预算可容纳性约束。实际种子first-fit核对使用既有账本，不重跑搜索。','',
       'ordered prefix与unordered mask不是同一对象。缓存共享同一恢复集合的UE值，不代表两个有序前缀的R1/R2成本或序列累计损失相同。详细说明见queue_priority_rule.md。','',
       '## 4. 条件DP与m阶段目标','',
       f'DP测试共{v["DP_test_rows"]}条记录：m=1..6，各3个固定数学成本表，逐一穷举m!序列对照DP，并测试巨大terminal哨兵和初始成本变化Delta/m。确定性种子{v["pure_math_seed"]}；这些仅为数学数据，不是新洪水或UE。','',
       '预先固定最小两个原情景ID1001、1002，使用历史完整1024状态成本表，在mask、恢复集合、TSTT0归一化单位验证之后，与独立DP、原exact_dp纯函数及封存最优目标/序列对照。末态第10阶段权重为0。证明和英文数学段落见definitions_and_induction.md。','',
       '该exact仅相对固定恢复集合和给定精度状态表条件精确。本次使用的是第四周历史RG=5e-4表，不替代4.2高精度复核，不声称训练或本表全部达到1e-9。','',
       f'另从既有查询日志核对{v["archived_sequence_objective_checks"]}次原完整序列评价的R0—R9目标，既不调用UE也不生成搜索路径。','',
       '## 5. 缺失、异常与停止点','']
    if v['fatal_stop']:
        report+=['**立即停止原因：**'+v['fatal_stop'],'', '未修改冻结源码或原结果。请查scientific_issue_traceback.txt及G2_automatic_checks.csv；本批尚未完成的项目不能报PASS。','']
        (dest/'G2_科学问题诊断报告.md').write_text('# G2 停止诊断\n\n'+v['fatal_stop']+'\n\n未修复原研究结果；原资产和历史验收状态保留。\n',encoding='utf-8')
    else:report+=['未发现触发CRITICAL_MISMATCH的代码版本、候选/队列顺序或目标差异。逐状态原log预测缺失仍保留，因此状态明确包含证据限制。','']
    report+=['没有增加模型推断、加载checkpoint、训练、洪水生成、UE求解或正式优化。没有修改原投稿Word、Supplement或正式Response。英文字段仅为后续可引用数学草稿。','',
             '**本批完成后停止，G3/G4未执行。** 所有输入SHA、逐项检查、环境与完整文件索引随附。','']
    (dest/'G2_中文验收报告.md').write_text('\n'.join(report),encoding='utf-8')
    missing=['# G2 缺失证据与限制','',f'状态：{v["status"]}。缺失不等同已经证实算法错误；不能将缺失项目写成已通过数值复现。','']
    for r in limitations:missing+=['## '+r['item'],'','状态：'+r['status'],'',r['limit'],'']
    missing+=['## 历史运行和展示边界','',
       '未独立恢复历史CPU/NumPy/pandas完整环境。本次使用的实际版本写入G2_validation.json，筛选/量化/队列的离散结果要求逐位一致。',
       '原日志不另存每次完整队列文件；本批以独立实现、冻结纯构建函数和实际种子请求顺序交叉验证，不伪称发现了原先不存在的队列快照文件。',
       'G1-R只对三成员直接解释Huber微差；原G1 FAIL状态和运行时访问/scheduler证据缺口保留。',
       '未进行Word/PDF渲染、正文修改或正式Response写入，因此不能宣称4.7整体已完成。','']
    (dest/'G2_缺失证据与限制.md').write_text('\n'.join(missing),encoding='utf-8')
    index=['# G2 结果文件索引','',f'状态：{v["status"]}；完成后停止。','',f'- {link(adjudication,"只追加的作者阶段性裁定")}', '']
    for p in sorted(dest.iterdir()):
        if p.is_file() and p.name not in ('G2_结果文件索引.md','G2_output_SHA256.csv'):index.append('- '+link(p))
    index+=['','- '+link(out/'tools/r47_math_check.py','离线G2审计程序'),'- '+link(out/'tools/r47_math_reporting.py','报告生成程序'),'','未创建压缩包。']
    (dest/'G2_结果文件索引.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
