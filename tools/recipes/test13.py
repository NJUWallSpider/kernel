"""Native test13 private one-hot menu projection proof.

The proof is constructed through the public ``rpx`` API and compiled
to RPA 12 / RPX 11 by the native compiler.  The legacy four-claim Request
layout collapses to the two MI-OPT directions: the linear target-to-source map
and one simultaneous integer menu lift that reconstructs all private source
options.  Menu and row associations are read from the reformulation audit.
"""

from rpx import Q as Fraction
from pathlib import Path
import json
from rpx import Expr, Fact, Proof, MenuSpec
from rpx.lowlevel import Assembler, affine


def expression(space, constant=0, terms=None):
    return affine(
        space,
        Fraction(constant),
        {i: Fraction(c) for (i, c) in (terms or {}).items() if c},
    )


def row_expr(row):
    """The row's fact expression: equality/upper rows are expr - rhs."""
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


def build(source, target, *, source_path=None, target_path=None):
    hints = json.loads(
        (Path(source_path).resolve().parent.parent / "output/audit.json").read_text()
    )
    (a, b) = (source, target)
    assert (len(a.vars), len(a.rows), len(b.vars), len(b.rows)) == (
        10399,
        14589,
        5677,
        14571,
    )
    common = [[a.vars[v.name].index, j] for (j, v) in enumerate(b.vars)]
    for i, j in common:
        assert (
            a.vars[i].name,
            a.vars[i].lower,
            a.vars[i].upper,
            a.vars[i].integer,
        ) == (b.vars[j].name, b.vars[j].lower, b.vars[j].upper, b.vars[j].integer)
    proof = Proof(source, target)
    f, r = proof.forward, proof.reverse
    f.map(default="same_name")
    forward = f.mapping
    definitions = []
    removed = set()
    raw_added = {}
    for d in hints["blocks"]:
        (L, U, c) = map(Fraction, (d["lower"], d["upper"], d["target"]))
        (x, g, cy) = [
            a.vars[d[key]].index for key in ("x", "trigger", "special_indicator")
        ]
        options = sorted(
            ((Fraction(v), a.vars[n].index) for (n, v) in d["indicator_values"].items())
        )
        assert [v for (v, i) in options] == list(
            range(int(L), int(U) + 1)
        ) and L < c < U
        assert options[int(c - L)][1] == cy
        assert not removed & {i for (v, i) in options}
        removed.update((i for (v, i) in options))
        for v, i in options:
            assert a.vars[i].integer and a.vars[i].lower == 0 and (a.vars[i].upper == 1)
        sum_row = a.rows[a.rows[d["sum_row"]].index]
        value_row = a.rows[a.rows[d["value_row"]].index]
        link_row = a.rows[a.rows[d["link_row"]].index]
        assert sum_row.lower == sum_row.upper
        assert value_row.lower == value_row.upper
        assert link_row.lower is None and link_row.upper == 0
        assert row_expr(sum_row) == expression(source, -1, {i: 1 for (v, i) in options})
        assert row_expr(value_row) == expression(
            source, 0, {**{i: v for (v, i) in options if v}, x: -1}
        )
        assert row_expr(link_row) == expression(source, 0, {g: 1, cy: -1})
        raw_added[d["added_lower_row"]] = [
            (d["value_row"], 1),
            (d["sum_row"], -L),
            (d["link_row"], c - L),
        ] + [("lower", i, v - L) for (v, i) in options if v != c and v != L]
        raw_added[d["added_upper_row"]] = [
            (d["value_row"], -1),
            (d["sum_row"], U),
            (d["link_row"], U - c),
        ] + [("lower", i, U - v) for (v, i) in options if v != c and v != U]
        definitions.append(
            {
                **d,
                "L": L,
                "U": U,
                "c": c,
                "x_id": b.vars[d["x"]].index,
                "g_id": b.vars[d["trigger"]].index,
                "options": [i for (v, i) in options],
            }
        )
    assert removed == {i for (i, v) in enumerate(a.vars) if v.name not in b.vars}
    assert len(removed) == 4722

    def added_terms(builder, entries):
        terms = []
        for entry in entries:
            if entry[0] == "lower":
                terms.append((builder.lower(entry[1]), Fraction(entry[2])))
            else:
                terms.append((builder.row(entry[0]), Fraction(entry[1])))
        return terms

    def prove(builder, kind, wanted, terms):
        """Attach one exact model fact or a native linear rule to an obligation."""
        if is_exact(kind, wanted):
            return None
        if isinstance(terms, Fact):
            assert terms.kind in (kind, "Eq") and terms.expression == wanted
            return terms
        if terms is None:
            raise AssertionError(("no premise", kind, wanted))
        if len(terms) == 1 and terms[0][1] == 1:
            fact = terms[0][0]
            if fact.kind in (kind, "Eq") and fact.expression == wanted:
                return fact
        return Assembler(builder).linear(
            kind, [(ref, Fraction(c)) for (ref, c) in terms], expect=wanted
        )

    def finish_checks(
        builder, output, mapping, domain_terms, row_terms, input_objective
    ):
        """Build Return checks in the order of the native obligation walker."""
        checks = []
        for i, variable in enumerate(output.vars):
            if variable.lower is not None:
                wanted = Expr(variable.lower) - mapping[i]
                checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarLower")))
            if variable.upper is not None:
                wanted = mapping[i] - Expr(variable.upper)
                checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarUpper")))
            if variable.integer:
                checks.append(
                    prove(builder, "Int", mapping[i], domain_terms(i, "VarInt"))
                )
        for i, row in enumerate(output.rows):
            typ = (
                "RowEq"
                if row.lower is not None and row.lower == row.upper
                else "RowUpper" if row.lower is None else "RowLower"
            )
            wanted = substitute(row_expr(row), mapping)
            checks.append(
                prove(builder, "Eq" if typ == "RowEq" else "Le", wanted, row_terms(i))
            )
        residual = substitute(output.objective, mapping) - input_objective
        checks.append(prove(builder, "Le", residual, []))
        return checks

    def forward_domain(i, kind):
        j = common[i][0]
        if kind == "VarLower":
            return f.lower(j)
        if kind == "VarUpper":
            return f.upper(j)
        return f.integer(j)

    def forward_row(i):
        name = b.rows[i].name
        if name in raw_added:
            return added_terms(f, raw_added[name])
        if name in a.rows:
            return [(f.row(name), Fraction(1))]
        raise AssertionError(("missing forwarded row", name))

    forward_checks = finish_checks(
        f, b, forward, forward_domain, forward_row, a.objective
    )
    Assembler(f).assign(forward_checks)
    f.finish()
    entries = []
    for d in definitions:
        (L, U, c, x) = (d["L"], d["U"], d["c"], d["x_id"])
        index = expression(target, -L, {x: 1})
        integer = Assembler(r).linear(
            "Int", [(r.integer(x), Fraction(1))], constant=-L, expect=index
        )
        entries.append(
            MenuSpec(
                int(U - L),
                1,
                index,
                [None, None, None, r.lower(x), r.upper(x), integer],
            )
        )
    extension = r.lift_menus(entries)
    child = extension.scope
    layout = extension
    assert len(layout) == len(definitions)
    mapping = {}
    rowproof = {}
    for d, generated in zip(definitions, layout):
        (L, U, c, x, g) = (d["L"], d["U"], d["c"], d["x_id"], d["g_id"])
        K = int(U - L)
        j = int(c - L)
        options = d["options"]
        op = [v.index for v in generated.options]
        assert len(op) == K + 1
        sumref = generated.sum
        moment = generated.moment
        for src, fresh in zip(options, op):
            mapping[a.vars[src].name] = child.vars[fresh]
        rowproof[d["sum_row"]] = [(sumref, Fraction(1))]
        rowproof[d["value_row"]] = [(moment, Fraction(1)), (sumref, L)]
        zc = op[j]
        goal = expression(child.model, 0, {g: 1, zc: -1})

        def active(
            branch,
            assumption,
            d=d,
            L=L,
            U=U,
            c=c,
            x=x,
            g=g,
            j=j,
            op=op,
            sumref=sumref,
            moment=moment,
            zc=zc,
            goal=goal,
        ):
            geq = branch.derive.eqpair(branch.upper(g), assumption)
            upper = Assembler(branch).linear(
                "Le",
                [(branch.row(d["added_upper_row"]), Fraction(1)), (geq, -(U - c))],
                expect=expression(child.model, -c, {x: 1}),
            )
            lower = Assembler(branch).linear(
                "Le",
                [(branch.row(d["added_lower_row"]), Fraction(1)), (geq, -(c - L))],
                expect=expression(child.model, c, {x: -1}),
            )
            xeq = branch.derive.eqpair(upper, lower)
            meq = Assembler(branch).linear(
                "Eq",
                [(moment, Fraction(1)), (xeq, Fraction(1))],
                expect=expression(
                    child.model, -j, {i: Fraction(q) for (q, i) in enumerate(op) if q}
                ),
            )
            desired = expression(child.model, -1, {zc: 1})

            def not_special(sub, zero):
                zeq = sub.derive.eqpair(zero, sub.lower(zc))
                part = expression(
                    child.model, 0, {i: 1 for (q, i) in enumerate(op) if q < j}
                )
                integer = Assembler(sub).linear(
                    "Int",
                    [
                        (sub.integer(i), Fraction(1))
                        for (q, i) in enumerate(op)
                        if q < j
                    ],
                    expect=part,
                )

                def no_lower(leaf, assump):
                    terms = [
                        (meq, Fraction(1)),
                        (sumref, Fraction(-j - 1)),
                        (assump, Fraction(j + 1)),
                        (zeq, Fraction(1)),
                    ]
                    terms += [
                        (leaf.lower(i), Fraction(q))
                        for (q, i) in enumerate(op)
                        if q < j and q
                    ]
                    terms += [
                        (leaf.lower(i), Fraction(q - j - 1))
                        for (q, i) in enumerate(op)
                        if q > j + 1
                    ]
                    return leaf.close_absurd(
                        Assembler(leaf).linear(
                            "Le", terms, expect=expression(child.model, 1)
                        )
                    )

                def some_lower(leaf, assump):
                    terms = [
                        (sumref, Fraction(K)),
                        (meq, Fraction(-1)),
                        (assump, Fraction(K - j + 1)),
                    ]
                    terms += [
                        (leaf.lower(i), Fraction(j - 1 - q))
                        for (q, i) in enumerate(op)
                        if q < j - 1
                    ]
                    terms += [
                        (leaf.lower(i), Fraction(K - q))
                        for (q, i) in enumerate(op)
                        if q >= j and q < K
                    ]
                    return leaf.close_absurd(
                        Assembler(leaf).linear(
                            "Le", terms, expect=expression(child.model, 1)
                        )
                    )

                case1 = sub.derive.cases(
                    part, kind="Eq", expect=desired, integer=integer
                )
                case1_fact = no_lower(case1.left, case1.left.assumption)
                if case1_fact is not None:
                    case1.left.conclude(case1_fact)
                case1_fact = some_lower(case1.right, case1.right.assumption)
                if case1_fact is not None:
                    case1.right.conclude(case1_fact)
                return case1.finish()

            def selected_one(sub, one):
                return sub.derive.eqpair(sub.upper(zc), one)

            case2 = branch.derive.cases(
                expression(child.model, 0, {zc: 1}),
                kind="Eq",
                expect=desired,
                integer=branch.integer(zc),
            )
            case2_fact = not_special(case2.left, case2.left.assumption)
            if case2_fact is not None:
                case2.left.conclude(case2_fact)
            case2_fact = selected_one(case2.right, case2.right.assumption)
            if case2_fact is not None:
                case2.right.conclude(case2_fact)
            selected = case2.finish()
            return Assembler(branch).linear(
                "Le", [(geq, Fraction(1)), (selected, Fraction(-1))], expect=goal
            )

        def left(branch, assumption, zc=zc, goal=goal):
            return Assembler(branch).linear(
                "Le",
                [(assumption, Fraction(1)), (branch.lower(zc), Fraction(1))],
                expect=goal,
            )

        case3 = child.derive.cases(
            expression(child.model, 0, {g: 1}),
            kind="Le",
            expect=goal,
            integer=child.integer(g),
        )
        case3_fact = left(case3.left, case3.left.assumption)
        if case3_fact is not None:
            case3.left.conclude(case3_fact)
        case3_fact = active(case3.right, case3.right.assumption)
        if case3_fact is not None:
            case3.right.conclude(case3_fact)
        rowproof[d["link_row"]] = case3.finish()
    child.map(mapping, default="same_name")
    mapping = child.mapping

    def reverse_domain(i, kind):
        j = next(iter(mapping[i].terms))
        if kind == "VarLower":
            return child.lower(j)
        if kind == "VarUpper":
            return child.upper(j)
        return child.integer(j)

    def reverse_row(i):
        name = a.rows[i].name
        if name in rowproof:
            return rowproof[name]
        if name in b.rows:
            return [(child.row(name), Fraction(1))]
        raise AssertionError(("missing reversed row", name))

    reverse_checks = finish_checks(
        child, a, mapping, reverse_domain, reverse_row, b.objective
    )
    Assembler(child).assign(reverse_checks)
    child.finish()
    return proof
