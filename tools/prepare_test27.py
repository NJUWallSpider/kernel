#!/usr/bin/env python3
"""Native signed-flow/shared-activation proof for test27.

The forward direction is one joint interval lift followed by complete-model
obligations.  The reverse direction is one joint signed decomposition followed
by complete-model obligations.  Every generated coordinate and row comes from
the native lift layout; no manual extension model is constructed.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha, signature
from prepare_native import compile_case, make_proof


def boolean_expr(p, e):
    if not e[1]:
        assert e[0] in (0, 1)
        return {'expr': e, 'value': e[0]}
    assert len(e[1]) == 1 and e[0] == 0 and next(iter(e[1].values())) == 1
    index = next(iter(e[1]))
    return {'expr': e,
            'lower': p.prove('Le', mul(e, -1)),
            'upper': p.prove('Le', plus(e, expression(-1))),
            'integer': p.lin('Int', [[{'VarInt': index}, F(1)]], e),
            'variable': index}


def binary_value(child, variable, value, assumption):
    if value == 0:
        return child.eqpair(assumption, child.ref({'VarLower': variable}))
    return child.eqpair(child.ref({'VarUpper': variable}), assumption)


def case_all(p, kind, wanted, bits, leaf):
    variable = []
    assigned = {}
    for bit in bits:
        key = signature(bit['expr'])
        if 'value' in bit:
            assigned[key] = (bit['value'], None)
        elif key not in [signature(x['expr']) for x in variable]:
            variable.append(bit)

    def recurse(cur, index, state):
        if index == len(variable):
            return leaf(cur, state)
        bit = variable[index]
        key = signature(bit['expr'])
        variable_index = bit['variable']

        def branch(child, assumption, value):
            fact = child._assumption_facts[assumption['Assumption']]
            return recurse(child, index + 1,
                           {**state, key: (F(value),
                                           binary_value(child, variable_index, value, fact))})

        return cur.cases(kind=kind, expected=wanted, split=bit['expr'],
                         integer=bit.get('integer'),
                         left=lambda child, assumption: branch(child, assumption, 0),
                         right=lambda child, assumption: branch(child, assumption, 1))

    return recurse(p, 0, assigned)


def checks(p, output, mapping, claim, domains, rows, objective):
    result = []
    for i, v in enumerate(output['vars']):
        for kind, typ, bound in [('Le', 'VarLower', v['lower']),
                                 ('Le', 'VarUpper', v['upper']),
                                 ('Int', 'VarInt', None)]:
            if typ == 'VarInt':
                if not claim['output_integers'] or not v['integer']:
                    continue
                wanted = mapping[i]
            else:
                if bound is None:
                    continue
                wanted = (plus(expression(bound), mapping[i], -1) if typ == 'VarLower'
                          else plus(mapping[i], expression(-bound)))
            ref = domains[(i, typ)]
            assert ref == 'Exact' or (p.kind(ref) in (kind, 'Eq') and
                                     p.refexpr(ref) == wanted), (i, typ)
            result.append(ref)
    for i, row in enumerate(output['rows']):
        wanted = substitute(row_fact(row, next(iter(row_ref(output, row['name'])))), mapping)
        ref = rows[i]
        assert p.refexpr(ref) == wanted
        result.append(ref)
    wanted = plus(substitute(output['objective'], mapping), p.model['objective'], -1)
    assert p.refexpr(objective) == wanted
    result.append(objective)
    return result


def prepare(a, b, h):
    pairs = h['pairs']
    C = F(h['capacity'])
    assert len(pairs) == 760
    proof, f, r = make_proof(a, b)

    intervals = []
    for d in pairs:
        u, v = [a['var_index'][d[k]] for k in ['forward_activation', 'reverse_activation']]
        assert all(a['vars'][i]['integer'] and a['vars'][i]['lower'] == 0 and
                   a['vars'][i]['upper'] == 1 for i in [u, v])
        intervals.append({'lower': [expression(0, {u: 1}), expression(0, {v: 1})],
                          'upper': [expression(0, {u: 1, v: 1}), expression(1)],
                          'checks': [{'VarLower': v}, {'VarUpper': u},
                                     {'VarLower': u}, {'VarUpper': v}]})

    p = f.intervals(intervals)
    layout = p.old_layout
    mapping = [None] * len(b['vars'])
    domains = {}
    rows = {}
    cost = []
    for d, entry in zip(pairs, layout):
        aa, bb, u, v = [a['var_index'][d[k]] for k in
                        ['forward_flow', 'reverse_flow', 'forward_activation', 'reverse_activation']]
        flow, activation = [b['var_index'][d[k]] for k in ['flow', 'activation']]
        zz = entry['variable']
        ze = expression(0, {zz: 1})
        lo = [{'RowLower': index} for index in entry['lower']]
        hi = [{'RowUpper': index} for index in entry['upper']]
        mapping[flow] = expression(0, {aa: 1, bb: -1})
        mapping[activation] = ze
        lower = p.lin('Le', [[lo[0], F(1)], [{'VarLower': u}, F(1)]], mul(ze, -1))
        upper = hi[1]
        bits = [boolean_expr(p, expression(0, {i: 1})) for i in [u, v]]

        def leaf(child, state):
            uv = [state[signature(bit['expr'])] for bit in bits]
            value = max(x[0] for x in uv)
            if value:
                j = next(j for j, x in enumerate(uv) if x[0] == 1)
                lower1 = child.lin('Le', [[lo[j], F(1)], [uv[j][1], F(-1)]],
                                   plus(expression(1), ze, -1))
                eq = child.eqpair(upper, lower1)
            else:
                upper0 = child.lin('Le', [[hi[0], F(1)]] + [[x[1], F(1)] for x in uv], ze)
                eq = child.eqpair(upper0, lower)
            return child.lin('Int', [[eq, F(1)]], ze, constant=value)

        integer = case_all(p, 'Int', ze, bits, leaf)
        domains[(activation, 'VarLower')] = lower
        domains[(activation, 'VarUpper')] = upper
        domains[(activation, 'VarInt')] = integer
        rows[b['row_index'][d['upper_link']]] = p.lin(
            'Le', [[row_ref(a, d['forward_link']), F(1)], [lo[0], C],
                   [{'VarLower': bb}, F(1)]], plus(mapping[flow], ze, -C))
        rows[b['row_index'][d['lower_link']]] = p.lin(
            'Le', [[row_ref(a, d['reverse_link']), F(1)], [lo[1], C],
                   [{'VarLower': aa}, F(1)]], plus(mul(mapping[flow], -1), ze, -C))
        cost.append([hi[0], F(d['cost'])])
    for i, row in enumerate(b['rows']):
        if i not in rows:
            ref = row_ref(a, row['name'])
            assert p.refexpr(ref) == substitute(row_fact(row, 'RowEq'), mapping)
            rows[i] = ref
    objective = p.lin('Le', cost,
                      plus(substitute(b['objective'], mapping), a['objective'], -1))
    fchecks = checks(p, b, mapping, {'output_integers': True}, domains, rows, objective)
    p.finish(mapping, fchecks)

    items = []
    for d in pairs:
        flow, activation = [b['var_index'][d[k]] for k in ['flow', 'activation']]
        items.append({'capacity': C,
                      'flow': expression(0, {flow: 1}),
                      'activation': expression(0, {activation: 1}),
                      'checks': [{'VarLower': activation}, {'VarUpper': activation},
                                 {'VarInt': activation}, row_ref(b, d['upper_link']),
                                 row_ref(b, d['lower_link'])]})
    child = r.signed(items)
    layout = child.old_layout
    mapping = [None] * len(a['vars'])
    domains = {}
    rows = {}
    cost = []
    flowalias = {}
    for d, entry in zip(pairs, layout):
        aa, bb, u, v = [a['var_index'][d[k]] for k in
                        ['forward_flow', 'reverse_flow', 'forward_activation', 'reverse_activation']]
        for old, new in [(aa, entry['positive']), (bb, entry['negative']),
                         (u, entry['positive_activation']), (v, entry['negative_activation'])]:
            mapping[old] = expression(0, {new: 1})
            domains[(old, 'VarLower')] = {'VarLower': new}
            if a['vars'][old]['upper'] is not None:
                domains[(old, 'VarUpper')] = {'VarUpper': new}
            if a['vars'][old]['integer']:
                domains[(old, 'VarInt')] = {'VarInt': new}
        rows[a['row_index'][d['forward_link']]] = {'RowUpper': entry['positive_capacity_row']}
        rows[a['row_index'][d['reverse_link']]] = {'RowUpper': entry['negative_capacity_row']}
        cost.append([{'RowEq': entry['activation_row']}, F(d['cost'])])
        flowalias[b['var_index'][d['flow']]] = {'RowEq': entry['flow_row']}
        child.add('Eq', {'RowEq': entry['flow_row']})
    for i, row in enumerate(a['rows']):
        if i in rows:
            continue
        if row['name'] == h['deleted_balance']['row']:
            terms = [[row_ref(b, name), F(-1)] for name in h['retained_balances']]
            base = child.lin('Eq', terms)
        else:
            base = row_ref(b, row['name'])
        raw = child.refexpr(base)
        terms = [[base, F(1)]] + [[flowalias[j], coefficient]
                                  for j, coefficient in raw[1].items()]
        wanted = substitute(row_fact(row, 'RowEq'), mapping)
        rows[i] = child.lin('Eq', terms, wanted)
    objective = child.lin('Eq', cost,
                          plus(substitute(a['objective'], mapping), b['objective'], -1))
    rchecks = checks(child, a, mapping, {'output_integers': True}, domains, rows, objective)
    child.finish(mapping, rchecks)

    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'claims': 2, 'signed_pairs': len(pairs),
              'interval_variables': len(p.scope.generated_variables),
              'signed_variables': len(child.scope.generated_variables),
              'obligations_by_claim': [len(fchecks), len(rchecks)],
              'linear_steps_forward_prelude': len(f.steps),
              'linear_steps_forward_body': len(p.scope.steps),
              'linear_steps_reverse_prelude': len(r.steps),
              'linear_steps_reverse_body': len(child.scope.steps)}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test27-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test27'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test27', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test27', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
