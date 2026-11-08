import time
BOOT=time.perf_counter()
from common44 import *
from components44 import build,gen
def main():
 sid=int(sys.argv[1]);m=int(sys.argv[2]);rep=int(sys.argv[3]);folder=Path(sys.argv[4]);folder.mkdir(parents=True,exist_ok=True)
 pin();import torch;torch.set_num_threads(1)
 # This worker cannot accidentally perform UE solves, including via inherited helpers.
 def forbidden(*a,**k):raise RuntimeError('S3 forbids all new UE solves')
 frozen.Network.solve=forbidden
 loaded=time.perf_counter();predictor=frozen.api.SurrogateV2(frozen.SOURCE/'surrogate/final_ensemble');model_load=time.perf_counter()-loaded
 if sid<4000:
  data=frame(ROOT/'inputs/new_validation/final_scenarios_physical_links.csv');ph=data[data.scenario_id==sid].sort_values('physical_link_id');roads,audit=select_roads(ph,m);fixture=False
 else:ph,roads,audit,fixture=physical(sid,m)
 development=frame(ROOT/'inputs/historical_201_260.csv');dev=development[development.scenario_id==246].sort_values('physical_link_id');devroads,_=select_roads(dev,10)
 warm=time.perf_counter();gen.subset_member_losses(predictor,dev.depth_m.to_numpy(float),dev.is_closed.to_numpy(np.uint8),list(devroads));gen.successor_policy(np.zeros(4),[1,2]);warmwall=time.perf_counter()-warm
 proc=psutil.Process();cpu=proc.cpu_times();start=time.perf_counter()
 dump(folder/'ready.json',{'online_started_perf_counter':start,'started':now(),'pid':os.getpid(),'core':0,'threads':1,'RSS_baseline':proc.memory_info().rss,'model_load_wall':model_load,'imports_input_model_warm_wall':start-BOOT,'prewarm_wall':warmwall,'m16_feature_only_fixture':fixture})
 try:
  screen,stats=build(ph,roads,audit,sid,rep,predictor,folder)
  cpu2=proc.cpu_times();stats.update({'scenario_id':sid,'m':m,'replicate':rep,'feature_only_fixture':fixture,'initial_closed_count':int(ph.is_closed.sum()),'initial_network_connected':connected(ph),'cpu_process_wall_including_export':cpu2.user+cpu2.system-cpu.user-cpu.system,'worker_peak_wset':getattr(proc.memory_info(),'peak_wset',None),'new_UE_calls':0})
  dump(folder/'result.json',stats)
 except Exception as e:
  import traceback
  dump(folder/'failure.json',{'status':'SCALING_FAILURE','error_type':type(e).__name__,'reason':str(e),'traceback':traceback.format_exc(),'elapsed':time.perf_counter()-start,'new_UE_calls':0});raise
if __name__=='__main__':main()
