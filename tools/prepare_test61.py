#!/usr/bin/env python3
"""Native test61 Boolean projection and continuous interval completion.

The legacy LP image and bijection claims are not part of the two-direction
MI-OPT contract; both integer directions remain complete.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import itertools
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test88 import fix_binary
from prepare_test48 import (emit_checks, int_witness, lift, rounded, sumexpr)
from prepare_native import compile_case, make_proof


def key(e):
    return tuple(sorted(e[1].items()))


def normalize(e):
    if not e[1]:
        return e, F(1)
    scale = abs(next(c for i, c in sorted(e[1].items())))
    return mul(e, 1 / scale), scale


def dedup(es):
    result = {}
    for e in es:
        e, _ = normalize(e)
        k = key(e)
        if k not in result or e[0] > result[k][0]:
            result[k] = e
    return list(result.values())


def cases(p, kind, wanted, variables, leaf):
    def recurse(q, ids, assigned):
        if not ids:
            return leaf(q, assigned)
        v = ids[0]
        split = expression(0, {v: 1})

        def left(child, assumption):
            fixed = fix_binary(child, v, 0, assumption)
            return recurse(child, ids[1:], {**assigned, v: (F(0), fixed)})

        def right(child, assumption):
            fixed = fix_binary(child, v, 1, assumption)
            return recurse(child, ids[1:], {**assigned, v: (F(1), fixed)})

        ref = q.cases(kind, wanted, split, {"VarInt": v}, left, right)
        return {"Witness": ref}

    return recurse(p, variables, {})


def fixed_expr(p, e, assigned, kind="Le"):
    value = e[0] + sum(c * assigned[i][0] for i, c in e[1].items())
    assert kind != "Eq" or value == 0
    assert kind != "Le" or value <= 0, (e, value)
    terms = [[assigned[i][1], c] for i, c in e[1].items() if c]
    return p.lin(kind, terms, e, constant=value)


def reduced(p, ref, assigned):
    e = p.refexpr(ref)
    assert set(e[1]) <= set(assigned)
    return p.lin(p.kind(ref), [[ref, F(1)]] +
                 [[assigned[i][1], -c] for i, c in e[1].items() if c])


def reduce_ref(p, ref, assigned):
    e = p.refexpr(ref)
    return p.lin(p.kind(ref), [[ref, F(1)]] +
                 [[assigned[i][1], -c] for i, c in e[1].items() if i in assigned])


def reduce_value(p, ref, assigned):
    e = p.refexpr(ref)
    return expression(e[0] + sum(c * assigned[i][0] for i, c in e[1].items()
                                 if i in assigned),
                      {i: c for i, c in e[1].items() if i not in assigned})


def source_pattern(p, a, d, name, assigned, voffset=0, rowoffset=0):
    v = a["var_index"][name] + voffset
    if name in d["fixed_zero_terms"]:
        rn = next(r["name"] for r in a["rows"]
                  if r["sense"] == "E" and set(r["terms"]) == {a["var_index"][name]})
        ref = {"RowEq": a["row_index"][rn] + rowoffset}
        assert p.refexpr(ref) == expression(0, {v: 1})
        return F(0), ref
    term = d["active_terms"][name]
    value = F(all(assigned[a["var_index"][vn] + voffset][0] ==
                  (1 if F(sign) > 0 else 0)
                  for vn, sign in term["inputs"].items()))
    refs = []
    for rn in term["rows"]:
        ref = row_ref(a, rn)
        typ, ri = next(iter(ref.items()))
        refs.append(reduce_ref(p, {typ: ri + rowoffset}, assigned))
    if value:
        lower = next(r for r in refs if p.refexpr(r)[1].get(v) == -1)
        assert p.refexpr(lower) == expression(1, {v: -1})
        upper = {"VarUpper": v}
    else:
        upper = next(r for r in refs if p.refexpr(r)[1].get(v) == 1)
        upper = rounded(p, upper, {"VarInt": v})
        assert p.refexpr(upper) == expression(0, {v: 1})
        lower = {"VarLower": v}
    return value, p.eqpair(upper, lower)


def target_local_refs(b, h):
    out = {root: [] for root in h["blocks"]}
    for d in h["all_facet_translation_records"]:
        if d["generated_row"] is not None:
            out[d["root"]].append(row_ref(b, d["generated_row"]))
    return out


def solve_columns(columns, goal):
    if not columns:
        return None
    width = len(columns)
    matrix = [[columns[j][i] for j in range(width)] + [goal[i]]
              for i in range(len(goal))]
    pivot = 0
    for j in range(width):
        row = next((i for i in range(pivot, len(matrix)) if matrix[i][j]), None)
        if row is None:
            return None
        matrix[pivot], matrix[row] = matrix[row], matrix[pivot]
        scale = matrix[pivot][j]
        matrix[pivot] = [x / scale for x in matrix[pivot]]
        for i in range(len(matrix)):
            if i != pivot and matrix[i][j]:
                scale = matrix[i][j]
                matrix[i] = [a - scale * b for a, b in zip(matrix[i], matrix[pivot])]
        pivot += 1
    if any(not any(row[:-1]) and row[-1] for row in matrix):
        return None
    return [matrix[j][-1] for j in range(width)]


class Dual:
    def __init__(self):
        self.cache = {}
        self.calls = 0

    def prove(self, p, e, refs):
        if not e[1] and e[0] <= 0:
            return "Exact"
        if all(p.model["vars"][i]["lower"] is not None and
               p.model["vars"][i]["upper"] is not None for i in e[1]):
            maximum = e[0] + sum(c * p.model["vars"][i]["upper" if c > 0 else "lower"]
                                 for i, c in e[1].items())
            if maximum <= 0:
                terms = [[{"VarUpper" if c > 0 else "VarLower": i}, abs(c)]
                         for i, c in e[1].items()]
                return p.lin("Le", terms, e, constant=maximum)
        facts = [p.refexpr(r) for r in refs]
        coords = sorted(set(e[1]) | {i for f in facts for i in f[1]})
        pos = {i: j for j, i in enumerate(coords)}
        cachekey = (tuple((p.kind(r), f[0], tuple((pos[i], c)
                                                  for i, c in sorted(f[1].items())))
                          for r, f in zip(refs, facts)),
                    e[0], tuple((pos[i], c) for i, c in sorted(e[1].items())))
        if cachekey in self.cache:
            mult, constant = self.cache[cachekey]
        else:
            columns = [[f[1].get(i, F(0)) for i in coords] for f in facts]
            goal = [e[1].get(i, F(0)) for i in coords]
            self.calls += 1
            answer = None
            tried = set()
            candidates = []
            for values in itertools.product((F(0), F(1)), repeat=len(coords)):
                activities = [f[0] + sum(c * x for c, x in zip(column, values))
                              for f, column in zip(facts, columns)]
                if all(activity == 0 if p.kind(ref) == "Eq" else activity <= 0
                       for ref, activity in zip(refs, activities)):
                    candidates.append((e[0] + sum(c * x for c, x in zip(goal, values)),
                                       tuple(j for j, activity in enumerate(activities)
                                             if activity == 0)))
            sets = [active for value, active in sorted(candidates, reverse=True)] + \
                   [tuple(range(len(refs)))]
            for active in sets:
                for size in range(1, min(len(coords), len(active)) + 1):
                    for chosen in itertools.combinations(active, size):
                        if chosen in tried:
                            continue
                        tried.add(chosen)
                        coeff = solve_columns([columns[j] for j in chosen], goal)
                        if coeff is None or any(c < 0 and p.kind(refs[j]) != "Eq"
                                                for j, c in zip(chosen, coeff)):
                            continue
                        constant = e[0] - sum(facts[j][0] * c
                                              for j, c in zip(chosen, coeff))
                        if constant > 0:
                            continue
                        mult = [F(0)] * len(refs)
                        for j, c in zip(chosen, coeff):
                            mult[j] = c
                        answer = (mult, constant)
                        break
                    if answer is not None:
                        break
                if answer is not None:
                    break
            assert answer is not None, ("no exact conic certificate", e)
            mult, constant = answer
            self.cache[cachekey] = (mult, constant)
        terms = [(r, c) for r, c in zip(refs, mult) if c]
        return p.lin("Le", terms, e, constant=constant)


def forward(a, b, h, p):
    mapping = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    byrow = {d["generated_row"]: d["root"]
             for d in h["all_facet_translation_records"] if d["generated_row"]}
    domains = {}
    for e in mapping:
        i = next(iter(e[1]))
        domains[i] = {"VarLower": {"VarLower": i}, "VarUpper": {"VarUpper": i},
                      "VarInt": {"VarInt": i}}
    rows = {}
    for i, row in enumerate(b["rows"]):
        root = byrow[row["name"]]
        d = h["blocks"][root]
        typ = "RowEq" if row["sense"] == "E" else "RowUpper"
        wanted = substitute(row_fact(row, typ), mapping)
        kind = "Eq" if typ == "RowEq" else "Le"
        variables = sorted({a["var_index"][v] for v in d["original_inputs"]})

        def leaf(q, assigned, d=d, wanted=wanted, kind=kind):
            assigned = dict(assigned)
            for name in d["original_terms"]:
                assigned[a["var_index"][name]] = source_pattern(q, a, d, name, assigned)
            rv = a["var_index"][root]
            value = F(any(assigned[a["var_index"][vn]][0]
                          for vn in d["original_terms"]))
            if rv not in assigned:
                bound = next(reduce_ref(q, row_ref(a, rn), assigned)
                             for rn in d["original_or_rows"]
                             if q.refexpr(row_ref(a, rn))[1][rv] ==
                             (1 if value == 0 else -1))
                if value:
                    bound = rounded(q, bound,
                                    q.lin("Int", [[{"VarInt": rv}, -1]],
                                          expression(0, {rv: -1})))
                    assert q.refexpr(bound) == expression(1, {rv: -1})
                    eq = q.eqpair({"VarUpper": rv}, bound)
                else:
                    assert q.refexpr(bound) == expression(0, {rv: 1})
                    eq = q.eqpair(bound, {"VarLower": rv})
                assigned[rv] = (value, eq)
            elif assigned[rv][0] != value:
                for rn in d["original_or_rows"]:
                    ref = reduce_ref(q, row_ref(a, rn), assigned)
                    e = q.refexpr(ref)
                    if not e[1] and e[0] > 0:
                        return {"Absurd": ref}
                raise AssertionError("self-dependent source contradiction missing")
            return {"Witness": fixed_expr(q, wanted, assigned, kind)}

        rows[i] = cases(p, kind, wanted, variables, leaf)["Witness"]
    checks = emit_checks(p, b, mapping, "Eq", rows=rows, domains=domains)
    p.finish(mapping, checks)
    return mapping, len(checks)


def integer_reverse(a, b, h, local, p):
    intervals = []
    private = []
    mapping = [expression(0, {b["var_index"][v["name"]]: 1})
               if v["name"] in b["var_index"] else expression() for v in a["vars"]]
    for root, d in h["blocks"].items():
        for name, td in d["active_terms"].items():
            literals = [expression(0, {b["var_index"][vn]: 1}) if F(sign) > 0
                        else expression(1, {b["var_index"][vn]: -1})
                        for vn, sign in td["inputs"].items()]
            total = expression(-2)
            for e in literals:
                total = plus(total, e)
            lower = [expression(), total]
            upper = literals
            checks = []
            for lo in lower:
                for up in upper:
                    e = plus(lo, up, -1)
                    checks.append(p.lin(
                        "Le",
                        [[{"VarUpper" if c > 0 else "VarLower": i}, abs(c)]
                         for i, c in e[1].items()],
                        e, constant=e[0] + sum(max(F(0), c) for c in e[1].values())))
            intervals.append({"lower": lower, "upper": upper, "checks": checks})
            private.append((root, name, lower, upper))
    p = lift(p, "intervals", intervals)
    layouts = p.old_layout
    bounds = {}
    ints = {}
    liftrefs = {}
    for (root, name, lower, upper), layout in zip(private, layouts):
        v = layout["variable"]
        mapping[a["var_index"][name]] = expression(0, {v: 1})
        refs = [{"RowLower": r} for r in layout["lower"]] + \
               [{"RowUpper": r} for r in layout["upper"]]
        liftrefs[name] = (v, refs, lower, upper)

    def fixed_private(q, name, d, assigned):
        if name in d["fixed_zero_terms"]:
            return F(0), None
        v, refs, lo, up = liftrefs[name]
        td = d["active_terms"][name]
        value = F(all(assigned[b["var_index"][vn]][0] ==
                      (1 if F(sign) > 0 else 0)
                      for vn, sign in td["inputs"].items()))
        lower = reduce_ref(q, refs[1] if value else refs[0], assigned)
        upper = next(reduce_ref(q, r, assigned) for r in refs[2:]
                     if reduce_value(q, r, assigned) == expression(-value, {v: 1}))
        assert q.refexpr(lower) == expression(value, {v: -1})
        return value, q.eqpair(upper, lower)

    for root, name, _, _ in private:
        d = h["blocks"][root]
        v = liftrefs[name][0]
        variables = sorted({b["var_index"][vn]
                            for vn in d["active_terms"][name]["inputs"]})
        wanted = expression(0, {v: 1})

        def leaf(q, assigned, name=name, d=d, v=v, wanted=wanted):
            value, ref = fixed_private(q, name, d, assigned)
            if ref is None:
                return {"Witness": q.lin("Int", [], wanted, constant=value)}
            return {"Witness": q.lin("Int", [[ref, 1]], wanted, constant=value)}

        ints[name] = cases(p, "Int", wanted, variables, leaf)["Witness"]

    dual = Dual()
    domains = {}
    rows = {}
    for i, var in enumerate(a["vars"]):
        name = var["name"]
        if name in b["var_index"]:
            v = b["var_index"][name]
            domains[(i, "VarLower")] = {"VarLower": v}
            domains[(i, "VarUpper")] = {"VarUpper": v}
            domains[(i, "VarInt")] = {"VarInt": v}
        elif name not in liftrefs:
            domains[(i, "VarLower")] = "Exact"
            domains[(i, "VarUpper")] = "Exact"
            domains[(i, "VarInt")] = "Exact"
        else:
            v, refs, _, upper = liftrefs[name]
            coords = set().union(*(set(x[1]) for x in upper))
            domains[(i, "VarLower")] = refs[0]
            domains[(i, "VarUpper")] = dual.prove(
                p, plus(mapping[i], expression(-1)),
                refs + [{"VarLower": j} for j in sorted(coords)] +
                [{"VarUpper": j} for j in sorted(coords)])
            domains[(i, "VarInt")] = ints[name]
    orrows = {rn: root for root, d in h["blocks"].items() for rn in d["original_or_rows"]}
    termrows = {rn: name for d in h["blocks"].values()
                for name, td in d["active_terms"].items() for rn in td["rows"]}
    for i, row in enumerate(a["rows"]):
        typ = next(iter(row_ref(a, row["name"])))
        wanted = substitute(row_fact(row, typ), mapping)
        if row["sense"] == "E":
            rows[i] = "Exact"
            continue
        if row["name"] in termrows:
            name = termrows[row["name"]]
            _, refs, _, upper = liftrefs[name]
            coords = set().union(*(set(e[1]) for e in upper))
            rows[i] = dual.prove(p, wanted,
                                 refs + [{"VarLower": j} for j in sorted(coords)] +
                                 [{"VarUpper": j} for j in sorted(coords)])
            continue
        root = orrows[row["name"]]
        d = h["blocks"][root]
        variables = sorted({b["var_index"][vn]
                            for vn in d["original_inputs"] + [root]})

        def leaf(q, assigned, d=d, wanted=wanted, root=root):
            val = {vn: assigned[b["var_index"][vn]][0]
                   for vn in d["original_inputs"]}
            result = any(all(val[vn] == (1 if F(sign) > 0 else 0)
                             for vn, sign in td["inputs"].items())
                         for td in d["active_terms"].values())
            if assigned[b["var_index"][root]][0] != int(result):
                for ref in local[root]:
                    e = q.refexpr(ref)
                    value = e[0] + sum(c * assigned[i][0] for i, c in e[1].items())
                    if value > 0 or q.kind(ref) == "Eq" and value != 0:
                        return {"Absurd": reduce_ref(q, ref, assigned)}
                raise AssertionError(("target local assignment not excluded", root, val))
            assignment = dict(assigned)
            for name in d["active_terms"]:
                v = liftrefs[name][0]
                assignment[v] = fixed_private(q, name, d, assigned)
            return {"Witness": fixed_expr(q, wanted, assignment)}

        rows[i] = cases(p, "Le", wanted, variables, leaf)["Witness"]
    checks = emit_checks(p, a, mapping, "Eq", rows=rows, domains=domains)
    p.finish(mapping, checks)
    return mapping, {"interval_pair_premises": sum(len(i["checks"]) for i in intervals),
                     "obligations": len(checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test61-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test61"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    a = parse_mps(source)
    b = parse_mps(target)
    h = json.loads(audit.read_text())
    local = target_local_refs(b, h)
    proof, f, r = make_proof(a, b)
    forward_map, forward_obligations = forward(a, b, h, f)
    reverse_map, reverse_info = integer_reverse(a, b, h, local, r)
    counts = {"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
              "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
              "claims": 2,
              "obligations_by_claim": [forward_obligations,
                                       reverse_info["obligations"]],
              **reverse_info}
    record = compile_case(proof, args.out, case_id="test61", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test61", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
