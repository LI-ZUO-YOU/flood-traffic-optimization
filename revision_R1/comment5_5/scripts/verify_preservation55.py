from common55 import *
import subprocess,datetime
def main():
 records=[]
 for i,r in enumerate(js(OUT/'audit/source_sha256.json')['files']):
  p=Path(r['path']);h=sha(p) if p.is_file() else 'MISSING';records.append(dict(path=str(p),before_sha256=r['sha256'],after_sha256=h,unchanged=h==r['sha256'],is_comment5_2='revision_R1\\comment5_2\\' in str(p),is_comment5_4='revision_R1\\comment5_4\\' in str(p)))
  if i and i%5000==0:print('final hashes',i,flush=True)
 df=save(OUT/'audit/source_preservation_final.csv',records);before=js(OUT/'audit/git_before.json');current={}
 for label,args in [('status',['status','--porcelain=v1','-z','--untracked-files=all']),('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('tracked_diff',['diff','--binary','HEAD'])]:
  b=subprocess.check_output(['git','-C',str(REPO),*args]);(OUT/'audit'/f'git_after_{label}.bin').write_bytes(b);current[label]=b.decode('utf-8').split('\0') if label=='status' else b.decode('utf-8')
 def outside(rows):return sorted(r for r in rows if r and not r[3:].replace('\\','/').startswith('revision_R1/comment5_5/'))
 gitok=all(before[k]==current[k] for k in ['head','branch','tracked_diff']) and outside(before['status'])==outside(current['status'])
 result=dict(status='PASS' if df.unchanged.all() and gitok else 'FAIL',checked_files=len(df),unchanged_files=int(df.unchanged.sum()),comment5_2_files=int(df.is_comment5_2.sum()),comment5_4_files=int(df.is_comment5_4.sum()),comment5_2_unchanged=bool(df[df.is_comment5_2].unchanged.all()),comment5_4_unchanged=bool(df[df.is_comment5_4].unchanged.all()),git_only_new_directory_changes=gitok,git_head=current['head'].strip(),git_branch=current['branch'].strip(),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 dump(OUT/'audit/source_preservation_validation.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
 if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
