#!/usr/bin/env python3
"""Exact interval image of rational boxes, independent of the Rust kernel.

For an affine scalar observation, endpoint signs give the attained minimum and
maximum over a box. Midpoints have an explicit common input preimage; points
beyond the endpoints do not. The output LP is a wider interval.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import random

SEED=0x46494252
rng=random.Random(SEED)


def generate():
    for case in range(120):
        dimension=2+case%4
        lower=[F(rng.randint(-12,7),rng.randint(1,11)) for _ in range(dimension)]
        upper=[v+F(rng.randint(0,12),rng.randint(1,13)) for v in lower]
        coefficients=[F(rng.randint(-8,8),rng.randint(1,9)) for _ in lower]
        if not any(coefficients):coefficients[0]=F(1)
        constant=F(rng.randint(-8,8),rng.randint(1,9))
        low=constant+sum((c*(lo if c>=0 else hi) for c,lo,hi in zip(coefficients,lower,upper)),F(0))
        high=constant+sum((c*(hi if c>=0 else lo) for c,lo,hi in zip(coefficients,lower,upper)),F(0))
        margin=F(rng.randint(1,7),rng.randint(1,9))
        if case%3==0:point=high+margin;direction="upper";strict=True
        elif case%3==1:point=low-margin;direction="lower";strict=True
        else:
            point=(low+high)/2;direction="upper";strict=False
            midpoint=[(lo+hi)/2 for lo,hi in zip(lower,upper)]
            assert constant+sum((c*x for c,x in zip(coefficients,midpoint)),F(0))==point
        yield {"lower":list(map(str,lower)),"upper":list(map(str,upper)),"coefficients":list(map(str,coefficients)),
               "constant":str(constant),"minimum":str(low),"maximum":str(high),
               "output_lower":str(low-2*margin),"output_upper":str(high+2*margin),"point":str(point),"direction":direction,"strict":strict}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"tests/vectors/fiber_oracle.json")
    args=parser.parse_args();cases=list(generate());args.output.write_text(json.dumps({"seed":SEED,"cases":cases},indent=2)+"\n")
    print(json.dumps({"seed":SEED,"cases":len(cases),"strict":sum(c['strict'] for c in cases),"non_strict":sum(not c['strict'] for c in cases)}))
