#!/usr/bin/env python3
"""Actual test24 dominance normalization with balanced local priority proofs."""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test23 import extend
from prepare_test54 import box, exact


def split(p, kind, wanted, e, integer, callbacks):
    ident=p.alloc(); branches=[]
    for side, callback in enumerate(callbacks):
        guard=e if side==0 else plus(expression(1),e,-1)
        child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[guard]);child.facts=ChainMap({},p.facts)
        ref=callback(child,{'Assumption':len(p.assumptions)})
        assert child.kind(ref)==kind and child.refexpr(ref)==wanted
        branches.append({'steps':child.steps,'end':{'Witness':ref}})
    p.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),'split':expr_json(e),'integer':integer,'left':branches[0],'right':branches[1]}})
    p.facts[ident]=(kind,wanted);return {'Local':ident}


def isum(p, ids):
    return p.lin('Int',[[{'VarInt':i},1] for i in ids],expression(0,{i:1 for i in ids}))


def positive_zero(p, z, ids, upper, positive):
    """A positive binary sum contains an active member; balanced local Cases."""
    wanted=expression(0,{z:1})
    if len(ids)==1:return p.lin('Le',[[upper[ids[0]],1],[positive,1]],wanted)
    cut=len(ids)//2;left,right=ids[:cut],ids[cut:];e=expression(0,{i:1 for i in left});integer=isum(p,left)
    def zero(c,r):
        pos=c.lin('Le',[[positive,1],[r,1]],expression(1,{i:-1 for i in right}))
        return positive_zero(c,z,right,upper,pos)
    return split(p,'Le',wanted,e,integer,[zero,lambda c,r:positive_zero(c,z,left,upper,r)])


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(10100,10180,2407,2487)
    covers=[a['rows'][a['row_index'][d['row']]] for d in h['row_sense_changes']]
    used=set(); intervals=[];records=[];pre=SparseBuilder(a)
    for row in covers:
        ids=sorted(row['terms']);assert row['sense']=='G' and row['rhs']==1 and all(c==1 for c in row['terms'].values()) and not used.intersection(ids);used.update(ids)
        assert 15<=len(ids)<=40
        # The first prefix is affine (1-x). Interior prefixes use one simultaneous
        # interval lift. The final prefix is zero by the actual cover inequality.
        rec={'row':row['name'],'ids':ids,'prefix':[expression(1)]}
        for k in range(1,len(ids)):
            if k==1:rec['prefix'].append(expression(1,{ids[0]:-1}));continue
            lower=[expression(),expression(1,{i:-1 for i in ids[:k]})];upper=[expression(1,{i:-1}) for i in ids[:k]];checks=[]
            for lo in lower:
                for hi in upper:checks.append(box(pre,plus(lo,hi,-1),True))
            rec['prefix'].append(len(intervals));intervals.append({'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':checks})
        rec['prefix'].append(expression());records.append(rec)
    assert len(used)==2307
    ext,layout=extend(a,intervals);p=SparseBuilder(ext,pre.counter,pre.facts);mapping={};dominance={};domains={};cover_eq={}
    for rec in records:
        ids=rec['ids'];prefix=rec['prefix'];meta={}
        for k in range(1,len(ids)):
            if k==1:continue
            ll=layout[prefix[k]];z=ll['variable'];prefix[k]=expression(0,{z:1})
            low={'RowLower':ll['lower'][0]};sumlow={'RowLower':ll['lower'][1]};upper={i:{'RowUpper':j} for i,j in zip(ids[:k],ll['upper'])}
            hi=p.lin('Le',[[upper[ids[0]],1],[{'VarLower':ids[0]},1]],expression(-1,{z:1}))
            e=expression(0,{i:1 for i in ids[:k]});integer=isum(p,ids[:k])
            def zero(c,r,z=z,sumlow=sumlow,hi=hi):
                lowone=c.lin('Le',[[sumlow,1],[r,1]],expression(1,{z:-1}))
                eq=c.eqpair(hi,lowone);return c.lin('Int',[[eq,1]],expression(0,{z:1}),1)
            def active(c,r,z=z,ids=ids[:k],upper=upper,low=low):
                eq=c.eqpair(positive_zero(c,z,ids,upper,r),low);return c.lin('Int',[[eq,1]],expression(0,{z:1}))
            integerz=split(p,'Int',prefix[k],e,integer,[zero,active]);meta[k]=(low,sumlow,upper,hi,integerz)
        # Each priority difference is integer, nonnegative and <= its original x.
        # A split on the preceding prefix sum has only balanced local subcases.
        for k,x in enumerate(ids,1):
            prev,cur=prefix[k-1],prefix[k];new=plus(prev,cur,-1);mapping[x]=new
            if k==1:
                assert new==expression(0,{x:1});domains[x]=({'VarLower':x},{'VarUpper':x},{'VarInt':x});dominance[x]=p.lin('Le',[],expression());continue
            previous_ids=ids[:k-1];sumexpr=expression(0,{i:1 for i in previous_ids});integer=isum(p,previous_ids)
            def branch_eq(c,r,side):
                # Return new=x when all previous choices vanish; otherwise new=0.
                if side==0:
                    if k-1==1:
                        preveq=c.eqpair(r,{'VarLower':previous_ids[0]});prevone=c.lin('Eq',[[preveq,-1]],plus(prev,expression(-1)))
                    else:
                        low,sl,up,hi,iz=meta[k-1];prevone=c.eqpair(hi,c.lin('Le',[[sl,1],[r,1]],plus(expression(1),prev,-1)))
                    if k==len(ids):
                        # With all previous x zero the cover forces the last x=1.
                        lowone=c.lin('Le',[[row_ref(a,rec['row']),1],[r,1]],expression(1,{x:-1}));xeq=c.eqpair({'VarUpper':x},lowone)
                        return c.lin('Eq',[[prevone,1],[xeq,-1]],plus(new,expression(0,{x:1}),-1))
                    low,sl,up,hi,iz=meta[k];z=next(iter(cur[1]));lowone=c.lin('Le',[[sl,1],[r,1]],plus(plus(expression(1),expression(0,{x:1}),-1),cur,-1));eqcur=c.eqpair(up[x],lowone)
                    return c.lin('Eq',[[prevone,1],[eqcur,-1]],plus(new,expression(0,{x:1}),-1))
                if k-1==1:
                    preveq=c.eqpair({'VarUpper':previous_ids[0]},r);peq=c.lin('Eq',[[preveq,-1]],prev)
                else:
                    low,sl,up,hi,iz=meta[k-1];peq=c.eqpair(positive_zero(c,next(iter(prev[1])),previous_ids,up,r),low)
                if not cur[1]:return peq
                low,sl,up,hi,iz=meta[k];ceq=c.eqpair(positive_zero(c,next(iter(cur[1])),previous_ids,up,r),low)
                return c.lin('Eq',[[peq,1],[ceq,-1]],new)
            def proof(kind,wanted):
                def callback(c,r,side):
                    eq=branch_eq(c,r,side)
                    if kind=='Int':return c.lin('Int',[[eq,1]]+([[{'VarInt':x},1]] if side==0 else []),wanted)
                    terms=[[eq,-1 if wanted==mul(new,-1) else 1]]
                    if wanted==mul(new,-1):
                        if side==0:terms.append([{'VarLower':x},1])
                    elif side==1:terms.append([{'VarLower':x},1])
                    return c.lin('Le',terms,wanted)
                return split(p,kind,wanted,sumexpr,integer,[lambda c,r:callback(c,r,0),lambda c,r:callback(c,r,1)])
            lower=proof('Le',mul(new,-1));dom=proof('Le',plus(new,expression(0,{x:1}),-1));integ=proof('Int',new);upper=p.lin('Le',[[dom,1],[{'VarUpper':x},1]],plus(new,expression(-1)))
            domains[x]=(lower,upper,integ);dominance[x]=dom
        total=expression()
        for x in ids:total=plus(total,mapping[x])
        assert total==expression(1);cover_eq[rec['row']]='Exact'
    retained=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];yprojection=[];fmap=[];checks=[]
    for i,j in retained:
        assert a['vars'][i]==b['vars'][j]
        if i in mapping:fmap.append(mapping[i]);checks.extend(domains[i])
        else:
            assert a['vars'][i]['upper']==13;fmap.append(expression(0,{i:1}));checks.extend([{'VarLower':i},{'VarUpper':i},{'VarInt':i}]);yprojection.append([i,j])
    for row in b['rows']:
        typ=next(iter(row_ref(b,row['name'])));wanted=substitute(row_fact(row,typ),fmap)
        if row['name'] in cover_eq:assert exact('Eq',wanted);checks.append('Exact')
        else:
            old=row_ref(a,row['name']);terms=[[old,1]]
            for j,c in row['terms'].items():
                i=retained[j][0]
                if i in mapping:assert c>0;terms.append([dominance[i],c])
            checks.append(p.lin('Eq' if typ=='RowEq' else 'Le',terms,wanted))
    objective=plus(substitute(b['objective'],fmap),a['objective'],-1);terms=[]
    for i,c in a['objective'][1].items():
        assert c>=0
        terms.append([dominance[i] if i in mapping else {'VarLower':i},c])
    checks.append(p.lin('Le',terms,objective));checks+=['Exact']*len(yprojection)
    forward={'steps':pre.steps,'end':{'IntervalLift':{'intervals':intervals,'body':{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in fmap],'checks':checks}}}}}}
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':yprojection,'inverse':None}
    r=SparseBuilder(b);reverse=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']];rc=[]
    for i,v in enumerate(a['vars']):
        e=reverse[i]
        if not e[1]:rc+=['Exact']*3
        else:j=next(iter(e[1]));rc.extend([{'VarLower':j},{'VarUpper':j},{'VarInt':j}])
    removed={d['removed_link_row']:d for d in h['removed_variables']}
    for row in a['rows']:
        typ=next(iter(row_ref(a,row['name'])));wanted=substitute(row_fact(row,typ),reverse)
        if row['name'] in removed:rc.append({'VarLower':b['var_index'][removed[row['name']]['linked_variable']]})
        elif row['name'] in cover_eq:rc.append(r.lin('Le',[[row_ref(b,row['name']),-1]],wanted))
        else:ref=row_ref(b,row['name']);assert r.refexpr(ref)==wanted;rc.append(ref)
    assert substitute(a['objective'],reverse)==b['objective'];rc+=['Exact']*(1+len(yprojection))
    backward={'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':rc}}}
    reverseclaim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in yprojection],'inverse':None}
    return {'claims':[claim,reverseclaim],'blocks':[forward,backward]}, {'source_variables':10100,'target_variables':2407,'source_rows':10180,'target_rows':2487,'disjoint_covers':79,'priority_intervals':len(intervals),'removed_binaries':7693,'retained_y_observations':100,'forward_steps':len(p.steps),'claims':2}


