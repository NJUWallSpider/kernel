import json
from pathlib import Path
import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable


class ProofTests(unittest.TestCase):
    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            result = proof.verify(directory)
            self.assertEqual(result["status"], "VERIFIED", result)
            self.assertFalse(list(Path(directory).glob("*.rpa")))
            # Corrupt the complete requested output map, leaving the Request fixed.
            cert = json.loads((Path(directory) / "certificate.json").read_text())
            if cert["blocks"] and "Return" in cert["blocks"][0]["end"]:
                cert["blocks"][0]["end"]["Return"]["map"][0]["constant"] = "999"
                (Path(directory) / "bad.json").write_text(json.dumps(cert))
                proof.kernel.call("compile", Path(directory) / "bad.json", Path(directory) / "bad.rpx")
                rejected = proof.kernel.verify(Path(directory) / "source.mcm", Path(directory) / "target.mcm",
                                                Path(directory) / "bad.rpx", Path(directory) / "request.json")
                self.assertEqual(rejected["status"], "INVALID", rejected)

    def test_affine_elimination_and_inverse(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=0, upper=2)],
                       [Row("define", y-2*x, lower=0, upper=0)], objective=y)
        target = source.substitute({"y": 2*x}, drop_rows=["define"])
        proof = Proof(source, target)
        f, r = proof.bijection({"x": x}, {"x": target.var("x"), "y": 2*target.var("x")}, integers=False)
        f.rewrite(f.lower("y"), {"y": f.row("define")})
        f.rewrite(f.upper("y"), {"y": f.row("define")})
        f.eq([(f.row("define"), -1)])
        self.assertFalse(f.missing())
        f.complete()
        r.complete()
        self.verify(proof)

    def test_rounding_requires_integer_mode(self):
        x = Expr.var(0)
        source = Model("src", [Variable("x", integer=True, lower=0, upper=1)], [Row("cap", 2*x, upper=1)])
        target = source.replace_row("cap", expr=x, upper=0)
        proof = Proof(source, target)
        f, r = proof.bijection("identity", "identity")
        f.round(f.le([(f.row("cap"), "1/2")]), f.integer("x"))
        f.complete()
        r.le([(r.row("cap"), 2)], constant=-1)
        r.complete()
        self.verify(proof)
        relaxed = Builder(source, integers=False)
        with self.assertRaises(BuildError):
            relaxed.integer("x")

    def test_case_strengthening_and_reverse_lp(self):
        x, y, a = (Expr.var(i) for i in range(3))
        variables = [Variable(n, integer=True, lower=0, upper=1) for n in ("x", "y", "a")]
        source = Model("src", variables, [Row("group", x+y, upper=1), Row("gate", x+y-2*a, upper=0)])
        target = source.replace_row("gate", expr=x+y-a)
        proof = Proof(source, target)
        f, r = proof.bijection("identity", "identity")
        goal = x+y-a
        f.cases(a, kind="Le", expect=goal,
                left=lambda b, s: b.le([(b.row("gate"), 1), (s, 1)], expect=goal),
                right=lambda b, s: b.le([(b.row("group"), 1), (s, 1)], expect=goal))
        f.complete()
        r.le([(r.row("gate"), 1), (r.lower("a"), 1)])
        r.complete()
        lp = proof.claim(reverse=True, integers=False, mapping="identity", projection="retained")
        lp.le([(lp.row("gate"), 1), (lp.lower("a"), 1)])
        lp.complete()
        proof.add_point({"ImageExclusion": {"point_in_target": False, "map": [x, y, a]}}, [1, 0, "1/2"])
        self.verify(proof)

    def test_interval_projection_lift(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model("src", [Variable("x", lower=0, upper=1), Variable("y", lower=0)],
                       [Row("cap", y-x, upper=0)])
        target = Model("tgt", [Variable("x", lower=0, upper=1)])
        proof = Proof(source, target)
        f = proof.claim(mapping={"x": x}, objective="None", projection="retained")
        f.complete()
        r = proof.claim(reverse=True, objective="None", projection="retained")
        scope = r.intervals([{"lower": [Expr(0)], "upper": [target.var("x")], "checks": [r.lower("x")]}])
        z = scope.model.var(scope.generated_variables[0])
        r.complete(scope=scope, mapping={"x": scope.model.var("x"), "y": z})
        self.verify(proof)

    def test_sibling_leak_and_dropped_parent_rejected(self):
        x = Expr.var(0)
        source = Model("src", [Variable("x", integer=True, lower=0, upper=1)])
        builder = Builder(source)
        exported = []
        def left(b, assumption):
            fact = b.le([(assumption, 1)])
            exported.append(fact)
            return fact
        # Different conclusions must not be silently accepted.
        with self.assertRaises(BuildError):
            builder.cases(x, kind="Le", expect=x, left=left, right=lambda b, s: exported[0])
        fact = builder.le([(builder.lower("x"), 1)])
        builder.drop(fact)
        child, _ = builder._branch(x)
        with self.assertRaises(BuildError):
            child.le([(fact, 1)])

    def test_unproved_obligation_is_visible(self):
        source = Model("src", [Variable("x", lower=0, upper=1)])
        target = source.with_bounds("x", upper=0)
        proof = Proof(source, target)
        forward = proof.claim(mapping="identity")
        missing = forward.missing()
        self.assertEqual([o.origin["kind"] for o in missing], ["variable.upper"])
        with self.assertRaises(BuildError):
            forward.complete()


if __name__ == "__main__":
    unittest.main()
