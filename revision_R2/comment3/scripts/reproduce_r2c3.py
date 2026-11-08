from common import *
import argparse
def main():
 parser=argparse.ArgumentParser(description='Audit the completed frozen experiment without adding simulation by default.');parser.add_argument('--offline-only',action='store_true');args=parser.parse_args()
 if not args.offline_only:raise SystemExit('Completed protocol is frozen. Use --offline-only; do not automatically add or rerun experiments.')
 assert js(OUT/'audit/UE_execution_validation.json')['status']=='PASS'
 from dp_r2c3 import tests
 tests()
 subprocess.run([sys.executable,'-X','utf8','-B',str(OUT/'scripts/validate_r2c3.py')],check=True)
if __name__=='__main__':main()
