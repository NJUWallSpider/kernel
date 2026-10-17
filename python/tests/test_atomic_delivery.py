from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Expr, KernelError, Model, Proof, Row, Variable, verify_bundle


class AtomicDeliveryTests(unittest.TestCase):
    def proof(self, source=None):
        x = Expr.var(0)
        source = source or Model('source', [Variable('x', lower=0, upper=1)],
                                 [Row('fixed', x, lower=0, upper=0)], objective=x)
        target = source.with_bounds('x', upper=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map('identity'), proof.reverse.map('identity'))
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
        names = ('source.mcm', 'target.mcm', 'proof.rpa',
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



if __name__ == '__main__':
    unittest.main()
