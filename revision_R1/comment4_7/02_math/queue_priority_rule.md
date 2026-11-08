# G2 Primary、Structural Reserve与真实UE队列规则

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

## 源码行号

- [select_scenario](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/screen_primary.py:76>)
- [structural_reserve](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/screen_structural_reserve.py:36>)
- [BudgetedSearch.prefix2_scores](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/run_full_method_live_ue.py:233>)
- [BudgetedSearch.build_seed_queue](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/run_full_method_live_ue.py:248>)
