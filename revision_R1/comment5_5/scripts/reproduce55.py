"""Offline result reproduction from accepted CSVs and the completed new-state log.

Never calls UE. Writes an isolated reproduction directory, not delivered results.
"""
from common55 import *
import datetime,importlib.util,shutil
def main():
 trial=OUT/'reproductions'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
 for sub in ['audit','raw','tests']:(trial/sub).mkdir(parents=True,exist_ok=True)
 for name in ['run_manifest.json','unique_requested_states.csv']:shutil.copyfile(OUT/name,trial/name)
 for name in ['UE_execution_validation.json']:shutil.copyfile(OUT/'audit'/name,trial/'audit'/name)
 shutil.copyfile(OUT/'raw/UE_query_log.csv',trial/'raw/UE_query_log.csv');shutil.copyfile(OUT/'raw/selection_manifest.csv',trial/'raw/selection_manifest.csv');shutil.copyfile(OUT/'Table_selection_rules_all10.csv',trial/'Table_selection_rules_all10.csv')
 spec=importlib.util.spec_from_file_location('analysis_reproduction',OUT/'scripts/analyze55.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.OUT=trial;module.main()
 comparisons=[]
 for name in ['Table_portfolio_DP_comparison.csv','Table_terminal_residual_by_portfolio.csv','Table_allclosed_counterfactual.csv','Table_scenario_selection_summary.csv']:
  a=read(OUT/name);b=read(trial/name);pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=1e-12,atol=1e-12);comparisons.append(dict(file=name,rows=len(a),status='PASS'))
 dump(trial/'reproduction_validation.json',dict(status='PASS',new_UE_calls=0,comparisons=comparisons));print('OFFLINE REPRODUCTION PASS',trial)
if __name__=='__main__':main()
