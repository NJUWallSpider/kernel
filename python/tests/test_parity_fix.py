"""Caller-given parity witnesses elaborate to existing Kernel proof rules."""
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable, attack


class ParityFixTests(unittest.TestCase):
    def model(self, selected, constant, *, other=2, integer=True, lower=0, upper=1):
        x, y, z = (Expr.var(i) for i in range(3))
        return Model("parity", [Variable("x", integer, lower, upper),
                                Variable("y", True, None, None), Variable("z", True, None, None)],
                     [Row("given", selected*x + other*y - 4*z + constant, 0, 0)])

    def test_odd_signs_both_parities_and_general_integer_terms_verify(self):
        for selected, constant in [(1, 0), (-1, 1), (3, -2), (-3, 1), (5, -1), (-5, -4)]:
            with self.subTest(selected=selected, constant=constant):
                source = self.model(selected, constant)
                parity = (-constant) % 2
                target = source.with_bounds("x", lower=parity, upper=parity)
                proof = Proof(source, target)
                forward, reverse = proof.bijection("identity", "identity")
                fixed = forward.parity_fix("x", forward.row("given"))
                self.assertEqual(fixed.kind, "Eq")
                self.assertEqual(fixed.expression, source.var("x")-parity)
                self.assertEqual({next(iter(step)) for step in forward.steps}, {"Lin", "Round", "EqPair"})
                forward.complete()
                # Reverse actual fixed bounds imply both old binary bounds.
                reverse.le([(reverse.lower("x"), 1)], constant=-parity)
                reverse.le([(reverse.upper("x"), 1)], constant=parity-1)
                reverse.complete()
                with tempfile.TemporaryDirectory() as directory:
                    result = proof.verify(directory)
                    self.assertEqual(result["status"], "VERIFIED", result)
                    broken = attack(proof, Path(directory)/"attack", ["blocks", 0, "steps", 0, "Lin", "terms", 1, 1],
                                    replacement="0")
                    self.assertTrue(broken["rejected_as_expected"], broken)

    def test_rejections_precede_any_proof_steps(self):
        invalid = [self.model(2, 0), self.model(1, "1/2"), self.model(1, 0, other=1),
                   self.model(1, 0, integer=False), self.model(1, 0, lower=None),
                   self.model(1, 0, upper=2)]
        for model in invalid:
            builder = Builder(model)
            with self.assertRaises(BuildError):
                builder.parity_fix("x", builder.row("given"))
            self.assertEqual(builder.steps, [])
        model = self.model(1, 0)
        relaxed = Builder(model, integers=False)
        with self.assertRaises(BuildError):
            relaxed.parity_fix("x", relaxed.row("given"))
        self.assertEqual(relaxed.steps, [])
        builder = Builder(model)
        with self.assertRaises(BuildError):
            builder.parity_fix("x", builder.upper("x"))
        self.assertEqual(builder.steps, [])
        continuous_other = Model("bad", [Variable("x", True, 0, 1), Variable("y", False, None, None)],
                                 [Row("given", Expr.var(0)+2*Expr.var(1), 0, 0)])
        builder = Builder(continuous_other)
        with self.assertRaises(BuildError):
            builder.parity_fix("x", builder.row("given"))
        self.assertEqual(builder.steps, [])

    def test_caller_combined_equalities_and_tighter_actual_binary_bounds(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("combined", [Variable("x", True, "1/3", 1), Variable("y", True, None, None)],
                       [Row("a", x+3*y, 1, 1), Row("b", y, 0, 0)])
        target = source.with_bounds("x", lower=1, upper=1)
        proof = Proof(source, target)
        forward = proof.claim(mapping="identity")
        supplied = forward.eq([(forward.row("a"), 1), (forward.row("b"), -1)])
        fixed = forward.parity_fix("x", supplied)
        self.assertEqual(fixed.expression, x-1)
        forward.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
