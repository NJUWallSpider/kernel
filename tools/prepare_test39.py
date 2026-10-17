#!/usr/bin/env python3
"""Native test39 balance cliques and complete dependent-row recovery."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact, sha
from prepare_test57 import substitute
from prepare_native import compile_case, make_proof


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']),
            len(b['rows'])) == (242736, 322248, 242736, 313956)
    assert a['vars'] == b['vars'] and a['objective'] == b['objective']
    n = len(a['vars'])
    mapping = [expression(0, {i: 1}) for i in range(n)]
    removed = {d['remove']: d for d in h['dependent_equalities']}
    duplicates = {d['remove']: d['retain'] for d in h['duplicate_rows']}
    packing = {d['row']: d for d in h['packing_replacements']}
    assert set(a['row_index']) - set(b['row_index']) == set(removed) | set(duplicates)
    proof, f, r = make_proof(a, b)
    structure = {}
    forward = {}
    rounds = 0
    for rn, d in packing.items():
        ref = row_ref(a, rn)
        eq = row_ref(a, d['balance_row'])
        old = f.refexpr(ref)
        balance = f.refexpr(eq)
        target = row_fact(b['rows'][b['row_index'][rn]], 'RowUpper')
        kept = {a['var_index'][v] for v in d['kept_variables']}
        other = {a['var_index'][v] for v in d['removed_variables']}
        extra = [a['var_index'][v] for v in d['extra_variable']]
        assert not kept & other and len(extra) <= 1
        assert old == expression(-2, {i: 1 for i in kept | other})
        assert target == expression(-1, {i: 1 for i in kept})
        sign = balance[1][next(iter(kept))]
        assert sign in (-1, 1)
        assert balance == expression(0, {**{i: sign for i in kept},
                                        **{i: -sign for i in other},
                                        **{i: -sign for i in extra}})
        for i in kept | other | set(extra):
            assert a['vars'][i]['integer']
            assert a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] == 1
        terms = [[ref, F(1, 2)], [eq, sign / F(2)]]
        if extra:
            terms.append([{'VarUpper': extra[0]}, F(1, 2)])
            le = f.lin('Le', terms, expression(F(-3, 2), target[1]))
            integer = f.lin('Int', [[{'VarInt': i}, 1] for i in sorted(kept)],
                            expression(0, target[1]))
            forward[rn] = f.round(le, integer)
            rounds += 1
        else:
            forward[rn] = f.lin('Le', terms, target)
        assert f.refexpr(forward[rn]) == target
        structure[rn] = (sign, extra)
    counts = {'source_variables': n, 'target_variables': n,
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'balance_clique_replacements': 1152, 'integer_rounded_cliques': rounds,
              'restored_dependent_equalities': 6564, 'restored_duplicates': 1728,
              'directions': 2, 'obligations_by_direction': {}}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = r if back else f
        checks = []
        recovered = {}
        if back:
            for rn, d in removed.items():
                assert len(d['members']) == 12 and rn in d['members']
                recovered[rn] = builder.lin(
                    'Eq', [[row_ref(b, member), -1] for member in d['members']
                           if member != rn],
                    row_fact(a['rows'][a['row_index'][rn]], 'RowEq'))
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
            if rn in packing:
                if back:
                    sign, extra = structure[rn]
                    eqname = packing[rn]['balance_row']
                    eq = recovered[eqname] if eqname in recovered else row_ref(b, eqname)
                    check = builder.lin(
                        'Le', [[row_ref(b, rn), 2], [eq, -sign]] +
                        [[{'VarLower': i}, 1] for i in extra],
                        row_fact(row, 'RowUpper'))
                else:
                    check = forward[rn]
            elif back and rn in recovered:
                check = recovered[rn]
            elif back and rn in duplicates:
                check = row_ref(b, duplicates[rn])
                assert builder.refexpr(check) == row_fact(row, 'RowUpper')
            else:
                assert row == inp['rows'][inp['row_index'][rn]]
                check = row_ref(inp, rn)
            checks.append(check)
        residual = plus(substitute(out['objective'], mapping), inp['objective'], -1)
        assert residual == expression()
        checks.append('Exact')
        builder.finish(mapping, checks)
        counts['obligations_by_direction']['forward' if not back else 'reverse'] = len(checks)
    assert rounds == 192
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test39-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test39'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test39', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test39', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
