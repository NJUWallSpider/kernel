#!/usr/bin/env python3
"""Native test34 one-hot weighted aggregation through balanced local Cases."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import csv
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_native import compile_case, make_proof, sha


def forward_tree(p, members, weights):
    if len(members) == 1:
        i = members[0]
        w = weights.get(i, F(0))
        return {"members": members, "sum": expression(0, {i: 1}),
                "weights": expression(0, {i: w}), "maximum": w,
                "nonnegative": {"VarLower": i}, "integer": {"VarInt": i},
                "complement": None}
    mid = len(members) // 2
    left = forward_tree(p, members[:mid], weights)
    right = forward_tree(p, members[mid:], weights)
    maximum = max(left["maximum"], right["maximum"])
    summed = plus(left["sum"], right["sum"])
    weighted = plus(left["weights"], right["weights"])
    terms = [[{"VarLower": i}, maximum - weights.get(i, F(0))]
             for i in members if maximum != weights.get(i, F(0))]
    return {"members": members, "sum": summed, "weights": weighted, "maximum": maximum,
            "nonnegative": p.lin("Le", [[left["nonnegative"], 1], [right["nonnegative"], 1]],
                                 mul(summed, -1)),
            "integer": p.lin("Int", [[left["integer"], 1], [right["integer"], 1]], summed),
            "complement": p.lin("Le", terms) if terms else None,
            "left": left, "right": right}


def weighted_zero(p, node, zero):
    terms = [] if not node["maximum"] else [[zero, node["maximum"]]]
    if node["complement"] is not None:
        terms.append([node["complement"], 1])
    return p.lin("Le", terms, node["weights"])


def aggregate_cases(p, node, selected, z, individual):
    wanted = plus(node["weights"], expression(0, {z: -1}))
    if "left" not in node:
        i = node["members"][0]
        ref = individual.get(i, {"VarLower": z})
        assert p.refexpr(ref) == wanted
        return ref
    left, right = node["left"], node["right"]
    split = left["sum"]

    def zero_side(child, assumption):
        zero = child.eqpair(assumption, left["nonnegative"])
        chosen = child.lin("Eq", [[selected, 1], [zero, -1]],
                           plus(right["sum"], expression(-1)))
        subbound = aggregate_cases(child, right, chosen, z, individual)
        other = weighted_zero(child, left, zero)
        return child.lin("Le", [[subbound, 1], [other, 1]], wanted)

    def one_side(child, assumption):
        upper = child.lin("Le", [[selected, 1], [right["nonnegative"], 1]],
                          plus(left["sum"], expression(-1)))
        chosen = child.eqpair(upper, assumption)
        zero = child.lin("Eq", [[selected, 1], [chosen, -1]], right["sum"])
        subbound = aggregate_cases(child, left, chosen, z, individual)
        other = weighted_zero(child, right, zero)
        return child.lin("Le", [[subbound, 1], [other, 1]], wanted)

    return p.cases("Le", wanted, split, left["integer"], zero_side, one_side)


def reverse_tree(p, members, weights):
    if len(members) == 1:
        i = members[0]
        w = weights.get(i, F(0))
        wanted = expression(0, {i: -w})
        terms = [] if not w else [[{"VarLower": i}, w]]
        ref = p.lin("Le", terms, wanted)
        return {"members": members, "negative": ref, "weights": mul(wanted, -1)}
    mid = len(members) // 2
    left = reverse_tree(p, members[:mid], weights)
    right = reverse_tree(p, members[mid:], weights)
    weighted = plus(left["weights"], right["weights"])
    return {"members": members, "weights": weighted,
            "negative": p.lin("Le", [[left["negative"], 1], [right["negative"], 1]],
                              mul(weighted, -1)),
            "left": left, "right": right}


def split_upper(p, node, upper, z, result):
    if "left" not in node:
        result[node["members"][0]] = upper
        return
    left, right = node["left"], node["right"]
    l = p.lin("Le", [[upper, 1], [right["negative"], 1]],
              plus(left["weights"], expression(0, {z: -1})))
    r = p.lin("Le", [[upper, 1], [left["negative"], 1]],
              plus(right["weights"], expression(0, {z: -1})))
    split_upper(p, left, l, z, result)
    split_upper(p, right, r, z, result)


def prepare(a, b, h, manifest):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (53593, 106954, 53593, 53824)
    assert a["vars"] == b["vars"] and a["objective"] == b["objective"]
    z = a["var_index"]["z"]
    assert not a["vars"][z]["integer"] and a["vars"][z]["lower"] == 0
    changes = {d["original_row"]: d for d in manifest}
    aggregates = {d["row"]: d for d in h["aggregates"]}
    assert set(a["row_index"]) - set(b["row_index"]) == set(changes)
    assert set(b["row_index"]) - set(a["row_index"]) == set(aggregates)
    individual = {}
    zero_rows = set()
    for rn, d in changes.items():
        ref = row_ref(a, rn)
        e = row_fact(a["rows"][a["row_index"][rn]], "RowUpper")
        if d["action"] == "delete_redundant":
            assert e == expression(0, {z: -1})
            zero_rows.add(rn)
        else:
            assert d["action"] == "replace_with_group_aggregate"
            i = a["var_index"][d["variable"]]
            weight = F(d["exact_distance"])
            assert weight > 0 and e == expression(0, {i: weight, z: -1})
            assert i not in individual
            individual[i] = ref

    proof, f, r = make_proof(a, b)
    forward = {}
    reverse = {}
    all_members = set()
    maximum_depth = 0
    for rn, d in aggregates.items():
        onehot = row_ref(a, d["one_hot_row"])
        g = f.refexpr(onehot)
        assert g[0] == -1 and len(g[1]) == 231 and all(c == 1 for c in g[1].values())
        members = sorted(g[1])
        assert not all_members & set(members)
        all_members.update(members)
        for i in members:
            assert a["vars"][i]["integer"] and a["vars"][i]["lower"] == 0 and a["vars"][i]["upper"] == 1
        target = row_fact(b["rows"][b["row_index"][rn]], "RowUpper")
        assert target[0] == 0 and target[1][z] == -1 and set(target[1]) - {z} <= set(members)
        weights = {i: c for i, c in target[1].items() if i != z}
        assert len(weights) == 230 and all(c > 0 for c in weights.values())
        for i in members:
            if i in weights:
                assert f.refexpr(individual[i]) == expression(0, {i: weights[i], z: -1})
                change = changes[a["rows"][individual[i]["RowUpper"]]["name"]]
                assert change["replacement_row"] == rn and change["assignment_row"] == d["one_hot_row"]
            else:
                assert i not in individual
        node = forward_tree(f, members, weights)
        forward[rn] = aggregate_cases(f, node, onehot, z, individual)
        assert f.refexpr(forward[rn]) == target
        maximum_depth = max(maximum_depth, (len(members) - 1).bit_length())
        reverse_node = reverse_tree(r, members, weights)
        split_upper(r, reverse_node, row_ref(b, rn), z, reverse)
    assert len(all_members) == 53361 and len(zero_rows) == 231

    n = len(a["vars"])
    mapping = [expression(0, {i: 1}) for i in range(n)]
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = r if back else f
        checks = []
        for i, v in enumerate(out["vars"]):
            if v["lower"] is not None:
                checks.append({"VarLower": i})
            if v["upper"] is not None:
                checks.append({"VarUpper": i})
            if v["integer"]:
                checks.append({"VarInt": i})
        for row in out["rows"]:
            rn = row["name"]
            if not back and rn in forward:
                check = forward[rn]
            elif back and rn in changes:
                if rn in zero_rows:
                    check = {"VarLower": z}
                else:
                    check = reverse[a["var_index"][changes[rn]["variable"]]]
                assert builder.refexpr(check) == row_fact(row, "RowUpper")
            else:
                assert row == inp["rows"][inp["row_index"][rn]]
                check = row_ref(inp, rn)
            checks.append(check)
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 53593, "target_variables": 53593,
        "source_rows": 106954, "target_rows": 53824,
        "onehot_groups": 231, "exhaustive_choice_leaves": 53361,
        "local_integer_cases": 53130, "maximum_case_depth": maximum_depth,
        "deleted_zero_distance_rows": 231, "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test34-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test34"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    manifest = run / "output/row_changes.csv"
    with manifest.open() as stream:
        rows = list(csv.DictReader(stream))
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()), rows)
    record = compile_case(proof, args.out, case_id="test34", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "row_manifest": {"path": str(manifest), "sha256": sha(manifest)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test34", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
