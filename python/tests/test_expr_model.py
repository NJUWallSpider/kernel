"""Exact algebra, edit audit, and real kernel readback regression checks."""
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from kernel_compiler.expr import Expr, exact, linear_sum
from kernel_compiler.model import Model, Row, Variable
from kernel_compiler.backend import Kernel


class ExpressionTests(unittest.TestCase):
    def test_exact_numbers_and_sparse_normalization(self):
        self.assertEqual(exact("1.2D-2"), Fraction(3, 250))
        self.assertEqual(exact("-3/-6"), Fraction(1, 2))
        expression = Expr("0.1", [(5, 2), (1, "1/3"), (5, -2), (1, "2/3")])
        self.assertEqual(expression.to_json(), {"constant": "1/10", "terms": [[1, "1"]]})
        self.assertEqual(Expr.from_json(expression.to_json()), expression)

    def test_affine_arithmetic_is_exact(self):
        x, y = Expr.var(0), Expr.var(1)
        expression = (x / 3 + 2 * y - "0.1") * 3
        self.assertEqual(expression, Expr("-3/10", {0: 1, 1: 6}))
        self.assertEqual(expression.evaluate(["3/10", 0]), 0)
        self.assertEqual(linear_sum([x, y, -x, "1/3"]), y + "1/3")
        self.assertEqual(sum([x, y]), x + y)
        self.assertEqual(2 - x, Expr(2, {0: -1}))

    def test_substitution_is_simultaneous_and_sparse(self):
        expression = Expr(1, {0: 2, 1: -2, 2: 1})
        # Replacing 0 by 1 and 1 by 0 swaps them; it does not recurse.
        self.assertEqual(expression.substitute({0: Expr.var(1), 1: Expr.var(0)}),
                         Expr(1, {0: -2, 1: 2, 2: 1}))
        self.assertEqual(expression.substitute([Expr.var(0), Expr.var(0), 3]), Expr(4))

    def test_floating_point_never_enters_an_expression(self):
        for construct in (lambda: exact(0.1), lambda: Expr(0.1), lambda: Expr(terms={0: 0.1}),
                          lambda: Expr.var(0) * 0.1, lambda: Expr.var(0) + 0.1,
                          lambda: Expr.var(0).evaluate([0.1]), lambda: Expr.var(0).substitute({0: 0.1})):
            with self.assertRaises(TypeError):
                construct()
        with self.assertRaises(TypeError):
            Expr.var(0) * Expr.var(1)

    def test_expression_is_immutable(self):
        expression = Expr.var(0)
        with self.assertRaises(TypeError):
            expression.terms[0] = Fraction(4)
        with self.assertRaises(AttributeError):
            expression._constant = Fraction(2)
        self.assertEqual(hash(expression), hash(Expr.var(0)))


