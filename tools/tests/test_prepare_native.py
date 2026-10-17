"""Focused checks for the native preparer bridge."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python"))

from prepare_native import compile_case, legacy_from_native, make_proof, native_model


def one_variable_model(name="m"):
    return {
        "name": name,
        "vars": [{"name": "x", "integer": False, "lower": 0, "upper": 1}],
        "var_index": {"x": 0},
        "rows": [],
        "row_index": {},
        "objective": (0, {}),
    }


class NativePreparerTests(unittest.TestCase):
    def test_model_roundtrip(self):
        data = one_variable_model()
        native = native_model(data)
        view = legacy_from_native(native)
        self.assertEqual(view["vars"], data["vars"])
        self.assertEqual(view["rows"], [])
        self.assertEqual(view["objective"], (0, {}))

    def test_identity_native_compile(self):
        data = one_variable_model()
        proof, forward, reverse = make_proof(data, data)
        for builder in (forward, reverse):
            builder.finish([(0, {0: 1})], [{"VarLower": 0}, {"VarUpper": 0}, "Exact"])
        with tempfile.TemporaryDirectory() as directory:
            record = compile_case(proof, Path(directory), case_id="identity")
            self.assertEqual(record["status"], "VERIFIED")
            self.assertEqual(record["verification"]["guarantee"], "MI_OPT")
            self.assertTrue((Path(directory) / "proof.rpa").is_file())
            self.assertTrue((Path(directory) / "proof.rpx").is_file())
            self.assertFalse((Path(directory) / "certificate.json").exists())


if __name__ == "__main__":
    unittest.main()
