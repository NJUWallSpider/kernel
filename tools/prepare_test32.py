#!/usr/bin/env python3
"""Native test32: binary one-hot exclusions and complete zero-extension proof."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import fact, box
from prepare_native import compile_case, make_proof, sha


def cases_zero(builder, variable, right):
    wanted = expression(0, {variable: 1})

    def zero_branch(child, assumption):
        witness = child.eqpair(assumption, {"VarLower": variable})
        assert child.refexpr(witness) == wanted
        return {"Witness": witness}

    def one_branch(child, assumption):
        contradiction = right(child, assumption)
        residual = child.refexpr(contradiction)
        assert child.kind(contradiction) == "Le" and not residual[1] and residual[0] > 0
        return {"Absurd": contradiction}

    return builder.cases("Eq", wanted, wanted, {"VarInt": variable},
                         zero_branch, one_branch)


def prepare(a, b, h):
    assert (len(a["vars"]), len(a["rows"]), len(b["vars"]), len(b["rows"])) == (18380, 576, 4792, 382)
    common = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    relaxed = set(h["relaxed_integer_variables"])
    removed = {i for i, v in enumerate(a["vars"]) if v["name"] not in b["var_index"]}
    for i, j in common:
        av, bv = a["vars"][i], b["vars"][j]
        assert av["name"] == bv["name"] and av["lower"] == bv["lower"] and av["upper"] == bv["upper"]
        assert av["integer"] and bv["integer"] == (bv["name"] not in relaxed)
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression() if i in removed else
               expression(0, {b["var_index"][v["name"]]: 1})
               for i, v in enumerate(a["vars"])]

    proof, f, r = make_proof(a, b)
    zero = {}
    initial = {a["var_index"][n] for n in h["removed_original_fixed_zero"]}
    for i in sorted(initial):
        assert a["vars"][i]["lower"] == a["vars"][i]["upper"] == 0
        zero[i] = f.eqpair({"VarUpper": i}, {"VarLower": i})
    groups = {}
    group_of = {}
    definition = {}
    time_row = {}
    tree_cache = {}
    tree_count = 0
    for g in h["choice_groups"]:
        ref = row_ref(a, g["onehot_row"])
        e = f.refexpr(ref)
        assert e[0] == -1 and all(c == 1 for c in e[1].values())
        members = sorted(set(e[1]) - initial)
        assert members
        for i in members:
            assert i not in group_of and a["vars"][i]["integer"]
            assert a["vars"][i]["lower"] == 0 and a["vars"][i]["upper"] == 1
            group_of[i] = g["job"]
        reduced = f.lin("Eq", [[ref, 1]] + [[zero[i], -1] for i in e[1] if i in initial],
                        expression(-1, {i: 1 for i in members}))
        groups[g["job"]] = (members, reduced, {i: p for p, i in enumerate(members)})
        for rn, vn in [(g["start_row"], g["start_variable"]),
                       (g["completion_row"], g["completion_variable"])]:
            t = a["var_index"][vn]
            ref = row_ref(a, rn)
            e = f.refexpr(ref)
            assert e[0] == 0 and e[1][t] == -1
            assert set(e[1]) - {t} <= set(a["rows"][a["row_index"][g["onehot_row"]]]["terms"])
            # Normalize the actual defining row to T-sum c*x=0 and remove FX zeros.
            desired = expression(0, {i: -c for i, c in e[1].items() if i not in initial})
            d = f.lin("Eq", [[ref, -1]] +
                      [[zero[i], c] for i, c in e[1].items() if i in initial], desired)
            coefficients = {i: -desired[1].get(i, F(0)) for i in members}
            definition[t] = (d, coefficients, min(coefficients.values()), max(coefficients.values()))
            time_row[vn] = rn

    def weighted_subset(t, side, members, lo, hi):
        nonlocal tree_count
        key = t, side, lo, hi
        if key in tree_cache:
            return tree_cache[key]
        _, coefficients, minimum, maximum = definition[t]
        if hi - lo == 1:
            i = members[lo]
            w = coefficients[i] - minimum if side == "above" else maximum - coefficients[i]
            ref = None if not w else {"VarLower": i} if w == 1 else f.lin("Le", [[{"VarLower": i}, w]])
        else:
            mid = (lo + hi) // 2
            left = weighted_subset(t, side, members, lo, mid)
            right = weighted_subset(t, side, members, mid, hi)
            ref = right if left is None else left if right is None else f.lin("Le", [[left, 1], [right, 1]])
        tree_cache[key] = ref
        tree_count += 1
        return ref

    def all_except(t, side, members, position, lo, hi):
        if position < lo or position >= hi:
            r = weighted_subset(t, side, members, lo, hi)
            return [] if r is None else [[r, 1]]
        if hi - lo == 1:
            return []
        mid = (lo + hi) // 2
        return (all_except(t, side, members, position, lo, mid) +
                all_except(t, side, members, position, mid, hi))

    for name, witnesses in h["removed_onehot_bound_excluded"].items():
        i = a["var_index"][name]
        assert i not in zero
        members, onehot, positions = groups[group_of[i]]
        vn, side, cvalue, bvalue = witnesses[0]
        t = a["var_index"][vn]
        d, coefficients, minimum, maximum = definition[t]
        cv = coefficients[i]
        assert cv == F(cvalue)
        if side == "above":
            bound = a["vars"][t]["upper"]
            assert bound == F(bvalue) and cv > bound
            terms = [[d, -1], [onehot, -minimum], [{"VarUpper": t}, 1]]
            k = cv - minimum
            contradiction = cv - bound
        else:
            assert side == "below"
            bound = a["vars"][t]["lower"]
            assert bound == F(bvalue) and cv < bound
            terms = [[d, 1], [onehot, maximum], [{"VarLower": t}, 1]]
            k = maximum - cv
            contradiction = bound - cv
        terms += all_except(t, side, members, positions[i], 0, len(members))
        zero[i] = cases_zero(f, i, lambda child, assumption:
                             child.lin("Le", terms + [[assumption, k]],
                                       expression(contradiction)))
    assert set(zero) == removed and len(initial) == 7282 and len(zero) - len(initial) == 6306

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        time_integer = {}
        duration = {}
        if back:
            for g in h["choice_groups"]:
                for rn, vn in [(g["start_row"], g["start_variable"]),
                               (g["completion_row"], g["completion_variable"])]:
                    t = b["var_index"][vn]
                    ref = row_ref(b, rn)
                    e = builder.refexpr(ref)
                    assert e[0] == 0 and e[1][t] == -1
                    time_integer[t] = builder.lin(
                        "Int", [[ref, -1]] +
                        [[{"VarInt": j}, c] for j, c in e[1].items() if j != t],
                        expression(0, {t: 1}))
                start = row_ref(b, g["start_row"])
                completion = row_ref(b, g["completion_row"])
                raw = plus(builder.refexpr(completion), builder.refexpr(start), -1)
                s = b["var_index"][g["start_variable"]]
                c = b["var_index"][g["completion_variable"]]
                assert raw[1][s] == 1 and raw[1][c] == -1
                weights = {j: q for j, q in raw[1].items() if j not in (s, c)}
                assert all(q > 0 for q in weights.values())
                duration[g["job"]] = builder.lin(
                    "Le", [[completion, 1], [start, -1]] +
                    [[{"VarLower": j}, q] for j, q in weights.items()],
                    expression(0, {s: 1, c: -1}))
        for i, v in enumerate(out["vars"]):
            e = mapping[i]
            for value, sign in [(v["lower"], -1), (v["upper"], 1)]:
                if value is not None:
                    checks.append(box(builder, plus(mul(e, sign), expression(-sign * value)), True))
            if v["integer"]:
                if back and e[1] and next(iter(e[1])) in time_integer:
                    check = time_integer[next(iter(e[1]))]
                else:
                    check = fact(builder, "Int", e,
                                 [[{"VarInt": j}, q] for j, q in e[1].items()], e[0], True)
                checks.append(check)
        for row in out["rows"]:
            rn = row["name"]
            typ = next(iter(row_ref(out, rn)))
            kind = "Eq" if typ == "RowEq" else "Le"
            wanted = substitute(row_fact(row, typ), mapping)
            if not back:
                ref = row_ref(a, rn)
                check = fact(builder, kind, wanted,
                             [[ref, 1]] +
                             [[zero[i], -c] for i, c in builder.refexpr(ref)[1].items()
                              if i in removed], terminal=True)
            elif rn in b["row_index"]:
                check = row_ref(b, rn)
                assert builder.refexpr(check) == wanted
            elif rn in h["removed_capacity_rows"]:
                ref = row_ref(b, h["removed_capacity_rows"][rn])
                delta = plus(wanted, builder.refexpr(ref), -1)
                check = builder.lin("Le", [[ref, 1], [box(builder, delta), 1]], wanted)
            else:
                witness = h["removed_precedence_rows"][rn]
                assert witness["type"] == "retained_path"
                check = builder.lin("Le", [[row_ref(b, n), 1] for n in witness["rows"]] +
                                    [[duration[j], 1] for j in witness["jobs"][1:-1]], wanted)
            checks.append(check)
        wanted = plus(substitute(out["objective"], mapping), inp["objective"], -1)
        assert wanted == expression()
        checks.append("Exact")
        builder.finish(mapping, checks)
    return proof, {
        "source_variables": 18380, "target_variables": 4792,
        "source_rows": 576, "target_rows": 382,
        "original_fixed_zero": 7282, "binary_onehot_exclusions": 6306,
        "restored_time_integrality": 60, "removed_capacity_rows": 168,
        "removed_precedence_rows": 26, "weighted_subset_nodes": tree_count,
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test32-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test32"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test32", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test32", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
