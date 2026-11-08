from common import *

def main():
    target=OUT/'manifest.json'
    if target.exists():raise FileExistsError('Round-2 baseline already frozen; do not overwrite.')
    original=[]
    for p in ROOT.rglob('*'):
        if not p.is_file() or OUT in p.parents or '__pycache__' in p.parts:continue
        if p.suffix.lower() in ['.pyc','.nbc','.nbi']:continue
        original.append(p)
    frozen=json.loads((ROOT/'protocol/all_method_outputs_frozen.json').read_text(encoding='utf-8'))
    for n,h in frozen['files'].items():assert sha(ROOT/n)==h
    plan=ROOT.parent.parent/'4.1进一步修改.txt'
    dump(target,{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'ROUND2_POSTHOC_BASELINE_FROZEN',
        'original_files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(original)},
        'plan':str(plan),'plan_sha256':sha(plan),'scenario_ids':list(range(3001,3031)),
        'search_replays':300,'new_scenarios':False,'surrogate_retraining':False,'method_retuning':False,
        'UE_calls_permitted_only_for':'S2 fresh enumeration and explicitly labelled offline training-state cost measurement; plan reference to S3 timing is a section-number typo',
        'interpretation_notes':['All round-2 diagnostics and start controls are post hoc, not new confirmatory tests.',
            'The empirical 0.0510 percentage-point remaining improvement ceiling concerns the observed 30-scenario mean; it does not prove statistical impossibility or a future-population bound.',
            'Proposed interleaves multiple local-search calls with sequence completion; first pre-LS to final change is not a pure local-search causal effect.',
            'Proxy top-1 in the full pool and proxy top-1 in the primary shortlist can coincide; identical controls will be reported rather than interpreted as reserve ablation evidence.',
            'Sequence-level proxy/oracle rank correlation is distinct from within-stage state ranking; both will be distinguished.']})
    (OUT/'原计划_只读副本.txt').write_bytes(plan.read_bytes())
    print('Frozen',len(original),'original files; all 9000 core output hashes match.',flush=True)
if __name__=='__main__':main()

