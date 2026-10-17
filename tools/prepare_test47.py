#!/usr/bin/env python3
"""Native test47 exchange normalization through intervals and menus.

Each stage extends one current point by native interval scopes, proves all new
binary facts with Cases, and preserves every original covering inequality. The
reverse aggregation uses one native MenuLift. Both integer directions are the
only claims; the legacy extra observations collapse to the MI-OPT contract.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test48 import (emit_checks, fixed_bit, int_witness, lift, rounded,
                            sumexpr)
from prepare_native import compile_case, make_proof


def bit(p, e, lo, hi, integer):
    return {"expr": e, "lower": lo, "upper": hi, "integer": integer}


def and_integrality(p, z, layout, bits):
    """Balanced integer-sum search for a zero factor, or proof all are one."""
    def split(cur, ids):
        e = plus(sumexpr(bits[k]["expr"] for k in ids), expression(1 - len(ids)))
        integer = cur.lin("Int", [[bits[k]["integer"], F(1)] for k in ids], e,
                          constant=1 - len(ids))
        return {"expr": e, "integer": integer}

    def deficient(cur, ids, missing):
        if len(ids) == 1:
            k = ids[0]
            eq = cur.eqpair(missing, bits[k]["lower"])
            upper = cur.lin("Le", [[{"RowUpper": layout["upper"][k]}, F(1)],
                                   [eq, F(1)]], z)
            fixed_zero = cur.eqpair(upper, {"RowLower": layout["lower"][0]})
            return {"Witness": cur.lin("Int", [[fixed_zero, F(1)]], z)}
        cut = len(ids) // 2
        left, right = ids[:cut], ids[cut:]

        def zero(child, assumption):
            return deficient(child, left, assumption)

        def one(child, assumption):
            remaining = plus(sumexpr(bits[k]["expr"] for k in right),
                             expression(1 - len(right)))
            ref = child.lin("Le", [[missing, F(1)], [assumption, F(1)]], remaining)
            return deficient(child, right, ref)

        descriptor = split(cur, left)
        return {"Witness": cur.cases("Int", z, descriptor["expr"], descriptor["integer"],
                                     zero, one)}

    def all_one(cur, assumption):
        fixed = []
        for k, b in enumerate(bits):
            lower = cur.lin("Le", [[assumption, F(1)]] +
                            [[v["upper"], F(1)] for j, v in enumerate(bits) if j != k],
                            plus(expression(1), b["expr"], -1))
            fixed.append(cur.eqpair(b["upper"], lower))
        lower = cur.lin("Le", [[{"RowLower": layout["lower"][1]}, F(1)]] +
                        [[r, F(-1)] for r in fixed], plus(expression(1), z, -1))
        upper = cur.lin("Le", [[{"RowUpper": layout["upper"][0]}, F(1)],
                               [fixed[0], F(1)]], plus(z, expression(-1)))
        eq = cur.eqpair(upper, lower)
        return {"Witness": cur.lin("Int", [[eq, F(1)]], z, constant=1)}

    ids = list(range(len(bits)))
    descriptor = split(p, ids)
    return p.cases("Int", z, descriptor["expr"], descriptor["integer"],
                   lambda cur, a: deficient(cur, ids, a), all_one)


def factors_one(p, z_eq, layout, bits):
    result = []
    for k, b in enumerate(bits):
        lower = p.lin("Le", [[{"RowUpper": layout["upper"][k]}, F(1)],
                             [z_eq, F(-1)]], plus(expression(1), b["expr"], -1))
        result.append(p.eqpair(b["upper"], lower))
    return result


def normalized_forward(a, b, h, p):
    binary = [i for i, v in enumerate(a["vars"]) if v["integer"]]
    current = [expression(0, {i: 1}) for i in range(len(a["vars"]))]
    bits = {i: bit(p, current[i], {"VarLower": i}, {"VarUpper": i}, {"VarInt": i})
            for i in binary}
    old_count = sumexpr(current[i] for i in binary)
    count_eq = p.lin("Eq", [], expression())
    cover = {a["row_index"][name]: row_ref(a, name) for name in h["covering_rows"]}
    cardinality = row_ref(a, h["cardinality_row"])
    stages = []
    count = h["cardinality_limit"]
    assert count == 20
    for stage, removed_name in enumerate(h["removed_binary_variables"]):
        removed = a["var_index"][removed_name]
        candidates = [a["var_index"][name]
                      for name in h["retained_dominator_witnesses"][removed_name]]
        assert len(candidates) == len(set(candidates)) == count
        assert removed not in candidates
        factors = [bits[removed]] + [bits[i] for i in candidates]
        intervals = []
        for j in range(1, count + 1):
            prefix = factors[:j + 1]
            lower = plus(sumexpr(x["expr"] for x in prefix), expression(1 - len(prefix)))
            checks = []
            for is_sum in [False, True]:
                for k, x in enumerate(prefix):
                    wanted = plus(lower if is_sum else expression(), x["expr"], -1)
                    terms = ([[v["upper"], F(1)] for l, v in enumerate(prefix) if l != k]
                             if is_sum else [[x["lower"], F(1)]])
                    checks.append(p.prove("Le", wanted, terms))
            intervals.append({"lower": [expression(), lower],
                              "upper": [x["expr"] for x in prefix], "checks": checks})
        p = lift(p, "intervals", intervals)
        layout = p.old_layout
        prefix_bits = [bits[removed]]
        for j, l in enumerate(layout):
            z = expression(0, {l["variable"]: 1})
            old_factors = factors[:j + 2]
            integer = and_integrality(p, z, l, old_factors)
            upper = p.lin("Le", [[{"RowUpper": l["upper"][0]}, F(1)],
                                 [factors[0]["upper"], F(1)]],
                          plus(z, expression(-1)))
            prefix_bits.append(bit(p, z, {"RowLower": l["lower"][0]}, upper, integer))
        last = prefix_bits[-1]
        subset = {removed, *candidates}
        subset_upper = p.lin("Le", [[cardinality, F(1)]] +
                             [[bits[i]["lower"], F(1)] for i in binary if i not in subset],
                             plus(sumexpr(current[i] for i in subset), expression(-count)))
        scaled = p.lin("Le", [[subset_upper, F(1)]] +
                       [[{"RowUpper": ri}, F(1)] for ri in layout[-1]["upper"]],
                       plus(mul(last["expr"], count + 1), expression(-count)))
        fractional = p.lin("Le", [[scaled, F(1, count + 1)]],
                           plus(last["expr"], expression(F(-count, count + 1))))
        last_round = rounded(p, fractional, last["integer"])
        assert p.refexpr(last_round) == last["expr"], (
            "round result differs from the staged integer expression", stage)
        last_zero = p.eqpair(last_round, last["lower"])
        swap_nonnegative = []
        for j, candidate in enumerate(candidates):
            prev, nxt = prefix_bits[j:j + 2]
            w = bits[candidate]
            difference = plus(nxt["expr"], prev["expr"], -1)
            if j == 0:
                nonnegative = {"RowUpper": layout[j]["upper"][0]}
            else:
                def next_zero(cur, assumption):
                    eq = fixed_bit(cur, nxt, 0, assumption)
                    return {"Witness": cur.lin("Le", [[eq, F(1)],
                                                      [prev["lower"], F(1)]], difference)}

                def next_one(cur, assumption):
                    eq = fixed_bit(cur, nxt, 1, assumption)
                    fixed = factors_one(cur, eq, layout[j], factors[:j + 2])
                    terms = [[{"RowLower": layout[j - 1]["lower"][1]}, F(1)]] + \
                            [[r, F(-1)] for r in fixed[:-1]] + [[eq, F(1)]]
                    return {"Witness": cur.lin("Le", terms, difference)}

                descriptor = nxt
                nonnegative = p.cases("Le", difference, descriptor["expr"],
                                      descriptor["integer"], next_zero, next_one)
            swap_nonnegative.append(nonnegative)
            updated = plus(w["expr"], difference, -1)
            wanted = plus(updated, expression(-1))

            def w_zero(cur, assumption):
                weq = fixed_bit(cur, w, 0, assumption)
                nupper = cur.lin("Le", [[{"RowUpper": layout[j]["upper"][-1]}, F(1)],
                                        [weq, F(1)]], nxt["expr"])
                neq = cur.eqpair(nupper, nxt["lower"])
                return {"Witness": cur.lin("Le", [[prev["upper"], F(1)], [weq, F(1)],
                                                  [neq, F(-1)]], wanted)}

            def w_one(cur, assumption):
                weq = fixed_bit(cur, w, 1, assumption)

                def p_zero(child, guard):
                    peq = fixed_bit(child, prev, 0, guard)
                    return {"Witness": child.lin("Le", [[weq, F(1)], [peq, F(1)],
                                                       [nxt["lower"], F(1)]], wanted)}

                def p_one(child, guard):
                    peq = fixed_bit(child, prev, 1, guard)
                    fixed = [peq] if j == 0 else factors_one(child, peq, layout[j - 1],
                                                             factors[:j + 1])
                    lower = child.lin("Le", [[{"RowLower": layout[j]["lower"][1]}, F(1)]] +
                                       [[r, F(-1)] for r in fixed] + [[weq, F(-1)]],
                                       plus(expression(1), nxt["expr"], -1))
                    return {"Witness": child.lin("Le", [[lower, F(1)], [peq, F(1)],
                                                        [weq, F(1)]], wanted)}

                return {"Witness": cur.cases("Le", wanted, prev["expr"],
                                             prev["integer"], p_zero, p_one)}

            upper = p.cases("Le", wanted, w["expr"], w["integer"], w_zero, w_one)
            lower = p.lin("Le", [[w["lower"], F(1)], [nonnegative, F(1)]],
                          mul(updated, -1))
            integer = p.lin("Int", [[w["integer"], F(1)], [prev["integer"], F(1)],
                                    [nxt["integer"], F(-1)]], updated)
            current[candidate] = updated
            bits[candidate] = bit(p, updated, lower, upper, integer)
        current[removed] = expression()
        bits[removed] = bit(p, expression(), p.lin("Le", [], expression()),
                            p.lin("Le", [], expression(-1), constant=-1),
                            p.lin("Int", [], expression()))
        count_eq = p.lin("Eq", [[count_eq, F(1)], [last_zero, F(-1)]],
                         plus(sumexpr(current[i] for i in binary), old_count, -1))
        cardinality = p.lin("Le", [[row_ref(a, h["cardinality_row"]), F(1)],
                                   [count_eq, F(1)]],
                            plus(sumexpr(current[i] for i in binary), expression(-count)))
        for ri, old_ref in list(cover.items()):
            row = a["rows"][ri]
            av = row["terms"].get(removed, F(0))
            terms = [[old_ref, F(1)], [last_zero, av]]
            for candidate, ref in zip(candidates, swap_nonnegative):
                delta = row["terms"].get(candidate, F(0)) - av
                assert delta >= 0
                if delta:
                    terms.append([ref, delta])
            terms = [(ref, c) for ref, c in terms if c]
            wanted = substitute(row_fact(row, "RowLower"), current)
            cover[ri] = p.lin("Le", terms, wanted)
        stages.append({"intervals": len(intervals), "rows": len(layout)})
    group_members = h["aggregated_binary_groups"]
    mapping = []
    domains = {}
    source_y = a["var_index"]["x151"]
    for oi, var in enumerate(b["vars"]):
        ids = ([a["var_index"][name] for name in group_members[var["name"]]]
               if var["name"] in group_members else [a["var_index"][var["name"]]])
        mapping.append(sumexpr(current[i] for i in ids))
        if ids == [source_y]:
            continue
        for typ, key in [("VarLower", "lower"), ("VarUpper", "upper"),
                         ("VarInt", "integer")]:
            kind = "Int" if typ == "VarInt" else "Le"
            expected = (mapping[-1] if kind == "Int"
                        else mul(mapping[-1], -1) if typ == "VarLower"
                        else plus(mapping[-1], expression(-len(ids))))
            domains[(oi, typ)] = p.lin(kind, [[bits[i][key], F(1)] for i in ids],
                                       expected)
    rows = {b["row_index"][name]: cover[a["row_index"][name]]
            for name in h["covering_rows"]}
    rows[b["row_index"][h["cardinality_row"]]] = cardinality
    objective = p.lin("Eq", [[count_eq, F("0.00001")]],
                      plus(substitute(b["objective"], mapping), a["objective"], -1))
    p.add("Eq", count_eq)
    checks = emit_checks(p, b, mapping, "Eq", rows=rows, domains=domains,
                         objective=objective)
    p.finish(mapping, checks)
    return {"stages": len(stages), "intervals": sum(s["intervals"] for s in stages),
            "interval_rows": sum(s["rows"] for s in stages),
            "allocated_ids": p.counter[0], "obligations": len(checks)}


def reverse_aggregation(a, b, h, pre):
    menus = []
    groups = {}
    for name, names in h["aggregated_binary_groups"].items():
        target = b["var_index"][name]
        upper = {"VarUpper": target}
        menus.append({"maximum_index": 2,
                      "activation": expression(1),
                      "index": expression(0, {target: 1}),
                      "checks": ["Exact", "Exact", "Exact",
                                 {"VarLower": target}, upper, "Exact"]})
        groups[name] = {"index": len(menus) - 1, "target": target, "name": name}
    p = lift(pre, "menus", menus)
    layouts = p.old_layout
    for name, g in groups.items():
        layout = layouts[g["index"]]
        g["start"] = layout["options"][0]
        g["sum"] = {"RowEq": layout["sum_row"]}
        g["moment"] = {"RowEq": layout["moment_row"]}
    mapping = []
    domains = {}
    removed = set(h["removed_binary_variables"])
    member = {n: (g, j) for g in groups.values() for j, n in enumerate(h["aggregated_binary_groups"][g["name"]])}
    for i, var in enumerate(a["vars"]):
        name = var["name"]
        if name in removed:
            mapping.append(expression())
        elif name in member:
            g, j = member[name]
            s = g["start"]
            mapping.append(expression(0, {s + 1: F(1), s + 2: F(1)}) if j == 0
                           else expression(0, {s + 2: F(1)}))
            if j == 0:
                domains[(i, "VarLower")] = p.lin(
                    "Le", [[{"VarLower": s + 1}, F(1)], [{"VarLower": s + 2}, F(1)]],
                    mul(mapping[-1], -1))
                domains[(i, "VarUpper")] = p.lin(
                    "Le", [[g["sum"], F(1)], [{"VarLower": s}, F(1)]],
                    plus(mapping[-1], expression(-1)))
        else:
            mapping.append(expression(0, {b["var_index"][name]: F(1)}))
    rows = {}
    for i, row in enumerate(a["rows"]):
        typ = next(iter(row_ref(a, row["name"])))
        raw = row_fact(row, typ)
        wanted = substitute(raw, mapping)
        terms = [[row_ref(b, row["name"]), F(1)]]
        for g in groups.values():
            names = h["aggregated_binary_groups"][g["name"]]
            coefficient = raw[1].get(a["var_index"][names[0]], F(0))
            assert coefficient == raw[1].get(a["var_index"][names[1]], F(0))
            if coefficient:
                terms.append([g["moment"], coefficient])
        rows[i] = p.lin("Le" if typ != "RowEq" else "Eq", terms, wanted)
    objective = p.lin("Eq", [[g["moment"], F("0.00001")] for g in groups.values()],
                      plus(substitute(a["objective"], mapping), b["objective"], -1))
    count = p.lin("Eq", [[g["moment"], F(1)] for g in groups.values()],
                  plus(sumexpr(mapping[i] for i, v in enumerate(a["vars"]) if v["integer"]),
                       sumexpr(expression(0, {i: F(1)}) for i, v in enumerate(b["vars"])
                              if v["integer"]), -1))
    p.add("Eq", count)
    checks = emit_checks(p, a, mapping, "Eq", rows=rows, domains=domains,
                         objective=objective)
    p.finish(mapping, checks)
    return {"menus": len(menus), "allocated_ids": p.counter[0],
            "obligations": len(checks)}


def prepare(a, b, h):
    proof, f, r = make_proof(a, b)
    forward = normalized_forward(a, b, h, f)
    reverse = reverse_aggregation(a, b, h, r)
    counts = {"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
              "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
              "claims": 2,
              "stages": forward["stages"], "intervals": forward["intervals"],
              "interval_rows": forward["interval_rows"],
              "menus": reverse["menus"],
              "obligations_by_claim": [forward["obligations"], reverse["obligations"]],
              "allocated_ids": [forward["allocated_ids"], reverse["allocated_ids"]]}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test47-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test47"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test47", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test47", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
