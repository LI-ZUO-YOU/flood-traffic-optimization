"""Authorized S3 only: prepare ->330 live tasks ->global seal ->references ->requested basic delivery."""
from s3_prepare import *
from s3_live import run_all
from s3_finish import references,analyze_and_deliver
import argparse,traceback

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-authorized-S3',action='store_true',required=True);p.parse_args();pin()
 try:
  preflight();freeze_deployment();generate();rows,net=run_all();references(net);analyze_and_deliver()
 except Exception as e:
  dump(CONTROL/'pipeline_error.json',{'at':now(),'error':repr(e),'traceback':traceback.format_exc(),'original_outputs_preserved':True,'no_tuning_or_replacement':True});raise

if __name__=='__main__':main()
