from common import *
import importlib.util,copy
from models.spatial_flood_field import gaussian_covariance,SPECS
from models.flood_mapping import disruption_from_depth
def generate_factors(physical,rng,corr_override=None):
 spec=SPECS['severe'];xy=physical[['mid_x_km','mid_y_km']].to_numpy(float);n=len(xy)
 blocked=int(rng.integers(spec.blocked_min,spec.blocked_max+1));wet=max(int(rng.integers(spec.wet_min,min(spec.wet_max,n)+1)),blocked)
 corr=float(rng.uniform(spec.corr_min_km,spec.corr_max_km));z=rng.standard_normal(n);center=int(rng.integers(0,n));scale=float(rng.uniform(2.,5.));amplitude=float(rng.uniform(.5,1.2));noise_closed=rng.normal(0.,.008,blocked);noise_open=rng.normal(0.,.006,wet-blocked)
 return dict(blocked=blocked,wet=wet,corr=corr,z=z.tolist(),center=center,radial_scale=scale,amplitude=amplitude,noise_closed=noise_closed.tolist(),noise_open=noise_open.tolist())
def field_from_factors(physical,f,corr=None):
 xy=physical[['mid_x_km','mid_y_km']].to_numpy(float);corr=f['corr'] if corr is None else corr
 latent=np.linalg.cholesky(gaussian_covariance(xy,corr))@np.asarray(f['z'])
 latent+=f['amplitude']*np.exp(-.5*(np.linalg.norm(xy-xy[f['center']],axis=1)/f['radial_scale'])**2)
 ranking=np.argsort(latent)[::-1];edges=physical[['physical_from','physical_to']].to_numpy(int);removed=set();chosen=[]
 for idx in ranking:
  trial=removed|{int(idx)};adj={i:[] for i in range(1,25)}
  for i,(u,v) in enumerate(edges):
   if i not in trial:adj[u].append(v);adj[v].append(u)
  seen={1};stack=[1]
  while stack:
   for v in adj[stack.pop()]:
    if v not in seen:seen.add(v);stack.append(v)
  if len(seen)==24:removed=trial
  if len(removed)==f['blocked']:break
 closed=[int(i) for i in ranking if int(i) in removed];opened=[int(i) for i in ranking if int(i) not in removed][:f['wet']-f['blocked']]
 assert len(closed)==f['blocked']
 d=np.zeros(38);ranks=np.linspace(1.,0.,len(closed),endpoint=False)
 d[closed]=np.maximum(.30+(SPECS['severe'].closed_depth_max_m-.30)*(.35+.65*ranks)+np.array(f['noise_closed']),.3001)
 ranks=np.linspace(1.,0.,len(opened),endpoint=False)
 d[opened]=np.clip(.05+(SPECS['severe'].passable_depth_max_m-.05)*(.15+.85*ranks)+np.array(f['noise_open']),0.,.299)
 p=physical.copy();p['depth_m']=d;p['is_wet']=(d>0).astype(int)
 for k,v in disruption_from_depth(d).items():p[k]=v
 return p
def main():
 init();spec=importlib.util.spec_from_file_location('original_generate',GEN);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 original_generate=module.load_generation_functions(NETROOT);physical=read(NETROOT/'data_src/SiouxFalls_flood_benchmark/processed/physical_links.csv').sort_values('physical_link_id').reset_index(drop=True)
 freeze=js(DATA/'scenario_generation_freeze_record.json');events=read(DATA/'final_scenario_rejection_log.csv');summary=read(DATA/'final_scenario_summary.csv');authority=read(PHYS);rng=np.random.default_rng(freeze['seed']);records=[];factors=[];frames=[]
 # Reproduce the actual original generator and independently trace each draw's
 # underlying random variates from the exact same pre-draw RNG state.
 for ev in events.itertuples():
  before=copy.deepcopy(rng.bit_generator.state);trace=np.random.default_rng();trace.bit_generator.state=copy.deepcopy(before)
  f=generate_factors(physical,trace);p,meta=original_generate(physical,rng);q=field_from_factors(physical,f)
  trace_err=float(np.max(abs(p.depth_m.to_numpy()-q.depth_m.to_numpy())));rng_equal=canonical(rng.bit_generator.state)==canonical(trace.bit_generator.state)
  depthhash=module.vector_hash(np.round(p.depth_m.to_numpy(float),9));maskhash=module.vector_hash(p.is_closed.to_numpy(np.uint8),np.uint8)
  sid=int(ev.scenario_id) if pd.notna(ev.scenario_id) else None;err=None;metadata_ok=True
  if sid:
   a=authority[authority.scenario_id.eq(sid)].sort_values('physical_link_id');err=float(np.max(abs(a.depth_m.to_numpy()-p.depth_m.to_numpy())));s=summary[summary.scenario_id.eq(sid)].iloc[0]
   metadata_ok=all(abs(float(meta[k])-float(s[k]))<=1e-12 for k in ['correlation_length_km','target_blocked_physical_links','target_wet_physical_links','storm_center_x_km','storm_center_y_km','storm_radial_scale_km'])
   p['scenario_id']=sid;p['draw_index']=int(ev.draw_index);frames.append(p)
  passed=bool(trace_err<=1e-12 and rng_equal and depthhash==ev.depth_sha256 and maskhash==ev.closed_mask_sha256 and metadata_ok and (err is None or err<=1e-12))
  records.append(dict(draw_index=int(ev.draw_index),scenario_id=sid,decision=ev.decision,rejection_reason=ev.reasons if isinstance(ev.reasons,str) else '',trace_max_depth_error=trace_err,baseline_max_depth_error=err,RNG_state_equal=rng_equal,depth_hash_match=depthhash==ev.depth_sha256,closed_mask_hash_match=maskhash==ev.closed_mask_sha256,metadata_match=metadata_ok,pass_=passed))
  factors.append(dict(draw_index=int(ev.draw_index),scenario_id=sid,decision=ev.decision,rng_before=before,rng_after=rng.bit_generator.state,**f))
 dump(OUT/'raw/replayed_random_factors.json',factors);save(OUT/'raw/replayed_baseline_physical.csv',pd.concat(frames));save(OUT/'audit/CRN_baseline_replay.csv',records)
 ok=all(r['pass_'] for r in records);dump(OUT/'audit/CRN_replay_validation.json',dict(status='PASS' if ok else 'PARTIAL',draws=len(records),accepted=sum(r['scenario_id'] is not None for r in records),passed=sum(r['pass_'] for r in records),exact_original_generator_used=True,depth_tolerance=1e-12))
 print('CRN replay',ok,len(records),flush=True)
if __name__=='__main__':main()
