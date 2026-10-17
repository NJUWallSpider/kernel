#!/usr/bin/env python3
"""Actual test41 exact integer affine bijection and target LP inclusion."""
from pathlib import Path
from fractions import Fraction as F
import json
import time
import argparse
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact
from prepare_native import compile_case, make_proof, sha
from prepare_test31 import mapped, trivial


def cases_le(builder, wanted, variable, left, right):
    return builder.cases('Le', wanted, expression(0, {variable: 1}),
                         integer={'VarInt': variable}, left=left, right=right)


def prepare(a, b, h):
    proof, f, r = make_proof(a, b)
    c = h['certificates']
    eliminated = {}
    lift = {}
    bounds = {}
    conditionals = {}
    nonempty = {}
    caps = {}
    for name, arc in c['arcs'].items():
        i = a['var_index'][name]
        cut = c['suffix_cuts'][str(arc['head'])]
        U = F(arc['upper'])
        bounds[i] = f.lin('Le', [[row_ref(a, rn), -1] for rn in cut['rows']] +
                          [[{'VarLower': a['var_index'][n]}, 1]
                           for n in cut['incoming_arcs'] if n != name],
                          expression(-U, {i: 1}))
    for z in c['binary_aliases']:
        i = a['var_index'][z['eliminate']]
        j = a['var_index'][z['keep']]
        refs = [row_ref(a, rn) for rn in z['rows']]
        p = next(ref for ref in refs if 'RowLower' in ref)
        n = next(ref for ref in refs if 'RowUpper' in ref)
        eliminated[i] = f.eqpair(p, n)
        lift[i] = expression(0, {j: 1})
        assert f.refexpr(eliminated[i]) == expression(0, {i: 1, j: -1})
    for block in c['interval_blocks']:
        t, d, z, w = [a['var_index'][block[k]] for k in ['t', 'd', 'z', 'weight_variable']]
        U = F(block['U'])
        rs = block['rows']
        zr = row_ref(a, rs[2])
        eliminated[z] = zr
        lift[z] = expression(1)
        pos = f.lin('Le', [[row_ref(a, rs[1]), 1], [zr, -61]], expression(0, {d: 1, t: -1}))
        eliminated[d] = f.eqpair(pos, row_ref(a, rs[0]))
        lift[d] = expression(0, {t: 1})
        remaining = []
        for pair in block['pairs']:
            y = a['var_index'][pair['y']]
            l = F(pair['lower'])
            u = F(pair['upper'])
            if l > U:
                le = f.lin('Le', [[row_ref(a, pair['lower_row']), 1 / l],
                                  [eliminated[d], 1 / l], [bounds[t], 1 / l]],
                           expression(-U / l, {y: 1}))
                up = f.round(le, {'VarInt': y})
                eliminated[y] = f.eqpair(up, {'VarLower': y})
                lift[y] = expression()
            else:
                remaining.append(y)
            if l <= U and u < U:
                wanted = expression(-U, {t: 1, y: U - u})
                old = f.lin('Le', [[row_ref(a, pair['upper_row']), 1], [eliminated[d], -1]])
                conditionals[pair['upper_row']] = cases_le(
                    f, wanted, y,
                    lambda child, zero, t=t, y=y, U=U, u=u:
                        child.lin('Le', [[bounds[t], 1], [zero, U - u]], wanted),
                    lambda child, one, old=old, U=U:
                        child.lin('Le', [[old, 1], [one, 61 - U]], wanted))
        weights = {a['var_index'][n]: F(v) for n, v in block['weights'].items()}
        eliminated[w] = row_ref(a, rs[-1])
        lift[w] = expression(0, weights)
        # Integer nonempty selection: weighted lower bound plus nonnegativity,
        # followed by exact rounding of the integer count (no idealized decimals).
        mx = max(weights[i] for i in remaining)
        terms = ([[{'VarLower': w}, 1 / mx], [eliminated[w], 1 / mx]] +
                 [[eliminated[i], weights[i] / mx] for i in weights if i not in remaining] +
                 [[{'VarLower': i}, 1 - weights[i] / mx]
                  for i in remaining if weights[i] != mx])
        le = f.lin('Le', terms, expression(F(9) / mx, {i: -1 for i in remaining}))
        inte = f.lin('Int', [[{'VarInt': i}, -1] for i in remaining])
        nonempty[rs[-1]] = f.round(le, inte)
        if block['new_weight_cap_rows']:
            caps[block['new_weight_cap_rows'][0]] = f.lin(
                'Le', [[{'VarUpper': w}, 1], [eliminated[w], -1]] +
                [[eliminated[i], -weights[i]] for i in weights if i not in remaining],
                expression(-105, {i: weights[i] for i in remaining}))
    assert len(eliminated) == 328
    forward = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]

    def reduce_fact(ref):
        e = f.refexpr(ref)
        return [[ref, 1]] + [[eliminated[i], -q] for i, q in e[1].items() if i in eliminated]

    def rewrite(ref, kind, e):
        terms = reduce_fact(ref)
        result = f.lin(kind, terms, e) if len(terms) > 1 else ref
        assert f.refexpr(result) == e
        return result

    fc = []
    for v in b['vars']:
        i = a['var_index'][v['name']]
        if v['lower'] is not None:
            fc.append({'VarLower': i})
        if v['upper'] is not None:
            fc.append(bounds.get(i, {'VarUpper': i}))
        if v['integer']:
            fc.append({'VarInt': i})
    for row in b['rows']:
        rn = row['name']
        typ = next(iter(row_ref(b, rn)))
        e = mapped(row_fact(row, typ), forward)
        if rn in conditionals:
            ref = conditionals[rn]
        elif rn in nonempty:
            ref = nonempty[rn]
        elif rn in caps:
            ref = caps[rn]
        else:
            ref = rewrite(row_ref(a, rn), 'Eq' if typ == 'RowEq' else 'Le', e)
        assert f.refexpr(ref) == e
        fc.append(ref)
    reverse = []
    rename = [expression(0, {b['var_index'][vv['name']]: 1})
              if vv['name'] in b['var_index'] else expression() for vv in a['vars']]
    for i, v in enumerate(a['vars']):
        es = lift.get(i, expression(0, {i: 1}))
        reverse.append(mapped(es, rename))
    assert mapped(a['objective'], reverse) == b['objective']
    wanted = mapped(b['objective'], forward)
    diff = expression(wanted[0] - a['objective'][0],
                      {i: wanted[1].get(i, 0) - a['objective'][1].get(i, 0)
                       for i in set(wanted[1]) | set(a['objective'][1])})
    fc.append(f.lin('Eq', [[eliminated[i], q] for i, q in diff[1].items() if i in eliminated],
                    diff))
    f.finish(forward, fc)

    old_upper = {p['upper_row']: (block, p) for block in c['interval_blocks']
                 for p in block['pairs']}
    weighted = {a['var_index'][block['weight_variable']]: block
                for block in c['interval_blocks']}
    rchecks = []

    def bounded(e):
        terms = []
        constant = e[0]
        for j, q in e[1].items():
            typ = 'VarUpper' if q > 0 else 'VarLower'
            bound = b['vars'][j]['upper' if q > 0 else 'lower']
            assert bound is not None
            terms.append([{typ: j}, abs(q)])
            constant += q * bound
        assert constant <= 0, ('not box-implied', e, constant)
        return r.lin('Le', terms, e, constant=constant)

    def wbound(i, upper, e):
        block = weighted[i]
        defrn = block['rows'][-1]
        if upper:
            if block['new_weight_cap_rows']:
                ref = row_ref(b, block['new_weight_cap_rows'][0])
                assert r.refexpr(ref) == e
                return ref
            return bounded(e)
        coeffs = {j: -q for j, q in e[1].items()}
        mn = min(coeffs.values())
        ref = row_ref(b, defrn)
        return r.lin('Le', [[ref, mn]] +
                     [[{'VarLower': j}, q - mn] for j, q in coeffs.items() if q != mn],
                     e, constant=e[0] - mn)

    for i, v in enumerate(a['vars']):
        es = reverse[i]
        for upper, bound in [(False, v['lower']), (True, v['upper'])]:
            if bound is None:
                continue
            sign = 1 if upper else -1
            e = expression(sign * (es[0] - bound), {j: sign * q for j, q in es[1].items()})
            if trivial('Le', e):
                ref = 'Exact'
            elif i in weighted:
                ref = wbound(i, upper, e)
            else:
                ref = bounded(e)
            rchecks.append(ref)
        if v['integer']:
            if trivial('Int', es):
                rchecks.append('Exact')
            else:
                assert es[0] == 0 and len(es[1]) == 1
                rchecks.append({'VarInt': next(iter(es[1]))})
    for row in a['rows']:
        rn = row['name']
        typ = next(iter(row_ref(a, rn)))
        e = mapped(row_fact(row, typ), reverse)
        kind = 'Eq' if typ == 'RowEq' else 'Le'
        if trivial(kind, e):
            ref = 'Exact'
        elif rn == c['removed_flow_row']['row']:
            ref = r.lin('Eq', [[row_ref(b, n), F(q)]
                               for n, q in c['removed_flow_row']['linear_combination'].items()], e)
        elif rn in b['row_index'] and rn not in nonempty:
            base = row_ref(b, rn)
            if r.refexpr(base) == e:
                ref = base
            else:
                block, pair = old_upper[rn]
                y = b['var_index'][pair['y']]
                U = F(block['U'])
                ref = r.lin('Le', [[base, 1], [{'VarUpper': y}, 61 - U]], e)
        else:
            assert kind == 'Le'
            ref = bounded(e)
        rchecks.append(ref)
    rchecks.append('Exact')
    r.finish(reverse, rchecks)
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'removed_variables': len(eliminated),
                   'conditional_bounds': len(conditionals),
                   'flow_cut_bounds': len(bounds), 'directions': 2,
                   'obligations_by_direction': {'forward': len(fc), 'reverse': len(rchecks)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('cases/test41'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = Path('/Users/bhz/Code/reform_test/runs/test41-nomf-B1')
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    h = json.loads(audit.read_text())
    proof, counts = prepare(parse_mps(source), parse_mps(target), h)
    record = compile_case(proof, args.out, case_id='test41', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test41', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
