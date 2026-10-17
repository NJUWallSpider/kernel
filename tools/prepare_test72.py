#!/usr/bin/env python3
"""Native test72 certificates using checked linear, case and menu rules.

The legacy continuous reverse LP claim is not part of the two-tree MI-OPT
contract; the forward and reverse integer directions are complete.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test21 import combine
from prepare_test48 import emit_checks, lift, rounded, sumexpr
from prepare_native import compile_case, make_proof


def total(es):
    return combine(((e, F(1)) for e in es))


def var(i):
    return expression(0, {i: 1})


def decoded(e):
    return expression(F(e["constant"]), {i: F(c) for i, c in e["terms"]})


def integer_fact(p, e):
    if e[0] == 0 and len(e[1]) == 1:
        i, c = next(iter(e[1].items()))
        if c == 1:
            return {"VarInt": i}
    return p.lin("Int", [[{"VarInt": i}, c] for i, c in e[1].items()],
                 e, constant=e[0])


def bounds(p, e):
    lo = p.prove("Le", mul(e, -1))
    hi = p.prove("Le", plus(e, expression(-1)))
    it = integer_fact(p, e)
    return {"expr": e, "lower": lo, "upper": hi, "integer": it}


def fix(p, bit, v, guard):
    return p.eqpair(guard, bit["lower"]) if v == 0 else p.eqpair(bit["upper"], guard)


def exhaustive(p, kind, wanted, bits, leaf):
    def rec(cur, k, state):
        if k == len(bits):
            return leaf(cur, state)
        bit = bits[k]

        def side(child, g, v):
            return rec(child, k + 1, state + [(v, fix(child, bit, v, g))])

        r = cur.cases(kind, wanted, bit["expr"], bit["integer"],
                      lambda q, g: side(q, g, 0), lambda q, g: side(q, g, 1))
        return {"Witness": r}

    return rec(p, 0, [])["Witness"]


def evaluated(p, e, state, es):
    terms = []
    value = e[0]
    for (v, ref), x in zip(state, es):
        assert len(x[1]) == 1
        i, c = next(iter(x[1].items()))
        assert c == 1
        coef = e[1].get(i, 0)
        value += coef * v
        if coef:
            terms.append([ref, coef])
    assert set(e[1]) <= set(next(iter(x[1])) for x in es)
    return value, terms


def menu_zero(p, m, l, u, guard):
    n = m["n"]
    start = m["start"]
    out = []
    if l > 0:
        tail = expression(0, {start + j: 1 for j in range(l)})
        refs = [[m["sum"], F(n, n - l + 1)], [m["moment"], -F(1, n - l + 1)],
                [guard, F(1, n - l + 1)]]
        refs += [[{"VarLower": start + j},
                  F((l - 1 - j) if j < l else (n - j), n - l + 1)]
                 for j in range(n + 1) if ((l - 1 - j) if j < l else (n - j))]
        le = p.lin("Le", refs, plus(tail, expression(F(l - n, n - l + 1))))
        integer = p.lin("Int", [[{"VarInt": i}, c] for i, c in tail[1].items()], tail)
        out.append((rounded(p, le, integer), range(l)))
    if u < n:
        tail = expression(0, {start + j: 1 for j in range(u + 1, n + 1)})
        refs = [[m["moment"], F(1, u + 1)], [guard, F(1, u + 1)]]
        refs += [[{"VarLower": start + j}, F(j, u + 1) - (1 if j > u else 0)]
                 for j in range(n + 1) if F(j, u + 1) != (1 if j > u else 0)]
        le = p.lin("Le", refs, plus(tail, expression(-F(u, u + 1))))
        integer = p.lin("Int", [[{"VarInt": i}, c] for i, c in tail[1].items()], tail)
        out.append((rounded(p, le, integer), range(u + 1, n + 1)))
    return out


def menu_segment(p, m, values, l, u, guard, alpha, beta):
    wanted = plus(expression(0, {m["start"] + j: v for j, v in enumerate(values) if v}),
                  plus(mul(m["index"], alpha), expression(beta)), -1)
    zeros = menu_zero(p, m, l, u, guard)
    base = [[m["sum"], beta], [m["moment"], alpha]]
    residual = {j: F(values[j]) - alpha * j - beta for j in range(m["n"] + 1)}

    def side(sign):
        refs = [[r, sign * c] for r, c in base if c]
        for zero, indices in zeros:
            scale = max([sign * residual[j] for j in indices] + [F(0)])
            if scale:
                refs.append([zero, scale])
            refs += [[{"VarLower": m["start"] + j},
                      scale - sign * residual[j]] for j in indices
                     if scale != sign * residual[j]]
        return p.lin("Le", refs, mul(wanted, sign))

    return p.eqpair(side(1), side(-1))


def menu_function(p, m, values, cut, left, right):
    e = expression(0, {m["start"] + j: v for j, v in enumerate(values) if v})
    wanted = plus(e, expression(), -1)
    split = plus(m["index"], expression(-cut))
    bit = {"expr": split, "integer": integer_fact(p, split)}

    def branch(q, g, low):
        l, u, alpha, beta = (0, cut, *left) if low else (cut + 1, m["n"], *right)
        eq = menu_segment(q, m, values, l, u, g, F(alpha), F(beta))
        return {"Witness": eq}

    return e, bit, branch


def forward(a, b, h, p):
    mapping = [var(a["var_index"][v["name"]]) if v["name"] in a["var_index"] else None
               for v in b["vars"]]
    rows = {}
    for d in h["capacity_blocks"]:
        q = b["var_index"][d["new_variable"]]
        mapping[q] = expression(0, {a["var_index"][x["lambda_variable"]]: F(x["cost"])
                                    for x in d["terms"]})
        for cut in d["cuts"]:
            if not cut["retained"]:
                continue
            t = F(cut["threshold"])
            refs = [[row_ref(a, d["original_row"]), t]]
            for x in d["terms"]:
                c = F(x["cost"])
                i = a["var_index"][x["lambda_variable"]]
                if c < t:
                    refs.append([row_ref(a, x["upper_row"]), t - c])
                if c > t:
                    refs.append([{"VarLower": i}, c - t])
            i = b["row_index"][cut["name"]]
            wanted = substitute(row_fact(b["rows"][i], "RowLower"), mapping)
            rows[i] = p.lin("Le", refs, wanted)
    for d in h["clique_rows"]:
        ri = b["row_index"][d["name"]]
        wanted = substitute(row_fact(b["rows"][ri], "RowUpper"), mapping)
        ids = [a["var_index"][n] for n in d["variables"]]
        bits = [bounds(p, var(i)) for i in ids]
        es = [x["expr"] for x in bits]

        def leaf(q, state):
            value, ts = evaluated(q, wanted, state, es)
            if value <= 0:
                return {"Witness": q.lin("Le", ts, wanted, constant=value)}
            for rn in d["original_edge_rows"]:
                r = row_ref(a, rn)
                val, refs = evaluated(q, q.refexpr(r), state, es)
                if val > 0:
                    return {"Absurd": q.lin("Le", [[r, F(1)]] +
                                            [[f, -c] for f, c in refs],
                                            expression(val))}
            raise AssertionError("uncovered clique")

        rows[ri] = exhaustive(p, "Le", wanted, bits, leaf)
    assert all(e is not None for e in mapping)
    checks = emit_checks(p, b, mapping, "Le", rows=rows)
    p.finish(mapping, checks)
    return len(checks)


def min_eq(p, d, K, guard, low, bound):
    if d["menu"] is None:
        if low:
            return p.lin("Eq", [], expression())
        assert d["k"] == K == bound
        return p.eqpair(d["upper"], guard)
    m = d["menu"]
    values = [min(j, K) for j in range(m["n"] + 1)]
    return menu_segment(p, m, values, 0 if low else bound,
                        bound if low else m["n"], guard,
                        F(1 if low else 0), F(0 if low else K))


def function_fact(p, m, values, cut, left, right, kind, wanted, leaf):
    e, bit, branch = menu_function(p, m, values, cut, left, right)

    def side(q, g, low):
        eq = branch(q, g, low)["Witness"]
        return leaf(q, g, low, eq)

    return p.cases(kind, wanted, bit["expr"], bit["integer"],
                   lambda q, g: side(q, g, True), lambda q, g: side(q, g, False))


def reverse_integer(a, b, h, pre):
    menus = []
    prefixes = []
    special = []
    mapping = [var(b["var_index"][v["name"]]) if v["name"] in b["var_index"] else None
               for v in a["vars"]]
    domains = {}
    rows = {}
    for d in h["capacity_blocks"]:
        K = d["K"]
        S = expression()
        seq = [{"expr": S, "count": S, "k": 0, "menu": None,
                "lower": None, "upper": None}]
        for k, x in enumerate(sorted(d["terms"], key=lambda x: -x["cost"]), 1):
            y = var(b["var_index"][x["primary_variable"]])
            S = plus(S, y)
            lo = pre.prove("Le", mul(S, -1))
            hi = pre.prove("Le", plus(S, expression(-k)))
            integer = pre.prove("Int", S)
            cur = {"expr": S, "k": k, "menu": None, "lower": lo,
                   "upper": hi, "term": x}
            if k > K:
                cur["menu_index"] = len(menus)
                menus.append({"maximum_index": k, "activation": expression(1),
                              "index": S,
                              "checks": ["Exact", "Exact", "Exact", lo, hi, integer]})
            else:
                cur["count"] = S
            seq.append(cur)
        prefixes.append((d, seq))
    incidence = defaultdict(list)
    for row in a["rows"]:
        for i in row["terms"]:
            incidence[i].append(row["name"])
    for name in h["relaxed_integer_variables"]:
        i = a["var_index"][name]
        vi = b["var_index"][name]
        v = a["vars"][i]
        rs = incidence[i]
        if len(rs) == 2 and v["upper"] == 1 and a["objective"][1].get(i, 0) == 0:
            link = next(rn for rn in rs
                        if a["rows"][a["row_index"][rn]]["sense"] == "L")
            row = a["rows"][a["row_index"][link]]
            ids = [b["var_index"][a["vars"][j]["name"]]
                   for j in row["terms"] if j != i]
            e = expression(0, {j: 1 for j in ids})
            n = len(ids)
            typ = "day"
            values = [min(j, 1) for j in range(n + 1)]
            cut = 0
            left = (1, 0)
            right = (0, 1)
            req = e
        elif v["upper"] == 1 and a["objective"][1].get(i, 0) == 2:
            if not rs:
                mapping[i] = expression()
                continue
            assert len(rs) == 1
            link = rs[0]
            row = a["rows"][a["row_index"][link]]
            assert row["sense"] == "G" and row["rhs"] == 0
            coeff = {b["var_index"][a["vars"][j]["name"]]: c
                     for j, c in row["terms"].items() if j != i}
            nneg = sum(c < 0 for c in coeff.values())
            n = len(coeff)
            e = expression(nneg, coeff)
            typ = "isolation"
            values = [max(0, nneg - j) for j in range(n + 1)]
            cut = nneg - 1
            left = (-1, nneg)
            right = (0, 0)
            req = expression(0, {j: -c for j, c in coeff.items()})
            if cut < 0:
                mapping[i] = expression()
                continue
        else:
            mapping[i] = None
            continue
        if n == 0:
            mapping[i] = expression()
            special.append({"i": i, "vi": vi, "type": "day", "menu_index": None,
                            "dominate": row_ref(b, link)})
            continue
        mi = len(menus)
        menus.append({"maximum_index": n, "activation": expression(1), "index": e,
                      "checks": ["Exact", "Exact", "Exact",
                                 pre.prove("Le", mul(e, -1)),
                                 pre.prove("Le", plus(e, expression(-n))),
                                 pre.prove("Int", e)]})
        special.append({"i": i, "vi": vi, "link": link, "menu_index": mi,
                        "type": typ, "values": values, "cut": cut,
                        "left": left, "right": right, "req": req})
    p = lift(pre, "menus", menus)
    ms = []
    for spec, layout in zip(menus, p.old_layout):
        ms.append({"start": layout["options"][0], "n": spec["maximum_index"],
                   "index": spec["index"], "sum": {"RowEq": layout["sum_row"]},
                   "moment": {"RowEq": layout["moment_row"]}})
    for d, seq in prefixes:
        K = d["K"]
        for cur in seq[1:]:
            if "menu_index" in cur:
                m = ms[cur["menu_index"]]
                cur["menu"] = m
                cur["count"] = expression(0, {m["start"] + j: min(j, K)
                                              for j in range(m["n"] + 1) if j})
                cur["prefix_upper"] = p.lin(
                    "Le", [[m["moment"], 1]] +
                    [[{"VarLower": m["start"] + j}, j - K]
                     for j in range(K + 1, m["n"] + 1)],
                    plus(cur["count"], cur["expr"], -1))
                cur["cap_upper"] = p.lin(
                    "Le", [[m["sum"], K]] +
                    [[{"VarLower": m["start"] + j}, K - j] for j in range(K)],
                    plus(cur["count"], expression(-K)))
            else:
                cur["prefix_upper"] = p.lin("Le", [], expression())
                cur["cap_upper"] = p.lin(
                    "Le", [[cur["upper"], 1]], plus(cur["count"], expression(-K)),
                    constant=cur["k"] - K)
        for prev, cur in zip(seq, seq[1:]):
            x = cur["term"]
            i = a["var_index"][x["lambda_variable"]]
            y = var(b["var_index"][x["primary_variable"]])
            lam = plus(y, plus(cur["count"], prev["count"], -1), -1)
            mapping[i] = lam
            if prev["k"] < K:
                assert lam == expression()
                continue
            split = plus(prev["expr"], expression(1 - K))
            bit = {"expr": split, "integer": integer_fact(p, split)}
            wanted = mul(lam, -1)

            def lowerside(q, g, low):
                if low:
                    eq = min_eq(q, prev, K, g, True, K - 1)
                    refs = [[cur["prefix_upper"], 1], [eq, -1]]
                else:
                    eq = min_eq(q, prev, K, g, False, K)
                    refs = [[cur["cap_upper"], 1], [eq, -1],
                            [{"VarLower": b["var_index"][x["primary_variable"]]}, 1]]
                return {"Witness": q.lin("Le", refs, wanted)}

            domains[(i, "VarLower")] = p.cases(
                "Le", wanted, bit["expr"], bit["integer"],
                lambda q, g: lowerside(q, g, True),
                lambda q, g: lowerside(q, g, False))
            ri = a["row_index"][x["upper_row"]]
            wanted = plus(lam, y, -1)

            def linkside(q, g, low):
                if low:
                    gc = q.lin("Le", [[g, 1],
                                      [{"VarUpper": b["var_index"][x["primary_variable"]]}, 1]],
                               plus(cur["expr"], expression(-K)))
                    ec = min_eq(q, cur, K, gc, True, K)
                    return {"Witness": q.lin(
                        "Le", [[prev["prefix_upper"], 1], [ec, -1],
                               [{"VarLower": b["var_index"][x["primary_variable"]]}, 1]],
                        wanted)}
                gc = q.lin("Le", [[g, 1],
                                  [{"VarLower": b["var_index"][x["primary_variable"]]}, 1]],
                           plus(expression(K), cur["expr"], -1))
                ec = min_eq(q, cur, K, gc, False, K)
                return {"Witness": q.lin("Le", [[prev["cap_upper"], 1],
                                                 [ec, -1]], wanted)}

            rows[ri] = p.cases("Le", wanted, bit["expr"], bit["integer"],
                               lambda q, g: linkside(q, g, True),
                               lambda q, g: linkside(q, g, False))
            domains[(i, "VarUpper")] = p.lin(
                "Le", [[rows[ri], 1],
                       [{"VarUpper": b["var_index"][x["primary_variable"]]}, 1]],
                plus(lam, expression(-1)))
        last = seq[-1]
        cap = plus(last["count"], expression(-K))
        if last["menu"]:
            m = last["menu"]
            rows[a["row_index"][d["original_row"]]] = p.lin(
                "Le", [[m["sum"], K]] +
                [[{"VarLower": m["start"] + j}, K - min(j, K)]
                 for j in range(m["n"] + 1) if j < K], cap)
        else:
            rows[a["row_index"][d["original_row"]]] = p.prove("Le", cap)
    # Local retained integer reconstructions from exact menu moments.
    for z in special:
        if z["menu_index"] is None:
            continue
        m = ms[z["menu_index"]]
        i, vi = z["i"], z["vi"]
        e = expression(0, {m["start"] + j: v for j, v in enumerate(z["values"]) if v})
        mapping[i] = e

        def prove_wanted(kind, wanted, which):
            def leaf(q, g, low, eq):
                alpha, beta = z["left"] if low else z["right"]
                aff = plus(mul(m["index"], alpha), expression(beta))
                refs = [[eq, 1 if which in ("upper", "dominate", "linkiso") else -1]]
                if which == "upper":
                    if z["type"] == "day":
                        return {"Witness": q.prove(
                            "Le", wanted,
                            [[m["sum"], 1]] +
                            [[{"VarLower": m["start"] + j}, 1 - z["values"][j]]
                             for j in range(m["n"] + 1) if z["values"][j] != 1])}
                    if low:
                        refs.append([row_ref(b, z["link"]), 1])
                        refs.append([{"VarUpper": vi}, 1])
                    else:
                        refs = []
                        return {"Witness": q.lin("Le", [[eq, 1]], wanted, constant=-1)}
                elif which == "dominate":
                    if z["type"] == "day":
                        if low:
                            refs = [[eq, -1], [row_ref(b, z["link"]), 1]]
                        else:
                            refs = [[eq, -1], [{"VarUpper": vi}, 1]]
                    else:
                        if low:
                            refs.append([row_ref(b, z["link"]), 1])
                        else:
                            refs.append([{"VarLower": vi}, 1])
                elif which == "linkday":
                    if low:
                        refs = [[eq, 1]]
                    else:
                        refs = [[eq, 1], [g, 1]]
                elif which == "linkiso":
                    if low:
                        refs = [[eq, -1]]
                    else:
                        refs = [[eq, -1], [g, 1]]
                return {"Witness": q.lin("Le", refs, wanted)}

            return function_fact(p, m, z["values"], z["cut"], z["left"], z["right"],
                                 kind, wanted, leaf)

        domains[(i, "VarLower")] = p.lin(
            "Le", [[{"VarLower": m["start"] + j}, v]
                   for j, v in enumerate(z["values"]) if v], mul(e, -1))
        domains[(i, "VarInt")] = p.prove("Int", e)
        domains[(i, "VarUpper")] = prove_wanted("Le", plus(e, expression(-1)), "upper")
        dominate = plus(var(vi), e, -1) if z["type"] == "day" else plus(e, var(vi), -1)
        z["dominate"] = prove_wanted("Le", dominate, "dominate")
        wanted = plus(e, z["req"], -1) if z["type"] == "day" else plus(z["req"], e, -1)
        rows[a["row_index"][z["link"]]] = prove_wanted(
            "Le", wanted, "linkday" if z["type"] == "day" else "linkiso")
    shortmenus = []
    shorts = []
    for name in h["relaxed_integer_variables"]:
        i = a["var_index"][name]
        if mapping[i] is None:
            assert a["objective"][1].get(i, 0) == 5
            rn = incidence[i][0]
            row = a["rows"][a["row_index"][rn]]
            days = [j for j in row["terms"] if j != i]
            nonempty = [j for j in days if mapping[j] != expression()]
            e = total(mapping[j] for j in days)
            n = len(days)
            lo = p.prove("Le", mul(e, -1),
                         [[domains[(j, "VarLower")], 1] for j in nonempty])
            hi = p.prove("Le", plus(e, expression(-n)),
                         [[domains[(j, "VarUpper")], 1] for j in nonempty],
                         constant=len(nonempty) - n)
            integer = p.prove("Int", e)
            shortmenus.append((e, n, lo, hi, integer))
            shorts.append({"i": i, "vi": b["var_index"][name], "rn": rn,
                           "days": days, "m": int(row["rhs"])})
    specs = [{"maximum_index": n, "activation": expression(1), "index": e,
              "checks": ["Exact", "Exact", "Exact", lo, hi, integer]}
             for e, n, lo, hi, integer in shortmenus]
    p = lift(p, "menus", specs)
    sm = [{"start": layout["options"][0], "n": spec["maximum_index"],
           "index": spec["index"], "sum": {"RowEq": layout["sum_row"]},
           "moment": {"RowEq": layout["moment_row"]}}
          for spec, layout in zip(specs, p.old_layout)]
    for z, m in zip(shorts, sm):
        values = [max(0, z["m"] - j) for j in range(m["n"] + 1)]
        e = expression(0, {m["start"] + j: v for j, v in enumerate(values) if v})
        i = z["i"]
        mapping[i] = e
        domains[(i, "VarLower")] = p.lin(
            "Le", [[{"VarLower": m["start"] + j}, v]
                   for j, v in enumerate(values) if v], mul(e, -1))
        domains[(i, "VarInt")] = p.prove("Int", e)
        old = p.lin("Le", [[row_ref(b, z["rn"]), 1]] +
                    [[next(t for t in special if t["i"] == j)["dominate"], 1]
                     for j in z["days"]],
                    plus(expression(z["m"]), plus(m["index"], var(z["vi"])), -1))

        def leaf(q, g, low, eq):
            refs = [[eq, 1]] + ([[old, 1]] if low else [[{"VarLower": z["vi"]}, 1]])
            return {"Witness": q.lin("Le", refs, plus(e, var(z["vi"]), -1))}

        z["dominate"] = function_fact(p, m, values, z["m"] - 1, (-1, z["m"]), (0, 0),
                                      "Le", plus(e, var(z["vi"]), -1), leaf)
        domains[(i, "VarUpper")] = p.lin(
            "Le", [[z["dominate"], 1], [{"VarUpper": z["vi"]}, 1]],
            plus(e, expression(-a["vars"][i]["upper"])))
        wanted = plus(expression(z["m"]), plus(m["index"], e), -1)

        def rowleaf(q, g, low, eq):
            return {"Witness": q.lin("Le", [[eq, -1]] +
                                     ([] if low else [[g, 1]]), wanted)}

        rows[a["row_index"][z["rn"]]] = function_fact(
            p, m, values, z["m"] - 1, (-1, z["m"]), (0, 0), "Le", wanted, rowleaf)
    # Each capacity cost is a threshold at the first cost-group prefix reaching K.
    costrefs = []
    for d, seq in prefixes:
        K = d["K"]
        qidx = b["var_index"][d["new_variable"]]
        cost = expression(0, {})
        for cur in seq[1:]:
            cost = plus(cost, mapping[a["var_index"][cur["term"]["lambda_variable"]]],
                        cur["term"]["cost"])
        wanted = plus(cost, var(qidx), -1)
        boundaries = [j for j in range(1, len(seq))
                      if j == len(seq) - 1 or
                      seq[j]["term"]["cost"] != seq[j + 1]["term"]["cost"]]
        coeffs = {j: F(seq[j]["term"]["cost"] -
                       (seq[j + 1]["term"]["cost"] if j < len(seq) - 1 else 0))
                  for j in boundaries}

        def rec(curp, pos, lows):
            if pos == len(boundaries):
                refs = [[{"VarLower": qidx}, 1]]
                refs += [[eq, -coeffs[j]] for j, eq in lows.items()]
                return {"Witness": curp.lin("Le", refs, wanted)}
            j = boundaries[pos]
            node = seq[j]
            t = F(node["term"]["cost"])
            split = plus(node["expr"], expression(1 - K))
            bit = {"expr": split, "integer": integer_fact(curp, split)}

            def low(child, g):
                eq = min_eq(child, node, K, g, True, K - 1)
                return rec(child, pos + 1, {**lows, j: eq})

            def high(child, g):
                if node["k"] < K:
                    return {"Absurd": child.lin("Le", [[g, 1], [node["upper"], 1]],
                                                expression(K - node["k"]))}
                guard = child.lin("Le", [[g, 1]],
                                  plus(expression(K), node["expr"], -1))
                eqs = dict(lows)
                for jj in boundaries[pos:]:
                    gg = guard if jj == j else child.lin(
                        "Le", [[guard, 1]] +
                        [[{"VarLower": b["var_index"][seq[k]["term"]["primary_variable"]]}, 1]
                         for k in range(j + 1, jj + 1)],
                        plus(expression(K), seq[jj]["expr"], -1))
                    eqs[jj] = min_eq(child, seq[jj], K, gg, False, K)
                cut = next(x for x in d["cuts"] if x["threshold"] == t)
                threshold = expression(-K * t,
                                       {b["var_index"][x["primary_variable"]]:
                                        min(F(x["cost"]), t) for x in d["terms"]})
                threshold = plus(threshold, var(qidx), -1)
                if cut["retained"]:
                    tr = row_ref(b, cut["name"])
                else:
                    terms = [[{"VarUpper": b["var_index"][x["primary_variable"]]},
                              min(F(x["cost"]), t)] for x in d["terms"]] + \
                            [[{"VarLower": qidx}, 1]]
                    terms = [(ref, c) for ref, c in terms if c]
                    tr = child.prove("Le", threshold, terms,
                                     constant=cut["maximum_rhs_over_box"])
                return {"Witness": child.lin(
                    "Le", [[tr, 1]] + [[eq, -coeffs[jj]] for jj, eq in eqs.items()],
                    wanted)}

            ref = curp.cases("Le", wanted, bit["expr"], bit["integer"], low, high)
            return {"Witness": ref}

        costrefs.append(rec(p, 0, {})["Witness"])
    # Cliques imply all removed source edges by ordinary nonnegativity.
    for rn in h["removed_rows"]:
        if rn in rows or rn not in a["row_index"]:
            continue
        row = a["rows"][a["row_index"][rn]]
        if rn.startswith("CourseConflicts"):
            ids = set(row["terms"])
            cl = next(d for d in h["clique_rows"] if rn in d["original_edge_rows"])
            refs = [[row_ref(b, cl["name"]), 1]] + \
                   [[{"VarLower": b["var_index"][n]}, 1]
                    for n in cl["variables"] if a["var_index"][n] not in ids]
            rows[a["row_index"][rn]] = p.lin(
                "Le", refs, substitute(row_fact(row, "RowUpper"), mapping))
    objterms = [[r, 1] for r in costrefs] + \
               [[z["dominate"], 2] for z in special if z["type"] == "isolation"] + \
               [[z["dominate"], 5] for z in shorts]
    objterms += [[{"VarLower": b["var_index"][name]}, 2]
                 for name in h["relaxed_integer_variables"]
                 if a["objective"][1].get(a["var_index"][name], 0) == 2
                 and not incidence[a["var_index"][name]]]
    objective = p.lin("Le", objterms,
                      plus(substitute(a["objective"], mapping), b["objective"], -1))
    checks = emit_checks(p, a, mapping, "Le", rows=rows, domains=domains,
                         objective=objective)
    p.finish(mapping, checks)
    return p, {"menus": len(menus) + len(shorts), "obligations": len(checks)}


def prepare(source, target, audit):
    a = parse_mps(source)
    b = parse_mps(target)
    h = json.loads(Path(audit).read_text())
    proof, f, r = make_proof(a, b)
    proj = [[a["var_index"][n], b["var_index"][n]]
            for n in h["primary_binary_variables"]]
    forward_obligations = forward(a, b, h, f)
    p, reverse_info = reverse_integer(a, b, h, r)
    counts = {"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
              "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
              "primary_observations": len(proj),
              "capacity_blocks": len(h["capacity_blocks"]),
              "largest_capacity_block": max(len(d["terms"]) for d in h["capacity_blocks"]),
              "claims": 2, "menus": reverse_info["menus"],
              "obligations_by_claim": [forward_obligations,
                                       reverse_info["obligations"]]}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test72-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test72"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(source, target, audit)
    record = compile_case(proof, args.out, case_id="test72", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test72", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
