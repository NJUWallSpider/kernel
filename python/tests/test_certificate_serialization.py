"""Leaf serialization preserves legacy proof bytes without a whole-tree wire copy."""
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import (Builder, Expr, KernelError, Model, Proof, Row, Variable,
                             compile_certificate, verify_bundle)
from kernel_compiler.proof import wire
from kernel_compiler import session


class CertificateSerializationTests(unittest.TestCase):
    def encode(self, value):
        return json.dumps(value, cls=session._ProofJSONEncoder, separators=(",", ":"))

    def test_nested_standard_containers_and_typed_leaves_match_legacy_bytes(self):
        model = Model("typed", [Variable("x", True, 0, 1)])
        builder = Builder(model)
        # More than Python's usual 4300 decimal digits exercises the exact
        # Fraction text fallback. This encoder test does not claim wire fit.
        wide = Fraction(10**6000+1, 10**5999+3)
        values = [
            {"tuple": (builder.lower("x"), Expr(Fraction(-2, 7), {0: Fraction(3, 5)}),
                       Fraction(-7, 11)), "empty": [], "primitive": [None, True, 2, "\u03bb\n"]},
            [{"wide": wide, "expression": Expr(wide, {0: -wide})},
             (builder.integer("x"), {"nested": ((Fraction(0),),)})],
        ]
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(self.encode(value),
                                 json.dumps(wire(value), separators=(",", ":")))
        self.assertEqual(self.encode({"q": Fraction(-7, 11), "map": (Expr.var(0),)}),
                         '{"q":"-7/11","map":[{"constant":"0","terms":[[0,"1"]]}]}')

    def typed_proof(self):
        x = Expr.var(0)
        source = Model("exact", [Variable("x", True, 0, 1)],
                       [Row("twice", 2*x, upper=2)], objective=x/4)
        proof = Proof(source, source)
        self.addCleanup(proof.close)
        claim = proof.claim(mapping="identity", projection="retained",
                            affine_projection=[(x, x)], input_objective_lower=0)
        objective_lower = claim.le([(claim.lower("x"), Fraction(1, 4))], expect=-x/4)
        # Large but within the existing 13600-bit scalar wire budget.
        scale = Fraction(2**13000+1, 2**13000+3)
        claim.le([(claim.upper("x"), scale)])
        claim.complete()
        certificate, request = proof.certificate(), proof.request()
        for contract in (certificate["claims"][0], request["claims"][0]):
            contract["input_objective_lower"] = Fraction(0)
            contract["affine_projection"] = ((x, x),)
        certificate["claims"] = tuple(certificate["claims"])
        request["claims"] = tuple(request["claims"])
        block = certificate["blocks"][0]
        for step, fact, multiplier in zip(block["steps"],
                                          (claim.lower("x"), claim.upper("x")),
                                          (Fraction(1, 4), scale)):
            step["Lin"]["constant"] = Fraction(0)
            step["Lin"]["terms"] = ((fact, multiplier),)
        block["steps"] = tuple(block["steps"])
        terminal = block["end"]["Return"]
        terminal["map"] = (x,)
        handles = (claim.lower("x"), claim.upper("x"), claim.integer("x"),
                   claim.row("twice"), objective_lower)
        terminal["checks"] = tuple(next((fact for fact in handles if fact.reference == reference), reference)
                                    for reference in terminal["checks"])
        certificate["blocks"] = tuple(certificate["blocks"])
        return proof, certificate, request

    def test_typed_raw_compile_keeps_exact_json_rpx_and_whole_mps_binding(self):
        proof, certificate, request = self.typed_proof()
        expected_certificate = json.dumps(wire(certificate), separators=(",", ":"))+"\n"
        expected_request = json.dumps(wire(request), separators=(",", ":"))+"\n"
        legacy_wire = session.wire
        def reject_full_wire(value):
            if value is certificate or value is request:
                raise AssertionError("compile must not wire-copy the full proof/request tree")
            return legacy_wire(value)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            committed = proof.target.write_mps(directory/"committed.mps")
            with patch.object(session, "wire", side_effect=reject_full_wire):
                artifacts = compile_certificate(
                    proof.source, proof.target, certificate, request, directory/"delivery",
                    kernel=proof.kernel, committed_model=committed)
            self.assertEqual((artifacts["proof"].parent/"certificate.json").read_bytes(),
                             expected_certificate.encode())
            self.assertEqual(artifacts["request"].read_bytes(), expected_request.encode())
            legacy_json, legacy_rpx = directory/"legacy.json", directory/"legacy.rpx"
            legacy_json.write_text(expected_certificate)
            proof.kernel.call("compile", legacy_json, legacy_rpx)
            self.assertEqual(artifacts["proof"].read_bytes(), legacy_rpx.read_bytes())
            report = verify_bundle(artifacts["proof"].parent/"delivery.json", kernel=proof.kernel)
            self.assertEqual(report["status"], "VERIFIED", report)
            manifest = json.loads((artifacts["proof"].parent/"delivery.json").read_text())
            self.assertEqual(manifest["artifact_binding"]["status"], "MATCHED")

    def test_unsupported_objects_and_cycles_reject_without_replacing_old_rpx(self):
        proof, certificate, request = self.typed_proof()
        circular = []
        circular.append(circular)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            artifacts = compile_certificate(proof.source, proof.target, certificate, request,
                                            directory, kernel=proof.kernel)
            original = artifacts["proof"].read_bytes()
            for bad, error in (({"opaque": object()}, TypeError), (circular, ValueError)):
                with self.subTest(error=error.__name__), self.assertRaises(error):
                    compile_certificate(proof.source, proof.target, bad, request, directory,
                                        kernel=proof.kernel)
                self.assertEqual(artifacts["proof"].read_bytes(), original)
                self.assertEqual(list(directory.glob(".*.tmp")), [])

    def test_primitive_float_still_reaches_native_invalid_and_preserves_old_rpx(self):
        proof, certificate, request = self.typed_proof()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            artifacts = compile_certificate(proof.source, proof.target, certificate, request,
                                            directory, kernel=proof.kernel)
            original = artifacts["proof"].read_bytes()
            malformed = wire(certificate)
            malformed["blocks"][0]["steps"][0]["Lin"]["constant"] = 0.0
            with self.assertRaises(KernelError) as rejected:
                compile_certificate(proof.source, proof.target, malformed, request, directory,
                                    kernel=proof.kernel)
            self.assertEqual(rejected.exception.report["status"], "INVALID")
            self.assertEqual(artifacts["proof"].read_bytes(), original)
            self.assertEqual(list(directory.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
