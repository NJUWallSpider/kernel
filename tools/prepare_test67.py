#!/usr/bin/env python3
"""Actual four activation fixes, scalar coloring refutations, and full attainment."""
from collections import defaultdict,ChainMap,deque
from fractions import Fraction as F
from pathlib import Path
import argparse,json,re,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder
from prepare_test73 import split,execute,pop_mutation


def local_setup(a,g,p):
    edges=[];packing=[];activation=[a['var_index'][f'c{k}'] for k in range(4)]
    for edge in g['internal_edges']:
        variables=[a['var_index'][edge['variables_by_color'][f'c{k}']] for k in range(4)];ref=row_ref(a,edge['row']);assert p.kind(ref)=='Eq' and p.refexpr(ref)==expression(-1,{v:1 for v in variables});edges.append((variables,ref))
    allvars={v for vs,_ in edges for v in vs};assert len(allvars)==68
    for vertex,names in sorted(g['local_vertices'].items(),key=lambda kv:int(kv[0])):
        for k in range(4):
            ref=row_ref(a,names[f'c{k}']);e=p.refexpr(ref);c=activation[k];assert e[0]==0 and e[1][c]==-1 and all(q==1 for v,q in e[1].items() if v!=c)
            local=sorted(set(e[1])&allvars);external=set(e[1])-allvars-{c}
            reduced=p.lin('Le',[[ref,1]]+[[{'VarLower':v},1] for v in sorted(external)],expression(0,{**{v:1 for v in local},c:-1})) if external else ref
            packed=p.lin('Le',[[reduced,1],[{'VarUpper':c},1]],expression(-1,{v:1 for v in local}));packing.append((local,packed,reduced,k))
    return activation,edges,packing


def refute(p,disabled,zero,edges,packing,activation,stats):
    assigned={}
    for variables,_,reduced,k in packing:
        if k!=disabled:continue
        for x in variables:
            if x not in assigned:assigned[x]=(0,p.lin('Le',[[reduced,1],[zero,1]]+[[{'VarLower':y},1] for y in variables if y!=x],expression(0,{x:1})))
    def search(b,state,depth):
        stats['search_nodes']+=1;stats['maximum_depth']=max(stats['maximum_depth'],depth)
        while True:
            changed=False
            for variables,eq in edges:
                ones=[v for v in variables if state.get(v,(None,))[0]==1];unknown=[v for v in variables if v not in state];zeros=[v for v in variables if state.get(v,(None,))[0]==0]
                if len(ones)>=2:
                    terms=[[eq,1]]+[[state[v][1],1] for v in ones]+[[{'VarLower':v},1] for v in variables if v not in ones]
                    return {'Absurd':b.lin('Le',terms,expression(len(ones)-1))}
                if not ones and not unknown:return {'Absurd':b.lin('Le',[[eq,-1]]+[[state[v][1],1] for v in variables],expression(1))}
                if ones:
                    for x in unknown:
                        terms=[[eq,1],[state[ones[0]][1],1]]+[[{'VarLower':v},1] for v in variables if v not in (x,ones[0])]
                        state[x]=(0,b.lin('Le',terms,expression(0,{x:1})));changed=True
                elif len(unknown)==1:
                    x=unknown[0];state[x]=(1,b.lin('Le',[[eq,-1]]+[[state[v][1],1] for v in zeros],expression(1,{x:-1})));changed=True
            for variables,packed,_,_ in packing:
                ones=[v for v in variables if state.get(v,(None,))[0]==1];unknown=[v for v in variables if v not in state]
                if len(ones)>=2:
                    selected=ones[:2];terms=[[packed,1]]+[[state[v][1],1] for v in selected]+[[{'VarLower':v},1] for v in variables if v not in selected]
                    return {'Absurd':b.lin('Le',terms,expression(1))}
                if ones:
                    for x in unknown:
                        terms=[[packed,1],[state[ones[0]][1],1]]+[[{'VarLower':v},1] for v in variables if v not in (x,ones[0])]
                        state[x]=(0,b.lin('Le',terms,expression(0,{x:1})));changed=True
            if not changed:break
        choices=[(len(unknown),index,unknown) for index,(vs,_) in enumerate(edges) if (unknown:=[v for v in vs if v not in state])]
        assert choices,'Local coloring unexpectedly feasible'
        _,_,unknown=min(choices);x=unknown[0]
        def branch(child,assumption,value):return search(child,{**state,x:(value,assumption)},depth+1)
        result=split(b,expression(1),x,lambda child,assumption:branch(child,assumption,0),lambda child,assumption:branch(child,assumption,1));return {'Absurd':result}
    return search(p,assigned,0)


