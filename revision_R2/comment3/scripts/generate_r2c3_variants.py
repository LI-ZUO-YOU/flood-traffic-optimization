from common import *
from replay_flood_draws import field_from_factors
from models.flood_mapping import disruption_from_depth
def main():
 init();assert not (OUT/'run_manifest.json').exists(),'Already frozen'
 original=read(PHYS);physical=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/physical_links.csv').sort_values('physical_link_id').reset_index(drop=True)
 factors={int(f['scenario_id']):f for f in js(OUT/'raw/replayed_random_factors.json') if f['scenario_id'] is not None};CRN=js(OUT/'audit/CRN_replay_validation.json')['status']=='PASS'
 frames=[];rows=[];badOD=[];Es=originals()
 for sid in range(1001,1011):
  base=original[original.scenario_id.eq(sid)].sort_values('physical_link_id').reset_index(drop=True);conditions=[('depth',v) for v in [.90,.95,1.,1.05,1.10]]+[('threshold',v) for v in [.28,.30,.32]]+[('correlation',v) for v in ['original',3.,6.]]
  for factor,level in conditions:
   vid=f'{sid}_{factor}_{level}';tau=float(level) if factor=='threshold' else .30
   if factor=='correlation' and level!='original':
    if not CRN:
     rows.append(dict(variant_id=vid,scenario_id=sid,factor=factor,level=level,validity_status='CRN_REPLAY_FAILED'));continue
    p=field_from_factors(physical,factors[sid],float(level))
   else:
    p=base.copy();d=base.depth_m.to_numpy(float)*(float(level) if factor=='depth' else 1.)
    for k,v in disruption_from_depth(d,closure_depth_m=tau).items():p[k]=v
    p['is_wet']=(d>0).astype(int)
   p['scenario_id']=sid;p['variant_id']=vid;p['factor']=factor;p['level']=level
   reach,bad=reachability(p);closed=set(p.loc[p.is_closed.eq(1),'physical_link_id'].astype(int));oldclosed=set(base.loc[base.is_closed.eq(1),'physical_link_id'].astype(int));same=closed==oldclosed
   mult=p.free_flow_time_multiplier.to_numpy(float);base_mult=base.free_flow_time_multiplier.to_numpy(float)
   traffic_equal=bool(np.array_equal(p.is_closed.to_numpy(),base.is_closed.to_numpy()) and np.array_equal(mult[~p.is_closed.to_numpy(bool)],base_mult[~base.is_closed.to_numpy(bool)]))
   original_legal=set(Es[sid])<=closed
   E=selection(p) if factor=='correlation' else Es[sid] if original_legal else selection(p)
   finite_open=bool(np.isfinite(mult[~p.is_closed.to_numpy(bool)]).all())
   status='NOT_UE_FEASIBLE' if not reach['OD_reachable'] or not finite_open else 'FEWER_THAN_10_CLOSED' if len(closed)<10 else 'VALID'
   reasons=[]
   if not reach['OD_reachable']:reasons.append('positive-demand_OD_unreachable')
   if not finite_open:reasons.append('open_road_nonfinite_travel_time')
   if len(closed)<10:reasons.append('fewer_than_10_closed_roads')
   row=dict(variant_id=vid,scenario_id=sid,draw_index=factors[sid]['draw_index'],factor=factor,level=level,original_lambda_km=factors[sid]['corr'],lambda_km=float(level) if factor=='correlation' and level!='original' else factors[sid]['corr'],closure_threshold_m=tau,depth_multiplier=float(level) if factor=='depth' else 1.,wet_count=int(p.is_wet.sum()),closed_count=len(closed),closed_roads=sorted(closed),closed_symmetric_difference=sorted(closed^oldclosed),closed_symmetric_difference_n=len(closed^oldclosed),**reach,TSTT_defined=reach['OD_reachable'] and finite_open,original_E_still_closed=original_legal,original_preselection_unchanged=selection(p)==Es[sid],road_bit_order=E,portfolio_comparability='SAME_E' if set(E)==set(Es[sid]) else 'PORTFOLIO_CHANGED' if E else 'NO_TEN_ROAD_PORTFOLIO',traffic_state_identical_to_baseline=traffic_equal,same_topology_different_costs=same and not traffic_equal,validity_status=status,invalid_reason='|'.join(reasons),physical_depth_sha256=hashlib.sha256(p.depth_m.to_numpy('<f8').tobytes()).hexdigest(),full_mapping_sha256=hashlib.sha256(p[['depth_m','is_closed','speed_ratio','free_flow_time_multiplier','capacity_factor']].to_numpy('<f8').tobytes()).hexdigest(),CRN_baseline_verified=CRN)
   rows.append(row);frames.append(p)
   for od in bad.itertuples():badOD.append(dict(variant_id=vid,scenario_id=sid,origin=int(od.origin),destination=int(od.destination),demand=float(od.demand),reason='unreachable_before_restoration'))
 dump(OUT/'raw/variant_metadata.json',rows);save(OUT/'Table_R2C3_all10_feasibility.csv',[{k:canonical(v) if isinstance(v,list) else v for k,v in r.items()} for r in rows]);save(OUT/'raw/variant_physical_fields.csv',pd.concat(frames,ignore_index=True));save(OUT/'raw/unreachable_OD.csv',badOD)
 print('Preaudit variants',len(rows),'valid',sum(r.get('validity_status')=='VALID' for r in rows),'bad',len(badOD),flush=True)
if __name__=='__main__':main()
