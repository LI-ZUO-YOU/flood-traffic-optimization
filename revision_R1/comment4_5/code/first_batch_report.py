"""After-run acceptance, Chinese report and numerical-only archive. No optimization or fitting."""
from common45 import *
import argparse,unittest,io,zipfile,inspect
from verify_batch import verify_run,check_manifest

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--finalize',action='store_true',required=True);a=p.parse_args()
 analysis=OUT/'02_smoke_old_scenarios/acceptance';require_new_output(analysis)
 paths=sorted((OUT/'02_smoke_old_scenarios').glob('scenario_*/*/seed_00'));assert len(paths)==30
 for path in paths:check_manifest(path)
 dump(analysis/'all_smoke_outputs_frozen.json',{'at':now(),'runs':30,'files':{str(p/'pre_reference_manifest.json'):sha(p/'pre_reference_manifest.json') for p in paths},'purpose':'posthoc acceptance only; not main or retrospective quality analysis'})
 # Verify unchanged physical-only exports against the original, hash-frozen inputs.
 phall=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');dev=frame(ROOT/'inputs/historical_201_260.csv');public_rows=[]
 for sid in [246,247,249]+list(range(3001,3031)):
  old=(dev if sid<3000 else phall);old=old[old.scenario_id==sid].sort_values('physical_link_id').reset_index(drop=True)
  ph,roads,audit=public_scenario(sid)
  pd.testing.assert_frame_equal(ph.reset_index(drop=True),old,check_dtype=False,check_exact=True)
  expected_roads,expected_audit=E.select_roads(old)
  assert tuple(roads)==expected_roads
  pd.testing.assert_frame_equal(audit.reset_index(drop=True),expected_audit.reset_index(drop=True),check_dtype=False,check_exact=True)
  assert not {'loss','tstt','relative_gap','optimal_sequence','true_regret'}.intersection(ph.columns)
  for f in [OUT/f'00_audit/public_inputs/scenario_{sid}.csv',OUT/f'00_audit/public_inputs/scenario_{sid}.json',OUT/f'00_audit/public_inputs/road_audit_{sid}.csv']:public_rows.append({'scenario_id':sid,'path':str(f),'sha256':sha(f),'physical_export_matches_frozen_original':True})
 csv(analysis/'public_input_consistency.csv',public_rows)
 for sid in [3001,3002,3003]:
  base=OUT/f'02_smoke_old_scenarios/scenario_{sid}'
  f0=base/'F0_FULL/seed_00'
  for variant in ['F1_NO_RESERVE','F3_NO_DISAG']:assert sha(f0/'candidate_pool.csv.gz')==sha(base/f'{variant}/seed_00/candidate_pool.csv.gz')
  a0=frame(f0/'screened_candidates.csv.gz');a1=frame(base/'F1_NO_RESERVE/seed_00/screened_candidates.csv.gz')
  assert a0[a0.screening_tier=='primary_shortlist'].candidate_id.tolist()==a1[a1.screening_tier=='primary_shortlist'].candidate_id.tolist()
 rows=[];phase_rows=[];source_rows=[];fallback=[]
 for path in paths:
  row=verify_run(path,path.parent.name=='F0_FULL');r=js(path/'result.json');ls=frame(path/'local_search_calls.csv')
  row.update(first_LS_before_J=ls.iloc[0].best_J_before,first_LS_after_J=ls.iloc[0].best_J_after,LS_total_observed_improvement=float(ls.improvement.sum()),candidate_preparation_replay_seconds=r['candidate_construction_seconds'],surrogate_inference_seconds=r['surrogate_inference_seconds'])
  rows.append(row)
  for x in frame(path/'phase_query_efficiency.csv').to_dict('records'):phase_rows.append({'scenario_id':r['scenario_id'],'variant_id':r['variant_id'],'seed_index':r['replicate'],**x})
  pool=frame(path/'candidate_pool.csv.gz');winner='|'.join(map(str,r['best_sequence']));hit=pool[pool.sequence==winner]
  source_rows.append({'scenario_id':r['scenario_id'],'variant_id':r['variant_id'],'seed_index':r['replicate'],'sequence':winner,'in_candidate_pool':not hit.empty,'primary_source':hit.iloc[0].primary_source if not hit.empty else 'outside_pool_local_search','source_tags':hit.iloc[0].source_tags if not hit.empty else 'local_search','interpretation':'posthoc membership only; not causal attribution'})
  for x in r['fallback_log']:fallback.append({'scenario_id':r['scenario_id'],'variant_id':r['variant_id'],'seed_index':r['replicate'],**x})
 csv(analysis/'smoke_results_30.csv',rows);csv(analysis/'phase_query_efficiency.csv',phase_rows);csv(analysis/'selected_candidate_source_attribution.csv',source_rows);csv(analysis/'single_model_source_fallbacks.csv',fallback)
 stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(OUT/'tests'),pattern='test_acceptance.py');result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
 (analysis/'tests.log').write_text(stream.getvalue(),encoding='utf-8')
 dump(analysis/'test_validation.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'at':now()})
 assert result.wasSuccessful() and result.testsRun==10,'Acceptance test failure; preserve evidence and repair verification only if needed'
 verify_sources()
 protocol=js(OUT/'protocol/frozen_protocol.json');freeze=js(OUT/'protocol/freeze_manifest.json')
 for name,v in freeze['files'].items():assert sha(name)==v['sha256'],name
 audits=[]
 for variant in VARIANTS:
  for function in ['local_search','move_neighbors','run_interval','evaluate_prefix2','evaluate_prefix3_for','prefix2_scores','build_seed_queue','evaluate_sequence','fill_one_state']:
   body=inspect.getsource(getattr(E.original.BudgetedSearch,function))
   audits.append({'variant_id':variant,'original_function':function,'source_file':str(E.FORMAL/'run_full_method_live_ue.py'),'function_sha256':hashlib.sha256(body.encode()).hexdigest(),'algorithm_body':'flat prefix/queue adapter' if variant=='F1_NO_RESERVE' and function in ['evaluate_prefix2','evaluate_prefix3_for','build_seed_queue'] else 'unchanged inherited original','wrapper':'sequence/LS ledger instrumentation only' if function in ['local_search','evaluate_sequence'] else 'none','original_file_sha256':sha(E.FORMAL/'run_full_method_live_ue.py')})
 for variant in VARIANTS:
  audits.append({'variant_id':variant,'original_function':'candidate generation/screening','source_file':str(OUT/'code/candidate_factory.py'),'function_sha256':sha(OUT/'code/candidate_factory.py'),'algorithm_body':protocol['adapters'].get(variant,protocol['adapters'].get('F6_F8')),'wrapper':'public physical inputs only','original_file_sha256':sha(E.FORMAL/'generate_candidate_pool.py')})
 csv(OUT/'protocol/code_diff_audit.csv',audits)
 csv(analysis/'gate_summary.csv',[{'gate':g,'status':'PASS','completed_runs':n,'new_UE_solves':0,'new_scenarios_generated':0} for g,n in [('G0',0),('G1',3),('G2',30)]])
 schema=[{'field':'J / complete_J / state_cost','meaning':'original dimensionless loss; J=np.mean(R0..R9); no regret inference in smoke'}, {'field':'solver_seconds','meaning':'0 in replay; no live UE solves'},{'field':'historical_solver_seconds','meaning':'archived solve time for provenance only; never a current timing measurement'},{'field':'proxy_rank in F9','meaning':'fixed seeded random ordinal; proxy_objective_mean and disagreement NA'},{'field':'NA phase improvement','meaning':'no complete incumbent at phase boundary; not zero improvement'},{'field':'population','meaning':'30 technical smoke runs:3001/3002/3003 x ten variants x seed0; retrospective, not900-run secondary analysis'},{'field':'development246','meaning':'functional checks only;246 is present in original training, not independent validation'},{'field':'time columns','meaning':'sealed lookup replay only, not live online performance benchmark'},{'field':'source tags','meaning':'overlapping pool membership; not source causal effect'}]
 csv(analysis/'numeric_schema.csv',schema)
 # Archive numerical data only; no code, trained models, documents or figures.
 archive=OUT/'4.5_第一批_数值结果.zip';assert not archive.exists()
 files=[]
 for folder in [OUT/'02_smoke_old_scenarios',OUT/'01_freeze_and_regression/development_v2',OUT/'01_freeze_and_regression/reproducibility_v2']:
  files.extend(f for f in folder.rglob('*') if f.is_file() and (f.name.endswith('.csv') or f.name.endswith('.csv.gz')))
 files.extend([OUT/'01_freeze_and_regression/simple_models/training_record.csv',OUT/'00_audit/online_vs_full_table_precision.csv',OUT/'protocol/ablation_matrix.csv',OUT/'protocol/code_diff_audit.csv'])
 files=sorted(set(files));csv(analysis/'numeric_archive_index.csv',[{'relative_path':str(f.relative_to(OUT)).replace('\\','/'),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]);files.append(analysis/'numeric_archive_index.csv')
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for f in files:z.write(f,str(f.relative_to(OUT)))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  assert all(n.endswith(('.csv','.csv.gz')) for n in z.namelist())
 dump(analysis/'numeric_archive_validation.json',{'status':'PASS','path':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'files':len(files),'CRC_checked':True,'numerical_only':True,'at':now()})
 training=frame(OUT/'01_freeze_and_regression/simple_models/training_record.csv')
 table='\n'.join(f'| {sid} | '+' | '.join(f"{next(x['J'] for x in rows if x['scenario_id']==sid and x['variant_id']==v):.9f}" for v in VARIANTS)+' |' for sid in [3001,3002,3003])
 report=f'''# Reviewer 1 第4.5条：第一批 S0—S2 中文验收报告

完成时间：{now()}。本批 **G0、G1、G2全部通过**；完成十个变体×3001—3003×seed0的30条技术烟测。它们用于实现验收，不构成新情景主实验，也不是900条 retrospective 次要分析的完成记录。

## 一、资产与精度

来源清单最终1039项（初始G0记录1037项，S0增补另记录2项）。30张完整表共30,720状态，全部mask完整、RG≤1e-9。与4.1的300条Proposed运行合计76,800条独立查询记录比较，TSTT、loss、RG的float.hex均一致，排除“表精度与原在线UE精度不同”的回放冲突。使用4.1实际冻结源码，而非旧v1.1接口中的默认低精度常量。来源清单内原文件hash复核未变，所有新代码与输出均保存在本4.5目录。

## 二、十个变体及F9确认

用户已确认F9保留真实UE前缀排序，只随机化代理依赖部分。F9随机30k池、随机60条primary、随机序号替代代理顺序；真实UE二/三级前缀排序保留，C/D及LS算法体继承原实现，未加载模型、未调用特征变换、代理推理或代理DP。F9的legacy proxy_rank字段明确仅为随机序号，代理目标和disagreement为NA。

F1沿用F0相同池及primary60，不生成层次化reserve，按flat代理顺序选最多10种二路前缀及合法三级前缀，完整seed队列按flat代理秩产生。F3主名额25/0/15/10/10。F6—F8使用单policy；固定最多50,000次来源内原swap/insert扰动，仍不足则按预设独立随机子流在该来源补足，统一最多1,000,000次随机尝试后失败；补足数量逐运行记录，未根据烟测质量改规则。这些属于必要的系统适配，不能作严格单因子因果解释。

开发阶段发现并修正了F1先生成再丢弃reserve的冗余准备路径；保留v1冻结记录，以v2为正式烟测版本。v2前十个变体均在246完成开发功能验收；246属于原训练情景，只作工程检查，不能称独立泛化验证。另对F0和F9在246重复运行，候选/筛选及逻辑请求轨迹一致。

协议版本：{protocol['version']}。协议SHA256：`{sha(OUT/'protocol/frozen_protocol.json')}`。冻结后未改变算法、模型或参数。

## 三、模型及训练边界

原10成员不重训；单MLP固定文件名排序第一项member_01.pt。Ridge和HGB仅使用原训练分割3178条、120个情景，统一冻结120维特征和原log(TSTT/TSTT0)标签，不读取被禁旧/新情景标签拟合、早停或调参。固定Ridge拟合{training.iloc[0].fit_wall_seconds:.6f}s，HGB拟合{training.iloc[1].fit_wall_seconds:.6f}s；共享加载与特征时间另列训练CSV，不能重复计入每个模型。HGB关闭early stopping；cheap model按预设参数无加权拟合，属于系统替代。

## 四、回归与30条烟测

F0在3001、3002、3003的seed0均与4.1逐位一致：最终序列、J、候选池顺序hash、pool和screened语义字段、唯一UE请求顺序/阶段/原因及全部逻辑cache事件。所有30条均验证30,000唯一合法排列、60唯一primary、来源配额、缓存只计首次、R0计费、≤256唯一状态、逐状态重建完整J、阶段计数互斥加总、incumbent仅由完整序列更新。10项自动验收测试全部通过，具体日志见acceptance/tests.log。

下表仅列技术核对的原始J（显示9位小数；CSV保存17位及float.hex），不作性能排名或显著性声明。

| 情景 | F0 | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 |
|---|---|---|---|---|---|---|---|---|---|---|
{table}

## 五、隔离与成本口径

完整成本表仅在父进程；搜索子进程只能通过单mask接口获得已经请求的成本，父进程再次实施256状态硬上限。每个子进程对完整表的故意访问探针均被拒绝，无非预期参考访问。搜索还禁用live Network.solve；本批新增真实UE求解0次。优化计算单任务、CPU0、线程1，父进程仅查表服务，无并发优化或UE计算。

所有时间列都是sealed lookup replay口径，不是4.3式重新计算UE的在线计时。worker solver_seconds=0；historical_solver_seconds保留历史来源，绝不作为当前内核耗时。阶段账本区分首见状态、完整序列、最优解更新和LS调用；首次完整解之前改善为NA。budget_fill保留原结构化前缀补查，不将其自动称为有效改善。最终路径状态来源与候选source tags仅为事后描述，不能解释为单状态或来源的因果贡献。

## 六、缺失及后续边界

本批30/30成功，无被静默剔除或替换的任务，模型/候选/账本验收无缺失。新情景5101—5110尚未生成，主实验300消融+30 Greedy-ILS=330任务未运行；retrospective 900任务未运行；F6—F8共同F0池评分诊断未运行；正式live UE计时、主实验完整DP、统计、正文和英文审稿回复均留在后续批次。旧表DP仅在烟测输出封存后作独立验收，未回写或修改优化。

按照用户提供方案第9/10节“第一批只做S0、S1、S2”“只有在我验收后才开始新10情景的S3正式实验”，本批止于验收交付。主结论仍须基于5101—5110，旧30情景次要分析单独标注retrospective；不作组件优越性的确认性显著性声明，不预设神经网络或完整代理流程优于简化/UE-only强基线。

## 七、交付位置

- `02_smoke_old_scenarios/acceptance/smoke_results_30.csv`：30条J、序列、预算、hash和LS核对。
- `02_smoke_old_scenarios/acceptance/phase_query_efficiency.csv`：阶段计数及可观测改善。
- 每个运行目录：候选池、筛选、全部请求、唯一查询、完整序列、LS与封存/隔离记录。
- `protocol/frozen_protocol.json`、`freeze_manifest.json`、`code_diff_audit.csv`：协议与差异。
- `01_freeze_and_regression/simple_models/`：固定模型、训练时间与训练边界。
- `4.5_第一批_数值结果.zip`：仅CSV/CSV.GZ，共{len(files)}项，CRC校验通过，不打包代码、模型或文稿。
'''
 (OUT/'G0_G1_G2_CN_report.md').write_text(report,encoding='utf-8')
 (OUT/'missing_data_and_limitations.md').write_text('第一批无缺失：30/30烟测成功、F0回归3/3、自动测试10/10。\n后续未执行：5101—5110主实验330任务、旧30情景retrospective900任务、共同池评分诊断、live UE计时及正式正文/回复。未执行项目不得写成已完成。\n本批全部为已有状态表的隔离回放，真实新增UE求解0；无新增情景。\nF1/F6—F9为已声明必要适配的系统比较；无组件独立因果/神经网络整体优势/确认性显著性结论。\n',encoding='utf-8')
 dump(OUT/'first_batch_progress.json',{'at':now(),'G0':'PASS','G1':'PASS','G2':'PASS','smoke_runs':30,'baseline_bitwise_runs':3,'development_runs_final_version':10,'reproducibility_runs':2,'automatic_tests':10,'new_UE_solves':0,'new_scenarios':0,'formal_main_runs':0,'retrospective_900_runs':0,'original_sources_unchanged':True,'pending':'First-batch user acceptance before S3, per supplied plan','numeric_archive':str(archive)})
 dump(analysis/'validation.json',{'status':'PASS','G0':'PASS','G1':'PASS','G2':'PASS','smoke_runs':30,'tests':10,'at':now()})
 dump(analysis/'analysis_code_addendum.json',{'path':str(Path(__file__)),'sha256':sha(Path(__file__)),'purpose':'after-freeze reporting and tests only; no algorithm changes'})
 print(json.dumps({'status':'PASS','runs':30,'tests':10,'report':str(OUT/'G0_G1_G2_CN_report.md'),'numeric_zip':str(archive)},ensure_ascii=False))

if __name__=='__main__':main()
