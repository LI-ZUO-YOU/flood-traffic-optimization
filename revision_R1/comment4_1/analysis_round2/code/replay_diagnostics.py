from common import *
import concurrent.futures,multiprocessing,psutil,gzip
from scipy.stats import spearmanr

BASE_CORRECTION=ex.SharedCorrection
class InstrumentedCorrection(BASE_CORRECTION):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.ls_calls=[]
    def local_search(self,target_calls):
        before=self.oracle.best;seq=self.oracle.best_seq;start=self.oracle.used
        parents=sorted(self.result_by_sequence.items(),key=lambda kv:kv[1]['ue_objective'])[:5]
        rounds=[]
        # Trace Python locals of the unchanged function to observe its true stop.
        fn=ex.original.BudgetedSearch.local_search.__code__
        captured={}
        def tracer(frame,event,arg):
            if frame.f_code is fn and event=='return':
                captured.update({k:frame.f_locals.get(k) for k in ['round_no','rounds_without_improvement','evaluated']})
            return tracer
        previous=sys.gettrace();sys.settrace(tracer)
        try:super().local_search(target_calls)
        finally:sys.settrace(previous)
        reason=('budget_target_reached' if self.calls>=target_calls else 'two_rounds_below_0_1pct_or_no_evaluable_neighbors' if captured.get('rounds_without_improvement',0)>=2 else 'no_completed_parent' if not parents else 'other')
        self.ls_calls.append({'call_index':len(self.ls_calls)+1,'target_calls':target_calls,'queries_before':start,'queries_after':self.oracle.used,
            'best_before':before,'best_sequence_before':list(seq) if seq else None,'best_after':self.oracle.best,
            'top_five_parents':[{'sequence':list(s),'objective':r['ue_objective']} for s,r in parents],
            'stop_reason':reason,**captured})

def pin():
    allowed=psutil.Process().cpu_affinity();cores=[x for x in allowed if x%2==0][:4]
    ix=(multiprocessing.current_process()._identity or [1])[0]-1
    psutil.Process().cpu_affinity([cores[ix%len(cores)]])
def forbidden(*a,**kw):raise RuntimeError('UE solves are forbidden in S0/S1 table-only replays')

def captured_candidates(ph,roads,audit,sid,rep,predictor):
    rows=[];member=[];candidate_fn=ex.gen.candidate_row;subset_fn=ex.gen.subset_member_losses
    def collect(*a,**kw):
        row=candidate_fn(*a,**kw);rows.append(row);return row
    def collect_subsets(*a,**kw):
        x=subset_fn(*a,**kw);member.append(x.copy());return x
    ex.gen.candidate_row=collect;ex.gen.subset_member_losses=collect_subsets
    try:screened,report=ex.build_candidates(ph,roads,audit,sid,rep,predictor)
    finally:ex.gen.candidate_row=candidate_fn;ex.gen.subset_member_losses=subset_fn
    pool=pd.DataFrame(rows).sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').reset_index(drop=True)
    pool['proxy_rank']=np.arange(1,len(pool)+1)
    assert len(pool)==30000 and len(member)==1
    return pool,screened,report,member[0]

def score_pool(pool,roads,costarray):
    seq=np.array([list(map(int,s.split('|'))) for s in pool.sequence],dtype=np.int64)
    bits=np.empty_like(seq)
    for i,r in enumerate(roads):bits[seq==r]=1<<i
    masks=np.zeros((len(pool),10),dtype=np.int64);masks[:,1:]=np.bitwise_or.accumulate(bits,axis=1)[:,:9]
    return costarray[masks].mean(axis=1)

def phase_group(name):
    if name.startswith('A_'):return 'two_road_prefix'
    if name.startswith('B_'):return 'three_road_prefix'
    if name.startswith('C_'):return 'sequence_completion'
    if name.startswith('D_'):return 'local_search'
    return name

