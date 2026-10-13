#!/usr/bin/env python3
"""Full actual alias/fixed/unused elimination projections, checked by the RPX kernel."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test54 import fact,box,exact
from prepare_test70 import SparseBuilder


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(33242,49565,26625,37573)
    edits=h['modifications'];aliases={a['var_index'][n]:a['var_index'][d['target']] for n,d in edits['alias_eliminations'].items()};zeros={a['var_index'][n] for n in edits['fixed_zero_eliminations']};unused={a['var_index'][n] for n in edits['unused_zero_objective_binary_eliminations']};removed=set(aliases)|zeros|unused
    assert (len(aliases),len(zeros),len(unused),len(removed))==(5663,477,477,6617)
    assert removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    assert not (unused&set(a['objective'][1])) and all(not (unused&set(row['terms'])) for row in a['rows'])
    for i in unused:assert a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression() if i in zeros|unused else expression(0,{b['var_index'][a['vars'][aliases.get(i,i)]['name']]:1}) for i in range(len(a['vars']))]
    witnesses={}
    for name,d in edits['alias_eliminations'].items():
        i=a['var_index'][name];ref=row_ref(a,d['defining_row']);assert 'RowEq' in ref;e=row_fact(a['rows'][ref['RowEq']],'RowEq');c=e[1][i];assert mul(e,1/c)==expression(0,{i:1,aliases[i]:-1});witnesses[i]=(ref,1/c)
    deleted=set(a['row_index'])-set(b['row_index']);assert deleted=={d['defining_row'] for d in edits['alias_eliminations'].values()}|set(edits['bound_implied_row_deletions'])|set(edits['parallel_row_deletions'])
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp);checks=[];zeroeq={}
            if not back:
                for i in sorted(zeros):assert a['vars'][i]['lower']==a['vars'][i]['upper']==0;zeroeq[i]=p.eqpair({'VarUpper':i},{'VarLower':i})
            def equality_terms(e):
                terms=[]
                for i,c in e[1].items():
                    if i in aliases:r,scale=witnesses[i];terms.append([r,-c*scale])
                    elif i in zeros:terms.append([zeroeq[i],-c])
                    else:assert i not in unused
                return terms
            for i,v in enumerate(out['vars']):
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(mapping[i],sign),expression(-sign*value));checks.append(box(p,wanted,True))
                if integer and v['integer']:checks.append('Exact' if not mapping[i][1] else {'VarInt':next(iter(mapping[i][1]))})
            for row in out['rows']:
                rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if rn in b['row_index']:check=row_ref(b,rn);assert p.refexpr(check)==wanted
                    elif exact(kind,wanted):check='Exact'
                    elif rn in edits['bound_implied_row_deletions']:assert kind=='Le';check=box(p,wanted,True)
                    else:
                        d=edits['parallel_row_deletions'][rn];ref=row_ref(b,d['witness']);check=fact(p,kind,wanted,[[ref,F(d['scale'])]],terminal=True)
                else:
                    ref=row_ref(a,rn);check=fact(p,kind,wanted,[[ref,F(1)]]+equality_terms(p.refexpr(ref)),terminal=True)
                checks.append(check)
            residual=plus(substitute(out['objective'],mapping),inp['objective'],-1);checks.append(fact(p,'Eq',residual,[] if back else equality_terms(a['objective']),terminal=True))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':None});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':33242,'target_variables':26625,'source_rows':49565,'target_rows':37573,'aliases':5663,'fixed_zeros':477,'unused_zero_cost_binary_variables':477,'box_redundancies':6323,'duplicate_redundancies':6,'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test43-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test43'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test43','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Four complete objective-preserving integer and LP projection directions with every retained-coordinate observation. Aliases and fixed zeros follow from actual equalities and domains; unused zero-cost binaries are restored as zero. Every source domain and removed row is checked. No bijection is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_alias','Drops an actual alias equality from a changed retained row proof.'),('wrong_mapping','Changes a retained coordinate in the reverse mapping.'),('wrong_fixed_zero','Replaces an upper-bound premise in a fixed-zero equality by its lower bound.'),('missing_projection','Omits one requested retained-coordinate observation.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_alias':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>1)['terms'].pop()
            elif name=='wrong_mapping':next(e for e in bad['blocks'][1]['end']['Return']['map'] if e['terms'])['constant']='1'
            elif name=='wrong_fixed_zero':eq=next(s['EqPair'] for s in bad['blocks'][0]['steps'] if 'EqPair' in s);eq['positive']=eq['negative']
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
