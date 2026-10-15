#!/usr/bin/env python3
"""Supplied C9/test70 proof regression; run only after the controller's quality gate.

This script does not discover a formulation, cover, packing witness, or map.
Both arms use one frozen package and the original source/target artifacts. The
only arm choice is the elaboration of the supplied packing-subset inequalities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback
from collections import defaultdict
from fractions import Fraction


ORIGINAL = Path('/Users/bhz/Code/reform_test/runs/test70-compiler-compiler-batch-C9-20261015')
WORK = Path('/Users/bhz/Code/reform_test/runs/compiler-provided-witness-test70-20261015')
CHECKPOINT = '8ebcc97673f752a5be549ade0d6b25c02109929c'
NATIVE_SHA = '5775d6a67b78493ce30a1b6d44b76af7dd264f3cb29371081652e881776839f4'
EXPECTED = {
    'input/model.mps': '3989e335c0e1c754ae8c6f6b2ab12fa51844a20c27278f915811cab258eb0259',
    'output/source.mcm': '6700f534955c041dbd4f205f03fc4cda633b8d494479c701367512f9d9a7fe6f',
    'output/target.mcm': 'f1c1138e03789a9622f0b796118cf763e73f37b767e2fdf9a10a619289871345',
    'output/request.json': '69913f461d781259a1cac3842d3c5f2563dc88768a1fd91befdc2efc86b783e4',
    'output/proof.rpx': 'b7467eb754485e27d953e3dab568e8d38a96f05a3755574f50e6901895840aa4',
    'output/reformulated.mps': '0fe67ea4e2d3f12b4fd092a0b2a444a529cc04864fd10365277eaa73ee8dca88',
}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def emit(event, **fields):
    print(json.dumps({'event': event, **fields}), flush=True)


def interval_chunks(indices):
    # Exact public Agent function, unchanged apart from whitespace.
    xs = sorted(indices)
    chunks = []
    if not xs:
        return chunks
    start = prev = xs[0]

    def add_run(a, b):
        while a < b:
            length = (a & -a) if a else 1 << ((b-a).bit_length()-1)
            while length > b-a:
                length //= 2
            chunks.append((a, length))
            a += length

    for j in xs[1:]:
        if j == prev+1:
            prev = j
        else:
            add_run(start, prev+1)
            start = prev = j
    add_run(start, prev+1)
    return chunks


def lower_sums(builder):
    # Exact public Agent dyadic lower-bound construction, used in both arms for
    # aggregate lower bounds. The handwritten arm also uses it for cancellations.
    dyadic_facts = {}

    def lower_interval(a, n):
        if n == 1:
            return builder.lower(a)
        key = (a, n)
        if key not in dyadic_facts:
            dyadic_facts[key] = builder.le([
                (lower_interval(a, n//2), 1),
                (lower_interval(a+n//2, n//2), 1)])
        return dyadic_facts[key]

    def lower_subset(subset):
        return [(lower_interval(a, n), 1) for a, n in interval_chunks(subset)]

    return lower_subset, dyadic_facts


def handwritten_subsets(builder, packings, subset_needs, packing_facts,
                        lower_subset, Expr):
    # Exact supplied containment-parent construction from the public cell at
    # 537.869 s. It selects only sharing among already supplied desired subsets;
    # it does not construct any gate cover or choose mathematical premises.
    parents = {}
    for t, sets in subset_needs.items():
        root = frozenset(packings[t][2])
        known = [root]
        for selected in sorted(sets, key=lambda s: (-len(s), tuple(sorted(s)))):
            if selected == root:
                continue
            parent = min((candidate for candidate in known if selected <= candidate), key=len)
            parents[t, selected] = parent
            known.append(selected)
    facts = {}
    for t, sets in subset_needs.items():
        root = frozenset(packings[t][2])
        facts[t, root] = packing_facts[t]
        for selected in sorted(sets, key=lambda s: (-len(s), tuple(sorted(s)))):
            if selected == root:
                continue
            parent = parents[t, selected]
            facts[t, selected] = builder.le(
                [(facts[t, parent], 1)] + lower_subset(parent-selected),
                expect=Expr(-1, {j: Fraction(1) for j in selected}))
    return facts


def helper_subsets(builder, packings, subset_needs, packing_facts):
    facts = {}
    for t, sets in subset_needs.items():
        root = frozenset(packings[t][2])
        facts[t, root] = packing_facts[t]
        # Preserve the same caller-selected sets and order as the manual arm.
        selected = sorted(sets, key=lambda s: (-len(s), tuple(sorted(s))))
        results = builder.subset_bounds(packing_facts[t], selected)
        assert len(results) == len(selected)
        facts.update(((t, subset), fact) for subset, fact in zip(selected, results))
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('handwritten', 'helper'), required=True)
    parser.add_argument('--execute', action='store_true', help='Explicit post-quality controller gate')
    parser.add_argument('--package', type=Path, default=WORK / 'package')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.execute:
        parser.error('Static preparation only: --execute requires the controller to finish quality timing first')
    destination = (args.output or WORK / args.arm).resolve()
    if destination.exists():
        raise FileExistsError('Preserve prior evidence; choose a fresh --output directory')
    destination.mkdir(parents=True)
    package = args.package.resolve()
    snapshot = json.loads((package / 'snapshot.json').read_text())
    assert snapshot['source_checkpoint'] == CHECKPOINT
    package_hashes = {}
    for name, record in snapshot['files'].items():
        actual = digest(package / name)
        assert actual == record['sha256'], name
        package_hashes[name] = actual
    evidence = json.loads((WORK / 'prepared.json').read_text())
    assert evidence['status'] == 'PREPARED_NOT_EXECUTED'
    for name, expected in EXPECTED.items():
        assert digest(ORIGINAL / name) == expected, name
    for name, expected in evidence['additional_original_sha256'].items():
        assert digest(ORIGINAL / name) == expected, name
    # No large certificate body was read while independent quality was timing.
    # Bind it now, before either measured model load or authoring phase.
    additional_hashes = dict(evidence['additional_original_sha256'])
    additional_hashes['output/certificate.json'] = digest(ORIGINAL / 'output/certificate.json')
    binary = ORIGINAL / 'compiler/bin/rpx'
    assert digest(binary) == NATIVE_SHA
    sys.path.insert(0, str(package / 'python'))
    from kernel_compiler import Model, Expr, Proof
    from kernel_compiler.backend import Kernel
    from kernel_compiler.session import compile_certificate
    import kernel_compiler.proof as proof_module
    assert package in Path(proof_module.__file__).resolve().parents

    times, native_calls = {}, []
    phase = 'load'

    class TimedKernel(Kernel):
        def call(self, *arguments, **kwargs):
            started = time.perf_counter()
            result = super().call(*arguments, **kwargs)
            native_calls.append({'phase': phase, 'command': str(arguments[0]),
                                 'wall_s': time.perf_counter()-started,
                                 'status': result.get('status')})
            return result

    def measured(label, function, *arguments, **kwargs):
        started = time.perf_counter()
        value = function(*arguments, **kwargs)
        times[label] = time.perf_counter()-started
        emit('phase_complete', arm=args.arm, phase=label, seconds=times[label])
        return value

    kernel = TimedKernel(binary)
    total_started = time.perf_counter()
    source = measured('fixed_source_MCM_load_s', Model.load, ORIGINAL / 'output/source.mcm', kernel=kernel)
    target = measured('fixed_target_MCM_load_s', Model.load, ORIGINAL / 'output/target.mcm', kernel=kernel)
    phase = 'witness_setup'
    setup_started = time.perf_counter()
    audit = json.loads((ORIGINAL / 'output/structural_audit.json').read_text())
    supplied_request = json.loads((ORIGINAL / 'output/request.json').read_text())
    assert source.stats() == audit['source_stats'] and target.stats() == audit['target_stats']
    assert len(source.vars) == 48417 and len(target.vars) == 46219

    # This is the original public basis-reading loop, with the final target and
    # all selected cover/group witnesses already fixed by structural_audit.json.
    # No cover, duplicate-column, leaf, free-variable, or target search is run.
    packings = []
    for k, row in enumerate(source.rows):
        if row.lower != row.upper or row.lower is None:
            continue
        if row.lower == 1 and set(row.expr.terms.values()) == {1}:
            packings.append((k, None, set(row.expr.terms)))
        elif row.lower == 0:
            negatives = [j for j, a in row.expr.terms.items() if a == -1]
            if len(negatives) == 1 and all(a == 1 or j == negatives[0] for j, a in row.expr.terms.items()):
                packings.append((k, negatives[0], {j for j, a in row.expr.terms.items() if a == 1}))
    assert len(packings) == 173
    pack_by_name = {source.rows[k].name: t for t, (k, _, _) in enumerate(packings)}
    groups = [[source.var_index[name] for name in group['members']] for group in audit['aggregate_groups']]
    assert len(groups) == 1202
    agg_packing = {group[0]: pack_by_name[record['packing_row']]
                   for group, record in zip(groups, audit['aggregate_groups'])}
    assert all(source.vars[group[0]].name == record['representative']
               for group, record in zip(groups, audit['aggregate_groups']))
    free = {source.var_index[name] for name in audit['objective_only_fixed_zero']}
    leaves = {source.var_index[item['variable']] for item in audit['zero_cost_leaf_controls']}
    leaf_rows = {item['row'] for item in audit['zero_cost_leaf_controls']}
    forced = [source.var_index[name] for name in audit['forced_ones']['variables']]
    assert len(free) == 301 and len(leaves) == 298 and len(forced) == 2
    removed_duplicates = {j for group in groups for j in group[1:]}
    replacements = {source.vars[j].name: Expr(0) for j in free | removed_duplicates}
    replacements.update({source.vars[j].name: Expr(1) for j in leaves | set(forced)})
    tighten = {}
    covers = {}
    for item in audit['tightened_gates']:
        name = item['row']
        selected = [(None if part['packing_row'] is None else pack_by_name[part['packing_row']],
                     [source.var_index[v] for v in part['members']]) for part in item['cover']]
        tighten[name] = (source.var_index[item['control']], Fraction(item['old_M']), item['new_M'])
        covers[name] = selected
        positive = {j for j, coefficient in source.row(name).expr.terms.items() if coefficient == 1}
        assert {j for _, subset in selected for j in subset} == positive
        assert sum(len(subset) for _, subset in selected) == len(positive)
        assert len(selected) == item['new_M']
    assert len(tighten) == 1679
    subset_needs = defaultdict(set)
    for name in tighten:
        for t, subset in covers[name]:
            if t is not None:
                subset_needs[t].add(frozenset(subset))
    for group in groups:
        subset_needs[agg_packing[group[0]]].add(frozenset(group))

    groups_by_rep = {group[0]: group for group in groups}
    fmap = {v.name: (Expr(0, {j: Fraction(1) for j in groups_by_rep[source.var_index[v.name]]})
                    if source.var_index[v.name] in groups_by_rep else source.var(v.name)) for v in target.vars}
    rmap = {v.name: replacements[v.name] if v.name in replacements else target.var(v.name) for v in source.vars}
    observations = [(v.name, v.name) for v in target.vars if source.var_index[v.name] not in groups_by_rep]
    assert len(observations) == 45017
    proof = Proof(source, target, kernel=kernel)
    forward, reverse = proof.correspondence(fmap, rmap, projection=observations)
    reverse_lp = proof.claim(reverse=True, mapping=rmap, integers=False,
                             objective='Equal', projection=observations)
    assert proof.request() == supplied_request
    objective_delta = target.objective.substitute({i: fmap[v.name] for i, v in enumerate(target.vars)})-source.objective
    times['provided_witness_and_maps_setup_s'] = time.perf_counter()-setup_started
    emit('phase_complete', arm=args.arm, phase='provided_witness_and_maps_setup_s',
         seconds=times['provided_witness_and_maps_setup_s'])
    del audit

    phase = 'proof_authoring'
    def common_prefix():
        packing_facts = {}
        for t, (k, control, _) in enumerate(packings):
            row_fact = forward.row(source.rows[k].name)
            packing_facts[t] = forward.le([(row_fact, 1), (forward.upper(control), 1)]) if control is not None else forward.le([(row_fact, 1)])
        fixed_facts = {}
        for j, other in [(forced[0], forced[1]), (forced[1], forced[0])]:
            lower_one = forward.le([(forward.row('c1201'), Fraction(1, 20)), (forward.upper(other), 1)],
                                   expect=1-source.var(source.vars[j].name))
            fixed_facts[source.vars[j].name] = forward.eqpair(forward.upper(j), lower_one)
        forward.substitution(fixed_facts)
        return packing_facts, fixed_facts

    packing_facts, fixed_facts = measured('packing_fixed_and_substitution_s', common_prefix)
    lower_subset, dyadic_facts = lower_sums(forward)
    if args.arm == 'handwritten':
        subset_facts = measured('provided_subset_elaboration_s', handwritten_subsets,
                                forward, packings, subset_needs, packing_facts, lower_subset, Expr)
    else:
        subset_facts = measured('provided_subset_elaboration_s', helper_subsets,
                                forward, packings, subset_needs, packing_facts)

    check_started = time.perf_counter()
    expression_hash = hashlib.sha256()
    assert len(subset_facts) == 6887
    for (t, selected), fact in sorted(subset_facts.items(), key=lambda item: (item[0][0], tuple(sorted(item[0][1])))):
        assert fact.kind == 'Le' and fact.expression == Expr(-1, {j: Fraction(1) for j in selected})
        assert fact.scope is forward and forward.parent is None and forward.model is source
        forward._visible(fact)
        entry = [t, sorted(selected), fact.kind, fact.expression.to_json()]
        expression_hash.update(json.dumps(entry, separators=(',', ':')).encode()+b'\n')
    subset_checks = {'count': len(subset_facts), 'expression_sha256': expression_hash.hexdigest(),
                     'all_exact_supplied_subset_inequalities': True,
                     'all_visible_in_exact_MI_forward_root_scope': True}
    times['all_returned_subset_expression_scope_checks_s'] = time.perf_counter()-check_started

    def remaining_forward():
        for group in groups:
            name = source.vars[group[0]].name
            lower = forward.le(lower_subset(group), expect=Expr(0, {j: Fraction(-1) for j in group}))
            upper = subset_facts[agg_packing[group[0]], frozenset(group)]
            forward.check('variable.lower['+name+']', lower)
            forward.check('variable.upper['+name+']', upper)
        fact = forward.le([(forward.lower(j), source.objective.terms[j]) for j in sorted(free)] +
                          [(fixed_facts[source.vars[j].name], -source.objective.terms.get(j, 0)) for j in forced],
                          expect=objective_delta)
        forward.check('objective.non_increasing', fact)
        for name, (control, old_m, new_m) in tighten.items():
            premises = [((forward.upper(subset[0]) if t is None else subset_facts[t, frozenset(subset)]), 1)
                        for t, subset in covers[name]]
            positive = {j for j, coefficient in source.row(name).expr.terms.items() if coefficient == 1}
            bound = forward.le(premises, expect=Expr(-new_m, {j: Fraction(1) for j in positive}))
            goal = Expr(0, {**{j: Fraction(1) for j in positive}, control: Fraction(-new_m)})
            old = forward.row(name)
            fact = forward.cases(source.var(control), kind='Le', expect=goal,
                left=lambda b, a, old=old, old_m=old_m, new_m=new_m, goal=goal: b.le([(old, 1), (a, old_m-new_m)], expect=goal),
                right=lambda b, a, bound=bound, new_m=new_m, goal=goal: b.le([(bound, 1), (a, new_m)], expect=goal))
            forward.check('row.upper['+name+']', fact)
    measured('aggregation_objective_and_gate_cases_s', remaining_forward)

    def reverse_finish(builder):
        for goal in builder.missing():
            assert goal.label.startswith('row.upper[')
            name = goal.label[len('row.upper['):-1]
            if name in tighten:
                control, old_m, new_m = tighten[name]
                fact = builder.le([(builder.row(name), 1), (builder.lower(source.vars[control].name), old_m-new_m)],
                                  expect=goal.expression)
            else:
                assert name in leaf_rows | {'c1200'}
                fact = builder.box_le(goal.expression)
            builder.check(goal.label, fact)
        builder.complete()
    measured('MI_reverse_supplied_bounds_and_completion_s', reverse_finish, reverse)
    measured('LP_reverse_supplied_bounds_and_completion_s', reverse_finish, reverse_lp)
    measured('MI_forward_completion_s', forward.complete)
    phase = 'materialize'
    certificate = measured('certificate_materialize_s', proof.certificate)
    request = measured('request_materialize_s', proof.request)
    assert request == supplied_request
    phase = 'serialization_and_binding'
    paths = measured('serialization_compile_and_whole_artifact_binding_s', compile_certificate,
                     source, target, certificate, request, destination, kernel=kernel,
                     committed_model=ORIGINAL / 'output/reformulated.mps')
    phase = 'native_verify'
    receipt = measured('native_verify_process_wall_s', kernel.verify,
                       paths['source'], paths['target'], paths['proof'], paths['request'])
    assert receipt['status'] == 'VERIFIED' and receipt['claims'] == 3
    assert receipt['statistics']['obligations'] == 522056
    delivery = json.loads((destination / 'delivery.json').read_text())
    assert delivery['artifact_binding']['status'] == 'MATCHED'
    for role in ['source', 'target', 'request', 'committed_model']:
        original_name = {'source': 'output/source.mcm', 'target': 'output/target.mcm',
                         'request': 'output/request.json', 'committed_model': 'output/reformulated.mps'}[role]
        assert delivery['artifacts'][role]['sha256'] == EXPECTED[original_name]
    receipt['artifacts'] = delivery['artifacts']
    receipt['request_summary'] = delivery['request_summary']
    receipt['artifact_audit'] = delivery['artifact_binding']
    (destination / 'verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
    times['total_measured_execution_s'] = time.perf_counter()-total_started
    native_serialization_s = sum(call['wall_s'] for call in native_calls if call['phase'] == 'serialization_and_binding')
    times['serialization_binding_python_IO_excluding_native_processes_s'] = (
        times['serialization_compile_and_whole_artifact_binding_s']-native_serialization_s)

    # Outside all measured phases: independently compare every original Return
    # map with the new complete maps. This intentionally reads the original
    # certificate only after native verification; it is not proof authoring time.
    oracle_started = time.perf_counter()
    old_certificate = json.loads((ORIGINAL / 'output/certificate.json').read_text())
    assert old_certificate['claims'] == certificate['claims'] == supplied_request['claims']
    maps_hash = hashlib.sha256()
    map_dimensions = []
    for index in range(3):
        old = old_certificate['blocks'][index]['end']['Return']['map']
        new = certificate['blocks'][index]['end']['Return']['map']
        assert old == new
        map_dimensions.append(len(new))
        maps_hash.update(json.dumps(new, separators=(',', ':')).encode()+b'\n')
    assert map_dimensions == [46219, 48417, 48417]
    del old_certificate
    oracle_seconds = time.perf_counter()-oracle_started
    identity = {'original_complete_Request_exact': True, 'all_original_Return_maps_exact': True,
                'map_dimensions': map_dimensions, 'maps_sha256': maps_hash.hexdigest(),
                'claims': 3, 'observations_per_claim': 45017, 'obligations': 522056,
                'source_target_request_committed_original_bytes_exact': True}
    if args.arm == 'helper':
        reference_path = WORK / 'handwritten/result.json'
        reference = json.loads(reference_path.read_text())
        assert reference['status'] == 'VERIFIED' and reference['package_checkpoint'] == CHECKPOINT
        assert reference['subset_fact_checks'] == subset_checks
        assert reference['fixed_proof_identity'] == identity
    for name, expected in {**EXPECTED, **additional_hashes}.items():
        assert digest(ORIGINAL / name) == expected, 'Original artifact changed: '+name
    result = {'schema': 'provided-witness-proof-regression-v1', 'arm': args.arm, 'status': 'VERIFIED',
              'not_fresh_Agent_acceptance': True, 'not_solver_or_nomf_comparison': True,
              'purpose': 'Only supplied packing-subset proof elaboration changes; final target/maps/full scope are fixed.',
              'package_checkpoint': CHECKPOINT, 'package': str(package), 'package_hashes': package_hashes,
              'native_sha256': NATIVE_SHA, 'times': times, 'native_calls': native_calls,
              'post_measurement_full_original_map_oracle_s': oracle_seconds,
              'subset_fact_checks': subset_checks, 'fixed_proof_identity': identity,
              'verification_statistics': receipt['statistics'], 'verification_native_total_us': receipt['total_us'],
              'artifact_binding': delivery['artifact_binding'], 'artifacts': delivery['artifacts'],
              'python_parent_peak_RSS': {'value': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'unit': 'bytes on Darwin', 'scope': 'Python parent only, not process-tree peak', 'acceptance_gate': False},
              'handwritten_dyadic_facts': len(dyadic_facts),
              'original_artifacts_unchanged_after_execution': True,
              'additional_original_sha256_at_execution': additional_hashes,
              'original_certificate_bytes_identical': digest(destination / 'certificate.json') == additional_hashes['output/certificate.json'],
              'original_RPX_bytes_identical': delivery['artifacts']['proof']['sha256'] == EXPECTED['output/proof.rpx']}
    (destination / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    emit('complete', arm=args.arm, status='VERIFIED', result=str(destination / 'result.json'))
    proof.close()
    source.close()
    target.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
