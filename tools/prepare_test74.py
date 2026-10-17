#!/usr/bin/env python3
"""Native test74 private binary reconstruction without product branching."""
from fractions import Fraction as F
from pathlib import Path
from itertools import combinations, product
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test48 import emit_checks, lift
from prepare_test72 import bounds, evaluated, fix, var
from prepare_native import compile_case, make_proof


def decision(d):
    n = len(d["other_variables"])
    allowed = {tuple(t["bits"]): t["allowed_auxiliary_values"]
               for t in d["truth_table"] if t["allowed_auxiliary_values"]}
    for k in range(n + 1):
        for ids in combinations(range(n), k):
            for vals in product([0, 1], repeat=k):
                for complement in [False, True]:
                    def value(bits):
                        return int(all(bits[i] == v for i, v in zip(ids, vals))) ^ int(complement)
                    if all(value(bits) in choices for bits, choices in allowed.items()):
                        return tuple(zip(ids, vals)), complement
    raise AssertionError(("no conjunctive completion", d["variable"]))


def replacement_owner(h, b):
    owners = {}
    duplicates = h["duplicate_rows"]

    def keeper(rn):
        seen = set()
        while rn in duplicates:
            assert rn not in seen
            seen.add(rn)
            rn = duplicates[rn]
        return rn

    for d in h["projections"]:
        for rn in d["replacement_rows"]:
            k = keeper(rn)
            if k in b["row_index"]:
                owners.setdefault(k, d)
    return owners, keeper


def bounded_cases(p, kind, wanted, bits, leaf, extra=None):
    extra = extra or {}
    ids = [next(iter(bit["expr"][1])) for bit in bits]

    def rec(cur, k, state):
        if kind == "Le":
            assigned = {i: item for i, item in zip(ids, state)}
            bound = wanted[0]
            refs = []
            for i, c in wanted[1].items():
                if i in assigned:
                    value, ref = assigned[i]
                    bound += c * value
                    refs.append([ref, c])
                    continue
                side = "upper" if c > 0 else "lower"
                if i in extra:
                    value, ref = extra[i][side]
                else:
                    value = cur.model["vars"][i][side]
                    ref = {("VarUpper" if c > 0 else "VarLower"): i}
                if value is None:
                    break
                bound += c * value
                refs.append([ref, abs(c)])
            else:
                if bound <= 0:
                    return {"Witness": cur.lin("Le", refs, wanted, constant=bound)}
        if k == len(bits):
            return leaf(cur, state)
        bit = bits[k]

        def side(child, g, v):
            return rec(child, k + 1, state + [(v, fix(child, bit, v, g))])

        ref = cur.cases(kind, wanted, bit["expr"], bit["integer"],
                        lambda q, g: side(q, g, 0), lambda q, g: side(q, g, 1))
        return {"Witness": ref}

    return rec(p, 0, [])["Witness"]


def forward(a, b, h, owners, p):
    mapping = [var(a["var_index"][v["name"]]) for v in b["vars"]]
    rows = {}
    first = next(iter(owners.values()))
    firstrow = first["source_rows"][0]
    alias = p.lin("Le", [[row_ref(a, firstrow), 1]],
                  row_fact(a["rows"][a["row_index"][firstrow]],
                           next(iter(row_ref(a, firstrow)))))
    for rn, d in owners.items():
        ri = b["row_index"][rn]
        typ = next(iter(row_ref(b, rn)))
        wanted = substitute(row_fact(b["rows"][ri], typ), mapping)
        kind = "Eq" if typ == "RowEq" else "Le"
        ids = [a["var_index"][n] for n in d["other_variables"]]
        bits = [bounds(p, var(i)) for i in ids]
        es = [x["expr"] for x in bits]
        zi = a["var_index"][d["variable"]]
        zbit = bounds(p, var(zi))

        def leaf(q, state, d=d, wanted=wanted, kind=kind, es=es, zi=zi, zbit=zbit):
            value, refs = evaluated(q, wanted, state, es)
            if (kind == "Le" and value <= 0) or (kind == "Eq" and value == 0):
                return {"Witness": q.lin(kind, refs, wanted, constant=value)}

            def zside(child, g, z):
                zfix = fix(child, zbit, z, g)
                st = state + [(z, zfix)]
                vs = es + [var(zi)]
                for source_row in d["source_rows"]:
                    ref = alias if source_row == firstrow else row_ref(a, source_row)
                    ev, rr = evaluated(child, child.refexpr(ref), st, vs)
                    if ev > 0:
                        return {"Absurd": child.lin("Le", [[ref, 1]] +
                                                    [[r, -c] for r, c in rr],
                                                    expression(ev))}
                raise AssertionError(("source assignment unexpectedly feasible", rn, state, z))

            contradiction = expression(1)
            r = q.cases("Le", contradiction, zbit["expr"], zbit["integer"],
                        lambda c, g: zside(c, g, 0), lambda c, g: zside(c, g, 1))
            return {"Absurd": r}

        rows[ri] = bounded_cases(p, kind, wanted, bits, leaf)
    checks = emit_checks(p, b, mapping, "Eq", rows=rows)
    p.finish(mapping, checks)
    return len(checks)


