"""Task B: analytic thresholds, actual mapping and graph checks; never UE."""
from common import *
from models.flood_mapping import disruption_from_depth,pregnolato_speed_ratio
from ue_solver import Network
import inspect
def map_field(p,tau):
 q=p.copy()
 for k,v in disruption_from_depth(q.depth_m.to_numpy(float),closure_depth_m=tau).items():q[k]=v
 return q
def main():
 init();source=inspect.getsource(disruption_from_depth);speedsource=inspect.getsource(pregnolato_speed_ratio)
 assert 'closed = d >= closure_depth_m' in source and 'np.where(d >= closure_depth_m, 0.0, ratio)' in speedsource,'Mapping differs; stop zero-UE invariance claim'
 net=Network(NETROOT);physical=read(PHYS);E0=originals();rows=[];tests=[];allbad=[];boundaryframes=[];statechecks=[]
 for sid in range(1001,1011):
  p=physical[physical.scenario_id.eq(sid)].sort_values('physical_link_id').reset_index(drop=True);d=p.depth_m.to_numpy(float);oldclosed=p.is_closed.to_numpy(bool);L=float(d[~oldclosed].max());U=float(d[oldclosed].min());Lids=p.loc[(~oldclosed)&p.depth_m.eq(L),'physical_link_id'].astype(int).tolist();Uids=p.loc[oldclosed&p.depth_m.eq(U),'physical_link_id'].astype(int).tolist()
  assert L<.3<=U;baseline=map_field(p,.3);assert all(np.array_equal(baseline[c],p[c]) for c in ['is_closed','speed_ratio','free_flow_time_multiplier','capacity_factor'])
  conditions=[('midpoint',(L+U)/2,True),('baseline',.3,True),('lower_nextafter_inside',float(np.nextafter(L,np.inf)),True),('upper_included',U,True),('lower_excluded',L,False),('below_lower_nextafter',float(np.nextafter(L,-np.inf)),False),('above_upper_nextafter',float(np.nextafter(U,np.inf)),False)]
  if L<.32<=U:conditions.append(('threshold_0.32',.32,True))
  boundary={}
  for label,tau,inside in conditions:
   q=map_field(p,tau);reach,bad=reachability(q);newclosed=q.is_closed.to_numpy(bool);flips=q.loc[oldclosed!=newclosed,'physical_link_id'].astype(int).tolist();newly_closed=q.loc[(~oldclosed)&newclosed,'physical_link_id'].astype(int).tolist();newly_opened=q.loc[oldclosed&(~newclosed),'physical_link_id'].astype(int).tolist();equal=np.array_equal(oldclosed,newclosed)
   transforms=all(np.array_equal(q[c].to_numpy(),baseline[c].to_numpy()) for c in ['is_closed','speed_ratio','free_flow_time_multiplier','capacity_factor'])
   assert equal==inside,(sid,label,tau)
   if inside:assert transforms
   test=dict(scenario_id=sid,test=label,threshold_m=tau,inside_invariance_interval=inside,mask_equal=bool(equal),full_mapping_equal=bool(transforms),flipped_road_ids=flips,newly_closed_ids=newly_closed,newly_opened_ids=newly_opened,n_flipped=len(flips),**reach,new_UE_calls=0,pass_=bool(equal==inside and (not inside or transforms)))
   tests.append(test);boundary[label]=test
   for od in bad.itertuples():allbad.append(dict(scenario_id=sid,test=label,threshold_m=tau,origin=int(od.origin),destination=int(od.destination),demand=float(od.demand),new_UE_calls=0))
   q['scenario_id']=sid;q['threshold_test']=label;q['threshold_m']=tau;boundaryframes.append(q)
   if inside:
    all_states_equal=True
    for mask in range(1024):
     a0,f0,c0=net.state_arrays(baseline,E0[sid],mask);a1,f1,c1=net.state_arrays(q,E0[sid],mask)
     equal_state=np.array_equal(a0,a1) and np.array_equal(f0,f1) and np.array_equal(c0,c1) and np.array_equal(net.cap*a0,net.cap*a1)
     all_states_equal=all_states_equal and equal_state
    assert all_states_equal
    statechecks.append(dict(scenario_id=sid,test=label,threshold_m=tau,states_compared=1024,active_equal=True,FFT_equal=True,effective_capacity_equal=True,BPR_coefficients_equal=True,all_inputs_equal=True,new_UE_calls=0))
  a=boundary['lower_excluded'];b=boundary['above_upper_nextafter']
  rows.append(dict(scenario_id=sid,h_open_max_m=L,h_closed_min_m=U,lower_open=True,upper_closed=True,lower_boundary_road_ids=Lids,upper_boundary_road_ids=Uids,interval_17digit=f'({L:.17g}, {U:.17g}]',interval_12decimal=f'({L:.12f}, {U:.12f}]',left_margin_from_0_30_m=.30-L,right_margin_from_0_30_m=U-.30,lower_excluded_newly_closed=a['newly_closed_ids'],lower_excluded_n_flipped=a['n_flipped'],lower_excluded_OD_reachable=a['OD_reachable'],lower_excluded_reachable_OD=a['reachable_OD'],lower_excluded_unreachable_OD=a['unreachable_OD'],lower_excluded_physical_connected=a['physical_connected'],above_upper_newly_opened=b['newly_opened_ids'],above_upper_n_flipped=b['n_flipped'],above_upper_OD_reachable=b['OD_reachable'],above_upper_reachable_OD=b['reachable_OD'],above_upper_unreachable_OD=b['unreachable_OD'],inside_mapping_inputs_identical=True,inside_1024_inputs_identical=True,new_UE_calls=0))
 L=max(r['h_open_max_m'] for r in rows);U=min(r['h_closed_min_m'] for r in rows);assert L<U
 glob=dict(h_open_max_global_m=L,h_closed_min_global_m=U,lower_open=True,upper_closed=True,lower_scenarios=[r['scenario_id'] for r in rows if r['h_open_max_m']==L],upper_scenarios=[r['scenario_id'] for r in rows if r['h_closed_min_m']==U],lower_extreme_road_sources=[dict(scenario_id=r['scenario_id'],road_ids=r['lower_boundary_road_ids']) for r in rows if r['h_open_max_m']==L],upper_extreme_road_sources=[dict(scenario_id=r['scenario_id'],road_ids=r['upper_boundary_road_ids']) for r in rows if r['h_closed_min_m']==U],interval_17digit=f'({L:.17g}, {U:.17g}]',interval_12decimal=f'({L:.12f}, {U:.12f}]',source_path=str(PHYS),source_sha256=sha(PHYS),new_UE_calls=0)
 def serial(r):return {k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in r.items()}
 save(OUT/'Table_R2C3_threshold_invariance.csv',[serial(r) for r in rows]);save(OUT/'Table_R2C3_threshold_global_intersection.csv',[serial(glob)]);save(OUT/'raw/threshold_boundary_tests.csv',[serial(r) for r in tests]);save(OUT/'raw/threshold_all1024_input_comparisons.csv',statechecks);save(OUT/'raw/threshold_boundary_unreachable_OD.csv',allbad);save(OUT/'raw/threshold_boundary_physical_fields.csv',pd.concat(boundaryframes,ignore_index=True));dump(OUT/'audit/threshold_invariance_validation.json',dict(status='PASS',new_UE_calls=0,scenarios=10,boundary_tests=len(tests),unchanged_all1024_conditions=len(statechecks),all1024_input_comparisons=sum(r['states_compared'] for r in statechecks),global_interval=glob,lower_boundary_disconnected_scenarios=[r['scenario_id'] for r in rows if not r['lower_excluded_OD_reachable']],upper_boundary_disconnected_scenarios=[r['scenario_id'] for r in rows if not r['above_upper_OD_reachable']],all_tests_pass=all(r['pass_'] for r in tests),source_mapping_sha256=sha(NETROOT/'models/flood_mapping.py')))
 (OUT/'audit/threshold_zero_UE_proof.md').write_text('''# 阈值不变性的零UE证明

固定38路原始水深及基准分类，closed_e ⇔ d_e ≥ h。要保持所有原开放道路仍开放，必须h>max_open_depth；所有原关闭道路仍关闭，必须h≤min_closed_depth。因此最大不变区间左开右闭。公共区间为各场景区间交集。

原速度多项式只含水深d，阈值仅通过np.where(d>=h,0,ratio)门控；容量默认只依赖closed；FFT为速度比倒数。若mask不变，38路全部映射值完全相同。对相同恢复集合R，恢复道路都置为干燥FFT和容量，因此全部1024状态的active/FFT/effective capacity/BPR系数、OD、solver和分母均相同，同一固定模型的成本和条件DP不变，无需新UE。实际逐状态输入比较保留在raw。

在左端等号处至少一条原开放道路关闭；右端等号仍保持原mask，向上一个float后至少一条原关闭道路开放。边界检查仅为图可达性，不能把仍连通的越界条件说成成本不变，也不能把下界外全概括为断网。宽区间来自先选连通关闭集、再分组赋分离深度的合成构造，不是现实安全裕度或水动力鲁棒性。
''',encoding='utf-8')
 print('Task B PASS, zero UE; common interval',glob['interval_17digit'],'left-disconnected',sum(not r['lower_excluded_OD_reachable'] for r in rows),flush=True)
if __name__=='__main__':main()
