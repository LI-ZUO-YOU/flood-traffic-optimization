from s4_common import *
def main():
 source=OUT/'optimization/scenario_4405/m_10/proposed/rep_01'
 target=OUT/'logs/premeasurement_interruptions/scenario_4405_m10_proposed_rep01_attempt0'
 assert source.resolve().is_relative_to(OUT.resolve()) and target.resolve().is_relative_to(OUT.resolve())
 mon=js(source/'monitor.json');assert mon['resource_stop']=='CONCURRENT_PYTHON_TASK' and mon['online_wall'] is None
 assert not (source/'ready.json').exists() and not (source/'timing.json').exists(),'Measured attempt must never be replaced'
 if (source/'physical_UE_journal.csv').exists():assert (source/'physical_UE_journal.csv').stat().st_size==0,'No experiment UE rows may be removed'
 assert not (OUT/'00_lock/optimization_outputs_freeze.json').exists()
 assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True)
 files={p.name:sha(p) for p in source.iterdir() if p.is_file()};source.rename(target)
 for name,h in files.items():assert sha(target/name)==h
 dump(OUT/'logs/premeasurement_interruption_audit.json',{'at':now(),'case':[4405,10,'proposed',1],'stage':'before ready/timing, no scenario UE journal rows, no output objective available','reason':'controller detected unknown concurrent Python; no other Python process present at restart check','all_original_attempt_files_retained':str(target),'file_hashes':files,'restart_rule':'same predeclared task and seed only; no measured outputs replaced, no parameters or cap changed','not_a_solver_or_scaling_failure':True})
 print('Premeasurement interruption archived intact; same scheduled task may resume',flush=True)
if __name__=='__main__':main()
