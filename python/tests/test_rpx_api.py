import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from fractions import Fraction
from rpx import *
from rpx.lowlevel import affine, Assembler, assemble, disassemble


def box(name="m", integer=False, lower=0, upper=1):
    b = ModelBuilder(name)
    b.add_var("x", integer=integer, lower=lower, upper=upper)
    return b.build()


def identity(model):
    p = Proof(model, model)
    p.forward.map(default="same_name").finish()
    p.reverse.map(default="same_name").finish()
    return p


class Verified(unittest.TestCase):
    def verify(self, p):
        with tempfile.TemporaryDirectory() as directory:
            bundle = p.compile(Path(directory) / "proof")
            report = bundle.verify()
            self.assertEqual(report.status, "VERIFIED", report.to_dict())
            self.assertEqual(report.guarantee, "MI_OPT")
            other = Path(directory) / "other.rpx"
            assemble(str(bundle.rpa), str(other))
            self.assertEqual(other.read_bytes(), bundle.proof.read_bytes())
            text = Path(directory) / "other.rpa"
            disassemble(str(other), str(text))
            self.assertEqual(text.read_bytes(), bundle.rpa.read_bytes())
            return report


class NumberTests(unittest.TestCase):
    def test_numeric_hash_contract_without_string_coercion(self):
        import sys

        p = sys.hash_info.modulus
        for value in [
            Fraction(-1),
            Fraction(0),
            Fraction(3, 7),
            Fraction(-3, p),
            Fraction(1, p * p),
            Fraction(p, 7),
            Fraction(10**1000, 3),
        ]:
            q = Q(value)
            e = Expr(q)
            self.assertEqual(hash(q), hash(value))
            self.assertEqual(hash(e), hash(value))
            self.assertEqual(len({q, e, value}), 1)
        self.assertEqual(len({Q(1), Expr(1), 1, Decimal(1)}), 1)
        self.assertNotEqual(Q(1), "1")
        self.assertNotEqual(Expr(1), "1")

    def test_exact_scalar_inputs(self):
        for v in [1, "1", "1.0", Q(1), Fraction(1), Decimal("1.00")]:
            with self.subTest(v=v):
                self.assertEqual(Q(v), 1)
        self.assertEqual(Q("0.1"), Q(1, 10))
        self.assertEqual(Q("1.2D-2"), Q(3, 250))
        self.assertEqual(Q("-3/-6"), Q(1, 2))
        self.assertEqual(Q(1, 3) + Q(1, 6), Q(1, 2))
        self.assertEqual(hash(Q(1, 3)), hash(Fraction(1, 3)))

    def test_inexact_scalars_rejected_everywhere(self):
        m = box()
        x = m.vars["x"]
        p = Proof(m, m)
        for v in [
            True,
            False,
            0.1,
            float("nan"),
            float("inf"),
            Decimal("NaN"),
            Decimal("Infinity"),
        ]:
            for call in [
                lambda: Q(v),
                lambda: Expr(v),
                lambda: x + v,
                lambda: x * v,
                lambda: ModelBuilder().add_var("z", upper=v),
                lambda: p.forward.map({"x": v}),
            ]:
                with self.subTest(v=repr(v), call=call), self.assertRaises(
                    (TypeError, CompilerError)
                ):
                    call()

    def test_zero_denominator_and_limits(self):
        for call in [lambda: Q(1, 0), lambda: Q("1/0"), lambda: Q(1) / 0]:
            with self.assertRaises((ZeroDivisionError, CompilerError)):
                call()
        for value in ["9" * 4097, "1e4097", 1 << 65536]:
            with self.assertRaises(CompilerError):
                Q(value)

    def test_fraction_decimal_and_native_roundtrip(self):
        from decimal import localcontext

        with localcontext() as context:
            context.prec = 2
            self.assertEqual(Q(Decimal("123456.125")), Q(987649, 8))
        q = Q(3, 7)
        self.assertEqual(q.numerator, 3)
        self.assertEqual(q.denominator, 7)
        self.assertEqual(2 * q, Q(6, 7))
        self.assertEqual(2 - q, Q(11, 7))
        self.assertEqual(2 / q, Q(14, 3))
        self.assertEqual(abs(-q), q)


