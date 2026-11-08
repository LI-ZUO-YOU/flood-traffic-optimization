from common import *
import importlib.util
def main():
 init()
 if (OUT/'run_manifest.json').exists():raise RuntimeError('Already frozen; audit cannot overwrite manifest')
 critical=[PHYS,PRE,GEN,SEL/'final_scenarios.json',SEL/'candidate_road_selection_audit.csv',SEL/'candidate_road_selection_freeze.json',R42/'completion_check.json',R42/'01_legacy_ue_state_comparison/independent_references.json']
 critical += [DATA/n for n in ['final_scenarios_physical_links.csv','final_scenario_summary.csv','final_scenario_rejection_log.csv','scenario_generation_freeze_record.json']]
 critical += [NETROOT/'models'/n for n in ['flood_mapping.py','spatial_flood_field.py']]+[BASE/'code'/n for n in ['ue_solver.py','path_ue.py']]
 critical += [TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz' for sid in range(1001,1011)]
 critical += [NETROOT/'data_src/SiouxFalls_flood_benchmark/processed'/n for n in ['physical_links.csv','directed_links.csv','od_long.csv']]
 critical += [REPO/'code/final_pipeline'/n for n in ['generate_final_holdout.py','select_final_recoverable_roads.py']]
 critical += [Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer2_Comment3_Codex_执行指令.md')]
 # All old scientific sources in the repository and revision tree are protected,
 # including SQLite. Only runtime dependencies and regenerable code caches excluded.
 paths=set(critical)
 for root in [REPO,REV]:
  for directory,dirs,files in os.walk(root):
   p=Path(directory);dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','runtime_deps','runtime_cache'] and (p/d).resolve()!=OUT.resolve()]
   if p.resolve()==OUT.resolve():dirs[:]=[];continue
   paths.update(p/f for f in files)
 records=[]
 for i,p in enumerate(sorted(paths,key=str)):
  records.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
  if i%1000==0:print('Hash snapshot',i,'/',len(paths),flush=True)
 dump(OUT/'audit/source_sha256.json',dict(git=gitstate(),critical=[dict(path=str(p),sha256=sha(p)) for p in critical],files=records))
 p=read(PHYS);pub=read(DATA/'final_scenarios_physical_links.csv');refs=js(R42/'01_legacy_ue_state_comparison/independent_references.json');checks=[];rows=[]
 def ck(name,ok,actual,expected):checks.append(dict(check=name,pass_=bool(ok),actual=actual,expected=expected))
 ck('4.2 accepted',js(R42/'completion_check.json')['G1']=='PASS',js(R42/'completion_check.json')['G1'],'PASS')
 ck('formal generator identity',sha(GEN)==sha(REPO/'code/final_pipeline/generate_final_holdout.py'),sha(GEN),sha(REPO/'code/final_pipeline/generate_final_holdout.py'))
 freeze=js(SEL/'candidate_road_selection_freeze.json')
 for path,key in [(PHYS,'scenario_physical_sha256'),(PRE,'surrogate_preprocessor_sha256')]:ck(key,sha(path)==freeze[key],sha(path),freeze[key])
 for sid,E in originals().items():
  a=p[p.scenario_id.eq(sid)].sort_values('physical_link_id');b=pub[pub.scenario_id.eq(sid)].sort_values('physical_link_id');t=oldtable(sid);j,seq,_,_=forward_dp(t.sort_values('subset_mask').loss.to_numpy(float),E)
  ck(f'{sid} 38 depth authority',len(a)==38 and np.array_equal(a.depth_m,b.depth_m),float(np.max(abs(a.depth_m.to_numpy()-b.depth_m.to_numpy()))),0.)
  ck(f'{sid} selection',selection(a)==E,selection(a),E);ck(f'{sid} 1024 RG',len(t)==1024 and t.relative_gap.max()<=TARGET,float(t.relative_gap.max()),TARGET)
  ck(f'{sid} baseline DP',abs(j-refs[str(sid)]['star_new'])<=1e-12,j,refs[str(sid)]['star_new'])
  rows.append(dict(scenario_id=sid,closed=int(a.is_closed.sum()),wet=int(a.is_wet.sum()),roads=E,J_star=j,sequence=seq))
 save(OUT/'audit/baseline_recomputed.csv',[{**r,'roads':canonical(r['roads']),'sequence':canonical(r['sequence'])} for r in rows]);dump(OUT/'audit/input_validation.json',dict(status='PASS' if all(r['pass_'] for r in checks) else 'PREFLIGHT_BLOCKED',checks=checks))
 dump(OUT/'run_manifest_preflight.json',dict(status='INPUT_AUDIT_COMPLETE' if all(r['pass_'] for r in checks) else 'PREFLIGHT_BLOCKED',git=gitstate(),seed=2026080701,scenarios=list(range(1001,1011)),representatives=[1006,1003,1008],depth_levels=[.90,.95,1.,1.05,1.10],main_depth_levels=[.95,1.05],thresholds=[.28,.30,.32],correlations_km=[3.,6.],RG=TARGET,max_new_UE=13000,old_sources=len(records)))
 (OUT/'audit/input_audit.md').write_text('# 输入审计\n\n'+canonical(checks)+'\n\n以4.2已验收1024状态表和原冻结物理数据为权威。原始单位为车辆×0.01小时，T0='+str(T0)+'，Q=360600。\n公开副本仅用于交叉核对，未使用旧RG5e-4成本。容量默认仅关闭道路为0，开放湿路保持原容量。\n源文件和Git信息见source_sha256.json。',encoding='utf-8')
 assert all(r['pass_'] for r in checks),'PREFLIGHT_BLOCKED'
 print('Input audit PASS',len(records),flush=True)
if __name__=='__main__':main()
