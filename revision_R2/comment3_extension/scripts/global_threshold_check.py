from common import *
from threshold_invariance import map_field
def main():
 g=read(OUT/'Table_R2C3_threshold_global_intersection.csv').iloc[0];bounds=read(OUT/'Table_R2C3_threshold_invariance.csv').set_index('scenario_id');physical=read(PHYS);rows=[]
 for label,h in [('global_lower_excluded',float(g.h_open_max_global_m)),('global_lower_nextafter_inside',float(np.nextafter(g.h_open_max_global_m,np.inf))),('global_upper_included',float(g.h_closed_min_global_m)),('global_upper_nextafter_outside',float(np.nextafter(g.h_closed_min_global_m,np.inf)))]:
  for sid in range(1001,1011):
   p=physical[physical.scenario_id.eq(sid)].sort_values('physical_link_id');q=map_field(p,h);a=p.is_closed.to_numpy(bool);b=q.is_closed.to_numpy(bool);reach,bad=reachability(q);expected=bool(bounds.loc[sid,'h_open_max_m']<h<=bounds.loc[sid,'h_closed_min_m']);equal=np.array_equal(a,b);assert equal==expected
   rows.append(dict(scenario_id=sid,test=label,threshold_m=h,mask_equal=bool(equal),expected_mask_equal=expected,flipped_ids=canonical(q.loc[a!=b,'physical_link_id'].astype(int).tolist()),**reach,new_UE_calls=0,pass_=bool(equal==expected)))
 save(OUT/'raw/global_threshold_boundary_tests.csv',rows);dump(OUT/'audit/global_threshold_validation.json',dict(status='PASS',tests=40,new_UE_calls=0,all_pass=all(r['pass_'] for r in rows),conditions=[dict(test=label,mask_changed_scenarios=[r['scenario_id'] for r in rows if r['test']==label and not r['mask_equal']],OD_unreachable_scenarios=[r['scenario_id'] for r in rows if r['test']==label and not r['OD_reachable']]) for label in dict.fromkeys(r['test'] for r in rows)]));print('Global boundary40 zero-UE checks PASS')
if __name__=='__main__':main()
