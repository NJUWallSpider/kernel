import array
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from rpx import *
from rpx.lowlevel import affine


class Models(unittest.TestCase):
    def model(self, n=3):
        b = ModelBuilder("model")
        for i in range(n):
            b.add_var(f"x{i}", integer=True, lower=0, upper=5)
        return b.build()

    def test_integer_buffer_expression_paths(self):
        m = self.model()
        indices = array.array("I", [0, 1, 2, 0])
        values = array.array("q", [1, -2, 3, 4])
        e = Expr.from_terms(m, indices, values, constant="1/7")
        self.assertEqual(e, Q(1, 7) + 5 * m.vars[0] - 2 * m.vars[1] + 3 * m.vars[2])
        self.assertEqual(
            Expr.dot(array.array("q", [1, 2, 3]), m.vars),
            m.vars[0] + 2 * m.vars[1] + 3 * m.vars[2],
        )
        self.assertEqual(
            Expr.dot(memoryview(array.array("q", [1, 99, 2, 99, 3]))[::2], m.vars),
            m.vars[0] + 2 * m.vars[1] + 3 * m.vars[2],
        )

    def test_float_and_bool_buffers_rejected(self):
        m = self.model()
        for values in [
            array.array("d", [1, 2, 3]),
            memoryview(bytes([0, 1, 0])).cast("?"),
        ]:
            with self.assertRaises(TypeError):
                Expr.dot(values, m.vars)
        with self.assertRaises(TypeError):
            Expr.from_terms(m, [True], [1])

    def test_bulk_arity_and_coordinate_validation(self):
        m = self.model()
        for call in [
            lambda: Expr.dot([1], m.vars),
            lambda: Expr.dot([1] * 4, m.vars),
            lambda: Expr.from_terms(m, [0, 1], [1]),
            lambda: Expr.from_terms(m, [-1], [1]),
            lambda: Expr.from_terms(m, [3], [1]),
        ]:
            with self.assertRaises((TypeError, IndexError, OverflowError)):
                call()

    def test_default_map_and_views_have_bounded_python_allocation(self):
        m = self.model(10000)
        p = Proof(m, m)
        tracemalloc.start()
        tracemalloc.reset_peak()
        variables = m.vars
        rows = m.rows
        p.forward.map(default="same_name")
        view = p.forward.mapping
        goals = p.forward.plan()
        total = quicksum(variables)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak, 100_000)
        self.assertEqual(len(view), 10000)
        self.assertEqual(len(total.terms), 10000)
        self.assertEqual(goals.count, 30001)
        self.assertLess(len(repr(m)), 1000)
        self.assertLess(len(repr(goals)), 5000)

    def test_bounds_clear_and_preserve(self):
        m = self.model()
        t = m.with_bounds("x0", lower=None)
        self.assertIsNone(t.vars["x0"].lower)
        self.assertEqual(t.vars["x0"].upper, 5)
        self.assertEqual(m.vars["x0"].lower, 0)
        with self.assertRaises(TypeError):
            m.with_bounds("x0", typo=1)

    def test_row_replace_clear_bounds_and_space(self):
        m = self.model()
        m = m.add_row("r", m.vars["x0"], lower=0, upper=3)
        t = m.replace_row("r", lower=None, upper=4)
        self.assertIsNone(t.rows["r"].lower)
        self.assertEqual(t.rows["r"].upper, 4)
        with self.assertRaises(CoordinateSpaceError):
            t.replace_row("r", expression=m.vars["x0"])

    def test_expression_evaluation_and_point_violations(self):
        m = self.model()
        e = m.vars["x0"] + 2 * m.vars["x1"]
        self.assertEqual(e.evaluate({"x0": 1, "x1": 2}), 5)
        self.assertEqual(e.evaluate([1, 2, 0]), 5)
        self.assertEqual(m.check_point(array.array("i", [1, 2, 3])), [])
        self.assertEqual(
            m.check_point({"x0": 1, "x1": 2, "x2": 6})[0]["kind"], "VarUpper"
        )
        self.assertEqual(m.check_point([Q(1, 2), 0, 0])[0]["kind"], "VarInt")
        self.assertEqual(m.check_point([Q(1, 2), 0, 0], integers=False), [])

    def test_duplicate_and_invalid_model_inputs(self):
        b = ModelBuilder()
        x = b.add_var("x")
        with self.assertRaises(KeyError):
            b.add_var("x")
        b.add_row("r", x, upper=0)
        with self.assertRaises(KeyError):
            b.add_row("r", x, upper=0)
        with self.assertRaises(TypeError):
            b.add_row("bad", x, equal=0, upper=0)
        m = b.build()
        with self.assertRaises(IndexError):
            m.vars[8]
        with self.assertRaises(KeyError):
            m.rows["missing"]

    def test_substitution_keeps_only_removed_bounds_and_fresh_names(self):
        b = ModelBuilder()
        x = b.add_var("x", lower=0, upper=1)
        y = b.add_var("y", lower=0, upper=2)
        b.add_row("__bound_y", x, upper=1)
        m = b.build()
        t = m.substitute({"y": 2 * x})
        self.assertEqual(len(t.rows), 2)
        self.assertEqual(len({r.name for r in t.rows}), 2)
        self.assertEqual(len(t.vars), 1)

    def test_substitution_rejects_cycles_and_foreign_values(self):
        m = self.model()
        other = self.model()
        for replacements in [
            {"x0": m.vars["x0"]},
            {"x0": m.vars["x1"], "x1": m.vars["x0"]},
        ]:
            with self.assertRaises(CompilerError):
                m.substitute(replacements)
        with self.assertRaises(CoordinateSpaceError):
            m.substitute({"x0": other.vars["x0"]})

    def test_native_activity_and_support(self):
        m = self.model()
        m = m.add_row("row", m.vars["x0"] - 2 * m.vars["x1"] + 1, upper=4)
        self.assertEqual(m.row_activity("row"), (-9, 6))
        self.assertEqual(m.support("row"), [0, 1])

    def test_standard_mps_adapter_rational_matrix_bounds_objective(self):
        b = ModelBuilder("rational")
        x = b.add_var("x", lower="1/3", upper="1/3")
        z = b.add_var("z", integer=True, lower=0, upper=1)
        b.add_row("range", x / 6 + z / 4 + Q(1, 3), lower="1/5", upper="2/3")
        b.add_row("eq", x / 7 - z / 3, equal="1/21")
        b.minimize(x / 7 + z / 3 - Q(1, 7))
        m = b.build()
        a = StandardMPSAdapter(m)
        with tempfile.TemporaryDirectory() as d:
            target = a.target.write_mps(Path(d) / "target.mps")
            self.assertTrue(a.target.same_formulation(Model.read(target)))
            p = a.proof()
            self.assertEqual(
                p.verify(Path(d) / "bundle", target_artifact=target).status, "VERIFIED"
            )
        self.assertEqual(m.vars["x"].lower, Q(1, 3))
        self.assertGreater(len(a.target.vars), len(m.vars))

    def test_standard_adapter_decimal_has_no_extra_variable(self):
        m = self.model()
        a = StandardMPSAdapter(m)
        self.assertEqual(len(a.target.vars), len(m.vars))
        self.assertTrue(m.same_formulation(a.target))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(a.proof().verify(Path(d) / "b").status, "VERIFIED")

    def test_adapter_requires_objective_auxiliary_for_nondecimal(self):
        m = self.model()
        m = m.with_objective(m.vars[0] / 3)
        with self.assertRaises(CompilerError):
            StandardMPSAdapter(m, objective_auxiliary=False)

    def test_adapter_report_is_a_copy(self):
        m = self.model()
        a = StandardMPSAdapter(m)
        first = a.report
        first.clear()
        self.assertIn("before", a.report)

    def test_wide_exact_model_and_codec_budgets(self):
        b = ModelBuilder("wide")
        x = b.add_var("x")
        b.add_row("wide", (1 << 13000) * x, equal=0)
        m = b.build()
        with tempfile.TemporaryDirectory() as d:
            path = m.write_mcm(Path(d) / "model.mcm")
            self.assertTrue(m.same_formulation(Model.read(path)))
        p = Proof(m, m)
        p.forward.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(p.verify(Path(d) / "bundle").status, "VERIFIED")

    def test_empty_models_and_exact_return(self):
        m = ModelBuilder("empty").build()
        p = Proof(m, m)
        p.forward.map({}).finish()
        p.reverse.map({}).finish()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(p.verify(Path(d) / "bundle").status, "VERIFIED")

    def test_foreign_model_accepted_only_by_explicit_substitution(self):
        m = self.model()
        t = self.model()
        e = m.vars[0] + m.vars[1]
        with self.assertRaises(CoordinateSpaceError):
            e.substitute({0: t.vars[0]})
        self.assertEqual(
            e.substitute({0: t.vars[0], 1: t.vars[1]}), t.vars[0] + t.vars[1]
        )

    def test_stale_mapping_and_obligation_views(self):
        m = self.model()
        s = Proof(m, m).forward.map(default="same_name")
        mapping = s.mapping
        goals = s.plan()
        s.map(default="same_name")
        for call in [
            lambda: mapping[0],
            lambda: len(mapping),
            lambda: goals[0],
            lambda: goals.summary(),
            lambda: repr(goals),
        ]:
            with self.assertRaises(ScopeError):
                call()
