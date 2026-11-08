"""S1/G1 read-only independent audit. Does not import any frozen project module.

Only existing CSV/JSON/NPZ/checkpoint bytes are read. Recovery subset masks and
bootstrap draws are reconstructed offline; no flood fields, traffic solutions,
model predictions, gradients, or optimization searches are generated.
"""
from __future__ import annotations
import argparse
import ast
import collections
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
import pickle
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''):
            h.update(b)
    return h.hexdigest()


def rows(p):
    op = gzip.open if str(p).endswith('.gz') else open
    with op(p, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def dump(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def table(p, data, fields=None):
    fields = fields or list(dict.fromkeys(k for x in data for k in x))
    with Path(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in data:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, tuple)) else v for k,v in x.items()})


def link(p, label=None, line=None):
    return f'[{label or Path(p).name}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'


def idlist(value):
    value = str(value).strip()
    if not value:
        return []
    if value.startswith('['):
        return [int(v) for v in json.loads(value)]
    return [int(v) for v in value.split(';') if v]


def flag(value):
    return str(value).lower() in ('true', '1')


class OpaqueStorage:
    pass


def opaque_tensor(storage, offset, shape, stride, *unused):
    return {'storage': storage, 'offset': offset, 'shape': list(shape), 'stride': list(stride)}


class MetadataOnlyUnpickler(pickle.Unpickler):
    """Whitelisted container/metadata decoding; no torch imports or tensor rebuilds."""
    def find_class(self, module, name):
        allowed = {('torch._utils','_rebuild_tensor_v2'): opaque_tensor,
                   ('torch','FloatStorage'): OpaqueStorage,
                   ('collections','OrderedDict'): collections.OrderedDict,
                   ('torch.torch_version','TorchVersion'): str}
        if (module, name) not in allowed:
            raise pickle.UnpicklingError(f'Unapproved checkpoint global: {module}.{name}')
        return allowed[module, name]

    def persistent_load(self, value):
        if len(value) != 5 or value[0] != 'storage' or value[1] is not OpaqueStorage:
            raise pickle.UnpicklingError('Unapproved persistent object')
        return {'key': value[2], 'device': value[3], 'count': value[4]}


def checkpoint_metadata(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith('/data.pkl'))
        obj = MetadataOnlyUnpickler(io.BytesIO(z.read(name))).load()
        tensor_rows = []
        prefix = name.rsplit('/', 1)[0]
        for name, tensor in obj['state_dict'].items():
            storage_path = prefix+'/data/'+tensor['storage']['key']
            data = z.read(storage_path)
            tensor_rows.append({'name':name, 'shape':tensor['shape'], 'stride':tensor['stride'],
                                'storage_sha256':hashlib.sha256(data).hexdigest(), 'storage_bytes':len(data),
                                'storage_count':tensor['storage']['count']})
        return {k:v for k,v in obj.items() if k != 'state_dict'}, tensor_rows


def first_sampler(closed, quota, seed):
    """Independent implementation of archived prefix-mask sampling, no UE calls."""
    rng = np.random.default_rng(seed)
    closed = sorted(closed)
    records = {}
    def add(subset, trajectory, stage, order):
        key = tuple(sorted(subset))
        if key not in records:
            records[key] = {'restored':list(key), 'trajectory':trajectory, 'stage':stage, 'order':list(order)}
    add([],0,0,closed)
    if quota > 1:
        add(closed,0,len(closed),closed)
    trajectory, attempts = 1, 0
    while len(records)<quota and attempts<max(1000,quota*100):
        order = rng.permutation(closed).astype(int).tolist()
        for stage in range(len(order)+1):
            add(order[:stage],trajectory,stage,order)
            if len(records)>=quota:
                break
        trajectory += 1
        attempts += 1
    fallback_count = 0
    if len(records)<quota:
        for bits in range(2**len(closed)):
            subset = [v for i,v in enumerate(closed) if bits & (1<<i)]
            n = len(records)
            add(subset,trajectory,len(subset),subset+[v for v in closed if v not in subset])
            fallback_count += len(records)-n
            trajectory += 1
            if len(records)>=quota:
                break
    return list(records.values()), {'attempted_permutations':attempts, 'fallback_added':fallback_count}


