#!/usr/bin/env python3
"""Native test55 auxiliary projection and local binary activation bounds.

The forward direction uses only actual row combinations, integer rounding-free
case splits and the committed activation capacities.  The reverse direction
reconstructs every removed auxiliary as ``x/480`` and checks the complete
source model.  No SparseBuilder, raw step dictionary, RPA write, request file,
subprocess, point claim, or LP duplicate is used.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, mul, row_fact, substitute, sha
from prepare_test24 import split
from prepare_native import compile_case, make_proof


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == (3872, 3904, 2848, 2880)
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    forward = [expression(0, {i: 1}) for i, j in common]
    assert all(a['vars'][i] == b['vars'][j] for i, j in common)

    proof, f, r = make_proof(a, b)
    modified = {}
    deleted = {}
    ys = {}
    for d in h['blocks']:
        y = a['var_index'][d['removed_column']]
        x = a['var_index'][d['x']]
        us = [a['var_index'][v] for v in d['binary_columns']]
        M = F(d['new_M'])
        old = F(d['old_M'])
        assert old == 480 and 0 < M <= old and len(us) in (1, 3)
        assert not a['vars'][x]['integer'] and not a['vars'][y]['integer']
        assert a['vars'][x]['lower'] == a['vars'][y]['lower'] == 0
        assert a['vars'][y]['upper'] is None and not a['objective'][1].get(y, 0)
        assert all(a['vars'][u]['integer'] and a['vars'][u]['lower'] == 0 and
                   a['vars'][u]['upper'] == 1 for u in us)
        vub = row_ref(a, d['removed_row'])
        assert f.refexpr(vub) == expression(0, {x: 1, y: -old})
        assert len(d['modified_rows']) == len(us)
        links = {}
        for rn, u in zip(d['modified_rows'], us):
            links[u] = row_ref(a, rn)
            assert f.refexpr(links[u]) == expression(0, {y: 1, u: -1})
            assert substitute(row_fact(b['rows'][b['row_index'][rn]], 'RowUpper'),
                              forward) == expression(0, {x: 1, u: -M})
            modified[rn] = (d, u, x, y, M)
        ys[y] = x
        deleted[d['removed_row']] = y
        if M == old:
            for rn, u in zip(d['modified_rows'], us):
                modified[rn] = f.lin('Le', [[vub, 1], [links[u], old]],
                                     expression(0, {x: 1, u: -M}))
            continue
        cc = d['capacity_certificate']
        cap = row_ref(a, cc['row'])
        row = a['rows'][a['row_index'][cc['row']]]
        ax = row['terms'][x]
        assert row['sense'] == 'L' and row['rhs'] == F(cc['rhs'])
        assert ax == F(cc['x_coefficient']) > 0
        assert all(c >= 0 and a['vars'][i]['lower'] == 0 for i, c in row['terms'].items())
        mandatory = sum(row['terms'].get(u, F(0)) for u in us)
        assert mandatory == F(cc['mandatory']) and ax * M + mandatory == row['rhs']
        assert M == F(cc['upper'])

        for rn, targetu in zip(d['modified_rows'], us):
            wanted = expression(0, {x: 1, targetu: -M})

            def recurse(p, k, fixed):
                if k == len(us):
                    terms = [[cap, 1 / ax]]
                    for i, c in row['terms'].items():
                        if i == x:
                            continue
                        if i in fixed:
                            terms.append([fixed[i], -c / ax])
                        else:
                            terms.append([{'VarLower': i}, c / ax])
                    active = p.lin('Le', terms, expression(-M, {x: 1}))
                    return p.lin('Le', [[active, 1], [fixed[targetu], -M]], wanted)
                u = us[k]

                def zero(c, assumption):
                    # A single inactive actual activation forces x=0.
                    xzero = c.lin('Le', [[vub, 1], [links[u], old],
                                         [assumption, old]], expression(0, {x: 1}))
                    return c.lin('Le', [[xzero, 1], [{'VarLower': targetu}, M]], wanted)

                def one(c, assumption):
                    assigned = dict(fixed)
                    assigned[u] = c.eqpair({'VarUpper': u}, assumption)
                    return recurse(c, k + 1, assigned)

                return split(p, 'Le', wanted, expression(0, {u: 1}),
                             {'VarInt': u}, [zero, one])

            modified[rn] = recurse(f, 0, {})

    assert len(ys) == 1024 and len(modified) == 1536 and len(deleted) == 1024
    assert {i for i, v in enumerate(a['vars']) if v['name'] not in b['var_index']} == set(ys)

    forward_checks = []
    for i, j in common:
        v = b['vars'][j]
        if v['lower'] is not None:
            forward_checks.append({'VarLower': i})
        if v['upper'] is not None:
            forward_checks.append({'VarUpper': i})
        if v['integer']:
            forward_checks.append({'VarInt': i})
    for row in b['rows']:
        rn = row['name']
        typ = next(iter(row_ref(b, rn)))
        wanted = substitute(row_fact(row, typ), forward)
        ref = modified[rn] if rn in modified else row_ref(a, rn)
        assert f.refexpr(ref) == wanted
        forward_checks.append(ref)
    assert substitute(b['objective'], forward) == a['objective']
    forward_checks.append('Exact')
    f.finish(forward, forward_checks)

    reverse = []
    for i, v in enumerate(a['vars']):
        if i in ys:
            reverse.append(expression(0, {b['var_index'][a['vars'][ys[i]]['name']]: F(1, 480)}))
        else:
            reverse.append(expression(0, {b['var_index'][v['name']]: 1}))
    auditlinks = {rn: d for d in h['blocks'] for rn in d['modified_rows']}
    checks = []
    for i, v in enumerate(a['vars']):
        j = next(iter(reverse[i][1]))
        if i in ys:
            checks.append(r.lin('Le', [[{'VarLower': j}, F(1, 480)]],
                                mul(reverse[i], -1)))
        else:
            if v['lower'] is not None:
                checks.append({'VarLower': j})
            if v['upper'] is not None:
                checks.append({'VarUpper': j})
            if v['integer']:
                checks.append({'VarInt': j})
    for row in a['rows']:
        rn = row['name']
        typ = next(iter(row_ref(a, rn)))
        wanted = substitute(row_fact(row, typ), reverse)
        if rn in deleted:
            assert wanted == expression()
            checks.append('Exact')
        elif rn in auditlinks:
            d = auditlinks[rn]
            M = F(d['new_M'])
            u = next(i for i, c in wanted[1].items() if c == -1)
            checks.append(r.lin('Le', [[row_ref(b, rn), F(1, 480)],
                                       [{'VarLower': u}, (480 - M) / 480]], wanted))
        else:
            ref = row_ref(b, rn)
            assert r.refexpr(ref) == wanted
            checks.append(ref)
    assert substitute(a['objective'], reverse) == b['objective']
    checks.append('Exact')
    r.finish(reverse, checks)

    counts = {
        'source_variables': 3872, 'target_variables': 2848,
        'source_rows': 3904, 'target_rows': 2880,
        'removed_private_continuous': 1024, 'rewritten_links': 1536,
        'strengthened_links': 1024, 'activated_capacity_certificates': 512,
        'directions': 2, 'legacy_claims_collapsed': 3,
        'legacy_continuous_reverse_omitted': 1,
        'retained_coordinate_observations_omitted': len(common),
        'obligations_by_direction': [len(forward_checks), len(checks)],
    }
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test55-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test55'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/model.mps'
    audit = run / 'output/audit.json'
    inventory = next(c for c in json.loads(
        Path('audit/corpus_inventory.json').read_text())['cases']
        if c['case_id'] == 'test55')
    assert sha(source) == inventory['source_models'][0]['sha256']
    assert sha(target) == inventory['final_target_models'][0]['sha256']
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test55', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test55', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
