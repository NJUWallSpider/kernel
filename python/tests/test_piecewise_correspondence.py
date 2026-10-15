"""Deferred full maps can combine a supplied split and constructive SignedLift.

This is a generic API regression, not a case-specific reformulation preparer.
"""
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Expr, Model, Proof, Row, Variable, attack


class PiecewiseCorrespondenceTests(unittest.TestCase):
    def test_deferred_piecewise_canonicalization_and_constructive_reconstruction(self):
        capacity = 3
        flow, positive, negative, up, down = (Expr.var(i) for i in range(5))
        source = Model(
            "two_activations",
            [Variable("Flow", lower=-capacity, upper=capacity),
             Variable("p", upper=capacity), Variable("n", upper=capacity),
             Variable("u", True, 0, 1), Variable("v", True, 0, 1)],
            [Row("balance", flow-positive+negative, lower=0, upper=0),
             Row("positive_capacity", positive-capacity*up, upper=0),
             Row("negative_capacity", negative-capacity*down, upper=0)],
            objective=up+down)
        target_flow, active = Expr.var(0), Expr.var(1)
        target = Model(
            "one_activation",
            [Variable("Flow", lower=-capacity, upper=capacity),
             Variable("z", True, 0, 1)],
            [Row("positive_capacity", target_flow-capacity*active, upper=0),
             Row("negative_capacity", -target_flow-capacity*active, upper=0)],
            objective=active)

        proof = Proof(source, target)
        self.addCleanup(proof.close)
        # Neither direction needs a single affine map at declaration time.
        forward, reverse = proof.correspondence(projection="retained")
        self.assertIsNone(forward.mapping)
        self.assertIsNone(reverse.mapping)

        def inactive(scope, assumption):
            # u <= 0 and the actual lower bound give u=0, then p=0.
            u_zero = scope.eqpair(assumption, scope.lower("u"))
            p_upper = scope.le([(scope.row("positive_capacity"), 1),
                                (u_zero, capacity)], expect=positive)
            p_zero = scope.eqpair(p_upper, scope.lower("p"))
            scope.le([(scope.row("balance"), 1), (p_zero, 1),
                      (scope.lower("n"), 1), (scope.lower("v"), capacity)],
                     expect=flow-capacity*down)
            scope.le([(scope.row("balance"), -1),
                      (scope.row("negative_capacity"), 1),
                      (scope.lower("p"), 1)], expect=-flow-capacity*down)
            scope.le([(u_zero, -1)], expect=-up)
            forward.complete(scope=scope, mapping={"Flow": flow, "z": down})

        def activated(scope, assumption):
            # The other integer branch has u=1. Declared Flow bounds justify
            # z=1 even when v=1 as well; this map is allowed to improve cost.
            u_one = scope.eqpair(scope.upper("u"), assumption)
            scope.le([(u_one, -1), (scope.lower("v"), 1)],
                     expect=1-up-down)
            forward.complete(scope=scope, mapping={"Flow": flow, "z": 1})

        forward.split(up, left=inactive, right=activated)

        # The reverse direction supplies the five explicit parent premises.
        original_flow, original_active = reverse.model.var("Flow"), reverse.model.var("z")
        scope = reverse.signed([{
            "capacity": capacity, "flow": original_flow, "activation": original_active,
            "checks": [reverse.lower("z"), reverse.upper("z"), reverse.integer("z"),
                       reverse.row("positive_capacity"), reverse.row("negative_capacity")]}])
        item = scope.signed_decomposition(0)
        # The generated activation bounds and capacity laws also prove the
        # original finite p/n bounds; no generated variable is omitted.
        scope.le([(item.positive_capacity, 1),
                  (scope.upper(item.positive_activation), capacity)],
                 expect=item.positive-capacity)
        scope.le([(item.negative_capacity, 1),
                  (scope.upper(item.negative_activation), capacity)],
                 expect=item.negative-capacity)
        scope.eq([(item.flow, -1)],
                 expect=original_flow-item.positive+item.negative)
        reverse.complete(scope=scope, mapping={
            "Flow": original_flow, "p": item.positive, "n": item.negative,
            "u": item.positive_activation, "v": item.negative_activation})

        request = proof.request()
        self.assertEqual(len(request["claims"]), 2)
        self.assertEqual([c["reverse"] for c in request["claims"]], [False, True])
        self.assertEqual([c["objective"] for c in request["claims"]],
                         ["NonIncreasing", "Equal"])
        for claim in request["claims"]:
            self.assertTrue(claim["input_integers"])
            self.assertTrue(claim["output_integers"])
            self.assertIsNone(claim["inverse"])
            self.assertEqual(claim["projection"], [[0, 0]])
            self.assertNotIn("input_objective_level", claim)
            self.assertNotIn("input_halfspace", claim)
        self.assertEqual(request["bijections"], [])
        # Both source activations may be one. The right branch sends this
        # feasible point from cost 2 to cost 1, so pointwise Equal/inverse or
        # a full LP equality is deliberately not part of this theorem.
        overlap = [1, 2, 1, 1, 1]
        self.assertEqual(source.check_point(overlap), [])
        self.assertEqual(target.check_point([1, 1]), [])
        self.assertEqual(source.objective.evaluate(overlap), 2)
        self.assertEqual(target.objective.evaluate([1, 1]), 1)

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            committed = target.write_mps(directory/"committed.mps")
            report = proof.verify(directory/"delivery", committed_model=committed)
            self.assertEqual(report["status"], "VERIFIED", report)
            self.assertEqual(report["artifact_audit"]["status"], "MATCHED")
            # Retaining Flow alone does not excuse a wrong omitted activation:
            # z=0 on the u=1 branch cannot satisfy both target capacity rows.
            broken = attack(
                proof, directory/"wrong_branch",
                ["blocks", 0, "end", "Split", "right", "end", "Return", "map", 1],
                replacement=Expr(0).to_json())
            self.assertTrue(broken["rejected_as_expected"], broken)


if __name__ == "__main__":
    unittest.main()
