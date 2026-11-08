from common import *
import importlib.util,contextlib,io
SKILL=Path('C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
def load(name):
 spec=importlib.util.spec_from_file_location(name,SKILL/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
 records=[]
 for name in ['Figure_R2C6_SA_seed_stability','Figure_R2C6_budget_and_regret']:
  path=OUT/f'figures/{name}.pdf'
  for module,args,label in [('audit_pdf_text',[str(path),'--min-pt','7','--json'],'font'),('audit_figure_collisions',[str(path),'--json-out',str(OUT/f'audit/{name}_collision.json'),'--overlay-pdf',str(OUT/f'audit/{name}_collision_overlay.pdf')],'collision')]:
   buf=io.StringIO()
   with contextlib.redirect_stdout(buf):
    try:code=load(module).main(args)
    except SystemExit as e:code=e.code
   (OUT/f'audit/{name}_{label}.log').write_text(buf.getvalue(),encoding='utf-8');records.append(dict(figure=name,test=label,returncode=int(code or 0)));print(name,label,code)
  from PIL import Image
  im=Image.open(OUT/f'figures/{name}.png');records.append(dict(figure=name,test='raster_dpi',returncode=0 if min(im.info['dpi'])>=599 else 1,pixels=im.size,dpi=im.info['dpi']))
 source=io.StringIO()
 with contextlib.redirect_stdout(source):
  try:code=load('validate_figure').main([str(OUT/'scripts/plot_figures.py'),'--json'])
  except SystemExit as e:code=e.code
 (OUT/'audit/plot_source_audit.json').write_text(source.getvalue(),encoding='utf-8');records.append(dict(figure='plot_figures.py',test='source',returncode=int(code or 0)))
 dump(OUT/'audit/figure_automated_QA.json',records)
if __name__=='__main__':main()
