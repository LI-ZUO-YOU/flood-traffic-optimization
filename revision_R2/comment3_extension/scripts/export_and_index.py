from common import *
def main():
 data=read(OUT/'raw/UE_all_logical_states.csv');folder=OUT/'raw/state_tables';folder.mkdir(exist_ok=True)
 for vid,g in data.groupby('variant_id'):save(folder/(vid+'_1024_states.csv'),g.sort_values('subset_mask'))
 files=[p for p in OUT.rglob('*') if p.is_file() and not any(s in p.relative_to(OUT).parts for s in ['runtime_cache','__pycache__']) and p.name not in ['output_manifest.csv','output_manifest.sha256']]
 save(OUT/'output_manifest.csv',[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files,key=str)]);(OUT/'output_manifest.sha256').write_text(sha(OUT/'output_manifest.csv')+'  output_manifest.csv\n',encoding='utf-8');print('Indexed',len(files),'files',flush=True)
if __name__=='__main__':main()
