"""Native test10 recipe: shared load budget with exact threshold cuts.

The source has 200 shared-load equalities and a 950-row assignment system.  The
target substitutes the load columns, tightens the activation links at the exact
budget cutoff, replaces the selector rows by an interval lift, and removes the
selector coordinate.  Every threshold and branch below is derived from the two
models; no reformulation hints are read.
"""

from rpx import Q as Fraction
from rpx import Expr, Proof, IntervalSpec, MenuSpec
from rpx.lowlevel import Assembler, affine


def exact(kind, expression):
    if expression.terms:
        return False
    if kind == "Eq":
        return expression.constant == 0
    if kind == "Le":
        return expression.constant <= 0
    return expression.constant.denominator == 1


def fact(builder, kind, expression, terms=(), constant=0, terminal=False):
    if terminal and exact(kind, expression):
        return None
    if (
        len(terms) == 1
        and terms[0][1] == 1
        and (not constant)
        and (terms[0][0].kind == kind)
        and (terms[0][0].expression == expression)
    ):
        return terms[0][0]
    return Assembler(builder).linear(kind, terms, expect=expression, constant=constant)


def box(builder, expression, terminal=False):
    terms = []
    ceiling = expression.constant
    for i, coefficient in expression.terms.items():
        variable = builder.model.vars[i]
        bound = variable.upper if coefficient > 0 else variable.lower
        assert bound is not None, (
            "unbounded box coordinate",
            variable.name,
            coefficient,
        )
        ceiling += coefficient * bound
        terms.append(
            (
                builder.upper(i) if coefficient > 0 else builder.lower(i),
                abs(coefficient),
            )
        )
    assert ceiling <= 0, ("box not valid", expression, ceiling)
    return fact(builder, "Le", expression, terms, ceiling, terminal)


def row_kind(row):
    if row.lower is not None and row.upper is not None:
        assert row.lower == row.upper
        return "RowEq"
    if row.lower is None:
        return "RowUpper"
    assert row.upper is None
    return "RowLower"


def row_fact(row, kind):
    if kind == "RowUpper":
        return row.expression - row.upper
    if kind == "RowLower":
        return row.lower - row.expression
    return row.expression - row.lower


def substitute(expression, mapping):
    return expression.substitute(mapping)


