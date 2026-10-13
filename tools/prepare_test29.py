#!/usr/bin/env python3
"""Replay the actual support quotient with exact local certificates and receipts."""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict,ChainMap
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,plus,mul,sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder


def prove(p,kind,wanted,terms=(),constant=0):
    if not wanted[1] and ((kind=='Eq' and wanted[0]==0) or (kind=='Le' and wanted[0]<=0) or (kind=='Int' and wanted[0].denominator==1)):return 'Exact'
    if len(terms)==1 and terms[0][1]==1 and p.kind(terms[0][0])==kind and p.refexpr(terms[0][0])==wanted:return terms[0][0]
    return p.lin(kind,list(terms),wanted,constant)


def split_case(p,kind,wanted,split,integer,left,right):
    ident=p.alloc();branches=[]
    for side,fn in enumerate((left,right)):
        assumption=split if side==0 else plus(expression(1),split,-1)
        child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[assumption]);child.facts=ChainMap({},p.facts)
        end=fn(child,{'Assumption':len(p.assumptions)})
        if 'Witness' in end:assert child.kind(end['Witness'])==kind and child.refexpr(end['Witness'])==wanted
        else:assert child.kind(end['Absurd'])=='Le' and child.refexpr(end['Absurd'])[0]>0 and not child.refexpr(end['Absurd'])[1]
        branches.append({'steps':child.steps,'end':end})
    p.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),'split':expr_json(split),'integer':integer,'left':branches[0],'right':branches[1]}});p.facts[ident]=(kind,wanted);return {'Local':ident}