def and_integer(p, d):
    e = d["expr"]
    wanted = e
    literals = d["literals"]

    def rec(cur, k, assigned):
        if k == len(literals):
            refs = [[d["lower"][1], 1]] + [[r, -1] for r in assigned]
            lower = cur.lin("Le", refs, plus(expression(1), e, -1))
            upper = cur.lin("Le", [[d["upper"][0], 1], [assigned[0], 1]],
                            plus(e, expression(-1)))
            eq = cur.eqpair(upper, lower)
            return {"Witness": cur.lin("Int", [[eq, 1]], wanted, constant=1)}
        bit = literals[k]

        def zero(child, g):
            eqbit = fix(child, bit, 0, g)
            upper = child.lin("Le", [[d["upper"][k], 1], [eqbit, 1]], e)
            eq = child.eqpair(upper, d["lower"][0])
            return {"Witness": child.lin("Int", [[eq, 1]], wanted)}

        def one(child, g):
            eqbit = fix(child, bit, 1, g)
            assigned.append(eqbit)
            result = rec(child, k + 1, assigned)
            assigned.pop()
            return result

        r = cur.cases("Int", wanted, bit["expr"], bit["integer"], zero, one)
        return {"Witness": r}

    return rec(p, 0, [])["Witness"]


def reverse(a, b, h, pre, keeper):
    mapping = [var(b["var_index"][v["name"]]) if v["name"] in b["var_index"] else None
               for v in a["vars"]]
    domains = {}
    rows = {}
    pairs = []
    conjunctions = {}
    specs = []
    for name, value in h["isolated_fixed_variables"].items():
        mapping[a["var_index"][name]] = expression(value)
    for d in h["projections"]:
        choice, complement = decision(d)
        ids = [b["var_index"][n] for n in d["other_variables"]]
        key = tuple(sorted((ids[j], v) for j, v in choice))
        entry = {"hint": d, "ids": ids, "choice": key, "complement": complement}
        pairs.append(entry)
        if len(key) == 0:
            entry["base"] = expression(1)
        elif len(key) == 1:
            entry["base"] = (var(key[0][0]) if key[0][1]
                             else plus(expression(1), var(key[0][0]), -1))
        else:
            if key not in conjunctions:
                lits = [var(i) if v else plus(expression(1), var(i), -1)
                        for i, v in key]
                lo = plus(total(lits), expression(1 - len(lits)))
                checks = []
                for lower in [expression(), lo]:
                    for upper in lits:
                        checks.append(pre.prove("Le", plus(lower, upper, -1)))
                conjunctions[key] = {"index": len(specs), "lits": lits}
                specs.append({"lower": [expression(), lo],
                              "upper": lits, "checks": checks})
    p = lift(pre, "intervals", specs)
    layouts = p.old_layout
    for key, c in conjunctions.items():
        layout = layouts[c["index"]]
        c.update({"variable": layout["variable"],
                  "lower": [{"RowLower": r} for r in layout["lower"]],
                  "upper": [{"RowUpper": r} for r in layout["upper"]],
                  "expr": var(layout["variable"])})
        c["literals"] = [bounds(p, e) for e in c["lits"]]
        c["integer"] = and_integer(p, c)
        c["zero"] = c["lower"][0]
        c["one"] = p.lin("Le", [[c["upper"][0], 1], [c["literals"][0]["upper"], 1]],
                         plus(c["expr"], expression(-1)))
    for entry in pairs:
        d = entry["hint"]
        key = entry["choice"]
        i = a["var_index"][d["variable"]]
        comp = entry["complement"]
        conj = conjunctions.get(key)
        base = conj["expr"] if conj else entry["base"]
        mapping[i] = plus(expression(1), base, -1) if comp else base
        if conj:
            domains[(i, "VarLower")] = conj["one"] if comp else conj["zero"]
            domains[(i, "VarUpper")] = conj["zero"] if comp else conj["one"]
            domains[(i, "VarInt")] = (p.lin("Int", [[conj["integer"], -1]], mapping[i],
                                            constant=1) if comp else conj["integer"])
        bits = [bounds(p, var(j)) for j in entry["ids"]]
        es = [x["expr"] for x in bits]
        for rn in d["source_rows"]:
            ri = a["row_index"][rn]
            typ = next(iter(row_ref(a, rn)))
            wanted = substitute(row_fact(a["rows"][ri], typ), mapping)

            def leaf(q, state, entry=entry, d=d, key=key, comp=comp, conj=conj,
                     base=base, wanted=wanted, es=es):
                vals = {j: v for j, (v, ref) in zip(entry["ids"], state)}
                fixed = {j: ref for j, (v, ref) in zip(entry["ids"], state)}
                bv = int(all(vals[j] == v for j, v in key))
                zv = bv ^ int(comp)
                allowed = next(t["allowed_auxiliary_values"] for t in d["truth_table"]
                               if t["bits"] == [int(v) for v, ref in state])
                if not allowed:
                    for new in d["replacement_rows"]:
                        kept = keeper(new)
                        ref = row_ref(b, kept)
                        e = q.refexpr(ref)
                        value, refs = evaluated(q, e, state, es)
                        if q.kind(ref) == "Eq" and value != 0:
                            return {"Absurd": q.lin(
                                "Le", [[ref, 1 if value > 0 else -1]] +
                                [[r, -c if value > 0 else c] for r, c in refs],
                                expression(abs(value)))}
                        if q.kind(ref) == "Le" and value > 0:
                            return {"Absurd": q.lin(
                                "Le", [[ref, 1]] + [[r, -c] for r, c in refs],
                                expression(value))}
                    raise AssertionError("missing projected contradiction")
                assert zv in allowed
                terms = []
                value = wanted[0]
                if conj:
                    if bv:
                        lr = [[conj["lower"][1], 1]]
                        ur = [[conj["upper"][0], 1]]
                        for j, v in key:
                            lr.append([fixed[j], -1 if v else 1])
                        j, v = key[0]
                        ur.append([fixed[j], 1 if v else -1])
                        lo = q.lin("Le", lr, plus(expression(1), base, -1))
                        hi = q.lin("Le", ur, plus(base, expression(-1)))
                        eq = q.eqpair(hi, lo)
                    else:
                        j, v = next((j, v) for j, v in key if vals[j] != v)
                        k = list(key).index((j, v))
                        hi = q.lin("Le", [[conj["upper"][k], 1],
                                          [fixed[j], 1 if v else -1]], base)
                        eq = q.eqpair(hi, conj["lower"][0])
                    coef = wanted[1].get(next(iter(base[1])), 0)
                    value += coef * bv
                    if coef:
                        terms.append([eq, coef])
                for j, ref in fixed.items():
                    coef = wanted[1].get(j, 0)
                    value += coef * vals[j]
                    if coef:
                        terms.append([ref, coef])
                assert value <= 0
                return {"Witness": q.lin("Le", terms, wanted, constant=value)}

            extra = ({next(iter(base[1])): {"lower": (F(0), conj["zero"]),
                                            "upper": (F(1), conj["one"])}}
                     if conj else {})
            rows[ri] = bounded_cases(p, "Le", wanted, bits, leaf, extra)
    checks = emit_checks(p, a, mapping, "Eq", rows=rows, domains=domains)
    p.finish(mapping, checks)
    return len(checks), len(conjunctions)


