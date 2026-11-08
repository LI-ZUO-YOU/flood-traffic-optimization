from common44 import *
import shutil,math,difflib,dataclasses
PLAN=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\Downloads\Reviewer1_4.4_规模扩展与复杂度验证实施方案.md')
SUPP=Path(r'E:\jcr2区意见\返稿\4.4补充意见.txt')
def setup():
 lock=OUT/'00_lock/frozen_scaling_protocol.json'
 if lock.exists():raise FileExistsError('Protocol already frozen')
 vm=psutil.virtual_memory()
 protocol={'frozen_at':now(),'authority':'User requested plan plus supplement; supplement overrides conflicting defaults',
  'batch_scope':'S0-S3 first batch; deliver and stop for assessment before S4 as explicitly required in original plan',
  'scenario_seed':2026102904,'scenario_ids':list(range(4401,4407)),'extended_closed_count':14,'max_generation_draws':10000,
  'scenario_mechanism':'Frozen connectivity-constrained generate_final_holdout.load_generation_functions. Change severe blocked_min/max ONLY to 14/14. Other severe parameters unchanged.',
  'scenario_label':'extended-severity exploratory scaling stress test, not original-distribution holdout',
  'regression_scenarios':[3001,3002,3003],'regression_replicate_indices':[0],
  'regression_methods':['proposed','greedy_ils','ue_bibeam','sa_original'],'regression_physical_cost_source':'archived 4.1 state table, no new UE solves, independent empty logical caches; logic reproducibility only',
  'components_m':[8,10,12,14,16],'component_repeats':3,'optional_m_18_20':False,'optional_m15':False,
  'm16_fixture':'Extend each 14-closure feature vector with its first two open physical road IDs. Feature-only, disconnected, no UE or decision-quality claim.',
  'candidate_target':30000,'source_quotas':frozen.gen.SOURCE_QUOTAS,
  'adapted_name':'size-adapted Proposed','m10_name':'Original Proposed (m=10)',
  'prefix_rule_m_le_10':'unchanged exhaustive original 3-tail prefix generation and prefix5 random fill',
  'prefix_rule_m_gt_10':'Seeded random ordering of cyclic road-index orbits: base prefixes (0,a,b,c), distinct nonzero a,b,c; random orbit order and rotation offset, visit all m rotations. Each visited prefix attempts mean/member/random tail in original order; stop adding at exactly 16000 unique source sequences. Last prefix may be partial. Record visited prefixes, position balance and all attempted tails. No quota increase.',
  'prefix_rng':'same candidate RNG as original; seed 2026080702+sid+1000000*rep; orbit selection uses this RNG before tails',
  'surrogate':'unchanged 10 weights, full 2^m matrix, full-state inference batch, unchanged float32 feature transform',
  'primary':60,'reserve_prefix2_groups':10,'reserve_per_source_quantile_limit':10,
  'LS_early_positions':5,'LS_parents':5,'LS_stall_rounds':2,'LS_relative_threshold':.001,'UE_budget':256,
  'seed_shares':[.55,.5,.5],'checkpoints':[64,128,256],
  'future_S4_methods':['proposed','greedy_ils','ue_bibeam','sa_original'],'future_S4_m':[10,12,14],'future_S4_rep_indices':[0,1,2],
  'future_S4_initialization':'Greedy Q=m(m+1)/2 incl R0, charged to B; checkpoints may have no complete sequence',
  'future_S4_UE_target':1e-9,'future_S4_objective':'mean R0 through R(m-1); terminal zero weight',
  'future_S4_exact_reference':'full independent 2^m UE table after all method outputs frozen; original m10 may reuse only if physical input and roads identical',
  'inference_testing':'descriptive only, no significance tests, seeds technical repeats nested in scenario',
  'runtime':'single active worker process, CPU0, one compute thread, sequential tasks, warm code fresh surrogate state; no other Python jobs',
  'max_RSS_bytes':int(vm.available*.8),'available_RAM_at_freeze':vm.available,
  'm10_calibration':'3 warm fresh-state component repetitions on predeclared original scenario3001, rep0. Freeze max task seconds =10*median calibration end-to-end candidate preparation; calibration before extended-scale results.',
  'resource_failure_policy':'Record partial components and right-censored time/RSS, no deletion, no weakened generation rules, each planned repeat attempted',
  'statistics':'scenario-level descriptive summaries, no p-values, no significance claims',
  'packaging':'numerical CSV/CSV.GZ only; code/reports/figures remain outside numerical archive'}
 dump(lock,protocol);(OUT/'00_lock/frozen_scaling_protocol.sha256').write_text(sha(lock))
 shutil.copy2(PLAN,OUT/'00_lock'/PLAN.name);shutil.copy2(SUPP,OUT/'00_lock'/SUPP.name)
 files=[PLAN,SUPP,ROOT/'protocol/frozen_protocol.json',ROOT/'inputs/new_validation/final_scenarios_physical_links.csv',ROOT/'inputs/new_validation/selected_roads.json']
 for base in [ROOT/'code',frozen.SOURCE/'code',frozen.SOURCE/'surrogate/final_ensemble']:
  files.extend(p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
 for sid in [3001,3002,3003]:
  files.extend(p for p in (ROOT/f'exact/scenario_{sid}').rglob('*') if p.is_file())
  for method in protocol['regression_methods']:files.extend(p for p in (ROOT/f'runs/query_cap/scenario_{sid}/{method}/rep_00').iterdir() if p.is_file())
 dump(OUT/'00_lock/S0_frozen_manifest.json',{'created':now(),'sha256':{str(p):sha(p) for p in sorted(set(files))}})
 # Local source copy with reviewed dimensional substitutions. Originals remain unchanged.
 src=(frozen.FORMAL/'generate_candidate_pool.py').read_text(encoding='utf-8')
 adapted=src.replace('(1024, 10)','(1 << len(roads), 10)').replace('Invalid 1024-by-10 surrogate subset matrix','Invalid 2^m-by-10 surrogate subset matrix')
 adapted=adapted.replace('self.member_loss = member_loss','self.member_loss = member_loss\n        self.n = len(roads)').replace('sequence[:9]','sequence[:self.n-1]')
 (OUT/'code/candidate_generalized.py').write_text(adapted,encoding='utf-8')
 src2=(ROOT/'code/experiment.py').read_text(encoding='utf-8')
 changes={"ROOT=Path(__file__).resolve().parents[1]":f'ROOT=Path({str(ROOT)!r})',"gen=load_module('revision_frozen_candidates',FORMAL/'generate_candidate_pool.py')":"gen=load_module('revision_scaling_candidates',Path(__file__).with_name('candidate_generalized.py'))",
  'sequence[:9]':'sequence[:len(roads)-1]','while len(seq)<9:':'while len(seq)<len(roads)-1:',
  'rng.choice(10,2,replace=False)':'rng.choice(len(child),2,replace=False)',
  '1023':'((1<<len(roads))-1)','len(seq)==10':'len(seq)==len(roads)','len(set(seq))==10':'len(set(seq))==len(roads)',
  'range(1,1024)':'range(1,1<<len(roads))','/10,seq[':'/len(roads),seq['}
 for old,new in changes.items():
  assert old in src2,old
  src2=src2.replace(old,new)
 # Inherited correction is dimension-independent except the following two methods.
 insertion='''    def masks_for_sequence(self,sequence):
        return masks(sequence,self.roads)
    def fill_one_state(self,target):
        if self.calls>=target:return False
        ordered=self.screened.sort_values(['screening_tier','proxy_rank'],kind='stable')
        for seq in ordered['seq_tuple']:
            current=0
            for stage,road in enumerate(seq[:len(self.roads)-1],start=1):
                current|=1<<self.road_to_bit[road]
                if self.state_hash(current) not in self.state_by_hash:
                    self.evaluate_mask(current,'budget_fill',f'structured_unseen_prefix:R{stage}',seq)
                    return True
        return False

'''
 src2=src2.replace('def masks(sequence,roads):',insertion+'def masks(sequence,roads):')
 (OUT/'code/methods_generalized.py').write_text(src2,encoding='utf-8')
 diff=''.join(difflib.unified_diff((ROOT/'code/experiment.py').read_text(encoding='utf-8').splitlines(True),src2.splitlines(True),fromfile='frozen/experiment.py',tofile='revision/methods_generalized.py'))
 (OUT/'01_code_audit/dimensional_changes.diff').write_text(diff,encoding='utf-8')
 audit=[]
 patterns={'generate_candidate_pool.py':['(1024, 10)','sequence[:9]','TARGET_PER_SCENARIO','SOURCE_QUOTAS','permutations(roads, 4)','range(10)','range(64)'],
 'run_full_method_live_ue.py':['sequence[:9]','len(seq) != 10','range(5)','[:5]','< 2','0.001','BUDGET_LEVELS'],
 'select_final_recoverable_roads.py':['head(10)','< 10'],
 'interfaces_week3.py':['len(sequence) != 10','range(11)','(1024','120','38'],
 'experiment.py':['[:9]','<9','choice(10','1023','1024','/10','head(10)','len(closed)']}
 for name,needles in patterns.items():
  p=ROOT/'code'/name if name=='experiment.py' else frozen.FORMAL/name
  if not p.exists():continue
  for no,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
   for needle in needles:
    if needle in line:audit.append({'file':str(p),'line':no,'assumption':needle,'source_text':line.strip(),'handling':'dimensional substitutions in independent copy; quotas/K/d/network/LS window fixed; alternative prefix sampler for m>10','original_modified':False})
 csv(OUT/'01_code_audit/S0_code_assumption_audit.csv',audit)
 complexity=[]
 for m in [8,10,12,14,15,16,18,20]:
  complexity.append({'m':m,'subsets':2**m,'permutations':math.factorial(m),'prefix4':math.perm(m,4),'three_tail_attempts':3*math.perm(m,4),'DP_predecessors':m*2**(m-1),'policy_calls':90,'matrix_float64_bytes':80*2**m,'input_float32_bytes':480*2**m,'greedy_initial_queries':m*(m+1)//2,'B256_fraction':256/2**m,'physical_recovery_feasible_upper_bound':m<=15})
 csv(OUT/'05_analysis/S1_complexity_table.csv',complexity)
 print(json.dumps({'status':'FROZEN','source_files':len(set(files)),'RAM_limit_GiB':vm.available*.8/2**30}),flush=True)
def scenarios():
 verify();protocol=js(OUT/'00_lock/frozen_scaling_protocol.json')
 existing=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');eligible=[]
 for sid,g in existing.groupby('scenario_id'):
  r,_=select_roads(g,10);original,_=frozen.select_roads(g);assert r==original
  eligible.append({'scenario_id':sid,'source':'existing_4.1','closed_count':int(g.is_closed.sum()),'connected':connected(g),'eligible_m14':int(g.is_closed.sum())>=14 and connected(g),'m10_roads_match':True,'decision':'ineligible for nested m14' if g.is_closed.sum()<14 else 'eligible'})
 gen=frozen.load_module('revision_frozen_flood_generator',frozen.FORMAL/'generate_final_holdout.py')
 generate=gen.load_generation_functions(frozen.MODEL)
 from models import spatial_flood_field as flood
 old=flood.SPECS['severe'];new=dataclasses.replace(old,blocked_min=14,blocked_max=14)
 flood.SPECS['severe']=new
 base=frame(frozen.MODEL/'data_src/SiouxFalls_flood_benchmark/processed/physical_links.csv').sort_values('physical_link_id').reset_index(drop=True)
 priors=list((ROOT/'inputs').glob('*.csv'))+[ROOT/'inputs/new_validation/final_scenarios_physical_links.csv']
 priors=[p for p in priors if {'scenario_id','physical_link_id','depth_m','is_closed'}<=set(pd.read_csv(p,nrows=0).columns)]
 depths,closures,hashes,sources=gen.prior_hashes(priors)
 rng=np.random.default_rng(protocol['scenario_seed']);accepted=[];metadata=[];events=[]
 try:
  for draw in range(1,protocol['max_generation_draws']+1):
   ph,meta=generate(base,rng);depth=gen.vector_hash(np.round(ph.depth_m.to_numpy(float),9));closed=gen.vector_hash(ph.is_closed.to_numpy(np.uint8),np.uint8);combined=gen.scenario_hash(ph.depth_m,ph.is_closed)
   reasons=[]
   if not connected(ph):reasons.append('disconnected')
   if ph.is_closed.sum()!=14:reasons.append('not_14_closures')
   for h,s,n in [(depth,depths,'duplicate_depth'),(closed,closures,'duplicate_closure'),(combined,hashes,'duplicate_scenario')]:
    if h in s:reasons.append(n)
   sid=4401+len(accepted)
   events.append({'draw':draw,'master_seed':protocol['scenario_seed'],'scenario_id':sid if not reasons else None,'accepted':not reasons,'reason':'|'.join(reasons),'depth_hash':depth,'closed_hash':closed,'scenario_hash':combined})
   if reasons:continue
   depths.add(depth);closures.add(closed);hashes.add(combined);ph.insert(0,'scenario_id',sid);ph.insert(1,'severity','extended_severe_14');accepted.append(ph)
   metadata.append({'scenario_id':sid,'draw':draw,'master_seed':protocol['scenario_seed'],**meta,'scenario_hash':combined})
   ranked,road_audit=select_roads(ph,14);csv(OUT/f'02_scenarios/road_ranking_{sid}.csv',road_audit)
   for m in [8,10,12,14]:eligible.append({'scenario_id':sid,'source':'extended_severity','closed_count':14,'connected':True,'eligible_m14':True,'m':m,'nested_roads':'|'.join(map(str,ranked[:m])),'decision':'selected prospectively'})
   if len(accepted)==6:break
 finally:flood.SPECS['severe']=old
 assert len(accepted)==6,'Could not generate all frozen cases'
 csv(OUT/'02_scenarios/extended_severity_physical.csv',pd.concat(accepted,ignore_index=True));csv(OUT/'02_scenarios/generation_events.csv',events);csv(OUT/'02_scenarios/generation_metadata.csv',metadata);csv(OUT/'02_scenarios/S2_eligibility_and_selection.csv',eligible)
 dump(OUT/'02_scenarios/S2_scaling_scenarios_manifest.json',{'generated_at':now(),'protocol_SHA':sha(OUT/'00_lock/frozen_scaling_protocol.json'),'generation_source':str(frozen.FORMAL/'generate_final_holdout.py'),'only_modified_spec_fields':{'blocked_min':[8,14],'blocked_max':[12,14]},'prior_sources':sources,'selected':metadata,'files_sha256':{str(p):sha(p) for p in (OUT/'02_scenarios').glob('*.csv')}})
 print(json.dumps({'extended_scenarios':6,'draws':draw,'original_m14_eligible':sum(x['eligible_m14'] for x in eligible if x['source']=='existing_4.1')}),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='scenarios':scenarios()
 else:setup()
