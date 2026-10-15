#!/usr/bin/env python3
"""Third arm: fixed helper proof with an explicitly frozen encoder snapshot.

Do not run before the controller announces the tested snapshot. Example:
  python encoder_benchmark.py --package /absolute/frozen/snapshot --checkpoint FULL_SHA
The prior two arms and their files are never rewritten by this script.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback
from fractions import Fraction

HERE = Path(__file__).resolve().parent
ORIGINAL = Path('/Users/bhz/Code/reform_test/runs/test16-compiler-compiler-batch-C8-20261015')
PACKAGE = None  # Required explicitly at invocation, never the live checkout.
WORK = Path('/Users/bhz/Code/reform_test/runs/compiler-provided-witness-test16-20261015')
NATIVE_SHA = '5775d6a67b78493ce30a1b6d44b76af7dd264f3cb29371081652e881776839f4'


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def emit(event, **fields):
    print(json.dumps({'event': event, **fields}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--reference-result', type=Path, default=HERE / 'helpers-result.json')
    parser.add_argument('--output', type=Path, default=WORK / 'encoder')
    args = parser.parse_args()
    global PACKAGE
    PACKAGE = args.package.resolve()
    arm = 'encoder'
    destination = args.output.resolve()
    if destination.exists():
        raise FileExistsError('Preserve previous third-arm evidence; choose a new --output directory')
    destination.mkdir(parents=True)
    reference_path = args.reference_result.resolve()
    reference = json.loads(reference_path.read_text())
    assert reference['arm'] == 'helpers' and reference['status'] == 'VERIFIED'
    snapshot = json.loads((PACKAGE / 'snapshot.json').read_text())
    assert snapshot['source_checkpoint'] == args.checkpoint
    assert len(args.checkpoint) == 40 and all(c in '0123456789abcdef' for c in args.checkpoint)
    package_hashes = {}
    for name, expected in snapshot['files'].items():
        actual = digest(PACKAGE / name)
        assert actual == expected['sha256'], name
        package_hashes[name] = actual
    assert digest(WORK / 'rpx') == NATIVE_SHA
    sys.path.insert(0, str(PACKAGE / 'python'))
    from kernel_compiler import Model, Expr, Proof
    from kernel_compiler.backend import Kernel
    from kernel_compiler.session import compile_certificate
    import kernel_compiler.proof as imported_proof
    assert Path(imported_proof.__file__).resolve().is_relative_to(PACKAGE)

    times, native_calls = {}, []
    phase = 'load'

    class TimedKernel(Kernel):
        def call(self, *arguments, **kwargs):
            started = time.perf_counter()
            result = super().call(*arguments, **kwargs)
            native_calls.append({'phase': phase, 'command': str(arguments[0]),
                                 'wall_s': time.perf_counter() - started,
                                 'status': result.get('status')})
            return result

    kernel = TimedKernel(WORK / 'rpx')

    def measured(label, function, *arguments, **kwargs):
        started = time.perf_counter()
        value = function(*arguments, **kwargs)
        times[label] = time.perf_counter() - started
        emit('phase_complete', arm=arm, phase=label, seconds=times[label])
        return value

    total_started = time.perf_counter()
    source = measured('source_MPS_load_s', Model.load, ORIGINAL / 'input/model.mps', kernel=kernel)
    target = measured('provided_target_MCM_load_s', Model.load, ORIGINAL / 'output/target.mcm', kernel=kernel)
    phase = 'setup'
    setup_started = time.perf_counter()
    witnesses = json.loads((ORIGINAL / 'output/witnesses.json').read_text())
    edits = json.loads((ORIGINAL / 'output/edits.json').read_text())
    supplied_request = json.loads((ORIGINAL / 'output/request.json').read_text())
    zsteps = [(source.row_index[w['row']], w['normalized_sign'],
               [source.var_index[name] for name in w['new_zeros']])
              for w in witnesses['zero_steps']]
    fixed = {source.var_index[name]: Fraction(value) for name, value in edits['fixed_coordinates'].items()}
    zcoords = {index for index, value in fixed.items() if value == 0}
    aliases = {source.var_index[name]: source.var_index[other] for name, other in edits['aliases'].items()}
    alias_row = {source.var_index[name]: source.row_index[w['row']]
                 for name, w in witnesses['alias_definitions'].items()}
    assert len(zsteps) == 25842 and len(zcoords) == 29502 and len(aliases) == 20683
    assert len(fixed) == 29503 and source.stats() == edits['source_stats']
    assert target.stats() == edits['target_stats'] and len(target.vars) == 178164
    assert all(w['retained'] == edits['aliases'][name]
               for name, w in witnesses['alias_definitions'].items())
    forward_map = [source.var(v.name) for v in target.vars]
    reverse_map = []
    for index, variable in enumerate(source.vars):
        if index in fixed:
            reverse_map.append(Expr(fixed[index]))
        elif index in aliases:
            reverse_map.append(target.var(source.vars[aliases[index]].name))
        else:
            reverse_map.append(target.var(variable.name))
    proof = Proof(source, target)
    f_mi, r_mi = proof.bijection(forward_map, reverse_map, integers=True, projection='retained')
    f_lp, r_lp = proof.bijection(forward_map, reverse_map, integers=False, projection='retained')
    assert proof.request() == supplied_request
    times['provided_witness_and_maps_setup_s'] = time.perf_counter() - setup_started
    emit('phase_complete', arm=arm, phase='provided_witness_and_maps_setup_s',
         seconds=times['provided_witness_and_maps_setup_s'])

    namespace = {'source': source, 'zsteps': zsteps, 'zcoords': zcoords, 'fixed': fixed,
                 'aliases': aliases, 'alias_row': alias_row, 'Fraction': Fraction}
    exec(compile((HERE / 'original_author_forward.py').read_text(),
                 str(HERE / 'original_author_forward.py'), 'exec'), namespace)
    original_author = namespace['author_forward']

    def helper_author(builder):
        zeros = {}
        for row_index, sign, fresh in zsteps:
            row = source.rows[row_index]
            additions = builder.zero_sum(builder.row(row.name), zeros=zeros,
                                         scale=sign if row.equality else 1,
                                         coordinates=fresh)
            assert set(additions) == set(fresh)
            zeros.update(additions)
        assert set(zeros) == zcoords
        definitions = dict(zeros)
        for index in fixed:
            if index not in definitions:
                definitions[index] = builder.eqpair(builder.upper(index), builder.lower(index))
        # All rows, pivots and representatives come from the supplied witnesses.
        # One pivot plan handles the complete explicit alias-row batch.
        items = list(aliases.items())
        reduced = builder.rewrite_many([builder.row(alias_row[index]) for index, _ in items], zeros)
        for (index, other), equality in zip(items, reduced):
            coefficient = source.rows[alias_row[index]].expr.coefficient(index)
            definitions[index] = builder.eq([(equality, 1 / coefficient)],
                                            expect=source.var(index) - source.var(other))
        builder.substitution(definitions)
        return definitions

    checks = {}

    def author(builder, label):
        # Instrument only the existing substitution call, without modifying its
        # behavior or the original author function's operations/assertions.
        original_substitution = builder.substitution
        def timed_substitution(*arguments, **kwargs):
            return measured(label + '_substitution_s', original_substitution, *arguments, **kwargs)
        builder.substitution = timed_substitution
        definitions = measured(label + '_author_total_s',
                               original_author if arm == 'baseline' else helper_author, builder)
        builder.substitution = original_substitution
        times[label + '_zero_fixed_alias_derivation_s'] = (
            times[label + '_author_total_s'] - times[label + '_substitution_s'])
        start = time.perf_counter()
        expr_hash = hashlib.sha256()
        assert len(definitions) == 50186
        for index in sorted(definitions):
            fact = definitions[index]
            expected = (source.var(index) - fixed[index] if index in fixed else
                        source.var(index) - source.var(aliases[index]))
            assert fact.kind == 'Eq' and fact.expression == expected
            assert fact.scope is builder and builder.parent is None and builder.model is source
            builder._visible(fact)
            entry = [index, fact.kind, fact.expression.to_json()]
            expr_hash.update(json.dumps(entry, separators=(',', ':')).encode() + b'\n')
        checks[label] = {'checked_EQs': len(definitions), 'zeros': 29502, 'fixed_nonzero': 1,
                         'aliases': 20683, 'all_exact_expected_expressions': True,
                         'all_facts_visible_in_exact_claim_root_scope': True,
                         'input_integers': builder.integers, 'expression_sha256': expr_hash.hexdigest()}
        times[label + '_all_definition_expression_scope_check_s'] = time.perf_counter() - start
        return definitions

    phase = 'proof_authoring'
    definitions_mi = author(f_mi, 'MI_forward')
    measured('MI_forward_completion_s', f_mi.complete)

    def reverse_complete(builder):
        pending = builder.missing()
        assert len(pending) == 20515 and all(goal.kind == 'Le' for goal in pending)
        for goal in pending:
            builder.check(goal.label, builder.box_le(goal.expression))
        builder.complete()
        return len(pending)

    measured('MI_reverse_bounds_and_completion_s', reverse_complete, r_mi)
    definitions_lp = author(f_lp, 'LP_forward')
    measured('LP_forward_completion_s', f_lp.complete)
    measured('LP_reverse_bounds_and_completion_s', reverse_complete, r_lp)
    assert checks['MI_forward']['expression_sha256'] == checks['LP_forward']['expression_sha256']
    phase = 'materialize'
    certificate = measured('certificate_materialize_s', proof.certificate)
    request = measured('request_materialize_s', proof.request)
    assert request == supplied_request
    phase = 'serialization_and_artifact_binding'
    paths = measured('serialization_compile_and_whole_artifact_binding_s', compile_certificate,
                     source, target, certificate, request, destination,
                     kernel=kernel, committed_model=ORIGINAL / 'output/reformulated.mps')
    phase = 'native_verify'
    receipt = measured('native_verify_process_wall_s', kernel.verify,
                       paths['source'], paths['target'], paths['proof'], paths['request'])
    assert receipt['status'] == 'VERIFIED'
    delivery = json.loads((destination / 'delivery.json').read_text())
    assert delivery['artifact_binding']['status'] == 'MATCHED'
    assert delivery['artifacts']['committed_model']['sha256'] == 'a392f1a778ab98c3cf20b73314b9cf204c98618bf64e798f9e409f091d4eb2ee'
    receipt['artifacts'] = delivery['artifacts']
    receipt['request_summary'] = delivery['request_summary']
    receipt['artifact_audit'] = delivery['artifact_binding']
    (destination / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    times['total_measured_execution_s'] = time.perf_counter() - total_started
    native_compile_s = sum(x['wall_s'] for x in native_calls if x['phase'] == 'serialization_and_artifact_binding')
    times['serialization_and_binding_python_IO_excluding_native_processes_s'] = (
        times['serialization_compile_and_whole_artifact_binding_s'] - native_compile_s)
    # Outside all measured phases: literal full-byte equality, not size or
    # semantic equality alone. This includes the potentially large certificate.
    def equal_bytes(left, right):
        if left.stat().st_size != right.stat().st_size:
            return False
        with left.open('rb') as old, right.open('rb') as new:
            while True:
                before, after = old.read(1024 * 1024), new.read(1024 * 1024)
                if before != after:
                    return False
                if not before:
                    return True

    equivalent = {}
    for role in ['source', 'target', 'request', 'proof', 'committed_model']:
        old = Path(reference['artifacts'][role]['path'])
        new = Path(delivery['artifacts'][role]['path'])
        equivalent[role] = {'bytes': new.stat().st_size,
                            'identical_bytes': equal_bytes(old, new),
                            'old_sha256': reference['artifacts'][role]['sha256'],
                            'new_sha256': delivery['artifacts'][role]['sha256']}
    old_certificate = Path(reference['artifacts']['source']['path']).parent / 'certificate.json'
    new_certificate = destination / 'certificate.json'
    equivalent['certificate'] = {'bytes': new_certificate.stat().st_size,
                                 'identical_bytes': equal_bytes(old_certificate, new_certificate),
                                 'old_sha256': digest(old_certificate),
                                 'new_sha256': digest(new_certificate)}
    assert all(item['identical_bytes'] for item in equivalent.values())
    assert checks == reference['definition_checks']
    assert receipt['statistics'] == reference['verification_statistics']
    assert reference['original_function_sha256'] == digest(HERE / 'original_author_forward.py')
    original_paths = ['input/model.mps', 'output/source.mcm', 'output/target.mcm',
                      'output/witnesses.json', 'output/analysis.json', 'output/edits.json',
                      'output/request.json', 'output/reformulated.mps', 'session.jsonl']
    result = {'schema': 'provided-witness-proof-regression-v1', 'arm': arm, 'status': 'VERIFIED',
              'not_fresh_Agent_acceptance': True, 'not_solver_or_nomf_comparison': True,
              'third_arm_purpose': 'Isolate tested leaf-encoder implementation on the same helper proof',
              'reference_helpers_result': str(reference_path),
              'reference_helpers_result_sha256': digest(reference_path),
              'byte_equivalence_to_old_helpers': equivalent,
              'native_statistics_exactly_equal_old_helpers': True,
              'package': str(PACKAGE), 'package_checkpoint': snapshot['source_checkpoint'],
              'package_hashes': package_hashes, 'native_sha256': NATIVE_SHA,
              'native_calls': native_calls, 'times': times, 'definition_checks': checks,
              'request_equals_original_complete_Request': True, 'directional_claims': 4,
              'observations_per_claim': 178164, 'whole_artifact_binding': delivery['artifact_binding'],
              'verification_native_total_us': receipt['total_us'],
              'verification_statistics': receipt['statistics'],
              'artifacts': delivery['artifacts'],
              'original_inputs_sha256': {name: digest(ORIGINAL / name) for name in original_paths},
              'reproducer_sha256': digest(__file__),
              'original_function_sha256': digest(HERE / 'original_author_forward.py'),
              'self_peak_rss_raw': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'child_peak_rss_raw': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              'rss_unit': 'bytes on macOS',
              'host_load_at_end': os.getloadavg(),
              'measurement_boundary': 'One serial execution per arm. Derivation excludes separately timed substitution; validation checks and full certificate/request materialization are separately timed. Serialization+binding includes exact committed-MPS readback, Python IO and native canonical/inspect/compile calls, each native call separately recorded. No isolated attribution to one assertion or stable repeated timing claim.'}
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / (arm + '-result.json')).write_text(json.dumps(result, indent=2) + '\n')
    emit('complete', arm=arm, status='VERIFIED', output=str(destination), times=times)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        error = traceback.format_exc()
        (WORK / ('failure-' + str(os.getpid()) + '.txt')).write_text(error)
        raise
