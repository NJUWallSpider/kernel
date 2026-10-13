#!/usr/bin/env python3
"""Independent exact interval feasibility and simultaneous construction oracle.

Every affine value and chosen maximum/minimum uses Fraction. No Rust or solver
code is imported; the fixture contains both feasible and inconsistent families.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import random

SEED=0x494e5456
rng=random.Random(SEED)


def scalar():return F(rng.randint(-17,17),rng.randint(1,19))


def expression_at(point,value):
    terms=[[i,c] for i in range(len(point)) if (c:=scalar())]
    constant=value-sum((c*point[i] for i,c in terms),F(0))
    return {"constant":str(constant),"terms":[[i,str(c)] for i,c in terms]}


def evaluate(expr,point):
    return F(expr["constant"])+sum((F(c)*point[i] for i,c in expr["terms"]),F(0))


def generate():
    for case in range(240):
        point=[scalar() for _ in range(case%7)]
        intervals=[];constructed=[];accept=True;bad=case%2==1
        for interval_index in range(1+case%6):
            center=scalar()
            mode=(case+interval_index)%5
            lower_count=[0,1,0,2,3][mode]
            upper_count=[0,0,2,3,2][mode]
            if bad and interval_index==0:lower_count=upper_count=3
            lowers=[expression_at(point,center-abs(scalar())) for _ in range(lower_count)]
            uppers=[expression_at(point,center+abs(scalar())) for _ in range(upper_count)]
            if bad and interval_index==0:
                lowers[1]=expression_at(point,center+F(2,7))
                uppers[1]=expression_at(point,center+F(1,7))
            low_values=[evaluate(e,point) for e in lowers]
            high_values=[evaluate(e,point) for e in uppers]
            pairs=[l-u for l in low_values for u in high_values]
            valid=all(v<=0 for v in pairs)
            accept=accept and valid
            choice=max(low_values) if low_values else min(high_values) if high_values else F(0)
            if valid:
                assert all(l<=choice for l in low_values)
                assert all(choice<=u for u in high_values)
            intervals.append({"lower":lowers,"upper":uppers,"pair_values":list(map(str,pairs))})
            constructed.append(str(choice))
        yield {"input":list(map(str,point)),"intervals":intervals,"accept":accept,"constructed":constructed}
    yield {"input":["2/3"],"intervals":[],"accept":True,"constructed":[]}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"tests/vectors/interval_oracle.json")
    args=parser.parse_args();cases=list(generate())
    args.output.write_text(json.dumps({"seed":SEED,"cases":cases},indent=2)+"\n")
    print(json.dumps({"seed":SEED,"cases":len(cases),"accepted":sum(c['accept'] for c in cases),"rejected":sum(not c['accept'] for c in cases)}))