def build(source, target, *, source_path=None, target_path=None):
    assert (len(source.vars), len(source.rows), len(target.vars), len(target.rows)) == (
        190402,
        2303,
        190201,
        2105,
    )
    assert all((row.expression.constant == 0 for row in source.rows))
    assert all((row.expression.constant == 0 for row in target.rows))
    common = [
        (source.vars[variable.name].index, j)
        for (j, variable) in enumerate(target.vars)
    ]
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
            for (i, j) in common
        )
    )
    proof = Proof(source, target)
    f, r = proof.forward, proof.reverse
    f.map(default="same_name")
    forward = f.mapping
    assignment = {}
    assignment_names = []
    for k in range(950):
        name = f"R{951 + k:04d}"
        row = source.rows[source.rows[name].index]
        assert row.lower == row.upper == 1 and len(row.expression.terms) == 200
        assert all((coefficient == 1 for coefficient in row.expression.terms.values()))
        assignment_names.append(name)
        for index in row.expression.terms:
            assert index not in assignment
            assignment[index] = name
    load_rows = {}
    for ri, row in enumerate(source.rows):
        if row.lower != 0 or row.upper != 0 or len(row.expression.terms) != 951:
            continue
        negative = [i for (i, c) in row.expression.terms.items() if c < 0]
        if len(negative) != 1:
            continue
        pivot = negative[0]
        variable = source.vars[pivot]
        if (
            variable.name in target.vars
            or variable.integer
            or variable.lower != 0
            or (variable.upper is not None)
        ):
            continue
        if row.expression.terms[pivot] != -1 or not all(
            (c > 0 for (i, c) in row.expression.terms.items() if i != pivot)
        ):
            continue
        load_rows[pivot] = ri
    assert len(load_rows) == 200
    removed = {
        i
        for (i, variable) in enumerate(source.vars)
        if variable.name not in target.vars
    }
    assert len(removed) == 201
    extra = removed - set(load_rows)
    assert len(extra) == 1
    selector_index = next(iter(extra))
    link_by_signature = {}
    link_rows = {}
    for ri, row in enumerate(source.rows):
        if row.lower is not None or row.upper != 0 or len(row.expression.terms) != 951:
            continue
        negative = [i for (i, c) in row.expression.terms.items() if c < 0]
        if len(negative) != 1:
            continue
        activation = negative[0]
        if not all(
            (c == 1 for (i, c) in row.expression.terms.items() if i != activation)
        ):
            continue
        support = frozenset((i for i in row.expression.terms if i != activation))
        assert support not in link_by_signature
        link_by_signature[support] = activation
        link_rows[activation] = row.name
    assert len(link_rows) == 200
    loads = {}
    load_expr = {}
    counts = {}
    groups = {}
    weights = {}
    for pivot in sorted(load_rows):
        row = source.rows[load_rows[pivot]]
        terms = {i: c for (i, c) in row.expression.terms.items() if i != pivot}
        activation = link_by_signature[frozenset(terms)]
        assert activation not in groups
        loads[pivot] = None
        load_expr[pivot] = affine(source, 0, terms)
        counts[pivot] = affine(source, 0, {i: 1 for i in terms})
        groups[activation] = (pivot, source.vars[activation].name)
        for index, coefficient in terms.items():
            name = assignment[index]
            assert name not in weights or weights[name] == coefficient
            weights[name] = coefficient
    assert set(weights) == set(assignment_names)
    budget_rows = [row for row in source.rows if row.upper == 900000000]
    assert len(budget_rows) == 1 and budget_rows[0].lower is None
    budget_row = budget_rows[0]
    assert len(budget_row.expression.terms) == 400
    assert set(budget_row.expression.terms) == set(loads) | set(groups)
    costs = {}
    charges = {}
    for activation, (pivot, name) in groups.items():
        costs[activation] = budget_row.expression.terms[pivot]
        charges[activation] = budget_row.expression.terms[activation]
        assert costs[activation] > 0 and charges[activation] > 0
    special = list(groups)[:4]
    assert [source.vars[i].name for i in special] == [
        "C190202",
        "C190203",
        "C190204",
        "C190205",
    ]
    cmin = min(costs.values())
    total_weight = sum(weights.values())
    prefix = [Fraction(0)]
    for weight in sorted(weights.values()):
        prefix.append(prefix[-1] + weight)
    for pivot in loads:
        loads[pivot] = f.row(source.rows[load_rows[pivot]].name)
    total = Assembler(f).linear(
        "Eq",
        [(loads[pivot], -1) for pivot in loads]
        + [(f.row(name), weight) for (name, weight) in weights.items()],
        expect=affine(source, -total_weight, {pivot: 1 for pivot in loads}),
    )
    base = Assembler(f).linear("Le", [(f.row(budget_row.name), 1), (total, -cmin)])
    fixed4 = affine(source, 0, {i: -charges[i] for i in special})

    def pair_charge(pair, activation=None):
        value = sum((charges[i] for i in pair))
        if activation is not None and activation not in pair:
            value += charges[activation]
        return value

    def selector_fact(builder, wanted):

        def branch(child, assumption, side):
            pair = special[:2] if side else special[2:]
            row = child.row("R2302" if side else "R2303")
            forced = {}
            for i, j in (pair, pair[::-1]):
                forced[i] = Assembler(child).linear(
                    "Le",
                    [(row, 1), (assumption, 2), (child.upper(j), 1)],
                    expect=affine(source, 1, {i: -1}),
                )
            terms = []
            ceiling = wanted.constant
            for i, coefficient in wanted.terms.items():
                if coefficient > 0:
                    (ref, value) = (child.upper(i), 1)
                elif i in forced:
                    (ref, value) = (forced[i], 1)
                else:
                    (ref, value) = (child.lower(i), 0)
                terms.append((ref, abs(coefficient)))
                ceiling += coefficient * value
            assert ceiling <= 0
            return Assembler(child).linear("Le", terms, expect=wanted, constant=ceiling)

        case1 = builder.derive.cases(
            source.vars[selector_index],
            kind="Le",
            expect=wanted,
            integer=builder.integer(selector_index),
        )
        case1_fact = (lambda child, assumption: branch(child, assumption, 0))(
            case1.left, case1.left.assumption
        )
        if case1_fact is not None:
            case1.left.conclude(case1_fact)
        case1_fact = (lambda child, assumption: branch(child, assumption, 1))(
            case1.right, case1.right.assumption
        )
        if case1_fact is not None:
            case1.right.conclude(case1_fact)
        return case1.finish()

    pair_min = min(pair_charge(special[:2]), pair_charge(special[2:]))
    global_fixed = selector_fact(f, Expr(pair_min) + fixed4)
    fixed_cond = {}
    for activation in special:
        value = min(
            pair_charge(special[:2], activation), pair_charge(special[2:], activation)
        )
        fixed_cond[activation] = selector_fact(
            f, fixed4 + affine(source, 0, {activation: value})
        )
    tightened = {}
    tightened_owner = {}
    tightened_bound = {}
    for activation, (pivot, name) in groups.items():
        row_name = link_rows[activation]
        old = f.row(row_name)
        count = counts[pivot]
        assert old.expression == count + affine(source, 0, {activation: -950})
        fixed = min(
            pair_charge(special[:2], activation), pair_charge(special[2:], activation)
        )
        delta = costs[activation] - cmin
        limit = (
            950
            if delta == 0
            else max(
                (
                    k
                    for (k, value) in enumerate(prefix)
                    if delta * value + cmin * total_weight + fixed <= budget_row.upper
                )
            )
        )
        target_row = target.rows[target.rows[row_name].index]
        assert row_kind(target_row) == "RowUpper"
        assert substitute(row_fact(target_row, "RowUpper"), forward) == count + affine(
            source, 0, {activation: -limit}
        )
        if limit == 950:
            continue
        assert delta > 0 and 0 < limit < 950
        terms = [(base, 1)]
        for other, (other_pivot, _) in groups.items():
            if other != activation and costs[other] > cmin:
                terms.append((f.lower(other_pivot), costs[other] - cmin))
        if activation in special:
            terms.append((fixed_cond[activation], 1))
            for other in groups:
                if other not in special:
                    terms.append((f.lower(other), charges[other]))
        else:
            terms.append((global_fixed, 1))
            terms.append((f.upper(activation), pair_min))
            for other in groups:
                if other not in special and other != activation:
                    terms.append((f.lower(other), charges[other]))
        conditional = Assembler(f).linear(
            "Le",
            terms,
            expect=affine(
                source,
                cmin * total_weight - budget_row.upper,
                {pivot: delta, activation: fixed},
            ),
        )
        threshold = sorted(weights.values())[int(limit)]
        correction = sum(
            (max(Fraction(0), threshold - weight) for weight in weights.values())
        )
        boxterms = []
        for index, weight in load_expr[pivot].terms.items():
            if threshold > weight:
                boxterms.append((f.upper(index), threshold - weight))
            elif threshold < weight:
                boxterms.append((f.lower(index), weight - threshold))
        support = Assembler(f).linear(
            "Le", boxterms, expect=count * threshold - load_expr[pivot] - correction
        )
        integer = Assembler(f).linear(
            "Int", [(f.integer(i), 1) for i in count.terms], expect=count
        )
        wanted = count + affine(source, 0, {activation: -limit})

        def zero(child, assumption, old=old, limit=limit, wanted=wanted):
            return Assembler(child).linear(
                "Le", [(old, 1), (assumption, 950 - limit)], expect=wanted
            )

        def one(
            child,
            assumption,
            pivot=pivot,
            delta=delta,
            fixed=fixed,
            threshold=threshold,
            conditional=conditional,
            support=support,
            integer=integer,
            limit=limit,
            wanted=wanted,
        ):
            weightbound = Assembler(child).linear(
                "Le", [(conditional, 1), (assumption, fixed), (loads[pivot], delta)]
            )
            bound = Assembler(child).linear(
                "Le", [(weightbound, 1 / (delta * threshold)), (support, 1 / threshold)]
            )
            rounded = child.derive.round(bound, integer)
            assert rounded.expression == count - limit
            return Assembler(child).linear(
                "Le", [(rounded, 1), (assumption, limit)], expect=wanted
            )

        case2 = f.derive.cases(
            source.vars[activation],
            kind="Le",
            expect=wanted,
            integer=f.integer(activation),
        )
        case2_fact = zero(case2.left, case2.left.assumption)
        if case2_fact is not None:
            case2.left.conclude(case2_fact)
        case2_fact = one(case2.right, case2.right.assumption)
        if case2_fact is not None:
            case2.right.conclude(case2_fact)
        tightened[row_name] = case2.finish()
        tightened_owner[row_name] = activation
        tightened_bound[row_name] = limit
    assert len(tightened) == 170
    selector = {}
    for row in target.rows:
        if row.name in source.rows:
            continue
        wanted = substitute(row_fact(row, "RowLower"), forward)
        selector[row.name] = selector_fact(f, wanted)
    checks = []
    for i, j in common:
        variable = target.vars[j]
        if variable.lower is not None:
            checks.append(f.lower(i))
        if variable.upper is not None:
            checks.append(f.upper(i))
        if variable.integer:
            checks.append(f.integer(i))
    for row in target.rows:
        name = row.name
        kind = row_kind(row)
        wanted = substitute(row_fact(row, kind), forward)
        if name in tightened:
            ref = tightened[name]
        elif name in selector:
            ref = selector[name]
        elif name == budget_row.name:
            ref = Assembler(f).linear(
                "Le",
                [(f.row(budget_row.name), 1)]
                + [
                    (loads[pivot], budget_row.expression.terms[pivot])
                    for pivot in loads
                ],
                expect=wanted,
            )
        else:
            ref = f.row(name)
        assert ref.expression == wanted
        checks.append(ref)
    assert substitute(target.objective, forward) == source.objective
    checks.append(None)
    Assembler(f).assign(checks)
    f.finish()
    bs = [target.vars[source.vars[i].name].index for i in special]
    (aa, bb, cc, dd) = bs
    lower = [
        Expr(),
        affine(target, -1, {aa: 1, bb: 1}),
        affine(target, 1, {cc: Fraction(-1, 2), dd: Fraction(-1, 2)}),
    ]
    upper = [affine(target, 0, {aa: 1}), affine(target, 0, {bb: 1})]
    premises = []
    for k, value in enumerate(lower):
        for j in range(2):
            wanted = value - upper[j]
            if k < 2:
                ref = box(r, wanted, True)
            else:
                ref = Assembler(r).linear(
                    "Le",
                    [
                        (r.row(f"P{1 + 2 * j:04d}"), Fraction(1, 2)),
                        (r.row(f"P{2 + 2 * j:04d}"), Fraction(1, 2)),
                    ],
                    expect=wanted,
                )
            premises.append(ref)
    extension = r.lift_intervals([IntervalSpec(lower, upper, premises)])
    lifted = extension.scope
    interval = extension[0]
    assert len(interval.lower_rows) == 3 and len(interval.upper_rows) == 2
    lo = interval.lower_rows
    hi = interval.upper_rows
    ze = extension.variable
    generated = ze.index
    retained = {
        source.vars[i].name: 0
        for i in range(len(source.vars))
        if source.vars[i].name not in target.vars
    }
    lifted.map(retained, default="same_name")
    reverse = {
        source.vars[pivot].name: lifted.pullback(value)
        for pivot, value in load_expr.items()
    }
    reverse[source.vars[selector_index].name] = ze
    lifted.map(reverse, default="same_name")
    reverse = lifted.mapping

    zupper = Assembler(lifted).linear(
        "Le", [(hi[0], 1), (lifted.upper(aa), 1)], expect=ze - 1
    )

    def azero(child, assumption):
        up = Assembler(child).linear("Le", [(hi[0], 1), (assumption, 1)], expect=ze)
        return Assembler(child).linear(
            "Int", [(child.derive.eqpair(up, lo[0]), 1)], expect=ze
        )

    def aone(child, assumption):

        def bzero(inner, branch):
            up = Assembler(inner).linear("Le", [(hi[1], 1), (branch, 1)], expect=ze)
            return Assembler(inner).linear(
                "Int", [(inner.derive.eqpair(up, lo[0]), 1)], expect=ze
            )

        def bone(inner, branch):
            low = Assembler(inner).linear(
                "Le", [(lo[1], 1), (assumption, 1), (branch, 1)], expect=Expr(1) - ze
            )
            return Assembler(inner).linear(
                "Int", [(inner.derive.eqpair(zupper, low), 1)], expect=ze, constant=1
            )

        case3 = child.derive.cases(
            lifted.model.vars[bb], kind="Int", expect=ze, integer=child.integer(bb)
        )
        case3_fact = bzero(case3.left, case3.left.assumption)
        if case3_fact is not None:
            case3.left.conclude(case3_fact)
        case3_fact = bone(case3.right, case3.right.assumption)
        if case3_fact is not None:
            case3.right.conclude(case3_fact)
        return case3.finish()

    case4 = lifted.derive.cases(
        lifted.model.vars[aa], kind="Int", expect=ze, integer=lifted.integer(aa)
    )
    case4_fact = azero(case4.left, case4.left.assumption)
    if case4_fact is not None:
        case4.left.conclude(case4_fact)
    case4_fact = aone(case4.right, case4.right.assumption)
    if case4_fact is not None:
        case4.right.conclude(case4_fact)
    zint = case4.finish()
    checks = []
    for i, variable in enumerate(source.vars):
        value = reverse[i]
        if i == selector_index:
            checks += [lo[0], zupper, zint]
        elif i in loads:
            checks.append(box(lifted, value * -1, True))
        else:
            j = next(iter(value.terms))
            assert value == affine(lifted.model, 0, {j: 1})
            if variable.lower is not None:
                checks.append(lifted.lower(j))
            if variable.upper is not None:
                checks.append(lifted.upper(j))
            if variable.integer:
                checks.append(lifted.integer(j))
    for row in source.rows:
        name = row.name
        kind = row_kind(row)
        wanted = substitute(row_fact(row, kind), reverse)
        if exact("Eq" if kind == "RowEq" else "Le", wanted):
            ref = None
        elif name == "R2302":
            ref = Assembler(lifted).linear(
                "Le", [(hi[0], 1), (hi[1], 1)], expect=wanted
            )
        elif name == "R2303":
            ref = Assembler(lifted).linear("Le", [(lo[2], 2)], expect=wanted)
        elif name in tightened:
            activation = tightened_owner[name]
            ref = Assembler(lifted).linear(
                "Le",
                [
                    (lifted.row(name), 1),
                    (
                        lifted.lower(target.vars[source.vars[activation].name].index),
                        950 - tightened_bound[name],
                    ),
                ],
                expect=wanted,
            )
        else:
            ref = lifted.row(name)
        assert ref == None or ref.expression == wanted
        checks.append(ref)
    assert substitute(source.objective, reverse) == target.objective
    checks.append(None)
    Assembler(lifted).assign(checks)
    lifted.finish()
    return proof
