"""Native test11 full alias-elimination affine bijections.

Every eliminated coordinate is recovered from its own alias equality; the
remaining deleted rows are discharged by variable bounds or by a unique
support-containment dominance witness."""

from collections import defaultdict
from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        62529,
        121161,
        40488,
        90561,
    )
    eliminated = {i for (i, v) in enumerate(source.vars) if v.name not in target.vars}
    assert len(eliminated) == 22041
    deleted = {_row.name for _row in source.rows} - {_row.name for _row in target.rows}

    def row_expr(model, name):
        row = model.rows[model.rows[name].index]
        if row.lower is not None and row.lower == row.upper:
            return row.expression - row.upper
        if row.lower is None:
            return row.expression - row.upper
        return row.lower - row.expression

    def row_kind(model, name):
        row = model.rows[model.rows[name].index]
        return "Eq" if row.lower is not None and row.lower == row.upper else "Le"

    eliminated_names = {source.vars[i].name for i in eliminated}
    alias_info = {}
    for name in deleted:
        row = source.rows[source.rows[name].index]
        if row.lower is None or row.lower != row.upper:
            continue
        if len(row.expression.terms) != 2 or row.expression.constant != 0:
            continue
        ((i, ci), (j, cj)) = row.expression.terms.items()
        if ci != -cj:
            continue
        if (source.vars[i].name in eliminated_names) == (
            source.vars[j].name in eliminated_names
        ):
            continue
        alias_info[name] = (i, j) if source.vars[i].name in eliminated_names else (j, i)
    aliases = {i: j for (i, j) in alias_info.values()}
    assert len(alias_info) == len(aliases) == 22041
    assert set(aliases) == eliminated
    assert set(alias_info) <= deleted
    witnesses = {}
    for name, (i, j) in alias_info.items():
        e = row_expr(source, name)
        scale = 1 / e.terms[i]
        assert e * scale == affine(source, 0, {i: 1, j: -1})
        assert i not in witnesses
        witnesses[i] = (name, scale)
    assert set(witnesses) == set(aliases)
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
    r.map(
        {
            source.vars[i].name: target.vars[source.vars[j].name]
            for i, j in aliases.items()
        },
        default="same_name",
    )
    forward, reverse = f.mapping, r.mapping

    def substitute(e, mapping):
        return e.substitute(mapping)

    def substitute_ordered(e, mapping):
        constant = e.constant
        terms = {}
        for i, c in e.terms.items():
            base = mapping[i]
            constant += c * base.constant
            for j, q in base.terms.items():
                value = terms.get(j, Fraction(0)) + c * q
                if value:
                    terms[j] = value
                else:
                    terms.pop(j, None)
        return (constant, terms)

    assert substitute(source.objective, reverse) == target.objective
    assert substitute(target.objective, forward) == source.objective
    index = defaultdict(list)
    for ridx, row in enumerate(target.rows):
        e = row_expr(target, row.name)
        for i, c in e.terms.items():
            index[i, c].append((ridx, row.name, e))

    def dominance_witness(wanted):
        key = min(wanted.terms.items(), key=lambda ic: len(index[ic]))
        found = []
        for ridx, name, e in index[key]:
            if e.constant != wanted.constant:
                continue
            if any((e.terms.get(i) != c for (i, c) in wanted.terms.items())):
                continue
            extra = [(i, c) for (i, c) in e.terms.items() if i not in wanted.terms]
            if all((c > 0 and target.vars[i].lower == 0 for (i, c) in extra)):
                found.append((ridx, name))
        assert len(found) == 1
        return found[0][1]

    def boxable(model, e):
        ceiling = e.constant
        for i, c in e.terms.items():
            v = model.vars[i]
            bound = v.upper if c > 0 else v.lower
            if bound is None:
                return False
            ceiling += c * bound
        return ceiling <= 0

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

    def box(builder, e, terminal=False, order=None):
        terms = []
        ceiling = e.constant
        for i, c in (
            e.terms.items()
            if order is None
            else order.items() if hasattr(order, "items") else order
        ):
            v = builder.model.vars[i]
            bound = v.upper if c > 0 else v.lower
            assert bound is not None
            ceiling += c * bound
            terms.append((builder.upper(i) if c > 0 else builder.lower(i), abs(c)))
        assert ceiling <= 0
        return fact(builder, "Le", e, terms, ceiling, terminal)

    checks = []
    for i, v in enumerate(target.vars):
        for typ, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = forward[i] * sign + Expr(-sign * value)
            checks.append(box(f, wanted, True))
        if v.integer:
            checks.append(f.integer(next(iter(forward[i].terms))))
    for row in target.rows:
        name = row.name
        kind = row_kind(target, name)
        wanted = substitute(row_expr(target, name), forward)
        ref = f.row(name)
        terms = [(ref, Fraction(1))]
        for i, c in ref.expression.terms.items():
            if i in aliases:
                (witness, scale) = witnesses[i]
                terms.append((f.row(witness), -c * scale))
        checks.append(fact(f, kind, wanted, terms, terminal=True))
    checks.append(None)
    Assembler(f).assign(checks)
    f.finish()
    checks = []
    for i, v in enumerate(source.vars):
        for typ, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = reverse[i] * sign + Expr(-sign * value)
            checks.append(box(r, wanted, True))
        if v.integer:
            checks.append(r.integer(next(iter(reverse[i].terms))))
    bound_boxes = 0
    exact_rows = 0
    dominance = 0
    for row in source.rows:
        name = row.name
        kind = row_kind(source, name)
        (constant, order) = substitute_ordered(row_expr(source, name), reverse)
        wanted = affine(target, constant, order)
        if name in target.rows:
            check = r.row(name)
            assert check.expression == wanted
        elif is_exact(kind, wanted):
            check = None
            exact_rows += 1
        elif boxable(target, wanted):
            assert kind == "Le"
            check = box(r, wanted, True, order)
            bound_boxes += 1
        else:
            assert kind == "Le"
            witness = dominance_witness(wanted)
            ref = r.row(witness)
            delta = dict(order)
            for j, c in ref.expression.terms.items():
                value = delta.get(j, Fraction(0)) - c
                if value:
                    delta[j] = value
                else:
                    delta.pop(j, None)
            assert wanted.constant - ref.expression.constant == 0
            terms = [(ref, Fraction(1))]
            for j, c in delta.items():
                assert c < 0 and source.vars[j].lower == 0
                terms.append((r.lower(j), -c))
            check = fact(r, "Le", wanted, terms, terminal=True)
            dominance += 1
        checks.append(check)
    assert (exact_rows, bound_boxes, dominance) == (22041 + 38, 6505, 2016), (
        exact_rows,
        bound_boxes,
        dominance,
    )
    checks.append(None)
    Assembler(r).assign(checks)
    r.finish()
    return proof
