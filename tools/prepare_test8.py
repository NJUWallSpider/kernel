#!/usr/bin/env python3
"""Actual LP pair: complete integer identity and relaxation tightening.

The certificate is the native two-direction MI-OPT proof; the legacy strictness
point and LP-side claims are no longer part of the proof.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import json
import time
from audit_menus import lp_model
from prepare_affine import row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_native import compile_case, make_proof


def cases_le(builder, wanted, variable, left, right):
    return builder.cases('Le', wanted, expression(0, {variable: 1}),
                         integer={'VarInt': variable}, left=left, right=right)


def prepare(a, b):
    n = len(a['vars'])
    assert (n, len(a['rows']), len(b['vars']), len(b['rows'])) == (4914, 13206, 4914, 12450)
    ids = [a['var_index'][v['name']] for v in b['vars']]
    rev = [b['var_index'][v['name']] for v in a['vars']]

    def rename(e, indices):
        return expression(e[0], {indices[i]: c for i, c in e[1].items()})

    assert all(a['vars'][i] == b['vars'][j] for j, i in enumerate(ids)) and \
        rename(b['objective'], ids) == a['objective']
    resources = [r for r in a['rows'] if r['rhs'] == 3 and
                 all(not a['vars'][i]['integer'] and c == 1 for i, c in r['terms'].items())]
    incident = defaultdict(list)
    for r in resources:
        for i in r['terms']:
            incident[i].append(r)
    pairs = {frozenset(r['terms']): r['name'] for r in a['rows']
             if r['rhs'] == 1 and len(r['terms']) == 2 and
             all(a['vars'][i]['integer'] and c == 1 for i, c in r['terms'].items())}
    gates = {r['name']: r for r in a['rows'] if r['rhs'] == 1200}
    links = {r['name']: r for r in a['rows'] if r['rhs'] == 0}
    assert len(resources) == 2646 and len(pairs) == 4977 and len(gates) == len(links) == 2457
    deleted = (set(a['row_index']) - set(b['row_index']) -
               {r['name'][6:] for r in b['rows'] if r['name'].startswith('tight_')})
    deleted_gates = deleted & set(gates)
    deleted_cards = deleted - deleted_gates
    assert len(deleted_gates) == 441 and len(deleted_cards) == 315

    proof, f, r = make_proof(a, b)
    cache = {}

    def restricted(p, model, row, support, indices=None):
        actual = {model['var_index'][a['vars'][i]['name']] for i in support}
        rr = model['rows'][model['row_index'][row['name']]]
        key = (row['name'], frozenset(actual))
        if p is f and key in cache:
            return cache[key]
        terms = ([[row_ref(model, row['name']), 1]] +
                 [[{'VarLower': i}, 1] for i in sorted(set(rr['terms']) - actual)])
        ref = p.lin('Le', terms, expression(-3, {i: 1 for i in actual}))
        if p is f:
            cache[key] = ref
        return ref

    activity = {i: restricted(f, a, incident[i][0], {i})
                for i in range(n) if not a['vars'][i]['integer']}
    forward = {}
    covers = {}
    for name, row in links.items():
        x = next(i for i, c in row['terms'].items() if c == 1)
        y = next(i for i, c in row['terms'].items() if c == -8)
        wanted = expression(0, {x: 1, y: -3})
        forward['tight_' + name] = cases_le(
            f, wanted, y,
            lambda p, z, row=row: p.lin('Le', [[row_ref(a, row['name']), 1], [z, 5]], wanted),
            lambda p, o, x=x: p.lin('Le', [[activity[x], 1], [o, 3]], wanted))
    for name, row in gates.items():
        y = next(i for i, c in row['terms'].items() if c == 1197)
        support = set(row['terms']) - {y}
        if name in deleted_gates:
            cover = next(rr for rr in incident[min(support)] if support <= set(rr['terms']))
            covers[name] = [(cover, support)]
            continue
        target = b['rows'][b['row_index']['tight_' + name]]
        u = target['rhs']
        assert u in (6, 9, 12)
        remaining = set(support)
        chosen = []
        while remaining:
            candidates = {rr['name']: rr for i in remaining for rr in incident[i]}
            rr = max(candidates.values(),
                     key=lambda rr: (len(remaining & set(rr['terms'])), -a['row_index'][rr['name']]))
            part = remaining & set(rr['terms'])
            chosen.append((rr, part))
            remaining -= part
        assert len(chosen) * 3 <= u, (name, len(chosen), u)
        bound = f.lin('Le', [[restricted(f, a, rr, part), 1] for rr, part in chosen],
                      expression(-u, {i: 1 for i in support}), constant=3 * len(chosen) - u)
        wanted = rename(row_fact(target, 'RowUpper'), ids)
        forward['tight_' + name] = cases_le(
            f, wanted, y,
            lambda p, z: p.lin('Le', [[bound, 1], [z, u - 3]], wanted),
            lambda p, o, row=row: p.lin('Le', [[row_ref(a, row['name']), 1], [o, 1200 - u]], wanted))

    def matching(support):
        if not support:
            return []
        i = min(support)
        best = [({'VarUpper': i}, 1)] + matching(support - {i})
        for j in sorted(support - {i}):
            pair = frozenset((i, j))
            if pair in pairs:
                candidate = [(pairs[pair], 1)] + matching(support - {i, j})
                if len(candidate) < len(best):
                    best = candidate
        return best

    cardcovers = {name: matching(set(a['rows'][a['row_index'][name]]['terms']))
                  for name in deleted_cards}
    assert all(len(x) <= 3 for x in cardcovers.values())

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = r if back else f
        indices = rev if back else ids
        checks = []
        for j, v in enumerate(out['vars']):
            i = indices[j]
            for key, field in [('VarLower', 'lower'), ('VarUpper', 'upper')]:
                if v[field] is not None:
                    checks.append({key: i})
            if v['integer']:
                checks.append({'VarInt': i})
        for row in out['rows']:
            name = row['name']
            wanted = rename(row_fact(row, 'RowUpper'), indices)
            if not back and name.startswith('tight_'):
                ref = forward[name]
            elif back and name in deleted_gates:
                rr, support = covers[name][0]
                y = next(i for i, c in row['terms'].items() if c == 1197)
                ref = builder.lin('Le', [[restricted(builder, b, rr, support), 1],
                                         [{'VarUpper': rev[y]}, 1197]], wanted)
            elif back and name in deleted_cards:
                terms = [[row_ref(b, x) if isinstance(x, str) else {'VarUpper': rev[x['VarUpper']]}, c]
                         for x, c in cardcovers[name]]
                ref = builder.lin('Le', terms, wanted, constant=len(terms) - 3)
            elif back and name in gates:
                tr = b['rows'][b['row_index']['tight_' + name]]
                y = next(i for i, c in row['terms'].items() if c == 1197)
                ref = builder.lin('Le', [[row_ref(b, 'tight_' + name), 1],
                                         [{'VarUpper': rev[y]}, 1200 - tr['rhs']]], wanted)
            elif back and name in links:
                y = next(i for i, c in row['terms'].items() if c == -8)
                ref = builder.lin('Le', [[row_ref(b, 'tight_' + name), 1],
                                         [{'VarLower': rev[y]}, 5]], wanted)
            else:
                ref = row_ref(inp, name)
            assert builder.refexpr(ref) == wanted
            checks.append(ref)
        checks.append('Exact')
        builder.finish([expression(0, {i: 1}) for i in indices], checks)

    return proof, {'source_variables': n, 'target_variables': n,
                   'source_rows': 13206, 'target_rows': 12450,
                   'tightened_links': 2457, 'tightened_gates': 2016,
                   'deleted_resource_gates': 441, 'deleted_cardinalities': 315,
                   'shared_resource_restrictions': len(cache), 'directions': 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('cases/test8'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = Path('/Users/bhz/Code/reform_test/runs/test8-20261003-213957')
    source = run / 'input/model.lp'
    target = run / 'output/reformulated.lp'
    audit = run / 'output/report.md'
    proof, counts = prepare(lp_model(source), lp_model(target))
    record = compile_case(proof, args.out, case_id='test8', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test8', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
