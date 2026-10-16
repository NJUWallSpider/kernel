from rule_checks import assert_rules_checked
"""Builder scope, lookup, and explicit proof-template regression checks."""
import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Contradiction, Expr, Model, Proof, Row, Variable


class BuilderSafetyTests(unittest.TestCase):
    def binary(self):
        return Model("binary", [Variable("x", integer=True, lower=0, upper=1)])

    def test_dropped_duplicate_falls_back_to_a_live_fact(self):
        builder = Builder(self.binary())
        first = builder.le([(builder.upper("x"), 2)])
        second = builder.le([(first, 1)])
        builder.drop(second)
        self.assertIs(builder.find("Le", first.expression), first)
        self.assertNotIn(second.reference["Local"], builder._facts.maps[0])

    def test_child_drop_shadow_preserves_parent_and_sibling(self):
        builder = Builder(self.binary())
        parent = builder.le([(builder.upper("x"), 2)])
        child, _ = builder._branch(-builder.model.var("x"))
        child_fact = child.le([(parent, 1)])
        child.drop(child_fact)
        self.assertIs(child.find("Le", parent.expression), parent)
        child.drop(parent)
        self.assertIsNone(child.find("Le", parent.expression))
        self.assertIs(builder.find("Le", parent.expression), parent)
        sibling, _ = builder._branch(-builder.model.var("x"))
        self.assertIs(sibling.find("Le", parent.expression), parent)

    def test_branch_assumptions_and_base_index_are_reused(self):
        builder = Builder(self.binary())
        child, assumption = builder._branch(builder.model.var("x"))
        self.assertIs(child.find("Le", assumption.expression), assumption)
        self.assertTrue(builder._indexed)
        self.assertEqual(child._base, {})
        self.assertIs(child.upper("x"), builder.upper("x"))
        nested, nested_assumption = child._branch(-builder.model.var("x"))
        self.assertIs(nested.find("Le", nested_assumption.expression), nested_assumption)
        self.assertIs(nested.find("Le", assumption.expression), assumption)

    def test_failed_drop_is_atomic(self):
        builder = Builder(self.binary())
        fact = builder.le([(builder.upper("x"), 2)])
        before = len(builder.steps)
        with self.assertRaises(BuildError):
            builder.drop(fact, fact)
        self.assertEqual(len(builder.steps), before)
        self.assertIs(builder.find("Le", fact.expression), fact)
        with self.assertRaises(BuildError):
            builder.drop(fact, builder.upper("x"))
        self.assertIs(builder.find("Le", fact.expression), fact)

    def test_cases_rejects_a_forged_contradiction_wrapper(self):
        builder = Builder(self.binary())
        x = builder.model.var("x")
        with self.assertRaisesRegex(BuildError, "Absurd requires"):
            builder.cases(x, kind="Le", expect=x,
                          left=lambda b, s: Contradiction(s), right=lambda b, s: s)

    def test_kind_rules_match_kernel_and_reject_before_building(self):
        builder = Builder(Model("zero", [Variable("x")], [Row("zero", Expr.var(0), 0, 0)]))
        zero = builder.row("zero")
        self.assertEqual(builder.int([(zero, "1/2")]).expression, Expr.var(0) / 2)
        for kind, constant in [("Eq", -1), ("Le", 1), ("Int", "1/2"), ("Unknown", 0)]:
            before = len(builder.steps)
            with self.assertRaises(BuildError):
                builder.lin(kind, constant=constant)
            self.assertEqual(len(builder.steps), before)
        with self.assertRaisesRegex(BuildError, "outside this scope"):
            builder.find("Int", Expr.var(9))
        with self.assertRaises(BuildError):
            builder.le([(builder.lower("x"), -1)])

    def test_continuous_split_false_shorthand(self):
        builder = Builder(Model("continuous", [Variable("x")]))
        expression, integer = builder._split(Expr.var(0), False)
        self.assertEqual(expression, Expr.var(0))
        self.assertIsNone(integer)

    def test_plotkin_rejects_domains_labels_and_missing_cliques(self):
        model = Model("pair", [Variable("x", True, 0, 1), Variable("y", True, 0, 1)])
        builder = Builder(model)
        for variables, cliques in [([(0, 0), (0, 1)], []), ([(0, 4)], []), ([(0, 0), (1, 0)], [])]:
            with self.assertRaises(BuildError):
                builder.plotkin(bits=2, distance=2, variables=variables, cliques=cliques)
        with self.assertRaises(BuildError):
            Builder(Model("continuous", [Variable(v.name, False, v.lower, v.upper) for v in model.vars], model.rows, model.objective)).plotkin(bits=2, distance=2, variables=[(0, 0)], cliques=[])

    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))

    def test_explicit_fixed_equality_template_verifies(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("fixed", [Variable("x", lower=0, upper=1), Variable("y", lower=2, upper=2)],
                       [Row("xfix", 3*x, lower=1, upper=1)])
        goal = 3*x + 2*y - 5
        target = source.add_row("derived", goal, equal=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        forward.eq_on_fixed(goal, {"x": forward.row("xfix")})
        forward.complete()
        reverse.complete()
        self.verify(proof)
        invalid = Builder(source)
        with self.assertRaisesRegex(BuildError, "nonzero exact residual"):
            invalid.eq_on_fixed(goal+1, {"x": invalid.row("xfix")})
        self.assertEqual(invalid.steps, [])

    def test_caller_selected_row_combination_verifies(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("rows", [Variable("x", lower=None), Variable("y", lower=None)],
                       [Row("a", x+y, lower=1), Row("b", y, upper=3)])
        target = source.add_row("derived", x, lower=-2)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        forward.combine_rows("Le", {"a": 1, ("b", "Upper"): 1}, expect=-x-2)
        forward.complete()
        reverse.complete()
        self.verify(proof)

    def test_plotkin_handles_generator_inputs_and_verifies(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("plotkin", [Variable("x", True, 0, 1), Variable("y", True, 0, 1)],
                       [Row("clique", x+y, upper=1)])
        target = source.add_row("cut", x+y, upper=2)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map("identity"), proof.reverse.map("identity"))
        forward.plotkin(bits=2, distance=2, variables=((i, 0) for i in (0, 1)),
                        cliques=(forward.row("clique") for _ in range(1)))
        forward.complete()
        reverse.complete()
        self.verify(proof)


if __name__ == "__main__":
    unittest.main()