class ModelExpressionTests(Verified):
    def test_goal_queries_do_not_change_fact_selection(self):
        b = ModelBuilder()
        x = b.add_var("x", lower=0, upper=5)
        b.add_row("same", x, upper=5)
        m = b.build()
        encodings = []
        with tempfile.TemporaryDirectory() as directory:
            for query in [False, True]:
                p = Proof(m, m)
                s = p.forward.map(default="same_name")
                if query:
                    self.assertEqual(len(s.missing()), 0)
                s.derive.le(s.row("same"))
                s.finish()
                p.reverse.map(default="same_name").finish()
                bundle = p.compile(Path(directory) / str(query))
                encodings.append(bundle.proof.read_bytes())
                self.assertEqual(bundle.verify().status, "VERIFIED")
        self.assertEqual(*encodings)

    def test_trace_index_is_native_and_materialization_is_explicit(self):
        import tracemalloc

        b = ModelBuilder()
        [b.add_var(f"x{i}", lower=0, upper=1) for i in range(1000)]
        m = b.build()
        p = Proof(m, m)
        s = p.forward
        s.derive.box_le(quicksum(m.vars) - 1000)
        tracemalloc.start()
        step = s.trace[0]
        self.assertEqual(step.kind, "Lin")
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        self.assertLess(peak, 20000)
        self.assertIn("Lin", step.to_dict())
        s.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        block = p.certificate()["forward"]
        self.assertEqual(block[0].kind, "Lin")
        self.assertEqual(block[0].to_dict(), step.to_dict())
        self.assertEqual(len(list(s.trace)), len(s.trace))

    def test_fact_html_is_bounded_and_escaped(self):
        b = ModelBuilder()
        x = b.add_var("<x>", lower=0)
        m = b.build()
        fact = Proof(m, m).forward.lower("<x>")
        self.assertIn("&lt;x&gt;", fact._repr_html_())
        self.assertNotIn("<x>", fact._repr_html_())

    def test_identity_is_not_name_or_formulation(self):
        a, b = box(), box()
        self.assertTrue(a.same_formulation(b))
        self.assertNotEqual(a.vars["x"], b.vars["x"])
        with self.assertRaises(CoordinateSpaceError):
            a.vars["x"] + b.vars["x"]
        with self.assertRaises(CoordinateSpaceError):
            Proof(a, b).forward.map({"x": b.vars["x"]})
        self.assertEqual(a.vars["x"] + 1, 1 + a.vars["x"])

    def test_builder_freezes_and_preserves_handles(self):
        b = ModelBuilder("m")
        x = b.add_var("x")
        b.minimize(x)
        m = b.build()
        self.assertEqual(x, m.vars["x"])
        self.assertEqual(m.objective, x)
        for call in [lambda: b.add_var("y"), lambda: b.minimize(0), lambda: b.build()]:
            with self.assertRaises(ScopeError):
                call()
        with self.assertRaises(AttributeError):
            m.name = "new"

    def test_builder_rejects_foreign_coordinates_and_duplicates(self):
        b = ModelBuilder()
        b.add_var("x")
        with self.assertRaises(KeyError):
            b.add_var("x")
        with self.assertRaises(CoordinateSpaceError):
            b.add_row("foreign", box().vars["x"])
        b.add_row("r", 0, equal=0)
        with self.assertRaises(KeyError):
            b.add_row("r", 0)

    def test_lazy_views_and_native_sums(self):
        b = ModelBuilder()
        xs = [b.add_var(f"x{i}") for i in range(100)]
        m = b.build()
        self.assertIsInstance(m.vars, VariablesView)
        self.assertEqual(len(m.vars), 100)
        self.assertEqual(len(list(m.vars.iter(limit=3))), 3)
        self.assertEqual(quicksum(m.vars), Expr.dot([1] * 100, m.vars))
        self.assertEqual(Expr.from_terms(m, [1, 0, 1], [2, 1, -2]), xs[0])
        with self.assertRaises((IndexError, CompilerError)):
            Expr.from_terms(m, [100], [1])
        with self.assertRaises(TypeError):
            Expr.dot([1], m.vars)

    def test_expression_views_are_explicit_and_immutable(self):
        m = box()
        x = m.vars["x"]
        e = 2 * x + Q(1, 3)
        self.assertEqual(e.constant, Q(1, 3))
        self.assertEqual(e.terms[0], 2)
        self.assertEqual(list(e.terms.items()), [(0, Q(2))])
        self.assertEqual(e.terms.to_dict(), {0: Q(2)})
        with self.assertRaises(TypeError):
            e.terms[0] = 3
        with self.assertRaises(TypeError):
            x * x
        with self.assertRaises(AttributeError):
            Expr.var(0)

    def test_model_edit_space_and_substitution(self):
        b = ModelBuilder("source")
        x = b.add_var("x", lower=0, upper=1)
        y = b.add_var("y", lower=0, upper=2)
        b.add_row("definition", y - 2 * x, equal=0)
        b.minimize(y)
        s = b.build()
        t = s.substitute({"y": 2 * x}, drop_rows=["definition"])
        self.assertEqual(len(t.vars), 1)
        self.assertEqual(len(t.rows), 1)
        self.assertEqual(t.objective, 2 * t.vars["x"])
        self.assertEqual(t.rows[0].name, "__bound_y")
        with self.assertRaises(CoordinateSpaceError):
            t.vars["x"] + x
        with self.assertRaises(CompilerError):
            s.substitute({"y": y})
        p = Proof(s, t)
        f = p.forward.map(default="same_name")
        f.derive.substitution({"y": f.row("definition")})
        f.finish()
        p.reverse.map({"y": 2 * t.vars["x"]}, default="same_name").finish()
        self.verify(p)

    def test_mcm_mps_roundtrip_and_magic(self):
        b = ModelBuilder("m")
        x = b.add_var("x", integer=True, lower=-2, upper=3)
        b.add_row("r", x + Q(1, 2), lower=0, upper=2)
        b.minimize(x - Q(1, 4))
        m = b.build()
        with tempfile.TemporaryDirectory() as d:
            for suffix in [".mcm", ".arbitrary", ".mps"]:
                path = Path(d) / ("m" + suffix)
                (m.write_mps if suffix == ".mps" else m.write_mcm)(path)
                r = Model.read(path)
                self.assertTrue(m.same_formulation(r))
                if suffix != ".mps":
                    self.assertEqual(
                        r.write_mcm(Path(d) / "copy.mcm").read_bytes(),
                        path.read_bytes(),
                    )

    def test_mps_nonterminating_never_rounds(self):
        m = box(lower=Q(1, 3))
        with self.assertRaises(CompilerError):
            m.to_mps()
        self.assertIn("1/3", m.to_mps(rational_literals=True))

    def test_immutable_edits_and_named_comparison(self):
        m = box()
        n = m.with_bounds("x", upper=2)
        self.assertEqual(m.vars["x"].upper, 1)
        self.assertEqual(n.vars["x"].upper, 2)
        self.assertFalse(m.same_formulation(n))
        self.assertTrue(m.same_formulation(m.renamed("other")))
        with self.assertRaises(CoordinateSpaceError):
            n.with_objective(m.vars["x"])


