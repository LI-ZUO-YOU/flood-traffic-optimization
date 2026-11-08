"""Read-only inventory of newly transferred files and source provenance."""
from pathlib import Path
import subprocess,csv,json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
BASE=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    paths=[Path(p) for p in subprocess.check_output(['rg','--files',str(BASE)],text=True,encoding='utf-8').splitlines()]
    rows=[]
    for p in paths:
        st=p.stat();rows.append({'relative_path':str(p.relative_to(BASE)),'extension':p.suffix.lower(),'bytes':st.st_size,'top_folder':p.relative_to(BASE).parts[0]})
    out=ROOT/'inputs/recovered_source_inventory.csv'
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    sa=[p for p in paths if p.name=='run_permutation_sa.py']
    rec=[{'file':str(p),'sha256':sha(p)} for p in sa]
    hist=BASE/'第二周工作/final_untouched_holdout_v1.0/scenarios/flood_scenarios_physical_links.csv'
    source=BASE/'初稿/Frontiers_Submission_Package_P1_v2.2/reproducibility/p1_revision_tools/run_permutation_sa.py'
    report={'file_count':len(paths),'inventory_scope':'rg --files; honors ignored paths; does not expand archive members','total_bytes':sum(r['bytes'] for r in rows),
        'top_folder_counts':dict(collections.Counter(r['top_folder'] for r in rows)),
        'historical_121_160':{'source':str(hist),'sha256':sha(hist),'expected_freeze_sha256':'08810201b2365389b476ad1c9cc897977cbdd1576970da1e76d0f28758aca780'},
        'original_sa_variants':rec,'chosen_original_sa':str(source),'chosen_matches_snapshot':sha(source)==sha(ROOT/'source_snapshot/legacy_sa/run_permutation_sa.py')}
    assert report['historical_121_160']['sha256']==report['historical_121_160']['expected_freeze_sha256']
    assert report['chosen_matches_snapshot']
    (ROOT/'inputs/recovered_source_provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f'''# 老家传入资料搜索与恢复记录

已搜索 `{BASE}`，rg 文件清单共 {len(paths):,} 个文件，详见 recovered_source_inventory.csv。清单遵循 rg 忽略规则，未把压缩包成员冒充已逐一读取的文件。目录中的研究计划、对话记录与旧说明作为资料，不视为当前用户新增指令。

恢复的两项关键输入：

1. 121–160 历史情景原始物理道路水深表：`{hist}`。SHA256 与旧冻结协议完全匹配：`{sha(hist)}`。已复制至本次 inputs/historical_121_160.csv，完成新情景生成前的全历史去重门槛；不在这40个历史情景上优化。
2. 投稿包原始 SA：`{source}`。已保留未修改的快照于 source_snapshot/legacy_sa/run_permutation_sa.py。旧十个情景逐项复现目标值、最终序列与查询数均匹配，检查见 development/original_SA_compatibility.json。其他版本的原始 SA 文件哈希亦记录在 provenance JSON 中。

当前正式返修工作目录为 `{ROOT}`。此前恢复原始 SA 之前启动的 2001–2030 仅保留作废工程记录；正式输入为冻结后一次生成的 3001–3030。任何科学结论只引用本目录正式结果。

目录里存在多轮第一至四周过程材料与多个投稿包。文件夹日期或版本号只能提示来源，不能单凭“最新”认定对应初稿；本次正式算法快照以原冻结协议和代码哈希核对，原始 SA 以源程序回放核对。原始文件没有被改写或删除。
'''
    (ROOT/'inputs/老家资料搜索与恢复说明.md').write_text(text,encoding='utf-8')
    print(json.dumps({'files':len(paths),'historical_hash_match':True,'original_sa_snapshot_match':True}))
if __name__=='__main__':main()
