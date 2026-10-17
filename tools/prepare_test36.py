#!/usr/bin/env python3
"""Test36 blocker receipt for the all-source-optimizer caller contract.

The native Proof API certifies exactly two MI-OPT directions: one forward
nonincreasing map and one reverse nonincreasing map.  It has no caller-bound
universal optimizer-exclusion claim, so the historical all-optimizer statement
is not fabricated here.  The untrusted analysis helpers remain for review; no
RPA, request, point, or improvement certificate is written and no kernel
subprocess is invoked.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_test21 import substitute


def reverse_identity(a, b):
    """Complete retained-coordinate target-to-source zero-extension analysis."""
    reverse = [expression(0, {b['var_index'][v['name']]: 1})
               if v['name'] in b['var_index'] else expression() for v in a['vars']]
    checks = []
    for v, e in zip(a['vars'], reverse):
        i = next(iter(e[1])) if e[1] else None
        if v['lower'] is not None:
            checks.append({'VarLower': i} if i is not None else 'Exact')
        if v['upper'] is not None:
            checks.append({'VarUpper': i} if i is not None else 'Exact')
        if v['integer']:
            checks.append({'VarInt': i})
    for row in a['rows']:
        ref = row_ref(b, row['name'])
        assert substitute(row_fact(row, next(iter(ref))), reverse) == \
            row_fact(b['rows'][b['row_index'][row['name']]], next(iter(ref)))
        checks.append(ref)
    assert substitute(a['objective'], reverse) == b['objective']
    checks.append('Exact')
    return reverse, checks


def point_values(a, h):
    """Recompute the historical feasible zero-terminal witness from the audit."""
    values = [F(0) if v['name'] in h['certificate']['zero_binary_variables']
              else F(1) if v['integer'] else None for v in a['vars']]
    pending = list(a['rows'][1:])
    while pending:
        rest = []
        for row in pending:
            neg = [i for i, c in row['terms'].items() if c == -1]
            assert len(neg) == 1
            z = neg[0]
            pos = [i for i, c in row['terms'].items() if c == 1]
            if any(values[i] is None for i in pos):
                rest.append(row)
                continue
            values[z] = max(F(0), sum(values[i] for i in pos) - 1)
        assert len(rest) < len(pending)
        pending = rest
    return values


def blocker_receipt(a, b, h, source, target, audit, inventory):
    reverse, checks = reverse_identity(a, b)
    values = point_values(a, h)
    objective = (sum(values[i] * c for i, c in a['objective'][1].items()) + a['objective'][0]
                 if all(v is not None for v in values) else None)
    terminal = next(i for i, v in enumerate(a['vars']) if v['name'] not in b['var_index'])
    return {
        'case_id': 'test36',
        'status': 'BLOCKED',
        'blocker': {
            'kind': 'NO_NATIVE_ALL_SOURCE_OPTIMIZER_EXCLUSION_CLAIM',
            'missing_contract': ('Caller-bound universal strict-improvement/optimality '
                                 'exclusion with a condition on source terminal positivity '
                                 'or noncanonical lift.'),
            'why_existing_rules_do_not_suffice': (
                'Native Lin/Cases/Round/Feasible discharge directional obligations only. '
                'The objective obligation is nonincreasing; it does not bind strict '
                'improvement to terminal positivity.  The fixed objective-level point '
                'claim used historically is absent from the native MI-OPT Proof, and here '
                'the optimum is unknown: 6425 is only a feasible upper bound.'),
            'routes_examined': [
                'Intended all-optimizer caller statement rejected as unknown Claim field.',
                'Fixed objective level cannot bind an unknown optimum; a certified feasible '
                'noncanonical positive terminal demonstrates no unrestricted '
                'terminal-integrality assertion.',
            ],
        },
        'reachable_evidence': (
            'NON-ACCEPTANCE analysis only: complete objective-equal retained-coordinate '
            'zero extension and one source feasible witness with all 200 terminal '
            'coordinates zero.  These observations do not imply the all-optimizer '
            'contract, and no proof is emitted.'),
        'source': {'path': str(source), 'sha256': sha(source)},
        'target': {'path': str(target), 'sha256': sha(target)},
        'audit': {'path': str(audit), 'sha256': sha(audit)},
        'inventory_entry': {
            'source_sha256': inventory['source_models'][0]['sha256'],
            'target_sha256': inventory['final_target_models'][0]['sha256'],
        },
        'analysis_counts': {
            'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
            'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
            'terminal_coordinates': 200,
            'reverse_checks': len(checks),
            'zero_terminal_witness_objective': str(objective),
            'positive_terminal_probe': (str(values[terminal] + F(1, 4850))
                                       if values[terminal] is not None else None),
        },
        'native_portability': {
            'forward_minimum_preservation': 'prepare_test36_full.py',
            'reverse_objective_recovery': 'prepare_test36_full.py',
            'strict_all_optimizer_exclusion': 'NOT_REPRESENTABLE',
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test36-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test36'))
    args = parser.parse_args()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    inventory = json.loads(Path('audit/corpus_inventory.json').read_text())
    entry = next(c for c in inventory['cases'] if c['case_id'] == 'test36')
    for path, key in [(source, 'source_models'), (target, 'final_target_models')]:
        assert str(path) == str(run / entry[key][0]['path'])
        assert sha(path) == entry[key][0]['sha256']
    a, b = parse_mps(source), parse_mps(target)
    h = json.loads(audit.read_text())
    receipt = blocker_receipt(a, b, h, source, target, audit, entry)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'blocker.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': 'test36', 'status': receipt['status'],
                      'blocker': receipt['blocker']['kind'],
                      'analysis_counts': receipt['analysis_counts']}, indent=2))


if __name__ == '__main__':
    main()
