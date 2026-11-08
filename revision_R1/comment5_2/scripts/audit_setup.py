"""Read-only source inventory and a prospective freeze for Comment 5.2."""
from pathlib import Path
import csv, hashlib, json, os, platform, shutil, subprocess, sys, time
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parents[1]
REPO=OUT.parents[1]
REV=Path('E:/jcr2区意见/返稿')
BASE=REV/'4.1专项返修_20261026'
PLAN=Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Comment5.2_Codex_%E6%89%A7%E8%A1%8C%E6%8C%87%E4%BB%A4.md')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def git(*args,cwd=REPO):
 p=subprocess.run(['git',*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8')
 return dict(command=['git',*args],returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
def main():
 for name in ['audit','scripts','tests','raw','cache','logs','figures','runtime_cache']:(OUT/name).mkdir(exist_ok=True)
 if (OUT/'source_sha256.json').exists():raise RuntimeError('Source baseline already exists; do not overwrite it')
 shutil.copyfile(PLAN,OUT/'Comment5.2_Codex_执行指令.md')
 events=dict(repository=str(REPO),cwd_workspace='C:/Users/Wuzeqian.PC-20220914MSMS/Documents/Vibe1',initial_repo_status=git('status','--short','--untracked-files=all'),branch=git('branch','--show-current'),commit=git('rev-parse','HEAD'),workspace_status=git('status','--short',cwd='C:/Users/Wuzeqian.PC-20220914MSMS/Documents/Vibe1'),workspace_HEAD=git('rev-parse','HEAD',cwd='C:/Users/Wuzeqian.PC-20220914MSMS/Documents/Vibe1'))
 dump(OUT/'audit/git_before.json',events)
 # Freeze existing scientific assets and caches. Exclusions are dependency and
 # runtime directories only; every scientific sqlite/db/cache result is included.
 skip={'runtime_deps','__pycache__','runtime_cache','.git'}
 paths=set()
 for root in [REPO,*[p for p in REV.iterdir() if p.is_dir()]]:
  for parent,dirs,files in os.walk(root):
   dirs[:]=[n for n in dirs if n not in skip and (Path(parent)/n).resolve()!=OUT.resolve()]
   for name in files:
    if name.startswith('~$'):continue
    p=Path(parent)/name
    if OUT in p.parents:continue
    paths.add(p)
 paths.add(PLAN)
 rows=[];start=time.perf_counter()
 for p in sorted(paths):rows.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256=sha(p)))
 dump(OUT/'source_sha256.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),scope='All pre-existing files in the local reproducibility Git repository and 4.1–4.7/reply delivery directories; scientific caches included',excluded_directory_names=sorted(skip),files=rows,hash_seconds=time.perf_counter()-start))
 with (OUT/'audit/source_sha256.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 old=json.loads((REV/'reviewer_4_2/00_protocol_and_input_audit/source_records/archive/exact_dp_solution.json').read_text(encoding='utf-8-sig'))['scenarios']
 ranking=sorted([(int(s),float(v['exact_objective'])) for s,v in old.items()],key=lambda x:(x[1],x[0]))
 selected=[ranking[i][0] for i in [0,4,9]]
 paths4=json.loads((REV/'reviewer_4_2/02_original_method_path_reevaluation/frozen_paths.json').read_text(encoding='utf-8-sig'))
 records=[]
 for sid in range(1001,1011):
  proposed=next(r for r in paths4 if r['scenario_id']==sid and r['label']=='Proposed_B256')
  ref=old[str(sid)]
  assert proposed['roads']==ref['candidate_roads']
  for label,seq in [('full_method',proposed['sequence']),('exact_DP_original_rho1',ref['optimal_sequence'])]:
   assert len(seq)==10 and set(seq)==set(proposed['roads'])
   records.append(dict(scenario_id=sid,method=label,roads=proposed['roads'],sequence=seq,source='4.2 accepted original fixed paths / original archived exact solution'))
 dump(OUT/'audit/frozen_paths.json',records)
 protocol=dict(status='FROZEN_BEFORE_NEW_DEMAND_UE',created_utc=datetime.now(timezone.utc).isoformat(),output_root=str(OUT),local_authority='4.2 accepted source/path solver and original frozen 1001–1010; public repository used as output Git root and provenance comparator only',solver_source=str(BASE/'code/ue_solver.py'),path_solver_source=str(BASE/'code/path_ue.py'),network_root=str(BASE/'source_snapshot/code/model_backend'),physical_inputs=str(BASE/'inputs/historical_1001_1010.csv'),highprecision_table_root=str(REV/'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables'),scenario_ids=list(range(1001,1011)),demand_multipliers=[1.0,.75,.5],UE_tolerance=1e-9,max_outer=20000,solver='unchanged frozen solve_paths; cold initialization for each unique state',threads=1,CPU_affinity=[0],capacity_BPR_flood_changes=False,weighted_stages=list(range(10)),terminal_stage=10,terminal_weight=0,representative_selection='Rank 1,5,10 by ORIGINAL archived rho=1 Jstar, ties scenario ID, before any new-demand results',ranking=[dict(rank=i+1,scenario_id=s,Jstar_original=v,selected=s in selected) for i,(s,v) in enumerate(ranking)],representative_scenarios=selected,representative_demand_tables=[dict(scenario_id=s,rho=r,unique_masks=1024) for s in selected for r in [.75,.5]],diagnostic_stages=[0,1,3,5,7,9,10],methods=['full_method','exact_DP_original_rho1'],Greedy_availability='No accepted 1001–1010 Greedy paths located. 4.1 confirmatory Greedy results are for 3001–3030 and cannot substitute for original scenarios.',normalization='Independently solve dry TSTT0(rho) for every rho; never use a rho=1 denominator at lower demand',old_cache_policy='Never open old cache databases. Read immutable accepted CSV cost tables only; new cache includes full context and preserves flow vectors.',cache_key_fields=['scenario_id','rho','UE_tolerance','solver_sha256','model_sha256','physical_state_sha256','road_bit_order_sha256','subset_mask','OD_sha256'],comparisons='Post-hoc demand sensitivity and fixed-path transfer, not new confirmatory evidence or recalibrated surrogate performance',precision_comparison=dict(archived_FW_RG=.0005,accepted_path_RG=1e-9,empirical_kappa=2.816128890834728e-7,not_error_bound=True),validation_thresholds=dict(flow_balance_max_abs=1e-5,independent_RG_max=1e-9,finite=True,all_528_positive_ODs_reachable=True,archive_same_solver_state_relative_check=2.816128890834728e-7,DP_relative_reconciliation=1e-12),no_retraining=True,no_algorithm_search=True,no_new_flood=True)
 dump(OUT/'run_manifest.json',protocol)
 dump(OUT/'audit/prospective_freeze.json',dict(run_manifest_sha256=sha(OUT/'run_manifest.json'),frozen_paths_sha256=sha(OUT/'audit/frozen_paths.json'),instruction_sha256=sha(PLAN),sources_sha256_manifest_sha256=sha(OUT/'source_sha256.json')))
 print(json.dumps(dict(frozen_files=len(rows),protected_GB=sum(r['size_bytes'] for r in rows)/1e9,representatives=selected,ranking=ranking,Git_commit=events['commit']['stdout'].strip()),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