def execute(case, source, target, audit, out, kernel, cert, counts, contract, version, mutations, start, preparer):
    out.mkdir(parents=True,exist_ok=True);rpa=out/'proof.rpa';request=out/'request.json'
    def save(path,obj):path.write_text('RPA '+str(version)+'\n'+json.dumps(obj,separators=(',',':'))+'\n')
    save(rpa,cert);request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(preparer),'sha256':sha(preparer)},'claims':contract,'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(kernel),'kernel_runs':[],'negative_checks':[]}
    receipt=out/'preparation.json'
    def run(args):
        cmd=[str(kernel)]+[str(x) for x in args];p=subprocess.run(cmd,capture_output=True,text=True);record={'command':cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(record);return p,record
    def good(args):
        p,_=run(args)
        if p.returncode:
            d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';receipt.write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(p.stdout+p.stderr)
        return p
    good(['canonical',source,out/'source.mcm']);good(['canonical',target,out/'target.mcm']);good(['assemble',rpa,out/'proof.rpx'])
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request];good(verify)
    repeat=out/'deterministic.rpx';good(['assemble',rpa,repeat]);assert sha(repeat)==sha(out/'proof.rpx');repeat.unlink();d['assemble_byte_deterministic']=True
    for name,reason,mutate in mutations:
        undo=mutate(cert);path=out/(name+'.rpa');save(path,cert);undo();encoded=out/(name+'.rpx')
        assembled,ar=run(['assemble',path,encoded]);assert assembled.returncode==0,assembled.stdout+assembled.stderr
        p,vr=run(['verify',out/'source.mcm',out/'target.mcm',encoded,request]);result=json.loads(p.stdout);assert p.returncode==2 and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'kernel_runs':[ar,vr],'storage':'Mutated files deleted; deterministic recipe in preparer.'});path.unlink();encoded.unlink()
    first=good(verify);second=good(verify)
    semantic=lambda p:{k:v for k,v in json.loads(p.stdout).items() if not k.endswith('_us')}
    assert semantic(first)==semantic(second) and semantic(first)['status']=='VERIFIED'
    d['verify_deterministic']=True;d['verify_determinism_scope']='Status, counts and exact execution statistics; wall-clock timing fields excluded.'
    d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['preparation_seconds']=time.perf_counter()-start;receipt.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':case,'status':d['status'],'counts':counts,'negative_checks':len(d['negative_checks']),'artifacts':d['artifacts']}))


