# 第一周恢复状态数据集

本目录完成研究计划第一周剩余两项工作：恢复状态样本生成，以及训练、校准、普通测试、严重测试四类无泄漏划分。

## 结论

输入数据在结构、映射、量纲和连通性方面可用于后续代理模型研究。实际使用的是 `Sioux Falls` 标准基准路网、公开标准 OD 和空间相关模拟积水场，不是真实城区 OSM/实测内涝数据。因此，本数据集适合写成“基准网络上的受控方法验证”，不能写成真实城市内涝重建或直接政策应用。

生成的数据规模如下：

| 数据集 | 情景编号 | 独立情景数 | 状态样本数 | 严重度 |
|---|---:|---:|---:|---|
| train | 1–60 | 60 | 1500 | mild + moderate |
| calibration | 61–80 | 20 | 300 | mild + moderate |
| test_id | 81–100 | 20 | 300 | mild + moderate |
| test_severe | 101–120 | 20 | 300 | severe |

每个 `scenario_id` 只属于一个数据集，同一洪涝实例产生的所有恢复状态不会跨集合出现。

## 主要文件

- `recovery_states_train.csv`：训练集。
- `recovery_states_calibration.csv`：独立校准集，仅用于 normalized split conformal 等校准。
- `recovery_states_test_id.csv`：与训练分布相近的普通测试集。
- `recovery_states_test_severe.csv`：严重损伤压力测试集。
- `recovery_states_all.csv`：四类数据合并文件。
- `recovery_state_manifest.csv`：状态来源、轨迹、恢复子集和状态哈希。
- `recovery_state_features.csv`：仅包含 `state_id` 与 114 个输入特征。
- `recovery_dataset_summary.csv`：各集合汇总统计。
- `recovery_dataset_quality_checks.csv`：最终质量门检查。
- `recovery_dataset_config.json`：随机种子、UE 容差和恢复语义。
- `input_validation/`：输入数据核查、关键道路、容差稳定性与哈希记录。
- `scripts/`、`models/`：可复现生成代码；本地 UE 模型含无 SciPy 环境下的根求解回退。

## 样本定义

每行是一个恢复状态，而不是一个完整排列：

`x = [d, r] -> y = TSTT(d, r)`

- `d_depth_m_pl001`–`d_depth_m_pl038`：38 条物理道路的初始积水深度（m）。
- `d_closed_pl001`–`d_closed_pl038`：初始关闭标记。
- `r_restored_pl001`–`r_restored_pl038`：当前已完成抢通的道路标记。
- `tstt`：静态 UE 下的总旅行时间。
- `normalized_tstt`：`tstt / 7,480,225.3449211195`。
- `excess_tstt_ratio`：`normalized_tstt - 1`。
- `log_tstt_ratio`：`log(normalized_tstt)`，建议第二周优先评估该输出，以减弱长尾回归不稳定。

恢复语义：被恢复的初始关闭物理道路恢复为干燥基准自由流时间和容量；情景中原本未关闭但积水的道路保留其背景扰动。

## UE 求解设置

- 方法：Frank–Wolfe 静态用户均衡。
- 目标相对间隙：`5e-4`。
- 常规最大迭代：1000；未达标样本自动以 3000 次重试。
- 结果：2400/2400 全部收敛，最大相对间隙小于 `5e-4`。
- 5 个情景的容差稳定性复核显示，相比 `1e-4` 参考解，TSTT 相对差异为 0.0175%–0.0920%。

## 第二周使用规则

1. 不要再次随机拆分 CSV；直接使用现有四类文件。
2. 训练集用于拟合模型参数；校准集不得用于早停、调参或模型选择。
3. 普通测试集报告 R²、RMSE、PICP、MPIW。
4. 严重测试集只作为分布偏移压力测试，报告误差、区间增幅和误差—不确定性关系，不宣称 conformal 的分布无关覆盖保证仍成立。
5. 特征标准化参数只能由训练集估计，再应用到其他集合。
6. 轻度情景唯一状态空间较小，训练集仅有 146 个不重复 mild 状态；训练时建议按严重度或 `scenario_id` 使用样本权重，避免中度状态数量占优。

