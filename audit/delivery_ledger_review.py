#!/usr/bin/env python3
"""Read-only independent delivery receipt/ledger auditor. Writes only its review JSON."""
import hashlib,json,time
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/DELIVERY_LEDGER_REVIEW.json'
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def absolute(path):
 p=Path(path);return p.resolve() if p.is_absolute() else (ROOT/p).resolve()
def ident(path):
 p=Path(path);return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':digest(p)}
def check(condition,label,problems):
 if not condition:problems.append(label)
start=time.perf_counter();ledger_path=ROOT/'audit/acceptance.json';inventory_path=ROOT/'audit/corpus_inventory.json';ledger_identity=ident(ledger_path);inventory_identity=ident(inventory_path);ledger=json.loads(ledger_path.read_text());inventory=json.loads(inventory_path.read_text());byid={x['case_id']:x for x in inventory['cases']};entries=[]
for l in ledger['cases']:
 cid=l['case_id']
 if l['status']!='VERIFIED':continue
 folder=ROOT/'cases'/cid;path=folder/'preparation.json';d=json.loads(path.read_text());problems=[];notes=[];files={};iv=byid[cid]
 check(d['status']=='VERIFIED','receipt status is not VERIFIED',problems)
 check(d.get('case_id')==cid,'receipt case_id mismatch',problems)
 check(digest(path)==l.get('execution_receipt',{}).get('sha256'),'ledger receipt hash differs from current receipt',problems)
 for role,key in [('source','source_models'),('target','final_target_models')]:
  observed=ident(d[role]['path']);files[role]=observed
  check(observed['sha256']==d[role]['sha256']==iv[key][0]['sha256'],role+' corpus/receipt/inventory hash mismatch',problems)
  check(observed['sha256']==l.get(role,{}).get('sha256'),role+' ledger hash mismatch',problems)
 for name in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']:
  observed=ident(folder/name);files[name]=observed
  if name=='proof.rpa':expected=d.get('rpa_sha256',d.get('artifacts',{}).get(name,{}).get('sha256'));size=d.get('rpa_bytes',d.get('artifacts',{}).get(name,{}).get('bytes'))
  else:expected=d['artifacts'][name]['sha256'];size=d['artifacts'][name]['bytes']
  check(observed['sha256']==expected,name+' receipt hash mismatch',problems)
  if size is not None:check(observed['bytes']==size,name+' receipt size mismatch',problems)
  check(observed['sha256']==l.get('artifacts',{}).get(name,{}).get('sha256'),name+' ledger hash mismatch',problems)
  check(observed['bytes']==l.get('artifacts',{}).get(name,{}).get('bytes'),name+' ledger size mismatch',problems)
 q=json.loads((folder/'request.json').read_text());claims=q if isinstance(q,list) else q['claims'];points=[] if isinstance(q,list) else q.get('points',[]);bijections=[] if isinstance(q,list) else q.get('bijections',[])
 check(q==l.get('claims'),'ledger request differs from actual request',problems)
 last=d['kernel_runs'][-1];command=last['command'];result=json.loads(last['stdout']);check(last['exit_code']==0 and len(command)>=6 and command[1]=='verify','last command is not successful verify',problems);check(result['status']=='VERIFIED','last verify status differs',problems)
 for j,name in enumerate(['source.mcm','target.mcm','proof.rpx','request.json'],2):check(absolute(command[j])==(folder/name).resolve(),'last verify does not reference reviewed '+name,problems)
 for key,count in [('claims',len(claims)),('points',len(points)),('bijections',len(bijections))]:check(result.get(key,0)==count,key+' result/request count mismatch',problems)
 check(result==l.get('verification'),'ledger verification payload differs from receipt',problems)
 kh=d.get('kernel_binary_sha256',d.get('kernel_binary',{}).get('sha256'));check(isinstance(kh,str) and len(kh)==64 and kh==l.get('kernel_binary_sha256'),'kernel binary identity field mismatch',problems)
 canonical=[];assembly=[]
 for run in d['kernel_runs']:
  cmd=run['command']
  if len(cmd)>=4 and cmd[1]=='canonical':canonical.append({'command':cmd,'exit_code':run['exit_code']})
  if len(cmd)>=4 and cmd[1]=='assemble':assembly.append({'command':cmd,'exit_code':run['exit_code']})
 for role,name in [('source','source.mcm'),('target','target.mcm')]:
  check(any(c['exit_code']==0 and absolute(c['command'][2])==absolute(d[role]['path']) and absolute(c['command'][3])==(folder/name).resolve() for c in canonical),role+' canonical command identity missing/mismatched',problems)
 check(any(c['exit_code']==0 and absolute(c['command'][2])==(folder/'proof.rpa').resolve() and absolute(c['command'][3])==(folder/'proof.rpx').resolve() for c in assembly),'assembly command does not bind reviewed RPA/RPX paths',problems)
 preparer=d.get('proof_preparer',{});preparer_identity=None
 if preparer.get('path') and Path(preparer['path']).exists():
  preparer_identity=ident(preparer['path'])
  if preparer_identity['sha256']!=preparer.get('sha256'):notes.append('Current preparer differs from receipt identity; frozen RPA/RPX identities still checked.')
 with (folder/'proof.rpa').open() as f:header=f.readline().strip()
 entries.append({'case_id':cid,'mechanical_status':'PASS' if not problems else 'FAIL','problems':problems,'notes':notes,'receipt':ident(path),'files':files,'kernel_binary_sha256':kh,'last_verify_command':command,'last_verify_exit_code':last['exit_code'],'result':result,'request_summary':{'claims':[{k:len(v) if k in ('projection','affine_projection') else v for k,v in c.items()} for c in claims],'points':points,'bijections':bijections},'request_keys':list(q) if isinstance(q,dict) else ['legacy_claim_array'],'rpa_header':header,'current_preparer':preparer_identity,'negative_check_count':len(d.get('negative_checks',[])),'protocol_status':d.get('protocol_status'),'ancillary_unverified_contracts':{k:v for k,v in d.items() if k.startswith('ancillary_')}})
 print(cid,entries[-1]['mechanical_status'],flush=True)
counts=Counter(x['status'] for x in ledger['cases']);global_problems=[];check(dict(counts)==ledger['summary']['statuses'],'ledger summary status counts mismatch',global_problems);check(len(byid)==len(ledger['cases'])==81,'81-case inventory/ledger size mismatch',global_problems);check({x['case_id'] for x in ledger['cases']}==set(byid),'ledger/inventory case identity set mismatch',global_problems);check(digest(ledger_path)==ledger_identity['sha256'],'ledger changed during audit',global_problems);check(digest(inventory_path)==inventory_identity['sha256'],'inventory changed during audit',global_problems)
output={'schema':'delivery-ledger-independent-review-v1','scope':'Read-only identity/receipt validation. No kernel replay and no inference that requested-contract validity equals original-report completeness.','auditor':ident(Path(__file__)),'ledger':ledger_identity,'inventory':inventory_identity,'summary':{'ledger_verified':counts['VERIFIED'],'mechanically_passed':sum(x['mechanical_status']=='PASS' for x in entries),'mechanical_failures':sum(x['mechanical_status']=='FAIL' for x in entries),'unverified_cases':[x['case_id'] for x in ledger['cases'] if x['status']!='VERIFIED'],'global_problems':global_problems,'elapsed_seconds':time.perf_counter()-start},'entries':entries}
OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(output['summary'],indent=2))
