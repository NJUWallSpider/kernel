#!/usr/bin/env python3
"""Native test26 identity/integrality/gate proof with scalar rules only."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_native import compile_case, make_proof


def integrality(m, h, p):
    known = {i: {'VarInt': i} for i, v in enumerate(m['vars']) if v['integer']}
    for d in h['integrality_proof']:
        i = m['var_index'][d['variable']]
        r = row_ref(m, d['row'])
        e = p.refexpr(r)
        pivot = e[1][i]
        assert i not in known and pivot in [F(-1), F(1)] and pivot == d['pivot_coefficient']
        assert set(d['dependencies']) == {m['vars'][j]['name'] for j in e[1] if j != i}
        terms = [[r, 1 / pivot]] + [[known[j], -c / pivot] for j, c in e[1].items() if j != i]
        known[i] = p.lin('Int', terms, expression(0, {i: 1}), -e[0] / pivot)
    assert len(known) == len(m['vars']) and len(h['integrality_proof']) == 4502
    return known


def prepare(a, b, h):
    assert set(a['var_index']) == set(b['var_index']) and len(a['vars']) == 11717
    assert set(a['row_index']) == set(b['row_index']) and len(a['rows']) == 10460
    gates = {d['row']: d for d in h['gate_rounding']}
    assert len(gates) == 38
    proof, forward_builder, reverse_builder = make_proof(a, b)
    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'relaxed_integrality': len(h['integrality_proof']),
              'gate_rounding': len(gates), 'directions': 2,
              'obligations_by_direction': {}}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = reverse_builder if back else forward_builder
        mapping = [expression(0, {inp['var_index'][v['name']]: 1}) for v in out['vars']]
        known = integrality(inp, h, builder) if back else {}
        checks = []
        for v, e in zip(out['vars'], mapping):
            j = inp['var_index'][v['name']]
            assert v['lower'] == inp['vars'][j]['lower']
            assert v['upper'] == inp['vars'][j]['upper']
            if v['lower'] is not None:
                checks.append({'VarLower': j})
            if v['upper'] is not None:
                checks.append({'VarUpper': j})
            if v['integer']:
                assert j in known or inp['vars'][j]['integer']
                checks.append(known[j] if j in known else {'VarInt': j})
        for row in out['rows']:
            name = row['name']
            r = row_ref(inp, name)
            wanted = substitute(row_fact(row, next(iter(row_ref(out, name)))), mapping)
            if name not in gates:
                assert builder.refexpr(r) == wanted
                checks.append(r)
                continue
            d = gates[name]
            y = inp['var_index'][d['gate']]
            zs = [inp['var_index'][n] for n in d['sum_variables']]
            aa = F(d['old_gate_coeff'])
            k = F(d['unit'])
            q = aa // k
            assert aa > 0 and k > 0 and q == d['max_integer_sum']
            assert inp['vars'][y]['lower'] == 0 and inp['vars'][y]['upper'] == 1
            total = expression(0, {z: 1 for z in zs})
            cut = plus(total, expression(0, {y: -q}))
            old = plus(mul(total, k), expression(0, {y: -aa}))
            if back:
                assert builder.refexpr(r) == cut and wanted == old
                assert aa - k * q >= 0
                terms = [[r, k]] + ([[{'VarLower': y}, aa - k * q]]
                                    if aa - k * q else [])
                checks.append(builder.lin('Le', terms, wanted))
            else:
                assert builder.refexpr(r) == old and wanted == cut
                assert aa / k - q > 0

                def left(child, assumption, r=r, wanted=wanted, weight=aa / k - q):
                    return {'Witness': child.lin('Le', [[r, 1 / k], [assumption, weight]],
                                                 wanted)}

                def right(child, assumption, r=r, y=y, zs=zs, total=total,
                          wanted=wanted, aa=aa, k=k, q=q):
                    eq = child.eqpair({'VarUpper': y}, assumption)
                    le = child.lin('Le', [[r, 1 / k], [eq, aa / k]],
                                   plus(total, expression(-aa / k)))
                    ints = child.lin('Int', [[{'VarInt': z}, F(1)] for z in zs], total)
                    rounded = child.round(le, ints)
                    return {'Witness': child.lin('Le', [[rounded, 1], [eq, -q]], wanted)}

                checks.append(builder.cases('Le', wanted, expression(0, {y: 1}),
                                            integer={'VarInt': y}, left=left, right=right))
        assert substitute(out['objective'], mapping) == inp['objective']
        checks.append('Exact')
        builder.finish(mapping, checks)
        counts['obligations_by_direction']['forward' if not back else 'reverse'] = len(checks)
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test26-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test26'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/model_reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test26', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test26', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
