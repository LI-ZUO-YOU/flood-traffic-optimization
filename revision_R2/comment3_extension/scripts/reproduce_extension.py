from common import *
import argparse
def main():
 parser=argparse.ArgumentParser(description='Offline audit of the frozen completed extension.');parser.add_argument('--offline-only',action='store_true');args=parser.parse_args()
 if not args.offline_only:raise SystemExit('Use --offline-only; no additional simulation or automatic rerun permitted.')
 from analyze_depth import small_tests
 small_tests();subprocess.run([sys.executable,'-X','utf8','-B',str(OUT/'scripts/validate_extension.py')],check=True)
 if js(OUT/'final_validation.json')['status']!='PASS':raise SystemExit('Final audit not PASS; inspect findings')
 subprocess.run([sys.executable,'-X','utf8','-B',str(OUT/'scripts/export_and_index.py')],check=True)
if __name__=='__main__':main()
