#!/usr/bin/env python3
"""Actual test76 capacity rounding and exact auxiliary substitution."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test54 import fact,box
from prepare_test84 import rounded


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(1758,351,1682,301)
    removed_zero={a['var_index'][n] for n in h['removed_zero_variables']};aux={a['var_index'][n] for n in h['removed_auxiliary_variables']};assert len(removed_zero)==26 and len(aux)==50
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    assert removed_zero|aux=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    f=SparseBuilder(a);chain=f.lin('Eq',[[row_ref(a,'c00_1'),1]]+[[row_ref(a,f'c01_{k}'),1] for k in range(1,96)])
    cap=f.lin('Le',[[chain,-1]]+[[row_ref(a,f'c04_{j}'),-F(w)] for j,w in h['zero_choice_proof']['mandatory_groups'].items()]+[[{'VarUpper':a['var_index']['z#95']},1]])
    capexpr=f.refexpr(cap);assert capexpr[0]==-4 and all(c>0 for c in capexpr[1].values());zero={}
    for i in sorted(removed_zero):
        assert capexpr[1][i]==5 and a['vars'][i]['integer'];le=f.lin('Le',[[cap,F(1,5)]]+[[{'VarLower':j},c/F(5)] for j,c in capexpr[1].items() if j!=i],expression(F(-4,5),{i:1}));zero[i]=f.eqpair(rounded(f,le,{'VarInt':i}),{'VarLower':i})
    forward=[expression(0,{i:1}) for i,j in common];reverse=[None]*len(a['vars']);definitions={};recoveries={};groups={}
    for i,j in common:reverse[i]=expression(0,{j:1})
    for i in removed_zero:reverse[i]=expression()
    for key,hint in h['substitution_certificates'].items():
        i=a['var_index'][hint['eliminated_variable']];rn=f'c02_{key}';hn=f'c04_{key}';ref=row_ref(a,rn);e=f.refexpr(ref);assert e[0]==0 and e[1][i]==1 and i in aux
        reverse[i]=expression(0,{b['var_index'][a['vars'][j]['name']]:-c for j,c in e[1].items() if j!=i and j not in removed_zero});definitions[i]=(rn,hn);groups[f'c03_{key}']=(rn,hn,F(hint['original_bound_lower']))
        expected=plus(substitute(reverse[i],forward),expression(0,{i:1}),-1);recoveries[i]=f.lin('Eq',[[ref,-1]]+[[zero[j],c] for j,c in e[1].items() if j in removed_zero],expected)
    assert all(e is not None for e in reverse)
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            e=mapping[i]
            for value,sign in [(v['lower'],-1),(v['upper'],1)]:
                if value is None:continue
                wanted=plus(mul(e,sign),expression(-sign*value))
                if back and i in aux:
                    rn,hn=definitions[i];href=row_ref(b,hn);assert set(e[1])<=set(p.refexpr(href)[1]);weights={j:(value-c if sign==1 else c-value) for j,c in e[1].items()};assert all(c>=0 for c in weights.values());check=fact(p,'Le',wanted,[[href,sign*value]]+[[{'VarLower':j},c] for j,c in weights.items() if c],terminal=True)
                else:check=box(p,wanted,True)
                checks.append(check)
            if integer and v['integer']:checks.append(fact(p,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if not back:
                terms=[[row_ref(a,rn),1]]
                if rn in groups:
                    dn,hn,lower=groups[rn];terms += [[row_ref(a,dn),-1],[row_ref(a,hn),-lower]]
                raw=expression()
                for r,c in terms:raw=plus(raw,p.refexpr(r),c)
                terms += [[zero[i],-c] for i,c in raw[1].items() if i in removed_zero];check=fact(p,kind,wanted,terms,terminal=True)
            elif rn in h['removed_rows']:assert wanted==expression();check='Exact'
            elif rn in groups:
                dn,hn,lower=groups[rn];check=fact(p,kind,wanted,[[row_ref(b,rn),1],[row_ref(b,hn),lower]],terminal=True)
            else:check=row_ref(b,rn);assert p.refexpr(check)==wanted
            checks.append(check)
        wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);assert wanted==expression();checks.append('Exact')
        projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=[1,0,None][index]
        if inverse is not None:
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                terms=[[zero[i],-1]] if not back and i in removed_zero else [[recoveries[i],1]] if not back and i in aux else []
                checks.append(fact(p,'Eq',wanted,terms,terminal=True))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':1758,'target_variables':1682,'source_rows':351,'target_rows':301,'capacity_binary_zeros':26,'continuous_affine_substitutions':50,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test76-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test76'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test76','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer affine bijection with all retained coordinates, pointwise objective equality and both inverse identities, plus target LP inclusion. Twenty-six binary zeros are proved from actual capacity-chain equations, mandatory one-hot contributions, explicit capacity bound, and integer rounding. Fifty continuous auxiliaries are uniquely recovered and every eliminated bound and replaced row checked. No forward LP equality or strictness claim.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_capacity_bound','Omits the actual capacity bound from the common mandatory-load proof.'),('wrong_rounding_domain','Uses a continuous time coordinate as the rounding integrality premise.'),('wrong_auxiliary_recovery','Changes one recovered continuous coordinate.'),('missing_auxiliary_bound','Drops a one-hot premise needed to bound a recovered auxiliary.'),('missing_inverse','Omits one full inverse identity.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_capacity_bound':bad['blocks'][0]['steps'][1]['Lin']['terms'].pop()
            elif name=='wrong_rounding_domain':next(s['Round'] for s in bad['blocks'][0]['steps'] if 'Round' in s)['integer']={'VarInt':parse_mps(source)['var_index']['s#1']}
            elif name=='wrong_auxiliary_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if len(e['terms'])>1)['constant']='1'
            elif name=='missing_auxiliary_bound':bad['blocks'][1]['steps'][0]['Lin']['terms'].pop(0)
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
