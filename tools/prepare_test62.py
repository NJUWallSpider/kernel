#!/usr/bin/env python3
"""Native test62 Boolean projection and interval reconstruction.

The legacy bijection, injectivity and LP image claims are outside the two-tree
MI-OPT contract; both integer directions are complete.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test54 import box
from prepare_test57 import substitute
from prepare_test88 import fix_binary
from prepare_test48 import emit_checks, lift, rounded
from prepare_native import compile_case, make_proof


def cases(p, kind, wanted, variables, leaf, state=None):
    state = {} if state is None else state
    if not variables:
        return leaf(p, state)
    variable = variables[0]
    split = expression(0, {variable: 1})

    def left(child, assumption):
        fixed = fix_binary(child, variable, 0, assumption)
        return cases(child, kind, wanted, variables[1:], leaf,
                     {**state, variable: (F(0), fixed)})

    def right(child, assumption):
        fixed = fix_binary(child, variable, 1, assumption)
        return cases(child, kind, wanted, variables[1:], leaf,
                     {**state, variable: (F(1), fixed)})

    ref = p.cases(kind, wanted, split, {"VarInt": variable}, left, right)
    return {"Witness": ref}


def under(p, kind, wanted, state):
    value = wanted[0] + sum(c * state[i][0] for i, c in wanted[1].items())
    terms = [[state[i][1], c] for i, c in wanted[1].items() if c]
    assert (kind == "Le" and value <= 0) or (kind == "Eq" and value == 0) or \
           (kind == "Int" and value.denominator == 1)
    return p.lin(kind, terms, wanted, constant=value)


def reduced(p, ref, state):
    e = p.refexpr(ref)
    assert set(e[1]) <= set(state)
    return p.lin(p.kind(ref), [[ref, 1]] +
                 [[state[i][1], -c] for i, c in e[1].items() if c])


def source_indicator(p, pattern, state, offset=0, rowoffset=0):
    a = pattern["a"]
    variable = a["var_index"][pattern["aux"]] + offset
    match = all(state[a["var_index"][name] + offset][0] == value
                for name, value in pattern["pattern"].items())
    value = F(int(match))
    refs = []
    for name in pattern["rows"]:
        ref = row_ref(a, name)
        kind, index = next(iter(ref.items()))
        ref = {kind: index + rowoffset}
        e = p.refexpr(ref)
        terms = [[ref, 1]] + [[state[i][1], -c] for i, c in e[1].items()
                              if i != variable]
        bound = p.lin("Le", terms)
        assert set(p.refexpr(bound)[1]) == {variable}
        refs.append(bound)
    lower = next(r for r in refs if p.refexpr(r)[1][variable] == -1)
    upper = next(r for r in refs if p.refexpr(r)[1][variable] == 1)
    if match:
        assert p.refexpr(lower) == expression(1, {variable: -1})
        eq = p.eqpair({"VarUpper": variable}, lower)
    else:
        rounded_upper = rounded(p, upper, {"VarInt": variable})
        assert p.refexpr(rounded_upper) == expression(0, {variable: 1})
        eq = p.eqpair(rounded_upper, {"VarLower": variable})
    assert p.refexpr(eq) == expression(-value, {variable: 1})
    return value, eq


def generated_indicator(p, pattern, state, layout):
    variable = layout["variable"]
    match = all(state[p.model["var_index"][name]][0] == value
                for name, value in pattern["pattern"].items())
    value = F(int(match))
    if match:
        ref = {"RowLower": layout["lower"][1]}
        e = p.refexpr(ref)
        lower = p.lin("Le", [[ref, 1]] +
                      [[state[i][1], -c] for i, c in e[1].items()
                       if i != variable], expression(1, {variable: -1}))
        upper = {"RowUpper": layout["upper"][0]}
        e = p.refexpr(upper)
        upper = p.lin("Le", [[upper, 1]] +
                      [[state[i][1], -c] for i, c in e[1].items()
                       if i != variable], expression(-1, {variable: 1}))
    else:
        index = next(j for j, (name, v) in enumerate(pattern["pattern"].items())
                     if state[p.model["var_index"][name]][0] != v)
        ref = {"RowUpper": layout["upper"][index]}
        e = p.refexpr(ref)
        upper = p.lin("Le", [[ref, 1]] +
                      [[state[i][1], -c] for i, c in e[1].items()
                       if i != variable], expression(0, {variable: 1}))
        lower = {"RowLower": layout["lower"][0]}
    return value, p.eqpair(upper, lower)


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (4500, 7029, 500, 2539)
    assert all(v["integer"] and v["lower"] == 0 and v["upper"] == 1
               for v in a["vars"] + b["vars"])
    forward = [expression(0, {a["var_index"][v["name"]]: 1}) for v in b["vars"]]
    common = [[next(iter(e[1])), j] for j, e in enumerate(forward)]
    assert substitute(b["objective"], forward) == a["objective"]
    patterns = []
    fixed = {}
    groupbyrow = {}
    allrows = []
    for g in h["groups"]:
        for name, row in g["fixed_zero_auxiliaries"].items():
            i = a["var_index"][name]
            ref = row_ref(a, row)
            assert row_fact(a["rows"][ref["RowEq"]], "RowEq") == expression(0, {i: 1})
            fixed[i] = ref
            allrows.append(row)
        for pat in g["active_patterns"]:
            pat = {**pat, "a": a}
            patterns.append(pat)
            allrows += pat["rows"]
            T = expression(sum(1 for v in pat["pattern"].values() if v == 1),
                           {a["var_index"][name]: 1 if v == 0 else -1
                            for name, v in pat["pattern"].items()})
            i = a["var_index"][pat["aux"]]
            refs = {a["rows"][a["row_index"][name]]["sense"]:
                    row_fact(a["rows"][a["row_index"][name]],
                             "RowLower" if a["rows"][a["row_index"][name]]["sense"] == "G"
                             else "RowUpper") for name in pat["rows"]}
            assert refs["G"] == plus(expression(1, {i: -1}), T, -1)
            assert refs["L"] == plus(expression(F(-1099, 1000), {i: 1}), T,
                                     F(333, 1000))
        allrows += g["original_or_rows"]
        for name in g["replacement_rows"]:
            assert name not in groupbyrow
            groupbyrow[name] = g
    assert len(allrows) == len(set(allrows)) == 7029
    assert set(allrows) == set(a["row_index"]) and set(groupbyrow) == set(b["row_index"])
    patbyname = {pat["aux"]: pat for pat in patterns}

    def completed_source(p, g, state):
        result = dict(state)
        for name in g["auxiliary_variables"]:
            i = a["var_index"][name]
            result[i] = (F(0), fixed[i]) if i in fixed else source_indicator(p, patbyname[name], state)
        return result

    proof, f, r = make_proof(a, b)
    fdomains = {}
    for i, j in common:
        fdomains[i] = {"VarLower": {"VarLower": i}, "VarUpper": {"VarUpper": i},
                       "VarInt": {"VarInt": i}}
    frows = {}
    for i, row in enumerate(b["rows"]):
        g = groupbyrow[row["name"]]
        wanted = substitute(row_fact(row, "RowLower"), forward)
        variables = [a["var_index"][name] for name in g["relation_variables"]]

        def leaf(p, state, g=g, wanted=wanted):
            value = wanted[0] + sum(c * state[i][0] for i, c in wanted[1].items())
            if value <= 0:
                return {"Witness": under(p, "Le", wanted, state)}
            full = completed_source(p, g, state)
            for name in g["original_or_rows"]:
                ref = row_ref(a, name)
                e = p.refexpr(ref)
                v = e[0] + sum(c * full[i][0] for i, c in e[1].items())
                if v > 0:
                    return {"Absurd": reduced(p, ref, full)}
            raise AssertionError(("original admits forbidden clause cube",
                                  g["output"], state))

        frows[i] = cases(f, "Le", wanted, variables, leaf)["Witness"]
    fchecks = emit_checks(f, b, forward, "Eq", rows=frows, domains=fdomains)
    f.finish(forward, fchecks)

    pre = r
    intervals = []
    for pat in patterns:
        literals = [expression(0, {b["var_index"][name]: 1}) if value
                    else expression(1, {b["var_index"][name]: -1})
                    for name, value in pat["pattern"].items()]
        total = expression(-2)
        for e in literals:
            total = plus(total, e)
        lows = [expression(), total]
        highs = literals
        checks = [box(pre, plus(lo, hi, -1)) for lo in lows for hi in highs]
        intervals.append({"lower": lows, "upper": highs, "checks": checks})
    p = lift(pre, "intervals", intervals)
    layouts = p.old_layout
    layoutbyname = {pat["aux"]: layout for pat, layout in zip(patterns, layouts)}
    mapping = []
    domains = {}
    rrows = {}
    for i, v in enumerate(a["vars"]):
        name = v["name"]
        if name in b["var_index"]:
            j = b["var_index"][name]
            mapping.append(expression(0, {j: 1}))
            domains[(i, "VarLower")] = {"VarLower": j}
            domains[(i, "VarUpper")] = {"VarUpper": j}
            domains[(i, "VarInt")] = {"VarInt": j}
        elif i in fixed:
            mapping.append(expression())
            domains[(i, "VarLower")] = "Exact"
            domains[(i, "VarUpper")] = "Exact"
            domains[(i, "VarInt")] = "Exact"
        else:
            layout = layoutbyname[name]
            variable = layout["variable"]
            mapping.append(expression(0, {variable: 1}))
            lower = {"RowLower": layout["lower"][0]}
            upperref = {"RowUpper": layout["upper"][0]}
            residual = plus(expression(-1, {variable: 1}), p.refexpr(upperref), -1)
            upper = p.lin("Le", [[upperref, 1], [box(p, residual), 1]],
                          expression(-1, {variable: 1}))
            pat = patbyname[name]

            def leaf(child, state, pat=pat, layout=layout, variable=variable):
                value, eq = generated_indicator(child, pat, state, layout)
                return {"Witness": child.lin("Int", [[eq, 1]],
                                             expression(0, {variable: 1}),
                                             constant=value)}

            integer = cases(p, "Int", expression(0, {variable: 1}),
                            [b["var_index"][n] for n in pat["pattern"]],
                            leaf)["Witness"]
            domains[(i, "VarLower")] = lower
            domains[(i, "VarUpper")] = upper
            domains[(i, "VarInt")] = integer
    originalproof = {}
    for i, ref in fixed.items():
        originalproof[ref["RowEq"]] = "Exact"
    for pat in patterns:
        layout = layoutbyname[pat["aux"]]
        for name in pat["rows"]:
            ri = a["row_index"][name]
            row = a["rows"][ri]
            wanted = substitute(row_fact(row, "RowLower" if row["sense"] == "G"
                                         else "RowUpper"), mapping)
            if row["sense"] == "G":
                ref = {"RowLower": layout["lower"][1]}
                assert p.refexpr(ref) == wanted
            else:
                base = p.lin("Le", [[{"RowUpper": index}, F(1, 3)]
                                    for index in layout["upper"]])
                residual = plus(wanted, p.refexpr(base), -1)
                ref = p.lin("Le", [[base, 1], [box(p, residual), 1]], wanted)
            originalproof[ri] = ref
    for g in h["groups"]:
        variables = [b["var_index"][name] for name in g["relation_variables"]]
        for name in g["original_or_rows"]:
            ri = a["row_index"][name]
            row = a["rows"][ri]
            wanted = substitute(row_fact(row, "RowLower" if row["sense"] == "G"
                                         else "RowUpper"), mapping)

            def leaf(child, state, g=g, wanted=wanted):
                for targetname in g["replacement_rows"]:
                    ref = row_ref(b, targetname)
                    e = child.refexpr(ref)
                    value = e[0] + sum(c * state[i][0] for i, c in e[1].items())
                    if value > 0:
                        return {"Absurd": reduced(child, ref, state)}
                full = dict(state)
                for aux in g["auxiliary_variables"]:
                    if aux in layoutbyname:
                        layout = layoutbyname[aux]
                        full[layout["variable"]] = generated_indicator(
                            child, patbyname[aux], state, layout)
                return {"Witness": under(child, "Le", wanted, full)}

            originalproof[ri] = cases(p, "Le", wanted, variables, leaf)["Witness"]
    assert set(originalproof) == set(range(7029))
    rrows = {i: originalproof[i] for i in range(7029)}
    rchecks = emit_checks(p, a, mapping, "Eq", rows=rrows, domains=domains)
    p.finish(mapping, rchecks)
    counts = {"source_variables": 4500, "target_variables": 500,
              "source_rows": 7029, "target_rows": 2539, "local_groups": 500,
              "eliminated_auxiliaries": 4000,
              "active_pattern_intervals": len(patterns),
              "fixed_zero_auxiliaries": len(fixed), "claims": 2,
              "obligations_by_claim": [len(fchecks), len(rchecks)]}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test62-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test62"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test62", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test62", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
