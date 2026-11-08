# G2 数学定义、条件DP归纳证明与英文引用草稿

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

## 5. 冻结源码定位

- [subset_member_losses](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/generate_candidate_pool.py:53>)
- [ProxyObjective.evaluate](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/generate_candidate_pool.py:109>)
- [candidate_row](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/generate_candidate_pool.py:318>)
- [BudgetedSearch.masks_for_sequence](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/run_full_method_live_ue.py:163>)
- [BudgetedSearch.evaluate_sequence](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/run_full_method_live_ue.py:189>)
- [exact_dp](<E:/jcr2区意见/老家/sci-jcr2区交付/第三周工作/day7_final_method_protocol_freeze_v1.1/formal_code/run_exact_reference_after_method_freeze.py:66>)
