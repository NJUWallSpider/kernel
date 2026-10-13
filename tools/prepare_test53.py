#!/usr/bin/env python3
"""Actual test53 epigraph load pigeonhole bounds, exact shifts and strict LP."""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test54 import fact,box


def load_cases(builder,wanted,loads,integer_refs,epigraphs,total,k=0):
    ident=builder.alloc();split=loads[k];branches=[]
    for side in (0,1):
        assumption=split if side==0 else plus(expression(1),split,-1);child=SparseBuilder(builder.model,builder.counter,assumptions=builder.assumptions+[assumption]);child.facts=ChainMap({},builder.facts);ref={'Assumption':len(builder.assumptions)}
        if side:end={'Witness':child.lin('Le',[[epigraphs[k],1],[ref,1]],wanted)}
        elif k==len(loads)-1:
            contradiction=child.lin('Le',[[total,-1]]+[[{'Assumption':j},1] for j in range(len(child.assumptions))]);e=child.refexpr(contradiction);assert not e[1] and e[0]>0;end={'Absurd':contradiction}
        else:end={'Witness':load_cases(child,wanted,loads,integer_refs,epigraphs,total,k+1)}
        branches.append({'steps':child.steps,'end':end})
    builder.steps.append({'Cases':{'id':ident,'kind':'Le','expression':expr_json(wanted),'split':expr_json(split),'integer':integer_refs[k],'left':branches[0],'right':branches[1]}});builder.facts[ident]=('Le',wanted);return {'Local':ident}


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(156,161,156,160)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];forward=[expression(0,{i:1}) for i,j in common];reverse=[expression(0,{b['var_index'][v['name']]:1}) for v in a['vars']];bounds={d['variable']:d for d in h['lower_bounds']};shifts={d['row']:(g['shift'],d['equality']) for g in h['epigraph_shifts'] for d in g['rows']};f=SparseBuilder(a);lower={}
    for i,j in common:
        av,bv=a['vars'][i],b['vars'][j];assert av['name']==bv['name'] and av['upper']==bv['upper'] and av['integer']==bv['integer'];assert av['lower']==bv['lower'] if av['name'] not in bounds else av['lower']==0 and bv['lower']==F(bounds[av['name']]['after'])
    for group in h['epigraph_shifts']:
        z=a['var_index'][group['variable']];L=F(bounds[group['variable']]['after']);B=L+5;assert not a['vars'][z]['integer'];loads=[];integers=[];epigraphs=[];summed=expression()
        for d in group['rows']:
            ref=row_ref(a,d['row']);e=f.refexpr(ref);assert e[0]==-5 and e[1][z]==-1;load=expression(0,{j:c for j,c in e[1].items() if j!=z});assert all(c.denominator==1 and c>=0 and a['vars'][j]['integer'] for j,c in load[1].items());summed=plus(summed,load);split=plus(load,expression(1-B));integer=f.lin('Int',[[{'VarInt':j},c] for j,c in split[1].items()],split,split[0]);loads.append(split);integers.append(integer);epigraphs.append(ref)
        total_terms=[]
        for j in range(26):
            ref=row_ref(a,f'R{131+j:04d}');e=f.refexpr(ref);assert e[0]==-1 and len(e[1])==5 and all(c==1 for c in e[1].values());weights={summed[1].get(v,F(0)) for v in e[1]};assert len(weights)==1;weight=weights.pop()
            if weight:total_terms.append([ref,weight])
        S=F(bounds[group['variable']]['coefficient_sum']);total=f.lin('Eq',total_terms,expression(-S,summed[1]));assert S>5*(B-1)
        lower[z]=load_cases(f,expression(L,{z:-1}),loads,integers,epigraphs,total)
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            e=mapping[i];j=next(iter(e[1]))
            for value,sign in [(v['lower'],-1),(v['upper'],1)]:
                if value is None:continue
                wanted=plus(mul(e,sign),expression(-sign*value));check=lower[j] if not back and sign==-1 and j in lower else box(p,wanted,True);assert check=='Exact' or p.refexpr(check)==wanted;checks.append(check)
            if integer and v['integer']:checks.append({'VarInt':j})
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if rn in shifts:
                shift,eq=shifts[rn];check=fact(p,kind,wanted,[[row_ref(inp,rn),1],[row_ref(inp,eq),F(shift)*(1 if back else -1)]],terminal=True)
            elif rn not in inp['row_index']:
                d=next(v for v in h['removed_equalities'] if v['row']==rn);check=fact(p,kind,wanted,[[row_ref(inp,v['row']),F(v['multiplier'])] for v in d['certificate']],terminal=True)
            else:check=row_ref(inp,rn);assert p.refexpr(check)==wanted
            checks.append(check)
        assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact');projection=[[j,i] for i,j in common] if back else common;checks+=['Exact']*len(projection);inverse=[1,0,None][index]
        if inverse is not None:checks+=['Exact']*len(inp['vars'])
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    point={'Strictness':{'inclusion_claim':2}};values=h['fractional_witness']['values'];assert set(values)==set(a['var_index'])
    return {'claims':claims,'blocks':blocks,'points':[{'claim':point,'values':[str(F(values[v['name']])) for v in a['vars']]}]},{'source_variables':156,'target_variables':156,'source_rows':161,'target_rows':160,'rounded_max_load_bounds':26,'integer_load_cases':130,'epigraph_row_shifts':130,'removed_dependent_equalities':1,'claims':3,'points':1,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test53-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test53'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n')
    d={'case_id':'test53','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete same-coordinate mixed-integer feasible-set bijection and exact objective with both complete inverse identities; target LP inclusion and an actual full 156-coordinate source-LP point outside target LP prove strict strengthening. Twenty-six lower bounds on continuous epigraph variables are proved by integer Cases on five actual integer loads and their actual fixed sum, without assuming continuous epigraph integrality. Every equality row shift, removed equality and model obligation is checked.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_load_integrality','Weakens an exhaustive integer load split to a sign split.'),('missing_fixed_sum_premise','Drops an actual assignment equality from the load-sum identity.'),('wrong_epigraph_shift','Changes the signed equality multiplier used to sparsify an actual epigraph row.'),('infeasible_strictness_point','Sets one source point epigraph below its actual lower bound.'),('missing_inverse','Omits an original-coordinate inverse obligation.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_load_integrality':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['integer']=None
            elif name=='missing_fixed_sum_premise':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Eq')['terms'].pop()
            elif name=='wrong_epigraph_shift':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le')['terms'][-1][1]='1'
            elif name=='infeasible_strictness_point':bad['points'][0]['values'][parse_mps(source)['var_index']['C0001']]='-1'
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 3\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
