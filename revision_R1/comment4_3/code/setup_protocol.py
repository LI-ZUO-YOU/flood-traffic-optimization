from common43 import *
import shutil,subprocess,sys

def main():
 target=OUT/'00_protocol_and_input_audit';pin()
 topology=core_masks();groups=[next(i for i,g in enumerate(topology) if c in g) for c in FOUR_CORES];assert len(set(groups))==4
 assert CORE in psutil.Process().cpu_affinity()
 # Query OS information without altering the power policy.
 power=subprocess.run(['powercfg','/GETACTIVESCHEME'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout.strip()
 hardware=subprocess.run(['powershell','-NoProfile','-Command','Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout.strip()
 import torch,scipy,numba
 torch.set_num_threads(1)
 from threadpoolctl import threadpool_info,threadpool_limits
 with threadpool_limits(limits=1):libinfo=threadpool_info()
 files=[PLAN,ROOT/'protocol/frozen_protocol.json',ROOT/'protocol/frozen_protocol.sha256',ROOT/'inputs/new_validation/final_scenarios_physical_links.csv',
 ROOT/'inputs/new_validation/selected_roads.json',ROOT/'inputs/historical_201_260.csv',OLD/'4.1数值结果_第二轮及最后收尾_20261028.zip']
 files += list((ROOT/'code').glob('*.py'))
 files += list((OUT/'code').glob('*.py'))
 files += [p for p in (ex.SOURCE/'code').rglob('*.py')]
 files += [p for p in (ex.SOURCE/'surrogate/final_ensemble').rglob('*') if p.is_file()]
 files += [p for p in (ex.MODEL/'data_src/SiouxFalls_flood_benchmark/processed').glob('*.csv')]
 files += [OLD/n for n in ['S2_fresh_timing.csv','S2_online_comparison.csv','S2_online_comparison_by_scenario.csv','S2_Proposed_components.csv','S2_amortization.csv','S2_offline_cost/offline_cost_summary.json']]
 for sid in range(3001,3031):
  for method in METHODS[:-1]:
   for rep in range(3) if method in STOCHASTIC else [0]:
    files += [ROOT/f'runs/query_cap/scenario_{sid}/{method}/rep_{rep:02d}'/n for n in ['result.json','logical_query_ledger.csv.gz','all_query_events.csv.gz']]
  files += [ROOT/f'exact/scenario_{sid}'/n for n in ['all_1024_states.csv.gz','exact_solution.json']]
 assert sha(ROOT/'protocol/frozen_protocol.json')==(ROOT/'protocol/frozen_protocol.sha256').read_text().strip()
 for rel,h in CFG['source_hashes'].items():assert sha(ROOT/rel)==h
 files=sorted(set(files));dump(target/'S0_manifest.json',{'created_Asia_Shanghai':now(),'files_sha256':{str(p):sha(p) for p in files},'source_versions':'4.1 original frozen v2 methods and weights; RG1e-9 same path solver as4.2'})
 shutil.copy2(PLAN,target/PLAN.name)
 schedule=[]
 for repeat in range(3):
  for sid in range(3001,3031):
   offset=(sid-3001+repeat)%len(METHODS);order=METHODS[offset:]+METHODS[:offset]
   for orderpos,method in enumerate(order):schedule.append({'task_index':len(schedule)+1,'scenario_id':sid,'method':method,'replicate':repeat,'position_within_scenario':orderpos+1})
 csv(target/'frozen_serial_schedule.csv',schedule)
 protocol={'frozen_before_timing':True,'created_Asia_Shanghai':now(),'methods':METHODS,'scenario_ids':list(range(3001,3031)),
 'stochastic_original_rep_indices':[0,1,2],'deterministic_repeats':3,'serial_tasks':450,'primary_core':CORE,'primary_processes':1,'primary_threads':1,
 'sequential_policy':'Only one main timing task at a time; no independent scientific jobs in parallel. All main methods and enumeration run in one Python process on CPU0.',
 'algorithm_seeds':'Exactly original4.1 formulas for rep0,1,2; no new algorithm seeds','run_order':'five-method cyclic Latin rotation by scenario index plus repeat index',
 'query_cap':256,'wall_clock_cap':None,'warm_policy':'UE JIT and torch loaded/prewarmed on development246; every measured run starts an empty in-memory PhysicalStore or direct independent UE solves; no flow warm-start',
 'online_scope':'includes candidate construction/screening and all search bookkeeping, UE network calls and DP; excludes initial input/model loading, JIT warm-up and disk exports; nested component times never double-counted',
 'bitwise_gate':'For every timing run compare objective.float.hex, final sequence, queries, logical event path and candidate hash to corresponding4.1 query-cap output. Stop on any mismatch.',
 'enum_serial_repeats':3,'enum4within_repeats':3,'enum4within_cores':FOUR_CORES,'enum4within_policy':'Run only after all serial tasks; one scenario at a time, four workers each solve a disjoint256-state chunk; warm pool startup separately recorded, no simultaneous other scenarios',
 'cold_start_scope':'fresh Python-process supplements for fixed scenario3001 rep0 for each of the five methods, exactly once each; includes imports/input/model/first-use JIT-cache load; warm compiled disk code cache; not an all-scenario cold-speed claim',
 'offline_training_policy':'temporary CPU single-thread reproduction of original ten-member config and original archived labels; new checkpoints never used for online tests or overwrite frozen weights',
 'offline_dataset_policy':'all3178 unique training states re-solved serially on same core atRG1e-9 solely to measure current deployment-label cost; not historical generation wall time; train timing uses original label files to preserve config',
 'fixed12s_experiment':'NOT_PERFORMED per direct user instruction; prior4.1 time-cap retained as historical supplement only',
 'statistics':'aggregate repetitions within each scenario; scenario is paired statistical unit n30. Arithmetic crossovers need positive mean saving and are not quality-matched ROI.',
 'bootstrap_resamples':20000,'bootstrap_statistical_seed':20261028043,'archive_policy':'numeric CSV results only'}
 dump(target/'frozen_4_3_protocol.json',protocol)
 evidence=[{'source':n,'status':'existing; not reused as primary B256 timing','limitation':why} for n,why in [
 ('S2_fresh_timing.csv','serial and four-scenario parallel enumeration from a different batch'),('S2_online_comparison.csv','old competitors use scenario-specific elapsed caps, not commonB256'),
 ('S2_Proposed_components.csv','inference is nested in candidate time'),('S2_amortization.csv','70.093s combines current labels with historical training loop; not same-run offline wall')]]
 csv(target/'S0_existing_evidence_audit.csv',evidence)
 environment={'created_Asia_Shanghai':now(),'platform':platform.platform(),'python':sys.version,'interpreter':sys.executable,'CPU_from_Windows':hardware,
 'logical_CPUs':psutil.cpu_count(),'physical_cores':psutil.cpu_count(False),'physical_core_logical_CPU_groups':topology,
 'RAM_bytes':psutil.virtual_memory().total,'power_scheme':power,'frequency_policy':'OS active power scheme retained; not forced to constant frequency','frequency_snapshot':psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
 'versions':{'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'numba':numba.__version__,'torch':torch.__version__},
 'thread_environment':{k:os.environ[k] for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']},'threadpools':libinfo,
 'primary_CPU_affinity':[CORE],'parallel_enum_UE_affinity':FOUR_CORES,'main_task_concurrency':1,'UE_solver':'unchanged path_column_generation_pairwise','UE_tolerance':1e-9,'TSTT_normalizer':ex.LEGACY_BASELINE,
 'initial_background_CPU_percent_per_CPU':psutil.cpu_percent(interval=1,percpu=True)}
 dump(OUT/'02_serial_B256/S2_run_environment.json',environment)
 write='''# 复杂度与计费参照

固定物理条件下m!个完整排序共享至多2^m个恢复子集成本。m=10时为3,628,800个排序、1,024个状态；实际前驱转移候选数为m·2^(m−1)=5,120，时间O(m2^m)，空间O(2^m)。本轮保持公开参照实际求解全部1,024状态，其中全恢复终态在当前目标中权重为零。

75%仅为1−256/1024的唯一状态查询数减少，不等同于实测耗时下降或对强UE-only方法的优势。完整状态枚举可在一个情景内部并行，后续DP独立串行；Proposed的自适应查询轨迹在本实现中顺序执行。本轮将两种资源配置分开报告。
'''
 (OUT/'01_complexity/S1_computational_reference.md').write_text(write,encoding='utf-8')
 print('PROTOCOL FROZEN',len(files),'source files; physical core groups',topology,'serial tasks',len(schedule),flush=True)

if __name__=='__main__':main()
