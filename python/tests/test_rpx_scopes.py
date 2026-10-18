import tempfile
import unittest
from rpx import *


class Scopes(unittest.TestCase):
    def model(self, integer=True):
        b = ModelBuilder("scope")
        b.add_var("x", integer=integer, lower=0, upper=1)
        return b.build()

    def verified(self, p):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(p.verify(d + "/proof").status, "VERIFIED")

    def test_continuous_split_right_includes_boundary(self):
        m = self.model(False)
        p = Proof(m, m)
        x = m.vars["x"]
        a, b = p.forward.split(x, at=Q(1, 2))
        self.assertEqual(a.assumption.expression, x - Q(1, 2))
        self.assertEqual(b.assumption.expression, Q(1, 2) - x)
        a.map(default="same_name").finish()
        b.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_integer_split_threshold(self):
        m = self.model()
        p = Proof(m, m)
        x = m.vars["x"]
        a, b = p.forward.split(x, at=1, kind="integer", because=p.forward.integer(x))
        self.assertEqual(a.assumption.expression, x - 1)
        self.assertEqual(b.assumption.expression, 2 - x)
        a.map(default="same_name").finish()
        b.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_invalid_split_keeps_parent_open(self):
        m = self.model()
        s = Proof(m, m).forward
        x = m.vars["x"]
        for kw in [
            {"kind": "integer", "at": Q(1, 2)},
            {"kind": "integer", "because": s.lower("x")},
            {"kind": "unknown"},
        ]:
            with self.assertRaises((CompilerError, TypeError)):
                s.split(x, **kw)
            self.assertEqual(len(s.trace), 0)
        s.map(default="same_name").finish()

    def test_cross_proof_fact_and_goal(self):
        m = self.model()
        p, q = Proof(m, m), Proof(m, m)
        x = m.vars["x"]
        with self.assertRaises(ScopeError):
            p.forward.split(x, kind="integer", because=q.forward.integer(x))
        with self.assertRaises(ScopeError):
            p.forward.lift_interval(lower=0, upper=x, because=q.forward.lower(x))

    def test_siblings_facts_and_generated_coordinates(self):
        m = self.model()
        p = Proof(m, m)
        a, b = p.forward.split(m.vars["x"])
        ea = a.lift_interval(lower=0, upper=1)
        eb = b.lift_interval(lower=0, upper=1)
        with self.assertRaises(CoordinateSpaceError):
            ea.variable + eb.variable
        with self.assertRaises(CoordinateSpaceError):
            p.forward.derive.box_le(ea.variable - 1)
        with self.assertRaises(ScopeError):
            eb.scope.derive.le(ea[0].upper_rows[0])
        for e in [ea, eb]:
            e.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_cases_explicit_conclusions_and_parent_freeze(self):
        m = self.model()
        p = Proof(m, m)
        s = p.forward
        x = m.vars["x"]
        c = s.derive.cases(x, kind="Le", expect=x - 1, integer=s.integer(x))
        with self.assertRaises(ScopeError):
            s.map(default="same_name")
        with self.assertRaises(UnprovedGoalError):
            c.finish()
        with self.assertRaises(InvalidDerivationError):
            c.left.conclude(c.left.lower(x))
        c.left.conclude(c.left.derive.le(c.left.assumption - 1))
        c.right.conclude(c.right.upper(x))
        f = c.finish()
        self.assertEqual(f.expression, x - 1)
        self.assertEqual(c.finish(), f)
        with self.assertRaises(ScopeError):
            s.derive.le(c.left.assumption)
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_cases_contradiction_and_nested_binary_product(self):
        b = ModelBuilder("product")
        x = b.add_var("x", integer=True, lower=0, upper=1)
        y = b.add_var("y", integer=True, lower=0, upper=1)
        t = b.add_var("t", lower=0, upper=1)
        b.add_row("a", t - x, upper=0)
        b.add_row("b", t - y, upper=0)
        b.add_row("c", x + y - t - 1, upper=0)
        m = b.build()
        target = m.with_integrality(["t"], True)
        p = Proof(m, target)
        s = p.forward
        outer = s.derive.cases(x, kind="Int", expect=t, integer=s.integer(x))
        for xi, scope in enumerate([outer.left, outer.right]):
            fx = (
                scope.derive.eqpair(scope.assumption, scope.lower(x))
                if xi == 0
                else scope.derive.eqpair(scope.upper(x), scope.assumption)
            )
            inner = scope.derive.cases(
                y, kind="Int", expect=t, integer=scope.integer(y)
            )
            for yi, leaf in enumerate([inner.left, inner.right]):
                fy = (
                    leaf.derive.eqpair(leaf.assumption, leaf.lower(y))
                    if yi == 0
                    else leaf.derive.eqpair(leaf.upper(y), leaf.assumption)
                )
                if xi == yi == 1:
                    low = leaf.derive.rewrite(leaf.row("c"), {"x": fx, "y": fy})
                    eq = leaf.derive.eqpair(leaf.upper(t), low)
                    out = leaf.derive.int(eq + 1)
                else:
                    up = leaf.derive.rewrite(
                        leaf.row("a" if xi == 0 else "b"), {"x": fx, "y": fy}
                    )
                    eq = leaf.derive.eqpair(up, leaf.lower(t))
                    out = leaf.derive.int(eq)
                leaf.conclude(out)
            scope.conclude(inner.finish())
        outer.finish()
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_interval_multiple_and_parent_embedding(self):
        m = self.model()
        p = Proof(m, m)
        s = p.forward
        x = m.vars["x"]
        lift = s.lift_intervals(
            [
                IntervalSpec([0], [x], [s.lower(x)]),
                IntervalSpec(
                    [x, 0],
                    [1, 2],
                    [s.upper(x), s.derive.le(s.upper(x) - 1), None, None],
                ),
            ]
        )
        self.assertEqual(lift.scope.vars["x"], x)
        first, second = lift[0], lift[1]
        self.assertEqual(first.upper_rows[0].expression, first.variable - x)
        self.assertEqual(len(second.lower_rows), 2)
        with self.assertRaises(ScopeError):
            s.map(default="same_name")
        lift.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_lift_invalid_premise_atomic(self):
        m = self.model()
        s = Proof(m, m).forward
        x = m.vars["x"]
        before = len(s.trace)
        with self.assertRaises(InvalidDerivationError):
            s.lift_interval(lower=0, upper=x, because=s.upper(x))
        self.assertEqual(len(s.trace), before)
        s.map(default="same_name").finish()

    def test_menu_variable_and_rows(self):
        m = self.model()
        p = Proof(m, m)
        s = p.forward
        x = m.vars["x"]
        lift = s.lift_menus(
            [
                MenuSpec(
                    1, 1, x, [None, None, None, s.lower(x), s.upper(x), s.integer(x)]
                )
            ]
        )
        g = lift[0]
        a, b = g.options
        self.assertEqual(g.sum.expression, a + b - 1)
        self.assertEqual(g.moment.expression, b - x)
        lift.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_signed_components(self):
        b = ModelBuilder("signed")
        f = b.add_var("f", lower=-2, upper=2)
        z = b.add_var("z", integer=True, lower=0, upper=1)
        b.add_row("p", f - 2 * z, upper=0)
        b.add_row("n", -f - 2 * z, upper=0)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        lift = s.lift_signed(
            [
                SignedSpec(
                    2,
                    f,
                    z,
                    [s.lower(z), s.upper(z), s.integer(z), s.row("p"), s.row("n")],
                )
            ]
        )
        g = lift[0]
        self.assertEqual(g.flow.expression, g.positive - g.negative - f)
        self.assertEqual(
            g.activation.expression, g.positive_activation + g.negative_activation - z
        )
        lift.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_flow_conservation_recovery(self):
        b = ModelBuilder("flow")
        f = b.add_var("f", lower=2, upper=2)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        eq = s.derive.eq_on_fixed(f - 2)
        lift = s.lift_flow(
            FlowSpec(
                2,
                [(0, 1)],
                [
                    FlowGroup(
                        0,
                        [(1, 1), (1, 1)],
                        [f],
                        [s.derive.le(s.lower(f) - 2)],
                        [eq, s.derive.eq(-eq)],
                    )
                ],
            )
        )
        g = lift[0]
        self.assertEqual(g.source, 0)
        self.assertEqual(g.commodities[0].demand, 1)
        self.assertEqual(
            g.recovery[0].expression,
            g.commodities[0].flows[0] + g.commodities[1].flows[0] - f,
        )
        lift.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_subflow_remainder(self):
        b = ModelBuilder("subflow")
        f = b.add_var("f", lower=2, upper=2)
        g = b.add_var("g", lower=1, upper=1)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        eq = s.derive.eq_on_fixed(f - g - 1)
        lift = s.lift_subflow(
            SubflowSpec(
                2,
                [(0, 1), (1, 0)],
                [
                    SubflowGroup(
                        0,
                        [(1, 1)],
                        [f, g],
                        [s.derive.le(s.lower(f) - 2), s.derive.le(s.lower(g) - 1)],
                        [eq, s.derive.eq(-eq)],
                    )
                ],
            )
        )
        group = lift[0]
        a, b = group.flows
        self.assertEqual(group.balances[0].expression, a - b - 1)
        self.assertEqual(group.remainder_nonnegative[0].expression, a - f)
        lift.scope.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)
