#!/usr/bin/env python3
"""Paired descriptive timing of original and migrated optimization proofs."""
import argparse,json,re,subprocess,time
from pathlib import Path
from case_delivery import ROOT,sha,load_delivery,load_optimization
p=argparse.ArgumentParser();p.add_argument('--legacy',type=Path,required=True);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('Preserve existing measurements; select a new output.')
a.out.parent.mkdir(parents=True,exist_ok=True)
records=[]
for case in sorted((ROOT/'cases').iterdir()):
 if not (case/'optimization.json').exists():continue
 old=load_delivery(case);new=load_optimization(case)
 specs={'before':(a.legacy,[old['source'],old['target'],*[c['rpx'] for c in old['pieces']]]),'after':(a.kernel,[new['source'],new['target'],new['proof']])}
 entry={'case':case.name}
 for label in (('before','after') if len(records)%2==0 else ('after','before')):
  binary,operands=specs[label];start=time.perf_counter()
  process=subprocess.run(['/usr/bin/time','-l',str(binary.resolve()),'verify',*map(str,operands)],capture_output=True,text=True)
  report=json.loads(process.stdout)
  if process.returncode or report.get('guarantee')!='MI_OPT':raise RuntimeError((case.name,label,report,process.stderr))
  rss=re.search(r'(\d+)\s+maximum resident set size',process.stderr)
  entry[label]={'wall_seconds':time.perf_counter()-start,'maximum_rss_bytes':int(rss[1]) if rss else None,'proof_bytes':sum(Path(path).stat().st_size for path in operands[2:]),'report':report}
 records.append(entry)
 a.out.with_suffix('.progress.json').write_text(json.dumps(records,indent=2)+'\n')
 print(case.name,flush=True)
summary={label:{'proof_bytes':sum(c[label]['proof_bytes'] for c in records),'execute_us':sum(c[label]['report']['execute_us'] for c in records),'wall_seconds':sum(c[label]['wall_seconds'] for c in records),'work':sum(c[label]['report']['statistics']['work'] for c in records),'max_rss_bytes':max(c[label]['maximum_rss_bytes'] or 0 for c in records)} for label in ('before','after')}
a.out.write_text(json.dumps({'legacy_kernel_sha256':sha(a.legacy),'kernel_sha256':sha(a.kernel),'cases':records,'totals':summary,'method':'One sequential paired fresh-process pass; alternating before/after order; MCM import excluded; descriptive timing, no exclusive host control. RSS from macOS time -l in bytes.'},indent=2)+'\n')
print(json.dumps(summary,indent=2))
