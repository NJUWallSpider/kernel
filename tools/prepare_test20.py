#!/usr/bin/env python3
"""Actual test20 affine offsets, deleted balances and dominated thresholds."""
from pathlib import Path
from fractions import Fraction as F
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def prepare(a,b,h):
    removed={v['variable']:v for v in h['removed_variables']}
    assert set(a['var_index'])-set(b['var_index'])==set(removed)
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[]
    for v in a['vars']:
        name=v['name']
        if name in removed:
            r=removed[name]['reconstruct'];reverse.append(expression(F(r['constant']),{b['var_index'][n]:F(c) for n,c in r['coefficients'].items()}))
        else:reverse.append(expression(0,{b['var_index'][name]:1}))
    claims=[];blocks=[]
    for integer in [True,False]:
        for rev in [False,True]:
            inp,out=(b,a) if rev else (a,b);mapping=reverse if rev else forward;back=forward if rev else reverse;builder=Builder(inp);aliases={};checks=[]
            projection=[[b['var_index'][v['name']],a['var_index'][v['name']]] if rev else [a['var_index'][v['name']],b['var_index'][v['name']]] for v in b['vars']]
            claim={'reverse':rev,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]};claims.append(claim)
            if not rev:
                for name,r in removed.items():
                    i=a['var_index'][name];lift=substitute(reverse[i],forward);wanted=plus(expression(0,{i:1}),lift,-1)
                    combination=h['aggregate_balance_certificates'][name[-1]]['original_equality_combination']
                    aliases[i]=builder.lin('Eq',[[row_ref(a,n),-F(c)] for n,c in combination.items()],wanted)
            def prove(kind,wanted,terms,slack=0):
                if not wanted[1] and ((kind=='Eq' and wanted[0]==0) or (kind=='Le' and wanted[0]<=0)):
                    return 'Exact'
                if len(terms)==1 and terms[0][1]==1 and slack==0 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==wanted:return terms[0][0]
                return builder.lin(kind,terms,wanted,constant=slack)
            for i,v in enumerate(out['vars']):
                name=v['name']
                for typ,bound in [('VarLower',v['lower']),('VarUpper',v['upper'])]:
                    if bound is None:continue
                    wanted=plus(expression(bound),mapping[i],-1) if typ=='VarLower' else plus(mapping[i],expression(-bound))
                    if name in inp['var_index']:
                        j=inp['var_index'][name];assert v==inp['vars'][j];terms=[[{typ:j},F(1)]];slack=0
                    else:
                        assert rev and name in removed and typ=='VarLower' and not v['integer']
                        assert len(mapping[i][1])==1
                        j,coefficient=next(iter(mapping[i][1].items()));assert coefficient==1
                        terms=[[{'VarLower':j},F(1)]];slack=wanted[0]-builder.refexpr(terms[0][0])[0];assert slack<=0
                    checks.append(prove('Le',wanted,terms,slack))
                if integer and v['integer']:
                    assert name in inp['var_index'] and inp['vars'][inp['var_index'][name]]['integer'];checks.append('Exact')
            for row in out['rows']:
                name=row['name'];typ={'E':'RowEq','G':'RowLower','L':'RowUpper'}[row['sense']];kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping);slack=0
                if name in inp['row_index']:
                    ref=row_ref(inp,name);terms=[[ref,F(1)]]
                    if not rev:terms += [[aliases[i],-c] for i,c in builder.refexpr(ref)[1].items() if i in aliases]
                elif name in h['removed_rows']['demand_definitions']:
                    combination=h['aggregate_balance_certificates'][name[-1]]['original_equality_combination'];assert F(combination[name])==-1
                    terms=[[row_ref(inp,n),F(c)] for n,c in combination.items() if n!=name]
                elif name in h['removed_rows']['dominated_thresholds']:
                    ref=row_ref(inp,h['removed_rows']['dominated_thresholds'][name]);terms=[[ref,F(1)]]
                    slack=wanted[0]-builder.refexpr(ref)[0];assert slack<=0
                elif name in h['removed_rows']['duplicates']:terms=[[row_ref(inp,h['removed_rows']['duplicates'][name]),F(1)]]
                else:
                    assert name==h['degree_certificate']['removed_row'];terms=[[row_ref(inp,n),F(c)] for n,c in h['degree_certificate']['retained_equality_combination'].items()]
                checks.append(prove(kind,wanted,terms,slack))
            assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact');checks+=['Exact']*len(projection)
            for i,e in enumerate(back):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                checks.append(prove('Eq',wanted,[[aliases[i],F(-1)]] if i in aliases else []))
            blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test20-nomf-B1'));p.add_argument('--out',type=Path,default=Path('cases/test20'));p.add_argument('--kernel',type=Path,required=True);args=p.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target);cert=prepare(a,b,json.loads(audit.read_text()));rp=out/'proof.rpa';request=out/'request.json';rp.write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n');k=args.kernel.resolve()
    d={'case_id':'test20','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP affine bijections, all retained coordinates and every objective value preserved, both inverse identities in both domains. The24 demand offsets are proved from actual full balance combinations; no claim assumes supply equals demand.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]},'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rp.stat().st_size,'rpa_sha256':sha(rp),'kernel_binary_sha256':sha(k),'kernel_runs':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[];save()
    for name,reason in [('wrong_offset','Changes a reconstructed demand constant while preserving both inverse contracts.'),('wrong_balance','Corrupts a middle balance multiplier in a full offset derivation.'),('missing_middle','Deletes a middle original-row obligation.'),('lp_integer_borrow','Adds an integer fact to a relaxed-domain proof.'),('weakened_contract','Certificate drops objective equality while the independent caller still requires it.')]:
        bad=copy.deepcopy(cert)
        if name=='wrong_offset':
            i=a['var_index'][next(v for v in a['var_index'] if v not in b['var_index'])];bad['blocks'][1]['end']['Return']['map'][i]['constant']='0'
        elif name=='wrong_balance':bad['blocks'][0]['steps'][0]['Lin']['terms'][20][1]='0'
        elif name=='missing_middle':bad['blocks'][1]['end']['Return']['checks'].pop(15000)
        elif name=='lp_integer_borrow':bad['blocks'][2]['steps'].append({'Lin':{'id':999999,'kind':'Int','constant':'0','terms':[[{'VarInt':next(i for i,v in enumerate(a['vars']) if v['integer'])},'1']]}})
        else:bad['claims'][0]['objective']='None'
        text=out/(name+'.rpa');binary=out/(name+'.rpx');text.write_text('RPA 1\n'+json.dumps(bad,separators=(',',':'))+'\n');p=subprocess.run([str(k),'assemble',str(text),str(binary)],capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(text),'rpx_sha256':sha(binary)});save()
    print(json.dumps({'case':d['case_id'],'status':d['status'],'counts':d['counts'],'verification':json.loads(d['kernel_runs'][-1]['stdout']),'attacks':len(d['negative_checks'])},indent=2))

if __name__=='__main__':main()
