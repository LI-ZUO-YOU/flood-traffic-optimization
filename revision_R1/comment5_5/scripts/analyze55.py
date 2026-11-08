"""Conditional portfolio DP and signed terminal decomposition, archived-state only."""
from common55 import *
import itertools,time
CHECKS=[]
def ck(name,ok,actual='',expected='',evidence=''):
 CHECKS.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',actual=actual,expected=expected,evidence=str(evidence)))
 if not ok:
  dump(OUT/'audit/numerical_validation.json',dict(status='FAIL',checks=CHECKS));raise RuntimeError('CRITICAL_MISMATCH '+name)
def dp_forward(c,roads,post=False):
 N=1<<len(roads);v=np.full(N,np.inf);v[0]=float(c[0]) if post else 0.;parent=np.full(N,-1,int);last=parent.copy()
 for s in range(1,N):
  v[s],_,before,bit=min((float(v[s^(1<<i)]+(0. if s==N-1 else c[s])) if post else float(v[s^(1<<i)]+c[s^(1<<i)]),roads[i],s^(1<<i),i) for i in range(len(roads)) if s&(1<<i));parent[s]=before;last[s]=bit
 s=N-1;sequence=[]
 while s:sequence.append(roads[last[s]]);s=parent[s]
 return float(v[-1]/len(roads)),sequence[::-1],v,parent,last
def dp_backward(c,m):
 N=1<<m;v=np.zeros(N)
 for s in range(N-2,-1,-1):v[s]=float(c[s])+min(v[s|(1<<i)] for i in range(m) if not s&(1<<i))
 return float(v[0]/m),v
def path_masks(seq,roads):
 mask=0;result=[0];bits={e:1<<i for i,e in enumerate(roads)}
 for e in seq:mask|=bits[e];result.append(mask)
 return result
