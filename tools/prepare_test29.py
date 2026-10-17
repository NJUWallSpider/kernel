#!/usr/bin/env python3
"""Replay the actual support quotient with native exact MI-OPT directions."""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, sha
from prepare_test57 import substitute
from prepare_native import compile_case, make_proof


def zero_extension(a, b, forward_builder, reverse_builder, zeros, forward_rows, reverse_rows):
    forward = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]
    reverse = [expression(0, {b['var_index'][v['name']]: 1}) if v['name'] in b['var_index']
               else expression() for v in a['vars']]
    assert set(zeros) == set(range(len(a['vars']))) - {next(iter(e[1])) for e in forward}
    obligations = {}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        builder = reverse_builder if back else forward_builder
        checks = []
        for v, e in zip(out['vars'], mapping):
            if not e[1]:
                assert v['integer'] and v['lower'] == 0 and v['upper'] == 1
                checks.extend(['Exact', 'Exact', 'Exact'])
                continue
            j = next(iter(e[1]))
            assert v == inp['vars'][j] and v['integer']
            assert v['lower'] == 0 and v['upper'] == 1
            checks.extend([{'VarLower': j}, {'VarUpper': j}, {'VarInt': j}])
        checks.extend((reverse_rows if back else forward_rows)[row['name']] for row in out['rows'])
        diff = plus(substitute(out['objective'], mapping), inp['objective'], -1)
        if back:
            assert diff == expression()
            checks.append('Exact')
        else:
            checks.append(builder.prove('Eq', diff,
                                        [[zeros[i], c] for i, c in diff[1].items()]))
        builder.finish(mapping, checks)
        obligations['forward' if not back else 'reverse'] = len(checks)
    return {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
            'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
            'zero_variables': len(zeros), 'directions': 2,
            'obligations_by_direction': obligations}


