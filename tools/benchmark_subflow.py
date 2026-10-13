#!/usr/bin/env python3
"""Fixed joint-subflow draft workloads; independent preparation and honest sampling."""
from fractions import Fraction as F
from pathlib import Path
import argparse,hashlib,importlib.util,json,platform,re,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'bench/subflow_workloads_v10_draft.json'
spec=importlib.util.spec_from_file_location('independent_wire',ROOT/'tests/vectors/generate_vectors.py');wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ex(c=0,terms=()):return {'constant':str(c),'terms':[[i,str(a)] for i,a in sorted(terms) if a]}
def expression_bytes(e):return wire.expression(F(e['constant']),[(i,F(c).numerator,F(c).denominator) for i,c in e['terms']])
def scale(e,a):return ex(F(e['constant'])*a,[(i,F(c)*a) for i,c in e['terms']])
def evaluate(e,x):return F(e['constant'])+sum((F(c)*x[i] for i,c in e['terms']),F(0))
def encode_model(name,variables,rows,obj):
    def var(v):return wire.name(v['name'])+wire.tag(0)+wire.optional(wire.q(0))+wire.optional(None if v['upper'] is None else wire.q(v['upper']))
    def row(r):return wire.name(r['name'])+expression_bytes(r['expr'])+wire.optional(None if r['lower'] is None else wire.q(r['lower']))+wire.optional(None if r['upper'] is None else wire.q(r['upper']))
    return wire.frame(b'MCM\0',wire.name(name)+wire.array([var(v) for v in variables])+wire.array([row(r) for r in rows])+expression_bytes(obj))
