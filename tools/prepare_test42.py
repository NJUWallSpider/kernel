#!/usr/bin/env python3
"""Native test42 full activation-prefix aggregation with MI-OPT directions."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test88 import fix_binary
from prepare_test54 import fact, box
from prepare_native import compile_case, make_proof, sha


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (167056, 169576, 167056, 3076)
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression(0, {b["var_index"][v["name"]]: 1}) for v in a["vars"]]
    fixed = {a["var_index"][d["variable"]] for d in h["edits"]["bound_changes"]}
    assert len(fixed) == 189
    for i, j in common:
        av, bv = a["vars"][i], b["vars"][j]
        assert av["integer"] and bv["integer"]
        assert av["lower"] == 0 and av["upper"] == 1 and bv["upper"] == 1
        assert bv["lower"] == (1 if i in fixed else 0)
    changes = {d["row"]: d for d in h["edits"]["modified_group_rows"]}
    deleted = set(a["row_index"]) - set(b["row_index"])
    assert len(deleted) == 166500
    links = {}
    link_by_row = {}
    for rn in deleted:
        row = a["rows"][a["row_index"][rn]]
        assert row["sense"] == "G" and row["rhs"] == 0 and len(row["terms"]) == 2
        x = next(i for i, c in row["terms"].items() if c == -1)
        y = next(i for i, c in row["terms"].items() if c == 1)
        assert x not in links
        links[x] = (y, rn)
        link_by_row[rn] = (x, y)
    group_for_x = {}
    groups = {}
    for row in a["rows"]:
        if (row["sense"] == "L" and row["rhs"] == 1 and len(row["terms"]) == 100 and
                all(c == 1 for c in row["terms"].values()) and
                all(i in links for i in row["terms"])):
            members = sorted(row["terms"])
            ys = {links[i][0] for i in members}
            assert len(ys) == 1
            y = next(iter(ys))
            groups[row["name"]] = (members, y)
            for i in members:
                assert i not in group_for_x
                group_for_x[i] = row["name"]
    assert len(groups) == 1665 and set(group_for_x) == set(links)

    proof, f, r = make_proof(a, b)
    hint = h["certificates"]["objective_bound"]
    ys = [a["var_index"][n] for n in hint["result_coefficients"]["variables"]]
    assert len(ys) == 556 and set(ys[:189]) == fixed
    terms = ([[row_ref(a, n), F(1, 4)] for n in hint["capacity_rows"]] +
             [[row_ref(a, d["row"]), -F(d["multiplier"], 4)] for d in hint["subtract_equalities"]])
    demand = f.lin("Le", terms, expression(F(753, 4), {i: -1 for i in ys}))
    chain = [row_ref(a, n) for n in hint["chain_rows"]]
    for j, ref in enumerate(chain):
        assert f.refexpr(ref) == expression(0, {ys[j + 1]: 1, ys[j]: -1})
    pivot = ys[188]

    def impossible(child, assumption):
        terms = ([[demand, F(1)]] +
                 [[{"VarUpper": i}, F(1)] for i in ys[:188]] +
                 [[chain[k], F(555 - k)] for k in range(188, 555)] +
                 [[assumption, F(368)]])
        return {"Absurd": child.lin("Le", terms, expression(F(1, 4)))}

    def last_witness(child, assumption):
        return {"Witness": fix_binary(child, pivot, F(1), assumption)}

    last_fixed = f.cases("Eq", expression(-1, {pivot: 1}),
                         expression(0, {pivot: 1}), {"VarInt": pivot},
                         impossible, last_witness)
    fixed_eq = {pivot: last_fixed}
    for j in range(188):
        lower = f.lin("Le", [[chain[k], F(1)] for k in range(j, 188)] +
                      [[last_fixed, F(-1)]], expression(1, {ys[j]: -1}))
        fixed_eq[ys[j]] = f.eqpair({"VarUpper": ys[j]}, lower)
    aggregate = {}
    for rn, d in changes.items():
        members, y = groups[rn]
        wanted = substitute(row_fact(b["rows"][b["row_index"][rn]], "RowUpper"), forward)
        assert wanted == expression(0, {**{i: 1 for i in members}, y: -1})

        def left(child, assumption):
            return child.lin("Le", [[row_ref(a, links[i][1]), F(1)] for i in members] +
                             [[assumption, F(99)]], wanted)

        def right(child, assumption):
            return child.lin("Le", [[row_ref(a, rn), F(1)], [assumption, F(1)]], wanted)

        aggregate[rn] = f.cases("Le", wanted, expression(0, {y: 1}),
                                {"VarInt": y}, left, right)

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        restored = {}
        if back:
            # Every leaf link follows through checked subset bounds. Shared binary
            # trees avoid expanding all other 99 members for every leaf.
            for rn, (source_members, sy) in groups.items():
                if sy in fixed:
                    continue
                members = [b["var_index"][a["vars"][i]["name"]] for i in source_members]
                y = b["var_index"][a["vars"][sy]["name"]]
                negative = {}

                def nonpositive(lo, hi):
                    if hi - lo == 1:
                        return {"VarLower": members[lo]}
                    key = (lo, hi)
                    if key not in negative:
                        mid = (lo + hi) // 2
                        negative[key] = builder.lin("Le", [[nonpositive(lo, mid), F(1)],
                                                           [nonpositive(mid, hi), F(1)]])
                    return negative[key]

                def descend(lo, hi, upper):
                    if hi - lo == 1:
                        restored[links[source_members[lo]][1]] = upper
                        return
                    mid = (lo + hi) // 2
                    left = builder.lin("Le", [[upper, F(1)], [nonpositive(mid, hi), F(1)]],
                                       expression(0, {**{members[k]: 1 for k in range(lo, mid)}, y: -1}))
                    right = builder.lin("Le", [[upper, F(1)], [nonpositive(lo, mid), F(1)]],
                                        expression(0, {**{members[k]: 1 for k in range(mid, hi)}, y: -1}))
                    descend(lo, mid, left)
                    descend(mid, hi, right)

                descend(0, len(members), row_ref(b, rn))
        for i, v in enumerate(out["vars"]):
            j = next(iter(mapping[i][1]))
            if not back and j in fixed:
                checks.append(fact(builder, "Le", expression(1, {j: -1}), [[fixed_eq[j], F(-1)]]))
            else:
                checks.append(box(builder, expression(v["lower"], {j: -1}), True))
            checks.append({"VarUpper": j})
            checks.append({"VarInt": j})
        for row in out["rows"]:
            rn = row["name"]
            typ = next(iter(row_ref(out, rn)))
            wanted = substitute(row_fact(row, typ), mapping)
            if not back and rn in aggregate:
                check = aggregate[rn]
                assert builder.refexpr(check) == wanted
            elif back and rn in deleted:
                x, y = link_by_row[rn]
                if y in fixed:
                    tx = b["var_index"][a["vars"][x]["name"]]
                    ty = b["var_index"][a["vars"][y]["name"]]
                    check = fact(builder, "Le", wanted,
                                 [[{"VarUpper": tx}, F(1)], [{"VarLower": ty}, F(1)]])
                else:
                    check = restored[rn]
                    assert builder.refexpr(check) == wanted
            elif back and rn in changes:
                y = b["var_index"][a["vars"][groups[rn][1]]["name"]]
                check = fact(builder, "Le", wanted,
                             [[row_ref(b, rn), F(1)], [{"VarUpper": y}, F(1)]])
            else:
                check = row_ref(inp, rn)
                assert builder.refexpr(check) == wanted
            checks.append(check)
        assert substitute(out["objective"], mapping) == inp["objective"]
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 167056, "target_variables": 167056,
        "source_rows": 169576, "target_rows": 3076,
        "fixed_activation_prefix": 189, "strengthened_groups": 1101,
        "restored_individual_links": 166500, "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test42-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test42"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test42", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test42", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
