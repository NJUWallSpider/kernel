#!/usr/bin/env python3
"""Exact complete test57 bounded-sum elimination proof, with all auxiliary bounds."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,expr_json,row_fact,sha
from prepare_test88 import Builder


def substitute(e,mapping):
    # The actual objective has 73,940 terms. Accumulate once instead of copying
    # a growing Python dictionary once per term; arithmetic remains Fraction.
    constant=e[0];terms={}
    for i,c in e[1].items():
        constant+=c*mapping[i][0]
        for j,q in mapping[i][1].items():terms[j]=terms.get(j,F(0))+c*q
    return expression(constant,{j:q for j,q in terms.items() if q})


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
    projection=[[j,i] for i,e in enumerate(forward) for j in e[1]];claims=[];blocks=[]
    for integer in [True,False]:
        for back in [False,True]:
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;builder=Builder(inp);checks=[]
            claim={'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in projection] if back else projection,'inverse':[1,0,3,2][len(claims)]};claims.append(claim)
            def prove(kind,e,terms):
                if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):checks.append('Exact');return
                if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:checks.append(terms[0][0]);return
                checks.append(builder.lin(kind,terms,e))
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                if back and i in removed:
                    hint=removed[i];gate=b['row_index'][hint['gate_row']];g=b['var_index'][hint['gate_variable']];row=b['rows'][gate]
                    assert row['sense']=='L' and row['rhs']==0 and row['terms'][g]==-1 and all(q==1 for j,q in row['terms'].items() if j!=g)
                    assert set(e[1])<=set(row['terms'])-{g}
                    prove('Le',plus(expression(v['lower']),e,-1),[[{'VarLower':j},c] for j,c in e[1].items()])
                    terms=[[{'RowUpper':gate},F(1)],[{'VarUpper':g},F(1)]]+[[{'VarLower':j},F(1)] for j in row['terms'] if j!=g and j not in e[1]]
                    prove('Le',plus(e,expression(-v['upper'])),terms)
                    if integer:prove('Int',e,[[{'VarInt':j},c] for j,c in e[1].items()])
                else:
                    j=next(iter(e[1]));assert e==expression(0,{j:1}) and v==inp['vars'][j]
                    checks.extend([{'VarLower':j},{'VarUpper':j}])
                    if integer:checks.append({'VarInt':j})
            for row in out['rows']:
                typ=next(iter(row_ref(out,row['name'])));e=substitute(row_fact(row,typ),mapping)
                if back:
                    terms=[] if row['name'] not in b['row_index'] else [[row_ref(b,row['name']),F(1)]]
                else:
                    original=a['rows'][a['row_index'][row['name']]];terms=[[row_ref(a,row['name']),F(1)]]
                    for i,c in row_fact(original,typ)[1].items():
                        if i in definitions:
                            ri,pivot=definitions[i];terms.append([{'RowEq':ri},-c/pivot])
                prove('Eq' if typ=='RowEq' else 'Le',e,terms)
            prove('Eq',plus(substitute(out['objective'],mapping),inp['objective'],-1),[])
            for i,j in claim['projection']:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                residual=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                prove('Eq',residual,[[{'RowEq':definitions[i][0]},-1/definitions[i][1]]] if not back and i in definitions else [])
            blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'eliminated_bounded_binary_sums':len(removed),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'steps_by_claim':[len(x['steps']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test57-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test57'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test57','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete objective-preserving integer and continuous-relaxation affine bijections; all retained coordinates preserved, all reconstructed binary-sum domains and bounds proved from actual target gate rows, and both compositions equal the identity.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_gate_upper','Omits the gate variable upper bound required to prove a reconstructed auxiliary is at most one.'),('wrong_sum_recovery','Adds one to an eliminated binary sum, violating the actual auxiliary bounds and defining equality.'),('missing_inverse','Omits a full composition obligation from an explicitly requested affine bijection.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_gate_upper':
                step=next(s['Lin'] for s in bad['blocks'][1]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le' and any('VarUpper' in r for r,c in s['Lin']['terms']));step['terms']=[t for t in step['terms'] if 'VarUpper' not in t[0]]
            elif name=='wrong_sum_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if len(e['terms'])>1)['constant']='1'
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 1\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
