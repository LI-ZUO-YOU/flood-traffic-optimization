"""S2/S3 reads frozen scalar results. Original simulation/model code is never imported."""
from load_frozen_results import *
import sys,time

SEED=2026103006
B=20000
IDS=np.arange(3001,3031,dtype=np.int64)
SCHEMES=['scenario-only','scenario+seed']

def locations(out):
 out=Path(out).resolve()
 return {'out':out,'audit':out/'00_audit/batch2','bootstrap':out/'02_new30/batch2','variance':out/'03_variance','figures':out/'05_figures/batch2','delivery':out/'06_delivery'}

def verify_first_batch(out):
 out=Path(out);seal=js(out/'00_audit/first_batch_delivery_seal.json')
 assert seal['status']=='FIRST_BATCH_COMPLETE_STOP' and seal['G1']=='PASS'
 assert sha(out/'00_audit/source_manifest.csv')==seal['source_manifest_sha256']
 assert sha(out/'00_audit/analysis_protocol.json')==seal['analysis_protocol_sha256']
 assert sha(out/'00_audit/output_manifest.csv')==seal['output_manifest_sha256']
 for row in frame(out/'00_audit/output_manifest.csv').itertuples():assert sha(row.path)==row.SHA256,row.path
 check_immutable(out)
 spec=js(out/'00_audit/analysis_protocol.json');assert spec['future_gated']['bootstrap_seed']==SEED and spec['future_gated']['bootstrap_repetitions']==B
 assert spec['new30']['IDs']==IDS.tolist() and spec['new30']['stochastic_methods']==STOCH and spec['new30']['single_run_methods']==DETERM
 return spec

def inputs(out):
 out=Path(out);raw=tables(out)['all_run_results.csv'];x=raw[raw.phase=='query_cap'].copy();saved=frame(out/'02_new30/new30_run_level.csv')
 pd.testing.assert_frame_equal(x.reset_index(drop=True),saved.reset_index(drop=True),check_dtype=False,check_exact=True)
 assert len(x)==1590
 assert not x.duplicated(['scenario_id','method','replicate']).any() and set(x.scenario_id)==set(IDS)
 arrays={}
 for m in METHODS:
  n=10 if m in STOCH else 1;g=x[x.method==m];assert len(g)==30*n
  arrays[m]=np.array([g[g.scenario_id==sid].sort_values('replicate').relative_regret_pct.to_numpy() for sid in IDS],float)
  assert arrays[m].shape==(30,n) and np.isfinite(arrays[m]).all()
 return x,arrays

