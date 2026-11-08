"""Reconstruct selection rules and freeze all sets/states before new UE or DP."""
from common55 import *
import os,datetime,subprocess,platform
def main():
 if (OUT/'run_manifest.json').exists():raise SystemExit('Already frozen; do not regenerate.')
 checks=[]
 def ck(name,ok,actual='',expected='',evidence=''):
  checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected,evidence=str(evidence)))
  if not ok:
   dump(OUT/'audit/input_validation.json',dict(status='FAIL',checks=checks));raise RuntimeError('INPUT_MISMATCH '+name)
 freeze=js(SEL/'01_road_selection/candidate_road_selection_freeze.json')
 critical=[PHYS,PRE,SEL/'01_road_selection/final_scenarios.json',SEL/'01_road_selection/candidate_road_selection_audit.csv',SEL/'01_road_selection/candidate_road_selection_freeze.json',SEL/'frozen_inputs/formal_code/select_final_recoverable_roads.py',HOME/'day1_final_untouched_scenarios_v1.0/final_scenario_summary.csv',BASE/'code/ue_solver.py',BASE/'code/path_ue.py',REV/'reviewer_4_2/completion_check.json',REV/'reviewer_4_2/02_original_method_path_reevaluation/frozen_paths.json',REPO/'revision_R1/comment5_2/Table_terminal_residual.csv',REPO/'revision_R1/comment5_2/unit_validation.json']
 critical += [NETROOT/'data_src/SiouxFalls_flood_benchmark/processed'/f for f in ['directed_links.csv','od_long.csv']]
 critical += [REV/f'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables/scenario_{sid}_path_solver_1e9_1024_states.csv.gz' for sid in range(1001,1011)]
 critical += [BASE/f'development/legacy_precision/scenario_{sid}/exact_solution.json' for sid in range(1001,1011)]
 for p,key in [(PHYS,'scenario_physical_sha256'),(PRE,'surrogate_preprocessor_sha256'),(critical[2],'final_scenarios_sha256'),(critical[3],'candidate_road_selection_audit_sha256')]:ck('original_selection_freeze_'+key,sha(p)==freeze[key],sha(p),freeze[key],p)
 ck('4_2_numerical_authority',js(REV/'reviewer_4_2/completion_check.json')['G1']=='PASS',True,True)
 metadata=js(critical[2])['scenarios'];original={r['scenario_id']:r for r in metadata};physical=read(PHYS);pre=js(PRE);audit=read(critical[3]);summary=read(critical[6]);full=js(critical[10])
 flow=np.array(pre['baseline_flow']);between=np.array(pre['betweenness']);ck('frozen_static_metrics_38',len(flow)==len(between)==38 and np.isfinite(flow).all() and np.isfinite(between).all(),len(flow),38)
 # Verify read-only formal copies; no public metric recomputation/inference.
 ck('formal_preprocessor_snapshot_identity',sha(PRE)==sha(BASE/'source_snapshot/surrogate/final_ensemble/preprocessor_v2.json'),sha(PRE),sha(BASE/'source_snapshot/surrogate/final_ensemble/preprocessor_v2.json'))
 links=read(critical[13]);od=read(critical[14]);ck('network_38_roads_76_arcs',len(links)==76 and links.physical_link_id.nunique()==38,len(links),76);ck('OD_fixed',float(od.demand.sum())==Q and (od.demand>0).sum()==528,float(od.demand.sum()),Q)
 rules=[];portfolios=[];metrics=[];scenarios=[]
 expected=[11,10,12,11,12,10,11,12,11,10]
 # Everything below uses only pre-flood metrics and scenario definitions, no UE outcome.
 for sid in range(1001,1011):
  p=physical[physical.scenario_id==sid].sort_values('physical_link_id').copy();ck(f'38_physical_rows_{sid}',len(p)==38 and p.physical_link_id.tolist()==list(range(1,39)),len(p),38)
  p['physical_flow']=flow;p['betweenness']=between;f=p[p.is_closed==1].copy();F=f.physical_link_id.astype(int).tolist();n=len(F)
  ck('closed_count_'+str(sid),n==expected[sid-1001],n,expected[sid-1001]);ck('closed_summary_'+str(sid),n==int(summary.loc[summary.scenario_id.eq(sid),'closed_physical_links'].iloc[0]),n,n)
  ck('closed_metadata_'+str(sid),F==original[sid]['initially_closed_roads'],F,original[sid]['initially_closed_roads'])
  f['flow_score']=(n-f.physical_flow.rank(method='min',ascending=False))/(n-1);f['betweenness_score']=(n-f.betweenness.rank(method='min',ascending=False))/(n-1);f['combined_score']=.5*(f.flow_score+f.betweenness_score)
  ranked=f.sort_values(['combined_score','physical_flow','betweenness','physical_link_id'],ascending=[False,False,False,True],kind='mergesort');A0=ranked.head(10).physical_link_id.astype(int).tolist()
  ck('original_A0_order_'+str(sid),A0==original[sid]['selected_recoverable_roads'],A0,original[sid]['selected_recoverable_roads'])
  ck('4_2_bit_order_'+str(sid),all(r['roads']==A0 for r in full if r['scenario_id']==sid),A0,'4.2 frozen paths')
  archived=audit[(audit.scenario_id==sid)&audit.eligible_initially_closed].set_index('physical_link_id')
  compare=f.set_index('physical_link_id').sort_index();archived=archived.sort_index()
  for name in ['physical_flow','betweenness','flow_score','betweenness_score','combined_score']:
   err=float(abs(compare[name]-archived[name]).max());ck(f'original_metric_{sid}_{name}',err<=1e-12,err,'<=1e-12',critical[3])
  for i,r in enumerate(ranked.itertuples()):metrics.append(dict(scenario_id=sid,road_id=int(r.physical_link_id),initial_depth_m=float(r.depth_m),baseline_flow=float(r.physical_flow),betweenness=float(r.betweenness),flow_score=float(r.flow_score),betweenness_score=float(r.betweenness_score),combined_score=float(r.combined_score),original_combined_rank=i+1,selected_A0=i<10))
  A1=f.sort_values(['physical_flow','betweenness','physical_link_id'],ascending=[False,False,True],kind='mergesort').head(10).physical_link_id.astype(int).tolist()
  A2=f.sort_values(['betweenness','physical_flow','physical_link_id'],ascending=[False,False,True],kind='mergesort').head(10).physical_link_id.astype(int).tolist()
  labels=[('A0','original_50_50',A0),('A1','flow_only',A1),('A2','betweenness_only',A2)];swap=None
  if n>10 and set(A1)==set(A0) and set(A2)==set(A0):
   new=int(f[~f.physical_link_id.isin(A0)].sort_values(['depth_m','physical_link_id'],ascending=[False,True],kind='mergesort').physical_link_id.iloc[0]);old=A0[-1];A3=[e for e in A0 if e!=old]+[new];labels.append(('A3','diagnostic_one_swap',A3));swap=dict(road_in=new,road_out=old)
  dedup={}
  for label,name,E in labels:
   ck(f'valid_selected_set_{sid}_{label}',len(E)==10 and len(set(E))==10 and set(E)<=set(F),E,'10 unique initially closed roads')
   key=tuple(sorted(E))
   if key not in dedup:
    pid=f'{sid}_P{len(dedup):02d}';dedup[key]=pid
    portfolios.append(dict(portfolio_id=pid,scenario_id=sid,road_bit_order=A0 if label=='A0' else sorted(E),selected_roads_sorted=sorted(E),selected_physical_mask=pmask(E),original=label=='A0',rule_labels=[label],remaining_closed_ids=sorted(set(F)-set(E)),roads_in=sorted(set(E)-set(A0)),roads_out=sorted(set(A0)-set(E)),overlap_A0=len(set(E)&set(A0))))
   else:
    pid=dedup[key];next(x for x in portfolios if x['portfolio_id']==pid)['rule_labels'].append(label)
   rules.append(dict(scenario_id=sid,label=label,rule=name,portfolio_id=pid,selected_roads_sorted=json.dumps(sorted(E)),rule_ranked_selected=json.dumps(E),same_as_original=set(E)==set(A0),same_actual_set_as_prior_label=any(x['scenario_id']==sid and x['portfolio_id']==pid for x in rules),remaining_closed_ids=json.dumps(sorted(set(F)-set(E))),roads_in=json.dumps(sorted(set(E)-set(A0))),roads_out=json.dumps(sorted(set(A0)-set(E))),initial_closed_count=n,no_alternative_set=n==10,diagnostic_only=label=='A3'))
  wet=p[(p.is_closed==0)&p.is_wet.eq(1)&p.free_flow_time_multiplier.gt(1)].physical_link_id.astype(int).tolist()
  scenarios.append(dict(scenario_id=sid,initially_closed_roads=F,n_closed=n,original_roads=A0,unique_portfolios=len(dedup),A3_swap=swap,wet_open_affected_roads=wet,scenario_summary_hashes={k:str(summary.loc[summary.scenario_id.eq(sid),k].iloc[0]) for k in ['depth_sha256','closed_mask_sha256','scenario_sha256']}))
 # Full union dedup by scenario + unordered restored physical road set, independent of portfolio.
 requested={};channels=[]
 for p in portfolios:
  for mask in range(1024):
   phys=submask(p['road_bit_order'],mask);key=(p['scenario_id'],phys)
   requested.setdefault(key,dict(scenario_id=key[0],restored_physical_mask=phys,restored_ids=json.dumps(restored(phys)),uses_DP=True,uses_allclosed_counterfactual=False,portfolio_channel_count=0,source='new_UE'))['portfolio_channel_count']+=1
   channels.append(dict(portfolio_id=p['portfolio_id'],scenario_id=p['scenario_id'],subset_mask=mask,restored_physical_mask=phys))
 for sc in scenarios:
  key=(sc['scenario_id'],pmask(sc['initially_closed_roads']))
  row=requested.setdefault(key,dict(scenario_id=key[0],restored_physical_mask=key[1],restored_ids=json.dumps(restored(key[1])),uses_DP=False,uses_allclosed_counterfactual=True,portfolio_channel_count=0,source='new_UE'));row['uses_allclosed_counterfactual']=True
 for sc in scenarios:
  for mask in range(1024):
   key=(sc['scenario_id'],submask(sc['original_roads'],mask));row=requested[key];row['source']='accepted_4_2';row['original_subset_mask']=mask
 states=list(requested.values());states.sort(key=lambda r:(r['scenario_id'],r['restored_physical_mask']))
 for i,r in enumerate(states):r['task_id']=i
 newDP=sum(r['source']=='new_UE' and r['uses_DP'] for r in states);newCF=sum(r['source']=='new_UE' and not r['uses_DP'] for r in states)
 save(OUT/'Table_selection_rules_all10.csv',rules);save(OUT/'raw/selection_manifest.csv',metrics);save(OUT/'raw/portfolio_state_mapping.csv',channels);save(OUT/'unique_requested_states.csv',states)
 save(OUT/'Table_unique_portfolios.csv',[{**p,**{k:json.dumps(v) for k,v in p.items() if isinstance(v,list)}} for p in portfolios])
 save(OUT/'audit/scenario_closed_and_wet_audit.csv',[{**s,**{k:json.dumps(v) for k,v in s.items() if isinstance(v,(list,dict))}} for s in scenarios])
 ck('three_no_alternative_scenarios',[s['scenario_id'] for s in scenarios if s['n_closed']==10]==[1002,1006,1010],[s['scenario_id'] for s in scenarios if s['n_closed']==10],[1002,1006,1010])
 if newDP+newCF>6000:
  dump(OUT/'audit/input_validation.json',dict(status='PREFLIGHT_BLOCKED',reason='More than6000 new unique states',new_DP=newDP,new_counterfactual=newCF,checks=checks));raise SystemExit('PREFLIGHT_BLOCKED no UE authorized beyond6000')
 # Snapshot all old sources and every earlier 5.2/5.4 output, never old DB writes.
 prior=js(REPO/'revision_R1/comment5_4/source_sha256.json');paths={Path(x['path']) for x in prior['files']};paths.update(critical);paths.add(Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Comment5.5_Codex_执行指令.md'))
 exclude={'.git','__pycache__','runtime_deps','runtime_cache'}
 for root in (REPO,REV):
  for directory,dirs,files in os.walk(root):
   parent=Path(directory);dirs[:]=[d for d in dirs if d not in exclude and (parent/d).resolve()!=OUT.resolve()]
   if parent.resolve()==OUT.resolve():dirs[:]=[];continue
   paths.update(parent/f for f in files)
 for sibling in ['comment5_2','comment5_4']:paths.update(p for p in (REPO/'revision_R1'/sibling).rglob('*') if p.is_file())
 sources=[]
 for i,p in enumerate(sorted(paths,key=str)):
  sources.append(dict(path=str(p),sha256=sha(p),size_bytes=p.stat().st_size))
  if i and i%5000==0:print('source freeze',i,flush=True)
 bypath={r['path']:r['sha256'] for r in sources};ck('prior_frozen_sources_still_identical',all(bypath[x['path']]==x['sha256'] for x in prior['files']),True,True)
 dump(OUT/'audit/source_sha256.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='All previous source paths plus repository/返稿 sources and every5.2/5.4 output including caches; no new directory',files=sources))
 solver_version=digest(dict(ue_solver=sha(BASE/'code/ue_solver.py'),path_ue=sha(BASE/'code/path_ue.py'),links=sha(critical[13]),OD=sha(critical[14]),tol=TARGET,max_outer=MAX_OUTER))
 man=dict(status='FROZEN_BEFORE_NEW_UE_OR_DP',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scenario_ids=list(range(1001,1011)),scenarios=scenarios,portfolios=portfolios,rule_definitions=dict(A0='min descending ranks normalized within initial closed set,0.5/0.5; score desc,flow desc,betweenness desc,ID asc',A1='flow desc,betweenness desc,ID asc',A2='betweenness desc,flow desc,ID asc',A3='Only if >10 closed and A1=A2=A0: add deepest excluded closed road(tie ID asc), remove last selected in original combined ranking'),seeds='none; deterministic',DP_tie='minimum float objective, tie ascending physical ID of last road; no tolerance-based replacement',n_original_portfolios=10,n_unique_portfolios=len(portfolios),n_unique_alternatives=len(portfolios)-10,new_DP_states=newDP,new_allclosed_states=newCF,new_states_total=newDP+newCF,unique_requested_states=len(states),accepted_4_2_reused=sum(r['source']=='accepted_4_2' for r in states),state_identity='scenario + actual restored physical road unordered mask + full model/OD/tolerance context; excludes portfolio identity',critical_sources=[dict(path=str(p),sha256=sha(p)) for p in critical],frozen_generated_files=[dict(path=str(p),sha256=sha(p)) for p in [OUT/'unique_requested_states.csv',OUT/'raw/portfolio_state_mapping.csv',OUT/'Table_selection_rules_all10.csv',OUT/'Table_unique_portfolios.csv',OUT/'raw/selection_manifest.csv']],frozen_code=[dict(path=str(p),sha256=sha(p)) for p in sorted((OUT/'scripts').glob('*.py'))],solver_version=solver_version,UE_tolerance=TARGET,max_outer=MAX_OUTER,initialization='cold per new physical state; single process/core; no relaxed tolerance/fallback',source_snapshot_sha256=sha(OUT/'audit/source_sha256.json'),TSTT0_raw=T0,dry_baseline_note='Original4.2 denominator preserved; 5.2 recomputed dry denominator differs3.3178e-8 relative; physical TSTT/ATT match directly, do not substitute5.2 normalized ratio',Q=Q,raw_time_to_hours=.01,weighted_stages=list(range(10)),terminal_weight=0,model_parameter_changes=False,validation=dict(archive_RG=TARGET,new_RG=TARGET,independent_RG=TARGET*(1+1e-6),flow_balance=1e-5,DP_relative=1e-12),environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform()))
 dump(OUT/'run_manifest.json',man);dump(OUT/'audit/prospective_freeze.json',dict(run_manifest_sha256=sha(OUT/'run_manifest.json'),requested_states_sha256=sha(OUT/'unique_requested_states.csv'),source_manifest_sha256=sha(OUT/'audit/source_sha256.json')))
 git={}
 for label,args in [('status',['status','--porcelain=v1','-z','--untracked-files=all']),('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('tracked_diff',['diff','--binary','HEAD'])]:
  b=subprocess.check_output(['git','-C',str(REPO),*args]);(OUT/'audit'/f'git_before_{label}.bin').write_bytes(b);git[label]=b.decode('utf-8').split('\0') if label=='status' else b.decode('utf-8')
 dump(OUT/'audit/git_before.json',git);dump(OUT/'audit/input_validation.json',dict(status='PASS',checks=checks,checks_passed=len(checks),checks_total=len(checks),new_DP_states=newDP,new_counterfactual_states=newCF,n_unique_portfolios=len(portfolios),new_UE_started=False,DP_started=False))
 print('PREFLIGHT PASS',len(portfolios),'unique portfolios;',newDP,'new DP states +',newCF,'counterfactual;',len(sources),'protected files',flush=True)
if __name__=='__main__':main()
