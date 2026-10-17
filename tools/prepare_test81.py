#!/usr/bin/env python3
"""Exact full-model time-window certificates as native MI-OPT directions."""
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_native import compile_case, make_proof


def parse(path):
    # The shared parser predates explicit OBJSENSE. Only an explicit MIN block
    # is stripped for that parser; the kernel canonicalizes the original bytes.
    class Input:
        def read_text(self):
            lines = path.read_text().splitlines()
            out = []
            i = 0
            while i < len(lines):
                if lines[i].strip() == 'OBJSENSE':
                    assert lines[i + 1].strip() == 'MIN'
                    i += 2
                else:
                    out.append(lines[i])
                    i += 1
            return '\n'.join(out)

    return parse_mps(Input())


def cases_le(builder, wanted, variable, left, right):
    return builder.cases('Le', wanted, expression(0, {variable: 1}),
                         integer={'VarInt': variable}, left=left, right=right)


def zero_case(p, x, packing, old, D, upper_difference):
    wanted = expression(0, {x: 1})

    def left(child, assumption):
        return {'Witness': child.eqpair(assumption, {'VarLower': x})}

    def right(child, assumption):
        qzero = child.lin('Le', [[packing, 1], [assumption, 1]])
        contradiction = child.lin('Le', [[old, 1], [qzero, D],
                                         [assumption, 60000], [upper_difference, 1]])
        e = child.refexpr(contradiction)
        assert not e[1] and e[0] > 0
        return {'Absurd': contradiction}

    return p.cases('Eq', wanted, expression(0, {x: 1}), integer={'VarInt': x},
                   left=left, right=right)