class ModelTests(unittest.TestCase):
    def source(self):
        return Model("source", [Variable("x", True, 0, 1), Variable("y", True, 0, 1),
                                Variable("z", False, None, "3/2")],
                     [Row("alias", Expr(0, {0: 1, 1: -1}), 0, 0),
                      Row("ranged", Expr("1/5", {0: 2, 2: -1}), "-1/2", "3/4")],
                     Expr("-1/10", {0: 2, 1: 3, 2: "1/2"}))

    def test_model_readback_facts_honor_ranged_bounds_and_constants(self):
        model = self.source()
        self.assertEqual(model.fact("VarLower", "x"), ("Le", -model.var("x")))
        self.assertEqual(model.fact("VarUpper", 2), ("Le", model.var(2) - "3/2"))
        self.assertEqual(model.fact("VarInt", "y"), ("Int", model.var("y")))
        self.assertEqual(model.fact("RowLower", "ranged"), ("Le", "-1/2" - model.row("ranged").expr))
        self.assertEqual(model.fact("RowUpper", "ranged"), ("Le", model.row("ranged").expr - "3/4"))
        self.assertEqual(model.fact("RowEq", "alias"), ("Eq", model.var("x") - model.var("y")))
        self.assertEqual(model.ref("RowUpper", "ranged"), {"RowUpper": 1})
        for kind, name in [("VarLower", "z"), ("VarInt", "z"), ("RowEq", "ranged")]:
            with self.assertRaises(ValueError):
                model.fact(kind, name)

    def test_elimination_renumbers_every_expression_and_retains_bound(self):
        source = self.source()
        target = source.substitute({"y": source.var("x")}, drop_rows=["alias"])
        self.assertEqual([v.name for v in target.vars], ["x", "z"])
        self.assertEqual(target.objective, Expr("-1/10", {0: 5, 1: "1/2"}))
        self.assertEqual(target.row("ranged").expr, Expr("1/5", {0: 2, 1: -1}))
        bound = target.row("__bound_y")
        self.assertEqual((bound.expr, bound.lower, bound.upper), (target.var("x"), 0, 1))
        self.assertEqual(len(source.vars), 3)
        self.assertEqual([e.kind for e in target.ledger], ["DeleteRow", "EliminateVariable", "AddEliminatedBound"])
        json.dumps(target.ledger.to_json())

    def test_substitution_rejects_dangling_or_recursive_elimination(self):
        source = self.source()
        for replacements in ({"y": source.var("y")}, {"x": source.var("y"), "y": source.var("x")},
                             {"x": Expr.var(9)}):
            with self.assertRaises(ValueError):
                source.substitute(replacements)
        shifted = source.substitute({"x": source.var("x") + 1}, remove=False)
        self.assertEqual(shifted.row("alias").expr.constant, 1)

    def test_immutable_edit_chain_has_an_explicit_ledger(self):
        source = self.source()
        target = source.delete_rows("alias").with_bounds("z", lower="-3/2").with_integrality("y", False)
        target = target.add_variable("a", integer=True, upper=1)
        target = target.add_row("gate", target.var("a") - target.var("x"), upper=0)
        target = target.replace_row("ranged", lower=None, upper="1/2").with_objective(target.var("a"))
        self.assertEqual(len(source.rows), 2)
        self.assertEqual(len(target.ledger), 7)
        self.assertEqual(target.fact("RowUpper", "gate"), ("Le", target.var("a") - target.var("x")))
        self.assertFalse(target.vars[target.var_index["y"]].integer)
        self.assertEqual(target.vars[target.var_index["z"]].lower, Fraction(-3, 2))
        self.assertEqual({e.kind for e in source.diff(target)}, {"DeleteRow", "ChangeVariable", "AddVariable", "AddRow", "ChangeRow", "ChangeObjective"})

    def test_named_diff_does_not_mistake_renumbering_for_row_edit(self):
        before = Model("same", [Variable("unused"), Variable("x")], [Row("r", Expr.var(1), upper=1)], Expr.var(1))
        after = before.substitute({"unused": 0}, preserve_bounds=False)
        self.assertEqual([e.kind for e in before.diff(after)], ["DeleteVariable"])

    def test_scope_queries_and_exact_point_diagnostics(self):
        model = self.source()
        self.assertEqual(model.support("ranged", names=True), ("x", "z"))
        self.assertEqual(model.row_activity("ranged"), (Fraction(-13, 10), None))
        self.assertTrue(model.is_binary("x"))
        self.assertEqual(model.column_incidence()[1], ((0, Fraction(-1)),))
        self.assertEqual(model.stats()["ranged_rows"], 1)
        self.assertEqual(model.check_point({"x": 0, "y": 0, "z": 0}), [])
        violations = model.check_point(["1/2", "1/2", 0])
        self.assertEqual([v["kind"] for v in violations], ["VarInt", "VarInt", "RowUpper"])
        with self.assertRaises(TypeError):
            model.with_bounds("x", upper=0.3)
        with self.assertRaises(ValueError):
            model.check_point([0])

    def test_schema_duplicates_and_coordinates_are_rejected(self):
        for construct in (lambda: Model("m", [Variable("x"), Variable("x")]),
                          lambda: Model("m", [Variable("x")], [Row("r", Expr.var(1))]),
                          lambda: Model.from_json({"name": "m", "unexpected": 3}),
                          lambda: Model("m", [Variable("x", integer=1)])):
            with self.assertRaises((ValueError, TypeError)):
                construct()

    def test_nonterminating_mps_numbers_are_explicit(self):
        model = Model("rational", [Variable("x")], objective=Expr("1/3", {0: "2/7"}))
        with self.assertRaisesRegex(ValueError, "no finite exact decimal"):
            model.to_mps()
        self.assertIn("2/7", model.to_mps(rational_literals=True))


class KernelModelRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.kernel = Kernel()
        except FileNotFoundError as error:
            raise unittest.SkipTest(str(error))

    def test_direct_mcm_preserves_all_fields_and_bytes(self):
        model = Model("direct", [Variable("x", True, "-1/3", 1), Variable("free", False, None, None)],
                      [Row("contradictory", Expr("2/7", {0: "3/11", 1: -2}), 4, 2),
                       Row("no_sides", Expr.var(1))], Expr("-5/3", {1: "1/17"}))
        with tempfile.TemporaryDirectory() as directory:
            path = model.write_mcm(Path(directory) / "direct.mcm")
            loaded = Model.load(path, self.kernel)
            self.assertEqual(loaded.to_json(), model.to_json())
            self.assertEqual(loaded.to_mcm(), path.read_bytes())

    def test_free_mps_preserves_bounds_integrality_ranges_and_objective(self):
        model = Model("mps_roundtrip", [Variable("binary", True, 0, 1), Variable("continuous", False, None, 2),
                                        Variable("integer", True, -2, None), Variable("fixed", False, "1/5", "1/5"),
                                        Variable("free", False, None, None)],
                      [Row("range", Expr(0, {0: 1, 1: "-1/2"}), "-1/5", "3/10"),
                       Row("equality", Expr.var(2), 1, 1), Row("lower", Expr.var(3), lower="1/5")],
                      Expr("-1/10", {0: 3, 1: "1/4"}))
        with tempfile.TemporaryDirectory() as directory:
            path = model.write_mps(Path(directory) / "model.mps")
            self.assertEqual(Model.load(path, self.kernel).to_json(), model.to_json())

    def test_mps_folds_row_constants_exactly(self):
        model = Model("constants", [Variable("x")], [Row("row", Expr("1/3", {0: 2}), lower="-2/3", upper="5/3")])
        with tempfile.TemporaryDirectory() as directory:
            path = model.write_mps(Path(directory) / "model.mps", rational_literals=True)
            loaded = Model.load(path, self.kernel)
            self.assertEqual(loaded.fact("RowLower", "row"), model.fact("RowLower", "row"))
            self.assertEqual(loaded.fact("RowUpper", "row"), model.fact("RowUpper", "row"))


if __name__ == "__main__":
    unittest.main()
