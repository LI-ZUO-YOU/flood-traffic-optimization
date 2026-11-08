"""Post-seal full reference, requested descriptive checks, Chinese S3 report and CSV archive."""
from s3_prepare import *
import zipfile,math

def verify_task(path):
 m=js(path/'pre_reference_manifest.json')
 for name,e in m['files'].items():assert sha(path/name)==e['sha256'],str(path/name)
 return m

def verify_global_seal():
 f=CONTROL/'all_330_method_outputs_frozen.json';seal=js(f);assert seal['task_records']==330
 for name,h in seal['files'].items():assert sha(name)==h;verify_task(Path(name).parent)
 return sha(f)

def independent_backward(costs,roads):
 v=np.full(1024,np.inf);v[1023]=0.0;nextroad={}
 for mask in range(1022,-1,-1):
  child_value,road,child=min((v[mask|(1<<i)],r,mask|(1<<i)) for i,r in enumerate(roads) if not mask&(1<<i))
  v[mask]=costs[mask]+child_value;nextroad[mask]=road
 seq=[];mask=0
 while mask!=1023:
  road=nextroad[mask];seq.append(road);mask|=1<<roads.index(road)
 return float(v[0]/10),tuple(seq)

def references(net):
 seal_sha=verify_global_seal();require_new_output(REF)
 for i,sid in enumerate(range(5101,5111)):
  ph,roads,_=public_scenario(sid);folder=REF/f'scenario_{sid}';folder.mkdir();rows=[];errors=[];start=time.perf_counter()
  for mask in range(1024):
   try:rows.append(net.solve(ph,roads,mask,1e-9))
   except Exception as e:errors.append({'scenario_id':sid,'subset_mask':mask,'error':repr(e),'target':1e-9})
   if (mask+1)%128==0:dump(CONTROL/'progress.json',{'stage':'reference','completed_scenarios':i,'scenario':sid,'states_attempted':mask+1,'converged_states':len(rows),'failed_states':len(errors),'at':now()})
  csv(folder/'all_states_RG1e-9.csv.gz',rows);csv(folder/'failed_states.csv',errors if errors else pd.DataFrame(columns=['scenario_id','subset_mask','error','target']))
  valid=len(rows)==1024
  if valid:
   costs={int(r['subset_mask']):r['loss'] for r in rows};value,seq=E.exact_dp(costs,roads);back,bseq=independent_backward(costs,roads)
   rebuilt=float(np.mean([costs[m] for m in E.masks(seq,roads)]));rebuilt_b=float(np.mean([costs[m] for m in E.masks(bseq,roads)]))
   assert abs(value-back)<=1e-10*max(1,abs(value));assert abs(value-rebuilt)<=1e-12*max(1,abs(value));assert abs(value-rebuilt_b)<=1e-10*max(1,abs(value))
   assert all(r['converged'] and r['relative_gap']<=1e-9 for r in rows)
   dump(folder/'conditional_DP.json',{'status':'PASS','scenario_id':sid,'roads':roads,'objective':value,'sequence':seq,'backward_objective':back,'backward_sequence':bseq,'reconstructed_J':rebuilt,'two_independent_recurrences_verified':True,'conditional_numerical_reference':True,'RG_is_not_a_TSTT_error_bound':True,'kappa_empirical':KAPPA,'all_330_outputs_seal_sha256':seal_sha})
  dump(folder/'validation.json',{'status':'PASS' if valid else 'INCOMPLETE','states':len(rows),'failed_masks':[r['subset_mask'] for r in errors],'wall_seconds':time.perf_counter()-start,'UE_kernel_seconds':sum(r['solver_seconds'] for r in rows),'fresh_independent_reference_solves':len(rows),'started_after_all_method_outputs_frozen':True,'all_330_outputs_seal_sha256':seal_sha,'at':now()})
  print(json.dumps({'event':'reference_complete','scenario_id':sid,'states':len(rows),'failed':len(errors),'at':now()}),flush=True)

