from common import *
import sqlite3,inspect
from models.flood_mapping import disruption_from_depth
from ue_solver import Network
def main():
 init();assert not (OUT/'run_manifest.json').exists(),'Already frozen'
 checks=[]
 def ck(name,ok,actual=None,expected=None):
  checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected))
  if not ok:dump(OUT/'audit/input_validation.json',dict(status='PREFLIGHT_BLOCKED',checks=checks));raise RuntimeError('PREFLIGHT_BLOCKED: '+name)
 parent_accept=js(PARENT/'final_validation.json');ck('parent_accepted',parent_accept['status']=='PASS',parent_accept['status'],'PASS')
 ck('parent_output_manifest_SHA',sha(PARENT/'output_manifest.csv')==(PARENT/'output_manifest.sha256').read_text().split()[0])
 for row in read(PARENT/'output_manifest.csv').itertuples():ck('parent_frozen_'+row.path,sha(PARENT/row.path)==row.sha256)
 # Snapshot all pre-existing scientific files, including the full parent results
 # and SQLite; only regenerable runtime caches/dependencies are excluded.
 paths=set();critical=[PHYS,PRE,GEN,NETROOT/'models/flood_mapping.py',SEL/'final_scenarios.json',R42/'00_protocol_and_input_audit/S0_input_manifest.csv',R42/'completion_check.json',R42/'01_legacy_ue_state_comparison/independent_references.json',PARENT/'run_manifest.json',PARENT/'final_validation.json',PARENT/'raw/variant_physical_fields.csv',PARENT/'raw/logical_state_mapping.csv',PARENT/'raw/DP_all_states.csv',PARENT/'cache/sensitivity_states.sqlite3',BASE/'code/ue_solver.py',BASE/'code/path_ue.py',Path('C:/Users/Wuzeqian.PC-20220914MSMS/Downloads/Reviewer2_Comment3_补充实验_Codex执行指令.md')]
 critical += [TABLES/f'scenario_{sid}_path_solver_1e9_1024_states.csv.gz' for sid in range(1001,1011)]+[NETROOT/'data_src/SiouxFalls_flood_benchmark/processed'/n for n in ['directed_links.csv','od_long.csv','physical_links.csv']]
 for root in [REPO,REV]:
  for directory,dirs,files in os.walk(root):
   p=Path(directory);dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','runtime_deps','runtime_cache'] and (p/d).resolve()!=OUT.resolve()]
   if p.resolve()==OUT.resolve():dirs[:]=[];continue
   paths.update(p/n for n in files)
 paths.update(critical);records=[]
 for i,p in enumerate(sorted(paths,key=str)):
  records.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
  if i%10000==0:print('Source snapshot',i,'/',len(paths),flush=True)
 dump(OUT/'audit/source_sha256.json',dict(files=records,git=gitstate(),critical=[dict(path=str(p),sha256=sha(p)) for p in critical]))
 binding=read(R42/'00_protocol_and_input_audit/S0_input_manifest.csv')
 for name in ['ue_solver.py','path_ue.py']:
  r=binding[binding.absolute_path.str.endswith('\\'+name)].iloc[0];ck('4.2_solver_'+name,sha(BASE/'code'/name)==r.sha256,sha(BASE/'code'/name),r.sha256)
 parentman=js(PARENT/'run_manifest.json');ck('same_UE_settings',parentman['RG']==TARGET and parentman['max_outer']==MAX_OUTER and parentman['T0_raw']==T0 and parentman['Q']==Q)
 net=Network(NETROOT);ck('network_demand',len(net.links)==76 and net.links.physical_link_id.nunique()==38 and float(net.od.sum())==Q and np.count_nonzero(net.od>0)==528)
 ck('BPR_original',np.all(net.alpha==.15) and np.all(net.links.bpr_beta==4))
 ck('mapping_capacity_default',inspect.signature(disruption_from_depth).parameters['capacity_reduction'].default is False)
 authority=read(PHYS);public=read(DATA/'final_scenarios_physical_links.csv');E0=originals();fields=[];plans=[];preflight=[];base=[];reuse={}
 oldfields=read(PARENT/'raw/variant_physical_fields.csv');oldmapping=read(PARENT/'raw/logical_state_mapping.csv');oldcost=read(PARENT/'raw/DP_all_states.csv')
 oldDB=sqlite3.connect(f'file:{(PARENT/"cache/sensitivity_states.sqlite3").as_posix()}?mode=ro',uri=True)
 for key,payload in oldDB.execute('SELECT state_key,payload FROM states'):
  r=json.loads(payload);reuse[key]=dict(source='accepted_R2C3',tstt_raw=r['tstt_raw'],ue_gap=r['ue_gap'],source_variant_id=r['variant_id'],source_subset_mask=r['subset_mask'])
 originalrefs=js(R42/'01_legacy_ue_state_comparison/independent_references.json');reuse_checks=[]
 for sid in range(1001,1011):
  p0=authority[authority.scenario_id.eq(sid)].sort_values('physical_link_id').reset_index(drop=True);pub=public[public.scenario_id.eq(sid)].sort_values('physical_link_id');E=E0[sid]
  ck(f'{sid}_original_depth',np.array_equal(p0.depth_m,pub.depth_m));ck(f'{sid}_original_E',E==selection(p0))
  t=oldtable(sid).sort_values('subset_mask');ck(f'{sid}_original_1024_RG',len(t)==1024 and t.relative_gap.max()<=TARGET)
  j,seq,_,_=forward_dp(t.loss.to_numpy(float),E);ck(f'{sid}_original_DP',abs(j-originalrefs[str(sid)]['star_new'])<=1e-12)
  for mask in range(1024):
   key,_,_,_=state_context(p0,E,mask,net);reuse.setdefault(key,dict(source='accepted_4_2',tstt_raw=float(t.tstt.iloc[mask]),ue_gap=float(t.relative_gap.iloc[mask]),source_variant_id=f'{sid}_depth_1.0',source_subset_mask=mask))
  for rho in [.90,.95,1.]:
   p=p0.copy();d=p0.depth_m.to_numpy(float)*rho
   for k,v in disruption_from_depth(d,closure_depth_m=.30).items():p[k]=v
   p['is_wet']=(d>0).astype(int);vid=f'{sid}_depth_{rho}';p['variant_id']=vid;p['scenario_id']=sid;p['factor']='depth';p['level']=rho
   reach,bad=reachability(p);same=np.array_equal(p.is_closed.to_numpy(),p0.is_closed.to_numpy());legal=set(E)<=set(p.loc[p.is_closed.eq(1),'physical_link_id'].astype(int))
   ck(vid+'_preflight_expected_scope',reach['OD_reachable'] and reach['physical_connected'] and same and legal,dict(**reach,same_mask=bool(same),E_legal=legal),'same mask; 528 OD reachable; original ten roads closed')
   row=dict(variant_id=vid,scenario_id=sid,factor='depth',level=rho,road_bit_order=E,original_E_legal=legal,same_original_mask=bool(same),closed_count=int(p.is_closed.sum()),wet_count=int(p.is_wet.sum()),physical_depth_sha256=hashlib.sha256(d.astype('<f8').tobytes()).hexdigest(),full_mapping_sha256=hashlib.sha256(p[['depth_m','is_closed','speed_ratio','free_flow_time_multiplier','capacity_factor']].to_numpy('<f8').tobytes()).hexdigest(),validity_status='VALID',invalid_reason='',n_logical_states=1024,**reach)
   fields.append(p);plans.append(row);preflight.append(row)
   if rho==.95 and sid in [1006,1003,1008]:
    oldp=oldfields[oldfields.variant_id.eq(vid)].sort_values('physical_link_id');oldplan=next(r for r in parentman['table_plan'] if r['variant_id']==vid)
    ck(vid+'_full_fields_match_parent',all(np.array_equal(p[c].to_numpy(),oldp[c].to_numpy()) for c in ['depth_m','is_closed','speed_ratio','free_flow_time_multiplier','capacity_factor']))
    ck(vid+'_bit_order_parent',oldplan['road_bit_order']==E)
    gm=oldmapping[oldmapping.variant_id.eq(vid)].set_index('subset_mask');gc=oldcost[oldcost.variant_id.eq(vid)].set_index('subset_mask')
    for mask in range(1024):
     key,_,_,_=state_context(p,E,mask,net);dbrow=oldDB.execute('SELECT payload,length(flow) FROM states WHERE state_key=?',(key,)).fetchone();r=json.loads(dbrow[0]) if dbrow else None
     ok=bool(dbrow and key==gm.loc[mask,'state_key']==gc.loc[mask,'state_key'] and r['validation_passed'] and r['ue_gap']<=TARGET and r['tstt_raw']==float(gc.loc[mask,'tstt_raw']) and dbrow[1]==76*8)
     reuse_checks.append(dict(variant_id=vid,subset_mask=mask,state_key=key,full_context_and_cost_match=ok,ue_gap=r['ue_gap'] if r else None))
     ck(vid+f'_reuse_mask_{mask}',ok)
 oldDB.close();save(OUT/'audit/R2C3_reuse_identity_checks.csv',reuse_checks);save(OUT/'raw/variant_physical_fields.csv',pd.concat(fields,ignore_index=True));save(OUT/'audit/all10_depth_preflight.csv',[{**r,'road_bit_order':canonical(r['road_bit_order'])} for r in preflight])
 mapping=[];tasks={}
 for plan in plans:
  p=next(g for g in fields if g.variant_id.iloc[0]==plan['variant_id']);E=plan['road_bit_order']
  for mask in range(1024):
   key,_,_,_=state_context(p,E,mask,net);known=reuse.get(key)
   r=dict(variant_id=plan['variant_id'],scenario_id=plan['scenario_id'],factor='depth',level=plan['level'],subset_mask=mask,restored_ids=canonical([r for i,r in enumerate(E) if mask&(1<<i)]),physical_depth_sha256=plan['physical_depth_sha256'],full_mapping_sha256=plan['full_mapping_sha256'],state_key=key,source=known['source'] if known else 'new_UE')
   mapping.append(r);tasks.setdefault(key,{**r,**(known or {})})
 save(OUT/'raw/logical_state_mapping.csv',mapping);save(OUT/'raw/unique_state_requests.csv',list(tasks.values()));dump(OUT/'raw/table_plan.json',plans)
 new=sum(r['source']=='new_UE' for r in tasks.values());ck('new_state_budget',new<=18500 and new<=17*1024,new,'<=17408, hard cap18500')
 ck('three_parent_tables_reused',len(reuse_checks)==3072 and all(r['full_context_and_cost_match'] for r in reuse_checks),len(reuse_checks),3072)
 dump(OUT/'audit/input_validation.json',dict(status='PASS',checks=checks));dump(OUT/'audit/parent_acceptance_binding.json',dict(final_validation_sha256=sha(PARENT/'final_validation.json'),output_manifest_sha256=sha(PARENT/'output_manifest.csv'),parent_status='PASS',reused_parent_tables=3,reused_parent_states=3072))
 (OUT/'audit/input_audit.md').write_text('# 输入与复用审计\n\n来源见source_sha256.json。以原4.2高精度solver与原十路bit顺序为权威。30个深度条件均重新映射并验证与原关闭mask相同、528正OD可达，20个扰动使用原十路恢复集。R2C3三张0.95表已逐状态比较完整38路字段、有效网络key、bit顺序、OD/求解器/精度/分母身份、CSV成本与只读SQLite流量长度；3072项通过。\n\n阈值证明使用closed = depth >= threshold以及开放道路速度仅依赖depth的原映射，实际端点映射测试另存。\n\n真实独立新UE状态预算='+str(new)+'，最多18500；所有原目录只读。',encoding='utf-8')
 frozen=[dict(path=str(p),sha256=sha(p)) for p in sorted((OUT/'scripts').glob('*.py'))]
 man=dict(status='FROZEN_BEFORE_FIRST_NEW_UE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),git=gitstate(),scenario_ids=list(range(1001,1011)),depth_multipliers=[.90,.95],baseline=1.,T0_raw=T0,Q=Q,ATT0_min=ATT0,RG=TARGET,max_outer=MAX_OUTER,new_unique_states=new,hard_cap_new_UE=18500,reused_parent_tables=3,logical_tables_total=30,perturbed_tables_total=20,new_tables=17,unique_states_total=len(tasks),table_plan=plans,critical_sources=js(OUT/'audit/source_sha256.json')['critical'],frozen_scripts=frozen,logical_mapping_sha256=sha(OUT/'raw/logical_state_mapping.csv'),unique_requests_sha256=sha(OUT/'raw/unique_state_requests.csv'),physical_fields_sha256=sha(OUT/'raw/variant_physical_fields.csv'),threshold_task_new_UE=0,threshold_tests='closed iff depth>=tau; np.nextafter strict endpoints; midpoint/baseline/.32 where inside; outsideOD only',near_tie_threshold='1e-12*max(1,abs(Jstar)) diagnostic only; strict DP uses lexicographic physical IDs for floating ties',DP_absolute_validation_tolerance=1e-12,cache='isolated extension SQLite, complete effective network/OD/BPR/solver/RG/max_outer/normalizer key, full depth/portfolio context in mapping',stage_weights='S0..S9 each1/10, S10 zero',optional_frozen_Full_transfer='Not requested; omitted to keep core fixed-DP transfer analysis bounded')
 dump(OUT/'run_manifest.json',man);dump(OUT/'audit/prospective_freeze.json',dict(run_manifest_sha256=sha(OUT/'run_manifest.json'),new_UE_calls_before_freeze=0));print('FROZEN',new,'new states; 3 parent tables matched; all20 perturbations valid',flush=True)
if __name__=='__main__':main()
