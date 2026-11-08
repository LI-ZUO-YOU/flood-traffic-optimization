"""Provider distinction: sealed RPC for smoke, unchanged high-precision solver for later live runs."""
from common45 import *

def live_store(network,physical,roads,db=None):
 # No live run is launched by this module. The first-batch runner accepts old IDs only.
 return E.PhysicalStore(network,physical,roads,db=db,target=1e-9)

def dp_after_freeze(run_paths,costs,roads):
 for path in run_paths:
  if not (Path(path)/'pre_reference_manifest.json').is_file():raise RuntimeError('DP requires frozen method outputs')
 return E.exact_dp(costs,roads)
