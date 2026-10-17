#!/usr/bin/env python3
"""Native test70 aggregate-gate tightening with explicit exact cover proofs.

One implementation serves the three historical variants through ``mode``:
``restricted`` partitions each gate support among its cover rows, ``naive``
expands every cover with per-coordinate excess, and ``subset`` groups those
excess terms into chunked nonnegative subsets. Only the two MI-OPT directions
are emitted; the legacy LP duplicate is outside that contract.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import Counter
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_test19 import cases_le
from prepare_native import compile_case, make_proof


def prepare(a, b, h, mode='restricted'):
    assert mode in ('restricted', 'naive', 'subset')
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == (48417, 2187, 48417, 2187)
    assert set(a['var_index']) == set(b['var_index']) and set(a['row_index']) == set(b['row_index'])
    forward = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]
    reverse = [expression(0, {b['var_index'][v['name']]: 1}) for v in a['vars']]
    common = [[next(iter(e[1])), j] for j, e in enumerate(forward)]
    forward_ids = [next(iter(e[1])) for e in forward]
    reverse_ids = [next(iter(e[1])) for e in reverse]

    def rename(e, ids):
        return e[0], {ids[i]: c for i, c in e[1].items()}
    for i, j in common:
        assert a['vars'][i] == b['vars'][j] and a['vars'][i]['integer'] and \
            a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] == 1
    assert rename(b['objective'], forward_ids) == a['objective']
    changes = {d['row']: d for d in h['changes']}
    assert len(changes) == 1975
    proof, f, r = make_proof(a, b)
    packing = {}
    for d in h['packing_sources']:
        ref = row_ref(a, d['row'])
        row = a['rows'][a['row_index'][d['row']]]
        assert row['sense'] == 'E'
        if d['kind'] == 'unit_assignment_equality':
            assert row['rhs'] == 1 and all(c == 1 for c in row['terms'].values())
            packing[d['row']] = (ref, set(row['terms']))
        else:
            negative = [i for i, c in row['terms'].items() if c == -1]
            assert len(negative) == 1 and row['rhs'] == 0
            z = negative[0]
            support = {i for i, c in row['terms'].items() if c == 1}
            assert len(support) + 1 == len(row['terms'])
            packing[d['row']] = (f.lin('Le', [[ref, F(1)], [{'VarUpper': z}, F(1)]],
                                      expression(-1, {i: 1 for i in support})), support)
    gatefacts = {}
    subset_cache = {}
    naive_cancellations = 0
    shared_cancellations = 0

    def nonnegative_subset(base, width, mask):
        assert mask and mask.bit_length() <= width
        if mask & (mask - 1) == 0:
            return {'VarLower': base + mask.bit_length() - 1}
        key = (base, width, mask)
        if key in subset_cache:
            return subset_cache[key]
        half = width // 2
        lower = mask & ((1 << half) - 1)
        upper = mask >> half
        if not lower:
            ref = nonnegative_subset(base + half, half, upper)
        elif not upper:
            ref = nonnegative_subset(base, half, lower)
        else:
            ref = f.lin('Le', [[nonnegative_subset(base, half, lower), F(1)],
                               [nonnegative_subset(base + half, half, upper), F(1)]])
        subset_cache[key] = ref
        return ref
    restricted = {}
    global_upper = {}
    parts = {}
    parent_terms = 0
    restriction_cancellations = 0
    if mode == 'restricted':
        # Partition each gate support among its actual cover rows in audit order.
        # A restricted packing bound is itself an ordinary Lin derivation. Reuse
        # its smallest earlier superset to avoid expanding huge original rows.
        restrictions = {rn: set() for rn in packing}

        def cancel_terms(indices):
            masks = {}
            for i in indices:
                masks[i // 64] = masks.get(i // 64, 0) | (1 << (i % 64))
            return [[nonnegative_subset(chunk * 64, 64, mask), F(1)]
                    for chunk, mask in sorted(masks.items())]
        for name, d in changes.items():
            control = a['var_index'][d['control']]
            support = set(a['rows'][a['row_index'][name]]['terms']) - {control}
            remaining = set(support)
            selected = []
            for rn in d['cover_rows']:
                t = frozenset(remaining & packing[rn][1])
                assert t
                remaining -= t
                restrictions[rn].add(t)
                selected.append((rn, t))
            assert remaining == {a['var_index'][n] for n in d['individual_upper_bounds']}
            parts[name] = selected
        for rn, sets in restrictions.items():
            parent_ref, parent_support = packing[rn]
            done = [(frozenset(parent_support), parent_ref)]
            for support in sorted(sets, key=lambda t: (-len(t), sorted(t))):
                if support in global_upper:
                    ref = global_upper[support]
                elif len(support) == 1:
                    ref = {'VarUpper': next(iter(support))}
                else:
                    parent, ref = next((p, r) for p, r in reversed(done) if support <= p)
                    if support != parent:
                        removed = parent - support
                        parent_terms += len(parent)
                        restriction_cancellations += len(removed)
                        ref = f.lin('Le', [[ref, F(1)]] + cancel_terms(removed),
                                    expression(-1, {i: 1 for i in support}))
                global_upper[support] = ref
                restricted[rn, support] = ref
                done.append((support, ref))
    for name, d in changes.items():
        control = a['var_index'][d['control']]
        old = -F(d['old_coefficient'])
        new = -F(d['new_coefficient'])
        ref = row_ref(a, name)
        row = a['rows'][a['row_index'][name]]
        support = set(row['terms']) - {control}
        assert row['sense'] == 'L' and row['rhs'] == 0 and row['terms'][control] == -old and \
            old == len(support) and 0 < new < old and all(row['terms'][i] == 1 for i in support)
        if mode == 'restricted':
            terms = [[restricted[rn, t], F(1)] for rn, t in parts[name]] + \
                    [[{'VarUpper': a['var_index'][vn]}, F(1)] for vn in d['individual_upper_bounds']]
        else:
            cover = Counter()
            terms = []
            for rn in d['cover_rows']:
                packed, packed_support = packing[rn]
                terms.append([packed, F(1)])
                cover.update(packed_support)
            for vn in d['individual_upper_bounds']:
                i = a['var_index'][vn]
                terms.append([{'VarUpper': i}, F(1)])
                cover[i] += 1
            assert len(d['cover_rows']) + len(d['individual_upper_bounds']) == new
            assert all(cover[i] >= 1 for i in support)
            if mode == 'naive':
                for i, c in cover.items():
                    excess = c - (1 if i in support else 0)
                    if excess:
                        terms.append([{'VarLower': i}, F(excess)])
            else:
                masks = {}
                for i, c in cover.items():
                    excess = c - (1 if i in support else 0)
                    if excess:
                        naive_cancellations += 1
                        key = (i // 64, excess)
                        masks[key] = masks.get(key, 0) | (1 << (i % 64))
                shared_cancellations += len(masks)
                for (chunk, multiplier), mask in sorted(masks.items()):
                    terms.append([nonnegative_subset(chunk * 64, 64, mask), F(multiplier)])
        if mode == 'restricted':
            assert len(terms) == new
        bound = f.lin('Le', terms, expression(-new, {i: 1 for i in support}))
        wanted = expression(0, {**{i: 1 for i in support}, control: -new})
        assert wanted == rename(row_fact(b['rows'][b['row_index'][name]], 'RowUpper'), forward_ids)
        gatefacts[name] = cases_le(f, wanted, control,
            lambda child, zero: child.lin('Le', [[ref, F(1)], [zero, old - new]], wanted),
            lambda child, one: child.lin('Le', [[bound, F(1)], [one, new]], wanted))
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = r if back else f
        checks = []
        for i, v in enumerate(out['vars']):
            j = next(iter(mapping[i][1]))
            checks.extend([{'VarLower': j}, {'VarUpper': j}, {'VarInt': j}])
        for row in out['rows']:
            n = row['name']
            typ = next(iter(row_ref(out, n)))
            wanted = rename(row_fact(row, typ), reverse_ids if back else forward_ids)
            if not back and n in changes:
                check = gatefacts[n]
                assert builder.refexpr(check) == wanted
            elif back and n in changes:
                d = changes[n]
                control = b['var_index'][d['control']]
                check = builder.lin('Le', [[row_ref(b, n), F(1)],
                                           [{'VarLower': control},
                                            F(d['new_coefficient']) - F(d['old_coefficient'])]], wanted)
            else:
                check = row_ref(inp, n)
                assert builder.refexpr(check) == wanted
            checks.append(check)
        assert rename(out['objective'], reverse_ids if back else forward_ids) == inp['objective']
        checks.append('Exact')
        builder.finish(mapping, checks)
    counts = {'source_variables': 48417, 'target_variables': 48417,
              'source_rows': 2187, 'target_rows': 2187,
              'gate_tightenings': 1975, 'packing_sources': 82, 'directions': 2,
              'mode': mode}
    if mode == 'restricted':
        counts.update(restricted_packing_bounds=len(restricted),
                      distinct_restricted_supports=len(global_upper),
                      parent_packing_terms=parent_terms,
                      restriction_cancellation_terms=restriction_cancellations,
                      subset_cache_entries=len(subset_cache))
    elif mode == 'subset':
        counts.update(naive_cancellation_refs=naive_cancellations,
                      shared_cancellation_refs=shared_cancellations,
                      subset_cache_entries=len(subset_cache))
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test70-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test70'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()), mode='restricted')
    record = compile_case(proof, args.out, case_id='test70', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {'path': str(Path(__file__).resolve()),
                                                       'sha256': sha(Path(__file__))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test70', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
