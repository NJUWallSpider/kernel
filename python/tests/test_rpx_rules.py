"""Selected derivations: success, invalid premises, rollback, and Kernel evidence."""

import tempfile
import unittest
from rpx import *
from rpx.lowlevel import Assembler, affine


def fixture(names=("x", "y", "z"), *, integer=False, lower=0, upper=5):
    b = ModelBuilder("rules")
    xs = [b.add_var(n, integer=integer, lower=lower, upper=upper) for n in names]
    return b, xs


class Rules(unittest.TestCase):
    def verified(self, p):
        with tempfile.TemporaryDirectory() as d:
            result = p.verify(d + "/bundle")
            self.assertEqual(result.status, "VERIFIED", result)
            self.assertEqual(result.guarantee, "MI_OPT")

    def test_ordered_rewrite_and_batch(self):
        b, (x, y, z) = fixture()
        b.add_row("xy", x - y, equal=0)
        b.add_row("yz", y - z, equal=0)
        b.add_row("goal", x + 2 * y, upper=5)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        defs = {"x": s.row("xy"), "y": s.row("yz")}
        result = s.derive.rewrite_many([s.row("goal")] * 3, defs)
        self.assertEqual([v.expression for v in result], [3 * z - 5] * 3)
        reverse = s.derive.rewrite(s.row("goal"), {"y": s.row("yz"), "x": s.row("xy")})
        self.assertEqual(reverse.expression, y + 2 * z - 5)
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_invalid_rewrite_does_not_append(self):
        b, (x, y, z) = fixture()
        b.add_row("d", x - y, equal=0)
        b.add_row("g", z, upper=0)
        m = b.build()
        s = Proof(m, m).forward
        for defs, expected in [({"x": s.row("g")}, None), ({"y": s.row("d")}, x)]:
            before = s.trace.to_list()
            with self.assertRaises(CompilerError):
                s.derive.rewrite(s.row("g"), defs, expect=expected)
            self.assertEqual(s.trace.to_list(), before)

    def test_substitution_elimination_objective(self):
        b, (x, y) = fixture(("x", "y"))
        b.add_row("balance", x + y, equal=1)
        b.minimize(2 * x + y)
        m = b.build()
        t = m.substitute({"x": 1 - y}, drop_rows=["balance"])
        p = Proof(m, t)
        f = p.forward.map(default="same_name")
        f.derive.substitution({"x": f.row("balance")})
        f.finish()
        p.reverse.map({"x": 1 - t.vars["y"]}, default="same_name").finish()
        self.verified(p)

    def test_substitution_fact_and_kind(self):
        b, (x, y) = fixture(("x", "y"))
        b.add_row("d", x - y, equal=0)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        fact = s.derive.substitution_fact(x - 5, {"x": s.row("d")}, s.upper("y"))
        self.assertEqual((fact.kind, fact.expression), ("Le", x - 5))
        with self.assertRaises(CompilerError):
            s.derive.substitution_fact(x - 4, {"x": s.row("d")}, s.upper("y"))
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_zero_sum_closure(self):
        b, (x, y, z) = fixture()
        b.add_row("a", -2 * x, equal=0)
        b.add_row("b", x + 3 * y, upper=0)
        b.add_row("c", -y - 5 * z, equal=0)
        b.minimize(x + y + z)
        m = b.build()
        t = ModelBuilder("empty").build()
        p = Proof(m, t)
        s = p.forward.map({})
        zeros = s.derive.zero_sum(s.row("a"))
        self.assertEqual(zeros["x"].expression, x)
        zeros.update(s.derive.zero_sum(s.row("b"), zeros=zeros))
        zeros.update(s.derive.zero_sum(s.row("c"), zeros=zeros, scale=-1))
        self.assertEqual(set(zeros), {"x", "y", "z"})
        s.derive.substitution(zeros)
        s.finish()
        p.reverse.map({"x": 0, "y": 0, "z": 0}).finish()
        self.verified(p)

    def test_zero_sum_selection_and_invalid_conditions(self):
        b, (x, y, z) = fixture()
        b.add_row("sum", 2 * x + 3 * y + z, upper=0)
        b.add_row("bad", x - y, equal=0)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        self.assertEqual(
            list(s.derive.zero_sum(s.row("sum"), coordinates=["y", "y"])), ["y"]
        )
        for fact, scale in [(s.row("bad"), 1), (s.row("sum"), 0), (s.row("sum"), -1)]:
            before = s.trace.to_list()
            with self.assertRaises(CompilerError):
                s.derive.zero_sum(fact, scale=scale)
            self.assertEqual(s.trace.to_list(), before)
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_parity_signs(self):
        for c, k in [(1, 0), (-1, 1), (3, -2), (-3, 1), (5, -1), (-5, -4)]:
            with self.subTest(c=c, k=k):
                b = ModelBuilder("parity")
                x = b.add_var("x", integer=True, lower=0, upper=1)
                y = b.add_var("y", integer=True)
                z = b.add_var("z", integer=True)
                b.add_row("eq", c * x + 2 * y - 4 * z + k, equal=0)
                m = b.build()
                value = (-k) % 2
                t = m.with_bounds("x", lower=value, upper=value)
                p = Proof(m, t)
                s = p.forward.map(default="same_name")
                f = s.derive.parity_fix("x", s.row("eq"))
                self.assertEqual(f.expression, x - value)
                s.finish()
                r = p.reverse.map(default="same_name")
                r.derive.le(r.lower("x") - value)
                r.derive.le(r.upper("x") + value - 1)
                r.finish()
                self.verified(p)

    def test_parity_rejects_nonbinary_and_even_coefficient(self):
        for upper, c in [(2, 1), (1, 2)]:
            b, (x, y) = fixture(("x", "y"), integer=True, upper=upper)
            b.add_row("eq", c * x + 2 * y, equal=0)
            m = b.build()
            s = Proof(m, m).forward
            with self.assertRaises(CompilerError):
                s.derive.parity_fix("x", s.row("eq"))
            self.assertEqual(len(s.trace), 0)

    def test_weighted_subset_bounds(self):
        b = ModelBuilder("subset")
        x = b.add_var("x", integer=True, lower=1, upper=5)
        y = b.add_var("y", integer=True, lower=-3, upper=4)
        z = b.add_var("z", lower=-2, upper=3)
        root = 3 * x - 2 * y + z / 3 - 8
        b.add_row("given", root, upper=0)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        sets = [["x", "y", "z"], ["x"], ["y"], ["z"], [], ["x", "z"], ["x"]]
        result = s.derive.subset_bounds(s.row("given"), sets)
        expected = [
            root,
            3 * x - Q(50, 3),
            -2 * y - Q(17, 3),
            z / 3 - 13,
            Expr(Q(-41, 3)),
            3 * x + z / 3 - 16,
            3 * x - Q(50, 3),
        ]
        self.assertEqual([f.expression for f in result], expected)
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_subset_rolls_back_late_failure(self):
        b = ModelBuilder("free")
        x = b.add_var("x")
        y = b.add_var("y", lower=2)
        b.add_row("g", x + 3 * y, upper=10)
        m = b.build()
        s = Proof(m, m).forward
        with self.assertRaises(CompilerError):
            s.derive.subset_bounds(s.row("g"), [["x"], []])
        self.assertEqual(len(s.trace), 0)
        self.assertEqual(
            s.derive.subset_bounds(s.row("g"), [["x"]])[0].expression, x - 4
        )

    def test_round_and_eqpair(self):
        b = ModelBuilder("round")
        x = b.add_var("x", integer=True, lower=0, upper="1/2")
        m = b.build()
        t = m.with_bounds("x", upper=0)
        p = Proof(m, t)
        s = p.forward.map(default="same_name")
        up = s.derive.round(s.upper("x"), s.integer("x"))
        self.assertEqual(up.expression, x)
        s.derive.eqpair(up, s.lower("x"))
        s.finish()
        r = p.reverse.map(default="same_name")
        r.derive.le(r.upper("x") - Q(1, 2))
        r.finish()
        self.verified(p)

    def test_box_failure_and_explicit_fixed(self):
        b, (x,) = fixture(("x",), lower=1, upper=1)
        m = b.build()
        s = Proof(m, m).forward
        self.assertEqual(s.derive.eq_on_fixed(3 * x - 3).expression, 3 * x - 3)
        self.assertEqual(s.derive.box_le(4 * x - 5).expression, 4 * x - 5)
        before = len(s.trace)
        with self.assertRaises(CompilerError):
            s.derive.box_le(x)
        self.assertEqual(len(s.trace), before)

    def test_plotkin_selected_cliques(self):
        b, xs = fixture(("a", "b", "c"), integer=True, upper=1)
        for i in range(3):
            for j in range(i + 1, 3):
                b.add_row(f"{i}{j}", xs[i] + xs[j], upper=1)
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        f = s.derive.plotkin(
            bits=2,
            distance=2,
            variables=[("a", 0), ("b", 1), ("c", 2)],
            cliques=[s.row("01"), s.row("02"), s.row("12")],
        )
        self.assertEqual(f.kind, "Le")
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)

    def test_iterable_inputs_can_read_their_scope(self):
        b, (x, y) = fixture(("x", "y"))
        b.add_row("sum", x + y, upper=0)
        m = b.build()
        p = Proof(m, m)
        s = p.forward

        def coordinates():
            self.assertEqual(s.row("sum").expression, x + y)
            yield "x"

        def subsets():
            self.assertEqual(s.lower("x").expression, -x)
            yield coordinates()

        self.assertEqual(
            s.derive.subset_bounds(s.row("sum"), subsets())[0].expression, x
        )
        self.assertEqual(
            s.derive.zero_sum(s.row("sum"), coordinates=coordinates())["x"].expression,
            x,
        )
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verified(p)