def main():
 man=js(OUT/'run_manifest.json');run=js(OUT/'audit/UE_execution_validation.json');ck('all_new_UE_completed',run['status']=='PASS' and run['new_states_succeeded']==man['new_states_total'],run['new_states_succeeded'],man['new_states_total'])
 for r in man['critical_sources']+man['frozen_generated_files']:ck('frozen_input_'+Path(r['path']).name,sha(r['path'])==r['sha256'],sha(r['path']),r['sha256'])
 tests=[]
 for m in range(1,8):
  roads=list(range(1,m+1));c=np.array([2.+(s*13%31)/17+(1<<m)-s for s in range(1<<m)],float);W,seq,_,_,_=dp_forward(c,roads);V=dp_forward(c,roads,True)[0];H=dp_backward(c,m)[0];brute=min(sum(c[s] for s in path_masks(seq,roads)[:-1])/m for seq in itertools.permutations(roads));sentinel=c.copy();sentinel[-1]=1e30;shift=c.copy();shift[0]+=.875
  for test,a,b in [('W_vs_exhaustive',W,brute),('V_vs_W',V,W),('H_vs_W',H,W),('terminal_sentinel',dp_forward(sentinel,roads)[0],W),('initial_shift',dp_forward(shift,roads)[0]-W,.875/m)]:
   ok=close(a,b);tests.append(dict(m=m,test=test,actual=a,expected=b,abs_difference=abs(a-b),pass_check=ok));ck(f'test_{m}_{test}',ok,a,b)
 save(OUT/'tests/DP_exhaustive_and_weight_tests.csv',tests)
 requested=read(OUT/'unique_requested_states.csv');new=read(OUT/'raw/UE_query_log.csv');newmap={(int(r.scenario_id),int(r.restored_physical_mask)):r._asdict() for r in new.itertuples(index=False)}
 ck('new_UE_no_duplicates',len(newmap)==len(new)==man['new_states_total'],len(newmap),man['new_states_total'])
 ph=read(PHYS);od=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/od_long.csv');arr=np.zeros((24,24))
 for r in od.itertuples():arr[int(r.origin)-1,int(r.destination)-1]+=float(r.demand)
 odhash=hashlib.sha256(arr.astype('<f8').tobytes()).hexdigest();contexts={};accepted={};sourcepaths={}
 for sc in man['scenarios']:
  sid=sc['scenario_id'];p=ph[ph.scenario_id.eq(sid)].sort_values('physical_link_id');raw=np.column_stack([p.physical_link_id,p.depth_m,p.is_closed,p.free_flow_time_multiplier,p.capacity_factor]).astype('<f8')
  contexts[sid]=dict(scenario_id=sid,physical_scenario_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),OD_array_sha256=odhash,rho=1.,Q=Q,solver_version=man['solver_version'],UE_tolerance=TARGET,max_outer=MAX_OUTER)
  file=REV/f'reviewer_4_2/01_legacy_ue_state_comparison/source_state_tables/scenario_{sid}_path_solver_1e9_1024_states.csv.gz';sourcepaths[sid]=file;accepted[sid]=read(file).set_index('subset_mask')
 unique=[];reuse=[]
 for task in requested.itertuples():
  sid=int(task.scenario_id);pm=int(task.restored_physical_mask);ctx={**contexts[sid],'restored_physical_mask':pm};key=digest(ctx)
  if task.source=='accepted_4_2':
   oldmask=int(task.original_subset_mask);r=accepted[sid].loc[oldmask];record=dict(scenario_id=sid,restored_physical_mask=pm,state_key=key,restored_ids=json.dumps(restored(pm)),source='accepted_4_2',tstt_raw=float(r.tstt),cost=float(r.tstt/T0-1),ue_gap=float(r.relative_gap),iterations=int(r.iterations),converged=bool(r.converged),solver_seconds=float(r.solver_seconds),source_path=str(sourcepaths[sid]),source_sha256=sha(sourcepaths[sid]),solver_version=man['solver_version'],OD_array_sha256=odhash,physical_scenario_sha256=ctx['physical_scenario_sha256'],UE_tolerance=TARGET,portfolio_channel_count=int(task.portfolio_channel_count),uses_DP=bool(task.uses_DP),uses_allclosed_counterfactual=bool(task.uses_allclosed_counterfactual))
   reuse.append(dict(scenario_id=sid,restored_physical_mask=pm,original_subset_mask=oldmask,state_key=key,source_path=str(sourcepaths[sid]),source_sha256=sha(sourcepaths[sid]),status='READONLY_ACCEPTED_HIGH_PRECISION_REUSE'))
  else:
   r=newmap[(sid,pm)];ck('new_context_task_'+str(task.task_id),key==r['state_key'] and r['validation_passed'] and r['ue_gap']<=TARGET,key,r['state_key'])
   record=dict(scenario_id=sid,restored_physical_mask=pm,state_key=key,restored_ids=json.dumps(restored(pm)),source='new_UE',tstt_raw=r['tstt_raw'],cost=r['tstt_raw']/T0-1,ue_gap=r['ue_gap'],iterations=r['iterations'],converged=r['converged'],solver_seconds=r['solver_seconds'],source_path=str(OUT/'cache/portfolio_states.sqlite3'),source_sha256='',solver_version=man['solver_version'],OD_array_sha256=odhash,physical_scenario_sha256=ctx['physical_scenario_sha256'],UE_tolerance=TARGET,portfolio_channel_count=int(task.portfolio_channel_count),uses_DP=bool(task.uses_DP),uses_allclosed_counterfactual=bool(task.uses_allclosed_counterfactual))
  unique.append(record)
 unique=save(OUT/'raw/unique_state_costs.csv',unique);save(OUT/'raw/UE_reuse_log.csv',reuse);lookup=unique.set_index(['scenario_id','restored_physical_mask']);ck('physical_states_exact_union',len(unique)==man['unique_requested_states'] and not unique.duplicated(['scenario_id','restored_physical_mask']).any(),len(unique),man['unique_requested_states'])
 solutions={};dpvalid=[];dpstates=[];trajectories=[]
 for p in man['portfolios']:
  sid=p['scenario_id'];roads=p['road_bit_order'];cost=np.array([float(lookup.loc[(sid,submask(roads,k)),'cost']) for k in range(1024)]);tstt=np.array([float(lookup.loc[(sid,submask(roads,k)),'tstt_raw']) for k in range(1024)])
  start=time.perf_counter();J,seq,W,parent,last=dp_forward(cost,roads);V,seqv,Vval,_,_=dp_forward(cost,roads,True);H,Hval=dp_backward(cost,10);seconds=time.perf_counter()-start;masks=path_masks(seq,roads);explicit=float(np.sum(cost[masks[:-1]])/10)
  ck('DP_three_forms_'+p['portfolio_id'],close(J,V) and close(J,H) and close(J,explicit),dict(W=J,V=V,H=H,explicit=explicit),'relative1e-12');ck('DP_path_permutation_'+p['portfolio_id'],len(seq)==10 and set(seq)==set(roads),seq,roads)
  if p['original']:
   original=js(BASE/f'development/legacy_precision/scenario_{sid}/exact_solution.json');oldseq=original['highprecision_exact_sequence'];oldobjective=float(np.mean(cost[path_masks(oldseq,roads)[:-1]]));ck('A0_accepted_objective_'+str(sid),close(J,original['new_table_objective']) and close(J,oldobjective),J,original['new_table_objective'])
  solutions[p['portfolio_id']]=dict(J=J,sequence=seq,masks=masks,terminal_raw=float(tstt[-1]),initial_raw=float(tstt[0]),cost=cost,tstt=tstt)
  dpvalid.append(dict(portfolio_id=p['portfolio_id'],scenario_id=sid,state_count=1024,W_objective=J,V_objective=V,H_objective=H,explicit_path_objective=explicit,max_abs_difference=max(abs(J-V),abs(J-H),abs(J-explicit)),sequence=json.dumps(seq),post_cost_sequence=json.dumps(seqv),passed=True,offline_DP_seconds=seconds))
  for k in range(1024):dpstates.append(dict(portfolio_id=p['portfolio_id'],scenario_id=sid,subset_mask=k,restored_physical_mask=submask(roads,k),W=float(W[k]),V=float(Vval[k]),H_remaining=float(Hval[k]),parent_mask=int(parent[k]),last_road_id=roads[last[k]] if last[k]>=0 else None,cost=float(cost[k]),tstt_raw=float(tstt[k])))
  for k,mask in enumerate(masks):trajectories.append(dict(portfolio_id=p['portfolio_id'],scenario_id=sid,stage=k,subset_mask=mask,restored_physical_mask=submask(roads,mask),restored_ids=json.dumps(seq[:k]),road_just_restored=seq[k-1] if k else None,objective_weight=.1 if k<10 else 0.,cost=float(cost[mask]),tstt_raw=float(tstt[mask]),tstt_veh_h=.01*float(tstt[mask]),ATT_minutes=.6*float(tstt[mask])/Q))
 save(OUT/'raw/DP_independent_validation.csv',dpvalid);save(OUT/'raw/DP_state_values_and_predecessors.csv',dpstates);save(OUT/'raw/dp_trajectories.csv',trajectories)
 results=[];terminals=[];counter=[];scenarios=[];metrics=read(OUT/'raw/selection_manifest.csv');terminal52=read(REPO/'revision_R1/comment5_2/Table_terminal_residual.csv');dry52=float(read(REPO/'revision_R1/comment5_2/raw/dry_baselines.csv').loc[lambda z:z.rho.eq(1),'tstt_raw'].iloc[0])
 for sc in man['scenarios']:
  sid=sc['scenario_id'];pp=[p for p in man['portfolios'] if p['scenario_id']==sid];A0=next(p for p in pp if p['original']);original=solutions[A0['portfolio_id']];best=min(solutions[p['portfolio_id']]['J'] for p in pp);initials=[solutions[p['portfolio_id']]['initial_raw'] for p in pp];ck('shared_initial_'+str(sid),all(x==initials[0] for x in initials),initials,'identical physical S0')
  F=sc['initially_closed_roads'];cf=lookup.loc[(sid,pmask(F))];allraw=float(cf.tstt_raw)
  counter.append(dict(scenario_id=sid,initial_closed_count=len(F),restored_all_closed_ids=json.dumps(F),restored_physical_mask=pmask(F),source=cf.source,ue_gap=float(cf.ue_gap),TSTT_allclosed_raw=allraw,TSTT_allclosed_veh_h=.01*allraw,ATT_allclosed_minutes=.6*allraw/Q,ratio_to_original_dry=allraw/T0,remaining_wet_open_ids=json.dumps(sc['wet_open_affected_roads']),remaining_wet_open_count=len(sc['wet_open_affected_roads']),remaining_model_difference_raw=allraw-T0,remaining_model_difference_veh_h=.01*(allraw-T0),A0_terminal_minus_allclosed_raw=original['terminal_raw']-allraw,A0_terminal_minus_allclosed_veh_h=.01*(original['terminal_raw']-allraw),A0_terminal_total_residual_raw=original['terminal_raw']-T0,description='All originally closed roads dry-restored; initially open wet roads retain original flood effects; not fully dry network'))
  allgains=[]
  for p in pp:
   sol=solutions[p['portfolio_id']];J=sol['J'];seq=sol['sequence'];gain=100*(original['J']-J)/original['J'];delta=.6*T0/Q*(original['J']-J);allgains.append(gain);ck('positive_J_'+p['portfolio_id'],J>0,J,'>0')
   common=set(seq)&set(original['sequence']);commonA=[e for e in seq if e in common];commonB=[e for e in original['sequence'] if e in common];ranks={e:i for i,e in enumerate(commonB)};inv=sum(ranks[commonA[i]]>ranks[commonA[j]] for i in range(len(commonA)) for j in range(i+1,len(commonA)));pairs=len(common)*(len(common)-1)//2;common_tau=1-2*inv/pairs if pairs else None
   results.append(dict(portfolio_id=p['portfolio_id'],scenario_id=sid,labels=json.dumps(p['rule_labels']),is_original=p['original'],selected_roads=json.dumps(p['selected_roads_sorted']),road_bit_order=json.dumps(p['road_bit_order']),roads_in=json.dumps(p['roads_in']),roads_out=json.dumps(p['roads_out']),overlap_A0=p['overlap_A0'],set_jaccard_A0=len(common)/len(set(seq)|set(original['sequence'])),J_star=J,optimal_sequence=json.dumps(seq),first_road=seq[0],first3_roads=json.dumps(seq[:3]),terminal_restored_mask=p['selected_physical_mask'],selection_gain_pct=gain,delta_model_ATT_minutes=delta,best_tested_J_star=best,A0_selection_gap_to_best_tested_pct=100*(original['J']-best)/best,mean_stage_TSTT_raw=T0*(1+J),mean_stage_TSTT_veh_h=.01*T0*(1+J),mean_stage_ATT_minutes=.6*T0/Q*(1+J),common_roads_count=len(common),common_road_pairs=pairs,common_roads_kendall_tau=common_tau,prefix3_set_jaccard=len(set(seq[:3])&set(original['sequence'][:3]))/len(set(seq[:3])|set(original['sequence'][:3])),full_information_post_study_oracle=True))
   terminal=sol['terminal_raw'];decomp1=terminal-allraw;decomp2=allraw-T0;ck('terminal_decomposition_'+p['portfolio_id'],close(decomp1+decomp2,terminal-T0) and close(.01*decomp1+.01*decomp2,.01*(terminal-T0)),decomp1+decomp2,terminal-T0)
   info=metrics[(metrics.scenario_id==sid)&metrics.road_id.isin(p['remaining_closed_ids'])][['road_id','initial_depth_m','baseline_flow','betweenness']].to_dict('records')
   terminals.append(dict(portfolio_id=p['portfolio_id'],scenario_id=sid,labels=json.dumps(p['rule_labels']),is_original=p['original'],initial_closed_count=len(F),selected_roads_count=10,residual_closed_count=len(p['remaining_closed_ids']),residual_closed_ids=json.dumps(p['remaining_closed_ids']),residual_closed_details=json.dumps(info),unrepaired_passable_wet_count=len(sc['wet_open_affected_roads']),unrepaired_passable_wet_ids=json.dumps(sc['wet_open_affected_roads']),terminal_TSTT_raw=terminal,terminal_TSTT_veh_h=.01*terminal,terminal_ATT_minutes=.6*terminal/Q,terminal_ratio_to_original_dry=terminal/T0,terminal_excess_veh_h=.01*(terminal-T0),terminal_objective_weight=0,terminal_minus_A0_raw=terminal-original['terminal_raw'],terminal_minus_A0_ATT_minutes=.6*(terminal-original['terminal_raw'])/Q,terminal_minus_allclosed_raw=decomp1,terminal_minus_allclosed_veh_h=.01*decomp1,allclosed_minus_dry_raw=decomp2,allclosed_minus_dry_veh_h=.01*decomp2,total_residual_raw=terminal-T0,total_residual_veh_h=.01*(terminal-T0),allclosed_ATT_minutes=.6*allraw/Q))
   if p['original']:
    old=terminal52[(terminal52.scenario_id==sid)&terminal52.rho.eq(1)].iloc[0];ck('5_2_A0_terminal_'+str(sid),close(.01*terminal,old.terminal_TSTT_veh_h) and close(.6*terminal/Q,old.terminal_ATT_minutes) and len(p['remaining_closed_ids'])==old.residual_closed_roads and len(sc['wet_open_affected_roads'])==old.unrepaired_passable_wet_roads,dict(TSTT_veh_h=.01*terminal,ATT=.6*terminal/Q),dict(TSTT_veh_h=float(old.terminal_TSTT_veh_h),ATT=float(old.terminal_ATT_minutes)))
  bestterminal=min(pp,key=lambda p:solutions[p['portfolio_id']]['terminal_raw']);bestJ=[p['portfolio_id'] for p in pp if close(solutions[p['portfolio_id']]['J'],best)];terminalset=[p['portfolio_id'] for p in pp if close(solutions[p['portfolio_id']]['terminal_raw'],solutions[bestterminal['portfolio_id']]['terminal_raw'])]
  scenarios.append(dict(scenario_id=sid,n_closed=len(F),n_unique_portfolios=len(pp),n_alternatives=len(pp)-1,no_alternative_set=len(F)==10,A0_J=original['J'],best_tested_J=best,A0_selection_gap_to_best_tested_pct=100*(original['J']-best)/best,best_selection_gain_pct=max(allgains),worst_selection_gain_pct=min(allgains),best_cumulative_portfolios=json.dumps(bestJ),best_terminal_portfolios=json.dumps(terminalset),best_cumulative_and_terminal_disjoint=not bool(set(bestJ)&set(terminalset))))
 rr=save(OUT/'Table_portfolio_DP_comparison.csv',results);tt=save(OUT/'Table_terminal_residual_by_portfolio.csv',terminals);save(OUT/'Table_allclosed_counterfactual.csv',counter);ss=save(OUT/'Table_scenario_selection_summary.csv',scenarios)
 rules=read(OUT/'Table_selection_rules_all10.csv');labels=rules.merge(rr,on=['scenario_id','portfolio_id'],how='left',validate='many_to_one',suffixes=('_rule','_DP'));save(OUT/'Table_rule_label_results.csv',labels)
 dump(OUT/'audit/numerical_validation.json',dict(status='PASS',checks_passed=len(CHECKS),checks_total=len(CHECKS),checks=CHECKS,source_dry_T0_raw=T0,comment5_2_dry_T0_raw=dry52))
 print('ANALYSIS PASS',len(CHECKS),'checks;',len(rr),'distinct portfolio DPs;',len(unique),'unique physical states',flush=True)
if __name__=='__main__':main()
