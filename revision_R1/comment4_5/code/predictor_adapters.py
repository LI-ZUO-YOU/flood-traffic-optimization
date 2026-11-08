from common45 import *

class FrozenFeatures120:
 def __init__(self):
  self.preprocessor=js(E.SOURCE/'surrogate/final_ensemble/preprocessor_v2.json')
  for key in ['depth_mean','depth_std','aggregate_mean','aggregate_std','baseline_flow','betweenness']:setattr(self,key,np.asarray(self.preprocessor[key],dtype=np.float64))
 transform=E.api.SurrogateV2.transform

def subset_states(ph,roads):
 states=[]
 for mask in range(1024):
  restored=np.zeros(38,dtype=np.uint8)
  for bit,road in enumerate(roads):
   if mask&(1<<bit):restored[road-1]=1
  states.append({'depth_m':ph.depth_m.to_numpy(float),'initial_closed':ph.is_closed.to_numpy(np.uint8),'restored':restored})
 return states

class SingleMLP(FrozenFeatures120):
 def __init__(self):
  super().__init__();import torch;torch.set_num_threads(1)
  self.torch=torch;self.path=sorted((E.SOURCE/'surrogate/final_ensemble/models').glob('member_*.pt'))[0]
  self.model=E.api.RecoveryMLPV2.build();self.model.load_state_dict(torch.load(self.path,map_location='cpu',weights_only=False)['state_dict']);self.model.eval()
 def predict_members(self,states):
  X=self.transform(states)
  with self.torch.no_grad():return self.model(self.torch.from_numpy(X)).numpy().astype(np.float64)[:,None]

class SimpleRegressor(FrozenFeatures120):
 def __init__(self,variant):
  super().__init__();import joblib
  self.model=joblib.load(OUT/f'01_freeze_and_regression/simple_models/{variant}.joblib')
 def predict_members(self,states):return np.asarray(self.model.predict(self.transform(states)),dtype=np.float64)[:,None]

def predictor(variant):
 if variant=='F9_NO_SURROGATE':return None
 if variant=='F6_SINGLE_MLP':return SingleMLP()
 if variant in ['F7_RIDGE','F8_TREE']:return SimpleRegressor(variant)
 import torch;torch.set_num_threads(1)
 return E.api.SurrogateV2(E.SOURCE/'surrogate/final_ensemble')
