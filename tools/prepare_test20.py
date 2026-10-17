#!/usr/bin/env python3
"""Native test20 affine offsets, deleted balances and dominated thresholds."""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact, substitute
from prepare_test54 import fact, exact
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    removed = {v["variable"]: v for v in h["removed_variables"]}
    assert set(a["var_index"]) - set(b["var_index"]) == set(removed)
    forward = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    reverse = []
    for v in a["vars"]:
        name = v["name"]
        if name in removed:
            r = removed[name]["reconstruct"]
            reverse.append(expression(F(r["constant"]),
                                     {b["var_index"][n]: F(c) for n, c in r["coefficients"].items()}))
        else:
            reverse.append(expression(0, {b["var_index"][name]: 1}))

    proof, f, r = make_proof(a, b)
    aliases = {}
    for name, data in removed.items():
        i = a["var_index"][name]
        lift = substitute(reverse[i], forward)
        wanted = plus(expression(0, {i: 1}), lift, -1)
        combination = h["aggregate_balance_certificates"][name[-1]]["original_equality_combination"]
        aliases[i] = f.lin("Eq", [[row_ref(a, n), -F(c)] for n, c in combination.items()], wanted)

    def prove(builder, kind, wanted, terms, slack=0):
        if not wanted[1] and ((kind == "Eq" and wanted[0] == 0) or
                              (kind == "Le" and wanted[0] <= 0)):
            return "Exact"
        if len(terms) == 1 and terms[0][1] == 1 and slack == 0 and \
                builder.kind(terms[0][0]) == kind and builder.refexpr(terms[0][0]) == wanted:
            return terms[0][0]
        return builder.lin(kind, terms, wanted, constant=slack)

    checks = []
    for i, v in enumerate(b["vars"]):
        name = v["name"]
        for typ, bound in (("VarLower", v["lower"]), ("VarUpper", v["upper"])):
            if bound is None:
                continue
            wanted = plus(expression(bound), forward[i], -1) if typ == "VarLower" else \
                plus(forward[i], expression(-bound))
            assert name in a["var_index"]
            j = a["var_index"][name]
            assert v == a["vars"][j]
            checks.append(prove(f, "Le", wanted, [[{typ: j}, F(1)]]))
        if v["integer"]:
            assert name in a["var_index"] and a["vars"][a["var_index"][name]]["integer"]
            checks.append(fact(f, "Int", forward[i],
                               [[{"VarInt": j}, c] for j, c in forward[i][1].items()],
                               forward[i][0], True))
    for row in b["rows"]:
        name = row["name"]
        typ = {"E": "RowEq", "G": "RowLower", "L": "RowUpper"}[row["sense"]]
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        if name in a["row_index"]:
            ref = row_ref(a, name)
            terms = [[ref, F(1)]]
            terms += [[aliases[i], -c] for i, c in f.refexpr(ref)[1].items() if i in aliases]
            checks.append(prove(f, kind, wanted, terms))
        elif name in h["removed_rows"]["demand_definitions"]:
            combination = h["aggregate_balance_certificates"][name[-1]]["original_equality_combination"]
            assert F(combination[name]) == -1
            terms = [[row_ref(a, n), F(c)] for n, c in combination.items() if n != name]
            checks.append(prove(f, kind, wanted, terms))
        elif name in h["removed_rows"]["dominated_thresholds"]:
            ref = row_ref(a, h["removed_rows"]["dominated_thresholds"][name])
            slack = wanted[0] - f.refexpr(ref)[0]
            assert slack <= 0
            checks.append(prove(f, "Le", wanted, [[ref, F(1)]], slack))
        elif name in h["removed_rows"]["duplicates"]:
            ref = row_ref(a, h["removed_rows"]["duplicates"][name])
            checks.append(prove(f, kind, wanted, [[ref, F(1)]]))
        else:
            assert name == h["degree_certificate"]["removed_row"]
            terms = [[row_ref(a, n), F(c)]
                     for n, c in h["degree_certificate"]["retained_equality_combination"].items()]
            checks.append(prove(f, kind, wanted, terms))
    assert substitute(b["objective"], forward) == a["objective"]
    checks.append("Exact")
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        name = v["name"]
        for typ, bound in (("VarLower", v["lower"]), ("VarUpper", v["upper"])):
            if bound is None:
                continue
            wanted = plus(expression(bound), reverse[i], -1) if typ == "VarLower" else \
                plus(reverse[i], expression(-bound))
            if name in b["var_index"]:
                j = b["var_index"][name]
                assert v == b["vars"][j]
                terms = [[{typ: j}, F(1)]]
                slack = 0
            else:
                assert name in removed and typ == "VarLower" and not v["integer"]
                assert len(reverse[i][1]) == 1
                j, coefficient = next(iter(reverse[i][1].items()))
                assert coefficient == 1
                terms = [[{"VarLower": j}, F(1)]]
                slack = wanted[0] - r.refexpr(terms[0][0])[0]
                assert slack <= 0
            checks.append(prove(r, "Le", wanted, terms, slack))
        if v["integer"]:
            assert name in b["var_index"] and b["vars"][b["var_index"][name]]["integer"]
            checks.append(fact(r, "Int", reverse[i],
                               [[{"VarInt": j}, c] for j, c in reverse[i][1].items()],
                               reverse[i][0], True))
    for row in a["rows"]:
        name = row["name"]
        typ = {"E": "RowEq", "G": "RowLower", "L": "RowUpper"}[row["sense"]]
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), reverse)
        if name in b["row_index"]:
            ref = row_ref(b, name)
            checks.append(prove(r, kind, wanted, [[ref, F(1)]]))
        elif name in h["removed_rows"]["demand_definitions"]:
            combination = h["aggregate_balance_certificates"][name[-1]]["original_equality_combination"]
            assert F(combination[name]) == -1
            terms = [[row_ref(b, n), F(c)] for n, c in combination.items() if n != name]
            checks.append(prove(r, kind, wanted, terms))
        elif name in h["removed_rows"]["dominated_thresholds"]:
            ref = row_ref(b, h["removed_rows"]["dominated_thresholds"][name])
            slack = wanted[0] - r.refexpr(ref)[0]
            assert slack <= 0
            checks.append(prove(r, "Le", wanted, [[ref, F(1)]], slack))
        elif name in h["removed_rows"]["duplicates"]:
            ref = row_ref(b, h["removed_rows"]["duplicates"][name])
            checks.append(prove(r, kind, wanted, [[ref, F(1)]]))
        else:
            assert name == h["degree_certificate"]["removed_row"]
            terms = [[row_ref(b, n), F(c)]
                     for n, c in h["degree_certificate"]["retained_equality_combination"].items()]
            checks.append(prove(r, kind, wanted, terms))
    assert substitute(a["objective"], reverse) == b["objective"]
    checks.append("Exact")
    r.finish(reverse, checks)

    return proof, {
        "source_variables": len(a["vars"]),
        "target_variables": len(b["vars"]),
        "source_rows": len(a["rows"]),
        "target_rows": len(b["rows"]),
        "removed_variables": len(removed),
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test20-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test20"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    a, b = parse_mps(source), parse_mps(target)
    proof, counts = prepare(a, b, json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test20", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test20", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
