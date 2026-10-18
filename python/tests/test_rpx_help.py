"""Offline discovery, coverage, deterministic CLI and executable guide checks."""

import contextlib
import importlib
import inspect
import io
import json
from pathlib import Path
import pydoc
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import rpx
from rpx import lowlevel
from rpx._help import SCHEMA, declarations, resolve, search, topics
from rpx.__main__ import main


class Help(unittest.TestCase):
    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(list(args))
        return status, output.getvalue()

    def test_overview_and_formats(self):
        code, text = self.cli()
        self.assertEqual(code, 0)
        self.assertIn("python -m rpx help quickstart", text)
        self.assertNotIn("\x1b", text)
        for fmt in ("text", "markdown", "json"):
            code, text = self.cli("help", "Scope.map", "--format", fmt)
            self.assertEqual(code, 0)
            self.assertIn("same_name", text)
        data = json.loads(self.cli("--format", "json")[1])
        self.assertEqual((data["schema"], data["kind"]), (SCHEMA, "overview"))

    def test_resolution_and_failure(self):
        self.assertEqual(resolve("rpx.Scope.map")[0], "Scope.map")
        self.assertEqual(resolve("map")[0], "Scope.map")
        self.assertIsNone(resolve("finish")[0])
        self.assertIn("Scope.finish", resolve("finish")[1])
        for query in ("finish", "Scope.mapp", "does-not-exist"):
            status, text = self.cli("help", query, "--format", "json")
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(text)["kind"], "error")
        status, text = self.cli("help", "Generated.commodities", "--format", "json")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(text)["topic"]["category"], "field")

    def test_search_limits_order_and_determinism(self):
        total, records = search("Scope.map")
        self.assertGreaterEqual(total, 1)
        self.assertEqual(records[0]["identifier"], "Scope.map")
        total, records = search("eliminate variable", 5)
        self.assertGreater(total, 0)
        self.assertLessEqual(len(records), 5)
        count, empty = search("flow", 0)
        self.assertGreater(count, 0)
        self.assertEqual(empty, [])
        for query in ("flow", "eliminate variable", "Scope.map"):
            args = ("search", query, "--format", "json")
            first = self.cli(*args)[1]
            self.assertEqual(first, self.cli(*args)[1])
            data = json.loads(first)
            self.assertEqual(data["schema"], SCHEMA)
            self.assertLessEqual(len(data["results"]), 10)
            self.assertIn("total", data)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["search", "flow", "--limit", "-1"])
        self.assertEqual(error.exception.code, 2)

    def test_index_coverage_links_and_signatures(self):
        index = topics()
        data = json.loads(self.cli("help", "--list", "--format", "json")[1])
        self.assertEqual(data["total"], len(index))
        self.assertEqual([r["identifier"] for r in data["results"]], sorted(index))
        for key, topic in index.items():
            with self.subTest(key=key):
                self.assertTrue(topic["summary"])
                self.assertTrue(topic["sections"])
                self.assertTrue(set(topic["related"]).issubset(index))
                self.assertEqual(
                    set(topic),
                    {
                        "identifier",
                        "category",
                        "title",
                        "summary",
                        "signature",
                        "sections",
                        "related",
                    },
                )
        for module, prefix in ((rpx, ""), (lowlevel, "lowlevel.")):
            for name in module.__all__:
                self.assertIn(prefix + name, index)
                obj = getattr(module, name)
                self.assertTrue(inspect.getdoc(obj))
                if inspect.isclass(obj) and not issubclass(obj, BaseException):
                    for member in vars(obj):
                        if not member.startswith("_"):
                            self.assertIn(prefix + name + "." + member, index)
        self.assertIn("Generated", declarations())
        self.assertIsNone(index["Generated"]["signature"])
        self.assertEqual(index["Goal.kind"]["signature"], "kind: Kind")
        self.assertNotIn("-> None", index["Q"]["signature"])
        self.assertIn("ScopeError", index["Goal"]["sections"]["Description"])
        self.assertIn("LinCombination", index["Fact.__mul__"]["summary"])

    def test_standard_introspection(self):
        for obj in (
            rpx,
            rpx.Model,
            rpx.Scope.map,
            rpx.IntervalSpec,
            rpx.Generated,
            rpx.MappingError,
        ):
            self.assertGreater(len(pydoc.render_doc(obj)), 100)
        self.assertIn("Operators", rpx.Fact.__doc__)
        self.assertIn("Fields", rpx.Generated.__doc__)
        self.assertIn("## Parameters", rpx.Scope.map.__doc__)

    def test_help_never_performs_proof_work(self):
        # Real state is captured before help; Python constructors and execution
        # boundaries are disabled while every topic is rendered.
        builder = rpx.ModelBuilder("unchanged")
        builder.add_var("x", lower=0)
        model = builder.build()
        proof = rpx.Proof(model, model)
        before = proof.forward.trace.to_list()
        topics.cache_clear()
        with patch.object(
            rpx.Proof, "compile", side_effect=AssertionError("compile")
        ), patch.object(
            rpx.Proof, "verify", side_effect=AssertionError("verify")
        ), patch.object(
            rpx.Bundle, "verify", side_effect=AssertionError("verify")
        ), patch.object(
            rpx.Proof, "__init__", side_effect=AssertionError("construct")
        ), patch.object(
            lowlevel, "verify", side_effect=AssertionError("kernel")
        ):
            # Existing descriptors are documented without invoking them.
            for key in topics():
                self.assertEqual(self.cli("help", key)[0], 0)
            self.cli("search", "flow")
        topics.cache_clear()
        self.assertEqual(proof.forward.trace.to_list(), before)
        proof.forward.map(default="same_name").finish()

    def test_packaged_examples_are_self_contained(self):
        # Resource source checks also run in an installed wheel outside the repo.
        from importlib.resources import files

        for name in ("quickstart", "workflow", "branches", "lifts", "errors"):
            source = files("rpx._help.examples").joinpath(name + ".py").read_text()
            self.assertNotIn("sys.path", source)
            module = importlib.import_module("rpx._help.examples." + name)
            with patch.object(sys, "argv", [name]), contextlib.redirect_stdout(
                io.StringIO()
            ) as output:
                module.main()
            self.assertIn("VERIFIED", output.getvalue())

    def test_subprocess_status(self):
        result = subprocess.run(
            [sys.executable, "-m", "rpx", "help", "finish", "--format", "json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["schema"], SCHEMA)


if __name__ == "__main__":
    unittest.main()
