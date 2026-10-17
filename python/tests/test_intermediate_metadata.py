from rule_checks import assert_rules_checked
from decimal import localcontext
from fractions import Fraction
import sys
import tempfile
import unittest

from kernel_compiler import Expr, Model, Proof, Row, Variable, exact


class IntermediateMetadataTests(unittest.TestCase):
    def test_wide_metadata_roundtrip_keeps_literal_and_bit_limits(self):
        wide = Fraction(10**6000 + 1, 10**5999 + 3)
        expr = Expr(wide, {0: -wide})
        with localcontext() as context:
            context.prec = 3
            data = expr.to_json()
            self.assertEqual(Expr.from_json(data, intermediate=True), expr)
            self.assertIn(data["constant"], repr(expr))
        with self.assertRaises(ValueError):
            Expr.from_json(data)
        with self.assertRaises(ValueError):
            exact(data["constant"])
        for bad in ["9"*19730, "1/0", "1_0", "nan"]:
            with self.assertRaises((ValueError, ZeroDivisionError)):
                Expr.from_json({"constant": bad}, intermediate=True)
        with self.assertRaises(ValueError):
            Expr.from_json({"constant": "9"*19729}, intermediate=True)
        summary = expr.summary()
        self.assertEqual(summary["constant"]["sign"], 1)
        self.assertLess(len(str(summary)), 500)
        many = Expr(3, {i: Fraction(1, 3) for i in range(1000)})
        self.assertEqual(many.summary(2), {"constant": "3", "term_count": 1000,
            "terms": [[0, "1/3"], [1, "1/3"]], "omitted_terms": 998})

    def test_valid_wide_derived_fact_resolves_and_verifies_without_global_policy_change(self):
        limit = sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits") else None
        scale = 10**3000
        source = Model("src", [Variable("x", lower=0, upper=0)])
        target = Model("dst", [Variable("y", lower=0, upper=0)],
                       [Row("large", scale*Expr.var(0), upper=0)])
        proof = Proof(source, target)
        proof.reverse.map({"x": 0}).complete()
        claim = proof.forward.map({"y": scale*source.var("x")})
        claim.le([(claim.lower("x"), scale)])
        first = claim.le([(claim.upper("x"), scale)])
        wide = claim.le([(first, scale)])
        goals = claim.plan()
        self.assertEqual(goals[2].expression, wide.expression)
        self.assertEqual(claim.missing(), [])
        claim.complete()
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))
        claim.complete(witnesses={2: wide})
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))
        if limit is not None:
            self.assertEqual(sys.get_int_max_str_digits(), limit)


if __name__ == "__main__":
    unittest.main()
