#!/usr/bin/env python3
"""Independent exact common-source flow construction and generalized vectors.

Executes bounded BFS path extraction with Fraction, preserves the entire residual
circulation, and independently checks every commodity balance and arc total.
No Rust or solver code is imported.
"""
from collections import deque
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import random

SEED=0x464c4f57
rng=random.Random(SEED)


def balance(nodes, arcs, flow):
    result=[F(0)]*nodes
    for (tail,head),value in zip(arcs,flow):
        result[tail]+=value
        result[head]-=value
    return result


def construct(nodes,arcs,source,commodities,aggregate):
    residual=list(aggregate)
    result=[[F(0)]*len(arcs) for _ in commodities]
    outgoing=[[] for _ in range(nodes)]
    for j,(tail,head) in enumerate(arcs):outgoing[tail].append(j)
    extractions=0
    for k,(sink,original_demand) in enumerate(commodities):
        if sink==source:continue
        demand=original_demand
        while demand>0:
            previous={source:None};queue=deque([source])
            while queue and sink not in previous:
                u=queue.popleft()
                for j in outgoing[u]:
                    v=arcs[j][1]
                    if residual[j]>0 and v not in previous:
                        previous[v]=j;queue.append(v)
            assert sink in previous
            path=[];node=sink
            while node!=source:
                j=previous[node];path.append(j);node=arcs[j][0]
            amount=min([demand]+[residual[j] for j in path])
            assert amount>0
            for j in path:residual[j]-=amount;result[k][j]+=amount
            demand-=amount;extractions+=1
            assert extractions<=len(arcs)+len(commodities)
    assert balance(nodes,arcs,residual)==[0]*nodes
    for j,value in enumerate(residual):result[0][j]+=value
    for (sink,demand),flow in zip(commodities,result):
        expected=[F(0)]*nodes;expected[source]+=demand;expected[sink]-=demand
        assert all(v>=0 for v in flow)
        assert balance(nodes,arcs,flow)==expected
    assert [sum(f[j] for f in result) for j in range(len(arcs))]==aggregate
    return result,extractions,sum(residual)


def generate():
    for case in range(96):
        nodes=1 if case%12==0 else rng.randint(2,7)
        arcs=[(a,b) for a in range(nodes) for b in range(nodes)]
        arcs+=arcs[:min(3,len(arcs))] # Parallel arcs have distinct coordinates.
        rng.shuffle(arcs)
        groups=[]
        for _ in range(rng.randint(1,3)):
            source=rng.randrange(nodes)
            commodities=[(rng.randrange(nodes),F(rng.randint(0,7),rng.randint(1,9))) for _ in range(rng.randint(1,5))]
            aggregate=[F(0)]*len(arcs)
            for sink,demand in commodities:
                if sink!=source:
                    eligible=[j for j,arc in enumerate(arcs) if arc==(source,sink)]
                    aggregate[rng.choice(eligible)]+=demand
            # Explicit loops and cycles may be disconnected from the source.
            for _ in range(5):
                path=rng.sample(range(nodes),rng.randint(1,nodes))
                amount=F(rng.randint(1,5),rng.randint(1,11))
                for a,b in zip(path,path[1:]+path[:1]):
                    eligible=[j for j,arc in enumerate(arcs) if arc==(a,b)]
                    aggregate[rng.choice(eligible)]+=amount
            flow,steps,circulation=construct(nodes,arcs,source,commodities,aggregate)
            groups.append({"source":source,"commodities":[[s,str(d)] for s,d in commodities],
                           "aggregate":list(map(str,aggregate)),"constructed":[list(map(str,f)) for f in flow],
                           "extractions":steps,"circulation_arc_total":str(circulation)})
        yield {"nodes":nodes,"arcs":arcs,"groups":groups}
    # Empty arcs: source==sink and zero demands impose zero divergence.
    yield {"nodes":2,"arcs":[],"groups":[{"source":0,"commodities":[[0,"5/7"],[1,"0"]],"aggregate":[],"constructed":[[],[]],"extractions":0,"circulation_arc_total":"0"}]}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"tests/vectors/flow_oracle.json")
    args=parser.parse_args();cases=list(generate())
    args.output.write_text(json.dumps({"seed":SEED,"cases":cases},indent=2)+"\n")
    print(json.dumps({"seed":SEED,"cases":len(cases),"groups":sum(len(v['groups']) for v in cases)}))
