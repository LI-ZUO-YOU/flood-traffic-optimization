"""Execute the unchanged original search AST, excluding its post-search DP.

Instrumentation does not change initialization, proposal, acceptance, cooling,
best update, or stopping statements. No reference objective enters the kernel.
"""
from common import *
import ast,copy,importlib.util,math,time
def load_original():
 spec=importlib.util.spec_from_file_location('r2c6_frozen_original_sa',SA_SOURCE);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
LEGACY=load_original()
class SealedCostView:
 __slots__=('__values','owner','reads','phase','call_number','__seen')
 def __init__(self,values):self.__values=tuple(float(values[i]) for i in range(1024));self.owner=None;self.reads=[];self.phase=None;self.call_number=0;self.__seen=set()
 def __getitem__(self,mask):
  if not isinstance(mask,(int,np.integer)) or not 0<=int(mask)<1024:raise PermissionError('Only one legal integer mask may be requested')
  mask=int(mask)
  if self.owner is None or mask not in self.owner.queried:raise PermissionError('Uncharged state access denied')
  if len(self.owner.queried)>self.owner.budget:raise PermissionError('Budget exceeded')
  first=mask not in self.__seen;self.__seen.add(mask);value=self.__values[mask]
  self.reads.append(dict(access_index=len(self.reads)+1,sequence_call=self.call_number,iteration=self.phase,subset_mask=mask,new_charge=int(first),charged_after=len(self.owner.queried),loss=value,read_kind='new_state_ledger_value' if first else 'objective_or_cached_value'))
  return value
 def __iter__(self):raise PermissionError('Full-table iteration forbidden')
 def __len__(self):raise PermissionError('Full-table interface forbidden')
class AuditOracle(LEGACY.LogicalUEOracle):
 def __init__(self,view,budget):
  assert isinstance(view,SealedCostView) and view.owner is None
  super().__init__(view,budget);view.owner=self;self.calls=[]
 def evaluate_sequence(self,sequence,iteration):
  view=self._loss_by_mask;view.phase=iteration;view.call_number=len(self.calls)+1;before=set(self.queried);ms=masks(sequence);missing=len(set(ms)-before)
  value=super().evaluate_sequence(sequence,iteration)
  self.calls.append(dict(call_index=len(self.calls)+1,iteration=iteration,sequence_bits='-'.join(map(str,sequence)),missing_states_before=missing,unique_before=len(before),unique_after=len(self.queried),budget_feasible=value is not None,objective=value,new_queries=len(self.queried)-len(before)))
  assert len(self.queried)<=self.budget
  if value is None:assert before==self.queried
  return value
def make_kernel():
 tree=ast.parse(SA_SOURCE.read_text(encoding='utf-8'));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_sa')
 cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='exact_dp')
 prefix=copy.deepcopy(fn.body[:cut]);new=copy.deepcopy(fn);new.name='run_frozen_search_only';new.body=prefix+[ast.Return(value=ast.Call(func=ast.Name(id='locals',ctx=ast.Load()),args=[],keywords=[]))]
 new.returns=None;mod=ast.fix_missing_locations(ast.Module(body=[new],type_ignores=[]))
 namespace={'np':np,'math':math,'N_ROADS':10,'BUDGET':256,'SAConfig':LEGACY.SAConfig,'LogicalUEOracle':AuditOracle,'propose':LEGACY.propose}
 compiled=compile(mod,str(SA_SOURCE),'exec');exec(compiled,namespace)
 assert not any(isinstance(n,ast.Name) and n.id in ['exact_dp','exact_objective','exact_sequence','Jstar','J_star'] for body in prefix for n in ast.walk(body))
 evidence=dict(original_source_sha256=sha(SA_SOURCE),search_body_AST_sha256=hashlib.sha256(ast.dump(ast.Module(body=prefix,type_ignores=[]),include_attributes=False).encode()).hexdigest(),original_search_lines=[fn.lineno,fn.body[cut].lineno-1],excluded_after_search_line=fn.body[cut].lineno,changes='Only function name/return packaging and a passive oracle subclass; original search statements/propose retained verbatim',DP_calls_in_search=0,UE_solver_imports=0,training_imports=0,source_code_unmodified=True)
 return namespace[new.name],evidence
SEARCH,EVIDENCE=make_kernel()
def execute(sid,values,config,seed):
 view=SealedCostView(values);t=time.perf_counter();cpu=time.process_time();local=SEARCH(sid,view,config,seed=int(seed),budget=256);cpu=time.process_time()-cpu;wall=time.perf_counter()-t
 oracle=local['oracle'];history=local['history'];bits=tuple(int(v) for v in local['best']);stop='unique_budget_exhausted' if oracle.remaining==0 else 'stalled_1000' if local['stalled']>=config.max_stalled_proposals else 'UNKNOWN'
 assert set(masks(bits))<=oracle.queried and stop!='UNKNOWN'
 return dict(scenario_id=sid,seed=int(seed),best_sequence_bits=list(bits),J_SA=float(local['best_objective']),queries_charged=len(oracle.queried),requested_masks=[r['subset_mask'] for r in oracle.ledger],proposals=int(local['iteration']),accepted_moves=sum(bool(r['accepted']) for r in history[1:]),stalled=int(local['stalled']),stopping_reason=stop,sequence_evaluations=sum(r['budget_feasible'] for r in oracle.calls),budget_rejected_proposals=sum(not r['budget_feasible'] for r in oracle.calls),actual_cost_reads=len(view.reads),repeat_cost_reads=len(view.reads)-len(oracle.queried),runtime_s=wall,search_CPU_s=cpu,history=history,ledger=oracle.ledger,sequence_calls=oracle.calls,cost_reads=view.reads,RNG_final_state=local['rng'].bit_generator.state)
def firewall_tests():
 v=SealedCostView(range(1024));blocked=[]
 for label,action in [('unrequested',lambda:v[0]),('table_iteration',lambda:iter(v)),('table_length',lambda:len(v)),('slice',lambda:v[:])]:
  try:action();blocked.append(dict(test=label,pass_=False))
  except PermissionError:blocked.append(dict(test=label,pass_=True))
 oracle=AuditOracle(v,9);result=oracle.evaluate_sequence(tuple(range(10)),0);blocked.append(dict(test='atomic_budget_precheck',pass_=result is None and len(oracle.queried)==len(v.reads)==0))
 assert all(x['pass_'] for x in blocked);return blocked