def zero_extension(a,b,f,zeros,forward_rows,reverse_builder,reverse_rows):
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    assert set(zeros)==set(range(len(a['vars'])))-{next(iter(e[1])) for e in forward}
    projection=[[next(iter(e[1])),j] for j,e in enumerate(forward)];claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=reverse_builder if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            e=mapping[i]
            if not e[1]:checks.extend(['Exact','Exact']+(['Exact'] if integer else []));continue
            j=next(iter(e[1]));assert v==inp['vars'][j] and v['integer'] and v['lower']==0 and v['upper']==1
            checks.extend([{'VarLower':j},{'VarUpper':j}]+([{'VarInt':j}] if integer else []))
        checks.extend((reverse_rows if back else forward_rows)[r['name']] for r in out['rows'])
        diff=plus(substitute(out['objective'],mapping),inp['objective'],-1)
        checks.append(prove(p,'Eq',diff,[[zeros[i],c] for i,c in diff[1].items()] if not back else []))
        checks.extend(['Exact']*len(projection));inverse=1 if index==0 else 0 if index==1 else None
        if inverse is not None:
            for i in range(len(inp['vars'])):checks.append(p.lin('Eq',[[zeros[i],-1]],expression(0,{i:-1})) if not back and i in zeros else 'Exact')
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in projection] if back else projection,'inverse':inverse})
        blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks}, {'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'zero_variables':len(zeros),'claims':3,'steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def quotient(a,b,h,case):
    f=SparseBuilder(a);zeros={};deductions=h['zero_deductions'] if case==29 else h['zero_derivations']
    for d in deductions:
        head=a['var_index'][d['variable']];ref=row_ref(a,d['row'] if case==29 else d['original_support_row']);e=f.refexpr(ref);assert e[0]==0 and e[1][head]==1 and all(c==-1 for i,c in e[1].items() if i!=head)
        support=set(e[1])-{head}
        if support<=zeros.keys():upper=f.lin('Le',[[ref,1]]+[[zeros[i],1] for i in sorted(support)],expression(0,{head:1}));zeros[head]=f.eqpair(upper,{'VarLower':head});continue
        groups=defaultdict(set);prior=[]
        for reason in d['support_reasons']:
            i=a['var_index'][reason['variable']]
            if reason['kind']=='earlier_zero':assert i in zeros;prior.append(i)
            else:groups[reason['equality']].add(i)
        assert set(prior)|set().union(*groups.values())==support
        bounds=[]
        for rn,selected in groups.items():
            rr=row_ref(a,rn);ee=f.refexpr(rr);assert ee[0]==-1 and all(c==1 for c in ee[1].values()) and selected|{head}<=ee[1].keys()
            bound=f.lin('Le',[[rr,1]]+[[{'VarLower':i},1] for i in sorted(set(ee[1])-selected-{head})],expression(-1,{i:1 for i in selected|{head}}));bounds.append(bound)
        def left(p,ass):return {'Witness':p.eqpair(ass,{'VarLower':head})}
        def right(p,ass):
            terms=[[ref,1]]+[[zeros[i],1] for i in prior]+[[r,1] for r in bounds]+[[ass,len(bounds)+1]]
            return {'Absurd':p.lin('Le',terms,expression(1))}
        zeros[head]=split_case(f,'Eq',expression(0,{head:1}),expression(0,{head:1}),{'VarInt':head},left,right)
    retained={a['var_index'][v['name']] for v in b['vars']};assert retained|zeros.keys()==set(range(len(a['vars'])))
    residual={};rowlookup={}
    for row in a['rows']:
        ref=row_ref(a,row['name']);e=f.refexpr(ref);wanted=expression(e[0],{i:c for i,c in e[1].items() if i in retained});kind=f.kind(ref)
        residual[row['name']]=prove(f,kind,wanted,[[ref,1]]+[[zeros[i],-c] for i,c in e[1].items() if i in zeros])
        if row['sense']=='L':
            heads=[i for i,c in wanted[1].items() if c==1]
            if heads:assert len(heads)==1;head=heads[0];rowlookup[head,frozenset(set(wanted[1])-{head})]=row['name']
    classes=h['balance_classes'] if case==29 else [{'name':d['name'],'left_equality':d['left_group'],'right_equality':d['right_group'],'positive_variables':d['left_variables'],'negative_variables':d['right_variables'],'omitted':not d['retained']} for d in h['support_blocks']]
    balances={};rowclass={};byedge=defaultdict(list)
    for d in classes:
        H={a['var_index'][v] for v in d['positive_variables']};S={a['var_index'][v] for v in d['negative_variables']};assert H and S and not H&S
        def direction(A,B,group):
            rows=[rowlookup[i,frozenset(B)] for i in sorted(A)]
            for rn in rows:assert rn not in rowclass;rowclass[rn]=(d['name'],A,B)
            aggregate=f.lin('Le',[[residual[rn],1] for rn in rows],expression(0,{**{i:1 for i in A},**{i:-len(A) for i in B}}))
            base=residual[group];ee=f.refexpr(base);assert ee[0]==-1 and A<=ee[1].keys() and all(c==1 for c in ee[1].values())
            upper=f.lin('Le',[[base,1]]+[[{'VarLower':i},1] for i in sorted(set(ee[1])-A)],expression(-1,{i:1 for i in A}))
            split=expression(0,{i:1 for i in B});integer=f.lin('Int',[[{'VarInt':i},1] for i in sorted(B)],split);wanted=expression(0,{**{i:1 for i in A},**{i:-1 for i in B}})
            return split_case(f,'Le',wanted,split,integer,lambda p,s:{'Witness':p.lin('Le',[[aggregate,1],[s,len(A)-1]],wanted)},lambda p,s:{'Witness':p.lin('Le',[[upper,1],[s,1]],wanted)})
        balances[d['name']]=f.eqpair(direction(H,S,d['left_equality']),direction(S,H,d['right_equality']));byedge[d['left_equality'],d['right_equality']].append(d)
    forward={}
    rename_to_a=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    for row in b['rows']:
        rn=row['name'];ref=balances[rn] if rn in balances else residual[rn];assert f.refexpr(ref)==substitute(SparseBuilder(b).refexpr(row_ref(b,rn)),rename_to_a);forward[rn]=ref
    r=SparseBuilder(b);restored={rn:row_ref(b,rn) for rn in b['row_index']}
    if case==85:
        for rn,terms in h['removed_original_equalities'].items():restored[rn]=r.lin('Eq',[[row_ref(b,n),c] for n,c in sorted(terms.items())])
    for edge,ds in byedge.items():
        omitted=[d for d in ds if d['omitted']];assert len(omitted)==1;d=omitted[0]
        restored[d['name']]=r.lin('Eq',[[restored[edge[0]],1],[restored[edge[1]],-1]]+[[restored[x['name']],-1] for x in ds if not x['omitted']])
    positives={d['name']:{a['var_index'][v] for v in d['positive_variables']} for d in classes}
    reverse={};mapping=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    for row in a['rows']:
        rn=row['name'];ref=row_ref(a,rn);wanted=substitute(f.refexpr(ref),mapping)
        if row['sense']=='E':check=restored[rn];assert r.refexpr(check)==wanted
        elif rn in rowclass:
            cn,A,B=rowclass[rn];head=next(i for i,c in f.refexpr(residual[rn])[1].items() if c==1);sign=1 if head in positives[cn] else -1
            terms=[[restored[cn],sign]]+[[{'VarLower':b['var_index'][a['vars'][i]['name']]},1] for i in sorted(A-{head})];check=prove(r,'Le',wanted,terms)
        else:check=prove(r,'Le',wanted,[[{'VarLower':i},-c] for i,c in wanted[1].items()],constant=wanted[0])
        reverse[rn]=check
    cert,counts=zero_extension(a,b,f,zeros,forward,r,reverse);counts.update(reciprocal_blocks=len(classes),omitted_blocks=sum(d['omitted'] for d in classes));return cert,counts


def execute(case,prepare,script):
    ap=argparse.ArgumentParser();ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();entry=next(e for e in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if e['case_id']==f'test{case}');run=Path(entry['run_directory']);source=run/entry['source_models'][0]['path'];target=run/entry['final_target_models'][0]['path'];audit=run/'output/audit.json';out=Path(f'cases/test{case}').resolve();out.mkdir(parents=True,exist_ok=True)
    assert sha(source)==entry['source_models'][0]['sha256'] and sha(target)==entry['final_target_models'][0]['sha256']
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n');k=args.kernel.resolve()
    d={'case_id':f'test{case}','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(script).resolve()),'sha256':sha(Path(script))},'claims':'Complete original-coordinate zero-extension integer feasible-set bijection, exact objective values, every retained coordinate preserved, both full inverse identities; independently verified objective-preserving target-to-source LP inclusion. No feasibility, optimality or global strictness assertion.','counts':counts,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def command(cmd,expected=0):
        p=subprocess.run([str(k)]+[str(x) for x in cmd],capture_output=True,text=True);record={'command':[str(k)]+[str(x) for x in cmd],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(record)
        if p.returncode!=expected:d['status']='EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(record)
        return record
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]
    command(['canonical',source,out/'source.mcm']);command(['canonical',target,out/'target.mcm']);command(['assemble',rpa,out/'proof.rpx']);command(verify)
    duplicate=out/'deterministic.rpx';command(['assemble',rpa,duplicate]);assert sha(duplicate)==sha(out/'proof.rpx');duplicate.unlink();d['assemble_byte_deterministic']=True
    mutations=[('missing_inverse','Full inverse identity omitted.'),('wrong_zero_extension','A removed coordinate reconstructs as one rather than zero.'),('missing_linear_premise','An exact linear derivation loses a necessary premise.')]
    for name,reason in mutations:
        if name=='missing_inverse':obj=cert['blocks'][0]['end']['Return']['checks'];old=obj.pop();undo=lambda:obj.append(old)
        elif name=='wrong_zero_extension':obj=next(e for e in cert['blocks'][1]['end']['Return']['map'] if not e['terms']);old=obj['constant'];obj['constant']='1';undo=lambda:obj.update(constant=old)
        else:obj=next(s['Lin']['terms'] for s in cert['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['terms']);old=obj.pop(0);undo=lambda:obj.insert(0,old)
        path=out/(name+'.rpa');encoded=out/(name+'.rpx');path.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();assembly=command(['assemble',path,encoded]);failure=command(['verify',out/'source.mcm',out/'target.mcm',encoded,request],2);result=json.loads(failure['stdout']);assert result['status']=='INVALID';d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':2,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'kernel_runs':[assembly,failure],'storage':'Temporary mutation files removed; deterministic recipe retained in preparer.'});path.unlink();encoded.unlink()
    command(verify);last=command(verify);assert json.loads(last['stdout'])['status']=='VERIFIED'
    positive=[{key:value for key,value in json.loads(x['stdout']).items() if not key.endswith('_us')} for x in d['kernel_runs'] if x['command'][1]=='verify' and x['exit_code']==0]
    assert all(result==positive[0] for result in positive);d['verify_deterministic']=True;d['verify_determinism_scope']='All result fields except measured *_us timings.'
    d['status']='VERIFIED';d['preparation_seconds']=time.perf_counter()-start;d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({key:d[key] for key in ['case_id','status','counts','preparation_seconds','rpa_bytes']}))


if __name__=='__main__':execute(29,lambda a,b,h:quotient(a,b,h,29),__file__)
