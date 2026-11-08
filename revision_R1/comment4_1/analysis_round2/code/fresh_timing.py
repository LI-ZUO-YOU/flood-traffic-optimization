from common import *
import concurrent.futures,multiprocessing,psutil,shutil

def warm(net):
    d=pd.read_csv(ROOT/'inputs/historical_201_260.csv');ph=d[d.scenario_id==246].sort_values('physical_link_id');roads,_=ex.select_roads(ph)
    net.solve(ph,roads,0)

def enumeration(sid,mode):
    old=json.loads((ROOT/f'runs/time_cap/scenario_{sid}/proposed/rep_00/result.json').read_text(encoding='utf-8'))
    core=old['cpu_core'];psutil.Process().cpu_affinity([core])
    ph,roads,_,sol=data(sid);net=ex.Network(ex.MODEL);warm(net)
    target=OUT/f'S2_timing_raw/{mode}/scenario_{sid}';target.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    # No preloaded numeric cost store and no cross-state flow warm start.
    states=[net.solve(ph,roads,m,1e-9) for m in range(1024)]
    after_ue=time.perf_counter();costs={r['subset_mask']:r['loss'] for r in states}
    dpstart=time.perf_counter();j,sequence=ex.exact_dp(costs,roads);end=time.perf_counter()
    result={'scenario_id':sid,'mode':mode,'cpu_core':core,'fresh_states':1024,'ue_stage_seconds':after_ue-start,
        'solver_kernel_seconds_sum':sum(r['solver_seconds'] for r in states),'dp_seconds':end-dpstart,'end_to_end_seconds':end-start,
        'objective':j,'relative_regret_pct':regret(j,sol['exact_objective']),'gap_max':max(r['relative_gap'] for r in states),
        'same_reference_sequence':list(sequence)==sol['sequence'],'JIT_setup_and_input_loading_included':False,'fresh_state_cache':True}
    assert abs(j-sol['exact_objective'])<=cfg()['equivalence']['equivalence_kappa']*max(1,abs(j))
    pd.DataFrame(states).to_csv(target/'all_fresh_1024_states.csv.gz',index=False,compression='gzip')
    dump(target/'timing.json',result);return result

def training_cost():
    base=Path(r'E:\jcr2区意见\老家\sci-jcr2区交付\第二周工作')
    sources={'original_states':base/'day1_freeze_preprocess/week1_recovery_dataset_v1.0/recovery_states_train.csv',
        'expanded_states':base/'v2_day1_training_expansion/recovery/v2_new_training_states.csv.gz',
        'training_summary':base/'v2_day2_huber_ensemble/ensemble_training_summary.csv',
        'training_config':base/'v2_day2_huber_ensemble/ensemble_training_config_v2.json',
        'training_manifest':base/'v2_day2_huber_ensemble/combined_training_manifest.json'}
    target=OUT/'S2_offline_cost';target.mkdir(exist_ok=True)
    sourceout=target/'source_records';sourceout.mkdir(exist_ok=True)
    hashes={k:sha(p) for k,p in sources.items()}
    manifest=json.loads(sources['training_manifest'].read_text(encoding='utf-8'))
    assert hashes['original_states']==manifest['source_files']['train_original']['sha256']
    assert hashes['expanded_states']==manifest['source_files']['train_expansion']['sha256']
    train=pd.concat([pd.read_csv(sources['original_states']),pd.read_csv(sources['expanded_states'])],ignore_index=True)
    assert len(train)==3178 and train.state_hash.nunique()==3178
    members=pd.read_csv(sources['training_summary']);assert len(members)==10
    for r in members.itertuples(index=False):assert sha(ex.SOURCE/f'surrogate/final_ensemble/models/{r.member_id}.pt')==r.model_hash_sha256
    for k,p in sources.items():shutil.copy2(p,sourceout/p.name)
    dump(target/'source_provenance.json',{'sources':{k:{'path':str(p),'sha256':hashes[k]} for k,p in sources.items()},'all_ten_training_hashes_match_frozen_weights':True})
    net=ex.Network(ex.MODEL);warm(net);mapping=ex.load_module('round2_original_flood_mapping',ex.MODEL/'models/flood_mapping.py')
    psutil.Process().cpu_affinity([0]);records=[];start=time.perf_counter()
    for i,row in enumerate(train.to_dict('records'),1):
        depth=np.array([row[f'd_depth_m_pl{k:03d}'] for k in range(1,39)])
        closed=np.array([row[f'd_closed_pl{k:03d}'] for k in range(1,39)],dtype=int)
        restored=np.array([row[f'r_restored_pl{k:03d}'] for k in range(1,39)],dtype=int)
        physical=pd.DataFrame({'physical_link_id':np.arange(1,39),'is_closed':closed,
            'free_flow_time_multiplier':mapping.disruption_from_depth(depth)['free_flow_time_multiplier']})
        assert np.array_equal(mapping.disruption_from_depth(depth)['is_closed'],closed.astype(bool))
        mask=sum(1<<(k-1) for k in range(1,39) if restored[k-1]);a=time.perf_counter();r=net.solve(physical,tuple(range(1,39)),mask,1e-9)
        records.append({'state_id':row['state_id'],'scenario_id':int(row['scenario_id']),'severity':row['severity'],'state_hash':row['state_hash'],
            'current_cold_state_seconds':time.perf_counter()-a,'solver_seconds':r['solver_seconds'],'relative_gap':r['relative_gap'],'current_tstt':r['tstt'],
            'archived_state_elapsed_seconds':float(row['elapsed_seconds'])})
        if i%500==0:print('Measured training-state costs',i,'/3178',flush=True)
    elapsed=time.perf_counter()-start
    pd.DataFrame(records).to_csv(target/'3178_training_state_costs.csv',index=False)
    config=json.loads(sources['training_config'].read_text(encoding='utf-8'))
    historic=float(members.training_time_seconds.sum());historic_total=float(config['total_training_seconds'])
    dump(target/'offline_cost_summary.json',{'training_states':3178,'current_sequential_UE_dataset_wall_seconds':elapsed,
        'current_UE_state_call_seconds_sum':sum(r['current_cold_state_seconds'] for r in records),
        'current_UE_solver_kernel_seconds_sum':sum(r['solver_seconds'] for r in records),
        'archived_UE_state_elapsed_seconds_sum':sum(r['archived_state_elapsed_seconds'] for r in records),
        'archived_ten_member_training_seconds_sum':historic,'archived_training_process_total_seconds':historic_total,
        'archived_total_minus_member_sum_seconds':historic_total-historic,'hybrid_current_UE_plus_archived_training_seconds':elapsed+historic_total,
        'training_rerun':False,'original_training_hardware':'not established from supplied timing record; CPU framework recorded',
        'caveat':'Current UE uses RG<=1e-9; archived labels used original numerical protocol. Member timers and the archived overall training timer have distinct scopes; both are preserved. The hybrid cost uses the overall timer and is not a same-hardware retraining benchmark.'})
    return elapsed

