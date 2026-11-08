from common42 import *
import re,zipfile,xml.etree.ElementTree as ET

def main():
 net=ex.Network(ex.MODEL);phall=physical();saved=saved_solutions();rows=[]
 for sid in range(1001,1011):
  ph=phall[phall.scenario_id==sid].sort_values('physical_link_id');roads=saved[str(sid)]['candidate_roads']
  for m in range(1024):
   closed=ph.is_closed.to_numpy(bool).copy();factor=ph.capacity_factor.to_numpy(float).copy();mult=ph.free_flow_time_multiplier.to_numpy(float).copy()
   for i,r in enumerate(roads):
    if m&(1<<i):closed[r-1]=False;factor[r-1]=1.;mult[r-1]=1.
   active=~closed[net.pid];cap=net.cap*factor[net.pid];fft=net.dryfft*mult[net.pid]
   active_new,fft_new,coef_new=net.state_arrays(ph,roads,m)
   assert np.array_equal(active,active_new) and np.array_equal(cap[active],net.cap[active]) and np.array_equal(fft[active],fft_new[active])
   assert np.array_equal(coef_new[active],(fft*net.alpha/net.cap**4)[active])
   rows.append({'scenario_id':sid,'subset_mask':m,'active_arcs_equal':True,'active_capacity_equal':True,'active_free_flow_time_equal':True,
    'same_alpha_and_beta4':True,'same_fixed_OD':True,'same_dry_baseline_TSTT':T0})
 csv(AUD/'S0_state_physical_pairing.csv',rows)
 settings=[
 ('physical_state','same 38 roads, depth/closure fields and restored IDs','same; checked for all 10240 masks','unchanged'),
 ('network_OD_BPR','archived directed_links/od_long; alpha per arc, beta=4','identical; active capacity factors equal one','unchanged'),
 ('dry_normalizer',str(T0),str(T0),'unchanged; never recomputed'),
 ('assignment_numerical_algorithm','link-based Frank-Wolfe','route column generation with pairwise flow equilibration','changed'),
 ('shortest_path','heap Dijkstra, strict relaxation margin 1e-12','compiled array Dijkstra, strict relaxation margin 1e-12','implementation changed'),
 ('initialization','cold free-flow all-or-nothing for a solve; tables may reuse previously cached result','cold route/AON initialization for each newly solved state','cache provenance differs'),
 ('stopping_RG','5e-4; achieved RG checked without relaxed cutoff','1e-9; same solver refined to 1e-11','changed'),
 ('iteration_limits','exact wrapper attempts max_iter 1000/3000/10000; interface also retries at 3000','max_outer=20000, five equilibration sweeps per outer iteration','different counting units, not directly comparable'),
 ('line_or_pair_search','FW Brent root, xtol=rtol=1e-12, maxiter=100','pairwise safeguarded Newton/bisection max22 steps; derivative threshold 1e-11*max(1,|g0|)','changed'),
 ('path_storage','link-flow representation','maximum128 stored routes per OD; overflow returns failure','changed'),
 ('internal_small_values','direction<=1e-14; endpoint derivative thresholds1e-11; small flow<1e-10 zeroed','flow transfer skips<=1e-9; improvement skip max(1e-9, |bestcost|*target*.01)','changed; target-dependent internal skip also documented'),
 ('cost_table_scope','all1024 states per old scenario','all1024 states at1e-9;194 selected states total at1e-11','1e-11 is not a full-table optimum certification')]
 csv(AUD/'S0_solver_settings_comparison.csv',[{'setting':a,'archived_FW':b,'high_precision_path_solver':c,'comparison':d} for a,b,c,d in settings])
 d=frame(S1/'S1_state_precision_comparison.csv');csv(S1/'S1_largest_state_changes_top100.csv',d.nlargest(100,'relative_TSTT_change'))
 st=frame(S3/'S3_refinement_states.csv')
 st['terminal_state_zero_objective_weight']=st.subset_mask.eq(1023)
 csv(S3/'S3_refinement_states.csv',st)
 # Original texts are audited only; no manuscript source is silently rewritten.
 docs=[Path(r'E:\jcr2区意见\导师分享_初稿与正式代码_20261026\01_投稿初稿与补充材料\投稿初稿_Manuscript(1).docx'),
       Path(r'E:\jcr2区意见\导师分享_初稿与正式代码_20261026\01_投稿初稿与补充材料\Supplementary_Material.docx')]
 wordrows=[];sources=[];ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
 pattern=re.compile(r'exact\s+(?:optimum|solution|regret|reference)|exact\s+optimal|exactness|true\s+(?:UE[- ]model\s+)?optimum',re.I)
 for path in docs:
  sources.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'role':'read-only submitted-text terminology audit'})
  with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('word/document.xml'))
  for i,p in enumerate(root.findall('.//w:body//w:p',ns),1):
   text=''.join(x.text or '' for x in p.findall('.//w:t',ns))
   matches=list(pattern.finditer(text))
   for hit in matches:
    qualifier=bool(re.search('conditional|numerically|state.cost.table',text,re.I))
    wordrows.append({'document':path.name,'absolute_source_path':str(path),'OOXML_paragraph_index':i,'matched_phrase':hit.group(),
      'paragraph':text,'has_local_conditional_or_numerical_qualifier':qualifier,
      'proposed_action':'retain if referring to exact combinatorial DP; verify qualifier remains explicit' if qualifier else 'qualify as exact optimum of the numerically evaluated UE state-cost table or conditional exact reference, according to context',
      'status':'AUDITED_NOT_APPLIED_TO_WORD','physical_accuracy_certification_claim_permitted':False})
 csv(S5/'S5_exactness_wording_audit.csv',wordrows);dump(S5/'manuscript_source_manifest.json',sources)
 # Add additional source inputs with hashes before final immutability checks.
 manifest=frame(AUD/'S0_input_manifest.csv');add=[];known=set(manifest.absolute_path)
 extras=[(ex.MODEL/'models/scenario_adapter.py','original closure/capacity mapping source'),(ex.MODEL/'models/__init__.py','original model exports'),
   (FORMAL/'inputs/new_validation/final_scenarios_physical_links.csv','new30 physical inputs')]+[(Path(x['path']),x['role']) for x in sources]
 for path,role in extras:
  if str(path) in known:continue
  add.append({'relative_path':os.path.relpath(path,OUT),'absolute_path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'data_role':role,
      'filesystem_mtime_local':datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),'version_date_note':'Added source audit during execution; source not modified'})
 csv(AUD/'S0_input_manifest.csv',pd.concat([manifest,pd.DataFrame(add)],ignore_index=True))
 print('Physical state pairing PASS',len(rows),'states; exactness wording matches',len(wordrows),flush=True)

if __name__=='__main__':main()
