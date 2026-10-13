#!/usr/bin/env python3
"""Actual test14 complete zero/bound cleanup and binary-conflict disaggregation."""
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
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(1166,2295,1046,1804)
    zeros={a['var_index'][d['variable']]:d for d in h['deleted_fixed_variables']};assert len(zeros)==120 and set(zeros)=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];forward=[expression(0,{i:1}) for i,j in common];reverse=[expression() if i in zeros else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])]
    bounds={a['var_index'][d['variable']]:d for d in h['retained_bound_changes']};gates={d['row']:d for d in h['binary_implication_changes']};f=SparseBuilder(a);zeroeq={}
    for i,d in zeros.items():
        ref=row_ref(a,d['witness']);e=f.refexpr(ref);assert e[0]==0 and set(e[1])=={i} and e[1][i]>0 and a['vars'][i]['lower']==0
        zeroeq[i]=f.eqpair(fact(f,'Le',expression(0,{i:1}),[[ref,1/e[1][i]]]),{'VarLower':i})
    edges={}
    for rn,d in gates.items():
        z=a['var_index'][d['center']];neighbors=[a['var_index'][n] for n in d['neighbors']];ref=row_ref(a,rn);assert f.refexpr(ref)==expression(-1,{z:1,**{j:F(1,4) for j in neighbors}})
        for name,j in zip(d['edge_rows'],neighbors):
            wanted=expression(-1,{z:1,j:1});assert a['vars'][z]['integer'] and a['vars'][z]['lower']==0 and a['vars'][z]['upper']==1 and a['vars'][j]['integer'] and a['vars'][j]['upper']==1
            edges[name]=cases_le_shared(f,wanted,z,lambda child,assumption:child.lin('Le',[[{'VarUpper':j},F(1)],[assumption,F(1)]],wanted),lambda child,assumption:child.lin('Le',[[ref,F(4)]]+[[{'VarLower':k},F(1)] for k in neighbors if k!=j]+[[assumption,F(3)]],wanted))
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            e=mapping[i]
            for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                if value is None:continue
                wanted=plus(mul(e,sign),expression(-sign*value))
                if not back and typ=='VarUpper' and next(iter(e[1])) in bounds:
                    j=next(iter(e[1]));ref=row_ref(a,bounds[j]['witness']);coefficient=p.refexpr(ref)[1][j];check=fact(p,'Le',wanted,[[ref,1/coefficient]],terminal=True)
                else:check=box(p,wanted,True)
                checks.append(check)
            if integer and v['integer']:checks.append(fact(p,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if back:
                if rn in b['row_index']:check=row_ref(b,rn);assert p.refexpr(check)==wanted
                elif exact(kind,wanted):check='Exact'
                else:
                    d=h['removed_rows'][rn]
                    if d['reason']=='box_implied':assert kind=='Le';check=box(p,wanted,True)
                    elif d['reason']=='exact_duplicate':check=row_ref(b,d['retained_row']);assert p.refexpr(check)==wanted
                    else:
                        d=gates[rn];n=len(d['neighbors']);assert n<=4;terms=[[row_ref(b,name),F(1,4)] for name in d['edge_rows']]
                        if n<4:terms.append([{'VarUpper':b['var_index'][d['center']]},1-F(n,4)])
                        check=fact(p,'Le',wanted,terms,terminal=True)
            elif rn in edges:check=edges[rn];assert p.refexpr(check)==wanted
            else:
                ref=row_ref(a,rn);check=fact(p,kind,wanted,[[ref,F(1)]]+[[zeroeq[i],-c] for i,c in p.refexpr(ref)[1].items() if i in zeros],terminal=True)
            checks.append(check)
        wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);checks.append(fact(p,'Eq',wanted,[] if back else [[zeroeq[i],-c] for i,c in a['objective'][1].items() if i in zeros],terminal=True))
        projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=[1,0,None][index]
        if inverse is not None:
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1);checks.append(fact(p,'Eq',wanted,[[zeroeq[i],F(-1)]] if not back and i in zeros else [],terminal=True))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':1166,'target_variables':1046,'source_rows':2295,'target_rows':1804,'forced_zero_continuous_variables':120,'folded_upper_bounds':118,'binary_conflicts':246,'deleted_small_aggregates':75,'retained_large_aggregates':13,'box_rows':588,'duplicate_rows':74,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test14-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test14'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test14','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer affine bijection with all retained-coordinate observations, exact objective and both inverse identities, plus objective-preserving target LP inclusion. Every added conflict follows from actual binary domains and original aggregate rows. No globally strict LP containment is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_binary_domain','Removes integrality from a conflict case split.'),('missing_neighbor_bound','Drops a nonnegative neighbor premise from the active binary branch.'),('missing_lp_center_bound','Omits a control upper bound from LP restoration of a small-degree aggregate.'),('missing_inverse','Omits a requested complete affine inverse coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_binary_domain':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['integer']=None
            elif name=='missing_neighbor_bound':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['right']['steps'][0]['Lin']['terms'].pop(1)
            elif name=='missing_lp_center_bound':next(s['Lin'] for s in bad['blocks'][2]['steps'] if 'Lin' in s and any(isinstance(r,dict) and 'VarUpper' in r and c!='1' for r,c in s['Lin']['terms']))['terms'].pop()
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
