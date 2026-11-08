from s4_common import *
import ast,subprocess,importlib.metadata
def main():
 assert (OUT/'logs/S4_computation_complete.json').exists()
 for p in (OUT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
 versions=[{'package':name,'version_observed_at_analysis':importlib.metadata.version(name),'observation_scope':'post-computation environment, not a claim of continuous OS isolation'} for name in ['numpy','pandas','scipy','numba','torch']]
 csv(OUT/'analysis/S4_environment_versions.csv',versions)
 for name in ['s4_analyze.py','s4_finalize.py']:
  p=subprocess.run([sys.executable,str(OUT/'code'/name)],capture_output=True,text=True,encoding='utf-8')
  (OUT/'logs'/f'{name}.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8');print(json.dumps({'script':name,'exit_code':p.returncode,'stdout':p.stdout[-3500:],'stderr':p.stderr[-2500:]},ensure_ascii=False),flush=True)
  if p.returncode:raise RuntimeError(name+' failed; review postprocessing log; do not rerun scientific tasks')
 print('S4_ANALYSIS_REPORTS_AND_NUMERIC_ARCHIVE_COMPLETE',flush=True)
if __name__=='__main__':main()
