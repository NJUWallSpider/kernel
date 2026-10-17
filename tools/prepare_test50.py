#!/usr/bin/env python3
"""Native test50 implied-integrality and row equivalence proof."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact, exact
from prepare_native import compile_case, make_proof, sha


def cases_int(builder, variable, split_var, left, right):
    wanted = expression(0, {variable: 1})
    split = expression(0, {split_var: 1})

    def left_branch(child, assumption):
        ref = left(child, assumption)
        assert child.kind(ref) == "Int" and child.refexpr(ref) == wanted
        return {"Witness": ref}

    def right_branch(child, assumption):
        ref = right(child, assumption)
        assert child.kind(ref) == "Int" and child.refexpr(ref) == wanted
        return {"Witness": ref}

    return builder.cases("Int", wanted, split, {"VarInt": split_var},
                         left_branch, right_branch)


def integrality(b, h, builder):
    known = {}
    for d in h["u_integrality"]:
        x = b["var_index"][d["x"]]
        k = F(d["k"])
        us = [b["var_index"][n] for n in d["u_variables"]]
        links = [row_ref(b, n) for n in d["lower_rows"]]
        balance = row_ref(b, d["balance_row"])
        count = row_ref(b, d["original_count_row"])
        assert b["vars"][x]["integer"] and b["vars"][x]["lower"] == 0 and b["vars"][x]["upper"] == 1
        assert builder.refexpr(balance) == expression(0, {**{i: 1 for i in us}, x: -k})
        sums = []
        combined = expression()
        for u, link in zip(us, links):
            assert not b["vars"][u]["integer"]
            e = builder.refexpr(link)
            s = plus(e, expression(1, {x: -1, u: 1}))
            assert s[0] == 0 and all(c == 1 and b["vars"][i]["integer"] for i, c in s[1].items())
            sums.append(s)
            combined = plus(combined, s)
        assert plus(combined, expression(-k)) == builder.refexpr(count)
        for pos, (u, s) in enumerate(zip(us, sums)):
            assert u not in known

            def inactive(child, assumption):
                terms = ([[balance, F(1)], [assumption, k]] +
                         [[{"VarLower": i}, F(1)] for i in us if i != u])
                upper = child.lin("Le", terms, expression(0, {u: 1}))
                eq = child.eqpair(upper, {"VarLower": u})
                return child.lin("Int", [[eq, F(1)]], expression(0, {u: 1}))

            def active(child, assumption):
                fixed = child.eqpair({"VarUpper": x}, assumption)
                wanted = plus(expression(0, {u: 1}), s, -1)
                terms = ([[balance, F(1)], [count, F(-1)], [fixed, k - (len(us) - 1)]] +
                         [[link, F(1)] for q, link in enumerate(links) if q != pos])
                upper = child.lin("Le", terms, wanted)
                lower = child.lin("Le", [[links[pos], F(1)], [assumption, F(1)]],
                                  mul(wanted, -1))
                eq = child.eqpair(upper, lower)
                return child.lin("Int", [[eq, F(1)]] +
                                 [[{"VarInt": i}, c] for i, c in s[1].items()],
                                 expression(0, {u: 1}))

            known[u] = cases_int(builder, u, x, inactive, active)
    for d in h["unit_definition_integrality"]:
        i = b["var_index"][d["variable"]]
        ref = row_ref(b, d["row"])
        e = builder.refexpr(ref)
        pivot = e[1][i]
        terms = [[ref, 1 / pivot]] + [[{"VarInt": j}, -c / pivot]
                                      for j, c in e[1].items() if j != i]
        assert i not in known and not b["vars"][i]["integer"]
        known[i] = builder.lin("Int", terms, expression(0, {i: 1}), -e[0] / pivot)
    assert set(known) == {i for i, v in enumerate(b["vars"]) if not v["integer"]}
    assert len(known) == 11935
    return known


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (28926, 23294, 28926, 20024)
    assert set(a["var_index"]) == set(b["var_index"])
    assert all(v["integer"] and v["lower"] == 0 and v["upper"] == 1 for v in a["vars"])
    assert all(v["lower"] == 0 and v["upper"] == 1 for v in b["vars"])
    forward = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    reverse = [expression(0, {b["var_index"][v["name"]]: 1}) for v in a["vars"]]
    common = [[next(iter(e[1])), j] for j, e in enumerate(forward)]
    pairs = {d["retained"]: d["removed"] for d in h["opposite_pairs"]}
    partners = {d["removed"]: d["retained"] for d in h["opposite_pairs"]}
    aggregate = {d["removed_row"]: d["linear_combination"] for d in h["redundant_equalities"]}
    assert set(a["row_index"]) - set(b["row_index"]) == set(partners) | set(aggregate) | set(h["empty_tautologies"])
    assert substitute(b["objective"], forward) == a["objective"]

    proof, f, r = make_proof(a, b)
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        known = integrality(b, h, builder) if back else {}
        checks = []
        for i, v in enumerate(out["vars"]):
            j = next(iter(mapping[i][1]))
            checks.extend([{"VarLower": j}, {"VarUpper": j}])
            if v["integer"]:
                checks.append(known[j] if j in known else {"VarInt": j})
        for row in out["rows"]:
            n = row["name"]
            typ = next(iter(row_ref(out, n)))
            kind = "Eq" if typ == "RowEq" else "Le"
            wanted = substitute(row_fact(row, typ), mapping)
            if not back and n in pairs:
                ref = builder.eqpair(row_ref(a, n), row_ref(a, pairs[n]))
                assert builder.refexpr(ref) == wanted
                check = ref
            elif back and (n in pairs or n in partners):
                retained = partners.get(n, n)
                ref = {"RowEq": b["row_index"][retained]}
                e = builder.refexpr(ref)
                scale = F(1) if e == wanted else F(-1)
                check = fact(builder, "Le", wanted, [[ref, scale]])
            elif back and n in aggregate:
                check = fact(builder, "Eq", wanted,
                             [[row_ref(b, source), F(c)] for source, c in aggregate[n].items()])
            elif exact(kind, wanted):
                check = "Exact"
            else:
                check = row_ref(inp, n)
                assert builder.refexpr(check) == wanted and builder.kind(check) == kind
            checks.append(check)
        assert plus(substitute(out["objective"], mapping), inp["objective"], -1) == expression()
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 28926, "target_variables": 28926,
        "source_rows": 23294, "target_rows": 20024,
        "implied_integrality_variables": 11935, "conditional_groups": 320,
        "opposite_row_pairs": 320, "aggregate_equalities": 10,
        "empty_tautologies": 2940, "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test50-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test50"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/model_reformulated.mps"
    audit = run / "output/audit.json"
    witness = run / "output/proof_certificates.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(witness.read_text()))
    record = compile_case(proof, args.out, case_id="test50", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "proof_hints": {"path": str(witness), "sha256": sha(witness)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test50", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
