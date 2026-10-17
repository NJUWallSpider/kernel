"""Native model readback, exact MCM ownership, and format dispatch."""
from fractions import Fraction
from pathlib import Path
import struct
import tempfile
import unittest

from kernel_compiler import Expr, Model, Row, Variable


class MCMStreamTests(unittest.TestCase):
    def source(self):
        return Model('order and exactness', [Variable('z', True, '-1/3', '7/5'),
                                            Variable('a', False, None, None),
                                            Variable('fixed', False, '2/7', '2/7')],
                     [Row('ranged', Expr('1/11', {0: '-2/3', 2: '4/5'}), '-3/7', '5/13'),
                      Row('equality', Expr('-2/17', {1: 2}), 3, 3),
                      Row('contradictory', Expr.var(0), 4, 2),
                      Row('no_sides', Expr.var(2))], Expr('-7/19', {0: '3/23', 1: -2}))

    def test_mcm_load_is_exact_and_owns_its_value(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = self.source()
            original = source.write_mcm(directory / 'original.bin')
            original_bytes = original.read_bytes()
            loaded = Model.load(original)
            original.write_bytes(b'changed after load')
            self.assertEqual(loaded.to_mcm(), original_bytes)
            self.assertEqual(loaded.to_json(), source.to_json())
            loaded.close()

    def test_mps_ranges_and_lp_are_native_canonicalized(self):
        mps_model = Model('ranges', [Variable('b', True, 0, 1), Variable('x', False, None, 2),
                                   Variable('fixed', False, '1/5', '1/5')],
                          [Row('r', Expr('1/10', {0: 1, 1: '-1/2'}), '-1/5', '3/10'),
                           Row('eq', Expr.var(2), '1/5', '1/5')], Expr('-1/10', {0: 3, 1: '1/4'}))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            mps = mps_model.write_mps(directory / 'model.any')
            lp = directory / 'model.LP'
            lp.write_text('Minimize\n obj: - 1/3 x + 2 y + 1/7\nSubject To\n r: 1/5 x - y <= 2/7\n eq: x = 1/3\nBounds\n x free\n 0 <= y <= 1\nGeneral\n y\nEnd\n')
            for path in (mps, lp):
                with self.subTest(format=path.suffix), Model.load(path) as loaded:
                    self.assertEqual(loaded.path.suffix, '.mcm')
                    self.assertEqual(len(loaded.rows), 2)
                    self.assertEqual(Model.load(loaded.path).to_json(), loaded.to_json())

    def test_empty_and_largest_wire_rationals_match_native_export(self):
        d = (1 << 13598) + 1
        q = Fraction(2 * d + 1, d)
        models = [Model('empty', objective=Fraction(-2, 7)),
                  Model('maximum_wire', [Variable('x', False, -q, q)],
                        [Row('r', Expr(q, {0: -q}), -q, q)], Expr(-q, {0: q}))]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for index, model in enumerate(models):
                path = model.write_mcm(directory / f'{index}.mcm')
                with self.subTest(model=model.name), Model.load(path) as loaded:
                    self.assertEqual(loaded.to_json(), model.to_json())
                    self.assertEqual(loaded.to_mcm(), path.read_bytes())

    def test_json_first_and_actual_reader_suffix_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model = Model('m', [Variable('x')])
            text = model.write_json(directory / 'valid.JSON')
            loaded = Model.load(text)
            self.assertIsNone(loaded.path)
            self.assertEqual(loaded.to_json(), model.to_json())
            binary_json = model.write_mcm(directory / 'binary.json')
            with self.assertRaises(ValueError):
                Model.load(binary_json)
            mps = model.write_mps(directory / 'source.mps')
            wrong = directory / 'source.lp'
            wrong.write_bytes(mps.read_bytes())
            with self.assertRaises(ValueError):
                Model.load(wrong)
            binary_lp = model.write_mcm(directory / 'binary.LP')
            with Model.load(binary_lp) as loaded:
                self.assertEqual(loaded.to_json(), model.to_json())

    def test_bad_mcm_version_is_rejected_before_python_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.mcm'
            body = b'MCM\0' + struct.pack('<HHQ', 2, 0, 16)
            path.write_bytes(body)
            with self.assertRaises(ValueError):
                Model.load(path)


if __name__ == '__main__':
    unittest.main()
