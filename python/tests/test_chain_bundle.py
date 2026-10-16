from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import BuildError, Expr, Kernel, Model, Proof, Variable, verify_bundle, write_chain


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ChainBundleTests(unittest.TestCase):
    def model(self, name, names, *, fixed=None, upper=1):
        fixed = fixed or {}
        variables = [Variable(n, integer=n not in fixed, lower=fixed.get(n, 0),
                              upper=fixed.get(n, upper)) for n in names]
        objective = sum((Expr.var(i) for i, n in enumerate(names) if n not in fixed), Expr())
        if 's' in names:
            objective += Expr.var(names.index('s'))
        return Model(name, variables, objective=objective)

    def fixture(self, directory, *, count=3, objective='NonIncreasing', restricted=False,
                lower=True, domains=(True, False), broken_join=False):
        directory = Path(directory)
        source = self.model('original', ['x', 'y', 's'], fixed={'s': 0})
        middle = self.model('middle', ['y', 'x'])
        reordered = self.model('renamed_model', ['x', 'y'], upper=2 if broken_join else 1)
        renamed = self.model('renamed_coordinates', ['z', 'x'], upper=2 if broken_join else 1)
        final_source = self.model('reordered_again', ['x', 'z'])
        final = self.model('final', ['z', 'x', 't'], fixed={'t': 1})
        proofs = [Proof(source, middle), Proof(reordered, renamed), Proof(final_source, final)][:count]
        for mode in (True,):
            f, r = (proofs[0].forward.map({'x': source.var('x'), 'y': source.var('y')}), proofs[0].reverse.map({'x': middle.var('x'), 'y': middle.var('y'), 's': 0}))
            f.substitution({'s': f.eqpair(f.upper('s'), f.lower('s'))})
            f.complete(); r.complete()
            if count > 1:
                arguments = {'integers': mode, 'projection': [('x', 'x'), ('y', 'z')]}
                forward_map = {'x': reordered.var('x'), 'z': reordered.var('y')}
                reverse_map = {'x': renamed.var('x'), 'y': renamed.var('z')}
                if restricted:
                    f = proofs[1].forward.map(forward_map)
                    r = proofs[1].reverse.map(reverse_map)
                else:
                    f, r = (proofs[1].forward.map(forward_map), proofs[1].reverse.map(reverse_map))
                if lower:
                    f.le([(f.lower('x'), 1), (f.lower('y'), 1)])
                f.complete(); r.complete()
            if count > 2:
                f, r = (proofs[2].forward.map({'x': final_source.var('x'), 'z': final_source.var('z'), 't': 1}), proofs[2].reverse.map({'x': final.var('x'), 'z': final.var('z')}))
                r.substitution({'t': r.eqpair(r.upper('t'), r.lower('t'))})
                f.complete(); r.complete()
        manifests = []
        for i, proof in enumerate(proofs):
            proof.compile(directory / f'stage{i}')
            manifests.append(directory / f'stage{i}/delivery.json')
            proof.close()
        original = directory / 'original.mps'
        committed = directory / 'final.mps'
        source.write_mps(original)
        proofs[-1].target.write_mps(committed)
        return manifests, original, committed

    def chain(self, directory, *, paths=None, **options):
        stages, original, committed = self.fixture(directory, **options)
        if paths is None:
            count = len(stages)
            paths = {'mi_forward': [0]*count, 'mi_reverse': [1]*count,
                     'lp_forward': [2]*count, 'lp_reverse': [3]*count}
        output = write_chain(stages, Path(directory)/'chain.json', original_model=original,
                             committed_model=committed)
        return output, stages, original, committed

    def change(self, path, mutate):
        document = json.loads(Path(path).read_text())
        mutate(document)
        Path(path).write_text(json.dumps(document))

    def reader_fixture(self, directory):
        directory = Path(directory)
        model = self.model('same', ['x', 'y'])
        stages = []
        for index in range(2):
            proof = Proof(model, model)
            proof.reverse.map("identity").complete()
            f, r = (proof.forward.map('identity'), proof.reverse.map('identity'))
            f.complete(); r.complete()
            proof.compile(directory/f'stage{index}')
            stages.append(directory/f'stage{index}/delivery.json')
        committed = directory/'committed.mps'
        model.write_mps(committed)
        return model, stages, committed

    def rebind_stage_role(self, manifest, role, path):
        def update(document):
            document['pieces'][0][role] = str(path)
            document['artifacts'][role] = {'path': str(path), 'sha256': digest(path)}
        self.change(manifest, update)

    def rebind_top_from_stages(self, chain, stages):
        def update(document):
            for index, manifest in enumerate(stages):
                stage = json.loads(manifest.read_text())
                document['pieces'][index] = stage['pieces'][0]
                for role in ('source', 'target', 'proof'):
                    document['artifacts'][f'stages.{index}.{role}'] = stage['artifacts'][role]
                document['artifacts'][f'stages.{index}.manifest'] = {'path': str(manifest), 'sha256': digest(manifest)}
        self.change(chain, update)

    def test_real_three_stage_composition_reordered_coordinates_and_global_lower(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, _, _, _ = self.chain(directory)
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'VERIFIED', result)
            self.assertEqual(len(result['parts']), 3)
            self.assertEqual(result['artifacts'], json.loads(chain.read_text())['artifacts'])
            audit = result['artifact_audit']
            self.assertEqual(audit['status'], 'MATCHED')
            self.assertEqual(audit['method'], 'Kernel standard-format readback and exact named formulation comparison')
            self.assertIn('Only the final complete proof target', audit['scope'])
            self.assertEqual(audit['committed_model'], result['artifacts']['committed_model'])
            self.assertEqual(audit['proof_target'], result['artifacts']['stages.2.target'])
            composition = result['composition']
            self.assertTrue(composition['final_relation_derived'])
            self.assertEqual(len(composition['joins']), 2)
            self.assertEqual(composition['guarantee'], 'MI_OPT')

    def test_real_two_stages_and_explicit_empty_paths_only_verify_locally(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, _, _, _ = self.chain(directory, count=2, paths={})
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'VERIFIED', result)
            self.assertTrue(result['composition']['final_relation_derived'])

    def test_same_mps_bytes_with_lp_suffix_cannot_reuse_a_different_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model, stages, committed = self.reader_fixture(directory)
            chain = write_chain(stages, directory/'chain.json', committed_model=committed)
            target = directory/'intermediate.mps'; model.write_mps(target)
            source = directory/'mislabelled.LP'; source.write_bytes(target.read_bytes())
            self.assertEqual(digest(target), digest(source))
            independent = Kernel().call('canonical', source, directory/'bad.mcm', check=False)
            self.assertEqual(independent['status'], 'INVALID', independent)
            self.rebind_stage_role(stages[0], 'target', target)
            self.rebind_stage_role(stages[1], 'source', source)
            with self.assertRaises(BuildError):
                write_chain(stages, directory/'cannot-publish.json', committed_model=committed)
            self.rebind_top_from_stages(chain, stages)
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'INCOMPLETE', result)
            self.assertFalse(result['composition']['final_relation_derived'])
            self.assertNotIn('artifact_audit', result)

    def test_mcm_magic_reuse_accepts_arbitrary_nonjson_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            _, stages, committed = self.reader_fixture(directory)
            mcm = Path(json.loads(stages[0].read_text())['pieces'][0]['target']).read_bytes()
            target, source = directory/'intermediate.LP', directory/'next.bin'
            target.write_bytes(mcm); source.write_bytes(mcm)
            self.rebind_stage_role(stages[0], 'target', target)
            self.rebind_stage_role(stages[1], 'source', source)
            chain = write_chain(stages, directory/'chain.json', committed_model=committed)
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'VERIFIED', result)
            self.assertTrue(result['composition']['final_relation_derived'])

    def test_same_reader_reuse_preserves_lp_case_and_mps_fallback_dispatch(self):
        for reader in ('lp', 'mps'):
            with self.subTest(reader=reader), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                model, stages, committed = self.reader_fixture(directory)
                if reader == 'lp':
                    target, source = directory/'intermediate.lp', directory/'next.LP'
                    target.write_text('Minimize\n obj: x + y\nSubject To\nBounds\n 0 <= x <= 1\n 0 <= y <= 1\nGeneral\n x y\nEnd\n')
                else:
                    target, source = directory/'intermediate.text', directory/'next.data'
                    model.write_mps(target)
                source.write_bytes(target.read_bytes())
                self.rebind_stage_role(stages[0], 'target', target)
                self.rebind_stage_role(stages[1], 'source', source)
                chain = write_chain(stages, directory/'chain.json', committed_model=committed)
                result = verify_bundle(chain)
                self.assertEqual(result['status'], 'VERIFIED', result)
                self.assertTrue(result['composition']['final_relation_derived'])

    def test_mcm_bytes_json_suffix_cannot_skip_model_json_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            _, stages, committed = self.reader_fixture(directory)
            chain = write_chain(stages, directory/'chain.json', committed_model=committed)
            source = directory/'source.JSON'
            source.write_bytes(Path(json.loads(stages[0].read_text())['pieces'][0]['target']).read_bytes())
            with self.assertRaises(ValueError):
                Model.load(source)
            self.rebind_stage_role(stages[1], 'source', source)
            with self.assertRaises(BuildError):
                write_chain(stages, directory/'cannot-publish.json', committed_model=committed)
            self.rebind_top_from_stages(chain, stages)
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'INCOMPLETE', result)
            self.assertFalse(result['composition']['final_relation_derived'])

    def test_json_anchor_and_committed_readers_are_preserved_and_labeled_accurately(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model, stages, committed = self.reader_fixture(directory)
            original_json, committed_json = directory/'original.JSON', directory/'final.json'
            model.write_json(original_json); model.write_json(committed_json)
            chain = write_chain(stages, directory/'chain.json', committed_model=committed_json,
                                original_model=original_json)
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'VERIFIED', result)
            self.assertEqual(result['artifact_audit']['method'], 'Python canonical JSON readback and exact named formulation comparison')
            self.assertEqual(result['artifact_audit']['committed_reader'], 'python_canonical_json')
            self.assertEqual(result['artifact_audit']['proof_target_reader'], 'kernel_mcm')
            self.assertEqual(result['composition']['original_anchor_reader'], 'python_canonical_json')
            # An original JSON anchor does not change the committed MPS audit.
            standard = write_chain(stages, directory/'standard.json', committed_model=committed,
                                   original_model=original_json)
            result = verify_bundle(standard)
            self.assertEqual(result['artifact_audit']['method'], 'Kernel standard-format readback and exact named formulation comparison')
            self.assertEqual(result['composition']['original_anchor_reader'], 'python_canonical_json')


    def test_chain_needs_no_request_or_claim_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, stages, _, _ = self.chain(directory, count=2)
            for manifest in stages:
                stage = json.loads(manifest.read_text())
                self.assertNotIn('request', stage['pieces'][0])
                self.assertFalse((manifest.parent/'request.json').exists())
            self.assertEqual(json.loads(chain.read_text())['composition'], {'ordered_chain': True})
            self.assertEqual(verify_bundle(chain)['status'], 'VERIFIED')

    def test_broken_named_join_and_final_target_mismatch_rejected_before_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            stages, original, committed = self.fixture(directory, count=2, broken_join=True)
            output = Path(directory)/'chain.json'; output.write_bytes(b'previous manifest')
            with self.assertRaisesRegex(BuildError, 'Broken exact named model join'):
                write_chain(stages, output, original_model=original, committed_model=committed)
            self.assertEqual(output.read_bytes(), b'previous manifest')
        with tempfile.TemporaryDirectory() as directory:
            stages, original, _ = self.fixture(directory, count=2)
            wrong = Path(directory)/'wrong.mps'; self.model('wrong', ['x', 'z'], upper=2).write_mps(wrong)
            with self.assertRaisesRegex(BuildError, 'Last chain target'):
                write_chain(stages, Path(directory)/'chain.json', original_model=original, committed_model=wrong)

    def test_mandatory_stage_hashes_and_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, stages, _, _ = self.chain(directory, count=2)
            original = chain.read_text()
            for key in ('stages.0.proof', 'stages.1.source', 'committed_model', 'original_model'):
                chain.write_text(original)
                self.change(chain, lambda d: d['artifacts'].pop(key))
                self.assertEqual(verify_bundle(chain)['status'], 'INCOMPLETE', key)
            chain.write_text(original)
            proof = Path(json.loads(stages[0].read_text())['pieces'][0]['proof'])
            proof.write_bytes(proof.read_bytes()+b'tamper')
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'INCOMPLETE', result)
            self.assertIn('digest mismatch', result['error'])

    def test_invalid_native_stage_cannot_produce_a_final_relation_even_with_updated_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, stages, _, _ = self.chain(directory, count=2)
            proof = Path(json.loads(stages[0].read_text())['pieces'][0]['proof'])
            proof.write_bytes(proof.read_bytes()+b'extra invalid RPX bytes')
            stage = json.loads(stages[0].read_text())
            stage['artifacts']['proof']['sha256'] = digest(proof)
            stages[0].write_text(json.dumps(stage))
            self.change(chain, lambda d: (
                d['artifacts']['stages.0.proof'].update(sha256=digest(proof)),
                d['artifacts']['stages.0.manifest'].update(sha256=digest(stages[0]))))
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'INCOMPLETE', result)
            self.assertEqual(len(result['parts']), 2)
            self.assertNotEqual(result['parts'][0]['status'], 'VERIFIED')
            self.assertEqual(result['artifact_audit']['status'], 'MATCHED')
            self.assertFalse(result['composition']['final_relation_derived'])

    def test_pristine_mutation_and_rehashed_semantic_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            chain, _, original, _ = self.chain(directory, count=2)
            self.model('changed', ['x', 'y', 's'], fixed={'s': 0}, upper=2).write_mps(original)
            self.assertEqual(verify_bundle(chain)['status'], 'INCOMPLETE')
            self.change(chain, lambda d: d['artifacts']['original_model'].update(sha256=digest(original)))
            result = verify_bundle(chain)
            self.assertEqual(result['status'], 'INCOMPLETE', result)
            self.assertIn('declared original', result['error'])
            self.assertNotIn('artifact_audit', result)

    def test_manifest_output_aliases_protected_inputs_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            stages, original, committed = self.fixture(directory, count=2)
            protected = Path(json.loads(stages[0].read_text())['pieces'][0]['proof'])
            initial = protected.read_bytes()
            for output in (protected, stages[0], original, committed):
                with self.assertRaisesRegex(BuildError, 'aliases'):
                    write_chain(stages, output, original_model=original, committed_model=committed)
            for kind in ('hardlink', 'symlink'):
                output = directory/kind
                if kind == 'hardlink': os.link(protected, output)
                else: output.symlink_to(protected)
                with self.assertRaisesRegex(BuildError, 'aliases'):
                    write_chain(stages, output, committed_model=committed)
            self.assertEqual(protected.read_bytes(), initial)
            output = directory/'chain.json'
            outside = directory/'unrelated.json'; outside.write_bytes(b'keep unrelated')
            output.symlink_to(outside)
            write_chain(stages, output, committed_model=committed)
            self.assertFalse(output.is_symlink())
            self.assertEqual(outside.read_bytes(), b'keep unrelated')
            previous = output.read_bytes()
            with patch.object(Path, 'replace', side_effect=OSError('publication failure')):
                with self.assertRaisesRegex(BuildError, 'publication failure'):
                    write_chain(stages, output, committed_model=committed)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(list(directory.glob('.*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
