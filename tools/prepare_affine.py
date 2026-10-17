#!/usr/bin/env python3
"""Untrusted exact preparation for actual same-coordinate corpus reductions.

Sources and final MPS files are immutable. The witness JSON is only a hint:
Python checks identities independently, and all claims are checked again by RPX.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import time
from prepare_test40 import expression,plus,mul,row_fact,substitute,sha
from prepare_native import compile_case,make_proof


def parse_mps(path):
    rows=OrderedDict();vars=OrderedDict();rhs={};objective=None;section=None;marker=False;ended=False;name=''
    rhs_vectors=set();bound_vectors=set()
    for no,line in enumerate(path.read_text().splitlines(),1):
        if not line.strip() or line.startswith('*'):continue
        t=line.split()
        if not line[0].isspace():
            section=t[0]
            if section=='NAME':name=t[1] if len(t)>1 else '';continue
            if section=='ENDATA':ended=True;break
            assert section in ('ROWS','COLUMNS','RHS','RANGES','BOUNDS'),(path,no,'unsupported section',section)
            continue
        if section=='ROWS':
            sense,r=t;assert r not in rows and sense in ('N','E','L','G')
            rows[r]={'name':r,'sense':sense,'terms':{}}
            if sense=='N':assert objective is None;objective=r
        elif section=='COLUMNS':
            if len(t)==3 and t[1].strip("'")=='MARKER':
                tag=t[2].strip("'");assert tag in ('INTORG','INTEND') and marker!=(tag=='INTORG');marker=tag=='INTORG';continue
            assert len(t) in (3,5)
            v=t[0]
            if v not in vars:vars[v]={'name':v,'lower':F(0),'upper':None,'integer':marker,'explicit':False,'id':len(vars)}
            else:assert vars[v]['integer']==marker,('inconsistent marker',v)
            vi=vars[v]['id']
            for r,s in zip(t[1::2],t[2::2]):
                assert r in rows
                a=rows[r]['terms'];a[vi]=a.get(vi,F(0))+F(s.replace('D','E').replace('d','e'))
                if not a[vi]:del a[vi]
        elif section=='RHS':
            assert len(t) in (3,5);rhs_vectors.add(t[0])
            for r,s in zip(t[1::2],t[2::2]):assert r in rows and r not in rhs;rhs[r]=F(s)
        elif section=='BOUNDS':
            assert len(t) in (3,4);typ,bv,v=t[:3];bound_vectors.add(bv);assert v in vars
            var=vars[v];var['explicit']=True;n=F(t[3]) if len(t)==4 else None
            if typ in ('LO','LI'):assert n is not None;var['lower']=n
            elif typ in ('UP','UI'):assert n is not None;var['upper']=n
            elif typ=='FX':assert n is not None;var['lower']=var['upper']=n
            elif typ=='FR':assert n is None;var['lower']=var['upper']=None
            elif typ=='MI':assert n is None;var['lower']=None
            elif typ=='PL':assert n is None;var['upper']=None
            elif typ=='BV':
                assert n is None
                var['lower']=max(F(0),var['lower']) if var['lower'] is not None else F(0)
                var['upper']=min(F(1),var['upper']) if var['upper'] is not None else F(1)
                var['integer']=True
            else:raise AssertionError((path,no,'bound',typ))
            if typ in ('LI','UI'):var['integer']=True
        else:raise AssertionError((path,no,'unsupported nonempty section',section))
    assert ended and not marker and objective is not None and len(rhs_vectors)<=1 and len(bound_vectors)<=1
    for v in vars.values():
        if v['integer'] and not v['explicit']:v['upper']=F(1)
        v.pop('explicit');v.pop('id')
    obj=expression(-rhs.get(objective,F(0)),rows.pop(objective)['terms'])
    for row in rows.values():row['rhs']=rhs.get(row['name'],F(0))
    return {'name':name,'vars':list(vars.values()),'var_index':{v:i for i,v in enumerate(vars)},'rows':list(rows.values()),'row_index':{r:i for i,r in enumerate(rows)},'objective':obj}


def row_ref(model,name):
    idx=model['row_index'][name];return {{'E':'RowEq','L':'RowUpper','G':'RowLower'}[model['rows'][idx]['sense']]:idx}

def get_fact(model,ref,locals):
    typ,idx=next(iter(ref.items()))
    if typ=='Local':return locals[idx]
    if typ.startswith('Row'):return row_fact(model['rows'][idx],typ)
    v=model['vars'][idx]
    if typ=='VarLower':return expression(v['lower'],{idx:-1})
    if typ=='VarUpper':return expression(-v['upper'],{idx:1})
    if typ=='VarInt':return expression(0,{idx:1})
    raise AssertionError(ref)


def load_hints(case,run):
    a=json.loads((run/'output/audit.json').read_text())
    if case==79:return {'rewrites':{v['row']:v for v in a['modifications']['row_rewrites']},'duplicates':{v['deleted']:v['retained'] for v in a['modifications']['duplicate_deletions']}}
    if case==68:return {v['row']:v for v in a['row_transformations']}
    if case==33:return {v['removed_row']:v for v in a['certificates']}
    if case==65:
        with (run/'output/redundancy_certificates.tsv').open() as f:return {v['deleted_row']:v for v in csv.DictReader(f,delimiter='\t')}
    raise ValueError(case)


def derivation(case,row,reverse,inp,hints,rowchecks):
    n=row['name']
    if case==79:
        if n in hints['duplicates']:return [[row_ref(inp,hints['duplicates'][n]),F(1)]]
        h=hints['rewrites'][n];sign=-1 if reverse else 1
        return [[row_ref(inp,n),F(1)],[row_ref(inp,h['balance_row']),sign*F(h['balance_multiplier'])],[row_ref(inp,h['degree_row']),sign*F(h['degree_multiplier'])]]
    if case==68:
        h=hints[n]
        if not reverse:return [[row_ref(inp,v['original_row']),F(v['multiplier'])] for v in h['sources']]
        assert len(h['sources'])==2 and h['sources'][0]['original_row']==n and h['sources'][0]['multiplier']==1 and h['sources'][1]['multiplier']==-1
        predecessor=h['sources'][1]['original_row'];assert predecessor in rowchecks
        return [[row_ref(inp,n),F(1)],[rowchecks[predecessor],F(1)]]
    if case==33:
        assert reverse
        return [[row_ref(inp,n),F(1)] for n in hints[n]['retained_path_rows']]
    if case==65:
        assert reverse;h=hints[n]
        return [[row_ref(inp,h['upper_row']),F(1)],[row_ref(inp,h['link_row']),F(h['link_multiplier'])],[{'VarLower':inp['var_index'][h['nonnegative_y']]},F(1)],[{'VarLower':inp['var_index'][h['nonnegative_z']]},F(h['z_bound_multiplier'])]]
    raise AssertionError(case)


def native_block(case,inp,output,reverse,hints,builder):
    """Replay the case's exact row derivations on a native MI direction."""
    checks=[];rowchecks={}
    mapping=[expression(0,{inp['var_index'][v['name']]:1}) for v in output['vars']]
    for v in output['vars']:
        i=inp['var_index'][v['name']]
        assert v==inp['vars'][i]
        if v['lower'] is not None:checks.append({'VarLower':i})
        if v['upper'] is not None:checks.append({'VarUpper':i})
        if v['integer']:checks.append({'VarInt':i})
    for row in output['rows']:
        name=row['name'];typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        expected=substitute(row_fact(row,typ),mapping)
        direct=row_ref(inp,name) if name in inp['row_index'] else None
        if direct is not None and builder.refexpr(direct)==expected:
            ref=direct
        else:
            terms=derivation(case,row,reverse,inp,hints,rowchecks)
            ref=builder.lin('Eq' if typ=='RowEq' else 'Le',terms,expected)
        rowchecks[name]=ref
        checks.append(ref)
    assert substitute(output['objective'],mapping)==inp['objective'],'objective changed'
    checks.append('Exact')
    builder.finish(mapping,checks)
    return len(checks)


