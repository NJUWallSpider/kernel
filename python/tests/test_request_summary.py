import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Expr, Model, Proof, Variable, compile_certificate
from kernel_compiler.request_summary import summarize_request


class RequestSummaryTests(unittest.TestCase):
    def test_scope_is_explicit_and_bounded_without_obligation_planning(self):
        source = Model("source", [Variable("x", integer=True, lower=0, upper=1),
                                  Variable("aux", lower=0, upper=2)])
        target = Model("target", [Variable("other", lower=0, upper=2),
                                  Variable("core", integer=True, lower=0, upper=1)])
        proof = Proof(source, target)
        claim = proof.claim(mapping={"other": source.var("aux"), "core": source.var("x")},
                            input_integers=True, output_integers=False, objective="None",
                            projection=[("x", "core"), ("aux", "other")],
                            input_objective_lower=0, input_objective_level=0,
                            input_halfspace=source.var("x")-1,
                            affine_projection=[(source.var("x")+source.var("aux"),
                                                target.var("core")+target.var("other"))])
        with patch.object(proof, "request", side_effect=AssertionError("full Request copy")), \
             patch.object(proof.kernel, "call", side_effect=AssertionError("Kernel call")):
            summary = proof.contract_summary(max_items=1)
            empty = proof.contract_summary(max_items=0)
        item = summary["claims"][0]
        self.assertEqual((item["direction"], item["input_integers"], item["output_integers"],
                          item["objective"], item["inverse_claim"]),
                         ("source_to_target", True, False, "None", None))
        self.assertEqual(item["observations"]["coordinates"], [{"input": "x", "output": "core"}])
        self.assertEqual(item["observations"]["coordinate_count"], 2)
        self.assertEqual(item["observations"]["omitted_coordinates"], 1)
        self.assertEqual(item["observations"]["affine"][0]["input"]["omitted_terms"], 1)
        self.assertEqual(set(item["input_restrictions"]), {"objective_level", "halfspace"})
        self.assertEqual(item["input_objective_lower"], "0")
        self.assertEqual(item["input_objective_lower_scope"], "declared_input_domain")
        self.assertEqual(empty["counts"]["claims"], 1)
        self.assertEqual(empty["claims"], [])
        self.assertEqual(empty["omitted_claims"], 1)
        self.assertFalse(claim.steps)
        proof.close()

    def test_global_bound_is_not_a_domain_restriction_and_inverse_is_separate(self):
        model = Model("model", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        f, r = proof.bijection("identity", "identity", integers=False)
        f.claim["input_objective_lower"] = "0"
        summary = proof.contract_summary()
        self.assertEqual(summary["claims"][0]["input_restrictions"], {})
        self.assertEqual(summary["claims"][0]["inverse_claim"], 1)
        self.assertEqual(summary["claims"][1]["direction"], "target_to_source")
        self.assertEqual(summary["counts"]["bijections"], 0)  # paired-domain injectivity is a separate request
        proof.close()

    def test_restricted_lower_bound_is_not_presented_as_global(self):
        x = Expr.var(0)
        model = Model("conditional", [Variable("x", lower=0, upper=1)], objective=x)
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity", integers=False,
                            input_objective_level=1, input_objective_lower=1)
        claim.le([(claim.domain.objective_level, -1)])
        claim.complete()
        summary = proof.contract_summary()["claims"][0]
        self.assertEqual(summary["input_objective_lower"], "1")
        self.assertEqual(summary["input_restrictions"], {"objective_level": "1"})
        self.assertEqual(summary["input_objective_lower_scope"], "declared_input_domain")
        # x=0 is feasible outside the restricted domain, so 1 is not a global bound.
        self.assertEqual(model.check_point([0]), [])
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")
        proof.close()

    def test_receipt_summary_does_not_change_complete_request_or_verification(self):
        model = Model("model", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        f, r = proof.bijection("identity", "identity", integers=False)
        f.complete(); r.complete()
        proof.feasible_point({"x": 0}, integers=False)
        full = proof.request()
        with tempfile.TemporaryDirectory() as directory:
            result = proof.verify(directory)
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertEqual(json.loads((Path(directory)/"request.json").read_text()), json.loads(json.dumps(full)))
            self.assertEqual(result["request_summary"], proof.contract_summary())
            self.assertEqual(result["request_summary"]["points"][0]["kind"], "Feasible")
            self.assertEqual(json.loads((Path(directory)/"verification.json").read_text())["request_summary"],
                             result["request_summary"])
        proof.close()

    def test_large_observations_and_scalars_stay_bounded(self):
        model = Model("model", [Variable("x", lower=0, upper=1)])
        claim = {"reverse": False, "input_integers": False, "output_integers": False,
                 "objective": "Equal", "inverse": None, "projection": [(0, 0)]*100000,
                 "input_objective_lower": str(1 << 1000)}
        summary = summarize_request(model, model, [claim], max_items=2)
        self.assertLess(len(json.dumps(summary)), 2500)
        self.assertEqual(summary["claims"][0]["observations"]["coordinate_count"], 100000)
        self.assertEqual(summary["claims"][0]["input_objective_lower"]["numerator_bits"], 1001)
        for invalid in (True, -1, "1"):
            with self.assertRaises(ValueError):
                summarize_request(model, model, [claim], max_items=invalid)

    def test_invalid_raw_requests_keep_native_feedback(self):
        model = Model("model", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.claim(mapping="identity").complete()
        certificate, request = proof.certificate(), proof.request()
        certificate["claims"][0]["projection"] = [(99, 0)]
        request["claims"][0]["projection"] = [(99, 0)]
        with tempfile.TemporaryDirectory() as directory:
            paths = compile_certificate(model, model, certificate, request, directory)
            delivery = json.loads((Path(directory)/"delivery.json").read_text())
            self.assertEqual(delivery["request_summary"]["claims"][0]["observations"]["coordinates"][0]["input"],
                             {"index": 99, "error": "invalid_coordinate"})
            result = proof.kernel.verify(paths["source"], paths["target"], paths["proof"], paths["request"])
            self.assertEqual(result["status"], "INVALID", result)
        # Malformed Request metadata is optional, even when a raw certificate
        # itself is valid. The native parser retains the final decision.
        request = {"claims": [{"projection": [[0]]}]}
        with tempfile.TemporaryDirectory() as directory:
            paths = compile_certificate(model, model, proof.certificate(), request, directory)
            delivery = json.loads((Path(directory)/"delivery.json").read_text())
            self.assertEqual(delivery["request_summary"]["status"], "UNAVAILABLE")
            result = proof.kernel.verify(paths["source"], paths["target"], paths["proof"], paths["request"])
            self.assertEqual(result["status"], "INVALID", result)
        proof.close()


if __name__ == "__main__":
    unittest.main()
