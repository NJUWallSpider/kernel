from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_compiler_agents import assess, create_workspace, digest, main


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


class CompilerSourceSelectionTests(unittest.TestCase):
    def inputs(self, directory):
        root = Path(directory) / "checkout"
        corpus = Path(directory) / "corpus"
        package = Path(directory) / "pinned/kernel_compiler"
        for path in (root / "docs", root / "python/kernel_compiler", root / "python/tests",
                     root / "tools", root / "cases/test9", corpus / "docs", corpus / "data",
                     corpus / "runs", package / "__pycache__"):
            path.mkdir(parents=True, exist_ok=True)
        (root / "python/kernel_compiler/__init__.py").write_text("DEFAULT_PACKAGE = True\n")
        (root / "docs/COMPILER_AGENT_PROTOCOL.md").write_text("DEFAULT_ADDON\n")
        (root / "docs/FORMAT.md").write_text("generic format\n")
        (root / "python/tests/test_proof.py").write_text("# generic proof example\n")
        (root / "cases/test9/preparation.json").write_text("{}\n")
        for name in ("run_compiler_agents.py", "verify_staged_agent_delivery.py"):
            (root / "tools" / name).write_text("# evaluator snapshot\n")
        baseline = (
            "Shared mathematical exploration and complete evidence requirements.\n"
            "You do NOT have access to mipframe or any other specialized model-analysis, presolve, reformulation, or optimization framework.\n"
            "Do not use a package whose purpose is to parse, inspect, presolve, reformulate, or solve LP/MIP models. The purpose of this baseline is to test what can be achieved by reasoning directly over the MPS representation with general-purpose computational tools.\n"
            "Shared final commitment requirements.\n")
        (corpus / "docs/NO_MIPFRAME.md").write_text(baseline)
        (corpus / "data/test9.mps").write_text("pristine problem\n")
        (package / "__init__.py").write_text("PINNED_PACKAGE = True\n")
        (package / "helper.py").write_text("PINNED_HELPER = True\n")
        (package / "__pycache__/ignored.pyc").write_bytes(b"not a source")
        protocol = Path(directory) / "selected-addon.md"
        protocol.write_text("SELECTED_ADDON: preserve complete native contracts.\n")
        api = Path(directory) / "pinned/API.md"
        api.write_text("PINNED_API\n")
        binary = Path(directory) / "pinned/rpx"
        binary.write_bytes(b"pinned native binary")
        interpreter = Path(directory) / "python"
        interpreter.write_text("test interpreter\n")
        return SimpleNamespace(root=root, corpus=corpus, package=package, protocol=protocol,
                               api=api, binary=binary, interpreter=interpreter, baseline=baseline,
                               batch=corpus / "runs/compiler-batch-override")

    def workspace(self, inputs, arm="compiler", **kwargs):
        return create_workspace(inputs.batch, inputs.corpus, "test9", arm,
                                inputs.interpreter, inputs.binary, inputs.api, **kwargs)

    def test_selected_package_and_addon_are_copied_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(directory)
            with patch("run_compiler_agents.ROOT", inputs.root):
                run = self.workspace(inputs, compiler_package=inputs.package,
                                     compiler_protocol=inputs.protocol)
            self.assertEqual((run / "compiler/python/kernel_compiler/__init__.py").read_text(),
                             "PINNED_PACKAGE = True\n")
            self.assertFalse((run / "compiler/python/kernel_compiler/__pycache__").exists())
            self.assertEqual((run / "compiler/API.md").read_text(), "PINNED_API\n")
            self.assertEqual((run / "compiler/bin/rpx").read_bytes(), inputs.binary.read_bytes())
            protocol = (run / "protocol.md").read_text()
            self.assertTrue(protocol.endswith("\n\n" + inputs.protocol.read_text()))
            self.assertIn("Shared mathematical exploration and complete evidence requirements.", protocol)
            self.assertIn("Apart from the supplied kernel_compiler API", protocol)
            self.assertNotIn("DEFAULT_ADDON", protocol)
            manifest = json.loads((run / "workspace-manifest.json").read_text())
            sources = manifest["compiler_sources"]
            self.assertEqual(sources["package"]["path"], str(inputs.package.resolve()))
            self.assertEqual(sources["protocol"]["sha256"], digest(inputs.protocol))
            self.assertEqual(sources["package"]["files_sha256"]["helper.py"],
                             manifest["compiler_snapshot"]["compiler/python/kernel_compiler/helper.py"])
            self.assertNotIn("__pycache__/ignored.pyc", sources["package"]["files_sha256"])

    def test_nomf_keeps_its_protocol_and_receives_no_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(directory)
            with patch("run_compiler_agents.ROOT", inputs.root):
                run = self.workspace(inputs, "nomf", compiler_package=inputs.package,
                                     compiler_protocol=inputs.protocol)
            self.assertEqual((run / "protocol.md").read_text(), inputs.baseline)
            self.assertFalse((run / "compiler").exists())
            manifest = json.loads((run / "workspace-manifest.json").read_text())
            self.assertEqual(manifest["compiler_snapshot"], {})
            self.assertNotIn("compiler_sources", manifest)

    def test_missing_selected_source_fails_before_creating_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(directory)
            for package, protocol, message in (
                    (inputs.package / "missing", inputs.protocol, "missing selected compiler package"),
                    (inputs.package, inputs.protocol.with_name("missing.md"), "missing selected compiler protocol")):
                with self.subTest(message=message), patch("run_compiler_agents.ROOT", inputs.root):
                    with self.assertRaisesRegex(ValueError, message):
                        self.workspace(inputs, compiler_package=package, compiler_protocol=protocol)
                self.assertFalse((inputs.corpus / "runs/test9-compiler-compiler-batch-override").exists())

    def test_original_positional_call_keeps_default_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(directory)
            with patch("run_compiler_agents.ROOT", inputs.root):
                run = self.workspace(inputs)
            self.assertEqual((run / "compiler/python/kernel_compiler/__init__.py").read_text(),
                             "DEFAULT_PACKAGE = True\n")
            self.assertTrue((run / "protocol.md").read_text().endswith("\n\nDEFAULT_ADDON\n"))

    def test_prepare_only_cli_records_overrides_in_batch_and_workspaces(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(directory)
            command = ["run_compiler_agents.py", "--cases", "test9", "--id", "override",
                       "--corpus", str(inputs.corpus), "--interpreter", str(inputs.interpreter),
                       "--kernel", str(inputs.binary), "--api-doc", str(inputs.api),
                       "--compiler-package", str(inputs.package),
                       "--compiler-protocol", str(inputs.protocol), "--prepare-only"]
            with patch("run_compiler_agents.ROOT", inputs.root), patch.object(sys, "argv", command), \
                    patch("run_compiler_agents.shutil.which", return_value=str(inputs.binary)), \
                    patch("run_compiler_agents.subprocess.run", return_value=SimpleNamespace(stdout="test-runtime")), \
                    patch("run_compiler_agents.run_agent") as launch, redirect_stdout(StringIO()):
                self.assertEqual(main(), 0)
            launch.assert_not_called()
            batch = json.loads((inputs.batch / "batch.json").read_text())
            self.assertEqual(batch["compiler_sources"]["protocol"]["sha256"], digest(inputs.protocol))
            compiler = inputs.corpus / "runs/test9-compiler-compiler-batch-override"
            manifest = json.loads((compiler / "workspace-manifest.json").read_text())
            self.assertEqual(manifest["compiler_sources"]["package"], batch["compiler_sources"]["package"])
            self.assertTrue((compiler / "protocol.md").read_text().endswith(inputs.protocol.read_text()))
            self.assertFalse((inputs.corpus / "runs/test9-nomf-compiler-batch-override/compiler").exists())


if __name__ == "__main__":
    unittest.main()
