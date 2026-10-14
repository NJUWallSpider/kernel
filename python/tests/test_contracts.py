from pathlib import Path
import tempfile
import unittest

from kernel_compiler import BuildError, Expr, Model, Proof, Row, Variable, attack, mutate, verify_bundle


class ContractTests(unittest.TestCase):
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
        level.eq([(level.row(len(model.rows)), -1)])
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
