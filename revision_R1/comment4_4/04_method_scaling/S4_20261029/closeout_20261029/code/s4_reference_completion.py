from pathlib import Path
import sys,os,time,csv as csvmod
BASE=Path(r'E:\jcr2区意见\返稿\revision_4_4_scaling\04_method_scaling\S4_20261029')
sys.path.insert(0,str(BASE/'code'))
from s4_common import *
CLOSE=BASE/'closeout_20261029'

def main():
    pin();verify_s4();p=js(CLOSE/'reference_only_protocol.json');start_all=time.perf_counter()
    for sid in p['scenarios']:
        folder=CLOSE/f'reference/scenario_{sid}'
        assert not (folder/'completion.json').exists() and not (folder/'supplemental_UE_journal.csv').exists()
        ph,roads,_,fixture=physical(sid,14);assert not fixture
        reused=frame(folder/'reused_states.csv.gz');missing=frame(folder/'missing_masks_before.csv').subset_mask.astype(int).tolist()
        assert set(reused.subset_mask).isdisjoint(missing) and len(reused)+len(missing)==16384
        t=time.perf_counter();net=frozen.Network(frozen.MODEL);warm(net);setup=time.perf_counter()-t
        dump(folder/'ready_supplement.json',{'at':now(),'pid':os.getpid(),'CPU_affinity':psutil.Process().cpu_affinity(),'threads':1,'reused_states':len(reused),'new_states_to_solve':len(missing),'setup_prewarm_seconds':setup,'label':'supplemental reference completion','optimizer_executed':False})
        rows=[];start=time.perf_counter();cpu0=psutil.Process().cpu_times();peak=psutil.Process().memory_info().rss
        try:
            with (folder/'supplemental_UE_journal.csv').open('x',encoding='utf-8',newline='',buffering=1) as f:
                w=None
                for k in missing:
                    if time.perf_counter()-start_all>p['supplemental_total_safety_timeout_seconds']:raise TimeoutError('supplemental overall safety timeout')
                    r=net.solve(ph,roads,k,1e-9)
                    if w is None:w=csvmod.DictWriter(f,fieldnames=list(r));w.writeheader()
                    w.writerow(r);rows.append(r)
                    assert r['converged'] and r['relative_gap']<=1e-9
                    peak=max(peak,psutil.Process().memory_info().rss)
                    if len(rows)%256==0:
                        progress={'scenario_id':sid,'new_completed':len(rows),'remaining':len(missing)-len(rows),'wall_seconds':time.perf_counter()-start,'at':now()}
                        dump(folder/'progress.json',progress);print(json.dumps(progress),flush=True)
            solvewall=time.perf_counter()-start;cpu1=psutil.Process().cpu_times()
            new=pd.DataFrame(rows);old=reused.drop(columns=['source_count','source_paths']);old['completion_origin']='reused historical valid state';new['completion_origin']='new supplemental reference-only solve'
            full=pd.concat([old,new],ignore_index=True).sort_values('subset_mask');assert len(full)==16384 and full.subset_mask.nunique()==16384
            costs=dict(zip(full.subset_mask.astype(int),full.loss));t=time.perf_counter();value,sequence=exact_dp(costs,roads);dpwall=time.perf_counter()-t
            t=time.perf_counter();other,otherseq=A.exact_dp(costs,roads);checkwall=time.perf_counter()-t;assert float(value).hex()==float(other).hex()
            assert float(full.relative_gap.max())<=1e-9
            csv(folder/'all_states_completed.csv.gz',full)
            result={'scenario_id':sid,'m':14,'label':'supplemental reference completion','status':'PASS','full_states':len(full),'reused_states':len(old),'new_UE_states':len(new),'supplemental_solve_wall_seconds':solvewall,'new_UE_kernel_seconds':float(new.solver_seconds.sum()),'new_CPU_seconds':cpu1.user+cpu1.system-cpu0.user-cpu0.system,'DP_wall_seconds':dpwall,'independent_DP_check_seconds':checkwall,'setup_prewarm_excluded_seconds':setup,'peak_RSS_sampled_after_each_solve_bytes':peak,'max_RG':float(full.relative_gap.max()),'exact_objective':value,'exact_objective_hex':float(value).hex(),'sequence':list(map(int,sequence)),'independent_DP_objective_hex':float(other).hex(),'other_DP_sequence':list(map(int,otherseq)),'DP_scope':'exact on finite recorded UE state table, not infinite-precision UE','original_capped_timing_replaced':False,'is_fresh_enumeration_timing':False,'optimizer_executed':False,'finished_at':now()}
            dump(folder/'completion.json',result);print(json.dumps(result),flush=True)
        except BaseException as e:
            dump(folder/'failure.json',{'scenario_id':sid,'error':repr(e),'completed_new_states':len(rows),'at':now()});raise
    dump(CLOSE/'reference_completion_finished.json',{'at':now(),'status':'PASS','supplemental_total_including_setup_export_seconds':time.perf_counter()-start_all})

if __name__=='__main__':main()