def run(case):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs',type=Path,default=Path('/Users/bhz/Code/reform_test/runs'))
    ap.add_argument('--out',type=Path,default=Path(f'cases/test{case}'))
    ap.add_argument('--kernel',type=Path,help='accepted for old invocations; native compilation is in-process')
    args=ap.parse_args()
    started=time.perf_counter()
    candidates=[item for item in args.runs.resolve().glob(f'test{case}-*')
                if (item/'input/model.mps').is_file() and (item/'output/audit.json').is_file()]
    if case==65:
        candidates=[item for item in candidates if (item/'output/redundancy_certificates.tsv').is_file()]
    if not candidates:
        raise SystemExit(f'No audited run for test{case}')
    run=max(candidates,key=lambda item:item.stat().st_mtime)
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps'
    targets=list((run/'output').glob('*.mps'));assert len(targets)==1;target=targets[0]
    a=parse_mps(source);b=parse_mps(target);hints=load_hints(case,run)
    assert set(a['var_index'])==set(b['var_index'])
    proof,forward,reverse=make_proof(a,b)
    native_block(case,a,b,False,hints,forward)
    native_block(case,b,a,True,hints,reverse)
    audit=run/'output/audit.json'
    record=compile_case(proof,out,case_id=f'test{case}',source=source,target=target,
                        metadata={'audit':{'path':str(audit),'sha256':sha(audit)},
                                  'claims':'Native MI-OPT directions: original-coordinate feasible-set equality and pointwise objective equality.',
                                  'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),
                                            'source_rows':len(a['rows']),'target_rows':len(b['rows']),'directions':2},
                                  'preparation_seconds':time.perf_counter()-started})
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case_id':f'test{case}','status':record['status'],
                      'guarantee':record['verification'].get('guarantee'),
                      'obligations':record['verification']['statistics']['obligations']}))

