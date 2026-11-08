from common44 import *
import subprocess
def call(script,args=(),log=None):
 p=subprocess.run([sys.executable,str(script),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
 if log:Path(log).write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
 print(json.dumps({'script':Path(script).name,'exit_code':p.returncode,'stdout':p.stdout[-5000:],'stderr':p.stderr[-1500:]},ensure_ascii=False),flush=True)
 if p.returncode:raise RuntimeError(f'{script} failed; inspect log')
def main():
 assert js(OUT/'logs/component_batch_completion.json')['tasks']==90
 if 'figure-only' not in sys.argv:
  for name in ['analyze44.py','audit_outputs44.py','audit_search_adapter44.py']:call(OUT/'code'/name,log=OUT/'logs'/f'{name}.log')
 skill=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure\scripts');figdir=OUT/'05_analysis/figures';figdir.mkdir(exist_ok=True)
 call(skill/'validate_figure.py',[OUT/'code/plot_scaling44.py','--json'],figdir/'source_validation.json')
 call(OUT/'code/plot_scaling44.py',log=OUT/'logs/plot_scaling44.log')
 pdf=figdir/'Fig_4_4_component_scaling.pdf'
 call(skill/'audit_pdf_text.py',[pdf,'--min-pt','5','--json'],figdir/'PDF_text_audit.json')
 call(skill/'audit_figure_collisions.py',[pdf,'--json-out',figdir/'collision_audit.json','--overlay-pdf',figdir/'collision_audit.pdf'],figdir/'collision_audit.log')
 dump(OUT/'logs/postprocess_complete.json',{'finished':now(),'status':'AWAITING_VISUAL_FIGURE_QA_AND_FINAL_PACKAGING'})
if __name__=='__main__':main()
