#!/usr/bin/env python3
"""Fixed V1 baseline: fresh-process latency plus kernel timing, bytes and RSS."""
import argparse,hashlib,json,platform,re,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--kernel',default='target/release/rpx');p.add_argument('--label',required=True);p.add_argument('--source-root',default=str(ROOT));a=p.parse_args()
kernel=(ROOT/a.kernel).resolve();config=json.loads((ROOT/'bench/workloads.json').read_text())
source_root=Path(a.source_root).resolve()
out=ROOT/'bench/results'/a.label;out.mkdir(parents=True,exist_ok=True)
if (out/'raw.json').exists():raise SystemExit('Refusing to replace a preserved benchmark result; choose a fresh label.')
def call(args):
    start=time.perf_counter_ns();r=subprocess.run([str(kernel),*map(str,args)],capture_output=True,text=True);wall=time.perf_counter_ns()-start
    try:v=json.loads(r.stdout)
    except json.JSONDecodeError:v={'status':'IO_ERROR','message':r.stderr,'stdout':r.stdout}
    return {'command':[str(kernel),*map(str,args)],'exit_code':r.returncode,'wall_ns':wall,'result':v}
def fixture(kind,n):
    generation_start=time.perf_counter_ns()
    d=ROOT/'bench/generated'/f'{kind}-{n}';d.mkdir(parents=True,exist_ok=True)
    dense=kind!='identity'; coeff=('0.125' if kind=='rational' else '1');
    lines=['NAME bench','ROWS',' N OBJ']+[f' L r{i}' for i in range(1 if dense else n)]+['COLUMNS']
    for i in range(n):lines.append(f' x{i} r{0 if dense else i} {coeff}')
    lines+=['RHS']+[f' rhs r{i} {n if dense else 1}' for i in range(1 if dense else n)]+['BOUNDS']
    for i in range(n):lines.append(f' BV bnd x{i}')
    lines.append('ENDATA');(d/'model.mps').write_text('\n'.join(lines)+'\n')
    refs=[]
    for i in range(n):refs += [{'VarLower':i},{'VarUpper':i},{'VarInt':i}]
    refs += [{'RowUpper':i} for i in range(1 if dense else n)]+['Exact']
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}
    cert={'claims':[claim],'blocks':[{'steps':[],'end':{'Return':{'map':[{'constant':'0','terms':[[i,'1']]} for i in range(n)],'checks':refs}}}]}
    (d/'proof.rpa').write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps([claim]))
    generation_ns=time.perf_counter_ns()-generation_start
    prep=[call(['canonical',d/'model.mps',d/'model.mcm']),call(['assemble',d/'proof.rpa',d/'proof.rpx'])]
    return d,prep,generation_ns
meta={'config':config,'label':a.label,'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'source_root':str(source_root),'hardware': {k: subprocess.check_output(['sysctl','-n',k],text=True).strip() for k in ['machdep.cpu.brand_string','hw.memsize','hw.ncpu']} if platform.system()=='Darwin' else {},'platform':platform.platform(),'processor':platform.processor(),'rustc':subprocess.check_output(['rustc','-Vv'],text=True),'cache_condition':'warm filesystem after preparation; each observation fresh process, no cache flushing','sources':{str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((source_root/'crates/core/src').rglob('*.rs'))},'lock_sha256':hashlib.sha256((source_root/'Cargo.lock').read_bytes()).hexdigest(),'workloads':[]}
for kind,sizes in [('identity',config['identity_sizes']),('dense',config['dense_row_sizes']),('rational',config['rational_sizes'])]:
 for n in sizes:
    d,prep,generation_ns=fixture(kind,n);rec={'name':f'{kind}-{n}','preparation':prep,'preparation_generation_ns':generation_ns,'samples':[],'bytes':{f:(d/f).stat().st_size for f in ['model.mps','model.mcm','proof.rpa','proof.rpx','request.json']}}
    rec['artifacts']={f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in ['model.mps','model.mcm','proof.rpa','proof.rpx','request.json']}
    if any(x['exit_code']!=0 for x in prep):
        meta['workloads'].append(rec);(out/'raw.json').write_text(json.dumps(meta,indent=2)+'\n');raise SystemExit('Preparation failed; evidence retained.')
    for k in range(config['repetitions']):
        rec['samples'].append(call(['verify',d/'model.mcm',d/'model.mcm',d/'proof.rpx',d/'request.json']))
    command=[str(kernel),'verify',str(d/'model.mcm'),str(d/'model.mcm'),str(d/'proof.rpx'),str(d/'request.json')]
    if platform.system()=='Darwin':
        rss=subprocess.run(['/usr/bin/time','-l',*command],capture_output=True,text=True)
        match=re.search(r'(\d+)\s+maximum resident set size',rss.stderr);rec['rss_bytes']=int(match.group(1)) if match else None;rec['rss_raw']=rss.stderr
        rec['rss_exit_code']=rss.returncode;rec['rss_stdout']=rss.stdout
    elapsed=[s['wall_ns']/1e6 for s in rec['samples']];execute=[s['result']['execute_us']/1000 for s in rec['samples'] if s['result']['status']=='VERIFIED'];rec['summary']={'process_ms_min':min(elapsed),'process_ms_median':statistics.median(elapsed),'process_ms_max':max(elapsed),'execute_ms_median':statistics.median(execute) if execute else None,'verified':len(execute)}
    meta['workloads'].append(rec);(out/'raw.json').write_text(json.dumps(meta,indent=2)+'\n');print(rec['name'],json.dumps(rec['summary']),flush=True)
    if any(x['exit_code']!=0 or x['result']['status']!='VERIFIED' for x in rec['samples']):raise SystemExit('Verification failed; all samples retained.')
    if platform.system()=='Darwin' and (rec['rss_exit_code']!=0 or json.loads(rec['rss_stdout'])['status']!='VERIFIED' or not rec['rss_bytes']):raise SystemExit('RSS verification failed; raw output retained.')
meta['kernel_sha256_after']=hashlib.sha256(kernel.read_bytes()).hexdigest()
(out/'raw.json').write_text(json.dumps(meta,indent=2)+'\n')
if meta['kernel_sha256_after']!=meta['kernel_sha256']:raise SystemExit('Binary changed during sampling.')
print(out/'raw.json')
