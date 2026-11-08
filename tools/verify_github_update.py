"""Read-only verification of the increment or merged repository; stdlib only."""
from pathlib import Path
import argparse,csv,hashlib,json,sys
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['overlay','merged'],default='overlay');args=parser.parse_args()
def digest(b):return hashlib.sha256(b).hexdigest()
errors=[];exact=0;normalized=[]
if args.mode=='overlay':
 with (root/'REVISION_FILES_SHA256.csv').open(encoding='utf-8-sig',newline='') as f:items=[(x['path'],x['sha256']) for x in csv.DictReader(f)]
else:
 items=[]
 for s in (root/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
  h,p=s.split('  ',1);items.append((p,h))
for rel,h in items:
 p=(root/rel).resolve()
 if root not in p.parents or not p.is_file():errors.append([rel,'MISSING_OR_OUTSIDE_ROOT']);continue
 b=p.read_bytes()
 if digest(b)==h:exact+=1;continue
 try:
  b.decode('utf-8-sig')
  fixed=b.replace(b'\r\n',b'\n')
  # Support either LF or CRLF archived text, never other content changes.
  if digest(fixed)==h or digest(fixed.replace(b'\n',b'\r\n'))==h:normalized.append(rel);continue
 except UnicodeDecodeError:pass
 errors.append([rel,'CONTENT_SHA_MISMATCH'])
print(json.dumps(dict(status='PASS' if not errors else 'FAIL',mode=args.mode,files=len(items),exact_byte_matches=exact,newline_only_matches=normalized,errors=errors,scope='INTEGRITY_ONLY_NO_UE_NO_TRAINING_NO_SEARCH'),ensure_ascii=False))
sys.exit(1 if errors else 0)
