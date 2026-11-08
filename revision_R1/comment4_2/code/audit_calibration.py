from common42 import *

def main():
 raw=frame(BASE/'development/precision_stability.csv');pairs=frame(BASE/'development/precision_pair_differences.csv')
 assert len(raw)==180 and len(pairs)==60
 rows=[];computed=[]
 for (sid,mask),g in raw.groupby(['scenario_id','subset_mask']):
  assert len(g)==3 and set(g.tolerance)=={1e-7,1e-9,1e-11}
  assert g.converged.all() and g.relative_gap.le(g.tolerance).all()
  a=g[g.tolerance==1e-9].iloc[0];b=g[g.tolerance==1e-11].iloc[0]
  r=abs(a.tstt-b.tstt)/b.tstt;computed.append(r)
  record=pairs[(pairs.scenario_id==sid)&(pairs.subset_mask==mask)].iloc[0]
  assert abs(r-record.relative_tstt_difference)<1e-20
  rows.append({'scenario_id':sid,'subset_mask':mask,'tstt_primary_1e9':a.tstt,'tstt_refined_1e11':b.tstt,
     'primary_actual_RG':a.relative_gap,'refined_actual_RG':b.relative_gap,'relative_TSTT_difference_recomputed':r})
 assert max(1e-7,10*max(computed))==KAPPA
 csv(AUD/'S0_equivalence_calibration_60pairs.csv',rows)
 scopes=[]
 for tolerance,g in raw.groupby('tolerance'):scopes.append({'tolerance':tolerance,'development_states':len(g),'max_actual_RG':g.relative_gap.max(),'all_converged':g.converged.all()})
 csv(AUD/'S0_calibration_RG_scope.csv',scopes)
 dump(AUD/'equivalence_calibration_audit.json',{'status':'PASS','original_pair_count':60,'raw_state_tolerance_records':180,
   'max_relative_TSTT_difference':max(computed),'reproduced_kappa':KAPPA,'formula':'max(1e-7, 10*max_relative_TSTT_difference_of_1e-9_vs_1e-11_pairs)',
   'max_observed_relative_gap_field_scope':'Maximum over all three calibration tiers (1e-7,1e-9,1e-11), not maximum of the 1e-9 primary tables',
   'rule_unchanged':True,'empirical_not_rigorous_error_bound':True})
 manifest=frame(AUD/'S0_input_manifest.csv');known=set(manifest.absolute_path);add=[]
 for path in [BASE/'development/precision_stability.csv',BASE/'development/precision_pair_differences.csv',BASE/'development/precision_protocol.json',BASE/'code/develop_and_freeze.py']:
  if str(path) not in known:add.append({'relative_path':os.path.relpath(path,OUT),'absolute_path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'data_role':'original frozen kappa calibration provenance','filesystem_mtime_local':datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),'version_date_note':'calibration reused; not recomputed UE'})
 csv(AUD/'S0_input_manifest.csv',pd.concat([manifest,pd.DataFrame(add)],ignore_index=True))
 note='\n\n补充核查：κ已从60对真实开发状态独立复算，规则为 max(1e-7, 10×最大1e-9/1e-11相对TSTT变化)，与冻结值逐位相同。protocol中max_observed_relative_gap约9.9856e-8是全部三档开发记录（含1e-7）的最大值，不是1e-9主表最大值；原始源代码与分档CSV已确认其统计范围，未修改冻结字段。\n'
 p=AUD/'S0_gap_report.md';text=p.read_text(encoding='utf-8')
 if '补充核查：κ已从60对' not in text:p.write_text(text+note,encoding='utf-8')
 print('Frozen kappa calibration independently reproduced from 60 pairs.',flush=True)

if __name__=='__main__':main()
