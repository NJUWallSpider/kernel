#!/usr/bin/env python3
"""Actual test15 singleton elimination including its exact fixed objective-offset column."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test54 import fact,box,exact


def prepare(a,b):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(4516,32,4485,32)
    removed={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']};assert len(removed)==32
    added={j for j,v in enumerate(b['vars']) if v['name'] not in a['var_index']};assert len(added)==1;offset=next(iter(added));assert b['vars'][offset]['lower']==b['vars'][offset]['upper']==1 and not b['vars'][offset]['integer']
    incidence={i:[] for i in removed}
    for ri,row in enumerate(a['rows']):
        for i in set(row['terms'])&removed:incidence[i].append(ri)
    definitions={};byrow={};reverse=[];forward=[];common=[]
    for j,v in enumerate(b['vars']):
        if j==offset:forward.append(expression(1))
        else:
            i=a['var_index'][v['name']];assert a['vars'][i]==v;forward.append(expression(0,{i:1}));common.append([i,j])
    for i,v in enumerate(a['vars']):
        if i not in removed:reverse.append(expression(0,{b['var_index'][v['name']]:1}));continue
        assert len(incidence[i])==1 and v['integer'] and v['lower']==0 and v['upper']==1
        ri=incidence[i][0];row=a['rows'][ri];pivot=row['terms'][i];assert row['sense']=='E' and pivot==1 and ri not in byrow
        terms={b['var_index'][a['vars'][j]['name']]:-c/pivot for j,c in row['terms'].items() if j!=i};reverse.append(expression(row['rhs']/pivot,terms));definitions[i]=(ri,pivot);byrow[ri]=i
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;builder=Builder(inp);checks=[]
            fixed=builder.eqpair({'VarUpper':offset},{'VarLower':offset}) if back else None
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(e,sign),expression(-sign*value))
                    if exact('Le',wanted):check='Exact'
                    elif back and i in definitions:
                        n=a['rows'][definitions[i][0]]['name']
                        if typ=='VarLower':check=row_ref(b,n);assert builder.refexpr(check)==wanted
                        else:check=box(builder,wanted,True)
                    else:check={typ:next(iter(e[1]))};assert builder.refexpr(check)==wanted
                    checks.append(check)
                if integer and v['integer']:checks.append(fact(builder,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
            for row in out['rows']:
                n=row['name'];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if a['row_index'][n] in byrow:assert exact('Eq',wanted);check='Exact'
                    else:check=row_ref(b,n);assert builder.refexpr(check)==wanted
                elif a['row_index'][n] in byrow:
                    i=byrow[a['row_index'][n]];assert kind=='Le' and typ=='RowUpper';check=fact(builder,'Le',wanted,[[row_ref(a,n),F(1)],[{'VarLower':i},F(1)]])
                else:check=row_ref(a,n);assert builder.refexpr(check)==wanted
                checks.append(check)
            residual=plus(substitute(out['objective'],mapping),inp['objective'],-1)
            terms=[[fixed,-b['objective'][1][offset]]] if back else [[{'RowEq':ri},-a['objective'][1].get(i,F(0))/pivot] for i,(ri,pivot) in definitions.items() if a['objective'][1].get(i,F(0))]
            checks.append(fact(builder,'Eq',residual,terms,terminal=True))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                residual=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                if back:terms=[[fixed,F(-1)]] if i==offset else []
                else:terms=[[{'RowEq':definitions[i][0]},-1/definitions[i][1]]] if i in definitions else []
                checks.append(fact(builder,'Eq',residual,terms,terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':4516,'target_variables':4485,'source_rows':32,'target_rows':32,'eliminated_integer_singletons':32,'explicit_fixed_offset':str(b['objective'][1][offset]),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test15-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test15'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test15','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP affine bijections, preserving all retained original coordinates and the exact objective including the actual fixed offset column. Both complete inverse compositions, all removed bounds and all original rows are proved.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('wrong_offset','Maps the actual fixed objective-offset column to zero.'),('missing_nonnegative_premise','Drops the eliminated nonnegative variable bound needed for a projected inequality.'),('wrong_recovery','Changes an eliminated singleton recovery constant.'),('missing_inverse','Omits a requested complete affine composition coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='wrong_offset':next(e for e in bad['blocks'][0]['end']['Return']['map'] if not e['terms'])['constant']='0'
            elif name=='missing_nonnegative_premise':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le')['terms'].pop()
            elif name=='wrong_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if len(e['terms'])>1)['constant']='2'
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
