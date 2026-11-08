from s4_common import *
if __name__=='__main__':
 ops=prepare()
 import s4_statistics,s4_phases
 s4_statistics.run();s4_phases.run()
 dump(S4/'00_audit/stage_data_complete.json',{'at':now(),'status':'PASS','forbidden_operations':ops})
