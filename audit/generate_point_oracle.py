#!/usr/bin/env python3
"""Deterministic exact point oracle. Python Fraction is independent of Rust.

Writes semantic data and expected decisions, never invokes the implementation
under test or a solver. Strictness vectors are supplementary separation checks;
the Rust integration test separately requires a verified inclusion proof.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import random

SEED = 0x505433
rng = random.Random(SEED)


def scalar():
    return F(rng.randint(-11, 11), rng.randint(1, 13))


def expression(n):
    return {"constant": str(scalar()), "terms": [[i, str(c)] for i in range(n) if (c := scalar())]}


def evaluate(e, values):
    return F(e["constant"]) + sum((F(c) * values[i] for i, c in e["terms"]), F(0))


def satisfied_model(values):
    n = len(values)
    m = {"vars": [{"integer": False, "lower": str(x-2), "upper": str(x+2)} for x in values],
         "rows": [], "objective": expression(n)}
    for _ in range(rng.randrange(5)):
        e = expression(n)
        at = evaluate(e, values)
        width = abs(scalar())
        m["rows"].append({"expr": e, "lower": str(at-width), "upper": str(at+width)})
    return m


def feasible(m, values, integers):
    if len(values) != len(m["vars"]):
        return False
    for v, x in zip(m["vars"], values):
        if v["lower"] is not None and x < F(v["lower"]): return False
        if v["upper"] is not None and x > F(v["upper"]): return False
        if integers and v["integer"] and x.denominator != 1: return False
    for row in m["rows"]:
        at = evaluate(row["expr"], values)
        if row["lower"] is not None and at < F(row["lower"]): return False
        if row["upper"] is not None and at > F(row["upper"]): return False
    return True


def feasibility_vectors():
    for k in range(240):
        n = rng.randint(1, 6)
        values = [scalar() for _ in range(n)]
        source, target = satisfied_model(values), satisfied_model(values)
        is_target, integers = bool(rng.randrange(2)), bool(rng.randrange(2))
        selected = target if is_target else source
        for var, value in zip(selected["vars"], values):
            var["integer"] = integers and value.denominator == 1
        objective = evaluate(selected["objective"], values) if k % 3 else None
        if k % 2:
            bad = (k // 2) % 4
            if bad == 0: selected["vars"][0]["lower"] = str(values[0]+F(1,17))
            elif bad == 1:
                e = expression(n)
                selected["rows"].append({"expr": e, "lower": None, "upper": str(evaluate(e,values)-F(1,19))})
            elif bad == 2:
                objective = evaluate(selected["objective"], values)+F(1,23)
            else:
                values[0] = F(1,29)
                selected["vars"][0] = {"integer":True,"lower":None,"upper":None}
                integers = True
        accept = feasible(selected,values,integers) and (objective is None or evaluate(selected["objective"],values)==objective)
        yield {"source":source,"target":target,"claims":[],
               "point":{"claim":{"Feasible":{"target":is_target,"integers":integers,"objective":None if objective is None else str(objective)}},"values":list(map(str,values))},
               "accept":accept}


def strictness_vectors():
    for k in range(240):
        n = rng.randint(1, 6)
        values = [scalar() for _ in range(n)]
        permutation = list(range(n)); rng.shuffle(permutation)
        # projection pair (input i, output permutation[i])
        inverse = {o:i for i,o in enumerate(permutation)}
        output = satisfied_model(values)
        ipoint = [values[o] for o in permutation]
        input_model = json.loads(json.dumps(output))
        input_model["vars"] = [output["vars"][o].copy() for o in permutation]
        for row in input_model["rows"]:
            row["expr"]["terms"] = sorted([[inverse[o],c] for o,c in row["expr"]["terms"]])
        cut = {"expr":{"constant":"2/7","terms":[[0,"1"]]},"lower":None,
               "upper":str(F(2,7)+ipoint[0] + (F(-1,31) if k%2 == 0 else F(1,31)))}
        input_model["rows"].append(cut)
        reverse = bool(rng.randrange(2))
        source,target = (output,input_model) if reverse else (input_model,output)
        claim = {"reverse":reverse,"input_integers":False,"output_integers":False,"objective":"None",
                 "projection":[[i,o] for i,o in enumerate(permutation)],"inverse":None}
        accept = feasible(output,values,False) and not feasible(input_model,ipoint,False)
        yield {"source":source,"target":target,"claims":[claim],
               "point":{"claim":{"Strictness":{"inclusion_claim":0}},"values":list(map(str,values))},"accept":accept}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"tests/vectors/point_oracle.json")
    args=parser.parse_args()
    cases = list(feasibility_vectors()) + list(strictness_vectors())
    args.output.write_text(json.dumps({"seed":SEED,"cases":cases},indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"accept":sum(v["accept"] for v in cases),"reject":sum(not v["accept"] for v in cases),"seed":SEED}))