def popmut(getter):
    def mutate(cert):
        obj=getter(cert);old=obj.pop();return lambda:obj.append(old)
    return mutate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test24-nomf-B1');source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    inventory=next(c for c in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if c['case_id']=='test24');assert sha(source)==inventory['source_models'][0]['sha256'] and sha(target)==inventory['final_target_models'][0]['sha256']
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    mutations=[('missing_prefix_bound','Omits the old binary bound proving a prefix interval is inhabited.',popmut(lambda c:c['blocks'][0]['steps'][0]['Lin']['terms'])),('missing_y_observation','Omits a requested retained y observation.',popmut(lambda c:c['blocks'][1]['end']['Return']['checks'])),('missing_removed_link','Omits an original removed linking row obligation.',popmut(lambda c:c['blocks'][1]['end']['Return']['checks']))]
    # Distinct semantic mutation: reverse zero extension is changed to one.
    def wrongzero(c):
        arr=c['blocks'][1]['end']['Return']['map'];i=next(i for i,e in enumerate(arr) if not e['terms']);old=arr[i];arr[i]=expr_json(expression(1));return lambda:arr.__setitem__(i,old)
    mutations[-1]=('wrong_removed_binary_completion','Sets a deleted binary to one rather than zero, violating original linking and objective obligations.',wrongzero)
    execute('test24',source,target,audit,Path('cases/test24').resolve(),args.kernel.resolve(),cert,counts,'Preserve integer feasibility status, minimum objective and every retained y choice: forward NonIncreasing dominance normalization, reverse Equal zero extension. No bijection or preservation of every original objective level; no full LP equality claim. All domains, rows, full objective and 100 retained y observations are checked.',5,mutations,start,Path(__file__).resolve())

if __name__=='__main__':main()
