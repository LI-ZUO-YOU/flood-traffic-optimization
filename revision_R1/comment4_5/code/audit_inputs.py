from common45 import *
import argparse,shutil,sqlite3,platform

def main():
 ap=argparse.ArgumentParser(description='S0 read-only asset, split and online/table precision audit; no UE solves')
 ap.add_argument('--root',default=str(OUT));ap.add_argument('--source-root',default=str(ROOT));ap.add_argument('--out',default=str(OUT/'00_audit'));args=ap.parse_args()
 assert Path(args.root).resolve()==OUT.resolve() and Path(args.source_root).resolve()==ROOT.resolve()
 dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
 assert not (dest/'G0_validation.json').exists(),'Audit already completed; refuse replacing its evidence'
 (OUT/'protocol').mkdir(exist_ok=True);shutil.copy2(PLAN,OUT/'protocol/原4.5方案_只读副本.md')
 files={}
 def add(p,role):
  p=Path(p);assert p.is_file(),p;files[str(p)]={'path':str(p),'role':role,'bytes':p.stat().st_size,'sha256':sha(p)}
 for p in (ROOT/'source_snapshot').rglob('*'):
  if p.is_file():add(p,'4.1 frozen source/model snapshot')
 for name in ['experiment.py','ue_solver.py','path_ue.py']:add(ROOT/'code'/name,'4.1 executed baseline source')
 add(ROOT/'protocol/frozen_protocol.json','4.1 protocol and kappa freeze')
 for rel in ['inputs/new_validation/final_scenarios_physical_links.csv','inputs/new_validation/selected_roads.json','inputs/historical_201_260.csv','analysis_round2/manifest.json','analysis_round2/S0_replay_acceptance.json']:
  add(ROOT/rel,'historical scenario/replay provenance')
 add(OUT/'protocol/原4.5方案_只读副本.md','user implementation plan')
 add(ROOT.parent.parent/'reviewer_4_3/00_protocol_and_input_audit/frozen_protocol.json','controlled timing protocol') if (ROOT.parent.parent/'reviewer_4_3/00_protocol_and_input_audit/frozen_protocol.json').exists() else None
 training=HOME/'day1_freeze_preprocess/week1_recovery_dataset_v1.0'
 paths={'train_original':training/'recovery_states_train.csv','train_expansion':HOME/'v2_day1_training_expansion/recovery/v2_new_training_states.csv.gz','calibration':training/'recovery_states_calibration.csv','internal_id':training/'recovery_states_test_id.csv','internal_severe':training/'recovery_states_test_severe.csv'}
 manifest=js(E.SOURCE/'surrogate/final_ensemble/combined_training_manifest.json');splits={}
 for name,p in paths.items():
  add(p,'original training split' if name.startswith('train') else 'forbidden-for-fitting split inventory only')
  assert sha(p)==manifest['source_files'][name]['sha256'],name
  z=frame(p,usecols=['scenario_id']);splits[name]={'path':str(p),'sha256':sha(p),'rows':len(z),'scenario_ids':sorted(map(int,z.scenario_id.unique()))}
 ids=set(splits['train_original']['scenario_ids'])|set(splits['train_expansion']['scenario_ids'])
 assert ids==set(range(1,61))|set(range(201,261))
 assert sum(splits[n]['rows'] for n in ['train_original','train_expansion'])==3178
 dump(dest/'data_split_firewall.json',{'training_splits':{n:splits[n] for n in ['train_original','train_expansion']},'other_splits_not_for_fitting':{n:splits[n] for n in ['calibration','internal_id','internal_severe']},'allow_training_scenario_ids':sorted(ids),'forbid_training_scenario_ids':list(range(121,161))+list(range(1001,1011))+list(range(3001,3031))+list(range(4401,4407))+list(range(5101,5111)),'development_246_247_249_already_belong_to_original_training':True,'no_model_selection_or_early_stopping_on_replay_scenarios':True})
 # Every archived full table is compared with every original Proposed logical unique-state value.
 checks=[];index=[]
 phall=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');selected=js(ROOT/'inputs/new_validation/selected_roads.json')
 for sid in range(3001,3031):
  table=ROOT/f'exact/scenario_{sid}/all_1024_states.csv.gz';add(table,'4.1 complete RG1e-9 table, sealed replay provider only')
  ref=ROOT/f'exact/scenario_{sid}/exact_solution.json';add(ref,'reference provenance, never offered to optimizer')
  d=frame(table);assert len(d)==1024 and set(d.subset_mask)==set(range(1024)) and d.subset_mask.nunique()==1024
  assert (d.relative_gap<=1e-9).all() and d.converged.all()
  costs=d.set_index('subset_mask');n=0
  for rep in range(10):
   base=ROOT/f'runs/query_cap/scenario_{sid}/proposed/rep_{rep:02d}'
   for name in ['result.json','logical_query_ledger.csv.gz']:add(base/name,'original Proposed output and online solver return ledger')
   r=js(base/'result.json');l=frame(base/'logical_query_ledger.csv.gz');assert r['actual_queries']==256 and len(l)==256
   for row in l.itertuples():
    state=costs.loc[row.subset_mask]
    for col in ['loss','tstt','relative_gap']:assert float(getattr(row,col)).hex()==float(state[col]).hex(),(sid,rep,row.subset_mask,col)
   n+=len(l)
   replay=ROOT/f'analysis_round2/replay/scenario_{sid}/rep_{rep:02d}/replay_check.json';add(replay,'existing deterministic Proposed replay acceptance')
   index.append({'scenario_id':sid,'seed_index':rep,'original_result':str(base/'result.json'),'ledger':str(base/'logical_query_ledger.csv.gz'),'sealed_cost_table':str(table),'states':1024,'online_rows_matched':len(l),'bitwise_precision_match':True,'candidate_order_sha256':r['candidate_order_sha256']})
  checks.append({'scenario_id':sid,'complete_table_states':1024,'online_ledger_states_compared':n,'TSTT_loss_RG_all_bitwise_equal':True,'max_RG':float(d.relative_gap.max()),'full_table_solver':str(d.solver.iloc[0]),'full_table_tolerance':float(d.tolerance.iloc[0]),'not_a_new_UE_solve':True})
  ph=phall[phall.scenario_id==sid].sort_values('physical_link_id');roads,audit=E.select_roads(ph);assert list(roads)==selected[str(sid)]['roads']
  csv(dest/f'public_inputs/scenario_{sid}.csv',ph);csv(dest/f'public_inputs/road_audit_{sid}.csv',audit);dump(dest/f'public_inputs/scenario_{sid}.json',{'scenario_id':sid,'roads':list(roads),'labels_present':False})
 # Development inputs and preexisting SQLite tables are inventoried but not re-solved.
 dev=frame(ROOT/'inputs/historical_201_260.csv')
 for sid in [246,247,249]:
  ph=dev[dev.scenario_id==sid].sort_values('physical_link_id');roads,audit=E.select_roads(ph)
  csv(dest/f'public_inputs/scenario_{sid}.csv',ph);csv(dest/f'public_inputs/road_audit_{sid}.csv',audit);dump(dest/f'public_inputs/scenario_{sid}.json',{'scenario_id':sid,'roads':list(roads),'labels_present':False})
  add(ROOT/f'development/highprecision_{sid}.sqlite','existing development cost cache; sealed provider only')
 csv(dest/'source_manifest.csv',list(files.values()));csv(dest/'replay_inputs_index.csv',index);csv(dest/'online_vs_full_table_precision.csv',checks)
 versions={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__}
 for module in ['torch','sklearn','scipy','numba']:
  m=__import__(module);versions[module]=m.__version__
 dump(dest/'environment_versions.json',versions)
 (dest/'missing_inputs.md').write_text('No required training/source/table input missing. Actual members are member_01 through member_10; F6 will use filename-sorted member_01, never choose by performance.\n',encoding='utf-8')
 (dest/'code_assumptions.md').write_text('''# S0 implementation assumptions

Decision baseline is formally executed experiment.py plus its unchanged source_snapshot functions, not the older public FW interface alone. Its Network.solve default mode3 uses path_column_generation_pairwise at target1e-9, cold flow and max_iter20000. All 76,800 recorded unique online states of the 300 Proposed runs match the 30 full tables bit for bit in TSTT, loss and achieved RG. Thus a precision change is not expected to explain F0 replay differences.

V2 has 120 features and original training scenarios1–60 and201–260. Development IDs246/247/249 occur within that historical training set; they are functional-check inputs, not independent model validation. Cheap models use original labels only, no retrospective/new quality labels or model selection.

The baseline A prefix selection uses proxy-selected reserve clusters. prefix2_scores subsequently ranks their evaluated costs using true UE, not surrogate scores. B prefix3 queries also use true UE; C queue uses UE prefix scores plus proxy-derived membership/tie priorities. F9 must distinguish eliminating proxy priorities from removing high-fidelity correction. Its final explicit adaptation is frozen in the new protocol before any new scenarios.

Original fill_one_state queries structured unseen candidate prefixes and can consume residual budget even without immediately completing a sequence. It is retained for F0 reproduction and all variants, tagged budget_fill, and is not represented as an incumbent improvement. No new unrelated fill states are introduced. Exact-target behaviour and natural-stop rules are reported separately; no budget/time rules are silently changed.
''',encoding='utf-8')
 dump(dest/'G0_validation.json',{'gate':'G0','status':'PASS','at':now(),'source_files':len(files),'training_rows':3178,'training_features':120,'table_scenarios':30,'table_states':30720,'online_unique_rows_bitwise_compared':76800,'new_UE_solves':0,'new_scenarios_generated':0,'precision_conflict':False,'original_files_changed':False})
 print(json.dumps(js(dest/'G0_validation.json')),flush=True)

if __name__=='__main__':main()
