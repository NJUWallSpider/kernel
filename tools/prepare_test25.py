#!/usr/bin/env python3
"""Actual test25 complete constant threshold and Boolean-gate elimination."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder,fix_binary
from prepare_test70 import SparseBuilder,cases_le_shared
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(11659,18442,11064,16193)
    fixed={a['var_index'][d['variable']]:d for d in h['fixed_variables']};assert len(fixed)==595 and set(fixed)=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression(F(fixed[i]['value'])) if i in fixed else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])];f=Builder(a);fixed_eq={}
    def cancel_box(builder,e,excluded=()):
        terms=[];constant=e[0]
        for j,c in e[1].items():
            if j in excluded:continue
            # Cancel terms with the bound that minimizes their row contribution.
            typ='VarLower' if c>0 else 'VarUpper';v=builder.model['vars'][j];bound=v['lower'] if c>0 else v['upper'];assert bound is not None;terms.append([{typ:j},abs(c)]);constant+=c*bound
        return terms,constant
    for i,d in fixed.items():
        value=F(d['value']);wanted=expression(-value,{i:1})
        if d['kind']=='original_bound':assert a['vars'][i]['lower']==a['vars'][i]['upper']==value;fixed_eq[i]=f.eqpair({'VarUpper':i},{'VarLower':i})
        elif d['kind']=='threshold_domain':
            assert value in (0,1) and a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
            wrong=1-value;candidates=[]
            for rn in d['rows']:
                ref=row_ref(a,rn);assert f.kind(ref)=='Le';e=f.refexpr(ref);reduced=expression(e[0]+e[1].get(i,F(0))*wrong,{j:c for j,c in e[1].items() if j!=i});terms,minimum=cancel_box(f,reduced)
                if minimum>0:candidates.append((ref,e[1].get(i,F(0)),terms,minimum))
            assert candidates,('wrong binary value needs stronger refutation',d);ref,coef,cancellation,minimum=candidates[0]
            def branch(child,assumption,chosen):
                eq=fix_binary(child,i,chosen,assumption)
                if chosen==value:return {'Witness':eq}
                contradiction=child.lin('Le',[[ref,F(1)],[eq,-coef]]+cancellation,expression(minimum));return {'Absurd':contradiction}
            fixed_eq[i]=f.cases(wanted,i,lambda child,assumption:branch(child,assumption,F(0)),lambda child,assumption:branch(child,assumption,F(1)))
        else:
            assert d['kind']=='gate' and value in (0,1);sign=F(1) if value==0 else F(-1);desired=mul(wanted,sign);proof=None
            for rn in d['rows']:
                ref=row_ref(a,rn);assert f.kind(ref)=='Le';e=f.refexpr(ref);coef=e[1].get(i,F(0))
                if not coef or coef*sign<=0:continue
                scale=sign/coef;terms=[[ref,scale]];reduced=mul(e,scale)
                for j,c in list(reduced[1].items()):
                    if j!=i and j in fixed_eq:terms.append([fixed_eq[j],-c]);reduced=plus(reduced,f.refexpr(fixed_eq[j]),-c)
                cancellation,constant=cancel_box(f,reduced,(i,));residual=constant-desired[0]
                if residual>=0:proof=f.lin('Le',terms+cancellation,desired,-residual);break
            assert proof is not None,('gate cannot be bounded',d)
            fixed_eq[i]=f.eqpair(proof,{'VarLower':i}) if value==0 else f.eqpair({'VarUpper':i},proof)
        assert f.refexpr(fixed_eq[i])==wanted
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;p=Builder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            e=mapping[i]
            for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                if value is not None:checks.append(box(p,plus(mul(e,sign),expression(-sign*value)),True))
            if integer and v['integer']:checks.append(fact(p,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if back:
                if rn in b['row_index']:check=row_ref(b,rn);assert p.refexpr(check)==wanted
                elif exact(kind,wanted):check='Exact'
                elif kind=='Le':check=box(p,wanted,True)
                else:check=p.eqpair(box(p,wanted),box(p,mul(wanted,-1)))
            else:
                ref=row_ref(a,rn);check=fact(p,kind,wanted,[[ref,F(1)]]+[[fixed_eq[i],-c] for i,c in p.refexpr(ref)[1].items() if i in fixed],terminal=True)
            checks.append(check)
        wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);checks.append(fact(p,'Eq',wanted,[] if back else [[fixed_eq[i],-c] for i,c in a['objective'][1].items() if i in fixed],terminal=True))
        projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=[1,0,None][index]
        if inverse is not None:
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1);checks.append(fact(p,'Eq',wanted,[[fixed_eq[i],F(-1)]] if not back and i in fixed else [],terminal=True))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':11659,'target_variables':11064,'source_rows':18442,'target_rows':16193,'fixed_original_domains':19,'fixed_binary_thresholds':487,'fixed_gate_outputs':89,'removed_box_rows':2249,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test25-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test25'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test25','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer constant-extension affine bijection with all retained-coordinate observations, exact objective and both inverse identities, plus target LP inclusion. Actual rows and domain bounds refute each excluded binary threshold value; checked gate rows propagate constants. No forward LP equivalence is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_binary_domain','Removes integrality from a threshold split.'),('missing_threshold_bound','Drops an actual domain bound from an impossible binary branch.'),('wrong_recovery','Changes a fixed coordinate in the reverse map.'),('missing_inverse','Omits a requested complete affine inverse coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_binary_domain':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['integer']=None
            elif name=='missing_threshold_bound':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['right']['steps'][-1]['Lin']['terms'].pop()
            elif name=='wrong_recovery':e=next(e for e in bad['blocks'][1]['end']['Return']['map'] if not e['terms']);e['constant']=str(F(e['constant'])+1)
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
