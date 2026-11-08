from common44 import *
import math,zipfile,io,csv as csvmod
def markdown(d):
 cols=list(d.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
 for values in d.itertuples(index=False,name=None):lines.append('| '+' | '.join('未完成' if pd.isna(x) else f'{x:.4g}' if isinstance(x,float) else str(x) for x in values)+' |')
 return '\n'.join(lines)
def write(p,s):Path(p).write_text(s,encoding='utf-8')
def main():
 gate=js(OUT/'completion_check.json');accept=js(OUT/'01_code_audit/final_output_acceptance.json');assert accept['status']=='PASS'
 search=js(OUT/'00_lock/frozen_future_search_adapter.json');assert search['SA_m10_replays_pass']==3 and search['m12_m14_proposal_dimension_checks']
 for p,h in search['source_sha256'].items():assert sha(p)==h
 gate['nested_SA_dimensional_adapter']='PASS'
 qa=js(OUT/'05_analysis/figures/visual_QA.json');assert qa['status']=='PASS'
 assert js(OUT/'05_analysis/figures/source_validation.json')['summary']['counts']['FAIL']==0
 gate['figure_visual_and_automated_QA']='PASS; source LOG-GUARD label-only warning reviewed'
 d=frame(OUT/'03_component_scaling/S3_component_profile_raw.csv');summary=frame(OUT/'03_component_scaling/S3_scaling_summary.csv');resource=js(OUT/'00_lock/calibrated_resource_limits.json');prot=js(OUT/'00_lock/frozen_scaling_protocol.json');memory_limit=prot['max_RSS_bytes']/2**30
 table=summary[['m','subsets','completed_runs','failed_runs','candidate_wall_scenario_mean','sampled_peak_RSS_scenario_mean_MiB','mean_prefix_coverage_fraction','mean_completed_policy_wall']].copy()
 table.columns=['m','代理子集数','完成次数','失败次数','候选准备均值秒','采样RSS均值MiB','前缀访问覆盖率','89次DP均值秒'];csv(OUT/'05_analysis/Table_4_4_first_batch_summary.csv',table)
 # Mathematical corrections are explicit, separate from any benchmark code.
 proof=OUT/'05_analysis/S1_complexity_proof.md';t=proof.read_text(encoding='utf-8')
 t+='''\n补充的计数边界。3P(m,4)是构造尝试，不是去重后的唯一序列数。m12的尝试数超过16k本身不足以证明唯一来源必然溢出；m14有24024种不同前缀，每种至少一条唯一序列，才可直接证明原全覆盖逻辑无法容纳16k配额。均衡抽样器构建(m−1)(m−2)(m−3)个循环轨道代表，额外时间与空间O(m³)，然后逐轨道生成tail直到唯一来源达到16k。最后一个轨道或prefix可能只部分使用，实际每位置各道路出现次数的差异由独立审计要求≤1。\n'''
 if '补充的计数边界' not in proof.read_text(encoding='utf-8'):write(proof,t)
 write(OUT/'01_code_audit/S0_parameterization_scope.md','''# 参数化边界和原代码保全

正式 source_snapshot 与4.1 experiment.py均未覆盖。新目录中的 candidate_generalized.py 和 methods_generalized.py 是逐项替换的副本，dimensional_changes.diff可核对搜索部分。ProxyObjective使用R0至R(m−1)的m项均值；高保真mask路径、Greedy终止长度、ILS交换范围、Beam全mask/终止长度、条件DP范围及除数均按m解释。继承的local_search函数保持原样，仅覆盖其调用的mask路径与预算补齐函数；前5位窗口、最好5父序列、两轮停滞和0.001阈值保留。

固定内容包括10个模型、120维特征、38物理道路、候选30k和五来源配额、Primary60、Reserve前10个二路组及每源每三路组最多10个分位点。m>10使用独立定义的循环轨道前缀抽样，明确为size-adapted Proposed。m<=10调用原前缀生成函数。

为了保持原函数上下文，复制文件仍含未使用的历史CLI main、默认select_roads和旧候选包装器；它们不是本批入口。本批只通过common44.select_roads、components44.build与install_search_dimensions进入流程。SurrogateV2.evaluate_proxy_sequence这个历史十道路/11阶段便利接口未调用，真正使用的是冻结transform与predict_members，以及已泛化的ProxyObjective。不能把这些副本宣传为所有历史CLI均已适配的通用软件包。

3个原情景、4种方法的回归使用4.1归档数值状态表，仅验证候选和搜索逻辑，未重新调用UE。每个方法的逻辑缓存独立清空，物理数据来自已知的归档表；这不构成新的UE精度或运行时间证据。新扩展情景的S3进程将Network.solve替换为拒绝调用的函数，全部任务新增UE次数为0。

深入审计还发现原SA内部propose函数使用模块级N_ROADS=10。仅外层m10回归无法暴露这个问题，因此未来S4统一从search_adapter44.install进入，内部提案使用len(sequence)，保持原概率、随机调用次序和种子。该入口又在3001/3002/3003作3次归档SA完整轨迹回归，全部通过；m12/m14各1000次无UE提案检查证明所有位置均可被移动。组件计时的冻结入口和代码没有修改。这是维度硬编码修复，不是依据新规模质量调优；新规模质量尚未产生。
''')
 write(OUT/'03_component_scaling/measurement_definitions.md',f'''# 计时与内存口径

每个组件任务独立子进程，CPU0，NumPy/BLAS/OMP/Torch计算线程限制为1。控制器绑定另一物理核CPU2，仅监测和安排任务，一次只有一个计算worker；无情景或规模并行。启动时检查其他Python任务，代码内未启动其他计算任务。不能据此声称OS绝对无后台调度或锁定CPU频率。

同一开发情景246用于预热框架，计时开始前释放其状态矩阵。每任务重新载入相同权重，每次新建surrogate状态、DP、候选和缓存。主计时是候选准备，不含UE和方法搜索，不等于论文完整在线时间。初始加载、开发预热和候选CSV导出另列。少量分阶段progress日志写入仍包含在准备墙钟内，属于测量开销；89次DP的内部计时不含这些写入。

mask_and_restored_state_build_wall 是整个subset构建调用减predict_members的残差，除mask/restored数组构建，还包括exp反变换、输入提取及有限性/shape检查。feature_transform_wall来自冻结transform；ensemble_forward_wall还包括tensor/输出组装等predict_members内的非transform开销，不冒称纯网络乘法时间。subset_all_inclusive_wall包含前三项，proxy_DP_source_inclusive_wall包含其内部78次DP，不能重复相加。other_bookkeeping_and_progress_log_wall是非嵌套分项和与端到端的差。

RSS是控制器名义50ms采样的计算进程树观测最大值，窗口从ready直到worker结束，包含解释器、模型、准备及CSV导出的分配，不是连续精确峰值，也不是纯在线算法增量内存。另给ready时RSS及相对该基线的增量。worker_peak_wset是Windows进程生命周期高水位，含启动；保存在逐次JSON中。内存图使用采样RSS口径；准备时间图排除CSV导出，二者窗口差异必须保留。输入/模型加载的所谓cold是新进程、已有磁盘缓存，不是清空OS文件缓存的测量。

三次原m10预校准墙钟 {resource['m10_calibration_wall_seconds']} 秒；按事先冻结规则取中位数×10，时间上限为 {resource['max_preprocessing_seconds']:.8f} 秒。RAM上限为冻结可用内存的80%，即 {memory_limit:.5f} GiB。全部计划任务均保留，资源失败将作为右删失时间和未完整观察内存报告，不填0、不因速度重跑。
''')
 status='全部组件任务完成' if gate['component_runs_failed']==0 else '存在已保留的组件失败'
 readiness='m=14组件闸口通过，可以评估进入第二批S4。' if gate['m14_all_component_runs_pass'] else 'm=14组件闸口尚未全面通过，不能直接推进完整质量比较。'
 report=f'''# Reviewer1 4.4 第一批模拟与中文核对

更新于2026年10月29日。当前状态为第一批S0至S3完成，{status}。这不是4.4全部返修完成。原实施方案要求“第一批交付后停止、评估是否适合运行S4”，因此本批到阶段交付处停止。补充意见覆盖了候选配额、前缀设计、强灾情景和对照配置的冲突项，但未取消该阶段交付要求。

## 已完成的证据

源代码和原权重哈希冻结，3个原m10情景×4方法共12次逻辑回归均通过。Proposed候选池顺序、筛选顺序、最终目标float.hex、最终序列、唯一查询及全部逻辑请求路径保持一致。回归复用归档状态成本，没有新增UE求解，不能当作新计时或精度实验。深入审计修复嵌套SA的N_ROADS=10后，另作3次m10完整SA轨迹回归，仍逐位一致；m12/m14无UE提案检查覆盖所有位置。未来方法入口已单独冻结，未改本批组件计时代码。

现有3001至3030均不足14条初始闭路。采用冻结的连通性选路生成机制，只把severe关闭数范围从8至12改为固定14，其他严重洪水参数不变。主种子2026102904，依次6次生成得到4401至4406，全部保留；历史水深、闭路mask和综合hash均作去重。每个新情景保持24节点38道路连通，以全部14条初始关闭道路为共同评分基准一次排序，取嵌套前8/10/12/14条，未按m重设评分分母。

6情景×5规模×3重复，共90个单核组件任务，完成{gate['component_runs_completed']}，失败{gate['component_runs_failed']}。均使用同一冻结10成员模型，完整枚举2^m代理状态，不训练模型、不调用新UE。m16是人为多关闭两条道路的断连特征夹具，只验证计算开销。原图连通要求给出关闭数≤15的必要上界，因此m16不属于原恢复模型的可行实验。

## 数值汇总

{markdown(table)}

时间为六个情景各三次准备时间均值后再平均。RSS为进程树名义50ms采样最大值，包含解释器/权重/CSV导出；它与排除CSV导出的准备时间窗口不同，不能解释为纯模型矩阵占用。m16行必须标注feature fixture，不用于质量外推。每次记录、实际来源配额、候选表、89个DP分项和前缀轨迹都保留。

## 算法改变与复杂度解释

m10保持全5040四前缀的原逻辑；m>10保持30,000候选与16k/5k/4k/3k/2k来源配额，采用冻结的循环轨道均衡前缀抽样。每个完整循环使各道路在四个位置出现次数相同，最后部分循环允许每位置差1；实际均衡性经独立审计。被访问prefix尝试原mean/member/random三类tail，最后一个prefix可能只登记部分tail，以精确满足唯一来源配额。须称size-adapted Proposed，不是未经改动的原Proposed。不能把候选池整体覆盖率与prefix来源抽样覆盖率混为一谈。

实际每次89个DP，包含初始mean和10member，加proxy来源重复10member、4个SD和64个混合DP，mean复用。原初始理论表曾将mean复用重复计数为90，最终理论表按源码与所有完整运行校正为89，计时程序未改变。全状态表和DP仍保留指数项，固定候选数、固定B均不能使总成本成为多项式。Kendall orientation还含候选数乘m²的时间和空间项。完整说明见S1_complexity_proof.md。

## 阶段闸口与下一批边界

{readiness} 第二批尚未启动，未产生m12/m14真实目标、条件regret、命中率或方法优劣结论。既定第二批为4401至4406、m10/12/14、Proposed适配版/Greedy-ILS/双向Beam/原SA、原种子索引0/1/2及B256。Greedy初始化55/78/105状态均计费；低预算检查点可能没有完整序列。计划完整参考6×(1024+4096+16384)=129024个UE状态，这些状态目前尚未新算。方法输出必须先冻结，再计算独立参考，不允许把S3代理预测当作UE精确参考。

6个情景是扩展强灾探索性压力测试，没有显著性检验，不是新的确认性盲测。m10/12/14固定B256分别覆盖25%、6.25%、1.5625%的状态空间；不同m的目标使用不同长度的均值，绝对J不能当成同一个问题直接排名。规模适配改变前缀生成的随机流，训练大多针对m10，扩大闭路数还引入输入分布变化，后续质量变化不能全归因于m。即便下一批观察到某规模有利，也不能据此推翻此前4.1和4.3的负面证据，或声称跨网络规模泛化。m15/m18/m20本批未运行。Word正文和最终response均未整合，不标注为可提交材料。

## 阅读顺序

先看05_analysis/Table_4_4_first_batch_summary.csv与图，再看03_component_scaling/S3_component_profile_raw.csv和S3_memory_profile.csv。01_code_audit保存原假设、差异和回归验收；02_scenarios保存新输入、原情景资格与嵌套排序。measurement_definitions.md列出嵌套计时和内存窗口的限制。数值ZIP只放CSV与CSV.GZ；代码、模型、报告和图不进入数值压缩包。
'''
 write(OUT/'first_batch_CN_report.md',report)
 write(OUT/'README_阅读与复现.md','''# 4.4第一批

先阅读first_batch_CN_report.md。第一批仅S0-S3，未启动第二批真实UE优化和完整条件参照。

Python入口按顺序为setup44.py、regression44.py、setup44.py scenarios、run_components44.py、analyze44.py、audit_outputs44.py、plot_scaling44.py和finalize44.py。冻结和情景生成入口拒绝覆盖。历史运行已完成，不要为了查看结果重跑；直接读取表格和逐次JSON。代码入口和原文件的差异见01_code_audit。

原正式模型与4.1/4.2/4.3不修改。此次10道路回归使用归档真实成本，仅审计候选/搜索逻辑。规模组件阶段强制禁止UE。m16是断连特征夹具，不能当作物理恢复案例。下一批须在本批阶段闸口评估后另行启动，沿用已冻结场景/算法/种子/预算。
''')
 write(OUT/'06_manuscript_response/S5_状态说明.md','S5尚未开始。本批仅交付S0至S3证据和内部中文核对；完整UE质量模拟、正文替换和Reviewer1最终回复仍待第二批。Word原稿未修改，不能称为ready_to_submit。\n')
 paths=[]
 for p in OUT.rglob('*'):
  if not p.is_file() or not (p.name.endswith('.csv') or p.name.endswith('.csv.gz')):continue
  if p.name in ['S0_code_assumption_audit.csv','numerical_files_index.csv'] or 'runtime_cache' in p.parts:continue
  paths.append(p)
 index=[]
 for p in sorted(paths):index.append({'relative_path':str(p.relative_to(OUT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)})
 csv(OUT/'05_analysis/numerical_files_index.csv',index)
 paths=sorted(set(paths+[OUT/'05_analysis/numerical_files_index.csv']))
 zipfile_path=OUT/'4.4第一批数值结果_组件规模与回归_20261029.zip'
 with zipfile.ZipFile(zipfile_path,'w',allowZip64=True) as z:
  for p in paths:z.write(p,str(p.relative_to(OUT)).replace('\\','/'),compress_type=zipfile.ZIP_STORED if p.name.endswith('.gz') else zipfile.ZIP_DEFLATED,compresslevel=6)
 with zipfile.ZipFile(zipfile_path) as z:assert z.testzip() is None;assert all(n.endswith(('.csv','.csv.gz')) for n in z.namelist())
 package={'path':str(zipfile_path),'files':len(paths),'bytes':zipfile_path.stat().st_size,'sha256':sha(zipfile_path),'CRC':'PASS','numeric_only':True};dump(OUT/'numeric_package_integrity.json',package)
 gate['independent_output_audit']='PASS';gate['numeric_package_CRC']='PASS';gate['numerical_files']=len(paths);gate['figure_generated']=(OUT/'05_analysis/figures/Fig_4_4_component_scaling.pdf').exists();gate['finished_at']=now();dump(OUT/'completion_check.json',gate)
 manifest={str(p.relative_to(OUT)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file() and 'runtime_cache' not in p.parts and '__pycache__' not in p.parts and p.name not in ['manifest.json','checksums.sha256']}
 dump(OUT/'manifest.json',{'created':now(),'files':manifest});write(OUT/'checksums.sha256','\n'.join(f"{v['sha256']}  {p}" for p,v in sorted(manifest.items()))+'\n')
 print(json.dumps(package,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
