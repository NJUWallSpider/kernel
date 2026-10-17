from rule_checks import assert_rules_checked
"""Caller-selected subset inequalities share ordinary, scope-safe Lin proofs."""
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable, attack


class SubsetBoundsTests(unittest.TestCase):
    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            result = proof.verify(directory)
            assert_rules_checked(self, result)
            self.assertTrue((Path(directory) / "proof.rpa").is_file())
            return result

    def test_weighted_signed_rational_bounds_and_native_tampering(self):
        x, y, z = (Expr.var(i) for i in range(3))
        root = 3*x-2*y+z/3-8
        source = Model("weighted", [Variable("x", True, 1, 5),
                       Variable("y", True, -3, 4), Variable("z", False, -2, 3)],
                       [Row("given", root, upper=0)], objective=x+y+z)
        subsets = [["x", "y", "z"], ["x"], ["y"], ["z"], [], ["x", "z"], [0, 0]]
        expected = [root, 3*x-Expr("50/3"), -2*y-Expr("17/3"),
                    z/3-13, Expr("-41/3"), 3*x+z/3-16, 3*x-Expr("50/3")]
        target = source
        for index, expression in enumerate(expected[1:-1]):
            target = target.add_row(f"derived{index}", expression, upper=0)
        for integers in (True, False):
            proof = Proof(source, target)
            forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
            facts = forward.subset_bounds(forward.row("given"), iter(subsets))
            self.assertEqual([fact.expression for fact in facts], expected)
            self.assertTrue(all(fact.kind == "Le" for fact in facts))
            self.assertIs(facts[1], facts[-1])
            self.assertEqual({next(iter(step)) for step in forward.steps}, {"Lin"})
            forward.complete(); reverse.complete()
            with tempfile.TemporaryDirectory() as directory:
                assert_rules_checked(self, proof.verify(directory))
                broken = attack(proof, Path(directory)/"attack",
                                ["forward", "steps", 0, "Lin", "terms", 1, 1],
                                replacement="0")
                self.assertTrue(broken["rejected_as_expected"], broken)

    def test_retained_unbounded_coordinate_needs_no_endpoint(self):
        x, y = Expr.var(0), Expr.var(1)
        model = Model("free_kept", [Variable("x", lower=None), Variable("y", lower=2)],
                      [Row("given", x+3*y, upper=10)])
        builder = Builder(model)
        result, = builder.subset_bounds(builder.row("given"), [[x]])
        self.assertEqual(result.expression, x-4)
        self.assertEqual(builder.subset_bounds(builder.row("given"), []), [])
        before = list(builder.steps)
        with self.assertRaisesRegex(BuildError, "lower bound.*x"):
            builder.subset_bounds(builder.row("given"), [[x], []])
        self.assertEqual(builder.steps, before)

    def test_invalid_subsets_kinds_and_missing_upper_are_preflighted(self):
        x, y = Expr.var(0), Expr.var(1)
        model = Model("invalid", [Variable("x", True), Variable("y", upper=None)],
                      [Row("one", x, upper=1), Row("negative", x-y, upper=1)])
        builder = Builder(model)
        for fact, subsets in [(builder.row("one"), [["x"], ["y"]]),
                              (builder.row("negative"), [["y"], ["x"]]),
                              (builder.integer("x"), [[]]),
                              (builder.row("one"), ["x"])]:
            with self.subTest(subsets=subsets), self.assertRaises(BuildError):
                builder.subset_bounds(fact, subsets)
            self.assertEqual(builder.steps, [])

    def test_eq_input_and_inconsistent_domain_do_not_claim_existence(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("empty_domain", [Variable("x", lower=1), Variable("y")],
                       [Row("given", x+2*y, 0, 0)])
        target = source.add_row("impossible", Expr(1), upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        full, empty = forward.subset_bounds(forward.row("given"), [[0, 1], []])
        self.assertEqual((full.kind, full.expression), ("Le", x+2*y))
        self.assertEqual((empty.kind, empty.expression), ("Le", Expr(1)))
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_dropped_subset_and_cached_bound_sum_rebuild_safely(self):
        n = 32
        total = Expr(0, {i: 1 for i in range(n)})
        source = Model("drop_cache", [Variable(f"x{i}", lower=0, upper=1) for i in range(n)],
                       [Row("given", total, upper=1)])
        target = source.add_row("subset", Expr(-1, {i: 1 for i in range(8)}), upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        first, = forward.subset_bounds(forward.row("given"), [range(16)])
        before = len(forward.steps)
        again, = forward.subset_bounds(forward.row("given"), [range(16)])
        self.assertIs(first, again)
        self.assertEqual(len(forward.steps), before)
        chunk = forward.find("Le", Expr(0, {i: -1 for i in range(16, 32)}))
        self.assertIsNotNone(chunk)
        forward.drop(chunk, first)
        rebuilt, = forward.subset_bounds(forward.row("given"), [range(8)])
        self.assertEqual(rebuilt.expression, target.rows[-1].expr)
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_sibling_unrelated_and_shadow_dropped_premises_are_rejected(self):
        x, y = Expr.var(0), Expr.var(1)
        model = Model("scope", [Variable("x"), Variable("y")],
                      [Row("given", x+y, upper=1)])
        builder = Builder(model)
        root = builder.le([(builder.row("given"), 1)])
        left, _ = builder._branch(x)
        right, _ = builder._branch(-x)
        local, = left.subset_bounds(root, [[0]])
        for invalid in (local, Builder(model).row("given")):
            with self.assertRaises(BuildError):
                right.subset_bounds(invalid, [[]])
        left.drop(root)
        with self.assertRaises(BuildError):
            left.subset_bounds(root, [[0]])
        self.assertEqual(right.subset_bounds(root, [[0]])[0].expression, x-1)
        self.assertEqual(builder.subset_bounds(root, [[0]])[0].expression, x-1)

    def test_sparse_cancellation_does_not_touch_unbounded_holes(self):
        support = [0, 1, 2, 3, 4, 6, 8]
        source = Model("sparse", [Variable(f"x{i}", lower=0 if i in support else None)
                       for i in range(10)],
                       [Row("given", Expr(0, {i: 1 for i in support}), upper=2)])
        selected = Expr(-2, {6: 1, 8: 1})
        target = source.add_row("selected", selected, upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        first, empty = forward.subset_bounds(forward.row("given"), [[6, 8], []])
        self.assertEqual(first.expression, selected)
        self.assertEqual(empty.expression, Expr(-2))
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_generated_scope_retains_an_unbounded_declared_coordinate(self):
        source = Model("original", [Variable("x", lower=0, upper=1),
                       Variable("y", lower=None, upper=2)], objective=Expr.var(0))
        target = Model("projected", [Variable("x", lower=0, upper=1)], objective=Expr.var(0))
        proof = Proof(source, target)
        forward, reverse = proof.forward.map({"x": source.var("x")}), proof.reverse
        forward.complete()
        scope = reverse.intervals([{"lower": [Expr(0)], "upper": [reverse.model.var("x")],
                                    "checks": [reverse.lower("x")]}])
        handle = scope.interval(0)
        z = handle.variable
        self.assertIsNone(scope.model.vars[next(iter(z.terms))].lower)
        x = scope.model.var("x")
        given = scope.le([(handle.upper_rows[0], 1), (scope.upper("x"), 2)], expect=x+z-2)
        result, = scope.subset_bounds(given, [[z]])
        self.assertEqual(result.expression, z-2)
        reverse.complete(scope=scope, mapping={"x": x, "y": z})
        self.verify(proof)

    def test_equal_expressions_from_distinct_premises_keep_separate_results(self):
        x, y = Expr.var(0), Expr.var(1)
        builder = Builder(Model("premises", [Variable("x"), Variable("y")],
                                [Row("given", x+y, upper=1)]))
        first_root = builder.le([(builder.row("given"), 1)])
        second_root = builder.le([(first_root, 1)])
        first, = builder.subset_bounds(first_root, [[0]])
        second, = builder.subset_bounds(second_root, [[0]])
        self.assertIsNot(first, second)
        self.assertEqual(first.expression, second.expression)
        builder.drop(first_root)
        self.assertIs(builder.subset_bounds(second_root, [[0]])[0], second)
        with self.assertRaises(BuildError):
            builder.subset_bounds(first_root, [[0]])

    def test_overlapping_supplied_subsets_compress_linear_references(self):
        n = 1024
        source = Model("overlap", [Variable(f"x{i}", lower=0, upper=1) for i in range(n)],
                       [Row("given", Expr(0, {i: 1 for i in range(n)}), upper=1)])
        target = source
        for k in range(1, 257):
            target = target.add_row(f"prefix{k}", Expr(-1, {i: 1 for i in range(k)}), upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        facts = forward.subset_bounds(forward.row("given"), (range(k) for k in range(1, 257)))
        self.assertEqual(facts[0].expression, Expr.var(0)-1)
        self.assertEqual(facts[-1].expression, Expr(-1, {i: 1 for i in range(256)}))
        references = sum(len(step["Lin"]["terms"]) for step in forward.steps)
        naive_references = sum(1+n-k for k in range(1, 257))
        self.assertLess(references, 8*n)
        self.assertLess(references*20, naive_references)
        forward.complete(); reverse.complete()
        self.verify(proof)


if __name__ == "__main__":
    unittest.main()
