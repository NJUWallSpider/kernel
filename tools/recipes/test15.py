"""Native test15 recipe: singleton elimination with an exact fixed offset column."""

from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        4516,
        32,
        4485,
        32,
    )
    removed = {i for (i, v) in enumerate(source.vars) if v.name not in target.vars}
    assert len(removed) == 32
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
            len(incidence[i]) == 1 and v.integer and (v.lower == 0) and (v.upper == 1)
        )
        ri = incidence[i][0]
        row = source.rows[ri]
        pivot = row.expression.terms[i]
        assert (
            row.lower == row.upper
            and row.lower is not None
            and (pivot == 1)
            and (ri not in byrow)
        )
        terms = {
            target.vars[source.vars[j].name].index: -c / pivot
            for (j, c) in row.expression.terms.items()
            if j != i
        }
        reverse[v.name] = affine(target, row.lower / pivot, terms)
        definitions[i] = (ri, pivot)
        byrow[ri] = i
    proof = Proof(source, target)
    (f, r) = (proof.forward, proof.reverse)
    f.map({target.vars[offset].name: 1}, default="same_name")
    r.map(reverse, default="same_name")
    forward, reverse = f.mapping, r.mapping

    def exact(kind, e):
        return not e.terms and (
            kind == "Eq"
            and e.constant == 0
            or (kind == "Le" and e.constant <= 0)
            or (kind == "Int" and e.constant.denominator == 1)
        )

    def fact(builder, kind, e, terms=(), constant=0, terminal=False):
        if terminal and exact(kind, e):
            return None
        if (
            len(terms) == 1
            and terms[0][1] == 1
            and (not constant)
            and (terms[0][0].kind == kind)
            and (terms[0][0].expression == e)
        ):
            return terms[0][0]
        return Assembler(builder).linear(kind, list(terms), expect=e, constant=constant)

    def substitute(e, mapping):
        return e.substitute(mapping)

    checks = []
    for i, v in enumerate(target.vars):
        e = forward[i]
        for kind, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = e * sign - sign * value
            if exact("Le", wanted):
                check = None
            else:
                check = next(iter(e.terms))
                check = f.lower(check) if kind == "VarLower" else f.upper(check)
                assert check.expression == wanted
            checks.append(check)
        if v.integer:
            checks.append(
                fact(
                    f,
                    "Int",
                    e,
                    [(f.integer(j), c) for (j, c) in e.terms.items()],
                    e.constant,
                    True,
                )
            )
    for row in target.rows:
        name = row.name
        kind = "Eq" if row.equality else "Le"
        wanted = substitute(
            row.expression - (row.upper if row.lower is None else row.lower), forward
        )
        if source.rows[name].index in byrow:
            i = byrow[source.rows[name].index]
            assert kind == "Le" and row.lower is None
            check = fact(
                f, "Le", wanted, [(f.row(name), Fraction(1)), (f.lower(i), Fraction(1))]
            )
        else:
            check = f.row(name)
            assert check.expression == wanted, name
        checks.append(check)
    residual = substitute(target.objective, forward) - source.objective
    terms = [
        (f.row(ri, side="equal"), -source.objective.terms.get(i, Fraction(0)) / pivot)
        for (i, (ri, pivot)) in definitions.items()
        if source.objective.terms.get(i)
    ]
    checks.append(fact(f, "Eq", residual, terms, terminal=True))
    Assembler(f).assign(checks)
    f.finish()
    fixed = r.derive.eqpair(r.upper(offset), r.lower(offset))
    checks = []
    for i, v in enumerate(source.vars):
        e = reverse[i]
        for kind, value, sign in (("VarLower", v.lower, -1), ("VarUpper", v.upper, 1)):
            if value is None:
                continue
            wanted = e * sign - sign * value
            if exact("Le", wanted):
                check = None
            elif i in definitions:
                name = source.rows[definitions[i][0]].name
                if kind == "VarLower":
                    check = r.row(name)
                    assert check.expression == wanted, name
                else:
                    check = "box"
            else:
                j = next(iter(e.terms))
                check = r.lower(j) if kind == "VarLower" else r.upper(j)
                assert check.expression == wanted
            if check == "box":
                terms = []
                ceiling = wanted.constant
                for j, c in wanted.terms.items():
                    bound = target.vars[j].upper if c > 0 else target.vars[j].lower
                    assert bound is not None
                    ceiling += c * bound
                    terms.append((r.upper(j) if c > 0 else r.lower(j), abs(c)))
                assert ceiling <= 0
                check = fact(r, "Le", wanted, terms, ceiling, True)
            checks.append(check)
        if v.integer:
            checks.append(
                fact(
                    r,
                    "Int",
                    e,
                    [(r.integer(j), c) for (j, c) in e.terms.items()],
                    e.constant,
                    True,
                )
            )
    for row in source.rows:
        name = row.name
        kind = "Eq" if row.equality else "Le"
        wanted = substitute(
            row.expression - (row.upper if row.lower is None else row.lower), reverse
        )
        if source.rows[name].index in byrow:
            assert exact("Eq", wanted)
            check = None
        else:
            check = r.row(name)
            assert check.expression == wanted, name
        checks.append(check)
    residual = substitute(source.objective, reverse) - target.objective
    checks.append(
        fact(
            r, "Eq", residual, [(fixed, -target.objective.terms[offset])], terminal=True
        )
    )
    Assembler(r).assign(checks)
    r.finish()
    return proof
