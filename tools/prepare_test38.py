#!/usr/bin/env python3
"""Untrusted scalar certificate for the actual shared switch DAG (no DAG theorem)."""
from collections import ChainMap
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder,fix_binary


def model(path):
    m=parse_mps(path)
    for v in m['vars']:v['name']=v['name'].strip('"')
    for r in m['rows']:r['name']=r['name'].strip('"')
    m['var_index']={v['name']:i for i,v in enumerate(m['vars'])}
    m['row_index']={r['name']:i for i,r in enumerate(m['rows'])}
    return m


def cases(b,kind,desired,var,left,right):
    i=b.alloc();split=expression(0,{var:1});children=[]
    for which,cb in enumerate((left,right)):
        child=Builder.__new__(Builder);child.model=b.model;child.counter=b.counter
        child.facts=ChainMap({},b.facts);child.assumptions=b.assumptions+[split if which==0 else expression(1,{var:-1})];child.steps=[]
        ref=cb(child,{'Assumption':len(b.assumptions)})
        assert child.refexpr(ref)==desired and child.kind(ref) in (kind,'Eq')
        children.append({'steps':child.steps,'end':{'Witness':ref}})
    b.steps.append({'Cases':{'id':i,'kind':kind,'expression':expr_json(desired),'split':expr_json(split),'integer':{'VarInt':var},'left':children[0],'right':children[1]}})
    b.facts[i]=(kind,desired);return {'Local':i}


def bound(b,e,terms=()):
    terms=list(terms);res=e
    for ref,c in terms:res=plus(res,b.refexpr(ref),-c)
    for i,c in list(res[1].items()):
        ref={'VarUpper':i} if c>0 else {'VarLower':i};terms.append((ref,abs(c)))
        res=plus(res,b.refexpr(ref),-abs(c))
    assert not res[1] and res[0]<=0,('box bound unavailable',e,res)
    return b.lin('Le',terms,e,constant=res[0])


def key(e):return (e[0],tuple(sorted(e[1].items())))


