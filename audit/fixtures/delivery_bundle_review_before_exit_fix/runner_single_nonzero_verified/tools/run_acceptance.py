#!/usr/bin/env python3
"""Fresh locked build, executed tests, and replay of every prepared real RPX.

Does not substitute replay success for completeness of the corpus ledger.
"""
import argparse,hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from case_delivery import load_delivery
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--skip-build',action='store_true');p.add_argument('--source-root',default=str(ROOT));a=p.parse_args()
source_root=Path(a.source_root).resolve()
prepared_cases=[]
for directory in sorted((ROOT/'cases').iterdir()):
 if directory.is_dir() and (directory/'preparation.json').exists():
  receipt=json.loads((directory/'preparation.json').read_text())
  if receipt.get('status')=='VERIFIED':prepared_cases.append((directory,load_delivery(directory,receipt)))
out=ROOT/'audit/validation'/a.label;out.mkdir(parents=True,exist_ok=True)
if (out/'run.json').exists():raise SystemExit('Result exists; choose a fresh label.')
target=ROOT/'target'/('validation-'+a.label);kernel=target/'release/rpx';records=[]
def invoke(args,env=None):
 start=time.perf_counter();r=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,text=True,env=env);record={'command':list(map(str,args)),'exit_code':r.returncode,'seconds':time.perf_counter()-start,'stdout':r.stdout,'stderr':r.stderr};records.append(record);return record
if not a.skip_build:
 for cmd in [['cargo','test','--manifest-path',str(source_root/'Cargo.toml'),'-p','kernel-core','--locked','--target-dir',str(target)],['cargo','build','--manifest-path',str(source_root/'Cargo.toml'),'-p','kernel-core','--release','--locked','--target-dir',str(target)]]:
  result=invoke(cmd)
  (out/'progress.json').write_text(json.dumps(records,indent=2)+'\n')
  if result['exit_code']:raise SystemExit('Build/test failed; raw result saved.')
if not kernel.exists():raise SystemExit('Missing requested validation binary.')
case_results=[]
for d,delivery in prepared_cases:
 pieces=[]
 for piece in delivery['pieces']:
  result=invoke([kernel,'verify',delivery['source'],delivery['target'],piece['rpx'],piece['request']])
  try:reply=json.loads(result['stdout'])
  except json.JSONDecodeError:reply={'status':'IO_ERROR','message':result['stderr']}
  pieces.append({'piece':piece['id'],'exit_code':result['exit_code'],'result':reply})
 if delivery['kind']=='single':
  entry={'case':d.name,'exit_code':pieces[0]['exit_code'],'result':pieces[0]['result'],'artifacts':{name:value['sha256'] for name,value in delivery['artifacts'].items()}}
 else:
  complete=all(x['exit_code']==0 and x['result']['status']=='VERIFIED' for x in pieces)
  entry={'case':d.name,'exit_code':0 if complete else 1,'result':{'status':'VERIFIED' if complete else 'BUNDLE_INCOMPLETE','kind':'independent-complete-request-conjunction','not_a_single_kernel_invocation':True},'pieces':pieces,'artifacts':{name:value['sha256'] for name,value in delivery['artifacts'].items()}}
 case_results.append(entry)
 print(d.name,entry['result']['status'],flush=True)
report={'recorded_utc':datetime.now(timezone.utc).isoformat(),'source_root':str(source_root),'source_sha256':{str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((source_root/'crates').rglob('*.rs')) if 'target' not in p.parts},'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'lock_sha256':hashlib.sha256((source_root/'Cargo.lock').read_bytes()).hexdigest(),'commands':records,'replayed':case_results,'all_replayed_verified':all(c['result']['status']=='VERIFIED' for c in case_results),'functional_delivery_complete':False,'note':'Replay verifies prepared certificates enumerated at start only; unprepared corpus targets remain outstanding. See audit/acceptance.json for denominator.'}
(out/'run.json').write_text(json.dumps(report,indent=2)+'\n');print(out/'run.json')
raise SystemExit(0 if report['all_replayed_verified'] else 1)