def enumeration_group(ids):
    results=[]
    for sid in ids:
        r=enumeration(sid,'parallel4');results.append(r);print('Parallel fresh enumeration complete',sid,flush=True)
    return results

def main():
    if not (OUT/'S0_replay_acceptance.json').exists():raise RuntimeError('S0/S1 replay acceptance must pass before fresh timing')
    verify_manifest();rows=[]
    prior_serial=[p for p in (OUT/'S2_timing_raw/serial').glob('scenario_*/timing.json')] if (OUT/'S2_timing_raw/serial').exists() else []
    dump(OUT/'logs/S2_current_execution.json',{'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),
        'prior_completed_serial_cases':len(prior_serial),'parallel_scheduler':'one process per fixed CPU group; no affinity collisions'})
    start=time.perf_counter()
    for sid in range(3001,3031):
        p=OUT/f'S2_timing_raw/serial/scenario_{sid}/timing.json'
        result=json.loads(p.read_text()) if p.exists() else enumeration(sid,'serial');rows.append(result)
        print('Serial fresh enumeration complete',sid,flush=True)
    serial_wall=time.perf_counter()-start
    psutil.Process().cpu_affinity(list(range(psutil.cpu_count())))
    start=time.perf_counter()
    groups={}
    for sid in range(3001,3031):
        old=json.loads((ROOT/f'runs/time_cap/scenario_{sid}/proposed/rep_00/result.json').read_text(encoding='utf-8'))
        groups.setdefault(old['cpu_core'],[]).append(sid)
    assert len(groups)==4
    # One worker per old timing CPU: no two simultaneous scenarios share a core.
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(enumeration_group,ids) for core,ids in sorted(groups.items())]
        for f in concurrent.futures.as_completed(futures):rows.extend(f.result())
    parallel_wall=time.perf_counter()-start
    pd.DataFrame(rows).to_csv(OUT/'S2_fresh_timing.csv',index=False)
    dump(OUT/'S2_execution_timing.json',{'serial_batch_including_setup_and_output_seconds':serial_wall if not prior_serial else None,
        'serial_resume_execution_wall_seconds':serial_wall,'serial_online_seconds_sum':sum(r['end_to_end_seconds'] for r in rows if r['mode']=='serial'),
        'serial_cases_retained_from_same_protocol_before_scheduler_guard':len(prior_serial),'parallel4_batch_including_setup_startup_and_output_seconds':parallel_wall,
        'parallel_workers':4,'parallel_CPU_groups':groups,'no_concurrent_CPU_affinity_collisions':True,'same_scenario_CPU_as_previous_time_cap':True,'CPU_model':'Intel Core i5-12600KF',
        'timing_scope':'per-scenario end-to-end time excludes JIT/model data setup and disk exports; prior comparison methods were measured in a four-worker batch, so serial and parallel enumeration are reported separately',
        'completed_enumeration_state_solves':61440,'completed_training_state_solves':3178,'completed_case_development_warmup_solves':61,
        'technical_note':'Serial measurements were resumed after enforcing a one-process-per-CPU parallel scheduler. Completed serial outputs were retained; an interrupted unfinished case is not a measured timing result. This was unrelated to search quality.'})
    training_cost();verify_manifest();print('S2 fresh and offline-state timing complete; original files unchanged.',flush=True)
if __name__=='__main__':main()
