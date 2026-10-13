#!/usr/bin/env python3
"""Actual large test39 balance cliques and complete dependent-row recovery."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder
from prepare_test84 import rounded


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(242736,322248,242736,313956)
    assert a['vars']==b['vars'] and a['objective']==b['objective'];n=len(a['vars']);projection=[[i,i] for i in range(n)];mapping=[expr_json(expression(0,{i:1})) for i in range(n)]
    removed={d['remove']:d for d in h['dependent_equalities']};duplicates={d['remove']:d['retain'] for d in h['duplicate_rows']};packing={d['row']:d for d in h['packing_replacements']};assert set(a['row_index'])-set(b['row_index'])==set(removed)|set(duplicates)
    structure={};f=SparseBuilder(a);forward={};rounds=0
    for rn,d in packing.items():
        ref=row_ref(a,rn);eq=row_ref(a,d['balance_row']);old=f.refexpr(ref);balance=f.refexpr(eq);target=row_fact(b['rows'][b['row_index'][rn]],'RowUpper');kept={a['var_index'][v] for v in d['kept_variables']};other={a['var_index'][v] for v in d['removed_variables']};extra=[a['var_index'][v] for v in d['extra_variable']];assert not kept&other and len(extra)<=1
        assert old==expression(-2,{i:1 for i in kept|other}) and target==expression(-1,{i:1 for i in kept})
        sign=balance[1][next(iter(kept))];assert sign in (-1,1) and balance==expression(0,{**{i:sign for i in kept},**{i:-sign for i in other},**{i:-sign for i in extra}})
        for i in kept|other|set(extra):assert a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
        terms=[[ref,F(1,2)],[eq,sign/F(2)]]
        if extra:
            terms.append([{'VarUpper':extra[0]},F(1,2)]);le=f.lin('Le',terms,expression(F(-3,2),target[1]));integer=f.lin('Int',[[{'VarInt':i},1] for i in sorted(kept)],expression(0,target[1]));forward[rn]=rounded(f,le,integer);rounds+=1
        else:forward[rn]=f.lin('Le',terms,target)
        assert f.refexpr(forward[rn])==target;structure[rn]=(sign,extra)
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);p=SparseBuilder(inp) if back else f;checks=[];recovered={}
        if back:
            for rn,d in removed.items():
                assert len(d['members'])==12 and rn in d['members'];recovered[rn]=p.lin('Eq',[[row_ref(b,member),-1] for member in d['members'] if member!=rn],row_fact(a['rows'][a['row_index'][rn]],'RowEq'))
        for i,v in enumerate(out['vars']):
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for row in out['rows']:
            rn=row['name']
            if rn in packing:
                if back:
                    sign,extra=structure[rn];eqname=packing[rn]['balance_row'];eq=recovered[eqname] if eqname in recovered else row_ref(b,eqname);check=p.lin('Le',[[row_ref(b,rn),2],[eq,-sign]]+[[{'VarLower':i},1] for i in extra],row_fact(row,'RowUpper'))
                else:check=forward[rn]
            elif back and rn in recovered:check=recovered[rn]
            elif back and rn in duplicates:
                check=row_ref(b,duplicates[rn]);assert p.refexpr(check)==row_fact(row,'RowUpper')
            else:
                assert row==inp['rows'][inp['row_index'][rn]];check=row_ref(inp,rn)
            checks.append(check)
        checks.append('Exact');checks+=['Exact']*n;inverse=[1,0,None][index]
        if inverse is not None:checks+=['Exact']*n
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    assert rounds==192
    return {'claims':claims,'blocks':blocks},{'source_variables':242736,'target_variables':242736,'source_rows':322248,'target_rows':313956,'balance_clique_replacements':1152,'integer_rounded_cliques':rounds,'restored_dependent_equalities':6564,'restored_duplicates':1728,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'steps_by_claim':[len(x['steps']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test39-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test39'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test39','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete original-coordinate mixed-integer feasible-set equality and pointwise objective equality with full identity observations and both inverse identities; objective-preserving target LP inclusion. All 1152 clique replacements,192 integer rounding arguments,6564 removed equalities,1728 duplicates,all242736 domains and every actual row are checked. No global LP strictness is asserted from a merely local witness.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_extra_binary_bound','Omits the extra binary upper bound needed for a rounded clique.'),('wrong_rounding_domain','Claims a continuous coordinate is integer in the rounding premise.'),('missing_dependent_row','Omits a retained component equality from a deleted equality reconstruction.'),('missing_reverse_nonnegativity','Drops the extra binary lower bound needed to recover an original packing row.'),('missing_inverse','Omits a complete inverse-coordinate obligation.')]:
            if name=='missing_extra_binary_bound':obj=cert['blocks'][0]['steps'][0]['Lin']['terms'];old=obj.pop();undo=lambda:obj.append(old)
            elif name=='wrong_rounding_domain':obj=next(s['Round'] for s in cert['blocks'][0]['steps'] if 'Round' in s);old=obj['integer'];obj['integer']={'VarInt':0};undo=lambda:obj.update(integer=old)
            elif name=='missing_dependent_row':obj=cert['blocks'][1]['steps'][0]['Lin']['terms'];old=obj.pop();undo=lambda:obj.append(old)
            elif name=='missing_reverse_nonnegativity':obj=next(s['Lin']['terms'] for s in cert['blocks'][1]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le' and len(s['Lin']['terms'])==3);old=obj.pop();undo=lambda:obj.append(old)
            else:obj=cert['blocks'][1]['end']['Return']['checks'];old=obj.pop();undo=lambda:obj.append(old)
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'storage':'Temporary large mutated files removed after exact hash and execution recording; deterministic recipe retained.'});path.unlink();encoded.unlink()
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
