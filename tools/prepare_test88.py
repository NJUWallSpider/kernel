#!/usr/bin/env python3
"""Native test88 mixed-integer alias proof with exact local binary cases.

Every rule runs on the native proof scopes.  The legacy ``Builder`` class and
``fix_binary`` remain exported until their remaining preparers migrate; this
module's own ``prepare`` and ``main`` no longer emit RPA or run the kernel.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import time
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_native import compile_case,make_proof

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
            result=bp.cases('Eq',desired,expression(0,{n:1}),integer={'VarInt':n},
                            left=lambda bn,an:nbranch(bn,an,0),right=lambda bn,an:nbranch(bn,an,1))
            return {'Witness':result}
        result=b.cases('Eq',desired,expression(0,{p:1}),integer={'VarInt':p},
                       left=lambda bp,ap:pbranch(bp,ap,0),right=lambda bp,ap:pbranch(bp,ap,1))
        return {'Witness':result}
    return recurse(builder,0,{},F(1))['Witness']


def prepare(source,target,audit):
    a=parse_mps(source);b=parse_mps(target);aliases=audit['variable_aliases'];defs=definitions(a,audit)
    assert len(a['vars'])==784 and len(b['vars'])==432 and len(a['rows'])==5998 and len(b['rows'])==2298
    assert set(aliases)==set(a['var_index'])-set(b['var_index'])
    assert all(v in b['var_index'] for v in aliases.values())
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[expression(0,{b['var_index'][aliases.get(v['name'],v['name'])]:1}) for v in a['vars']]
    proof,f,r=make_proof(a,b);aliasrefs={}
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
        ref=row_ref(a,row['name']);e=f.refexpr(ref);typ=next(iter(row_ref(b,row['name'])));terms=[[ref,F(1)]]
        for i,c in list(e[1].items()):
            if i in aliasrefs:terms.append([aliasrefs[i],-c])
        expected=substitute(row_fact(row,typ),forward)
        if len(terms)==1:assert e==expected;fchecks.append(ref)
        else:fchecks.append(f.lin('Eq' if typ=='RowEq' else 'Le',terms,expected))
    assert substitute(b['objective'],forward)==a['objective'];fchecks.append('Exact')
    f.finish(forward,fchecks)
    rchecks=[]
    for v in a['vars']:
        i=b['var_index'][aliases.get(v['name'],v['name'])];w=b['vars'][i]
        assert all(v[k]==w[k] for k in ['lower','upper','integer'])
        if v['lower'] is not None:rchecks.append({'VarLower':i})
        if v['upper'] is not None:rchecks.append({'VarUpper':i})
        if v['integer']:rchecks.append('Exact')
    for row in a['rows']:
        n=audit['removed_rows_same_after_substitution'].get(row['name'],row['name']);ref=row_ref(b,n)
        typ=next(iter(row_ref(a,row['name'])))
        expected=substitute(row_fact(row,typ),reverse)
        assert expected==r.refexpr(ref),(row['name'],n)
        rchecks.append(ref)
    assert substitute(a['objective'],reverse)==b['objective'];rchecks.append('Exact')
    r.finish(reverse,rchecks)
    return proof,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':2,'global_alias_equalities':len(aliasrefs),'all_allocated_fact_ids':f.counter[0],'obligations_by_direction':[len(fchecks),len(rchecks)]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test88-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test88'));ap.add_argument('--kernel',type=Path,help='accepted for old invocations; native compilation is in-process');args=ap.parse_args()
    started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/model_reformulated.mps';audit_path=run/'output/audit.json'
    proof,counts=prepare(source,target,json.loads(audit_path.read_text()))
    record=compile_case(proof,out,case_id='test88',source=source,target=target,
                         metadata={'audit':{'path':str(audit_path),'sha256':sha(audit_path)},
                                   'claims':'Native MI-OPT directions: objective-preserving mixed-integer correspondence with all retained coordinates and exact local binary cases for product aliases.',
                                   'counts':counts,
                                   'preparation_seconds':time.perf_counter()-started})
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'case_id':'test88','status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':counts,'obligations':record['verification']['statistics']['obligations'],'preparation_seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