def quotient(a, b, h, case):
    proof, forward_builder, reverse_builder = make_proof(a, b)
    f = forward_builder
    r = reverse_builder
    zeros = {}
    deductions = h['zero_deductions'] if case == 29 else h['zero_derivations']
    for d in deductions:
        head = a['var_index'][d['variable']]
        ref = row_ref(a, d['row'] if case == 29 else d['original_support_row'])
        e = f.refexpr(ref)
        assert e[0] == 0 and e[1][head] == 1 and all(c == -1 for i, c in e[1].items() if i != head)
        support = set(e[1]) - {head}
        if support <= zeros.keys():
            upper = f.lin('Le', [[ref, 1]] + [[zeros[i], 1] for i in sorted(support)],
                          expression(0, {head: 1}))
            zeros[head] = f.eqpair(upper, {'VarLower': head})
            continue
        groups = defaultdict(set)
        prior = []
        for reason in d['support_reasons']:
            i = a['var_index'][reason['variable']]
            if reason['kind'] == 'earlier_zero':
                assert i in zeros
                prior.append(i)
            else:
                groups[reason['equality']].add(i)
        assert set(prior) | set().union(*groups.values()) == support
        bounds = []
        for rn, selected in groups.items():
            rr = row_ref(a, rn)
            ee = f.refexpr(rr)
            assert ee[0] == -1 and all(c == 1 for c in ee[1].values())
            assert selected | {head} <= ee[1].keys()
            bound = f.lin('Le', [[rr, 1]] + [[{'VarLower': i}, 1]
                                           for i in sorted(set(ee[1]) - selected - {head})],
                          expression(-1, {i: 1 for i in selected | {head}}))
            bounds.append(bound)

        def left(p, assumption, head=head):
            return {'Witness': p.eqpair(assumption, {'VarLower': head})}

        def right(p, assumption, ref=ref, prior=prior, bounds=bounds):
            terms = ([[ref, 1]] + [[zeros[i], 1] for i in prior] +
                     [[bound, 1] for bound in bounds] + [[assumption, len(bounds) + 1]])
            return {'Absurd': p.lin('Le', terms, expression(1))}

        zeros[head] = f.cases('Eq', expression(0, {head: 1}), expression(0, {head: 1}),
                              integer={'VarInt': head}, left=left, right=right)
    retained = {a['var_index'][v['name']] for v in b['vars']}
    assert retained | zeros.keys() == set(range(len(a['vars'])))
    residual = {}
    rowlookup = {}
    for row in a['rows']:
        ref = row_ref(a, row['name'])
        e = f.refexpr(ref)
        wanted = expression(e[0], {i: c for i, c in e[1].items() if i in retained})
        kind = f.kind(ref)
        residual[row['name']] = f.prove(kind, wanted,
                                        [[ref, 1]] + [[zeros[i], -c]
                                                      for i, c in e[1].items() if i in zeros])
        if row['sense'] == 'L':
            heads = [i for i, c in wanted[1].items() if c == 1]
            if heads:
                assert len(heads) == 1
                head = heads[0]
                rowlookup[head, frozenset(set(wanted[1]) - {head})] = row['name']
    classes = h['balance_classes'] if case == 29 else [
        {'name': d['name'], 'left_equality': d['left_group'],
         'right_equality': d['right_group'], 'positive_variables': d['left_variables'],
         'negative_variables': d['right_variables'], 'omitted': not d['retained']}
        for d in h['support_blocks']]
    balances = {}
    rowclass = {}
    byedge = defaultdict(list)
    for d in classes:
        H = {a['var_index'][v] for v in d['positive_variables']}
        S = {a['var_index'][v] for v in d['negative_variables']}
        assert H and S and not H & S

        def direction(A, B, group):
            rows = [rowlookup[i, frozenset(B)] for i in sorted(A)]
            for rn in rows:
                assert rn not in rowclass
                rowclass[rn] = (d['name'], A, B)
            aggregate = f.lin('Le', [[residual[rn], 1] for rn in rows],
                              expression(0, {**{i: 1 for i in A}, **{i: -len(A) for i in B}}))
            base = residual[group]
            ee = f.refexpr(base)
            assert ee[0] == -1 and A <= ee[1].keys() and all(c == 1 for c in ee[1].values())
            upper = f.lin('Le', [[base, 1]] + [[{'VarLower': i}, 1]
                                              for i in sorted(set(ee[1]) - A)],
                          expression(-1, {i: 1 for i in A}))
            split = expression(0, {i: 1 for i in B})
            integer = f.lin('Int', [[{'VarInt': i}, 1] for i in sorted(B)], split)
            wanted = expression(0, {**{i: 1 for i in A}, **{i: -1 for i in B}})
            def left(p, s, aggregate=aggregate, wanted=wanted, weight=len(A) - 1):
                terms = [[aggregate, 1]] + ([[s, weight]] if weight else [])
                return {'Witness': p.lin('Le', terms, wanted)}

            def right(p, s, upper=upper, wanted=wanted):
                return {'Witness': p.lin('Le', [[upper, 1], [s, 1]], wanted)}

            return f.cases('Le', wanted, split, integer=integer, left=left, right=right)

        balances[d['name']] = f.eqpair(direction(H, S, d['left_equality']),
                                       direction(S, H, d['right_equality']))
        byedge[d['left_equality'], d['right_equality']].append(d)
    forward = {}
    rename_to_a = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]
    for row in b['rows']:
        rn = row['name']
        ref = balances[rn] if rn in balances else residual[rn]
        assert f.refexpr(ref) == substitute(r.refexpr(row_ref(b, rn)), rename_to_a)
        forward[rn] = ref
    restored = {rn: row_ref(b, rn) for rn in b['row_index']}
    if case == 85:
        for rn, terms in h['removed_original_equalities'].items():
            restored[rn] = r.lin('Eq', [[row_ref(b, n), c] for n, c in sorted(terms.items())])
    for edge, ds in byedge.items():
        omitted = [d for d in ds if d['omitted']]
        assert len(omitted) == 1
        d = omitted[0]
        restored[d['name']] = r.lin(
            'Eq', [[restored[edge[0]], 1], [restored[edge[1]], -1]] +
            [[restored[x['name']], -1] for x in ds if not x['omitted']])
    positives = {d['name']: {a['var_index'][v] for v in d['positive_variables']}
                 for d in classes}
    reverse = {}
    mapping = [expression(0, {b['var_index'][v['name']]: 1}) if v['name'] in b['var_index']
               else expression() for v in a['vars']]
    for row in a['rows']:
        rn = row['name']
        ref = row_ref(a, rn)
        wanted = substitute(f.refexpr(ref), mapping)
        if row['sense'] == 'E':
            check = restored[rn]
            assert r.refexpr(check) == wanted
        elif rn in rowclass:
            cn, A, B = rowclass[rn]
            head = next(i for i, c in f.refexpr(residual[rn])[1].items() if c == 1)
            sign = 1 if head in positives[cn] else -1
            terms = ([[restored[cn], sign]] +
                     [[{'VarLower': b['var_index'][a['vars'][i]['name']]}, 1]
                      for i in sorted(A - {head})])
            check = r.prove('Le', wanted, terms)
        else:
            check = r.prove('Le', wanted,
                            [[{'VarLower': i}, -c] for i, c in wanted[1].items()],
                            constant=wanted[0])
        reverse[rn] = check
    counts = zero_extension(a, b, f, r, zeros, forward, reverse)
    counts.update(reciprocal_blocks=len(classes),
                  omitted_blocks=sum(d['omitted'] for d in classes))
    return proof, counts


def execute(case, prepare, script):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path(f'cases/test{case}'))
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    inventory = Path(__file__).resolve().parent.parent / 'audit/corpus_inventory.json'
    entry = next(e for e in json.loads(inventory.read_text())['cases']
                 if e['case_id'] == f'test{case}')
    run = Path(entry['run_directory']) if args.run is None else args.run.resolve()
    source = run / entry['source_models'][0]['path']
    target = run / entry['final_target_models'][0]['path']
    audit = run / 'output/audit.json'
    assert sha(source) == entry['source_models'][0]['sha256']
    assert sha(target) == entry['final_target_models'][0]['sha256']
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id=f'test{case}', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {
                                        'path': str(Path(script).resolve()),
                                        'sha256': sha(Path(script))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': record['case_id'], 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    execute(29, lambda a, b, h: quotient(a, b, h, 29), __file__)
