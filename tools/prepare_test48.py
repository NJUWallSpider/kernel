#!/usr/bin/env python3
"""Exact native proof of actual test48 conditional-simplex normalization.

All old variables/rows/bounds/objectives are checked. Local priority choices are
joint real interval extensions; their integrality and cost bound follow only
from ordinary exhaustive binary Cases. The legacy four-claim layout collapses
to the two native MI-OPT directions; no production theorem is added.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref, get_fact
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha, signature
from prepare_native import (compile_case, is_exact, legacy_expr,
                            legacy_from_native, make_proof)


def sumexpr(es):
    result = expression()
    for e in es:
        result = plus(result, e)
    return result


def lift(builder, kind, entries):
    """Install a native lift and expose the extended legacy model view."""
    child = getattr(builder, kind)(entries)
    child.model = legacy_from_native(child.scope.model)
    return child


def rounded(p, le, integer):
    a, z = p.refexpr(le), p.refexpr(integer)
    assert p.kind(le) == "Le" and p.kind(integer) == "Int" and a[1] == z[1]
    d = a[0] - z[0]
    ceil = -((-d.numerator) // d.denominator)
    fact = p.round(le, integer)
    assert p.refexpr(fact) == (z[0] + ceil, z[1])
    return fact


def fixed_bit(p, bit, value, assumption):
    if value == 0:
        return p.eqpair(assumption, bit["lower"])
    return p.eqpair(bit["upper"], assumption)


def boolean_expr(p, e, lower=None, upper=None):
    if not e[1]:
        assert e[0] in (0, 1)
        return {"expr": e, "value": e[0]}
    lo = p.prove("Le", mul(e, -1), lower)
    hi = p.prove("Le", plus(e, expression(-1)), upper)
    terms = [[{"VarInt": i}, c] for i, c in e[1].items()]
    integer = p.lin("Int", terms, e, constant=e[0])
    return {"expr": e, "lower": lo, "upper": hi, "integer": integer}


def case_all(p, kind, wanted, bits, leaf):
    variable = []
    assigned = {}
    for bit in bits:
        key = signature(bit["expr"])
        if "value" in bit:
            assigned[key] = (bit["value"], None)
        elif key not in [signature(x["expr"]) for x in variable]:
            variable.append(bit)

    def recurse(cur, index, state):
        if index == len(variable):
            return {"Witness": leaf(cur, state)}
        bit = variable[index]
        key = signature(bit["expr"])

        def branch(child, assumption, value):
            return recurse(child, index + 1,
                           {**state, key: (F(value), fixed_bit(child, bit, value, assumption))})

        ref = cur.cases(kind, wanted, bit["expr"], bit.get("integer"),
                        lambda child, a: branch(child, a, 0),
                        lambda child, a: branch(child, a, 1))
        return {"Witness": ref}

    return recurse(p, 0, assigned)["Witness"]


def int_witness(p, e, ref=None):
    if not e[1]:
        assert e[0].denominator == 1
        return "Exact"
    if ref and ref != "Exact":
        fact = p.ref(ref)
        assert fact.kind == "Int" and legacy_expr(fact.expression) == e, (
            "integer witness mismatch", e, fact)
        return ref
    terms = []
    for i, c in e[1].items():
        variable = p.model["vars"][i]
        assert variable["integer"] and c.denominator == 1, (
            "no integer witness", e, variable)
        terms.append([{"VarInt": i}, c])
    return p.lin("Int", terms, e)


def emit_checks(p, output, mapping, objective_kind="Le", rows=None, domains=None,
                objective=None):
    checks = []
    def terms(ref):
        if ref is None or ref == "Exact":
            return None
        return ref if isinstance(ref, list) else [[ref, F(1)]]
    for i, v in enumerate(output["vars"]):
        for typ, side, sign in [("VarLower", "lower", -1), ("VarUpper", "upper", 1)]:
            if v[side] is None:
                continue
            wanted = plus(mul(mapping[i], sign), expression(-sign * v[side]))
            ref = (domains or {}).get((i, typ))
            checks.append(p.prove("Le", wanted, terms(ref)))
        if v["integer"]:
            ref = (domains or {}).get((i, "VarInt"))
            checks.append(int_witness(p, mapping[i], ref))
    for i, row in enumerate(output["rows"]):
        typ = next(iter(row_ref(output, row["name"])))
        wanted = substitute(row_fact(row, typ), mapping)
        ref = (rows or {}).get(i)
        checks.append(p.prove("Eq" if typ == "RowEq" else "Le", wanted, terms(ref)))
    wanted = plus(substitute(output["objective"], mapping), p.model["objective"], -1)
    checks.append(p.prove(objective_kind, wanted, terms(objective)))
    return checks


def eliminate(builder, ref, removed, kind=None):
    raw = builder.refexpr(ref)
    terms = [[ref, F(1)]]
    for i, c in list(raw[1].items()):
        if i in removed:
            terms.append([removed[i], -c])
    return builder.lin(kind or builder.kind(ref), terms)


def source_elimination(a, b, h, f):
    alias = {}
    for name, root in h["copy_substitutions"].items():
        i, j = a["var_index"][name], a["var_index"][root]
        wanted = expression(0, {i: 1, j: -1})
        alias[i] = f.prove("Eq", wanted)
    fixed = {}
    for name, hint in h["fixed_zero_representatives"].items():
        if hint["kind"] != "original_bound_or_equality":
            continue
        i = a["var_index"][name]
        original = hint["original_fixed"][0]
        j = a["var_index"][original]
        assert a["vars"][j]["lower"] == a["vars"][j]["upper"] == 0
        eq = f.eqpair({"VarUpper": j}, {"VarLower": j})
        if i != j:
            eq = f.lin("Eq", [[eq, F(1)], [alias[j], F(-1)]], expression(0, {i: 1}))
        fixed[i] = eq
    for name, hint in h["fixed_zero_representatives"].items():
        if hint["kind"] != "zero_parent":
            continue
        i = a["var_index"][name]
        j = a["var_index"][hint["parent"]]
        upper = f.lin("Le", [[row_ref(a, hint["implication_row"]), F(1)],
                             [fixed[j], F(1)]], expression(0, {i: 1}))
        fixed[i] = f.eqpair(upper, {"VarLower": i})
    removed = dict(fixed)
    for i, ref in alias.items():
        root = h["copy_substitutions"][a["vars"][i]["name"]]
        j = a["var_index"][root]
        removed[i] = (f.lin("Eq", [[ref, F(1)], [fixed[j], F(1)]], expression(0, {i: 1}))
                      if j in fixed else ref)
    d = a["var_index"][h["free_variable_substitution"]["column"]]
    ref = row_ref(a, "R0001936")
    scale = 1 / f.refexpr(ref)[1][d]
    terms = [[ref, scale]]
    for i, c in f.refexpr(ref)[1].items():
        if i in removed:
            terms.append([removed[i], -c * scale])
    removed[d] = f.lin("Eq", terms)
    assert len(removed) == len(a["vars"]) - len(b["vars"])
    forward = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    reverse = []
    for i, v in enumerate(a["vars"]):
        if v["name"] in b["var_index"]:
            reverse.append(expression(0, {b["var_index"][v["name"]]: 1}))
            continue
        eq = f.refexpr(removed[i])
        assert eq[1][i] == 1
        back = plus(expression(0, {i: 1}), eq, -1)
        assert all(a["vars"][j]["name"] in b["var_index"] for j in back[1])
        reverse.append(expression(back[0], {b["var_index"][a["vars"][j]["name"]]: c
                                            for j, c in back[1].items()}))
        assert plus(expression(0, {i: 1}), substitute(reverse[-1], forward), -1) == eq
    return removed, forward, reverse


def linear_blocks(a, b, h, f):
    removed, forward, reverse = source_elimination(a, b, h, f)
    frows = {}
    for i, row in enumerate(b["rows"]):
        ref = row_ref(a, row["name"])
        desired = substitute(row_fact(row, next(iter(row_ref(b, row["name"])))), forward)
        terms = [[ref, F(1)]]
        for j, c in f.refexpr(ref)[1].items():
            if j in removed:
                terms.append([removed[j], -c])
        frows[i] = f.lin("Eq" if row["sense"] == "E" else "Le", terms, desired)
    for ref in removed.values():
        f.add("Eq", ref)
    domains = {}
    for i, v in enumerate(b["vars"]):
        j = a["var_index"][v["name"]]
        if forward[i] != expression(0, {j: 1}):
            continue
        if v["lower"] is not None:
            domains[(i, "VarLower")] = {"VarLower": j}
        if v["upper"] is not None:
            domains[(i, "VarUpper")] = {"VarUpper": j}
        if v["integer"]:
            domains[(i, "VarInt")] = {"VarInt": j}
    checks = emit_checks(f, b, forward, "Eq", rows=frows, domains=domains)
    f.finish(forward, checks)
    return forward, reverse, len(checks)


def normalize_reverse(a, b, h, claim, reverse, pre):
    intervals = []
    groups = []

    def target_expr(name):
        return expression(0, {b["var_index"][name]: 1}) if name in b["var_index"] else expression()

    for block in h["local_block_certificates"]:
        children = sorted(block["optional_children"],
                          key=lambda x: F(x["objective_coefficient_after_deficit_elimination"]))
        current = [x for x in children if not x["fixed_zero"]]
        mandatory = sumexpr(target_expr(name) for name in block["mandatory_selectors"])
        residual = plus(expression(1), mandatory, -1)
        old_children = sumexpr(target_expr(x["column"]) for x in current)
        capacity = plus(old_children, residual, -1)
        cap = pre.prove("Le", capacity)
        r = boolean_expr(pre, residual, [[cap, F(1)]] +
                         [[{"VarLower": b["var_index"][x["column"]]}, F(1)] for x in current])
        eligible = [boolean_expr(pre, target_expr(x["selector"])) for x in current]
        g = {"hint": block, "children": current, "r": r, "eligible": eligible,
             "capacity": cap, "interval_ids": []}
        for j, x in enumerate(current):
            bits = [r["expr"], eligible[j]["expr"]] + \
                   [plus(expression(1), y["expr"], -1) for y in eligible[:j]]
            low = plus(sumexpr(bits), expression(1 - len(bits)))
            checks = []
            for lower in [expression(), low]:
                for k, upper in enumerate(bits):
                    expected = plus(lower, upper, -1)
                    if lower == expression():
                        if k == 0:
                            terms = [[r["lower"], F(1)]] if "lower" in r else []
                        elif k == 1:
                            terms = [[eligible[j]["lower"], F(1)]] if "lower" in eligible[j] else []
                        else:
                            terms = ([[eligible[k - 2]["upper"], F(1)]]
                                     if "upper" in eligible[k - 2] else [])
                    else:
                        terms = []
                        for l, bit in enumerate(bits):
                            if l == k:
                                continue
                            desc = r if l == 0 else eligible[j] if l == 1 else eligible[l - 2]
                            key = "upper" if l < 2 else "lower"
                            if key in desc:
                                terms.append([desc[key], F(1)])
                    computed = sumexpr(pre.refexpr(ref) for ref, c in terms)
                    slack = plus(expected, computed, -1)
                    assert not slack[1] and slack[0] <= 0
                    checks.append(pre.prove("Le", expected, terms, constant=slack[0]))
            g["interval_ids"].append(len(intervals))
            intervals.append({"lower": [expression(), low],
                              "upper": list(bits), "checks": checks})
        groups.append(g)
    p = lift(pre, "intervals", intervals)
    layout = p.old_layout
    mapping = [expression(F(e[0]), dict(e[1])) for e in reverse]
    domains = {}
    rowproofs = {}
    costfacts = []
    for group in groups:
        children = group["children"]
        r = group["r"]
        eligible = group["eligible"]
        layouts = [layout[k] for k in group["interval_ids"]]
        z = [expression(0, {l["variable"]: 1}) for l in layouts]
        allbits = [r] + eligible

        def z_fixed(cur, state):
            rr = state[signature(r["expr"])][0]
            ys = [state[signature(bit["expr"])][0] for bit in eligible]
            result = []
            for j, l in enumerate(layouts):
                descriptors = [(r, False), (eligible[j], False)] + \
                              [(bit, True) for bit in eligible[:j]]
                vals = []
                eqs = []
                for bit, negated in descriptors:
                    val, ref = state[signature(bit["expr"])]
                    vals.append(1 - val if negated else val)
                    if ref is not None:
                        eqs.append([ref, F(-1 if negated else 1)])
                chosen = int(all(vals))
                if chosen:
                    lower = cur.lin("Le", [[{"RowLower": l["lower"][1]}, F(1)]] +
                                    [[ref, -c] for ref, c in eqs],
                                    plus(expression(1), z[j], -1))
                    upper = cur.lin("Le", [[{"RowUpper": l["upper"][0]}, F(1)]] +
                                    ([[state[signature(r["expr"])][1], F(1)]]
                                     if state[signature(r["expr"])][1] else []),
                                    plus(z[j], expression(-1)))
                else:
                    k = vals.index(0)
                    bit, negated = descriptors[k]
                    ref = state[signature(bit["expr"])][1]
                    upper = cur.lin("Le", [[{"RowUpper": l["upper"][k]}, F(1)]] +
                                    ([[ref, F(-1 if negated else 1)]] if ref else []), z[j])
                    lower = {"RowLower": l["lower"][0]}
                result.append((F(chosen), cur.eqpair(upper, lower)))
            return rr, ys, result

        for j, (x, l) in enumerate(zip(children, layouts)):
            source_index = a["var_index"][x["column"]]
            mapping[source_index] = z[j]
            domains[(source_index, "VarLower")] = {"RowLower": l["lower"][0]}
            domains[(source_index, "VarUpper")] = p.prove(
                "Le", plus(z[j], expression(-1)),
                [[{"RowUpper": l["upper"][0]}, F(1)]] +
                ([[r["upper"], F(1)]] if "upper" in r else []))

            def integral_leaf(cur, state, j=j):
                _, _, values = z_fixed(cur, state)
                val, eq = values[j]
                return cur.lin("Int", [[eq, F(1)]], z[j], constant=val)

            domains[(source_index, "VarInt")] = case_all(p, "Int", z[j], allbits,
                                                         integral_leaf)
            rowproofs[a["row_index"][x["link_row"]]] = {"RowUpper": l["upper"][1]}
        wanted = plus(sumexpr(z), r["expr"], -1)

        def packing_leaf(cur, state):
            rv, _, values = z_fixed(cur, state)
            terms = [[ref, F(1)] for _, ref in values]
            ref = state[signature(r["expr"])][1]
            if ref:
                terms.append([ref, F(-1)])
            return cur.lin("Le", terms, wanted,
                           constant=sum(val for val, _ in values) - rv)

        rowproofs[a["row_index"][group["hint"]["row"]]] = (
            case_all(p, "Le", wanted, allbits, packing_leaf) if children
            else p.prove("Le", wanted))
        costs = [F(x["objective_coefficient_after_deficit_elimination"]) for x in children]
        wanted_cost = plus(sumexpr(mul(zz, c) for zz, c in zip(z, costs)),
                           sumexpr(mul(expression(0, {b["var_index"][x["column"]]: 1}), c)
                                   for x, c in zip(children, costs)), -1)

        def cost_leaf(cur, state):
            rv, ys, values = z_fixed(cur, state)
            selected = [j for j, (val, _) in enumerate(values) if val]
            cstar = costs[selected[0]] if selected else min(costs) if rv == 0 and costs else F(0)
            terms = [[group["capacity"], -cstar]] if cstar else []
            for j, (x, c) in enumerate(zip(children, costs)):
                vi = b["var_index"][x["column"]]
                if c >= cstar:
                    terms.append([{"VarLower": vi}, c - cstar])
                else:
                    assert ys[j] == 0
                    selector_eq = state[signature(eligible[j]["expr"])][1]
                    upper = cur.lin("Le", [[row_ref(b, x["link_row"]), F(1)]] +
                                    ([[selector_eq, F(1)]] if selector_eq else []),
                                    expression(0, {vi: 1}))
                    zero = cur.eqpair(upper, {"VarLower": vi})
                    terms.append([zero, cstar - c])
            residual_eq = state[signature(r["expr"])][1]
            if residual_eq and cstar:
                terms.append([residual_eq, -cstar])
            terms += [[ref, c] for (_, ref), c in zip(values, costs)]
            terms = [(ref, c) for ref, c in terms if c]
            return cur.lin("Le", terms, wanted_cost)

        costfacts.append(case_all(p, "Le", wanted_cost, allbits, cost_leaf)
                         if children else "Exact")
    # Restore removed copies/fixed values, and both complete free coordinates.
    d = a["var_index"][h["free_variable_substitution"]["column"]]
    child_ids = [a["var_index"][x["column"]] for g in h["local_block_certificates"]
                 for x in g["optional_children"]]
    mapping[d] = plus(expression(475), sumexpr(mapping[i] for i in child_ids), -1)
    objective_index = a["var_index"]["C0001746"]
    row = a["rows"][a["row_index"]["R0002107"]]
    pivot = row["terms"][objective_index]
    assert pivot == 1
    mapping[objective_index] = mul(
        substitute(plus(expression(row["rhs"]),
                        expression(0, {i: c for i, c in row["terms"].items()
                                       if i != objective_index}), -1), mapping), 1 / pivot)
    obj_wanted = plus(substitute(a["objective"], mapping), b["objective"], -1)
    objective = p.lin("Le", [[ref, F(1)] for ref in costfacts if ref != "Exact"] +
                      [[row_ref(b, "R0002107"), F(-1)]], obj_wanted)
    # Direct retained coordinates and unchanged rows are already base facts;
    # supplying them avoids a full local-fact search per obligation.
    for i, v in enumerate(a["vars"]):
        name = v["name"]
        if any((i, typ) in domains for typ in ("VarLower", "VarUpper", "VarInt")):
            continue
        if name not in b["var_index"]:
            continue
        j = b["var_index"][name]
        if mapping[i] != expression(0, {j: 1}):
            continue
        if v["lower"] is not None:
            domains[(i, "VarLower")] = {"VarLower": j}
        if v["upper"] is not None:
            domains[(i, "VarUpper")] = {"VarUpper": j}
        if v["integer"]:
            domains[(i, "VarInt")] = {"VarInt": j}
    for i, row in enumerate(a["rows"]):
        if i in rowproofs:
            continue
        name = row["name"]
        typ = next(iter(row_ref(a, name)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), mapping)
        if is_exact(kind, wanted):
            rowproofs[i] = "Exact"
        elif name in b["row_index"]:
            bt = next(iter(row_ref(b, name)))
            if (bt == typ or (kind == "Le" and bt == "RowUpper")) and \
                    row_fact(b["rows"][b["row_index"][name]], bt) == wanted:
                rowproofs[i] = row_ref(b, name)
    checks = emit_checks(p, a, mapping, "Le", rows=rowproofs, domains=domains,
                         objective=objective)
    p.finish(mapping, checks)
    interval_rows = sum(len(l["lower"]) + len(l["upper"]) for l in layout)
    return {"intervals": len(intervals), "interval_rows": interval_rows,
            "body_obligations": len(checks), "allocated_ids": p.counter[0]}


def prepare(a, b, h):
    retained = h["retained_binary_columns"]
    deleted = [v for v in h["fixed_zero_representatives"]
               if v not in {x["column"] for g in h["local_block_certificates"]
                            for x in g["optional_children"]}]
    assert len(retained) == 144 and len(deleted) == 6
    proof, f, r = make_proof(a, b)
    forward, reverse, forward_obligations = linear_blocks(a, b, h, f)
    counts = normalize_reverse(a, b, h, None, reverse, r)
    return proof, {"source_variables": len(a["vars"]),
                   "target_variables": len(b["vars"]),
                   "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
                   "claims": 2, "retained_selector_projections": 144,
                   "fixed_selector_affine_observations": 6,
                   "local_blocks": len(h["local_block_certificates"]),
                   "obligations_by_claim": [forward_obligations,
                                            counts["body_obligations"]],
                   **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test48-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test48"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test48", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test48", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
