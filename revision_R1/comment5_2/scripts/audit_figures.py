from pathlib import Path
import os,sys,subprocess,json
OUT=Path(__file__).resolve().parents[1]
SKILL=Path('C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
os.environ['PYTHONPATH']='E:/jcr2区意见/返稿/4.1专项返修_20261026/runtime_deps'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
calls=[('source_preflight',[str(SKILL/'validate_figure.py'),str(OUT/'scripts/plot52.py'),'--json'])]
for name in ['trajectory','bottleneck','demand_policy']:
 base=OUT/'figures'/f'Figure_R1_5_2_{name}'
 calls += [(name+'_pdf_text',[str(SKILL/'audit_pdf_text.py'),str(base.with_suffix('.pdf')),'--min-pt','5','--json']), (name+'_collisions',[str(SKILL/'audit_figure_collisions.py'),str(base.with_suffix('.pdf')),'--json-out',str(base.with_suffix('.collisions.json')),'--overlay-pdf',str(base.with_suffix('.collisions.pdf'))])]
records=[]
for label,args in calls:
 p=subprocess.run([sys.executable,'-X','utf8','-B',*args],capture_output=True,text=True,encoding='utf-8')
 (OUT/'audit'/f'{label}.stdout.txt').write_text(p.stdout,encoding='utf-8')
 (OUT/'audit'/f'{label}.stderr.txt').write_text(p.stderr,encoding='utf-8')
 records.append(dict(label=label,command=[sys.executable,'-X','utf8','-B',*args],returncode=p.returncode))
 print(label,p.returncode,p.stdout[:500],flush=True)
(OUT/'audit/figure_audit_commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
if any(r['returncode'] for r in records):raise SystemExit(1)