def prepare(a,b,h):
    nodes=h['original_nodes'];term=h['terminal_substitutions'];defs=h['new_definitions'];av=a['var_index'];bv=b['var_index'];fixed=av[h['budget_fixation']['variable']]
    retained=set(av)&set(bv)
    assert set(av)==retained|set(nodes)|set(term) and set(bv)==retained|set(defs)
    assert all(v['lower']==0 and v['upper']==1 for v in a['vars'])
    def replacement(n):return {'constant':term[n]['value']} if n in term else nodes[n]['replacement']
    def symbolic(e,ids):return expression(F(e['constant'])) if 'constant' in e else expression(0,{ids[e['variable']]:1})
    reps={}
    for n,d in nodes.items():
        rep=d['replacement']
        if 'variable' not in rep:continue
        target=defs[rep['variable']]
        if replacement(d['first_child'])!=target['first_child'] or replacement(d['second_child'])!=target['second_child'] or F(d['q'])!=F(target['q']):continue
        if (target['kind']=='switch' and d['selector']==target['selector']) or (target['kind']=='mix' and av[d['selector']]==fixed):reps.setdefault(rep['variable'],n)
    assert set(reps)==set(defs)
    fi={n:av[r] for n,r in reps.items()}
    forward=[expression(0,{av[v['name']]:1}) if v['name'] in retained else expression(0,{fi[v['name']]:1}) for v in b['vars']]
    reverse=[expression(0,{bv[v['name']]:1}) if v['name'] in retained else symbolic(replacement(v['name']),bv) for v in a['vars']]
    canon={n:substitute(symbolic(replacement(n),bv),forward) for n in list(term)+list(nodes)}
    f=Builder(a);alias={};visiting=set()
    # The actual full budget plus every other nonnegative selector proves fixation.
    budget=row_ref(a,'budget');be=f.refexpr(budget);c=be[1][fixed]
    upper=f.lin('Le',[(budget,1/c)]+[({'VarLower':i},q/c) for i,q in be[1].items() if i!=fixed],expression(be[0]/c,{fixed:1}))
    assert all(q>0 for q in be[1].values()) and 0<=-be[0]/c<1
    rr=f.alloc();f.steps.append({'Round':{'id':rr,'le':upper,'integer':{'VarInt':fixed}}});f.facts[rr]=('Le',expression(0,{fixed:1}))
    fixed_eq=f.eqpair({'Local':rr},{'VarLower':fixed})
    for n,d in term.items():
        ref=row_ref(a,d['defining_row']);assert f.kind(ref)=='Eq' and f.refexpr(ref)==plus(expression(0,{av[n]:1}),canon[n],-1);alias[n]=ref
    def norm(builder,n,sel_eq,value):
        d=nodes[n];q=F(d['q']);weights=[(d['first_child'],F(1))] if value else [(d['first_child'],1-q),(d['second_child'],q)]
        oldvalue=expression()
        for child,w in weights:oldvalue=plus(oldvalue,expression(0,{av[child]:1}),w)
        wanted=plus(expression(0,{av[n]:1}),oldvalue,-1);bounds=[]
        for label,sign in [('U',1),('L',-1)]:
            ref=row_ref(a,d['removed_block_rows'][label+str(value)]);raw=builder.refexpr(ref);diff=plus(raw,mul(wanted,sign),-1)
            sx=av[d['selector']];coef=diff[1].get(sx,F(0));assert diff==mul(builder.refexpr(sel_eq),coef),(n,label,value,diff)
            bounds.append(builder.lin('Le',[(ref,F(1)),(sel_eq,-coef)],mul(wanted,sign)))
        eq=builder.eqpair(*bounds);terms=[(eq,F(1))]
        for child,w in weights:
            if child in alias:terms.append((alias[child],w))
            else:assert canon[child]==expression(0,{av[child]:1})
        normalized=expression()
        for child,w in weights:normalized=plus(normalized,canon[child],w)
        return builder.lin('Eq',terms,plus(expression(0,{av[n]:1}),normalized,-1)),normalized
    def ensure(n):
        if n in alias:return
        if canon[n]==expression(0,{av[n]:1}):return
        assert n not in visiting,('cyclic candidate alias',n);visiting.add(n)
        d=nodes[n]
        for child in [d['first_child'],d['second_child']]:ensure(child)
        same=canon[d['first_child']]==canon[d['second_child']]==canon[n]
        rep=None if same or not canon[n][1] else reps[d['replacement']['variable']]
        if rep:
            for child in [nodes[rep]['first_child'],nodes[rep]['second_child']]:ensure(child)
        desired=plus(expression(0,{av[n]:1}),canon[n],-1);sx=av[d['selector']]
        def branch(builder,eq,value):
            nr,nv=norm(builder,n,eq,value)
            if rep:
                assert av[nodes[rep]['selector']]==sx
                rr,rv=norm(builder,rep,eq,value);assert nv==rv
                return builder.lin('Eq',[(nr,F(1)),(rr,F(-1))],desired)
            assert nv==canon[n],(n,value,nv,canon[n]);return nr
        if sx==fixed:alias[n]=branch(f,fixed_eq,0)
        else:alias[n]=cases(f,'Eq',desired,sx,lambda z,ass:branch(z,fix_binary(z,sx,0,ass),0),lambda z,ass:branch(z,fix_binary(z,sx,1,ass),1))
        visiting.remove(n)
    for n in nodes:ensure(n)
    # Ensure children needed by representative definitions have global aliases.
    for n in reps.values():
        for child in [nodes[n]['first_child'],nodes[n]['second_child']]:ensure(child)
    fchecks=[]
    for i,v in enumerate(b['vars']):
        j=next(iter(forward[i][1]));assert b['vars'][i]['integer']==a['vars'][j]['integer']
        fchecks.append({'VarLower':j});fchecks.append(fixed_eq if j==fixed else {'VarUpper':j})
        if v['integer']:fchecks.append('Exact')
    new_rows={n+'_'+suffix:n for n,d in defs.items() for suffix in (['mix'] if d['kind']=='mix' else ['U0','L0','U1','L1'])}
    for row in b['rows']:
        ref=row_ref(b,row['name']);kind='Eq' if 'RowEq' in ref else 'Le';want=substitute(row_fact(row,next(iter(ref))),forward)
        if row['name'] not in new_rows:
            old=row_ref(a,row['name']);e=f.refexpr(old);terms=[(old,F(1))]
            for i,c in e[1].items():
                n=a['vars'][i]['name']
                if n in alias:terms.append((alias[n],-c))
            fchecks.append(f.lin(kind,terms,want));continue
        dn=new_rows[row['name']];n=reps[dn];d=defs[dn]
        if d['kind']=='mix':
            eq,_=norm(f,n,fixed_eq,0);assert f.refexpr(eq)==want;fchecks.append(eq);continue
        sx=av[d['selector']];out=av[n]
        def rowbranch(builder,ass,value):
            eq=fix_binary(builder,sx,value,ass);nr,_=norm(builder,n,eq,value)
            terms=[(nr,want[1].get(out,F(0)))];res=plus(want,builder.refexpr(nr),-terms[0][1]);terms.append((eq,res[1].get(sx,F(0))))
            return bound(builder,want,terms)
        fchecks.append(cases(f,'Le',want,sx,lambda z,ass:rowbranch(z,ass,0),lambda z,ass:rowbranch(z,ass,1)))
    assert substitute(b['objective'],forward)==a['objective'];fchecks.append('Exact')
    projection=sorted(retained);fchecks+=['Exact']*len(projection)
    for i,e in enumerate(reverse):
        want=plus(substitute(e,forward),expression(0,{i:1}),-1);n=a['vars'][i]['name']
        fchecks.append('Exact' if want==expression() else f.lin('Eq',[(alias[n],F(-1))],want))
    r=Builder(b);rchecks=[]
    for i,v in enumerate(a['vars']):
        for typ,e in [('VarLower',plus(expression(v['lower']),reverse[i],-1)),('VarUpper',plus(reverse[i],expression(-v['upper'])))]:
            rchecks.append(bound(r,e))
        if v['integer']:rchecks.append('Exact')
    rowfacts={key(r.refexpr(row_ref(b,row['name']))):row_ref(b,row['name']) for row in b['rows']}
    for row in a['rows']:
        oldref=row_ref(a,row['name']);kind='Eq' if 'RowEq' in oldref else 'Le';want=substitute(row_fact(row,next(iter(oldref))),reverse)
        if key(want) in rowfacts:rchecks.append(rowfacts[key(want)]);continue
        if kind=='Eq':assert want==expression(),(row['name'],want);rchecks.append('Exact');continue
        node=next((n for n in [row['name'].removeprefix('pbc_').rsplit('_',1)[0]] if n in nodes),None)
        options=[[]]
        if node and 'variable' in nodes[node]['replacement']:
            dn=nodes[node]['replacement']['variable'];vi=bv[dn]
            for suffix in (['mix'] if defs[dn]['kind']=='mix' else ['U0','L0','U1','L1']):
                ref=row_ref(b,dn+'_'+suffix);raw=r.refexpr(ref)
                if raw[1].get(vi):
                    q=want[1].get(vi,F(0))/raw[1][vi]
                    if r.kind(ref)=='Eq' or q>=0:options.append([(ref,q)])
        # Small deterministic candidate list. Failure never becomes acceptance.
        for terms in options:
            res=want
            for ref,c in terms:res=plus(res,r.refexpr(ref),-c)
            hi=res[0]+sum(c*(b['vars'][i]['upper'] if c>0 else b['vars'][i]['lower']) for i,c in res[1].items())
            if hi<=0:rchecks.append(bound(r,want,terms));break
        else:raise AssertionError(('reverse inequality unproved',row['name'],want))
    assert substitute(a['objective'],reverse)==b['objective'];rchecks.append('Exact');rchecks+=['Exact']*(len(projection)+len(b['vars']))
    claims=[]
    for rev,inp,out in [(False,a,b),(True,b,a)]:claims.append({'reverse':rev,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[inp['var_index'][n],out['var_index'][n]] for n in projection],'inverse':0 if rev else 1})
    cert={'claims':claims,'blocks':[{'steps':f.steps,'end':{'Return':{'map':list(map(expr_json,forward)),'checks':fchecks}}},{'steps':r.steps,'end':{'Return':{'map':list(map(expr_json,reverse)),'checks':rchecks}}}]}
    return cert,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'source_nodes':len(nodes),'shared_nodes':len(defs),'aliases':len(alias),'root_steps':[len(f.steps),len(r.steps)],'obligations':[len(fchecks),len(rchecks)]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path);p.add_argument('--out',type=Path,default=Path('cases/test38'));a=p.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test38-nomf-B1');out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/model_shared_dag.mps';hint=run/'output/audit.json';cert,counts=prepare(model(source),model(target),json.loads(hint.read_text()));rpa=out/'proof.rpa';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request=out/'request.json';request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    data={'case_id':'test38','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(hint),'sha256':sha(hint)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Full objective-preserving mixed-integer affine bijection with both inverse identities and all107retained p/x coordinates. Shared DAG aliases use scalar local integer Cases. No LP equivalence or strictness claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rpa.stat().st_size,'rpa_sha256':sha(rpa),'kernel_runs':[]}
    if a.kernel:
        kernel=a.kernel.resolve();data['kernel_binary_sha256']=sha(kernel)
        for command in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]:
            args=list(map(str,[kernel,*command]));res=subprocess.run(args,capture_output=True,text=True);data['kernel_runs'].append({'command':args,'exit_code':res.returncode,'stdout':res.stdout,'stderr':res.stderr})
            if res.returncode:data['status']=json.loads(res.stdout)['status'];(out/'preparation.json').write_text(json.dumps(data,indent=2)+'\n');raise SystemExit(res.stdout)
        data['status']='VERIFIED';data['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
    if a.kernel:
        data['negative_checks']=[]
        continuous=next(i for i,v in enumerate(model(source)['vars']) if not v['integer'])
        for name,reason in [('continuous_selector','Claims integrality of a continuous source variable in local Cases.'),('false_alias','Alters the common alias equality while retaining the branch witnesses.'),('missing_obligation','Removes a middle final-output obligation witness.'),('wrong_shared_representative','Replaces one shared-node output map with an unrelated source coordinate.'),('weakened_inverse','Removes the requested inverse claim in the certificate only.')]:
            bad=copy.deepcopy(cert)
            if name in ('continuous_selector','false_alias'):
                case=next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)
                if name=='continuous_selector':case['integer']={'VarInt':continuous}
                else:case['expression']['constant']='1'
            elif name=='missing_obligation':del bad['blocks'][0]['end']['Return']['checks'][len(bad['blocks'][0]['end']['Return']['checks'])//2]
            elif name=='wrong_shared_representative':
                target_model=model(target);j=next(i for i,v in enumerate(target_model['vars']) if v['name'].startswith('d'))
                bad['blocks'][0]['end']['Return']['map'][j]=expr_json(expression(0,{continuous:1}))
            else:bad['claims'][0]['inverse']=None
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            assembled=subprocess.run([str(kernel),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert assembled.returncode==0,assembled.stdout
            checked=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(checked.stdout)
            assert checked.returncode!=0 and result['status']=='INVALID',(name,result)
            data['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':checked.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({k:data[k] for k in ['status','counts','rpa_bytes','preparation_seconds']},indent=2))
if __name__=='__main__':main()
