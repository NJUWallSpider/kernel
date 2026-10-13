#!/usr/bin/env python3
"""Prepare the actual test40 affine-complement RPA certificate, outside the TCB.

No source corpus files are modified. Exact Python fractions independently read
actual MPS coefficients. The Rust canonicalizer and kernel decide acceptance.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import time


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


def expression(c=0,t=None):return F(c),{i:F(v) for i,v in (t or {}).items() if v}
def plus(a,b,mult=1):
    c,t=a;t=t.copy();mult=F(mult)
    for i,v in b[1].items():
        t[i]=t.get(i,F(0))+v*mult
        if not t[i]:del t[i]
    return c+b[0]*mult,t

def mul(e,n):return expression(e[0]*n,{i:c*n for i,c in e[1].items()})
def expr_json(e):return {'constant':str(e[0]),'terms':[[i,str(v)] for i,v in sorted(e[1].items())]}
def substitute(e,mapping):
    out=expression(e[0])
    for i,v in e[1].items():out=plus(out,mapping[i],v)
    return out

def row_fact(row,which):
    e=expression(-row['rhs'],row['terms'])
    return mul(e,-1) if which=='RowLower' else e

def facts(model,integer):
    result=[]
    for i,var in enumerate(model['vars']):
        if var['lower'] is not None:result.append(('Le',expression(var['lower'],{i:-1}),{'VarLower':i}))
        if var['upper'] is not None:result.append(('Le',expression(-var['upper'],{i:1}),{'VarUpper':i}))
        if integer and var['integer']:result.append(('Int',expression(0,{i:1}),{'VarInt':i}))
    for i,row in enumerate(model['rows']):
        typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        result.append(('Eq' if typ=='RowEq' else 'Le',row_fact(row,typ),{typ:i}))
    return result

def signature(e):return e[0],tuple(sorted(e[1].items()))

def build_claim(inp,out,mapping,claim,audit,inverse_map):
    fs=facts(inp,claim['input_integers']);lookup={}
    for kind,e,ref in fs:lookup.setdefault((kind,signature(e)),ref)
    steps=[];checks=[];obligations=[]
    def check(kind,e,rowname=None):
        obligations.append((kind,expr_json(e)))
        trivial=(not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0))) or (kind=='Int' and e[0].denominator==1 and all(v.denominator==1 and claim['input_integers'] and inp['vars'][i]['integer'] for i,v in e[1].items()))
        if trivial:checks.append('Exact');return
        direct=lookup.get((kind,signature(e))) or lookup.get(('Eq',signature(e)))
        if direct is not None:checks.append(direct);return
        opposite=lookup.get(('Eq',signature(mul(e,-1))))
        if opposite is not None:
            local=len(steps);steps.append({'Lin':{'id':local,'kind':kind,'constant':'0','terms':[[opposite,'-1']]}})
            checks.append({'Local':local});return
        assert rowname and not claim['reverse'],('missing derivation',rowname,kind,e)
        ri=inp['row_index'][rowname];row=inp['rows'][ri]
        typ={'L':'RowUpper','G':'RowLower','E':'RowEq'}[row['sense']]
        base=row_fact(row,typ);terms=[[{typ:ri},'1']];computed=base
        for s in audit['substitutions']:
            removed=inp['var_index'][s['removed_variable']]
            coefficient=computed[1].get(removed,F(0))
            if coefficient:
                eq_index=inp['row_index'][s['deleted_equality_rows'][0]]
                eq=row_fact(inp['rows'][eq_index],'RowEq')
                assert eq[1][removed]==1
                terms.append([{'RowEq':eq_index},str(-coefficient)])
                computed=plus(computed,eq,-coefficient)
        assert computed==e,('linear combination differs',rowname,computed,e)
        local=len(steps);steps.append({'Lin':{'id':local,'kind':kind,'constant':'0','terms':terms}})
        checks.append({'Local':local})
    for i,var in enumerate(out['vars']):
        if var['lower'] is not None:check('Le',plus(expression(var['lower']),mapping[i],-1))
        if var['upper'] is not None:check('Le',plus(mapping[i],expression(-var['upper'])))
        if var['integer'] and claim['output_integers']:check('Int',mapping[i])
    for row in out['rows']:
        typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        check('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),row['name'])
    check('Eq',plus(substitute(out['objective'],mapping),inp['objective'],-1))
    for i,o in claim['projection']:check('Eq',plus(mapping[o],expression(0,{i:1}),-1))
    for i,e in enumerate(inverse_map):check('Eq',plus(substitute(e,mapping),expression(0,{i:1}),-1))
    return {'steps':steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}},len(obligations)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test40-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test40'))
    ap.add_argument('--kernel',type=Path,help='Built rpx binary; when supplied, canonicalize, assemble, verify, and execute adversarial proof checks.')
    args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit_path=run/'output/audit.json'
    a=parse_mps(source);b=parse_mps(target);audit=json.loads(audit_path.read_text())
    assert len(a['vars'])==274 and len(b['vars'])==154 and len(a['rows'])==498 and len(b['rows'])==258
    by_removed={s['removed_variable']:s for s in audit['substitutions']};assert len(by_removed)==120
    fwd=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    rev=[]
    for var in a['vars']:
        n=var['name']
        if n in b['var_index']:rev.append(expression(0,{b['var_index'][n]:1}))
        else:
            s=by_removed[n];assert s['inverse']=='removed = 1 - retained'
            rev.append(expression(1,{b['var_index'][s['retained_variable']]:-1}))
    claims=[];blocks=[];counts=[]
    for integer in (True,False):
        for reverse in (False,True):
            inp,output,mapping=(b,a,rev) if reverse else (a,b,fwd)
            projection=[[inp['var_index'][n],output['var_index'][n]] for n in sorted(set(inp['var_index'])&set(output['var_index']))]
            claim={'reverse':reverse,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':([1,0,3,2][len(claims)])}
            block,count=build_claim(inp,output,mapping,claim,audit,fwd if reverse else rev)
            claims.append(claim);blocks.append(block);counts.append(count)
    certificate={'claims':claims,'blocks':blocks}
    rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 1\n'+json.dumps(certificate,indent=2)+'\n');request.write_text(json.dumps(claims,indent=2)+'\n')
    metadata={'case_id':'test40','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit_path),'sha256':sha(audit_path)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Both integer and LP directions, pointwise objective equality and identity on every retained coordinate. Reverse affine map restores every removed y as 1-x. Source complement equalities force uniqueness, so these maps are inverse on feasible sets.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'obligations_by_claim':counts,'linear_steps_by_claim':[len(b['steps']) for b in blocks]},'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    (out/'coordinate_index.json').write_text(json.dumps({'source_variables':[v['name'] for v in a['vars']],'source_rows':[r['name'] for r in a['rows']],'target_variables':[v['name'] for v in b['vars']],'target_rows':[r['name'] for r in b['rows']]},indent=2)+'\n')
    if args.kernel:
        kernel=args.kernel.resolve()
        commands=[['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]
        for command in commands:
            proc=subprocess.run([str(kernel)]+command,capture_output=True,text=True)
            record={'command':[str(kernel)]+command,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr};metadata['kernel_runs'].append(record)
            if proc.returncode:
                (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        result=json.loads(metadata['kernel_runs'][-1]['stdout']);assert result['status']=='VERIFIED';metadata['status']='VERIFIED'
        metadata['rpx_sha256']=sha(out/'proof.rpx');metadata['rpx_bytes']=(out/'proof.rpx').stat().st_size
        # A broken complement and a missing output obligation must both be rejected.
        attacks=[]
        import copy
        bad=copy.deepcopy(certificate);deleted_index=next(i for i,v in enumerate(a['vars']) if v['name'] in by_removed)
        bad['blocks'][1]['end']['Return']['map'][deleted_index]['constant']='0'
        attacks.append(('bad_complement',bad,'Changes y=1-x to y=-x, violating its bound/row obligations.'))
        bad=copy.deepcopy(certificate);bad['blocks'][0]['end']['Return']['checks'].pop()
        attacks.append(('missing_obligation',bad,'Omits a required affine inverse identity obligation.'))
        metadata['negative_checks']=[]
        for name,bad,reason in attacks:
            path=out/(name+'.rpa');path.write_text('RPA 1\n'+json.dumps(bad,indent=2)+'\n')
            encoded=out/(name+'.rpx');assembled=subprocess.run([str(kernel),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert assembled.returncode==0,assembled.stdout
            checked=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True)
            result=json.loads(checked.stdout);assert checked.returncode!=0 and result['status']=='INVALID',(name,checked.stdout)
            metadata['negative_checks'].append({'mutation':name,'rule_broken':reason,'result':result,'exit_code':checked.returncode,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'status':metadata['status'],'output':str(out),'counts':metadata['counts'],'preparation_seconds':metadata['preparation_seconds']},indent=2))

if __name__=='__main__':main()
