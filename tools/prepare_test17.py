#!/usr/bin/env python3
"""Actual test17 complete positive-row redundancy and weighted binary order-chain reformulation."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test70 import SparseBuilder,cases_le_shared
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(57756,3757,57756,1765)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression(0,{b['var_index'][v['name']]:1}) for v in a['vars']];f=SparseBuilder(a);adjacent={}
    for rn,d in h['row_replacements'].items():
        ref=row_ref(a,rn);e=f.refexpr(ref);assert e[0]==0 and len(e[1])==2;(x,c)=next((i,c) for i,c in e[1].items() if c>0);(y,neg)=next((i,c) for i,c in e[1].items() if c<0);n=-neg;assert n>c>0
        wanted=substitute(row_fact(b['rows'][b['row_index'][rn]],'RowUpper'),forward);assert wanted==expression(0,{x:1,y:-1})
        adjacent[rn]=cases_le_shared(f,wanted,y,lambda child,assumption:child.lin('Le',[[ref,1/c],[assumption,n/c-1]],wanted),lambda child,assumption:child.lin('Le',[[{'VarUpper':x},F(1)],[assumption,F(1)]],wanted))
    order={**h['pair_row_deletions'],**{n:d['reverse_certificate'] for n,d in h['row_replacements'].items()}};claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            j=next(iter(mapping[i][1]));assert v['integer'] and v['lower']==0 and v['upper']==1;checks.extend([{'VarLower':j},{'VarUpper':j}])
            if integer:checks.append({'VarInt':j})
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));wanted=substitute(row_fact(row,typ),mapping)
            if not back and rn in adjacent:check=adjacent[rn];assert p.refexpr(check)==wanted
            elif back and rn in order:
                d=order[rn];terms=[[row_ref(b,n),F(d['chain_multiplier'])] for n in d['chain_rows']]+[[{'VarLower':b['var_index'][d['lower_bound_variable']]},F(d['lower_bound_multiplier'])]];check=fact(p,'Le',wanted,terms,terminal=True)
            elif back and rn in h['positive_row_deletions']:
                d=h['positive_row_deletions'][rn];terms=[[row_ref(b,d['source_row']),F(d['source_multiplier'])]]
                if d.get('gate_upper_bound'):terms.append([{'VarUpper':b['var_index'][d['gate_upper_bound']]},F(d['source_multiplier'])])
                raw=expression()
                for r,c in terms:raw=plus(raw,p.refexpr(r),c)
                delta=plus(wanted,raw,-1);assert delta[0]==0 and all(c<0 for c in delta[1].values())
                terms.extend([[{'VarLower':j},-c] for j,c in delta[1].items()]);check=fact(p,'Le',wanted,terms,terminal=True)
            else:check=row_ref(inp,rn);assert p.refexpr(check)==wanted
            checks.append(check)
        assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact');projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=[1,0,None][index]
        if inverse is not None:checks.extend(['Exact']*len(inp['vars']))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':57756,'target_variables':57756,'source_rows':3757,'target_rows':1765,'positive_row_deletions':1046,'adjacent_binary_replacements':44,'restored_original_order_rows':990,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test17-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test17'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test17','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete same-coordinate integer affine bijection with exact objective and both inverse identities, plus target LP inclusion. Original adjacent weighted orders imply the binary chain by checked Cases; all removed positive and transitive rows are restored by explicit target-row/bound combinations. No global LP strictness is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_binary_domain','Removes integrality from a binary order split.'),('missing_order_bound','Drops the nonnegative final-node bound restoring an original weighted order.'),('missing_positive_bound','Omits a domain premise in a positive capacity restoration.'),('missing_inverse','Omits a requested complete affine inverse coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_binary_domain':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['integer']=None
            elif name=='missing_order_bound':bad['blocks'][1]['steps'][0]['Lin']['terms'].pop()
            elif name=='missing_positive_bound':next(s['Lin'] for s in bad['blocks'][2]['steps'] if 'Lin' in s and any(isinstance(r,dict) and 'VarUpper' in r for r,c in s['Lin']['terms']))['terms'].pop()
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
