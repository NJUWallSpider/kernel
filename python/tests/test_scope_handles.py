"""Native semantic extension handles: no author-side coordinate/row offsets."""
from fractions import Fraction
import tempfile
import unittest

from kernel_compiler import BuildError, Expr, Model, Proof, Row, Variable


class ScopeHandleTests(unittest.TestCase):
    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            result = proof.verify(directory)
            self.assertEqual(result["status"], "VERIFIED", result)

    def test_heterogeneous_intervals_and_branch_visibility(self):
        x = Expr.var(0)
        model = Model("intervals", [Variable("x", lower=0, upper=1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity", integers=False)
        upper_slack = claim.le([(claim.lower("x"), 1)], constant=-1)
        scope = claim.intervals([
            {"lower": [0, x-1], "upper": [x, x+1],
             "checks": [claim.lower("x"), upper_slack, "Exact", "Exact"]},
            {"lower": [-1], "upper": [1], "checks": ["Exact"]}])
        first, second = scope.interval(0), scope.interval(1)
        self.assertEqual([f.expression for f in first.lower_rows], [-first.variable, x-1-first.variable])
        self.assertEqual([f.expression for f in first.upper_rows], [first.variable-x, first.variable-x-1])
        self.assertEqual(second.lower_rows[0].expression, -1-second.variable)
        self.assertEqual(second.upper_rows[0].expression, second.variable-1)
        self.assertNotEqual(first.variable, second.variable)
        branch, _ = scope._branch(x)
        self.assertIs(branch.interval(0).lower_rows[0], first.lower_rows[0])
        with self.assertRaises(BuildError):
            claim.le([(first.lower_rows[0], 1)])
        for index in (-1, 2, True):
            with self.assertRaises(BuildError):
                scope.interval(index)
        with self.assertRaises(BuildError):
            scope.menu(0)
        claim.complete(scope=scope, mapping="identity")
        self.verify(proof)

    def test_menus_recover_a_real_reencoding_with_different_option_counts(self):
        i, j = Expr.var(0), Expr.var(1)
        source = Model("indices", [Variable("i", True, 0, 1), Variable("j", True, 0, 2)], objective=i+j)
        z0, z1, w0, w1, w2 = (Expr.var(k) for k in range(5))
        target = Model("options", [Variable(n, True, 0, 1) for n in ("z0", "z1", "w0", "w1", "w2")],
                       [Row("z_sum", z0+z1, 1, 1), Row("w_sum", w0+w1+w2, 1, 1)],
                       objective=z1+w1+2*w2)
        proof = Proof(source, target)
        forward = proof.claim(affine_projection=[(i, z1), (j, w1+2*w2)])
        reverse = proof.claim(reverse=True, mapping={"i": z1, "j": w1+2*w2},
                              affine_projection=[(z1, i), (w1+2*w2, j)])
        scope = forward.menus([
            {"maximum_index": maximum, "activation": 1, "index": source.var(name),
             "checks": ["Exact", "Exact", "Exact", forward.lower(name), forward.upper(name), forward.integer(name)]}
            for name, maximum in (("i", 1), ("j", 2))])
        first, second = scope.menu(0), scope.menu(1)
        self.assertEqual((len(first.options), len(second.options)), (2, 3))
        self.assertEqual(first.sum.expression, sum(first.options)-1)
        self.assertEqual(first.moment.expression, first.options[1]-i)
        self.assertEqual(second.sum.expression, sum(second.options)-1)
        self.assertEqual(second.moment.expression, second.options[1]+2*second.options[2]-j)
        scope.eq([(first.moment, 1), (second.moment, 1)])
        forward.complete(scope=scope, mapping=dict(zip((v.name for v in target.vars), (*first.options, *second.options))))
        reverse.le([(reverse.lower("w1"), 1), (reverse.lower("w2"), 2)])
        reverse.le([(reverse.row("w_sum"), 2), (reverse.lower("w0"), 2), (reverse.lower("w1"), 1)])
        reverse.complete()
        self.verify(proof)

    def test_signed_handles_name_each_component_and_law(self):
        flow, active = Expr.var(0), Expr.var(1)
        model = Model("signed", [Variable("f", False, -2, 2), Variable("z", True, 0, 1)],
                      [Row("positive", flow-2*active, upper=0), Row("negative", -flow-2*active, upper=0)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity")
        scope = claim.signed([
            {"capacity": 2, "flow": flow, "activation": active,
             "checks": [claim.lower("z"), claim.upper("z"), claim.integer("z"),
                        claim.row("positive"), claim.row("negative")]},
            {"capacity": 3, "flow": 0, "activation": 0, "checks": ["Exact"]*5}])
        for index, original_flow, original_activation, capacity in ((0, flow, active, 2), (1, Expr(0), Expr(0), 3)):
            item = scope.signed_decomposition(index)
            self.assertEqual(item.flow.expression, item.positive-item.negative-original_flow)
            self.assertEqual(item.activation.expression, item.positive_activation+item.negative_activation-original_activation)
            self.assertEqual(item.positive_capacity.expression, item.positive-capacity*item.positive_activation)
            self.assertEqual(item.negative_capacity.expression, item.negative-capacity*item.negative_activation)
            self.assertEqual((item.flow.kind, item.activation.kind, item.positive_capacity.kind), ("Eq", "Eq", "Le"))
        claim.complete(scope=scope, mapping="identity")
        self.verify(proof)

    def test_flow_groups_commodities_balances_and_recovery(self):
        f, g = Expr.var(0), Expr.var(1)
        model = Model("flow", [Variable("f", False, 2, 2), Variable("g", False, 1, 1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity", integers=False)
        groups = []
        for name, demand, commodities in (("f", 2, [(1, 1), (1, 1)]), ("g", 1, [(1, 1)])):
            expression = model.var(name)
            balance = claim.eq_on_fixed(expression-demand)
            groups.append({"source": 0, "commodities": commodities, "flows": [expression],
                           "nonnegative": [claim.le([(claim.lower(name), 1)], constant=-demand)],
                           "balances": [balance, claim.eq([(balance, -1)])]})
        scope = claim.flow({"nodes": 2, "arcs": [(0, 1)], "groups": groups})
        for group_index, original in ((0, f), (1, g)):
            group = scope.flow_group(group_index)
            self.assertEqual(group.source, 0)
            for commodity_index, item in enumerate(group.commodities):
                self.assertIs(scope.commodity(group_index, commodity_index), item)
                self.assertEqual(item.sink, 1)
                self.assertEqual(item.demand, Fraction(1))
                self.assertEqual([r.expression for r in item.balances], [item.flows[0]-1, 1-item.flows[0]])
            self.assertEqual(group.recovery[0].expression, sum(item.flows[0] for item in group.commodities)-original)
        with self.assertRaises(BuildError):
            scope.commodity(1, 1)
        claim.complete(scope=scope, mapping="identity")
        self.verify(proof)

    def test_subflow_handles_preserve_conservation_and_remainder(self):
        f, g = Expr.var(0), Expr.var(1)
        model = Model("subflow", [Variable("f", False, 2, 2), Variable("g", False, 1, 1)])
        proof = Proof(model, model)
        claim = proof.claim(mapping="identity", integers=False)
        balance = claim.eq_on_fixed(f-g-1)
        scope = claim.subflow({"nodes": 2, "arcs": [(0, 1), (1, 0)], "groups": [
            {"source": 0, "demands": [(1, 1)], "flows": [f, g],
             "nonnegative": [claim.le([(claim.lower("f"), 1)], constant=-2),
                             claim.le([(claim.lower("g"), 1)], constant=-1)],
             "balances": [balance, claim.eq([(balance, -1)])]}]})
        group = scope.subflow_group(0)
        a, b = group.flows
        self.assertEqual(group.source, 0)
        self.assertEqual([r.expression for r in group.balances], [a-b-1, b-a+1])
        self.assertEqual([r.expression for r in group.remainder_nonnegative], [a-f, b-g])
        self.assertTrue(all(r.kind == "Le" for r in group.remainder_nonnegative))
        claim.complete(scope=scope, mapping="identity")
        self.verify(proof)


if __name__ == "__main__":
    unittest.main()
