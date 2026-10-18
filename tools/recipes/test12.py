"""Native test12 complete forced-zero closure and zero-extension bijections.

995 binary coordinates are forced to zero by support-containment differences;
duplicate and linearly dependent equalities are recovered from the retained
rows.  The fixing order and row dependencies are read from the reformulation
audit produced with the model pair."""

import json
from rpx import Q as Fraction
from pathlib import Path
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        7195,
        426,
        6200,
        310,
    )
    hints = json.loads(
        (Path(source_path).resolve().parent.parent / "output/audit.json").read_text()
    )
    removed = {i for (i, v) in enumerate(source.vars) if v.name not in target.vars}
    assert removed == {source.vars[name].index for name in hints["removed_variables"]}
    assert len(removed) == 995
    common = [[source.vars[v.name].index, j] for (j, v) in enumerate(target.vars)]
    for i, j in common:
        assert (
            source.vars[i].name,
            source.vars[i].lower,
            source.vars[i].upper,
            source.vars[i].integer,
        ) == (
            target.vars[j].name,
            target.vars[j].lower,
            target.vars[j].upper,
            target.vars[j].integer,
        )
    proof = Proof(source, target)
    f, r = proof.forward, proof.reverse
    f.map(default="same_name")
    r.map({source.vars[i].name: 0 for i in removed}, default="same_name")
    forward, reverse = f.mapping, r.mapping

    def row_expr(model, name):
        row = model.rows[model.rows[name].index]
        if row.lower is not None and row.lower == row.upper:
            return row.expression - row.upper
        if row.lower is None:
            return row.expression - row.upper
        return row.lower - row.expression

    def substitute(e, mapping):
        return e.substitute(mapping)

    def is_exact(kind, e):
        return not e.terms and (
            kind == "Eq"
            and e.constant == 0
            or (kind == "Le" and e.constant <= 0)
            or (kind == "Int" and e.constant.denominator == 1)
        )

    def fact(builder, kind, e, terms=(), constant=0, terminal=False):
        if terminal and is_exact(kind, e):
            return None
        if (
            len(terms) == 1
            and terms[0][1] == 1
            and (not constant)
            and (terms[0][0].kind == kind)
            and (terms[0][0].expression == e)
        ):
            return terms[0][0]
        native_terms = [(ref, Fraction(c)) for (ref, c) in terms if Fraction(c) != 0]
        return Assembler(builder).linear(
            kind, native_terms, constant=Fraction(constant), expect=e
        )

    p = f
    zero = {}
    containments = 0
    for round_hint in hints["fixing_rounds"]:
        previous = dict(zero)
        pairs = {}
        for d in round_hint["fixings"]:
            i = source.vars[d["variable"]].index
            assert i not in zero and d["value"] == 0
            small = d["witness"]["smaller"]
            large = d["witness"]["larger"]
            pair = (small, large)
            if pair not in pairs:
                sr = p.row(small)
                lr = p.row(large)
                assert sr.kind == "Eq" and lr.kind == "Eq"
                constant = lr.expression.constant - sr.expression.constant
                ordered = dict(lr.expression.terms)
                for j, c in sr.expression.terms.items():
                    value = ordered.get(j, Fraction(0)) - c
                    if value:
                        ordered[j] = value
                    else:
                        ordered.pop(j, None)
                terms = [(lr, Fraction(1)), (sr, Fraction(-1))]
                for j, c in ordered.items():
                    if j in previous:
                        terms.append((previous[j], -c))
                wanted = affine(
                    source,
                    constant,
                    {j: c for (j, c) in ordered.items() if j not in previous},
                )
                assert wanted.constant == 0 and wanted.terms
                assert all((c == 1 for c in wanted.terms.values()))
                pairs[pair] = Assembler(p).linear("Eq", terms, expect=wanted)
                containments += 1
            eq = pairs[pair]
            e = eq.expression
            assert e.terms[i] == 1
            terms = [(eq, Fraction(1))]
            terms.extend(((p.lower(j), c) for (j, c) in e.terms.items() if j != i))
            upper = Assembler(p).linear("Le", terms, expect=affine(source, 0, {i: 1}))
            zero[i] = p.derive.eqpair(upper, p.lower(i))
    assert set(zero) == removed
    assert containments == 54
    checks = []
    for i, v in enumerate(target.vars):
        e = forward[i]
        for typ, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = e * sign + Expr(-sign * value)
            if is_exact("Le", wanted):
                check = None
            else:
                j = next(iter(e.terms))
                check = f.lower(j) if typ == "VarLower" else f.upper(j)
                assert check.expression == wanted
            checks.append(check)
        if v.integer:
            checks.append(None if not e.terms else f.integer(next(iter(e.terms))))
    for row in target.rows:
        name = row.name
        assert row.lower is not None and row.lower == row.upper
        wanted = substitute(row_expr(target, name), forward)
        ref = f.row(name)
        terms = [(ref, Fraction(1))]
        terms.extend(
            ((zero[i], -c) for (i, c) in ref.expression.terms.items() if i in zero)
        )
        checks.append(fact(f, "Eq", wanted, terms, terminal=True))
    wanted = substitute(target.objective, forward) - source.objective
    terms = [(zero[i], -c) for (i, c) in source.objective.terms.items() if i in zero]
    checks.append(fact(f, "Eq", wanted, terms, terminal=True))
    Assembler(f).assign(checks)
    f.finish()
    duplicates = hints["duplicate_rows"]
    relations = hints["linear_relations"]
    recovered = {}

    def recover_row(name):
        if name in recovered:
            return recovered[name]
        wanted = substitute(row_expr(source, name), reverse)
        if name in target.rows:
            ref = r.row(name)
            assert ref.expression == wanted
        elif name in duplicates:
            ref = recover_row(duplicates[name])
            assert ref.expression == wanted
        else:
            coefficients = relations[name]["coefficients"]
            assert coefficients[name] == 1
            assert all((rn in target.rows for rn in coefficients if rn != name))
            terms = [
                (r.row(rn), -Fraction(c))
                for (rn, c) in coefficients.items()
                if rn != name
            ]
            ref = Assembler(r).linear("Eq", terms, expect=wanted)
        recovered[name] = ref
        return ref

    checks = []
    for i, v in enumerate(source.vars):
        e = reverse[i]
        for typ, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = e * sign + Expr(-sign * value)
            if is_exact("Le", wanted):
                check = None
            else:
                j = next(iter(e.terms))
                check = r.lower(j) if typ == "VarLower" else r.upper(j)
                assert check.expression == wanted
            checks.append(check)
        if v.integer:
            checks.append(None if not e.terms else r.integer(next(iter(e.terms))))
    for row in source.rows:
        assert row.lower is not None and row.lower == row.upper
        checks.append(recover_row(row.name))
    wanted = substitute(source.objective, reverse) - target.objective
    checks.append(fact(r, "Eq", wanted, [], terminal=True))
    Assembler(r).assign(checks)
    r.finish()
    return proof
