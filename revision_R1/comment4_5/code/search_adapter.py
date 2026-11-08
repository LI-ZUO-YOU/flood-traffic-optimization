"""Instrumentation wraps the frozen correction routines; LS is inherited unchanged."""
from common45 import *
from candidate_factory import prefixes

class LedgerOracle(E.QueryOracle):
 def __init__(self,store,sid,variant,rep):
  super().__init__(store,256,None);self.sid=sid;self.variant=variant;self.rep=rep;self.request_rows=[];self.context=None
 def request(self,mask,phase='search',reason=''):
  hit=int(mask) in self.known;row=super().request(mask,phase,reason)
  first=next(x for x in self.rows if int(x['subset_mask'])==int(mask))
  seq=self.context
  self.request_rows.append({'run_id':f'{self.sid}_{self.variant}_{self.rep}','scenario_id':self.sid,'variant_id':self.variant,'seed_index':self.rep,'request_index':self.requests,'mask':int(mask),'restored_count':int(mask).bit_count(),'phase':phase,'reason':reason,'cache_hit':hit,'first_seen_phase':first['phase'],'unique_query_index':first['query_index'],'RG':row['relative_gap'],'state_cost':row['loss'],'solver_seconds':0.0,'historical_solver_seconds':row.get('historical_solver_seconds'),'sequence_id':E.original.sequence_id(seq) if seq else None,'candidate_id':hashlib.sha256(f"{self.sid}|{'|'.join(map(str,seq))}".encode()).hexdigest() if seq else None,'current_best_J':self.best,'timestamp_elapsed':time.perf_counter()-self.started})
  return row

class InstrumentedCorrection(E.SharedCorrection):
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw);self.complete_rows=[];self.ls_calls=[];self.phase_blocks=[];self._last_phase=None
 def evaluate_mask(self,mask,phase,reason,sequence=None):
  self.oracle.context=sequence
  if phase!=self._last_phase:
   if self.phase_blocks:self.phase_blocks[-1].update(end_queries=self.oracle.used,end_best_J=self.oracle.best)
   self.phase_blocks.append({'phase':phase,'start_queries':self.oracle.used,'start_best_J':self.oracle.best});self._last_phase=phase
  return super().evaluate_mask(mask,phase,reason,sequence)
 def evaluate_sequence(self,sequence,phase,reason,*a,**kw):
  fresh=sequence not in self.result_by_sequence;before=self.oracle.best;used=self.oracle.used
  row=super().evaluate_sequence(sequence,phase,reason,*a,**kw)
  if fresh and row is not None:
   self.complete_rows.append({'sequence_id':row['sequence_id'],'candidate_id':row['candidate_id'],'sequence':row['sequence'],'phase':phase,'completion_budget':self.oracle.used,'complete_J':row['ue_objective'],'incumbent_before':before,'incumbent_after':self.oracle.best,'new_unique_UE_states':self.oracle.used-used,'incumbent_update':before is None or self.oracle.best<before})
  return row
 def local_search(self,target_calls):
  before=self.oracle.best;used=self.oracle.used;t=time.perf_counter();start=len(self.complete_rows)
  super().local_search(target_calls)
  self.ls_calls.append({'call_index':len(self.ls_calls)+1,'target_queries':target_calls,'before_queries':used,'after_queries':self.oracle.used,'best_J_before':before,'best_J_after':self.oracle.best,'improvement':None if before is None else before-self.oracle.best,'completed_sequences':len(self.complete_rows)-start,'wall_seconds_including_rpc':time.perf_counter()-t})

class FlatCorrection(InstrumentedCorrection):
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw)
  self.flat=self.screened.sort_values(['proxy_rank','candidate_id'],kind='mergesort')
  self.flat_prefixes=self.flat.prefix_2.drop_duplicates().head(10).tolist()
 def evaluate_prefix2(self):
  self.evaluate_mask(0,'A_prefix2','common_R0')
  for p2 in self.flat_prefixes:
   p=E.original.parse_sequence(p2)
   self.evaluate_mask(self.mask_for(p[:1]),'A_prefix2',f'flat_prefix2:{p2}:R1')
   self.evaluate_mask(self.mask_for(p),'A_prefix2',f'flat_prefix2:{p2}:R2')
  return self.flat_prefixes
 def evaluate_prefix3_for(self,ps,phase):
  for p2 in ps:
   for p3 in sorted(self.flat.loc[self.flat.prefix_2==p2,'prefix_3'].unique()):
    self.evaluate_mask(self.mask_for(E.original.parse_sequence(p3)),phase,f'flat_prefix3:{p3}:R3')
 def build_seed_queue(self):
  self._seed_queue=[{'sequence':r.seq_tuple,'reason':'flat_proxy_order'} for r in self.flat.itertuples() if r.prefix_2 in self.flat_prefixes and self.state_hash(self.mask_for(E.original.parse_sequence(r.prefix_3))) in self.state_by_hash]

def run_search(oracle,roads,sid,rep,variant,screened):
 old=E.SharedCorrection;capture={};cls=FlatCorrection if variant=='F1_NO_RESERVE' else InstrumentedCorrection
 def factory(*a,**kw):capture['engine']=cls(*a,**kw);return capture['engine']
 E.SharedCorrection=factory
 try:E.run_method('proposed',oracle,roads,sid,rep,screened)
 finally:E.SharedCorrection=old
 engine=capture['engine']
 if engine.phase_blocks:engine.phase_blocks[-1].update(end_queries=oracle.used,end_best_J=oracle.best)
 for row in engine.complete_rows:row['final_is_incumbent']=row['sequence']=='|'.join(map(str,oracle.best_seq))
 return engine

def save_ledgers(path,q,engine):
 final_masks=set(E.masks(q.best_seq,engine.roads))
 for row in q.request_rows:row['query_on_final_sequence']=row['mask'] in final_masks
 csv(path/'request_ledger.csv.gz',q.request_rows)
 csv(path/'complete_sequence_history.csv.gz',engine.complete_rows)
 csv(path/'local_search_moves.csv.gz',engine.local_rows)
 csv(path/'local_search_calls.csv',engine.ls_calls)
 csv(path/'incumbent_improvement_trace.csv',q.trace)
 csv(path/'phase_blocks.csv',engine.phase_blocks)
 unique=pd.DataFrame(q.rows);complete=pd.DataFrame(engine.complete_rows);phases=[]
 for phase in dict.fromkeys(r['phase'] for r in q.request_rows):
  blocks=[b for b in engine.phase_blocks if b['phase']==phase]
  changes=[b['start_best_J']-b['end_best_J'] for b in blocks if b['start_best_J'] is not None and b['end_best_J'] is not None]
  c=complete[complete.phase==phase]
  phases.append({'phase':phase,'unique_queries_phase':int((unique.phase==phase).sum()),'complete_sequences_phase':len(c),'incumbent_updates_phase':int(c.incumbent_update.sum()),'delta_best_J_phase':sum(changes) if len(changes)==len(blocks) else None,'final_sequence_unique_states':int(((unique.phase==phase)&unique.subset_mask.isin(final_masks)).sum()),'definition':'observed transitions; not causal contribution'})
 csv(path/'phase_query_efficiency.csv',phases)
 assert sum(p['unique_queries_phase'] for p in phases)==q.used
