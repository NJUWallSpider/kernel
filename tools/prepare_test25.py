#!/usr/bin/env python3
"""Native test25 constant threshold and Boolean-gate elimination."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test88 import fix_binary
from prepare_test54 import fact, box, exact
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (11659, 18442, 11064, 16193)
    fixed = {a["var_index"][d["variable"]]: d for d in h["fixed_variables"]}
    assert len(fixed) == 595
    assert set(fixed) == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression(F(fixed[i]["value"])) if i in fixed else
               expression(0, {b["var_index"][v["name"]]: 1})
               for i, v in enumerate(a["vars"])]

    proof, f, r = make_proof(a, b)

    def cancel_box(builder, e, excluded=()):
        terms = []
        constant = e[0]
        for j, c in e[1].items():
            if j in excluded:
                continue
            # Cancel terms with the bound that minimizes their row contribution.
            typ = "VarLower" if c > 0 else "VarUpper"
            v = builder.model["vars"][j]
            bound = v["lower"] if c > 0 else v["upper"]
            assert bound is not None
            terms.append([{typ: j}, abs(c)])
            constant += c * bound
        return terms, constant

    fixed_eq = {}
    for i, d in fixed.items():
        value = F(d["value"])
        wanted = expression(-value, {i: 1})
        if d["kind"] == "original_bound":
            assert a["vars"][i]["lower"] == a["vars"][i]["upper"] == value
            fixed_eq[i] = f.eqpair({"VarUpper": i}, {"VarLower": i})
        elif d["kind"] == "threshold_domain":
            assert value in (0, 1) and a["vars"][i]["integer"]
            assert a["vars"][i]["lower"] == 0 and a["vars"][i]["upper"] == 1
            wrong = 1 - value
            candidates = []
            for rn in d["rows"]:
                ref = row_ref(a, rn)
                assert f.kind(ref) == "Le"
                e = f.refexpr(ref)
                reduced = expression(e[0] + e[1].get(i, F(0)) * wrong,
                                     {j: c for j, c in e[1].items() if j != i})
                terms, minimum = cancel_box(f, reduced)
                if minimum > 0:
                    candidates.append((ref, e[1].get(i, F(0)), terms, minimum))
            assert candidates, ("wrong binary value needs stronger refutation", d)
            ref, coef, cancellation, minimum = candidates[0]

            def branch(child, assumption, chosen):
                eq = fix_binary(child, i, chosen, assumption)
                if chosen == value:
                    return {"Witness": eq}
                contradiction = child.lin("Le", [[ref, F(1)], [eq, -coef]] + cancellation,
                                          expression(minimum))
                return {"Absurd": contradiction}

            fixed_eq[i] = f.cases("Eq", wanted, expression(0, {i: 1}), {"VarInt": i},
                                  lambda child, assumption: branch(child, assumption, F(0)),
                                  lambda child, assumption: branch(child, assumption, F(1)))
        else:
            assert d["kind"] == "gate" and value in (0, 1)
            sign = F(1) if value == 0 else F(-1)
            desired = mul(wanted, sign)
            proof_fact = None
            for rn in d["rows"]:
                ref = row_ref(a, rn)
                assert f.kind(ref) == "Le"
                e = f.refexpr(ref)
                coef = e[1].get(i, F(0))
                if not coef or coef * sign <= 0:
                    continue
                scale = sign / coef
                terms = [[ref, scale]]
                reduced = mul(e, scale)
                for j, c in list(reduced[1].items()):
                    if j != i and j in fixed_eq:
                        terms.append([fixed_eq[j], -c])
                        reduced = plus(reduced, f.refexpr(fixed_eq[j]), -c)
                cancellation, constant = cancel_box(f, reduced, (i,))
                residual = constant - desired[0]
                if residual >= 0:
                    proof_fact = f.lin("Le", terms + cancellation, desired, -residual)
                    break
            assert proof_fact is not None, ("gate cannot be bounded", d)
            fixed_eq[i] = (f.eqpair(proof_fact, {"VarLower": i}) if value == 0
                           else f.eqpair({"VarUpper": i}, proof_fact))
        assert f.refexpr(fixed_eq[i]) == wanted

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        for i, v in enumerate(out["vars"]):
            e = mapping[i]
            for typ, value, sign in [("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)]:
                if value is not None:
                    checks.append(box(builder, plus(mul(e, sign), expression(-sign * value)), True))
            if v["integer"]:
                checks.append(fact(builder, "Int", e,
                                   [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
        for row in out["rows"]:
            rn = row["name"]
            typ = next(iter(row_ref(out, rn)))
            kind = "Eq" if typ == "RowEq" else "Le"
            wanted = substitute(row_fact(row, typ), mapping)
            if back:
                if rn in b["row_index"]:
                    check = row_ref(b, rn)
                    assert builder.refexpr(check) == wanted
                elif exact(kind, wanted):
                    check = "Exact"
                elif kind == "Le":
                    check = box(builder, wanted, True)
                else:
                    check = builder.eqpair(box(builder, wanted), box(builder, mul(wanted, -1)))
            else:
                ref = row_ref(a, rn)
                check = fact(builder, kind, wanted,
                             [[ref, F(1)]] +
                             [[fixed_eq[i], -c] for i, c in builder.refexpr(ref)[1].items()
                              if i in fixed], terminal=True)
            checks.append(check)
        wanted = plus(substitute(out["objective"], mapping), inp["objective"], -1)
        checks.append(fact(builder, "Eq", wanted,
                           [] if back else [[fixed_eq[i], -c]
                                            for i, c in a["objective"][1].items() if i in fixed],
                           terminal=True))
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 11659, "target_variables": 11064,
        "source_rows": 18442, "target_rows": 16193,
        "fixed_original_domains": 19, "fixed_binary_thresholds": 487,
        "fixed_gate_outputs": 89, "removed_box_rows": 2249,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test25-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test25"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test25", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test25", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
