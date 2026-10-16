from rule_checks import assert_rules_checked
"""Caller-supplied nonnegative-sum witnesses lower to ordinary Kernel rules."""
from collections.abc import Mapping
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable, attack


class SparseZeros(Mapping):
    """A large logical map which forbids whole-map iteration or copying."""
    def __init__(self, values):
        self.values, self.lookups = values, []

    def __getitem__(self, key):
        self.lookups.append(key)
        return self.values[key]

    def __len__(self):
        return 100_000

    def __iter__(self):
        raise AssertionError("zero_sum must only inspect its supplied row's coordinates")


class ZeroSumTests(unittest.TestCase):
    def verify(self, proof, directory):
        result = proof.verify(directory)
        assert_rules_checked(self, result)
        return result

    def test_complete_integer_and_continuous_zero_eliminations_and_tampering(self):
        x, y, z = (Expr.var(i) for i in range(3))
        source = Model("nonnegative", [Variable("x", True, 0, 2), Variable("y"), Variable("z")],
                       [Row("given", 2*x+3*y+5*z, upper=0)], objective=x+2*y+3*z)
        for integers in (True, False):
            with self.subTest(integers=integers):
                proof = Proof(source, Model("zero_target"))
                forward, reverse = (proof.forward.map([]), proof.reverse.map([0, 0, 0]))
                zeros = forward.zero_sum(forward.row("given"))
                self.assertEqual(set(zeros), {0, 1, 2})
                self.assertTrue(all(f.kind == "Eq" and f.expression == Expr.var(i) for i, f in zeros.items()))
                self.assertEqual({next(iter(s)) for s in forward.steps}, {"Lin", "EqPair"})
                forward.substitution(zeros)
                forward.complete(); reverse.complete()
                with tempfile.TemporaryDirectory() as directory:
                    self.verify(proof, directory)
                    broken = attack(proof, Path(directory)/"attack",
                                    ["forward", "steps", 0, "Lin", "terms", 1, 1], replacement="0")
                    self.assertTrue(broken["rejected_as_expected"], broken)

    def test_explicit_ordered_closure_with_names_and_scaled_prior_zeros(self):
        x, y, z = (Expr.var(i) for i in range(3))
        source = Model("ordered", [Variable(n) for n in ("x", "y", "z")],
                       [Row("seed", -2*x, 0, 0), Row("next", x+3*y, upper=0),
                        Row("last", -y-5*z, 0, 0)], objective=x+y+z)
        proof = Proof(source, Model("zero_target"))
        forward, reverse = (proof.forward.map([]), proof.reverse.map([0, 0, 0]))
        first = forward.zero_sum(forward.row("seed"))
        zeros = {"x": forward.eq([(first[0], -7)])}
        zeros.update(forward.zero_sum(forward.row("next"), zeros=zeros))
        zeros.update(forward.zero_sum(forward.row("last"), zeros=zeros, scale=-1))
        forward.substitution(zeros)
        forward.complete(); reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.verify(proof, directory)

    def test_sparse_prior_zero_lookups_and_selected_outputs(self):
        x, y, z = (Expr.var(i) for i in range(3))
        source = Model("selected", [Variable(n) for n in ("x", "y", "z")],
                       [Row("seed", z, 0, 0), Row("sum", 2*x+3*y+4*z, upper=0)])
        target = source.add_row("only_x", x, lower=0, upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        sparse = SparseZeros({2: forward.eq([(forward.row("seed"), -2)])})
        zeros = forward.zero_sum(forward.row("sum"), zeros=sparse, coordinates=["x", "x"])
        self.assertEqual(list(zeros), [0])
        self.assertLessEqual(len(sparse.lookups), 6)
        self.assertTrue(set(sparse.lookups) <= {0, 1, 2, "x", "y", "z"})
        forward.complete(); reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.verify(proof, directory)

    def test_single_coordinate_equality_needs_no_nonnegative_bound(self):
        x = Expr.var(0)
        source = Model("free", [Variable("x", False, None, None)], [Row("given", -3*x, 0, 0)], objective=x)
        proof = Proof(source, Model("zero_target"))
        forward, reverse = (proof.forward.map([]), proof.reverse.map([0]))
        zeros = forward.zero_sum(forward.row("given"))
        self.assertEqual(zeros[0].expression, x)
        forward.substitution(zeros)
        forward.complete(); reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.verify(proof, directory)

    def test_positive_declared_lower_bound_is_weakened_exactly(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("inconsistent_sum", [Variable("x", lower=1), Variable("y")],
                       [Row("sum", x+y, upper=0)])
        # Both models are infeasible; no point/existence assertion is submitted.
        target = source.add_row("zero_x", x, lower=0, upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        zeros = forward.zero_sum(forward.row("sum"))
        self.assertEqual(zeros[0].expression, x)
        forward.complete(); reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.verify(proof, directory)

    def test_invalid_conditions_do_not_emit_partial_derivations(self):
        x, y = Expr.var(0), Expr.var(1)
        variants = [
            Model("mixed", [Variable("x"), Variable("y")], [Row("given", x-y, 0, 0)]),
            Model("negative", [Variable("x", lower=-1), Variable("y")], [Row("given", x+y, upper=0)]),
            Model("unbounded", [Variable("x", lower=None), Variable("y")], [Row("given", x+y, upper=0)]),
            Model("nonzero_rhs", [Variable("x"), Variable("y")], [Row("given", x+y, upper=1)]),
        ]
        for model in variants:
            builder = Builder(model)
            with self.subTest(model=model.name), self.assertRaises(BuildError):
                builder.zero_sum(builder.row("given"))
            self.assertEqual(builder.steps, [])
        source = Model("bad_scale", [Variable("x", True), Variable("y")], [Row("given", x+y, upper=0)])
        for scale in (0, -1):
            builder = Builder(source)
            with self.assertRaises(BuildError):
                builder.zero_sum(builder.row("given"), scale=scale)
            self.assertEqual(builder.steps, [])
        builder = Builder(source)
        with self.assertRaises(BuildError):
            builder.zero_sum(builder.integer("x"))
        self.assertEqual(builder.steps, [])

    def test_wrong_dropped_or_unrelated_zero_witness_is_rejected(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("witnesses", [Variable("x"), Variable("y")],
                       [Row("sum", x+y, upper=0), Row("not_zero", y, 1, 1), Row("zero", y, 0, 0)])
        builder = Builder(source)
        with self.assertRaises(BuildError):
            builder.zero_sum(builder.row("sum"), zeros={1: builder.row("not_zero")})
        self.assertEqual(builder.steps, [])
        other = Builder(source)
        with self.assertRaises(BuildError):
            builder.zero_sum(builder.row("sum"), zeros={1: other.row("zero")})
        self.assertEqual(builder.steps, [])
        dropped = builder.eq([(builder.row("zero"), 1)])
        builder.drop(dropped)
        before = list(builder.steps)
        with self.assertRaises(BuildError):
            builder.zero_sum(builder.row("sum"), zeros={1: dropped})
        self.assertEqual(builder.steps, before)

    def test_caller_selected_orientation_and_empty_residual(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("orientation", [Variable("x"), Variable("y")],
                       [Row("sum", -2*x-3*y, 0, 0), Row("x_zero", x, 0, 0), Row("y_zero", y, 0, 0)])
        builder = Builder(source)
        with self.assertRaises(BuildError):
            builder.zero_sum(builder.row("sum"))
        self.assertEqual(builder.steps, [])
        zeros = builder.zero_sum(builder.row("sum"), scale=-1)
        self.assertEqual(set(zeros), {0, 1})
        before = list(builder.steps)
        self.assertEqual(builder.zero_sum(builder.row("sum"), zeros=zeros), {})
        self.assertEqual(builder.steps, before)


if __name__ == "__main__":
    unittest.main()
