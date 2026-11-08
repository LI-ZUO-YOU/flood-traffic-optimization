"""Read saved CSVs only; does not import the study implementation."""
from pathlib import Path
import csv,json,collections
root=Path(__file__).resolve().parents[1]
def rows(p):
 with (root/p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
r41=[r for r in rows('revision_R1/comment4_1/analysis/all_run_results.csv') if r['phase']=='query_cap']
assert len(r41)==1590 and {int(r['scenario_id']) for r in r41}==set(range(3001,3031))
r45=rows('revision_R1/comment4_5/08_S3_delivery/all_330_task_status.csv')
assert len(r45)==330 and all(x['status']=='PASS' for x in r45)
boot=rows('revision_R1/comment4_5/09_S4_mechanism_robustness/01_statistics/frozen_v2_descriptive_paired_bootstrap.csv')
assert len(boot)==22 and all(int(x['seed'])==2026102906 and int(x['scenario_resamples'])==10000 and int(x['independent_units'])==10 for x in boot)
r44=rows('revision_R1/comment4_4/04_method_scaling/S4_20261029/closeout_20261029/analysis/all_180_runs_posthoc_scored.csv')
assert len(r44)==180 and sum(x['status']=='PASS' for x in r44)==179
out=dict(status='PASS_SAVED_RECORD_INSPECTION',R41_query_cap_runs=len(r41),R41_independent_scenarios=30,R45_completed_runs=330,R44_completed=179,R44_planned=180,ablation_bootstrap=boot,no_scientific_code_executed=True)
print(json.dumps(out,ensure_ascii=False,indent=2))
