#!/usr/bin/env python3
"""Frozen extension/injectivity families and actual full-contract certificates."""
from pathlib import Path
import argparse,json,hashlib,platform,subprocess,time,re,statistics
ROOT=Path(__file__).resolve().parents[1]
def expr(terms=(),constant=0):return {'constant':str(constant),'terms':[[i,str(c)] for i,c in terms if c]}
def lin(i,terms):return {'Lin':{'id':i,'kind':'Le','constant':'0','terms':[[r,str(c)] for r,c in terms]}}
def mps(path,variables,rows):
    text=['NAME theorem_benchmark','ROWS',' N obj']+[f' {s} {r}' for r,s,e,b in rows]+['COLUMNS'];cols=[[] for _ in variables]
    for name,sense,terms,rhs in rows:
        for i,c in terms:cols[i].append((name,c))
    for i,((integer,upper),column) in enumerate(zip(variables,cols)):
        text.append(f' x{i} obj 0');text += [f' x{i} {r} {c}' for r,c in column]
    text+=['RHS']+[f' rhs {r} {b}' for r,s,e,b in rows]+['BOUNDS']
    for i,(integer,upper) in enumerate(variables):
        text.append(f' {"LI" if integer else "LO"} b x{i} 0')
        if upper is not None:text.append(f' {"UI" if integer else "UP"} b x{i} {upper}')
    path.write_text('\n'.join(text+['ENDATA','']))
def baseclaim(integer=False):return {'reverse':False,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[],'inverse':None}
def synthetic(kind,n,k=None):
    name=f'{kind}-{n}'+(f'-k{k}' if k is not None else '');d=ROOT/'bench/theorem-generated'/name;d.mkdir(parents=True,exist_ok=True)
    c=baseclaim(kind in ('menu','injectivity'));steps=[];checks=[];observations=[];pair=[]
    if kind=='menu':
        variables=[v for _ in range(n) for v in [(True,1),(True,k)]];rows=[(f'gate{i}','L',[(2*i,-k),(2*i+1,1)],0) for i in range(n)];outvars=[(True,1)]*(n*(k+1));outrows=[(f'pack{i}','L',[(i*(k+1)+j,1) for j in range(k+1)],1) for i in range(n)];menus=[];mapping=[expr([(2*n+j,1)]) for j in range(n*(k+1))]
        for i in range(n):
            menus.append({'maximum_index':k,'activation':expr([(2*i,1)]),'index':expr([(2*i+1,1)]),'checks':[{'VarLower':2*i},{'VarUpper':2*i},'Exact',{'VarLower':2*i+1},{'RowUpper':i},'Exact']})
            steps.append(lin(i,[({'RowEq':n+2*i},1),({'VarUpper':2*i},1)]))
            observations += [[expr([(2*i,1)]),expr([(i*(k+1)+j,1) for j in range(k+1)])],[expr([(2*i+1,1)]),expr([(i*(k+1)+j,j) for j in range(k+1)])]]
        for j in range(n*(k+1)):checks += [{'VarLower':2*n+j},{'VarUpper':2*n+j},'Exact']
        checks += [{'Local':i} for i in range(n)]+['Exact']+[{'RowEq':n+i} for i in range(2*n)]
        end={'MenuLift':{'menus':menus,'body':{'steps':steps,'end':{'Return':{'map':mapping,'checks':checks}}}}}
    elif kind=='interval':
        variables=outvars=[(False,1)]*n;rows=outrows=[];mapping=[expr([(n+i,1)]) for i in range(n)];intervals=[]
        for i in range(n):
            intervals.append({'lower':[expr([(i,1)])],'upper':[expr([(i,1)])],'checks':['Exact']})
            steps += [lin(3*i,[({'RowLower':2*i},1),({'VarLower':i},1)]),lin(3*i+1,[({'RowUpper':2*i+1},1),({'VarUpper':i},1)]),{'EqPair':{'id':3*i+2,'positive':{'RowUpper':2*i+1},'negative':{'RowLower':2*i}}}]
            checks += [{'Local':3*i},{'Local':3*i+1}];observations.append([expr([(i,1)]),expr([(i,1)])])
        checks+=['Exact']+[{'Local':3*i+2} for i in range(n)]
        end={'IntervalLift':{'intervals':intervals,'body':{'steps':steps,'end':{'Return':{'map':mapping,'checks':checks}}}}}
    elif kind=='flow':
        variables=[(False,None)]*n;outvars=[(False,None)]*(2*n);rows=outrows=[];groups=[];mapping=[expr([(n+i,1)]) for i in range(2*n)]
        for i in range(n):
            groups.append({'source':0,'commodities':[[0,'0'],[0,'0']],'flows':[expr([(i,1)])],'nonnegative':[{'VarLower':i}],'balances':['Exact']});observations.append([expr([(i,1)]),expr([(2*i,1),(2*i+1,1)])])
        checks=[{'VarLower':n+i} for i in range(2*n)]+['Exact']+[{'RowEq':3*i+2} for i in range(n)]
        end={'FlowLift':{'witness':{'nodes':1,'arcs':[[0,0]],'groups':groups},'body':{'steps':[],'end':{'Return':{'map':mapping,'checks':checks}}}}}
    else:
        variables=outvars=[(True,1)]*n;rows=outrows=[];mapping=[expr([(i,1)]) for i in range(n)]
        checks=[r for i in range(n) for r in [{'VarLower':i},{'VarUpper':i},'Exact']]+['Exact'];end={'Return':{'map':mapping,'checks':checks}}
    if observations:c['affine_projection']=observations
    cert={'claims':[c],'blocks':[{'steps':[],'end':end}]}
    if kind=='injectivity':
        back=dict(c,reverse=True);cert['claims'].append(back);cert['blocks'].append({'steps':[],'end':{'Return':{'map':mapping,'checks':checks+['Exact']*n}}});pair=[{'forward_claim':0,'reverse_claim':1}];cert['bijections']=[{'claim':pair[0],'injectivity':{'steps':[],'checks':[{'RowEq':i} for i in range(n)]}}]
    mps(d/'source.mps',variables,rows);mps(d/'target.mps',outvars,outrows);(d/'proof.rpa').write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps({'claims':cert['claims'],'points':[],'bijections':pair})+'\n');return d

