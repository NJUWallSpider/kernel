#!/usr/bin/env python3
"""Native test17 positive-row redundancy and weighted binary order-chain reformulation."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (57756, 3757, 57756, 1765)
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression(0, {b["var_index"][v["name"]]: 1}) for v in a["vars"]]

    proof, f, r = make_proof(a, b)
    adjacent = {}
    for rn, d in h["row_replacements"].items():
        ref = row_ref(a, rn)
        e = f.refexpr(ref)
        assert e[0] == 0 and len(e[1]) == 2
        x, c = next((i, c) for i, c in e[1].items() if c > 0)
        y, neg = next((i, c) for i, c in e[1].items() if c < 0)
        n = -neg
        assert n > c > 0
        wanted = substitute(row_fact(b["rows"][b["row_index"][rn]], "RowUpper"), forward)
        assert wanted == expression(0, {x: 1, y: -1})

        def left(child, assumption):
            return child.lin("Le", [[ref, 1 / c], [assumption, n / c - 1]], wanted)

        def right(child, assumption):
            return child.lin("Le", [[{"VarUpper": x}, F(1)], [assumption, F(1)]], wanted)

        adjacent[rn] = f.cases("Le", wanted, expression(0, {y: 1}),
                               {"VarInt": y}, left, right)

    order = {**h["pair_row_deletions"],
             **{n: d["reverse_certificate"] for n, d in h["row_replacements"].items()}}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        for i, v in enumerate(out["vars"]):
            j = next(iter(mapping[i][1]))
            assert v["integer"] and v["lower"] == 0 and v["upper"] == 1
            checks.extend([{"VarLower": j}, {"VarUpper": j}, {"VarInt": j}])
        for row in out["rows"]:
            rn = row["name"]
            typ = next(iter(row_ref(out, rn)))
            wanted = substitute(row_fact(row, typ), mapping)
            if not back and rn in adjacent:
                check = adjacent[rn]
                assert builder.refexpr(check) == wanted
            elif back and rn in order:
                d = order[rn]
                terms = ([[row_ref(b, n), F(d["chain_multiplier"])] for n in d["chain_rows"]] +
                         [[{"VarLower": b["var_index"][d["lower_bound_variable"]]},
                           F(d["lower_bound_multiplier"])]])
                check = fact(builder, "Le", wanted, terms, terminal=True)
            elif back and rn in h["positive_row_deletions"]:
                d = h["positive_row_deletions"][rn]
                terms = [[row_ref(b, d["source_row"]), F(d["source_multiplier"])]]
                if d.get("gate_upper_bound"):
                    terms.append([{"VarUpper": b["var_index"][d["gate_upper_bound"]]},
                                  F(d["source_multiplier"])])
                raw = expression()
                for ref, c in terms:
                    raw = plus(raw, builder.refexpr(ref), c)
                delta = plus(wanted, raw, -1)
                assert delta[0] == 0 and all(c < 0 for c in delta[1].values())
                terms.extend([[{"VarLower": j}, -c] for j, c in delta[1].items()])
                check = fact(builder, "Le", wanted, terms, terminal=True)
            else:
                check = row_ref(inp, rn)
                assert builder.refexpr(check) == wanted
            checks.append(check)
        assert substitute(out["objective"], mapping) == inp["objective"]
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 57756, "target_variables": 57756,
        "source_rows": 3757, "target_rows": 1765,
        "positive_row_deletions": 1046, "adjacent_binary_replacements": 44,
        "restored_original_order_rows": 990, "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test17-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test17"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test17", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test17", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
