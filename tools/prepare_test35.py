#!/usr/bin/env python3
"""Native test35 fixed/affine elimination including original bounds and normalization deps."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact, box, exact
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (4456, 1667, 3510, 675)
    removed = {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    assert len(removed) == 946
    fixed = {a["var_index"][n]: d for n, d in h["fixed_variables"].items()}
    defs = {a["var_index"][n]: d for n, d in h["affine_eliminations"].items()}
    assert removed == set(fixed) | set(defs)
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = []
    for i, v in enumerate(a["vars"]):
        if i in fixed:
            e = expression(F(fixed[i]["value"]))
        elif i in defs:
            e = expression(F(defs[i]["constant"]),
                           {b["var_index"][n]: F(c) for n, c in defs[i]["coefficients"].items()})
        else:
            e = expression(0, {b["var_index"][v["name"]]: 1})
        reverse.append(e)

    proof, f, r = make_proof(a, b)
    p = f
    equalities = {}
    visiting = set()

    def prove(i):
        if i in equalities:
            return equalities[i]
        assert i not in visiting
        visiting.add(i)
        d = fixed.get(i, defs.get(i))
        rn = d.get("row", d.get("defining_row"))
        ref = row_ref(a, rn)
        assert "RowEq" in ref
        e = p.refexpr(ref)
        pivot = e[1][i]
        terms = [[ref, 1 / pivot]]
        for j, c in e[1].items():
            if j != i and j in removed:
                terms.append([prove(j), -c / pivot])
        wanted = plus(expression(0, {i: 1}), substitute(reverse[i], forward), -1)
        equalities[i] = fact(p, "Eq", wanted, terms)
        visiting.remove(i)
        return equalities[i]

    for i in sorted(removed):
        prove(i)
    dependencies = {d["removed"]: d["zero_linear_combination"]
                    for d in h["equality_dependency_witnesses"]}

    checks = []
    for i, v in enumerate(b["vars"]):
        e = forward[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is not None:
                checks.append(box(f, plus(mul(e, sign), expression(-sign * value)), True))
        if v["integer"]:
            checks.append(fact(f, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in b["rows"]:
        n = row["name"]
        typ = next(iter(row_ref(b, n)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        ref = row_ref(a, n)
        checks.append(fact(f, kind, wanted,
                           [[ref, F(1)]] + [[equalities[i], -c]
                                            for i, c in f.refexpr(ref)[1].items() if i in removed],
                           terminal=True))
    wanted = plus(substitute(b["objective"], forward), a["objective"], -1)
    checks.append(fact(f, "Eq", wanted,
                       [[equalities[i], -c] for i, c in a["objective"][1].items() if i in removed],
                       terminal=True))
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        e = reverse[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is not None:
                checks.append(box(r, plus(mul(e, sign), expression(-sign * value)), True))
        if v["integer"]:
            checks.append(fact(r, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in a["rows"]:
        n = row["name"]
        typ = next(iter(row_ref(a, n)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), reverse)
        if n in b["row_index"]:
            check = row_ref(b, n)
            assert r.refexpr(check) == wanted
        elif exact(kind, wanted):
            check = "Exact"
        elif n in dependencies:
            cs = dependencies[n]
            pivot = F(cs[n])
            check = fact(r, "Eq", wanted,
                         [[row_ref(b, rr), -F(c) / pivot] for rr, c in cs.items() if rr != n])
        else:
            assert kind == "Le"
            check = box(r, wanted, True)
        checks.append(check)
    wanted = plus(substitute(a["objective"], reverse), b["objective"], -1)
    checks.append(fact(r, "Eq", wanted, [], terminal=True))
    r.finish(reverse, checks)

    return proof, {
        "source_variables": 4456,
        "target_variables": 3510,
        "source_rows": 1667,
        "target_rows": 675,
        "fixed_variables": 810,
        "affine_definitions": 136,
        "normalization_dependencies": 45,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test35-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test35"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test35", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test35", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
