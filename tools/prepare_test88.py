#!/usr/bin/env python3
"""Exact, untrusted preparation of actual test88 mixed-integer alias proof.

Local case splits use only source binary bounds/integrality, original definitions,
and original inequalities. No product theorem or unchecked side-audit PASS enters
the kernel. The original LP-equivalence claim is deliberately not made.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import subprocess
import time
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha

class Builder:
    def __init__(self,model,counter=None,facts=None,assumptions=None):
        self.model=model;self.counter=counter if counter is not None else [0]
        self.facts={} if facts is None else facts.copy();self.assumptions=[] if assumptions is None else assumptions[:];self.steps=[]
    def alloc(self):
        i=self.counter[0];self.counter[0]+=1;return i
    def refexpr(self,r):
        typ,i=next(iter(r.items()))
        if typ=='Local':return self.facts[i][1]
        if typ=='Assumption':return self.assumptions[i]
        return get_fact(self.model,r,{})
    def kind(self,r):
        typ,i=next(iter(r.items()))
        if typ=='Local':return self.facts[i][0]
        if typ=='RowEq':return 'Eq'
        if typ=='VarInt':return 'Int'
        return 'Le'
    def lin(self,kind,terms,expected=None,constant=0):
        e=expression(constant)
        assert (kind=='Eq' and constant==0) or (kind=='Le' and constant<=0) or (kind=='Int' and F(constant).denominator==1)
        for r,c in terms:
            k=self.kind(r)
            assert k=='Eq' or (kind=='Le' and k=='Le' and c>=0) or (kind=='Int' and k=='Int' and F(c).denominator==1)
            e=plus(e,self.refexpr(r),c)
        if expected is not None:assert e==expected,('bad lin',e,expected)
        i=self.alloc();self.steps.append({'Lin':{'id':i,'kind':kind,'constant':str(constant),'terms':[[r,str(c)] for r,c in terms]}});self.facts[i]=(kind,e);return {'Local':i}
    def eqpair(self,positive,negative):
        assert self.kind(positive)==self.kind(negative)=='Le';e=self.refexpr(positive);assert mul(e,-1)==self.refexpr(negative)
        i=self.alloc();self.steps.append({'EqPair':{'id':i,'positive':positive,'negative':negative}});self.facts[i]=('Eq',e);return {'Local':i}
    def cases(self,desired,var,left,right):
        split=expression(0,{var:1});i=self.alloc();branches=[]
        for which,callback in enumerate((left,right)):
            assumption=split if which==0 else expression(1,{var:-1})
            child=Builder(self.model,self.counter,self.facts,self.assumptions+[assumption]);end=callback(child,{'Assumption':len(self.assumptions)})
            if 'Witness' in end:assert child.refexpr(end['Witness'])==desired and child.kind(end['Witness'])=='Eq'
            else:
                e=child.refexpr(end['Absurd']);assert not e[1] and child.kind(end['Absurd'])=='Le' and e[0]>0
            branches.append({'steps':child.steps,'end':end})
        self.steps.append({'Cases':{'id':i,'kind':'Eq','expression':expr_json(desired),'split':expr_json(split),'integer':{'VarInt':var},'left':branches[0],'right':branches[1]}});self.facts[i]=('Eq',desired);return {'Local':i}


def definitions(model,audit):
    result={}
    for group in audit['equality_classes']:
        binary={model['var_index'][v]:F(c) for v,c in group['binary_expression'].items()}
        for v in group['members']:
            i=model['var_index'][v];ri=model['row_index'][group['definition_rows'][v]];r=model['rows'][ri]
            expected=expression(0,{i:1});expected=plus(expected,expression(0,binary),-1)
            assert r['sense']=='E' and row_fact(r,'RowEq')==expected
            result[i]={'row':ri,'binary':binary}
    return result


def fix_binary(builder,var,value,assumption):
    v=builder.model['vars'][var];assert v['integer'] and v['lower']==0 and v['upper']==1
    if value==0:return builder.eqpair(assumption,{'VarLower':var})
    return builder.eqpair({'VarUpper':var},assumption)


def fixed_definition(builder,var,assigned,definitions,cache):
    if var in cache:return cache[var]
    d=definitions[var];value=sum(c*assigned[i][0] for i,c in d['binary'].items())
    terms=[[{'RowEq':d['row']},F(1)]]+[[assigned[i][1],c] for i,c in d['binary'].items()]
    ref=builder.lin('Eq',terms,expression(-value,{var:1}));cache[var]=(value,ref);return value,ref


def product_bound(builder,var,sign,value,block_rows,assigned,defs,cache):
    wanted=expression(-sign*value,{var:sign});m=builder.model
    direct={'VarUpper':var} if sign==1 else {'VarLower':var}
    if builder.refexpr(direct)==wanted:return direct
    for name in block_rows:
        ref=row_ref(m,name);e=builder.refexpr(ref)
        if e[1].get(var)!=sign:continue
        remaining={i:c for i,c in e[1].items() if i!=var}
        if not all(i in defs and set(defs[i]['binary'])<=set(assigned) for i in remaining):continue
        reduced=expression(e[0]+sum(c*sum(q*assigned[j][0] for j,q in defs[i]['binary'].items()) for i,c in remaining.items()),{var:sign})
        if reduced!=wanted:continue
        terms=[[ref,F(1)]]
        for i,c in remaining.items():
            _,fixed=fixed_definition(builder,i,assigned,defs,cache);terms.append([fixed,-c])
        return builder.lin('Le',terms,wanted)
    raise AssertionError(('no exact product bound',m['vars'][var]['name'],sign,value,assigned))


def product_alias(builder,removed,representative,group,audit,defs):
    m=builder.model;desired=expression(0,{removed:1,representative:-1})
    factors=group['signed_factors'];pairs=[[m['var_index'][audit['binary_pairs'][s][key]] for key in ['positive','negative']] for s in factors]
    magnitudes=[m['var_index'][audit['signed_magnitude_map'][s]] for s in factors]
    assert len(set(i for pair in pairs for i in pair))==6
    names=[m['vars'][i]['name'] for i in [removed,representative]]
    def leaf(b,assigned,value):
        cache={};bounds=[]
        for var,name in zip([removed,representative],names):
            rr=group['original_block_rows'][name]
            upper=product_bound(b,var,1,value,rr,assigned,defs,cache)
            lower=product_bound(b,var,-1,value,rr,assigned,defs,cache)
            bounds.append((upper,lower))
        positive=b.lin('Le',[[bounds[0][0],F(1)],[bounds[1][1],F(1)]],desired)
        negative=b.lin('Le',[[bounds[0][1],F(1)],[bounds[1][0],F(1)]],mul(desired,-1))
        return {'Witness':b.eqpair(positive,negative)}
    def recurse(b,index,assigned,product):
        if index==3:return leaf(b,assigned,product)
        p,n=pairs[index]
        def pbranch(bp,ap,pv):
            pr=fix_binary(bp,p,pv,ap);statep={**assigned,p:(F(pv),pr)}
            def nbranch(bn,an,nv):
                nr=fix_binary(bn,n,nv,an);state={**statep,n:(F(nv),nr)}
                if pv==nv==1:
                    magnitude=magnitudes[index];val,eq=fixed_definition(bn,magnitude,state,defs,{})
                    assert val==2
                    contradiction=bn.lin('Le',[[{'VarUpper':magnitude},F(1)],[eq,F(-1)]],expression(1))
                    return {'Absurd':contradiction}
                if pv==nv==0:return leaf(bn,state,F(0))
                return recurse(bn,index+1,state,product*(pv-nv))
            result=bp.cases(desired,n,lambda bn,an:nbranch(bn,an,0),lambda bn,an:nbranch(bn,an,1))
            return {'Witness':result}
        result=b.cases(desired,p,lambda bp,ap:pbranch(bp,ap,0),lambda bp,ap:pbranch(bp,ap,1))
        return {'Witness':result}
    return recurse(builder,0,{},F(1))['Witness']


def prepare(source,target,audit):
    a=parse_mps(source);b=parse_mps(target);aliases=audit['variable_aliases'];defs=definitions(a,audit)
    assert len(a['vars'])==784 and len(b['vars'])==432 and len(a['rows'])==5998 and len(b['rows'])==2298
    assert set(aliases)==set(a['var_index'])-set(b['var_index'])
    assert all(v in b['var_index'] for v in aliases.values())
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[expression(0,{b['var_index'][aliases.get(v['name'],v['name'])]:1}) for v in a['vars']]
    f=Builder(a);aliasrefs={}
    for removed,rep in aliases.items():
        i,j=a['var_index'][removed],a['var_index'][rep]
        assert a['vars'][i]['lower']==a['vars'][j]['lower'] and a['vars'][i]['upper']==a['vars'][j]['upper'] and not a['vars'][i]['integer']
        if i in defs:
            assert defs[i]['binary']==defs[j]['binary']
            aliasrefs[i]=f.lin('Eq',[[{'RowEq':defs[i]['row']},F(1)],[{'RowEq':defs[j]['row']},F(-1)]],expression(0,{i:1,j:-1}))
    assert len(aliasrefs)==96
    for group in audit['product_classes']:
        rep=group['representative'];j=a['var_index'][rep]
        for removed in group['members']:
            if removed==rep:continue
            i=a['var_index'][removed];assert aliases[removed]==rep
            aliasrefs[i]=product_alias(f,i,j,group,audit,defs)
    assert len(aliasrefs)==352
    fchecks=[]
    for v in b['vars']:
        i=a['var_index'][v['name']];assert v==a['vars'][i]
        if v['lower'] is not None:fchecks.append({'VarLower':i})
        if v['upper'] is not None:fchecks.append({'VarUpper':i})
        if v['integer']:fchecks.append('Exact')
    for row in b['rows']:
        ref=row_ref(a,row['name']);e=f.refexpr(ref);terms=[[ref,F(1)]]
        for i,c in list(e[1].items()):
            if i in aliasrefs:terms.append([aliasrefs[i],-c])
        expected=substitute(row_fact(row,next(iter(row_ref(b,row['name'])))),forward)
        if len(terms)==1:assert e==expected;fchecks.append(ref)
        else:fchecks.append(f.lin('Eq' if row['sense']=='E' else 'Le',terms,expected))
    assert substitute(b['objective'],forward)==a['objective'];fchecks.append('Exact')
    fchecks+=['Exact']*len(b['vars'])
    for i,back in enumerate(reverse):
        e=plus(substitute(back,forward),expression(0,{i:1}),-1)
        if not e[1] and not e[0]:fchecks.append('Exact')
        else:fchecks.append(f.lin('Eq',[[aliasrefs[i],F(-1)]],e))
    # Reverse lifting is an exact identity after copying every alias.
    r=Builder(b);rchecks=[]
    for v in a['vars']:
        i=b['var_index'][aliases.get(v['name'],v['name'])];w=b['vars'][i]
        assert all(v[k]==w[k] for k in ['lower','upper','integer'])
        if v['lower'] is not None:rchecks.append({'VarLower':i})
        if v['upper'] is not None:rchecks.append({'VarUpper':i})
        if v['integer']:rchecks.append('Exact')
    for row in a['rows']:
        n=audit['removed_rows_same_after_substitution'].get(row['name'],row['name']);ref=row_ref(b,n)
        expected=substitute(row_fact(row,next(iter(row_ref(a,row['name'])))),reverse)
        assert expected==r.refexpr(ref),(row['name'],n)
        rchecks.append(ref)
    assert substitute(a['objective'],reverse)==b['objective'];rchecks.append('Exact')
    rchecks+=['Exact']*len(b['vars']);rchecks+=['Exact']*len(b['vars'])
    claims=[]
    for direction,inp,out in [(False,a,b),(True,b,a)]:
        claims.append({'reverse':direction,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[inp['var_index'][v['name']],out['var_index'][v['name']]] for v in b['vars']],'inverse':0 if direction else 1})
    cert={'claims':claims,'blocks':[{'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':fchecks}}},{'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':rchecks}}}]}
    return cert,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':2,'global_alias_equalities':len(aliasrefs),'all_allocated_fact_ids':f.counter[0],'obligations_by_claim':[len(fchecks),len(rchecks)]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test88-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test88'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/model_reformulated.mps';audit_path=run/'output/audit.json';audit=json.loads(audit_path.read_text())
    cert,counts=prepare(source,target,audit);rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n')
    metadata={'case_id':'test88','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit_path),'sha256':sha(audit_path)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Objective-preserving bijection of mixed-integer feasible sets, all retained coordinates and both inverse identities. Product aliases use exact local binary cases; LP equivalence is not requested.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        kernel=args.kernel.resolve();metadata['kernel_binary_sha256']=sha(kernel)
        for command in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(kernel)]+command,capture_output=True,text=True);metadata['kernel_runs'].append({'command':[str(kernel)]+command,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                metadata['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        result=json.loads(metadata['kernel_runs'][-1]['stdout']);assert result['status']=='VERIFIED';metadata['status']='VERIFIED';metadata['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
    if args.kernel:
        import copy
        negative=[]
        first_case=next(i for i,step in enumerate(cert['blocks'][0]['steps']) if 'Cases' in step)
        continuous=next(i for i,v in enumerate(parse_mps(source)['vars']) if not v['integer'])
        for name,reason in [('continuous_split','Integer case splitting cites a continuous variable as its INT witness.'),('changed_conclusion','A Cases conclusion differs from its checked child witnesses.')]:
            bad=copy.deepcopy(cert);step=bad['blocks'][0]['steps'][first_case]['Cases']
            if name=='continuous_split':step['integer']={'VarInt':continuous}
            else:step['expression']['terms'][0][1]='2'
            bad_rpa=out/(name+'.rpa');bad_rpx=out/(name+'.rpx')
            bad_rpa.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n')
            assembled=subprocess.run([str(kernel),'assemble',str(bad_rpa),str(bad_rpx)],capture_output=True,text=True);assert assembled.returncode==0,assembled.stdout
            checked=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(bad_rpx),str(request)],capture_output=True,text=True)
            result=json.loads(checked.stdout);assert checked.returncode!=0 and result['status']=='INVALID',(name,checked.stdout)
            negative.append({'mutation':name,'rule_broken':reason,'exit_code':checked.returncode,'result':result,'rpa_sha256':sha(bad_rpa),'rpx_sha256':sha(bad_rpx)})
        metadata['negative_checks']=negative
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({k:metadata[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))

if __name__=='__main__':main()
