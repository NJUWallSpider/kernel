#!/usr/bin/env python3
"""Untrusted exact preparation of test19 complete bijection and strict LP image."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder
from prepare_test84 import rounded
from prepare_test71 import evaluate


def cases_le(b,desired,var,left,right):
    split=expression(0,{var:1});ident=b.alloc();branches=[]
    for side,callback in enumerate((left,right)):
        assumption=split if side==0 else expression(1,{var:-1})
        child=Builder(b.model,b.counter,b.facts,b.assumptions+[assumption])
        ref=callback(child,{'Assumption':len(b.assumptions)})
        assert child.kind(ref)=='Le' and child.refexpr(ref)==desired
        branches.append({'steps':child.steps,'end':{'Witness':ref}})
    b.steps.append({'Cases':{'id':ident,'kind':'Le','expression':expr_json(desired),'split':expr_json(split),'integer':{'VarInt':var},'left':branches[0],'right':branches[1]}})
    b.facts[ident]=('Le',desired);return {'Local':ident}


def prepare(a,b,h):
    assert len(a['vars'])==1462 and len(b['vars'])==1459 and len(a['rows'])==1655 and len(b['rows'])==1668
    removed=set(h['removed_columns']);assert set(a['var_index'])-set(b['var_index'])==removed
    assert set(a['row_index'])-set(b['row_index'])==set(h['removed_rows'])
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[];definition={}
    for v in a['vars']:
        name=v['name'];i=a['var_index'][name]
        if name not in removed:
            assert v==b['vars'][b['var_index'][name]];reverse.append(expression(0,{b['var_index'][name]:1}));continue
        assert not v['integer'] and v['lower'] is None and v['upper'] is None
        matches=[ri for ri in h['removed_rows'] if a['rows'][a['row_index'][ri]]['terms'].get(i)==1]
        assert len(matches)==1;ri=a['row_index'][matches[0]];r=a['rows'][ri];assert r['sense']=='E' and r['rhs']==0
        definition[i]=ri;reverse.append(expression(0,{b['var_index'][a['vars'][j]['name']]:-c for j,c in r['terms'].items() if j!=i}))
    assert substitute(a['objective'],reverse)==b['objective']
    changes={x['row']:x for x in h['coefficient_changes']};assert len(changes)==210
    newrows={c['new_row'] for c in h['cycle_certificates']}
    assert set(b['row_index'])-set(a['row_index'])==newrows
    for row in b['rows']:
        if row['name'] in newrows:continue
        original=a['rows'][a['row_index'][row['name']]];expected=substitute(row_fact(original,next(iter(row_ref(a,row['name'])))),reverse)
        if row['name'] in changes:
            ch=changes[row['name']];assert original['terms'][a['var_index'][ch['column']]]==F(ch['old'])
            expected=plus(expected,expression(0,{b['var_index'][ch['column']]:F(ch['new'])-F(ch['old'])}))
        assert expected==row_fact(row,next(iter(row_ref(b,row['name']))))
    projection=[[j,i] for i,e in enumerate(forward) for j in e[1]]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':1},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in projection],'inverse':0},
            {'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[j,i] for i,j in projection],'inverse':None}]
    f=Builder(a);cycle_eq={};prod_cycle={};upper={};activation={};changed={};cuts={}
    for c in h['cycle_certificates']:
        prod=[a['var_index'][n] for n in c['production']];D=F(c['total_demand'])
        eq=f.lin('Eq',[[row_ref(a,n),F(-1)] for n in c['rows']],expression(-D,{j:1 for j in prod}))
        cycle_eq[c['index']]=eq
        for j in prod:assert j not in prod_cycle;prod_cycle[j]=c
    for name,hint in h['production_bound_certificates'].items():
        j=a['var_index'][name];c=prod_cycle[j];D=F(c['total_demand']);U=min(F(4500),D)
        if D<4500:terms=[[cycle_eq[c['index']],F(1)]]+[[{'VarLower':a['var_index'][n]},F(1)] for n in c['production'] if n!=name]
        else:terms=[[row_ref(a,hint['row']),F(1)],[{'VarLower':a['var_index'][hint['inventory']]},F(1)]]
        upper[j]=f.lin('Le',terms,expression(-U,{j:1}))
        # Find the actual unique activation row by its complete two-column support.
        y=a['var_index'][c['activation'][c['production'].index(name)]]
        rows=[r['name'] for r in a['rows'] if r['sense']=='L' and r['rhs']==0 and r['terms']=={j:F(1),y:F(-4500)}]
        assert len(rows)==1;activation[j]=rows[0]
    for name,ch in changes.items():
        z=a['var_index'][ch['column']];B=-F(ch['new']);old=-F(ch['old']);original=row_ref(a,name)
        prod=[a['var_index'][ch['production']]] if isinstance(ch['production'],str) else [a['var_index'][n] for n in ch['production']]
        desired=expression(0,{**{j:F(1) for j in prod},z:-B})
        assert f.refexpr(original)==expression(0,{**{j:F(1) for j in prod},z:-old})
        assert sum(-f.refexpr(upper[j])[0] for j in prod)==B
        changed[name]=cases_le(f,desired,z,
            lambda child,s,original=original,old=old,B=B:child.lin('Le',[[original,F(1)],[s,old-B]],desired),
            lambda child,s,prod=prod,B=B:child.lin('Le',[[upper[j],F(1)] for j in prod]+[[s,B]],desired))
    for c in h['cycle_certificates']:
        M=F(c['production_upper']);prod=[a['var_index'][n] for n in c['production']];ys=[a['var_index'][n] for n in c['activation']]
        terms=[[changed.get(activation[j],row_ref(a,activation[j])),1/M] for j in prod]+[[cycle_eq[c['index']],-1/M]]
        le=f.lin('Le',terms,expression(F(c['total_demand'])/M,{y:-1 for y in ys}))
        integer=f.lin('Int',[[{'VarInt':y},F(-1)] for y in ys],expression(0,{y:-1 for y in ys}))
        cuts[c['new_row']]=rounded(f,le,integer)
        assert f.refexpr(cuts[c['new_row']])==substitute(row_fact(b['rows'][b['row_index'][c['new_row']]],'RowLower'),forward)
    def finish(builder,out,mapping,claim,rowterms,objterms,othermap):
        checks=[]
        def prove(kind,e,terms):
            if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):checks.append('Exact');return
            if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:checks.append(terms[0][0]);return
            checks.append(builder.lin(kind,terms,e))
        for i,v in enumerate(out['vars']):
            for kind,enabled in [('VarLower',v['lower'] is not None),('VarUpper',v['upper'] is not None),('VarInt',claim['output_integers'] and v['integer'])]:
                if not enabled:continue
                assert mapping[i][0]==0 and len(mapping[i][1])==1
                j=next(iter(mapping[i][1]));assert mapping[i][1][j]==1
                e=plus(expression(v['lower']),mapping[i],-1) if kind=='VarLower' else plus(mapping[i],expression(-v['upper'])) if kind=='VarUpper' else mapping[i]
                prove('Int' if kind=='VarInt' else 'Le',e,[[{kind:j},F(1)]])
        for row in out['rows']:
            typ=next(iter(row_ref(out,row['name'])));prove('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),rowterms(row['name']))
        prove('Eq',plus(substitute(out['objective'],mapping),builder.model['objective'],-1),objterms)
        for i,j in claim['projection']:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        if claim['inverse'] is not None:
            for i,e in enumerate(othermap):
                residual=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                prove('Eq',residual,[[{'RowEq':definition[i]},F(-1)]] if i in definition and not claim['reverse'] else [])
        return {'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}
    blocks=[finish(f,b,forward,claims[0],lambda n:[[changed.get(n,cuts.get(n,row_ref(a,n) if n in a['row_index'] else None)),F(1)]],[[{'RowEq':ri},F(-1)] for ri in definition.values()],reverse)]
    for claim in claims[1:]:
        r=Builder(b)
        def rows(n):
            if n in h['removed_rows']:return []
            result=[[row_ref(b,n),F(1)]]
            if n in changes:
                ch=changes[n];result.append([{'VarLower':b['var_index'][ch['column']]},F(ch['new'])-F(ch['old'])])
            return result
        blocks.append(finish(r,a,reverse,claim,rows,[],forward))
    values=[F(h['original_relaxation_witness'][v['name']]) for v in a['vars']]
    original_eval=evaluate(a,values,False);target_values=[sum(c*values[i] for i,c in e[1].items())+e[0] for e in forward];target_eval=evaluate(b,target_values,False)
    assert not original_eval['violations'] and len(target_eval['violations'])==226 and original_eval['objective']==target_eval['objective']
    separator=b['rows'][b['row_index']['CYC0001']];terms=[[row_ref(b,'CYC0001'),'1']]
    # Fiber rows are in reverse claim projection order, namely target variable order.
    for i,c in row_fact(separator,'RowLower')[1].items():terms.append([{'RowEq':len(b['rows'])+i},str(-c)])
    point={'claim':{'FiberStrictness':{'inclusion_claim':2}},'values':[str(x) for x in values],'refutation':{'steps':[{'Lin':{'id':0,'kind':'Le','constant':'0','terms':terms}}],'end':{'Absurd':{'fact':{'Local':0}}}}}
    return {'claims':claims,'blocks':blocks,'points':[point]}, {'original_lp_witness':original_eval,'target_projected_witness':target_eval,'source_values':[str(x) for x in values],'target_values':[str(x) for x in target_values]}, {'claims':3,'points':1,'cases':len(changes),'rounds':len(cuts),'root_steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test19-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test19'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,evidence,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 6\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n');(out/'independent_exact_checks.json').write_text(json.dumps(evidence,indent=2)+'\n')
    d={'case_id':'test19','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete objective-preserving integer affine bijection, with all retained coordinates observed; target LP contained in projected source LP, with strictness proved by a complete source point and exact target fiber refutation. No optimum or LP objective-bound claim.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('continuous_split','Substitutes a continuous production variable for the integer branch premise.'),('missing_round','Uses the unrounded continuous lower bound to justify an integer cycle cut.'),('wrong_inverse','Changes a reconstructed free auxiliary, violating its original defining equation and inverse.'),('infeasible_separator','Changes source witness production without the coupled inventory balance.'),('empty_fiber_proof','Cancels the positive fiber contradiction to a nonpositive constant.')]:
            bad=copy.deepcopy(cert)
            if name=='continuous_split':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['integer']={'VarInt':0}
            elif name=='missing_round':
                rr=next(s['Round'] for s in bad['blocks'][0]['steps'] if 'Round' in s);rr['integer']=rr['le']
            elif name=='wrong_inverse':bad['blocks'][1]['end']['Return']['map'][924]['constant']='1'
            elif name=='infeasible_separator':bad['points'][0]['values'][0]='0'
            else:bad['points'][0]['refutation']['steps'][0]['Lin']['constant']='-673/900'
            path=out/(name+'.rpa');path.write_text('RPA 6\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
