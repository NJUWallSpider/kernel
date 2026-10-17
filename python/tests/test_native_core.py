from fractions import Fraction
from types import SimpleNamespace
import unittest

from kernel_compiler import _native


class NativeCoreTests(unittest.TestCase):
    def test_expression_and_model_native_roundtrip(self):
        x = _native.Expr.var(0)
        self.assertEqual(x.to_json(), {"constant": "0", "terms": [[0, "1"]]})
        self.assertEqual((x + "1/2").constant, Fraction(1, 2))
        model = _native.Model(
            "m",
            [SimpleNamespace(name="x", integer=False, lower=Fraction(0), upper=Fraction(1))],
            [],
            x,
        )
        self.assertEqual(model.fact("VarLower", "x")[1], -x)
        self.assertEqual(model.stats()["variables"], 1)

    def test_native_compile_and_verify_share_one_artifact(self):
        x = _native.Expr.var(0)
        model = _native.Model(
            "m",
            [SimpleNamespace(name="x", integer=False, lower=Fraction(0), upper=Fraction(1))],
            [],
            x,
        )
        proof = _native.Proof(model, model)
        proof.forward.map([x])
        proof.forward.complete()
        proof.reverse.map([x])
        proof.reverse.complete()
        compiled = proof.compile()
        self.assertTrue(compiled.rpa.startswith("RPA 12\n"))
        self.assertGreater(len(compiled.rpx), 0)
        self.assertEqual(proof.verify()["obligations"], 6)


if __name__ == "__main__":
    unittest.main()
