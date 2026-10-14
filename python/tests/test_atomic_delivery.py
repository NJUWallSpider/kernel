from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Expr, KernelError, Model, Proof, Row, Variable, compile_certificate, verify_bundle


class AtomicDeliveryTests(unittest.TestCase):
    def proof(self, source=None):
        x = Expr.var(0)
        source = source or Model('source', [Variable('x', lower=0, upper=1)],
                                 [Row('fixed', x, lower=0, upper=0)], objective=x)
        target = source.with_bounds('x', upper=0)
        proof = Proof(source, target)
        forward, reverse = proof.bijection('identity', 'identity', integers=False)
        forward.le([(forward.row('fixed'), 1)], expect=x)
        forward.complete()
        reverse.le([(reverse.upper('x'), 1)], constant=-1)
        reverse.complete()
        return proof

    def assert_no_temporaries(self, directory):
        self.assertEqual(list(Path(directory).glob('.*.tmp')), [])

    def assert_formulation(self, path, expected):
        with Model.load(path) as actual:
            self.assertTrue(actual.same_formulation(expected))

    def test_linked_generated_model_outputs_are_replaced_with_distinct_correct_models(self):
        proof = self.proof()
        for link in ('hardlink', 'symlink'):
            with self.subTest(link=link), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                source_path, target_path = directory / 'source.mcm', directory / 'target.mcm'
                proof.source.write_mcm(source_path)
                if link == 'hardlink':
                    os.link(source_path, target_path)
                else:
                    target_path.symlink_to(source_path)
                self.assertTrue(source_path.samefile(target_path))
                report = proof.verify(directory)
                self.assertEqual(report['status'], 'VERIFIED', report)
                self.assert_formulation(source_path, proof.source)
                self.assert_formulation(target_path, proof.target)
                self.assertFalse(source_path.samefile(target_path))
                self.assertFalse(target_path.is_symlink())
                self.assert_no_temporaries(directory)

    def test_all_generated_outputs_linked_to_pristine_input_preserve_its_bytes(self):
        names = ('source.mcm', 'target.mcm', 'certificate.json', 'request.json',
                 'proof.rpx', 'delivery.json', 'verification.json')
        for link in ('hardlink', 'symlink'):
            with self.subTest(link=link), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                pristine = directory / 'input.mps'
                initial = self.proof()
                initial.source.write_mps(pristine)
                original_bytes = pristine.read_bytes()
                proof = self.proof(Model.load(pristine))
                committed = directory / 'reformulated.mps'
                proof.target.write_mps(committed)
                committed_bytes = committed.read_bytes()
                output = directory / 'output'
                output.mkdir()
                for name in names:
                    if link == 'hardlink':
                        os.link(pristine, output / name)
                    else:
                        (output / name).symlink_to(pristine)
                report = proof.verify(output, committed_model=committed)
                self.assertEqual(report['status'], 'VERIFIED', report)
                self.assertEqual(report['artifact_audit']['status'], 'MATCHED')
                self.assertEqual(pristine.read_bytes(), original_bytes)
                self.assertEqual(committed.read_bytes(), committed_bytes)
                self.assert_formulation(pristine, proof.source)
                self.assert_formulation(output / 'source.mcm', proof.source)
                self.assert_formulation(output / 'target.mcm', proof.target)
                self.assertTrue(all(not (output / name).is_symlink() for name in names))
                self.assertTrue(all(not (output / name).samefile(pristine) for name in names))
                self.assertEqual(verify_bundle(output / 'delivery.json')['status'], 'VERIFIED')
                self.assert_no_temporaries(output)
                proof.source.close()
                proof.close()

    def test_native_compile_failure_cleans_up_and_preserves_old_rpx(self):
        proof = self.proof()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            proof.verify(directory)
            old_rpx = (directory / 'proof.rpx').read_bytes()
            certificate = deepcopy(proof.certificate())
            certificate['blocks'][0]['end']['Return']['checks'][0] = {'UnknownProofReference': 0}
            with self.assertRaises(KernelError):
                compile_certificate(proof.source, proof.target, certificate, proof.request(), directory,
                                    kernel=proof.kernel)
            self.assertEqual((directory / 'proof.rpx').read_bytes(), old_rpx)
            self.assert_no_temporaries(directory)

    def test_failed_partial_native_write_cannot_touch_an_external_link_target(self):
        proof = self.proof()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / 'output'
            proof.verify(output)
            original = directory / 'original.rpx'
            original.write_bytes((output / 'proof.rpx').read_bytes())
            original_bytes = original.read_bytes()
            (output / 'proof.rpx').unlink()
            (output / 'proof.rpx').symlink_to(original)
            def fail(*arguments, **kwargs):
                self.assertEqual(arguments[0], 'compile')
                temporary = Path(arguments[-1])
                self.assertNotEqual(temporary.resolve(), original.resolve())
                temporary.write_bytes(b'partial invalid RPX')
                raise KernelError({'status': 'EXECUTION_FAILED', 'error': 'test partial writer failure'})
            with patch.object(proof.kernel, 'call', side_effect=fail):
                with self.assertRaises(KernelError):
                    proof.compile(output)
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertEqual((output / 'proof.rpx').read_bytes(), original_bytes)
            self.assertTrue((output / 'proof.rpx').is_symlink())
            self.assert_no_temporaries(output)


if __name__ == '__main__':
    unittest.main()
