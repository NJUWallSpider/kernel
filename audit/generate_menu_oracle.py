#!/usr/bin/env python3
"""Independent Fraction checks of optional one-hot extension and paired domains.

This test fixture writer imports no kernel/preparer code and confers no authority.
"""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import json
import random

SEED = 0x4D454E55
rng = random.Random(SEED)


def scalar():
    return F(rng.randrange(-7, 8), rng.randrange(1, 8))


def expr(c, terms):
    return {"constant": str(c), "terms": [[i, str(v)] for i, v in sorted(terms.items()) if v]}


def evaluate(e, point):
    return F(e["constant"]) + sum(F(c) * point[i] for i, c in e["terms"])


def at_value(point, value):
    terms = {i: scalar() for i in range(len(point))}
    return expr(value - sum(c * point[i] for i, c in terms.items()), terms)


def premise_values(a, i, k):
    return [-a, a - 1, a, -i, i - k * a, i]


def premise_valid(values):
    return all(v <= 0 for n, v in enumerate(values) if n not in (2, 5)) and all(values[n].denominator == 1 for n in (2, 5))


def menus():
    cases = [{"input": [], "menus": [], "accept": True, "constructed": []}]
    for n in range(240):
        point = [scalar() for _ in range(3)]
        family = []
        choices = []
        valid = True
        for m in range(1 + n % 3):
            k = rng.randrange(13)
            a = F(rng.randrange(2))
            i = F(rng.randrange(k + 1)) if a else F(0)
            if n % 2 and m == 0:
                mutation = (n // 2) % 6
                if mutation < 3:
                    a = [F(-1), F(1, 2), F(2)][mutation]
                else:
                    i = [F(-1), F(1, 2), F(k + 1)][mutation - 3]
            values = premise_values(a, i, k)
            okay = premise_valid(values)
            valid &= okay
            selection = [F(0)] * (k + 1)
            if okay and a:
                selection[int(i)] = F(1)
            choices.extend(selection)
            family.append({"maximum_index": k, "activation": at_value(point, a), "index": at_value(point, i), "premise_values": [str(v) for v in values]})
        assert valid == (n % 2 == 0)
        cases.append({"input": [str(v) for v in point], "menus": family, "accept": valid, "constructed": [str(v) for v in choices]})
    enumerated = 0
    unique_states = 0
    for k in range(13):
        fibers = {}
        for values in product((0, 1), repeat=k + 1):
            enumerated += 1
            a, i = sum(values), sum(j * v for j, v in enumerate(values))
            if a <= 1:
                assert (a, i) not in fibers
                fibers[a, i] = values
        assert len(fibers) == k + 2
        for a, i in fibers:
            expected = tuple(int(a == 1 and j == i) for j in range(k + 1))
            assert fibers[a, i] == expected
        unique_states += len(fibers)
    return {"seed": SEED, "cases": cases, "binary_vectors_enumerated": enumerated, "unique_menu_states": unique_states}


def shifted(e, offset):
    return expr(F(e["constant"]), {i + offset: F(c) for i, c in e["terms"]})


def feasible(model, point, integers):
    for variable, value in zip(model["vars"], point):
        if variable["lower"] is not None and value < F(variable["lower"]):
            return False
        if variable["upper"] is not None and value > F(variable["upper"]):
            return False
        if integers and variable["integer"] and value.denominator != 1:
            return False
    for row in model["rows"]:
        value = evaluate(row["expr"], point)
        if row["lower"] is not None and value < F(row["lower"]):
            return False
        if row["upper"] is not None and value > F(row["upper"]):
            return False
    return True


def paired():
    cases = []
    for case in range(80):
        n, m = case % 6, (case // 6) % 7
        point = [F(rng.randrange(-2, 3)) for _ in range(n)]
        variables = []
        for i in range(n):
            variables.append({"integer": bool(rng.randrange(2)), "lower": None if i % 3 == 0 else str(point[i] - 1), "upper": None if i % 4 == 0 else str(point[i] + 1)})
        rows = []
        for j in range(case % 4):
            e = expr(scalar(), {i: scalar() for i in range(n)})
            value = evaluate(e, point)
            rows.append({"expr": e, "lower": str(value) if j % 3 else None, "upper": str(value) if j % 3 != 2 else None})
        source = {"vars": variables, "rows": rows, "objective": expr(scalar(), {i: scalar() for i in range(n)})}
        mapping = [expr(scalar(), {i: scalar() if case % 5 else F(0) for i in range(n)}) for _ in range(m)]
        expected_rows = []
        for offset in (0, n):
            expected_rows.extend({**r, "expr": shifted(r["expr"], offset)} for r in rows)
        for e in mapping:
            terms = {i: F(c) for i, c in e["terms"]}
            terms.update({i + n: -F(c) for i, c in e["terms"]})
            expected_rows.append({"expr": expr(F(0), terms), "lower": "0", "upper": "0"})
        pairs = []
        for trial in range(8):
            left = point if trial < 4 else [scalar() for _ in range(n)]
            right = left if trial % 3 == 0 else [scalar() for _ in range(n)]
            same = all(evaluate(e, left) == evaluate(e, right) for e in mapping)
            pairs.append({"values": [str(v) for v in left + right], "lp": feasible(source, left, False) and feasible(source, right, False) and same, "integer": feasible(source, left, True) and feasible(source, right, True) and same, "equalities": [str(a - b) for a, b in zip(left, right)]})
        cases.append({"source": source, "map": mapping, "expected_rows": expected_rows, "pairs": pairs})
    return {"seed": SEED, "cases": cases}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    (root / "tests/vectors/menu_oracle.json").write_text(json.dumps(menus(), separators=(",", ":")) + "\n")
    (root / "tests/vectors/injectivity_oracle.json").write_text(json.dumps(paired(), separators=(",", ":")) + "\n")
    print("wrote 241 menu cases, exhaustive K=0..12 states, and 80 paired-domain cases with 640 point pairs")
