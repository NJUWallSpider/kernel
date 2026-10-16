from rule_checks import assert_rules_checked
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import BuildError, Expr, Model, Proof, Row, Variable, attack, mutate, verify_bundle


class ContractTests(unittest.TestCase):






    def test_integerness_of_continuous_expression_can_be_proved_and_rounded(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", integer=True, lower=0, upper=1)],
                       [Row("def", x-y, lower=0, upper=0), Row("cap", x, upper="9/10")])
        target = source.replace_row("cap", upper=0)
        proof = Proof(source, target)
        f, r = (proof.forward.map("identity"), proof.reverse.map("identity"))
        derived = f.int([(f.row("def"), 1), (f.integer("y"), 1)], expect=x)
        f.round(f.row("cap"), derived)
        f.complete()
        r.le([(r.row("cap"), 1)], constant="-9/10")
        r.complete()
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))

    def test_completed_check_cache_and_terminal_replacement(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map("identity")
        claim.complete()
        with patch.object(claim, "complete", wraps=claim.complete) as complete:
            proof.certificate()
            proof.certificate()
            self.assertEqual(complete.call_count, 0)
            claim.le([(claim.lower("x"), 1)])
            proof.certificate()
            self.assertEqual(complete.call_count, 1)
        claim.split(Expr.var(0), integer=None,
                    left=lambda b, s: claim.complete(scope=b, mapping="identity"),
                    right=lambda b, s: claim.complete(scope=b, mapping="identity"))
        certificate = proof.certificate()
        self.assertIn("Split", certificate["forward"]["end"])
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))
        claim.complete()
        self.assertIsNone(claim._children)
        self.assertIn("Return", proof.certificate()["forward"]["end"])

    def test_late_map_and_check_updates_are_not_overwritten(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map("identity")
        claim.complete()
        claim.map({"x": 0})
        certificate = proof.certificate()
        self.assertEqual(certificate["forward"]["end"]["Return"]["map"], [Expr(0).to_json()])
        claim.map("identity")
        first = claim.le([(claim.lower("x"), 1)])
        claim.check("variable.lower[x]", first)
        claim.complete()
        claim.drop(first)
        second = claim.le([(claim.lower("x"), 1)])
        claim.check("variable.lower[x]", second)
        certificate = proof.certificate()
        self.assertEqual(certificate["forward"]["end"]["Return"]["checks"][0], second.reference)
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))

    def test_completed_cache_distinguishes_index_from_label_selectors(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map("identity")
        fact = claim.lower("x")
        claim.check(0, fact)
        claim.complete()
        del claim._assigned[0]
        claim.check("0", fact)
        with self.assertRaises(BuildError):
            proof.certificate()

    def test_explicit_substitution_proof_expands_all_changed_facts(self):
        x, y, z = (Expr.var(i) for i in range(3))
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=0, upper=2),
                              Variable("z", lower=1, upper=3)],
                       [Row("dy", y-2*x, lower=0, upper=0), Row("dz", z-y, lower=1, upper=1)], objective=z)
        target = source.substitute({"y": 2*x, "z": 2*x+1}, drop_rows=["dy", "dz"])
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map({"x": x}), proof.reverse.map({"x": target.var("x"), "y": 2*target.var("x"),
                                                      "z": 2*target.var("x")+1}))
        forward.substitution({"z": forward.row("dz"), "y": forward.row("dy")})
        forward.complete()
        reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))

    def test_mutation_preserves_original_and_fixed_request(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        forward = proof.forward.map("identity")
        forward.complete()
        original = proof.certificate()
        mutated = mutate(original, ["forward", "end", "Return", "checks", 0], replacement="Exact")
        self.assertNotEqual(original["forward"]["end"]["Return"]["checks"][0], "Exact")
        self.assertIs(original["reverse"], mutated["reverse"])
        with tempfile.TemporaryDirectory() as directory:
            result = attack(proof, directory, ["forward", "end", "Return", "checks", 0], replacement="Exact")
            self.assertTrue(result["rejected_as_expected"], result)

    def test_committed_solver_model_is_bound_to_proof_target(self):
        x = Expr.var(0)
        model = Model("src", [Variable("x", lower=0, upper=1)], [Row("r", x+1, upper=2)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        proof.forward.map("identity").complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model.write_mps(directory / "good.mps")
            model.with_bounds("x", upper=0).write_mps(directory / "bad.mps")
            with self.assertRaises(BuildError):
                proof.compile(directory / "bad", committed_model=directory / "bad.mps")
            result = proof.verify(directory / "good", committed_model=directory / "good.mps")
            assert_rules_checked(self, result)
            self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
            self.assertEqual(result["artifact_audit"]["committed_model"], result["artifacts"]["committed_model"])
            self.assertEqual(result["artifact_audit"]["proof_target"], result["artifacts"]["target"])
            saved = json.loads((directory / "good/verification.json").read_text())
            self.assertEqual(saved["artifact_audit"], result["artifact_audit"])
            assert_rules_checked(self, verify_bundle(directory / "good/delivery.json"))

    def test_committed_canonical_json_audit_uses_python_reader_label(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        proof.forward.map("identity").complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            committed = directory / "committed.JSON"
            model.write_json(committed)
            result = proof.verify(directory / "proof", committed_model=committed)
            assert_rules_checked(self, result)
            self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
            self.assertEqual(result["artifact_audit"]["method"], "Python canonical JSON readback and exact named formulation comparison")
    def test_scope_cannot_be_borrowed_from_another_claim(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        forward = proof.forward.map("identity")
        reverse = proof.reverse.map("identity")
        with self.assertRaises(BuildError):
            forward.complete(scope=reverse)



    def test_nontrivial_exact_extension_premise_cannot_be_forged(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map("identity")
        with self.assertRaises(BuildError):
            claim.intervals([{"lower": [1], "upper": [Expr.var(0)], "checks": ["Exact"]}])


if __name__ == "__main__":
    unittest.main()
