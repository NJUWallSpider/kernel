#!/usr/bin/env python3
"""Native test76 capacity rounding and exact auxiliary substitution."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact, box
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (1758, 351, 1682, 301)
    removed_zero = {a["var_index"][n] for n in h["removed_zero_variables"]}
    aux = {a["var_index"][n] for n in h["removed_auxiliary_variables"]}
    assert len(removed_zero) == 26 and len(aux) == 50
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    assert removed_zero | aux == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}

    proof, f, r = make_proof(a, b)
    chain = f.lin("Eq", [[row_ref(a, "c00_1"), 1]] +
                  [[row_ref(a, f"c01_{k}"), 1] for k in range(1, 96)])
    cap = f.lin("Le", [[chain, -1]] +
                [[row_ref(a, f"c04_{j}"), -F(w)]
                 for j, w in h["zero_choice_proof"]["mandatory_groups"].items()] +
                [[{"VarUpper": a["var_index"]["z#95"]}, 1]])
    capexpr = f.refexpr(cap)
    assert capexpr[0] == -4 and all(c > 0 for c in capexpr[1].values())

    def rounded(builder, le, integer):
        le_ref = builder.refexpr(le)
        int_ref = builder.refexpr(integer)
        assert builder.kind(le) == "Le" and builder.kind(integer) == "Int" and le_ref[1] == int_ref[1]
        d = le_ref[0] - int_ref[0]
        ceiling = -((-d.numerator) // d.denominator)
        expected = expression(int_ref[0] + ceiling, int_ref[1])
        result = builder.round(le, integer)
        assert builder.refexpr(result) == expected
        return result

    zero = {}
    for i in sorted(removed_zero):
        assert capexpr[1][i] == 5 and a["vars"][i]["integer"]
        le = f.lin("Le", [[cap, F(1, 5)]] +
                   [[{"VarLower": j}, c / F(5)] for j, c in capexpr[1].items() if j != i],
                   expression(F(-4, 5), {i: 1}))
        zero[i] = f.eqpair(rounded(f, le, {"VarInt": i}), {"VarLower": i})

    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [None] * len(a["vars"])
    definitions = {}
    recoveries = {}
    groups = {}
    for i, j in common:
        reverse[i] = expression(0, {j: 1})
    for i in removed_zero:
        reverse[i] = expression()
    for key, hint in h["substitution_certificates"].items():
        i = a["var_index"][hint["eliminated_variable"]]
        rn = f"c02_{key}"
        hn = f"c04_{key}"
        ref = row_ref(a, rn)
        e = f.refexpr(ref)
        assert e[0] == 0 and e[1][i] == 1 and i in aux
        reverse[i] = expression(0, {b["var_index"][a["vars"][j]["name"]]: -c
                                    for j, c in e[1].items()
                                    if j != i and j not in removed_zero})
        definitions[i] = (rn, hn)
        groups[f"c03_{key}"] = (rn, hn, F(hint["original_bound_lower"]))
        expected = plus(substitute(reverse[i], forward), expression(0, {i: 1}), -1)
        recoveries[i] = f.lin("Eq", [[ref, -1]] +
                              [[zero[j], c] for j, c in e[1].items() if j in removed_zero],
                              expected)
    assert all(e is not None for e in reverse)

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        for i, v in enumerate(out["vars"]):
            e = mapping[i]
            for value, sign in [(v["lower"], -1), (v["upper"], 1)]:
                if value is None:
                    continue
                wanted = plus(mul(e, sign), expression(-sign * value))
                if back and i in aux:
                    rn, hn = definitions[i]
                    href = row_ref(b, hn)
                    assert set(e[1]) <= set(builder.refexpr(href)[1])
                    weights = {j: (value - c if sign == 1 else c - value)
                               for j, c in e[1].items()}
                    assert all(c >= 0 for c in weights.values())
                    check = fact(builder, "Le", wanted,
                                 [[href, sign * value]] +
                                 [[{"VarLower": j}, c] for j, c in weights.items() if c],
                                 terminal=True)
                else:
                    check = box(builder, wanted, True)
                checks.append(check)
            if v["integer"]:
                checks.append(fact(builder, "Int", e,
                                   [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
        for row in out["rows"]:
            rn = row["name"]
            typ = next(iter(row_ref(out, rn)))
            kind = "Eq" if typ == "RowEq" else "Le"
            wanted = substitute(row_fact(row, typ), mapping)
            if not back:
                terms = [[row_ref(a, rn), 1]]
                if rn in groups:
                    dn, hn, lower = groups[rn]
                    terms += [[row_ref(a, dn), -1], [row_ref(a, hn), -lower]]
                raw = expression()
                for ref, c in terms:
                    raw = plus(raw, builder.refexpr(ref), c)
                terms += [[zero[i], -c] for i, c in raw[1].items() if i in removed_zero]
                check = fact(builder, kind, wanted, terms, terminal=True)
            elif rn in h["removed_rows"]:
                assert wanted == expression()
                check = "Exact"
            elif rn in groups:
                dn, hn, lower = groups[rn]
                check = fact(builder, kind, wanted,
                             [[row_ref(b, rn), 1], [row_ref(b, hn), lower]], terminal=True)
            else:
                check = row_ref(b, rn)
                assert builder.refexpr(check) == wanted
            checks.append(check)
        wanted = plus(substitute(out["objective"], mapping), inp["objective"], -1)
        assert wanted == expression()
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 1758, "target_variables": 1682,
        "source_rows": 351, "target_rows": 301,
        "capacity_binary_zeros": 26, "continuous_affine_substitutions": 50,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test76-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test76"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test76", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test76", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
