#!/usr/bin/env python3
"""Actual test64: local binary aliases, ordered saturation, and full integer inverse."""
from fractions import Fraction as F
from prepare_test45 import execute
from prepare_affine import row_ref
from prepare_test40 import expression, plus, mul, row_fact
from prepare_test57 import substitute
from prepare_test54 import box, exact
from prepare_native import make_proof


def cases_eq(p, wanted, y, left, right):
    return p.cases('Eq', wanted, expression(0, {y: 1}),
                   integer={'VarInt': y}, left=left, right=right)


def prepare(a, b, h):
    ai = a['var_index']
    bi = b['var_index']
    proof, f, r = make_proof(a, b)
    aliases = {}
    pre = {}
    for d in h['x_alias_proofs']:
        x, t = [ai[n] for n in d['eliminated']]
        y = ai[d['retained']]
        row = row_ref(a, d['row'])
        assert f.refexpr(row) == expression(0, {x: 1, t: 1, y: -2})
        for i in (x, t, y):
            assert a['vars'][i]['integer'] and a['vars'][i]['lower'] == 0 and \
                a['vars'][i]['upper'] == 1
        wanted = expression(0, {x: 1, y: -1})

        def branch(c, g, side):
            yeq = c.eqpair({'VarUpper': y}, g) if side else c.eqpair(g, {'VarLower': y})
            if side:
                low = c.lin('Le', [[row, -1], [{'VarUpper': t}, 1], [g, 2]],
                            expression(1, {x: -1}))
                xeq = c.eqpair({'VarUpper': x}, low)
            else:
                up = c.lin('Le', [[row, 1], [{'VarLower': t}, 1], [g, 2]],
                           expression(0, {x: 1}))
                xeq = c.eqpair(up, {'VarLower': x})
            return c.lin('Eq', [[xeq, 1], [yeq, -1]], wanted)

        aliases[x] = cases_eq(f, wanted, y, lambda c, g: branch(c, g, 0),
                              lambda c, g: branch(c, g, 1))
        aliases[t] = f.lin('Eq', [[row, 1], [aliases[x], -1]], expression(0, {t: 1, y: -1}))
        pre[x] = pre[t] = expression(0, {y: 1})
    normalized = {}
    merged = {}

    def normalize(n):
        if n in normalized:
            return normalized[n]
        if n in merged:
            return merged[n]
        ref = row_ref(a, n)
        e = f.refexpr(ref)
        terms = [[ref, 1]] + [[aliases[i], -q] for i, q in e[1].items() if i in aliases]
        result = ref if len(terms) == 1 else f.lin(f.kind(ref), terms)
        normalized[n] = result
        return result

    for d in h['merged_pairs']:
        le = normalize(d['retained'])
        ge = normalize(d['removed'])
        merged[d['retained']] = f.eqpair(le, ge)
        normalized.pop(d['retained'], None)
    for d in h['w_alias_proofs']:
        w, u = ai[d['eliminated']], ai[d['retained']]
        row = normalize(d['row'])
        aliases[w] = f.lin('Eq', [[merged[d['paired_rows'][0]], 1], [row, -1]],
                           expression(0, {w: 1, u: -1}))
        pre[w] = expression(0, {u: 1})
    # Cached rows above were only used while establishing x/w aliases. Subsequent
    # normalizations incorporate every now-established substitution.
    normalized = {}
    for n, rn in h['cost_definitions'].items():
        i = ai[n]
        row = row_ref(a, rn)
        e = f.refexpr(row)
        assert e[0] == 0 and e[1][i] == -1
        pre[i] = expression(0, {j: q for j, q in e[1].items() if j != i})
        assert all(q > 0 and q.denominator == 1 and a['vars'][j]['integer'] and
                   a['vars'][j]['lower'] >= 0 for j, q in pre[i][1].items())
        aliases[i] = f.lin('Eq', [[row, -1]], plus(expression(0, {i: 1}), pre[i], -1))
    z = ai['z']
    zr = row_ref(a, 'z')
    ze = f.refexpr(zr)
    pre[z] = expression()
    terms = [[zr, -1]]
    for i, q in ze[1].items():
        if i != z:
            pre[z] = plus(pre[z], pre[i], q)
            terms.append([aliases[i], q])
    aliases[z] = f.lin('Eq', terms, plus(expression(0, {z: 1}), pre[z], -1))
    assert {a['vars'][i]['name']: {a['vars'][j]['name']: int(q) for j, q in e[1].items()}
            for i, e in pre.items()} == h['substitutions']
    fixed = {}
    fixedrefs = {}
    for d in h['ordered_fixing_proofs']:
        row = normalize(d['row'])
        e = f.refexpr(row)
        terms = [[row, 1]] + [[fixedrefs[i], -q] for i, q in e[1].items() if i in fixed]
        reduced = row if len(terms) == 1 else f.lin(f.kind(row), terms)
        e = f.refexpr(reduced)
        sgn = -1 if d['extreme'] == 'max' and f.kind(reduced) == 'Eq' else 1
        oriented = mul(e, sgn)
        assert f.kind(reduced) == 'Eq' or sgn == 1
        expected = {a['vars'][i]['name']: (a['vars'][i]['lower'] if q > 0
                                           else a['vars'][i]['upper'])
                    for i, q in oriented[1].items()}
        assert expected == d['fixed']
        assert oriented[0] + sum(q * F(expected[a['vars'][i]['name']])
                                 for i, q in oriented[1].items()) == 0
        for n, value in d['fixed'].items():
            i = ai[n]
            q = oriented[1][i]
            value = F(value)
            comb = [[reduced, sgn / abs(q)]]
            for j, c in oriented[1].items():
                if j != i:
                    comb.append([{'VarLower' if c > 0 else 'VarUpper': j}, abs(c / q)])
            opposite = f.lin('Le', comb,
                             expression(-value if q > 0 else value,
                                        {i: 1 if q > 0 else -1}))
            fixedrefs[i] = (f.eqpair(opposite, {'VarLower': i}) if q > 0
                            else f.eqpair({'VarUpper': i}, opposite))
            fixed[i] = value
    assert {a['vars'][i]['name']: int(value) for i, value in fixed.items()} == \
        h['fixed_variables']
    common = [[ai[v['name']], j] for j, v in enumerate(b['vars'])]
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = []
    full = {}
    for i, v in enumerate(a['vars']):
        n = v['name']
        if i in fixed:
            e = expression(fixed[i])
        elif i in pre:
            e = expression(pre[i][0])
            comb = [[aliases[i], 1]]
            for j, q in pre[i][1].items():
                if j in fixed:
                    e = plus(e, expression(fixed[j]), q)
                    comb.append([fixedrefs[j], q])
                else:
                    assert a['vars'][j]['name'] in bi
                    e = plus(e, expression(0, {bi[a['vars'][j]['name']]: 1}), q)
            full[i] = (aliases[i] if len(comb) == 1 else
                       f.lin('Eq', comb, plus(expression(0, {i: 1}),
                                              substitute(e, forward), -1)))
        else:
            assert n in bi
            e = expression(0, {bi[n]: 1})
        if i in fixed:
            full[i] = fixedrefs[i]
        reverse.append(e)
    assert set(full) == set(pre) | set(fixed)
    checks = []
    for i, j in common:
        v = b['vars'][j]
        assert v == a['vars'][i]
        if v['lower'] is not None:
            checks.append({'VarLower': i})
        if v['upper'] is not None:
            checks.append({'VarUpper': i})
        if v['integer']:
            checks.append({'VarInt': i})
    for row in b['rows']:
        n = row['name']
        ref = normalize(n)
        e = f.refexpr(ref)
        wanted = substitute(row_fact(row, next(iter(row_ref(b, n)))), forward)
        terms = [[ref, 1]] + [[fixedrefs[i], -q] for i, q in e[1].items() if i in fixed]
        check = ref if len(terms) == 1 else \
            f.lin('Eq' if row['sense'] == 'E' else 'Le', terms, wanted)
        assert f.refexpr(check) == wanted, (n, 'forward')
        checks.append(check)
    objective = plus(substitute(b['objective'], forward), a['objective'], -1)
    checks.append(f.lin('Eq', [[full[z], -1]], objective))
    f.finish(forward, checks)

    cache = {}
    mergednames = {d['retained'] for d in h['merged_pairs']}
    initial = h['initial_removed_rows']

    def recover(n):
        if n in cache:
            return cache[n]
        row = a['rows'][a['row_index'][n]]
        typ = 'RowEq' if n in mergednames else next(iter(row_ref(a, n)))
        wanted = substitute(row_fact(row, typ), reverse)
        kind = 'Eq' if typ == 'RowEq' else 'Le'
        if exact(kind, wanted):
            ref = 'Exact'
        elif n in b['row_index']:
            ref = row_ref(b, n)
        elif n in h['bound_removed_rows']:
            if kind == 'Eq':
                ref = r.eqpair(box(r, wanted), box(r, mul(wanted, -1)))
            else:
                ref = box(r, wanted, True)
        else:
            d = initial[n]
            k = d['kind']
            if k == 'merged_opposite_inequalities':
                terms = [[recover(d['retained']), -1]]
            elif k == 'same_equality_after_substitution':
                terms = [[recover(d['retained']), 1]]
            elif k == 'negative_equality':
                terms = [[recover(d['retained']), -1]]
            elif k == 'exact_linear_combination':
                terms = [[recover(t), F(q)] for t, q in d['terms']]
            elif k == 'equality_and_binary_upper_bound':
                terms = [[recover(d['equality']), 1]]
                u = ai[d['variable']]
                ue = reverse[u]
                bound = plus(ue, expression(-F(d['upper'])))
                br = box(r, bound, True)
                if br == 'Exact':
                    ref = r.lin('Le', [t for t in terms if t[0] != 'Exact'],
                                wanted, bound[0])
                    cache[n] = ref
                    return ref
                terms.append([br, 1])
            else:
                raise AssertionError((n, k, wanted))
            # Constant identities in dependency rows are genuine zero expressions.
            terms = [t for t in terms if t[0] != 'Exact']
            ref = r.lin(kind, terms, wanted)
        assert ref == 'Exact' or r.refexpr(ref) == wanted, (n, 'reverse')
        cache[n] = ref
        return ref

    rchecks = []
    for i, v in enumerate(a['vars']):
        e = reverse[i]
        for bound, sgn in [(v['lower'], -1), (v['upper'], 1)]:
            if bound is not None:
                rchecks.append(box(r, plus(mul(e, sgn), expression(-sgn * bound)), True))
        if v['integer']:
            rchecks.append('Exact' if exact('Int', e)
                           else r.lin('Int', [[{'VarInt': j}, q] for j, q in e[1].items()],
                                      e, e[0]))
    for row in a['rows']:
        n = row['name']
        ref = recover(n)
        wanted = substitute(row_fact(row, next(iter(row_ref(a, n)))), reverse)
        if n in mergednames and ref != 'Exact':
            ref = r.lin('Le', [[ref, 1]], wanted)
        assert ref == 'Exact' or r.refexpr(ref) == wanted
        rchecks.append(ref)
    assert substitute(a['objective'], reverse) == b['objective']
    rchecks.append('Exact')
    r.finish(reverse, rchecks)
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'binary_triples': len(h['x_alias_proofs']), 'x_aliases': 13750,
                   'merged_pairs': len(merged), 'w_aliases': 550, 'cost_coordinates': 6,
                   'ordered_saturation_steps': len(h['ordered_fixing_proofs']),
                   'fixed_coordinates': len(fixed),
                   'bound_entailed_rows': len(h['bound_removed_rows']),
                   'dependent_assignment_rows': 69, 'directions': 2}


if __name__ == '__main__':
    execute('test64', prepare, __file__)
