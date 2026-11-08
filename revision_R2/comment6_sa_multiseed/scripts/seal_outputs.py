from common import *
def main():
 validation=js(OUT/'final_validation.json');assert validation['status']=='PASS'
 rows=[]
 for p in sorted(OUT.rglob('*')):
  if not p.is_file() or any(x in p.relative_to(OUT).parts for x in ['runtime_cache','__pycache__']):continue
  if p.name in ['output_manifest.csv','output_manifest.sha256.json']:continue
  rows.append(dict(relative_path=p.relative_to(OUT).as_posix(),absolute_path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
 save(OUT/'output_manifest.csv',rows)
 dump(OUT/'output_manifest.sha256.json',dict(manifest='output_manifest.csv',sha256=sha(OUT/'output_manifest.csv'),files=len(rows),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),excluded=['this manifest and its hash companion (avoid circular hash)','runtime_cache/ and __pycache__/'],final_status='PASS'))
 # Immediate independent digest readback, including the large raw ledger.
 m=read(OUT/'output_manifest.csv');assert all(sha(r.absolute_path)==r.sha256 for r in m.itertuples())
 print('Final output hash manifest verified',len(rows),'files;100SA only, no extra searches',flush=True)
if __name__=='__main__':main()