def generate_strict_image(case,d):
    start=time.perf_counter_ns();d.mkdir(exist_ok=True,parents=True);n=case['coordinates'];kind=case['kind'];assert n>=1 and kind in ['strict','image']
    variables=[{'name':f'x{i}','upper':F(1)} for i in range(n)];objective=ex(0,[(i,1) for i in range(n)])
    (d/'source.mcm').write_bytes(encode_model('source_'+case['name'],variables,[],objective));target=[dict(v) for v in variables]
    if kind=='strict':
        claim={'target':False,'integers':False,'positive':objective};request={'claims':[],'improvements':[claim]}
        block={'steps':[],'end':{'ImproveReturn':{'map':[ex() for i in range(n)],'checks':['Exact']*(2*n+1),'margin':{'Predicate':'1'}}}}
        cert={'claims':[],'blocks':[],'improvements':[{'claim':claim,'block':block}]}
        old=[F(2,3)]*n;joint=[F(0)]*n;assert all(0<=x<=1 for x in old+joint)
        assert evaluate(objective,joint)-evaluate(objective,old)+evaluate(claim['positive'],old)==0 and evaluate(objective,joint)<evaluate(objective,old)
    else:
        target[-1]['upper']=F(1,2);mapping=[ex(0,[(i,1)]) for i in range(n)];claim={'ImageExclusion':{'point_in_target':False,'map':mapping}};request={'claims':[],'points':[claim]};old=[F(2,3)]*n
        cert={'claims':[],'blocks':[],'points':[{'claim':claim,'values':[str(v) for v in old]}]}
        image=[evaluate(e,old) for e in mapping];assert all(0<=x<=1 for x in old) and len(image)==n and image[-1]>target[-1]['upper']
    (d/'target.mcm').write_bytes(encode_model('target_'+case['name'],target,[],objective));(d/'proof.rpa').write_text('RPA 10\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps(request,separators=(',',':'))+'\n')
    result={'status':'GENERATED_EXACT_CHECKED','generation_ns':time.perf_counter_ns()-start,'name':case['name'],'source_variables':n,'source_rows':0,'target_variables':n,'target_rows':0,'source_terms':n,'target_terms':n,'proof_steps':0,'complete_obligations':2*n+1 if kind=='strict' else None,'full_point_coordinates':n if kind=='image' else None,'caller_bound_coordinate_count':n,'independent_point_and_margin_check':True}
    (d/'generation.json').write_text(json.dumps(result,indent=2)+'\n');return result
def generate_halfspace(case,d):
    start=time.perf_counter_ns();d.mkdir(exist_ok=True,parents=True);n=case['coordinates'];assert n>=1
    variables=[{'name':f'x{i}','upper':F(1)} for i in range(n)];objective=ex(7,[(i,1) for i in range(n)]);halfspace=ex(0,[(i,1) for i in range(n)])
    (d/'source.mcm').write_bytes(encode_model('source_'+case['name'],variables,[],objective));(d/'target.mcm').write_bytes(encode_model('target_'+case['name'],variables,[],objective))
    claim={'reverse':False,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[i,i] for i in range(n)],'inverse':None,'input_halfspace':halfspace}
    if case['level']:claim['input_objective_level']='7'
    checks=[]
    for i in range(n):checks.extend([{'VarLower':i},{'VarUpper':i}])
    checks+=['Exact']*(n+1)
    cert={'claims':[claim],'blocks':[{'steps':[],'end':{'Return':{'map':[ex(0,[(i,1)]) for i in range(n)],'checks':checks}}}]}
    (d/'proof.rpa').write_text('RPA 10\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps([claim],separators=(',',':'))+'\n')
    point=[F(0)]*n;assert len(point)==n and all(0<=x<=1 for x in point) and evaluate(halfspace,point)==0 and evaluate(objective,point)==7
    assert evaluate(halfspace,[F(2,3)]*n)>0
    result={'status':'GENERATED_EXACT_CHECKED','generation_ns':time.perf_counter_ns()-start,'name':case['name'],'source_variables':n,'source_rows':0,'target_variables':n,'target_rows':0,'source_terms':n,'target_terms':n,'proof_steps':0,'complete_obligations':len(checks),'caller_bound_coordinate_count':n,'expected_generated_domain_rows':1+int(case['level']),'independent_nonempty_restriction_checked':True}
    (d/'generation.json').write_text(json.dumps(result,indent=2)+'\n');return result
def generate(case,d):
    if case.get('kind') in ['strict','image']:return generate_strict_image(case,d)
    if case.get('kind')=='halfspace':return generate_halfspace(case,d)
    start=time.perf_counter_ns();d.mkdir(exist_ok=True,parents=True);n,G,width=case['nodes'],case['groups'],case['width'];assert n>=2
    arcs=[(0,v) for v in range(1,n)]+[(v,0) for v in range(1,n)]+[(v,v) for v in range(n)];m=len(arcs);assert m==3*n-2
    c=F(0) if width==1 else F(1,7);coeff=[F(1)] if width==1 else [F(k+1,k+2) for k in range(width)]
    flow=[ex(c,[(e*width+k,coeff[k]) for k in range(width)]) for e in range(m)];nv=m*width;variables=[{'name':f'x{i}','upper':None} for i in range(nv)]
    rhs=[F(n-1)]+[F(-1)]*(n-1);rows=[]
    for v in range(n):
        terms=[];constant=F(0)
        for (tail,head),e in zip(arcs,flow):
            s=int(tail==v)-int(head==v);constant+=s*F(e['constant']);terms.extend((i,s*F(a)) for i,a in e['terms'] if s)
        rows.append({'name':f'balance{v}','expr':ex(constant,terms),'lower':rhs[v],'upper':rhs[v]})
    objective=ex(F(13,11),[(i,F(1,11)) for i in range(nv)])
    (d/'source.mcm').write_bytes(encode_model('source_'+case['name'],variables,rows,objective))
    outputvars=list(variables);outputrows=list(rows);steps=[];groups=[];checks=[{'VarLower':i} for i in range(nv)]
    nextid=0
    def linear(kind,constant,terms):
        nonlocal nextid
        ident=nextid;nextid+=1;steps.append({'Lin':{'id':ident,'kind':kind,'constant':str(constant),'terms':[[ref,str(v)] for ref,v in terms]}});return {'Local':ident}
    for group in range(G):
        a=F(7+group,7);B=a*(n-1);startvar=len(outputvars);flows=[scale(e,a) for e in flow]
        nonneg=[linear('Le',-F(e['constant']),[({'VarLower':i},F(v)) for i,v in e['terms']]) for e in flows]
        balances=[linear('Eq',0,[({'RowEq':v},a)]) for v in range(n)]
        groups.append({'source':0,'demands':[[v,str(a)] for v in range(1,n)],'flows':flows,'nonnegative':nonneg,'balances':balances})
        for i in range(m):outputvars.append({'name':f'g{group}_{i}','upper':B});checks.extend([{'VarLower':startvar+i},{'VarUpper':startvar+i}])
        for v in range(n):
            terms=[(startvar+i,int(u==v)-int(w==v)) for i,(u,w) in enumerate(arcs) if u!=w and (u==v or w==v)]
            outputrows.append({'name':f'g{group}_balance{v}','expr':ex(0,terms),'lower':a*rhs[v],'upper':a*rhs[v]})
        for i,e in enumerate(flows):outputrows.append({'name':f'g{group}_sub{i}','expr':ex(-F(e['constant']),[(j,-F(v)) for j,v in e['terms']]+[(startvar+i,1)]),'lower':None,'upper':F(0)})
    for i,r in enumerate(outputrows):checks.append({'RowEq' if r['lower'] is not None else 'RowUpper':i})
    checks+=['Exact']*(nv+1)
    claim={'reverse':False,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[i,i] for i in range(nv)],'inverse':None}
    body={'steps':[],'end':{'Return':{'map':[ex(0,[(i,1)]) for i in range(len(outputvars))],'checks':checks}}}
    cert={'claims':[claim],'blocks':[{'steps':steps,'end':{'SubflowLift':{'witness':{'nodes':n,'arcs':arcs,'groups':groups},'body':body}}}]}
    (d/'target.mcm').write_bytes(encode_model('target_'+case['name'],outputvars,outputrows,objective));(d/'proof.rpa').write_text('RPA 10\n'+json.dumps(cert,separators=(',',':'))+'\n');(d/'request.json').write_text(json.dumps([claim],separators=(',',':'))+'\n')
    # An independently evaluated nonempty point with source circulation larger
    # than the bound in the smallest case. The proof is universal, not this point.
    old=[F(0)]*nv
    for i in range(m):old[i*width]=F(4 if i<n-1 else 3 if i<2*(n-1) else 5)/coeff[0]
    joint=list(old)
    for group in range(G):joint.extend(F(7+group,7) if i<n-1 else F(0) for i in range(m))
    for r in rows:assert evaluate(r['expr'],old)==r['lower']
    for v,x in zip(outputvars,joint):assert x>=0 and (v['upper'] is None or x<=v['upper'])
    for r in outputrows:
        value=evaluate(r['expr'],joint);assert (r['lower'] is None or value>=r['lower']) and (r['upper'] is None or value<=r['upper'])
    assert evaluate(objective,old)==evaluate(objective,joint)
    result={'status':'GENERATED_EXACT_CHECKED','generation_ns':time.perf_counter_ns()-start,'name':case['name'],'nodes':n,'arcs':m,'groups':G,'affine_width':width,'source_variables':nv,'source_rows':n,'target_variables':len(outputvars),'target_rows':len(outputrows),'proof_steps':len(steps),'complete_obligations':len(checks),'source_terms':sum(len(r['expr']['terms']) for r in rows)+len(objective['terms']),'target_terms':sum(len(r['expr']['terms']) for r in outputrows)+len(objective['terms']),'independent_joint_point_checked':True}
    (d/'generation.json').write_text(json.dumps(result,indent=2)+'\n');return result

