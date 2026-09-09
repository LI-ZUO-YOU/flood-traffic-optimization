# 第二周第1天：数据冻结与预处理

## 完成状态

- 冻结版本：`week1_recovery_dataset_v1.0`（第一周目录逐字节复制，原文件未修改）
- 四类样本：train=1500、calibration=300、test_id=300、test_severe=300
- 情景数：60 / 20 / 20 / 20，任意两类的 scenario_id 交集均为 0
- 输入：114维，顺序为 38 个标准化水深 + 38 个初始关闭标记 + 38 个已恢复标记
- 标签：`ln(TSTT / 7480225.3449211195)`
- 标准化器：只在训练集上拟合；校准和测试数据只调用 transform
- 权重：训练集中每个情景的总权重均为 25
- bootstrap：10 组，按 60 个训练情景有放回抽取 60 次，每组均保留非空 OOB 情景
- 质量检查：58/58 通过

## 核心交付物

- `preprocessor.pkl`：训练集水深 StandardScaler、列顺序、基准 TSTT 和目标定义
- `feature_config.json`：114 维输入、特征块、数据用途和反变换公式
- `dataset_manifest.json`：版本、划分、质量检查、软件版本和 SHA-256 哈希
- `bootstrap_scenarios.json`：10 个成员的情景抽样、重复次数、OOB 情景和随机种子
- `processed/preprocessed_*.npz`：第二天模型直接读取的四类数组
- `processed/preprocessed_*.csv.gz`：便于审计的压缩表格版本
- `processed/scenario_equal_weights.csv`：训练情景均衡权重
- `scripts/scenario_bootstrap.py`：可独立复现 bootstrap 计划

## 不可违反的数据用途

1. 校准集不参与模型权重训练或 OOB 早停。
2. 普通测试集不用于网络结构选择。
3. 严重测试集不用于调参或重新估计共形分位数。
4. 不得重新合并四类数据后随机划分。
