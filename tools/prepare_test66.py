#!/usr/bin/env python3
"""Native test66 conditional five-cycle cuts with two MI-OPT directions."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_test57 import substitute
from prepare_native import compile_case, make_proof


def identity_certificate(a, b, f, r, derived):
    assert a['vars'] == b['vars'] and a['objective'] == b['objective']
    n = len(a['vars'])
    mapping = [expression(0, {i: 1}) for i in range(n)]
    columns = {'source_variables': n, 'target_variables': n,
               'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
               'directions': 2, 'obligations_by_direction': {}}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = r if back else f
        checks = []
        for i, v in enumerate(out['vars']):
            if v['lower'] is not None:
                checks.append({'VarLower': i})
            if v['upper'] is not None:
                checks.append({'VarUpper': i})
            if v['integer']:
                assert inp['vars'][i]['integer']
                checks.append({'VarInt': i})
        for row in out['rows']:
            rn = row['name']
            if not back and rn in derived:
                ref = derived[rn]
            else:
                assert row == inp['rows'][inp['row_index'][rn]]
                ref = row_ref(inp, rn)
            assert builder.refexpr(ref) == row_fact(row, next(iter(row_ref(out, rn))))
            checks.append(ref)
        residual = substitute(out['objective'], mapping)
        assert residual == inp['objective']
        checks.append('Exact')
        builder.finish(mapping, checks)
        columns['obligations_by_direction']['forward' if not back else 'reverse'] = len(checks)
    return columns


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']),
            len(b['rows'])) == (73728, 67583, 73728, 88067)
    assert a['vars'] == b['vars'] and a['objective'] == b['objective']
    cuts = {d['row']: d for d in h['cuts']}
    assert len(cuts) == 20484
    assert set(b['row_index']) - set(a['row_index']) == set(cuts)
    proof, f, r = make_proof(a, b)
    derived = {}
    for rn, d in cuts.items():
        y = a['var_index'][d['activation']]
        v = a['vars'][y]
        assert v['integer'] and v['lower'] == 0 and v['upper'] == 1
        target = row_fact(b['rows'][b['row_index'][rn]], 'RowUpper')
        support = set(target[1]) - {y}
        assert target == expression(0, {**dict.fromkeys(support, F(1)), y: F(-2)})
        assert len(support) == 5
        assert {a['var_index'][name]: F(c) for name, c in d['coefficients'].items()} == target[1]
        assert len(d['source_vertex_rows']) == 5
        assert len(set(d['source_vertex_rows'])) == 5
        totals = {}
        terms = []
        for name in d['source_vertex_rows']:
            ref = row_ref(a, name)
            e = f.refexpr(ref)
            assert 'RowUpper' in ref and e[0] == 0 and e[1][y] == -1
            assert all(c == 1 for i, c in e[1].items() if i != y)
            terms.append([ref, F(1, 2)])
            for i, c in e[1].items():
                totals[i] = totals.get(i, F(0)) + c
        assert totals[y] == -5 and all(totals[i] == 2 for i in support)
        spokes = set(totals) - support - {y}
        assert all(totals[i] == 1 and a['vars'][i]['lower'] == 0 for i in spokes)
        terms += [[{'VarLower': i}, F(1, 2)] for i in sorted(spokes)]
        base = f.lin('Le', terms, expression(0, {**dict.fromkeys(support, F(1)),
                                                 y: F(-5, 2)}))
        integer = f.lin('Int', [[{'VarInt': i}, F(1)] for i in sorted(support)],
                        expression(0, dict.fromkeys(support, F(1))))

        def left(child, zero, base=base, target=target):
            return child.lin('Le', [[base, F(1)], [zero, F(1, 2)]], target)

        def right(child, one, base=base, target=target, y=y, integer=integer):
            bound = child.lin('Le', [[base, F(1)], [{'VarUpper': y}, F(5, 2)]],
                              expression(F(-5, 2), dict.fromkeys(support, F(1))))
            cut = child.round(bound, integer)
            return child.lin('Le', [[cut, F(1)], [one, F(2)]], target)

        derived[rn] = f.cases('Le', target, expression(0, {y: 1}),
                              integer={'VarInt': y}, left=left, right=right)
    columns = identity_certificate(a, b, f, r, derived)
    columns.update(five_cycles=5121, cuts=len(cuts), integer_rounds=len(cuts),
                   binary_cases=len(cuts))
    return proof, columns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test66-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test66'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/model_odd5.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test66', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test66', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
