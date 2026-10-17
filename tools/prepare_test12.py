#!/usr/bin/env python3
"""Native complete forced-zero closure and zero-extension bijections for test12."""
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
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (7195, 426, 6200, 310)
    removed = {a["var_index"][n] for n in h["removed_variables"]}
    assert len(removed) == 995
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
    containments = 0
    for round_hint in h["fixing_rounds"]:
        previous = dict(zero)
        pairs = {}
        for d in round_hint["fixings"]:
            i = a["var_index"][d["variable"]]
            assert i not in zero and d["value"] == 0
            small = d["witness"]["smaller"]
            large = d["witness"]["larger"]
            pair = (small, large)
            if pair not in pairs:
                sr = row_ref(a, small)
                lr = row_ref(a, large)
                assert "RowEq" in sr and "RowEq" in lr
                e = plus(p.refexpr(lr), p.refexpr(sr), -1)
                terms = [[lr, F(1)], [sr, F(-1)]]
                for j, c in e[1].items():
                    if j in previous:
                        terms.append([previous[j], -c])
                wanted = expression(e[0], {j: c for j, c in e[1].items() if j not in previous})
                assert wanted[0] == 0 and wanted[1] and all(c == 1 for c in wanted[1].values())
                pairs[pair] = p.lin("Eq", terms, wanted)
                containments += 1
            eq = pairs[pair]
            e = p.refexpr(eq)
            assert e[1][i] == 1
            upper = p.lin("Le", [[eq, F(1)]] +
                          [[{"VarLower": j}, c] for j, c in e[1].items() if j != i],
                          expression(0, {i: 1}))
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
        assert row["sense"] == "E"
        wanted = substitute(row_fact(row, "RowEq"), forward)
        ref = row_ref(a, n)
        terms = [[ref, F(1)]] + [[zero[i], -c] for i, c in f.refexpr(ref)[1].items() if i in zero]
        checks.append(fact(f, "Eq", wanted, terms, terminal=True))
    wanted = plus(substitute(b["objective"], forward), a["objective"], -1)
    terms = [[zero[i], -c] for i, c in a["objective"][1].items() if i in zero]
    checks.append(fact(f, "Eq", wanted, terms, terminal=True))
    f.finish(forward, checks)

    recovered = {}

    def recover_row(name):
        if name in recovered:
            return recovered[name]
        wanted = substitute(row_fact(a["rows"][a["row_index"][name]], "RowEq"), reverse)
        if name in b["row_index"]:
            ref = row_ref(b, name)
            assert r.refexpr(ref) == wanted
        elif name in h["duplicate_rows"]:
            ref = recover_row(h["duplicate_rows"][name])
            assert r.refexpr(ref) == wanted
        else:
            coeff = h["linear_relations"][name]["coefficients"]
            assert coeff[name] == 1 and all(rr in b["row_index"] for rr in coeff if rr != name)
            ref = r.lin("Eq", [[row_ref(b, rr), -F(c)] for rr, c in coeff.items() if rr != name], wanted)
        recovered[name] = ref
        return ref

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
        assert row["sense"] == "E"
        checks.append(recover_row(n))
    wanted = plus(substitute(a["objective"], reverse), b["objective"], -1)
    checks.append(fact(r, "Eq", wanted, [], terminal=True))
    r.finish(reverse, checks)

    return proof, {
        "source_variables": 7195,
        "target_variables": 6200,
        "source_rows": 426,
        "target_rows": 310,
        "forced_zeros": 995,
        "distinct_containment_premises": containments,
        "duplicates": 83,
        "signed_linear_dependencies": 33,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test12-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test12"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test12", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test12", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