def color_point(a):
    """Construct each actual 12-vertex block with stubs, then match bridge colors."""
    graph=defaultdict(list);edges=[];edgevars=[]
    for row in a['rows']:
        if row['sense']!='E':continue
        colors={};ends=None
        for v,q in row['terms'].items():
            match=re.fullmatch(r'x(\d+)_(\d+)_(\d+)',a['vars'][v]['name']);assert match and q==1
            u,w,c=map(int,match.groups());assert ends is None or ends==(u,w);ends=(u,w);colors[c]=v
        assert set(colors)==set(range(4));idx=len(edges);edges.append(ends);edgevars.append(colors)
        for u in ends:graph[u].append(idx)
    assert len(edges)==9215
    # Iterative Tarjan bridge search avoids recursion on the full graph.
    discovered={};low={};parent={};bridges=set();clock=0
    for root in sorted(graph):
        if root in discovered:continue
        discovered[root]=low[root]=clock;clock+=1;stack=[(root,iter(graph[root]))]
        while stack:
            u,it=stack[-1]
            try:ei=next(it)
            except StopIteration:
                stack.pop()
                if u in parent:
                    par,pe=parent[u];low[par]=min(low[par],low[u])
                    if low[u]>discovered[par]:bridges.add(pe)
                continue
            if u in parent and ei==parent[u][1]:continue
            v=edges[ei][0] if edges[ei][1]==u else edges[ei][1]
            if v not in discovered:parent[v]=(u,ei);discovered[v]=low[v]=clock;clock+=1;stack.append((v,iter(graph[v])))
            else:low[u]=min(low[u],discovered[v])
    component={};members=[]
    for root in sorted(graph):
        if root in component:continue
        cid=len(members);vertices=[];queue=[root];component[root]=cid
        while queue:
            u=queue.pop();vertices.append(u)
            for ei in graph[u]:
                if ei in bridges:continue
                v=edges[ei][0] if edges[ei][1]==u else edges[ei][1]
                if v not in component:component[v]=cid;queue.append(v)
        members.append(sorted(vertices))
    assert len(bridges)==511 and len(members)==512 and all(len(vs)==12 for vs in members)
    locals=[]
    for vs in members:
        actual=sorted({ei for v in vs for ei in graph[v]});used={v:set() for v in vs};local={};support={ei:[v for v in edges[ei] if v in used] for ei in actual}
        def search():
            if len(local)==len(actual):return True
            choices=[]
            for ei in actual:
                if ei in local:continue
                available=sorted(set(range(4))-set().union(*(used[v] for v in support[ei])));choices.append((len(available),-len(support[ei]),ei,available))
            _,_,ei,available=min(choices)
            for color in available:
                local[ei]=color
                for v in support[ei]:used[v].add(color)
                if search():return True
                for v in support[ei]:used[v].remove(color)
                del local[ei]
            return False
        assert search();locals.append(local)
    blocktree=defaultdict(list)
    for ei in sorted(bridges):
        u,v=edges[ei];c,d=component[u],component[v];blocktree[c].append((d,ei));blocktree[d].append((c,ei))
    full={};visited={0};queue=deque([(0,None)])
    while queue:
        cid,incoming=queue.popleft();perm=list(range(4))
        if incoming is not None:
            localcolor=locals[cid][incoming];required=full[incoming];perm[localcolor],perm[required]=perm[required],perm[localcolor]
        for ei,c in locals[cid].items():
            value=perm[c];assert ei not in full or full[ei]==value;full[ei]=value
        for child,ei in sorted(blocktree[cid]):
            if child not in visited:visited.add(child);queue.append((child,ei))
    assert len(full)==len(edges) and len(visited)==len(members)
    point=[0]*len(a['vars'])
    for k in range(4):point[a['var_index'][f'c{k}']]=1
    for ei,color in full.items():point[edgevars[ei][color]]=1
    for row in a['rows']:
        value=sum(q*point[v] for v,q in row['terms'].items());assert value==row['rhs'] if row['sense']=='E' else value<=row['rhs']
    return point,{'coloring_vertices':len(graph),'coloring_edges':len(edges),'coloring_blocks':len(members),'coloring_bridges':len(bridges)}


