import json
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Expr, Model, Proof, Variable, verify_bundle


class MiOptTests(unittest.TestCase):
    def test_dominated_solution_deletion_and_no_request_input(self):
        x = Expr.var(0)
        source = Model("source", [Variable("x", True, 0, 1)], objective=x)
        target = Model("target", [Variable("x", True, 0, 0)], objective=x)
        proof = Proof(source, target)
        self.addCleanup(proof.close)
        f, r = (proof.forward.map({"x": 0}), proof.reverse.map("identity"))
        f.complete()
        r.le([(r.upper("x"), 1)], constant=-1)
        r.complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            result = proof.verify(directory)
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertEqual(result["guarantee"], "MI_OPT")
            self.assertFalse((directory/"request.json").exists())
            self.assertNotIn("request", result["artifacts"])
            self.assertEqual(verify_bundle(directory/"delivery.json")["status"], "VERIFIED")
            # A stale sidecar cannot change the fixed target in either direction.
            (directory/"request.json").write_text("[]")
            self.assertEqual(verify_bundle(directory/"delivery.json")["status"], "VERIFIED")

    def test_two_required_blocks_and_no_property_selection(self):
        from kernel_compiler import BuildError, KernelError, compile_certificate
        model = Model("m", [Variable("x", True, 0, 1)])
        proof = Proof(model, model)
        self.addCleanup(proof.close)
        proof.forward.map("identity").complete()
        with self.assertRaises(BuildError):
            proof.certificate()
        proof.reverse.map("identity").complete()
        certificate = proof.certificate()
        self.assertEqual(set(certificate), {"forward", "reverse"})
        for name in ("claim", "bijection", "improvement", "injectivity", "feasible_point"):
            self.assertFalse(hasattr(proof, name))
        with tempfile.TemporaryDirectory() as directory:
            for field in ("claims", "points", "improvements", "bijections"):
                malformed = dict(certificate, **{field: []})
                with self.assertRaises(KernelError):
                    compile_certificate(model, model, malformed, directory)

    def test_one_certificate_and_shared_budget(self):
        model = Model("m", [Variable("x", True, 0, 1)])
        proof = Proof(model, model)
        self.addCleanup(proof.close)
        proof.forward.map("identity").complete(); proof.reverse.map("identity").complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            report = proof.verify(directory)
            self.assertEqual(report["status"], "VERIFIED")
            work = report["statistics"]["work"]
            self.assertEqual(proof.verify(directory, work=work)["status"], "VERIFIED")
            self.assertEqual(proof.verify(directory, work=work-1)["status"], "RESOURCE_LIMIT")
            manifest = directory/"delivery.json"
            document = json.loads(manifest.read_text())
            document["pieces"] *= 2
            manifest.write_text(json.dumps(document))
            self.assertEqual(verify_bundle(manifest)["status"], "INCOMPLETE")
