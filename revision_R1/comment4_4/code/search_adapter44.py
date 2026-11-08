"""Second-batch search entry point, prepared before any new-scale UE outcomes.

Component timers use the separately frozen components44 entry point. This file
does not change those timers. It fixes a nested legacy-SA dimensional constant
discovered during the deeper S0 audit, retaining its proposal order and RNG calls.
"""
from common44 import *
from components44 import install_search_dimensions
from types import SimpleNamespace
def propose(sequence,rng,config):
 candidate=list(sequence);n=len(sequence);draw=float(rng.random())
 if draw<config.adjacent_probability:
  i=int(rng.integers(0,n-1));candidate[i],candidate[i+1]=candidate[i+1],candidate[i]
 elif draw<config.adjacent_probability+config.insertion_probability:
  i,j=rng.choice(n,size=2,replace=False).tolist();item=candidate.pop(i);candidate.insert(j,item)
 else:
  i,j=rng.choice(n,size=2,replace=False).tolist();candidate[i],candidate[j]=candidate[j],candidate[i]
 return tuple(candidate)
def install():
 a=install_search_dimensions()
 a.legacy_sa=SimpleNamespace(SAConfig=frozen.legacy_sa.SAConfig,propose=propose)
 return a
