#!/usr/bin/env python3
"""Exact corpus test31 integer projection; shared zero-sum facts and leaf integer cuts."""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict, deque
import json, subprocess, time, argparse, resource
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, expr_json, row_fact, sha
from prepare_test70 import SparseBuilder
from prepare_test84 import rounded

class StreamingPath:
    def __init__(self,path): self.path=path
    def read_text(self): return self
    def splitlines(self): return self.path.open()

def mapped(e,mapping):
    c=e[0]; t={}
    for i,a in e[1].items():
        q,s=mapping[i];c+=a*q
        for j,b in s.items():t[j]=t.get(j,0)+a*b
    return expression(c,t)

def trivial(kind,e):
    return not e[1] and (e[0]==0 if kind=='Eq' else e[0]<=0 if kind=='Le' else e[0].denominator==1)

def obligations(p,out,mapping,integer,rowcheck,intrefs=None):
    checks=[]
    for i,v in enumerate(out['vars']):
        e=mapping[i]
        for typ,bound,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
            if bound is None:continue
            wanted=expression(-sign*bound+sign*e[0],{j:sign*q for j,q in e[1].items()})
            if trivial('Le',wanted):checks.append('Exact')
            else:
                assert e[0]==0 and len(e[1])==1 and next(iter(e[1].values()))==1
                j=next(iter(e[1]));ref={typ:j};assert p.refexpr(ref)==wanted;checks.append(ref)
        if integer and v['integer']:
            if trivial('Int',e):checks.append('Exact')
            else:
                j=next(iter(e[1]));ref=(intrefs or {}).get(j,{'VarInt':j});assert p.refexpr(ref)==e;checks.append(ref)
    for row in out['rows']:
        typ=next(iter(row_ref(out,row['name'])));e=mapped(row_fact(row,typ),mapping);kind='Eq' if typ=='RowEq' else 'Le'
        checks.append('Exact' if trivial(kind,e) else rowcheck(row,e,kind))
    return checks

def run_receipt(case,cert,counts,run,out,k,audit,contract,mutations,start):
    out.mkdir(parents=True,exist_ok=True);rpa=out/'proof.rpa';request=out/'request.json'
    def encode(path,obj):
        with path.open('w') as f:f.write('RPA 2\n');json.dump(obj,f,separators=(',',':'));f.write('\n')
    encode(rpa,cert);request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    source=run/'input/model.mps';target=run/'output/reformulated.mps'
    d={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).with_name('prepare_'+case+'.py').resolve()),'sha256':sha(Path(__file__).with_name('prepare_'+case+'.py'))},'claims':contract,'counts':counts,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def record(args,expected=0):
        then=time.perf_counter();p=subprocess.run([str(k)]+list(map(str,args)),capture_output=True,text=True)
        item={'command':[str(k)]+list(map(str,args)),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'seconds':time.perf_counter()-then};d['kernel_runs'].append(item)
        if p.returncode!=expected:
            d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';d['preparation_seconds']=time.perf_counter()-start;(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(item)
        return item
    record(['canonical',source,out/'source.mcm']);record(['canonical',target,out/'target.mcm']);record(['assemble',rpa,out/'proof.rpx'])
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]
    first=record(verify);assert json.loads(first['stdout'])['status']=='VERIFIED'
    record(['assemble',rpa,out/'determinism.rpx']);assert sha(out/'determinism.rpx')==sha(out/'proof.rpx');(out/'determinism.rpx').unlink()
    d['assemble_byte_deterministic']=True
    for name,reason,mutate in mutations:
        undo=mutate();path=out/(name+'.rpa');encoded=out/(name+'.rpx');encode(path,cert);undo()
        assembled=record(['assemble',path,encoded]);bad=record(['verify',out/'source.mcm',out/'target.mcm',encoded,request],2);result=json.loads(bad['stdout']);assert result['status']=='INVALID'
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':2,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'assemble':assembled,'verify':bad,'storage':'Temporary mutation files removed; deterministic recipe in proof preparer.'});path.unlink();encoded.unlink()
    def semantic_result(item):
        return {key:value for key,value in json.loads(item['stdout']).items() if not key.endswith('_us')}
    for _ in range(2):assert semantic_result(record(verify))==semantic_result(first)
    d['verify_deterministic_semantics_and_work']=True
    d['status']='VERIFIED';d['preparation_seconds']=time.perf_counter()-start;d['peak_children_rss_bytes']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss;d['peak_preparer_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':case,'status':d['status'],'counts':counts,'rpa_bytes':d['rpa_bytes'],'negative_checks':len(d['negative_checks'])}),flush=True)
    return d