def expanded_sampler(closed, quota, seed):
    """Existing scenario subset-selection replay only; no flood regeneration."""
    rng = np.random.default_rng(seed)
    closed = sorted(closed)
    m = len(closed)
    records = {}
    def add(subset, stage):
        key = tuple(sorted(subset))
        if key not in records:
            records[key] = {'restored':list(key), 'trajectory':len(records), 'stage':stage,
                            'order':list(key)+[v for v in closed if v not in key]}
    stages = sorted({0,math.floor(.25*m),math.floor(.5*m),math.floor(.75*m),m})
    intermediate = 10 if quota<=32 else 15
    for stage in stages:
        combos = list(itertools.combinations(closed,stage))
        take = 1 if stage in (0,m) else min(intermediate,len(combos))
        for index in rng.choice(len(combos),size=take,replace=False):
            add(combos[int(index)],stage)
    stratified_count = len(records)
    all_subsets = []
    for stage in range(m+1):
        combos = list(itertools.combinations(closed,stage))
        rng.shuffle(combos)
        all_subsets.extend((combo,stage) for combo in combos)
    rng.shuffle(all_subsets)
    for combo, stage in all_subsets:
        if len(records)>=quota:
            break
        add(combo,stage)
    return list(records.values()), {'stratified_initial_count':stratified_count,
                                   'random_fill_added':len(records)-stratified_count, 'target_stages':stages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--read-only', action='store_true', required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    dest = out/'01_training'
    dest.mkdir(parents=True,exist_ok=True)
    project = out.parent.parent
    home = project/'老家/sci-jcr2区交付'
    train = home/'第二周工作/v2_day2_huber_ensemble'
    first = home/'第二周工作/day1_freeze_preprocess/week1_recovery_dataset_v1.0'
    expanded = home/'第二周工作/v2_day1_training_expansion'
    original_generator = first/'scripts/generate_recovery_dataset.py'
    expansion_generator = expanded/'run_v2_day1_training_expansion.py'
    base_generator = home/'第二周工作/final_untouched_holdout_v1.0/generate_final_holdout.py'
    training_code = train/'scripts/run_v2_day2_huber_ensemble.py'
    g0 = out/'00_audit'
    start = time.perf_counter()
    checks, limitations, events, sources, evidence = [], [], [], {}, []
    g0_manifest = rows(g0/'source_manifest.csv')
    frozen = {str(Path(r['path']).resolve()):r for r in g0_manifest}
    g0_files = [p for p in g0.rglob('*') if p.is_file()] + [out/'tools/r47_audit.py',out/'4.7_G0_文件索引.md']
    g0_seal = {p:sha(p) for p in g0_files}
    def log(event,**data):
        obj = {'utc':datetime.now(timezone.utc).isoformat(),'event':event,**data}
        events.append(obj)
        print(json.dumps(obj,ensure_ascii=False),flush=True)
        (dest/'G1_automatic_audit_log.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in events)+'\n',encoding='utf-8')
    def check(name, passed, observed, expected, source='', detail=''):
        checks.append({'check':name,'status':'PASS' if passed else 'FAIL','observed':observed,
                       'expected':expected,'source':str(source),'detail':detail})
    def limit(item,reason,source='',status='UNVERIFIED'):
        limitations.append({'item':item,'status':status,'reason':reason,'source':str(source)})
    def use(path,role):
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = sha(path)
        previous = frozen.get(str(path))
        if previous and digest != previous['sha256']:
            raise RuntimeError(f'G0 SHA mismatch: {path}; {digest} != {previous["sha256"]}')
        sources[path] = {'path':str(path),'sha256':digest,'bytes':path.stat().st_size,'role':role,
                         'G0_source_id':previous['source_id'] if previous else '',
                         'provenance':'G0_FROZEN_SOURCE' if previous else ('ACCEPTED_G0_OUTPUT_REUSED_UNCHANGED' if path.is_relative_to(g0) else 'SUPPLEMENTAL_EXISTING_ORIGINAL_FILE_NOT_REPLACING_G0')}
        return path
    def source_location(p,symbol=None,text=None):
        source = Path(p).read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        if symbol:
            node = next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==symbol)
            line, end = node.lineno,node.end_lineno
        else:
            line = next(i for i,s in enumerate(source.splitlines(),1) if text in s)
            end = line
        evidence.append({'topic':symbol or text,'path':str(p),'sha256':sources[Path(p)]['sha256'],
                         'line':line,'end_line':end})
        return link(p,symbol or text,line)
    log('start',stage='G1',G0_source_count=len(g0_manifest),python=sys.executable,numpy=np.__version__)
    preflight = []
    for i,r in enumerate(g0_manifest,1):
        p = Path(r['path'])
        actual = sha(p) if p.is_file() else 'MISSING'
        preflight.append({'path':str(p),'G0_sha256':r['sha256'],'before_G1_sha256':actual,'matches_G0':actual==r['sha256']})
        if i%500==0:
            log('G0_preflight_progress',checked=i,total=len(g0_manifest))
    table(dest/'G0_1661_source_preflight.csv',preflight)
    check('G0_source_count',len(g0_manifest)==1661,len(g0_manifest),1661,g0/'source_manifest.csv')
    check('all_G0_source_hashes_match',all(x['matches_G0'] for x in preflight),sum(x['matches_G0'] for x in preflight),1661,g0/'source_manifest.csv')
    if not all(x['matches_G0'] for x in preflight):
        dump(dest/'G1_validation.json',{'stage':'G1','status':'STOP_SOURCE_HASH_MISMATCH','checks':checks})
        return 1
    for p in [g0/'source_manifest.csv',g0/'code_version_relations.csv',g0/'manifest_binding_checks.csv',g0/'g0_validation.json']:
        use(p,'accepted_G0_evidence')
    for p in [original_generator,expansion_generator,base_generator,training_code,
              train/'artifact_manifest.json',train/'bootstrap_scenarios_v2.json',train/'combined_training_manifest.json',
              train/'ensemble_training_config_v2.json',train/'preprocessor_v2.json',train/'v2_day2_protocol_pre_registered.json',
              train/'ensemble_training_summary.csv',train/'ensemble_predictions_raw_v2.csv.gz',train/'processed/preprocessed_train_v2.npz',
              first/'recovery_dataset_config.json',expanded/'v2_day1_protocol_pre_registered.json',expanded/'scenarios/metadata.json',
              home/'第一周工作/SiouxFalls_UE_flood_models/scripts/generate_connected_flood_dataset.py',
              home/'第一周工作/SiouxFalls_UE_flood_models/models/spatial_flood_field.py']:
        use(p,'original_training_or_sampling_source')
    archived_bindings = rows(g0/'manifest_binding_checks.csv')
    training_hash = sources[training_code]['sha256']
    check('original_training_code_bound_to_G0',any(x['target_path']==str(training_code) and x['status']=='PASS' and x['expected_sha256']==training_hash for x in archived_bindings),training_hash,'G0 original asset manifest PASS',training_code)
    code_text = training_code.read_text(encoding='utf-8-sig')
    constants = {}
    for node in ast.parse(code_text).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            try: constants[node.targets[0].id]=ast.literal_eval(node.value)
            except (ValueError,TypeError): pass
    expected_constants={'EARLY_STOPPING_PATIENCE':100,'MIN_DELTA':1e-7,'MAX_EPOCHS':1000,'LR_PATIENCE':25,'LR_FACTOR':.5,'MIN_LR':1e-6}
    for key,value in expected_constants.items():
        check('frozen_constant_'+key,constants.get(key)==value,constants.get(key),value,training_code)
    raw_paths={'initial_1500':first/'recovery_states_train.csv','expansion_1678':expanded/'recovery/v2_new_training_states.csv.gz',
               'calibration':first/'recovery_states_calibration.csv','internal_ID':first/'recovery_states_test_id.csv',
               'internal_severe':first/'recovery_states_test_severe.csv'}
    datasets={name:rows(use(path,'original_raw_label_CSV')) for name,path in raw_paths.items()}
    combined=datasets['initial_1500']+datasets['expansion_1678']
    all_states=[]
    validity=[]
    by_source_scenario={}
    for name,data in datasets.items():
        grouped=collections.defaultdict(list)
        for csv_line,r in enumerate(data,2):
            sid=int(r['scenario_id'])
            closed=[i for i in range(1,39) if int(r[f'd_closed_pl{i:03d}'])==1]
            restored=[i for i in range(1,39) if int(r[f'r_restored_pl{i:03d}'])==1]
            depth=np.array([float(r[f'd_depth_m_pl{i:03d}']) for i in range(1,39)],dtype=np.float64)
            restored_flags=np.array([float(r[f'r_restored_pl{i:03d}']) for i in range(1,39)])
            digest=hashlib.sha256(np.concatenate((np.round(depth,9),restored_flags)).tobytes()).hexdigest()
            expected_range={'mild':(1,3),'moderate':(4,7),'severe':(8,12)}[r['severity']]
            tests={'restored_subset_closed':set(restored)<=set(closed),
                   'initial_closed_count':len(closed)==int(r['initial_closed_count']),
                   'restored_count':len(restored)==int(r['restored_count']),
                   'remaining_count':len(set(closed)-set(restored))==int(r['remaining_closed_count']),
                   'initial_links_field':idlist(r['initial_closed_physical_links'])==closed,
                   'remaining_links_field':idlist(r['remaining_closed_physical_links'])==[v for v in closed if v not in restored],
                   'state_hash':digest==r['state_hash'],
                   'source_stage':int(r['source_stage'])==len(restored),
                   'severity_closed_range':expected_range[0]<=len(closed)<=expected_range[1],
                   'closure_matches_depth_threshold':closed==[i+1 for i,d in enumerate(depth) if d>=.30],
                   'recovery_fraction':math.isclose(float(r['recovery_fraction']),len(restored)/len(closed) if closed else 1,abs_tol=1e-14)}
            if 'restored_physical_links' in r:
                tests['restored_links_field']=idlist(r['restored_physical_links'])==restored
            order=idlist(r['source_restoration_order'])
            tests['order_is_permutation_closed']=len(order)==len(closed) and set(order)==set(closed)
            tests['restored_equals_order_prefix']=set(order[:len(restored)])==set(restored)
            failed=[k for k,v in tests.items() if not v]
            validity.append({'source':name,'csv_line':csv_line,'state_id':r['state_id'],'scenario_id':sid,
                             'mask':sum(1<<i for i,v in enumerate(closed) if v in restored),
                             'state_hash_raw':r['state_hash'],'state_hash_recomputed':digest,
                             'status':'PASS' if not failed else 'FAIL','failed_checks':failed})
            r['_closed']=closed;r['_restored']=restored;r['_depth']=depth;r['_source']=name;r['_csv_line']=csv_line
            grouped[sid].append(r)
            all_states.append(r)
        by_source_scenario[name]=dict(grouped)
    table(dest/'state_integrity_audit.csv',validity)
    check('all_raw_state_integrity',all(x['status']=='PASS' for x in validity),sum(x['status']=='PASS' for x in validity),len(validity),'state_integrity_audit.csv','含训练3178+诊断900；扩展CSV没有restored links列时由38维恢复标志重建')
    for label,data,expected_rows,expected_ids in [('initial_1500',datasets['initial_1500'],1500,set(range(1,61))),('expansion_1678',datasets['expansion_1678'],1678,set(range(201,261))),('combined',combined,3178,set(range(1,61))|set(range(201,261)))]:
        check(label+'_rows',len(data)==expected_rows,len(data),expected_rows,raw_paths.get(label,'two raw CSVs'))
        actual={int(r['scenario_id']) for r in data}
        check(label+'_scenario_ids',actual==expected_ids,sorted(actual),sorted(expected_ids),raw_paths.get(label,'two raw CSVs'))
    check('training_unique_state_ids',len({r['state_id'] for r in combined})==len(combined),len({r['state_id'] for r in combined}),3178)
    check('training_unique_state_hashes',len({r['state_hash'] for r in combined})==len(combined),len({r['state_hash'] for r in combined}),3178)
    check('training_unique_scenario_mask',len({(int(r['scenario_id']),tuple(r['_restored'])) for r in combined})==len(combined),len({(int(r['scenario_id']),tuple(r['_restored'])) for r in combined}),3178)
    severity_rows=[]
    for label,data in [('initial_1500',datasets['initial_1500']),('expansion_1678',datasets['expansion_1678']),('combined',combined)]:
        for sev in ('mild','moderate','severe'):
            part=[r for r in data if r['severity']==sev]
            ids={int(r['scenario_id']) for r in part}
            counts=collections.Counter(int(r['scenario_id']) for r in part)
            severity_rows.append({'source_batch':label,'severity':sev,'scenario_count':len(ids),'state_count':len(part),
                                  'states_per_scenario_mean':len(part)/len(ids) if ids else '',
                                  'states_per_scenario_min':min(counts.values()) if counts else '',
                                  'states_per_scenario_max':max(counts.values()) if counts else '',
                                  'scenario_ids':sorted(ids),'raw_source':str(raw_paths[label]) if label in raw_paths else 'initial_1500 + expansion_1678'})
    table(dest/'training_scenario_severity_recomputed.csv',severity_rows)
    for sev,n_scen,n_states in [('mild',50,236),('moderate',55,2042),('severe',15,900)]:
        row=next(r for r in severity_rows if r['source_batch']=='combined' and r['severity']==sev)
        check('raw_recomputed_'+sev,row['scenario_count']==n_scen and row['state_count']==n_states,
              {'scenarios':row['scenario_count'],'states':row['state_count']},{'scenarios':n_scen,'states':n_states},'raw training CSVs, not manifest')

    # Reconstruct quotas and existing masks independently. No archived generator is imported.
    original_part=by_source_scenario['initial_1500']
    quotas={sid:2**len(part[0]['_closed']) if part[0]['severity']=='mild' else 0 for sid,part in original_part.items()}
    remaining=1500-sum(quotas.values())
    eligible=[sid for sid,part in original_part.items() if part[0]['severity']=='moderate']
    while remaining>0:
        progressed=False
        for sid in eligible:
            if quotas[sid]<2**len(original_part[sid][0]['_closed']):
                quotas[sid]+=1;remaining-=1;progressed=True
                if not remaining:break
        if not progressed:raise RuntimeError('Independent initial quota allocation stalled')
    sampling=[]
    scenario_stats=[]
    for batch in ('initial_1500','expansion_1678'):
        for sid,part in by_source_scenario[batch].items():
            closed=part[0]['_closed'];m=len(closed);severity=part[0]['severity']
            quota=quotas[sid] if batch=='initial_1500' else min(2**m,{'mild':8,'moderate':32,'severe':60}[severity])
            seed=(202608031 if batch=='initial_1500' else 202608052)+sid
            replay,details=(first_sampler if batch=='initial_1500' else expanded_sampler)(closed,quota,seed)
            actual=[{'restored':r['_restored'],'trajectory':int(r['source_trajectory_id']),'stage':int(r['source_stage']),
                     'order':idlist(r['source_restoration_order'])} for r in part]
            matches=(replay==actual)
            stable=all(r['_closed']==closed and np.array_equal(r['_depth'],part[0]['_depth']) and r['severity']==severity for r in part)
            sampling.append({'source_batch':batch,'scenario_id':sid,'severity':severity,'initial_closed_count':m,
                             'available_subsets':2**m,'quota_recomputed':quota,'observed_states':len(part),
                             'quota_matches':quota==len(part),'state_seed':seed,'closed_links':closed,
                             'all_mask_and_order_metadata_match_replay':matches,'scenario_features_stable':stable,
                             'empty_set_present':any(not r['_restored'] for r in part),
                             'full_set_present':any(len(r['_restored'])==m for r in part),
                             'subset_coverage_fraction':len(part)/(2**m),**details,
                             'source_CSV':str(raw_paths[batch]),'generator':str(original_generator if batch=='initial_1500' else expansion_generator)})
            scenario_stats.append({'source_batch':batch,'scenario_id':sid,'severity':severity,'initial_closed_count':m,
                                   'state_count':len(part),'restored_count_min':min(len(r['_restored']) for r in part),
                                   'restored_count_max':max(len(r['_restored']) for r in part),
                                   'state_coverage':len(part)/(2**m)})
    table(dest/'recovery_sampling_audit.csv',sampling)
    table(dest/'training_scenario_summary_recomputed.csv',scenario_stats)
    check('all_120_scenario_quota_and_sampler_replay',all(r['quota_matches'] and r['all_mask_and_order_metadata_match_replay'] and r['scenario_features_stable'] and r['empty_set_present'] and r['full_set_present'] for r in sampling),sum(r['quota_matches'] and r['all_mask_and_order_metadata_match_replay'] for r in sampling),120,'recovery_sampling_audit.csv')
    stage_counts=collections.Counter((r['_source'],r['severity'],len(r['_closed']),len(r['_restored'])) for r in combined)
    stage_rows=[{'source_batch':k[0],'severity':k[1],'initial_closed_count':k[2],'restored_count':k[3],
                 'recovery_fraction':k[3]/k[2],'state_count':v} for k,v in sorted(stage_counts.items())]
    table(dest/'recovery_stage_distribution.csv',stage_rows)
    closed_groups=collections.defaultdict(list)
    for r in scenario_stats:closed_groups[(r['source_batch'],r['severity'],r['initial_closed_count'])].append(r)
    table(dest/'initial_closed_count_distribution.csv',[{'source_batch':k[0],'severity':k[1],'initial_closed_count':k[2],
          'scenario_count':len(part),'state_count':sum(r['state_count'] for r in part)} for k,part in sorted(closed_groups.items())])
    log('training_reconstruction_complete',scenarios=len(sampling),states=len(combined),sampler_exact_matches=sum(r['all_mask_and_order_metadata_match_replay'] for r in sampling))

    # Firewalls: scenario IDs AND complete 38-link physical signatures.
    final_summary=use(home/'第二周工作/final_untouched_holdout_v1.0/scenarios/scenario_summary.csv','supplemental_original_historical_holdout_IDs')
    final_physical=use(home/'第二周工作/final_untouched_holdout_v1.0/scenarios/flood_scenarios_physical_links.csv','supplemental_original_historical_holdout_physical_signature_only')
    holdout_provenance=use(out.parent/'4.1专项返修_20261026/正式模拟_v2/inputs/recovered_source_provenance.json','supplemental_existing_4_1_holdout_hash_record')
    expected_holdout_hash=load(holdout_provenance)['historical_121_160']['expected_freeze_sha256']
    check('historical_final_physical_matches_existing_4_1_record_hash',sha(final_physical)==expected_holdout_hash,sha(final_physical),expected_holdout_hash,holdout_provenance,'该4.1来源记录也是G1新增只读证据，不能声称已被G0的1661项冻结')
    physical_groups=collections.defaultdict(list)
    for r in rows(final_physical):physical_groups[int(r['scenario_id'])].append(r)
    def signature(depth,closed_flags):
        return hashlib.sha256(np.concatenate([np.round(np.asarray(depth,dtype=float),9),np.asarray(closed_flags,dtype=float)]).tobytes()).hexdigest()
    split_ids={'train':{int(r['scenario_id']) for r in combined},
               **{name:{int(r['scenario_id']) for r in data} for name,data in datasets.items() if name not in ('initial_1500','expansion_1678')},
               'historical_final':{int(r['scenario_id']) for r in rows(final_summary)}}
    split_sigs={}
    signatures=[]
    for name,data in [('train',combined),('calibration',datasets['calibration']),('internal_ID',datasets['internal_ID']),('internal_severe',datasets['internal_severe'])]:
        per_sid={int(r['scenario_id']):r for r in data}
        split_sigs[name]=set()
        for sid,r in per_sid.items():
            sig=signature(r['_depth'],[int(r[f'd_closed_pl{i:03d}']) for i in range(1,39)])
            split_sigs[name].add(sig)
            signatures.append({'split':name,'scenario_id':sid,'physical_signature':sig})
    split_sigs['historical_final']=set()
    for sid,part in physical_groups.items():
        part=sorted(part,key=lambda r:int(r['physical_link_id']))
        sig=signature([float(r['depth_m']) for r in part],[int(r['is_closed']) for r in part])
        split_sigs['historical_final'].add(sig)
        signatures.append({'split':'historical_final','scenario_id':sid,'physical_signature':sig})
    leakage=[]
    for a,b in itertools.combinations(split_ids,2):
        overlap=sorted(split_ids[a]&split_ids[b]);duplicates=sorted(split_sigs[a]&split_sigs[b])
        leakage.append({'split_A':a,'split_B':b,'scenario_count_A':len(split_ids[a]),'scenario_count_B':len(split_ids[b]),
                        'scenario_ID_overlap':overlap,'physical_signature_overlap_count':len(duplicates),
                        'status':'PASS' if not overlap and not duplicates else 'FAIL'})
    expected_splits={'calibration':set(range(61,81)),'internal_ID':set(range(81,101)),
                     'internal_severe':set(range(101,121)),'historical_final':set(range(121,161))}
    for name,want in expected_splits.items():
        check('split_'+name,split_ids[name]==want,sorted(split_ids[name]),sorted(want))
    check('all_split_pair_ID_and_physical_signature_disjoint',all(r['status']=='PASS' for r in leakage),len([r for r in leakage if r['status']=='PASS']),len(leakage),'train_calibration_test_leakage_checks.csv')
    table(dest/'train_calibration_test_leakage_checks.csv',leakage)
    table(dest/'scenario_physical_signature_firewall.csv',signatures)
    # NPZ is numeric-only reading; object arrays are not unpickled.
    with np.load(train/'processed/preprocessed_train_v2.npz',allow_pickle=False) as npz:
        ids=np.array([int(r['scenario_id']) for r in combined])
        raw_counts=collections.Counter(ids.tolist())
        weights=np.array([1/raw_counts[s] for s in ids],dtype=np.float32)
        npz_ok=(np.array_equal(npz['scenario_id'],ids) and np.array_equal(npz['sample_weight'],weights)
                and np.array_equal(npz['y_log_tstt_ratio'],np.array([float(r['log_tstt_ratio']) for r in combined],dtype=np.float32))
                and np.array_equal(npz['restored_count'],np.array([len(r['_restored']) for r in combined])))
        check('original_preprocessed_NPZ_raw_label_and_weights_alignment',npz_ok,{'shape':list(npz['X'].shape),'scenario_rows':len(npz['scenario_id'])},'3178 rows, same ordered training IDs/y/restored counts/sample weights',train/'processed/preprocessed_train_v2.npz')
    # Source locations are recorded without importing source modules.
    loc_training=source_location(training_code,'train_member')
    loc_main=source_location(training_code,'main')
    loc_boot=source_location(training_code,'make_bootstrap_plan')
    loc_weight=source_location(training_code,'scenario_balanced_weights')
    loc_first=source_location(original_generator,'generate_masks')
    loc_quota=source_location(original_generator,'distribute_quotas')
    loc_exp=source_location(expansion_generator,'stratified_masks')
    loc_expquota=source_location(expansion_generator,'quota_by_scenario')
    loc_ue_first=source_location(original_generator,'_solve_task')
    loc_ue_exp=source_location(base_generator,'solve_task')
    loc_exp_main=source_location(expansion_generator,'main')
    scheduler_call='scheduler.step(oob_loss)' in code_text
    freeze_comment=code_text.index('for index, member in enumerate(bootstrap["members"], start=1)') < code_text.index('for split in ("calibration", "internal_id", "internal_severe")')
    check('static_scheduler_same_oob_loss',scheduler_call,scheduler_call,True,training_code,'静态源码支持；独立运行时监控身份未获得')
    check('static_all_weights_saved_before_diagnostic_read',freeze_comment and 'torch.save(checkpoint, model_path)' in code_text,freeze_comment,True,training_code,'main串行10成员完成后读取外部诊断CSV，不等同系统访问日志')
    limit('独立运行时calibration/internal访问先后','未保存系统文件访问轨迹；只能由已绑定源码顺序和归档资产支持。不得声称取得了独立运行时防火墙证明。',training_code)
    limit('逐epoch网络预测或权重快照','history逐epoch只有损失/计数/LR，不能从每epoch原预测重新算损失或重建每epoch权重。可独立重算早停决策，并用归档最佳模型预测复算最终OOB损失。',train/'histories')
    limit('scheduler独立运行时传参及完整state_dict','checkpoint未保存scheduler/optimizer state或逐次step参数轨迹；源码可确认step(oob_loss)，日志可确认LR缩减因子。',training_code)
    limit('min_lr=1e-6运行时触底','记录中的LR最小值是否触底将逐成员列出；未触底时不能由日志验证下限真的生效。配置与源码参数另标STATIC_VERIFIED。',train/'histories')
    limit('历史holdout完全未被任何程序读取的绝对声明','扩展生成脚本在状态标签完成后读取121—160的物理洪水表用于重复签名检查；不读取这些情景的UE标签/预测参与训练。ensemble训练源码不读121—160。',expansion_generator,'SCOPE_CLARIFICATION')

    # Epoch and member audit. No Torch import, optimizer, prediction or retraining.
    bootstrap=load(train/'bootstrap_scenarios_v2.json')
    summary_csv={r['member_id']:r for r in rows(train/'ensemble_training_summary.csv')}
    predictions={r['state_id']:r for r in rows(train/'ensemble_predictions_raw_v2.csv.gz') if r['split']=='train'}
    check('archived_train_predictions_complete',set(predictions)=={r['state_id'] for r in combined},len(predictions),3178,train/'ensemble_predictions_raw_v2.csv.gz')
    epoch_rows=[];member_rows=[];weight_rows=[];tensor_rows=[];checkpoint_rows=[];lr_events=[];discrepancies=[]
    universe=sorted(split_ids['train'])
    def weighted_huber_from_archived_prediction(mid,selected_rows,w):
        y=np.asarray([float(r['log_tstt_ratio']) for r in selected_rows],dtype=np.float32)
        pred=np.asarray([float(predictions[r['state_id']][mid+'_y']) for r in selected_rows],dtype=np.float64)
        error=np.abs(pred-y)
        elements=np.where(error<=1,.5*error**2,error-.5)
        return float(np.sum(w*elements)/np.sum(w))
    for member in bootstrap['members']:
        mid=member['member_id']
        history_path=use(train/f'histories/{mid}_training_history.csv','original_epoch_history')
        summary_path=use(train/f'summaries/{mid}_summary.json','original_member_summary')
        checkpoint_path=use(train/f'models/{mid}.pt','original_frozen_checkpoint')
        history=rows(history_path);summary=load(summary_path)
        metadata,tensors=checkpoint_metadata(checkpoint_path)
        dump(dest/(mid+'_checkpoint_metadata_readonly.json'),metadata)
        for row in tensors:tensor_rows.append({'member_id':mid,'checkpoint_sha256':sources[checkpoint_path]['sha256'],**row})
        draws=np.random.default_rng(int(member['bootstrap_seed'])).choice(np.asarray(universe),size=len(universe),replace=True).tolist()
        multiplicity=dict(sorted(collections.Counter(draws).items()))
        declared={int(k):int(v) for k,v in member['scenario_multiplicity'].items()}
        inbag=set(multiplicity);oob=set(universe)-inbag
        boot_ok=(multiplicity==declared and set(member['oob_scenario_ids'])==oob and inbag.isdisjoint(oob)
                 and inbag|oob==set(universe) and sum(multiplicity.values())==120 and len(inbag)==member['unique_inbag_scenario_count']
                 and len(oob)==member['oob_scenario_count'] and not (inbag|oob)&set(range(61,161)))
        in_rows=[r for r in combined if int(r['scenario_id']) in inbag]
        oob_rows=[r for r in combined if int(r['scenario_id']) in oob]
        w_in=np.asarray([1/raw_counts[int(r['scenario_id'])] for r in in_rows],dtype=np.float32)*np.asarray([multiplicity[int(r['scenario_id'])] for r in in_rows],dtype=np.float32)
        w_oob=np.asarray([1/raw_counts[int(r['scenario_id'])] for r in oob_rows],dtype=np.float32)
        for sid in universe:
            c=multiplicity.get(sid,0);base=float(np.float32(1/raw_counts[sid]));w=float(np.float32(base)*np.float32(c))
            weight_rows.append({'member_id':mid,'scenario_id':sid,'state_count':raw_counts[sid],
                                'bootstrap_multiplicity':c,'inbag':sid in inbag,'OOB':sid in oob,
                                'per_state_base_float32_weight':base,'per_state_train_float32_weight':w,
                                'train_total_scenario_weight_float64_sum':w*raw_counts[sid],
                                'OOB_per_state_weight':base if sid in oob else 0})
        best=float('inf');best_epoch=0;without=0;epoch_ok=True
        first_stop=None;min_delta=constants['MIN_DELTA'];patience=constants['EARLY_STOPPING_PATIENCE']
        for expected_epoch,row in enumerate(history,1):
            epoch=int(row['epoch']);loss=float(row['oob_weighted_huber'])
            improved=loss<best-min_delta
            if improved:best=loss;best_epoch=epoch;without=0
            else:without+=1
            row_ok=(epoch==expected_epoch and math.isfinite(loss) and row['member_id']==mid and flag(row['improved'])==improved
                    and int(row['epochs_without_improvement'])==without and math.isclose(float(row['best_oob_huber_so_far']),best,abs_tol=1e-15,rel_tol=0))
            if without>=patience and first_stop is None:first_stop=epoch
            epoch_ok &= row_ok
            epoch_rows.append({'member_id':mid,'epoch':epoch,'OOB_loss_raw':loss,'improved_recomputed':improved,
                               'best_epoch_recomputed':best_epoch,'best_loss_recomputed':best,'epochs_without_improvement_recomputed':without,
                               'history_decision_fields_match':row_ok,'learning_rate_raw':float(row['learning_rate'])})
        stop_epoch=int(history[-1]['epoch'])
        stop_ok=(first_stop==stop_epoch if stop_epoch<constants['MAX_EPOCHS'] else first_stop in (None,stop_epoch))
        epochs_ok=epoch_ok and stop_ok and best_epoch==summary['best_epoch'] and stop_epoch==summary['epochs_completed'] and stop_epoch<=1000
        # Log-observable LR changes only, no unrecorded scheduler state invented.
        lr_factors=[]
        for prev,cur in zip(history,history[1:]):
            if float(cur['learning_rate'])!=float(prev['learning_rate']):
                ratio=float(cur['learning_rate'])/float(prev['learning_rate']);lr_factors.append(ratio)
                lr_events.append({'member_id':mid,'observed_at_epoch':int(cur['epoch']),
                                  'scheduler_step_source_epoch':int(prev['epoch']),
                                  'lr_before':float(prev['learning_rate']),'lr_after':float(cur['learning_rate']),
                                  'ratio':ratio,'oob_loss_at_source_epoch':float(prev['oob_weighted_huber']),
                                  'interpretation':'history记录在scheduler.step之前；下一epoch反映LR变更；具体scheduler内部状态未保存'})
        factor_ok=bool(lr_factors) and all(math.isclose(x,.5,abs_tol=1e-14) for x in lr_factors)
        oob_recomputed=weighted_huber_from_archived_prediction(mid,oob_rows,w_oob)
        train_recomputed=weighted_huber_from_archived_prediction(mid,in_rows,w_in)
        oob_loss_ok=math.isclose(oob_recomputed,summary['best_oob_weighted_huber'],abs_tol=1e-12,rel_tol=1e-12)
        train_loss_ok=math.isclose(train_recomputed,summary['best_train_weighted_huber'],abs_tol=1e-12,rel_tol=1e-12)
        loss_ok=oob_loss_ok and train_loss_ok
        for metric,actual,expected,ok in [('best_OOB_weighted_Huber',oob_recomputed,summary['best_oob_weighted_huber'],oob_loss_ok),
                                         ('best_inbag_weighted_Huber',train_recomputed,summary['best_train_weighted_huber'],train_loss_ok)]:
            discrepancies.append({'member_id':mid,'metric':metric,'recomputed_from_archived_predictions':actual,
                                  'summary_value':expected,'difference':actual-expected,'absolute_difference':abs(actual-expected),
                                  'strict_abs_tolerance':1e-12,'strict_rel_tolerance':1e-12,'strict_result':'PASS' if ok else 'FAIL',
                                  'history_path':str(history_path),'summary_path':str(summary_path),'summary_sha256':sha(summary_path),
                                  'checkpoint_path':str(checkpoint_path),'checkpoint_sha256':sha(checkpoint_path),
                                  'archived_predictions_path':str(train/'ensemble_predictions_raw_v2.csv.gz'),
                                  'archived_predictions_sha256':sha(train/'ensemble_predictions_raw_v2.csv.gz'),
                                  'explanation_status':'UNVERIFIED_CAUSE; separate subset vs complete training prediction calls in frozen source; possible batch-dependent floating-point arithmetic. No new inference run.'})
        # History monitoring is float32; final summary Huber uses float64 predictions.
        history_vs_final_tol=8*np.finfo(np.float32).eps*max(1,abs(best))
        roundoff_consistent=abs(best-oob_recomputed)<=history_vs_final_tol
        meta_ok=(metadata['member_id']==mid and metadata['best_epoch']==best_epoch
                 and metadata['scenario_multiplicity']==member['scenario_multiplicity']
                 and metadata['oob_scenario_ids']==member['oob_scenario_ids']
                 and metadata['bootstrap_seed']==member['bootstrap_seed'] and metadata['initialization_seed']==member['initialization_seed']
                 and metadata['preprocessor_sha256']==sha(train/'preprocessor_v2.json')
                 and metadata['best_oob_weighted_huber']==summary['best_oob_weighted_huber']
                 and metadata['best_train_weighted_huber']==summary['best_train_weighted_huber']
                 and sources[checkpoint_path]['sha256']==summary['model_hash_sha256']
                 and summary_csv[mid]['model_hash_sha256']==sources[checkpoint_path]['sha256']
                 and summary['unique_inbag_rows']==len(in_rows) and summary['oob_rows']==len(oob_rows)
                 and summary['unique_inbag_scenarios']==len(inbag) and summary['oob_scenarios']==len(oob)
                 and summary['retained'] is True and len(tensors)==8)
        state='PASS_WITH_UNVERIFIED_RUNTIME_ITEMS' if boot_ok and epochs_ok and loss_ok and meta_ok and factor_ok and roundoff_consistent else 'FAIL'
        member_rows.append({'member_id':mid,'inbag_scenario_count':len(inbag),'OOB_scenario_count':len(oob),
                            'bootstrap_draws':len(draws),'bootstrap_max_multiplicity':max(multiplicity.values()),
                            'inbag_unique_rows':len(in_rows),'OOB_rows':len(oob_rows),'bootstrap_seed':member['bootstrap_seed'],
                            'initialization_seed':member['initialization_seed'],'best_epoch_recomputed':best_epoch,
                            'best_epoch_summary':summary['best_epoch'],'stop_epoch':stop_epoch,'epochs_without_improvement_at_stop':without,
                            'best_OOB_loss_history_float32':best,'best_OOB_loss_archived_predictions_recomputed':oob_recomputed,
                            'best_OOB_loss_summary_float64':summary['best_oob_weighted_huber'],
                            'best_inbag_loss_archived_predictions_recomputed':train_recomputed,
                            'best_inbag_loss_summary_float64':summary['best_train_weighted_huber'],
                            'OOB_loss_difference_recomputed_minus_summary':oob_recomputed-summary['best_oob_weighted_huber'],
                            'inbag_loss_difference_recomputed_minus_summary':train_recomputed-summary['best_train_weighted_huber'],
                            'strict_OOB_Huber_recompute_check':oob_loss_ok,'strict_inbag_Huber_recompute_check':train_loss_ok,
                            'history_minus_final_OOB_loss':best-oob_recomputed,'roundoff_consistency_tolerance':history_vs_final_tol,
                            'checkpoint_sha256':sources[checkpoint_path]['sha256'],'bootstrap_checks':boot_ok,'epoch_and_stop_checks':epochs_ok,
                            'best_prediction_Huber_recompute_checks':loss_ok,'checkpoint_summary_metadata_checks':meta_ok,
                            'LR_factor_observed_check':factor_ok,'LR_min_observed':min(float(r['learning_rate']) for r in history),
                            'scheduler_patience_25':'STATIC_VERIFIED; INTERNAL_STATE_UNVERIFIED',
                            'scheduler_OOB_monitor':'STATIC_VERIFIED; RUNTIME_CALL_TRACE_UNVERIFIED',
                            'scheduler_min_lr_1e_6':'STATIC_VERIFIED; RUNTIME_FLOOR_UNVERIFIED_NOT_REACHED',
                            'runtime_diagnostic_file_access':'UNVERIFIED_NO_INDEPENDENT_ACCESS_LOG',
                            'checkpoint_path':str(checkpoint_path),'history_path':str(history_path),'summary_path':str(summary_path),'status':state})
        checkpoint_rows.append({'member_id':mid,'metadata_best_epoch':metadata['best_epoch'],'weight_hash':sources[checkpoint_path]['sha256'],
                                'preprocessor_hash':metadata['preprocessor_sha256'],'metadata_summary_match':meta_ok,
                                'tensor_count':len(tensors),'decoder':'restricted pickle metadata + opaque tensor descriptors; no torch import'})
    table(dest/'member_OOB_early_stopping_audit.csv',member_rows)
    table(dest/'member_epoch_decision_reconstruction.csv',epoch_rows)
    table(dest/'member_scenario_bootstrap_weights.csv',weight_rows)
    table(dest/'member_checkpoint_metadata_checks.csv',checkpoint_rows)
    table(dest/'checkpoint_tensor_storage_hashes.csv',tensor_rows)
    table(dest/'scheduler_observed_LR_changes.csv',lr_events)
    table(dest/'numeric_discrepancy_register.csv',discrepancies)
    for key,field in [('member_bootstrap','bootstrap_checks'),('member_epoch_and_stopping','epoch_and_stop_checks'),
                      ('member_archived_final_OOB_and_inbag_Huber_recompute','best_prediction_Huber_recompute_checks'),
                      ('member_checkpoint_metadata_and_hash','checkpoint_summary_metadata_checks'),('member_logged_LR_factors','LR_factor_observed_check')]:
        check(key,all(r[field] for r in member_rows),sum(r[field] for r in member_rows),10,'member_OOB_early_stopping_audit.csv')
    if any(r['strict_result']=='FAIL' for r in discrepancies):
        limit('归档最终预测Huber严格复算存在微差',
              'numeric_discrepancy_register.csv保留全部20项实际值、差值及来源哈希。1e-12绝对/相对容差原样保留，未提高容差或把失败改成通过。部分差异可能与原源码对inbag/OOB子矩阵预测与冻结后对全部训练矩阵预测的浮点运算有关，但没有新推断运行，原因尚未独立证实。checkpoint与summary本身、最佳epoch、停止过程仍分别检查。',
              train/'ensemble_predictions_raw_v2.csv.gz','NUMERIC_DISCREPANCY_STRICT_CHECK_FAILED')
    log('member_audit_complete',members=len(member_rows),epochs=len(epoch_rows),failed=[r['member_id'] for r in member_rows if r['status']=='FAIL'])

    ue_rows=[]
    for name,data in [('initial_1500',datasets['initial_1500']),('expansion_1678',datasets['expansion_1678'])]:
        gaps=[float(r['relative_gap']) for r in data]
        ue_rows.append({'source_batch':name,'state_count':len(data),'method':'Frank-Wolfe','target_RG':5e-4,
                        'observed_min_RG':min(gaps),'observed_max_RG':max(gaps),
                        'all_converged':all(flag(r['converged']) for r in data),'retry_rows':sum(flag(r['retry_used']) for r in data),
                        'max_iterations_observed':max(int(r['iterations']) for r in data),
                        'initial_iteration_cap':1000,'retry_iteration_cap':3000,
                        'source_CSV':str(raw_paths[name]),'solver_source':str(original_generator if name=='initial_1500' else base_generator),
                        'time_context':'archived August 2026 protocol; exact wall-clock provenance not independently established'})
        check('training_label_RG_'+name,all(flag(r['converged']) for r in data) and max(gaps)<=5e-4+1e-12,max(gaps),'<=0.0005',raw_paths[name])
    table(dest/'training_UE_label_precision_provenance.csv',ue_rows)
    limit('原标签精确生成时间','归档协议/种子和生产背景指向2026年8月初；复制到本机后的mtime不用于证明原生成时刻，未取得可信逐状态UTC访问/生成日志。',expanded/'v2_day1_protocol_pre_registered.json')
    # Include unchanged G0 items as a separate, inherited provenance limitation.
    limit('G0开放来源身份问题','两份原投稿Word身份、部分阶段目录非自包含等G0项继续保留；G1没有修改或选择Word主稿。',g0/'version_conflicts.csv','INHERITED_G0_OPEN_ITEMS')
    table(dest/'evidence_locations.csv',evidence)
    table(dest/'G1_source_manifest.csv',list(sources.values()))
    table(dest/'G1_supplemental_source_manifest.csv',[r for r in sources.values() if not r['G0_source_id']])
    table(dest/'G1_unverified_evidence.csv',limitations)
    source_post=[]
    for r in g0_manifest:
        p=Path(r['path']);digest=sha(p)
        source_post.append({'path':str(p),'G0_sha256':r['sha256'],'after_G1_sha256':digest,'unchanged':digest==r['sha256']})
    check('all_1661_G0_sources_unchanged_after_G1',all(r['unchanged'] for r in source_post),sum(r['unchanged'] for r in source_post),1661)
    table(dest/'G0_1661_source_postflight.csv',source_post)
    check('G0_audit_outputs_and_program_unchanged',all(sha(p)==h for p,h in g0_seal.items()),sum(sha(p)==h for p,h in g0_seal.items()),len(g0_seal),'G0 directory and r47_audit.py')
    supplemental_post=[{'path':str(p),'sha256_before':r['sha256'],'sha256_after':sha(p),'unchanged':sha(p)==r['sha256']} for p,r in sources.items()]
    table(dest/'G1_used_source_immutability.csv',supplemental_post)
    check('all_used_sources_unchanged',all(r['unchanged'] for r in supplemental_post),sum(r['unchanged'] for r in supplemental_post),len(supplemental_post))
    failed=[r for r in checks if r['status']=='FAIL']
    status='FAIL_NUMERIC_RECONCILIATION_PENDING' if failed else 'PASS_WITH_UNVERIFIED_RUNTIME_ITEMS'
    validation={'stage':'G1','status':status,'core_numeric_checks_pass':not failed,'checks_total':len(checks),
                'checks_passed':len(checks)-len(failed),'failed_checks':failed,'checks':checks,
                'G0_source_count':len(g0_manifest),'G0_source_manifest_sha256':sha(g0/'source_manifest.csv'),
                'G1_source_count':len(sources),'supplemental_source_count':sum(not r['G0_source_id'] for r in sources.values()),
                'supplemental_original_file_count':sum(r['provenance']=='SUPPLEMENTAL_EXISTING_ORIGINAL_FILE_NOT_REPLACING_G0' for r in sources.values()),
                'reused_accepted_G0_output_count':sum(r['provenance']=='ACCEPTED_G0_OUTPUT_REUSED_UNCHANGED' for r in sources.values()),
                'training_states':len(combined),'training_scenarios':len(split_ids['train']),
                'members_audited':len(member_rows),'epochs_audited':len(epoch_rows),'unverified_evidence':limitations,
                'strict_prediction_Huber_mismatches':[r for r in discrepancies if r['strict_result']=='FAIL'],
                'numeric_comparisons':{'integer_and_masks':'exact equality','epoch_log_decision_fields_abs_tolerance':1e-15,
                                       'best_saved_prediction_Huber_abs_tolerance':1e-12,'best_saved_prediction_Huber_rel_tolerance':1e-12,
                                       'history_vs_final_Huber_precision_bound':'8*float32_epsilon*max(1,abs(history_best)); actual differences retained'},
                'read_only_operations':{'UE_solves':0,'flood_fields_generated':0,'model_training':0,'model_parameter_tuning':0,
                                        'formal_searches':0,'new_model_predictions':0,'project_module_imports':0,'Word_edits':0,
                                        'offline_existing_recovery_mask_replays':120,'offline_existing_bootstrap_replays':10},
                'checkpoint_decoder':'whitelisted metadata-only unpickler; storage blobs hashed without building Torch tensors',
                'G2_G3_G4':'NOT_RUN','must_stop_after_G1':True,'elapsed_seconds':round(time.perf_counter()-start,3),
                'script':str(Path(__file__).resolve()),'script_sha256':sha(Path(__file__)),
                'python':sys.version,'numpy':np.__version__}
    dump(dest/'G1_validation.json',validation)
    table(dest/'G1_automatic_acceptance_checks.csv',checks)
    summary_lines=['|来源|强度|情景数|状态数|每情景状态均值/最小/最大|','|---|---|---:|---:|---|']
    for r in severity_rows:
        summary_lines.append(f'|{r["source_batch"]}|{r["severity"]}|{r["scenario_count"]}|{r["state_count"]}|{r["states_per_scenario_mean"]} / {r["states_per_scenario_min"]} / {r["states_per_scenario_max"]}|')
    member_lines=['|成员|in-bag/OOB情景|best epoch|stop epoch|最佳OOB（history）|重算最终OOB|状态|','|---|---:|---:|---:|---:|---:|---|']
    for r in member_rows:
        member_lines.append(f'|{r["member_id"]}|{r["inbag_scenario_count"]}/{r["OOB_scenario_count"]}|{r["best_epoch_recomputed"]}|{r["stop_epoch"]}|{r["best_OOB_loss_history_float32"]:.12g}|{r["best_OOB_loss_archived_predictions_recomputed"]:.12g}|{r["status"]}|')
    report=['# Reviewer 1第4.7条 S1/G1 中文验收报告','',f'状态：**{status}**。自动核心检查 {len(checks)-len(failed)}/{len(checks)} 通过。',
            '', '本批只读核验训练CSV、既有恢复子集、bootstrap、history、summary和checkpoint元数据。G0的1661项来源、G0审计程序及输出均未改写。模型版本使用G0绑定的原训练脚本，不采用GitHub路径适配副本或hidden failed版本。',
            '', '## 1. 原始训练数据独立重建','',
            f'直接读取 {link(raw_paths["initial_1500"])} 和 {link(raw_paths["expansion_1678"])}，分别得到1500与1678状态，共120情景、3178状态。来源SHA见G1_source_manifest.csv，计数从CSV逐行聚合，未拿manifest当计算输入。','',
            *summary_lines,'',
            '逐状态核对情景ID、38条道路的初始关闭/恢复标志、集合关系、恢复/剩余数量、轨迹前缀、深度关闭阈值和state hash；同时核对训练state_id、state_hash以及(scenario_id,恢复集合)的唯一性。扩展CSV没有独立restored_physical_links列，已从38个恢复标志重建，并与冻结采样元数据比对。完整逐状态结果见state_integrity_audit.csv。','',
            'recovery_stage_distribution.csv按来源、强度、初始关闭数和恢复阶段统计；initial_closed_count_distribution.csv按情景数和状态数分别统计关闭道路数。3178个状态不是3178个独立洪水情景；同情景状态共享洪水背景。','',
            '## 2. 两批恢复状态抽样分别核查','',
            f'首批配额见 {loc_quota}，恢复子集见 {loc_first}：mild情景完整分配2^m状态；1500总额度扣除mild后，余量按原顺序在moderate情景轮转分配并受2^m容量限制。每情景优先空集和全集，随后抽随机恢复排列的各前缀并去重，达到配额即停止；达到尝试上限仍不足时按bit mask顺序确定性补足。训练状态seed为202608031+scenario_id。','',
            f'扩展配额见 {loc_expquota}，采样见 {loc_exp}：mild/moderate/severe分别min(2^m,8/32/60)。在去重后的阶段{{0,floor(m/4),floor(m/2),floor(3m/4),m}}中，端点各取1，中间阶段按quota<=32取至多10，否则至多15种组合；随后对所有阶段组合打乱并补足。state seed为202608052+scenario_id，洪水情景生成seed202608051只作来源说明，本批未生成洪水。','',
            '扩展补足是“所有剩余子集打乱后补足”，不能将协议中balanced fill理解为各阶段精确均衡；不能称全训练池均匀抽取2^m状态。扩展source_trajectory_id是插入计数，source_restoration_order将已恢复集合放在前面，不应误称为首批真实随机轨迹编号。','',
            f'独立编写两套纯子集重建器，用既存120个情景的关闭集和冻结seed离线重建；{sum(r["all_mask_and_order_metadata_match_replay"] for r in sampling)}/120的mask、顺序、stage及source_trajectory_id与原CSV逐项一致。每个情景额度、覆盖率、端点、尝试数或补足数见recovery_sampling_audit.csv。没有重新生成洪水或计算状态标签。','',
            '强度类别来自原生成计划及冻结标签，并与源码SPECS的关闭数范围mild1—3、moderate4—7、severe8—12一致；不是用本批表现重新分类或筛选。','',
            '## 3. 数据分组防火墙与历史final holdout','',
            '训练1—60及201—260，与calibration61—80、internal-ID81—100、internal-severe101—120、历史final121—160分别核对ID集合；还以完整38维初始深度（round9）和关闭标志计算物理签名，避免只靠编号判断重复。两两检查见train_calibration_test_leakage_checks.csv。原预处理NPZ中的情景顺序、float32标签、恢复数量和scenario-balanced权重与原训练CSV核对。','',
            f'历史holdout签名核对需要读取原归档 {link(final_summary)} 和 {link(final_physical)}。这两项及既有4.1来源记录 {link(holdout_provenance)} 共3项，未在G0的1661项中，作为G1新增只读证据单列，未替换任何G0来源或选用公开副本。物理洪水表SHA与该4.1记录中的expected_freeze_sha256一致；该记录本身是本批新冻结，不能称它已获G0哈希冻结。另复用4份G0审计输出，其身份在补充清单中分别标明。','',
            f'必须限定“未读取holdout”的范围：{loc_exp_main} 在扩展标签生成后读取历史final物理洪水表，用于签名查重；不是读取holdout UE标签/预测参与训练。ensemble训练源码只加载原训练及扩展CSV；calibration/internal在全成员冻结后用于诊断。不得表述成整个历史工作流从未读取过final的任何文件。','',
            '## 4. 十成员OOB、权重与逐epoch早停','',
            f'{loc_boot} 按120情景有放回抽取120次。G1用各冻结seed独立重抽，核对scenario_multiplicity、OOB补集、互斥/覆盖和成员记录。{loc_weight} 的base weight为float32(1/n_s)，训练乘bootstrap重复次数c_s；OOB使用1/n_s。重复发生在情景抽样权重，不把重复情景当新独立洪水。member_scenario_bootstrap_weights.csv列出10×120个情景的实际权重。','',
            f'{loc_training} 使用OOB weighted Huber，MIN_DELTA=1e-7、patience=100、max_epochs=1000。G1从每epoch loss独立重算improved、best-so-far、未改善计数及首次应停止epoch，对比history、member summary和checkpoint元数据。并非只检查“stop=best+100”。','',
            *member_lines,'',
            '最佳checkpoint的元数据用受限pickle解析器读取；Torch tensor只保留形状/存储描述并对存储字节作哈希，没有导入Torch或运行模型。member_id、seed、scenario multiplicity/OOB、best epoch、preprocessor SHA、最佳loss及权重SHA与原摘要/manifest交叉核对。没有重选成员，原10成员全部保留。','',
            '进一步用已归档最佳成员预测CSV和原标签/OOB权重重算最终Huber，未产生新模型预测。标签依原训练转换成float32，预测保持归档float64。history中的监控loss由Torch float32计算，冻结后summary用float64预测计算Huber，两者数值并非逐位相同；差值逐成员保留，不改写日志。自动验收要求最佳epoch完全一致、最终预测重算loss与summary在1e-12绝对/相对容差内一致，history/final差仅作浮点精度一致性单列。','',
            '**严格Huber复算检查没有全部通过，不能宣布G1全项PASS。**10成员bootstrap、逐epoch早停决定、best/stop epoch、checkpoint元数据及SHA核对均通过；但将冻结后的整批训练预测按成员inbag/OOB再分组重算，部分最终Huber与summary存在微差。所有实际值、差值、源路径和源哈希见numeric_discrepancy_register.csv。', '',
            '**1e-12是本G1审计额外设置的归档预测损失对账容差，不是原冻结训练协议的早停或模型选择阈值。**原早停MIN_DELTA仍为1e-7，未调整。额外严格对账失败不等于已经证实原训练早停、权重或科学结果失效；它表示这一更严格的数值一致性没有被现有证据完整解释，故按原门槛保留失败，不强行匹配。', '',
            '|成员|OOB重算减summary|inbag重算减summary|OOB严格检查|inbag严格检查|', '|---|---:|---:|---|---|',
            *[f'|{r["member_id"]}|{r["OOB_loss_difference_recomputed_minus_summary"]:.16g}|{r["inbag_loss_difference_recomputed_minus_summary"]:.16g}|{r["strict_OOB_Huber_recompute_check"]}|{r["strict_inbag_Huber_recompute_check"]}|' for r in member_rows], '',
            '这里的第二类差异必须与history float32/summary float64的监控口径差异分开：归档整批训练预测与summary专用inbag/OOB预测虽然来自相同checkpoint，但源码调用的输入子矩阵不同。批尺寸/浮点运算可能造成微差，**本批没有新模型推断来独立证实这个原因**。不提高1e-12门槛，不修改原结果，也不将这种可能性写成已证实结论。', '',
            '## 5. scheduler和访问顺序的证据边界','',
            f'{loc_training} 静态确认ReduceLROnPlateau(mode=min,patience=25,factor=0.5,min_lr=1e-6)接收scheduler.step(oob_loss)。history记录在step之前，因此LR变化体现在下一epoch；所有可观测变化的比例另列scheduler_observed_LR_changes.csv。','',
            '归档未保存scheduler/optimizer完整state_dict或每次step实参轨迹。日志可以直接核验缩减比例0.5；patience=25及同一OOB监控由绑定源码支持，但不冒充独立运行时内部状态证明。日志未触及1e-6下限时，运行时触底行为标UNVERIFIED。不能为了补齐证据而训练或构造新训练日志。','',
            f'{loc_main} 串行完成10个train_member（每个保存checkpoint）后才读取calibration/internal，属于STATIC_VERIFIED。没有独立OS文件访问轨迹，运行时访问顺序仍UNVERIFIED；归档checkpoint与诊断预测存在不能单独证明真实访问时间先后。','',
            '## 6. 原标签精度与时间背景','',
            f'首批求解调用见 {loc_ue_first}，扩展经base调用见 {loc_ue_exp}。两者均为历史Frank-Wolfe、目标RG=5e-4、初始上限1000次，必要时重试3000次；实际每批最大RG和收敛/重试情况见下表。','',
            '|来源|状态数|最大实际RG|收敛|重试数|','|---|---:|---:|---|---:|',
            *[f'|{r["source_batch"]}|{r["state_count"]}|{r["observed_max_RG"]:.16g}|{r["all_converged"]}|{r["retry_rows"]}|' for r in ue_rows], '',
            '协议日期、种子和归档背景指向2026年8月初。精确逐状态生成时间没有独立可信时间轨迹，不能以本机拷贝时间代替。**原3178条训练标签不能称全部达到1e-9，也没有在本批以4.2精度重新求解。**','',
            '## 7. 验收、限制与停止点','',
            f'核心自动检查{len(checks)-len(failed)}/{len(checks)}。状态{status}保留运行时证据缺口，不将UNVERIFIED改成PASS。完整失败项：'+('无。' if not failed else json.dumps(failed,ensure_ascii=False)),
            '',f'自动程序 {link(Path(__file__).resolve())}；G1_validation.json和G1_automatic_acceptance_checks.csv保存实际检查、公式容差和来源。G1_缺失证据与限制.md列全部限制。各结论的源码行号见evidence_locations.csv，来源SHA见G1_source_manifest.csv。',
            '', '**本批到此停止。G2/G3/G4未运行；原投稿Word、冻结源码、模型、4.1—4.6结果和G0程序均未修改。**','']
    (dest/'G1_中文验收报告.md').write_text('\n'.join(report),encoding='utf-8')
    limits=['# G1 缺失证据与限制','',f'核心核验状态：{status}。UNVERIFIED表示证据不足，不能用于肯定运行时事实。','']
    for r in limitations:limits.extend([f'## {r["item"]}', '',f'状态：{r["status"]}。{r["reason"]}', '',f'来源：{link(r["source"])}' if r['source'] else '', ''])
    (dest/'G1_缺失证据与限制.md').write_text('\n'.join(limits),encoding='utf-8')
    log('finished',status=status,checks_passed=len(checks)-len(failed),checks_total=len(checks),failed_checks=[r['check'] for r in failed])
    names=['G1_中文验收报告.md','training_scenario_severity_recomputed.csv','recovery_sampling_audit.csv',
           'recovery_stage_distribution.csv','train_calibration_test_leakage_checks.csv','member_OOB_early_stopping_audit.csv',
           'G1_validation.json','G1_缺失证据与限制.md']
    index=['# G1 结果文件索引','',f'状态：{status}。完成后停止，G2/G3/G4未执行。','', '## 用户要求交付对应文件','']
    for name in names:index.append(f'- {link(dest/name)}')
    index.extend(['','## 全部附加核查文件',''])
    for p in sorted(dest.iterdir()):
        if p.is_file() and p.name not in names+['G1_结果文件索引.md','G1_output_sha256.csv']:
            index.append(f'- {link(p)}')
    index.extend(['',f'- {link(Path(__file__).resolve(),"独立G1审计程序")}',
                  f'- {link(g0/"source_manifest.csv","沿用的G0 1661项来源清单")}',
                  '', '未生成压缩包。所有数值CSV使用UTF-8 BOM，可在Excel中打开。'])
    (dest/'G1_结果文件索引.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    output_rows=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='G1_output_sha256.csv']
    output_rows.append({'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__)),'bytes':Path(__file__).stat().st_size})
    table(dest/'G1_output_sha256.csv',output_rows)
    return 1 if failed else 0


if __name__=='__main__':
    raise SystemExit(main())
