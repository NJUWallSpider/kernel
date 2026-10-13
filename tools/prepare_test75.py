#!/usr/bin/env python3
"""Complete affine-component, constant and leaf-sum bijection for actual test75."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(48950,98021,38001,72968)
    removed={a['var_index'][n]:d for n,d in h['removed_variables'].items()};assert len(removed)==10949
    assert set(removed)=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[]
    for i,v in enumerate(a['vars']):
        if i in removed:
            d=removed[i];reverse.append(expression(F(d['constant']),{b['var_index'][n]:F(c) for n,c in d['coefficients'].items()}))
        else:reverse.append(expression(0,{b['var_index'][v['name']]:1}))
    assert a['objective']==b['objective']==expression()
    p=Builder(a);graph={}
    for d in h['affine_relations']:
        x,y=a['var_index'][d['x']],a['var_index'][d['y']];s,t=F(d['sign']),F(d['offset']);assert s in (F(1),F(-1))
        rr=[row_ref(a,n) for n in d['rows']]
        if len(rr)==1:r=rr[0];assert p.kind(r)=='Eq'
        else:assert len(rr)==2;r=p.eqpair(rr[0],rr[1])
        scale=1/p.refexpr(r)[1][x];r=fact(p,'Eq',expression(-t,{x:1,y:-s}),[[r,scale]])
        graph.setdefault(y,[]).append((x,s,t,r,F(1)));graph.setdefault(x,[]).append((y,s,-s*t,r,-s))
    eq={};affine={};member_facts={};component_members=set()
    for d in h['affine_components']:
        root=a['var_index'][d['root']];members={a['var_index'][n] for n in d['members']};assert not(component_members&members);component_members|=members
        local={root:(F(1),F(0),None)};pending=[root]
        while pending:
            parent=pending.pop();ps,pt,pref=local[parent]
            for child,s,t,ref,scale in graph[parent]:
                if child in local:continue
                assert child in members;cs,ct=s*ps,s*pt+t
                terms=[[ref,scale]]+([[pref,s]] if pref is not None else [])
                got=fact(p,'Eq',expression(-ct,{child:1,root:-cs}),terms);local[child]=(cs,ct,got);pending.append(child)
        assert set(local)==members
        lower,upper=map(F,d['root_bounds']);root_fixed=None
        if lower==upper:
            bounds=[]
            for typ,witness in [('VarUpper',d['upper_witness']),('VarLower',d['lower_witness'])]:
                i=a['var_index'][witness];s,t,ref=local[i];upper_side=typ=='VarUpper';source_upper=upper_side==(s>0);r={'VarUpper' if source_upper else 'VarLower':i};terms=[[r,F(1)]]
                if ref is not None:terms.append([ref,F(-1 if source_upper else 1)])
                wanted=expression(-upper,{root:1}) if upper_side else expression(lower,{root:-1})
                bounds.append(fact(p,'Le',wanted,terms))
            root_fixed=p.eqpair(bounds[0],bounds[1])
        else:
            assert root not in removed and a['vars'][root]['lower']==lower and a['vars'][root]['upper']==upper
        for i,(s,t,ref) in local.items():
            affine[i]=(root,s,t);member_facts[i]=ref
            if i not in removed:continue
            desired=plus(expression(0,{i:1}),substitute(reverse[i],forward),-1)
            terms=([[ref,F(1)]] if ref is not None else [])+([[root_fixed,s]] if root_fixed is not None else [])
            eq[i]=fact(p,'Eq',desired,terms)
    for i,v in enumerate(a['vars']):
        if i not in removed or i in eq:continue
        if v['lower'] is not None and v['lower']==v['upper']:
            eq[i]=p.eqpair({'VarUpper':i},{'VarLower':i});assert p.refexpr(eq[i])==plus(expression(0,{i:1}),substitute(reverse[i],forward),-1)
    for n,d in h['leaf_definitions'].items():
        i=a['var_index'][n];assert i not in eq;r=row_ref(a,d['row']);raw=p.refexpr(r);scale=1/raw[1][i];terms=[[r,scale]]
        for j,c in raw[1].items():
            if j!=i and j in removed:terms.append([eq[j],-c*scale])
        eq[i]=fact(p,'Eq',plus(expression(0,{i:1}),substitute(reverse[i],forward),-1),terms)
    assert set(eq)==set(removed)
    claims=[];blocks=[];prefix=list(p.steps);facts=p.facts.copy();counter=p.counter[0]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse
            builder=Builder(inp) if back else Builder(a,[counter],facts)
            if not back:builder.steps=list(prefix)
            checks=[]
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(e,sign),expression(-sign*value))
                    checks.append(box(builder,wanted,True) if back else {typ:next(iter(e[1]))})
                if integer and v['integer']:checks.append(fact(builder,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
            for row in out['rows']:
                n=row['name'];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
                if back:
                    if n in b['row_index']:
                        ref=row_ref(b,n);assert builder.refexpr(ref)==wanted;check=ref
                    elif exact(kind,wanted):check='Exact'
                    elif kind=='Le':check=box(builder,wanted,True)
                    else:check=builder.eqpair(box(builder,wanted),box(builder,mul(wanted,-1)))
                else:
                    ref=row_ref(a,n);terms=[[ref,F(1)]]+[[eq[i],-c] for i,c in builder.refexpr(ref)[1].items() if i in eq]
                    check=fact(builder,kind,wanted,terms,terminal=True)
                checks.append(check)
            assert plus(substitute(out['objective'],mapping),inp['objective'],-1)==expression();checks.append('Exact')
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1)
                checks.append(fact(builder,'Eq',wanted,[[eq[i],F(-1)]] if not back and i in eq else [],terminal=True))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':[1,0,3,2][len(claims)]})
            blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'affine_relations':len(h['affine_relations']),'affine_components':len(h['affine_components']),'eliminated_variables':len(removed),'leaf_sums':len(h['leaf_definitions']),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'steps_by_claim':[len(x['steps']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test75-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test75'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test75','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and continuous-relaxation affine bijections with all retained original coordinates, all original bounds/rows and both full inverse compositions. All reconstruction and fixed-component facts follow from actual rows and bounds; objective equality is exact.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('wrong_opposite_row','Uses the same inequality twice in an equality antisymmetry proof.'),('wrong_affine_recovery','Changes an eliminated affine reconstruction constant.'),('missing_leaf_term','Omits one term from a reconstructed bounded integer leaf sum.'),('missing_inverse','Omits a coordinate from the explicitly requested full composition identity.')]:
            bad=copy.deepcopy(cert)
            if name=='wrong_opposite_row':step=next(s['EqPair'] for s in bad['blocks'][0]['steps'] if 'EqPair' in s);step['negative']=step['positive']
            elif name=='wrong_affine_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if e['constant']=='1' and e['terms'])['constant']='2'
            elif name=='missing_leaf_term':next(e for e in bad['blocks'][1]['end']['Return']['map'] if len(e['terms'])==4)['terms'].pop()
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