class ProofLifecycleTests(Verified):
    def test_goal_oriented_elimination(self):
        b = ModelBuilder("s")
        x = b.add_var("x", lower=0, upper=1)
        z = b.add_var("z", lower=0, upper=1)
        b.add_row("balance", x + z, equal=1)
        b.minimize(x)
        s = b.build()
        b = ModelBuilder("t")
        y = b.add_var("y", lower=0, upper=1)
        b.minimize(1 - y)
        t = b.build()
        p = Proof(s, t)
        f = p.forward.map({"y": z}, default="same_name")
        self.assertEqual(f.missing().count, 1)
        f.prove(f.obligations["objective.non_increasing"], by=-f.row("balance"))
        f.finish()
        p.reverse.map({"x": 1 - y, "z": y}).finish()
        self.verify(p)

    def test_sparse_mapping_names_and_orientation(self):
        m = box()
        t = m.add_variable("y")
        p = Proof(m, t)
        with self.assertRaises(MappingError):
            p.forward.map(default="same_name")
        p.forward.map({"y": 0}, default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verify(p)
        with self.assertRaises(MappingError):
            Proof(m, m).forward.map({"unknown": 0}, default="same_name")

    def test_goal_staleness_cross_scope_and_cross_proof(self):
        m = box()
        p = Proof(m, m)
        f = p.forward.map(default="same_name")
        g = f.obligations[0]
        f.map({"x": 0})
        with self.assertRaises(ScopeError):
            f.prove(g, by=f.lower("x"))
        other = Proof(m, m).forward.map(default="same_name")
        with self.assertRaises(ScopeError):
            f.prove(other.obligations[0], by=f.lower("x"))
        with self.assertRaises(ScopeError):
            f.derive.le(other.lower("x"))

    def test_sealed_scope_rejects_mutations(self):
        m = box()
        p = identity(m)
        f = p.forward
        for call in [
            lambda: f.map(default="same_name"),
            lambda: f.derive.le(f.lower("x")),
            lambda: f.split(m.vars["x"]),
            lambda: f.lift_interval(lower=0, upper=1),
        ]:
            with self.assertRaises(ScopeError):
                call()
        self.verify(p)

    def test_incomplete_proof_does_not_publish(self):
        m = box()
        p = Proof(m, m)
        p.forward.map(default="same_name").finish()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            with self.assertRaises(CompilerError):
                p.compile(out)
            self.assertFalse(out.exists())

    def test_failed_finish_remains_editable_and_bounded_diagnostic(self):
        m = box()
        t = m.with_bounds("x", upper=0)
        p = Proof(m, t)
        f = p.forward.map(default="same_name")
        with self.assertRaises(UnprovedGoalError) as error:
            f.finish()
        self.assertIn("variable.upper[x]", str(error.exception))
        self.assertNotIn("Ratio", str(error.exception))
        f.map({"x": 0}).finish()
        p.reverse.map(default="same_name")
        p.reverse.derive.le(p.reverse.upper("x") - 1)
        p.reverse.finish()
        self.verify(p)

    def test_cached_snapshot_and_fresh_verification_budget(self):
        p = identity(box())
        a = p.preflight()
        self.assertEqual(a, p.preflight())
        self.assertEqual(p._native.lowering_count, 1)
        with tempfile.TemporaryDirectory() as d:
            b = p.compile(Path(d) / "b")
            r = b.verify()
            p.compile(Path(d) / "b")
            self.assertEqual(p._native.lowering_count, 1)
            self.assertEqual(b.verify(work=r.statistics["work"]).status, "VERIFIED")
            limited = b.verify(work=r.statistics["work"] - 1)
            self.assertEqual(limited.status, "RESOURCE_LIMIT")
            self.assertIsNone(limited.guarantee)
            with self.assertRaises(ResourceLimitError):
                limited.raise_for_status()

    def test_failed_derivation_leaves_no_steps(self):
        m = box()
        f = Proof(m, m).forward
        n = len(f.trace)
        for call in [
            lambda: f.derive.eq(f.lower("x")),
            lambda: f.derive.le(f.lower("x") + 1),
            lambda: f.derive.int(Q(1, 2)),
            lambda: f.derive.le(f.lower("x"), expect=m.vars["x"]),
        ]:
            with self.assertRaises(InvalidDerivationError):
                call()
            self.assertEqual(len(f.trace), n)
        with self.assertRaises(InvalidDerivationError):
            -f.upper("x")

    def test_drop_is_scope_aware_and_atomic(self):
        m = box(integer=True)
        p = Proof(m, m)
        f = p.forward
        fact = f.derive.le(f.lower("x"))
        l, r = f.split(m.vars["x"], kind="integer")
        l.drop(fact)
        with self.assertRaises(ScopeError):
            l.derive.le(fact)
        r.derive.le(fact)
        another = r.derive.le(r.upper("x"))
        with self.assertRaises(CompilerError):
            r.drop([another, r.lower("x")])
        r.derive.le(another)
        l.map(default="same_name").finish()
        r.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        self.verify(p)

    def test_zero_linear_multiplier_drops_operand(self):
        m = box()
        f = Proof(m, m).forward
        z = Assembler(f).linear("Le", [(f.upper("x"), 0)])
        self.assertEqual(z.expression, Expr(0))

    def test_full_certificate_has_two_fixed_directions(self):
        p = identity(box(integer=True))
        d = p.certificate().to_dict()
        self.assertEqual(set(d), {"forward", "reverse"})
        for old in ["claim", "bijection", "complete", "close"]:
            self.assertFalse(hasattr(p, old))
        self.assertNotIsInstance(p.certificate(), dict)


if __name__ == "__main__":
    unittest.main()
