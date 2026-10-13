#!/usr/bin/env python3
"""Untrusted full actual test77 affine substitution/redundancy certificate.

Every proof step is an exact ordinary linear combination of actual model facts.
No original audit, numerical bound, row name or historical verifier is authority.
The Rust canonicalizer and checker decide the complete requested contracts.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, substitute, expr_json, row_fact, sha
from prepare_test48 import Proof, emit_checks


def variable(model, name):
    return expression(0, {model['var_index'][name]: 1})


def prepare(source, target):
    a, b = parse_mps(source), parse_mps(target)
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows'])) == (1536,351,1486,259)
    forward = [variable(a,v['name']) for v in b['vars']]
    reverse = [None] * len(a['vars'])
    eliminated = set(a['var_index']) - set(b['var_index'])
    assert eliminated == {f's#{j}' for j in range(1,51)}
    for i,v in enumerate(a['vars']):
        if v['name'] in b['var_index']:
            reverse[i] = variable(b,v['name'])
    groups = {}
    for j in range(1,51):
        s = a['var_index'][f's#{j}']
        row = a['rows'][a['row_index'][f'c02_{j}']]
        assert row['sense']=='E' and row['terms'][s]!=0
        normalized = mul(row_fact(row,'RowEq'),1/row['terms'][s])
        reconstruction = plus(expression(0,{s:1}),normalized,-1)
        assert reconstruction[0]==0 and all(a['vars'][i]['name'] in b['var_index'] for i in reconstruction[1])
        reverse[s] = substitute(reconstruction,[variable(b,v['name']) if v['name'] in b['var_index'] else expression() for v in a['vars']])
        simplex = b['rows'][b['row_index'][f'c04_{j}']]
        assert simplex['sense']=='E' and simplex['rhs']==1
        assert set(simplex['terms'])==set(reverse[s][1]) and set(simplex['terms'].values())=={F(1)}
        assert all(b['vars'][i]['lower']==0 and b['vars'][i]['upper']==1 and b['vars'][i]['integer'] for i in simplex['terms'])
        groups[j] = {'source':s,'map':reverse[s],'alias':normalized,'normalizer':1/row['terms'][s],
                     'simplex':row_ref(b,f'c04_{j}'),'minimum':min(reverse[s][1].values()),'maximum':max(reverse[s][1].values())}
        assert a['vars'][s]['lower']==groups[j]['minimum'] and a['vars'][s]['upper']==groups[j]['maximum']
    choices = [i for group in groups.values() for i in group['map'][1]]
    assert len(choices)==len(set(choices))==1284
    assert all(e is not None for e in reverse)
    removed_rows = set(a['row_index'])-set(b['row_index'])
    assert len(removed_rows)==92 and all(n.startswith(('c02_','c03_')) for n in removed_rows)

    claims=[]
    for integer in (True,False):
        for is_reverse in (False,True):
            inp,out=(b,a) if is_reverse else (a,b)
            claims.append({'reverse':is_reverse,'input_integers':integer,'output_integers':integer,
                           'objective':'Equal','projection':[[inp['var_index'][v['name']],out['var_index'][v['name']]] for v in b['vars']],
                           'inverse':[1,0,3,2][len(claims)]})

    def build_forward(claim):
        p=Proof(a);aliases={};rows={}
        for j,g in groups.items():
            aliases[g['source']]=p.lin('Eq',[[row_ref(a,f'c02_{j}'),g['normalizer']]],g['alias'])
            p.add('Eq',aliases[g['source']])
            p.add('Eq',p.lin('Eq',[[aliases[g['source']],F(-1)]]))
        for i,row in enumerate(b['rows']):
            ref=row_ref(a,row['name']);old=p.refexpr(ref)
            wanted=substitute(row_fact(row,next(iter(row_ref(b,row['name'])))),forward)
            terms=[[ref,F(1)]]+[[aliases[j],-coefficient] for j,coefficient in old[1].items() if j in aliases]
            rows[i]=p.prove('Eq' if row['sense']=='E' else 'Le',wanted,terms)
        return emit_checks(p,b,forward,claim,rows=rows,inverse=reverse)

    def build_reverse(claim):
        p=Proof(b);domains={};rows={};start_bounds={};trace={}
        for j,g in groups.items():
            lo,hi=g['minimum'],g['maximum'];e=g['map'];simplex=g['simplex']
            lower=p.lin('Le',[[simplex,-lo]]+[[{'VarLower':i},c-lo] for i,c in e[1].items() if c!=lo],plus(expression(lo),e,-1))
            upper=p.lin('Le',[[simplex,hi]]+[[{'VarLower':i},hi-c] for i,c in e[1].items() if c!=hi],plus(e,expression(-hi)))
            domains[(g['source'],'VarLower')]=lower;domains[(g['source'],'VarUpper')]=upper
            start_bounds[j]=(lower,upper)
        witness=20;g=groups[witness];completion=a['rows'][a['row_index'][f'c03_{witness}']]
        common=completion['rhs']+g['minimum'];assert common==171
        makespan=p.lin('Le',[[row_ref(b,f'c03_{witness}'),F(1)],[start_bounds[witness][0],F(1)]],plus(expression(common),variable(b,'mksp'),-1))
        trace['completion_fact']=makespan['Local'];trace['simplex_upper_fact']=start_bounds[1][1]['Local']
        for j,g in groups.items():
            name=f'c03_{j}'
            if name in b['row_index']:continue
            i=a['row_index'][name];row=a['rows'][i];wanted=substitute(row_fact(row,'RowLower'),reverse)
            slack=row['rhs']+g['maximum']-common;assert slack<=0
            rows[i]=p.lin('Le',[[makespan,F(1)],[start_bounds[j][1],F(1)]],wanted,constant=slack)

        # All 201 actual recurrence identities, built once in file-time order.
        recurrence={0:row_ref(b,'c00_1')};load={0:plus(variable(b,'z#0'),p.refexpr(recurrence[0]),-1)}
        for k in range(1,201):
            recurrence[k]=p.lin('Eq',[[recurrence[k-1],F(1)],[row_ref(b,f'c01_{k}'),F(1)]])
            load[k]=plus(variable(b,f'z#{k}'),p.refexpr(recurrence[k]),-1)
            assert load[k][0]==0 and set(load[k][1])<=set(choices) and all(c>0 for c in load[k][1].values())
        trace['recurrence_fact']=recurrence[1]['Local']
        removed_bounds=[];methods={'simplex':0,'containment':0}
        for k in range(201):
            name=f'z#{k}';si=a['var_index'][name];ti=b['var_index'][name]
            assert a['vars'][si]['lower']==b['vars'][ti]['lower']==0
            assert not a['vars'][si]['integer'] and not b['vars'][ti]['integer']
            bound=a['vars'][si]['upper'];assert bound==25
            if b['vars'][ti]['upper'] is not None:
                assert b['vars'][ti]['upper']==bound;continue
            removed_bounds.append(k);wanted=plus(variable(b,name),expression(-bound))
            maxima={j:max((load[k][1].get(i,F(0)) for i in g['map'][1]),default=F(0)) for j,g in groups.items()}
            upper=sum(maxima.values(),F(0))
            if upper<=bound:
                terms=[[recurrence[k],F(1)]]
                for j,g in groups.items():
                    m=maxima[j]
                    if m:terms.append([g['simplex'],m])
                    terms += [[{'VarLower':i},m-load[k][1].get(i,F(0))] for i in g['map'][1] if m!=load[k][1].get(i,F(0))]
                proof=p.lin('Le',terms,wanted,constant=upper-bound);methods['simplex']+=1
            else:
                candidates=[]
                for witness in range(201):
                    wi=b['var_index'][f'z#{witness}']
                    if b['vars'][wi]['upper']!=bound:continue
                    if all(c<=load[witness][1].get(i,F(0)) for i,c in load[k][1].items()):candidates.append(witness)
                assert candidates
                witness=min(candidates);wi=b['var_index'][f'z#{witness}']
                difference=plus(load[witness],load[k],-1);assert all(c>=0 for c in difference[1].values())
                terms=[[recurrence[k],F(1)],[recurrence[witness],F(-1)],[{'VarUpper':wi},F(1)]]+[[{'VarLower':i},c] for i,c in difference[1].items()]
                proof=p.lin('Le',terms,wanted);methods['containment']+=1
                trace['containment_fact']=proof['Local']
            domains[(si,'VarUpper')]=proof
        assert methods=={'simplex':50,'containment':8} and len(removed_bounds)==58
        block=emit_checks(p,a,reverse,claim,rows=rows,domains=domains,inverse=forward)
        return block,trace

    reverse_mi,trace=build_reverse(claims[1]);reverse_lp,_=build_reverse(claims[3])
    blocks=[build_forward(claims[0]),reverse_mi,build_forward(claims[2]),reverse_lp]
    return a,b,{'claims':claims,'blocks':blocks},trace


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test77-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test77'))
    ap.add_argument('--kernel',type=Path)
    args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source,target=run/'input/model.mps',run/'output/reformulated.mps'
    a,b,cert,trace=prepare(source,target)
    rpa,request=out/'proof.rpa',out/'request.json'
    rpa.write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    receipt={'case_id':'test77','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},
             'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
             'preparer_dependencies':{name:sha(Path(__file__).with_name(name)) for name in ['prepare_affine.py','prepare_test40.py','prepare_test48.py','prepare_test88.py','prepare_test23.py','audit_test23.py']},
             'claims':'Complete MI and LP affine bijection: both directions preserve objective, every retained coordinate, and all original-coordinate inverse identities. No numeric optimum or feasibility assertion.',
             'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'restored_start_variables':50,'restored_completion_rows':42,'restored_upper_bounds':58,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']],'linear_steps_by_claim':[len(x['steps']) for x in cert['blocks']]},
             'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    (out/'coordinate_index.json').write_text(json.dumps({'source_variables':[v['name'] for v in a['vars']],'target_variables':[v['name'] for v in b['vars']],'source_rows':[r['name'] for r in a['rows']],'target_rows':[r['name'] for r in b['rows']]},indent=2)+'\n')
    if args.kernel:
        kernel=args.kernel.resolve()
        def invoke(command):
            result=subprocess.run([str(kernel),*map(str,command)],capture_output=True,text=True)
            return {'command':[str(kernel),*map(str,command)],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        commands=[['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]
        for command in commands:
            result=invoke(command);receipt['kernel_runs'].append(result)
            if result['exit_code']:
                receipt['status']=json.loads(result['stdout']).get('status','FAILED');break
        else:
            receipt['status']='VERIFIED';receipt['kernel_binary_sha256']=sha(kernel)
            receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
            receipt['negative_checks']=[]
            attacks=[('incomplete_bound_checks','Remove one complete-model terminal obligation.'),
                     ('shifted_start_reconstruction','Shift an eliminated continuous start coordinate by one.'),
                     ('wrong_simplex_multiplier','Change the equality multiplier proving a reconstructed start upper bound.'),
                     ('missing_recurrence_equality','Drop a real recurrence from the prefix identity.'),
                     ('wrong_containment_witness','Use another retained resource bound in an active-set containment proof.'),
                     ('wrong_completion_bound','Double the retained completion inequality used to derive the common lower bound.')]
            for name,why in attacks:
                bad=copy.deepcopy(cert);body=bad['blocks'][1];ret=body['end']['Return']
                by_id={step['Lin']['id']:step['Lin'] for step in body['steps']}
                if name=='incomplete_bound_checks':ret['checks'].pop(0)
                elif name=='shifted_start_reconstruction':ret['map'][a['var_index']['s#1']]['constant']='1'
                elif name=='wrong_simplex_multiplier':by_id[trace['simplex_upper_fact']]['terms'][0][1]='0'
                elif name=='missing_recurrence_equality':by_id[trace['recurrence_fact']]['terms'].pop()
                elif name=='wrong_containment_witness':
                    terms=by_id[trace['containment_fact']]['terms'];index=next(i for i,(ref,c) in enumerate(terms) if isinstance(ref,dict) and 'VarUpper' in ref)
                    terms[index][0]={'VarUpper':b['var_index']['z#40']}
                else:by_id[trace['completion_fact']]['terms'][0][1]='2'
                path=out/(name+'.rpa');binary=out/(name+'.rpx');path.write_text('RPA 1\n'+json.dumps(bad,separators=(',',':'))+'\n')
                assembled=invoke(['assemble',path,binary]);assert assembled['exit_code']==0,assembled
                rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',binary,request]);result=json.loads(rejected['stdout'])
                assert rejected['exit_code']==2 and result['status']=='INVALID',(name,rejected)
                receipt['negative_checks'].append({'mutation':name,'rule_broken':why,'exit_code':rejected['exit_code'],'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(binary)})
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))
    if args.kernel and receipt['status']!='VERIFIED':raise SystemExit(1)


if __name__=='__main__':main()
