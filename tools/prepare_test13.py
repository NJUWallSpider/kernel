#!/usr/bin/env python3
"""Native test13 private one-hot menu projection proof.

The proof is constructed through ``kernel_compiler`` and compiled to RPA 12 /
RPX 11 by the native compiler.  The legacy four-claim Request layout collapses
to the two MI-OPT directions: the linear target-to-source map and one
simultaneous integer menu lift that reconstructs all private source options.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact
from prepare_test57 import substitute
from prepare_native import (
    compile_case,
    is_exact,
    legacy_expr,
    make_proof,
    sha,
)


def prove(builder, kind, wanted, terms):
    """Attach one exact model fact or a native linear rule to an obligation."""
    if is_exact(kind, wanted):
        return "Exact"
    if isinstance(terms, dict):
        fact = builder.ref(terms)
        assert fact.kind in (kind, "Eq") and legacy_expr(fact.expression) == wanted
        return terms
    if terms is None:
        raise AssertionError(("no premise", kind, wanted))
    if len(terms) == 1 and terms[0][1] == 1:
        fact = builder.ref(terms[0][0])
        if fact.kind in (kind, "Eq") and legacy_expr(fact.expression) == wanted:
            return terms[0][0]
    return builder.lin(kind, terms, wanted)


def finish_checks(builder, output, mapping, domain_terms, row_terms, objective_terms):
    """Build Return checks in the order of the native obligation walker."""
    checks = []
    for i, variable in enumerate(output["vars"]):
        if variable["lower"] is not None:
            wanted = plus(expression(variable["lower"]), mapping[i], -1)
            checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarLower")))
        if variable["upper"] is not None:
            wanted = plus(mapping[i], expression(-variable["upper"]))
            checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarUpper")))
        if variable["integer"]:
            checks.append(prove(builder, "Int", mapping[i], domain_terms(i, "VarInt")))
    for i, row in enumerate(output["rows"]):
        typ = next(iter(row_ref(output, row["name"])))
        wanted = substitute(row_fact(row, typ), mapping)
        checks.append(prove(builder, "Eq" if typ == "RowEq" else "Le", wanted, row_terms(i)))
    residual = plus(substitute(output["objective"], mapping), builder.model["objective"], -1)
    checks.append(prove(builder, "Le", residual, objective_terms))
    return checks


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (
        10399, 14589, 5677, 14571)
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    definitions = []
    removed = set()
    added = {}
    for d in h["blocks"]:
        L, U, c = map(F, (d["lower"], d["upper"], d["target"]))
        x, g, cy = [a["var_index"][d[key]] for key in ("x", "trigger", "special_indicator")]
        options = sorted((F(v), a["var_index"][n]) for n, v in d["indicator_values"].items())
        assert [v for v, i in options] == list(range(int(L), int(U) + 1)) and L < c < U
        assert options[int(c - L)][1] == cy
        assert not (removed & {i for v, i in options})
        removed.update(i for v, i in options)
        for v, i in options:
            assert a["vars"][i]["integer"] and a["vars"][i]["lower"] == 0 and a["vars"][i]["upper"] == 1
        sumref = row_ref(a, d["sum_row"])
        valueref = row_ref(a, d["value_row"])
        linkref = row_ref(a, d["link_row"])
        assert row_fact(a["rows"][a["row_index"][d["sum_row"]]], "RowEq") == \
            expression(-1, {i: 1 for v, i in options})
        assert row_fact(a["rows"][a["row_index"][d["value_row"]]], "RowEq") == \
            expression(0, {**{i: v for v, i in options if v}, x: -1})
        assert row_fact(a["rows"][a["row_index"][d["link_row"]]], "RowUpper") == \
            expression(0, {g: 1, cy: -1})
        added[d["added_lower_row"]] = (
            [[valueref, F(1)], [sumref, -L], [linkref, c - L]] +
            [[{"VarLower": i}, v - L] for v, i in options if v != c and v != L])
        added[d["added_upper_row"]] = (
            [[valueref, F(-1)], [sumref, U], [linkref, U - c]] +
            [[{"VarLower": i}, U - v] for v, i in options if v != c and v != U])
        definitions.append({
            **d, "L": L, "U": U, "c": c,
            "x_id": b["var_index"][d["x"]],
            "g_id": b["var_index"][d["trigger"]],
            "options": [i for v, i in options],
        })
    assert removed == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    assert len(removed) == 4722

    proof, forward_builder, reverse_builder = make_proof(a, b)

    # Target-to-source: the retained coordinates are the exact identity map.
    def forward_domain(i, kind):
        return {kind: common[i][0]}

    def forward_row(i):
        name = b["rows"][i]["name"]
        if name in added:
            return added[name]
        if name in a["row_index"]:
            return [[row_ref(a, name), F(1)]]
        raise AssertionError(("missing forwarded row", name))

    forward_checks = finish_checks(
        forward_builder, b, forward, forward_domain, forward_row, [])
    forward_builder.finish(forward, forward_checks)

    # Source-to-target: one simultaneous lift reconstructs every private option.
    entries = []
    for d in definitions:
        L, U, c, x = d["L"], d["U"], d["c"], d["x_id"]
        index = expression(-L, {x: 1})
        integer = reverse_builder.lin(
            "Int", [[{"VarInt": x}, F(1)]], index, -L)
        entries.append({
            "maximum_index": int(U - L),
            "activation": expression(1),
            "index": index,
            "checks": ["Exact", "Exact", "Exact",
                       {"VarLower": x}, {"VarUpper": x}, integer],
        })
    child = reverse_builder.menus(entries)
    layout = child.layout
    assert len(layout) == len(definitions)

    mapping = [None] * len(a["vars"])
    for i, j in common:
        mapping[i] = expression(0, {j: 1})
    rowproof = {}
    for d, generated in zip(definitions, layout):
        L, U, c, x, g = d["L"], d["U"], d["c"], d["x_id"], d["g_id"]
        K = int(U - L)
        j = int(c - L)
        options = d["options"]
        op = generated["options"]
        assert len(op) == K + 1
        sumref = {"RowEq": generated["sum_row"]}
        moment = {"RowEq": generated["moment_row"]}
        for source, fresh in zip(options, op):
            mapping[source] = expression(0, {fresh: 1})
        rowproof[d["sum_row"]] = [[sumref, F(1)]]
        rowproof[d["value_row"]] = [[moment, F(1)], [sumref, L]]

        zc = op[j]
        goal = expression(0, {g: 1, zc: -1})

        def active(branch, assumption):
            geq = branch.eqpair({"VarUpper": g}, assumption)
            upper = branch.lin(
                "Le", [[{"RowUpper": d["added_upper_row"]}, F(1)],
                       [geq, -(U - c)]], expression(-c, {x: 1}))
            lower = branch.lin(
                "Le", [[{"RowUpper": d["added_lower_row"]}, F(1)],
                       [geq, -(c - L)]], expression(c, {x: -1}))
            xeq = branch.eqpair(upper, lower)
            meq = branch.lin(
                "Eq", [[moment, F(1)], [xeq, F(1)]],
                expression(-j, {i: F(q) for q, i in enumerate(op) if q}))
            desired = expression(-1, {zc: 1})

            def not_special(sub, zero):
                zeq = sub.eqpair(zero, {"VarLower": zc})
                part = expression(0, {i: 1 for q, i in enumerate(op) if q < j})
                integer = sub.lin(
                    "Int", [[{"VarInt": i}, F(1)] for q, i in enumerate(op) if q < j],
                    part)

                def no_lower(leaf, assump):
                    terms = [[meq, F(1)], [sumref, F(-j - 1)],
                             [assump, F(j + 1)], [zeq, F(1)]]
                    terms += [[{"VarLower": i}, F(q)]
                              for q, i in enumerate(op) if q < j and q]
                    terms += [[{"VarLower": i}, F(q - j - 1)]
                              for q, i in enumerate(op) if q > j + 1]
                    return {"Absurd": leaf.lin("Le", terms, expression(1))}

                def some_lower(leaf, assump):
                    terms = [[sumref, F(K)], [meq, F(-1)], [assump, F(K - j + 1)]]
                    terms += [[{"VarLower": i}, F(j - 1 - q)]
                              for q, i in enumerate(op) if q < j - 1]
                    terms += [[{"VarLower": i}, F(K - q)]
                              for q, i in enumerate(op) if q >= j and q < K]
                    return {"Absurd": leaf.lin("Le", terms, expression(1))}

                return {"Witness": sub.cases(
                    "Eq", desired, part, integer, no_lower, some_lower)}

            def selected_one(sub, one):
                return {"Witness": sub.eqpair({"VarUpper": zc}, one)}

            selected = branch.cases(
                "Eq", desired, expression(0, {zc: 1}), {"VarInt": zc},
                not_special, selected_one)
            return branch.lin("Le", [[geq, F(1)], [selected, F(-1)]], goal)

        def left(branch, assumption):
            return branch.lin(
                "Le", [[assumption, F(1)], [{"VarLower": zc}, F(1)]], goal)

        rowproof[d["link_row"]] = child.cases(
            "Le", goal, expression(0, {g: 1}), {"VarInt": g}, left, active)

    assert all(value is not None for value in mapping)

    def reverse_domain(i, kind):
        return {kind: next(iter(mapping[i][1]))}

    def reverse_row(i):
        name = a["rows"][i]["name"]
        if name in rowproof:
            return rowproof[name]
        if name in b["row_index"]:
            return [[row_ref(b, name), F(1)]]
        raise AssertionError(("missing reversed row", name))

    reverse_checks = finish_checks(
        child, a, mapping, reverse_domain, reverse_row, [])
    child.finish(mapping, reverse_checks)

    return proof, {
        "source_variables": 10399,
        "target_variables": 5677,
        "source_rows": 14589,
        "target_rows": 14571,
        "simultaneous_menus": len(definitions),
        "generated_binary_variables": sum(int(d["U"] - d["L"]) + 1 for d in definitions),
        "retained_coordinate_observations_per_claim": len(common),
        "directions": ["forward", "reverse"],
        "claims": 2,
        "legacy_claims_collapsed": 4,
        "legacy_projection_observations_omitted": len(common),
        "legacy_continuous_reverse_omitted": True,
        "obligations_by_claim": [len(forward_checks), len(reverse_checks)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test13-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test13"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(
        parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(
        proof, args.out, case_id="test13", source=source, target=target,
        metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                  "counts": counts,
                  "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({
        "case_id": "test13",
        "status": record["status"],
        "guarantee": record["verification"].get("guarantee"),
        "obligations": record["verification"]["statistics"]["obligations"],
        "seconds": record["preparation_seconds"],
    }))


if __name__ == "__main__":
    main()
