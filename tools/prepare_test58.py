#!/usr/bin/env python3
"""Test58 native-signed reverse helper and explicit forward blocker.

The historical file only ever completed the target-to-source signed direction.
A native Proof needs both MI-OPT directions, so this module exposes the reverse
construction for ``prepare_test58_full`` and records the unresolved joint
rerouting lemma instead of fabricating a forward certificate.  No RPA, request,
subprocess, local-merge certificate, point claim, or mutation is written.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha


def key(e):
    return e[0], tuple(sorted(e[1].items()))


def exact(e):
    return not e[1] and e[0] <= 0


def forward_blocker():
    """The unproved forward rerouting obligation, kept as an explicit receipt."""
    return {
        'kind': 'practical_joint_existence_gap_not_ISA_inexpressibility_theorem',
        'obligation': ('After merging paths 143 into 142 and 228 into 226, jointly '
                       'reroute within activated support, preserve all balances and '
                       'impose |F_p|<=82 Z_p without increasing activation cost. '
                       'Local arithmetic provides only |merged flow|<=164.'),
        'lemma_needed': ('For common-source nonnegative flow f with nonnegative sink '
                         'demands totaling B, choose g with identical balances, '
                         '0<=g_e<=f_e and g_e<=B on every arc, allowing loops and '
                         'disconnected circulations.'),
        'alternative_attempt': ('FlowLift commodity decomposition was inspected: '
                                'generated arc-total equalities require sum_k f[k,e]=f[e], '
                                'not <=f[e], so circulations remain and no per-commodity '
                                'or aggregate B bound is generated. SignedLift only '
                                'preserves signed net flows and activated capacities; it '
                                'cannot change balances by cycle cancellation. Per-arc '
                                'interval choices are not independent because conservation '
                                'couples them.'),
        'smallest_local_merge_counterexample': {
            'nodes': ['s', 't'],
            'arcs': [['s', 't'], ['s', 't'], ['t', 's']],
            'B': 82, 'flows': [82, 82, 82],
            'balances': {'s': 82, 't': -82},
            'merged_forward_flow': 164, 'capacity': 82,
            'circulation_free_solution': [82, 0, 0],
        },
        'qualification': ('The lemma is mathematically true by path/circulation '
                          'decomposition; existing Lin/Cases can in principle encode '
                          'explicit cycle cancellation or spanning-tree cases. No proof '
                          'of fundamental inexpressibility is claimed. A compact '
                          'complete such route was not established.'),
        'fixture_check': {
            'balances': [82, -82], 'merged_f': [164, 82], 'merged_g': [82, 0],
            'note': 'Regression arithmetic only; not an acceptance artifact.',
        },
    }


def reverse(builder, a, b, h):
    """Complete the native target-to-source SignedLift direction."""
    paths = {p['id']: p for p in h['series_paths']}
    edges = {e['id']: e for e in h['symmetric_edges']}
    decompositions = []
    for pid in h['retained_path_ids']:
        path = paths[pid]
        fi = b['var_index'][path['flow_var']]
        zi = b['var_index'][path['activation_var']]
        decompositions.append({
            'capacity': F(path['capacity']),
            'flow': expression(0, {fi: 1}),
            'activation': expression(0, {zi: 1}),
            'checks': [{'VarLower': zi}, {'VarUpper': zi}, {'VarInt': zi},
                       row_ref(b, path['upper_row']), row_ref(b, path['lower_row'])],
        })
    child = builder.signed(decompositions)
    layout = child.old_layout
    assert len(layout) == len(h['retained_path_ids'])
    mapping = [None] * len(a['vars'])
    for entry, pid in zip(layout, h['retained_path_ids']):
        path = paths[pid]
        positive = entry['positive']
        positive_activation = entry['positive_activation']
        for eid, sign in path['steps']:
            edge = edges[eid]
            for direction, k in [('forward', 0), ('reverse', 1)]:
                offset = k if sign == 1 else 1 - k
                mapping[a['var_index'][edge[direction]['x']]] = expression(0, {positive + offset: 1})
                mapping[a['var_index'][edge[direction]['y']]] = expression(
                    0, {positive_activation + offset: 1})
    for d in h['parallel_dominance']:
        for eid, _ in paths[d['removed']]['steps']:
            for direction in ('forward', 'reverse'):
                for t in ('x', 'y'):
                    mapping[a['var_index'][edges[eid][direction][t]]] = expression()
    for cut in h['bridge_cut_witnesses']:
        flow = F(cut['flow'])
        edge = edges[cut['edge_id']]
        for direction, sign in [('forward', 1), ('reverse', -1)]:
            value = max(F(0), flow * sign)
            mapping[a['var_index'][edge[direction]['x']]] = expression(value)
            mapping[a['var_index'][edge[direction]['y']]] = expression(int(value > 0))
    assert all(e is not None for e in mapping)

    eqs = {key(row_fact(row, 'RowEq')): {'RowEq': i}
           for i, row in enumerate(b['rows']) if row['sense'] == 'E'}
    omitted = child.lin('Eq', [[{'RowEq': i}, -1]
                               for i, row in enumerate(b['rows']) if row['sense'] == 'E'])
    eqs[key(child.refexpr(omitted))] = omitted

    def equal(e):
        terms = []
        reduced = e
        for entry in layout:
            ref = {'RowEq': entry['flow_row']}
            c = reduced[1].get(entry['positive'], F(0))
            if c:
                terms.append([ref, c])
                reduced = plus(reduced, child.refexpr(ref), -c)
        if reduced[1] or reduced[0]:
            if key(reduced) in eqs:
                terms.append([eqs[key(reduced)], 1])
            elif key(mul(reduced, -1)) in eqs:
                terms.append([eqs[key(mul(reduced, -1))], -1])
            else:
                raise AssertionError(('unmatched balance', reduced))
        if not terms:
            return 'Exact'
        return child.lin('Eq', terms, e)

    facts = {key(child.refexpr({'RowUpper': i})): {'RowUpper': i}
             for i, row in enumerate(child.model['rows']) if row['sense'] == 'L'}
    checks = []
    for i, v in enumerate(a['vars']):
        e = mapping[i]
        for typ, desired in [
                ('VarLower', plus(expression(v['lower']), e, -1)),
                ('VarUpper', plus(e, expression(-v['upper'])) if v['upper'] is not None else None),
                ('VarInt', e if v['integer'] else None)]:
            if desired is None:
                continue
            if not e[1]:
                checks.append('Exact')
            else:
                checks.append({typ: next(iter(e[1]))})
    for row in a['rows']:
        typ = 'RowEq' if row['sense'] == 'E' else 'RowUpper'
        wanted = substitute(row_fact(row, typ), mapping)
        checks.append(equal(wanted) if typ == 'RowEq'
                      else 'Exact' if exact(wanted) else facts[key(wanted)])
    objective = plus(substitute(a['objective'], mapping), b['objective'], -1)
    terms = []
    for entry, pid in zip(layout, h['retained_path_ids']):
        terms.append([{'RowEq': entry['flow_row'] + 1}, F(paths[pid]['cost'])])
    fixed = b['var_index']['OBJFIX']
    fix = child.eqpair({'VarUpper': fixed}, {'VarLower': fixed})
    terms.append([fix, -205])
    checks.append(child.lin('Eq', terms, objective))
    child.finish(mapping, checks)
    return {
        'source_variables': len(a['vars']), 'source_rows': len(a['rows']),
        'target_variables': len(b['vars']), 'target_rows': len(b['rows']),
        'signed_decompositions': len(decompositions),
        'checks': len(checks),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test58-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test58'))
    args = parser.parse_args()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    receipt = {
        'case_id': 'test58',
        'status': 'BLOCKED',
        'acceptance': False,
        'scope': ('The native Proof contract requires both MI-OPT directions. '
                  'Only the target-to-source SignedLift direction is portable and '
                  'is exposed through reverse(); the forward rerouting proof remains '
                  'unestablished here.'),
        'forward_blocker': forward_blocker(),
        'reverse_helper': 'reverse(builder, a, b, h)',
        'full_native_port_for_established_directions': 'prepare_test58_full.py',
        'source': {'path': str(source), 'sha256': sha(source)},
        'target': {'path': str(target), 'sha256': sha(target)},
        'audit': {'path': str(audit), 'sha256': sha(audit)},
        'counts': {
            'original_edges': 625, 'bridge_cut_equalities_checked': 199,
            'series_internal_nodes': 121, 'retained_paths': 303,
            'reverse_signed_decompositions': 303,
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'blocker.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': 'test58', 'status': 'BLOCKED',
                      'forward_blocker': receipt['forward_blocker']['kind']}, indent=2))


if __name__ == '__main__':
    main()
