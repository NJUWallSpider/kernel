#!/usr/bin/env python3
"""Full actual alias-elimination affine bijections, checked by the RPX kernel."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test54 import fact,box,exact
from prepare_test70 import SparseBuilder


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(62529,121161,40488,90561)
    edits=h['edits'];aliases={a['var_index'][n]:a['var_index'][rep] for n,rep in edits['eliminated_variables'].items()};assert len(aliases)==22041
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    assert set(aliases)=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression(0,{b['var_index'][a['vars'][aliases.get(i,i)]['name']]:1}) for i in range(len(a['vars']))]
    witnesses={}
    for rn in edits['alias_equalities_removed']:
        ref=row_ref(a,rn);assert 'RowEq' in ref;row=a['rows'][a['row_index'][rn]];removed=[i for i in row['terms'] if i in aliases];assert len(removed)==1;i=removed[0]
        e=row_fact(row,'RowEq');c=e[1][i];assert mul(e,1/c)==expression(0,{i:1,aliases[i]:-1}) and i not in witnesses;witnesses[i]=(ref,1/c)
    assert set(witnesses)==set(aliases)
    deleted=set(a['row_index'])-set(b['row_index']);assert deleted==set(edits['alias_equalities_removed'])|set(edits['bound_redundancy_certificates'])|set(edits['nonnegative_dominance_certificates'])
    assert substitute(a['objective'],reverse)==b['objective'] and substitute(b['objective'],forward)==a['objective']
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;p=SparseBuilder(inp);checks=[]
            for i,v in enumerate(out['vars']):
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(mapping[i],sign),expression(-sign*value));checks.append(box(p,wanted,True))
                if integer and v['integer']:checks.append({'VarInt':next(iter(mapping[i][1]))})
            for row in out['rows']:
                rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if rn in b['row_index']:check=row_ref(b,rn);assert p.refexpr(check)==wanted
                    elif exact(kind,wanted):check='Exact'
                    elif rn in edits['bound_redundancy_certificates']:assert kind=='Le';check=box(p,wanted,True)
                    else:
                        assert kind=='Le';d=edits['nonnegative_dominance_certificates'][rn];ref=row_ref(b,d['retained_witness_row']);delta=plus(wanted,p.refexpr(ref),-1)
                        terms=[[ref,F(1)]]
                        for j,c in delta[1].items():assert c<0 and b['vars'][j]['lower']==0;terms.append([{'VarLower':j},-c])
                        assert delta[0]==0;check=fact(p,'Le',wanted,terms,terminal=True)
                else:
                    ref=row_ref(a,rn);terms=[[ref,F(1)]]
                    for i,c in p.refexpr(ref)[1].items():
                        if i in aliases:r,scale=witnesses[i];terms.append([r,-c*scale])
                    check=fact(p,kind,wanted,terms,terminal=True)
                checks.append(check)
            checks.append('Exact');projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                terms=[]
                if not back and i in aliases:r,c=witnesses[i];terms=[[r,-c]]
                checks.append(fact(p,'Eq',wanted,terms,terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'aliases':len(aliases),'box_redundancies':len(edits['bound_redundancy_certificates']),'dominance_redundancies':len(edits['nonnegative_dominance_certificates']),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test11-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test11'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/model_reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test11','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Full integer and LP affine bijections with all retained-coordinate observations, exact objective equality and both complete inverse identities. Actual source equalities justify every alias, while exact target box and dominance deductions restore all removed source rows.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_alias','Drops an actual alias equality from a changed retained row proof.'),('wrong_recovery','Recovers an eliminated alias with the wrong constant.'),('missing_dominance','Drops a target dominance-row premise.'),('missing_inverse','Omits one requested full inverse coordinate.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_alias':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>1)['terms'].pop()
            elif name=='wrong_recovery':bad['blocks'][1]['end']['Return']['map'][next(i for i in range(counts['source_variables']) if i not in {e['terms'][0][0] for e in cert['blocks'][0]['end']['Return']['map']})]['constant']='1'
            elif name=='missing_dominance':next(s['Lin'] for s in bad['blocks'][1]['steps'] if 'Lin' in s and any(isinstance(r,dict) and any(k.startswith('Row') for k in r) for r,c in s['Lin']['terms']))['terms'].pop(0)
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
