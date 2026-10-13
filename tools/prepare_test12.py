#!/usr/bin/env python3
"""Complete actual forced-zero closure and zero-extension bijections for test12."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test54 import fact,box,exact
from prepare_test70 import SparseBuilder


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(7195,426,6200,310)
    removed={a['var_index'][n] for n in h['removed_variables']};assert len(removed)==995 and removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression() if i in removed else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])]
    p=SparseBuilder(a);zero={};containments=0
    for round_hint in h['fixing_rounds']:
        previous=dict(zero);pairs={}
        for d in round_hint['fixings']:
            i=a['var_index'][d['variable']];assert i not in zero and d['value']==0;small=d['witness']['smaller'];large=d['witness']['larger'];pair=(small,large)
            if pair not in pairs:
                sr=row_ref(a,small);lr=row_ref(a,large);assert 'RowEq' in sr and 'RowEq' in lr;e=plus(p.refexpr(lr),p.refexpr(sr),-1);terms=[[lr,F(1)],[sr,F(-1)]]
                for j,c in e[1].items():
                    if j in previous:terms.append([previous[j],-c])
                wanted=expression(e[0],{j:c for j,c in e[1].items() if j not in previous});assert wanted[0]==0 and wanted[1] and all(c==1 for c in wanted[1].values())
                pairs[pair]=p.lin('Eq',terms,wanted);containments+=1
            eq=pairs[pair];e=p.refexpr(eq);assert e[1][i]==1
            upper=p.lin('Le',[[eq,F(1)]]+[[{'VarLower':j},c] for j,c in e[1].items() if j!=i],expression(0,{i:1}));zero[i]=p.eqpair(upper,{'VarLower':i})
    assert set(zero)==removed
    prefix=list(p.steps);facts=p.facts.copy();counter=p.counter[0];claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse
            builder=SparseBuilder(inp) if back else SparseBuilder(a,[counter],facts)
            if not back:builder.steps=list(prefix)
            checks=[];recovered={}
            def recover_row(name):
                if name in recovered:return recovered[name]
                wanted=substitute(row_fact(a['rows'][a['row_index'][name]],'RowEq'),reverse)
                if name in b['row_index']:ref=row_ref(b,name);assert builder.refexpr(ref)==wanted
                elif name in h['duplicate_rows']:ref=recover_row(h['duplicate_rows'][name]);assert builder.refexpr(ref)==wanted
                else:
                    coeff=h['linear_relations'][name]['coefficients'];assert coeff[name]==1 and all(r in b['row_index'] for r in coeff if r!=name)
                    ref=builder.lin('Eq',[[row_ref(b,r),-F(c)] for r,c in coeff.items() if r!=name],wanted)
                recovered[name]=ref;return ref
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
                n=row['name'];assert row['sense']=='E';wanted=substitute(row_fact(row,'RowEq'),mapping)
                if back:check=recover_row(n)
                else:
                    ref=row_ref(a,n);terms=[[ref,F(1)]]+[[zero[i],-c] for i,c in builder.refexpr(ref)[1].items() if i in zero];check=fact(builder,'Eq',wanted,terms,terminal=True)
                checks.append(check)
            wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);terms=[] if back else [[zero[i],-c] for i,c in a['objective'][1].items() if i in zero];checks.append(fact(builder,'Eq',wanted,terms,terminal=True))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1);checks.append(fact(builder,'Eq',wanted,[[zero[i],F(-1)]] if not back and i in zero else [],terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':7195,'target_variables':6200,'source_rows':426,'target_rows':310,'forced_zeros':995,'distinct_containment_premises':containments,'duplicates':83,'signed_linear_dependencies':33,'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test12-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test12'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test12','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP zero-extension affine bijections with every retained original coordinate, exact objective equality and both full inverse identities. Actual equal-RHS containment rows establish the zeros; actual retained rows and signed linear combinations restore every removed row.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_zero_row','Omits a source-row premise needed to establish a zero fact.'),('wrong_zero_recovery','Recovers a proved-zero source variable with value one.'),('missing_linear_relation','Omits a retained-row term needed to reconstruct a removed equality.'),('missing_inverse','Omits an explicitly requested full composition coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_zero_row':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s)['terms'].pop(0)
            elif name=='wrong_zero_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if not e['terms'])['constant']='1'
            elif name=='missing_linear_relation':next(s['Lin'] for s in bad['blocks'][1]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>1)['terms'].pop()
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
