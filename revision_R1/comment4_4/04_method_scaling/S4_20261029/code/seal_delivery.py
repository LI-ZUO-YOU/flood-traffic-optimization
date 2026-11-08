from s4_common import *
import zipfile
def main():
 verify_s4();gate=js(OUT/'completion_check.json');d=frame(OUT/'analysis/S4_scale_method_runs.csv');refs=frame(OUT/'analysis/S4_exact_reference_by_m.csv')
 assert len(d)==180 and d[['scenario_id','m','method','replicate']].drop_duplicates().shape[0]==180
 assert set(d.scenario_id)==set(range(4401,4407)) and set(d.m)=={10,12,14}
 assert int((d.status=='PASS').sum())==gate['optimization_passed']
 assert int(refs.has_full_conditional_reference.sum())==gate['conditional_references_available']
 for p,h in js(OUT/'00_lock/optimization_outputs_freeze.json')['sha256'].items():assert sha(p)==h
 integrity=js(OUT/'numeric_package_integrity.json');package=Path(integrity['path']);assert sha(package)==integrity['SHA256']
 with zipfile.ZipFile(package) as z:assert z.testzip() is None and len(z.namelist())==integrity['files'] and all(p.endswith(('.csv','.csv.gz')) for p in z.namelist())
 idx=frame(OUT/'analysis/numerical_files_index.csv')
 for r in idx.itertuples(index=False):assert sha(OUT/r.relative_path)==r.sha256,r.relative_path
 manuscript=(OUT/'manuscript/4.4_正文替换与中文核对.md').read_text(encoding='utf-8');reply=(OUT/'manuscript/Reviewer1_Comment4.4_回复草稿.md').read_text(encoding='utf-8')
 excerpt=manuscript.split('## Scope and limitation replacement draft',1)[1].split('## 中文核对',1)[0].strip()
 assert '*'+excerpt+'*' in reply and 'Reviewer 2' not in reply and 'R2.' not in reply
 audit={'status':'PASS','sealed_at':now(),'planned_unique_optimization_runs':180,'successful_optimization_runs':gate['optimization_passed'],'valid_conditional_references':gate['conditional_references_available'],'numeric_index_entries_verified':len(idx),'numeric_archive_CRC':'PASS','numeric_archive_SHA256':integrity['SHA256'],'optimization_freeze_unchanged_after_references':True,'first_batch_and_formal_frozen_sources_unchanged':True,'response_quote_consistency':'PASS','reviewer_isolation':'PASS','Word_integration_pending':True,'readiness':'draft_with_placeholders'}
 dump(OUT/'delivery_QA.json',audit);gate['delivery_integrity']='PASS';dump(OUT/'completion_check.json',gate)
 # Seal only after the postprocessing parent has closed its logs.
 manifest={str(p.relative_to(OUT)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file() and 'runtime_cache' not in p.parts and '__pycache__' not in p.parts and p.name not in ['manifest.json','checksums.sha256']}
 dump(OUT/'manifest.json',{'sealed_at':now(),'files':manifest});(OUT/'checksums.sha256').write_text('\n'.join(f"{v['sha256']}  {k}" for k,v in sorted(manifest.items()))+'\n',encoding='utf-8')
 print(json.dumps(audit,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