def analyze_and_deliver():
 core_check();verify_sources();seal_sha=verify_global_seal();require_new_output(DELIVERY)
 index=frame(CONTROL/'task_index.csv');assert len(index)==330;records=[];missing=[];phases=[];pairs=[];stage_quality=[];fallbacks=[];source_attribution=[]
 reference_rows=[]
 for sid in range(5101,5111):
  v=js(REF/f'scenario_{sid}/validation.json');refpath=REF/f'scenario_{sid}/conditional_DP.json';d=js(refpath) if refpath.exists() else None
  reference_rows.append({'scenario_id':sid,'reference_status':v['status'],'states':v['states'],'reference_J':d['objective'] if d else None,'reference_sequence':'|'.join(map(str,d['sequence'])) if d else None,'wall_seconds':v['wall_seconds'],'UE_kernel_seconds':v['UE_kernel_seconds']})
 for item in index.to_dict('records'):
  path=Path(item['path']);verify_task(path);val=js(path/'validation.json');sid=int(item['scenario_id']);variant=item['variant_id'];rep=int(item['seed_index']);ref=next(x for x in reference_rows if x['scenario_id']==sid)
  if val['status']!='PASS' or not (path/'result.json').exists():
   missing.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,'reason':'optimization task failed','details':str(val['failure'])});continue
  r=js(path/'result.json');timing=js(path/'timing.json');req=frame(path/'request_ledger.csv.gz');unq=frame(path/'logical_query_ledger.csv.gz');complete=frame(path/'complete_sequence_history.csv.gz');ls=frame(path/'local_search_calls.csv')
  assert r['backend']=='fresh_live_UE' and r['fresh_cache'] and r['actual_queries']<=256 and r['live_UE_calls']==r['actual_queries']
  assert len(unq)==unq.subset_mask.nunique()==r['actual_queries'] and int(unq.iloc[0].subset_mask)==0
  seen=set()
  for x in req.itertuples():assert bool(x.cache_hit)==(x.mask in seen);seen.add(x.mask)
  assert len(seen)==r['actual_queries'];costs=dict(zip(unq.subset_mask,unq.loss));J=float(np.mean([costs[m] for m in E.masks(r['best_sequence'],r['roads'])]));assert J.hex()==float(r['best_objective']).hex()
  for x in complete.itertuples():assert float(np.mean([costs[m] for m in E.masks(E.original.parse_sequence(x.sequence),r['roads'])])).hex()==float(x.complete_J).hex()
  assert abs(req.solver_seconds.sum()-r['UE_kernel_seconds'])<=1e-8*max(1,r['UE_kernel_seconds'])
  phase=frame(path/'phase_query_efficiency.csv');assert phase.unique_queries_phase.sum()==r['actual_queries']
  for x in phase.to_dict('records'):phases.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,**x,'backend':'fresh_live_UE'})
  pool=None
  if variant!='Greedy-ILS':
   pool=frame(path/'candidate_pool.csv.gz');sc=frame(path/'screened_candidates.csv.gz');primary=sc[sc.screening_tier=='primary_shortlist']
   assert len(pool)==pool.sequence.nunique()==pool.candidate_id.nunique()==30000 and len(primary)==primary.candidate_id.nunique()==60
   if variant=='F3_NO_DISAG':assert primary.channel.value_counts().to_dict()=={'proxy_top':25,'sequence_diversity':15,'heuristic':10,'random':10}
   if variant=='F1_NO_RESERVE':assert not (sc.screening_tier=='structural_reserve').any() and len(sc)==30000
   if variant=='F9_NO_SURROGATE':assert not r['model_file_reads'] and not r['surrogate_loaded'] and r['surrogate_inference_calls']==0 and r['proxy_dp_policies']==0 and pool.proxy_objective_mean.isna().all()
   for x in frame(path/'source_fallback_records.csv').to_dict('records'):fallbacks.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,**x})
   seq='|'.join(map(str,r['best_sequence']));hit=pool[pool.sequence==seq]
   source_attribution.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,'sequence':seq,'in_pool':not hit.empty,'primary_source':hit.iloc[0].primary_source if not hit.empty else 'outside_pool_local_search','source_tags':hit.iloc[0].source_tags if not hit.empty else 'local_search','interpretation':'observed membership, not causal attribution'})
  reference_J=ref['reference_J'];regret=None if reference_J is None else 100*(J-reference_J)/reference_J
  if reference_J is None:missing.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,'reason':'incomplete reference; raw J retained','details':ref['reference_status']})
  if reference_J is not None:
   rt=frame(REF/f'scenario_{sid}/all_states_RG1e-9.csv.gz').set_index('subset_mask')
   for x in unq.itertuples():assert float(x.loss).hex()==float(rt.loc[x.subset_mask,'loss']).hex(),'Independent live/reference state mismatch'
  row={'scenario_id':sid,'variant_id':variant,'seed_index':rep,'J':J,'J_hex':J.hex(),'sequence':'|'.join(map(str,r['best_sequence'])),'reference_J':reference_J,'regret_pct':regret,'equivalent_to_DP':None if reference_J is None else abs(J-reference_J)<=KAPPA*max(1,abs(reference_J)),'unique_UE_queries':r['actual_queries'],'logical_requests':r['logical_requests'],'candidate_order_sha256':r.get('candidate_order_sha256'),'candidate_count':r.get('candidate_count',0),'primary_count':r.get('primary_count',0),'reserve_count':r.get('reserve_count',0),'prefix4_coverage':r.get('prefix4_coverage'),'fresh_online_seconds':r['fresh_online_seconds'],'candidate_prepare_seconds':r['candidate_prepare_seconds'],'surrogate_inference_seconds':r['surrogate_inference_seconds'],'UE_network_call_seconds':r['UE_network_call_seconds'],'UE_kernel_seconds':r['UE_kernel_seconds'],'LS_non_UE_seconds':r['LS_non_UE_seconds'],'search_other_bookkeeping_seconds':r['search_other_bookkeeping_seconds'],'initial_input_load_seconds':r['initial_input_load_seconds'],'model_load_and_development_inference_warmup_seconds':r['model_load_and_development_inference_warmup_seconds'],'peak_RSS_bytes':r['peak_RSS_bytes'],'backend':'fresh_live_UE','status':'PASS'}
  records.append(row)
  before=ls.iloc[0].best_J_before if len(ls) else np.nan;after=ls.iloc[0].best_J_after if len(ls) else np.nan
  stage_quality.append({'scenario_id':sid,'variant_id':variant,'seed_index':rep,'first_LS_before_J':before,'first_LS_after_J':after,'first_LS_before_regret_pct':100*(before-reference_J)/reference_J if reference_J is not None and pd.notna(before) else None,'first_LS_after_regret_pct':100*(after-reference_J)/reference_J if reference_J is not None and pd.notna(after) else None,'first_LS_improvement_J':before-after,'LS_total_observed_improvement_J':float(ls.improvement.sum()) if len(ls) else 0.0,'LS_calls':len(ls),'final_J':J,'interpretation':'observed complete-incumbent changes; not causal state contributions'})
 # Check all main-run pool/primary sharing commitments after every output has been frozen.
 for sid in range(5101,5111):
  for rep in range(3):
   base=RUNS/f'scenario_{sid}';f0=base/f'F0_FULL/seed_{rep:02d}'
   if js(f0/'validation.json')['status']!='PASS':continue
   for variant in ['F1_NO_RESERVE','F3_NO_DISAG']:
    other=base/f'{variant}/seed_{rep:02d}'
    if js(other/'validation.json')['status']=='PASS':assert sha(f0/'candidate_pool.csv.gz')==sha(other/'candidate_pool.csv.gz')
   f1=base/f'F1_NO_RESERVE/seed_{rep:02d}'
   if js(f1/'validation.json')['status']=='PASS':
    a=frame(f0/'screened_candidates.csv.gz');b=frame(f1/'screened_candidates.csv.gz');assert a[a.screening_tier=='primary_shortlist'].candidate_id.tolist()==b[b.screening_tier=='primary_shortlist'].candidate_id.tolist()
 df=pd.DataFrame(records);csv(DELIVERY/'all_330_task_status.csv',index);csv(DELIVERY/'all_successful_runs_regret_and_cost.csv',df);csv(DELIVERY/'reference_10_scenarios.csv',reference_rows);csv(DELIVERY/'phase_UE_query_efficiency.csv',phases);csv(DELIVERY/'first_LS_quality_and_improvement.csv',stage_quality);csv(DELIVERY/'source_fallback_records.csv',fallbacks);csv(DELIVERY/'selected_candidate_source_attribution.csv',source_attribution)
 for x in records:
  f0=next((b for b in records if b['scenario_id']==x['scenario_id'] and b['seed_index']==x['seed_index'] and b['variant_id']=='F0_FULL'),None)
  if f0 and x['regret_pct'] is not None and f0['regret_pct'] is not None:pairs.append({'scenario_id':x['scenario_id'],'variant_id':x['variant_id'],'seed_index':x['seed_index'],'J_variant':x['J'],'J_F0':f0['J'],'regret_variant_pct':x['regret_pct'],'regret_F0_pct':f0['regret_pct'],'delta_regret_percentage_points_variant_minus_F0':x['regret_pct']-f0['regret_pct']})
 csv(DELIVERY/'paired_differences_vs_F0.csv',pairs)
 means=[]
 for (sid,v),g in df.groupby(['scenario_id','variant_id']):
  means.append({'scenario_id':sid,'variant_id':v,'n_seeds':len(g),'mean_J':g.J.mean(),'mean_regret_pct':g.regret_pct.mean(),'mean_unique_UE_queries':g.unique_UE_queries.mean(),'mean_fresh_online_seconds':g.fresh_online_seconds.mean(),'mean_candidate_prepare_seconds':g.candidate_prepare_seconds.mean(),'mean_UE_network_call_seconds':g.UE_network_call_seconds.mean(),'equivalence_hits':int(g.equivalent_to_DP.fillna(False).sum())})
 mean=pd.DataFrame(means);csv(DELIVERY/'scenario_seed_means.csv',mean);summary=[]
 paired=pd.DataFrame(pairs)
 for variant in VARIANTS+['Greedy-ILS']:
  g=mean[(mean.variant_id==variant)&(mean.n_seeds==3)];valid=g[g.mean_regret_pct.notna()];pp=paired[paired.variant_id==variant].groupby('scenario_id').agg(delta=('delta_regret_percentage_points_variant_minus_F0','mean'),n=('seed_index','count'));pp=pp[pp.n==3]
  wins=ties=losses=0
  for sid,pair in pp.iterrows():
   a=next(x for x in means if x['scenario_id']==sid and x['variant_id']==variant);b=next(x for x in means if x['scenario_id']==sid and x['variant_id']=='F0_FULL');ref=next(x['reference_J'] for x in reference_rows if x['scenario_id']==sid);d=a['mean_J']-b['mean_J'];tol=KAPPA*max(1,abs(ref))
   if abs(d)<=tol:ties+=1
   elif d<0:wins+=1
   else:losses+=1
  summary.append({'variant_id':variant,'n_scenarios_all3seeds':len(g),'n_scenarios_exact_regret':len(valid),'mean_scenario_regret_pct':valid.mean_regret_pct.mean(),'median_scenario_regret_pct':valid.mean_regret_pct.median(),'P90_scenario_regret_pct':valid.mean_regret_pct.quantile(.9),'max_scenario_regret_pct':valid.mean_regret_pct.max(),'mean_fresh_online_seconds':g.mean_fresh_online_seconds.mean(),'mean_candidate_prepare_seconds':g.mean_candidate_prepare_seconds.mean(),'mean_unique_UE_queries':g.mean_unique_UE_queries.mean(),'mean_paired_delta_regret_pp_vs_F0':pp.delta.mean(),'paired_scenarios_all3seeds':len(pp),'variant_wins_vs_F0':wins,'equivalent_ties_vs_F0':ties,'variant_losses_vs_F0':losses})
 csv(DELIVERY/'descriptive_summary.csv',summary);csv(DELIVERY/'missing_data.csv',missing if missing else pd.DataFrame(columns=['scenario_id','variant_id','seed_index','reason','details']))
 # No new training. Preserve original measured cheap-model fitting components with provenance.
 training=frame(OUT/'01_freeze_and_regression/simple_models/training_record.csv');training['cost_provenance']='first-batch fixed fit measurement; not retrained in S3';csv(DELIVERY/'fixed_surrogate_training_costs.csv',training)
 csv(DELIVERY/'cost_accounting_schema.csv',[{'field':'fresh_online_seconds','meaning':'real new UE calls + candidate preparation + search bookkeeping; excludes disk exports/input loading/model warmup/training'},{'field':'candidate_prepare_seconds','meaning':'includes surrogate_inference_seconds; do not add nested inference twice'},{'field':'UE_network_call_seconds','meaning':'includes solver kernel, state setup and checks; UE_kernel_seconds nested'},{'field':'LS_non_UE_seconds','meaning':'LS wall minus its UE network calls; UE is already in total network time'},{'field':'search_other_bookkeeping_seconds','meaning':'search wall minus total network UE time minus LS nonUE'},{'field':'sealed lookup replay','meaning':'S0-S2 only; absent from S3 runtime summaries'},{'field':'training','meaning':'S3 retraining calls0; reusable original ensemble has prior training cost, not zero lifetime cost; first-batch cheap fits separately measured'},{'field':'delta regret','meaning':'variant minus F0 in percentage points; positive favors F0'},{'field':'unit','meaning':'scenario after averaging three seeds; ten independent synthetic scenarios; exploratory descriptive results only'}])
 # Complete numerical archive: raw runs, inputs, complete references and requested descriptive CSV.
 files=[]
 for folder in [NEW,RUNS,REF,DELIVERY,CONTROL]:files.extend(f for f in folder.rglob('*') if f.is_file() and f.name.endswith(('.csv','.csv.gz')))
 files=sorted(set(files));csv(DELIVERY/'numeric_archive_index.csv',[{'path':str(f.relative_to(OUT)).replace('\\','/'),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]);files.append(DELIVERY/'numeric_archive_index.csv')
 archive=OUT/'4.5_S3正式实验_数值结果.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for f in files:z.write(f,str(f.relative_to(OUT)))
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 dump(DELIVERY/'archive_validation.json',{'status':'PASS','path':str(archive),'files':len(files),'bytes':archive.stat().st_size,'sha256':sha(archive),'CRC_checked':True,'CSV_only':True})
 table='\n'.join(f"| {s['variant_id']} | {s['n_scenarios_exact_regret']}/10 | {s['mean_scenario_regret_pct']:.6f} | {s['mean_paired_delta_regret_pp_vs_F0']:.6f} | {s['mean_fresh_online_seconds']:.4f} | {s['variant_wins_vs_F0']}/{s['equivalent_ties_vs_F0']}/{s['variant_losses_vs_F0']} |" for s in summary)
 report=f'''# Reviewer 1 第4.5条 第二批S3中文验收报告

完成时间：{now()}。冻结v2协议SHA256：`{EXPECTED}`。本轮未修改F0—F9定义/参数、未重训模型、未调整情景或种子。

## 执行与封存

原生成器按2026102905一次性生成5101—5110十个新严重洪水情景，沿用闭路8—12分布、至少10条初始关闭道路和连通性要求。深度向量、closure mask和组合hash对原训练/开发、1001—1010、3001—3030、4401—4406及已知历史输入去重；拒绝事件全保留。道路按原规则预选10条并冻结。

计划330任务，已逐一尝试330：成功{len(records)}，失败{330-len(records)}。每任务独立空缓存，B≤256（含R0），seed索引0/1/2，全部单进程CPU0、线程1、顺序执行，无墙钟上限。阶段账本记录所有请求、首见状态、完整序列目标、incumbent及LS变化。所有任务记录先封存，之后才独立重算每情景1024个RG≤1e-9状态与条件DP；全局封存SHA256：`{seal_sha}`。完整参照{sum(x['states']==1024 for x in reference_rows)}/10。失败记录和缺失分母见missing_data.csv，未替换或丢弃任何情景/任务。

## 完整性验收

F3严格25/0/15/10/10，无disagreement名额。F1使用flat队列、30k合法唯一候选和原60 primary；F1/F3池与同情景同种子F0哈希一致。F6—F8保留来源补足条数（包括0与prefix补足的逐条来源）；F9无模型文件读取、无代理预测、无proxy DP，保留真实UE前缀排序。对每个成功运行独立重建最终及全部完整序列J，缓存命中不重复计费，阶段首见状态互斥加总，在线UE状态与独立参考成本逐位一致。DP由前向与独立后向递推交叉核验。所有Frozen v2源/模型哈希复核不变。

## 请求的描述性数值

下表先在每情景内平均三个种子，再跨情景汇总。差异为变体regret减F0（百分点），正值表示F0较好；胜/等价/负按同情景种子平均J与经验κ比较。P90、逐情景/逐运行regret和配对差异均保留CSV。这是十个合成情景上的探索性系统比较，不作显著性声明，不把技术重复视为独立情景，不据此宣称代理相对于UE-only强基线有整体优势。

| 变体 | 精确regret情景 | 平均regret% | 相对F0差值pp | 真实在线秒 | 变体对F0胜/等价/负 |
|---|---|---|---|---|---|
{table}

## 时间与训练成本

本批fresh_online_seconds来自真实在线UE新求解，**不是**第一批sealed lookup replay时间。输入读取、模型加载/开发暖机、JIT开发暖机及落盘导出均在主计时之外另记。模型只读复用，F9/Greedy-ILS不调用任何预测。每次状态求解仍冷启动流量，不跨任务复用已知UE成本。候选准备包含代理推理，UE network时间包含kernel，LS非UE时间已扣除UE，分项不得重复相加。运行顺序按情景/种子循环旋转11方法，所有候选和搜索审计开销计入相应在线范围。

Ridge/HGB训练发生在第一批，S3新增拟合0次；其原3178训练行、120维特征、fit/数据加载/特征处理分项见fixed_surrogate_training_costs.csv。原十成员模型沿用既有权重，未重新测量或声称其生命周期训练成本为0；在线结果属于可复用模型口径。

## 阶段质量与解释边界

first_LS_quality_and_improvement.csv给出首次LS前/后J及精确regret、首次提升和全部LS调用的可观测改善；phase_UE_query_efficiency.csv给出各阶段首见查询、完成序列、incumbent更新和最终路径状态来源。首次完整解出现前改善为NA。Greedy-ILS保留greedy/greedy_complete/initial_start/restart/LS实际阶段，初始化查询同样计费。budget_fill沿用冻结结构化前缀规则，不自动称为有用改善；单状态、阶段和source tag归属都不能作独立因果贡献。

## 交付及停止范围

原始候选/筛选、查询/完整序列/LS、计时/来源、任务封存记录在04_method_runs_pre_reference；完整状态与条件DP在05_reference_after_freeze；本报告、逐情景regret、配对差异、阶段效率及训练/成本CSV在08_S3_delivery。数值包：`4.5_S3正式实验_数值结果.zip`，{len(files)}个CSV/CSV.GZ，CRC通过。未打包代码、权重或文稿。

按本轮授权止于S3验收与所要求的基本数值汇总，未执行900次retrospective、共同池模型评分诊断、bootstrap/显著性检验、第三批扩展或论文/英文回复，未根据结果改良方法。
'''
 (DELIVERY/'S3_中文验收报告.md').write_text(report,encoding='utf-8')
 dump(DELIVERY/'validation.json',{'status':'PASS' if len(records)==330 and all(x['states']==1024 for x in reference_rows) else 'COMPLETE_WITH_EXPLICIT_MISSING_DATA','tasks_attempted':330,'successful':len(records),'failed':330-len(records),'complete_references':sum(x['states']==1024 for x in reference_rows),'frozen_v2_unchanged':True,'third_batch_started':False,'at':now()})
 dump(CONTROL/'progress.json',{'stage':'S3_COMPLETE','tasks':330,'successful':len(records),'references_complete':sum(x['states']==1024 for x in reference_rows),'delivery':str(DELIVERY),'numeric_zip':str(archive),'at':now()})
 print(json.dumps({'event':'S3_COMPLETE','delivery':str(DELIVERY),'archive':str(archive),'at':now()},ensure_ascii=False),flush=True)
