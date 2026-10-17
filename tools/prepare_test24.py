#!/usr/bin/env python3
"""Native test24 dominance normalization with balanced local priority proofs.

All priority intervals and case splits are native proof scopes: the forward
direction installs one ``IntervalLift`` over the disjoint cover prefixes and
finishes the lifted body through the direction. The two MI-OPT directions
carry the legacy forward NonIncreasing and reverse Equal claims.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, sha
from prepare_test57 import substitute
from prepare_test54 import box, exact
from prepare_native import compile_case, make_proof


def split(p, kind, wanted, e, integer, callbacks):
    """Native Cases step whose two branches prove one common conclusion."""
    left, right = callbacks
    return p.cases(kind, wanted, e, integer, left, right)


def isum(p, ids):
    return p.lin('Int', [[{'VarInt': i}, 1] for i in ids],
                 expression(0, {i: 1 for i in ids}))


def positive_zero(p, z, ids, upper, positive):
    """A positive binary sum contains an active member; balanced local Cases."""
    wanted = expression(0, {z: 1})
    if len(ids) == 1:
        return p.lin('Le', [[upper[ids[0]], 1], [positive, 1]], wanted)
    cut = len(ids) // 2
    left, right = ids[:cut], ids[cut:]
    e = expression(0, {i: 1 for i in left})
    integer = isum(p, left)
    def zero(c, r):
        pos = c.lin('Le', [[positive, 1], [r, 1]], expression(1, {i: -1 for i in right}))
        return positive_zero(c, z, right, upper, pos)
    return split(p, 'Le', wanted, e, integer,
                 [zero, lambda c, r: positive_zero(c, z, left, upper, r)])


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == \
        (10100, 10180, 2407, 2487)
    covers = [a['rows'][a['row_index'][d['row']]] for d in h['row_sense_changes']]
    used = set()
    intervals = []
    records = []
    proof, forward_builder, reverse_builder = make_proof(a, b)
    pre = forward_builder
    for row in covers:
        ids = sorted(row['terms'])
        assert row['sense'] == 'G' and row['rhs'] == 1 and \
            all(c == 1 for c in row['terms'].values()) and not used.intersection(ids)
        used.update(ids)
        assert 15 <= len(ids) <= 40
        # The first prefix is affine (1-x). Interior prefixes use one simultaneous
        # interval lift. The final prefix is zero by the actual cover inequality.
        rec = {'row': row['name'], 'ids': ids, 'prefix': [expression(1)]}
        for k in range(1, len(ids)):
            if k == 1:
                rec['prefix'].append(expression(1, {ids[0]: -1}))
                continue
            lower = [expression(), expression(1, {i: -1 for i in ids[:k]})]
            upper = [expression(1, {i: -1}) for i in ids[:k]]
            checks = []
            for lo in lower:
                for hi in upper:
                    checks.append(box(pre, plus(lo, hi, -1), True))
            rec['prefix'].append(len(intervals))
            intervals.append({'lower': [lo for lo in lower],
                              'upper': [hi for hi in upper],
                              'checks': checks})
        rec['prefix'].append(expression())
        records.append(rec)
    assert len(used) == 2307

    p = pre.intervals(intervals)
    layout = p.old_layout
    mapping = {}
    dominance = {}
    domains = {}
    cover_eq = {}
    for rec in records:
        ids = rec['ids']
        prefix = rec['prefix']
        meta = {}
        for k in range(1, len(ids)):
            if k == 1:
                continue
            ll = layout[prefix[k]]
            z = ll['variable']
            prefix[k] = expression(0, {z: 1})
            low = {'RowLower': ll['lower'][0]}
            sumlow = {'RowLower': ll['lower'][1]}
            upper = {i: {'RowUpper': j} for i, j in zip(ids[:k], ll['upper'])}
            hi = p.lin('Le', [[upper[ids[0]], 1], [{'VarLower': ids[0]}, 1]],
                       expression(-1, {z: 1}))
            e = expression(0, {i: 1 for i in ids[:k]})
            integer = isum(p, ids[:k])
            def zero(c, r, z=z, sumlow=sumlow, hi=hi):
                lowone = c.lin('Le', [[sumlow, 1], [r, 1]], expression(1, {z: -1}))
                eq = c.eqpair(hi, lowone)
                return c.lin('Int', [[eq, 1]], expression(0, {z: 1}), 1)
            def active(c, r, z=z, ids=ids[:k], upper=upper, low=low):
                eq = c.eqpair(positive_zero(c, z, ids, upper, r), low)
                return c.lin('Int', [[eq, 1]], expression(0, {z: 1}))
            integerz = split(p, 'Int', prefix[k], e, integer, [zero, active])
            meta[k] = (low, sumlow, upper, hi, integerz)
        # Each priority difference is integer, nonnegative and <= its original x.
        # A split on the preceding prefix sum has only balanced local subcases.
        for k, x in enumerate(ids, 1):
            prev, cur = prefix[k - 1], prefix[k]
            new = plus(prev, cur, -1)
            mapping[x] = new
            if k == 1:
                assert new == expression(0, {x: 1})
                domains[x] = ({'VarLower': x}, {'VarUpper': x}, {'VarInt': x})
                dominance[x] = p.lin('Le', [], expression())
                continue
            previous_ids = ids[:k - 1]
            sumexpr = expression(0, {i: 1 for i in previous_ids})
            integer = isum(p, previous_ids)
            def branch_eq(c, r, side):
                # Return new=x when all previous choices vanish; otherwise new=0.
                if side == 0:
                    if k - 1 == 1:
                        preveq = c.eqpair(r, {'VarLower': previous_ids[0]})
                        prevone = c.lin('Eq', [[preveq, -1]], plus(prev, expression(-1)))
                    else:
                        low, sl, up, hi, iz = meta[k - 1]
                        prevone = c.eqpair(hi, c.lin('Le', [[sl, 1], [r, 1]],
                                                     plus(expression(1), prev, -1)))
                    if k == len(ids):
                        # With all previous x zero the cover forces the last x=1.
                        lowone = c.lin('Le', [[row_ref(a, rec['row']), 1], [r, 1]],
                                       expression(1, {x: -1}))
                        xeq = c.eqpair({'VarUpper': x}, lowone)
                        return c.lin('Eq', [[prevone, 1], [xeq, -1]],
                                     plus(new, expression(0, {x: 1}), -1))
                    low, sl, up, hi, iz = meta[k]
                    lowone = c.lin('Le', [[sl, 1], [r, 1]],
                                   plus(plus(expression(1), expression(0, {x: 1}), -1),
                                        cur, -1))
                    eqcur = c.eqpair(up[x], lowone)
                    return c.lin('Eq', [[prevone, 1], [eqcur, -1]],
                                 plus(new, expression(0, {x: 1}), -1))
                if k - 1 == 1:
                    preveq = c.eqpair({'VarUpper': previous_ids[0]}, r)
                    peq = c.lin('Eq', [[preveq, -1]], prev)
                else:
                    low, sl, up, hi, iz = meta[k - 1]
                    peq = c.eqpair(positive_zero(c, next(iter(prev[1])), previous_ids, up, r), low)
                if not cur[1]:
                    return peq
                low, sl, up, hi, iz = meta[k]
                ceq = c.eqpair(positive_zero(c, next(iter(cur[1])), previous_ids, up, r), low)
                return c.lin('Eq', [[peq, 1], [ceq, -1]], new)
            def proof(kind, wanted):
                def callback(c, r, side):
                    eq = branch_eq(c, r, side)
                    if kind == 'Int':
                        return c.lin('Int', [[eq, 1]] + ([[{'VarInt': x}, 1]] if side == 0 else []),
                                     wanted)
                    terms = [[eq, -1 if wanted == mul(new, -1) else 1]]
                    if wanted == mul(new, -1):
                        if side == 0:
                            terms.append([{'VarLower': x}, 1])
                    elif side == 1:
                        terms.append([{'VarLower': x}, 1])
                    return c.lin('Le', terms, wanted)
                return split(p, kind, wanted, sumexpr, integer,
                             [lambda c, r: callback(c, r, 0),
                              lambda c, r: callback(c, r, 1)])
            lower = proof('Le', mul(new, -1))
            dom = proof('Le', plus(new, expression(0, {x: 1}), -1))
            integ = proof('Int', new)
            upper = p.lin('Le', [[dom, 1], [{'VarUpper': x}, 1]],
                          plus(new, expression(-1)))
            domains[x] = (lower, upper, integ)
            dominance[x] = dom
        total = expression()
        for x in ids:
            total = plus(total, mapping[x])
        assert total == expression(1)
        cover_eq[rec['row']] = 'Exact'

    retained = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    yprojection = []
    fmap = []
    checks = []
    for i, j in retained:
        assert a['vars'][i] == b['vars'][j]
        if i in mapping:
            fmap.append(mapping[i])
            checks.extend(domains[i])
        else:
            assert a['vars'][i]['upper'] == 13
            fmap.append(expression(0, {i: 1}))
            checks.extend([{'VarLower': i}, {'VarUpper': i}, {'VarInt': i}])
            yprojection.append([i, j])
    for row in b['rows']:
        typ = next(iter(row_ref(b, row['name'])))
        wanted = substitute(row_fact(row, typ), fmap)
        if row['name'] in cover_eq:
            assert exact('Eq', wanted)
            checks.append('Exact')
        else:
            old = row_ref(a, row['name'])
            terms = [[old, 1]]
            for j, c in row['terms'].items():
                i = retained[j][0]
                if i in mapping:
                    assert c > 0
                    terms.append([dominance[i], c])
            checks.append(p.lin('Eq' if typ == 'RowEq' else 'Le', terms, wanted))
    objective = plus(substitute(b['objective'], fmap), a['objective'], -1)
    terms = []
    for i, c in a['objective'][1].items():
        assert c >= 0
        terms.append([dominance[i] if i in mapping else {'VarLower': i}, c])
    checks.append(p.lin('Le', terms, objective))
    # Retained y observation identities are asserted by the complete map and are
    # not separate MI-OPT obligations.
    for i, j in yprojection:
        assert fmap[j] == expression(0, {i: 1})
    p.finish(fmap, checks)

    r = reverse_builder
    reverse = [expression(0, {b['var_index'][v['name']]: 1})
               if v['name'] in b['var_index'] else expression() for v in a['vars']]
    rc = []
    for i, v in enumerate(a['vars']):
        e = reverse[i]
        if not e[1]:
            rc += ['Exact'] * 3
        else:
            j = next(iter(e[1]))
            rc.extend([{'VarLower': j}, {'VarUpper': j}, {'VarInt': j}])
    removed = {d['removed_link_row']: d for d in h['removed_variables']}
    for row in a['rows']:
        typ = next(iter(row_ref(a, row['name'])))
        wanted = substitute(row_fact(row, typ), reverse)
        if row['name'] in removed:
            rc.append({'VarLower': b['var_index'][removed[row['name']]['linked_variable']]})
        elif row['name'] in cover_eq:
            rc.append(r.lin('Le', [[row_ref(b, row['name']), -1]], wanted))
        else:
            ref = row_ref(b, row['name'])
            assert r.refexpr(ref) == wanted
            rc.append(ref)
    assert substitute(a['objective'], reverse) == b['objective']
    # The final Exact witness is the objective equality; the retained-y
    # observations are carried by the complete reverse map.
    rc.append('Exact')
    r.finish(reverse, rc)

    counts = {'source_variables': 10100, 'target_variables': 2407,
              'source_rows': 10180, 'target_rows': 2487,
              'disjoint_covers': 79, 'priority_intervals': len(intervals),
              'removed_binaries': 7693, 'retained_y_observations': 100,
              'forward_obligations': len(checks), 'claims': 2}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test24-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test24'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test24', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test24', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