def prepare(a,b,g,h):
    assert [v['name'] for v in a['vars']]==[v['name'] for v in b['vars']] and a['objective']==b['objective'];n=len(a['vars']);f=SparseBuilder(a);activation,edges,packing=local_setup(a,g,f);fixed={};stats={'search_nodes':0,'maximum_depth':0}
    for k,c in enumerate(activation):
        wanted=expression(1,{c:-1})
        fixed[c]=split(f,wanted,c,lambda child,zero,k=k:refute(child,k,zero,edges,packing,activation,stats),lambda child,one:{'Witness':one})
    claims=[];blocks=[];mapping=[expr_json(expression(0,{i:1})) for i in range(n)];projection=[[i,i] for i in range(n)]
    for index,back in enumerate((False,True)):
        inp,out=(b,a) if back else (a,b);p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            assert v['integer'] and v['upper']==1
            checks.append(fixed[i] if not back and i in fixed else p.lin('Le',[[{'VarLower':i},1]],expression(0,{i:-1}),constant=-1) if back and i in fixed else {'VarLower':i});checks.extend([{'VarUpper':i},{'VarInt':i}])
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));wanted=row_fact(row,typ);original=inp['rows'][inp['row_index'][rn]]
            if row==original:ref=row_ref(inp,rn)
            else:
                control=next(i for i in activation if i in (a['rows'][a['row_index'][rn]]['terms']));assert row['sense']=='L'
                # Forward: -c is removed using c<=1. Reverse: restore it using c>=1.
                ref=p.lin('Le',[[row_ref(inp,rn),1],[{'VarUpper':control} if not back else {'VarLower':control},1]],wanted)
            checks.append(ref)
        checks+=['Exact']*(1+2*n);claim={'reverse':back,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':1-index}
        if not back:
            claim['input_objective_lower']='4';checks.append(p.lin('Le',[[fixed[c],1] for c in activation],expression(4,{c:-1 for c in activation})))
        claims.append(claim);blocks.append({'steps':p.steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    point,colorcounts=color_point(a);pointclaim={'Feasible':{'target':False,'integers':True,'objective':'4'}};cert={'claims':claims,'blocks':blocks,'points':[{'claim':pointclaim,'values':[str(v) for v in point]}]};request={'claims':claims,'points':[pointclaim]}
    counts={'source_variables':n,'target_variables':n,'source_rows':len(a['rows']),'target_rows':len(b['rows']),'fixed_activations':4,'substituted_rows':sum(len(v['rows']) for v in h['substitutions'].values()),'local_edges':17,'local_binary_variables':68,**stats,**colorcounts,'claims':2,'points':1,'steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}
    return cert,request,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test67-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test67'));ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();source=run/'input/model.mps';target=run/'output/model.mps';audit=run/'output/audit.json';cert,request,counts=prepare(parse_mps(source),parse_mps(target),json.loads((run/'output/certificate.json').read_text()),json.loads(audit.read_text()))
    root=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s);local=root['left']['steps'][0]['Lin']['terms'];reverse=cert['blocks'][1]['steps'][-1]['Lin']['terms']
    def point_mutation():
        values=cert['points'][0]['values'];i=next(i for i,v in enumerate(values[4:],4) if v=='1');old=values[i];values[i]='0';return lambda:values.__setitem__(i,old)
    mutations=[('missing_inactive_color_assumption','Drops activation=0 from a local forbidden-color bound.',lambda:pop_mutation(local,1)),('missing_reverse_fixed_activation','Drops c>=1 from a substituted source row reconstruction.',lambda:pop_mutation(reverse)),('invalid_complete_coloring','Removes a selected edge color from the complete source feasible point.',point_mutation),('missing_inverse_coordinate','Drops an identity-inverse obligation.',lambda:pop_mutation(cert['blocks'][1]['end']['Return']['checks']))]
    execute('test67',source,target,audit,cert,request,counts,'Same complete original-coordinate integer feasible assignments and pointwise objective after all four activations are proved fixed to one by explicit bounded local coloring refutations with scalar propagation and Cases. Every actual substituted row, bound, domain, objective and full inverse identity is checked. Original feasibility and minimum objective exactly 4 are certified by input_objective_lower and a complete Feasible integer point with objective 4. No LP equivalence or symmetry restriction is asserted.',args.out.resolve(),args.kernel.resolve(),Path(__file__).resolve(),start,mutations,version=6)

if __name__=='__main__':main()
