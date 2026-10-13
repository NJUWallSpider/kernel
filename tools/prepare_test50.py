#!/usr/bin/env python3
"""Complete test50 implied-integrality and row equivalence certificate."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test54 import fact,exact


def cases_int(builder,variable,split_var,left,right):
    wanted=expression(0,{variable:1});split=expression(0,{split_var:1});ident=builder.alloc();branches=[]
    for side,callback in enumerate((left,right)):
        assumption=split if side==0 else expression(1,{split_var:-1});child=Builder(builder.model,builder.counter,builder.facts,builder.assumptions+[assumption]);ref=callback(child,{'Assumption':len(builder.assumptions)})
        assert child.kind(ref)=='Int' and child.refexpr(ref)==wanted;branches.append({'steps':child.steps,'end':{'Witness':ref}})
    builder.steps.append({'Cases':{'id':ident,'kind':'Int','expression':expr_json(wanted),'split':expr_json(split),'integer':{'VarInt':split_var},'left':branches[0],'right':branches[1]}});builder.facts[ident]=('Int',wanted);return {'Local':ident}


def integrality(b,h,builder):
    known={}
    for d in h['u_integrality']:
        x=b['var_index'][d['x']];k=F(d['k']);us=[b['var_index'][n] for n in d['u_variables']];links=[row_ref(b,n) for n in d['lower_rows']];balance=row_ref(b,d['balance_row']);count=row_ref(b,d['original_count_row'])
        assert b['vars'][x]['integer'] and b['vars'][x]['lower']==0 and b['vars'][x]['upper']==1
        assert builder.refexpr(balance)==expression(0,{**{i:1 for i in us},x:-k})
        sums=[];combined=expression()
        for u,link in zip(us,links):
            assert not b['vars'][u]['integer'];e=builder.refexpr(link);s=plus(e,expression(1,{x:-1,u:1}));assert s[0]==0 and all(c==1 and b['vars'][i]['integer'] for i,c in s[1].items());sums.append(s);combined=plus(combined,s)
        assert plus(combined,expression(-k))==builder.refexpr(count)
        for pos,(u,s) in enumerate(zip(us,sums)):
            assert u not in known
            def inactive(child,assumption):
                terms=[[balance,F(1)],[assumption,k]]+[[{'VarLower':i},F(1)] for i in us if i!=u]
                upper=child.lin('Le',terms,expression(0,{u:1}));eq=child.eqpair(upper,{'VarLower':u});return child.lin('Int',[[eq,F(1)]],expression(0,{u:1}))
            def active(child,assumption):
                fixed=child.eqpair({'VarUpper':x},assumption);wanted=plus(expression(0,{u:1}),s,-1)
                terms=[[balance,F(1)],[count,F(-1)],[fixed,k-(len(us)-1)]]+[[link,F(1)] for q,link in enumerate(links) if q!=pos]
                upper=child.lin('Le',terms,wanted);lower=child.lin('Le',[[links[pos],F(1)],[assumption,F(1)]],mul(wanted,-1));eq=child.eqpair(upper,lower)
                return child.lin('Int',[[eq,F(1)]]+[[{'VarInt':i},c] for i,c in s[1].items()],expression(0,{u:1}))
            known[u]=cases_int(builder,u,x,inactive,active)
    for d in h['unit_definition_integrality']:
        i=b['var_index'][d['variable']];ref=row_ref(b,d['row']);e=builder.refexpr(ref);pivot=e[1][i];terms=[[ref,1/pivot]]+[[{'VarInt':j},-c/pivot] for j,c in e[1].items() if j!=i]
        assert i not in known and not b['vars'][i]['integer'];known[i]=builder.lin('Int',terms,expression(0,{i:1}),-e[0]/pivot)
    assert set(known)=={i for i,v in enumerate(b['vars']) if not v['integer']} and len(known)==11935
    return known


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(28926,23294,28926,20024)
    assert set(a['var_index'])==set(b['var_index']) and all(v['integer'] and v['lower']==0 and v['upper']==1 for v in a['vars'])
    assert all(v['lower']==0 and v['upper']==1 for v in b['vars'])
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];reverse=[expression(0,{b['var_index'][v['name']]:1}) for v in a['vars']]
    common=[[next(iter(e[1])),j] for j,e in enumerate(forward)];pairs={d['retained']:d['removed'] for d in h['opposite_pairs']};partners={d['removed']:d['retained'] for d in h['opposite_pairs']};aggregate={d['removed_row']:d['linear_combination'] for d in h['redundant_equalities']}
    assert set(a['row_index'])-set(b['row_index'])==set(partners)|set(aggregate)|set(h['empty_tautologies'])
    assert substitute(b['objective'],forward)==a['objective']
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;builder=Builder(inp);known=integrality(b,h,builder) if back and integer else {};checks=[]
            for i,v in enumerate(out['vars']):
                j=next(iter(mapping[i][1]));checks.extend([{'VarLower':j},{'VarUpper':j}])
                if integer and v['integer']:checks.append(known[j] if j in known else {'VarInt':j})
            for row in out['rows']:
                n=row['name'];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if not back and n in pairs:
                    ref=builder.eqpair(row_ref(a,n),row_ref(a,pairs[n]));assert builder.refexpr(ref)==wanted;check=ref
                elif back and (n in pairs or n in partners):
                    retained=partners.get(n,n);ref={'RowEq':b['row_index'][retained]};e=builder.refexpr(ref);scale=F(1) if e==wanted else F(-1);check=fact(builder,'Le',wanted,[[ref,scale]])
                elif back and n in aggregate:check=fact(builder,'Eq',wanted,[[row_ref(b,source),F(c)] for source,c in aggregate[n].items()])
                elif exact(kind,wanted):check='Exact'
                else:check=row_ref(inp,n);assert builder.refexpr(check)==wanted and builder.kind(check)==kind
                checks.append(check)
            assert plus(substitute(out['objective'],mapping),inp['objective'],-1)==expression();checks.append('Exact')
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            checks.extend(['Exact']*len(inp['vars']))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':28926,'target_variables':28926,'source_rows':23294,'target_rows':20024,'implied_integrality_variables':11935,'conditional_groups':320,'opposite_row_pairs':320,'aggregate_equalities':10,'empty_tautologies':2940,'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test50-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test50'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/model_reformulated.mps';audit=run/'output/audit.json';witness=run/'output/proof_certificates.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(witness.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test50','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_hints':{'path':str(witness),'sha256':sha(witness)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete identity correspondence for all original coordinates and the objective, in integer and continuous-relaxation modes, including full inverse identities. All11935 removed integer declarations are recovered from actual target constraints with ordinary integer Cases/Lin rules.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('continuous_split','Attempts to use an explicitly relaxed coordinate as an integer split premise.'),('missing_active_balance','Omits the actual balance equality from an active-case integrality proof.'),('wrong_opposite_pair','Repeats the same inequality instead of proving its opposite.'),('missing_inverse','Omits one requested full identity composition coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='continuous_split':step=next(s['Cases'] for s in bad['blocks'][1]['steps'] if 'Cases' in s);step['integer']={'VarInt':step['expression']['terms'][0][0]}
            elif name=='missing_active_balance':branch=next(s['Cases'] for s in bad['blocks'][1]['steps'] if 'Cases' in s)['right'];next(s['Lin'] for s in branch['steps'] if 'Lin' in s and s['Lin']['kind']=='Le')['terms'].pop(0)
            elif name=='wrong_opposite_pair':step=next(s['EqPair'] for s in bad['blocks'][0]['steps'] if 'EqPair' in s);step['negative']=step['positive']
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
