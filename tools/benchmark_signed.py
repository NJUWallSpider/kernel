#!/usr/bin/env python3
"""Frozen V8 signed theorem benchmark and affine/renaming generalizations."""
from pathlib import Path
from fractions import Fraction as F
import argparse,json,hashlib,platform,subprocess,time,re,statistics,random,importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_wire',ROOT/'tests/vectors/generate_vectors.py');wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
def expr(c=0,t=()):return {'constant':str(c),'terms':[[i,str(a)] for i,a in sorted(t) if a]}
def eqexpr(e):return wire.expression(F(e['constant']),[(i,F(c).numerator,F(c).denominator) for i,c in e['terms']])
def plus(a,b,scale=1):
 terms={i:F(c) for i,c in a['terms']}
 for i,c in b['terms']:terms[i]=terms.get(i,F(0))+scale*F(c)
 return expr(F(a['constant'])+scale*F(b['constant']),terms.items())
def var(n,integer,lo,hi):return wire.name(n)+wire.tag(integer)+wire.optional(None if lo is None else wire.q(lo))+wire.optional(None if hi is None else wire.q(hi))
def row(n,e):return wire.name(n)+eqexpr(e)+wire.optional(None)+wire.optional(wire.q(0))
def synthetic(n,capacity,seed):
 name=f'signed-{n}-c{capacity.replace("/","_")}-s{seed}';d=ROOT/'bench/signed-generated'/name;d.mkdir(parents=True,exist_ok=True);r=random.Random(seed);C=F(capacity)
 si=list(range(2*n));ti=list(range(4*n));sr=list(range(2*n));tr=list(range(2*n))
 for p in [si,ti,sr,tr]:r.shuffle(p)
 sourcevars=[None]*(2*n);targetvars=[None]*(4*n);srows=[None]*(2*n);trows=[None]*(2*n);sobj=expr(F(7,11));tobj=expr(F(7,11));decompositions=[];mapping=[None]*(4*n);domain=[None]*(4*n);rowchecks=[None]*(2*n);observations=[];affinechecks=[];terms=[]
 for j in range(n):
  x,z=si[2*j:2*j+2];out=ti[4*j:4*j+4];gen=list(range(2*n+4*j,2*n+4*j+4));ri=2*n+4*j;flipped=j%2==1;weight=[F(1,7),F(2,3),F(5)][j%3];flow=expr(F((j%7)-3,11),[(x,[F(-2,3),F(3,5),F(2)][j%3])]);activation=expr(1 if flipped else 0,[(z,-1 if flipped else 1)])
  sourcevars[x]=var(f'real_{seed}_{j}',0,None,None);sourcevars[z]=var(f'gate_{seed}_{j}',1,0,1)
  sobj=plus(sobj,activation,weight);tobj=plus(tobj,expr(0,[(out[2],1),(out[3],1)]),weight)
  upper=plus(flow,activation,-C);lower=plus(plus(expr(),flow,-1),activation,-C)
  srows[sr[2*j]]=row(f'src_{seed}_{j}_a',upper);srows[sr[2*j+1]]=row(f'src_{seed}_{j}_b',lower)
  for k,i in enumerate(out):
   targetvars[i]=var(f'out_{seed}_{j}_{k}',k>=2,0,1 if k>=2 else None);mapping[i]=expr(0,[(gen[k],1)]);domain[i]=[{'VarLower':gen[k]}]+([{'VarUpper':gen[k]},{'VarInt':gen[k]}] if k>=2 else [])
  for k in range(2):trows[tr[2*j+k]]=row(f'dst_{seed}_{j}_{k}',expr(0,[(out[k],1),(out[k+2],-C)]));rowchecks[tr[2*j+k]]={'RowUpper':ri+2+k}
  checks=[{'VarUpper' if flipped else 'VarLower':z},{'VarLower' if flipped else 'VarUpper':z},'Exact',{'RowUpper':sr[2*j]},{'RowUpper':sr[2*j+1]}]
  decompositions.append({'capacity':str(C),'flow':flow,'activation':activation,'checks':checks});terms.append([{'RowEq':ri+1},str(weight)])
  observations.extend([[flow,expr(0,[(out[0],1),(out[1],-1)])],[activation,expr(0,[(out[2],1),(out[3],1)])]]);affinechecks.extend([{'RowEq':ri},{'RowEq':ri+1}])
 (d/'source.mcm').write_bytes(wire.frame(b'MCM\0',wire.name('source_'+name)+wire.array(sourcevars)+wire.array(srows)+eqexpr(sobj)))
 (d/'target.mcm').write_bytes(wire.frame(b'MCM\0',wire.name('target_'+name)+wire.array(targetvars)+wire.array(trows)+eqexpr(tobj)))
 claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'affine_projection':observations,'inverse':None}
 body={'steps':[{'Lin':{'id':0,'kind':'Eq','constant':'0','terms':terms}}],'end':{'Return':{'map':mapping,'checks':[c for ds in domain for c in ds]+rowchecks+[{'Local':0}]+affinechecks}}}
 cert={'claims':[claim],'blocks':[{'steps':[],'end':{'SignedLift':{'decompositions':decompositions,'body':body}}}]}
 (d/'proof.rpa').write_text('RPA 8\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps([claim],separators=(',',':'))+'\n');return d

def main():
 p=argparse.ArgumentParser();p.add_argument('--kernel',required=True,type=Path);p.add_argument('--source-root',required=True,type=Path);p.add_argument('--label',required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args();kernel=a.kernel.resolve();source=a.source_root.resolve();config=json.loads((ROOT/'bench/signed_workloads_v8.json').read_text());out=ROOT/'bench/results'/a.label;out.mkdir(parents=True,exist_ok=True)
 if (out/'raw.json').exists():raise SystemExit('Refusing to replace evidence')
 def invoke(cmd):
  start=time.perf_counter_ns();command=list(map(str,cmd));r=subprocess.run(command,capture_output=True,text=True)
  try:result=json.loads(r.stdout)
  except json.JSONDecodeError:result={'status':'IO_ERROR','stdout':r.stdout,'stderr':r.stderr}
  return {'command':command,'wall_ns':time.perf_counter_ns()-start,'exit_code':r.returncode,'result':result}
 report={'config':config,'diagnostic':a.diagnostic,'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'source_root':str(source),'sources':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'crates/core/src').glob('*.rs')},'lock_sha256':hashlib.sha256((source/'Cargo.lock').read_bytes()).hexdigest(),'rustc':subprocess.check_output(['rustc','-Vv'],text=True),'platform':platform.platform(),'hardware':{k:subprocess.check_output(['sysctl','-n',k],text=True).strip() for k in ['machdep.cpu.brand_string','hw.memsize','hw.ncpu']},'cache':'warm after preparation, fresh process, no flushing','workloads':[]}
 cases=[('signed',n,c,seed) for c,seed in config['capacity_seeds'] for n in config['counts']]+[('real',n,None,None) for n in config['real_cases']]
 for kind,n,c,seed in cases:
  start=time.perf_counter_ns();prep=[]
  if kind=='real':
   d=ROOT/'cases'/f'test{n}';receipt=d/'preparation.json';(out/'receipts').mkdir(exist_ok=True);(out/'receipts'/f'test{n}.json').write_bytes(receipt.read_bytes());generation=None
  else:
   d=synthetic(n,c,seed);generation=time.perf_counter_ns()-start;prep=[invoke([kernel,'assemble',d/'proof.rpa',d/'proof.rpx'])]
   if any(p['exit_code'] for p in prep):(out/'failed-preparation.json').write_text(json.dumps(prep,indent=2));raise SystemExit('Preparation failed; saved')
  command=[kernel,'verify',d/'source.mcm',d/'target.mcm',d/'proof.rpx',d/'request.json'];record={'name':d.name,'generation_ns':generation,'preparation':prep,'preparation_note':'Synthetic MCM and RPA generated directly by independent exact Python writer; no MPS canonicalization stage. Actual receipt supplies its prior preparation.','artifacts':{f:{'bytes':(d/f).stat().st_size,'sha256':hashlib.sha256((d/f).read_bytes()).hexdigest()} for f in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']},'samples':[invoke(command) for _ in range(1 if a.diagnostic else config['repetitions'])],'rss':[]}
  if not a.diagnostic:
   for _ in range(3):
    r=subprocess.run(['/usr/bin/time','-l',*map(str,command)],capture_output=True,text=True);m=re.search(r'(\d+)\s+maximum resident set size',r.stderr);record['rss'].append({'bytes':int(m[1]) if m else None,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  record['all_verified']=all(r['exit_code']==0 and r['result']['status']=='VERIFIED' for r in record['samples']) and all(r['exit_code']==0 and json.loads(r['stdout'])['status']=='VERIFIED' for r in record['rss'])
  if record['all_verified']:
   record['summary']={}
   for metric,values in [('process_ms',[x['wall_ns']/1e6 for x in record['samples']]),('execute_ms',[x['result']['execute_us']/1000 for x in record['samples']])]:record['summary'][metric]={'min':min(values),'median':statistics.median(values),'max':max(values)}
  report['workloads'].append(record);(out/'raw.json').write_text(json.dumps(report,indent=2)+'\n');print(d.name,record['all_verified'],record.get('summary'),flush=True)
  if not record['all_verified']:raise SystemExit('Nonverification retained as failure, not successful timing')
if __name__=='__main__':main()
