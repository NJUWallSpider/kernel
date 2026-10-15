"""Small exact decimal adapters, verified with the real frozen Kernel."""
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import (BuildError, Expr, Model, Proof, Row, StandardMPSAdapter,
                             Variable, verify_bundle, write_chain)


class StandardMPSAdapterTests(unittest.TestCase):
    def verify(self, adapter, directory):
        directory = Path(directory)
        mps = adapter.target.write_mps(directory / "target.mps")
        with Model.load(mps) as parsed:
            self.assertTrue(adapter.target.same_formulation(parsed))
        proof = adapter.proof()
        try:
            result = proof.verify(directory / "proof", committed_model=mps)
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
            self.assertEqual(len(proof.claims), 4)
            self.assertEqual([(c.claim["reverse"], c.claim["input_integers"],
                               c.claim["output_integers"], c.claim["objective"], c.claim["inverse"])
                              for c in proof.claims],
                             [(False, True, True, "Equal", 1), (True, True, True, "Equal", 0),
                              (False, False, False, "Equal", 3), (True, False, False, "Equal", 2)])
            return proof.certificate()
        finally:
            proof.close()

    def test_ranged_and_equality_rows_fixed_bounds_and_negative_objective(self):
        source = Model("rational", [Variable("x", False, "1/3", "1/3"),
                                   Variable("b", True, 0, 1), Variable("z", False, None, "1/6")],
                       [Row("ranged", Expr("1/3", {0: "1/6", 1: "1/4"}), "1/5", "2/3"),
                        Row("equality", Expr(terms={0: "1/7", 1: "-1/3"}), "1/21", "1/21"),
                        Row("cancelled_constant", Expr("1/3", {2: "1/2"}), upper="5/6")],
                       Expr("-1/7", {0: "1/7", 1: "1/3", 2: "1/2"}))
        original = source.to_json()
        adapter = source.standard_mps_adapter()
        self.assertIsInstance(adapter, StandardMPSAdapter)
        self.assertIs(adapter.source, source)
        self.assertEqual(source.to_json(), original)
        self.assertEqual([v.name for v in adapter.target.vars[:3]], ["x", "b", "z"])
        report = adapter.report
        json.dumps(report)
        self.assertEqual(report["row_scales"], [{"row": "ranged", "scale": "3"},
                                               {"row": "equality", "scale": "21"}])
        self.assertEqual([r.expr.constant for r in adapter.target.rows], [0]*len(adapter.target.rows))
        self.assertIsNone(adapter.target.vars[0].lower)
        self.assertIsNone(adapter.target.vars[0].upper)
        self.assertEqual([m["side"] for m in report["bound_moves"]], ["lower", "upper", "upper"])
        for move in report["bound_moves"]:
            self.assertFalse(adapter.target.row(move["row"]).equality)
        auxiliary = adapter.target.vars[-1]
        self.assertEqual((auxiliary.integer, auxiliary.lower, auxiliary.upper), (False, None, None))
        point = [Fraction(1, 3), 0, 0]
        cost = source.objective.evaluate(point)
        self.assertLess(cost, 0)
        self.assertEqual(source.check_point(point), [])
        self.assertEqual(adapter.target.check_point([*point, cost]), [])
        self.assertEqual(adapter.target.objective.evaluate([*point, cost]), cost)
        self.assertEqual(report["added"], {"variables": 1, "rows": 4, "nonzeros": 7})
        self.assertEqual(report["coefficient_stats"]["source"], source.coefficient_stats())
        self.assertEqual(report["coefficient_stats"]["target"], adapter.target.coefficient_stats())
        # Metadata cannot modify the plan used for certificate construction.
        report["row_scales"].clear()
        self.assertEqual(len(adapter.report["row_scales"]), 2)
        with self.assertRaises(AttributeError):
            adapter.target = source
        with tempfile.TemporaryDirectory() as directory:
            certificate = self.verify(adapter, directory)
        self.assertTrue(all(set(step) == {"Lin"} for block in certificate["blocks"] for step in block["steps"]))

    def test_objective_only_and_constant_only_use_exact_free_continuous_value(self):
        models = [Model("objective", [Variable("x", True, 0, 1)], objective=Expr.var(0)/3),
                  Model("negative_constant", objective=Expr("-2/7")),
                  Model("positive_constant", objective=Expr("2/7"))]
        for source in models:
            with self.subTest(name=source.name), tempfile.TemporaryDirectory() as directory:
                adapter = source.standard_mps_adapter()
                self.assertEqual(len(adapter.target.vars), len(source.vars)+1)
                self.assertEqual(adapter.target.objective, Expr.var(len(source.vars)))
                self.assertTrue(adapter.target.rows[-1].equality)
                self.verify(adapter, directory)

    def test_finite_and_zero_objectives_need_no_auxiliary_or_redundant_lin(self):
        models = [Model("no_op", [Variable("x", True, 0, 1)],
                        [Row("upper", Expr.var(0), upper="1/2")], Expr("1/10", {0: "1/2"})),
                  Model("zero", [Variable("x", False, None, None)], objective=0),
                  Model("fold", [Variable("x", False, None, None)],
                        [Row("fold", Expr("1/3", {0: "1/2"}), upper="5/6")], objective=0)]
        for source in models:
            with self.subTest(name=source.name), tempfile.TemporaryDirectory() as directory:
                adapter = source.standard_mps_adapter(objective_auxiliary=False)
                self.assertIsNone(adapter.report["objective_auxiliary"])
                self.assertEqual(adapter.report["row_scales"], [])
                self.assertEqual(adapter.report["added"], {"variables": 0, "rows": 0, "nonzeros": 0})
                self.assertTrue(source.same_formulation(adapter.target))
                certificate = self.verify(adapter, directory)
                self.assertEqual([block["steps"] for block in certificate["blocks"]], [[], [], [], []])

    def test_disabled_objective_and_generated_name_collisions(self):
        source = Model("names", [Variable("__mps_objective", False, "1/3", 1),
                                 Variable("__mps_objective_1", True, 0, 1)],
                       [Row("__mps_bound_0_lower", Expr(), upper=0),
                        Row("__mps_objective_2_definition", Expr(), upper=0)], Expr.var(0)/3)
        before = source.to_json()
        with self.assertRaisesRegex(BuildError, "enable objective_auxiliary"):
            source.standard_mps_adapter(objective_auxiliary=False)
        adapter = source.standard_mps_adapter()
        self.assertEqual(source.to_json(), before)
        self.assertEqual(adapter.target.vars[-1].name, "__mps_objective_2")
        self.assertEqual(adapter.report["bound_moves"][0]["row"], "__mps_bound_0_lower_1")
        self.assertEqual(adapter.report["objective_auxiliary"]["definition_row"], "__mps_objective_2_definition_1")
        with tempfile.TemporaryDirectory() as directory:
            self.verify(adapter, directory)
        with self.assertRaises(TypeError):
            source.standard_mps_adapter(objective_auxiliary=1)
        with self.assertRaises(TypeError):
            Model("float", [Variable("x", upper=0.1)])

    def test_resource_and_unsupported_format_failures_are_not_approximated(self):
        # Small in-memory scalars exercise actual limits without a large model.
        source = Model("scale_text", [Variable("x")],
                       [Row("too_long_scale", Expr(terms={0: Fraction(1, 3**9000)}), upper=1)])
        with self.assertRaisesRegex(BuildError, "RESOURCE_LIMIT.*13600.*RPX"):
            source.standard_mps_adapter()
        # Every individual input denominator fits RPX; their LCM exceeds the
        # separate intermediate rational bound even when proof chunks fit.
        primes = (3, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61)
        source = Model("scale_bits", [Variable(f"x{i}") for i in range(len(primes))],
                       [Row("too_large_lcm", Expr(terms={i: Fraction(1, p**1024)
                                                         for i, p in enumerate(primes)}), upper=1)])
        with self.assertRaisesRegex(BuildError, "RESOURCE_LIMIT.*65536"):
            source.standard_mps_adapter()
        source = Model("mps_text", [Variable("x")], objective=Expr(terms={0: 10**4096}))
        with self.assertRaisesRegex(BuildError, "RESOURCE_LIMIT.*decimal digit"):
            source.standard_mps_adapter()
        for source in (Model("bad name", [Variable("x")]),
                       Model("unbounded_row", [Variable("x")], [Row("none", Expr.var(0))]),
                       Model("contradictory_row", [Variable("x")], [Row("bad", Expr.var(0), 2, 1)])):
            with self.subTest(name=source.name), self.assertRaises(BuildError):
                source.standard_mps_adapter()

    def test_row_lcm_above_wire_scalar_limit_uses_given_denominator_chunks(self):
        p, q = 3**4291, 7**2423
        self.assertLessEqual(max(p.bit_length(), q.bit_length()), 13600)
        self.assertGreater((p*q).bit_length(), 13600)
        self.assertLessEqual(len(str(p*q)), 4096)
        rows = [(Row("le", Expr(terms={0: Fraction(1, p), 1: Fraction(1, q)}), upper=0),
                 Expr(terms={0: q, 1: p})),
                (Row("eq", Expr(Fraction(1, p), {0: Fraction(1, p), 1: Fraction(1, q)}),
                     lower=Fraction(1, p), upper=Fraction(1, p)), Expr(terms={0: q, 1: p})),
                # Neither raw constant nor bound exceeds wire capacity. Their
                # folded difference has denominator p*q, yet no factorization
                # or nonminimal scale is needed to elaborate its proof.
                (Row("folded_bound", Expr(Fraction(1, p)), upper=Fraction(1, q)), Expr())]
        for row, expected in rows:
            source = Model("chunked", [Variable("x"), Variable("y")], [row])
            adapter = source.standard_mps_adapter()
            self.assertEqual(adapter.target.rows[0].expr, expected)
            scale = adapter.report["row_scales"][0]
            self.assertEqual(Fraction(scale["scale"]), p*q)
            self.assertEqual([Fraction(c) for c in scale["proof_chunks"]], [p, q])
            with self.subTest(kind=row.name), tempfile.TemporaryDirectory() as directory:
                certificate = self.verify(adapter, directory)
                for block, reverse in zip(certificate["blocks"], (False, True, False, True)):
                    multipliers = [Fraction(step["Lin"]["terms"][0][1]) for step in block["steps"]]
                    self.assertEqual(multipliers, [1/Fraction(q), 1/Fraction(p)] if reverse else [p, q])
                    self.assertTrue(all(max(abs(c.numerator).bit_length(), c.denominator.bit_length())<=13600
                                        for c in multipliers))

    def test_single_generated_factor_above_wire_limit_fails_before_readback(self):
        factor = 3**8581
        self.assertGreater(factor.bit_length(), 13600)
        self.assertLessEqual(len(str(factor)), 4096)
        source = Model("single_factor", [Variable("x")],
                       [Row("r", Expr(terms={0: Fraction(1, factor)}), upper=0)])
        with self.assertRaisesRegex(BuildError, "RESOURCE_LIMIT.*scale factor.*13600.*RPX"):
            source.standard_mps_adapter()

    def test_adapter_chain_preserves_authored_rational_target_without_changing_its_proof(self):
        source = Model("source", [Variable("b", True, 0, 1), Variable("x", False, 0, 1)],
                       objective=Expr.var(1))
        authored = Model("authored", [Variable("b", True, 0, 1), Variable("y", False, 0, 3)],
                         objective=Expr.var(1)/3)
        original_proof = Proof(source, authored)
        for integers in (True, False):
            f, r = original_proof.bijection({"b": source.var("b"), "y": 3*source.var("x")},
                                            {"b": authored.var("b"), "x": authored.var("y")/3},
                                            integers=integers)
            f.le([(f.lower("x"), 3)]); f.le([(f.upper("x"), 3)])
            r.le([(r.lower("y"), Fraction(1, 3))]); r.le([(r.upper("y"), Fraction(1, 3))])
            f.complete(); r.complete()
        before = original_proof.certificate()
        adapter = authored.standard_mps_adapter()
        adapted_proof = adapter.proof()
        try:
            with tempfile.TemporaryDirectory() as raw:
                d = Path(raw)
                original = source.write_mps(d/"original.mps")
                committed = adapter.target.write_mps(d/"committed.mps")
                original_proof.compile(d/"stage0"); adapted_proof.compile(d/"stage1")
                chain = write_chain([d/"stage0/delivery.json", d/"stage1/delivery.json"], d/"delivery.json",
                                    original_model=original, committed_model=committed,
                                    claim_paths={"mi_forward": [0, 0], "mi_reverse": [1, 1],
                                                 "lp_forward": [2, 2], "lp_reverse": [3, 3]})
                result = verify_bundle(chain)
                self.assertEqual(result["status"], "VERIFIED", result)
                self.assertTrue(result["composition"]["original_anchor_checked"])
                self.assertTrue(result["composition"]["final_relation_derived"])
                self.assertEqual(result["artifact_audit"]["status"], "MATCHED")
                self.assertTrue(all(path["objective"] == "Equal" for path in result["composition"]["paths"]))
                self.assertEqual(len(result["composition"]["bidirectional"]), 2)
                self.assertTrue(all(pair["equal_optimal_infima"] for pair in result["composition"]["bidirectional"]))
                self.assertEqual(original_proof.certificate(), before)
                self.assertIs(original_proof.target, authored)
        finally:
            original_proof.close(); adapted_proof.close()


if __name__ == "__main__":
    unittest.main()
