"""Package completed, audited local results without publishing anything."""
from pathlib import Path
import json,hashlib,zipfile,datetime,importlib.metadata,platform,shutil
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    summary=json.loads((ROOT/'analysis/analysis_summary.json').read_text(encoding='utf-8'))
    assert summary['status']=='ANALYSIS_COMPLETE' and summary['all_run_integrity_checks_passed']
    assert summary['query_cap_runs']==1590 and summary['time_cap_runs']==660
    unit=json.loads((ROOT/'development/unit_test_result.json').read_text());assert unit['passed']
    precision=json.loads((ROOT/'analysis/selected_objective_precision_stability.json').read_text());assert precision['all_within_frozen_objective_epsilon']
    audits=json.loads((ROOT/'figures/qa/automatic_audit_summary.json').read_text());assert all(r['returncode']==0 for r in audits)
    visual=json.loads((ROOT/'figures/qa/manual_visual_review.json').read_text());assert visual['all_figures_passed']
    cfg=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
    for name,h in cfg['source_hashes'].items():assert sha(ROOT/name)==h,name
    assert sha(ROOT/'protocol/frozen_protocol.json')==(ROOT/'protocol/frozen_protocol.sha256').read_text().strip()
    historic=ROOT/'development/historical_precision';historic.mkdir(exist_ok=True)
    parent=ROOT.parent
    for src in [parent/'analysis/历史十情景_高精度复算汇总.csv',parent/'development/legacy_precision/all_recomputed_decisions.csv']:
        assert src.exists();shutil.copy2(src,historic/src.name)
    packages={}
    for name in ['numpy','pandas','scipy','torch','numba','llvmlite','matplotlib','pymupdf','psutil']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    dump(ROOT/'environment_versions.json',{'python':platform.python_version(),'platform':platform.platform(),'processor':'12th Gen Intel Core i5-12600KF','physical_cores':10,'logical_processors':16,'timing_worker_affinity':[0,2,4,6],'library_threads':1,'packages':packages})
    status={'status':'SIMULATIONS_AND_COMMENT_LEVEL_DRAFTS_COMPLETE','completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'formal_scenarios':list(range(3001,3031)),'query_runs':1590,'time_runs':660,'conditional_reference_states':30720,
        'protocol_sha256':sha(ROOT/'protocol/frozen_protocol.json'),'algorithm_outputs_freeze_sha256':sha(ROOT/'protocol/all_method_outputs_frozen.json'),
        'all_integrity_checks_passed':True,'all_figure_audits_passed':True,'full_word_manuscript_integrated':False,'remote_publication_performed':False,
        'entry_point':'manuscript/4.1_返修结果与中文核对.md'}
    dump(ROOT/'00_完成状态.json',status)
    rootstatus=json.loads((parent/'00_正在运行的正式实验.json').read_text(encoding='utf-8-sig'));rootstatus['status']=status['status'];rootstatus['completion_report']=str(ROOT/'00_完成状态.json');dump(parent/'00_正在运行的正式实验.json',rootstatus)
    (parent/'00_当前进度与结果说明.md').write_text('''# 4.1 返修模拟已完成

当前有效正式结果在“正式模拟_v2”。已完成 30 个新情景（3001–3030）、1,590 次同查询预算运行、660 次独立耗时运行，以及全部搜索输出封存后的 30,720 状态条件精确参照。数值、账本、独立 DP 和图形验收均已通过。

请先阅读 正式模拟_v2/manuscript/4.1_返修结果与中文核对.md，再看 Table R2、R3 与 Figure R2。英文 4.1 回复草稿、正文替换段落及补充方法也在 manuscript 中，尚未整合为完整 Word 修订稿，不能将局部草稿视为全部审稿意见已解决。

老家传入文件已补齐历史 121–160 原始水深输入并恢复原 SA；历史输入与旧冻结 SHA256 一致，原 SA 在旧十情景回放的目标、序列、查询数全部匹配。来源与 21,832 个文件清单在正式目录 inputs 中。

恢复原 SA 前的工程批次 2001–2030 保留为无效工程记录，不参与科学比较。其作废源于实现依据校正，在读取比较结果前完成；正式批次通过新的冻结种子生成，与结果胜负无关。历史十情景的高精度复算只作数值桥接，不并入新的独立样本。

原始稿件、原始代码和旧结果均未覆盖。没有执行远程投稿、上传或发送。
''',encoding='utf-8')
    # Archive preserves all scientific raw outputs; runtime/JIT caches and diagnostic
    # overlay PDFs are not needed to reproduce the decisions.
    def include(p):
        return p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.nbc','.nbi'} and not p.name.endswith('.collision-overlay.pdf') and p.name!='交付文件SHA256.json'
    files=sorted(p for p in ROOT.rglob('*') if include(p))
    manifest={'created_utc':status['completed_utc'],'status':status['status'],'files':{str(p.relative_to(ROOT)):sha(p) for p in files}}
    dump(ROOT/'交付文件SHA256.json',manifest)
    target=parent/'4.1正式模拟结果与代码_3001至3030_20261027.zip'
    if target.exists():raise FileExistsError('Keep existing delivery archive; choose a new explicit version.')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[ROOT/'交付文件SHA256.json']:z.write(p,ROOT.name+'/'+str(p.relative_to(ROOT)))
    dump(parent/'4.1交付压缩包校验.json',{'file':str(target),'bytes':target.stat().st_size,'sha256':sha(target),'scientific_files':len(files),'archive_check':zipfile.ZipFile(target).testzip()})
    print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,'files':len(files),'status':status['status']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
