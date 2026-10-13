#!/usr/bin/env python3
"""Independent exact structural audit of actual test80, without accepting a proof.

The final relation is an optimal-face bijection, not whole-feasible-set equality.
No corpus file or trusted source is modified. Old audit data is compared only
after reconstructing the complete structure from the independently read models.
"""
from collections import Counter,defaultdict,deque
from fractions import Fraction as F
from pathlib import Path
import argparse,json,re,subprocess,sys,time
from prepare_affine import parse_mps
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha


def subst(e,mapping):
    c=e[0];terms=defaultdict(F)
    for i,a in e[1].items():
        z,t=mapping[i];c+=a*z
        for j,b in t.items():terms[j]+=a*b
    return expression(c,{i:a for i,a in terms.items() if a})


def value(e,x):return e[0]+sum((a*x[i] for i,a in e[1].items()),F(0))


def feasible(m,x):
    assert len(x)==len(m['vars'])
    for v,z in zip(m['vars'],x):
        assert (v['lower'] is None or z>=v['lower']) and (v['upper'] is None or z<=v['upper'])
        assert not v['integer'] or z.denominator==1
    for r in m['rows']:
        z=value(expression(0,r['terms']),x)
        assert {'E':z==r['rhs'],'L':z<=r['rhs'],'G':z>=r['rhs']}[r['sense']],r['name']
    return value(m['objective'],x)


