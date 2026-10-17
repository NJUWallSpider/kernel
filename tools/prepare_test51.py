#!/usr/bin/env python3
"""Native test51 five-weight simplex/minimum certificates, without a solver.

Every fixing, comparison, substitution and reconstruction is replayed by the
native proof scope. Ties remain legal: Cases asks whether a candidate is
selected, never one-hotness. Only the two MI-OPT directions are emitted; the
legacy LP duplicate is outside that contract.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from functools import lru_cache

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_native import compile_case, make_proof


def cases(p, kind, wanted, z, left, right):
    if isinstance(z, tuple):
        split, integer = z
    else:
        split, integer = expression(0, {z: 1}), {'VarInt': z}
    return p.cases(kind, wanted, split, integer, left, right)


def structure(a):
    simplex = a['rows'][a['row_index']['c0']]
    assert simplex['sense'] == 'E' and simplex['rhs'] == 1 and len(simplex['terms']) == 5 and \
        set(simplex['terms'].values()) == {F(1)}
    weights = sorted(simplex['terms'])
    defs = {}
    scores = {}
    comparisons = {}
    groups = []
    owned = set(weights)
    for row in a['rows']:
        if row['sense'] != 'E' or row['name'] == 'c0':
            continue
        other = set(row['terms']) - set(weights)
        assert len(other) == 1 and row['rhs'] == 0
        s = next(iter(other))
        assert row['terms'][s] == -1
        defs[s] = row_ref(a, row['name'])
        scores[s] = expression(0, {w: row['terms'].get(w, F(0)) for w in weights})
        assert all(c >= 0 for c in scores[s][1].values())
        owned.add(s)
    for row in a['rows']:
        if row['sense'] != 'L' or row['rhs'] != 1:
            continue
        binary = [i for i in row['terms'] if a['vars'][i]['integer']]
        assert len(binary) == 1
        z = binary[0]
        score = {i for i in row['terms'] if i in defs}
        assert len(score) == 1
        s = next(iter(score))
        t = next(iter(set(row['terms']) - {z, s}))
        assert row['terms'] == {z: F(1), s: F(1), t: F(-1)}
        comparisons[z] = {'score': s, 'threshold': t, 'upper': row_ref(a, row['name'])}
        owned.update((z, t))
    eps = None
    score_to_z = {d['score']: z for z, d in comparisons.items()}
    for row in a['rows']:
        binary = [i for i in row['terms'] if a['vars'][i]['integer']]
        if row['sense'] == 'G' and binary and set(row['terms']) == set(binary):
            assert row['rhs'] == 1 and set(row['terms'].values()) == {F(1)}
            zs = sorted(binary)
            ts = {comparisons[z]['threshold'] for z in zs}
            assert len(ts) == 1
            groups.append({'zs': zs, 'threshold': next(iter(ts)), 'cover': row_ref(a, row['name'])})
        elif row['sense'] == 'G' and binary:
            assert len(binary) == 1
            z = binary[0]
            d = comparisons[z]
            s, t = d['score'], d['threshold']
            epsilon = row['terms'][z]
            assert row['terms'] == {z: epsilon, s: F(1), t: F(-1)} and row['rhs'] == epsilon
            if eps is None:
                eps = epsilon
            assert eps == epsilon
            d['lower'] = row_ref(a, row['name'])
        elif row['sense'] == 'L' and row['rhs'] == 0 and len(row['terms']) == 2:
            ss = {i for i in row['terms'] if i in defs}
            if not ss:
                continue
            s = next(iter(ss))
            t = next(iter(set(row['terms']) - {s}))
            assert row['terms'] == {t: F(1), s: F(-1)}
            comparisons[score_to_z[s]]['nonneg'] = row_ref(a, row['name'])
    assert len(owned) == len(a['vars']) and sum(len(g['zs']) for g in groups) == len(comparisons)
    assert len(a['rows']) == 1 + len(groups) + 4 * len(comparisons)
    for z, d in comparisons.items():
        assert set(d) == {'score', 'threshold', 'lower', 'upper', 'nonneg'}
        v = a['vars'][z]
        assert v['integer'] and v['lower'] == 0 and v['upper'] == 1
    for i in owned - set(comparisons):
        assert not a['vars'][i]['integer'] and a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] is None
    return weights, defs, scores, comparisons, groups, eps


def prepare(a, b, h, number):
    weights, defs, scores, cmp, groups, eps = structure(a)
    n = len(a['vars'])
    proof, f, r = make_proof(a, b)
    eqs = {}
    zero = {}
    one = {}
    tight = {}
    fixed_threshold = {}
    name = lambda i: a['vars'][i]['name']
    hints = h['fixed_zero_binary_certificates'] if number == 51 else h['fixed_zero_binaries']
    ones = h['fixed_one_binaries']
    zero_ids = {a['var_index'][z] for z in hints}
    one_ids = {a['var_index'][z] for z in ones}
    assert not zero_ids & one_ids
    # Canonical source equalities are oriented variable minus reconstruction.
    for s, eq in defs.items():
        eqs[s] = f.lin('Eq', [[eq, -1]], plus(expression(0, {s: 1}), scores[s], -1))
    simplex = row_ref(a, 'c0')
    cache = {}

    def vector_bound(p, e, U):
        assert e[0] == 0 and set(e[1]) <= set(weights) and all(e[1].get(w, 0) <= U for w in weights)
        key = (U, tuple(e[1].get(w, F(0)) for w in weights))
        if key not in cache:
            terms = [[simplex, U]] + \
                    [[{'VarLower': w}, U - e[1].get(w, 0)] for w in weights if U != e[1].get(w, 0)]
            cache[key] = p.lin('Le', terms, plus(e, expression(-U)))
        return cache[key]

    @lru_cache(maxsize=None)
    def difference(i, j):
        return plus(scores[cmp[i]['score']], scores[cmp[j]['score']], -1)

    def source_score_bound(i, j, U):
        e = difference(i, j)
        base = vector_bound(f, e, U)
        return f.lin('Le', [[base, 1], [eqs[cmp[i]['score']], 1], [eqs[cmp[j]['score']], -1]],
                     expression(-U, {cmp[i]['score']: 1, cmp[j]['score']: -1}))
    # Uniform positive dominance rules out selecting the larger score.
    for z in sorted(zero_ids):
        hint = hints[name(z)]
        j = a['var_index'][hint['witness'] if number == 51 else hint['strictly_smaller_score_binary']]
        d = difference(z, j)
        delta = min(d[1].get(w, F(0)) for w in weights)
        assert delta > 0 and cmp[z]['threshold'] == cmp[j]['threshold']
        base = vector_bound(f, mul(d, -1), -delta)
        lower = f.lin('Le', [[base, 1], [eqs[cmp[z]['score']], -1], [eqs[cmp[j]['score']], 1],
                             [cmp[j]['nonneg'], 1]],
                      expression(delta, {cmp[z]['threshold']: 1, cmp[z]['score']: -1}))

        def left(p, ass, z=z):
            return {'Witness': p.eqpair(ass, {'VarLower': z})}

        def right(p, ass, z=z, lower=lower, delta=delta):
            return {'Absurd': p.lin('Le', [[lower, 1], [cmp[z]['upper'], 1], [ass, 1]],
                                    expression(delta))}
        zero[z] = cases(f, 'Eq', expression(0, {z: 1}), z, left, right)
        eqs[z] = zero[z]
    # Reduce actual covers only using already checked zeros.
    group_for = {z: g for g in groups for z in g['zs']}
    for g in groups:
        g['candidates'] = [z for z in g['zs'] if z not in zero_ids]
        assert g['candidates']
        g['cover_reduced'] = f.lin('Le', [[g['cover'], 1]] +
                                   [[zero[z], 1] for z in g['zs'] if z in zero_ids],
                                   expression(1, {z: -1 for z in g['candidates']}))
    bounds = {}
    subset_integers = {}

    def selected_bound(i, U):
        key = (i, U)
        if key in bounds:
            return bounds[key]
        g = group_for[i]
        cs = g['candidates']
        s, t = cmp[i]['score'], cmp[i]['threshold']
        wanted = expression(-U, {s: 1, t: -1})
        pair = {j: source_score_bound(i, j, U) for j in cs if j != i}

        def recurse(p, subset, selected):
            if len(subset) == 1:
                j = subset[0]
                terms = [[cmp[j]['upper'], 1], [selected, 1]]
                if j != i:
                    terms.append([pair[j], 1])
                return {'Witness': p.lin('Le', terms, wanted, constant=-U if j == i else 0)}
            middle = len(subset) // 2
            left = tuple(subset[:middle])
            right = subset[middle:]
            split = expression(0, {j: 1 for j in left})
            integer = p.lin('Int', [[{'VarInt': j}, 1] for j in left], split)

            def no_left(child, ass):
                selected_right = child.lin('Le', [[selected, 1], [ass, 1]],
                                           expression(1, {j: -1 for j in right}))
                return recurse(child, right, selected_right)
            ref = cases(p, 'Le', wanted, (split, integer), no_left,
                        lambda child, ass: recurse(child, left, ass))
            return {'Witness': ref}
        bounds[key] = recurse(f, cs, g['cover_reduced'])['Witness']
        return bounds[key]
    for z in sorted(one_ids):
        g = group_for[z]
        U = max(difference(z, j)[1].get(w, F(0)) for j in g['zs'] for w in weights)
        assert U == 0
        bound = selected_bound(z, U)
        lower = f.lin('Le', [[bound, 1 / eps], [cmp[z]['lower'], 1 / eps]],
                      expression(1, {z: -1}))
        one[z] = f.eqpair({'VarUpper': z}, lower)
        eqs[z] = one[z]
        t, s = cmp[z]['threshold'], cmp[z]['score']
        assert t not in fixed_threshold
        positive = cmp[z]['nonneg']
        negative = f.lin('Le', [[cmp[z]['upper'], 1], [one[z], -1]],
                         expression(0, {s: 1, t: -1}))
        teq = f.eqpair(positive, negative)
        eqs[t] = f.lin('Eq', [[teq, 1], [eqs[s], 1]],
                       plus(expression(0, {t: 1}), scores[s], -1))
        fixed_threshold[t] = z
    # Each retained upper comparison is conditioned on its own binary; a
    # separate exhaustive selected-candidate proof supplies the inactive bound.
    upper_to_z = {next(iter(d['upper'].values())): z for z, d in cmp.items()}
    for row in b['rows']:
        if row['name'] not in a['row_index']:
            raise AssertionError('unexpected target row')
        oldidx = a['row_index'][row['name']]
        if oldidx not in upper_to_z:
            continue
        z = upper_to_z[oldidx]
        assert z not in zero_ids | one_ids
        bi = b['var_index'][name(z)]
        M = row['terms'][bi]
        assert row['rhs'] == M and 0 < M < 1
        g = group_for[z]
        assert all(difference(z, j)[1].get(w, F(0)) <= M
                   for j in g['candidates'] for w in weights)
        bound = selected_bound(z, M)
        wanted = expression(-M, {cmp[z]['score']: 1, cmp[z]['threshold']: -1, z: M})
        tight[row['name']] = cases(f, 'Le', wanted, z,
            lambda p, ass, bound=bound, M=M, wanted=wanted:
                {'Witness': p.lin('Le', [[bound, 1], [ass, M]], wanted)},
            lambda p, ass, z=z, M=M, wanted=wanted:
                {'Witness': p.lin('Le', [[cmp[z]['upper'], 1], [ass, 1 - M]], wanted)})
    forward = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]
    reverse = []
    for i, v in enumerate(a['vars']):
        if v['name'] in b['var_index']:
            reverse.append(expression(0, {b['var_index'][v['name']]: 1}))
        elif i in zero_ids:
            reverse.append(expression())
        elif i in one_ids:
            reverse.append(expression(1))
        elif i in scores:
            reverse.append(expression(0, {b['var_index'][name(w)]: c for w, c in scores[i][1].items()}))
        elif i in fixed_threshold:
            sc = scores[cmp[fixed_threshold[i]]['score']]
            reverse.append(expression(0, {b['var_index'][name(w)]: c for w, c in sc[1].items()}))
        else:
            raise AssertionError(('missing reconstruction', v['name']))
    eliminated = {i for i, v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    assert eliminated == set(eqs)

    def eliminate(ref, wanted):
        terms = [[ref, 1]] + [[eqs[i], -c] for i, c in f.refexpr(ref)[1].items() if i in eliminated]
        if len(terms) == 1:
            assert f.refexpr(ref) == wanted
            return ref
        return f.lin(f.kind(ref), terms, wanted)
    fc = []
    for v in b['vars']:
        i = a['var_index'][v['name']]
        assert v == a['vars'][i]
        if v['lower'] is not None:
            fc.append({'VarLower': i})
        if v['upper'] is not None:
            fc.append({'VarUpper': i})
        if v['integer']:
            fc.append('Exact')
    for row in b['rows']:
        typ = next(iter(row_ref(b, row['name'])))
        wanted = substitute(row_fact(row, typ), forward)
        fc.append(eliminate(tight.get(row['name'], row_ref(a, row['name'])), wanted))
    objective = plus(substitute(b['objective'], forward), a['objective'], -1)
    if objective == expression():
        fc.append('Exact')
    else:
        fc.append(f.lin('Eq', [[eqs[i], -c] for i, c in a['objective'][1].items() if i in eliminated],
                        objective))
    f.finish(forward, fc)
    # All reverse derivations are LP-valid. Bounds on reconstructed continuous
    # coordinates use their actual nonnegative five-weight expressions.
    rw = [b['var_index'][name(w)] for w in weights]
    rsimplex = row_ref(b, 'c0')
    rcache = {}

    def rbound(e, U):
        assert set(e[1]) <= set(rw) and all(e[1].get(w, 0) <= U for w in rw)
        key = (U, tuple(e[1].get(w, F(0)) for w in rw))
        if key not in rcache:
            rcache[key] = r.lin('Le', [[rsimplex, U]] +
                                [[{'VarLower': w}, U - e[1].get(w, 0)] for w in rw if U != e[1].get(w, 0)],
                                plus(e, expression(-U)))
        return rcache[key]

    def lower_bound(e):
        wanted = mul(e, -1)
        if not wanted[1]:
            return r.lin('Le', [], wanted, constant=wanted[0])
        if wanted[0] == 0 and set(wanted[1]) <= set(rw):
            return rbound(wanted, F(0))
        assert e[0] == 0 and len(e[1]) == 1 and next(iter(e[1].values())) == 1
        return {'VarLower': next(iter(e[1]))}
    rnonneg = {}
    for z, d in cmp.items():
        if z in zero_ids:
            continue
        wanted = substitute(f.refexpr(d['nonneg']), reverse)
        if z in one_ids:
            assert wanted == expression()
            rnonneg[z] = r.lin('Le', [], wanted)
        else:
            ref = row_ref(b, a['rows'][next(iter(d['lower'].values()))]['name'])
            bi = b['var_index'][name(z)]
            rnonneg[z] = r.lin('Le', [[ref, 1], [{'VarUpper': bi}, eps]], wanted)
    gapfacts = {}
    for z in sorted(zero_ids):
        d = cmp[z]
        rn = a['rows'][next(iter(d['lower'].values()))]['name']
        wanted = substitute(f.refexpr(d['lower']), reverse)
        if rn in b['row_index']:
            gapfacts[z] = row_ref(b, rn)
            assert r.refexpr(gapfacts[z]) == wanted
            continue
        g = group_for[z]
        j = next((j for j in g['candidates']
                  if all(difference(z, j)[1].get(w, 0) >= eps for w in weights)), None)
        assert j is not None
        diff = expression(0, {b['var_index'][name(w)]: c for w, c in difference(z, j)[1].items()})
        bound = rbound(mul(diff, -1), -eps)
        gapfacts[z] = r.lin('Le', [[bound, 1], [rnonneg[j], 1]], wanted)

    def reverse_checks():
        checks = []
        for i, v in enumerate(a['vars']):
            e = reverse[i]
            if v['lower'] is not None:
                checks.append(lower_bound(e))
            if v['upper'] is not None:
                wanted = plus(e, expression(-v['upper']))
                if not wanted[1]:
                    checks.append(r.lin('Le', [], wanted, constant=wanted[0]))
                else:
                    checks.append({'VarUpper': next(iter(e[1]))})
            if v['integer']:
                checks.append('Exact')
        cmp_by_row = {next(iter(ref.values())): (z, k) for z, d in cmp.items()
                      for k, ref in d.items() if isinstance(ref, dict)}
        group_by_row = {next(iter(g['cover'].values())): g for g in groups}
        for idx, row in enumerate(a['rows']):
            typ = next(iter(row_ref(a, row['name'])))
            wanted = substitute(row_fact(row, typ), reverse)
            if row['sense'] == 'E':
                assert wanted == expression() or row['name'] == 'c0'
                check = 'Exact' if wanted == expression() else row_ref(b, 'c0')
            elif row['name'] in b['row_index']:
                check = row_ref(b, row['name'])
                if idx in cmp_by_row and cmp_by_row[idx][1] == 'upper':
                    z = cmp_by_row[idx][0]
                    M = b['rows'][b['row_index'][row['name']]]['rhs']
                    check = r.lin('Le', [[check, 1], [{'VarUpper': b['var_index'][name(z)]}, 1 - M]],
                                  wanted)
                else:
                    assert r.refexpr(check) == wanted
            elif idx in group_by_row:
                assert wanted[0] <= 0 and all(c == -1 for c in wanted[1].values())
                check = r.lin('Le', [[{'VarLower': i}, 1] for i in wanted[1]],
                              wanted, constant=wanted[0])
            else:
                z, k = cmp_by_row[idx]
                d = cmp[z]
                if k == 'lower':
                    if z in zero_ids:
                        check = gapfacts[z]
                    else:
                        assert wanted == expression()
                        check = 'Exact'
                elif k == 'nonneg':
                    if z in zero_ids:
                        check = r.lin('Le', [[gapfacts[z], 1]], wanted, constant=-eps)
                    else:
                        check = rnonneg[z]
                elif k == 'upper':
                    if z in one_ids:
                        assert wanted == expression()
                        check = 'Exact'
                    else:
                        se = reverse[d['score']]
                        bound = rbound(se, F(1))
                        tref = lower_bound(reverse[d['threshold']])
                        check = r.lin('Le', [[bound, 1], [tref, 1]], wanted)
                else:
                    raise AssertionError(k)
            checks.append(check)
        assert substitute(a['objective'], reverse) == b['objective']
        checks.append('Exact')
        return checks
    rc = reverse_checks()
    r.finish(reverse, rc)
    return proof, {'source_variables': n, 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'groups': len(groups), 'fixed_zero_binaries': len(zero_ids),
                   'fixed_one_binaries': len(one_ids),
                   'eliminated_scores': len(scores),
                   'eliminated_thresholds': len(fixed_threshold),
                   'conditional_upper_bounds': len(tight),
                   'retained_exceptional_gap_rows': 4, 'directions': 2,
                   'obligations_by_claim': [len(fc), len(rc)]}


def run_case(number, script):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--out', type=Path, default=Path(f'cases/test{number}'))
    args = parser.parse_args()
    started = time.perf_counter()
    inventory = Path(__file__).resolve().parent.parent / 'audit/corpus_inventory.json'
    entry = next(e for e in json.loads(inventory.read_text())['cases']
                 if e['case_id'] == f'test{number}')
    run = Path(entry['run_directory']) if args.run is None else args.run.resolve()
    source = run / entry['source_models'][0]['path']
    target = run / entry['final_target_models'][0]['path']
    audit = run / 'output/audit.json'
    assert sha(source) == entry['source_models'][0]['sha256']
    assert sha(target) == entry['final_target_models'][0]['sha256']
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()), number)
    metadata = {'audit': {'path': str(audit), 'sha256': sha(audit)},
                'proof_preparer': {'path': str(Path(script).resolve()),
                                   'sha256': sha(Path(script))},
                'counts': counts,
                'preparation_seconds': time.perf_counter() - started}
    if number == 52:
        metadata['proof_preparer_dependencies'] = [
            {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))}]
    record = compile_case(proof, args.out, case_id=f'test{number}', source=source,
                          target=target, metadata=metadata)
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': record['case_id'], 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    run_case(51, __file__)
