"""Run required source, glyph and collision audits after the final render."""
from pathlib import Path
import subprocess,sys,json
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure\scripts')
QA=ROOT/'figures/qa';QA.mkdir(exist_ok=True)
records=[]
def run(name,args):
    r=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True,encoding='utf-8')
    (QA/(name+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
    records.append({'audit':name,'returncode':r.returncode,'log':str((QA/(name+'.log')).relative_to(ROOT))})
    return r
run('plot_source',[SCRIPTS/'validate_figure.py',ROOT/'code/plot_revision.py','--json'])
for p in sorted((ROOT/'figures').glob('Figure_R*.pdf')):
    if '.collision' in p.name:continue
    r=run(p.stem+'_glyphs',[SCRIPTS/'audit_pdf_text.py',p,'--min-pt','5','--json'])
    if r.returncode==0:
        try:(QA/(p.stem+'.glyph-audit.json')).write_text(json.dumps(json.loads(r.stdout),indent=2),encoding='utf-8')
        except json.JSONDecodeError:pass
    run(p.stem+'_collisions',[SCRIPTS/'audit_figure_collisions.py',p,'--json-out',QA/(p.stem+'.collision-audit.json'),'--overlay-pdf',QA/(p.stem+'.collision-overlay.pdf')])
(QA/'automatic_audit_summary.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
if any(r['returncode'] for r in records):raise SystemExit(1)
