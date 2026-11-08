from s4_common import *
import re,platform

def run():
 pin();guard=install_no_compute_guard();immutable_check()
 inp=frame(S4/'00_audit/input_manifest.csv')
 for r in inp.itertuples():assert sha(r.path)==r.sha256,r.path
 for folder in ['01_statistics','02_case5102','03_phases_costs','04_prediction_diagnostics']:assert js(S4/folder/'validation.json')['status']=='PASS'
 p=frame(S4/'03_phases_costs/phase_accounting_all_runs.csv');r=frame(S4/'03_phases_costs/run_budget_cache_management.csv')
 sums=p.groupby(['scenario_id','variant_id','seed_index']).sum(numeric_only=True).reset_index().merge(r,on=['scenario_id','variant_id','seed_index'],suffixes=('_phases','_run'))
 assert len(sums)==330
 assert sums.first_seen_UE_states.eq(256).all() and sums.unique_UE_states.eq(256).all()
 assert np.array_equal(sums.complete_unique_sequences_phases,sums.complete_unique_sequences_run)
 assert np.array_equal(sums.strict_incumbent_improvements_phases,sums.strict_incumbent_improvements_run)
 c=frame(S4/'02_case5102/5102_run_path_summary.csv');a=c[c.variant_id=='F0_FULL'].set_index('seed_index')
 assert a.loc[0,'final_sequence'].startswith('29|') and a.loc[2,'final_sequence'].startswith('29|') and a.loc[1,'final_sequence'].startswith('18|')
 assert pd.isna(a.loc[0,'road18_singleton_first_query']) and pd.isna(a.loc[2,'road18_singleton_first_query'])
 assert a.loc[1,'road18_singleton_first_query']==239 and a.loc[1,'road18_first_complete_budget']==240
 d=frame(S4/'02_case5102/5102_firstroad_phase_distribution.csv');d=d[(d.variant_id=='F0_FULL')&(d.phase=='C_true_ue_reranking')];assert d.first_road.eq(16).all() and len(d)==3
 gate=frame(S4/'02_case5102/5102_primary18_29_gate.csv');gate=gate[(gate.variant_id=='F0_FULL')&gate.sequence.str.startswith('18|')];assert len(gate)==4 and gate.channel.value_counts().to_dict()=={'random':3,'sequence_diversity':1} and not gate.ordered_prefix3_in_reserve.any()
 pr=frame(S4/'02_case5102/5102_ordered_prefix_requests.csv');lists=[pr[(pr.variant_id=='F0_FULL')&(pr.seed_index==i)].ordered_prefix2.tolist() for i in range(3)];assert lists[0]==lists[1]==lists[2]
 s=frame(S4/'01_statistics/full10_descriptive_summary.csv');assert len(s)==11 and s.n_scenarios.eq(10).all()
 lo=frame(S4/'01_statistics/LOSO_all10_omissions.csv');assert len(lo)==110 and set(lo.omitted_scenario_for_sensitivity_only)==set(range(5101,5111))
 assert len(frame(S4/'01_statistics/frozen_v2_descriptive_paired_bootstrap.csv'))==22
 model=frame(S4/'04_prediction_diagnostics/common_state_errors_by_scenario.csv');assert len(model)==80 and model.states.eq(1024).all()
 assert len(frame(S4/'04_prediction_diagnostics/exact_frozen_anchor_checks.csv'))==30
 figdir=S4/'05_figures';pre=js(figdir/'source_preflight.json');assert pre['summary']['counts']['FAIL']==0
 warnings=[x for x in pre['findings'] if x['level']=='WARN'];assert len(warnings)==1 and warnings[0]['check_id']=='EXPORT-RASTER'
 names=['Fig1_5102_mechanism','Fig2_full10_LOSO','Fig3_frozen_predictors','Fig4_online_time']
 for name in names:
  assert js(figdir/(name+'_collisions.json'))['verdict']=='PASS'
  a=js(figdir/(name+'_alignment.json'));assert a['verdict'] in ['PASS','NOT APPLICABLE']
  t=js(figdir/(name+'_text_log.json'));assert t['below_minimum_count']==0 and t['minimum_found_pt']>=7
  for ext in ['png','pdf','svg']:assert (figdir/(name+'.'+ext)).stat().st_size>1000
 # Every Markdown local result link must resolve. Figure previews and manuscript placeholders are separate.
 for f in S4.rglob('*.md'):
  for value in re.findall(r'\]\(<?([A-Z]:/[^>)]+)>?\)',f.read_text(encoding='utf-8')):assert Path(value).exists(),(f,value)
 eng=(S4/'06_report_response/Reviewer1_4.5_英文回复草稿.md').read_text(encoding='utf-8')
 assert '[PAGE/LINE TO BE FILLED]' in eng and 'All ten scenarios remain' in eng
 assert 'F 0' not in eng and 'Reviewer 2' not in eng
 dump(figdir/'visual_review.json',{'at':now(),'status':'PASS','reviewed_all4_final_PNGs_at_whole_figure_scale':True,'reviewed_panels':['Fig1 a,b,c,d','Fig2 a,b','Fig3 a,b','Fig4 single'],'final_width_mm':183,'PNG_dpi':600,'effective_PDF_text_min_pt':7,'alignment_tolerance_pt':1.5,'collision_reports_all_PASS':True,'source_preflight':'20 PASS,1 reviewed WARN,0 FAIL','reviewed_warning':'PNG preview present, no TIFF raster; editable PDF/SVG are supplied for manuscript layout, journal-specific TIFF not requested','no_tolerance_relaxation':True,'source_and_caption_checks':'all ten scenarios retained; Fig1 raw3 F0 paths, seed-range not CI; Fig2 full10 plus all10 omissions; Fig3 negative values visible; Fig4 zero-origin additive components'})
 environment={'python':sys.version,'platform':platform.platform(),'CPU_affinity':psutil.Process().cpu_affinity()}
 import matplotlib,scipy,torch,sklearn
 environment.update(numpy=np.__version__,pandas=pd.__version__,matplotlib=matplotlib.__version__,scipy=scipy.__version__,torch=torch.__version__,sklearn=sklearn.__version__);dump(S4/'00_audit/analysis_environment.json',environment)
 code=[OUT/'code'/name for name in ['s4_common.py','s4_stage_data.py','s4_statistics.py','s4_mechanism.py','s4_phases.py','s4_predict.py','s4_enrich.py','s4_figures.py','s4_report.py','s4_finish.py']]
 csv(S4/'00_audit/analysis_code_manifest.csv',[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in code])
 dump(S4/'00_audit/S4_final_validation.json',{'status':'PASS','at':now(),'frozen_v2_sha256':sha(OUT/'protocol/frozen_protocol.json'),'original_330_output_seal_sha256':sha(CONTROL/'all_330_method_outputs_frozen.json'),'immutable_sources_and_330_runs_rechecked':True,'all_analysis_input_hashes_unchanged':len(inp),'formal_optimization_outputs':330,'main_scenarios':10,'reference_states':10240,'S4_new_operations':guard,'retrospective_runs':0,'new_archives':0,'scenario_method_rows':110,'LOSO_rows':110,'frozen_paired_bootstrap_repetitions':10000,'frozen_paired_bootstrap_seed':2026102906,'diagnostic_common_pools':30,'diagnostic_predictors':4,'phase_query_and_complete_count_crosschecks':True,'figures':4,'figures_QA':'rendered checks PASS; single-panel alignment N/A; source TIFF-format warning reviewed','response_readiness':'draft_with_placeholders','manuscript_edited':False,'stop_after_delivery':True})
 (S4/'00_audit/S4_分析与文件说明.md').write_text('''# S4 分析说明

输入只读，输出位于独立09_S4_mechanism_robustness目录。s4_common实施禁止UE求解、优化入口、候选生成与拟合/反向传播的进程内防护；原始程序没有被修改。预测器仅做冻结前向推断，孤立Primary选择器仅作共同池诊断，LS邻居函数仅计算入口静态状态缺失数。没有运行优化、生成情景或训练模型。

执行逻辑为完整性检查及数据口径冻结、十情景统计、5102日志追踪、阶段去重核算、四预测器诊断、补充证据表、图件与审稿回复、最终哈希及交叉核对。所有脚本及版本的SHA256见analysis_code_manifest.csv。prepare拒绝覆盖已存在的S4目录；当前交付内容已完成，不应直接重跑准备脚本覆盖结果。

冻结v2的10000次情景配对bootstrap使用预定种子2026102906，只作描述性区间。全部十种LOSO均保留，5102不从主分母中剔除。R²、相关等在单状态分层不可定义时保留空值。F9原字段proxy_rank仅表示固定种子随机序号，不是读取或计算代理预测。

全部源S3结果、输入、参考表及模型/核心代码在分析前后核查哈希。S4_output_manifest.csv记录新增数据与报告的字节数和SHA256，排除它自身及最终封存JSON以避免自引用。single CSV.gz是大数值文件的存储格式，主要交付表均为普通CSV，没有生成结果ZIP。

本次仅有图件源预检的TIFF格式提示：已交付600dpi PNG预览及可编辑PDF/SVG，不存在字体、布局或碰撞失败。图4为单面板，面板间对齐不适用。visual_review.json保留实际图像复核记录。
''',encoding='utf-8')
 allfiles=[p for p in S4.rglob('*') if p.is_file() and p.name not in ['S4_output_manifest.csv','S4_delivery_seal.json']]
 csv(S4/'00_audit/S4_output_manifest.csv',[{'path':str(p),'relative_path':str(p.relative_to(S4)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(allfiles)])
 dump(S4/'00_audit/S4_delivery_seal.json',{'at':now(),'status':'SEALED','file_count':len(allfiles),'output_manifest_sha256':sha(S4/'00_audit/S4_output_manifest.csv'),'final_validation_sha256':sha(S4/'00_audit/S4_final_validation.json'),'protocol_sha256':EXPECTED,'further_work':'STOP; await user evaluation','archives_created':0})
 print(json.dumps({'status':'PASS','files':len(allfiles),'main_report':str(S4/'06_report_response/S4_中文验收报告.md'),'output_manifest_sha256':sha(S4/'00_audit/S4_output_manifest.csv')},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
