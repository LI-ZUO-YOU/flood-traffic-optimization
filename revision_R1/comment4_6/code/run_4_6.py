"""First-batch CLI. Later-stage computation is deliberately gated."""
import argparse,traceback,sys
from load_frozen_results import *

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',required=True,choices=['audit','legacy','new30','figures','validate','delivery','variance','bootstrap']);p.add_argument('--source41',type=Path);p.add_argument('--source42',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--bootstrap',type=int);p.add_argument('--seed',type=int);a=p.parse_args();out=a.out.resolve()
 if a.stage in ['variance','bootstrap'] or a.bootstrap is not None:raise RuntimeError('First-batch scope stops before bootstrap/variance. Author acceptance is required before later stages.')
 if a.stage=='audit':
  assert a.source41 and a.source42,'Audit requires both true source paths'
  from source_inventory import audit
  audit(out,a.source41,a.source42)
 elif a.stage in ['legacy','new30']:
  from tail_statistics import legacy,new30
  {'legacy':legacy,'new30':new30}[a.stage](out)
 elif a.stage=='validate':
  from test_4_6 import validate
  validate(out,True)
 elif a.stage=='figures':
  from render_figures import render
  render(out)
 elif a.stage=='delivery':
  from first_batch_report import deliver
  deliver(out)
 with (out/'00_audit/execution_log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at':now(),'stage':a.stage,'status':'PASS'},ensure_ascii=False)+'\n')

if __name__=='__main__':
 try:main()
 except Exception as exc:
  try:
   argv=sys.argv;out=Path(argv[argv.index('--out')+1]);(out/'00_audit').mkdir(parents=True,exist_ok=True)
   error={'at':now(),'stage':argv[argv.index('--stage')+1],'status':'FAIL','exception_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};dump(out/'00_audit/last_error.json',error)
   with (out/'00_audit/execution_log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(error,ensure_ascii=False)+'\n')
   (out/'00_audit/protocol_conflicts.md').write_text('# 执行异常，停止依赖分析\n\n'+str(exc)+'\n\n未填补数据、替换情景或种子。请根据last_error.json区分数据协议冲突与实现错误；数据冲突未经解决不得继续。\n',encoding='utf-8')
  except Exception:pass
  traceback.print_exc();sys.exit(1)
