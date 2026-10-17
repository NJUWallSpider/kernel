#!/usr/bin/env python3
"""Native full alias-elimination affine bijections for test11."""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (62529, 121161, 40488, 90561)
    edits = h["edits"]
    aliases = {a["var_index"][n]: a["var_index"][rep]
               for n, rep in edits["eliminated_variables"].items()}
    assert len(aliases) == 22041
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    assert set(aliases) == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression(0, {b["var_index"][a["vars"][aliases.get(i, i)]["name"]]: 1})
               for i in range(len(a["vars"]))]
    witnesses = {}
    for rn in edits["alias_equalities_removed"]:
        ref = row_ref(a, rn)
        assert "RowEq" in ref
        row = a["rows"][a["row_index"][rn]]
        removed = [i for i in row["terms"] if i in aliases]
        assert len(removed) == 1
        i = removed[0]
        e = row_fact(row, "RowEq")
        c = e[1][i]
        assert mul(e, 1 / c) == expression(0, {i: 1, aliases[i]: -1}) and i not in witnesses
        witnesses[i] = (ref, 1 / c)
    assert set(witnesses) == set(aliases)
    deleted = set(a["row_index"]) - set(b["row_index"])
    assert deleted == set(edits["alias_equalities_removed"]) | \
        set(edits["bound_redundancy_certificates"]) | \
        set(edits["nonnegative_dominance_certificates"])
    assert substitute(a["objective"], reverse) == b["objective"]
    assert substitute(b["objective"], forward) == a["objective"]

    proof, f, r = make_proof(a, b)

    checks = []
    for i, v in enumerate(b["vars"]):
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(forward[i], sign), expression(-sign * value))
            checks.append(box(f, wanted, True))
        if v["integer"]:
            checks.append({"VarInt": next(iter(forward[i][1]))})
    for row in b["rows"]:
        rn = row["name"]
        typ = next(iter(row_ref(b, rn)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        ref = row_ref(a, rn)
        terms = [[ref, F(1)]]
        for i, c in f.refexpr(ref)[1].items():
            if i in aliases:
                witness, scale = witnesses[i]
                terms.append([witness, -c * scale])
        checks.append(fact(f, kind, wanted, terms, terminal=True))
    checks.append("Exact")
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(reverse[i], sign), expression(-sign * value))
            checks.append(box(r, wanted, True))
        if v["integer"]:
            checks.append({"VarInt": next(iter(reverse[i][1]))})
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
        elif rn in edits["bound_redundancy_certificates"]:
            assert kind == "Le"
            check = box(r, wanted, True)
        else:
            assert kind == "Le"
            d = edits["nonnegative_dominance_certificates"][rn]
            ref = row_ref(b, d["retained_witness_row"])
            delta = plus(wanted, r.refexpr(ref), -1)
            terms = [[ref, F(1)]]
            for j, c in delta[1].items():
                assert c < 0 and b["vars"][j]["lower"] == 0
                terms.append([{"VarLower": j}, -c])
            assert delta[0] == 0
            check = fact(r, "Le", wanted, terms, terminal=True)
        checks.append(check)
    checks.append("Exact")
    r.finish(reverse, checks)

    return proof, {
        "source_variables": len(a["vars"]),
        "target_variables": len(b["vars"]),
        "source_rows": len(a["rows"]),
        "target_rows": len(b["rows"]),
        "aliases": len(aliases),
        "box_redundancies": len(edits["bound_redundancy_certificates"]),
        "dominance_redundancies": len(edits["nonnegative_dominance_certificates"]),
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test11-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test11"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/model_reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test11", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test11", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
