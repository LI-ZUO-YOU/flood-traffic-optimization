from common45 import *
import argparse

def main():
 ap=argparse.ArgumentParser(description='Fit fixed Ridge and HGB only on archived original training splits; no model selection')
 ap.add_argument('--manifest',default=str(OUT/'00_audit/source_manifest.csv'));ap.add_argument('--output',default=str(OUT/'01_freeze_and_regression'));args=ap.parse_args()
 verify_sources();pin();from predictor_adapters import FrozenFeatures120
 from sklearn.linear_model import Ridge
 from sklearn.ensemble import HistGradientBoostingRegressor
 from threadpoolctl import threadpool_limits
 import joblib
 target=Path(args.output)/'simple_models';require_new_output(target)
 firewall=js(OUT/'00_audit/data_split_firewall.json');inputs=firewall['training_splits'];loadstart=time.perf_counter()
 train=pd.concat([frame(inputs[n]['path']) for n in ['train_original','train_expansion']],ignore_index=True,sort=False)
 assert len(train)==3178 and train.state_hash.nunique()==3178
 ids=set(map(int,train.scenario_id));assert ids==set(firewall['allow_training_scenario_ids']) and ids.isdisjoint(firewall['forbid_training_scenario_ids'])
 loadwall=time.perf_counter()-loadstart;states=[]
 for row in train.to_dict('records'):
  states.append({'depth_m':np.array([row[f'd_depth_m_pl{k:03d}'] for k in range(1,39)]),'initial_closed':np.array([row[f'd_closed_pl{k:03d}'] for k in range(1,39)]),'restored':np.array([row[f'r_restored_pl{k:03d}'] for k in range(1,39)])})
 t=time.perf_counter();features=FrozenFeatures120();X=features.transform(states);y=train.log_tstt_ratio.to_numpy(np.float64);prep=time.perf_counter()-t
 assert X.shape==(3178,120) and np.isfinite(X).all() and np.isfinite(y).all()
 assert np.allclose(y,np.log(train.tstt.to_numpy(float)/E.LEGACY_BASELINE),atol=1e-10,rtol=1e-10)
 records=[]
 models={'F7_RIDGE':Ridge(alpha=1.0),'F8_TREE':HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=15,learning_rate=.05,min_samples_leaf=20,l2_regularization=.1,random_state=2026102905,early_stopping=False)}
 with threadpool_limits(limits=1):
  for name,m in models.items():
   t=time.perf_counter();m.fit(X,y);wall=time.perf_counter()-t
   pred=m.predict(X[:5]);assert np.isfinite(pred).all()
   path=target/f'{name}.joblib';joblib.dump(m,path)
   records.append({'variant':name,'training_rows':3178,'training_scenarios':len(ids),'features':120,'target':'original archived log(TSTT/TSTT0)','fit_wall_seconds':wall,'data_load_shared_seconds':loadwall,'feature_transform_shared_seconds':prep,'parameters':json.dumps(m.get_params(),sort_keys=True),'model_sha256':sha(path),'early_stopping':False,'parameter_search':False,'holdout_labels_read':False,'weights':'unweighted original training rows; no test fitting','at':now()})
   print(json.dumps({'model':name,'fit_seconds':wall,'sha256':sha(path)}),flush=True)
 csv(target/'training_record.csv',records)
 dump(target/'training_firewall_validation.json',{'status':'PASS','actual_training_ids':sorted(ids),'actual_raw_label_sources':inputs,'label_source_sha256_matches_original':all(sha(v['path'])==v['sha256'] for v in inputs.values()),'frozen_preprocessor_sha256':sha(E.SOURCE/'surrogate/final_ensemble/preprocessor_v2.json'),'input_X_SHA256':hashlib.sha256(X.tobytes()).hexdigest(),'input_y_SHA256':hashlib.sha256(y.tobytes()).hexdigest(),'full_ensemble_retrained':False,'retrospective_or_new_scenario_labels_used':False,'models_fixed_without_tuning':True,'HGB_early_stopping_explanation':'False explicitly; auto would also disable early stopping for3178 rows','global_variant_protocol_frozen':False,'F9_AB_resolution':'pending user clarification; these fixed training models are independent of that search decision'})
 verify_sources()

if __name__=='__main__':main()
