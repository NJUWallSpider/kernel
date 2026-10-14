from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import BuildError, Expr, Model, Proof, Row, Variable, attack, mutate, verify_bundle


class ContractTests(unittest.TestCase):
    def test_improvement_cases_preserve_the_root_assumption_index(self):
        x = Expr.var(0)
        model = Model("improve", [Variable("x", lower=0, upper=1)], objective=x)
        proof = Proof(model, model)
        better = proof.improvement(x, integers=False, mapping={"x": 0})
        self.assertEqual(better.domain.positive.expression, -x)
        self.assertEqual(better.domain.positive.reference, {"Assumption": 0})
        better.cases(x, integer=False, kind="Le", expect=Expr(0),
                     left=lambda branch, assumption: branch.le([(assumption, 1), (branch.lower("x"), 1)], expect=Expr(0)),
                     right=lambda branch, assumption: branch.le())
        branch_ref = better.steps[0]["Cases"]["left"]["steps"][0]["Lin"]["terms"][0][0]
        self.assertEqual(branch_ref, {"Assumption": 1})
        better.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")
        ordinary = proof.claim(mapping="identity")
        with self.assertRaises(BuildError):
            ordinary.le([(better.domain.positive, 1)])

    def test_improvement_terminal_split_uses_each_actual_branch_assumption(self):
        x = Expr.var(0)
        model = Model("improve_split", [Variable("x", lower=0, upper=1)], objective=x)
        proof = Proof(model, model)
        better = proof.improvement(x, integers=False, margin={"Predicate": "1/2"})
        def left(branch, assumption):
            upper = branch.le([(assumption, "1/2")], constant="-3/4", expect=x/2-1)
            branch.le([(branch.lower("x"), "1/2")], expect=-x/2)
            better.complete(scope=branch, mapping={"x": x/2}, witnesses={"variable.upper[x]": upper})
        def right(branch, assumption):
            gap = branch.le([(assumption, "1/2")], constant="-1/4", expect=-x/2)
            better.complete(scope=branch, mapping={"x": 0}, witnesses={"objective.non_increasing": gap})
        better.split(x-"1/2", integer=False, left=left, right=right)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_positive_refutation_closes_an_excluded_strict_domain_branch(self):
        x = Expr.var(0)
        model = Model("positive_refutation", [Variable("x", lower=0, upper=1)], objective=x)
        proof = Proof(model, model)
        better = proof.improvement(x, integers=False)
        better.split(x, integer=False,
                     left=lambda branch, assumption: branch.close_positive(assumption),
                     right=lambda branch, assumption: better.complete(scope=branch, mapping={"x": 0}))
        self.assertIn("PositiveRefutation", better._children[0].end)
        with self.assertRaises(BuildError):
            better.close_positive(better.domain.positive)  # -x is the weak fact, not +x.
        ordinary = Proof(model, model).claim(mapping="identity")
        with self.assertRaises(BuildError):
            ordinary.close_positive(ordinary.lower("x"))
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

    def test_improvement_margin_semantics_and_weak_domain_fact(self):
        x = Expr.var(0)
        model = Model("margin", [Variable("x", lower=0, upper=2)], objective=x)
        proof = Proof(model, model)
        # On x>1, x->0 saves at least the fixed margin 1. The root's weak fact
        # 1-x<=0 is the actual objective-gap witness, with no row/branch search.
        fixed = proof.improvement(x-1, integers=False, margin={"Constant": 1}, mapping={"x": 0})
        fixed.complete()
        self.assertEqual(fixed.end["ImproveReturn"]["checks"][-1], {"Assumption": 0})
        for kind in ("Constant", "Predicate"):
            for q in (0, -1):
                with self.assertRaises(BuildError):
                    proof.improvement(x, integers=False, margin={kind: q}, mapping={"x": 0})
        # A zero predicate has an empty strict domain, not a nonemptiness claim.
        vacuous = proof.improvement(0, integers=False, mapping="identity")
        vacuous.complete()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(proof.verify(directory)["status"], "VERIFIED")

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
            self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
            self.assertEqual(result["artifact_audit"]["committed_model"], result["artifacts"]["committed_model"])
            self.assertEqual(result["artifact_audit"]["proof_target"], result["artifacts"]["target"])
            saved = json.loads((directory / "good/verification.json").read_text())
            self.assertEqual(saved["artifact_audit"], result["artifact_audit"])
            self.assertEqual(verify_bundle(directory / "good/delivery.json")["status"], "VERIFIED")

    def test_committed_canonical_json_audit_uses_python_reader_label(self):
        model = Model("src", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        proof.claim(mapping="identity").complete()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            committed = directory / "committed.JSON"
            model.write_json(committed)
            result = proof.verify(directory / "proof", committed_model=committed)
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
            self.assertEqual(result["artifact_audit"]["method"], "Python canonical JSON readback and exact named formulation comparison")
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
