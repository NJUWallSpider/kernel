import os
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import BuildError, Model, Proof, Variable


class ArtifactAliasTests(unittest.TestCase):
    def test_binding_cannot_be_invalidated_by_generated_file_aliases(self):
        source = Model("src", [Variable("x", lower=0, upper=1)])
        target = source.with_bounds("x", upper=0)
        proof = Proof(source, target)
        f, r = proof.correspondence({"x": 0}, "identity", integers=False)
        f.complete()
        r.box_le(target.var("x")-1)
        r.complete()
        for alias in ("same_path", "symlink", "hardlink"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                output = directory / "output"
                output.mkdir()
                generated = output / "source.mcm"
                if alias == "same_path":
                    target.write_mcm(generated)
                    committed = generated
                else:
                    committed = directory / "reformulated.mps"
                    target.write_mps(committed)
                    if alias == "symlink":
                        generated.symlink_to(committed)
                    else:
                        os.link(committed, generated)
                original = committed.read_bytes()
                with self.assertRaisesRegex(BuildError, "aliases a generated proof file"):
                    proof.verify(output, committed_model=committed)
                self.assertEqual(committed.read_bytes(), original)
                self.assertFalse((output / "proof.rpx").exists())
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            committed = directory / "reformulated.mps"
            target.write_mps(committed)
            report = proof.verify(directory / "output", committed_model=committed)
            self.assertEqual(report["status"], "VERIFIED")
            self.assertEqual(report["artifact_audit"]["status"], "MATCHED")


if __name__ == "__main__":
    unittest.main()
