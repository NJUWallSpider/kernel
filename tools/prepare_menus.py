#!/usr/bin/env python3
"""Prepare existing-rule components of test59/60, without claiming a bijection.

The integer reverse lift and injectivity proof are intentionally still required.
Partial verification is kept in partial_preparation.json and cannot promote the
complete actual case in the acceptance ledger.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,time
from audit_menus import inspect,lp_model
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def existing_components(a,b,w):
    menus=w['menus'];resources=w['resources'];groups=w['groups'];forward=[None]*len(b['vars']);reverse=[None]*len(a['vars']);source_options={};groups_by_source={g['source_row']:g for g in groups}
    for mi,m in enumerate(menus):
        K=m['maximum_index'];y=m['target_activation'];z=m['target_index'];opts=m['source_options']
        forward[y]=expression(0,{i:F(1) for i in opts})
        if z is not None:forward[z]=expression(0,{i:F(j) for j,i in enumerate(opts) if j})
        for j,i in enumerate(opts):
            source_options[i]=(mi,j)
            reverse[i]=expression(0,{y:F(1)}) if K==0 else expression(0,{y:F(1),z:-F(1,K)}) if j==0 else expression(0,{z:F(1,K)}) if j==K else expression()
    definitions={}
    for v in resources+[w['objective']]:
        i=v['source_variable'];ri=v['source_row'] if 'source_row' in v else v['source_definition_row'];c=a['rows'][ri]['terms'][i]
        e=v['target_expression'];reverse[i]=expression(F(e['constant']),{j:F(q) for j,q in e['terms']});definitions[i]=(ri,c)
    assert all(e is not None for e in forward+reverse)
    observations=[[expr_json(e),expr_json(expression(0,{j:1}))] for j,e in enumerate(forward)]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'affine_projection':observations,'inverse':None},
            {'reverse':False,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[],'affine_projection':observations,'inverse':None},
            {'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[],'affine_projection':[[y,x] for x,y in observations],'inverse':None}]
    def finish(builder,output,mapping,claim,domain_terms,row_terms,objective_terms):
        checks=[]
        def prove(kind,e,terms):
            if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):checks.append('Exact');return
            if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:checks.append(terms[0][0]);return
            checks.append(builder.lin(kind,terms,e))
        for i,v in enumerate(output['vars']):
            if v['lower'] is not None:prove('Le',plus(expression(v['lower']),mapping[i],-1),domain_terms(i,'VarLower'))
            if v['upper'] is not None:prove('Le',plus(mapping[i],expression(-v['upper'])),domain_terms(i,'VarUpper'))
            if claim['output_integers'] and v['integer']:prove('Int',mapping[i],domain_terms(i,'VarInt'))
        for ri,row in enumerate(output['rows']):
            typ=next(iter(row_ref(output,row['name'])));prove('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),row_terms(ri))
        prove('Eq',plus(substitute(output['objective'],mapping),builder.model['objective'],-1),objective_terms)
        for x,y in claim['affine_projection']:
            x=expression(F(x['constant']),{i:F(c) for i,c in x['terms']});y=expression(F(y['constant']),{i:F(c) for i,c in y['terms']})
            assert plus(substitute(y,mapping),x,-1)==expression();checks.append('Exact')
        return {'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}
    target_vars={m['target_activation']:(m,False) for m in menus}
    target_vars.update({m['target_index']:(m,True) for m in menus if m['target_index'] is not None})
    target_groups={g['target_row']:g for g in groups};target_links={m['target_link_row']:m for m in menus if m['target_link_row'] is not None};target_resources={ri:v for v in resources for ri in v['target_rows']};blocks=[]
    for claim in claims[:2]:
        builder=Builder(a);fixed={}
        def domains(i,kind):
            m,is_index=target_vars[i];opts=m['source_options'];weights={v:F(j if is_index else 1) for j,v in enumerate(opts)}
            if kind in ('VarLower','VarInt'):return [[{kind:v},c] for v,c in weights.items() if c]
            scale=F(m['maximum_index'] if is_index else 1);row=a['rows'][m['source_group_row']]
            return [[{'RowUpper':m['source_group_row']},scale]]+[[{'VarLower':v},scale-weights.get(v,F(0))] for v in row['terms'] if scale!=weights.get(v,F(0))]
        def rows(ri):
            if ri in target_groups:return [[{'RowUpper':target_groups[ri]['source_row']},F(1)]]
            if ri in target_links:
                m=target_links[ri];K=m['maximum_index'];return [[{'VarLower':v},F(K-j)] for j,v in enumerate(m['source_options']) if j!=K]
            v=target_resources[ri];i=v['source_variable'];definition,c=definitions[i];r=b['rows'][ri]
            if r['sense']=='E':
                if i not in fixed:fixed[i]=builder.eqpair({'VarUpper':i},{'VarLower':i})
                return [[fixed[i],F(1)],[{'RowEq':definition},-1/c]]
            if r['sense']=='G':return [[{'VarLower':i},F(1)],[{'RowEq':definition},1/c]]
            return [[{'VarUpper':i},F(1)],[{'RowEq':definition},-1/c]]
        obj_i=w['objective']['source_variable'];ri,c=definitions[obj_i]
        blocks.append(finish(builder,b,forward,claim,domains,rows,[[{'RowEq':ri},-1/c]]))
    builder=Builder(b);source_resources={v['source_variable']:v for v in resources};source_definition_rows={ri for ri,c in definitions.values()}
    def reverse_domain(i,kind):
        if i in source_options:
            mi,j=source_options[i];m=menus[mi];K=m['maximum_index'];y=m['target_activation'];z=m['target_index']
            if K==0:return [[{kind:y},F(1)]]
            if 0<j<K:return []
            if kind=='VarLower':return [[{'RowUpper':m['target_link_row']},F(1,K)]] if j==0 else [[{'VarLower':z},F(1,K)]]
            return [[{'VarUpper':y},F(1)],[{'VarLower':z},F(1,K)]] if j==0 else [[{'RowUpper':m['target_link_row']},F(1,K)],[{'VarUpper':y},F(1)]]
        v=source_resources[i]
        for ri in v['target_rows']:
            row=b['rows'][ri]
            if row['sense']=='E':return [[{'RowEq':ri},F(-1 if kind=='VarLower' else 1)]]
            if (kind=='VarLower' and row['sense']=='G') or (kind=='VarUpper' and row['sense']=='L'):return [[row_ref(b,row['name']),F(1)]]
        raise AssertionError(('missing projected bound',i,kind))
    def reverse_rows(ri):
        if ri in source_definition_rows:return []
        return [[{'RowUpper':groups_by_source[ri]['target_row']},F(1)]]
    blocks.append(finish(builder,a,reverse,claims[2],reverse_domain,reverse_rows,[]))
    return {'claims':claims,'blocks':blocks,'points':[]},{'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'steps_by_claim':[len(x['steps']) for x in blocks],'affine_observations_per_claim':len(observations)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('case',type=int,choices=[59,60]);ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();root=Path(__file__).resolve().parents[1];out=root/f'cases/test{args.case}';out.mkdir(parents=True,exist_ok=True)
    w=inspect(args.case);source=Path(w['source']['path']);target=Path(w['target']['path']);a=parse_mps(source);b=lp_model(target) if args.case==60 else parse_mps(target)
    cert,counts=existing_components(a,b,w);rpa=out/'partial.rpa';request=out/'partial.request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[]},separators=(',',':'))+'\n')
    d={'case_id':f'test{args.case}','status':'PROOF_NOT_COMPLETED','component_status':'PREPARED','source':w['source'],'target':w['target'],'counts':counts,'required_missing':['Integer target-to-source reconstruction with simultaneous optional-menu selections.','Full injectivity/bijection responsibility for original binary options and uniquely defined auxiliaries.'],'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'partial.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'partial.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['component_status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'partial_preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['component_status']='VERIFIED_PARTIAL_CONTRACT_ONLY';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','partial.rpx','partial.request.json']}
    (out/'partial_preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','component_status','counts','required_missing','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
