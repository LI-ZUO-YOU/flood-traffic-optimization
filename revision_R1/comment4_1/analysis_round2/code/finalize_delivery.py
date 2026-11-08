"""Audit and package the already completed round-2 calculations; no simulations."""
from common import *
import ast, shutil, zipfile, gzip, re

def finalize():
    # Preserve both complete timing attempts and correct execution accounting.
    p=OUT/'S2_execution_timing.json'
    j=json.loads(p.read_text(encoding='utf-8'))
    j['completed_training_state_solves']=6356
    j['unique_training_states']=3178
    j['complete_training_cost_measurement_passes']=2
    j['completed_case_development_warmup_solves']=None
    j['warmup_accounting_note']='Warm-ups occurred on the initial execution, resumed execution and training-cost retry. Their exact count and unfinished interrupted-case calls are not reconstructed; neither is included in measured production-state counts.'
    j['training_cost_retry_note']='The first 3178-state pass completed but a subsequent metadata assertion incorrectly expected member timers to equal the outer training-loop timer. Both full measurements are retained. The second pass supplies the complete dataset wall clock; no decision-quality selection was performed.'
    j['first_training_pass_state_call_seconds_sum']=float(frame(OUT/'S2_offline_cost/3178_training_state_costs_attempt1.csv').current_cold_state_seconds.sum())
    dump(p,j)
    src=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第二周工作\v2_day2_huber_ensemble\scripts\run_v2_day2_huber_ensemble.py')
    dst=OUT/'S2_offline_cost/source_records'/src.name
    shutil.copy2(src,dst)
    dump(OUT/'S2_offline_cost/training_timer_scope_provenance.json',{
        'source':str(src),'copied_to':str(dst),'sha256':sha(src),'copied_sha256':sha(dst),
        'executed_in_round2':False,
        'member_timer':{'start_line':343,'stop_line':393,'export_line':432},
        'outer_member_loop_timer':{'start_line':553,'stop_line':565,'config_export_line':647},
        'interpretation':'Member training_time_seconds sum and outer total_training_seconds measure different scopes. Hybrid cost uses the outer timer, with historical hardware unknown.'})

    # Keep generating source and delivered prose consistent about timer scopes.
    gen=OUT/'code/write_reports.py'
    t=gen.read_text(encoding='utf-8')
    t=t.replace("The archived ten-member training record adds {fmt(offline['archived_ten_member_training_seconds_sum'])} s, with matching model hashes but unestablished original hardware. We label that sum a hybrid estimate, not a same-hardware retraining benchmark.","The archived outer training-loop timer adds {fmt(offline['archived_training_process_total_seconds'])} s (member timers sum to {fmt(offline['archived_ten_member_training_seconds_sum'])} s), with matching model hashes but unestablished original hardware. The resulting {fmt(offline['hybrid_current_UE_plus_archived_training_seconds'])} s is a hybrid estimate, not a same-hardware retraining benchmark.")
    t=t.replace("历史十成员训练记录 {fmt(offline['archived_ten_member_training_seconds_sum'])} 秒，权重哈希匹配。两者相加是跨测量背景的混合估计", "历史十成员分项合计 {fmt(offline['archived_ten_member_training_seconds_sum'])} 秒、外层训练循环 {fmt(offline['archived_training_process_total_seconds'])} 秒，权重哈希匹配。当前制样与外层循环相加得到 {fmt(offline['hybrid_current_UE_plus_archived_training_seconds'])} 秒，是跨测量背景的混合估计")
    gen.write_text(t,encoding='utf-8')
    # Rebuild only prose/aggregated summary exports. No model/solver/replay calls.
    import runpy
    runpy.run_path(str(gen),run_name='__main__')

    figures=[]
    for name in ['S1_regret_stages','S2_online_cost']:
        figures.append({'figure':name,'png_sha256':sha(OUT/f'figures/{name}.png'),
                        'pdf_sha256':sha(OUT/f'figures/{name}.pdf'),
                        'visual_review':'PASS','checked':['labels readable','no visible clipping','no visible overlap','legend and data distinguished'],
                        'review_scope':'Final exported PNG inspected in conversation; PDF text/collision audited separately. Subsequent Word scaling not checked.'})
    dump(OUT/'figures/qa/manual_visual_review.json',{'intended_width_mm':183,'figures':figures})
    (OUT/'figures/figure_legends.md').write_text('''# 第二轮图注与读图范围

**S1_regret_stages：30 个情景的 regret 阶段诊断。** 每个点是同一情景十个冻结搜索种子的均值，竖线为十种子的最小值至最大值；情景是独立汇总单位（n=30），种子不是额外独立情景。展示候选池 oracle 最佳、保留集 oracle 最佳、第一次局部搜索前最佳完整决策、最终 Proposed；冻结 UE-Greedy-ILS 为参照。纵轴为百分比 regret，使用 symlog，线性区域为 ±0.001%。这些是不同可达集合及不同阶段的描述性指标，不能相加解释为独立因果贡献；后续局部搜索可以生成池外序列。全部第二轮分析为事后诊断。

**S2_online_cost：在线耗时比较。** 每种方法显示 30 个情景的在线耗时点；箱线的中位线为中位数，箱体为四分位距，须为第 10–90 百分位。枚举组为本轮每情景冷状态缓存的 1,024 次 UE 加 DP；单进程与四进程分开。其余方法引用上一轮 fresh time-cap 测量，先在情景内汇总重复，再画 30 个点。计时不含 JIT、模型/输入准备及导出，完整并行批次墙钟另报；不同批次并非随机化速度试验。时间组方法质量不同，不能把该图解释为同质量加速比。

PDF/SVG 可编辑，PNG/TIFF 为 600 dpi，设计宽度 183 mm。自动检查和最终导出图人工核对记录见 qa/；Word 排版后的缩放需要另行核对。
''',encoding='utf-8')

    ref=OUT/'reference_original_results'; ref.mkdir(exist_ok=True)
    copied={}
    for folder in ['analysis','protocol']:
        for f in (ROOT/folder).iterdir():
            if f.is_file() and f.suffix in ['.csv','.json','.sha256']:
                target=ref/folder/f.name;target.parent.mkdir(exist_ok=True)
                shutil.copy2(f,target);copied[str(f.relative_to(ROOT))]=sha(target)
    dump(ref/'copied_original_sha256.json',copied)
    (OUT/'README_阅读与复现.md').write_text('''# 第二轮补充模拟与诊断

先读 `00_第二轮结果总览.md`，再读 S1 失败机制报告和 S2 计算成本报告。`manuscript/` 是可供整合的英文替换段落、证据对应表及分审稿人回复草稿；尚未合并完整 Word 稿件，页码/行号须在最终排版后补齐。

本轮仅分析已揭示的 3001–3030；未新增情景、未重训代理、未开发 V2、未修改冻结方法或确认性结果。S1 使用已有 1,024 状态表，UE 调用数为零；S2 的独立成本计时才重新求解 UE。原计划中“S3 计时例外”按实际章节 S2 理解。两个代理起点规则全部重合，不能据此声称完成整套方法删除 reserve 的消融。边际收益递减存在大量反例，未证明次模性。

## 内容

- S0：原始文件 SHA256 与 300 次回放核验。
- S1：9,000,000 条带 oracle 的候选、筛选/前缀/阶段预算/LS 轨迹，600 次事后起点控制及全部汇总。
- S2：30 个情景各单进程与四进程枚举计时（61,440 个生产状态求解）；3,178 个训练状态成本的两次完整计时均保留（6,356 次调用），并非重训。第一遍后的计时范围断言触发技术重试，第二遍提供完整制样墙钟。
- figures：可编辑 PDF/SVG、600 dpi PNG/TIFF、图注及检查记录。
- reference_original_results：冻结第一轮统计/协议副本，便于独立分析；这些文件的哈希与原文件一致。

## 复现

代码通过 `common.py` 将上级目录视为原 `正式模拟_v2/`，需要原冻结 `code/`、`inputs/`、`exact/`、`runs/`、`source_snapshot/`、`protocol/` 及第一轮结果。本压缩包可独立阅读分析，但重放需要与原正式模拟目录一起使用；`fresh_timing.py` 还需 provenance 所列原训练数据路径。不要单独解压后将重放误当为无需原数据的独立项目。

运行环境：Python 3.11.15，NumPy 2.4.6，pandas 3.0.3，SciPy 1.17.1，Numba 0.68，Torch 2.13 CPU，matplotlib 3.11.2。实际解释器 `E:\\ProgramData\\Anaconda3\\envs\\rag_demo\\python.exe`；`PYTHONPATH` 设置为上上级目录下 `runtime_deps/`。禁止对旧文件重新执行冻结脚本来掩盖变化。

按需依次运行 `code/replay_diagnostics.py --workers 4`、`code/analyze_round2.py`、`code/fresh_timing.py`、`code/summarize_and_plot.py`、`code/write_reports.py`、`code/audit_exports.py`。这些命令会覆盖本轮同名输出，通常无需重跑。CPU 亲和分组及历史计时范围以 S2 报告为准，计时不保证跨机器复现同一秒数。`code/finalize_delivery.py` 仅用于本次交付审计/打包；其中两次计时的执行记录专属于本次实际运行，不能用来为新运行推断调用数。

`completion_check.json` 为最终验收；`delivery_files_sha256.json` 为压缩前逐文件清单；ZIP 旁的 `package_integrity.json` 记录 ZIP SHA256 及 CRC 校验结果。压缩包排除自身、临时运行缓存和自身校验文件，原始科学数据/日志/代码全部保留。
''',encoding='utf-8')

    checks={}
    m=verify_manifest();checks['original_frozen_files_unchanged']=len(m['original_files_sha256'])
    r=frame(OUT/'S0_replay_consistency.csv');assert len(r)==300
    for c in ['objective_bitwise_equal','sequence_equal','query_order_phase_reason_equal','logical_requests_equal']:assert r[c].all()
    assert r.queries.eq(256).all() and r.UE_solves.eq(0).all()
    checks['source_faithful_bitwise_replays']=300
    phase=frame(OUT/'S1_budget_by_phase.csv');phase=phase[phase.scope=='phase_total']
    assert phase.groupby(['scenario_id','replicate']).unique_queries.sum().eq(256).all()
    checks['replay_query_budgets_verified']=300
    controls=frame(OUT/'S1_start_ablation.csv')
    controls=controls[controls.method.isin(['proxy_pool_top1_ls','primary_top1_ls'])]
    assert len(controls)==600 and controls.unique_queries.le(256).all()
    checks['post_hoc_start_controls_within_budget']=600
    pools=sorted((OUT/'replay').glob('scenario_*/rep_*/candidate_pool_30000_with_oracle.csv.gz'));assert len(pools)==300
    pool_rows=0
    for f in pools:
        with gzip.open(f,'rt',encoding='utf-8') as h: n=sum(1 for _ in h)-1
        assert n==30000;pool_rows+=n
    checks['candidate_oracle_rows']=pool_rows
    files=sorted((OUT/'S2_timing_raw').glob('*/scenario_*/all_fresh_1024_states.csv.gz'));assert len(files)==60
    gap=0.
    for f in files:
        df=frame(f);assert len(df)==1024 and set(df.subset_mask)==set(range(1024))
        assert df.converged.all() and df.relative_gap.le(1e-9).all();gap=max(gap,float(df.relative_gap.max()))
    checks.update(fresh_enumeration_batches=60,production_UE_states=61440,max_production_relative_gap=gap)
    for name in ['3178_training_state_costs.csv','3178_training_state_costs_attempt1.csv']:
        df=frame(OUT/'S2_offline_cost'/name);assert len(df)==3178 and df.relative_gap.le(1e-9).all()
    checks['training_cost_measurements_retained']=6356
    prov=json.loads((OUT/'S2_offline_cost/source_provenance.json').read_text(encoding='utf-8'))
    assert prov['all_ten_training_hashes_match_frozen_weights']
    for info in prov['sources'].values():assert sha(info['path'])==info['sha256']
    checks['training_source_and_weight_provenance']='PASS'
    audits=json.loads((OUT/'figures/qa/automatic_audits.json').read_text(encoding='utf-8'));assert len(audits)==5 and all(x['returncode']==0 for x in audits)
    for f in (OUT/'figures/qa').glob('*.collision.json'):
        j=json.loads(f.read_text(encoding='utf-8'));assert j['verdict']=='PASS' and j['summary']['warn']==0
    checks['figure_automatic_and_visual_review']='PASS: two figures; source, PDF text, collision, final exported PNG'
    a=(OUT/'manuscript/Reviewer1_4.1_4.3_4.5_5.1_回复草稿.md').read_text(encoding='utf-8')
    b=(OUT/'manuscript/Reviewer2_1_6_回复草稿.md').read_text(encoding='utf-8')
    assert not re.search(r'Reviewer\s*2',a,re.I) and not re.search(r'Reviewer\s*1',b,re.I)
    main=(OUT/'manuscript/S4_重新定位与英文替换段落.md').read_text(encoding='utf-8')
    conclusion=main.split('## Conclusion replacement\n\n')[1].split('\n\n## ')[0].strip()
    assert '*'+conclusion+'*' in a
    checks['reviewer_separation_and_conclusion_consistency']='PASS'
    codes=list((OUT/'code').glob('*.py'))
    for f in codes:ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
    checks['syntax_checked_round2_scripts']=len(codes)
    dump(OUT/'completion_check.json',{'status':'PASS','checks':checks,'S0':'verified complete','S1':'verified complete; post hoc','S2':'verified complete; timing scopes and retries disclosed','S3':'decision documented; no algorithm development','S4':'replacement passages and reply drafts supplied; final locations and complete Word integration pending','full_word_manuscript_integrated':False})
    print('FINAL AUDIT PASS',checks,flush=True)

    target=OUT/'4.1第二轮全部诊断与模拟结果_20261027.zip'
    excluded={'delivery_files_sha256.json','package_integrity.json',target.name}
    paths=[f for f in OUT.rglob('*') if f.is_file() and not set(f.relative_to(OUT).parts)&{'runtime_cache','__pycache__'} and f.name not in excluded]
    entries={f.relative_to(OUT).as_posix():{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(paths)}
    dump(OUT/'delivery_files_sha256.json',{'files':entries,'file_count':len(entries),'total_uncompressed_bytes':sum(v['bytes'] for v in entries.values()),'excluded':['runtime_cache','__pycache__',target.name,'delivery_files_sha256.json (self)','package_integrity.json (archive checksum)']})
    paths.append(OUT/'delivery_files_sha256.json')
    print('PACKAGING',len(paths),'files',sum(f.stat().st_size for f in paths),'bytes',flush=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
        for i,f in enumerate(paths):
            z.write(f,arcname='analysis_round2/'+f.relative_to(OUT).as_posix())
            if i%1000==0:print('packed',i,'of',len(paths),flush=True)
    with zipfile.ZipFile(target) as z:
        assert len(z.namelist())==len(paths)
        assert z.testzip() is None
    verify_manifest()
    dump(OUT/'package_integrity.json',{'archive':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'file_count':len(paths),'zip_crc_test':'PASS','original_frozen_files_final_recheck':'PASS','includes_full_Word_revision':False})
    print('DELIVERY COMPLETE',target,target.stat().st_size,flush=True)

if __name__=='__main__':finalize()
