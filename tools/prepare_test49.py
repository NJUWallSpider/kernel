#!/usr/bin/env python3
"""Actual test49: complete identity MILP equivalence and strict LP inclusion.

The external row multipliers and points are untrusted inputs. Every combination,
integrality premise, full output domain/row/map and complete separating vector
is verified by the ordinary RPX rules; there is no network-specific checker.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, substitute, sha
from prepare_test88 import Builder


def block(inp, out, claim, hints):
    b = Builder(inp)
    mapping = [expression(0,{inp['var_index'][v['name']]:1}) for v in out['vars']]
    checks = []
    for v in out['vars']:
        i = inp['var_index'][v['name']]
        assert v == inp['vars'][i]
        if v['lower'] is not None: checks.append({'VarLower':i})
        if v['upper'] is not None: checks.append({'VarUpper':i})
        if claim['output_integers'] and v['integer']: checks.append('Exact')
    for row in out['rows']:
        name = row['name']; typ = {'L':'RowUpper','G':'RowLower','E':'RowEq'}[row['sense']]
        wanted = substitute(row_fact(row,typ),mapping)
        if name in inp['row_index']:
            ref = row_ref(inp,name)
            assert b.refexpr(ref) == wanted
        elif name in hints['removed_rows']:
            assert claim['reverse'] and typ == 'RowEq'
            terms = [[row_ref(inp,n),F(c)] for n,c in hints['removed_rows'][name]['recovery']['row_multipliers'].items()]
            ref = b.lin('Eq',terms,wanted)
        else:
            assert not claim['reverse'] and claim['input_integers'] and typ == 'RowLower'
            h = hints['added_rows'][name]['validity_certificate']; divisor = F(h['divisor'])
            assert divisor > 0
            terms = [[row_ref(inp,n),1/divisor] for n in h['negated_capacity_rows']]
            terms += [[row_ref(inp,h['balance_row']),-F(h['balance_multiplier'])/divisor]]
            terms += [[{'VarLower':inp['var_index'][n]},2/divisor] for n in h['nonnegative_flow_variables_multiplier_2']]
            unrounded = expression(F(h['unrounded_capacity_rhs'])/divisor,wanted[1])
            le = b.lin('Le',terms,unrounded)
            integer = b.lin('Int',[[{'VarInt':i},c] for i,c in wanted[1].items()],expression(0,wanted[1]))
            rounded = -((-unrounded[0].numerator)//unrounded[0].denominator)
            assert wanted == expression(rounded,wanted[1])
            i = b.alloc(); b.steps.append({'Round':{'id':i,'le':le,'integer':integer}})
            b.facts[i] = ('Le',wanted); ref = {'Local':i}
        checks.append(ref)
    assert substitute(out['objective'],mapping) == inp['objective']
    checks.append('Exact')
    checks += ['Exact']*len(claim['projection'])
    if claim['inverse'] is not None: checks += ['Exact']*len(inp['vars'])
    return {'steps':b.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def prepare(a,b,h,w):
    assert set(a['var_index']) == set(b['var_index'])
    claims=[]; blocks=[]
    for reverse,integer,inverse in [(False,True,1),(True,True,0),(True,False,None)]:
        inp,out = (b,a) if reverse else (a,b)
        claim={'reverse':reverse,'input_integers':integer,'output_integers':integer,'objective':'Equal',
               'projection':[[i,out['var_index'][v['name']]] for i,v in enumerate(inp['vars'])],'inverse':inverse}
        claims.append(claim); blocks.append(block(inp,out,claim,h))
    points=[{'claim':{'Strictness':{'inclusion_claim':2}},
             'values':[str(F(w['original_relaxation_point'].get(v['name'],0))) for v in a['vars']]}]
    for name in ['integer_feasible_point','circulation_counterexample_point']:
        for target,model in [(False,a),(True,b)]:
            points.append({'claim':{'Feasible':{'target':target,'integers':True,'objective':None}},
                           'values':[str(F(w[name].get(v['name'],0))) for v in model['vars']]})
    return {'claims':claims,'blocks':blocks,'points':points}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test49-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test49'));ap.add_argument('--kernel',type=Path,required=True)
    args=ap.parse_args(); start=time.perf_counter(); run=args.run.resolve(); out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';witness=run/'output/witnesses.json'
    a,b=parse_mps(source),parse_mps(target); cert=prepare(a,b,json.loads(audit.read_text()),json.loads(witness.read_text()))
    rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n')
    request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},indent=2)+'\n')
    k=args.kernel.resolve()
    d={'case_id':'test49','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},
       'audit':{'path':str(audit),'sha256':sha(audit)},'witness_input':{'path':str(witness),'sha256':sha(witness)},
       'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
       'claims':'Same complete integer feasible vectors and objective under named-coordinate bijection; target LP strictly contained in source LP via complete reverse inclusion and exact full separating point. Both full integer tree/circulation vectors are checked on both actual models. No optimum or LP objective improvement is asserted.',
       'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
                 'claims':3,'point_claims':5,'rounded_cuts':20,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]},
       'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[]}
    def save(): (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:
            d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED'
    d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
    d['negative_checks']=[];save()
    attacks=[('continuous_integer','Replace an integer cut premise by an actual continuous flow coordinate.'),
             ('wrong_cut_multiplier','Corrupt a middle capacity premise coefficient.'),
             ('missing_obligation','Delete a middle full-model bound obligation.'),
             ('false_strictness','Supply an integer-feasible point of both models as the separating LP point.'),
             ('wrong_coordinate','Replace one mapped source coordinate with zero while retaining the full requested bijection.')]
    for name,reason in attacks:
        bad=copy.deepcopy(cert)
        if name=='continuous_integer':bad['blocks'][0]['steps'][1]['Lin']['terms'][0][0]={'VarInt':next(i for i,v in enumerate(a['vars']) if not v['integer'])}
        elif name=='wrong_cut_multiplier':bad['blocks'][0]['steps'][0]['Lin']['terms'][3][1]='1/7'
        elif name=='missing_obligation':bad['blocks'][1]['end']['Return']['checks'].pop(500)
        elif name=='false_strictness':bad['points'][0]['values']=bad['points'][1]['values'][:]
        else:bad['blocks'][0]['end']['Return']['map'][500]=expr_json(expression())
        rp=out/(name+'.rpa');rp.write_text('RPA 3\n'+json.dumps(bad,separators=(',',':'))+'\n');binary=out/(name+'.rpx')
        p=subprocess.run([str(k),'assemble',str(rp),str(binary)],capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request)],capture_output=True,text=True);result=json.loads(p.stdout)
        assert p.returncode and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(rp),'rpx_sha256':sha(binary)});save()
    print(json.dumps({'case':d['case_id'],'status':d['status'],'counts':d['counts'],'verification':json.loads(d['kernel_runs'][-1]['stdout']),'attacks':len(d['negative_checks'])},indent=2))

if __name__=='__main__': main()
