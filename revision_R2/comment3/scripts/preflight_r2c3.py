from common import *
from ue_solver import Network
def main():
 init();assert not (OUT/'run_manifest.json').exists(),'Already frozen'
 assert js(OUT/'audit/input_validation.json')['status']=='PASS'
 records=js(OUT/'raw/variant_metadata.json');fields=read(OUT/'raw/variant_physical_fields.csv');original=read(PHYS);net=Network(NETROOT);E0=originals();reuse={}
 for sid in range(1001,1011):
  p=original[original.scenario_id.eq(sid)].sort_values('physical_link_id');t=oldtable(sid).set_index('subset_mask')
  for mask in range(1024):
   key,_,_,_=state_context(p,E0[sid],mask,net)
   if key in reuse:assert abs(reuse[key]['tstt_raw']-float(t.loc[mask,'tstt']))/float(t.loc[mask,'tstt'])<=1e-8
   reuse.setdefault(key,dict(source='accepted_4_2',scenario_id=sid,original_subset_mask=mask,tstt_raw=float(t.loc[mask,'tstt']),ue_gap=float(t.loc[mask,'relative_gap'])))
 plans=[];mapping=[];tasks={}
 for r in records:
  if r['scenario_id'] not in [1006,1003,1008]:continue
  factor=r['factor'];level=r['level']
  wanted=(factor=='depth' and level in [.95,1.,1.05]) or (factor=='threshold') or factor=='correlation'
  if not wanted:continue
  plan={**r,'n_logical_states':0,'execution':'SKIP_INVALID','why':r['invalid_reason']}
  if r['validity_status']=='VALID':
   plan.update(n_logical_states=1024,execution='UE_TABLE_OR_READONLY_REUSE',why='')
   p=fields[fields.variant_id.eq(r['variant_id'])].sort_values('physical_link_id');E=r['road_bit_order']
   for mask in range(1024):
    key,_,_,_=state_context(p,E,mask,net)
    row=dict(variant_id=r['variant_id'],scenario_id=r['scenario_id'],draw_index=r['draw_index'],factor=factor,level=level,subset_mask=mask,restored_ids=canonical([road for i,road in enumerate(E) if mask&(1<<i)]),physical_depth_sha256=r['physical_depth_sha256'],full_mapping_sha256=r['full_mapping_sha256'],state_key=key,source='accepted_4_2' if key in reuse else 'new_UE')
    mapping.append(row)
    if key not in tasks:tasks[key]={**row,**reuse.get(key,{})}
  plans.append(plan)
 new=sum(x['source']=='new_UE' for x in tasks.values());blocked=new>13000
 source=js(OUT/'audit/source_sha256.json')
 save(OUT/'raw/logical_state_mapping.csv',mapping);save(OUT/'raw/unique_state_requests.csv',list(tasks.values()));dump(OUT/'raw/table_plan.json',plans)
 code=[dict(path=str(p),sha256=sha(p)) for p in sorted((OUT/'scripts').glob('*.py'))]
 manifest=dict(status='PREFLIGHT_BLOCKED' if blocked else 'FROZEN_BEFORE_FIRST_NEW_UE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),git=gitstate(),representatives=[1006,1003,1008],scenarios=list(range(1001,1011)),design='OAT: frozen levels; original E preferred for depth/threshold; new original-rule E for CRN endpoints',seed=2026080701,CRN_replay=js(OUT/'audit/CRN_replay_validation.json'),depth_levels=[.9,.95,1.,1.05,1.1],depth_DP=[.95,1.05],thresholds=[.28,.30,.32],correlations_km=[3.,6.],T0_raw=T0,Q=Q,RG=TARGET,max_outer=MAX_OUTER,BPR_alpha=.15,beta=4,stage_weights='S0..S9 each1/10; S10 zero',capacity_reduction=False,cache_isolation='new SQLite only; effective network+OD+solver+RG+normalizer key; full factor/depth/restoration provenance in mapping',new_unique_states=new,unique_requested_states=len(tasks),logical_states=len(mapping),reused_unique_states=sum(x['source']=='accepted_4_2' for x in tasks.values()),valid_tables=sum(p['n_logical_states']==1024 for p in plans),invalid_tables=sum(not p['n_logical_states'] for p in plans),table_plan=plans,critical_sources=source['critical'],frozen_scripts=code,logical_mapping_sha256=sha(OUT/'raw/logical_state_mapping.csv'),unique_requests_sha256=sha(OUT/'raw/unique_state_requests.csv'),physical_fields_sha256=sha(OUT/'raw/variant_physical_fields.csv'))
 dump(OUT/'run_manifest.json',manifest);dump(OUT/'audit/prospective_freeze.json',dict(run_manifest_sha256=sha(OUT/'run_manifest.json'),new_UE_calls_before_freeze=0,reason='All representatives, levels, fields, E and states fixed before UE'))
 dump(OUT/'audit/preflight_validation.json',dict(status='PREFLIGHT_BLOCKED' if blocked else 'PASS',new_unique_states=new,limit=13000,planned_valid_tables=manifest['valid_tables'],planned_invalid_tables=manifest['invalid_tables']))
 print('Manifest frozen',manifest['status'],'NEW=',new,'reuse=',manifest['reused_unique_states'],'valid tables=',manifest['valid_tables'],flush=True)
 if blocked:raise RuntimeError('Budget >13000; no UE permitted')
if __name__=='__main__':main()
