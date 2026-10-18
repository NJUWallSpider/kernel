"""Native test9 affine-exit elimination proof.

763 nonnegative exit variables are eliminated through their defining
equalities; the one added target coordinate is fixed at one.  The legacy
four-claim Request layout collapses to the two MI-OPT directions."""

from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        2298,
        1026,
        1536,
        846,
    )
    removed = {i for (i, v) in enumerate(source.vars) if v.name not in target.vars}
    assert len(removed) == 763
    added = {j for (j, v) in enumerate(target.vars) if v.name not in source.vars}
    assert len(added) == 1
    offset = next(iter(added))
    assert target.vars[offset].lower == target.vars[offset].upper == 1
    assert not target.vars[offset].integer
    incidence = {i: [] for i in removed}
    for ri, row in enumerate(source.rows):
        for i in set(row.expression.terms) & removed:
            incidence[i].append(ri)
    definitions = {}
    byrow = {}
    reverse = {}
    for j, v in enumerate(target.vars):
        if j != offset:
            old = source.vars[v.name]
            assert (old.name, old.lower, old.upper, old.integer) == (
                v.name,
                v.lower,
                v.upper,
                v.integer,
            )
    for i, v in enumerate(source.vars):
        if i not in removed:

            continue
        assert (
            len(incidence[i]) == 1
            and (not v.integer)
            and (v.lower == 0)
            and (v.upper is None)
        )
        ri = incidence[i][0]
        row = source.rows[ri]
        pivot = row.expression.terms[i]
        assert (
            row.lower is not None
            and row.lower == row.upper
            and (pivot == -1)
            and (ri not in byrow)
        )
        rhs = row.lower - row.expression.constant
        terms = {
            target.vars[source.vars[j].name].index: -c / pivot
            for (j, c) in row.expression.terms.items()
            if j != i
        }
        reverse[v.name] = affine(target, rhs / pivot, terms)
        definitions[i] = (ri, pivot)
        byrow[ri] = i
    proof = Proof(source, target)
    (f, r) = (proof.forward, proof.reverse)
    f.map({target.vars[offset].name: 1}, default="same_name")
    r.map(reverse, default="same_name")
    forward, reverse = f.mapping, r.mapping

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

    def box(builder, e, terminal=False):
        terms = []
        ceiling = e.constant
        for i, c in e.terms.items():
            v = builder.model.vars[i]
            bound = v.upper if c > 0 else v.lower
            assert bound is not None
            ceiling += c * bound
            terms.append((builder.upper(i) if c > 0 else builder.lower(i), abs(c)))
        assert ceiling <= 0
        return fact(builder, "Le", e, terms, ceiling, terminal)

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

    def substitute(e, mapping):
        return e.substitute(mapping)

    for back in (False, True):
        builder = r if back else f
        mapping = reverse if back else forward
        (output, inp) = (source, target) if back else (target, source)
        checks = []
        fixed = (
            builder.derive.eqpair(builder.upper(offset), builder.lower(offset))
            if back
            else None
        )
        for i, v in enumerate(output.vars):
            e = mapping[i]
            for typ, value, sign in (
                ("VarLower", v.lower, -1),
                ("VarUpper", v.upper, 1),
            ):
                if value is None:
                    continue
                wanted = e * sign + Expr(-sign * value)
                if is_exact("Le", wanted):
                    check = None
                elif back and i in definitions:
                    name = source.rows[definitions[i][0]].name
                    if name in target.rows:
                        check = builder.row(name)
                        assert check.expression == wanted
                    else:
                        check = box(builder, wanted, True)
                else:
                    j = next(iter(e.terms))
                    check = builder.lower(j) if typ == "VarLower" else builder.upper(j)
                    assert check.expression == wanted
                checks.append(check)
            if v.integer:
                terms = [(builder.integer(j), c) for (j, c) in e.terms.items()]
                checks.append(fact(builder, "Int", e, terms, e.constant, True))
        for row in output.rows:
            name = row.name
            kind = row_kind(output, name)
            wanted = substitute(row_expr(output, name), mapping)
            if back:
                assert name in source.rows
                if source.rows[name].index in byrow:
                    assert is_exact("Eq", wanted)
                    check = None
                else:
                    check = builder.row(name)
                    assert check.expression == wanted
            elif name in source.rows and source.rows[name].index in byrow:
                assert kind == "Le"
                i = byrow[source.rows[name].index]
                check = fact(
                    builder,
                    "Le",
                    wanted,
                    [
                        (builder.row(name), Fraction(-1)),
                        (builder.lower(i), Fraction(1)),
                    ],
                )
            else:
                check = builder.row(name)
                assert check.expression == wanted
            checks.append(check)
        residual = substitute(output.objective, mapping) - inp.objective
        if back:
            terms = [(fixed, -target.objective.terms[offset])]
        else:
            terms = [
                (builder.row(ri, side="equal"), -source.objective.terms[i] / pivot)
                for (i, (ri, pivot)) in definitions.items()
                if source.objective.terms.get(i)
            ]
        checks.append(fact(builder, "Eq", residual, terms, terminal=True))
        Assembler(builder).assign(checks)
        builder.finish()
    return proof
