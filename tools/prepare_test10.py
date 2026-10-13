#!/usr/bin/env python3
"""Actual test10: shared load-budget proof, exact threshold cuts and LP fiber.

This is an untrusted certificate preparer. Original models are immutable; every
bound, row, integer declaration, projection and extension premise reaches RPX.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test54 import fact, box, exact
from prepare_test23 import extend
from prepare_test37 import round_fact


def cases(p, kind, wanted, var, callbacks):
    ident=p.alloc(); branches=[]
    for side, callback in enumerate(callbacks):
        guard=expression(side,{var:1 if side==0 else -1})
        child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[guard])
        child.facts=ChainMap({},p.facts)
        ref=callback(child,{'Assumption':len(p.assumptions)})
        assert child.refexpr(ref)==wanted and child.kind(ref)==kind
        branches.append({'steps':child.steps,'end':{'Witness':ref}})
    p.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),
        'split':expr_json(expression(0,{var:1})),'integer':{'VarInt':var},
        'left':branches[0],'right':branches[1]}})
    p.facts[ident]=(kind,wanted);return {'Local':ident}


def selector_fact(p,wanted,special,z):
    """Only two ordinary branches. Actual selector rows force one full pair."""
    def branch(child,assumption,side):
        pair=special[:2] if side else special[2:]
        r=row_ref(child.model,'R2302' if side else 'R2303')
        forced={}
        for i,j in [pair,pair[::-1]]:
            forced[i]=child.lin('Le',[[r,1],[assumption,2],[{'VarUpper':j},1]],expression(1,{i:-1}))
        terms=[];ceiling=wanted[0]
        for i,c in wanted[1].items():
            if c>0:ref={'VarUpper':i};value=1
            elif i in forced:ref=forced[i];value=1
            else:ref={'VarLower':i};value=0
            terms.append([ref,abs(c)]);ceiling+=c*value
        assert ceiling<=0
        return child.lin('Le',terms,wanted,ceiling)
    return cases(p,'Le',wanted,z,[lambda c,r:branch(c,r,0),lambda c,r:branch(c,r,1)])


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(190402,2303,190201,2105)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    assert all(a['vars'][i]==b['vars'][j] for i,j in common)
    forward=[expression(0,{i:1}) for i,j in common]
    budget=row_ref(a,h['budget_substitution']['row']);br=a['rows'][budget['RowUpper']]
    loads={};weights={};assignment={};groups={};costs={};charges={}
    for k in range(950):
        name=f'R{951+k:04d}';row=a['rows'][a['row_index'][name]]
        assert row['sense']=='E' and row['rhs']==1 and len(row['terms'])==200 and all(c==1 for c in row['terms'].values())
        for i in row['terms']:assert i not in assignment;assignment[i]=name
    for d in h['eliminated_loads']:
        u,y=a['var_index'][d['variable']],a['var_index'][d['activation_variable']]
        r=row_ref(a,d['row']);e=row_fact(a['rows'][r['RowEq']],'RowEq')
        assert e[0]==0 and e[1][u]==-1 and not a['vars'][u]['integer'] and a['vars'][u]['lower']==0 and a['vars'][u]['upper'] is None
        terms={i:c for i,c in e[1].items() if i!=u};assert len(terms)==950 and all(c>0 for c in terms.values())
        assert set(assignment[i] for i in terms)==set(a['rows'][a['row_index'][f'R{951+k:04d}']]['name'] for k in range(950))
        for i,w in terms.items():
            rn=assignment[i];assert rn not in weights or weights[rn]==w;weights[rn]=w
        loads[u]=(r,expression(0,terms));groups[y]=(u,d['activation_variable']);costs[y]=br['terms'][u];charges[y]=br['terms'][y]
        assert costs[y]==F(d['budget_coefficient']) and costs[y]>0 and charges[y]>0
    z=a['var_index'][h['selector']['removed_variable']]
    assert {i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}==set(loads)|{z}
    assert set(br['terms'])==set(loads)|set(groups) and br['rhs']==900000000
    special=[a['var_index'][f'C{190202+k}'] for k in range(4)]
    assert row_fact(a['rows'][a['row_index']['R2302']],'RowLower')==expression(0,{special[0]:-1,special[1]:-1,z:2})
    assert row_fact(a['rows'][a['row_index']['R2303']],'RowLower')==expression(2,{special[2]:-1,special[3]:-1,z:-2})
    cmin=min(costs.values());W=sum(weights.values());prefix=[F(0)]
    for w in sorted(weights.values()):prefix.append(prefix[-1]+w)
    assert cmin==F(h['bound_proof']['minimum_unit_cost']) and W==F(h['bound_proof']['total_weight'])
    assert prefix==[F(x) for x in h['bound_proof']['sorted_weight_prefix_sums']]
    f=SparseBuilder(a)
    total=f.lin('Eq',[[r,-1] for r,e in loads.values()]+[[row_ref(a,n),w] for n,w in weights.items()],expression(-W,{u:1 for u in loads}))
    base=f.lin('Le',[[budget,1],[total,-cmin]])
    fixed4=expression(0,{i:-charges[i] for i in special})
    Fmin=min(sum(charges[i] for i in pair) for pair in [special[:2],special[2:]])
    global_fixed=selector_fact(f,plus(expression(Fmin),fixed4),special,z)
    fixed_cond={}
    for y in special:
        Fj=min(sum(charges[i] for i in pair)+(charges[y] if y not in pair else 0) for pair in [special[:2],special[2:]])
        fixed_cond[y]=selector_fact(f,plus(fixed4,expression(0,{y:Fj})),special,z)
    tightened={};thresholds=[]
    for y,(u,yn) in groups.items():
        d=h['link_bounds'][yn];name=d['row'];M=F(d['new_M']);old=row_ref(a,name)
        count=expression(0,{i:1 for i in loads[u][1][1]})
        assert f.refexpr(old)==plus(count,expression(0,{y:-950}))
        assert substitute(row_fact(b['rows'][b['row_index'][name]],'RowUpper'),forward)==plus(count,expression(0,{y:-M}))
        Fj=min(sum(charges[i] for i in pair)+(charges[y] if y not in pair else 0) for pair in [special[:2],special[2:]])
        delta=costs[y]-cmin
        expected=950 if delta==0 else max(k for k,P in enumerate(prefix) if delta*P+cmin*W+Fj<=br['rhs'])
        assert M==expected and Fj==F(d['conditional_fixed_charge_lower_bound'])
        if M==950:continue
        assert delta>0 and 0<M<950
        terms=[[base,1]]+[[{'VarLower':uu},costs[yy]-cmin] for yy,(uu,_) in groups.items() if yy!=y and costs[yy]>cmin]
        if y in special:
            terms.append([fixed_cond[y],1]);terms += [[{'VarLower':yy},charges[yy]] for yy in groups if yy not in special]
        else:
            terms += [[global_fixed,1],[{'VarUpper':y},Fmin]]
            terms += [[{'VarLower':yy},charges[yy]] for yy in groups if yy not in special and yy!=y]
        conditional=f.lin('Le',terms,expression(cmin*W-br['rhs'],{u:delta,y:Fj}))
        t=sorted(weights.values())[int(M)];C=sum(max(F(0),t-w) for w in weights.values())
        boxterms=[]
        for i,w in loads[u][1][1].items():
            if t>w:boxterms.append([{'VarUpper':i},t-w])
            elif t<w:boxterms.append([{'VarLower':i},w-t])
        support=f.lin('Le',boxterms,plus(plus(mul(count,t),loads[u][1],-1),expression(-C)))
        thresholds.append({'row':name,'M':int(M),'threshold':str(t),'box_correction':str(C),'conditional_fixed_charge':str(Fj)})
        integer=f.lin('Int',[[{'VarInt':i},1] for i in count[1]],count)
        wanted=plus(count,expression(0,{y:-M}))
        def zero(child,assumption,old=old,M=M,wanted=wanted):return child.lin('Le',[[old,1],[assumption,950-M]],wanted)
        def one(child,assumption,u=u,delta=delta,Fj=Fj,t=t,conditional=conditional,support=support,integer=integer,M=M,wanted=wanted):
            weightbound=child.lin('Le',[[conditional,1],[assumption,Fj],[loads[u][0],delta]])
            bound=child.lin('Le',[[weightbound,1/(delta*t)],[support,1/t]])
            rounded=round_fact(child,bound,integer);assert child.refexpr(rounded)==plus(count,expression(-M))
            return child.lin('Le',[[rounded,1],[assumption,M]],wanted)
        tightened[name]=cases(f,'Le',wanted,y,[zero,one])
    assert len(tightened)==170
    selector={}
    for d in h['selector']['new_rows']:
        wanted=substitute(row_fact(b['rows'][b['row_index'][d['row']]],'RowLower'),forward)
        selector[d['row']]=selector_fact(f,wanted,special,z)
    claims=[];blocks=[]
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':common,'inverse':None}
    checks=[]
    for i,j in common:
        v=b['vars'][j]
        for typ,bound in [('VarLower',v['lower']),('VarUpper',v['upper'])]:
            if bound is not None:checks.append({typ:i})
        if v['integer']:checks.append({'VarInt':i})
    for row in b['rows']:
        n=row['name'];typ=next(iter(row_ref(b,n)));wanted=substitute(row_fact(row,typ),forward)
        if n in tightened:ref=tightened[n]
        elif n in selector:ref=selector[n]
        elif n==h['budget_substitution']['row']:ref=f.lin('Le',[[budget,1]]+[[r,br['terms'][u]] for u,(r,e) in loads.items()],wanted)
        else:ref=row_ref(a,n)
        assert f.refexpr(ref)==wanted;checks.append(ref)
    assert substitute(b['objective'],forward)==a['objective'];checks+=['Exact']*(1+len(common))
    claims.append(claim);blocks.append({'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':checks}}})
    bs=[b['var_index'][a['vars'][i]['name']] for i in special];aa,bb,cc,dd=bs
    lower=[expression(),expression(-1,{aa:1,bb:1}),expression(1,{cc:F(-1,2),dd:F(-1,2)})]
    upper=[expression(0,{aa:1}),expression(0,{bb:1})]
    pre=SparseBuilder(b);premises=[]
    for k,l in enumerate(lower):
        for j,v in enumerate([aa,bb]):
            wanted=plus(l,upper[j],-1)
            if k<2:ref=box(pre,wanted,True)
            else:ref=pre.lin('Le',[[row_ref(b,f'P{1+2*j:04d}'),F(1,2)],[row_ref(b,f'P{2+2*j:04d}'),F(1,2)]],wanted)
            premises.append(ref)
    interval={'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':premises}
    ext,layout=extend(b,[interval]);ll=layout[0];zz=ll['variable'];ze=expression(0,{zz:1});lo=[{'RowLower':i} for i in ll['lower']];hi=[{'RowUpper':i} for i in ll['upper']]
    retained_map=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    reverse=[]
    for i,v in enumerate(a['vars']):
        if i in loads:reverse.append(substitute(loads[i][1],retained_map))
        elif i==z:reverse.append(ze)
        else:reverse.append(expression(0,{b['var_index'][v['name']]:1}))
    for integer in [True,False]:
        p=SparseBuilder(ext,pre.counter,pre.facts);zupper=p.lin('Le',[[hi[0],1],[{'VarUpper':aa},1]],plus(ze,expression(-1)))
        zint=None
        if integer:
            def azero(child,assumption):
                up=child.lin('Le',[[hi[0],1],[assumption,1]],ze)
                return child.lin('Int',[[child.eqpair(up,lo[0]),1]],ze)
            def aone(child,assumption):
                def bzero(c,r):
                    up=c.lin('Le',[[hi[1],1],[r,1]],ze)
                    return c.lin('Int',[[c.eqpair(up,lo[0]),1]],ze)
                def bone(c,r):
                    low=c.lin('Le',[[lo[1],1],[assumption,1],[r,1]],plus(expression(1),ze,-1))
                    return c.lin('Int',[[c.eqpair(zupper,low),1]],ze,1)
                return cases(child,'Int',ze,bb,[bzero,bone])
            zint=cases(p,'Int',ze,aa,[azero,aone])
        checks=[]
        for i,v in enumerate(a['vars']):
            e=reverse[i]
            if i==z:checks += [lo[0],zupper];checks += [zint] if integer else []
            elif i in loads:checks.append(box(p,mul(e,-1),True))
            else:
                j=next(iter(e[1]));assert e==expression(0,{j:1})
                for typ,bound in [('VarLower',v['lower']),('VarUpper',v['upper'])]:
                    if bound is not None:checks.append({typ:j})
                if integer and v['integer']:checks.append({'VarInt':j})
        for row in a['rows']:
            n=row['name'];typ=next(iter(row_ref(a,n)));wanted=substitute(row_fact(row,typ),reverse)
            if exact('Eq' if typ=='RowEq' else 'Le',wanted):ref='Exact'
            elif n=='R2302':ref=p.lin('Le',[[hi[0],1],[hi[1],1]],wanted)
            elif n=='R2303':ref=p.lin('Le',[[lo[2],2]],wanted)
            elif n in tightened:
                yn=next(yn for yn,d in h['link_bounds'].items() if d['row']==n);d=h['link_bounds'][yn]
                ref=p.lin('Le',[[row_ref(b,n),1],[{'VarLower':b['var_index'][yn]},950-F(d['new_M'])]],wanted)
            else:ref=row_ref(b,n)
            assert ref=='Exact' or p.refexpr(ref)==wanted;checks.append(ref)
        assert substitute(a['objective'],reverse)==b['objective'];checks+=['Exact']*(1+len(common))
        claims.append({'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in common],'inverse':None})
        body={'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':checks}}}
        blocks.append({'steps':pre.steps,'end':{'IntervalLift':{'intervals':[interval],'body':body}}})
    w=h['smoke_witnesses'];cheap=a['var_index'][w['cheapest_site']];high=a['var_index'][w['costly_site']];eps=F(w['fraction']);point=[F(0)]*len(a['vars'])
    for y,fraction in [(cheap,1-eps),(high,eps)]:
        u=groups[y][0]
        for i in loads[u][1][1]:point[i]=fraction
        point[y]=1 if y==cheap else eps
    for n in w['required_pair']:point[a['var_index'][n]]=1
    point[z]=F(set(w['required_pair'])=={a['vars'][i]['name'] for i in special[:2]})
    for u,(r,e) in loads.items():point[u]=sum(c*point[i] for i,c in e[1].items())
    tvar=a['var_index']['C0001'];point[tvar]=max(sum(-c*point[i] for i,c in a['rows'][a['row_index'][f'R{k+1:04d}']]['terms'].items() if i!=tvar) for k in range(950))
    for i,v in enumerate(a['vars']):assert (v['lower'] is None or point[i]>=v['lower']) and (v['upper'] is None or point[i]<=v['upper'])
    for row in a['rows']:
        e=row_fact(row,next(iter(row_ref(a,row['name']))));value=e[0]+sum(c*point[i] for i,c in e[1].items())
        assert value==0 if row['sense']=='E' else value<=0
    separating=b['rows'][b['row_index'][w['fractional_violation']]];e=row_fact(separating,'RowUpper')
    violation=e[0]+sum(c*point[common[i][0]] for i,c in e[1].items());assert violation>0
    terms=[[row_ref(b,separating['name']),'1']]+[[{'RowEq':len(b['rows'])+i},str(-c)] for i,c in e[1].items()]
    refutation={'steps':[{'Lin':{'id':0,'kind':'Le','constant':'0','terms':terms}}],'end':{'Absurd':{'fact':{'Local':0}}}}
    points=[{'claim':{'FiberStrictness':{'inclusion_claim':2}},'values':[str(x) for x in point],'refutation':refutation}]
    return {'claims':claims,'blocks':blocks,'points':points},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'eliminated_loads':len(loads),'tightened_activations':len(tightened),'selector_intervals_per_reverse':1,'retained_coordinates_per_claim':len(common),'claims':3,'fiber_contradiction':str(violation),'thresholds':thresholds}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test10-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test10'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/changes.json';k=args.kernel.resolve()
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(hint.read_text()));rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 6\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[x['claim'] for x in cert['points']]},separators=(',',':'))+'\n')
    d={'case_id':'test10','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(hint),'sha256':sha(hint)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[],
       'claims':'Full retained-coordinate MI projection and every objective value in both directions; target LP inclusion with full load and selector reconstruction; a complete source LP point and target observation-fiber refutation prove strict projected LP strengthening. No feasible-point bijection is requested.'}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    save()
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        now=time.perf_counter();p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'elapsed_seconds':time.perf_counter()-now,'stdout':p.stdout,'stderr':p.stderr});save()
        if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};save()
    print(json.dumps({'case_id':'test10','status':d['status'],'rpa_bytes':d['rpa_bytes'],'preparation_seconds':d['preparation_seconds'],'result':json.loads(d['kernel_runs'][-1]['stdout'])},indent=2))


if __name__=='__main__':main()
