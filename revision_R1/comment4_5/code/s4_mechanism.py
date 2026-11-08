from s4_common import *
COMPARE=['F0_FULL','F1_NO_RESERVE','F3_NO_DISAG','F6_SINGLE_MLP','F7_RIDGE','F9_NO_SURROGATE','Greedy-ILS']

def run():
 sid=5102;ph,roads,audit=public_scenario(sid);values=costs(sid);base=S4/'02_case5102'
 stage=[];summary=[];prefix=[];events=[];lineages=[];opportunities=[];primary=[];candidates=[];distributions=[];identical=[]
 # Exact conditional first-road objective from the existing subset table.
 tail=np.zeros(1024)
 for m in range(1022,-1,-1):tail[m]=values[m]+min(tail[m|(1<<b)] for b in range(10) if not m&(1<<b))
 conditional=[{'first_road':r,'singleton_state_loss':values[1<<b],'conditional_optimum_J':(values[0]+tail[1<<b])/10,'conditional_optimum_regret_pct':float(regret((values[0]+tail[1<<b])/10,sid)),'evidence':'exact deduction from sealed state table; not an optimization replay'} for b,r in enumerate(roads)]
 csv(base/'conditional_first_road_reference.csv',conditional)
 for v in COMPARE:
  for rep in range(3):
   p=path(sid,v,rep);res=js(p/'result.json');h=frame(p/'complete_sequence_history.csv.gz');q=frame(p/'request_ledger.csv.gz');u=frame(p/'logical_query_ledger.csv.gz');ls=frame(p/'local_search_calls.csv');mv=frame(p/'local_search_moves.csv.gz')
   h['ordinal']=np.arange(len(h));h['first_road']=sequences(h.sequence)[:,0];h['regret_pct']=regret(h.complete_J,sid)
   h['position18']=[list(map(int,s.split('|'))).index(18)+1 for s in h.sequence];h['position29']=[list(map(int,s.split('|'))).index(29)+1 for s in h.sequence]
   for x in h[h.incumbent_update].to_dict('records'):events.append({'variant_id':v,'seed_index':rep,**x})
   summary.append({'variant_id':v,'seed_index':rep,'final_J':res['best_objective'],'final_regret_pct':float(regret(res['best_objective'],sid)),'final_sequence':'|'.join(map(str,res['best_sequence'])),'first_complete_sequence':h.iloc[0].sequence,'first_complete_J':h.iloc[0].complete_J,'first_complete_budget':int(h.iloc[0].completion_budget),'first_LS_before_regret_pct':float(regret(ls.iloc[0].best_J_before,sid)),'first_LS_after_regret_pct':float(regret(ls.iloc[0].best_J_after,sid))})
   pool=None;sc=None
   if v!='Greedy-ILS':
    pool=frame(p/'candidate_pool.csv.gz');sc=frame(p/'screened_candidates.csv.gz');pool['oracle_J_posthoc']=score(sequences(pool.sequence),roads,values);pool['oracle_regret_pct_posthoc']=regret(pool.oracle_J_posthoc,sid)
    tiers={'pool':pool,'Primary60':pool[pool.candidate_id.isin(sc.loc[sc.screening_tier=='primary_shortlist','candidate_id'])],'Reserve':pool[pool.candidate_id.isin(sc.loc[sc.screening_tier=='structural_reserve','candidate_id'])]}
    if v=='F1_NO_RESERVE':tiers['flat_eligible']=pool
    for tier,d in tiers.items():
     for road in [18,29]:
      t=d[d.sequence.str.startswith(str(road)+'|')];stage.append({'variant_id':v,'seed_index':rep,'stage':tier,'first_road':road,'count':len(t),'minimum_proxy_rank':float(t.proxy_rank.min()) if len(t) and t.proxy_rank.notna().any() else None,'best_observed_J':float(t.oracle_J_posthoc.min()) if len(t) else None,'evidence':'posthoc sealed-pool labels, not queried online'})
    # Candidate-level audit is posthoc only; never used to regenerate or reorder a run.
    pool['in_primary']=pool.candidate_id.isin(tiers['Primary60'].candidate_id);pool['in_reserve']=pool.candidate_id.isin(tiers['Reserve'].candidate_id);pool['completed_C']=pool.sequence.isin(h.loc[h.phase=='C_true_ue_reranking','sequence']);pool['completed_D']=pool.sequence.isin(h.loc[h.phase=='D_local_search','sequence'])
    candidates.append(pool[['candidate_id','sequence','primary_source','proxy_rank','oracle_J_posthoc','oracle_regret_pct_posthoc','in_primary','in_reserve','completed_C','completed_D']].assign(variant_id=v,seed_index=rep))
    reserve=sc[sc.screening_tier=='structural_reserve'];p3=set(reserve.prefix_3.dropna().astype(str))
    for x in sc[(sc.screening_tier=='primary_shortlist') & sc.sequence.str.match(r'^(18|29)\|')].itertuples():primary.append({'variant_id':v,'seed_index':rep,'sequence':x.sequence,'candidate_id':x.candidate_id,'channel':x.channel,'proxy_rank':x.proxy_rank,'ordered_prefix3_in_reserve':x.prefix_3 in p3,'completed_C':x.sequence in set(h.loc[h.phase=='C_true_ue_reranking','sequence']),'evidence':'source rule: original C queue requires ordered prefix3 membership for reserve-based variants; F1 uses flat replacement'})
   for phase in ['C_true_ue_reranking','D_local_search']:
    d=h[h.phase==phase]
    for road,n in d.first_road.value_counts().items():distributions.append({'variant_id':v,'seed_index':rep,'phase':phase,'first_road':int(road),'unique_complete_sequences':int(n)})
   for road in [18,29]:
    bit=1<<roads.index(road);sq=u[u.subset_mask==bit];full=h[h.first_road==road]
    first=full.iloc[0] if len(full) else None
    summary[-1].update({f'road{road}_singleton_first_query':int(sq.iloc[0].query_index) if len(sq) else None,f'road{road}_singleton_first_phase':sq.iloc[0].phase if len(sq) else None,f'road{road}_first_complete_budget':int(first.completion_budget) if first is not None else None,f'road{road}_first_complete_J':float(first.complete_J) if first is not None else None})
    for phase,label in [('C_true_ue_reranking','C_completed'),('D_local_search','D_completed')]:
     d=h[(h.phase==phase)&(h.first_road==road)];stage.append({'variant_id':v,'seed_index':rep,'stage':label,'first_road':road,'count':len(d),'minimum_proxy_rank':None,'best_observed_J':float(d.complete_J.min()) if len(d) else None,'evidence':'direct unique complete-sequence history'})
    stage.append({'variant_id':v,'seed_index':rep,'stage':'final','first_road':road,'count':int(res['best_sequence'][0]==road),'minimum_proxy_rank':None,'best_observed_J':res['best_objective'] if res['best_sequence'][0]==road else None,'evidence':'direct final output'})
   # Full A requests preserve ordered prefixes, including cache hits (unordered UE states).
   a=q[(q.phase=='A_prefix2') & q.reason.str.endswith(':R2')]
   scores=[]
   for x in a.itertuples():
    st=x.reason.split(':')[1];rr=list(map(int,st.split('|')));mm=(1<<roads.index(rr[0]))|(1<<roads.index(rr[1]));scores.append((values[1<<roads.index(rr[0])]+values[mm],st,x))
   order={st:k+1 for k,(_,st,_) in enumerate(sorted(scores,key=lambda t:(t[0],t[1])))}
   for val,st,x in scores:prefix.append({'variant_id':v,'seed_index':rep,'ordered_prefix2':st,'request_index_R2':x.request_index,'R2_cache_hit':x.cache_hit,'true_UE_prefix_score_R1_R2':val,'true_score_rank':order[st],'B_initial_requests':int(((q.phase=='B_prefix3_initial')&q.reason.str.startswith('prefix3:'+st+'|')).sum()),'B_remaining_requests':int(((q.phase=='B_prefix3_remaining')&q.reason.str.startswith('prefix3:'+st+'|')).sum())})
   # Logged parent edges for each incumbent and first18 complete sequence.
   hm=h.set_index('sequence_id');firstedge=mv.drop_duplicates('child_sequence_id').set_index('child_sequence_id') if len(mv) else pd.DataFrame()
   targets=list(h.loc[h.incumbent_update,'sequence_id']);targets+=h.loc[h.first_road==18,'sequence_id'].head(1).tolist()
   for target in dict.fromkeys(targets):
    child=target;seen=set();depth=0
    while child in firstedge.index and child not in seen:
     seen.add(child);edge=firstedge.loc[child];par=edge.parent_sequence_id;row=hm.loc[child]
     lineages.append({'variant_id':v,'seed_index':rep,'target_sequence_id':target,'distance_back_from_target':depth,'child_sequence_id':child,'child_sequence':row.sequence,'parent_sequence_id':par,'parent_sequence':hm.loc[par].sequence if par in hm.index else None,'move':edge.move,'position_from':edge.position_from,'position_to':edge.position_to,'complete_J':row.complete_J,'completion_budget':row.completion_budget,'position18':row.position18,'position29':row.position29,'metadata_rows_for_child':int((mv.child_sequence_id==child).sum()),'evidence':'first logged parent edge; duplicate parent metadata may exist'})
     child=par;depth+=1
   if v=='F0_FULL':
    # Static opportunity inventory at each LS entry. No replay, UE request or objective evaluation.
    D=h[h.phase=='D_local_search'];offset=0
    for call in ls.itertuples():
     segment=D.iloc[offset:offset+int(call.completed_sequences)];offset+=int(call.completed_sequences)
     if len(segment)==0:continue
     ordinal=int(segment.iloc[0].ordinal);prior=h[h.ordinal<ordinal];parents=prior.sort_values('complete_J',kind='stable').head(5);known=set(u.loc[u.query_index<=call.before_queries,'subset_mask']);finished=set(prior.sequence);priorattempt=set(D.loc[D.ordinal<ordinal,'sequence']);items=[]
     for parent in parents.itertuples():
      seq=tuple(map(int,parent.sequence.split('|')))
      for seq2,move,i,j in E.original.BudgetedSearch.move_neighbors(seq):
       st='|'.join(map(str,seq2))
       if st in finished or st in priorattempt:continue
       missing=len(set(E.masks(seq2,roads))-known);key=(missing,move!='adjacent_swap',i,j,parent.complete_J)
       items.append((key,seq2,move,parent.sequence))
     items.sort(key=lambda z:z[0])
     for rank,(key,seq2,move,parentseq) in enumerate(items,1):
      if seq2[0] in [18,29]:opportunities.append({'variant_id':v,'seed_index':rep,'LS_call':int(call.call_index),'LS_entry_queries':int(call.before_queries),'target_queries':int(call.target_queries),'remaining_to_checkpoint':int(call.target_queries-call.before_queries),'static_rank_at_LS_entry':rank,'first_road':seq2[0],'missing_states_at_entry':key[0],'move':move,'position_from_1based':key[2]+1,'position_to_1based':key[3]+1,'parent_sequence':parentseq,'candidate_sequence':'|'.join(map(str,seq2)),'evidence':'source-rule static deduction only; counts/ranks change inside LS; does not prove which counterfactual candidate would run'})
    assert offset==len(D)
 for rep in range(3):
  fields={}
  for f in ['complete_sequence_history.csv.gz','request_ledger.csv.gz']:
   a=frame(path(sid,'F0_FULL',rep)/f);b=frame(path(sid,'F3_NO_DISAG',rep)/f)
   cols=['sequence','phase','completion_budget','complete_J'] if f.startswith('complete') else ['mask','phase','reason','cache_hit','unique_query_index','state_cost']
   fields[f]=a[cols].equals(b[cols])
  assert all(fields.values());identical.append({'seed_index':rep,**fields,'interpretation':'different primary channels but exactly equal observed queries and complete-sequence trajectories in5102 only'})
 csv(base/'5102_run_path_summary.csv',summary);csv(base/'5102_stage_firstroad_counts.csv',stage);csv(base/'5102_incumbent_trace.csv',events);csv(base/'5102_ordered_prefix_requests.csv',prefix);csv(base/'5102_primary18_29_gate.csv',primary);csv(base/'5102_firstroad_phase_distribution.csv',distributions);csv(base/'5102_parent_lineages.csv.gz',lineages);csv(base/'5102_static_LS_entry_opportunities.csv',opportunities);csv(base/'5102_pool_candidate_posthoc.csv.gz',pd.concat(candidates,ignore_index=True));dump(base/'F0_F3_trace_identity.json',identical)
 dump(base/'validation.json',{'status':'PASS','compared_runs':21,'firstroad_reference_from_existing_table':True,'static_LS_entry_inventory_only':True,'new_optimizer_runs':0,'new_UE_solves':0,'F0_F3_all3_trace_identity':True,'cache_hit_prefix_requests_retained':True})
 print('S4 5102 audit PASS',flush=True)

if __name__=='__main__':
 pin();install_no_compute_guard();run()
