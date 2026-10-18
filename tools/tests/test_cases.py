import json
from pathlib import Path
import tempfile
import unittest

from cases import (
    build_manifest,
    compile_recipe,
    verify_case,
    assemble_case,
    disassemble_case,
    check_case,
)
from rpx import ModelBuilder, Proof, ArtifactMismatchError


RECIPE = """from rpx import Proof

def build(source, target, *, source_path=None, target_path=None):
    proof = Proof(source, target)
    forward = proof.forward.map({"x": 0})
    reverse = proof.reverse.map(default="same_name")
    forward.finish()
    reverse.derive.le(reverse.upper("x") - 1)
    reverse.finish()
    return proof
"""


class CasePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        b = ModelBuilder("source")
        x = b.add_var("x", integer=True, lower=0, upper=1)
        b.minimize(x)
        source = b.build()
        target = source.with_bounds("x", upper=0)
        self.source = self.root / "source.mcm"
        self.target = self.root / "target.mcm"
        source.write_mcm(self.source)
        target.write_mcm(self.target)
        self.recipe = self.root / "recipe.py"
        self.recipe.write_text(RECIPE)
        self.out = self.root / "case"
        self.addCleanup(self.temporary.cleanup)

    def test_native_recipe_compiles_and_checks(self):
        result = compile_recipe(
            source=self.source, target=self.target, recipe=self.recipe, out=self.out
        )
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
        compile_recipe(
            source=self.source, target=self.target, recipe=self.recipe, out=self.out
        )
        delivery = self.out / "delivery.json"
        document = json.loads(delivery.read_text())
        document["artifacts"]["proof"]["sha256"] = "0" * 64
        delivery.write_text(json.dumps(document))
        with self.assertRaises(ArtifactMismatchError):
            verify_case(self.out)

    def test_unknown_recipe_selection_is_rejected(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"runs": ".", "cases": []}))
        with self.assertRaises(ValueError):
            build_manifest(manifest, out_root=self.out, only=["missing"])

    def test_non_proof_recipe_is_rejected(self):
        self.recipe.write_text(
            "def build(source, target, *, source_path=None, target_path=None):\n    return None\n"
        )
        with self.assertRaises(TypeError):
            compile_recipe(
                source=self.source, target=self.target, recipe=self.recipe, out=self.out
            )


if __name__ == "__main__":
    unittest.main()
