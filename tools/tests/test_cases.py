import json
from pathlib import Path
import tempfile
import unittest

from cases import compile_recipe, verify_case, assemble_case, disassemble_case, check_case
from kernel_compiler import Expr, Model, Proof, Variable


RECIPE = '''from kernel_compiler import Proof

def build(source, target):
    proof = Proof(source, target)
    forward = proof.forward.map({"x": 0})
    reverse = proof.reverse.map("identity")
    forward.complete()
    reverse.le([(reverse.upper("x"), 1)], constant=-1)
    reverse.complete()
    return proof
'''


class CasePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = Model("source", [Variable("x", True, 0, 1)], objective=Expr.var(0))
        target = Model("target", [Variable("x", True, 0, 0)], objective=Expr.var(0))
        self.source = self.root / "source.mcm"
        self.target = self.root / "target.mcm"
        source.write_mcm(self.source)
        target.write_mcm(self.target)
        self.recipe = self.root / "recipe.py"
        self.recipe.write_text(RECIPE)
        self.out = self.root / "case"
        self.addCleanup(self.temporary.cleanup)

    def test_native_recipe_compiles_and_checks(self):
        result = compile_recipe(source=self.source, target=self.target,
                                recipe=self.recipe, out=self.out)
        self.assertEqual(result["status"], "VERIFIED", result)
        self.assertEqual(result["guarantee"], "MI_OPT")
        verified = verify_case(self.out)
        self.assertEqual(verified["status"], "VERIFIED")
        self.assertEqual(verified["delivery"]["status"], "MATCHED")
        self.assertEqual(assemble_case(self.out)["status"], "MATCHED")
        self.assertEqual(disassemble_case(self.out)["status"], "MATCHED")
        checked = check_case(self.out)
        self.assertEqual(checked["status"], "VERIFIED")
        self.assertEqual(checked["assemble"], "MATCHED")
        self.assertEqual(checked["disassemble"], "MATCHED")

    def test_delivery_mismatch_is_reported(self):
        compile_recipe(source=self.source, target=self.target,
                       recipe=self.recipe, out=self.out)
        delivery = self.out / "delivery.json"
        document = json.loads(delivery.read_text())
        document["artifacts"]["proof"]["sha256"] = "0" * 64
        delivery.write_text(json.dumps(document))
        result = verify_case(self.out)
        self.assertEqual(result["delivery"]["status"], "MISMATCH")

    def test_non_proof_recipe_is_rejected(self):
        self.recipe.write_text("def build(source, target):\n    return None\n")
        with self.assertRaises(TypeError):
            compile_recipe(source=self.source, target=self.target,
                           recipe=self.recipe, out=self.out)


if __name__ == "__main__":
    unittest.main()
