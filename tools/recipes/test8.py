"""Native test8 recipe: source/target LP -> RPA 12 -> RPX 11.

Resource-cover tightening and integer link/gate cases."""

from collections import defaultdict
from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def build(source, target, *, source_path=None, target_path=None):
    n = len(source.vars)
    assert (n, len(source.rows), len(target.vars), len(target.rows)) == (
        4914,
        13206,
        4914,
        12450,
    )
    ids = [source.vars[v.name].index for v in target.vars]
    rev = [target.vars[v.name].index for v in source.vars]
    assert all(
        (
            (
                source.vars[i].name,
                source.vars[i].lower,
                source.vars[i].upper,
                source.vars[i].integer,
            )
            == (
                target.vars[j].name,
                target.vars[j].lower,
                target.vars[j].upper,
                target.vars[j].integer,
            )
            for (j, i) in enumerate(ids)
        )
    )
    proof = Proof(source, target)
    f, r = proof.forward, proof.reverse
    f.map(default="same_name")
    r.map(default="same_name")

    def rename(e, scope):
        return scope.pullback(e)

    assert rename(target.objective, f) == source.objective
    resources = [
        r
        for r in source.rows
        if r.upper == 3
        and r.lower is None
        and all(
            (
                not source.vars[i].integer and c == 1
                for (i, c) in r.expression.terms.items()
            )
        )
    ]
    incident = defaultdict(list)
    for resource in resources:
        for i in resource.expression.terms:
            incident[i].append(resource)
    pairs = {
        frozenset(r.expression.terms): r.name
        for r in source.rows
        if r.upper == 1
        and r.lower is None
        and (len(r.expression.terms) == 2)
        and all(
            (source.vars[i].integer and c == 1 for (i, c) in r.expression.terms.items())
        )
    }
    gates = {r.name: r for r in source.rows if r.upper == 1200 and r.lower is None}
    links = {r.name: r for r in source.rows if r.upper == 0 and r.lower is None}
    assert (
        len(resources) == 2646
        and len(pairs) == 4977
        and (len(gates) == len(links) == 2457)
    )
    deleted = (
        {_row.name for _row in source.rows}
        - {_row.name for _row in target.rows}
        - {r.name[6:] for r in target.rows if r.name.startswith("tight_")}
    )
    deleted_gates = deleted & set(gates)
    deleted_cards = deleted - deleted_gates
    assert len(deleted_gates) == 441 and len(deleted_cards) == 315
    cache = {}

    def row_expr(model, name):
        row = model.rows[model.rows[name].index]
        assert row.upper is not None and row.lower is None
        return row.expression - row.upper

    def restricted(p, model, row, support):
        actual = {model.vars[source.vars[i].name].index for i in support}
        rr = model.rows[model.rows[row.name].index]
        key = (row.name, frozenset(actual))
        if p is f and key in cache:
            return cache[key]
        terms = [(p.row(row.name), 1)]
        terms.extend(
            ((p.lower(i), 1) for i in sorted(set(rr.expression.terms) - actual))
        )
        ref = Assembler(p).linear(
            "Le", terms, expect=affine(model, -3, {i: 1 for i in actual})
        )
        if p is f:
            cache[key] = ref
        return ref

    activity = {
        i: restricted(f, source, incident[i][0], {i})
        for i in range(n)
        if not source.vars[i].integer
    }

    def cases_le(builder, wanted, variable, left, right):
        case1 = builder.derive.cases(
            builder.model.vars[variable],
            kind="Le",
            expect=wanted,
            integer=builder.integer(variable),
        )
        case1_fact = left(case1.left, case1.left.assumption)
        if case1_fact is not None:
            case1.left.conclude(case1_fact)
        case1_fact = right(case1.right, case1.right.assumption)
        if case1_fact is not None:
            case1.right.conclude(case1_fact)
        return case1.finish()

    forward = {}
    covers = {}
    for name, row in links.items():
        x = next((i for (i, c) in row.expression.terms.items() if c == 1))
        y = next((i for (i, c) in row.expression.terms.items() if c == -8))
        wanted = affine(source, 0, {x: 1, y: -3})
        forward["tight_" + name] = cases_le(
            f,
            wanted,
            y,
            lambda p, z, name=name: Assembler(p).linear(
                "Le", [(p.row(name), 1), (z, 5)], expect=wanted
            ),
            lambda p, o, x=x: Assembler(p).linear(
                "Le", [(activity[x], 1), (o, 3)], expect=wanted
            ),
        )
    for name, row in gates.items():
        y = next((i for (i, c) in row.expression.terms.items() if c == 1197))
        support = set(row.expression.terms) - {y}
        if name in deleted_gates:
            cover = next(
                (
                    rr
                    for rr in incident[min(support)]
                    if support <= set(rr.expression.terms)
                )
            )
            covers[name] = [(cover, support)]
            continue
        trow = target.rows[target.rows["tight_" + name].index]
        u = trow.upper
        assert u in (6, 9, 12) and trow.lower is None
        remaining = set(support)
        chosen = []
        while remaining:
            candidates = {rr.name: rr for i in remaining for rr in incident[i]}
            rr = max(
                candidates.values(),
                key=lambda rr: (
                    len(remaining & set(rr.expression.terms)),
                    -source.rows[rr.name].index,
                ),
            )
            part = remaining & set(rr.expression.terms)
            chosen.append((rr, part))
            remaining -= part
        assert len(chosen) * 3 <= u, (name, len(chosen), u)
        bound = Assembler(f).linear(
            "Le",
            [(restricted(f, source, rr, part), 1) for (rr, part) in chosen],
            expect=affine(source, -u, {i: 1 for i in support}),
            constant=3 * len(chosen) - u,
        )
        wanted = rename(row_expr(target, "tight_" + name), f)
        forward["tight_" + name] = cases_le(
            f,
            wanted,
            y,
            lambda p, z, u=u: Assembler(p).linear(
                "Le", [(bound, 1), (z, u - 3)], expect=wanted
            ),
            lambda p, o, name=name, u=u: Assembler(p).linear(
                "Le", [(p.row(name), 1), (o, 1200 - u)], expect=wanted
            ),
        )

    def matching(support):
        if not support:
            return []
        i = min(support)
        best = [({"VarUpper": i}, 1)] + matching(support - {i})
        for j in sorted(support - {i}):
            pair = frozenset((i, j))
            if pair in pairs:
                candidate = [(pairs[pair], 1)] + matching(support - {i, j})
                if len(candidate) < len(best):
                    best = candidate
        return best

    cardcovers = {
        name: matching(set(source.rows[source.rows[name].index].expression.terms))
        for name in deleted_cards
    }
    assert all((len(x) <= 3 for x in cardcovers.values()))
    for back in (False, True):
        (inp, out) = (target, source) if back else (source, target)
        builder = r if back else f
        indices = rev if back else ids
        checks = []
        for j, v in enumerate(out.vars):
            i = indices[j]
            if v.lower is not None:
                checks.append(builder.lower(i))
            if v.upper is not None:
                checks.append(builder.upper(i))
            if v.integer:
                checks.append(builder.integer(i))
        for row in out.rows:
            name = row.name
            wanted = rename(row_expr(out, name), builder)
            if not back and name.startswith("tight_"):
                ref = forward[name]
            elif back and name in deleted_gates:
                (rr, support) = covers[name][0]
                y = next((i for (i, c) in row.expression.terms.items() if c == 1197))
                ref = Assembler(builder).linear(
                    "Le",
                    [
                        (restricted(builder, target, rr, support), 1),
                        (builder.upper(rev[y]), 1197),
                    ],
                    expect=wanted,
                )
            elif back and name in deleted_cards:
                terms = []
                for x, c in cardcovers[name]:
                    terms.append(
                        (
                            (
                                builder.row(x)
                                if isinstance(x, str)
                                else builder.upper(rev[x["VarUpper"]])
                            ),
                            c,
                        )
                    )
                ref = Assembler(builder).linear(
                    "Le", terms, expect=wanted, constant=len(terms) - 3
                )
            elif back and name in gates:
                tr = target.rows[target.rows["tight_" + name].index]
                y = next((i for (i, c) in row.expression.terms.items() if c == 1197))
                ref = Assembler(builder).linear(
                    "Le",
                    [
                        (builder.row("tight_" + name), 1),
                        (builder.upper(rev[y]), 1200 - tr.upper),
                    ],
                    expect=wanted,
                )
            elif back and name in links:
                y = next((i for (i, c) in row.expression.terms.items() if c == -8))
                ref = Assembler(builder).linear(
                    "Le",
                    [(builder.row("tight_" + name), 1), (builder.lower(rev[y]), 5)],
                    expect=wanted,
                )
            else:
                ref = builder.row(name)
            assert ref.expression == wanted
            checks.append(ref)
        checks.append(None)
        Assembler(builder).assign(checks)
        builder.finish()
    return proof
