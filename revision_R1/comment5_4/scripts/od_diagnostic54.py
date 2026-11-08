"""Optional archived-flow shortest-path diagnostic, not a UE solve."""
from pathlib import Path
import sys,json,heapq,hashlib
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parents[1];P52=OUT.parent/'comment5_2'
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    odfile=Path('E:/jcr2区意见/返稿/4.1专项返修_20261026/source_snapshot/code/model_backend/data_src/SiouxFalls_flood_benchmark/processed/od_long.csv')
    flowfile=P52/'raw/all_new_UE_open_arc_flows.csv.gz'
    if not flowfile.exists() or not odfile.exists():
        dump(OUT/'audit/OD_diagnostic_validation.json',dict(status='NOT_RUN_INPUT_MISSING'));return
    s=pd.read_csv(P52/'stage_metrics_all10.csv');s=s[s.scenario_id.isin([1006,1003,1008])&s.rho.eq(1)&s.stage.isin([0,5,9])]
    keys=set(s.cache_key);flows=pd.read_csv(flowfile);flows=flows[flows.cache_key.isin(keys)]
    od=pd.read_csv(odfile);od=od[od.demand>0];Q=float(od.demand.sum());records=[];details=[]
    for key in sorted(keys):
        group=flows[flows.cache_key==key];graph={n:[] for n in range(1,25)}
        for a in group.itertuples():graph[int(a.from_node)].append((int(a.to_node),float(a.congested_time_raw)))
        all_d={}
        for origin in range(1,25):
            distances={n:float('inf') for n in graph};distances[origin]=0.;heap=[(0.,origin)]
            while heap:
                cost,node=heapq.heappop(heap)
                if cost!=distances[node]:continue
                for destination,arc_cost in graph[node]:
                    v=cost+arc_cost
                    if v<distances[destination]:distances[destination]=v;heapq.heappush(heap,(v,destination))
            all_d[origin]=distances
        values=[];weights=[]
        for r in od.itertuples():
            raw=all_d[int(r.origin)][int(r.destination)];values.append(raw*.6);weights.append(float(r.demand))
            details.append(dict(cache_key=key,scenario_id=int(group.scenario_id.iloc[0]),subset_mask=int(group.subset_mask.iloc[0]),origin=int(r.origin),destination=int(r.destination),demand=float(r.demand),shortest_time_raw=raw,shortest_time_minutes=raw*.6))
        x=np.asarray(values);w=np.asarray(weights);order=np.argsort(x,kind='stable');x=x[order];w=w[order];cdf=np.cumsum(w)
        quantile=lambda p:float(x[np.searchsorted(cdf,p*Q,side='left')])
        remaining=.1*Q;upper=0.
        for xi,wi in zip(x[::-1],w[::-1]):
            take=min(remaining,wi);upper+=take*xi;remaining-=take
            if remaining<=1e-10:break
        SPTT=float(np.dot(x,w)/.6);TSTT=float(group.TSTT_contribution_raw.sum());relative=abs(TSTT-SPTT)/TSTT
        mean=float(np.dot(x,w)/Q)
        for r in s[s.cache_key==key].itertuples():
            records.append(dict(scenario_id=int(r.scenario_id),policy=r.method,stage=int(r.stage),subset_mask=int(r.subset_mask),cache_key=key,positive_OD_count=len(od),total_demand=Q,weighted_P50_minutes=quantile(.5),weighted_P90_minutes=quantile(.9),upper_10percent_demand_mean_minutes=upper/(.1*Q),weighted_mean_shortest_minutes=mean,archived_flow_ATT_minutes=.6*TSTT/Q,accepted_4_2_ATT_minutes=.6*float(r.tstt_raw)/Q,flow_TSTT_raw=TSTT,shortest_path_TSTT_raw=SPTT,TSTT_SPTT_relative_difference=relative,archived_5_2_relative_gap=float(r.ue_gap),passes_UE_consistency=relative<=2e-9,reachable_all=np.isfinite(x).all()))
    df=pd.DataFrame(records);df.to_csv(OUT/'Table_OD_time_distribution_optional.csv',index=False,float_format='%.17g');pd.DataFrame(details).to_csv(OUT/'raw/OD_shortest_time_diagnostic.csv',index=False,float_format='%.17g')
    status='PASS' if df.passes_UE_consistency.all() and df.reachable_all.all() and len(df)==18 else 'FAIL'
    dump(OUT/'audit/OD_diagnostic_validation.json',dict(status=status,method_stage_rows=len(df),unique_archived_states=len(keys),ODs_per_state=528,max_TSTT_SPTT_relative_difference=float(df.TSTT_SPTT_relative_difference.max()),tolerance=2e-9,new_UE_calls=0,algorithm='Dijkstra on already archived congested arc times; does not optimize/re-solve traffic',scope='OD travel-time heterogeneity only; no population equity or facility accessibility claim',flow_file=str(flowfile),flow_sha256=hashlib.sha256(flowfile.read_bytes()).hexdigest()))
    print('OD_DIAGNOSTIC',status,len(df),'method-stage rows',len(keys),'unique archived states',flush=True)
if __name__=='__main__':main()