def prepare(a, b, case=81):
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    removed = sorted(set(range(len(a['vars']))) - {i for i, j in common})
    forward = [expression(0, {i: 1}) for i, j in common]
    reverse = [expression(0, {b['var_index'][v['name']]: 1})
               if v['name'] in b['var_index'] else expression() for v in a['vars']]
    assert len(a['vars']) == 11090 and len(a['rows']) == 4630
    assert len(removed) == (3341 if case == 81 else 3315)
    windows = {}
    for row in a['rows']:
        if len(row['terms']) == 1:
            i, c = next(iter(row['terms'].items()))
            if not a['vars'][i]['integer']:
                assert c == 1 and row['sense'] in ('G', 'L')
                side = 'lower' if row['sense'] == 'G' else 'upper'
                windows.setdefault(i, {})[side] = (row['rhs'], row_ref(a, row['name']))
    assert len(windows) == 65
    for i, w in windows.items():
        assert set(w) == {'lower', 'upper'}
        j = b['var_index'][a['vars'][i]['name']]
        assert b['vars'][j]['lower'] == w['lower'][0] and \
            b['vars'][j]['upper'] == w['upper'][0]
    pairs = {}
    for row in a['rows']:
        if len(row['terms']) != 4 or row['sense'] != 'G':
            continue
        continuous = [i for i in row['terms'] if not a['vars'][i]['integer']]
        if len(continuous) != 2:
            continue
        ti = next(i for i in continuous if row['terms'][i] == -1)
        tj = next(i for i in continuous if row['terms'][i] == 1)
        x = next(i for i in row['terms'] if row['terms'][i] == -60000)
        q = next(i for i in row['terms'] if i not in (ti, tj, x))
        D = row['terms'][q]
        A = row['rhs'] + 60000
        B = windows[tj]['lower'][0] - windows[ti]['upper'][0]
        M = A - B
        assert D > 0 and 0 <= 60000 - M and D == A
        assignment = next(r for r in a['rows'] if r['sense'] == 'E' and r['rhs'] == 1
                          and q in r['terms'] and x in r['terms'])
        assert all(c == 1 for c in assignment['terms'].values())
        pairs[row['name']] = (ti, tj, x, q, D, A, B, M, assignment)
    assert len(pairs) == 4160
    proof, f, r = make_proof(a, b)
    zero = {}
    tight = {}
    path = {}
    packing = {}

    def difference(ti, tj, upper=False):
        key = (ti, tj, upper)
        if key not in path:
            refs = [windows[ti]['lower' if upper else 'upper'][1],
                    windows[tj]['upper' if upper else 'lower'][1]]
            path[key] = f.lin('Le', [[ref, 1] for ref in refs])
        return path[key]

    for rn, (ti, tj, x, q, D, A, B, M, assignment) in pairs.items():
        if x not in removed and rn not in b['row_index']:
            assert B >= A
            continue
        assert a['vars'][q]['integer'] and a['vars'][x]['integer'] and \
            a['vars'][q]['lower'] == a['vars'][x]['lower'] == 0 and \
            a['vars'][q]['upper'] == a['vars'][x]['upper'] == 1
        pack = f.lin('Le', [[row_ref(a, assignment['name']), 1]] +
                     [[{'VarLower': i}, 1] for i in assignment['terms']
                      if i not in (q, x)], expression(-1, {q: 1, x: 1}))
        packing[rn] = pack
        if x in removed:
            zero[x] = zero_case(f, x, pack, row_ref(a, rn), D,
                                difference(ti, tj, True))
        else:
            wanted = substitute(row_fact(b['rows'][b['row_index'][rn]], 'RowLower'),
                                forward)
            assert wanted == expression(B, {ti: 1, tj: -1, x: M}) and M > 0
            old = row_ref(a, rn)
            bound = difference(ti, tj)
            tight[rn] = cases_le(
                f, wanted, x,
                lambda c, ref, bound=bound, M=M, wanted=wanted:
                    c.lin('Le', [[bound, 1], [ref, M]], wanted),
                lambda c, ref, old=old, pack=pack, D=D, M=M, wanted=wanted:
                    c.lin('Le', [[old, 1], [pack, D], [ref, 60000 + D - M]], wanted))
    assert set(zero) == set(removed) and len(tight) == (762 if case == 81 else 792)

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        p = r if back else f
        checks = []
        bounds = {i: {side: (v[side], {('VarLower' if side == 'lower' else 'VarUpper'): i})
                      for side in ('lower', 'upper') if v[side] is not None}
                  for i, v in enumerate(inp['vars'])}
        if not back:
            for i, w in windows.items():
                bounds[i] = w

        def prove(kind, wanted, terms=None):
            terms = [] if terms is None else list(terms)
            got = expression()
            for ref, c in terms:
                got = plus(got, p.refexpr(ref), c)
            residual = plus(wanted, got, -1)
            if not back:
                for i, c in list(residual[1].items()):
                    if i in zero:
                        terms.append([zero[i], c])
                        residual = plus(residual, p.refexpr(zero[i]), -c)
            if residual == expression():
                if not terms:
                    return 'Exact'
                if len(terms) == 1 and terms[0][1] == 1:
                    return terms[0][0]
                return p.lin(kind, terms, wanted)
            assert kind == 'Le', (kind, wanted, residual)
            ceiling = residual[0]
            for i, c in residual[1].items():
                value, ref = bounds[i]['upper' if c > 0 else 'lower']
                terms.append([ref, abs(c)])
                ceiling += c * value
            assert ceiling <= 0, ('positive residual', back, wanted, ceiling)
            return p.lin('Le', terms, wanted, ceiling)

        for i, v in enumerate(out['vars']):
            for side, sign in [('lower', -1), ('upper', 1)]:
                if v[side] is not None:
                    checks.append(prove('Le', plus(mul(mapping[i], sign),
                                                   expression(-sign * v[side]))))
            if v['integer']:
                checks.append({'VarInt': next(iter(mapping[i][1]))}
                              if mapping[i][1] else 'Exact')
        for row in out['rows']:
            rn = row['name']
            typ = next(iter(row_ref(out, rn)))
            wanted = substitute(row_fact(row, typ), mapping)
            kind = 'Eq' if typ == 'RowEq' else 'Le'
            if not back and rn in tight:
                ref = tight[rn]
                assert p.refexpr(ref) == wanted
            elif rn in inp['row_index']:
                ref = prove(kind, wanted, [[row_ref(inp, rn), 1]])
            elif back and rn == 'c209':
                ref = prove('Eq', wanted,
                            [[row_ref(b, f'c{k}'), 1 if k < 105 else -1]
                             for k in range(209)])
            else:
                ref = prove(kind, wanted)
            checks.append(ref)
        objective = plus(substitute(out['objective'], mapping), inp['objective'], -1)
        checks.append(prove('Eq', objective))
        p.finish(mapping, checks)

    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'zero_arcs': len(zero), 'conditional_M_rows': len(tight),
                   'automatic_pair_rows': 4160 - len(zero) - len(tight),
                   'window_bound_pairs': len(windows), 'domain_implied_rows': 130,
                   'dependent_equality_deletions': int(case == 82),
                   'directions': 2}


def main(case=81):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(f'cases/test{case}'))
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    inventory = json.loads(
        (Path(__file__).resolve().parent.parent / 'audit/corpus_inventory.json').read_text())
    entry = next(x for x in inventory['cases'] if x['case_id'] == f'test{case}')
    run = Path(entry['run_directory']) if args.run is None else args.run.resolve()
    source = run / entry['source_models'][0]['path']
    target = run / entry['final_target_models'][0]['path']
    audit = run / 'output/audit.json'
    assert sha(source) == entry['source_models'][0]['sha256']
    assert sha(target) == entry['final_target_models'][0]['sha256']
    proof, counts = prepare(parse(source), parse(target), case)
    record = compile_case(proof, args.out, case_id=f'test{case}', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': record['case_id'], 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
