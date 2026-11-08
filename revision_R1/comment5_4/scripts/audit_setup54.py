"""Freeze inputs/configuration BEFORE reading optimization results. No UE imports."""
from pathlib import Path
import sys, os, json, hashlib, datetime, subprocess, platform
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
OUT = Path(__file__).resolve().parents[1]
REPO = OUT.parents[1]
REV = Path('E:/jcr2区意见/返稿')
BASE = REV/'4.1专项返修_20261026'
P52 = OUT.parent/'comment5_2'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    if (OUT/'run_manifest.json').exists():
        raise SystemExit('Manifest already frozen: reuse it, do not regenerate configurations.')
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    prior=json.loads((P52/'source_sha256.json').read_text(encoding='utf-8'))
    paths={Path(r['path']) for r in prior['files'] if Path(r['path']).is_file()}
    # Re-enumerate source repositories, including every 5.2 file and its caches.
    excluded={'.git','__pycache__','runtime_cache','runtime_deps'}
    for root in (REPO,REV):
        for dirname,dirs,files in os.walk(root):
            parent=Path(dirname)
            dirs[:]=[d for d in dirs if d not in excluded and (parent/d).resolve()!=OUT.resolve()]
            if parent.resolve()==OUT.resolve(): dirs[:]=[];continue
            paths.update(parent/f for f in files)
    paths.update(p for p in P52.rglob('*') if p.is_file())
    instruction=Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Comment5.4_Codex_执行指令.md')
    paths.add(instruction)
    records=[]
    for i,p in enumerate(sorted(paths,key=str)):
        records.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256=sha(p)))
        if i and i%5000==0: print('source hashes',i,flush=True)
    dump(OUT/'source_sha256.json',dict(created_utc=started,scope='All earlier 5.2 frozen source paths plus current repository/返稿 files; every comment5_2 file including caches; exclude new comment5_4 and dependency/generated cache directories outside 5.2',files=records))
    bypath={r['path']:r for r in records}
    prior_checks=[]
    for r in prior['files']:
        p=Path(r['path']); now=bypath.get(str(p))
        prior_checks.append(dict(path=str(p),previous_sha256=r['sha256'],current_sha256=now['sha256'] if now else '',matches=bool(now and now['sha256']==r['sha256'])))
    pd.DataFrame(prior_checks).to_csv(OUT/'audit/prior_5_2_source_hash_verification.csv',index=False)
    if not all(x['matches'] for x in prior_checks): raise SystemExit('Pre-existing source conflict vs 5.2 freeze. STOP.')
    # Read only road identity/depth, not numerical optimization results at this point.
    frozen_path=REV/'reviewer_4_2/02_original_method_path_reevaluation/frozen_paths.json'
    pathrecords=json.loads(frozen_path.read_text(encoding='utf-8'))
    roads={int(r['scenario_id']):r['roads'] for r in pathrecords}
    physical=BASE/'inputs/historical_1001_1010.csv'
    inputs=pd.read_csv(physical)
    configs=[];assignments=[]
    weights={'uniform':[1.]*10,'moderate':[.5,.75,.75,1,1,1,1,1.25,1.25,1.5], 'strong':[.25,.5,.5,.75,.75,1,1,1.5,1.75,2]}
    for sid in range(1001,1011):
        rs=roads[sid]; dmap=inputs[inputs.scenario_id==sid].set_index('physical_link_id').depth_m.to_dict()
        orders={'uniform':sorted(rs),'depth_rank':sorted(rs,key=lambda e:(dmap[e],e))}
        for suffix,seed in [('1',2026110201),('2',2026110202)]:
            orders['permutation_seed_'+suffix]=np.random.Generator(np.random.PCG64(seed)).permutation(sorted(rs)).tolist()
        for level,w in weights.items():
            for allocation in (['uniform'] if level=='uniform' else ['depth_rank','permutation_seed_1','permutation_seed_2']):
                order=orders[allocation]; mapping=dict(zip(order,w));config_id=f'{sid}_{level}_{allocation}'
                configs.append(dict(config_id=config_id,scenario_id=sid,level=level,allocation=allocation,assignment_order=order,durations_original_bit_order=[mapping[e] for e in rs],roads_original_bit_order=rs,road_duration_mapping=[{'road_id':e,'duration':mapping[e]} for e in sorted(rs)]))
                for bit,e in enumerate(rs):assignments.append(dict(config_id=config_id,scenario_id=sid,level=level,allocation=allocation,bit_index=bit,road_id=e,depth_m=dmap[e],duration=mapping[e],assignment_position=order.index(e),total_duration=sum(w)))
    critical=[physical,frozen_path,P52/'final_validation.json',P52/'unit_validation.json',P52/'raw/dry_baselines.csv',P52/'stage_metrics_all10.csv',P52/'raw/all_new_UE_open_arc_flows.csv.gz',BASE/'source_snapshot/code/model_backend/data_src/SiouxFalls_flood_benchmark/processed/od_long.csv',REV/'reviewer_4_2/completion_check.json',REV/'reviewer_4_2/00_protocol_and_input_audit/source_records/archive/exact_dp_solution.json']
    critical += [REV/f'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables/scenario_{sid}_path_solver_1e9_1024_states.csv.gz' for sid in range(1001,1011)]
    critical += [BASE/f'development/legacy_precision/scenario_{sid}/exact_solution.json' for sid in range(1001,1011)]
    manifest=dict(status='FROZEN_BEFORE_OPTIMIZATION_RESULT_READ',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),output_root=str(OUT),scenario_ids=list(range(1001,1011)),configs=configs,config_count=70,heterogeneous_count=60,independent_flood_scenarios=10,weights=weights,random_generator='NumPy Generator(PCG64)',seeds=[2026110201,2026110202],randomization_rule='Initialize each fixed seed separately for each scenario on sorted physical road IDs; same positional permutation across scenarios and across severity levels. No scenario-dependent seed adjustment.',tie_break='Exact floating objective minimum; ties use ascending physical ID of last action in forward recurrence, then predecessor rank. No tolerance-based replacement.',near_tie_reporting_relative=1e-12,validation_relative_tolerance=1e-12,original_dry_TSTT_raw=7480225.3449211195,Q=360600.,raw_time_to_hours=.01,allowed_new_UE_calls=0,allowed_model_predictions=0,allowed_training=0,algorithms=dict(forward='two-best distinct sequence subset DP; predecessor-state C',independent='reverse remaining-actions Bellman recurrence',small_tests='m1..7 exhaustive permutations with fixed deterministic costs'),absolute_metric='Duration-weighted average stage model-implied per-trip minutes; not engineering duration, realized cumulative delay or project cost',source_snapshot_sha256=sha(OUT/'source_sha256.json'),critical_sources=[dict(path=str(p),sha256=sha(p)) for p in critical],audit_code=[dict(path=str(p),sha256=sha(p)) for p in sorted((OUT/'scripts').glob('*.py'))],environment=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,executable=sys.executable),optional_OD=dict(scenarios=[1006,1003,1008],rho=1,stages=[0,5,9],policies=['full_method','exact_DP_original_rho1'],percentile='Smallest OD shortest-time value with demand-weighted CDF >= p',top10='Fractional-demand weighted upper-decile mean',method='Dijkstra on archived 5.2 congested open-arc times; no UE call'))
    dump(OUT/'run_manifest.json',manifest)
    pd.DataFrame(assignments).to_csv(OUT/'Table_duration_assignments.csv',index=False,float_format='%.17g')
    git={}
    for label,args in [('status',['status','--porcelain=v1','-z','--untracked-files=all']),('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('tracked_diff',['diff','--binary','HEAD'])]:
        b=subprocess.check_output(['git','-C',str(REPO),*args]);(OUT/'audit'/('git_before_'+label+'.bin')).write_bytes(b);git[label]=b.decode('utf-8').split('\0') if label=='status' else b.decode('utf-8')
    dump(OUT/'audit/git_before.json',git)
    print('FROZEN',len(records),'source files, 70 configurations; no optimization result read',flush=True)
if __name__=='__main__':main()
