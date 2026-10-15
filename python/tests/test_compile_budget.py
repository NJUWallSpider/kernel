"""JSON compile budgets do not change the proof or its verification policy."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import (Kernel, KernelError, Model, Proof, Variable,
                             compile_certificate)


class CompileBudgetConstructorTests(unittest.TestCase):
    def test_rejects_non_integer_non_positive_and_out_of_u64_values(self):
        # A real existing path avoids relying on binary discovery in this test;
        # constructing Kernel never executes it.
        for value in (True, False, 1.0, "1024", [], object()):
            with self.subTest(value=repr(value)), self.assertRaises(TypeError):
                Kernel(__file__, compile_json_bytes=value)
        for value in (0, -1, 1 << 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Kernel(__file__, compile_json_bytes=value)
        for value in (None, 1, (1 << 64) - 1):
            with self.subTest(value=value):
                kernel = Kernel(__file__, compile_json_bytes=value)
                self.assertEqual(kernel.compile_json_bytes, value)
                self.assertEqual(kernel.binary, Path(__file__).resolve())

    def test_legacy_kernel_without_budget_or_compile_metadata_remains_compatible(self):
        class LegacyKernel:
            def call(self, *arguments):
                self.arguments = arguments
                Path(arguments[-1]).write_bytes(b"legacy test RPX")
                return {"status": "COMPILED", "proof": str(arguments[-1])}

        kernel = LegacyKernel()
        model = Model("legacy", [Variable("x", lower=0, upper=1)])
        request = {"claims": [], "points": [], "improvements": [], "bijections": []}
        certificate = {"claims": [], "blocks": [], "points": [],
                       "improvements": [], "bijections": []}
        with tempfile.TemporaryDirectory() as directory:
            paths = compile_certificate(model, model, certificate, request, directory,
                                        kernel=kernel)
            self.assertEqual(kernel.arguments[0], "compile")
            self.assertEqual(len(kernel.arguments), 3)
            manifest = json.loads((paths["proof"].parent / "delivery.json").read_text())
            self.assertNotIn("compile_limits", manifest)
            self.assertNotIn(".proof.rpx.", json.dumps(manifest))
            self.assertEqual(paths["proof"].read_bytes(), b"legacy test RPX")

    def test_records_only_returned_limits_not_atomic_temporary_paths(self):
        class ReportingKernel:
            compile_json_bytes = 4096

            def call(self, *arguments):
                self.arguments = arguments
                Path(arguments[-1]).write_bytes(b"test RPX")
                return {"status": "COMPILED", "proof": str(arguments[-1]),
                        "compile_limits": {"certificate_json_bytes": 4096},
                        "other_report_field": "not delivery metadata"}

        kernel = ReportingKernel()
        model = Model("reporting", [Variable("x", lower=0, upper=1)])
        request = {"claims": [], "points": [], "improvements": [], "bijections": []}
        with tempfile.TemporaryDirectory() as directory:
            paths = compile_certificate(model, model, {"claims": [], "blocks": []},
                                        request, directory, kernel=kernel)
            self.assertEqual(kernel.arguments[:3], ("compile", "--max-json-bytes", 4096))
            manifest = json.loads((paths["proof"].parent / "delivery.json").read_text())
            self.assertEqual(manifest["compile_limits"], {"certificate_json_bytes": 4096})
            self.assertNotIn("other_report_field", manifest)
            self.assertNotIn(".proof.rpx.", json.dumps(manifest))


class NativeCompileBudgetTests(unittest.TestCase):
    def test_default_and_explicit_budget_keep_same_rpx_and_atomic_old_proof(self):
        kernel = Kernel(compile_json_bytes=None)
        model = Model("budget", [Variable("x", True, 0, 1)], objective=1)
        proof = Proof(model, model, kernel=kernel)
        self.addCleanup(proof.close)
        claim = proof.claim(mapping="identity", projection="retained")
        claim.complete()
        certificate, request = proof.certificate(), proof.request()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            with patch.object(kernel, "call", wraps=kernel.call) as recorded:
                paths = proof.compile(directory)
            calls = [call.args for call in recorded.call_args_list if call.args[0] == "compile"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(calls[0]), 3)  # None leaves the native default untouched.
            old_rpx = paths["proof"].read_bytes()
            old_manifest = (directory / "delivery.json").read_bytes()
            self.assertEqual(json.loads(old_manifest)["compile_limits"],
                             {"certificate_json_bytes": 1 << 30})
            size = (directory / "certificate.json").stat().st_size
            too_small = Kernel(kernel.binary, compile_json_bytes=size - 1)
            with self.assertRaises(KernelError) as rejected:
                compile_certificate(model, model, certificate, request, directory,
                                    kernel=too_small)
            self.assertEqual(rejected.exception.report["status"], "RESOURCE_LIMIT")
            self.assertIn("input file bytes", str(rejected.exception))
            self.assertEqual(paths["proof"].read_bytes(), old_rpx)
            self.assertEqual((directory / "delivery.json").read_bytes(), old_manifest)
            self.assertEqual(list(directory.glob(".*.tmp")), [])

            # The exact serialized size is admitted; extra budget does not
            # change RPX bytes, the Request, or verification limits.
            for budget in (size, size + 100):
                sufficient = Kernel(kernel.binary, compile_json_bytes=budget)
                actual = compile_certificate(model, model, certificate, request, directory,
                                             kernel=sufficient)
                self.assertEqual(actual["proof"].read_bytes(), old_rpx)
                manifest = json.loads((directory / "delivery.json").read_text())
                self.assertEqual(manifest["compile_limits"],
                                 {"certificate_json_bytes": budget})
                self.assertNotIn(".proof.rpx.", json.dumps(manifest))
                report = sufficient.verify(actual["source"], actual["target"],
                                           actual["proof"], actual["request"])
                self.assertEqual(report["status"], "VERIFIED", report)
                self.assertEqual(list(directory.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
