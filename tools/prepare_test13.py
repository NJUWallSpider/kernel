#!/usr/bin/env python3
"""Actual private one-hot projection: complete MI and LP correspondences."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test19 import cases_le
from prepare_test23 import run_checks
from prepare_test54 import fact
from menu_injectivity import split_expression


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(10399,14589,5677,14571)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];definitions=[];removed=set();added={}
    for d in h['blocks']:
        L,U,c=map(F,(d['lower'],d['upper'],d['target']));x,g,cy=[a['var_index'][d[k]] for k in ('x','trigger','special_indicator')]
        options=sorted([(F(v),a['var_index'][n]) for n,v in d['indicator_values'].items()]);assert [v for v,i in options]==list(range(int(L),int(U)+1)) and L<c<U
        assert options[int(c-L)][1]==cy
        assert not(removed&{i for v,i in options});removed.update(i for v,i in options)
        for v,i in options:assert a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
        sumref=row_ref(a,d['sum_row']);valueref=row_ref(a,d['value_row']);linkref=row_ref(a,d['link_row'])
        assert row_fact(a['rows'][a['row_index'][d['sum_row']]],'RowEq')==expression(-1,{i:1 for v,i in options})
        assert row_fact(a['rows'][a['row_index'][d['value_row']]],'RowEq')==expression(0,{**{i:v for v,i in options if v},x:-1})
        assert row_fact(a['rows'][a['row_index'][d['link_row']]],'RowUpper')==expression(0,{g:1,cy:-1})
        added[d['added_lower_row']]=[[valueref,F(1)],[sumref,-L],[linkref,c-L]]+[[{'VarLower':i},v-L] for v,i in options if v!=c and v!=L]
        added[d['added_upper_row']]=[[valueref,F(-1)],[sumref,U],[linkref,U-c]]+[[{'VarLower':i},U-v] for v,i in options if v!=c and v!=U]
        definitions.append({**d,'L':L,'U':U,'c':c,'x_id':b['var_index'][d['x']],'g_id':b['var_index'][d['trigger']],'options':[i for v,i in options]})
    assert removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']} and len(removed)==4722
    claims=[];blocks=[]
    # Both forward directions are the same exact continuous-valid linear proof.
    for integer in (True,False):
        f=Builder(a);claim={'reverse':False,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':common,'affine_projection':[],'inverse':None}
        blocks.append(run_checks(f,b,forward,claim,lambda i,t:{t:common[i][0]},lambda i,e:added.get(b['rows'][i]['name'],[[row_ref(a,b['rows'][i]['name']),F(1)]] if b['rows'][i]['name'] in a['row_index'] else None),lambda e:[]));claims.append(claim)
    # The integer reverse is one simultaneous, complete menu extension.
    p=Builder(b);ext=copy.deepcopy(b);menus=[];layout=[];mapping=[None]*len(a['vars'])
    for i,j in common:mapping[i]=expression(0,{j:1})
    for k,d in enumerate(definitions):
        L,U,c,x,g=d['L'],d['U'],d['c'],d['x_id'],d['g_id'];K=int(U-L);first=len(ext['vars']);sr=len(ext['rows']);op=list(range(first,first+K+1))
        for j in range(K+1):ext['vars'].append({'name':f'menu_{k}_{j}','lower':F(0),'upper':F(1),'integer':True})
        ext['rows'].append({'name':f'menu_{k}_sum','sense':'E','rhs':F(1),'terms':{i:F(1) for i in op}})
        ext['rows'].append({'name':f'menu_{k}_moment','sense':'E','rhs':-L,'terms':{**{i:F(j) for j,i in enumerate(op) if j},x:F(-1)}})
        index=expression(-L,{x:1});integer=p.lin('Int',[[{'VarInt':x},F(1)]],index,-L)
        menus.append({'maximum_index':K,'activation':expr_json(expression(1)),'index':expr_json(index),'checks':['Exact','Exact','Exact',{'VarLower':x},{'VarUpper':x},integer]})
        for i,j in zip(d['options'],op):mapping[i]=expression(0,{j:1})
        layout.append((op,sr))
    ext['var_index']={v['name']:i for i,v in enumerate(ext['vars'])};ext['row_index']={r['name']:i for i,r in enumerate(ext['rows'])};r=Builder(ext,p.counter,p.facts);rowproof={}
    for d,(op,sr) in zip(definitions,layout):
        L,U,c,x,g=d['L'],d['U'],d['c'],d['x_id'],d['g_id'];K=int(U-L);j=int(c-L);zc=op[j];sumref={'RowEq':sr};moment={'RowEq':sr+1};goal=expression(0,{g:1,zc:-1})
        rowproof[d['sum_row']]=[[sumref,F(1)]];rowproof[d['value_row']]=[[moment,F(1)],[sumref,L]]
        def active(child,assumption):
            geq=child.eqpair({'VarUpper':g},assumption)
            upper=child.lin('Le',[[row_ref(b,d['added_upper_row']),F(1)],[geq,-(U-c)]],expression(-c,{x:1}))
            lower=child.lin('Le',[[row_ref(b,d['added_lower_row']),F(1)],[geq,-(c-L)]],expression(c,{x:-1}))
            xeq=child.eqpair(upper,lower);meq=child.lin('Eq',[[moment,F(1)],[xeq,F(1)]],expression(-j,{i:F(q) for q,i in enumerate(op) if q}))
            desired=expression(-1,{zc:1})
            def not_special(sub,zero):
                zeq=sub.eqpair(zero,{'VarLower':zc});part=expression(0,{i:1 for q,i in enumerate(op) if q<j});integer=sub.lin('Int',[[{'VarInt':i},F(1)] for q,i in enumerate(op) if q<j],part)
                def no_lower(leaf,assump):
                    terms=[[meq,F(1)],[sumref,F(-j-1)],[assump,F(j+1)],[zeq,F(1)]]+[[{'VarLower':i},F(q)] for q,i in enumerate(op) if q<j and q]+[[{'VarLower':i},F(q-j-1)] for q,i in enumerate(op) if q>j+1]
                    return {'Absurd':leaf.lin('Le',terms,expression(1))}
                def some_lower(leaf,assump):
                    terms=[[sumref,F(K)],[meq,F(-1)],[assump,F(K-j+1)]]+[[{'VarLower':i},F(j-1-q)] for q,i in enumerate(op) if q<j-1]+[[{'VarLower':i},F(K-q)] for q,i in enumerate(op) if q>=j and q<K]
                    return {'Absurd':leaf.lin('Le',terms,expression(1))}
                return {'Witness':split_expression(sub,desired,part,integer,no_lower,some_lower)}
            selected=child.cases(desired,zc,not_special,lambda sub,one:{'Witness':sub.eqpair({'VarUpper':zc},one)})
            return child.lin('Le',[[geq,F(1)],[selected,F(-1)]],goal)
        rowproof[d['link_row']]=cases_le(r,goal,g,lambda child,z:child.lin('Le',[[z,F(1)],[{'VarLower':zc},F(1)]],goal),active)
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in common],'affine_projection':[],'inverse':None}
    body=run_checks(r,a,mapping,claim,lambda i,t:{t:next(iter(mapping[i][1]))},lambda i,e:rowproof.get(a['rows'][i]['name'],[[row_ref(b,a['rows'][i]['name']),F(1)]] if a['rows'][i]['name'] in b['row_index'] else None),lambda e:[])
    claims.insert(1,claim);blocks.insert(1,{'steps':p.steps,'end':{'MenuLift':{'menus':menus,'body':body}}})
    # Continuous reverse uses the distinguished trigger mass and two endpoints.
    r=Builder(b);mapping=[None]*len(a['vars']);domain={}
    for i,j in common:mapping[i]=expression(0,{j:1});domain[i]={t:{t:j} for t in ('VarLower','VarUpper')}
    for d in definitions:
        L,U,c,x,g=d['L'],d['U'],d['c'],d['x_id'],d['g_id'];K=U-L;lo=d['options'][0];hi=d['options'][-1];mid=d['options'][int(c-L)]
        for i in d['options']:mapping[i]=expression();domain[i]={'VarLower':[],'VarUpper':[]}
        mapping[lo]=expression(U/K,{x:-1/K,g:-(U-c)/K});mapping[hi]=expression(-L/K,{x:1/K,g:-(c-L)/K});mapping[mid]=expression(0,{g:1})
        low_nonneg=r.lin('Le',[[row_ref(b,d['added_upper_row']),1/K]],mul(mapping[lo],-1));high_nonneg=r.lin('Le',[[row_ref(b,d['added_lower_row']),1/K]],mul(mapping[hi],-1))
        domain[lo]={'VarLower':low_nonneg,'VarUpper':[[high_nonneg,F(1)],[{'VarLower':g},F(1)]]};domain[hi]={'VarLower':high_nonneg,'VarUpper':[[low_nonneg,F(1)],[{'VarLower':g},F(1)]]};domain[mid]={'VarLower':{'VarLower':g},'VarUpper':{'VarUpper':g}}
    claim={'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[j,i] for i,j in common],'affine_projection':[],'inverse':None}
    blocks.append(run_checks(r,a,mapping,claim,lambda i,t:domain[i][t],lambda i,e:[] if a['rows'][i]['name'] not in b['row_index'] else [[row_ref(b,a['rows'][i]['name']),F(1)]],lambda e:[]));claims.append(claim)
    return {'claims':claims,'blocks':blocks},{'source_variables':10399,'target_variables':5677,'source_rows':14589,'target_rows':14571,'simultaneous_menus':18,'generated_binary_variables':4722,'retained_coordinate_observations_per_claim':5677,'claims':4,'obligations_by_claim':[len(blocks[0]['end']['Return']['checks']),len(body['end']['Return']['checks']),len(blocks[2]['end']['Return']['checks']),len(blocks[3]['end']['Return']['checks'])]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test13-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test13'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test13','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and LP projection correspondence on all retained original coordinates with pointwise objective equality. Every private indicator domain and defining/link row is checked in the simultaneous integer lift and explicit fractional section.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_menu_bound','Omits one of the simultaneous menu domain premises.'),('wrong_trigger_case','Uses a continuous source extension as an integer trigger premise.'),('wrong_fractional_mass','Changes an endpoint interpolation constant and violates the original sum/moment equations.'),('missing_projection','Omits one retained-coordinate observation from the requested contract.')]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['MenuLift']
            if name=='missing_menu_bound':lift['menus'][9]['checks'].pop(4)
            elif name=='wrong_trigger_case':next(s['Cases'] for s in lift['body']['steps'] if 'Cases' in s)['integer']={'VarInt':next(i for i,v in enumerate(parse_mps(target)['vars']) if not v['integer'])}
            elif name=='wrong_fractional_mass':next(e for e in bad['blocks'][3]['end']['Return']['map'] if len(e['terms'])==2)['constant']='2'
            else:bad['blocks'][2]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 7\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
