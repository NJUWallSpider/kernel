#!/usr/bin/env python3
"""Actual test35 fixed/affine elimination including all original bounds and normalization dependencies."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(4456,1667,3510,675)
    removed={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']};assert len(removed)==946
    fixed={a['var_index'][n]:d for n,d in h['fixed_variables'].items()};defs={a['var_index'][n]:d for n,d in h['affine_eliminations'].items()};assert removed==set(fixed)|set(defs)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[]
    for i,v in enumerate(a['vars']):
        if i in fixed:e=expression(F(fixed[i]['value']))
        elif i in defs:e=expression(F(defs[i]['constant']),{b['var_index'][n]:F(c) for n,c in defs[i]['coefficients'].items()})
        else:e=expression(0,{b['var_index'][v['name']]:1})
        reverse.append(e)
    p=Builder(a);equalities={};visiting=set()
    def prove(i):
        if i in equalities:return equalities[i]
        assert i not in visiting;visiting.add(i);d=fixed.get(i,defs.get(i));rn=d.get('row',d.get('defining_row'));ref=row_ref(a,rn);assert 'RowEq' in ref;e=p.refexpr(ref);pivot=e[1][i];terms=[[ref,1/pivot]]
        for j,c in e[1].items():
            if j!=i and j in removed:terms.append([prove(j),-c/pivot])
        wanted=plus(expression(0,{i:1}),substitute(reverse[i],forward),-1);equalities[i]=fact(p,'Eq',wanted,terms);visiting.remove(i);return equalities[i]
    for i in sorted(removed):prove(i)
    prefix=list(p.steps);facts=p.facts.copy();counter=p.counter[0];dependencies={d['removed']:d['zero_linear_combination'] for d in h['equality_dependency_witnesses']};claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;builder=Builder(inp) if back else Builder(a,[counter],facts)
            if not back:builder.steps=list(prefix)
            checks=[]
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is not None:checks.append(box(builder,plus(mul(e,sign),expression(-sign*value)),True))
                if integer and v['integer']:checks.append(fact(builder,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
            for row in out['rows']:
                n=row['name'];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if n in b['row_index']:check=row_ref(b,n);assert builder.refexpr(check)==wanted
                    elif exact(kind,wanted):check='Exact'
                    elif n in dependencies:
                        cs=dependencies[n];pivot=F(cs[n]);check=fact(builder,'Eq',wanted,[[row_ref(b,r),-F(c)/pivot] for r,c in cs.items() if r!=n])
                    else:assert kind=='Le';check=box(builder,wanted,True)
                else:
                    ref=row_ref(a,n);check=fact(builder,kind,wanted,[[ref,F(1)]]+[[equalities[i],-c] for i,c in builder.refexpr(ref)[1].items() if i in removed],terminal=True)
                checks.append(check)
            wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);checks.append(fact(builder,'Eq',wanted,[] if back else [[equalities[i],-c] for i,c in a['objective'][1].items() if i in removed],terminal=True))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1);checks.append(fact(builder,'Eq',wanted,[[equalities[i],F(-1)]] if not back and i in removed else [],terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':4456,'target_variables':3510,'source_rows':1667,'target_rows':675,'fixed_variables':810,'affine_definitions':136,'normalization_dependencies':45,'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test35-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test35'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test35','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP affine bijections, preserving all retained original coordinates and the exact substituted objective. Both complete inverse compositions, all eliminated integer domains and bounds, and every removed source row are proved.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_definition','Omits a premise needed to establish an eliminated affine coordinate.'),('wrong_recovery','Changes an eliminated variable recovery constant.'),('missing_dependency','Drops a retained equality from a removed normalization proof.'),('missing_inverse','Omits a requested complete affine composition coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_definition':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>1)['terms'].pop()
            elif name=='wrong_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if not e['terms'])['constant']='2'
            elif name=='missing_dependency':next(s['Lin'] for s in bad['blocks'][1]['steps'] if 'Lin' in s and s['Lin']['kind']=='Eq' and len(s['Lin']['terms'])>1)['terms'].pop()
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
