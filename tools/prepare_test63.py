#!/usr/bin/env python3
"""Complete exact affine slack/difference proof for immutable actual test63.

Only the two native MI-OPT directions are emitted.  The legacy LP duplicate
claims, affine-projection pairs and inverse obligations described a four-claim
RPA request and are not part of the native certificate.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,row_fact,substitute,sha
from prepare_test48 import emit_checks
from prepare_native import compile_case,make_proof


def inspect(a,b,h):
    old=a['var_index'];new=b['var_index'];fixed=old['x2'];height=old['h'];slacks=h['new_slack_variables']
    assert a['vars'][fixed]=={'name':'x2','integer':False,'lower':F(0),'upper':F(0)}
    assert a['vars'][height]=={'name':'h','integer':False,'lower':F(0),'upper':None}
    assert a['objective']==expression(0,{height:1,fixed:1}) and b['objective']==expression(0,{new['h']:1})
    assert len(slacks)==91 and len(a['vars'])==1456 and len(b['vars'])==1546
    assert len(a['rows'])==len(b['rows'])==111 and set(a['row_index'])==set(b['row_index'])
    assert set(new)==(set(old)-{'x2'})|{x['name'] for x in slacks}
    for var in b['vars']:
        if var['name'] in old:assert var==a['vars'][old[var['name']]]
        else:assert var=={'name':var['name'],'integer':False,'lower':F(0),'upper':None}
    reverse=[expression() if i==fixed else expression(0,{new[v['name']]:1}) for i,v in enumerate(a['vars'])]
    source_loads=[];previous=expression();load_names={x['row'] for x in slacks};seen_slacks=set()
    for item in slacks:
        name,row_name=item['name'],item['row'];assert name not in seen_slacks;seen_slacks.add(name)
        row=a['rows'][a['row_index'][row_name]];assert row['sense']=='L' and row['rhs']==0 and row['terms'][height]==-1
        assert all(c>0 for i,c in row['terms'].items() if i!=height) and fixed not in row['terms']
        load=substitute(row_fact(row,'RowUpper'),reverse);law=plus(load,expression(0,{new[name]:1}))
        expected=plus(law,previous,-1);actual=b['rows'][b['row_index'][row_name]]
        assert actual['sense']=='E' and row_fact(actual,'RowEq')==expected;previous=law;source_loads.append((row_name,name,row))
    assignment_variables=[]
    for row in a['rows']:
        if row['name'] in load_names:continue
        assert row['sense']=='E' and row['rhs']==1 and all(c==1 for c in row['terms'].values())
        assignment_variables+=list(row['terms'])
        actual=b['rows'][b['row_index'][row['name']]];assert actual['sense']=='E' and row_fact(actual,'RowEq')==substitute(row_fact(row,'RowEq'),reverse)
    integer={i for i,v in enumerate(a['vars']) if v['integer']};assert len(integer)==1454 and set(assignment_variables)==integer and len(assignment_variables)==len(integer)
    for i in integer:assert a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
    intervals=[]
    for i in sorted(integer):
        support=[j for j,(_,_,row) in enumerate(source_loads) if i in row['terms']];assert support and support==list(range(min(support),max(support)+1))
        weights={source_loads[j][2]['terms'][i] for j in support};assert len(weights)==1
        intervals.append({'variable':i,'start':min(support),'end':max(support),'weight':str(next(iter(weights)))})
    forward=[];slack_rows={s:a['rows'][a['row_index'][r]] for r,s,_ in source_loads}
    for var in b['vars']:
        name=var['name'];forward.append(mul(row_fact(slack_rows[name],'RowUpper'),-1) if name in slack_rows else expression(0,{old[name]:1}))
    return forward,reverse,source_loads,{'status':'ALL_FIELDS_EQUAL','source_variables':len(a['vars']),'target_variables':len(b['vars']),'rows':len(a['rows']),'interval_columns':intervals,'source_load_terms':sum(len(r['terms']) for _,_,r in source_loads),'target_load_terms':sum(len(b['rows'][b['row_index'][r]]['terms']) for r,_,_ in source_loads)}


def prepare(a,b,h):
    forward,reverse,loads,evidence=inspect(a,b,h);fixed=a['var_index']['x2']
    proof,f,r=make_proof(a,b)
    zero=f.eqpair({'VarUpper':fixed},{'VarLower':fixed})
    f.add('Eq',zero)
    f.finish(forward,emit_checks(f,b,forward))
    prefix=None;rows={}
    for row_name,slack,row in loads:
        ref=row_ref(b,row_name);terms=[[ref,F(1)]]+([[prefix,F(1)]] if prefix else [])
        prefix=r.lin('Eq',terms,plus(substitute(row_fact(row,'RowUpper'),reverse),expression(0,{b['var_index'][slack]:1})));r.add('Eq',prefix)
        rows[a['row_index'][row_name]]=r.lin('Le',[[prefix,F(1)],[{'VarLower':b['var_index'][slack]},F(1)]],substitute(row_fact(row,'RowUpper'),reverse))
    r.finish(reverse,emit_checks(r,a,reverse,rows=rows))
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'rows':len(a['rows']),
            'slack_variables':len(loads),'fixed_coordinates':1,'directions':2}
    return proof,evidence,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test63-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test63'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target)
    proof,evidence,counts=prepare(a,b,json.loads(hint.read_text()))
    record=compile_case(proof,out,case_id='test63',source=source,target=target,
                        metadata={'audit':{'path':str(hint),'sha256':sha(hint)},
                                  'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
                                  'claims':'Two native MI-OPT directions proving objective-preserving affine equivalence of the actual slack extended formulation; the legacy LP duplicate and separate projection/inverse claims are not emitted.',
                                  'counts':counts,'preparation_seconds':time.perf_counter()-start})
    (out/'independent_structure.json').write_text(json.dumps(evidence,indent=2)+'\n')
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case_id':record['case_id'],'status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':counts,'obligations':record['verification']['statistics']['obligations'],'seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