def one_case(sid):
    pin();import torch;torch.set_num_threads(1)
    ex.Network.solve=forbidden
    ph,roads,audit,sol=data(sid);rows=state_rows(sid);costs={m:r['loss'] for m,r in rows.items()};ca=np.array([costs[m] for m in range(1024)])
    predictor=ex.api.SurrogateV2(ex.SOURCE/'surrogate/final_ensemble')
    root=OUT/f'replay/scenario_{sid}';root.mkdir(parents=True,exist_ok=True)
    ex.SharedCorrection=InstrumentedCorrection
    for rep in range(10):
        folder=root/f'rep_{rep:02d}'
        if (folder/'complete.json').exists():continue
        folder.mkdir(exist_ok=True)
        dump(OUT/f'logs/replay_{sid}.json',{'scenario_id':sid,'replicate':rep,'status':'running'})
        pool,screened,cr,member=captured_candidates(ph,roads,audit,sid,rep,predictor)
        frozenpath=ex.ROOT/f'runs/query_cap/scenario_{sid}/proposed/rep_{rep:02d}'
        frozen=json.loads((frozenpath/'result.json').read_text(encoding='utf-8'))
        assert cr['candidate_order_sha256']==frozen['candidate_order_sha256']
        old=frame(frozenpath/'screened_candidates.csv.gz')
        assert list(old.candidate_id)==list(screened.candidate_id)
        for col in ['screening_tier','channel','prefix_2','prefix_3','primary_source']:
            assert old[col].fillna('').astype(str).tolist()==screened[col].fillna('').astype(str).tolist(),(sid,rep,col)
        q=ex.QueryOracle(TableStore(rows));engine=ex.proposed(q,roads,sid,screened)
        exactbit=float(q.best).hex()==float(frozen['best_objective']).hex()
        seqmatch=list(q.best_seq)==frozen['best_sequence']
        assert exactbit and seqmatch and q.used==frozen['actual_queries'],('REPLAY_MISMATCH_STOP',sid,rep,q.best,frozen['best_objective'])
        oldledger=frame(frozenpath/'logical_query_ledger.csv.gz')
        assert [r['subset_mask'] for r in q.rows]==oldledger.subset_mask.tolist()
        assert [r['phase'] for r in q.rows]==oldledger.phase.tolist()
        assert [r['reason'] for r in q.rows]==oldledger.reason.tolist()
        assert q.requests==frozen['logical_requests']
        # Oracle scores are appended only after successful source-faithful replay.
        pool['oracle_objective']=score_pool(pool,roads,ca)
        pool['oracle_regret_pct']=np.maximum(0.,100*(pool.oracle_objective-sol['exact_objective'])/sol['exact_objective'])
        pool.to_csv(folder/'candidate_pool_30000_with_oracle.csv.gz',index=False,compression={'method':'gzip','compresslevel':1})
        screened.to_csv(folder/'screened_replayed.csv.gz',index=False,compression={'method':'gzip','compresslevel':1})
        pd.DataFrame(engine.result_rows).to_csv(folder/'complete_sequence_history.csv.gz',index=False,compression='gzip')
        pd.DataFrame(engine.local_rows).to_csv(folder/'local_move_history.csv.gz',index=False,compression='gzip')
        pd.DataFrame(q.rows).to_csv(folder/'logical_query_ledger_replayed.csv.gz',index=False,compression='gzip')
        pd.DataFrame(q.trace).to_csv(folder/'incumbent_history_replayed.csv',index=False)
        dump(folder/'local_search_calls.json',engine.ls_calls)
        dump(folder/'replay_check.json',{'scenario_id':sid,'replicate':rep,'objective_bitwise_equal':exactbit,'sequence_equal':seqmatch,'query_order_phase_reason_equal':True,
            'logical_requests_equal':True,'queries':q.used,'objective_hex':float(q.best).hex(),'candidate_order_sha256':cr['candidate_order_sha256'],'UE_solves':0})
        if rep==0:
            pd.DataFrame({'subset_mask':range(1024),'proxy_mean_loss':member.mean(axis=1),'oracle_loss':ca,'restored_count':[m.bit_count() for m in range(1024)]}).to_csv(root/'subset_proxy_and_oracle.csv',index=False)
        # New post-hoc controls only replace initialization; actual LS is unchanged.
        first=pool.iloc[0];primary=screened[screened.screening_tier=='primary_shortlist'].sort_values(['proxy_objective_mean','candidate_id'],kind='mergesort').iloc[0]
        controls=[]
        for name,row in [('proxy_pool_top1_ls',first),('primary_top1_ls',primary)]:
            seed=tuple(map(int,row.sequence.split('|')));oq=ex.QueryOracle(TableStore(rows));ec=InstrumentedCorrection(oq,roads,sid)
            ec.evaluate_sequence(seed,'initial_start','posthoc_proxy_start')
            for target in [64,128,256]:ec.local_search(target)
            assert oq.used<=256
            oq.save(folder/name,name,rep,sid,{'post_hoc':True,'UE_solves':0,'initial_sequence':seed,'initial_objective':objective(seed,roads,costs)})
            controls.append({'method':name,'initial_sequence':list(seed),'initial_objective':objective(seed,roads,costs),'final_objective':oq.best,'queries':oq.used,'LS_stop_reasons':[c['stop_reason'] for c in ec.ls_calls]})
        dump(folder/'start_controls.json',controls)
        dump(folder/'complete.json',{'status':'SOURCE_FAITHFUL_REPLAY_AND_POSTHOC_CONTROLS_COMPLETE','scenario_id':sid,'replicate':rep,'UE_solves':0})
    dump(OUT/f'logs/replay_{sid}.json',{'scenario_id':sid,'status':'complete'});return sid

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--scenario',type=int);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    if a.scenario:one_case(a.scenario)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
            fs=[pool.submit(one_case,s) for s in range(3001,3031)]
            for f in concurrent.futures.as_completed(fs):print('replay complete',f.result(),flush=True)
