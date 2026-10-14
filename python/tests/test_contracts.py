from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import BuildError, Expr, Model, Proof, Row, Variable, attack, mutate, verify_bundle


class ContractTests(unittest.TestCase):
    def test_bijection_reverses_explicit_renamed_coordinate_pairs(self):
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=0, upper=2)])
        target = Model("dst", [Variable("b", lower=0, upper=2), Variable("a", lower=0, upper=1)])
        proof = Proof(source, target)
        f, r = proof.bijection({"b": source.var("y"), "a": source.var("x")},
                              {"x": target.var("a"), "y": target.var("b")},
                              projection=iter([("x", "a"), ("y", "b")]))
        self.assertEqual(f.claim["projection"], [(0, 1), (1, 0)])
        self.assertEqual(r.claim["projection"], [(1, 0), (0, 1)])
        f.complete(); r.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_correspondence_observations_do_not_pin_changed_auxiliaries(self):
        x, z = Expr.var(0), Expr.var(1)
        model = Model("src", [Variable("x", integer=True, lower=0, upper=1), Variable("z", lower=0, upper=1)], objective=z)
        proof = Proof(model, model)
        f, r = proof.correspondence({"x": x, "z": 0}, "identity", projection=iter([("x", "x")]))
        self.assertEqual(f.claim["projection"], r.claim["projection"])
        f.le([(f.lower("z"), 1)])
        f.complete(); r.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_integerness_of_continuous_expression_can_be_proved_and_rounded(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", integer=True, lower=0, upper=1)],
                       [Row("def", x-y, lower=0, upper=0), Row("cap", x, upper="9/10")])
        target = source.replace_row("cap", upper=0)
        proof = Proof(source, target)
        f, r = proof.bijection("identity", "identity")
        derived = f.int([(f.row("def"), 1), (f.integer("y"), 1)], expect=x)
        f.round(f.row("cap"), derived)
        f.complete()
        r.le([(r.row("cap"), 1)], constant="-9/10")
        r.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_completed_check_cache_and_terminal_replacement(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity")
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
        self.assertIn("Split", certificate["blocks"][0]["end"])
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")
        claim.complete()
        self.assertIsNone(claim._children)
        self.assertIn("Return", proof.certificate()["blocks"][0]["end"])

    def test_late_map_and_check_updates_are_not_overwritten(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity", objective="None")
        claim.complete()
        claim.map({"x": 0})
        certificate = proof.certificate()
        self.assertEqual(certificate["blocks"][0]["end"]["Return"]["map"], [Expr(0).to_json()])
        claim.map("identity")
        first = claim.le([(claim.lower("x"), 1)])
        claim.check("variable.lower[x]", first)
        claim.complete()
        claim.drop(first)
        second = claim.le([(claim.lower("x"), 1)])
        claim.check("variable.lower[x]", second)
        certificate = proof.certificate()
        self.assertEqual(certificate["blocks"][0]["end"]["Return"]["checks"][0], second.reference)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_completed_cache_distinguishes_index_from_label_selectors(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity")
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
        forward, reverse = proof.bijection({"x": x}, {"x": target.var("x"), "y": 2*target.var("x"),
                                                      "z": 2*target.var("x")+1}, integers=False)
        forward.substitution({"z": forward.row("dz"), "y": forward.row("dy")})
        forward.complete()
        reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_mutation_preserves_original_and_fixed_request(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        forward = proof.claim(mapping="identity")
        forward.complete()
        original = proof.certificate()
        mutated = mutate(original, ["blocks", 0, "end", "Return", "checks", 0], replacement="Exact")
        self.assertNotEqual(original["blocks"][0]["end"]["Return"]["checks"][0], "Exact")
        self.assertIs(original["claims"], mutated["claims"])
        with tempfile.TemporaryDirectory() as directory:
            result = attack(proof, directory, ["blocks", 0, "end", "Return", "checks", 0], replacement="Exact")
            self.assertTrue(result["rejected_as_expected"], result)

    def test_committed_solver_model_is_bound_to_proof_target(self):
        x = Expr.var(0)
        model = Model("src", [Variable("x", lower=0, upper=1)], [Row("r", x+1, upper=2)])
        proof = Proof(model, model)
        proof.claim(mapping="identity").complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model.write_mps(directory / "good.mps")
            model.with_bounds("x", upper=0).write_mps(directory / "bad.mps")
            with self.assertRaises(BuildError):
                proof.compile(directory / "bad", committed_model=directory / "bad.mps")
            result = proof.verify(directory / "good", committed_model=directory / "good.mps")
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertEqual(verify_bundle(directory / "good/delivery.json")["status"], "VERIFIED")
    def test_scope_cannot_be_borrowed_from_another_claim(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        forward = proof.claim(mapping="identity")
        reverse = proof.claim(reverse=True, mapping="identity")
        with self.assertRaises(BuildError):
            forward.complete(scope=reverse)

    def test_constructive_bijection_has_kernel_compositions(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=0, upper=1)],
                       [Row("def", y-x, lower=0, upper=0)])
        target = Model("tgt", [Variable("x", lower=0, upper=1)])
        proof = Proof(source, target)
        forward = proof.claim(mapping={"x": x}, integers=False)
        reverse = proof.claim(reverse=True, integers=False)
        forward.complete()
        paired = proof.injectivity(forward)
        n = len(source.vars)
        m = len(source.rows)
        # The caller identifies the actual observation and two definition rows.
        paired.eq([(paired.row(2*m), 1)], expect=paired.goals[0])
        paired.eq([(paired.row(0), 1), (paired.row(m), -1), (paired.row(2*m), 1)], expect=paired.goals[1])
        paired.complete()
        proof.add_bijection(forward.index, reverse.index, paired)
        scope = reverse.intervals([{"lower": [target.var("x")], "upper": [target.var("x")], "checks": ["Exact"]}])
        lower = scope.row(scope.generated_rows[0])
        upper = scope.row(scope.generated_rows[1])
        scope.eqpair(upper, lower)
        scope.le([(lower, 1), (scope.lower("x"), 1)])
        scope.le([(upper, 1), (scope.upper("x"), 1)])
        reverse.complete(scope=scope, mapping={"x": scope.model.var("x"), "y": scope.model.var(scope.generated_variables[0])})
        self.assertTrue(any(o.origin["kind"] == "bijection.coordinate" for o in reverse.plan(scope=scope, mapping=[Expr.var(0), Expr.var(1)])))
        with tempfile.TemporaryDirectory() as directory:
            report = proof.verify(directory)
            self.assertEqual(report["status"], "VERIFIED", report)
            self.assertEqual(verify_bundle(Path(directory) / "delivery.json")["status"], "VERIFIED")
            with (Path(directory) / "proof.rpx").open("ab") as stream:
                stream.write(b"tamper")
            self.assertEqual(verify_bundle(Path(directory) / "delivery.json")["status"], "INCOMPLETE")

    def test_strict_improvement_and_level_domain(self):
        x = Expr.var(0)
        model = Model("src", [Variable("x", lower=0, upper=1)], objective=x)
        proof = Proof(model, model)
        better = proof.improvement(x, integers=False, margin={"Predicate": "1"}, mapping={"x": 0})
        better.complete()
        proof.feasible_point([0], integers=False, objective=0)
        level = proof.claim(integers=False, input_objective_level=0, mapping={"x": 0})
        level.eq([(level.domain.objective_level, -1)])
        level.complete()
        with tempfile.TemporaryDirectory() as directory:
            report = proof.verify(directory)
            self.assertEqual(report["status"], "VERIFIED", report)

    def test_nontrivial_exact_extension_premise_cannot_be_forged(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity")
        with self.assertRaises(BuildError):
            claim.intervals([{"lower": [1], "upper": [Expr.var(0)], "checks": ["Exact"]}])


if __name__ == "__main__":
    unittest.main()
