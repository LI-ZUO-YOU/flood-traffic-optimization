from s4_common import *
from predictor_adapters import predictor,subset_states
from scipy.stats import spearmanr
from scipy.special import logsumexp

def errors(y,z):
 d=z-y;den=((y-y.mean())**2).sum()
 return {'MAE':float(np.abs(d).mean()),'RMSE':float(np.sqrt((d*d).mean())),'R2':float(1-(d*d).sum()/den) if den>0 else None,'bias':float(d.mean()),'Spearman':float(spearmanr(y,z).statistic) if len(y)>1 and np.ptp(y)>0 and np.ptp(z)>0 else None}

def run():
 base=S4/'04_prediction_diagnostics';models={k:predictor(v) for k,v in MODEL_VARIANTS.items()};state=[];err=[];byk=[];members=[];poolmetrics=[];top=[];selected=[];rank18=[];anchors=[];scoringtimes=[]
 selector=E.load_module('S4_diagnostic_primary_isolated',E.FORMAL/'screen_primary.py');selector.CHANNEL_QUOTAS={'proxy_top':25,'ensemble_disagreement':0,'sequence_diversity':15,'heuristic':10,'random':10}
 for sid in range(5101,5111):
  ph,roads,audit=public_scenario(sid);truth=costs(sid);states=subset_states(ph,roads);pred={};logs={};k=np.array([m.bit_count() for m in range(1024)])
  for name,model in models.items():
   t=time.perf_counter();raw=model.predict_members(states);elapsed=time.perf_counter()-t;loss=np.exp(raw)-1;pred[name]=loss;logs[name]=raw
   z=loss.mean(axis=1);logz=logsumexp(raw,axis=1)-np.log(raw.shape[1]);true_log=np.log1p(truth)
   scoringtimes.append({'scenario_id':sid,'model':name,'posthoc_inference1024_seconds':elapsed,'scope':'diagnostic inference only; not online search, training or model selection'})
   for m in range(1024):state.append({'scenario_id':sid,'model':name,'mask':m,'restored_count':k[m],'true_cost':truth[m],'predicted_cost':z[m],'true_log_ratio':true_log[m],'predicted_log_ratio_of_mean_exp':logz[m]})
   for scale,y,zz in [('cost',truth,z),('log_ratio',true_log,logz)]:
    err.append({'scenario_id':sid,'model':name,'scale':scale,'states':1024,**errors(y,zz)})
    for count in range(11):
     take=k==count;byk.append({'scenario_id':sid,'model':name,'scale':scale,'restored_count':count,'states':int(take.sum()),**errors(y[take],zz[take])})
  assert np.array_equal(logs['Ensemble'][:,0],logs['Single MLP'][:,0])
  for member in range(10):
   z=pred['Ensemble'][:,member];members.append({'scenario_id':sid,'member':member+1,**errors(truth,z)})
  for rep in range(3):
   pool=frame(path(sid,'F0_FULL',rep)/'candidate_pool.csv.gz');seq=sequences(pool.sequence);mask=mask_matrix(seq,roads);trueJ=truth[mask].mean(axis=1);trueReg=regret(trueJ,sid);trueTop=trueJ<=quant(trueJ,.01)
   diagnostic=pd.DataFrame({'scenario_id':sid,'seed_index':rep,'candidate_id':pool.candidate_id,'sequence':pool.sequence,'true_J_posthoc':trueJ,'true_regret_pct_posthoc':trueReg})
   for name in MODELS:
    memberJ=pred[name][mask].mean(axis=1);z=memberJ.mean(axis=1)
    if name=='Ensemble':
     maxerr=float(np.max(abs(z-pool.proxy_objective_mean.to_numpy())));assert maxerr<1e-10
     z=pool.proxy_objective_mean.to_numpy() # Exact frozen numerical ranking anchor.
    order=np.lexsort((pool.candidate_id.to_numpy(),z));rank=np.empty(len(pool),int);rank[order]=np.arange(1,len(pool)+1)
    diagnostic[name+'_predicted_J']=z;diagnostic[name+'_rank']=rank
    poolmetrics.append({'scenario_id':sid,'seed_index':rep,'model':name,'pool_size':len(pool),'Spearman_candidate_J':float(spearmanr(trueJ,z).statistic),'cost_MAE_candidate_J':float(np.abs(z-trueJ).mean()),'pool_best_true_regret_pct':float(trueReg.min()),'diagnostic_only_no_search':True})
    for topk in [10,60,300]:
     ix=order[:topk];top.append({'scenario_id':sid,'seed_index':rep,'model':name,'selection':'score_topK','K':topk,'best_true_regret_pct':float(trueReg[ix].min()),'median_true_regret_pct':float(np.median(trueReg[ix])),'mean_true_regret_pct':float(trueReg[ix].mean()),'recall_true_top1pct':float(trueTop[ix].sum()/trueTop.sum()),'selected_count_true_top1pct':int(trueTop[ix].sum()),'true_top1pct_denominator':int(trueTop.sum())})
    # Isolated frozen selector with no oracle labels in its inputs; same60-seat quota for every scorer.
    d=pool.copy();d['proxy_objective_mean']=z;d['proxy_rank']=rank;d['ensemble_disagreement']=memberJ.std(axis=1,ddof=1) if memberJ.shape[1]>1 else 0.0
    assert not any('true_' in c or 'oracle' in c for c in d.columns)
    chosen=selector.select_scenario(d,list(roads),audit,np.random.default_rng(2026080703+sid+1000000*rep))
    idx=pd.Series(np.arange(len(pool)),index=pool.candidate_id).loc[chosen.candidate_id].to_numpy();ix=idx.astype(int)
    top.append({'scenario_id':sid,'seed_index':rep,'model':name,'selection':'common_Primary60_25_0_15_10_10','K':60,'best_true_regret_pct':float(trueReg[ix].min()),'median_true_regret_pct':float(np.median(trueReg[ix])),'mean_true_regret_pct':float(trueReg[ix].mean()),'recall_true_top1pct':float(trueTop[ix].sum()/trueTop.sum()),'selected_count_true_top1pct':int(trueTop[ix].sum()),'true_top1pct_denominator':int(trueTop.sum())})
    for j,x in enumerate(chosen.itertuples()):selected.append({'scenario_id':sid,'seed_index':rep,'model':name,'candidate_id':x.candidate_id,'sequence':x.sequence,'channel':x.channel,'proxy_rank':x.proxy_rank,'true_J_posthoc':trueJ[ix[j]],'true_regret_pct_posthoc':trueReg[ix[j]]})
    if name=='Ensemble':
     actual=frame(path(sid,'F3_NO_DISAG',rep)/'screened_candidates.csv.gz');actual=actual[actual.screening_tier=='primary_shortlist']
     assert dict(zip(chosen.candidate_id,chosen.channel))==dict(zip(actual.candidate_id,actual.channel))
     anchors.append({'scenario_id':sid,'seed_index':rep,'pool_score_max_abs_error':maxerr,'common_primary_ensemble_equals_F3':True})
    if sid==5102:
     for road in roads:
      take=seq[:,0]==road;rank18.append({'scenario_id':sid,'seed_index':rep,'model':name,'first_road':road,'pool_count':int(take.sum()),'minimum_predicted_rank':int(rank[take].min()),'median_predicted_rank':float(np.median(rank[take])),'minimum_true_J':float(trueJ[take].min()),'selected_common_primary60':int((sequences(chosen.sequence)[:,0]==road).sum())})
   csv(base/f'common_F0_pool_{sid}_seed{rep:02d}_scores.csv.gz',diagnostic)
  print(f'S4 frozen prediction diagnostics {sid} complete',flush=True)
 csv(base/'common_state_predictions.csv.gz',state);csv(base/'common_state_errors_by_scenario.csv',err);csv(base/'state_errors_by_restored_count.csv',byk);csv(base/'all10_member_errors.csv',members);csv(base/'common_pool_rank_metrics.csv',poolmetrics);csv(base/'common_pool_topK_primary_quality.csv',top);csv(base/'common_primary60_candidates.csv.gz',selected);csv(base/'5102_firstroad_ranking.csv',rank18);csv(base/'exact_frozen_anchor_checks.csv',anchors);csv(base/'posthoc_inference_time.csv',scoringtimes)
 er=pd.DataFrame(err);csv(base/'state_error_model_means_n10.csv',er.groupby(['model','scale'])[['MAE','RMSE','R2','bias','Spearman']].mean().reset_index())
 pm=pd.DataFrame(poolmetrics);sc=pm.groupby(['scenario_id','model'])[['Spearman_candidate_J','cost_MAE_candidate_J','pool_best_true_regret_pct']].mean().reset_index();csv(base/'common_pool_metrics_scenario_means.csv',sc);csv(base/'common_pool_metrics_model_means_n10.csv',sc.groupby('model').mean(numeric_only=True).reset_index())
 tq=pd.DataFrame(top);tqs=tq.groupby(['scenario_id','model','selection','K'])[['best_true_regret_pct','median_true_regret_pct','mean_true_regret_pct','recall_true_top1pct']].mean().reset_index();csv(base/'common_pool_quality_scenario_means.csv',tqs);csv(base/'common_pool_quality_model_means_n10.csv',tqs.groupby(['model','selection','K'])[['best_true_regret_pct','median_true_regret_pct','mean_true_regret_pct','recall_true_top1pct']].mean().reset_index())
 dump(base/'validation.json',{'status':'PASS','scenarios':10,'models':4,'common_states_each':1024,'common_F0_pools':30,'candidate_records_per_model':900000,'ensemble_anchors':len(anchors),'single_is_frozen_member01':True,'training_tuning_or_optimization':0,'common_primary':'score-only diagnostic;25/0/15/10/10,no UE correction','state_and_pool_points_not_independent_replicates':True})

if __name__=='__main__':
 pin();install_no_compute_guard();run()
