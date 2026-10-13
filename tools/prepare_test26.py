#!/usr/bin/env python3
"""Untrusted actual26 full identity/integrality/gate certificate, scalar rules only."""
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, substitute, sha
from prepare_test88 import Builder
from prepare_test44 import le_cases


def integrality(m,h,p):
    known={i:{'VarInt':i} for i,v in enumerate(m['vars']) if v['integer']}
    for d in h['integrality_proof']:
        i=m['var_index'][d['variable']];r=row_ref(m,d['row']);e=p.refexpr(r);pivot=e[1][i]
        assert i not in known and pivot in [F(-1),F(1)] and pivot==d['pivot_coefficient']
        assert set(d['dependencies'])=={m['vars'][j]['name'] for j in e[1] if j!=i}
        terms=[[r,1/pivot]]+[[known[j],-c/pivot] for j,c in e[1].items() if j!=i]
        known[i]=p.lin('Int',terms,expression(0,{i:1}),-e[0]/pivot)
    assert len(known)==len(m['vars']) and len(h['integrality_proof'])==4502
    return known


def prepare(a,b,h):
    assert set(a['var_index'])==set(b['var_index']) and len(a['vars'])==11717
    assert set(a['row_index'])==set(b['row_index']) and len(a['rows'])==10460
    gates={d['row']:d for d in h['gate_rounding']};assert len(gates)==38
    claims=[];blocks=[]
    for rev,integer,inverse in [(False,True,1),(True,True,0),(True,False,None)]:
        inp,out=(b,a) if rev else (a,b);p=Builder(inp);mapping=[expression(0,{inp['var_index'][v['name']]:1}) for v in out['vars']]
        known=integrality(inp,h,p) if rev and integer else {};checks=[]
        claim={'reverse':rev,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[i,out['var_index'][v['name']]] for i,v in enumerate(inp['vars'])],'inverse':inverse};claims.append(claim)
        for i,v in enumerate(out['vars']):
            j=inp['var_index'][v['name']];assert v['lower']==inp['vars'][j]['lower'] and v['upper']==inp['vars'][j]['upper']
            if v['lower'] is not None:checks.append({'VarLower':j})
            if v['upper'] is not None:checks.append({'VarUpper':j})
            if integer and v['integer']:checks.append(known[j] if j in known else {'VarInt':j})
        for row in out['rows']:
            name=row['name'];r=row_ref(inp,name);wanted=substitute(row_fact(row,next(iter(row_ref(out,name)))),mapping)
            if name not in gates:assert p.refexpr(r)==wanted;checks.append(r);continue
            d=gates[name];y=inp['var_index'][d['gate']];zs=[inp['var_index'][n] for n in d['sum_variables']];aa=F(d['old_gate_coeff']);k=F(d['unit']);q=aa//k
            assert aa>0 and k>0 and q==d['max_integer_sum'] and inp['vars'][y]['lower']==0 and inp['vars'][y]['upper']==1
            total=expression(0,{z:1 for z in zs});cut=plus(total,expression(0,{y:-q}));old=plus(mul(total,k),expression(0,{y:-aa}))
            if rev:
                assert p.refexpr(r)==cut and wanted==old
                checks.append(p.lin('Le',[[r,k],[{'VarLower':y},aa-k*q]],wanted))
            else:
                assert p.refexpr(r)==old and wanted==cut
                def left(child,assumption):
                    return {'Witness':child.lin('Le',[[r,1/k],[assumption,aa/k-q]],wanted)}
                def right(child,assumption):
                    eq=child.eqpair({'VarUpper':y},assumption)
                    le=child.lin('Le',[[r,1/k],[eq,aa/k]],plus(total,expression(-aa/k)))
                    ints=child.lin('Int',[[{'VarInt':z},F(1)] for z in zs],total)
                    ident=child.alloc();rounded=plus(total,expression(-q));child.steps.append({'Round':{'id':ident,'le':le,'integer':ints}});child.facts[ident]=('Le',rounded)
                    return {'Witness':child.lin('Le',[[{'Local':ident},F(1)],[eq,-q]],wanted)}
                checks.append(le_cases(p,wanted,y,left,right))
        assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact');checks+=['Exact']*len(inp['vars'])
        if inverse is not None:checks+=['Exact']*len(inp['vars'])
        blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test26-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test26'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/model_reformulated.mps';hints=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target);cert=prepare(a,b,json.loads(hints.read_text()));rp=out/'proof.rpa';request=out/'request.json';rp.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n');k=args.kernel.resolve()
    d={'case_id':'test26','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(hints),'sha256':sha(hints)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete identical mixed-integer assignments and objective on all11717 coordinates, with both inverse identities; complete target LP inclusion into source LP, preserving all coordinates and objective. No LP equality or strictness requested. All4502 relaxed declarations are proved from actual ordered equalities; all38 cuts use ordinary binary Cases and Round.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':3,'implied_integer_variables':4502,'gated_cuts':38,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]},'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rp.stat().st_size,'rpa_sha256':sha(rp),'kernel_binary_sha256':sha(k),'kernel_runs':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        t=time.perf_counter();p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'elapsed_seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[];save()
    for name,reason in [('continuous_pivot','Uses an undeclared continuous pivot as a static INT fact.'),('missing_dependency','Drops one actual triangular integer dependency.'),('wrong_round','Replaces a gate sum INT premise with the unequal gate INT fact.'),('missing_middle','Omits one middle complete output bound/row obligation.'),('lp_integer_borrow','Borrows an integer declaration in the continuous-relaxation claim.'),('wrong_coordinate','Changes one mapped coordinate while full projection and inverse are requested.')]:
        bad=copy.deepcopy(cert)
        if name=='continuous_pivot':bad['blocks'][1]['end']['Return']['checks'][2]={'VarInt':b['var_index'][a['vars'][0]['name']]}
        elif name=='missing_dependency':bad['blocks'][1]['steps'][100]['Lin']['terms'].pop(1)
        elif name=='wrong_round':
            case=bad['blocks'][0]['steps'][0]['Cases'];next(s['Round'] for s in case['right']['steps'] if 'Round' in s)['integer']=case['integer']
        elif name=='missing_middle':bad['blocks'][1]['end']['Return']['checks'].pop(20000)
        elif name=='lp_integer_borrow':bad['blocks'][2]['steps'].append({'Lin':{'id':999999,'kind':'Int','constant':'0','terms':[[{'VarInt':0},'1']]}})
        else:bad['blocks'][0]['end']['Return']['map'][6000]['constant']='1'
        text=out/(name+'.rpa');binary=out/(name+'.rpx');text.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');p=subprocess.run([str(k),'assemble',str(text),str(binary)],capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(text),'rpx_sha256':sha(binary)});save()
    print(json.dumps({'case':d['case_id'],'status':d['status'],'counts':d['counts'],'verification':json.loads(d['kernel_runs'][-1]['stdout']),'attacks':len(d['negative_checks'])},indent=2))

if __name__=='__main__':main()