def prepare(a,b,h):
    f=SparseBuilder(a);fixed={};values={a['var_index'][z['variable']]:F(z['value']) for z in h['fixed_and_removed_variables']};projected={a['var_index'][z['variable']] for z in h['projected_and_removed_variables']}
    # Share every subtree nonnegativity fact, then propagate a zero sum downward.
    def zero_sum(ids,upper):
        ids=sorted(ids)
        def tree(lo,hi):
            if hi-lo==1:return ({'VarLower':ids[lo]},None)
            mid=(lo+hi)//2;left=tree(lo,mid);right=tree(mid,hi);return (f.lin('Le',[[left[0],1],[right[0],1]]),(left,right,lo,mid,hi))
        root=tree(0,len(ids))
        def descend(node,up,lo,hi):
            if hi-lo==1:
                i=ids[lo];fixed[i]=f.eqpair(up,{'VarLower':i});return
            left,right,_,mid,_=node[1]
            lup=f.lin('Le',[[up,1],[right[0],1]]);rup=f.lin('Le',[[up,1],[left[0],1]])
            descend(left,lup,lo,mid);descend(right,rup,mid,hi)
        descend(root,upper,0,len(ids))
    cap=a['rows'][a['row_index']['c212']];oversize={i for i,c in cap['terms'].items() if c==21600};assert len(oversize)==20320
    le=f.lin('Le',[[row_ref(a,'c212'),F(1,21600)]]+[[{'VarLower':i},c/F(21600)] for i,c in cap['terms'].items() if i not in oversize])
    integer=f.lin('Int',[[{'VarInt':i},1] for i in sorted(oversize)]);zero_sum(oversize,rounded(f,le,integer))
    unreachable=set(h['unreachable_rows']);pending=set(unreachable)
    while pending:
        progress=False
        for rn in sorted(pending,key=lambda n:a['row_index'][n]):
            row=a['rows'][a['row_index'][rn]];incoming=[i for i,c in row['terms'].items() if c==-1];outgoing=[i for i,c in row['terms'].items() if c==1 and i not in fixed]
            assert row['rhs']==0 and all(c in (-1,1) for c in row['terms'].values())
            if any(i not in fixed for i in incoming):continue
            if outgoing:
                terms=[[row_ref(a,rn),1]]+[[fixed[i],-c] for i,c in row['terms'].items() if i in fixed];up=f.lin('Le',terms,expression(0,{i:1 for i in outgoing}));zero_sum(outgoing,up)
            pending.remove(rn);progress=True
        assert progress,'unreachable graph induction stalled'
    for rn in ['c216','c217']:
        row=a['rows'][a['row_index'][rn]];sign=next(iter(row['terms'].values()))
        for i in row['terms']:
            lower=f.lin('Le',[[row_ref(a,rn),-sign]]+[[{'VarUpper':j},1] for j in row['terms'] if j!=i],expression(1,{i:-1}));fixed[i]=f.eqpair({'VarUpper':i},lower)
    for z in h['singleton_fix_proof']:
        row=a['rows'][a['row_index'][z['row']]];i=a['var_index'][z['variable']];c=row['terms'][i];fixed[i]=f.lin('Eq',[[row_ref(a,z['row']),1/c]]+[[fixed[j],-q/c] for j,q in row['terms'].items() if j!=i],expression(-values[i],{i:1}))
    assert set(fixed)==set(values)
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];reverse=[expression(values.get(i,0)) if i in values or i in projected else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])]
    big={a['var_index'][n] for n in h['replaced_row']['new_support']};row=a['rows'][a['row_index']['c213']]
    le=f.lin('Le',[[row_ref(a,'c213'),F(1,21600)]]+[[{'VarLower':i},c/F(21600)] for i,c in row['terms'].items() if i not in big]);inte=f.lin('Int',[[{'VarInt':i},1] for i in sorted(big)]);clique=rounded(f,le,inte)
    def forward_row(row,e,kind):
        if row['name']=='c213':ref=clique
        else:
            old=a['rows'][a['row_index'][row['name']]];terms=[[row_ref(a,row['name']),1]]+[[fixed[i],-c] for i,c in old['terms'].items() if i in fixed];ref=f.lin(kind,terms,e) if len(terms)>1 else terms[0][0]
        assert f.refexpr(ref)==e;return ref
    fc=obligations(f,b,forward,True,forward_row)
    objective=mapped(b['objective'],forward);wanted=expression(objective[0]-a['objective'][0],{i:objective[1].get(i,0)-a['objective'][1].get(i,0) for i in set(objective[1])|set(a['objective'][1])});fc.append(f.lin('Eq',[[fixed[i],c] for i,c in wanted[1].items()],wanted) if wanted[1] else 'Exact')
    projection=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];fc+=['Exact']*len(projection)
    r=SparseBuilder(b);relaxed={b['var_index'][n] for n in h['relaxed_integer_variables']};adj=defaultdict(list)
    for row in b['rows']:
        if row['sense']=='E':
            for i in row['terms']:
                if i in relaxed:adj[row['name']].append(i)
    endpoints=defaultdict(list)
    for rn,ids in adj.items():
        for i in ids:endpoints[i].append(rn)
    # Missing component roots are boundary endpoints. Peel leaves, exporting
    # single-coordinate Int facts instead of quadratic expanded signed cuts.
    intrefs={};degree={rn:len(ids) for rn,ids in adj.items()};queue=deque(rn for rn,d in degree.items() if d==1)
    while queue:
        rn=queue.popleft();unknown=[i for i in adj[rn] if i not in intrefs]
        if len(unknown)!=1:continue
        i=unknown[0];row=b['rows'][b['row_index'][rn]];pivot=row['terms'][i];assert pivot in (-1,1)
        terms=[[row_ref(b,rn),1/pivot]]+[[intrefs[j] if j in relaxed else {'VarInt':j},-c/pivot] for j,c in row['terms'].items() if j!=i]
        intrefs[i]=r.lin('Int',terms,expression(0,{i:1}),constant=row['rhs']/pivot)
        for other in endpoints[i]:
            degree[other]-=1
            if degree[other]==1:queue.append(other)
    assert set(intrefs)==relaxed,(len(intrefs),len(relaxed))
    recovered={}
    # The relaxed-tree incidence also identifies each entire surviving component.
    for z in h['flow_component_certificates']:
        root=z['omitted_row'];source_row=a['rows'][a['row_index'][root]];seeds={b['var_index'][a['vars'][i]['name']] for i in source_row['terms'] if a['vars'][i]['name'] in b['var_index']};nodes=set();todo=list(seeds);seen=set()
        while todo:
            i=todo.pop()
            if i in seen:continue
            seen.add(i)
            for rn in endpoints[i]:
                if rn not in nodes:nodes.add(rn);todo.extend(adj[rn])
        assert len(nodes)==z['row_count']-1,(root,len(nodes),z)
        wanted=mapped(row_fact(source_row,'RowEq'),reverse);recovered[root]=r.lin('Eq',[[row_ref(b,rn),-1] for rn in sorted(nodes,key=lambda n:b['row_index'][n])],wanted)
    assignment={}
    for row in b['rows']:
        if row['sense']=='L' and row['rhs']==1 and row['name']!='c213' and int(row['name'][1:])<=100:
            for i in row['terms']:assert i not in assignment;assignment[i]=row['name']
    def weighted_bound(e):
        groups=defaultdict(dict)
        for i,c in e[1].items():assert c>0;groups[assignment[i]][i]=c
        terms=[];total=0
        for rn,coeffs in groups.items():
            row=b['rows'][b['row_index'][rn]];mx=max(coeffs.values());total+=mx;terms.append([row_ref(b,rn),mx])
            terms.extend([{'VarLower':i},mx-coeffs.get(i,0)] for i in row['terms'] if mx!=coeffs.get(i,0))
        assert total<=-e[0],(total,e[0]);return r.lin('Le',terms,e,constant=e[0]+total)
    def reverse_row(row,e,kind):
        rn=row['name']
        if rn in b['row_index'] and rn!='c213':ref=row_ref(b,rn);assert r.refexpr(ref)==e;return ref
        if rn in recovered:return recovered[rn]
        if rn=='c213':
            new=row_ref(b,rn);high={i:c for i,c in e[1].items() if c==21600};small={i:c for i,c in e[1].items() if c!=21600};smallfact=weighted_bound(expression(-864,small));return r.lin('Le',[[new,21600],[smallfact,1]],e,constant=e[0]+22464)
        if kind=='Le' and row['sense']=='G':return r.lin('Le',[[{'VarLower':i},-c] for i,c in e[1].items()],e,constant=e[0])
        assert kind=='Le';return weighted_bound(e)
    rc=obligations(r,a,reverse,True,reverse_row,intrefs);assert mapped(a['objective'],reverse)==b['objective'];rc.append('Exact');rc+=['Exact']*len(projection)
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':None},{'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in projection],'inverse':None}]
    cert={'claims':claims,'blocks':[{'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':fc}}},{'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':rc}}}]}
    return cert,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'capacity_zero_arcs':len(oversize),'all_fixed_arcs':len(fixed),'tree_integer_facts':len(intrefs),'claims':2,'steps_by_claim':[len(f.steps),len(r.steps)],'obligations_by_claim':[len(fc),len(rc)]}

