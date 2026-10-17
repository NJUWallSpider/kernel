#!/usr/bin/env python3
"""Native test9 affine-exit elimination proof.

The proof is constructed through ``kernel_compiler`` and compiled to RPA 12 /
RPX 11 by the native compiler.  The legacy four-claim Request layout collapses
to the current two MI-OPT directions.
"""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (2298, 1026, 1536, 846)
    removed = {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    assert len(removed) == 763
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
    common = []
    for j, v in enumerate(b["vars"]):
        if j == offset:
            forward.append(expression(1))
        else:
            i = a["var_index"][v["name"]]
            assert a["vars"][i] == v
            forward.append(expression(0, {i: 1}))
            common.append([i, j])
    for i, v in enumerate(a["vars"]):
        if i not in removed:
            reverse.append(expression(0, {b["var_index"][v["name"]]: 1}))
            continue
        assert len(incidence[i]) == 1 and not v["integer"] and v["lower"] == 0 and v["upper"] is None
        ri = incidence[i][0]
        row = a["rows"][ri]
        pivot = row["terms"][i]
        assert row["sense"] == "E" and pivot == -1 and ri not in byrow
        terms = {b["var_index"][a["vars"][j]["name"]]: -c / pivot
                 for j, c in row["terms"].items() if j != i}
        reverse.append(expression(row["rhs"] / pivot, terms))
        definitions[i] = (ri, pivot)
        byrow[ri] = i

    proof, forward_builder, reverse_builder = make_proof(a, b)
    for back in (False, True):
        builder = reverse_builder if back else forward_builder
        mapping = reverse if back else forward
        other = forward if back else reverse
        output, inp = (a, b) if back else (b, a)
        checks = []
        fixed = builder.eqpair({"VarUpper": offset}, {"VarLower": offset}) if back else None
        for i, v in enumerate(output["vars"]):
            e = mapping[i]
            for typ, value, sign in [("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)]:
                if value is None:
                    continue
                wanted = plus(mul(e, sign), expression(-sign * value))
                if exact("Le", wanted):
                    check = "Exact"
                elif back and i in definitions:
                    name = a["rows"][definitions[i][0]]["name"]
                    if name in b["row_index"]:
                        check = row_ref(b, name)
                        assert builder.refexpr(check) == wanted
                    else:
                        check = box(builder, wanted, True)
                else:
                    check = {typ: next(iter(e[1]))}
                    assert builder.refexpr(check) == wanted
                checks.append(check)
            if v["integer"]:
                checks.append(fact(builder, "Int", e,
                                   [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
        for row in output["rows"]:
            name = row["name"]
            typ = next(iter(row_ref(output, name)))
            kind = "Eq" if typ == "RowEq" else "Le"
            wanted = substitute(row_fact(row, typ), mapping)
            if back:
                if a["row_index"][name] in byrow:
                    assert exact("Eq", wanted)
                    check = "Exact"
                else:
                    check = row_ref(b, name)
                    assert builder.refexpr(check) == wanted
            elif a["row_index"][name] in byrow:
                i = byrow[a["row_index"][name]]
                assert kind == "Le" and typ == "RowLower"
                check = fact(builder, "Le", wanted,
                             [[row_ref(a, name), F(-1)], [{"VarLower": i}, F(1)]])
            else:
                check = row_ref(a, name)
                assert builder.refexpr(check) == wanted
            checks.append(check)
        residual = plus(substitute(output["objective"], mapping), inp["objective"], -1)
        terms = ([[fixed, -b["objective"][1][offset]]] if back else
                 [[{"RowEq": ri}, -a["objective"][1].get(i, F(0)) / pivot]
                  for i, (ri, pivot) in definitions.items() if a["objective"][1].get(i, F(0))])
        checks.append(fact(builder, "Eq", residual, terms, terminal=True))
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 2298,
        "target_variables": 1536,
        "source_rows": 1026,
        "target_rows": 846,
        "eliminated_nonnegative_exits": 763,
        "removed_bound_rows": 180,
        "explicit_fixed_offset": str(b["objective"][1][offset]),
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test9-nomf-20261004-004349"))
    parser.add_argument("--out", type=Path, default=Path("cases/test9"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target))
    record = compile_case(proof, args.out, case_id="test9", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test9", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
