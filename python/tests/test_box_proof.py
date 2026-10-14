import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Variable


class BoxProofTests(unittest.TestCase):
    def test_selected_bound_inequality_strengthening_has_full_verified_maps(self):
        model = Model("src", [Variable("x", lower=2), Variable("y", lower=None, upper=5)])
        target = model.add_row("box", -2*model.var("x")+model.var("y"), upper=5)
        proof = Proof(model, target)
        f, r = proof.bijection("identity", "identity", integers=False)
        fact = f.box_le(-2*model.var("x")+model.var("y")-5)
        self.assertEqual(f.steps[-1]["Lin"]["constant"], "-4")
        f.check("row.upper[box]", fact)
        f.complete(); r.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_inconclusive_bounds_do_not_emit_a_proof_step(self):
        model = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=None)])
        builder = Builder(model)
        for expression in (model.var("x")-"1/2", model.var("y"), -model.var("y")):
            with self.assertRaises(BuildError):
                builder.box_le(expression)
        self.assertEqual(builder.steps, [])
        self.assertEqual(builder.box_le(-1).expression, Expr(-1))


if __name__ == "__main__":
    unittest.main()
