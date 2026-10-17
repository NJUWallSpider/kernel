#!/usr/bin/env python3
"""Native test30 absolute-value/alias/private-binary projection proof.

The reverse direction installs one native ``IntervalLift`` over all 930 free
auxiliaries and finishes the lifted body through the direction. Only the two
MI-OPT directions are built; the legacy LP duplicate claims are dropped.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, sha
from prepare_test57 import substitute
from prepare_test54 import fact, box, exact
from prepare_native import compile_case, make_proof


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == \
        (35378, 16516, 32337, 14717)
    aliases = {a['var_index'][n]: a['var_index'][r]
               for n, r in h['alias_eliminations']['column_to_representative'].items() if n != r}
    assert len(aliases) == 620
    aux = {a['var_index'][d['variable']]: d for d in h['auxiliary_eliminations']}
    singles = {a['var_index'][n] for d in h['singleton_eliminations']
               for n in d['removed_variables']}
    removed = set(aliases) | set(aux) | singles
    assert (len(aux), len(singles), len(removed)) == (961, 1460, 3041)
    assert removed == {i for i, v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    assert not removed & set(a['objective'][1])
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    for i, j in common:
        assert a['vars'][i] == b['vars'][j]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [None] * len(a['vars'])
    for i, v in enumerate(a['vars']):
        if i not in removed:
            reverse[i] = expression(0, {b['var_index'][v['name']]: 1})
        elif i in aliases:
            reverse[i] = expression(0, {b['var_index'][a['vars'][aliases[i]]['name']]: 1})
        else:
            reverse[i] = expression()
    projected = {}
    singleton_domains = {}
    for d in h['singleton_eliminations']:
        row = a['rows'][a['row_index'][d['row']]]
        ids = {a['var_index'][n] for n in d['removed_variables']}
        first = a['var_index'][d['reconstruction_variable']]
        assert row['sense'] == 'E' and row['rhs'] == 0 and first in ids and \
            all(row['terms'][i] == 1 for i in ids)
        e = substitute(expression(0, {i: -c for i, c in row['terms'].items() if i not in ids}),
                       reverse)
        reverse[first] = e
        singleton_domains[first] = d['row']
        projected[d['row']] = ids
    duplicates = {d['removed_row']: d['retained_row'] for d in h['duplicate_row_removals']}
    def retained_name(n):
        while n in duplicates:
            n = duplicates[n]
        return n
    interval_specs = []
    interval_by_aux = {}
    special_forward = {}
    for i, d in aux.items():
        ur = a['rows'][a['row_index'][d['upper_row']]]
        assert ur['sense'] == 'G' and ur['terms'][i] == -1
        upper = substitute(expression(-ur['rhs'], {j: c for j, c in ur['terms'].items() if j != i}),
                           reverse)
        if not d['lower_rows']:
            assert a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] is None
            special_forward[d['upper_row']] = [[row_ref(a, d['upper_row']), F(1)],
                                               [{'VarLower': i}, F(1)]]
            continue
        assert len(d['lower_rows']) == 2 and a['vars'][i]['lower'] is None and \
            a['vars'][i]['upper'] is None
        lowers = []
        for rn in d['lower_rows']:
            lr = a['rows'][a['row_index'][rn]]
            assert lr['sense'] == 'L' and lr['terms'][i] == -1
            lowers.append(substitute(
                expression(-lr['rhs'], {j: c for j, c in lr['terms'].items() if j != i}),
                reverse))
        assert lowers[0] == mul(lowers[1], -1)
        interval_by_aux[i] = len(interval_specs)
        interval_specs.append((lowers, [upper], [d['upper_row'], d['additional_row']]))
        for name, lr in zip([d['upper_row'], d['additional_row']], d['lower_rows']):
            special_forward[name] = [[row_ref(a, d['upper_row']), F(1)],
                                     [row_ref(a, lr), F(1)]]
    assert len(interval_specs) == 930

    proof, forward_builder, reverse_builder = make_proof(a, b)
    f = forward_builder
    alias_eq = {}
    graph = {}
    for rn in h['alias_eliminations']['removed_equality_rows']:
        ref = row_ref(a, rn)
        e = f.refexpr(ref)
        assert f.kind(ref) == 'Eq' and e[0] == 0 and len(e[1]) == 2
        (i, c), (j, d) = e[1].items()
        assert c == -d and abs(c) == 1
        graph.setdefault(i, []).append((j, ref, 1 / c))
        graph.setdefault(j, []).append((i, ref, 1 / d))
    for root in sorted(set(aliases.values())):
        seen = {root}
        todo = [root]
        while todo:
            j = todo.pop()
            for i, ref, scale_at_j in graph.get(j, []):
                if i in seen:
                    continue
                assert aliases[i] == root
                terms = [[ref, -scale_at_j]]
                if j != root:
                    terms.append([alias_eq[j], F(1)])
                alias_eq[i] = fact(f, 'Eq', expression(0, {i: 1, root: -1}), terms)
                seen.add(i)
                todo.append(i)
    assert set(alias_eq) == set(aliases)
    def corrected(kind, wanted, terms):
        raw = expression()
        for r, c in terms:
            raw = plus(raw, f.refexpr(r), c)
        terms = terms + [[alias_eq[i], -c] for i, c in raw[1].items() if i in aliases]
        return fact(f, kind, wanted, terms, terminal=True)
    checks = []
    for j, v in enumerate(b['vars']):
        i = common[j][0]
        if v['lower'] is not None:
            checks.append({'VarLower': i})
        if v['upper'] is not None:
            checks.append({'VarUpper': i})
        if v['integer']:
            checks.append({'VarInt': i})
    for row in b['rows']:
        rn = row['name']
        typ = next(iter(row_ref(b, rn)))
        wanted = substitute(row_fact(row, typ), forward)
        kind = 'Eq' if typ == 'RowEq' else 'Le'
        if rn in special_forward:
            terms = special_forward[rn]
        elif rn in projected:
            terms = [[row_ref(a, rn), F(1)]] + [[{'VarLower': i}, F(1)] for i in sorted(projected[rn])]
        else:
            terms = [[row_ref(a, rn), F(1)]]
        checks.append(corrected(kind, wanted, terms))
    assert substitute(b['objective'], forward) == a['objective']
    # One Exact witness discharges the objective equality; the retained
    # coordinate observations are part of the complete map, not extra claims.
    checks.append('Exact')
    f.finish(forward, checks)

    pre = reverse_builder
    intervals = []
    for lows, ups, names in interval_specs:
        refs = []
        for lower, name in zip(lows, names):
            wanted = plus(lower, ups[0], -1)
            ref = row_ref(b, retained_name(name))
            assert pre.refexpr(ref) == wanted
            refs.append(ref)
        intervals.append({'lower': lows, 'upper': ups, 'checks': refs})
    r = pre.intervals(intervals)
    layout = r.old_layout
    mapping = list(reverse)
    rowproof = {}
    for i, d in aux.items():
        if i not in interval_by_aux:
            continue
        k = interval_by_aux[i]
        mapping[i] = expression(0, {layout[k]['variable']: 1})
        rowproof[d['upper_row']] = {'RowUpper': layout[k]['upper'][0]}
        for rn, ri in zip(d['lower_rows'], layout[k]['lower']):
            rowproof[rn] = {'RowLower': ri}
    checks = []
    for i, v in enumerate(a['vars']):
        e = mapping[i]
        for typ, value, sign in [('VarLower', v['lower'], -1), ('VarUpper', v['upper'], 1)]:
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            if i in singleton_domains and typ == 'VarLower':
                rn = retained_name(singleton_domains[i])
                if rn in b['row_index']:
                    ref = row_ref(b, rn)
                    assert r.refexpr(ref) == wanted
                else:
                    ref = box(r, wanted, True)
            else:
                ref = box(r, wanted, True)
            checks.append(ref)
        if v['integer']:
            checks.append(fact(r, 'Int', e, [[{'VarInt': j}, c] for j, c in e[1].items()],
                               e[0], True))
    for row in a['rows']:
        rn = row['name']
        typ = next(iter(row_ref(a, rn)))
        kind = 'Eq' if typ == 'RowEq' else 'Le'
        wanted = substitute(row_fact(row, typ), mapping)
        if exact(kind, wanted):
            ref = 'Exact'
        elif rn in rowproof:
            ref = rowproof[rn]
            assert r.refexpr(ref) == wanted
        else:
            name = retained_name(rn)
            ref = row_ref(b, name)
            assert r.kind(ref) == kind and r.refexpr(ref) == wanted, (rn, name, kind)
        checks.append(ref)
    assert substitute(a['objective'], mapping) == b['objective']
    checks.append('Exact')
    r.finish(mapping, checks)

    counts = {'source_variables': 35378, 'target_variables': 32337,
              'source_rows': 16516, 'target_rows': 14717,
              'free_auxiliary_intervals': 930, 'nonnegative_auxiliaries': 31,
              'aliases': 620, 'private_binaries': 1460, 'singleton_rows': 640,
              'box_redundancies': 220, 'duplicates': 29,
              'claims': 2, 'forward_steps': len(f.steps),
              'reverse_obligations': len(checks)}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test30-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test30'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test30', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test30', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
