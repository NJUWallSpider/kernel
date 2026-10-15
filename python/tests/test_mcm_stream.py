"""Native-oracle checks for bounded, owned MCM model readback."""
from fractions import Fraction
from contextlib import ExitStack
import gc
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Expr, Kernel, KernelError, Model, Proof, Row, Variable
from kernel_compiler import _mcm


class RecordingKernel(Kernel):
    def __init__(self):
        super().__init__()
        self.commands = []

    def call(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments[0] == 'export-model':
            raise AssertionError('Model.load must not export a full JSON model')
        return super().call(*arguments, **kwargs)


class StreamProbe:
    def __init__(self, stream, reads):
        self.stream, self.reads = stream, reads

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def read(self, count=-1):
        if not 0 <= count <= _mcm.BUFFER_BYTES:
            raise AssertionError(f'unbounded Python binary read: {count}')
        self.reads.append(count)
        return self.stream.read(count)


class MCMStreamTests(unittest.TestCase):
    def source(self):
        return Model('order and exactness', [Variable('z', True, '-1/3', '7/5'),
                                            Variable('a', False, None, None),
                                            Variable('fixed', False, '2/7', '2/7')],
                     [Row('ranged', Expr('1/11', {0: '-2/3', 2: '4/5'}), '-3/7', '5/13'),
                      Row('equality', Expr('-2/17', {1: 2}), 3, 3),
                      Row('contradictory', Expr.var(0), 4, 2),
                      Row('no_sides', Expr.var(2))], Expr('-7/19', {0: '3/23', 1: -2}))

    def oracle(self, canonical, directory):
        exported = Path(directory)/'oracle.json'
        Kernel().call('export-model', canonical, exported)
        return json.loads(exported.read_text())

    def test_mcm_stream_is_exact_owned_and_never_materializes_json_or_full_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = self.source()
            original = source.write_mcm(directory/'original.bin')
            original_bytes = original.read_bytes()
            expected = self.oracle(original, directory)
            reads, original_open = [], Path.open
            def bounded_open(path, mode='r', *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                return StreamProbe(stream, reads) if mode == 'rb' else stream
            kernel = RecordingKernel()
            with ExitStack() as patches:
                patches.enter_context(patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read_bytes')))
                patches.enter_context(patch.object(Path, 'read_text', side_effect=AssertionError('whole-file read_text')))
                patches.enter_context(patch.object(Path, 'open', bounded_open))
                loaded = Model.load(original, kernel)
            self.assertTrue(reads)
            self.assertLessEqual(max(reads), _mcm.BUFFER_BYTES)
            self.assertEqual([c[0] for c in kernel.commands], ['inspect-model'])
            self.assertEqual(loaded.to_json(), expected)
            self.assertEqual(loaded.to_mcm(), original_bytes)
            self.assertNotEqual(loaded.path, original)
            owned = loaded.path
            self.assertEqual(owned.read_bytes(), original_bytes)
            self.assertFalse(list(owned.parent.glob('*.json')))
            # Reading owns a stable snapshot; it never writes into the input.
            original.write_bytes(b'changed after load')
            self.assertEqual(loaded.to_mcm(), original_bytes)
            self.assertEqual(owned.read_bytes(), original_bytes)
            loaded.close()
            self.assertFalse(owned.exists())
            self.assertEqual(original.read_bytes(), b'changed after load')

    def test_mps_ranges_and_lp_are_native_canonicalized_then_streamed(self):
        mps_model = Model('ranges', [Variable('b', True, 0, 1), Variable('x', False, None, 2),
                                   Variable('fixed', False, '1/5', '1/5')],
                          [Row('r', Expr('1/10', {0: 1, 1: '-1/2'}), '-1/5', '3/10'),
                           Row('eq', Expr.var(2), '1/5', '1/5')], Expr('-1/10', {0: 3, 1: '1/4'}))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            mps = mps_model.write_mps(directory/'model.any')
            lp = directory/'model.LP'
            lp.write_text('Minimize\n obj: - 1/3 x + 2 y + 1/7\nSubject To\n r: 1/5 x - y <= 2/7\n eq: x = 1/3\nBounds\n x free\n 0 <= y <= 1\nGeneral\n y\nEnd\n')
            for path in (mps, lp):
                kernel = RecordingKernel()
                with self.subTest(format=path.suffix), Model.load(path, kernel) as loaded:
                    self.assertEqual([c[0] for c in kernel.commands], ['canonical', 'inspect-model'])
                    self.assertEqual(loaded.to_json(), self.oracle(loaded.path, directory))
                    self.assertEqual(loaded.to_mcm(), loaded.path.read_bytes())
                    self.assertEqual(len(loaded.rows), 2)

    def test_empty_and_largest_wire_rationals_match_native_export(self):
        d = (1 << 13598)+1
        q = Fraction(2*d+1, d)
        models = [Model('empty', objective=Fraction(-2, 7)),
                  Model('maximum_wire', [Variable('x', False, -q, q)],
                        [Row('r', Expr(q, {0: -q}), -q, q)], Expr(-q, {0: q}))]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for index, model in enumerate(models):
                path = model.write_mcm(directory/f'{index}.mcm')
                with self.subTest(model=model.name), Model.load(path) as loaded:
                    self.assertEqual(loaded.to_json(), self.oracle(path, directory))
                    self.assertEqual(loaded.to_mcm(), path.read_bytes())

    def test_json_first_and_actual_reader_suffix_dispatch_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model = Model('m', [Variable('x')])
            text = model.write_json(directory/'valid.JSON')
            kernel = RecordingKernel()
            with patch.object(kernel, 'call', side_effect=AssertionError('JSON does not call Kernel')):
                loaded = Model.load(text, kernel)
            self.assertIsNone(loaded.path)
            self.assertEqual(loaded.to_json(), model.to_json())
            binary_json = model.write_mcm(directory/'binary.json')
            with self.assertRaises(ValueError):
                Model.load(binary_json)
            mps = model.write_mps(directory/'source.mps')
            wrong = directory/'source.lp'; wrong.write_bytes(mps.read_bytes())
            with self.assertRaises(KernelError) as rejected:
                Model.load(wrong)
            self.assertEqual(rejected.exception.report['status'], 'INVALID')
            binary_lp = model.write_mcm(directory/'binary.LP')
            with Model.load(binary_lp) as loaded:
                self.assertEqual(loaded.to_json(), model.to_json())

    def test_bad_mcm_metadata_and_widths_are_rejected_natively_before_python(self):
        base = bytearray(Model('m', [Variable('x')]).to_mcm())
        variants = []
        for offset, data in ((4, b'\2\0'), (6, b'\1\0'), (30, b'\2'), (31, b'\1'),
                             (35, b'\1'), (43, struct.pack('<I', 1701))):
            damaged = bytearray(base); damaged[offset:offset+len(data)] = data
            variants.append(damaged)
        variants += [base[:-1], base+b'unknown trailing bytes']
        # A claimed huge variable vector must fail before any allocation.
        damaged = bytearray(base); damaged[21:25] = struct.pack('<I', 10_000_001)
        variants.append(damaged)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for i, data in enumerate(variants):
                path = directory/f'invalid-{i}.mcm'; path.write_bytes(data)
                native = Kernel().call('inspect-model', path, check=False)
                self.assertIn(native['status'], ('INVALID', 'RESOURCE_LIMIT'))
                with self.subTest(variant=i), patch.object(_mcm, 'read_model', side_effect=AssertionError('Python must not admit invalid MCM')):
                    with self.assertRaises(KernelError) as rejected:
                        Model.load(path)
                self.assertEqual(rejected.exception.report['status'], native['status'])
                self.assertEqual(rejected.exception.report.get('message'), native.get('message'))

    def test_sparse_oversized_file_is_rejected_without_copying_or_python_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'too-large.mcm'
            with path.open('wb') as stream:
                stream.write(b'MCM\0')
                stream.truncate(_mcm.MAX_INPUT_BYTES+1)
            with patch.object(_mcm, 'read_model', side_effect=AssertionError('oversized file must remain native error')):
                with self.assertRaises(KernelError) as rejected:
                    Model.load(path)
            self.assertEqual(rejected.exception.report['status'], 'RESOURCE_LIMIT')

    def test_private_defensive_reader_rejects_counts_and_caps_with_bounded_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Model('m', [Variable('x')]).write_mcm(Path(directory)/'m.mcm')
            for cap in ('MAX_VARS', 'MAX_ITEMS', 'MAX_TOTAL_ITEMS', 'MAX_NAME_BYTES'):
                with self.subTest(cap=cap), patch.object(_mcm, cap, 0):
                    with self.assertRaisesRegex(ValueError, 'RESOURCE_LIMIT'):
                        _mcm.read_model(path, Model, Kernel())

    def test_lifecycle_and_kernel_proof_with_actual_committed_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            original = Model('box', [Variable('x', True, 0, 1)], objective=Expr.var(0))
            source_path = original.write_mcm(directory/'source.mcm')
            with Model.load(source_path) as source:
                owned = source.path
                proof = Proof(source, source)
                forward, reverse = proof.bijection('identity', 'identity')
                forward.complete(); reverse.complete()
                committed = original.write_mps(directory/'committed.mps')
                report = proof.verify(directory/'proof', committed_model=committed)
                self.assertEqual(report['status'], 'VERIFIED', report)
                self.assertEqual(report['artifact_audit']['status'], 'MATCHED')
                proof.close()
            self.assertFalse(owned.exists())
            self.assertTrue(source_path.exists())
            loaded = Model.load(source_path)
            owned = loaded.path
            del loaded
            gc.collect()
            self.assertFalse(owned.exists())


if __name__ == '__main__':
    unittest.main()
