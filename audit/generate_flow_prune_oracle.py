#!/usr/bin/env python3
"""Independent exact common-source subflow oracle; not production verification."""
from collections import deque
from fractions import Fraction as F
from pathlib import Path
import json,random


def prune(n,arcs,source,commodities,values):
    residual=list(values);kept=[F(0)]*len(arcs)
    for sink,demand in commodities:
        remaining=demand if sink!=source else F(0)
        while remaining:
            parent={source:None};queue=deque([source])
            while queue and sink not in parent:
                node=queue.popleft()
                for e,(tail,head) in enumerate(arcs):
                    if tail==node and residual[e]>0 and head not in parent:
                        parent[head]=(node,e);queue.append(head)
            assert sink in parent
            path=[];node=sink
            while node!=source:
                node,e=parent[node];path.append(e)
            amount=min([remaining]+[residual[e] for e in path]);assert amount>0
            for e in path:residual[e]-=amount;kept[e]+=amount
            remaining-=amount
    return kept


def case(n,arcs,s,commodities,flows):
    bound=sum((d for _,d in commodities),F(0));rhs=[F(0)]*n
    for t,d in commodities:rhs[s]+=d;rhs[t]-=d
    kept=prune(n,arcs,s,commodities,flows)
    for values in (flows,kept):
        actual=[F(0)]*n
        for (u,v),f in zip(arcs,values):actual[u]+=f;actual[v]-=f
        assert actual==rhs
    assert all(0<=g<=f and g<=bound for g,f in zip(kept,flows))
    return {'nodes':n,'arcs':arcs,'source':s,'commodities':[[t,str(d)] for t,d in commodities],
            'flows':list(map(str,flows)),'kept':list(map(str,kept)),'bound':str(bound)}


def generate():
    cases=[case(1,[],0,[(0,F(0))],[]),case(1,[(0,0)],0,[(0,F(5,7))],[F(123,11)]),
           case(4,[(0,1),(1,0),(2,3),(3,2),(2,2)],0,[(1,F(2,3)),(0,F(0))],[F(17,3),F(5),F(19,2),F(19,2),F(99)]),
           case(2,[(0,1),(0,1),(1,0)],0,[(1,F(3,5)),(1,F(7,11))],[F(3,5),F(18,11),F(1)])]
    rng=random.Random(5810001)
    for _ in range(240):
        n=rng.randrange(1,10);s=rng.randrange(n);arcs=[];flows=[];commodities=[]
        def add(u,v,f):arcs.append((u,v));flows.append(f)
        for _ in range(rng.randrange(1,9)):
            sink=rng.randrange(n);d=F(rng.randrange(8),rng.randrange(1,13));commodities.append((sink,d))
            middle=[v for v in range(n) if v not in (s,sink)];rng.shuffle(middle)
            if sink!=s:
                path=[s]+middle[:rng.randrange(len(middle)+1)]+[sink]
                for u,v in zip(path,path[1:]):add(u,v,d)
        for _ in range(rng.randrange(1,8)):
            size=rng.randrange(1,n+1);nodes=rng.sample(range(n),size);amount=F(rng.randrange(1,60),rng.randrange(1,14))
            for u,v in zip(nodes,nodes[1:]+nodes[:1]):add(u,v,amount)
        cases.append(case(n,arcs,s,commodities,flows))
    return {'schema':'fraction-flow-prune-oracle-v1','seed':5810001,'cases':cases}


if __name__=='__main__':
    output=Path(__file__).resolve().parents[1]/'tests/vectors/flow_prune_oracle.json'
    data=generate();output.write_text(json.dumps(data,separators=(',',':'))+'\n');print(json.dumps({'cases':len(data['cases']),'output':str(output)}))