def inspect(a,b,h):
    ai,bi=a['var_index'],b['var_index']
    xs=[[ai[f'x({i},{j})'] for j in range(16)] for i in range(470)]
    ys=[[ai[f'y({i},{j})'] for j in range(16)] for i in range(221)]
    ps=[[ai[f'p({i},{j})'] for j in range(15)] for i in range(221)]
    bs=[ai[f'b({j})'] for j in range(16)]
    allx=sum(xs,[]);ally=sum(ys,[]);allp=sum(ps,[])
    assert sorted(allx+ally+allp+bs)==list(range(len(a['vars'])))
    assert len(a['vars'])==14387 and len(a['rows'])==10765
    for v in a['vars']:
        lo=F(1) if v['name'] in {f'b({j})' for j in range(8)} else F(0)
        assert v=={'name':v['name'],'integer':True,'lower':lo,'upper':F(1)}
    assert a['objective']==expression(0,{**dict.fromkeys(allp,F(1)),**dict.fromkeys(bs,F(-10))})
    seen=set()
    def row(name,sense,rhs,terms):
        idx=a['row_index'][name];actual=a['rows'][idx]
        assert actual=={'name':name,'sense':sense,'rhs':F(rhs),'terms':terms},name
        assert idx not in seen;seen.add(idx);return idx
    assignment=[row(f'assign_row_{i}','E',1,dict.fromkeys(x,F(1))) for i,x in enumerate(xs)]
    linked={};link_rows={};ynames={idx:(t,j) for t,y in enumerate(ys) for j,idx in enumerate(y)}
    for r in a['rows']:
        match=re.fullmatch(r'row2var_(\d+)_(\d+)_1',r['name'])
        if not match:continue
        i,j=map(int,match.groups());assert 0<=i<470 and 0<=j<16
        members=[]
        for idx,c in r['terms'].items():
            if idx==xs[i][j]:assert c==-1
            else:
                t,position=ynames[idx];assert position==j and c==1;members.append(t)
        members=sorted(members);assert members
        if i in linked:assert linked[i]==members
        else:linked[i]=members
    assert len(linked)==300 and set(t for members in linked.values() for t in members)==set(range(221))
    for i,members in sorted(linked.items()):
        k=len(members);entries=[]
        for j in range(16):
            common={ys[t][j]:F(1) for t in members}
            upper=row(f'row2var_{i}_{j}_1','L',k-1,{**common,xs[i][j]:F(-1)})
            lower=row(f'row2var_{i}_{j}_2','G',0,{**common,xs[i][j]:F(-k)})
            entries.append([upper,lower])
            # Symbolic existing-Lin/Round implication for every actual member.
            for t in members:
                e=row_fact(a['rows'][lower],'RowLower')
                for u in members:
                    if u!=t:e=plus(e,expression(-1,{ys[u][j]:1}))
                e=mul(e,F(1,k));e=plus(e,expression(0,{ys[t][j]:-1}),1-F(1,k))
                assert e==expression(-F(k-1,k),{xs[i][j]:1,ys[t][j]:-1})
        link_rows[i]=entries
    pass_rows=[]
    for t in range(221):
        pterms=dict.fromkeys(ps[t],F(1));difference={**dict.fromkeys(ys[t],F(1)),**dict.fromkeys(ps[t],F(-1))}
        pass_rows.append([row(f'passonand_{t}','L',1,pterms),row(f'passon_{t}_lhs','G',0,difference),row(f'passon_{t}_rhs','L',1,difference)])
    globals_=[row('rowsizelb_','G',0,{**dict.fromkeys(allx,F(1)),**dict.fromkeys(bs,F(-10))}),row('varsizelb_','G',0,{**dict.fromkeys(ally,F(1)),**dict.fromkeys(bs,F(-10))})]
    empty=[]
    for idx,r in enumerate(a['rows']):
        if idx in seen:continue
        assert not r['terms'] and r['rhs']==0 and r['sense'] in ('G','L');empty.append(idx);seen.add(idx)
    assert len(empty)==30 and seen==set(range(len(a['rows'])))

    # Graph built from actual complete sets, not the old audit's edge list.
    adj={t:{} for t in range(221)}
    for i,members in sorted(linked.items()):
        first=members[0]
        for t in members[1:]:adj[first].setdefault(t,i);adj[t].setdefault(first,i)
    components=[];spanning=[];unseen=set(adj)
    while unseen:
        root=min(unseen);unseen.remove(root);component=[root];queue=deque([root])
        while queue:
            parent=queue.popleft()
            for t,i in sorted(adj[parent].items()):
                if t in unseen:
                    unseen.remove(t);component.append(t);queue.append(t);spanning.append({'from':parent,'to':t,'assignment':i})
        components.append(sorted(component))
    co={t:min(c) for c in components for t in c};unlinked=sorted(set(range(470))-set(linked))
    assert [(min(c),len(c)) for c in components]==[(0,183),(1,18),(60,18),(68,1),(195,1)] and len(unlinked)==170
    groups={f'component_{min(c)}':[f'g_{min(c)}_{j}' for j in range(16)] for c in components}
    groups.update({f'unlinked_{i}':[f'u_{i}_{j}' for j in range(16)] for i in unlinked})
    assert set(bi)=={'obj_constant'}|{v for names in groups.values() for v in names}
    assert set(b['row_index'])==set(groups) and len(b['vars'])==2801
    for v in b['vars']:
        assert v=={'name':v['name'],'integer':True,'lower':F(v['name']=='obj_constant'),'upper':F(1)}
    for r in b['rows']:assert r=={'name':r['name'],'sense':'E','rhs':F(1),'terms':dict.fromkeys([bi[n] for n in groups[r['name']]],F(1))}
    assert b['objective']==expression(0,{bi['obj_constant']:F(-160)})
    forward=[None]*len(b['vars']);reverse=[None]*len(a['vars'])
    for i,x in enumerate(xs):
        if i in linked:
            assert len({co[t] for t in linked[i]})==1
            target=[bi[f'g_{co[linked[i][0]]}_{j}'] for j in range(16)]
        else:
            target=[bi[f'u_{i}_{j}'] for j in range(16)]
            for src,dst in zip(x,target):forward[dst]=expression(0,{src:1})
        for src,dst in zip(x,target):reverse[src]=expression(0,{dst:1})
    for t,y in enumerate(ys):
        for j,src in enumerate(y):reverse[src]=expression(0,{bi[f'g_{co[t]}_{j}']:1})
    for c in components:
        t=min(c)
        for j in range(16):forward[bi[f'g_{t}_{j}']]=expression(0,{ys[t][j]:1})
    for idx in allp:reverse[idx]=expression()
    for idx in bs:reverse[idx]=expression(1)
    forward[bi['obj_constant']]=expression(1)
    assert all(e is not None for e in forward+reverse)
    assert subst(a['objective'],reverse)==expression(-160)
    # Complete reverse constraints, derived afresh from actual mapped rows.
    row_certificates=[];residuals=Counter()
    target_group={i:r for r in b['rows'] for i in r['terms']}
    for r in a['rows']:
        which={'E':'RowEq','L':'RowUpper','G':'RowLower'}[r['sense']]
        e=subst(row_fact(r,which),reverse);terms=[]
        touched={target_group[i]['name'] for i in e[1]}
        for name in sorted(touched):
            target=b['rows'][b['row_index'][name]]
            ids=list(target['terms']);weights={e[1].get(idx,F(0)) for idx in ids}
            if len(weights)==1:
                weight=next(iter(weights))
                if weight:
                    terms.append([b['row_index'][target['name']],str(weight)])
                    e=plus(e,row_fact(target,'RowEq'),-weight)
        maximum=e[0]
        for i,c in e[1].items():maximum+=c*(b['vars'][i]['upper'] if c>0 else b['vars'][i]['lower'])
        if r['sense']=='E':assert e==expression()
        else:assert maximum<=0
        residuals[str(maximum)]+=1
        row_certificates.append({'source_row':a['row_index'][r['name']],'kind':'Eq' if r['sense']=='E' else 'Le','target_equalities':terms,'residual':expr_json(e),'residual_maximum':str(maximum)})
    for idx,e in enumerate(reverse):
        v=a['vars'][idx];assert e[0].denominator==1 and all(c.denominator==1 for c in e[1].values())
        minimum=e[0]+sum((c*b['vars'][j]['lower'] for j,c in e[1].items()),F(0))
        maximum=e[0]+sum((c*b['vars'][j]['upper'] for j,c in e[1].items()),F(0))
        assert v['lower']<=minimum<=maximum<=v['upper']
    # Compare the old material only as a checked hint, never as proof authority.
    assert linked=={int(i):ts for i,ts in h['linked_assignment_sets'].items()}
    assert components==sorted(h['components'].values()) and unlinked==h['unlinked_assignments'] and groups==h['final_assignment_groups']
    for v,e in zip(a['vars'],reverse):
        hint=h['original_variable_reconstruction'][v['name']]
        expected=expression(F(hint['constant'])) if 'constant' in hint else expression(0,{bi[hint['variable']]:1})
        assert e==expected
    assert len(h['original_variable_reconstruction'])==len(a['vars'])
    # Independent finite local truth check, distinct from symbolic Round algebra.
    local_checks=0
    for k in sorted({len(v) for v in linked.values()}):
        for bits in range(1<<k):
            total=bin(bits).count('1')
            for x in (0,1):
                assert (total-x<=k-1 and total-k*x>=0)==(x==int(total==k));local_checks+=1
    samples=[]
    for test in range(23):
        point=[F(0)]*len(b['vars']);point[bi['obj_constant']]=F(1)
        for g,names in enumerate(groups.values()):
            j=0 if test==0 else 15 if test==1 else (g*(2*test+1)+test)%16
            point[bi[names[j]]]=F(1)
        lifted=[value(e,point) for e in reverse]
        assert feasible(b,point)==feasible(a,lifted)==-160
        assert [value(e,lifted) for e in forward]==point
        samples.append({'case':test,'source_objective':'-160','target_objective':'-160','all_domains_rows_and_roundtrip':True})
    source_point=[value(e,[F(int(i==bi['obj_constant'] or (v['name'].endswith('_0')))) for i,v in enumerate(b['vars'])]) for e in reverse]
    assert feasible(a,source_point)==-160
    suboptimal=source_point.copy();suboptimal[ps[0][0]]=F(1)
    assert feasible(a,suboptimal)==-159
    return {'status':'STRUCTURALLY_AUDITED_NOT_CERTIFIED','required_contract':'All original integer optimizers bijectively parameterized by the actual target; attained minimum -160. No full-feasible-set or LP-equivalence claim.',
        'missing_capability':'Caller-bound exact objective-level input domains and mandatory opposing-inverse domain closure; design docs/OBJECTIVE_LEVEL_DESIGN.md.',
        'dimensions':{'source_variables':len(a['vars']),'source_rows':len(a['rows']),'source_row_terms':sum(len(r['terms']) for r in a['rows']),'target_variables':len(b['vars']),'target_rows':len(b['rows']),'target_row_terms':sum(len(r['terms']) for r in b['rows'])},
        'full_structure':'ALL_FIELDS_EQUAL','source_x':xs,'source_y':ys,'source_p':ps,'source_b':bs,'assignment_rows':assignment,'linked_sets':linked,'link_rows':link_rows,'pass_rows':pass_rows,'global_rows':globals_,'empty_rows':empty,
        'components':components,'spanning_edges':spanning,'unlinked_assignments':unlinked,'target_groups':{name:[bi[v] for v in names] for name,names in groups.items()},
        'forward_map':[expr_json(e) for e in forward],'reverse_map':[expr_json(e) for e in reverse],'reverse_row_certificates':row_certificates,'residual_maximum_counts':dict(residuals),
        'lower_bound':'objective + 160 = sum(P) + 10 sum(1-B)','objective_level':'-160','source_attainment_values':[str(z) for z in source_point],
        'suboptimal_witness':{'changes_from_attainment':[[ps[0][0],'1']],'objective':'-159','all_actual_bounds_rows_checked':True},'local_and_truth_checks':local_checks,'full_point_roundtrip_checks':samples}


