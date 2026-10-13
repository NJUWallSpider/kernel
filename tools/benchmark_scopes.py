#!/usr/bin/env python3
"""Fixed full-parent branch workload; no change in mathematical task between kernels."""
import argparse, hashlib, json, platform, re, statistics, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--kernel',required=True);p.add_argument('--source-root',required=True);p.add_argument('--label',required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args()
kernel=(ROOT/a.kernel).resolve();source=Path(a.source_root).resolve();config=json.loads((ROOT/'bench/scope_workloads.json').read_text())
out=ROOT/'bench/results'/a.label;out.mkdir(parents=True,exist_ok=True)
if (out/'raw.json').exists():raise SystemExit('Refusing to overwrite evidence.')
def invoke(args):
 start=time.perf_counter_ns();r=subprocess.run([str(kernel),*map(str,args)],capture_output=True,text=True);wall=time.perf_counter_ns()-start
 try:reply=json.loads(r.stdout)
 except json.JSONDecodeError:reply={'status':'IO_ERROR','stdout':r.stdout,'stderr':r.stderr}
 return {'command':[str(kernel),*map(str,args)],'exit_code':r.returncode,'wall_ns':wall,'result':reply}
claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}
def expression(constant):return {'constant':str(constant),'terms':[[0,'1']]}
report={'config':config,'diagnostic':a.diagnostic,'source_root':str(source),'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'source_sha256':{str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((source/'crates/core/src').rglob('*.rs'))},'lock_sha256':hashlib.sha256((source/'Cargo.lock').read_bytes()).hexdigest(),'platform':platform.platform(),'rustc':subprocess.check_output(['rustc','-Vv'],text=True),'cache_condition':'warm after preparation, fresh process, no cache flush','workloads':[]}
for n in config['sizes']:
 start=time.perf_counter_ns();d=ROOT/'bench/scope-generated'/str(n);d.mkdir(parents=True,exist_ok=True)
 (d/'model.mps').write_text('NAME scope\nROWS\n N OBJ\nCOLUMNS\n x OBJ 0\nRHS\nBOUNDS\n BV b x\nENDATA\n')
 steps=[{'Lin':{'id':i,'kind':'Le','constant':'0','terms':[[{'VarUpper':0},'1']]}} for i in range(n)]
 for i in range(n):
  child={'steps':[],'end':{'Witness':{'Local':i}}}
  steps.extend([{'Cases':{'id':n,'kind':'Le','expression':expression(-1),'split':expression(0),'integer':{'VarInt':0},'left':child,'right':child}},{'Drop':{'ids':[n]}}])
 cert={'claims':[claim],'blocks':[{'steps':steps,'end':{'Return':{'map':[expression(0)],'checks':[{'VarLower':0},{'Local':0},{'VarInt':0},'Exact']}}}]}
 (d/'proof.rpa').write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps([claim])+'\n')
 generation=time.perf_counter_ns()-start
 prep=[invoke(['canonical',d/'model.mps',d/'model.mcm']),invoke(['assemble',d/'proof.rpa',d/'proof.rpx'])]
 if any(r['exit_code'] for r in prep):
  (out/'failed-preparation.json').write_text(json.dumps(prep,indent=2));raise SystemExit('Preparation failed; evidence saved.')
 command=['verify',d/'model.mcm',d/'model.mcm',d/'proof.rpx',d/'request.json']
 record={'name':f'parent-{n}-branches-{n}','generation_ns':generation,'preparation':prep,'artifacts':{f:{'bytes':(d/f).stat().st_size,'sha256':hashlib.sha256((d/f).read_bytes()).hexdigest()} for f in ['model.mcm','proof.rpa','proof.rpx','request.json']},'samples':[invoke(command) for _ in range(1 if a.diagnostic else config['repetitions'])],'rss':[]}
 if not a.diagnostic and platform.system()=='Darwin':
  for _ in range(3):
   r=subprocess.run(['/usr/bin/time','-l',str(kernel),*map(str,command)],capture_output=True,text=True);m=re.search(r'(\d+)\s+maximum resident set size',r.stderr)
   record['rss'].append({'bytes':int(m[1]) if m else None,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 record['status_counts']={status:sum(s['result']['status']==status for s in record['samples']) for status in sorted({s['result']['status'] for s in record['samples']})}
 successes=[s for s in record['samples'] if s['result']['status']=='VERIFIED']
 if successes:
  record['summary']={}
  for name,values in [('process_ms',[s['wall_ns']/1e6 for s in successes]),('execute_ms',[s['result']['execute_us']/1000 for s in successes])]:record['summary'][name]={'min':min(values),'median':statistics.median(values),'max':max(values)}
 report['workloads'].append(record);(out/'raw.json').write_text(json.dumps(report,indent=2)+'\n');print(record['name'],record['status_counts'],record.get('summary'),flush=True)
print(out/'raw.json')
