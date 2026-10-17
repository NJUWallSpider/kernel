#!/usr/bin/env python3
"""Native test10 shared load-budget proof with exact threshold cuts.

Every threshold, selector, interval and case split is a native proof scope.
The selector interval is a native ``IntervalLift``; the reverse body finishes
through the owning direction. The MI-OPT artifact carries the forward and
reverse directions only, so the legacy LP fiber point is not part of the proof.
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


def cases(p, kind, wanted, var, callbacks):
    """Native binary Cases step on an integer variable."""
    left, right = callbacks
    return p.cases(kind, wanted, expression(0, {var: 1}), {'VarInt': var}, left, right)


def selector_fact(p, wanted, special, z):
    """Only two ordinary branches. Actual selector rows force one full pair."""
    def branch(child, assumption, side):
        pair = special[:2] if side else special[2:]
        r = row_ref(child.model, 'R2302' if side else 'R2303')
        forced = {}
        for i, j in [pair, pair[::-1]]:
            forced[i] = child.lin('Le', [[r, 1], [assumption, 2], [{'VarUpper': j}, 1]],
                                  expression(1, {i: -1}))
        terms = []
        ceiling = wanted[0]
        for i, c in wanted[1].items():
            if c > 0:
                ref = {'VarUpper': i}
                value = 1
            elif i in forced:
                ref = forced[i]
                value = 1
            else:
                ref = {'VarLower': i}
                value = 0
            terms.append([ref, abs(c)])
            ceiling += c * value
        assert ceiling <= 0
        return child.lin('Le', terms, wanted, ceiling)
    return cases(p, 'Le', wanted, z,
                 [lambda c, r: branch(c, r, 0), lambda c, r: branch(c, r, 1)])


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == \
        (190402, 2303, 190201, 2105)
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    assert all(a['vars'][i] == b['vars'][j] for i, j in common)
    forward = [expression(0, {i: 1}) for i, j in common]
    budget = row_ref(a, h['budget_substitution']['row'])
    br = a['rows'][budget['RowUpper']]
    loads = {}
    weights = {}
    assignment = {}
    groups = {}
    costs = {}
    charges = {}
    for k in range(950):
        name = f'R{951 + k:04d}'
        row = a['rows'][a['row_index'][name]]
        assert row['sense'] == 'E' and row['rhs'] == 1 and len(row['terms']) == 200 and \
            all(c == 1 for c in row['terms'].values())
        for i in row['terms']:
            assert i not in assignment
            assignment[i] = name
    for d in h['eliminated_loads']:
        u, y = a['var_index'][d['variable']], a['var_index'][d['activation_variable']]
        r = row_ref(a, d['row'])
        e = row_fact(a['rows'][r['RowEq']], 'RowEq')
        assert e[0] == 0 and e[1][u] == -1 and not a['vars'][u]['integer'] and \
            a['vars'][u]['lower'] == 0 and a['vars'][u]['upper'] is None
        terms = {i: c for i, c in e[1].items() if i != u}
        assert len(terms) == 950 and all(c > 0 for c in terms.values())
        assert set(assignment[i] for i in terms) == \
            set(a['rows'][a['row_index'][f'R{951 + k:04d}']]['name'] for k in range(950))
        for i, w in terms.items():
            rn = assignment[i]
            assert rn not in weights or weights[rn] == w
            weights[rn] = w
        loads[u] = (r, expression(0, terms))
        groups[y] = (u, d['activation_variable'])
        costs[y] = br['terms'][u]
        charges[y] = br['terms'][y]
        assert costs[y] == F(d['budget_coefficient']) and costs[y] > 0 and charges[y] > 0
    z = a['var_index'][h['selector']['removed_variable']]
    assert {i for i, v in enumerate(a['vars']) if v['name'] not in b['var_index']} == \
        set(loads) | {z}
    assert set(br['terms']) == set(loads) | set(groups) and br['rhs'] == 900000000
    special = [a['var_index'][f'C{190202 + k}'] for k in range(4)]
    assert row_fact(a['rows'][a['row_index']['R2302']], 'RowLower') == \
        expression(0, {special[0]: -1, special[1]: -1, z: 2})
    assert row_fact(a['rows'][a['row_index']['R2303']], 'RowLower') == \
        expression(2, {special[2]: -1, special[3]: -1, z: -2})
    cmin = min(costs.values())
    W = sum(weights.values())
    prefix = [F(0)]
    for w in sorted(weights.values()):
        prefix.append(prefix[-1] + w)
    assert cmin == F(h['bound_proof']['minimum_unit_cost']) and \
        W == F(h['bound_proof']['total_weight'])
    assert prefix == [F(x) for x in h['bound_proof']['sorted_weight_prefix_sums']]

    proof, f, reverse_builder = make_proof(a, b)
    total = f.lin('Eq', [[r, -1] for r, e in loads.values()] +
                  [[row_ref(a, n), w] for n, w in weights.items()],
                  expression(-W, {u: 1 for u in loads}))
    base = f.lin('Le', [[budget, 1], [total, -cmin]])
    fixed4 = expression(0, {i: -charges[i] for i in special})
    Fmin = min(sum(charges[i] for i in pair) for pair in [special[:2], special[2:]])
    global_fixed = selector_fact(f, plus(expression(Fmin), fixed4), special, z)
    fixed_cond = {}
    for y in special:
        Fj = min(sum(charges[i] for i in pair) + (charges[y] if y not in pair else 0)
                 for pair in [special[:2], special[2:]])
        fixed_cond[y] = selector_fact(f, plus(fixed4, expression(0, {y: Fj})), special, z)
    tightened = {}
    thresholds = []
    for y, (u, yn) in groups.items():
        d = h['link_bounds'][yn]
        name = d['row']
        M = F(d['new_M'])
        old = row_ref(a, name)
        count = expression(0, {i: 1 for i in loads[u][1][1]})
        assert f.refexpr(old) == plus(count, expression(0, {y: -950}))
        assert substitute(row_fact(b['rows'][b['row_index'][name]], 'RowUpper'), forward) == \
            plus(count, expression(0, {y: -M}))
        Fj = min(sum(charges[i] for i in pair) + (charges[y] if y not in pair else 0)
                 for pair in [special[:2], special[2:]])
        delta = costs[y] - cmin
        expected = 950 if delta == 0 else \
            max(k for k, P in enumerate(prefix) if delta * P + cmin * W + Fj <= br['rhs'])
        assert M == expected and Fj == F(d['conditional_fixed_charge_lower_bound'])
        if M == 950:
            continue
        assert delta > 0 and 0 < M < 950
        terms = [[base, 1]] + [[{'VarLower': uu}, costs[yy] - cmin]
                               for yy, (uu, _) in groups.items() if yy != y and costs[yy] > cmin]
        if y in special:
            terms.append([fixed_cond[y], 1])
            terms += [[{'VarLower': yy}, charges[yy]] for yy in groups if yy not in special]
        else:
            terms += [[global_fixed, 1], [{'VarUpper': y}, Fmin]]
            terms += [[{'VarLower': yy}, charges[yy]] for yy in groups
                      if yy not in special and yy != y]
        conditional = f.lin('Le', terms,
                            expression(cmin * W - br['rhs'], {u: delta, y: Fj}))
        t = sorted(weights.values())[int(M)]
        C = sum(max(F(0), t - w) for w in weights.values())
        boxterms = []
        for i, w in loads[u][1][1].items():
            if t > w:
                boxterms.append([{'VarUpper': i}, t - w])
            elif t < w:
                boxterms.append([{'VarLower': i}, w - t])
        support = f.lin('Le', boxterms,
                        plus(plus(mul(count, t), loads[u][1], -1), expression(-C)))
        thresholds.append({'row': name, 'M': int(M), 'threshold': str(t),
                           'box_correction': str(C), 'conditional_fixed_charge': str(Fj)})
        integer = f.lin('Int', [[{'VarInt': i}, 1] for i in count[1]], count)
        wanted = plus(count, expression(0, {y: -M}))
        def zero(child, assumption, old=old, M=M, wanted=wanted):
            return child.lin('Le', [[old, 1], [assumption, 950 - M]], wanted)
        def one(child, assumption, u=u, delta=delta, Fj=Fj, t=t, conditional=conditional,
                support=support, integer=integer, M=M, wanted=wanted):
            weightbound = child.lin('Le', [[conditional, 1], [assumption, Fj],
                                           [loads[u][0], delta]])
            bound = child.lin('Le', [[weightbound, 1 / (delta * t)], [support, 1 / t]])
            rounded = child.round(bound, integer)
            assert child.refexpr(rounded) == plus(count, expression(-M))
            return child.lin('Le', [[rounded, 1], [assumption, M]], wanted)
        tightened[name] = cases(f, 'Le', wanted, y, [zero, one])
    assert len(tightened) == 170
    selector = {}
    for d in h['selector']['new_rows']:
        wanted = substitute(row_fact(b['rows'][b['row_index'][d['row']]], 'RowLower'), forward)
        selector[d['row']] = selector_fact(f, wanted, special, z)

    checks = []
    for i, j in common:
        v = b['vars'][j]
        for typ, bound in [('VarLower', v['lower']), ('VarUpper', v['upper'])]:
            if bound is not None:
                checks.append({typ: i})
        if v['integer']:
            checks.append({'VarInt': i})
    for row in b['rows']:
        n = row['name']
        typ = next(iter(row_ref(b, n)))
        wanted = substitute(row_fact(row, typ), forward)
        if n in tightened:
            ref = tightened[n]
        elif n in selector:
            ref = selector[n]
        elif n == h['budget_substitution']['row']:
            ref = f.lin('Le', [[budget, 1]] + [[r, br['terms'][u]] for u, (r, e) in loads.items()],
                        wanted)
        else:
            ref = row_ref(a, n)
        assert f.refexpr(ref) == wanted
        checks.append(ref)
    assert substitute(b['objective'], forward) == a['objective']
    # The objective equality is the final Return obligation; the retained
    # coordinate identities are carried by the complete forward map.
    checks.append('Exact')
    f.finish(forward, checks)

    bs = [b['var_index'][a['vars'][i]['name']] for i in special]
    aa, bb, cc, dd = bs
    lower = [expression(), expression(-1, {aa: 1, bb: 1}),
             expression(1, {cc: F(-1, 2), dd: F(-1, 2)})]
    upper = [expression(0, {aa: 1}), expression(0, {bb: 1})]
    pre = reverse_builder
    premises = []
    for k, l in enumerate(lower):
        for j, v in enumerate([aa, bb]):
            wanted = plus(l, upper[j], -1)
            if k < 2:
                ref = box(pre, wanted, True)
            else:
                ref = pre.lin('Le', [[row_ref(b, f'P{1 + 2 * j:04d}'), F(1, 2)],
                                     [row_ref(b, f'P{2 + 2 * j:04d}'), F(1, 2)]], wanted)
            premises.append(ref)
    interval = {'lower': lower, 'upper': upper, 'checks': premises}
    r = pre.intervals([interval])
    ll = r.old_layout[0]
    zz = ll['variable']
    ze = expression(0, {zz: 1})
    lo = [{'RowLower': i} for i in ll['lower']]
    hi = [{'RowUpper': i} for i in ll['upper']]
    retained_map = [expression(0, {b['var_index'][v['name']]: 1})
                    if v['name'] in b['var_index'] else expression() for v in a['vars']]
    reverse = []
    for i, v in enumerate(a['vars']):
        if i in loads:
            reverse.append(substitute(loads[i][1], retained_map))
        elif i == z:
            reverse.append(ze)
        else:
            reverse.append(expression(0, {b['var_index'][v['name']]: 1}))
    zupper = r.lin('Le', [[hi[0], 1], [{'VarUpper': aa}, 1]], plus(ze, expression(-1)))
    def azero(child, assumption):
        up = child.lin('Le', [[hi[0], 1], [assumption, 1]], ze)
        return child.lin('Int', [[child.eqpair(up, lo[0]), 1]], ze)
    def aone(child, assumption):
        def bzero(c, r_):
            up = c.lin('Le', [[hi[1], 1], [r_, 1]], ze)
            return c.lin('Int', [[c.eqpair(up, lo[0]), 1]], ze)
        def bone(c, r_):
            low = c.lin('Le', [[lo[1], 1], [assumption, 1], [r_, 1]],
                        plus(expression(1), ze, -1))
            return c.lin('Int', [[c.eqpair(zupper, low), 1]], ze, 1)
        return cases(child, 'Int', ze, bb, [bzero, bone])
    zint = cases(r, 'Int', ze, aa, [azero, aone])

    checks = []
    for i, v in enumerate(a['vars']):
        e = reverse[i]
        if i == z:
            checks += [lo[0], zupper, zint]
        elif i in loads:
            checks.append(box(r, mul(e, -1), True))
        else:
            j = next(iter(e[1]))
            assert e == expression(0, {j: 1})
            for typ, bound in [('VarLower', v['lower']), ('VarUpper', v['upper'])]:
                if bound is not None:
                    checks.append({typ: j})
            if v['integer']:
                checks.append({'VarInt': j})
    for row in a['rows']:
        n = row['name']
        typ = next(iter(row_ref(a, n)))
        wanted = substitute(row_fact(row, typ), reverse)
        if exact('Eq' if typ == 'RowEq' else 'Le', wanted):
            ref = 'Exact'
        elif n == 'R2302':
            ref = r.lin('Le', [[hi[0], 1], [hi[1], 1]], wanted)
        elif n == 'R2303':
            ref = r.lin('Le', [[lo[2], 2]], wanted)
        elif n in tightened:
            yn = next(yn for yn, d in h['link_bounds'].items() if d['row'] == n)
            d = h['link_bounds'][yn]
            ref = r.lin('Le', [[row_ref(b, n), 1],
                               [{'VarLower': b['var_index'][yn]}, 950 - F(d['new_M'])]], wanted)
        else:
            ref = row_ref(b, n)
        assert ref == 'Exact' or r.refexpr(ref) == wanted
        checks.append(ref)
    assert substitute(a['objective'], reverse) == b['objective']
    checks.append('Exact')
    r.finish(reverse, checks)

    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'eliminated_loads': len(loads), 'tightened_activations': len(tightened),
              'selector_intervals_per_reverse': 1,
              'retained_coordinates_per_claim': len(common), 'claims': 2,
              'thresholds': thresholds}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test10-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test10'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    hint = run / 'output/changes.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(hint.read_text()))
    record = compile_case(proof, args.out, case_id='test10', source=source, target=target,
                          metadata={'audit': {'path': str(hint), 'sha256': sha(hint)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test10', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
