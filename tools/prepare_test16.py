#!/usr/bin/env python3
"""Native complete forced-zero closure and zero-extension bijections for test16."""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (228350, 126512, 198848, 100518)
    removed = {a["var_index"][n] for n in h["removed_variables_zero"]}
    assert len(removed) == 29502
    assert removed == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression() if i in removed else expression(0, {b["var_index"][v["name"]]: 1})
               for i, v in enumerate(a["vars"])]

    proof, f, r = make_proof(a, b)
    p = f
    zero = {}
    for d in h["zero_proof_order"]:
        ref = row_ref(a, d["row"])
        e = p.refexpr(ref)
        assert e[0] == 0
        for n in d["new_zero_variables"]:
            i = a["var_index"][n]
            assert i not in zero and a["vars"][i]["lower"] == 0
            coef = e[1][i]
            terms = [[ref, 1 / coef]]
            for j, c in e[1].items():
                if i == j:
                    continue
                if j in zero:
                    terms.append([zero[j], -c / coef])
                else:
                    assert a["vars"][j]["lower"] == 0 and c / coef >= 0
                    terms.append([{"VarLower": j}, c / coef])
            upper = p.lin("Le", terms, expression(0, {i: 1}))
            zero[i] = p.eqpair(upper, {"VarLower": i})
    assert set(zero) == removed

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
            checks.append("Exact" if not e[1] else {"VarInt": next(iter(e[1]))})
    for row in b["rows"]:
        n = row["name"]
        typ = next(iter(row_ref(b, n)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        ref = row_ref(a, n)
        terms = [[ref, F(1)]] + [[zero[i], -c] for i, c in f.refexpr(ref)[1].items() if i in zero]
        checks.append(fact(f, kind, wanted, terms, terminal=True))
    wanted = plus(substitute(b["objective"], forward), a["objective"], -1)
    terms = [[zero[i], -c] for i, c in a["objective"][1].items() if i in zero]
    checks.append(fact(f, "Eq", wanted, terms, terminal=True))
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        e = reverse[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            if exact("Le", wanted):
                check = "Exact"
            else:
                check = {typ: next(iter(e[1]))}
                assert r.refexpr(check) == wanted
            checks.append(check)
        if v["integer"]:
            checks.append("Exact" if not e[1] else {"VarInt": next(iter(e[1]))})
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
        else:
            assert kind == "Le"
            check = box(r, wanted, True)
        checks.append(check)
    wanted = plus(substitute(a["objective"], reverse), b["objective"], -1)
    checks.append(fact(r, "Eq", wanted, [], terminal=True))
    r.finish(reverse, checks)

    return proof, {
        "source_variables": 228350,
        "target_variables": 198848,
        "source_rows": 126512,
        "target_rows": 100518,
        "forced_zero_variables": 29502,
        "ordered_zero_steps": 25842,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test16-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test16"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test16", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test16", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