def pop_mutation(obj):
    old=obj.pop();return lambda:obj.append(old)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test31-nomf-B1');out=Path('cases/test31').resolve();h=json.loads((run/'output/changes.json').read_text())
    a=parse_mps(StreamingPath(run/'input/model.mps'));b=parse_mps(StreamingPath(run/'output/reformulated.mps'));print('parsed test31',flush=True);cert,counts=prepare(a,b,h);del a,b;print('prepared test31',counts,flush=True)
    mutations=[('missing_capacity_nonnegativity','Drops a cancellation needed for the oversize sum capacity bound.',lambda:pop_mutation(cert['blocks'][0]['steps'][0]['Lin']['terms'])),('missing_tree_integer_term','Drops an integer premise of a relaxed tree-flow reconstruction.',lambda:pop_mutation(next(s['Lin']['terms'] for s in cert['blocks'][1]['steps'] if 'Lin' in s and s['Lin']['kind']=='Int' and len(s['Lin']['terms'])>1))),('missing_projection_coordinate','Drops a requested retained-coordinate equality.',lambda:pop_mutation(cert['blocks'][0]['end']['Return']['checks']))]
    run_receipt('test31',cert,counts,run,out,args.kernel.resolve(),run/'output/changes.json','Exact equality of the retained integer feasible projection and every objective value, in both directions. All 13,984 relaxed tree-flow coordinates reconstructed integer by shared leaf cut facts; 29,541 forced zeros and 18 forced ones restored. The 141 zero-cost projected auxiliaries have a canonical zero lift; their original values are not claimed uniquely forced. No LP equivalence or full auxiliary bijection asserted.',mutations,start)
if __name__=='__main__':main()