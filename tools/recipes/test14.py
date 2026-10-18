"""Native test14 recipe: zero/bound cleanup and binary-conflict proof.

Every hint the old preparer read from audit.json is reconstructed here from the
two native models: fixed-zero witnesses, retained upper-bound witnesses, gate
rows with their target edge rows, and removed-row classifications."""

from collections import defaultdict
from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        1166,
        2295,
        1046,
        1804,
    )

    def row_kind(row):
        if row.lower is not None and row.upper is not None:
            assert row.lower == row.upper
            return "Eq"
        return "Le"

    def row_fact(row):
        if row.lower is None:
            return row.expression - row.upper
        if row.upper is None:
            return row.lower - row.expression
        assert row.lower == row.upper
        return row.expression - row.lower

    def substitute(e, mapping):
        return e.substitute(mapping)

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

    def box(builder, e, terminal=False):
        terms = []
        ceiling = e.constant
        for i, c in e.terms.items():
            v = builder.model.vars[i]
            bound = v.upper if c > 0 else v.lower
            assert bound is not None
            ceiling += c * bound
            terms.append((builder.upper(i) if c > 0 else builder.lower(i), abs(c)))
        assert ceiling <= 0, (e, ceiling)
        return fact(builder, "Le", e, terms, ceiling, terminal)

    common = [(source.vars[v.name].index, j) for (j, v) in enumerate(target.vars)]
    zeros = {i: v for (i, v) in enumerate(source.vars) if v.name not in target.vars}
    assert len(zeros) == 120
    zero_rows = {}
    for i, v in zeros.items():
        candidates = [
            r
            for r in source.rows
            if r.lower is None
            and r.upper == 0
            and (r.expression.constant == 0)
            and (set(r.expression.terms) == {i})
            and (r.expression.terms[i] > 0)
        ]
        assert len(candidates) == 1, (v.name, len(candidates))
        zero_rows[i] = candidates[0]
    bounds = {}
    for i, j in common:
        if (
            source.vars[i].upper is not None
            and source.vars[i].upper != target.vars[j].upper
        ):
            candidates = [
                r
                for r in source.rows
                if r.lower is None
                and r.upper == target.vars[j].upper
                and (r.expression.constant == 0)
                and (set(r.expression.terms) == {i})
                and (r.expression.terms[i] > 0)
            ]
            assert len(candidates) == 1, (source.vars[i].name, len(candidates))
            bounds[i] = candidates[0]
    assert len(bounds) == 118
    gates = {}
    for row in source.rows:
        terms = row.expression.terms
        if (
            row.lower is not None
            or row.upper != 1
            or row.expression.constant != 0
            or (len(terms) < 2)
        ):
            continue
        centers = [i for (i, c) in terms.items() if c == 1]
        if len(centers) != 1 or not source.vars[centers[0]].integer:
            continue
        if not all(
            (c == Fraction(1, 4) for (i, c) in terms.items() if i != centers[0])
        ):
            continue
        gates[row.name] = (centers[0], [i for i in terms if i != centers[0]])
    assert len(gates) == 88
    proof = Proof(source, target)
    f, r = proof.forward, proof.reverse
    f.map(default="same_name")
    r.map({source.vars[i].name: 0 for i in zeros}, default="same_name")
    forward, reverse = f.mapping, r.mapping

    pair_rows = defaultdict(list)
    for row in target.rows:
        terms = row.expression.terms
        if (
            row.lower is None
            and row.upper == 1
            and (row.expression.constant == 0)
            and (len(terms) == 2)
            and all((c == 1 for c in terms.values()))
        ):
            pair_rows[frozenset((next(iter(forward[j].terms)) for j in terms))].append(
                row.name
            )
    edges = {}
    gate_edges = {}
    for name, (center, neighbors) in gates.items():
        gate_edges[name] = []
        for neighbor in neighbors:
            key = frozenset((center, neighbor))
            assert len(pair_rows[key]) == 1, (name, key, pair_rows[key])
            edge_name = pair_rows[key][0]
            gate_edges[name].append(edge_name)
            edges[edge_name] = (name, center, neighbors, neighbor)
    assert len(edges) == 246
    zeroeq = {}
    for i, row in zero_rows.items():
        ref = f.row(row.name)
        e = ref.expression
        assert e.constant == 0 and set(e.terms) == {i} and (e.terms[i] > 0)
        zeroeq[i] = f.derive.eqpair(
            fact(f, "Le", affine(source, 0, {i: 1}), [(ref, Fraction(1) / e.terms[i])]),
            f.lower(i),
        )
    edge_facts = {}
    for name, (center, neighbors) in gates.items():
        ref = f.row(name)
        for neighbor, edge_name in zip(neighbors, gate_edges[name]):
            wanted = affine(source, -1, {center: 1, neighbor: 1})

            def left(child, assumption, neighbor=neighbor):
                return Assembler(child).linear(
                    "Le",
                    [(child.upper(neighbor), Fraction(1)), (assumption, Fraction(1))],
                    expect=wanted,
                )

            def right(child, assumption, neighbor=neighbor):
                terms = [(ref, Fraction(4))]
                terms.extend(
                    ((child.lower(k), Fraction(1)) for k in neighbors if k != neighbor)
                )
                terms.append((assumption, Fraction(3)))
                return Assembler(child).linear("Le", terms, expect=wanted)

            case1 = f.derive.cases(
                source.vars[center], kind="Le", expect=wanted, integer=f.integer(center)
            )
            case1_fact = left(case1.left, case1.left.assumption)
            if case1_fact is not None:
                case1.left.conclude(case1_fact)
            case1_fact = right(case1.right, case1.right.assumption)
            if case1_fact is not None:
                case1.right.conclude(case1_fact)
            edge_facts[edge_name] = case1.finish()
    for back in (False, True):
        (inp, out) = (target, source) if back else (source, target)
        builder = r if back else f
        mapping = reverse if back else forward
        checks = []
        for i, v in enumerate(out.vars):
            e = mapping[i]
            for kind, value, sign in (
                ("VarLower", v.lower, -1),
                ("VarUpper", v.upper, 1),
            ):
                if value is None:
                    continue
                wanted = e * sign - sign * value
                if not back and kind == "VarUpper" and (next(iter(e.terms)) in bounds):
                    j = next(iter(e.terms))
                    ref = builder.row(bounds[j].name)
                    coefficient = ref.expression.terms[j]
                    check = fact(
                        builder,
                        "Le",
                        wanted,
                        [(ref, Fraction(1) / coefficient)],
                        terminal=True,
                    )
                else:
                    check = box(builder, wanted, True)
                checks.append(check)
            if v.integer:
                checks.append(
                    fact(
                        builder,
                        "Int",
                        e,
                        [(builder.integer(j), c) for (j, c) in e.terms.items()],
                        e.constant,
                        True,
                    )
                )
        for row in out.rows:
            name = row.name
            kind = row_kind(row)
            wanted = substitute(row_fact(row), mapping)
            if back:
                if name in target.rows:
                    check = builder.row(name)
                    assert check.expression == wanted, name
                elif exact(kind, wanted):
                    check = None
                elif name in gates:
                    (center, neighbors) = gates[name]
                    terms = [
                        (builder.row(edge), Fraction(1, 4)) for edge in gate_edges[name]
                    ]
                    if len(neighbors) < 4:
                        terms.append(
                            (
                                builder.upper(
                                    target.vars[source.vars[center].name].index
                                ),
                                Fraction(1) - Fraction(len(neighbors), 4),
                            )
                        )
                    check = fact(builder, "Le", wanted, terms, terminal=True)
                else:
                    matches = [
                        candidate
                        for candidate in target.rows
                        if row_kind(candidate) == kind and row_fact(candidate) == wanted
                    ]
                    if matches:
                        assert len(matches) == 1, (name, [m.name for m in matches])
                        check = builder.row(matches[0].name)
                        assert check.expression == wanted, name
                    else:
                        check = box(builder, wanted, True)
            elif name in edge_facts:
                check = edge_facts[name]
                assert check.expression == wanted, name
            else:
                ref = builder.row(name)
                assert ref.expression == row_fact(
                    source.rows[source.rows[name].index]
                ), name
                term_list = [(ref, Fraction(1))]
                term_list.extend(
                    (
                        (zeroeq[i], -c)
                        for (i, c) in ref.expression.terms.items()
                        if i in zeros
                    )
                )
                check = fact(builder, kind, wanted, term_list, terminal=True)
            checks.append(check)
        wanted = substitute(out.objective, mapping) - inp.objective
        if back:
            terms = []
        else:
            terms = [
                (zeroeq[i], -c)
                for (i, c) in source.objective.terms.items()
                if i in zeros
            ]
        checks.append(fact(builder, "Eq", wanted, terms, terminal=True))
        Assembler(builder).assign(checks)
        builder.finish()
    return proof
