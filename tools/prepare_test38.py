#!/usr/bin/env python3
"""Native test38 scalar certificate for the actual shared switch DAG (MI-OPT)."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test88 import fix_binary
from prepare_test54 import fact
from prepare_native import compile_case, make_proof, sha


def model(path):
    m = parse_mps(path)
    for v in m["vars"]:
        v["name"] = v["name"].strip('"')
    for r in m["rows"]:
        r["name"] = r["name"].strip('"')
    m["var_index"] = {v["name"]: i for i, v in enumerate(m["vars"])}
    m["row_index"] = {r["name"]: i for i, r in enumerate(m["rows"])}
    return m


def cases(builder, kind, desired, var, left, right):
    split = expression(0, {var: 1})

    def left_branch(child, assumption):
        ref = left(child, assumption)
        assert child.refexpr(ref) == desired and child.kind(ref) in (kind, "Eq")
        return {"Witness": ref}

    def right_branch(child, assumption):
        ref = right(child, assumption)
        assert child.refexpr(ref) == desired and child.kind(ref) in (kind, "Eq")
        return {"Witness": ref}

    return builder.cases(kind, desired, split, {"VarInt": var}, left_branch, right_branch)


def bound(b, e, terms=()):
    terms = [(ref, c) for ref, c in terms if c]
    res = e
    for ref, c in terms:
        res = plus(res, b.refexpr(ref), -c)
    for i, c in list(res[1].items()):
        ref = {"VarUpper": i} if c > 0 else {"VarLower": i}
        terms.append((ref, abs(c)))
        res = plus(res, b.refexpr(ref), -abs(c))
    assert not res[1] and res[0] <= 0, ("box bound unavailable", e, res)
    return b.lin("Le", terms, e, constant=res[0])


def key(e):
    return e[0], tuple(sorted(e[1].items()))


def prepare(a, b, h):
    nodes = h["original_nodes"]
    term = h["terminal_substitutions"]
    defs = h["new_definitions"]
    av = a["var_index"]
    bv = b["var_index"]
    fixed = av[h["budget_fixation"]["variable"]]
    retained = set(av) & set(bv)
    assert set(av) == retained | set(nodes) | set(term)
    assert set(bv) == retained | set(defs)
    assert all(v["lower"] == 0 and v["upper"] == 1 for v in a["vars"])

    def replacement(n):
        return {"constant": term[n]["value"]} if n in term else nodes[n]["replacement"]

    def symbolic(e, ids):
        return expression(F(e["constant"])) if "constant" in e else expression(0, {ids[e["variable"]]: 1})

    reps = {}
    for n, d in nodes.items():
        rep = d["replacement"]
        if "variable" not in rep:
            continue
        target = defs[rep["variable"]]
        if (replacement(d["first_child"]) != target["first_child"] or
                replacement(d["second_child"]) != target["second_child"] or
                F(d["q"]) != F(target["q"])):
            continue
        if ((target["kind"] == "switch" and d["selector"] == target["selector"]) or
                (target["kind"] == "mix" and av[d["selector"]] == fixed)):
            reps.setdefault(rep["variable"], n)
    assert set(reps) == set(defs)
    fi = {n: av[r] for n, r in reps.items()}
    forward = [expression(0, {av[v["name"]]: 1}) if v["name"] in retained
               else expression(0, {fi[v["name"]]: 1}) for v in b["vars"]]
    reverse = [expression(0, {bv[v["name"]]: 1}) if v["name"] in retained
               else symbolic(replacement(v["name"]), bv) for v in a["vars"]]
    canon = {n: substitute(symbolic(replacement(n), bv), forward)
             for n in list(term) + list(nodes)}

    proof, f, r = make_proof(a, b)
    alias = {}
    visiting = set()
    # The actual full budget plus every other nonnegative selector proves fixation.
    budget = row_ref(a, "budget")
    be = f.refexpr(budget)
    c = be[1][fixed]
    upper = f.lin("Le", [(budget, 1 / c)] +
                  [({"VarLower": i}, q / c) for i, q in be[1].items() if i != fixed],
                  expression(be[0] / c, {fixed: 1}))
    assert all(q > 0 for q in be[1].values()) and 0 <= -be[0] / c < 1
    upper_expr = f.refexpr(upper)
    assert upper_expr[1] == {fixed: upper_expr[1][fixed]}
    assert upper_expr[1][fixed] == 1
    delta = upper_expr[0]
    ceiling = -((-delta.numerator) // delta.denominator)
    expected = expression(ceiling, {fixed: 1})
    assert expected == expression(0, {fixed: 1})
    rounded_fact = f.round(upper, {"VarInt": fixed})
    assert f.refexpr(rounded_fact) == expected
    fixed_eq = f.eqpair(rounded_fact, {"VarLower": fixed})

    for n, d in term.items():
        ref = row_ref(a, d["defining_row"])
        assert f.kind(ref) == "Eq"
        assert f.refexpr(ref) == plus(expression(0, {av[n]: 1}), canon[n], -1)
        alias[n] = ref

    def norm(builder, n, sel_eq, value):
        d = nodes[n]
        q = F(d["q"])
        weights = ([(d["first_child"], F(1))] if value
                   else [(d["first_child"], 1 - q), (d["second_child"], q)])
        oldvalue = expression()
        for child, w in weights:
            oldvalue = plus(oldvalue, expression(0, {av[child]: 1}), w)
        wanted = plus(expression(0, {av[n]: 1}), oldvalue, -1)
        bounds = []
        for label, sign in [("U", 1), ("L", -1)]:
            ref = row_ref(a, d["removed_block_rows"][label + str(value)])
            raw = builder.refexpr(ref)
            diff = plus(raw, mul(wanted, sign), -1)
            sx = av[d["selector"]]
            coef = diff[1].get(sx, F(0))
            assert diff == mul(builder.refexpr(sel_eq), coef), (n, label, value, diff)
            bounds.append(builder.lin("Le", [(ref, F(1)), (sel_eq, -coef)], mul(wanted, sign)))
        eq = builder.eqpair(*bounds)
        terms = [(eq, F(1))]
        for child, w in weights:
            if child in alias:
                terms.append((alias[child], w))
            else:
                assert canon[child] == expression(0, {av[child]: 1})
        normalized = expression()
        for child, w in weights:
            normalized = plus(normalized, canon[child], w)
        return builder.lin("Eq", terms,
                           plus(expression(0, {av[n]: 1}), normalized, -1)), normalized

    def ensure(n):
        if n in alias:
            return
        if canon[n] == expression(0, {av[n]: 1}):
            return
        assert n not in visiting, ("cyclic candidate alias", n)
        visiting.add(n)
        d = nodes[n]
        for child in [d["first_child"], d["second_child"]]:
            ensure(child)
        same = canon[d["first_child"]] == canon[d["second_child"]] == canon[n]
        rep = None if same or not canon[n][1] else reps[d["replacement"]["variable"]]
        if rep:
            for child in [nodes[rep]["first_child"], nodes[rep]["second_child"]]:
                ensure(child)
        desired = plus(expression(0, {av[n]: 1}), canon[n], -1)
        sx = av[d["selector"]]

        def branch(builder, eq, value):
            nr, nv = norm(builder, n, eq, value)
            if rep:
                assert av[nodes[rep]["selector"]] == sx
                rr, rv = norm(builder, rep, eq, value)
                assert nv == rv
                return builder.lin("Eq", [(nr, F(1)), (rr, F(-1))], desired)
            assert nv == canon[n], (n, value, nv, canon[n])
            return nr

        if sx == fixed:
            alias[n] = branch(f, fixed_eq, 0)
        else:
            alias[n] = cases(f, "Eq", desired, sx,
                             lambda z, ass: branch(z, fix_binary(z, sx, 0, ass), 0),
                             lambda z, ass: branch(z, fix_binary(z, sx, 1, ass), 1))
        visiting.remove(n)

    for n in nodes:
        ensure(n)
    # Ensure children needed by representative definitions have global aliases.
    for n in reps.values():
        for child in [nodes[n]["first_child"], nodes[n]["second_child"]]:
            ensure(child)

    fchecks = []
    for i, v in enumerate(b["vars"]):
        j = next(iter(forward[i][1]))
        assert b["vars"][i]["integer"] == a["vars"][j]["integer"]
        fchecks.append({"VarLower": j})
        fchecks.append(fixed_eq if j == fixed else {"VarUpper": j})
        if v["integer"]:
            fchecks.append(fact(f, "Int", forward[i],
                                [[{"VarInt": j}, F(1)]], forward[i][0], True))
    new_rows = {n + "_" + suffix: n for n, d in defs.items()
                for suffix in (["mix"] if d["kind"] == "mix" else ["U0", "L0", "U1", "L1"])}
    for row in b["rows"]:
        ref = row_ref(b, row["name"])
        kind = "Eq" if "RowEq" in ref else "Le"
        want = substitute(row_fact(row, next(iter(ref))), forward)
        if row["name"] not in new_rows:
            old = row_ref(a, row["name"])
            e = f.refexpr(old)
            terms = [(old, F(1))]
            for i, c in e[1].items():
                n = a["vars"][i]["name"]
                if n in alias:
                    terms.append((alias[n], -c))
            fchecks.append(f.lin(kind, terms, want))
            continue
        dn = new_rows[row["name"]]
        n = reps[dn]
        d = defs[dn]
        if d["kind"] == "mix":
            eq, _ = norm(f, n, fixed_eq, 0)
            assert f.refexpr(eq) == want
            fchecks.append(eq)
            continue
        sx = av[d["selector"]]
        out = av[n]

        def rowbranch(builder, ass, value):
            eq = fix_binary(builder, sx, value, ass)
            nr, _ = norm(builder, n, eq, value)
            terms = [(nr, want[1].get(out, F(0)))]
            res = plus(want, builder.refexpr(nr), -terms[0][1])
            terms.append((eq, res[1].get(sx, F(0))))
            return bound(builder, want, terms)

        fchecks.append(cases(f, "Le", want, sx,
                             lambda z, ass: rowbranch(z, ass, 0),
                             lambda z, ass: rowbranch(z, ass, 1)))
    assert substitute(b["objective"], forward) == a["objective"]
    fchecks.append("Exact")
    f.finish(forward, fchecks)

    rchecks = []
    for i, v in enumerate(a["vars"]):
        for typ, e in [("VarLower", plus(expression(v["lower"]), reverse[i], -1)),
                       ("VarUpper", plus(reverse[i], expression(-v["upper"])))]:
            rchecks.append(bound(r, e))
        if v["integer"]:
            j = next(iter(reverse[i][1]), None) if reverse[i][1] else None
            if j is None:
                assert reverse[i][0].denominator == 1
                rchecks.append("Exact")
            else:
                rchecks.append(fact(r, "Int", reverse[i], [[{"VarInt": j}, F(1)]],
                                    reverse[i][0], True))
    rowfacts = {key(r.refexpr(row_ref(b, row["name"]))): row_ref(b, row["name"])
                for row in b["rows"]}
    for row in a["rows"]:
        oldref = row_ref(a, row["name"])
        kind = "Eq" if "RowEq" in oldref else "Le"
        want = substitute(row_fact(row, next(iter(oldref))), reverse)
        if key(want) in rowfacts:
            rchecks.append(rowfacts[key(want)])
            continue
        if kind == "Eq":
            assert want == expression(), (row["name"], want)
            rchecks.append("Exact")
            continue
        node = next((n for n in [row["name"].removeprefix("pbc_").rsplit("_", 1)[0]]
                     if n in nodes), None)
        options = [[]]
        if node and "variable" in nodes[node]["replacement"]:
            dn = nodes[node]["replacement"]["variable"]
            vi = bv[dn]
            for suffix in (["mix"] if defs[dn]["kind"] == "mix" else ["U0", "L0", "U1", "L1"]):
                ref = row_ref(b, dn + "_" + suffix)
                raw = r.refexpr(ref)
                if raw[1].get(vi):
                    q = want[1].get(vi, F(0)) / raw[1][vi]
                    if r.kind(ref) == "Eq" or q >= 0:
                        options.append([(ref, q)])
        # Small deterministic candidate list. Failure never becomes acceptance.
        for terms in options:
            res = want
            for ref, c in terms:
                res = plus(res, r.refexpr(ref), -c)
            hi = res[0] + sum(c * (b["vars"][i]["upper"] if c > 0 else b["vars"][i]["lower"])
                              for i, c in res[1].items())
            if hi <= 0:
                rchecks.append(bound(r, want, terms))
                break
        else:
            raise AssertionError(("reverse inequality unproved", row["name"], want))
    assert substitute(a["objective"], reverse) == b["objective"]
    rchecks.append("Exact")
    r.finish(reverse, rchecks)
    return proof, {
        "source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
        "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
        "source_nodes": len(nodes), "shared_nodes": len(defs), "aliases": len(alias),
        "root_steps": [len(f.steps), len(r.steps)],
        "directions": 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test38-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test38"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/model_shared_dag.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(model(source), model(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id="test38", source=source, target=target,
                          metadata={"audit": {"path": str(audit), "sha256": sha(audit)},
                                    "counts": counts,
                                    "preparation_seconds": time.perf_counter() - started})
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test38", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"]}))


if __name__ == "__main__":
    main()
