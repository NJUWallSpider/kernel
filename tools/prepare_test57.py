#!/usr/bin/env python3
"""Native exact complete test57 bounded-sum elimination proof."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,row_fact,sha
from prepare_native import compile_case,make_proof


def substitute(e,mapping):
    # The actual objective has 73,940 terms. Accumulate once instead of copying
    # a growing Python dictionary once per term; arithmetic remains Fraction.
    constant=e[0];terms={}
    for i,c in e[1].items():
        base,replacement=mapping[i]
        constant+=c*base
        if len(replacement)==1:
            j,q=next(iter(replacement.items()))
            value=terms.get(j,0)+c*q
            if value:terms[j]=value
            else:terms.pop(j,None)
        else:
            for j,q in replacement.items():
                value=terms.get(j,0)+c*q
                if value:terms[j]=value
                else:terms.pop(j,None)
    return expression(constant,terms)


def prepare(a,b,h):
    assert len(a['vars'])==114240 and len(b['vars'])==97368 and len(a['rows'])==29904 and len(b['rows'])==13032
    removed={a['var_index'][x['variable']]:x for x in h['removed_variables']};removed_ids=set(removed);assert len(removed)==16872
    assert set(a['var_index'])-set(b['var_index'])=={x['variable'] for x in removed.values()}
    definitions={};reverse=[];forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    for i,v in enumerate(a['vars']):
        assert v['integer'] and v['lower']==0 and v['upper']==1
        if i not in removed:
            assert v==b['vars'][b['var_index'][v['name']]];reverse.append(expression(0,{b['var_index'][v['name']]:1}));continue
        hint=removed[i];ri=a['row_index'][hint['definition_row']];row=a['rows'][ri];pivot=row['terms'][i]
        assert row['sense']=='E' and row['rhs']==0 and pivot in (F(-1),F(1))
        terms={a['var_index'][n]:F(1) for n in hint['sum_variables']};assert len(terms)==len(hint['sum_variables']) and not (set(terms)&removed_ids)
        assert row['terms']=={i:pivot,**{j:-pivot for j in terms}}
        definitions[i]=(ri,pivot);reverse.append(expression(0,{b['var_index'][a['vars'][j]['name']]:c for j,c in terms.items()}))
    assert set(a['row_index'])-set(b['row_index'])=={x['definition_row'] for x in removed.values()}
    assert not (set(a['objective'][1])&set(removed)) and substitute(a['objective'],reverse)==b['objective']
    projection=[[j,i] for i,e in enumerate(forward) for j in e[1]]
    proof,f,r=make_proof(a,b)

    def prove(builder,kind,e,terms):
        if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):return 'Exact'
        if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:return terms[0][0]
        return builder.lin(kind,terms,e)

    fchecks=[]
    for i,v in enumerate(b['vars']):
        e=forward[i];j=next(iter(e[1]));assert e==expression(0,{j:1}) and v==a['vars'][j]
        if v['lower'] is not None:fchecks.append({'VarLower':j})
        if v['upper'] is not None:fchecks.append({'VarUpper':j})
        if v['integer']:fchecks.append({'VarInt':j})
    for row in b['rows']:
        typ=next(iter(row_ref(b,row['name'])));e=substitute(row_fact(row,typ),forward)
        original=a['rows'][a['row_index'][row['name']]];terms=[[row_ref(a,row['name']),F(1)]]
        for i,c in row_fact(original,typ)[1].items():
            if i in definitions:
                ri,pivot=definitions[i];terms.append([{'RowEq':ri},-c/pivot])
        fchecks.append(prove(f,'Eq' if typ=='RowEq' else 'Le',e,terms))
    residual=plus(substitute(b['objective'],forward),a['objective'],-1)
    fchecks.append(prove(f,'Le',residual,[]))
    for i,j in projection:assert forward[j]==expression(0,{i:1})

    rchecks=[]
    for i,v in enumerate(a['vars']):
        e=reverse[i]
        if i in removed:
            hint=removed[i];gate=b['row_index'][hint['gate_row']];g=b['var_index'][hint['gate_variable']];row=b['rows'][gate]
            assert row['sense']=='L' and row['rhs']==0 and row['terms'][g]==-1 and all(q==1 for j,q in row['terms'].items() if j!=g)
            assert set(e[1])<=set(row['terms'])-{g}
            rchecks.append(prove(r,'Le',plus(expression(v['lower']),e,-1),[[{'VarLower':j},c] for j,c in e[1].items()]))
            terms=[[{'RowUpper':gate},F(1)],[{'VarUpper':g},F(1)]]+[[{'VarLower':j},F(1)] for j in row['terms'] if j!=g and j not in e[1]]
            rchecks.append(prove(r,'Le',plus(e,expression(-v['upper'])),terms))
            if v['integer']:rchecks.append(prove(r,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()]))
        else:
            j=next(iter(e[1]));assert e==expression(0,{j:1}) and v==b['vars'][j]
            if v['lower'] is not None:rchecks.append({'VarLower':j})
            if v['upper'] is not None:rchecks.append({'VarUpper':j})
            if v['integer']:rchecks.append({'VarInt':j})
    for row in a['rows']:
        typ=next(iter(row_ref(a,row['name'])));e=substitute(row_fact(row,typ),reverse)
        terms=[] if row['name'] not in b['row_index'] else [[row_ref(b,row['name']),F(1)]]
        rchecks.append(prove(r,'Eq' if typ=='RowEq' else 'Le',e,terms))
    residual=plus(substitute(a['objective'],reverse),b['objective'],-1)
    rchecks.append(prove(r,'Le',residual,[]))
    for i,j in projection:assert reverse[j]==expression(0,{i:1})

    f.finish(forward,fchecks)
    r.finish(reverse,rchecks)
    return proof,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'eliminated_bounded_binary_sums':len(removed),'claims':2,'obligations_by_direction':[len(fchecks),len(rchecks)],'steps_by_direction':[len(f.steps),len(r.steps)]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test57-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test57'));ap.add_argument('--kernel',type=Path,help='accepted for old invocations; native compilation is in-process');args=ap.parse_args();started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    proof,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    record=compile_case(proof,out,case_id='test57',source=source,target=target,
                        metadata={'audit':{'path':str(audit),'sha256':sha(audit)},
                                  'claims':'Native MI-OPT directions: all retained coordinates preserved and every reconstructed bounded binary sum proved from actual target gate rows; both directions preserve the objective.',
                                  'counts':counts,
                                  'preparation_seconds':time.perf_counter()-started})
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'case_id':'test57','status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':counts,'obligations':record['verification']['statistics']['obligations'],'preparation_seconds':record['preparation_seconds']},indent=2))


if __name__=='__main__':main()