def preflight(out):
 paths=locations(out);audit=paths['audit'];assert not (audit/'precomputation_freeze.json').exists(),'Refuse replacing a second-batch analysis or changing its frozen RNG realization'
 spec=verify_first_batch(out);x,arrays=inputs(out)
 for k in ['audit','bootstrap','figures']:paths[k].mkdir(parents=True,exist_ok=(k=='audit'))
 paths['variance'].mkdir(exist_ok=True)
 high=frame(Path(out)/'02_new30/new30_top_tail_influence.csv');high=high[high.method=='proposed'].sort_values('rank_descending');assert len(high)==5
 policy={'at':now(),'authorization':'user accepted S0-S1/new30 foundation and authorized S2-S3 only','first_batch_protocol_sha256':sha(Path(out)/'00_audit/analysis_protocol.json'),'author_plan_sha256':spec['provided_plan_sha256'],'original_protocol_unchanged':True,'seed':SEED,'B_each_scheme':B,'unit':'30 scenario IDs; frozen1590 query_cap rows; no time_cap','methods_fixed_order':METHODS,'stochastic_fixed_order':STOCH,'comparators_fixed_order':COMPARATORS,'quantile':'NumPy method=linear for statistic and percentile interval','CI':'descriptive percentile2.5/97.5; not a new prespecified confirmatory test','differences':'Proposed minus comparator; positive unfavorable to Proposed','paired_P90_metrics':['difference of marginal P90s','P90 of scenario-paired differences, kept separate'],'outer_rng':'numpy.default_rng(2026103006), PCG64; first draw integers(0,30,size=(20000,30)), default int64','inner_rng':'continue SAME generator after all outer draws; draw integers(0,10,size=(20000,5,30,10)), default int64; store losslessly as uint8','inner_axis_order':['bootstrap replicate','stochastic method in fixed STOCH order','outer sampled occurrence, including repeated IDs','seed draw1..10'],'inner_independence':'separate draws for every stochastic method and each sampled occurrence; no artificial cross-method seed pairing','same_outer_for_both_schemes':True,'deterministic':'lookup one archived value for each sampled scenario; no inner RNG draws','variance':{'within':'mean_s Var_r(regret),ddof1','observed_between':'Var_s(mean_r regret),ddof1','uncorrected_between':'observed_between-within/10','corrected_between':'max(0,uncorrected_between), report truncation','rough_total_single_run':'corrected_between+within','units':'variance pp^2; SD pp; no causal physical decomposition'},'high_tail_scenarios_fixed_from_first_batch':high[['scenario_id','rank_descending']].to_dict('records'),'influence':'all30 LOSO, unchanged main n30; condition existing full bootstrap distributions on high-case occurrence counts0,1,2,>=3; conditional percentile ranges are NOT confidence intervals','forbidden':['fresh UE','scenario generation','algorithm runs','training or prediction','changes to4.1 primary tests','new ZIP','Word changes','formal English Response','optional4.5 pooling'],'stop':'deliver S2/S3, then await author acceptance'}
 dump(audit/'batch2_execution_contract.json',policy)
 sources=[Path(out)/'02_new30'/n for n in ['new30_run_level.csv','new30_scenario_level.csv','new30_tail_summary.csv','new30_paired_basic_summary.csv','new30_LOSO.csv','new30_top_tail_influence.csv']]+[Path(out)/'00_audit'/n for n in ['analysis_protocol.json','first_batch_delivery_seal.json','archived_Table_R3_primary_paired_comparisons.csv']]
 csv(audit/'second_batch_input_manifest.csv',[{'path':str(p),'SHA256':sha(p),'size_bytes':p.stat().st_size} for p in sources])
 codefiles=[Path(__file__).parent/n for n in ['batch2_common.py','clustered_bootstrap.py','variance_components.py','batch2_influence.py','test_batch2.py','run_4_6_batch2.py']]
 assert all(p.is_file() for p in codefiles)
 csv(audit/'precomputation_code_manifest.csv',[{'path':str(p),'SHA256':sha(p),'size_bytes':p.stat().st_size} for p in codefiles])
 dump(audit/'precomputation_freeze.json',{'at':now(),'contract_sha256':sha(audit/'batch2_execution_contract.json'),'code_manifest_sha256':sha(audit/'precomputation_code_manifest.csv'),'status':'PASS_BEFORE_BOOTSTRAP','first_batch_files_unchanged':True,'runs':1590,'scenarios':30})
 print('Batch2 precomputation freeze PASS',flush=True)

def gate(out):
 p=locations(out)['audit'];s=js(p/'precomputation_freeze.json');assert sha(p/'batch2_execution_contract.json')==s['contract_sha256']
 for r in frame(p/'precomputation_code_manifest.csv').itertuples():assert sha(r.path)==r.SHA256,r.path

def summarize(values):
 a=np.asarray(values,float)
 return {'mean_regret_pct':np.mean(a,axis=-1),'median_regret_pct':np.quantile(a,.5,axis=-1,method='linear'),'P90_regret_pct':np.quantile(a,.9,axis=-1,method='linear'),'max_regret_pct':np.max(a,axis=-1)}

def interval_row(a,estimate,**meta):
 a=np.asarray(a,float);assert a.shape==(B,) and np.isfinite(a).all();lo,hi=np.quantile(a,[.025,.975],method='linear')
 return {**meta,'estimate_full30':float(estimate),'percentile95_low':float(lo),'percentile95_high':float(hi),'interval_width':float(hi-lo),'bootstrap_distribution_mean':float(a.mean()),'bootstrap_distribution_SD':float(a.std(ddof=1)),'bootstrap_distribution_median':float(np.median(a)),'B':B,'seed':SEED,'independent_scenarios':30,'interval_role':'descriptive posthoc uncertainty; not p value, equivalence proof or new independent sample'}