def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',required=True,type=Path);p.add_argument('--source-root',required=True,type=Path);p.add_argument('--label',required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args();kernel=a.kernel.resolve();source=a.source_root.resolve();config=json.loads((ROOT/'bench/theorem_workloads_v7.json').read_text());out=ROOT/'bench/results'/a.label;out.mkdir(parents=True,exist_ok=True)
    if (out/'raw.json').exists():raise SystemExit('Refusing to replace evidence')
    def invoke(cmd):
        start=time.perf_counter_ns();command=list(map(str,cmd));r=subprocess.run(command,capture_output=True,text=True)
        try:result=json.loads(r.stdout)
        except json.JSONDecodeError:result={'status':'IO_ERROR','stdout':r.stdout,'stderr':r.stderr}
        return {'command':command,'wall_ns':time.perf_counter_ns()-start,'exit_code':r.returncode,'result':result}
    report={'config':config,'diagnostic':a.diagnostic,'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'source_root':str(source),'sources':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'crates/core/src').glob('*.rs')},'lock_sha256':hashlib.sha256((source/'Cargo.lock').read_bytes()).hexdigest(),'rustc':subprocess.check_output(['rustc','-Vv'],text=True),'platform':platform.platform(),'hardware':{k:subprocess.check_output(['sysctl','-n',k],text=True).strip() for k in ['machdep.cpu.brand_string','hw.memsize','hw.ncpu']},'cache':'warm after preparation, fresh process, no flushing','workloads':[]}
    cases=[('menu',n,k) for k in config['menu_maximum_indices'] for n in config['menu_counts']]+[(kind,n,None) for kind,key in [('interval','interval_counts'),('flow','flow_group_counts'),('injectivity','injectivity_counts')] for n in config[key]]+[('real',n,None) for n in config['real_cases']]
    for kind,n,k in cases:
        start=time.perf_counter_ns();prep=[]
        if kind=='real':
            d=ROOT/'cases'/f'test{n}';receipt=d/'preparation.json'
            if not (d/'proof.rpx').exists():raise SystemExit('Missing actual RPX: '+str(d))
            (out/'receipts').mkdir(exist_ok=True);(out/'receipts'/f'test{n}.json').write_bytes(receipt.read_bytes());generation=0
        else:
            d=synthetic(kind,n,k);generation=time.perf_counter_ns()-start
            for cmd in [['canonical',d/'source.mps',d/'source.mcm'],['canonical',d/'target.mps',d/'target.mcm'],['assemble',d/'proof.rpa',d/'proof.rpx']]:prep.append(invoke([kernel,*cmd]))
            if any(p['exit_code'] for p in prep):(out/'failed-preparation.json').write_text(json.dumps(prep,indent=2));raise SystemExit('Preparation failed; saved')
        command=[kernel,'verify',d/'source.mcm',d/'target.mcm',d/'proof.rpx',d/'request.json'];record={'name':d.name,'generation_ns':generation,'preparation':prep,'artifacts':{f:{'bytes':(d/f).stat().st_size,'sha256':hashlib.sha256((d/f).read_bytes()).hexdigest()} for f in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']},'samples':[invoke(command) for _ in range(1 if a.diagnostic else config['repetitions'])],'rss':[]}
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
