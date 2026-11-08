"""Close out completed Comment 5.2 evidence without traffic or model calls."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, csv, gzip, hashlib, json, subprocess, sys
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];REPO=OUT.parents[1]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def frame(p):return pd.read_csv(p,float_precision='round_trip')
def write(p,rows):
 d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
 d.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')
def md(d,columns,formats=None):
 formats=formats or {};ans=['| '+' | '.join(columns.values())+' |','|'+'|'.join(['---']*len(columns))+'|']
 for _,r in d.iterrows():
  vals=[]
  for k in columns:
   v=r[k]
   vals.append(formats[k](v) if k in formats else str(v))
  ans.append('| '+' | '.join(vals)+' |')
 return '\n'.join(ans)
def protect_sources():
 records=js(OUT/'source_sha256.json')['files']+js(OUT/'audit/additional_sources_before.json');unique={r['path']:r for r in records};rows=[]
 for r in unique.values():
  p=Path(r['path']);actual=sha(p) if p.exists() else 'MISSING';rows.append(dict(path=str(p),sha256_before=r['sha256'],sha256_after=actual,unchanged=actual==r['sha256'],scientific_cache=p.suffix.lower() in ['.sqlite','.sqlite3','.db']))
 write(OUT/'audit/source_preservation_final.csv',rows)
 result=dict(status='PASS' if all(r['unchanged'] for r in rows) else 'FAIL',files=len(rows),scientific_database_files=sum(r['scientific_cache'] for r in rows),unchanged=sum(r['unchanged'] for r in rows),changed=[r for r in rows if not r['unchanged']])
 dump(OUT/'audit/source_preservation_final.json',result)
 return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify-sources-only',action='store_true');args=ap.parse_args()
 preservation=protect_sources()
 if args.verify_sources_only:
  print(json.dumps(preservation,ensure_ascii=False),flush=True)
  if preservation['status']!='PASS':raise SystemExit(1)
  return
 manifest=js(OUT/'run_manifest.json');unit=js(OUT/'unit_validation.json');analysis=js(OUT/'audit/analysis_validation.json');stats=js(OUT/'audit/final_solver_statistics.json')
 checks=list(unit['checks'])+list(analysis['checks'])
 def check(name,ok,actual,expected):checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
 check('all_old_scientific_sources_and_caches_unchanged',preservation['status']=='PASS',preservation,'all protected SHA unchanged')
 git=subprocess.run(['git','status','--porcelain','-z','--untracked-files=all'],cwd=REPO,capture_output=True,text=True,encoding='utf-8')
 # NUL termination disables Git's C-style quoting of non-ASCII paths. A quoted
 # Chinese instruction filename was incorrectly flagged in the first closeout.
 lines=[line for line in git.stdout.split('\0') if line];outside=[line for line in lines if not(line[:3]=='?? ' and line[3:].replace('\\','/').startswith('revision_R1/comment5_2/'))]
 head=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,capture_output=True,text=True,encoding='utf-8').stdout.strip();oldhead=js(OUT/'audit/git_before.json')['commit']['stdout'].strip()
 dump(OUT/'audit/git_after.json',dict(command='git status --porcelain -z --untracked-files=all',returncode=git.returncode,entries=lines,stderr=git.stderr,HEAD=head,outside_new_directory=outside))
 check('Git_only_new_comment5_2_files',git.returncode==0 and not outside and head==oldhead,dict(HEAD=head,unexpected=outside,new_files=len(lines)),dict(HEAD=oldhead,unexpected=[]))
 visual=js(OUT/'audit/figure_visual_review.json');figchecks=[]
 for r in visual['figures']:
  name=r['name'];png=OUT/'figures'/f'{name}.png';alignment=js(OUT/'figures'/f'{name}.alignment.json');collision=js(OUT/'figures'/f'{name}.collisions.json');text=js(OUT/'audit'/f'{r["short_name"]}_pdf_text.stdout.txt')
  # The matching PNG identifies the actually viewed final rendering.
  good=r['status']=='PASS' and sha(png)==r['png_sha256'] and text['auditable'] and text['below_minimum_count']==0
  check(name+'_actual_visual_and_glyphs',good,dict(PNG_matches=sha(png)==r['png_sha256'],min_pt=text['minimum_found_pt']),dict(PNG_matches=True,min_pt_at_least=5))
  figchecks.append(dict(name=name,alignment=alignment,collision=collision))
 calls=js(OUT/'audit/figure_audit_commands.json')
 check('figure_QA_commands_all_pass',len(calls)==7 and all(r['returncode']==0 for r in calls),[dict(label=r['label'],returncode=r['returncode']) for r in calls],'seven successful source/text/collision checks')
 sourcepre=js(OUT/'audit/source_preflight.stdout.txt')
 check('figure_source_preflight_no_FAIL',sourcepre['summary']['counts']['FAIL']==0,sourcepre['summary']['counts'],'no FAIL; TIFF warning reviewed because PDF and PNG were requested')
 check('no_failed_UE_attempts',not (OUT/'logs/UE_FAILURE.json').exists(),not (OUT/'logs/UE_FAILURE.json').exists(),True)
 attempts=sum(1 for _ in (OUT/'logs/UE_attempts.jsonl').open(encoding='utf-8'))
 meta=frame(OUT/'raw/all_new_UE_state_metadata.csv')
 check('UE_unique_and_attempt_count_reconciled',attempts==len(meta)==stats['unique_valid_states']==6482,dict(attempts=attempts,unique_states=len(meta),dry_states=int((meta.scenario_id==0).sum())),dict(unique_states=6482,dry_states=3))
 # Six demand tables each reuse only the same rho cache context.
 table=frame(OUT/'demand_dp_six_tables.csv');stage=frame(OUT/'stage_metrics_all10.csv');summary=frame(OUT/'demand_sensitivity_all10.csv');policy=frame(OUT/'demand_dp_policy_comparison.csv');agg=frame(OUT/'Table_all10_demand_summary.csv');bottle=frame(OUT/'Table_representative_initial_bottlenecks.csv');residual=frame(OUT/'Table_terminal_residual.csv');legacy=frame(OUT/'Table_original_and_highprecision_units.csv');dry=frame(OUT/'raw/dry_baselines.csv');changes=frame(OUT/'Table_demand_DP_changes.csv')
 missing=set(table.cache_key)-set(meta.cache_key)
 check('all6144_table_states_present_in_isolated_cache',not missing,len(missing),0)
 check('six_DP_sequences_changed_early_prefix_four',int((changes.new_DP_kendall_tau_vs_original_DP<1).sum())==6 and int(changes.new_DP_first3_changed_vs_original_DP.sum())==4,dict(all_sequence_changes=int((changes.new_DP_kendall_tau_vs_original_DP<1).sum()),first3_changes=int(changes.new_DP_first3_changed_vs_original_DP.sum())),dict(all_sequence_changes=6,first3_changes=4))
 # Check raw open-arc completeness against metadata, not method-labelled duplicates.
 count=0;rawsum={}
 with gzip.open(OUT/'raw/all_new_UE_open_arc_flows.csv.gz','rt',encoding='utf-8',newline='') as f:
  for row in csv.DictReader(f):
   count+=1;key=row['cache_key'];rawsum[key]=rawsum.get(key,0.)+float(row['TSTT_contribution_raw'])
 expected=int(meta.open_directed_arcs.sum());maxrel=max(abs(rawsum[r.cache_key]-r.tstt_raw)/r.tstt_raw for r in meta.itertuples(index=False))
 check('complete_raw_flow_export_reconciles_every_new_UE',count==expected and len(rawsum)==len(meta) and maxrel<1e-12,dict(open_arc_rows=count,covered_states=len(rawsum),max_TSTT_relative_difference=maxrel),dict(open_arc_rows=expected,covered_states=len(meta),relative_tolerance=1e-12))
 final=dict(status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',checks_passed=sum(c['status']=='PASS' for c in checks),checks_total=len(checks),checks=checks,completed_client_date='2026-11-02',completed_utc=datetime.now(timezone.utc).isoformat(),output_root=str(OUT),scenario_ids=manifest['scenario_ids'],representatives=manifest['representative_scenarios'],demand_levels=manifest['demand_multipliers'],unique_new_UE_states=len(meta),new_scenario_UE_states=int((meta.scenario_id!=0).sum()),dry_baselines=3,accepted_rho1_archived_states_reused=10240,new_DP_tables=6,new_DP_table_states=6144,stage_rows=660,path_demand_summary_rows=60,conditional_policy_rows=18,bottleneck_method_stage_rows=168,bottleneck_open_arc_rows=10640,all_new_open_arc_rows=count,max_UE_RG=stats['max_RG'],max_independent_RG=stats['max_independent_RG'],max_flow_balance_error=stats['max_flow_balance_error'],UE_failures=0,old_source_hashes_unchanged=preservation['status']=='PASS',protected_source_files=preservation['files'],protected_scientific_database_files=preservation['scientific_database_files'],new_flood_scenarios=0,surrogate_training=0,surrogate_inference=0,original_optimization_reruns=0,Greedy_original_paths_available=False,evidence_sufficiency='SUFFICIENT_FOR_BOUNDED_COMMENT_5_2_RESPONSE; not evidence of realized travel times or operational validity',response_readiness='draft_with_pending_master_merge_locations',figure_visual_review='PASS',figure_preflight_warning='No TIFF export; requested vector PDF and PNG are supplied. Reviewed, not a rendering defect.',limitations=['Demand multipliers are hypothetical external what-if, not calibrated elastic demand','Sioux Falls is hypothetical, with static UE and unbounded BPR, no interstage queue carryover','All 528 positive OD pairs remain served under a connected conditional scenario population','S10 completes only the selected interventions; residual closures and wet-link penalties remain','Greedy original-10 paths unavailable; new30 paths not substituted','No reoptimization of the surrogate-based strategy at lower demand; fixed-path transfer only','Three representative cases only for demand-conditional DP; no new confirmatory inference','Final manuscript and Supplement integration and page/line numbering pending'])
 dump(OUT/'final_validation.json',final)
 status=final['status'];now=datetime.now(timezone(timedelta(hours=8))).isoformat()
 ranges=agg[agg.method=='exact_DP_original_rho1'].sort_values('rho',ascending=False)
 range_table=md(ranges,{'rho':'OD倍率','n_scenarios':'情景数','minimum_ATT_hours':'平均阶段ATT最小(h)','maximum_ATT_hours':'平均阶段ATT最大(h)','maximum_initial_ATT_hours':'初始ATT最大(h)','maximum_terminal_ATT_minutes':'终态ATT最大(min)'},{'rho':lambda v:f'{v:.0%}','n_scenarios':lambda v:str(int(v)),**{k:lambda v:f'{v:.6f}' for k in ['minimum_ATT_hours','maximum_ATT_hours','maximum_initial_ATT_hours','maximum_terminal_ATT_minutes']}})
 dp_table=md(changes,{'scenario_id':'情景','rho':'OD倍率','Jstar_rho':'新J*','new_DP_kendall_tau_vs_original_DP':'新旧DP Kendall τ','new_DP_first3_changed_vs_original_DP':'前三路变化','frozen_full_regret_pct':'原Full regret(%)','frozen_full_delta_mean_trip_minutes':'原Full绝对差(min/次)','frozen_DP_regret_pct':'原DP regret(%)'},{'scenario_id':lambda v:str(int(v)),'rho':lambda v:f'{v:.0%}','Jstar_rho':lambda v:f'{v:.9f}','new_DP_kendall_tau_vs_original_DP':lambda v:f'{v:.6f}','new_DP_first3_changed_vs_original_DP':lambda v:'是' if v else '否','frozen_full_regret_pct':lambda v:f'{v:.6f}','frozen_full_delta_mean_trip_minutes':lambda v:f'{v:.6f}','frozen_DP_regret_pct':lambda v:f'{v:.6f}'})
 dry_table=md(dry,{'rho':'OD倍率','Q':'总需求','tstt_raw':'干燥TSTT原单位','tstt_veh_h':'干燥TSTT(veh·h)','att_minutes':'干燥ATT(min)'},{'rho':lambda v:f'{v:.0%}','Q':lambda v:f'{v:.0f}','tstt_raw':lambda v:f'{v:.9f}','tstt_veh_h':lambda v:f'{v:.9f}','att_minutes':lambda v:f'{v:.9f}'})
 b_table=md(bottle.sort_values(['scenario_id','rho'],ascending=[True,False]),{'scenario_id':'情景','rho':'OD倍率','max_vc':'最大v/c','max_bpr_multiplier':'最大BPR倍率','BPR_congestion_share':'BPR拥堵项占比','top5_TSTT_share':'前5有向弧TSTT占比'},{'scenario_id':lambda v:str(int(v)),'rho':lambda v:f'{v:.0%}','max_vc':lambda v:f'{v:.6f}','max_bpr_multiplier':lambda v:f'{v:.3f}','BPR_congestion_share':lambda v:f'{v:.2%}','top5_TSTT_share':lambda v:f'{v:.2%}'})
 method_table=md(agg.sort_values(['method','rho'],ascending=[True,False]),{'method':'固定方案','rho':'OD倍率','mean_ATT_hours':'跨10情景平均ATT(h)','median_ATT_hours':'中位ATT(h)','minimum_ATT_hours':'最小ATT(h)','maximum_ATT_hours':'最大ATT(h)'},{'rho':lambda v:f'{v:.0%}',**{k:lambda v:f'{v:.6f}' for k in ['mean_ATT_hours','median_ATT_hours','minimum_ATT_hours','maximum_ATT_hours']}})
 low=legacy.original_mean_stage_ATT_hours.min();high=legacy.original_mean_stage_ATT_hours.max();base=dry[dry.rho==1].iloc[0]
 maxr=stage.archive_diagnostic_relative_difference.max();full=policy[policy.method=='full_method'];oldDP=policy[policy.method=='exact_DP_original_rho1']
 report=f'''# Reviewer 1 Comment 5.2补充模拟中文技术报告

**实验验收结论：{status}。{final['checks_passed']}/{final['checks_total']}项检查通过。** 本轮实际完成单位与缓存审计、十情景三档需求路径评价、三代表情景六张1024状态UE+DP表、瓶颈流量、绝对损失、论文图及英文回复草稿。报告日期为2026年11月2日（Asia/Shanghai）。

最重要结论是：审稿人对极端延误的质疑成立，既有结果不是单位乘100造成的假象。需求削减显著降低模型ATT，但没有把所有场景变成可信的现实交通预测；低regret也不能建立现实恢复方案的可操作性。新增资料足以支持有明确模型边界的5.2回复，不能用作现实校准或总体代理优势的证明。

## 1 来源、版本与原文件保护

输出根目录为`{OUT}`。这是本地干净Git基线项目下唯一新增的revision_R1/comment5_2目录。Git main/commit为`{head}`。独立工作目录Vibe1没有有效HEAD且已有未跟踪旧文件，因此没有把它虚称为干净研究仓库。计算权威来源为本地4.2验收记录、4.1冻结高精度solver及原1001—1010输入，而非按公开副本较方便的实现替代。

实际使用的ue_solver.py、path_ue.py、directed_links.csv和od_long.csv的当前SHA与4.2的S0验收清单逐一相符。保留原5e-4 FW表、原路径及1e-9 path solver表，不覆盖旧成本、缓存、模型、Manuscript或4.1—5.1交付。收尾重新哈希的{preservation['files']}项来源全部未变，其中{preservation['scientific_database_files']}个已有数据库文件也未变。原始源清单排除安装依赖、__pycache__和runtime_cache等运行产物目录，未排除科学SQLite缓存；额外原TNTP文件单列追加哈希，未改写初始source清单。详见source_sha256.json、audit/additional_sources_before.json及audit/source_preservation_final.csv。

## 2 单位和加载时段

76条有向弧、528个正需求OD、总需求360600与源TNTP逐值核对通过。源README明确自由流时间单位为0.01小时，OD是原日需求的0.1，可视为近似小时加载量，不是实测小时交通，也不能推出每个恢复阶段恰好持续一小时。容量与需求维持原基准加载时段的共同解释，未更改容量或BPR参数。

`TSTT_veh_h = tstt_raw × 0.01`；`ATT_h = TSTT_veh_h / Q`；分钟再乘60。每档需求单独求干燥分母如下。

{dry_table}

rho=1新基准与原7480225.3449211195原单位基准的相对偏差为{abs(base.tstt_raw-7480225.3449211195)/7480225.3449211195:.12g}，不是为了对齐旧值放宽阈值。所有新求解保持RG≤1e-9和最多20000 outer；最大实际RG为{stats['max_RG']:.12g}，独立AON核验最大为{stats['max_independent_RG']:.12g}。RG是赋值收敛指标，不是TSTT或regret误差的数学界。

原始FW最优序列按原表换算得到平均阶段ATT {low:.6f}—{high:.6f}小时，复现审稿人5.21—40.19小时的量级。4.2高精度成本下为5.199062—40.147665小时，数值精化没有消除极端值。两套rho1 DP均从既有表独立对账通过，未把求解器变化误写成纯阈值效应。

## 3 固定场景与方案、缓存防火墙

保留1001—1010全部原洪水深度、关闭状态、十路恢复集合和full_method/原exact_DP完整顺序。4.1正式Greedy路径属于3001—3030，未找到1001—1010同情景的已验收Greedy方案，故没有借用不同情景或补跑优化伪造对照。

原get_state_hash不含需求倍率且旧normalizer固定，不能直接用于此次削减需求。新增缓存复合上下文包括情景、rho、RG、solver/model SHA、物理状态、道路bit顺序、mask和OD SHA；不同rho的缓存key集合互不相交，内存实际查找测试未发生交叉命中。未打开旧数据库；仅只读旧CSV，新SQLite和Numba缓存均在本输出目录。每个实际新状态检查528个正OD的有向可达性、有限性、独立AON gap及节点流守恒；初始连通检查和“恢复只增加弧”推理均另外保存。

## 4 全十情景需求敏感性

两条固定路径×10情景×3需求倍率×11状态得到660条阶段记录、60条方案汇总。每情景目标只平均S0—S9，S10用于可视化但目标权重为零。下表是原rho1 DP路径固定转移后的绝对指标，不是低需求下重新优化的结果。

{range_table}

全部两方法的描述性汇总如下。统计单位是十个既有情景，未新增独立洪水或开展事后显著性检验。

{method_table}

rho=0.50仍有平均阶段约2.94小时、初态约20.58小时的输出，均完整保留。未裁剪大值，未截断BPR，未改变需求档位。需求倍数为外生hypothetical what-if，不是校准过的elastic-demand UE或实际取消比例。不同rho均使用自身干燥基准，绝对ATT和归一化J同时报告，避免只比较百分比掩盖基准变化。

## 5 三代表情景与六张需求条件DP表

按原始rho1 Jstar从小到大、并列按情景ID选择第1/5/10名，即1006、1003、1008，在任何新需求结果产生前写入run_manifest。每个情景rho=.75和.50各恰有1024个不同mask，共6144状态。阶段C中同rho已算的88个状态安全复用，阶段D实际新增6056个；没有把复用和新增重复计为UE调用。

DP采用V(空集)=C(空集)，非终态加入C(S)，终态不加入，J*=V(E)/10。前驱与最后恢复道路全部保存，另用反向独立DP逐表复算，并验证恢复路径的十项成本和。最优性仅相对固定恢复集合和给定数值状态表。

{dp_table}

六个需求条件最优完整顺序全部与原DP不同，四组的前三条道路发生改变；1008两档需求的前三路相同，但后续顺序仍改变。原full方案相对新DP regret为{full.regret_pct.min():.6f}%—{full.regret_pct.max():.6f}%，绝对平均单次出行差为{full.delta_mean_trip_minutes.min():.6f}—{full.delta_mean_trip_minutes.max():.6f}分钟。原rho1 DP转移后的regret为{oldDP.regret_pct.min():.6f}%—{oldDP.regret_pct.max():.6f}%。这些不利结果说明原顺序并非需求不变的策略。

veh·h差按delta_J×TSTT0_raw(rho)×0.01计算，平均出行分钟差再除以rho×360600并乘60。不能把十个状态均值乘10直接解释成实际十小时累计损失；需要另外定义行动时长和需求加载期。本轮不重训代理、不重新优化原full算法，只评价冻结顺序的transfer robustness与新的DP参照。

## 6 瓶颈诊断及终态残余

三个代表情景重点输出S0、S1、S3、S5、S7、S9、S10。包含168条按方案标签记录的诊断状态和10640条开放有向弧记录，这不是168次额外独立UE。另导出全部{len(meta)}个新缓存状态的{count}条开放弧原始流量，供复核流量×时间、v/c及BPR构成。

{b_table}

1008原需求初态最大v/c约14.428，最大BPR倍率约6501.05，拥堵项占TSTT约99.80%；原需求下前五条有向弧贡献约85.93%的TSTT。50%需求下最大v/c仍约7.214，最大BPR倍率约407.25。原BPR没有物理流量硬上限，因此大量固定OD仍被分配到少量瓶颈。流量/容量是同一基准加载期下的比值；不能把数学允许的超容量稳态流量等同于现实可实现吞吐量。

新诊断流量与归档rho1成本由两次冷启动求解得到，最大相对TSTT差为{maxr:.12g}，在预先声明核对阈值内，并非逐位相等。rho1主要阶段成本优先保留4.2归档值，流量单独标记来源。闭合弧不计v/c和开放弧统计。

终态仍有{int(residual.residual_closed_roads.min())}—{int(residual.residual_closed_roads.max())}条原集合外关闭道路，且仍存在未恢复的可通行涉水道路。原需求终态ATT为{residual[residual.rho==1].terminal_ATT_minutes.min():.6f}—{residual[residual.rho==1].terminal_ATT_minutes.max():.6f}分钟。S10是选定十项干预完成，不是全网络恢复。逐情景残余关闭ID、涉水道路数和终态绝对值见Table_terminal_residual.csv。

## 7 论文图与证据文件

figures/Figure_R1_5_2_trajectory.pdf/png/svg展示全部十一阶段与三档需求，绝对ATT使用对数轴保留极大值；bottleneck图展示最大v/c和前五弧TSTT占比；demand_policy图展示固定方案相对新DP的绝对分钟差。英文caption在figures/Figure_captions_EN.md。三张图均完成最终PNG逐图实际查看、1.5pt面板对齐检查、PDF字体检查（最小7pt）和碰撞审计（均0 FAIL/0 WARN）。源预检只有“未生成TIFF”提示；任务要求PDF与PNG，另供SVG，故该提示不构成阻断。

主要数值为stage_metrics_all10.csv、demand_sensitivity_all10.csv、demand_dp_six_tables.csv、demand_dp_policy_comparison.csv、bottleneck_links.csv。全部CSV保留17位有效数。完整开放弧流量另存raw/all_new_UE_open_arc_flows.csv.gz。全部输出均为新增；没有ZIP打包。

## 8 负面结果、局限与回复充分性

新增结果支持把论文定位为合成严重洪水下的静态网络压力测试。Sioux Falls网络是示意性benchmark；固定需求、无界BPR、无出发/目的地响应、无跨阶段排队、固定洪水、瞬时恢复仍是限制。需求削减只作外生敏感性，不证明真实交通行为、洪水安全或实际灾害恢复策略有效。已有连通条件下所有OD均可达，并不覆盖断网和未服务需求，这属于后续5.3范围。

**Comment5.2已经具备回应“单位、绝对量、瓶颈和需求敏感性”的补充证据。** 接受这些边界并收缩操作性主张，才能形成诚实回复；不能把新结果包装成代理总体优势或现实可操作性的证明。正式正文/Supplement插入、整篇Word合并及最终页行号仍待后续完成，本轮仅交付英文草稿及建议位置。

## 9 审计程序修正记录

首轮收尾为133/134通过，唯一未通过项是Git新增文件归属检查。Git默认把中文文件名输出为带C式转义的引号字符串，审计程序误把本目录中的中文指令副本判为目录外文件；原文件哈希与全部数值检查当时均已通过。已改用Git原生NUL分隔状态输出处理路径，未修改Git配置、实验数据、参数或容差。首轮FAIL报告与原状态输出保留在audit/initial_closeout_parser_failure/，不静默抹去该记录。

## 10 实际执行与重现

实际UE运行使用`E:/ProgramData/Anaconda3/envs/rag_demo/python.exe -B scripts/experiment52.py --phase A`，依次执行B、C、D、bottlenecks；随后执行export_all_flows.py（零UE）、analyze52.py、plot52.py和audit_figures.py。UE与绘图复用已存在的Python3.11科学环境；桌面捆绑Python3.12不含numba/matplotlib，未安装或替换旧环境。所有JIT和绘图配置缓存隔离到本目录。

单条重现命令为`powershell -ExecutionPolicy Bypass -File "{OUT / 'run_all.ps1'}"`。该命令先核对源哈希，复用本实验缓存可恢复，不修改旧缓存。执行记录、完整UE逐调用元数据、DP独立复算、图形QA和文件哈希位于logs/、audit/及output_manifest.csv。

总新增有效UE为{len(meta)}，其中3个干燥网络状态、{final['new_scenario_UE_states']}个场景状态；{len(meta)}/{len(meta)}收敛且有限、528正OD可达，失败0。无新洪水、无训练、无代理推断、无原搜索补跑。最终状态：**{status}**。
'''
 (OUT/'Comment5_2_results_report_CN.md').write_text(report,encoding='utf-8')
 english_ranges=md(ranges,{'rho':'OD multiplier','minimum_ATT_hours':'Min mean-stage ATT (h)','maximum_ATT_hours':'Max mean-stage ATT (h)','maximum_initial_ATT_hours':'Max initial ATT (h)'},{'rho':lambda v:f'{v:.0%}',**{k:lambda v:f'{v:.3f}' for k in ['minimum_ATT_hours','maximum_ATT_hours','maximum_initial_ATT_hours']}})
 reply=f'''# Reviewer 1 Comment 5.2

## Comment

> The experiments imply extreme delays that require interpretation. Table S6 reports conditional optimum objectives from 24.093950 to 192.756052. Under Eq. 7, these imply mean stage TSTT between about 25.1 and 193.8 times the dry baseline. Using the paper's stated baseline of 74,802.2534 vehicle-hours and total OD demand of 360,600, the corresponding average trip durations are approximately (1 + J*) × 74,802.2534 / 360,600 = 5.21 to 40.19 hours. This is an inference from the stated normalization and units, not an independent observation of real flood traffic.
>
> These values make physical interpretation essential. Fixed demand and an unbounded BPR congestion function can force all trips through severe bottlenecks, with no cancellations, destination changes, departure-time shifts, or queues carried between stages. The results may therefore describe extreme static stress tests rather than plausible realized traffic. Confirm the units and assignment period, report absolute stage-level outcomes, and test demand adaptation or more realistic bottleneck behavior. Low regret against an extreme model optimum does not establish an operationally credible recovery plan.

## Reply

We agree. The large travel times are substantive outputs of the static stress-test model, rather than a time-unit conversion error, and low conditional regret does not establish an operationally credible plan. We completed the following supplementary calculations without changing the frozen floods, selected roads, restoration sequences, BPR parameters or earlier results. Corresponding manuscript additions are prepared, with final integration locations still to be confirmed.

### 1 Units and demand period

We checked the original TNTP network and OD files against the accepted processed inputs. There are 76 directed arcs, 528 positive OD pairs and total demand 360,600. The source documentation specifies 0.01 hours per raw time unit. Accordingly, raw TSTT is multiplied by 0.01 once to obtain vehicle-hours, and ATT is that total divided by demand. The newly solved full-demand dry baseline is {base.tstt_veh_h:.8f} vehicle-hours, giving ATT {base.att_minutes:.8f} minutes; its relative difference from the archived raw baseline is {abs(base.tstt_raw-7480225.3449211195)/7480225.3449211195:.3g}. The source demand is a rescaling of daily benchmark flows that may be interpreted as an approximate hourly loading, not observed hourly traffic. It does not specify that each restoration action lasts one hour. We therefore do not interpret ten model stages as ten elapsed hours.

### 2 Absolute stage outcomes and bottlenecks

The original table reproduces the reviewer's approximately 5.21 to 40.19 hours for mean-stage ATT. Using the already accepted higher-precision costs gives 5.199 to 40.148 hours along the same original DP sequences. Thus numerical refinement does not remove the extreme magnitudes. We provide TSTT, ATT and residual disruption for every state S0 through S10 of both frozen paths, while the optimization objective includes only S0 through S9. Stage S10 has zero objective weight and completes only the ten selected interventions, not the entire network.

Independent flow diagnostics show the model mechanism. In scenario 1008 at S0, maximum open-arc v/c is 14.428, the largest BPR time multiplier is 6501.05, and the congestion term accounts for approximately 99.80% of TSTT. The five largest directed-arc contributions account for approximately 85.93%. At 50% demand, maximum v/c is still 7.214. The BPR function permits flows above nominal capacity without a hard throughput or queue-storage constraint. These mathematical static assignments must not be interpreted as physically achievable steady traffic under a real flood. Closed arcs are excluded from the v/c statistics.

### 3 Prespecified exogenous demand sensitivity

We scaled every positive OD uniformly to 100%, 75% and 50% of its original value, retaining the same network, flood, capacity, recovery set and frozen sequences. A separate dry-network UE was solved for each demand level, giving dry ATT values of 12.4463, 8.1075 and 6.2249 minutes. New cache keys include demand, tolerance, scenario and immutable solver/state identities; no old cache database was reused.

The following ranges summarize the original full-demand DP sequence transferred unchanged to each demand level, over all ten existing scenarios.

{english_ranges}

Demand reduction substantially lowers absolute modeled trip times, but even the 50% condition has mean-stage ATT up to 2.938 hours and initial ATT up to 20.575 hours. These are hypothetical external demand reductions, not an estimated cancellation rate or a calibrated elastic-demand equilibrium. The largest values remain in the raw data and figures.

### 4 New demand-conditional DP references

Before the new-demand results were available, we selected scenarios 1006, 1003 and 1008 as ranks 1, 5 and 10 of the original full-demand J*. For each, we computed all 1,024 subset costs at both reduced-demand levels, using RG ≤ 1e-9 and the same zero-terminal-weight recurrence. All six full optimal orders changed; the first three roads changed in four of six comparisons. Relative to these new references, the frozen full-method path has regret {full.regret_pct.min():.4f}% to {full.regret_pct.max():.4f}% and a mean trip-time excess of {full.delta_mean_trip_minutes.min():.4f} to {full.delta_mean_trip_minutes.max():.4f} minutes. Even the original full-demand DP path is no longer generally optimal, with transferred regret {oldDP.regret_pct.min():.4f}% to {oldDP.regret_pct.max():.4f}%. All absolute vehicle-hour differences are supplied alongside regret.

These are post-hoc transfer and sensitivity diagnostics. We did not retrain the surrogate, reuse its full-demand predictions as calibrated lower-demand estimates, or reoptimize the original search strategy at lower demand. Existing original-ten-scenario Greedy paths were not available, and results from different scenarios were not substituted.

### 5 Interpretation

The additional evidence supports a narrower interpretation as a conditional algorithmic stress test on a hypothetical network. Static fixed-demand UE with unbounded BPR, no endogenous departure or destination response, and no interstage queue carryover does not establish realized flood travel times or operational recovery feasibility. We withdraw any implication that small relative regret alone provides such validation. The new experiments are not new independent flood samples or confirmatory tests of surrogate superiority.

## Action

Completed evidence consists of the ten-scenario absolute stage outputs, three-level demand sensitivity, six complete demand-specific UE tables with independently checked DP solutions, open-arc bottleneck diagnostics, three figures and their English captions. The prepared revisions target Methods (units, loading-period interpretation and demand sensitivity), Results (absolute trajectories and conditional policy changes), and Discussion/Limitations (static stress-test interpretation). Detailed state and flow tables are intended for the Supplement or source-data archive. Final manuscript table/figure numbers and page/line references remain pending master-file integration.

Suggested concise Results/Discussion replacement:

*The extreme delays are outputs of the static fixed-demand benchmark, not observed flood traffic. Along the frozen full-demand DP sequences, mean-stage ATT spans 5.199 to 40.148 hours at full demand and 0.847 to 2.938 hours at half demand. Full-demand optimal orders change under reduced demand in all six prespecified case/level comparisons. The results therefore quantify conditional search quality and sensitivity within a severe static stress test; low regret does not validate the physical feasibility or operational value of the resulting plan.*

## Supporting Evidence

- [Unit audit](unit_audit.md), [unit validation](unit_validation.json) and [prospective run manifest](run_manifest.json).
- [All 660 stage records](stage_metrics_all10.csv) and [all 60 fixed-path/demand summaries](demand_sensitivity_all10.csv).
- [Six complete UE tables with DP values and predecessors](demand_dp_six_tables.csv), [policy comparisons and absolute gaps](demand_dp_policy_comparison.csv), and [independent DP validation](audit/independent_DP_validation.csv).
- [Open-arc bottleneck records](bottleneck_links.csv), [complete new-state flow export](raw/all_new_UE_open_arc_flows.csv.gz), and [terminal residual disruption](Table_terminal_residual.csv).
- [ATT trajectories](figures/Figure_R1_5_2_trajectory.pdf), [bottleneck figure](figures/Figure_R1_5_2_bottleneck.pdf), [absolute policy-gap figure](figures/Figure_R1_5_2_demand_policy.pdf) and [English captions](figures/Figure_captions_EN.md). Each figure also has PNG and editable SVG exports.
- [Final numerical and preservation validation](final_validation.json). Status {status}; {len(meta)} valid new UE states, no failed solves. No previous result file or scientific cache was modified.

Readiness is a complete comment-level evidence draft with final manuscript integration locations pending. It is not a claim that the entire revision has already been merged or rendered.
'''
 (OUT/'Response_R1_Comment5_2_draft_EN.md').write_text(reply,encoding='utf-8')
 qa=f'''# Comment5.2最终验收

**{status}**，{final['checks_passed']}/{final['checks_total']}。单位阶段A为{unit['checks_passed']}/{unit['checks_total']}；独立数值分析为{analysis['checks_passed']}/{analysis['checks_total']}。

- 10个冻结场景、2条原方案、3档固定需求、660条阶段记录、60条路径汇总齐全。
- 3个代表场景按原Jstar第1/5/10名事前锁定；6张表各1024独立mask，合计6144，逐表独立DP和前驱复核通过。
- 共{len(meta)}个新增有效UE状态，含3个干燥状态；全部RG≤1e-9、有限、528正OD可达，流守恒最大误差{stats['max_flow_balance_error']:.12g}，失败0。
- 三档干燥分母和需求namespace隔离，旧SQLite未打开。旧FW与4.2高精度表分别对账，原路径和输入未变。
- 原文件{preservation['files']}项SHA全部未变，含{preservation['scientific_database_files']}个科学数据库；Git仅新增revision_R1/comment5_2文件，HEAD不变。
- S0—S9计目标，S10仅显示且权重0；输出绝对veh·h、ATT、v/c、BPR倍率及残余损失。
- 原始开放弧流量共{count}行，与全部新状态TSTT逐一独立求和吻合；单元与绝对量公式核对通过。
- 三张论文图逐图查看；所有面板对齐、字体和碰撞检查通过。源预检“无TIFF”提示已审查，按用户要求供PDF/PNG及SVG。
- 未重训、未代理推断、未生成新洪水、未重新跑原优化；无旧结果覆盖。

非失败限制：未找到原1001—1010 Greedy路径，因此按协议“如有”条件不纳入；需求倍率未校准；仅3代表情景做新DP；现实可操作性尚未验证。完整英文Response和建议插入文字已准备，正式Word/Supplement合并及页行仍待后续。

证据充分性：Comment5.2在单位、绝对量、瓶颈与需求what-if方面已具备有边界的回复证据；不能据此声称现实交通校准或代理优势。未通过自动验收项：{[c['check'] for c in checks if c['status']=='FAIL']}。
'''
 (OUT/'QA_validation.md').write_text(qa,encoding='utf-8')
 index=['# Comment5.2结果文件索引','',f'最终验收 {status}。所有新增材料位于本目录，不生成ZIP。','', '## 先看报告']
 names=['Comment5_2_results_report_CN.md','QA_validation.md','final_validation.json','Response_R1_Comment5_2_draft_EN.md','unit_audit.md','run_manifest.json','stage_metrics_all10.csv','demand_sensitivity_all10.csv','demand_dp_six_tables.csv','demand_dp_policy_comparison.csv','bottleneck_links.csv','Table_all10_demand_summary.csv','Table_demand_DP_changes.csv','Table_terminal_residual.csv','Table_representative_initial_bottlenecks.csv','figures/Figure_R1_5_2_trajectory.pdf','figures/Figure_R1_5_2_bottleneck.pdf','figures/Figure_R1_5_2_demand_policy.pdf','figures/Figure_captions_EN.md','raw/all_new_UE_open_arc_flows.csv.gz','raw/all_new_UE_state_metadata.csv','source_sha256.json','audit/source_preservation_final.csv','run_all.ps1']
 for name in names:index.append('- ['+name+']('+name+')')
 index+=['','raw/含3个干燥基准、逐表1024状态与DP JSON、新DP阶段曲线、瓶颈分解和全量开放弧流量。cache/仅含本实验新增缓存。audit/含版本、来源、自动验收与图形QA，logs/含每次新UE求解原始记录。scripts/和tests/保留全部新增程序与数学/缓存测试。','', '新DP参考不用于修改旧搜索结果。正文与Supplement整合不在本批执行。']
 (OUT/'结果文件索引.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
 # Final self-contained output manifest, excluding only itself and transient lock files.
 files=[]
 for p in sorted(OUT.rglob('*')):
  if p.is_file() and p.name!='output_manifest.csv' and not p.name.startswith('~$'):files.append(dict(relative_path=str(p.relative_to(OUT)),size_bytes=p.stat().st_size,sha256=sha(p)))
 write(OUT/'output_manifest.csv',files)
 print(json.dumps({k:final[k] for k in ['status','checks_passed','checks_total','unique_new_UE_states','new_DP_tables','new_DP_table_states','UE_failures','old_source_hashes_unchanged','evidence_sufficiency']},ensure_ascii=False),flush=True)
 if status!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
