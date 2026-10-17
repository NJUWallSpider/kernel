#!/usr/bin/env python3
"""Native affine-component, constant and leaf-sum bijection for test75."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact, box, exact
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (48950, 98021, 38001, 72968)
    removed = {a["var_index"][n]: d for n, d in h["removed_variables"].items()}
    assert len(removed) == 10949
    assert set(removed) == {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = []
    for i, v in enumerate(a["vars"]):
        if i in removed:
            d = removed[i]
            reverse.append(expression(F(d["constant"]),
                                     {b["var_index"][n]: F(c) for n, c in d["coefficients"].items()}))
        else:
            reverse.append(expression(0, {b["var_index"][v["name"]]: 1}))
    assert a["objective"] == b["objective"] == expression()

    proof, f, r = make_proof(a, b)
    p = f
    graph = {}
    for d in h["affine_relations"]:
        x, y = a["var_index"][d["x"]], a["var_index"][d["y"]]
        s, t = F(d["sign"]), F(d["offset"])
        assert s in (F(1), F(-1))
        rr = [row_ref(a, n) for n in d["rows"]]
        if len(rr) == 1:
            ref = rr[0]
            assert p.kind(ref) == "Eq"
        else:
            assert len(rr) == 2
            ref = p.eqpair(rr[0], rr[1])
        scale = 1 / p.refexpr(ref)[1][x]
        ref = fact(p, "Eq", expression(-t, {x: 1, y: -s}), [[ref, scale]])
        graph.setdefault(y, []).append((x, s, t, ref, F(1)))
        graph.setdefault(x, []).append((y, s, -s * t, ref, -s))
    eq = {}
    component_members = set()
    for d in h["affine_components"]:
        root = a["var_index"][d["root"]]
        members = {a["var_index"][n] for n in d["members"]}
        assert not (component_members & members)
        component_members |= members
        local = {root: (F(1), F(0), None)}
        pending = [root]
        while pending:
            parent = pending.pop()
            ps, pt, pref = local[parent]
            for child, s, t, ref, scale in graph[parent]:
                if child in local:
                    continue
                assert child in members
                cs, ct = s * ps, s * pt + t
                terms = [[ref, scale]] + ([[pref, s]] if pref is not None else [])
                got = fact(p, "Eq", expression(-ct, {child: 1, root: -cs}), terms)
                local[child] = (cs, ct, got)
                pending.append(child)
        assert set(local) == members
        lower, upper = map(F, d["root_bounds"])
        root_fixed = None
        if lower == upper:
            bounds = []
            for typ, witness in (("VarUpper", d["upper_witness"]), ("VarLower", d["lower_witness"])):
                i = a["var_index"][witness]
                s, t, ref = local[i]
                upper_side = typ == "VarUpper"
                source_upper = upper_side == (s > 0)
                bound_ref = {"VarUpper" if source_upper else "VarLower": i}
                terms = [[bound_ref, F(1)]]
                if ref is not None:
                    terms.append([ref, F(-1 if source_upper else 1)])
                wanted = expression(-upper, {root: 1}) if upper_side else expression(lower, {root: -1})
                bounds.append(fact(p, "Le", wanted, terms))
            root_fixed = p.eqpair(bounds[0], bounds[1])
        else:
            assert root not in removed and a["vars"][root]["lower"] == lower and a["vars"][root]["upper"] == upper
        for i, (s, t, ref) in local.items():
            if i not in removed:
                continue
            desired = plus(expression(0, {i: 1}), substitute(reverse[i], forward), -1)
            terms = ([[ref, F(1)]] if ref is not None else []) + \
                ([[root_fixed, s]] if root_fixed is not None else [])
            eq[i] = fact(p, "Eq", desired, terms)
    for i, v in enumerate(a["vars"]):
        if i not in removed or i in eq:
            continue
        if v["lower"] is not None and v["lower"] == v["upper"]:
            eq[i] = p.eqpair({"VarUpper": i}, {"VarLower": i})
            assert p.refexpr(eq[i]) == plus(expression(0, {i: 1}), substitute(reverse[i], forward), -1)
    for n, d in h["leaf_definitions"].items():
        i = a["var_index"][n]
        assert i not in eq
        ref = row_ref(a, d["row"])
        raw = p.refexpr(ref)
        scale = 1 / raw[1][i]
        terms = [[ref, scale]]
        for j, c in raw[1].items():
            if j != i and j in removed:
                terms.append([eq[j], -c * scale])
        eq[i] = fact(p, "Eq", plus(expression(0, {i: 1}), substitute(reverse[i], forward), -1), terms)
    assert set(eq) == set(removed)

    checks = []
    for i, v in enumerate(b["vars"]):
        e = forward[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            checks.append({typ: next(iter(e[1]))})
            assert f.refexpr(checks[-1]) == wanted
        if v["integer"]:
            checks.append(fact(f, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in b["rows"]:
        n = row["name"]
        typ = next(iter(row_ref(b, n)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), forward)
        ref = row_ref(a, n)
        terms = [[ref, F(1)]] + [[eq[i], -c] for i, c in f.refexpr(ref)[1].items() if i in eq]
        checks.append(fact(f, kind, wanted, terms, terminal=True))
    assert plus(substitute(b["objective"], forward), a["objective"], -1) == expression()
    checks.append("Exact")
    f.finish(forward, checks)

    checks = []
    for i, v in enumerate(a["vars"]):
        e = reverse[i]
        for typ, value, sign in (("VarLower", v["lower"], -1), ("VarUpper", v["upper"], 1)):
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            checks.append(box(r, wanted, True))
        if v["integer"]:
            checks.append(fact(r, "Int", e, [[{"VarInt": j}, c] for j, c in e[1].items()], e[0], True))
    for row in a["rows"]:
        n = row["name"]
        typ = next(iter(row_ref(a, n)))
        kind = "Eq" if typ == "RowEq" else "Le"
        wanted = substitute(row_fact(row, typ), reverse)
        if n in b["row_index"]:
            ref = row_ref(b, n)
            assert r.refexpr(ref) == wanted
            check = ref
        elif exact(kind, wanted):
            check = "Exact"
        elif kind == "Le":
            check = box(r, wanted, True)
        else:
            check = r.eqpair(box(r, wanted), box(r, mul(wanted, -1)))
        checks.append(check)
    assert plus(substitute(a["objective"], reverse), b["objective"], -1) == expression()
    checks.append("Exact")
    r.finish(reverse, checks)

    return proof, {
        "source_variables": len(a["vars"]),
        "target_variables": len(b["vars"]),
        "source_rows": len(a["rows"]),
        "target_rows": len(b["rows"]),
        "affine_relations": len(h["affine_relations"]),
        "affine_components": len(h["affine_components"]),
        "eliminated_variables": len(removed),
        "leaf_sums": len(h["leaf_definitions"]),
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test75-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test75"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / "input/model.mps"
    target = run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test75", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test75", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
