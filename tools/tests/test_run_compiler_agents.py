from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_compiler_agents import assess, digest


class OriginalInputIntegrityTests(unittest.TestCase):
    def workspace(self, directory):
        run = Path(directory)
        (run / "input").mkdir()
        (run / "output").mkdir()
        (run / "input/model.mps").write_text("pristine original problem\n")
        trusted = digest(run / "input/model.mps")
        (run / "workspace-manifest.json").write_text(json.dumps({"input_sha256": trusted}))
        return run, trusted

    def test_mutated_input_rejected_even_when_workspace_manifest_is_rewritten(self):
        for arm in ("compiler", "nomf"):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as directory:
                run, trusted = self.workspace(directory)
                (run / "input/model.mps").write_text("different easier problem\n")
                changed = digest(run / "input/model.mps")
                (run / "workspace-manifest.json").write_text(json.dumps({"input_sha256": changed}))
                with patch("run_compiler_agents.canonical_model") as readback:
                    result = assess(run, Path("uninvoked-kernel"), arm,
                                    expected_input_sha256=trusted)
                readback.assert_not_called()
                self.assertFalse(result["kernel_verified"])
                self.assertEqual(result["expected_input_sha256"], trusted)
                self.assertEqual(result["input_sha256"], changed)
                self.assertIn("original input changed", result["errors"][0])

    def test_mutable_workspace_manifest_cannot_override_the_trusted_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            run, trusted = self.workspace(directory)
            (run / "workspace-manifest.json").write_text(json.dumps({"input_sha256": "0" * 64}))
            with patch("run_compiler_agents.canonical_model", side_effect=ValueError("readback reached")) as readback:
                result = assess(run, Path("uninvoked-kernel"), "compiler",
                                expected_input_sha256=trusted)
            readback.assert_called_once()
            self.assertEqual(result["errors"], ["readback reached"])


if __name__ == "__main__":
    unittest.main()