def total(es):
    out = expression()
    for e in es:
        out = plus(out, e)
    return out


def prepare(source, target, audit):
    a = parse_mps(source)
    b = parse_mps(target)
    h = json.loads(Path(audit).read_text())
    owners, keeper = replacement_owner(h, b)
    proj = [[a["var_index"][v["name"]], j] for j, v in enumerate(b["vars"])]
    proof, f, r = make_proof(a, b)
    forward_obligations = forward(a, b, h, owners, f)
    reverse_obligations, conjunctions = reverse(a, b, h, r, keeper)
    counts = {"source_variables": len(a["vars"]), "target_variables": len(b["vars"]),
              "source_rows": len(a["rows"]), "target_rows": len(b["rows"]),
              "private_binary_completions": len(h["projections"]),
              "fixed_restorations": len(h["isolated_fixed_variables"]),
              "retained_observations": len(proj),
              "joint_AND_intervals": conjunctions,
              "audited_assignments": sum(len(d["truth_table"])
                                         for d in h["projections"]),
              "claims": 2,
              "obligations_by_claim": [forward_obligations, reverse_obligations]}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/Users/bhz/Code/reform_test/runs/test74-nomf-B1"))
    parser.add_argument("--out", type=Path, default=Path("cases/test74"))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / "input/model.mps", run / "output/reformulated.mps"
    audit = run / "output/audit.json"
    proof, counts = prepare(source, target, audit)
    record = compile_case(proof, args.out, case_id="test74", source=source,
                          target=target, metadata={"counts": counts})
    record["counts"] = counts
    record["preparation_seconds"] = time.perf_counter() - started
    (args.out / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_id": "test74", "status": record["status"],
                      "guarantee": record["verification"].get("guarantee"),
                      "obligations": record["verification"]["statistics"]["obligations"],
                      "counts": counts,
                      "preparation_seconds": record["preparation_seconds"]}))


if __name__ == "__main__":
    main()
