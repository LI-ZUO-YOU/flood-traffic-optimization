"""Sequential current-hardware cost components; temporary original-label training."""
from common43 import *
import copy,shutil

def main():
 assert js(OUT/'logs/serial_batch_completion.json')['status']=='COMPLETE'
 verify_sources();pin();import torch;torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
 from threadpoolctl import threadpool_limits
 target=OUT/'05_offline_cost';temp=target/'temporary_training_only';temp.mkdir(exist_ok=True)
 for name in ['models','histories','summaries']:(temp/name).mkdir(exist_ok=True)
 base=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第二周工作')
 source=base/'v2_day2_huber_ensemble/scripts/run_v2_day2_huber_ensemble.py'
 files={'train_original':base/'day1_freeze_preprocess/week1_recovery_dataset_v1.0/recovery_states_train.csv',
  'train_expansion':base/'v2_day1_training_expansion/recovery/v2_new_training_states.csv.gz',
  'critical_links':base/'day1_freeze_preprocess/week1_recovery_dataset_v1.0/input_validation/critical_links.csv',
  'trainer':source,'bootstrap':base/'v2_day2_huber_ensemble/bootstrap_scenarios_v2.json',
  'original_training_summary':base/'v2_day2_huber_ensemble/ensemble_training_summary.csv',
  'original_training_config':base/'v2_day2_huber_ensemble/ensemble_training_config_v2.json',
  'original_manifest':base/'v2_day2_huber_ensemble/combined_training_manifest.json',
  'original_preprocessor':base/'v2_day2_huber_ensemble/preprocessor_v2.json'}
 frozen={str(p):sha(p) for p in files.values()}
 frozen.update({str(p):sha(p) for p in (ex.SOURCE/'surrogate/final_ensemble').rglob('*') if p.is_file()})
 dump(target/'offline_input_freeze.json',{'created':now(),'source_hashes':frozen,'original_training_function_unmodified':True,
  'temporary_models_used_for_decisions':False,'training_labels':'archived original labels; newly measured high-precision TSTT is NOT substituted',
  'cost_estimate_scope':'same-hardware measured components, not an end-to-end generation-and-training run using the newly generated labels'})
 trainer=ex.load_module('cost43_original_trainer',source)
 with threadpool_limits(limits=1):
  workflow_start=time.perf_counter();a=time.perf_counter()
  train=pd.concat([trainer.load_raw(files['train_original']),trainer.load_raw(files['train_expansion'])],ignore_index=True,sort=False)
  assert len(train)==3178 and train.state_hash.nunique()==3178
  assert set(train.scenario_id.astype(int))==set(range(1,61))|set(range(201,261))
  data_load=time.perf_counter()-a
  original_manifest=js(files['original_manifest'])
  for k in ['train_original','train_expansion']:assert sha(files[k])==original_manifest['source_files'][k]['sha256']
  net=ex.Network(ex.MODEL);a=time.perf_counter();warm(net);warmwall=time.perf_counter()-a
  mapping=ex.load_module('cost43_flood_mapping',ex.MODEL/'models/flood_mapping.py')
  ueout=target/'S3_training_state_costs_3178.csv';records=[]
  if ueout.exists() and len(frame(ueout))==3178:
   records=frame(ueout).to_dict('records');UEdata=js(target/'training_state_wall.json')['wall_seconds']
  else:
   a=time.perf_counter()
   for i,row in enumerate(train.to_dict('records'),1):
    depth=np.array([row[f'd_depth_m_pl{k:03d}'] for k in range(1,39)])
    closed=np.array([row[f'd_closed_pl{k:03d}'] for k in range(1,39)],dtype=int)
    restored=np.array([row[f'r_restored_pl{k:03d}'] for k in range(1,39)],dtype=int)
    model=mapping.disruption_from_depth(depth);assert np.array_equal(model['is_closed'],closed.astype(bool))
    ph=pd.DataFrame({'physical_link_id':np.arange(1,39),'is_closed':closed,'free_flow_time_multiplier':model['free_flow_time_multiplier']})
    mask=sum(1<<k for k in range(38) if restored[k]);b=time.perf_counter();r=net.solve(ph,tuple(range(1,39)),mask,1e-9)
    records.append({'state_id':row['state_id'],'state_hash':row['state_hash'],'scenario_id':int(row['scenario_id']),
      'wall_seconds':time.perf_counter()-b,'solver_seconds':r['solver_seconds'],'actual_RG':r['relative_gap'],'iterations':r['iterations'],'tstt_current':r['tstt'],
      'archived_label_tstt':row['tstt'],'label_value_changed_for_training':False})
    if i%500==0:print('OFFLINE label cost',i,'/3178',flush=True)
   UEdata=time.perf_counter()-a;csv(ueout,records);dump(target/'training_state_wall.json',{'wall_seconds':UEdata,'states':3178,'core':CORE,'threads':1,'warmup_excluded':warmwall,'new_values_used_to_train':False})
  # All preprocessing and bootstrap logic is called from the unmodified source.
  a=time.perf_counter();critical=pd.read_csv(files['critical_links']).sort_values('physical_link_id')
  flows=critical.physical_flow.to_numpy(np.float64);betweenness=critical.betweenness.to_numpy(np.float64)
  pre=trainer.fit_preprocessor(train,flows,betweenness)
  X=trainer.transform(train,pre,flows,betweenness);y=train.log_tstt_ratio.to_numpy(np.float32);scenario_ids=train.scenario_id.to_numpy(int)
  weights=trainer.scenario_balanced_weights(scenario_ids);bootstrap=trainer.make_bootstrap_plan(scenario_ids)
  assert bootstrap['members']==js(files['bootstrap'])['members']
  original_pre=js(files['original_preprocessor'])
  for name in ['depth_mean','depth_std','aggregate_mean','aggregate_std']:assert np.array_equal(pre[name],np.array(original_pre[name]))
  preprocessing=time.perf_counter()-a
  csv(target/'feature_preprocessing_check.csv',[{'rows':len(X),'columns':X.shape[1],'preprocessor_values_identical_to_original':True,'bootstrap_members_identical_to_original':True,'seconds':preprocessing}])
  pre_hash=sha(files['original_preprocessor']);summaries=[];outerstart=time.perf_counter()
  for member in bootstrap['members']:
   existing=temp/'summaries'/f"{member['member_id']}_summary.json"
   if existing.exists():raise RuntimeError('Temporary training outputs already exist; do not silently reuse them as a fresh loop wall')
   a=time.perf_counter()
   result=trainer.train_member(member,X,y,scenario_ids,weights,temp/'models',temp/'histories',temp/'summaries',pre_hash)
   result['complete_member_function_wall']=time.perf_counter()-a
   result['model_role']='temporary_timing_only_unused_in_decisions'
   result['original_frozen_model_sha256']=sha(ex.SOURCE/f"surrogate/final_ensemble/models/{member['member_id']}.pt")
   summaries.append(result);print('OFFLINE trained',result['member_id'],'epochs',result['epochs_completed'],'wall',result['complete_member_function_wall'],flush=True)
  train_outer=time.perf_counter()-outerstart;workflowwall=time.perf_counter()-workflow_start
  csv(target/'S3_temporary_training_members.csv',summaries)
  # Three warm-process frozen-model loads and development-state predictions.
  loads=[];predicts=[]
  d=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=d[d.scenario_id==246].sort_values('physical_link_id');roads,_=ex.select_roads(ph)
  for rep in range(3):
   a=time.perf_counter();predictor=ex.api.SurrogateV2(ex.SOURCE/'surrogate/final_ensemble');loads.append(time.perf_counter()-a)
   a=time.perf_counter();values=ex.gen.subset_member_losses(predictor,ph.depth_m.to_numpy(float),ph.is_closed.to_numpy(np.uint8),list(roads));predicts.append(time.perf_counter()-a)
   assert values.shape==(1024,10)
  csv(target/'S3_model_load_prediction_overhead.csv',[{'repeat':i,'warm_process_model_load_wall':loads[i],'development_246_1024state_inference_including_transform_wall':predicts[i]} for i in range(3)])
  historic=js(files['original_training_config']);old=js(OLD/'S2_offline_cost/offline_cost_summary.json')
  measured=data_load+UEdata+preprocessing+train_outer
  breakdown=[
   {'component':'read_archived_training_tables','seconds':data_load,'type':'current isolated measurement','scope':'data loading; original labels retained'},
   {'component':'3178_state_generation_current_UE','seconds':UEdata,'type':'current isolated measurement','scope':'physical preparation plus fresh RG1e-9 solves; labels not used to retrain'},
   {'component':'features_preprocessor_bootstrap','seconds':preprocessing,'type':'current isolated measurement','scope':'original source functions and identical original preprocessing values'},
   {'component':'ten_member_training_outer_loop','seconds':train_outer,'type':'current isolated measurement','scope':'original labels/config; full member calls and file saves included; temporary checkpoints'},
   {'component':'ten_member_training_internal_timer_sum','seconds':sum(x['training_time_seconds'] for x in summaries),'type':'nested current diagnostic','scope':'do not add to outer loop'},
   {'component':'same_host_measured_components_sum','seconds':measured,'type':'component-based deployment estimate','scope':'not a single new-label-to-trained-model end-to-end run'},
   {'component':'current_observed_workflow_wall','seconds':workflowwall,'type':'current total workflow','scope':'includes development UE warm-up; uses old labels for training, not new labels'},
   {'component':'historical_training_loop','seconds':historic['total_training_seconds'],'type':'historical different context','scope':'17.7679s archive, hardware provenance incomplete'},
   {'component':'previous_mixed_offline_cost','seconds':old['hybrid_current_UE_plus_archived_training_seconds'],'type':'historical mixed estimate','scope':'70.0931s not current measured end-to-end cost'}]
  csv(target/'S3_offline_cost_breakdown.csv',breakdown)
  dump(target/'offline_summary.json',{'status':'COMPLETE','data_rows':3178,'data_load_wall':data_load,'current_state_generation_wall':UEdata,
    'preprocessing_wall':preprocessing,'temporary_original_label_training_outer_wall':train_outer,'same_host_measured_component_sum':measured,
    'observed_workflow_wall':workflowwall,'current_training_member_internal_sum':sum(x['training_time_seconds'] for x in summaries),
    'source_function_unchanged':True,'bootstrap_and_preprocessor_identical':True,'training_labels_unchanged':True,
    'formal_frozen_weights_unchanged':True,'new_temporary_weights_used_in_search':False,
    'end_to_end_new_labels_to_model_cost_measured':False,'historical_mixed_estimate':old['hybrid_current_UE_plus_archived_training_seconds'],
    'scope_caveat':'Current same-machine component estimate combines RG1e-9 generation-cost measurement with exact original-label training. New high-precision labels could alter convergence/epochs; this is not a confirmed end-to-end redeployment cost.'})
 for p,h in frozen.items():assert sha(p)==h
 verify_sources();dump(OUT/'logs/offline_completion.json',{'status':'COMPLETE','at':now(),'temporary_training_only':True})

if __name__=='__main__':main()
