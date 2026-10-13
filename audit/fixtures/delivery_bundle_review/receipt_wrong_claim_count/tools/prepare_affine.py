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
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha


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


def block(case,inp,out,integer,reverse,hints):
    steps=[];checks=[];locals={};rowchecks={}
    mapping=[expression(0,{inp['var_index'][v['name']]:1}) for v in out['vars']]
    for v in out['vars']:
        i=inp['var_index'][v['name']];w=inp['vars'][i];assert v==w
        if v['lower'] is not None:checks.append({'VarLower':i})
        if v['upper'] is not None:checks.append({'VarUpper':i})
        if v['integer'] and integer:checks.append('Exact')
    for row in out['rows']:
        n=row['name'];typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        expected=substitute(row_fact(row,typ),mapping)
        direct=row_ref(inp,n) if n in inp['row_index'] else None
        if direct is not None and get_fact(inp,direct,locals)==expected:ref=direct
        else:
            terms=derivation(case,row,reverse,inp,hints,rowchecks)
            computed=expression()
            for r,m in terms:computed=plus(computed,get_fact(inp,r,locals),m)
            assert computed==expected,(case,reverse,n,'bad exact identity')
            idx=len(steps);locals[idx]=computed
            steps.append({'Lin':{'id':idx,'kind':'Eq' if typ=='RowEq' else 'Le','constant':'0','terms':[[r,str(m)] for r,m in terms]}})
            ref={'Local':idx}
        checks.append(ref);rowchecks[n]=ref
    assert substitute(out['objective'],mapping)==inp['objective'],'objective changed'
    checks.append('Exact')
    checks+=['Exact']*len(inp['vars']) # identity projections
    checks+=['Exact']*len(inp['vars']) # full affine inverse identities
    return {'steps':steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def run(case):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--runs',type=Path,default=Path('/Users/bhz/Code/reform_test/runs'));ap.add_argument('--out',type=Path,default=Path(f'cases/test{case}'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=next(args.runs.resolve().glob(f'test{case}-*'));out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';targets=list((run/'output').glob('*.mps'));assert len(targets)==1;target=targets[0]
    a=parse_mps(source);b=parse_mps(target);parse_secs=time.perf_counter()-start;hints=load_hints(case,run)
    assert set(a['var_index'])==set(b['var_index'])
    claims=[];blocks=[]
    for integer in (True,False):
        for reverse in (False,True):
            inp,output=(b,a) if reverse else (a,b)
            projection=[[i,output['var_index'][v['name']]] for i,v in enumerate(inp['vars'])]
            claim={'reverse':reverse,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]}
            claims.append(claim);blocks.append(block(case,inp,output,integer,reverse,hints))
    cert={'claims':claims,'blocks':blocks};rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(claims,separators=(',',':'))+'\n')
    metadata={'case_id':f'test{case}','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(run/'output/audit.json'),'sha256':sha(run/'output/audit.json')},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Original-coordinate feasible-set equality, including integer and LP domains, pointwise objective equality, every coordinate preserved, both affine inverse identities.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'linear_steps_by_claim':[len(x['steps']) for x in blocks]},'independent_parse_seconds':parse_secs,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        kernel=args.kernel.resolve();metadata['kernel_binary_sha256']=sha(kernel)
        commands=[['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]
        for command in commands:
            proc=subprocess.run([str(kernel)]+command,capture_output=True,text=True)
            metadata['kernel_runs'].append({'command':[str(kernel)]+command,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                result=json.loads(proc.stdout) if proc.stdout else {'status':'EXECUTION_FAILED'};metadata['status']=result['status']
                (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        result=json.loads(metadata['kernel_runs'][-1]['stdout']);assert result['status']=='VERIFIED';metadata['status']='VERIFIED'
        metadata['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({k:metadata[k] for k in ['case_id','status','counts','independent_parse_seconds','preparation_seconds','rpa_bytes']},indent=2),flush=True)

def refresh_acceptance():
    """Merge actual successful execution receipts with the unchanged inventory.

    A status string alone is insufficient: require a successful verifier command,
    matching source/final byte identities, and every current proof/model/request
    artifact hash recorded at that execution. This is a bookkeeping tool, not TCB.
    """
    from collections import Counter
    root=Path(__file__).resolve().parents[1]
    inventory_path=root/'audit/corpus_inventory.json'
    inv=json.loads(inventory_path.read_text())
    scope_path=root/'audit/contract_scope_gates.json'
    scope=json.loads(scope_path.read_text())
    assert scope['schema']=='rpx-original-contract-scope-gates-v1'
    entries=[];families=set()
    for c in inv['cases']:
        entry={'case_id':c['case_id'],'run_name':c['run_name'],'families':c['families'],'status':c['status'],'reason':c['status_reason']}
        case=root/'cases'/c['case_id'];receipt_path=case/'preparation.json'
        if receipt_path.exists():
            d=json.loads(receipt_path.read_text())
            entry['latest_kernel_outcome']=d['status']
            if 'protocol_status' in d:entry['protocol_status']=d['protocol_status']
            entry['execution_receipt']={'path':str(receipt_path),'sha256':sha(receipt_path)}
            if d['status']=='VERIFIED':
                from case_delivery import load_delivery
                delivery=load_delivery(case,d)
                for role,key in [('source','source_models'),('target','final_target_models')]:
                    assert sha(Path(d[role]['path']))==d[role]['sha256']==c[key][0]['sha256']
                kernel_hash=d.get('kernel_binary_sha256',d.get('kernel_binary',{}).get('sha256'))
                assert isinstance(kernel_hash,str) and len(kernel_hash)==64
                entry.update(status='VERIFIED',reason='Actual source/target canonicalization and every complete requested RPX piece verified; original-contract scope is reviewed separately.',source=d['source'],target=d['target'],required_contract=d.get('claims',d.get('contract')),claims=delivery['request'],artifacts=delivery['artifacts'],kernel_binary_sha256=kernel_hash,verification=delivery['verification'],delivery_kind=delivery['kind'])
                gate=scope['cases'].get(c['case_id'])
                if gate:
                    entry['original_contract_scope']={'gate_file':str(scope_path),'gate_sha256':sha(scope_path),'review':gate}
                    expected_requests={str(piece['request']) for piece in delivery['pieces']}
                    if delivery['kind']=='bundle':expected_requests.add(str(case/'combined-request.json'))
                    complete=gate['status']=='REVIEWED_COMPLETE_REQUEST' and {x['path'] for x in gate.get('requests',[])}==expected_requests and all(Path(x['path']).exists() and sha(Path(x['path']))==x['sha256'] for x in gate.get('requests',[]))
                    if not complete:
                        entry['status']='PROOF_NOT_COMPLETED'
                        entry['reason']='Requested certificates verified, but the identified complete original-report contract awaits a matching scope review.'
                if entry['status']=='VERIFIED':families.update(c['families'])
            elif d['status']=='RESOURCE_LIMIT':entry.update(status='CAPABILITY_OR_RESOURCE_GAP',reason='Actual verification returned RESOURCE_LIMIT; this is not a refutation of the transformation.')
            else:entry['reason']='Certificate preparation/verification is incomplete; a failed certificate does not refute the model relation.'
        entries.append(entry)
    counts=dict(Counter(e['status'] for e in entries))
    ledger={'schema':'rpx-corpus-acceptance-v1','inventory':{'path':str(inventory_path),'sha256':sha(inventory_path)},'scope':'All supplied final committed targets; original inventory retained as immutable baseline. Exact requested contracts are recorded per accepted case.','summary':{'total_runs':len(entries),'model_pairs_present':inv['summary']['model_pair_present_count'],'statuses':counts,'verified_cases':[e['case_id'] for e in entries if e['status']=='VERIFIED'],'families_with_certified_example':sorted(families),'all_families':sorted(inv['family_definitions']),'functional_delivery_complete':all(e['status']=='VERIFIED' for e in entries)},'cases':entries}
    path=root/'audit/acceptance.json';path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(ledger['summary'],indent=2))

if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--acceptance']:refresh_acceptance()
    else:raise SystemExit('Invoke prepare_test79.py, prepare_test68.py, prepare_test33.py, prepare_test65.py, or prepare_affine.py --acceptance')