def invoke(cmd):
    started_unix_ns=time.time_ns();start=time.perf_counter_ns();r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    try:result=json.loads(r.stdout)
    except json.JSONDecodeError:result={'status':'IO_ERROR','stdout':r.stdout}
    return {'command':list(map(str,cmd)),'started_unix_ns':started_unix_ns,'finished_unix_ns':time.time_ns(),'wall_ns':time.perf_counter_ns()-start,'exit_code':r.returncode,'result':result,'stderr':r.stderr}
def summary(values):return {'min':min(values),'median':statistics.median(values),'max':max(values)}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',type=Path,default=CONFIG);ap.add_argument('--generate',help='Generate one named fixed workload');ap.add_argument('--directory',type=Path);ap.add_argument('--kernel',type=Path,default=ROOT/'target/subflow-production/release/rpx');ap.add_argument('--label');ap.add_argument('--diagnostic',action='store_true');ap.add_argument('--isolation-note');args=ap.parse_args();config=json.loads(args.config.read_text())
    if args.generate:
        assert args.directory;case=next(x for x in config['synthetic'] if x['name']==args.generate);print(json.dumps(generate(case,args.directory)));return
    assert args.label and (args.diagnostic or args.isolation_note),'Official run requires an explicit isolation note after coordinator clear.'
    kernel=args.kernel.resolve();assert sha(kernel)==config['kernel_sha256'],'Wrong fixed binary';out=ROOT/'bench/results'/args.label;out.mkdir(parents=True,exist_ok=True)
    assert not (out/'raw.json').exists(),'Refusing to overwrite raw evidence'
    receipt=ROOT/config.get('build_receipt','audit/subflow-next/production-receipt.json');(out/'build-receipt.json').write_bytes(receipt.read_bytes())
    if 'build_receipt_sha256' in config:
        assert sha(receipt)==config['build_receipt_sha256'],'Fixed build receipt changed'
        built=json.loads(receipt.read_text());assert built['status']=='PASS' and built['binary']['sha256']==sha(kernel),'Build receipt does not bind sampled binary'
    binding_path=ROOT/config.get('fixture_manifest','bench/subflow_fixture_manifest.json');binding=json.loads(binding_path.read_text()) if binding_path.exists() else None
    if not args.diagnostic:assert binding is not None,'Official timing requires the prevalidated artifact manifest'
    if binding:(out/'fixed-artifact-manifest.json').write_bytes(binding_path.read_bytes())
    report={'config':config,'config_sha256':sha(args.config),'script_sha256':sha(Path(__file__)),'independent_mcm_writer_sha256':sha(ROOT/'tests/vectors/generate_vectors.py'),'kernel':{'path':str(kernel),'sha256':sha(kernel)},'source_build_receipt_sha256':sha(receipt),'diagnostic_nonisolated':args.diagnostic,'isolation_note':args.isolation_note,'cache':'Warm after generation/assembly, independent process per sample, no cache flush','platform':platform.platform(),'rustc':subprocess.check_output(['rustc','-Vv'],text=True),'hardware':{k:subprocess.check_output(['sysctl','-n',k],text=True).strip() for k in ['machdep.cpu.brand_string','hw.memsize','hw.ncpu']},'workloads':[]}
    report['source_build_receipt_path']=str(receipt);report['archived_build_receipt']='build-receipt.json'
    report['driver_command']=['python3',str(Path(__file__).resolve()),*sys.argv[1:]];report['started_unix_ns']=time.time_ns()
    report['fixed_artifact_manifest_sha256']=sha(binding_path) if binding else None
    def save():(out/'raw.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    workloads=config['synthetic']+[{'name':f'test{n}','actual':n} for n in config['actual_cases']]
    for item in workloads:
        record={'name':item['name'],'preparation':[],'samples':[],'rss':[]};report['workloads'].append(record);save()
        if 'actual' not in item:
            for i in range(1 if args.diagnostic else config['preparation_repetitions']):
                d=out/'fixtures'/item['name']/f'prepare{i}';generated=invoke(['python3',Path(__file__), '--config',args.config,'--generate',item['name'],'--directory',d]);record['preparation'].append({'generation':generated});save()
                if generated['exit_code'] or generated['result']['status']!='GENERATED_EXACT_CHECKED':raise SystemExit('Generation failure saved')
                encoded=invoke([kernel,'assemble',d/'proof.rpa',d/'proof.rpx']);record['preparation'][-1]['assembly']=encoded;save()
                if encoded['exit_code'] or encoded['result']['status']!='ASSEMBLED':raise SystemExit('Assembly failure saved')
            record['preparation_note']='Synthetic independent MCM + RPA generation with Fraction joint-point check; no MPS canonicalization. Fresh author/assembler process every repetition.'
        else:
            original=ROOT/'cases'/f'test{item["actual"]}';p=original/'preparation.json';copyto=out/f'test{item["actual"]}-preparation.json';copyto.write_bytes(p.read_bytes());record['actual_preparation_receipt_sha256']=sha(copyto)
            if binding:assert sha(copyto)==binding['actual_preparation_receipt_sha256'],'Actual receipt changed after fixed diagnostic'
            d=out/'fixtures'/item['name'];d.mkdir(parents=True,exist_ok=True)
            for name in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']:(d/name).write_bytes((original/name).read_bytes())
            record['preparation_note']='Not remeasured. Full original author and canonical/assemble costs are in the archived actual receipt; an empty array is not zero preparation cost. Exact sampled actual artifacts are copied into this result directory.'
        names=['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json'];record['artifacts']={n:{'bytes':(d/n).stat().st_size,'sha256':sha(d/n)} for n in names}
        if binding:assert record['artifacts']==binding['workloads'][item['name']],'Artifact differs from prevalidated fixed workload'
        if 'actual' not in item:
            for i in range(len(record['preparation'])):
                for n in names:assert sha(d.parent/f'prepare{i}'/n)==record['artifacts'][n]['sha256'],'Nondeterministic prepared artifact'
            record['generation_counts']=json.loads((d/'generation.json').read_text())
        command=[kernel,'verify',d/'source.mcm',d/'target.mcm',d/'proof.rpx',d/'request.json'];expected=None
        for i in range(1 if args.diagnostic else config['verification_repetitions']):
            sample=invoke(command);record['samples'].append(sample);save()
            if sample['exit_code'] or sample['result']['status']!='VERIFIED':raise SystemExit('Non-VERIFIED sample saved; no timing summary')
            stats=sample['result']['statistics'];expected=stats if expected is None else expected
            if stats!=expected:raise SystemExit('Statistics mismatch saved; no timing summary')
        for i in range(0 if args.diagnostic else config['rss_repetitions']):
            sample=invoke(['/usr/bin/time','-l',*command]);match=re.search(r'(\d+)\s+maximum resident set size',sample['stderr']);sample['rss_bytes']=int(match[1]) if match else None;record['rss'].append(sample);save()
            if sample['exit_code'] or sample['result']['status']!='VERIFIED' or sample['rss_bytes'] is None or sample['result']['statistics']!=expected:raise SystemExit('RSS failure or statistics mismatch saved; no timing summary')
        record['statistics']=expected;record['all_verified']=True;record['summary']={'process_ms':summary([x['wall_ns']/1e6 for x in record['samples']])}
        for metric in ['read_us','model_decode_us','proof_decode_us','execute_us','total_us']:record['summary'][metric]=summary([x['result'][metric] for x in record['samples']])
        if record['rss']:record['summary']['rss_bytes']=summary([x['rss_bytes'] for x in record['rss']])
        if record['preparation']:
            record['summary']['preparation_process_ms']=summary([(x['generation']['wall_ns']+x['assembly']['wall_ns'])/1e6 for x in record['preparation']]);record['summary']['generation_internal_ms']=summary([x['generation']['result']['generation_ns']/1e6 for x in record['preparation']]);record['summary']['assembly_us']=summary([x['assembly']['result']['total_us'] for x in record['preparation']])
        save();print(item['name'],record['all_verified'],record['summary']['process_ms'],flush=True)
    report['kernel_sha256_after']=sha(kernel);save()
    if report['kernel_sha256_after']!=report['kernel']['sha256']:raise SystemExit('Binary changed during sampling; no timing summary')
    report['finished_unix_ns']=time.time_ns();report['status']='ALL_VERIFIED_DIAGNOSTIC_NONISOLATED' if args.diagnostic else 'ALL_VERIFIED_ISOLATION_DECLARED';save()
if __name__=='__main__':main()
