#!/usr/bin/env python3
"""Untrusted full actual test77 affine substitution/redundancy certificate.

Every proof step is an exact ordinary linear combination of actual model facts.
No original audit, numerical bound, row name or historical verifier is authority.
The native certificate has exactly two MI-OPT directions; the legacy LP duplicate
claims, projection pairs and inverse obligations are not emitted.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse, json, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, substitute, row_fact, sha
from prepare_test48 import emit_checks
from prepare_native import compile_case, make_proof


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

    proof, f, r = make_proof(a, b)

    def build_forward(p):
        aliases={};rows={}
        for j,g in groups.items():
            aliases[g['source']]=p.lin('Eq',[[row_ref(a,f'c02_{j}'),g['normalizer']]],g['alias'])
            p.add('Eq',aliases[g['source']])
            p.add('Eq',p.lin('Eq',[[aliases[g['source']],F(-1)]]))
        for i,row in enumerate(b['rows']):
            ref=row_ref(a,row['name']);old=p.refexpr(ref)
            wanted=substitute(row_fact(row,next(iter(row_ref(b,row['name'])))),forward)
            terms=[[ref,F(1)]]+[[aliases[j],-coefficient] for j,coefficient in old[1].items() if j in aliases]
            rows[i]=p.prove('Eq' if row['sense']=='E' else 'Le',wanted,terms)
        return emit_checks(p,b,forward,rows=rows)

    def build_reverse(p):
        domains={};rows={};start_bounds={}
        for j,g in groups.items():
            lo,hi=g['minimum'],g['maximum'];e=g['map'];simplex=g['simplex']
            lower=p.lin('Le',[[simplex,-lo]]+[[{'VarLower':i},c-lo] for i,c in e[1].items() if c!=lo],plus(expression(lo),e,-1))
            upper=p.lin('Le',[[simplex,hi]]+[[{'VarLower':i},hi-c] for i,c in e[1].items() if c!=hi],plus(e,expression(-hi)))
            domains[(g['source'],'VarLower')]=lower;domains[(g['source'],'VarUpper')]=upper
            start_bounds[j]=(lower,upper)
        witness=20;g=groups[witness];completion=a['rows'][a['row_index'][f'c03_{witness}']]
        common=completion['rhs']+g['minimum'];assert common==171
        makespan=p.lin('Le',[[row_ref(b,f'c03_{witness}'),F(1)],[start_bounds[witness][0],F(1)]],plus(expression(common),variable(b,'mksp'),-1))
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
            domains[(si,'VarUpper')]=proof
        assert methods=={'simplex':50,'containment':8} and len(removed_bounds)==58
        return emit_checks(p,a,reverse,rows=rows,domains=domains)

    f.finish(forward,build_forward(f))
    r.finish(reverse,build_reverse(r))
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),
            'source_rows':len(a['rows']),'target_rows':len(b['rows']),
            'restored_start_variables':50,'restored_completion_rows':42,
            'restored_upper_bounds':58,'directions':2}
    return proof,a,b,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test77-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test77'))
    args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve()
    source,target=run/'input/model.mps',run/'output/reformulated.mps'
    proof,a,b,counts=prepare(source,target)
    record=compile_case(proof,out,case_id='test77',source=source,target=target,
                        metadata={'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
                                  'claims':'Both native MI-OPT directions preserve the objective and prove the complete affine substitution in either direction. LP duplicates, projection pairs and inverse obligations are not emitted.',
                                  'counts':counts,'preparation_seconds':time.perf_counter()-start})
    (out/'coordinate_index.json').write_text(json.dumps({'source_variables':[v['name'] for v in a['vars']],'target_variables':[v['name'] for v in b['vars']],'source_rows':[r['name'] for r in a['rows']],'target_rows':[r['name'] for r in b['rows']]},indent=2)+'\n')
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case_id':record['case_id'],'status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':counts,'obligations':record['verification']['statistics']['obligations'],'seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
