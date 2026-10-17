#!/usr/bin/env python3
"""Native test78 count-aggregation reconstruction with intervals and menus."""
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, sha
from prepare_test21 import combine, substitute
from prepare_test48 import emit_checks, int_witness, lift, rounded, sumexpr
from prepare_native import compile_case, make_proof


def total(es):
    return combine(((e, F(1)) for e in es))


def var(i):
    return expression(0, {i: 1})


def terms(*items):
    return [[ref, F(coef)] for ref, coef in items if ref is not None]


def inspect(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (3472, 4633, 2720, 3881)
    assert a["objective"][0] == b["objective"][0] == 0
    sources = set(a["objective"][1])
    assert len(sources) == 2048 and set(a["objective"][1].values()) == {F(-1)}
    auxiliaries = set(range(len(a["vars"]))) - sources
    assert len(auxiliaries) == 1424
    assert all(v["integer"] and v["lower"] == 0 and v["upper"] == 1 for v in a["vars"])
    outgoing = defaultdict(list)
    capacity = {}
    packing = []
    for ri, row in enumerate(a["rows"]):
        assert row["sense"] == "L"
        ts = row["terms"]
        if len(ts) == 2 and row["rhs"] == 0:
            s = next(i for i, c in ts.items() if c == 1)
            z = next(i for i, c in ts.items() if c == -1)
            assert s in sources and z in auxiliaries
            outgoing[s].append((z, ri))
        elif row["rhs"] == 9:
            assert len(ts) == 128 and set(ts) <= sources
            assert set(ts.values()) == {F(1)}
            capacity[row["name"]] = sorted(ts)
        else:
            assert row["rhs"] == 1 and len(ts) == 16
            assert set(ts) <= auxiliaries and set(ts.values()) == {F(1)}
            packing.append(ri)
    assert set(outgoing) == sources and sum(map(len, outgoing.values())) == 4528
    assert len(capacity) == 16 and len(packing) == 89
    assert sorted(i for ids in capacity.values() for i in ids) == sorted(sources)
    assert sorted(i for r in packing for i in a["rows"][r]["terms"]) == sorted(auxiliaries)
    leaves = {i for i, refs in outgoing.items() if len(refs) == 1}
    assert len(leaves) == 768
    assert {a["vars"][i]["name"] for i in leaves} == set(h["removed_variables"])
    pools = {x["capacity_row"]: x for x in h["pools"]}
    assert set(pools) == set(capacity)
    for name, ids in capacity.items():
        assert {a["var_index"][n] for n in pools[name]["members"]} == set(ids) & leaves
        assert len(pools[name]["members"]) == 48
    assert set(b["var_index"]) == ({a["vars"][i]["name"] for i in set(range(len(a["vars"]))) - leaves} |
                                  {x["variable"] for x in pools.values()})
    for i in set(range(len(a["vars"]))) - leaves:
        v = b["vars"][b["var_index"][a["vars"][i]["name"]]]
        assert v["lower"] == 0 and v["upper"] == 1 and v["integer"] == (i in auxiliaries)
    for pool in pools.values():
        v = b["vars"][b["var_index"][pool["variable"]]]
        assert v["lower"] == 0 and v["upper"] == 48 and not v["integer"]
    return {"sources": sources, "aux": auxiliaries, "outgoing": outgoing,
            "capacities": capacity, "packing": packing, "leaves": leaves,
            "pools": pools}


def forward(a, b, h, p):
    mapping = []
    domains = {}
    rows = {}
    pool_by_name = {v["variable"]: (name, v) for name, v in h["pools"].items()}
    for j, v in enumerate(b["vars"]):
        if v["name"] in a["var_index"]:
            mapping.append(var(a["var_index"][v["name"]]))
            continue
        name, pool = pool_by_name[v["name"]]
        ids = [a["var_index"][n] for n in pool["members"]]
        mapping.append(total(var(i) for i in ids))
        domains[(j, "VarLower")] = p.lin(
            "Le", [[{"VarLower": i}, F(1)] for i in ids], mul(mapping[-1], -1))
        domains[(j, "VarUpper")] = p.lin(
            "Le", [[{"VarUpper": i}, F(1)] for i in ids],
            plus(mapping[-1], expression(-48)))
        ri = b["row_index"][pool["row"]]
        rows[ri] = p.lin("Le", [[{"RowUpper": h["outgoing"][i][0][1]}, F(1)]
                                for i in ids])
    for i, row in enumerate(b["rows"]):
        if i in rows:
            continue
        ref = row_ref(a, row["name"])
        assert p.refexpr(ref) == substitute(row_fact(row, "RowUpper"), mapping)
        rows[i] = ref
    checks = emit_checks(p, b, mapping, "Le", rows=rows, domains=domains)
    p.finish(mapping, checks)
    return len(checks)


def availability(a, b, h, pre):
    intervals = []
    original = []
    factors = {}
    for i in sorted(h["sources"]):
        bits = []
        for z, ri in h["outgoing"][i]:
            ti = b["var_index"][a["vars"][z]["name"]]
            bits.append({"expr": var(ti), "lower": {"VarLower": ti},
                         "upper": {"VarUpper": ti}, "integer": {"VarInt": ti},
                         "row": a["rows"][ri]["name"]})
        factors[i] = bits
        if len(bits) == 1:
            continue
        low = plus(total(x["expr"] for x in bits), expression(1 - len(bits)))
        checks = []
        for lower in [expression(), low]:
            for k, bit in enumerate(bits):
                checks.append(bit["lower"] if not lower[1] else
                              pre.lin("Le", [[x["upper"], F(1)]
                                             for j, x in enumerate(bits) if j != k],
                                      plus(low, bit["expr"], -1)))
        intervals.append({"lower": [expression(), low],
                          "upper": [x["expr"] for x in bits], "checks": checks})
        original.append(i)
    p = lift(pre, "intervals", intervals)
    layouts = p.old_layout
    available = {}
    old_bound = {}
    for i, bits in factors.items():
        if len(bits) == 1:
            available[i] = bits[0]
    for i, l in zip(original, layouts):
        bits = factors[i]
        z = var(l["variable"])
        old = var(b["var_index"][a["vars"][i]["name"]])
        lo = {"RowLower": l["lower"][0]}

        def derive(kind, wanted):
            def walk(cur, k, fixed):
                if k == len(bits):
                    one = cur.lin("Le", [[{"RowLower": l["lower"][1]}, F(1)]] +
                                  [[r, F(-1)] for r in fixed],
                                  plus(expression(1), z, -1))
                    if kind == "Le":
                        ref = cur.lin("Le", [[one, F(1)],
                                             [{"VarUpper": next(iter(old[1]))}, F(1)]],
                                      wanted)
                    else:
                        upper = cur.lin("Le", [[{"RowUpper": l["upper"][0]}, F(1)],
                                               [fixed[0], F(1)]],
                                        plus(z, expression(-1)))
                        eq = cur.eqpair(upper, one)
                        ref = cur.lin("Int", [[eq, F(1)]], z, constant=1)
                    return {"Witness": ref}
                bit = bits[k]

                def zero(child, guard):
                    eq = child.eqpair(guard, bit["lower"])
                    if kind == "Le":
                        ref = child.lin("Le", [[row_ref(b, bit["row"]), F(1)],
                                               [eq, F(1)], [lo, F(1)]], wanted)
                    else:
                        upper = child.lin("Le", [[{"RowUpper": l["upper"][k]}, F(1)],
                                                 [eq, F(1)]], z)
                        eqz = child.eqpair(upper, lo)
                        ref = child.lin("Int", [[eqz, F(1)]], z)
                    return {"Witness": ref}

                def one(child, guard):
                    return walk(child, k + 1,
                                fixed + [child.eqpair(bit["upper"], guard)])

                return {"Witness": cur.cases(kind, wanted, bit["expr"],
                                             bit["integer"], zero, one)}

            return walk(p, 0, [])["Witness"]

        integer = derive("Int", z)
        old_bound[i] = derive("Le", plus(old, z, -1))
        hi = p.lin("Le", [[{"RowUpper": l["upper"][0]}, F(1)],
                          [bits[0]["upper"], F(1)]], plus(z, expression(-1)))
        available[i] = {"expr": z, "lower": lo, "upper": hi, "integer": integer,
                        "links": {bit["row"]: {"RowUpper": l["upper"][k]}
                                  for k, bit in enumerate(bits)}}
    return p, intervals, available, old_bound


def menus_for_prefixes(p, h, available):
    menus = []
    prefix = {}
    specs = []
    for group, ids in h["capacities"].items():
        previous = {"expr": expression(), "lower": None, "upper": None,
                    "integer": None, "count": expression(), "count_int": None,
                    "k": 0, "menu": None}
        prefix[group] = [previous]
        for k, i in enumerate(ids, 1):
            b = available[i]
            s = plus(previous["expr"], b["expr"])
            lo = p.lin("Le", terms((previous["lower"], 1), (b["lower"], 1)),
                       mul(s, -1))
            hi = p.lin("Le", terms((previous["upper"], 1), (b["upper"], 1)),
                       plus(s, expression(-k)))
            integer = p.lin("Int", terms((previous["integer"], 1),
                                         (b["integer"], 1)), s)
            cur = {"expr": s, "lower": lo, "upper": hi, "integer": integer,
                   "k": k, "menu": None, "count": s, "count_int": integer}
            if k > 9:
                specs.append({"maximum_index": k,
                              "activation": expression(1), "index": s,
                              "checks": ["Exact", "Exact", "Exact", lo, hi, integer]})
                cur["menu_index"] = len(specs) - 1
            prefix[group].append(cur)
            previous = cur
    q = lift(p, "menus", specs)
    for seq in prefix.values():
        for d in seq:
            if d.get("menu_index") is not None:
                layout = q.old_layout[d["menu_index"]]
                start = layout["options"][0]
                d["menu"] = {"start": start, "n": d["k"],
                             "index": d["expr"],
                             "sum": {"RowEq": layout["sum_row"]},
                             "moment": {"RowEq": layout["moment_row"]}}
                d["count"] = expression(0, {start + j: min(j, 9)
                                            for j in range(d["k"] + 1) if j})
        for d in seq[10:]:
            d["count_int"] = q.lin("Int", [[{"VarInt": i}, c]
                                           for i, c in d["count"][1].items()],
                                   d["count"])
    return q, specs, prefix


def menu_upper(p, d):
    if d["menu"] is None:
        if d["k"] == 0:
            return p.lin("Le", [], expression(-9), constant=-9)
        return p.lin("Le", [[d["upper"], F(1)]],
                     plus(d["count"], expression(-9)), constant=d["k"] - 9)
    m = d["menu"]
    start = m["start"]
    return p.lin("Le", [[m["sum"], F(9)]] +
                 [[{"VarLower": start + j}, F(9 - j)] for j in range(9)],
                 plus(d["count"], expression(-9)))


def min_low(p, d, guard, bound):
    """Given S<=bound<=9, prove C-S=0, or None for an exact identity."""
    assert bound <= 9
    if d["menu"] is None:
        return None
    m = d["menu"]
    k = m["k"]
    start = m["start"]
    tail = expression(0, {start + j: 1 for j in range(10, k + 1)})
    refs = [[m["moment"], F(1, 10)], [guard, F(1, 10)]]
    refs += [[{"VarLower": start + j}, F(j, 10) - (1 if j >= 10 else 0)]
             for j in range(k + 1) if F(j, 10) != (1 if j >= 10 else 0)]
    upper = p.lin("Le", refs, plus(tail, expression(-F(bound, 10))))
    integer = p.lin("Int", [[{"VarInt": i}, c] for i, c in tail[1].items()], tail)
    zero = rounded(p, upper, integer)
    assert p.refexpr(zero) == tail
    wanted = plus(d["count"], d["expr"], -1)
    first = p.lin("Le", [[m["moment"], F(1)]] +
                  [[{"VarLower": start + j}, F(j - 9)] for j in range(10, k + 1)],
                  wanted)
    second = p.lin("Le", [[m["moment"], F(-1)], [zero, F(k - 9)]] +
                   [[{"VarLower": start + j}, F(k - j)] for j in range(10, k)],
                   mul(wanted, -1))
    return p.eqpair(first, second)


def min_high(p, d, guard, bound=9):
    """Given 9<=bound<=S, prove C-9=0."""
    assert 9 <= bound <= d["k"]
    if d["menu"] is None:
        assert d["k"] == bound == 9
        return p.eqpair(d["upper"], guard)
    m = d["menu"]
    k = m["k"]
    start = m["start"]
    low = expression(0, {start + j: 1 for j in range(9)})
    refs = [[m["sum"], F(k, k - 8)], [m["moment"], F(-1, k - 8)],
            [guard, F(1, k - 8)]]
    refs += [[{"VarLower": start + j},
              F(8 - j if j <= 8 else k - j, k - 8)]
             for j in range(k + 1) if (8 - j if j <= 8 else k - j)]
    upper = p.lin("Le", refs, plus(low, expression(F(bound - k, k - 8))))
    integer = p.lin("Int", [[{"VarInt": i}, c] for i, c in low[1].items()], low)
    zero = rounded(p, upper, integer)
    assert p.refexpr(zero) == low
    first = menu_upper(p, d)
    second = p.lin("Le", [[m["sum"], F(-9)], [zero, F(9)]] +
                   [[{"VarLower": start + j}, F(j)] for j in range(1, 9)],
                   plus(expression(9), d["count"], -1))
    return p.eqpair(first, second)


def reverse(a, b, h, pre):
    p, intervals, available, old_bound = availability(a, b, h, pre)
    p, menus, prefix = menus_for_prefixes(p, h, available)
    mapping = [None] * len(a["vars"])
    domains = {}
    rows = {}
    group_cost = []
    for i in h["aux"]:
        mapping[i] = var(b["var_index"][a["vars"][i]["name"]])
    for group, ids in h["capacities"].items():
        seq = prefix[group]
        chosen = []
        for k, i in enumerate(ids, 1):
            cur, previous = seq[k], seq[k - 1]
            bbit = available[i]
            w = plus(cur["count"], previous["count"], -1)
            mapping[i] = w
            chosen.append(w)
            if k <= 9:
                low = bbit["lower"]
                link = None
                integer = bbit["integer"]
            else:
                split = plus(previous["expr"], expression(-8))
                split_int = p.lin("Int", [[previous["integer"], F(1)]], split,
                                  constant=-8)
                descriptor = {"expr": split, "integer": split_int}

                def prove_delta(lower):
                    wanted = mul(w, -1) if lower else plus(w, bbit["expr"], -1)

                    def left(child, guard):
                        up = child.lin("Le", [[guard, F(1)], [bbit["upper"], F(1)]],
                                       plus(cur["expr"], expression(-9)))
                        ei = min_low(child, cur, up, 9)
                        ep = min_low(child, previous, guard, 8)
                        refs = terms((ei, -1 if lower else 1), (ep, 1 if lower else -1))
                        if lower:
                            refs.append([bbit["lower"], F(1)])
                        return {"Witness": child.lin("Le", refs, wanted)}

                    def right(child, guard):
                        down = child.lin("Le", [[guard, F(1)], [bbit["lower"], F(1)]],
                                         plus(expression(9), cur["expr"], -1))
                        ei = min_high(child, cur, down)
                        ep = min_high(child, previous, guard)
                        refs = terms((ei, -1 if lower else 1), (ep, 1 if lower else -1))
                        if not lower:
                            refs.append([bbit["lower"], F(1)])
                        return {"Witness": child.lin("Le", refs, wanted)}

                    return p.cases("Le", wanted, descriptor["expr"],
                                   descriptor["integer"], left, right)

                low = prove_delta(True)
                link = prove_delta(False)
                integer = p.lin("Int", [[cur["count_int"], F(1)],
                                        [previous["count_int"], F(-1)]], w)
            domains[(i, "VarLower")] = low
            domains[(i, "VarInt")] = integer
            domains[(i, "VarUpper")] = (bbit["upper"] if link is None else
                                        p.lin("Le", [[link, F(1)], [bbit["upper"], F(1)]],
                                              plus(w, expression(-1))))
            for aux, ri in h["outgoing"][i]:
                if i in h["leaves"]:
                    if link is None:
                        rows[ri] = "Exact"
                    else:
                        rows[ri] = link
                else:
                    ref = bbit["links"][a["rows"][ri]["name"]]
                    rows[ri] = (ref if link is None else
                                p.lin("Le", [[link, F(1)], [ref, F(1)]],
                                      plus(w, var(b["var_index"][a["vars"][aux]["name"]]), -1)))
        ri = a["row_index"][group]
        rows[ri] = menu_upper(p, seq[-1])
        assert p.refexpr(rows[ri]) == plus(total(chosen), expression(-9))
        pool = h["pools"][group]
        old_total = total([var(b["var_index"][a["vars"][i]["name"]])
                           for i in ids if i not in h["leaves"]] +
                          [var(b["var_index"][pool["variable"]])])
        available_upper = p.lin(
            "Le", [[row_ref(b, pool["row"]), F(1)]] +
            [[old_bound[i], F(1)] for i in ids if i not in h["leaves"]],
            plus(old_total, seq[-1]["expr"], -1))
        end = seq[-1]
        split = plus(end["expr"], expression(-9))
        sint = p.lin("Int", [[end["integer"], F(1)]], split, constant=-9)
        wanted = plus(old_total, end["count"], -1)

        def left(child, guard):
            eq = min_low(child, end, guard, 9)
            return {"Witness": child.lin("Le", [[available_upper, F(1)],
                                                [eq, F(-1)]], wanted)}

        def right(child, guard):
            eq = min_high(child, end, guard, 10)
            return {"Witness": child.lin("Le", [[row_ref(b, group), F(1)],
                                                [eq, F(-1)]], wanted)}

        group_cost.append(p.cases("Le", wanted, split, sint, left, right))
    for ri in h["packing"]:
        rows[ri] = row_ref(b, a["rows"][ri]["name"])
    objective = p.lin("Le", [[ref, F(1)] for ref in group_cost],
                      plus(substitute(a["objective"], mapping), b["objective"], -1))
    for ri, ref in list(rows.items()):
        if ref == "Exact":
            del rows[ri]
    checks = emit_checks(p, a, mapping, "Le", rows=rows, domains=domains,
                         objective=objective)
    p.finish(mapping, checks)
    info = {"availability_intervals": len(intervals),
            "prefix_menus": len(menus),
            "generated_menu_variables": sum(m["maximum_index"] + 1 for m in menus),
            "allocated_ids": p.counter[0], "reverse_obligations": len(checks)}
    return info


def prepare(source, target, audit):
    a = parse_mps(source)
    b = parse_mps(target)
    h = inspect(a, b, json.loads(Path(audit).read_text()))
    proof, f, r = make_proof(a, b)
    projection = [[i, b["var_index"][a["vars"][i]["name"]]] for i in sorted(h["aux"])]
    forward_obligations = forward(a, b, h, f)
    info = reverse(a, b, h, r)
    info["forward_obligations"] = forward_obligations
    info.update({"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
                 "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
                 "claims": 2, "auxiliary_projection": len(projection)})
    return proof, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test78-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test78"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    out = args.out.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, info = prepare(source, target, audit)
    record = compile_case(proof, out, case_id="test78", source=source,
                          target=target, metadata={"counts": info})
    record["counts"] = info
    record["preparation_seconds"] = time.perf_counter() - started
    (out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test78", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": info,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
