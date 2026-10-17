#!/usr/bin/env python3
"""Native test49 identity MILP equivalence.

The external row multipliers are untrusted inputs.  Every combination and
integrality premise is checked by the ordinary native rules; there is no
network-specific checker.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, substitute
from prepare_native import compile_case, make_proof, sha


def block(builder, inp, out, mapping, hints, *, back):
    checks = []
    for index, v in enumerate(out["vars"]):
        i = inp["var_index"][v["name"]]
        assert v == inp["vars"][i]
        if v["lower"] is not None:
            checks.append({"VarLower": i})
        if v["upper"] is not None:
            checks.append({"VarUpper": i})
        if v["integer"]:
            checks.append({"VarInt": next(iter(mapping[index][1]))})
    for row in out["rows"]:
        name = row["name"]
        typ = {"L": "RowUpper", "G": "RowLower", "E": "RowEq"}[row["sense"]]
        wanted = substitute(row_fact(row, typ), mapping)
        if name in inp["row_index"]:
            ref = row_ref(inp, name)
            assert builder.refexpr(ref) == wanted
        elif name in hints["removed_rows"]:
            assert back and typ == "RowEq"
            terms = [[row_ref(inp, n), F(c)]
                     for n, c in hints["removed_rows"][name]["recovery"]["row_multipliers"].items()]
            ref = builder.lin("Eq", terms, wanted)
        else:
            assert not back and typ == "RowLower"
            h = hints["added_rows"][name]["validity_certificate"]
            divisor = F(h["divisor"])
            assert divisor > 0
            terms = [[row_ref(inp, n), 1 / divisor] for n in h["negated_capacity_rows"]]
            terms += [[row_ref(inp, h["balance_row"]), -F(h["balance_multiplier"]) / divisor]]
            terms += [[{"VarLower": inp["var_index"][n]}, 2 / divisor]
                      for n in h["nonnegative_flow_variables_multiplier_2"]]
            unrounded = expression(F(h["unrounded_capacity_rhs"]) / divisor, wanted[1])
            le = builder.lin("Le", terms, unrounded)
            integer = builder.lin("Int", [[{"VarInt": j}, c] for j, c in wanted[1].items()],
                                  expression(0, wanted[1]))
            rounded = -((-unrounded[0].numerator) // unrounded[0].denominator)
            assert wanted == expression(rounded, wanted[1])
            ref = builder.round(le, integer)
        checks.append(ref)
    assert substitute(out["objective"], mapping) == inp["objective"]
    checks.append("Exact")
    return checks


def prepare(a, b, h):
    assert set(a["var_index"]) == set(b["var_index"])
    forward = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    backwards = [expression(0, {b["var_index"][v["name"]]: 1}) for v in a["vars"]]
    proof, f, r = make_proof(a, b)
    for builder, inp, out, mapping, back in ((f, a, b, forward, False),
                                             (r, b, a, backwards, True)):
        checks = block(builder, inp, out, mapping, h, back=back)
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": len(a["vars"]),
        "target_variables": len(b["vars"]),
        "source_rows": len(a["rows"]),
        "target_rows": len(b["rows"]),
        "added_rows": len(h["added_rows"]),
        "removed_rows": len(h["removed_rows"]),
        "rounded_cuts": 20,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test49-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test49"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    a, b = parse_mps(source), parse_mps(target)
    proof, counts = prepare(a, b, json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test49", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test49", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
