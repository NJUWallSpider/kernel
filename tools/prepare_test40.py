#!/usr/bin/env python3
"""Native test40 affine-complement proof with two MI-OPT directions.

Exact Python fractions read the actual MPS coefficients, then every rule and
obligation runs through ``kernel_compiler``.  The reverse map restores each
removed complement coordinate as ``1 - x``; the legacy LP/point claims are not
part of native MI optimization equivalence.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
from fractions import Fraction as F
Fraction=F
import json
from pathlib import Path
import time
from prepare_native import compile_case, is_exact, make_proof, sha


def q(s): return F(s.replace('D','E').replace('d','e'))

def parse_mps(path):
    rows=OrderedDict();columns=OrderedDict();bounds={};rhs={};integers=set()
    section=None;in_int=False;obj=None;name='';vectors=set();bound_vectors=set();seen_end=False
    for lineno,line in enumerate(path.read_text().splitlines(),1):
        if not line.strip() or line.startswith('*'):continue
        t=line.split()
        if not line[0].isspace():
            section=t[0]
            if section=='NAME': name=t[1] if len(t)>1 else '';continue
            if section=='ENDATA':seen_end=True;break
            assert section in ('ROWS','COLUMNS','RHS','BOUNDS'),(path,lineno,'unsupported section',section)
            continue
        if section=='ROWS':
            sense,r=t;assert r not in rows
            if sense=='N': assert obj is None;obj=r
            else:assert sense in ('E','L','G')
            rows[r]=sense
        elif section=='COLUMNS':
            if len(t)==3 and t[1].strip("'")=='MARKER':
                op=t[2].strip("'"); assert op in ('INTORG','INTEND')
                assert (op=='INTORG') != in_int
                in_int=op=='INTORG';continue
            assert len(t) in (3,5)
            v=t[0];col=columns.setdefault(v,{})
            if in_int:integers.add(v)
            for r,num in zip(t[1::2],t[2::2]):
                assert r in rows
                col[r]=col.get(r,F(0))+q(num)
        elif section=='RHS':
            assert len(t) in (3,5);vectors.add(t[0])
            for r,num in zip(t[1::2],t[2::2]):
                assert r in rows and r not in rhs
                rhs[r]=q(num)
        elif section=='BOUNDS':
            assert len(t) in (3,4);kind,bv,v=t[:3];bound_vectors.add(bv)
            assert v in columns
            lo,hi=bounds.get(v,(F(0),None));num=q(t[3]) if len(t)==4 else None
            if kind=='LO':assert num is not None;lo=num
            elif kind=='UP':assert num is not None;hi=num
            elif kind=='FR':assert num is None;lo=hi=None
            else:raise AssertionError((path,lineno,'unsupported bound',kind))
            bounds[v]=(lo,hi)
        else:raise AssertionError((path,lineno,section))
    assert seen_end and not in_int and obj is not None and len(vectors)<=1 and len(bound_vectors)<=1
    assert integers <= set(bounds), 'This case-specific preparer requires explicit bounds for every marked integer.'
    names=list(columns);rnames=[r for r in rows if r!=obj]
    variables=[{'name':v,'lower':bounds.get(v,(F(0),None))[0],'upper':bounds.get(v,(F(0),None))[1],'integer':v in integers} for v in names]
    index={n:i for i,n in enumerate(names)}
    def expression(r):return {index[v]:col[r] for v,col in columns.items() if col.get(r,F(0))}
    return {'name':name,'vars':variables,'rows':[{'name':r,'sense':rows[r],'rhs':rhs.get(r,F(0)),'terms':expression(r)} for r in rnames], 'objective':( -rhs.get(obj,F(0)),expression(obj)),'var_index':index,'row_index':{r:i for i,r in enumerate(rnames)}}


def _q(value):
    return value if isinstance(value,Fraction) else F(value)

def expression(c=0,t=None):
    terms={}
    for i,v in (t or {}).items():
        if v:terms[i]=v if isinstance(v,Fraction) else F(v)
    return _q(c),terms

def plus(a,b,mult=1):
    c,t=a;t=t.copy();mult=_q(mult)
    if mult==1:
        for i,v in b[1].items():
            value=t.get(i,0)+v
            if value:t[i]=value
            else:t.pop(i,None)
    else:
        for i,v in b[1].items():
            value=t.get(i,0)+v*mult
            if value:t[i]=value
            else:t.pop(i,None)
    return c+b[0]*mult,t

def mul(e,n):
    n=_q(n)
    if n==1:return e[0],e[1].copy()
    return expression(e[0]*n,{i:c*n for i,c in e[1].items()})
def expr_json(e):return {'constant':str(e[0]),'terms':[[i,str(v)] for i,v in sorted(e[1].items())]}
def substitute(e,mapping):
    out=expression(e[0])
    for i,v in e[1].items():out=plus(out,mapping[i],v)
    return out

def row_fact(row,which):
    e=expression(-row['rhs'],row['terms'])
    return mul(e,-1) if which=='RowLower' else e

def signature(e):return e[0],tuple(sorted(e[1].items()))

def integral(kind,e,model):
    return (kind=='Int' and e[0].denominator==1 and
            all(c.denominator==1 and model['vars'][i]['integer'] for i,c in e[1].items()))

def claim_checks(builder,inp,out,mapping,audit,reverse=False):
    """Discharge one native MI direction's Return obligations in plan order."""
    checks=[]
    def direct(kind,e):
        found=builder.find(kind,e)
        if found=='Exact':return 'Exact'
        if found is not None:return found
        opposite=builder.find('Eq',mul(e,-1))
        if opposite is not None and opposite!='Exact':
            return builder.lin(kind,[[opposite,F(-1)]],e)
        return None
    def prove(kind,e,rowname=None):
        if is_exact(kind,e) or integral(kind,e,builder.model):return 'Exact'
        found=direct(kind,e)
        if found is not None:return found
        if rowname is None:return builder.prove(kind,e)
        assert not reverse,('missing reverse row proof',rowname,kind,e)
        assert rowname in inp['row_index'],('missing derivation row',rowname,kind,e)
        ri=inp['row_index'][rowname];row=inp['rows'][ri]
        typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        terms=[[{typ:ri},F(1)]];computed=row_fact(row,typ)
        for s in audit['substitutions']:
            removed=inp['var_index'][s['removed_variable']]
            coefficient=computed[1].get(removed,F(0))
            if coefficient:
                eq_index=inp['row_index'][s['deleted_equality_rows'][0]]
                eq=row_fact(inp['rows'][eq_index],'RowEq')
                assert eq[1][removed]==1
                terms.append([{'RowEq':eq_index},-coefficient])
                computed=plus(computed,eq,-coefficient)
        assert computed==e,('linear combination differs',rowname,computed,e)
        return builder.lin(kind,terms,e)
    for i,var in enumerate(out['vars']):
        if var['lower'] is not None:checks.append(prove('Le',plus(expression(var['lower']),mapping[i],-1)))
        if var['upper'] is not None:checks.append(prove('Le',plus(mapping[i],expression(-var['upper']))))
        if var['integer']:checks.append(prove('Int',mapping[i]))
    for row in out['rows']:
        typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        checks.append(prove('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),row['name']))
    checks.append(prove('Le',plus(substitute(out['objective'],mapping),inp['objective'],-1)))
    return checks


def prepare(a,b,audit):
    assert len(a['vars'])==274 and len(b['vars'])==154 and len(a['rows'])==498 and len(b['rows'])==258
    by_removed={s['removed_variable']:s for s in audit['substitutions']};assert len(by_removed)==120
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[]
    for var in a['vars']:
        n=var['name']
        if n in b['var_index']:reverse.append(expression(0,{b['var_index'][n]:1}))
        else:
            s=by_removed[n];assert s['inverse']=='removed = 1 - retained'
            reverse.append(expression(1,{b['var_index'][s['retained_variable']]:-1}))
    for name in sorted(set(a['var_index'])&set(b['var_index'])):
        i=a['var_index'][name];j=b['var_index'][name]
        assert forward[j]==expression(0,{i:1}) and reverse[i]==expression(0,{j:1})
    proof,f,r=make_proof(a,b)
    fchecks=claim_checks(f,a,b,forward,audit)
    rchecks=claim_checks(r,b,a,reverse,audit,reverse=True)
    f.finish(forward,fchecks)
    r.finish(reverse,rchecks)
    return proof,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),
                  'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':2,
                  'complement_removed':len(by_removed),
                  'obligations_by_direction':[len(fchecks),len(rchecks)],
                  'steps_by_direction':[len(f.steps),len(r.steps)]}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test40-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test40'))
    ap.add_argument('--kernel',type=Path,help='accepted for old invocations; native compilation is in-process')
    args=ap.parse_args();started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit_path=run/'output/audit.json'
    a=parse_mps(source);b=parse_mps(target)
    proof,counts=prepare(a,b,json.loads(audit_path.read_text()))
    record=compile_case(proof,out,case_id='test40',source=source,target=target,
                        metadata={'audit':{'path':str(audit_path),'sha256':sha(audit_path)},
                                  'claims':'Native MI-OPT directions: retained-coordinate identity and reverse complement recovery y = 1 - x, with pointwise objective equality in both directions.',
                                  'counts':counts,
                                  'preparation_seconds':time.perf_counter()-started})
    (out/'coordinate_index.json').write_text(json.dumps({'source_variables':[v['name'] for v in a['vars']],'source_rows':[r['name'] for r in a['rows']],'target_variables':[v['name'] for v in b['vars']],'target_rows':[r['name'] for r in b['rows']]},indent=2)+'\n')
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'status':record['status'],'output':str(out),'counts':counts,'preparation_seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
