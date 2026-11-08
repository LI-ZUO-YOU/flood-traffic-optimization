"""Advisor-facing annotations beside recovered source; source bytes unchanged."""
from pathlib import Path
import ast,html,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'source_snapshot/legacy_sa/run_permutation_sa.py'
source=src.read_text(encoding='utf-8');tree=ast.parse(source)
notes={
'SAConfig':'原 SA 参数容器。相邻交换与插入概率显式给出，剩余概率对应任意两点交换；无新状态停滞上限默认 1000。',
'LogicalUEOracle':'原投稿后 SA 敏感性分析使用的逻辑 oracle：按每个方法首次请求的恢复子集计费。它的后端是已存在的旧状态表，不能直接把这段主程序当作本次新验证的执行入口。',
'LogicalUEOracle.evaluate_sequence':'只评价 R0–R9 的十个子集，不包括零权重 R10。完整候选若需要的新增状态超过余额，则返回 None，不消耗半条路径。',
'objective_from_table':'历史数值核对函数，直接读取已完成状态表；用于复算，不用于正式搜索阶段。',
'exact_dp':'旧包的条件精确子集 DP，终态不增加成本。当前正式实验只有封存所有搜索输出后才能调用独立的精确阶段。',
'propose':'原始邻域抽样：先相邻交换、再插入、其余为任意交换。本次直接复用这一函数，避免重写改变随机数消耗顺序。',
'run_sa':'原始 SA 本体。每一次提案（包括余额不够的提案）都推进迭代；温度尺度使用当前目标，而非固定初始目标。这是恢复源程序后校正的重要细节。函数尾部计算 DP/regret，所以本次新验证不直接调用整个 run_sa。',
'tables_by_scenario':'读取每情景完整 1024 状态的历史表；这是旧敏感性分析的数据入口。本次搜索只能通过标量实时请求接口访问状态。',
'parameter_grid':'原调参网格。初稿基线参数来自开发情景 246/247/249；不可在新情景结果揭盲后重选。',
'config_key':'配置序列化哈希，用于调参记录追溯。',
'main':'旧研究的完整后处理入口，含原机 D 盘绝对路径、开发调参和历史终检。导师阅读时可据此追溯，当前机器无需直接执行其 main。'
}
located={}
def walk(node,prefix=''):
    for n in getattr(node,'body',[]):
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
            name=prefix+n.name
            if name in notes:located[n.lineno]={'symbol':name,'note':notes[name],'end_line':n.end_lineno}
            if isinstance(n,ast.ClassDef):walk(n,name+'.')
walk(tree)
out=ROOT/'source_snapshot/legacy_sa/导师阅读_原始SA逐段标注.html'
parts=['<!doctype html><meta charset="utf-8"><title>投稿后原始 SA 源码标注</title><style>body{font:16px/1.6 "Microsoft YaHei",sans-serif;margin:28px;color:#222}.note{background:#eff6fa;padding:12px;margin:18px 0 8px;max-width:1100px}.code{font:13px/1.6 Consolas,monospace;white-space:pre;display:block}.ln{display:inline-block;width:4em;color:#888;user-select:none}h1{font-size:26px}a{color:#0067a0}</style><h1>恢复的原始 SA 代码阅读标注</h1><p>来源为老家资料初稿 P1 v2.2 投稿包。此文件为旁注，不改源程序。原始 .py 中 D 盘路径属于旧电脑。</p><p>本次正式返修入口为 code/run_revision.py；为保留后置精确参照信息隔离，复用旧 propose 与配置后，通过独立 QueryOracle 实时评价，而不直接调用旧 main/run_sa。旧十情景回放已核对目标、序列及查询数。</p>']
for i,line in enumerate(source.splitlines(),1):
    if i in located:parts.append('<div class="note"><b>'+html.escape(located[i]['symbol'])+'</b>：'+html.escape(located[i]['note'])+'</div>')
    parts.append(f'<span class="code" id="L{i}"><span class="ln">{i}</span>{html.escape(line)}</span>')
out.write_text('\n'.join(parts),encoding='utf-8')
(out.parent/'原始SA标注定位.json').write_text(json.dumps({'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'annotations':located},ensure_ascii=False,indent=2),encoding='utf-8')
print('Created source-preserving advisor annotations for',len(located),'code sections.')
