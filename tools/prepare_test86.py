#!/usr/bin/env python3
"""Certify 250 actual incoming-flow covers and complete strict LP witness."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,row_fact,sha
from prepare_test70 import SparseBuilder,cases_le_shared
from prepare_test66 import identity_certificate,execute,missing_inverse,invalid_point


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(990,550,990,800)
    assert a['vars']==b['vars'] and a['objective']==b['objective']
    added={d['name']:d for d in h['added_rows']};assert len(added)==250 and set(b['row_index'])-set(a['row_index'])==set(added)
    f=SparseBuilder(a);derived={}
    for rn,record in added.items():
        d=record['certificate'];p=a['var_index'][d['production']];y=a['var_index'][d['binary']];demand=F(d['demand']);incoming=[a['var_index'][name] for name in d['incoming']];outgoing=[a['var_index'][name] for name in d['outgoing']]
        assert demand>0 and len(set([p,y]+incoming+outgoing))==2+len(incoming)+len(outgoing)
        assert a['vars'][y]['integer'] and a['vars'][y]['lower']==0 and a['vars'][y]['upper']==1
        assert all(a['vars'][i]['lower']==0 for i in [p]+incoming+outgoing)
        balance=row_ref(a,d['balance']);link=row_ref(a,d['link']);linkexpr=f.refexpr(link);bigm=-linkexpr[1][y]
        assert bigm>demand and linkexpr==expression(0,{p:1,y:-bigm}) and 'RowUpper' in link
        assert 'RowEq' in balance and f.refexpr(balance)==expression(-demand,{p:1,**dict.fromkeys(incoming,F(1)),**dict.fromkeys(outgoing,F(-1))})
        wanted=expression(demand,{**dict.fromkeys(incoming,F(-1)),y:-demand})
        assert wanted==row_fact(b['rows'][b['row_index'][rn]],'RowLower')
        assert record['sense']=='G' and F(record['rhs'])==demand and {a['var_index'][name]:F(c) for name,c in record['coefficients'].items()}=={**dict.fromkeys(incoming,F(1)),y:demand}
        def left(child,zero):return child.lin('Le',[[balance,F(-1)],[link,F(1)]]+[[{'VarLower':i},F(1)] for i in outgoing]+[[zero,bigm-demand]],wanted)
        def right(child,one):return child.lin('Le',[[{'VarLower':i},F(1)] for i in incoming]+[[one,demand]],wanted)
        derived[rn]=cases_le_shared(f,wanted,y,left,right)
    point=h['strict_strengthening_witness']['point'];assert set(point)==set(a['var_index']);values=[F(point[v['name']]) for v in a['vars']]
    cert=identity_certificate(a,b,f,derived,values)
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'incoming_flow_cuts':len(added),'binary_cases':len(added),'claims':3,'points':1,'steps_by_claim':[len(x['steps']) for x in cert['blocks']],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]}
    return cert,counts


def missing_outgoing(cert):
    terms=cert['blocks'][0]['steps'][0]['Cases']['left']['steps'][0]['Lin']['terms'];old=terms.pop(2);return lambda:terms.insert(2,old)


def missing_active_gate(cert):
    terms=cert['blocks'][0]['steps'][0]['Cases']['right']['steps'][0]['Lin']['terms'];old=terms.pop();return lambda:terms.append(old)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test86-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test86'));ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();source=run/'input/model.mps';target=run/'output/model_strengthened.mps';audit=run/'output/audit.json'
    inventory=next(x for x in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if x['case_id']=='test86')
    assert sha(source)==inventory['source_models'][0]['sha256'] and sha(target)==inventory['final_target_models'][0]['sha256']
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    execute('test86',source,target,audit,__file__,cert,counts,args.out.resolve(),args.kernel.resolve(),start,'Complete same-coordinate mixed-integer feasible-set equality and exact pointwise objective equality after all 250 incoming-flow cover cuts, with both full inverse identities. Complete objective-preserving target LP inclusion and the full 990-coordinate fractional source-feasible point p=d, y=d/D, flows=0 on all five blocks establish strict target LP subset. Every actual original row, variable bound, binary domain, balance, link, and added cover is checked.',[('missing_outgoing_nonnegativity','Omits an outgoing-flow lower bound needed in the inactive production branch.',missing_outgoing),('missing_active_gate','Omits the active binary assumption from the nonnegative incoming-flow branch.',missing_active_gate),('missing_inverse','Omits a requested complete inverse coordinate.',missing_inverse),('infeasible_strictness_point','Violates a source variable lower bound in the complete fractional witness.',invalid_point)])


if __name__=='__main__':main()
