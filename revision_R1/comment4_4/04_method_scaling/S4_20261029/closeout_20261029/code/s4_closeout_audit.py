from pathlib import Path
import sys, os, time, json, math, ast
BASE=Path(r'E:\jcr2区意见\返稿\revision_4_4_scaling\04_method_scaling\S4_20261029')
sys.path.insert(0,str(BASE/'code'))
from s4_common import *
CLOSE=BASE/'closeout_20261029'

def objective(seq, roads, states):
    mask=0; vals=[]
    for r in seq:
        vals.append(float(states[mask])); mask |= 1<<roads.index(r)
    assert mask==(1<<len(roads))-1
    return float(np.mean(vals))

def prepare():
    assert not (CLOSE/'audit_complete.json').exists()
    for d in ['code','audit','reference','analysis','manuscript','logs']:(CLOSE/d).mkdir(parents=True,exist_ok=True)
    verify_s4()
    frozen_opt=js(BASE/'00_lock/optimization_outputs_freeze.json')['sha256']
    assert all(sha(p)==h for p,h in frozen_opt.items())
    originals={str(p):sha(p) for p in BASE.rglob('*') if p.is_file() and CLOSE not in p.parents and 'runtime_cache' not in p.parts}
    dump(CLOSE/'original_inputs_sha256.json',{'at':now(),'sha256':originals,'optimization_freeze_verified_files':len(frozen_opt)})
    runs=[]; phases=[]; same=[]; inventory=[]; sources=[]
    for sid in range(4401,4407):
        ph,roads,_,fixture=physical(sid,14);roads=list(map(int,roads));assert not fixture
        for p in sorted((BASE/f'optimization/scenario_{sid}/m_14').glob('*/rep_*/timing.json')):
            r=js(p); assert r['status']=='PASS'
            j=frame(p.parent/'physical_UE_journal.csv');costs=dict(zip(j.subset_mask.astype(int),j.loss))
            val=objective(r['sequence'],roads,costs);assert val.hex()==r['target_hex']
            h=frame(p.parent/'incumbent_history.csv')
            runs.append({'scenario_id':sid,'method':r['method'],'replicate':r['replicate'],'objective':val,'objective_hex':val.hex(),'sequence':seq_string(r['sequence']),'online_wall':r['online_wall'],'UE_queries':r['UE_queries'],'initial_objective':float(h.objective.iloc[0]),'improvement_from_initial':float(h.objective.iloc[0])-val,'journal_sha256':sha(p.parent/'physical_UE_journal.csv'),'timing_path':str(p)})
            q=frame(p.parent/'UE_query_phase_counts.csv');q['scenario_id']=sid;q['method']=r['method'];q['replicate']=r['replicate'];phases.extend(q.to_dict('records'))
        gj=[x for x in runs if x['scenario_id']==sid and x['method']=='greedy_ils'];b=next(x for x in runs if x['scenario_id']==sid and x['method']=='ue_bibeam')
        for g in gj:
            same.append({'scenario_id':sid,'greedy_replicate':g['replicate'],'greedy_J':g['objective'],'beam_J':b['objective'],'bitwise_same_J':g['objective_hex']==b['objective_hex'],'same_sequence':g['sequence']==b['sequence'],'greedy_initial_J':g['initial_objective'],'beam_initial_J':b['initial_objective'],'greedy_improvement':g['improvement_from_initial'],'beam_improvement':b['improvement_from_initial'],'same_query_journal':g['journal_sha256']==b['journal_sha256']})
        if sid not in [4401,4406]:continue
        folder=CLOSE/f'reference/scenario_{sid}';folder.mkdir(exist_ok=True)
        paths=list((BASE/f'enum_serial/scenario_{sid}/m_14').glob('physical_UE_journal.csv'))+sorted((BASE/f'enum_4core/scenario_{sid}/m_14').glob('chunk_*/physical_UE_journal.csv'))+sorted((BASE/f'optimization/scenario_{sid}/m_14').glob('*/rep_*/physical_UE_journal.csv'))
        union={};seen={};serial=set();quad=set();opt=set();historical=0.
        for p in paths:
            df=frame(p); group='serial' if 'enum_serial' in p.parts else 'four_core' if 'enum_4core' in p.parts else 'optimization'
            assert df.subset_mask.nunique()==len(df)
            new=0
            for row in df.to_dict('records'):
                k=int(row['subset_mask']);assert 0<=k<16384 and bool(row['converged']) and row['relative_gap']<=1e-9
                if k in union:
                    for col in ['loss','tstt']:assert float(row[col]).hex()==float(union[k][col]).hex(),(sid,k,col,p)
                else:union[k]=row;new+=1
                seen.setdefault(k,[]).append(str(p))
            masks=set(map(int,df.subset_mask));{'serial':serial,'four_core':quad,'optimization':opt}[group].update(masks)
            historical+=float(df.solver_seconds.sum())
            sources.append({'scenario_id':sid,'group':group,'path':str(p),'rows':len(df),'new_union_states_in_declared_order':new,'UE_kernel_seconds':float(df.solver_seconds.sum()),'sha256':sha(p)})
        csv(folder/'reused_states.csv.gz',[{**union[k],'source_count':len(seen[k]),'source_paths':'|'.join(seen[k])} for k in sorted(union)])
        missing=sorted(set(range(16384))-set(union));csv(folder/'missing_masks_before.csv',[{'subset_mask':k} for k in missing])
        estimate=sum(union[k]['solver_seconds'] for k in union)/len(union)*len(missing)
        inventory.append({'scenario_id':sid,'m':14,'required_states':16384,'serial_unique':len(serial),'four_core_journal_unique':len(quad),'optimization_unique_including_interrupted':len(opt),'union_reusable_states':len(union),'missing_states':len(missing),'historical_UE_kernel_seconds_all_copies':historical,'estimated_new_kernel_seconds_from_observed_mean':estimate,'estimate_is_not_guarantee':True})
    csv(CLOSE/'audit/m14_completed_runs.csv',runs);csv(CLOSE/'audit/m14_query_phases.csv',phases);csv(CLOSE/'audit/greedy_beam_equality.csv',same)
    csv(CLOSE/'audit/reference_state_inventory_before.csv',inventory);csv(CLOSE/'audit/reused_source_inventory.csv',sources)
    failed=BASE/'optimization/scenario_4406/m_14/greedy_ils/rep_01';df=frame(failed/'physical_UE_journal.csv')
    dump(CLOSE/'audit/unfinished_task_evidence.json',{'path':str(failed),'monitor':js(failed/'monitor.json'),'ready':js(failed/'ready.json'),'completed_physical_journal_rows':len(df),'last_completed_state':df.iloc[-1].to_dict(),'worker_log_bytes':(failed/'worker.log').stat().st_size,'UE_failure_record_exists':(failed/'UE_failure.json').exists(),'missing_files':['timing.json','result.json','logical_query_ledger.csv.gz'],'external_process_identity':'not recorded; cannot identify','classification':'measurement interrupted by concurrency guard; not time cap, not UE convergence failure','no_rerun':True})
    dump(CLOSE/'reference_only_protocol.json',{'frozen_at':now(),'label':'supplemental reference completion','scenarios':[4401,4406],'m':14,'reuse':'same scenario AND same m=14 recovery road order only; converged journal rows; loss/TSTT bitwise cross-check','masks':'only missing masks, ascending; cases sequential','solver':'unchanged frozen.Network; cold flow; target=1e-9; mode inherited unchanged; max_iter unchanged','processes':1,'CPU_core':0,'threads':1,'setup':'developer scenario 246 warm-up excluded','optimization_runs':0,'training_runs':0,'old_capped_timing':'immutable; supplemental cached completion has separate wall/kernel/DP costs and is not a fresh enumeration benchmark','supplemental_total_safety_timeout_seconds':7200,'on_solver_failure':'stop and retain original 4/6 denominator if incomplete','inventory':inventory,'kappa':KAPPA})
    dump(CLOSE/'audit_complete.json',{'at':now(),'completed_m14_runs':len(runs),'missing_optimization_runs':1,'inventory':inventory})
    print(json.dumps({'completed_runs':len(runs),'inventory':inventory,'equality':same},ensure_ascii=False),flush=True)

if __name__=='__main__':prepare()
