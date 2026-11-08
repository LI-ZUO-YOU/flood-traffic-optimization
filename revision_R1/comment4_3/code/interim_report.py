from common43 import *

def main():
 assert js(OUT/'logs/serial_batch_completion.json')['tasks']==450
 assert js(OUT/'logs/parallel_enum_completion.json')['tasks']==90
 rows=[]
 for parent,pattern in [(OUT/'02_serial_B256/runs','scenario_*/*/repeat_*/timing.json'),(OUT/'03_enum_within_scenario_4core/runs','scenario_*/repeat_*/timing.json')]:
  for f in parent.glob(pattern):
   r=js(f);assert r['bitwise_gate']['all_pass']
   rows.append({'scenario_id':r['scenario_id'],'method':r['method'],'repeat':r['repeat_id'],'seconds':r['total_online_wall'],'regret_pct':r['regret_pct'],'queries':r['unique_UE_queries']})
 d=pd.DataFrame(rows);assert len(d)==540
 g=d.groupby(['method','scenario_id'],as_index=False)[['seconds','regret_pct','queries']].mean()
 s=g.groupby('method',as_index=False).agg(mean_seconds=('seconds','mean'),median_scenario_seconds=('seconds','median'),mean_regret_pct=('regret_pct','mean'),mean_queries=('queries','mean'))
 csv(OUT/'02_serial_B256/S2_interim_method_summary.csv',s)
 lines=['| 方法 | 平均在线秒 | 情景中位秒 | 平均regret % | 平均唯一状态数 |','| --- | --- | --- | --- | --- |']
 for r in s.itertuples(index=False):lines.append(f'| {r.method} | {r.mean_seconds:.6f} | {r.median_scenario_seconds:.6f} | {r.mean_regret_pct:.8f} | {r.mean_queries:.3f} |')
 text='''# 4.3 第一批中期中文验收

S0资料冻结、S1复杂度参照和S2主计时及四核补充已完成，当前还不能将4.3整体标记完成。离线部署成本、时间回本模型、最终解释与回复需在S3之后完成。

主计时450次全部单进程、单线程、同一物理核、每次独立空状态缓存，没有12秒或其他情景墙钟截断。随机方法严格取4.1原rep0、1、2；确定性方法重复3次。全部目标float.hex、序列、查询账本和候选SHA均与原4.1对应输出一致。单进程完整枚举90次也均与冻结DP逐位一致。

另有90次单个情景内部四核枚举，1,024个独立状态分为四个互斥256状态块，之后合并并DP。四核结果和序列同样逐位一致。这一配置与以前“四个情景同时跑”不同，且没有混入单核主均值。四核池启动成本单列，不藏入UE求解时间。

下表先情景内平均三次，再汇总30个情景；仅为计时和固定算法成本说明，不是新独立泛化验证。

'''+ '\n'.join(lines)+'''

代理推理嵌套在候选总时长中，LS中UE嵌套在LS总时长中，最终成本表使用排除嵌套部分的分项，避免重复累加。冷Python进程补充只用预设情景3001、rep0，单列包含导出和初始化的整进程墙钟，不与上述online-only均值混合。
'''
 (OUT/'02_serial_B256/中期中文验收报告_S0_S1_S2.md').write_text(text,encoding='utf-8')
 dump(OUT/'logs/interim_acceptance.json',{'status':'FIRST_BATCH_PASS_NOT_FULL_4_3_COMPLETE','primary_tasks':450,'within_scenario4core_tasks':90,'all_bitwise_gates':True,'offline_and_final_response':'pending at this stage','created':now()})
 print(s.to_string(index=False),flush=True)

if __name__=='__main__':main()
