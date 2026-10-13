#!/usr/bin/env python3
"""Complete actual forced-zero closure and zero-extension bijections for test16."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test54 import fact,box,exact
from prepare_test70 import SparseBuilder


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(228350,126512,198848,100518)
    removed={a['var_index'][n] for n in h['removed_variables_zero']};assert len(removed)==29502 and removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression() if i in removed else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])]
    p=SparseBuilder(a);zero={}
    for d in h['zero_proof_order']:
        ref=row_ref(a,d['row']);e=p.refexpr(ref);assert e[0]==0
        for n in d['new_zero_variables']:
            i=a['var_index'][n];assert i not in zero and a['vars'][i]['lower']==0;coef=e[1][i];terms=[[ref,1/coef]]
            for j,c in e[1].items():
                if i==j:continue
                if j in zero:terms.append([zero[j],-c/coef])
                else:assert a['vars'][j]['lower']==0 and c/coef>=0;terms.append([{'VarLower':j},c/coef])
            upper=p.lin('Le',terms,expression(0,{i:1}));zero[i]=p.eqpair(upper,{'VarLower':i})
    assert set(zero)==removed
    prefix=list(p.steps);facts=p.facts.copy();counter=p.counter[0];claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse
            builder=SparseBuilder(inp) if back else SparseBuilder(a,[counter],facts)
            if not back:builder.steps=list(prefix)
            checks=[]
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(e,sign),expression(-sign*value))
                    if exact('Le',wanted):check='Exact'
                    else:check={typ:next(iter(e[1]))};assert builder.refexpr(check)==wanted
                    checks.append(check)
                if integer and v['integer']:checks.append('Exact' if not e[1] else {'VarInt':next(iter(e[1]))})
            for row in out['rows']:
                n=row['name'];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if n in b['row_index']:check=row_ref(b,n);assert builder.refexpr(check)==wanted
                    elif exact(kind,wanted):check='Exact'
                    else:assert kind=='Le';check=box(builder,wanted,True)
                else:
                    ref=row_ref(a,n);terms=[[ref,F(1)]]+[[zero[i],-c] for i,c in builder.refexpr(ref)[1].items() if i in zero]
                    check=fact(builder,kind,wanted,terms,terminal=True)
                checks.append(check)
            wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1)
            terms=[] if back else [[zero[i],-c] for i,c in a['objective'][1].items() if i in zero]
            checks.append(fact(builder,'Eq',wanted,terms,terminal=True))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                checks.append(fact(builder,'Eq',wanted,[[zero[i],F(-1)]] if not back and i in zero else [],terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':228350,'target_variables':198848,'source_rows':126512,'target_rows':100518,'forced_zero_variables':29502,'ordered_zero_steps':25842,'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test16-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test16'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test16','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP zero-extension affine bijections with every retained original coordinate, exact objective equality and both full inverse identities. Every forced-zero fact follows from actual source rows and bounds; all original domains and removed rows are checked after recovery.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_zero_row','Omits a source-row premise needed to establish a zero fact.'),('wrong_zero_recovery','Recovers a proved-zero source variable with value one.'),('missing_objective_term','Omits a removed variable contribution from the exact objective proof.'),('missing_inverse','Omits an explicitly requested full composition coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_zero_row':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s)['terms'].pop(0)
            elif name=='wrong_zero_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if not e['terms'])['constant']='1'
            elif name=='missing_objective_term':next(s['Lin'] for s in reversed(bad['blocks'][0]['steps']) if 'Lin' in s and len(s['Lin']['terms'])>1000)['terms'].pop()
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
