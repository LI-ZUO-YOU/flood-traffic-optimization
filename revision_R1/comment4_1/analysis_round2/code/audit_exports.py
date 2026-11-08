from common import *
import subprocess
SCRIPTS=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure\scripts')
QA=OUT/'figures/qa';QA.mkdir(exist_ok=True)
def main():
    jobs=[('source',[SCRIPTS/'validate_figure.py',OUT/'code/summarize_and_plot.py','--json'])]
    for p in sorted((OUT/'figures').glob('*.pdf')):
        jobs.append((p.stem+'_text',[SCRIPTS/'audit_pdf_text.py',p,'--min-pt','5','--json']))
        jobs.append((p.stem+'_collision',[SCRIPTS/'audit_figure_collisions.py',p,'--json-out',QA/(p.stem+'.collision.json'),'--overlay-pdf',QA/(p.stem+'.overlay.pdf')]))
    rows=[]
    for name,cmd in jobs:
        r=subprocess.run([sys.executable,*map(str,cmd)],capture_output=True,text=True,encoding='utf-8')
        (QA/(name+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
        rows.append({'audit':name,'returncode':r.returncode})
    dump(QA/'automatic_audits.json',rows);print(json.dumps(rows),flush=True)
    assert all(r['returncode']==0 for r in rows)
if __name__=='__main__':main()
