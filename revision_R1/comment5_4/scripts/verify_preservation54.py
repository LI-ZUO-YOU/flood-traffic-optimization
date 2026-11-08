from pathlib import Path
import sys,json,hashlib,subprocess,datetime
sys.dont_write_bytecode=True
import pandas as pd
OUT=Path(__file__).resolve().parents[1];REPO=OUT.parents[1]
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    snap=json.loads((OUT/'source_sha256.json').read_text(encoding='utf-8'));records=[]
    for i,r in enumerate(snap['files']):
        p=Path(r['path']);h=sha(p) if p.is_file() else 'MISSING'
        records.append(dict(path=str(p),before_sha256=r['sha256'],after_sha256=h,unchanged=h==r['sha256'],bytes=r['size_bytes'],is_comment5_2='revision_R1\\comment5_2\\' in str(p)))
        if i and i%5000==0:print('final source hashes',i,flush=True)
    df=pd.DataFrame(records);df.to_csv(OUT/'audit/source_preservation_final.csv',index=False)
    before=json.loads((OUT/'audit/git_before.json').read_text(encoding='utf-8'));current={}
    for label,args in [('status',['status','--porcelain=v1','-z','--untracked-files=all']),('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('tracked_diff',['diff','--binary','HEAD'])]:
        b=subprocess.check_output(['git','-C',str(REPO),*args]);(OUT/'audit'/('git_after_'+label+'.bin')).write_bytes(b);current[label]=b.decode('utf-8').split('\0') if label=='status' else b.decode('utf-8')
    def outside(rows):return sorted(r for r in rows if r and not r[3:].replace('\\','/').startswith('revision_R1/comment5_4/'))
    gitok=before['head']==current['head'] and before['branch']==current['branch'] and before['tracked_diff']==current['tracked_diff'] and outside(before['status'])==outside(current['status'])
    result=dict(status='PASS' if df.unchanged.all() and gitok else 'FAIL',checked_files=len(df),unchanged_files=int(df.unchanged.sum()),comment5_2_files=int(df.is_comment5_2.sum()),comment5_2_unchanged=bool(df[df.is_comment5_2].unchanged.all()),git_outside_new_directory_unchanged=gitok,git_head=current['head'].strip(),git_branch=current['branch'].strip(),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (OUT/'audit/source_preservation_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
