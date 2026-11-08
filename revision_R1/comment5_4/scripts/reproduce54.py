"""One-command numerical reproduction, isolated under comment5_4/reproductions/."""
from pathlib import Path
import sys,json,datetime,importlib.util,shutil
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def main():
    trial=ROOT/'reproductions'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S');(trial/'audit').mkdir(parents=True);(trial/'raw').mkdir()
    shutil.copyfile(ROOT/'run_manifest.json',trial/'run_manifest.json')
    for name in ['experiment54','od_diagnostic54']:
        mod=load(name);mod.OUT=trial;mod.P52=ROOT.parent/'comment5_2';mod.main()
    comparisons=[]
    for name in ['Table_duration_robustness.csv','Table_duration_summary.csv','Table_duration_summary_across_scenarios.csv','Table_original_absolute_regret.csv','Table_OD_time_distribution_optional.csv']:
        a=pd.read_csv(ROOT/name);b=pd.read_csv(trial/name);cols=[c for c in a.columns if c not in ['forward_seconds','reverse_seconds']]
        pd.testing.assert_frame_equal(a[cols],b[cols],check_exact=False,rtol=1e-12,atol=1e-12)
        comparisons.append(dict(file=name,status='PASS',rows=len(a),excluded_columns=['forward_seconds','reverse_seconds']))
    (trial/'reproduction_validation.json').write_text(json.dumps(dict(status='PASS',comparisons=comparisons,new_UE_calls=0),indent=2),encoding='utf-8');print('REPRODUCTION PASS',trial)
if __name__=='__main__':main()
