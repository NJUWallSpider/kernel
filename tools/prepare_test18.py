#!/usr/bin/env python3
"""Native test18 saturation/projection proof with two MI-OPT directions.

The legacy projective fiber-strictness clause is not representable by the
current integer MI-OPT Return obligations and is no longer claimed.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from audit_test18 import inspect
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_native import compile_case, make_proof


def alias(builder, group, edge):
    x = group['binary']
    d = len(group['edges'])
    desired = expression(0, {edge: 1, x: -1})
    eq = {'RowEq': group['row']}
    if d == 1:
        assert builder.refexpr(eq) == desired
        return eq
    others = [i for i in group['edges'] if i != edge]

    def zero(b, assumption):
        pos = b.lin('Le', [[eq, F(1)], [assumption, F(d - 1)]] +
                    [[{'VarLower': i}, F(1)] for i in others], desired)
        neg = b.lin('Le', [[assumption, F(1)], [{'VarLower': edge}, F(1)]],
                    mul(desired, -1))
        return {'Witness': b.eqpair(pos, neg)}

    def one(b, assumption):
        pos = b.lin('Le', [[{'VarUpper': edge}, F(1)], [assumption, F(1)]], desired)
        neg = b.lin('Le', [[eq, F(-1)], [assumption, F(d - 1)]] +
                    [[{'VarUpper': i}, F(1)] for i in others], mul(desired, -1))
        return {'Witness': b.eqpair(pos, neg)}

    return builder.cases('Eq', desired, expression(0, {x: 1}),
                         integer={'VarInt': x}, left=zero, right=one)


def finish_checks(builder, output, mapping, domain_proof, row_proof, objective_proof):
    checks = []

    def prove(kind, e, terms):
        if not e[1] and ((kind == 'Eq' and e[0] == 0) or
                         (kind == 'Le' and e[0] <= 0) or
                         (kind == 'Int' and e[0].denominator == 1)):
            checks.append('Exact')
            return
        if (len(terms) == 1 and terms[0][1] == 1 and builder.kind(terms[0][0]) == kind and
                builder.refexpr(terms[0][0]) == e):
            checks.append(terms[0][0])
            return
        checks.append(builder.lin(kind, terms, e))

    for i, v in enumerate(output['vars']):
        if v['lower'] is not None:
            prove('Le', plus(expression(v['lower']), mapping[i], -1),
                  domain_proof(i, 'VarLower'))
        if v['upper'] is not None:
            prove('Le', plus(mapping[i], expression(-v['upper'])),
                  domain_proof(i, 'VarUpper'))
        if v['integer']:
            prove('Int', mapping[i], domain_proof(i, 'VarInt'))
    for i, row in enumerate(output['rows']):
        typ = next(iter(row_ref(output, row['name'])))
        prove('Eq' if typ == 'RowEq' else 'Le',
              substitute(row_fact(row, typ), mapping), row_proof(i))
    prove('Eq', plus(substitute(output['objective'], mapping),
                     builder.model['objective'], -1), objective_proof)
    return checks


def prepare(a, b, h):
    w = inspect(a, b, h)
    projection = w['reverse_projection']
    proof, forward_builder, reverse_builder = make_proof(a, b)
    f = forward_builder
    aliases = {}
    for g in w['saturation']:
        for edge in g['edges']:
            aliases[edge] = alias(f, g, edge)
    y_eq = {}
    packing = {}
    for y in w['eliminated_y']:
        desired = expression(0, {y['source_variable']: 1})
        for target_i in y['support']:
            desired = plus(desired, expression(0, {projection[target_i][1]: 1}), -1)
        y_eq[y['source_variable']] = f.lin(
            'Eq', [[{'RowEq': y['source_row']}, F(-1)]] +
            [[aliases[i], F(1)] for i in y['edges']], desired)
        name = a['rows'][y['source_row']]['name']
        if name in b['row_index']:
            packing[b['row_index'][name]] = [
                [{'VarUpper': y['source_variable']}, F(1)],
                [y_eq[y['source_variable']], F(-1)]]
    budget = b['row_index'][h['retained_budget']['row']]
    packing[budget] = ([[row_ref(a, h['retained_budget']['row']), F(1)]] +
                       [[{'VarLower': a['var_index'][n]}, F(1)]
                        for n in h['removed_budget_only_variables']])
    mapping = [expression(0, {j: 1}) for i, j in projection]
    checks = finish_checks(
        f, b, mapping, lambda i, t: [[{t: projection[i][1]}, F(1)]],
        lambda i: packing[i],
        [[y_eq[i], -c] for i, c in a['objective'][1].items()])
    f.finish(mapping, checks)

    reverse_mapping = [expression(F(e['constant']), {i: F(c) for i, c in e['terms']})
                       for e in w['reverse_map']]
    y_lookup = {y['source_variable']: y for y in w['eliminated_y']}

    def domain(i, kind):
        e = reverse_mapping[i]
        if not e[1]:
            return []
        if i in y_lookup and kind == 'VarUpper':
            y = y_lookup[i]
            row = b['rows'][y['target_superset_row']]
            return ([[{'RowUpper': y['target_superset_row']}, F(1)]] +
                    [[{'VarLower': j}, F(1)] for j in row['terms'] if j not in e[1]])
        return [[{kind: j}, c] for j, c in e[1].items()]

    checks = finish_checks(
        reverse_builder, a, reverse_mapping, domain,
        lambda i: ([] if a['rows'][i]['sense'] == 'E'
                   else [[{'RowUpper': budget}, F(1)]]), [])
    reverse_builder.finish(reverse_mapping, checks)
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'directions': 2, 'saturation_aliases': len(aliases),
                   'saturation_branches': sum(len(g['edges']) for g in w['saturation']
                                              if len(g['edges']) > 1),
                   'eliminated_binaries': len(y_eq)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test18-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test18'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test18', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test18', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
