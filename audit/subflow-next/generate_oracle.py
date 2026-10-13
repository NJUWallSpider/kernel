#!/usr/bin/env python3
"""Independent Fraction constructions and field oracles, outside the TCB."""
from collections import deque
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import hashlib,json,random

ROOT=Path(__file__).resolve().parents[2]

def divergence(n,arcs,values):
    d=[Q(0)]*n
    for (u,v),x in zip(arcs,values):d[u]+=x;d[v]-=x
    return d

def expr(c=0,terms=()):
    acc={}
    for i,q in terms:acc[i]=acc.get(i,Q(0))+q
    return {'constant':str(c),'terms':[[i,str(q)] for i,q in sorted(acc.items()) if q]}

def construct(n,arcs,s,demands,f):
    assert n>=1 and all(0<=v<n and v!=s and d>=0 for v,d in demands)
    assert all(v>=0 for v in f)
    B=sum((d for _,d in demands),Q(0));rhs=[Q(0)]*n;rhs[s]=B
    for v,d in demands:rhs[v]-=d
    assert divergence(n,arcs,f)==rhs
    m=len(arcs);sink=n;extra=[(v,d,i) for i,(v,d) in enumerate(demands) if d>0]
    edges=list(arcs)+[(v,sink) for v,d,i in extra]
    residual=list(f)+[d for v,d,i in extra];kept=[Q(0)]*m;adj=[[] for _ in range(n+1)]
    for e,(u,v) in enumerate(edges):adj[u].append((v,e))
    paths=[];remaining=B
    while remaining:
        parent={s:None};queue=deque([s])
        while queue and sink not in parent:
            u=queue.popleft()
            for v,e in adj[u]:
                if residual[e]>0 and v not in parent:parent[v]=(u,e);queue.append(v)
        assert sink in parent
        path=[];v=sink
        while v!=s:v,e=parent[v];path.append(e)
        path.reverse();amount=min(residual[e] for e in path);assert amount>0
        for e in path:
            residual[e]-=amount
            if e<m:kept[e]+=amount
        remaining-=amount;assert remaining>=0
        paths.append({'edges':path[:-1],'demand_index':extra[path[-1]-m][2],'amount':str(amount)})
    assert len(paths)<=m+len(extra)
    assert divergence(n,arcs,kept)==rhs
    assert all(0<=g<=x and g<=B for g,x in zip(kept,f))
    # Expected symbolic fields independently assembled, never read from Rust.
    premises=[{'kind':'Le','expression':expr(0,[(e,-1)])} for e in range(m)]
    rows=[]
    for v in range(n):
        terms=[(e,int(u==v)-int(w==v)) for e,(u,w) in enumerate(arcs)]
        premises.append({'kind':'Eq','expression':expr(-rhs[v],terms)})
        rows.append({'expression':expr(0,[(m+e,c) for e,c in terms]),'lower':str(rhs[v]),'upper':str(rhs[v])})
    for e in range(m):rows.append({'expression':expr(0,[(e,-1),(m+e,1)]),'lower':None,'upper':'0'})
    return {'nodes':n,'arcs':arcs,'source':s,'demands':[[v,str(d)] for v,d in demands],'flows':list(map(str,f)),
            'kept':list(map(str,kept)),'B':str(B),'rhs':list(map(str,rhs)),'paths':paths,'premises':premises,'rows':rows}

def generate():
    old=ROOT/'tests/vectors/flow_prune_oracle.json';legacy=json.loads(old.read_text())
    cases=[]
    for c in legacy['cases']:
        demands=[(v,Q(d)) for v,d in c['commodities'] if v!=c['source']]
        cases.append(construct(c['nodes'],[tuple(x) for x in c['arcs']],c['source'],demands,list(map(Q,c['flows']))))
    families={'legacy_rebound':len(cases)}
    explicit=[(1,[],0,[],[]),(2,[],0,[(1,Q(0))],[]),(2,[(0,1),(0,1),(1,0)],0,[(1,Q(82))],[Q(82)]*3),
              (4,[(0,1),(1,0),(2,3),(3,2),(0,0)],0,[],[Q(7),Q(7),Q(9),Q(9),Q(21)]),
              (3,[(0,1),(1,2),(2,0),(0,2)],0,[(1,Q(1,3)),(2,Q(1,7)),(2,Q(2,7)),(1,Q(0))],[Q(7,3),Q(2),Q(2),Q(3,7)])]
    for args in explicit:cases.append(construct(*args))
    families['explicit']=len(explicit)
    before=len(cases)
    # Exhaustive finite coefficient domains; do not assume the oracle's generator
    # created path sums. Filter directly by the independently computed balance.
    for n,arcs,levels in [(2,[(0,1),(0,1),(1,0),(0,0)],(Q(0),Q(1,2),Q(1),Q(3,2))),
                          (3,[(0,1),(1,0),(0,2),(2,0),(1,2),(2,1)],(Q(0),Q(1,2)))]:
        for f in product(levels,repeat=len(arcs)):
            d=divergence(n,arcs,f)
            for s in range(n):
                if d[s]>=0 and all(x<=0 for v,x in enumerate(d) if v!=s):
                    cases.append(construct(n,arcs,s,[(v,-x) for v,x in enumerate(d) if v!=s and x<0],list(f)))
    families['exhaustive_balance_filtered']=len(cases)-before
    rng=random.Random(2026101158);before=len(cases)
    for sample in range(360):
        n=rng.randrange(1,11);s=rng.randrange(n);arcs=[];f=[];demands=[]
        def add(u,v,value):
            same=[e for e,a in enumerate(arcs) if a==(u,v)]
            if same and rng.randrange(4):f[rng.choice(same)]+=value
            else:arcs.append((u,v));f.append(value)
        for _ in range(rng.randrange(8)):
            if n==1:break
            sink=rng.choice([v for v in range(n) if v!=s]);d=Q(rng.randrange(8),rng.randrange(1,17));demands.append((sink,d))
            middle=[v for v in range(n) if v not in (s,sink)];rng.shuffle(middle)
            nodes=[s]+middle[:rng.randrange(len(middle)+1)]+[sink]
            for u,v in zip(nodes,nodes[1:]):add(u,v,d)
        for _ in range(rng.randrange(9)):
            nodes=rng.sample(range(n),rng.randrange(1,n+1));d=Q(rng.randrange(1,70),rng.randrange(1,19))
            for u,v in zip(nodes,nodes[1:]+nodes[:1]):add(u,v,d)
        # Reindex nodes and arcs without making ordering an authority.
        order=list(range(n));rng.shuffle(order);perm=list(range(len(arcs)));rng.shuffle(perm)
        scale=Q(rng.randrange(1,6),rng.randrange(1,7))
        arcs=[(order[arcs[e][0]],order[arcs[e][1]]) for e in perm];f=[f[e]*scale for e in perm]
        demands=[(order[v],d*scale) for v,d in demands]
        cases.append(construct(n,arcs,order[s],demands,f))
    families['random_shared_arc_permuted_scaled']=len(cases)-before
    return {'schema':'isolated-subflow-oracle-2','seed':2026101158,'arithmetic':'Python Fraction; adjacency-list supersink extraction',
            'legacy_path':str(old.relative_to(ROOT)),'legacy_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'families':families,'cases':cases}

if __name__=='__main__':
    p=Path(__file__).with_name('fixtures')/'oracle.json';d=generate();p.write_text(json.dumps(d,separators=(',',':'))+'\n')
    print(json.dumps({'status':'PASS','families':d['families'],'cases':len(d['cases']),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
