#!/usr/bin/env python3
"""Native full alias/fixed/unused elimination projections for test43."""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (33242, 49565, 26625, 37573)
    edits = h["modifications"]
    aliases = {a["var_index"][n]: a["var_index"][d["target"]]
               for n, d in edits["alias_eliminations"].items()}
    zeros = {a["var_index"][n] for n in edits["fixed_zero_eliminations"]}
    unused = {a["var_index"][n] for n in edits["unused_zero_objective_binary_eliminations"]}
    removed = set(aliases) | zeros | unused
    assert (len(aliases), len(zeros), len(unused), len(removed)) == (5663, 477, 477, 6617)
    assert removed == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    assert not (unused & set(a["objective"][1]))
    assert all(not (unused & set(row["terms"])) for row in a["rows"])
    for i in unused:
        assert a["vars"][i]["integer"] and a["vars"][i]["lower"] == 0 and a["vars"][i]["upper"] == 1
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression() if i in zeros | unused else
               expression(0, {b["var_index"][a["vars"][aliases.get(i, i)]["name"]]: 1})
               for i in range(len(a["vars"]))]
    witnesses = {}
    for name, d in edits["alias_eliminations"].items():
        i = a["var_index"][name]
        ref = row_ref(a, d["defining_row"])
        assert "RowEq" in ref
        e = row_fact(a["rows"][ref["RowEq"]], "RowEq")
        c = e[1][i]
        assert mul(e, 1 / c) == expression(0, {i: 1, aliases[i]: -1})
        witnesses[i] = (ref, 1 / c)
    deleted = set(a["row_index"]) - set(b["row_index"])
    assert deleted == {d["defining_row"] for d in edits["alias_eliminations"].values()} | \
        set(edits["bound_implied_row_deletions"]) | set(edits["parallel_row_deletions"])

    proof, f, r = make_proof(a, b)
    zeroeq = {}
    for i in sorted(zeros):
        assert a["vars"][i]["lower"] == a["vars"][i]["upper"] == 0
        zeroeq[i] = f.eqpair({"VarUpper": i}, {"VarLower": i})

    def equality_terms(e):
        terms = []
        for i, c in e[1].items():
            if i in aliases:
                witness, scale = witnesses[i]
                terms.append([witness, -c * scale])
            elif i in zeros:
                terms.append([zeroeq[i], -c])
            else:
                assert i not in unused
        return terms

    checks = []
    for i, v in enumerate(b["vars"]):
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(forward[i], sign), expression(-sign * value))
            checks.append(box(f, wanted, True))
        if v["integer"]:
            checks.append("Exact" if not forward[i][1] else {"VarInt": next(iter(forward[i][1]))})
    for row in b["rows"]:
        rn = row["name"]
        typ = next(iter(row_ref(b, rn)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        ref = row_ref(a, rn)
        checks.append(fact(f, kind, wanted, [[ref, F(1)]] + equality_terms(f.refexpr(ref)),
                           terminal=True))
    residual = plus(substitute(b["objective"], forward), a["objective"], -1)
    checks.append(fact(f, "Eq", residual, equality_terms(a["objective"]), terminal=True))
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(reverse[i], sign), expression(-sign * value))
            checks.append(box(r, wanted, True))
        if v["integer"]:
            checks.append("Exact" if not reverse[i][1] else {"VarInt": next(iter(reverse[i][1]))})
    for row in a["rows"]:
        rn = row["name"]
        typ = next(iter(row_ref(a, rn)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), reverse)
        if rn in b["row_index"]:
            check = row_ref(b, rn)
            assert r.refexpr(check) == wanted
        elif exact(kind, wanted):
            check = "Exact"
        elif rn in edits["bound_implied_row_deletions"]:
            assert kind == "Le"
            check = box(r, wanted, True)
        else:
            d = edits["parallel_row_deletions"][rn]
            ref = row_ref(b, d["witness"])
            check = fact(r, kind, wanted, [[ref, F(d["scale"])]], terminal=True)
        checks.append(check)
    residual = plus(substitute(a["objective"], reverse), b["objective"], -1)
    checks.append(fact(r, "Eq", residual, [], terminal=True))
    r.finish(reverse, checks)

    return proof, {
        "source_variables": 33242,
        "target_variables": 26625,
        "source_rows": 49565,
        "target_rows": 37573,
        "aliases": 5663,
        "fixed_zeros": 477,
        "unused_zero_cost_binary_variables": 477,
        "box_redundancies": 6323,
        "duplicate_redundancies": 6,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test43-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test43"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test43", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test43", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
