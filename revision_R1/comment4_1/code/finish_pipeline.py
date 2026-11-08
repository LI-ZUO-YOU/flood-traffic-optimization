"""Sequential post-query execution; no search parameter changes."""
from pathlib import Path
import subprocess,sys,json,datetime
ROOT=Path(__file__).resolve().parents[1]
stages=[['run_revision.py','time','--workers','4'],['run_revision.py','freeze_outputs'],['run_revision.py','exact','--workers','4'],['analyze_revision.py'],['check_selected_precision.py'],['plot_revision.py'],['build_revision_text.py']]
for command in stages:
    status={'stage':command,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running'}
    (ROOT/'logs/finish_pipeline_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print('START',command,flush=True)
    result=subprocess.run([sys.executable,str(ROOT/'code'/command[0]),*command[1:]],cwd=ROOT)
    if result.returncode:
        status.update(status='failed',returncode=result.returncode)
        (ROOT/'logs/finish_pipeline_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
        sys.exit(result.returncode)
    print('DONE',command,flush=True)
status.update(status='complete',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(ROOT/'logs/finish_pipeline_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