def canonical_json(m):
    def q(v):return None if v is None else str(v)
    return {'name':m['name'],'vars':[{**v,'lower':q(v['lower']),'upper':q(v['upper'])} for v in m['vars']],
        'rows':[{'name':r['name'],'expr':expr_json(expression(0,r['terms'])),'lower':q(r['rhs']) if r['sense'] in ('E','G') else None,'upper':q(r['rhs']) if r['sense'] in ('E','L') else None} for r in m['rows']],
        'objective':expr_json(m['objective'])}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test80-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test80'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json'
    a,b=parse_mps(source),parse_mps(target);evidence=inspect(a,b,json.loads(hint.read_text()))
    evidence.update(case_id='test80',source={'path':str(source),'sha256':sha(source)},target={'path':str(target),'sha256':sha(target)},hint={'path':str(hint),'sha256':sha(hint)},auditor={'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))})
    if args.kernel:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'));from lp_parse_sweep import Reader
        kernel=args.kernel.resolve();runs=[]
        for role,model,path in [('source',a,source),('target',b,target)]:
            output=out/f'{role}.mcm';command=[str(kernel),'canonical',str(path),str(output)];p=subprocess.run(command,capture_output=True,text=True)
            assert p.returncode==0,(p.stdout,p.stderr)
            assert Reader(output.read_bytes()).model()==canonical_json(model)
            runs.append({'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'independent_fraction_comparison':'ALL_FIELDS_EQUAL','output_sha256':sha(output)})
        evidence['canonical_crosscheck']={'kernel':str(kernel),'kernel_sha256':sha(kernel),'runs':runs}
    evidence['elapsed_seconds']=time.perf_counter()-start
    (out/'optimal_face_structure.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:evidence[k] for k in ['case_id','status','dimensions','full_structure','residual_maximum_counts','local_and_truth_checks','elapsed_seconds']},indent=2),flush=True)


if __name__=='__main__':main()
