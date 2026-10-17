#!/usr/bin/env python3
"""Actual test80 optimizer equivalence on the native two-direction MI-OPT contract.

The frozen V9 request additionally asked for an exact objective-level input
domain, source attainment at -160, and a bijective parameterization of every
optimizer.  Those claims need caller-bound objective-level domains and opposing
inverse-domain closure, which the native MI-OPT certificate does not express;
they are deliberately not emitted.  What is emitted is a complete pair of MI
directions: a source-to-target projection and the audited target-to-source lift.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,row_fact,sha,substitute
from prepare_test48 import emit_checks
from prepare_native import compile_case,make_proof
from audit_test80 import inspect


def parse_expr(e):return expression(F(e['constant']),{i:F(c) for i,c in e['terms']})


def forward_projection(a,b,evidence):
    """One assignment row per target group; the target constant maps to one."""
    forward=[None]*len(b['vars']);rows={}
    linked={int(i):members for i,members in evidence['linked_sets'].items()}
    for name,members in evidence['target_groups'].items():
        if name.startswith('component_'):
            component=int(name.split('_')[1])
            i=min(i for i,ms in linked.items() if component in ms)
        else:
            i=int(name.split('_')[1])
        for j,index in enumerate(members):
            forward[index]=expression(0,{a['var_index'][f'x({i},{j})']:1})
        rows[b['row_index'][name]]=row_ref(a,f'assign_row_{i}')
    forward[b['var_index']['obj_constant']]=expression(1)
    assert all(item is not None for item in forward)
    return forward,rows


def reverse_rows(p,a,b,evidence,reverse):
    """Every original row follows from the audited target equalities and bounds."""
    rows={}
    for cert in evidence['reverse_row_certificates']:
        terms=[[{'RowEq':i},F(c)] for i,c in cert['target_equalities']]
        residual=parse_expr(cert['residual']);maximum=F(cert['residual_maximum'])
        if cert['kind']=='Eq':assert residual==expression() and maximum==0
        else:
            for i,c in residual[1].items():terms.append([{'VarUpper' if c>0 else 'VarLower':i},abs(c)])
        row=a['rows'][cert['source_row']]
        wanted=substitute(row_fact(row,{'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]),reverse)
        rows[cert['source_row']]=p.prove(cert['kind'],wanted,terms,constant=maximum)
    return rows


def prepare(a,b,evidence):
    proof,f,r=make_proof(a,b)
    forward,rows=forward_projection(a,b,evidence)
    f.finish(forward,emit_checks(f,b,forward,rows=rows))
    reverse=list(map(parse_expr,evidence['reverse_map']))
    fixed=b['var_index']['obj_constant']
    fixed_eq=r.add('Eq',r.eqpair({'VarUpper':fixed},{'VarLower':fixed}))
    objective=r.lin('Eq',[[fixed_eq,F(160)]],plus(substitute(a['objective'],reverse),b['objective'],-1))
    r.finish(reverse,emit_checks(r,a,reverse,rows=reverse_rows(r,a,b,evidence,reverse),objective=objective))
    details={'directions':2,'target_groups':len(evidence['target_groups']),
             'reverse_row_certificates':len(evidence['reverse_row_certificates'])}
    return proof,details


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test80-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test80'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json'
    a,b=parse_mps(source),parse_mps(target);evidence=inspect(a,b,json.loads(hint.read_text()))
    proof,details=prepare(a,b,evidence)
    record=compile_case(proof,out,case_id='test80',source=source,target=target,
                        metadata={'audit':{'path':str(hint),'sha256':sha(hint)},
                                  'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
                                  'protocol_status':'NATIVE_MI_OPT_ONLY',
                                  'claims':'Two native MI-OPT directions prove equality of the optimal value: the source-to-target projection keeps the target constant objective -160 below every source objective, and the audited target-to-source lift reconstructs every source bound, integer coordinate and row with the same objective.',
                                  'unsupported_claims':['objective-level input domain and source attainment at -160','bijective parameterization of every original integer optimizer by the actual target'],
                                  'counts':{**evidence['dimensions'],**details},
                                  'preparation_seconds':time.perf_counter()-start})
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case_id':record['case_id'],'status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':record['counts'],'obligations':record['verification']['statistics']['obligations'],'seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
