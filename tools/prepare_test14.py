#!/usr/bin/env python3
"""Native test14 zero/bound cleanup and binary-conflict proof."""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (1166, 2295, 1046, 1804)
    zeros = {a["var_index"][d["variable"]]: d for d in h["deleted_fixed_variables"]}
    assert len(zeros) == 120
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression() if i in zeros else expression(0, {b["var_index"][v["name"]]: 1})
               for i, v in enumerate(a["vars"])]
    bounds = {a["var_index"][d["variable"]]: d for d in h["retained_bound_changes"]}
    gates = {d["row"]: d for d in h["binary_implication_changes"]}
    proof, f, r = make_proof(a, b)
    zeroeq = {}
    for i, d in zeros.items():
        ref = row_ref(a, d["witness"])
        e = f.refexpr(ref)
        assert e[0] == 0 and set(e[1]) == {i} and e[1][i] > 0
        zeroeq[i] = f.eqpair(fact(f, "Le", expression(0, {i: 1}), [[ref, 1 / e[1][i]]]),
                             {"VarLower": i})
    edges = {}
    for name, d in gates.items():
        z = a["var_index"][d["center"]]
        neighbors = [a["var_index"][n] for n in d["neighbors"]]
        ref = row_ref(a, name)
        for edge_name, j in zip(d["edge_rows"], neighbors):
            wanted = expression(-1, {z: 1, j: 1})
            def left(child, assumption):
                return child.lin("Le", [[{"VarUpper": j}, F(1)], [assumption, F(1)]], wanted)
            def right(child, assumption):
                return child.lin("Le", [[ref, F(4)]] +
                                 [[{"VarLower": k}, F(1)] for k in neighbors if k != j] +
                                 [[assumption, F(3)]], wanted)
            edges[edge_name] = f.cases("Le", wanted, expression(0, {z: 1}), {"VarInt": z}, left, right)

    for back in (False, True):
        builder = r if back else f
        mapping = reverse if back else forward
        output, inp = (a, b) if back else (b, a)
        checks = []
        for i, v in enumerate(output["vars"]):
            e = mapping[i]
            for typ, value, sign in [("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)]:
                if value is None:
                    continue
                wanted = plus(mul(e, sign), expression(-sign * value))
                if not back and typ == "VarUpper" and next(iter(e[1])) in bounds:
                    j = next(iter(e[1]))
                    ref = row_ref(a, bounds[j]["witness"])
                    coefficient = builder.refexpr(ref)[1][j]
                    check = fact(builder, "Le", wanted, [[ref, 1 / coefficient]], terminal=True)
                else:
                    check = box(builder, wanted, True)
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
                if name in b["row_index"]:
                    check = row_ref(b, name)
                    assert builder.refexpr(check) == wanted
                elif exact(kind, wanted):
                    check = "Exact"
                else:
                    d = h["removed_rows"][name]
                    if d["reason"] == "box_implied":
                        check = box(builder, wanted, True)
                    elif d["reason"] == "exact_duplicate":
                        check = row_ref(b, d["retained_row"])
                        assert builder.refexpr(check) == wanted
                    else:
                        d = gates[name]
                        n = len(d["neighbors"])
                        terms = [[row_ref(b, edge), F(1, 4)] for edge in d["edge_rows"]]
                        if n < 4:
                            terms.append([{"VarUpper": b["var_index"][d["center"]]}, 1 - F(n, 4)])
                        check = fact(builder, "Le", wanted, terms, terminal=True)
            elif name in edges:
                check = edges[name]
                assert builder.refexpr(check) == wanted
            else:
                ref = row_ref(a, name)
                check = fact(builder, kind, wanted,
                             [[ref, F(1)]] + [[zeroeq[i], -c] for i, c in builder.refexpr(ref)[1].items()
                                              if i in zeros], terminal=True)
            checks.append(check)
        wanted = plus(substitute(output["objective"], mapping), inp["objective"], -1)
        checks.append(fact(builder, "Eq", wanted,
                           [] if back else [[zeroeq[i], -c] for i, c in a["objective"][1].items()
                                            if i in zeros], terminal=True))
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 1166, "target_variables": 1046,
        "source_rows": 2295, "target_rows": 1804,
        "forced_zero_continuous_variables": 120, "binary_conflicts": 246,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test14-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test14"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test14", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test14", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
