#!/usr/bin/env python3
"""Native test15 singleton elimination including its exact fixed objective-offset column."""
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


def prepare(a, b):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (4516, 32, 4485, 32)
    removed = {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    assert len(removed) == 32
    added = {j for j, v in enumerate(b["vars"]) if v["name"] not in a["var_index"]}
    assert len(added) == 1
    offset = next(iter(added))
    assert b["vars"][offset]["lower"] == b["vars"][offset]["upper"] == 1
    assert not b["vars"][offset]["integer"]

    incidence = {i: [] for i in removed}
    for ri, row in enumerate(a["rows"]):
        for i in set(row["terms"]) & removed:
            incidence[i].append(ri)
    definitions = {}
    byrow = {}
    reverse = []
    forward = []
    for j, v in enumerate(b["vars"]):
        if j == offset:
            forward.append(expression(1))
        else:
            i = a["var_index"][v["name"]]
            assert a["vars"][i] == v
            forward.append(expression(0, {i: 1}))
    for i, v in enumerate(a["vars"]):
        if i not in removed:
            reverse.append(expression(0, {b["var_index"][v["name"]]: 1}))
            continue
        assert len(incidence[i]) == 1 and v["integer"] and v["lower"] == 0 and v["upper"] == 1
        ri = incidence[i][0]
        row = a["rows"][ri]
        pivot = row["terms"][i]
        assert row["sense"] == "E" and pivot == 1 and ri not in byrow
        terms = {b["var_index"][a["vars"][j]["name"]]: -c / pivot
                 for j, c in row["terms"].items() if j != i}
        reverse.append(expression(row["rhs"] / pivot, terms))
        definitions[i] = (ri, pivot)
        byrow[ri] = i

    proof, f, r = make_proof(a, b)

    checks = []
    for i, v in enumerate(b["vars"]):
        e = forward[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            if exact("Le", wanted):
                check = "Exact"
            else:
                check = {typ: next(iter(e[1]))}
                assert f.refexpr(check) == wanted
            checks.append(check)
        if v["integer"]:
            checks.append(fact(f, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in b["rows"]:
        name = row["name"]
        typ = next(iter(row_ref(b, name)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        if a["row_index"][name] in byrow:
            i = byrow[a["row_index"][name]]
            assert kind == "Le" and typ == "RowUpper"
            check = fact(f, "Le", wanted,
                         [[row_ref(a, name), F(1)], [{"VarLower": i}, F(1)]])
        else:
            check = row_ref(a, name)
            assert f.refexpr(check) == wanted
        checks.append(check)
    residual = plus(substitute(b["objective"], forward), a["objective"], -1)
    terms = [[{"RowEq": ri}, -a["objective"][1].get(i, F(0)) / pivot]
             for i, (ri, pivot) in definitions.items() if a["objective"][1].get(i, F(0))]
    checks.append(fact(f, "Eq", residual, terms, terminal=True))
    f.finish(forward, checks)

    fixed = r.eqpair({"VarUpper": offset}, {"VarLower": offset})
    checks = []
    for i, v in enumerate(a["vars"]):
        e = reverse[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            if exact("Le", wanted):
                check = "Exact"
            elif i in definitions:
                n = a["rows"][definitions[i][0]]["name"]
                if typ == "VarLower":
                    check = row_ref(b, n)
                    assert r.refexpr(check) == wanted
                else:
                    check = box(r, wanted, True)
            else:
                check = {typ: next(iter(e[1]))}
                assert r.refexpr(check) == wanted
            checks.append(check)
        if v["integer"]:
            checks.append(fact(r, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in a["rows"]:
        name = row["name"]
        typ = next(iter(row_ref(a, name)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), reverse)
        if a["row_index"][name] in byrow:
            assert exact("Eq", wanted)
            check = "Exact"
        else:
            check = row_ref(b, name)
            assert r.refexpr(check) == wanted
        checks.append(check)
    residual = plus(substitute(a["objective"], reverse), b["objective"], -1)
    checks.append(fact(r, "Eq", residual, [[fixed, -b["objective"][1][offset]]], terminal=True))
    r.finish(reverse, checks)

    return proof, {
        "source_variables": 4516,
        "target_variables": 4485,
        "source_rows": 32,
        "target_rows": 32,
        "eliminated_integer_singletons": 32,
        "explicit_fixed_offset": str(b["objective"][1][offset]),
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test15-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test15"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target))
    record = compile_case(proof, args.out, case_id="test15", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test15", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
