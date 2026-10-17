#!/usr/bin/env python3
"""Native test69 normalization through simultaneous real intervals.

The legacy three-claim layout collapses to the two integer MI-OPT directions;
the reverse LP recovery claim is not part of the current kernel contract.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test54 import fact, box, exact
from prepare_test48 import lift, emit_checks, int_witness, sumexpr
from prepare_native import compile_case, make_proof


def cases_le(b, desired, var, left, right):
    split = expression(0, {var: 1})

    def branch(callback):
        def visit(child, assumption):
            ref = callback(child, assumption)
            assert child.kind(ref) == "Le" and child.refexpr(ref) == desired
            return ref
        return visit

    return b.cases("Le", desired, split, {"VarInt": var},
                   branch(left), branch(right))


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (11697, 16381, 8697, 8885)
    common = [[i, b["var_index"][v["name"]]] for i, v in enumerate(a["vars"])
              if v["name"] in b["var_index"]]
    assert len(common) == 7197 and sum(a["vars"][i]["integer"] for i, j in common) == 7196
    for i, j in common:
        assert a["vars"][i] == b["vars"][j]
    proof, f, r = make_proof(a, b)
    graph = {}
    anchoreq = {}
    components = {}
    for w in h["equality_pair_witnesses"]:
        i, j = a["var_index"][w["positive_variable"]], a["var_index"][w["negative_variable"]]
        ref = f.eqpair(row_ref(a, w["forward_row"]), row_ref(a, w["reverse_row"]))
        scale = 1 / f.refexpr(ref)[1][i]
        ref = fact(f, "Eq", expression(-F(w["difference"]), {i: 1, j: -1}), [[ref, scale]])
        graph.setdefault(i, []).append((j, ref, F(-1)))
        graph.setdefault(j, []).append((i, ref, F(1)))
    for component in h["equality_components"]:
        root = a["var_index"][component["root"]]
        offsets = {a["var_index"][n]: F(v) for n, v in component["variables"].items()}
        assert offsets[root] == 0
        seen = {root}
        pending = [root]
        anchoreq[root] = None
        while pending:
            parent = pending.pop()
            for child, ref, c in graph[parent]:
                if child in seen:
                    continue
                assert child in offsets
                seen.add(child)
                pending.append(child)
                terms = [[ref, c]] + ([[anchoreq[parent], F(1)]]
                                      if anchoreq[parent] is not None else [])
                anchoreq[child] = fact(f, "Eq", expression(-offsets[child], {child: 1, root: -1}),
                                       terms)
        assert seen == set(offsets)
        components.update({i: (root, c) for i, c in offsets.items()})
    assert len(components) == 1500
    intervals = []
    endpoints = {}
    placements = {}
    for n, w in enumerate(h["intervals"]):
        lo, up, anchor = [a["var_index"][w[k]] for k in ("lower", "upper", "anchor")]
        length = F(w["length"])
        assert lo not in endpoints and up not in endpoints
        lower = [expression(), expression(length, {lo: 1, anchor: -1})]
        upper = [expression(length), expression(0, {up: 1, anchor: -1})]
        sources = [row_ref(a, v) for v in w["contain_rows"] + [w["length_row"]]]
        checks = []
        for le in lower:
            for ue in upper:
                e = plus(le, ue, -1)
                if exact("Le", e):
                    checks.append("Exact")
                else:
                    matches = [ref for ref in sources if f.refexpr(ref) == e]
                    assert len(matches) == 1
                    checks.append(matches[0])
        intervals.append({"lower": lower, "upper": upper, "checks": checks})
        endpoints[lo] = (n, "lower", anchor, length)
        endpoints[up] = (n, "upper", anchor, length)
        placements[b["var_index"][w["new_variable"]]] = n
    assert len(endpoints) == 3000 and set(endpoints).isdisjoint(components)
    p = lift(f, "intervals", intervals)
    layout = p.old_layout
    forward = [None] * len(b["vars"])
    domains = {}
    for i, j in common:
        forward[j] = expression(0, {i: 1})
        domains[i] = {"VarLower": {"VarLower": i}, "VarUpper": {"VarUpper": i},
                      "VarInt": {"VarInt": i}}
    for j, n in placements.items():
        v = layout[n]["variable"]
        forward[j] = expression(0, {v: 1})
        domains[v] = {"VarLower": {"RowLower": layout[n]["lower"][0]},
                      "VarUpper": {"RowUpper": layout[n]["upper"][0]}}
        assert b["vars"][j]["lower"] == 0
        assert b["vars"][j]["upper"] == F(h["intervals"][n]["length"])
        assert not b["vars"][j]["integer"]
    assert all(e is not None for e in forward)
    changes = {x["row"]: x for x in h["indicator_tightening"]}
    assert len(changes) == 6446

    def normalized(n):
        ref = row_ref(a, n)
        e = p.refexpr(ref)
        terms = [[ref, F(1)]]
        for i, c in list(e[1].items()):
            if i not in endpoints:
                continue
            k, which, anchor, length = endpoints[i]
            if which == "lower":
                assert c <= 0
                lref = {"RowLower": layout[k]["lower"][1]}
                scale = -c
            else:
                assert c >= 0
                lref = {"RowUpper": layout[k]["upper"][1]}
                scale = c
            terms.append([lref, scale])
            e = plus(e, p.refexpr(lref), scale)
        for i, c in list(e[1].items()):
            if i not in anchoreq or anchoreq[i] is None:
                continue
            terms.append([anchoreq[i], -c])
            e = plus(e, p.refexpr(anchoreq[i]), -c)
        assert not (set(e[1]) & set(components)), ("translation residual", n, e)
        return e, terms

    def frow(i, wanted):
        name = b["rows"][i]["name"]
        old, terms = normalized(name)
        if name not in changes:
            assert old == wanted
            return terms
        w = changes[name]
        binary = a["var_index"][w["binary"]]
        assert plus(old, expression(1, {binary: -1})) == wanted
        oldref = fact(p, "Le", old, terms)

        def inactive(child, assumption):
            remaining = expression(wanted[0], {j: c for j, c in wanted[1].items()
                                               if j != binary})
            terms = []
            ceiling = remaining[0]
            for j, c in remaining[1].items():
                typ = "VarUpper" if c > 0 else "VarLower"
                ref = domains[j][typ]
                terms.append([ref, abs(c)])
                bound = -child.refexpr(ref)[0] if c > 0 else child.refexpr(ref)[0]
                ceiling += c * bound
            assert ceiling <= 0 and wanted[1][binary] > 0
            terms.append([assumption, wanted[1][binary]])
            return fact(child, "Le", wanted, terms, ceiling)

        return cases_le(p, wanted, binary, inactive,
                        lambda child, assumption: fact(
                            child, "Le", wanted, [[oldref, F(1)], [assumption, F(1)]]))

    forward_checks = emit_checks(p, b, forward, "Eq",
                                 rows={i: frow(i, substitute(
                                     row_fact(row, next(iter(row_ref(b, row["name"])))),
                                     forward)) for i, row in enumerate(b["rows"])},
                                 domains=domains)
    p.finish(forward, forward_checks)

    reverse = []
    for v in a["vars"]:
        x = h["expansion_map"][v["name"]]
        terms = {b["var_index"][x["variable"]]: F(1)} if x.get("variable") is not None else {}
        reverse.append(expression(F(x["constant"]), terms))
    assert substitute(a["objective"], reverse) == b["objective"]
    rdomains = {}
    rrows = {}
    for i, var in enumerate(a["vars"]):
        e = reverse[i]
        if var["name"] in b["var_index"]:
            j = b["var_index"][var["name"]]
            rdomains[(i, "VarLower")] = {"VarLower": j}
            rdomains[(i, "VarUpper")] = {"VarUpper": j}
        else:
            for typ, sign in [("VarLower", -1), ("VarUpper", 1)]:
                expected = plus(mul(e, sign), expression(-sign * var["lower" if sign == -1 else "upper"]))
                rdomains[(i, typ)] = ("Exact" if exact("Le", expected)
                                      else box(r, expected))
        if var["integer"]:
            rdomains[(i, "VarInt")] = int_witness(r, e)
    bnames = b["row_index"]
    for i, row in enumerate(a["rows"]):
        name = row["name"]
        typ = next(iter(row_ref(a, name)))
        wanted = substitute(row_fact(row, typ), reverse)
        if name not in bnames:
            rrows[i] = "Exact" if exact("Le", wanted) else box(r, wanted)
        else:
            terms = [[row_ref(b, name), F(1)]]
            if name in changes:
                terms.append([{"VarUpper": b["var_index"][changes[name]["binary"]]}, F(1)])
            rrows[i] = r.prove("Le", wanted, terms)
    reverse_checks = emit_checks(r, a, reverse, "Eq", rows=rrows, domains=rdomains)
    r.finish(reverse, reverse_checks)
    counts = {"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
              "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
              "simultaneous_intervals": len(intervals),
              "affine_component_variables": len(components),
              "tightened_gates": len(changes), "preserved_original_binaries": 7196,
              "claims": 2,
              "obligations_by_claim": [len(forward_checks), len(reverse_checks)]}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test69-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test69"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test69", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test69", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
