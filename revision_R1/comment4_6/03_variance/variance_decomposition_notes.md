# 描述性方差分解口径

独立单位为30个洪水情景，每个随机方法的10个种子是给定情景内的技术重复。每情景均值先取10种子平均。observed_between=Var_s(情景均值)，within=mean_s Var_r(种子regret)，方差均用ddof=1。均值seed SD=mean_s sqrt(Var_r)，不等于sqrt(within)；后者为RMS seed SD。方差单位pp²，SD单位pp。

仅对十种子齐全的五个随机方法计算可选修正between_component=max(0,observed_between-within/10)，并同时保存截断前值及截断标记。粗略单次运行变异近似为between_component+within。这依赖将情景条件均值与种子噪声分开的抽样解释，不是无假设或因果物理机制分解，也不保证种子噪声同方差。不能把SD和方差直接相加。

确定性单记录方法的情景间统计可计算，但没有重复信息估计其seed SD或within。相应字段为NA，不人为生成十份观测。

scenario-only固定每情景原十种子均值，重抽样30情景。scenario+seed在同一外层情景索引下，对每个抽中位置和每个随机方法独立重抽10种子再求均值；同一情景被抽中多次时其内部种子也独立抽。两个区间的目标不同，双层区间不保证总比单层宽，不能据宽窄选择更有利方法。
