#!/usr/bin/env python3
"""Native test19 cycle cuts with exact auxiliary substitution.

Only the two MI-OPT directions are emitted: the legacy LP strictness point, the
bijection projection and the full inverse contracts are outside that contract.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact, substitute, sha
from prepare_test84 import rounded
from prepare_native import compile_case, make_proof


def cases_le(b, desired, var, left, right):
    return b.cases('Le', desired, expression(0, {var: 1}),
                   integer={'VarInt': var}, left=left, right=right)


def prepare(a, b, h):
    assert len(a['vars']) == 1462 and len(b['vars']) == 1459 and len(a['rows']) == 1655 and len(b['rows']) == 1668
    removed = set(h['removed_columns'])
    assert set(a['var_index']) - set(b['var_index']) == removed
    assert set(a['row_index']) - set(b['row_index']) == set(h['removed_rows'])
    forward = [expression(0, {a['var_index'][v['name']]: 1}) for v in b['vars']]
    reverse = []
    definition = {}
    for v in a['vars']:
        name = v['name']
        i = a['var_index'][name]
        if name not in removed:
            assert v == b['vars'][b['var_index'][name]]
            reverse.append(expression(0, {b['var_index'][name]: 1}))
            continue
        assert not v['integer'] and v['lower'] is None and v['upper'] is None
        matches = [ri for ri in h['removed_rows'] if a['rows'][a['row_index'][ri]]['terms'].get(i) == 1]
        assert len(matches) == 1
        ri = a['row_index'][matches[0]]
        r = a['rows'][ri]
        assert r['sense'] == 'E' and r['rhs'] == 0
        definition[i] = ri
        reverse.append(expression(0, {b['var_index'][a['vars'][j]['name']]: -c
                                      for j, c in r['terms'].items() if j != i}))
    assert substitute(a['objective'], reverse) == b['objective']
    changes = {x['row']: x for x in h['coefficient_changes']}
    assert len(changes) == 210
    newrows = {c['new_row'] for c in h['cycle_certificates']}
    assert set(b['row_index']) - set(a['row_index']) == newrows
    for row in b['rows']:
        if row['name'] in newrows:
            continue
        original = a['rows'][a['row_index'][row['name']]]
        expected = substitute(row_fact(original, next(iter(row_ref(a, row['name'])))), reverse)
        if row['name'] in changes:
            ch = changes[row['name']]
            assert original['terms'][a['var_index'][ch['column']]] == F(ch['old'])
            expected = plus(expected, expression(0, {b['var_index'][ch['column']]: F(ch['new']) - F(ch['old'])}))
        assert expected == row_fact(row, next(iter(row_ref(b, row['name']))))
    proof, f, r = make_proof(a, b)
    cycle_eq = {}
    prod_cycle = {}
    upper = {}
    activation = {}
    changed = {}
    cuts = {}
    for c in h['cycle_certificates']:
        prod = [a['var_index'][n] for n in c['production']]
        D = F(c['total_demand'])
        eq = f.lin('Eq', [[row_ref(a, n), F(-1)] for n in c['rows']],
                   expression(-D, {j: 1 for j in prod}))
        cycle_eq[c['index']] = eq
        for j in prod:
            assert j not in prod_cycle
            prod_cycle[j] = c
    for name, hint in h['production_bound_certificates'].items():
        j = a['var_index'][name]
        c = prod_cycle[j]
        D = F(c['total_demand'])
        U = min(F(4500), D)
        if D < 4500:
            terms = [[cycle_eq[c['index']], F(1)]] + \
                    [[{'VarLower': a['var_index'][n]}, F(1)] for n in c['production'] if n != name]
        else:
            terms = [[row_ref(a, hint['row']), F(1)],
                     [{'VarLower': a['var_index'][hint['inventory']]}, F(1)]]
        upper[j] = f.lin('Le', terms, expression(-U, {j: 1}))
        # Find the actual unique activation row by its complete two-column support.
        y = a['var_index'][c['activation'][c['production'].index(name)]]
        rows = [r['name'] for r in a['rows']
                if r['sense'] == 'L' and r['rhs'] == 0 and r['terms'] == {j: F(1), y: F(-4500)}]
        assert len(rows) == 1
        activation[j] = rows[0]
    for name, ch in changes.items():
        z = a['var_index'][ch['column']]
        B = -F(ch['new'])
        old = -F(ch['old'])
        original = row_ref(a, name)
        prod = [a['var_index'][ch['production']]] if isinstance(ch['production'], str) \
            else [a['var_index'][n] for n in ch['production']]
        desired = expression(0, {**{j: F(1) for j in prod}, z: -B})
        assert f.refexpr(original) == expression(0, {**{j: F(1) for j in prod}, z: -old})
        assert sum(-f.refexpr(upper[j])[0] for j in prod) == B
        changed[name] = cases_le(f, desired, z,
            lambda child, s, original=original, old=old, B=B:
                child.lin('Le', [[original, F(1)], [s, old - B]], desired),
            lambda child, s, prod=prod, B=B:
                child.lin('Le', [[upper[j], F(1)] for j in prod] + [[s, B]], desired))
    for c in h['cycle_certificates']:
        M = F(c['production_upper'])
        prod = [a['var_index'][n] for n in c['production']]
        ys = [a['var_index'][n] for n in c['activation']]
        terms = [[changed.get(activation[j], row_ref(a, activation[j])), 1 / M] for j in prod] + \
                [[cycle_eq[c['index']], -1 / M]]
        le = f.lin('Le', terms, expression(F(c['total_demand']) / M, {y: -1 for y in ys}))
        integer = f.lin('Int', [[{'VarInt': y}, F(-1)] for y in ys], expression(0, {y: -1 for y in ys}))
        cuts[c['new_row']] = rounded(f, le, integer)
        assert f.refexpr(cuts[c['new_row']]) == \
            substitute(row_fact(b['rows'][b['row_index'][c['new_row']]], 'RowLower'), forward)

    def finish(builder, out, mapping, rowterms, objterms):
        checks = []

        def prove(kind, e, terms):
            if not e[1] and ((kind == 'Eq' and e[0] == 0) or (kind == 'Le' and e[0] <= 0) or
                             (kind == 'Int' and e[0].denominator == 1)):
                checks.append('Exact')
                return
            if len(terms) == 1 and terms[0][1] == 1 and builder.kind(terms[0][0]) == kind \
                    and builder.refexpr(terms[0][0]) == e:
                checks.append(terms[0][0])
                return
            checks.append(builder.lin(kind, terms, e))

        for i, v in enumerate(out['vars']):
            for kind, enabled in [('VarLower', v['lower'] is not None),
                                  ('VarUpper', v['upper'] is not None),
                                  ('VarInt', v['integer'])]:
                if not enabled:
                    continue
                assert mapping[i][0] == 0 and len(mapping[i][1]) == 1
                j = next(iter(mapping[i][1]))
                assert mapping[i][1][j] == 1
                e = plus(expression(v['lower']), mapping[i], -1) if kind == 'VarLower' \
                    else plus(mapping[i], expression(-v['upper'])) if kind == 'VarUpper' \
                    else mapping[i]
                prove('Int' if kind == 'VarInt' else 'Le', e, [[{kind: j}, F(1)]])
        for row in out['rows']:
            typ = next(iter(row_ref(out, row['name'])))
            prove('Eq' if typ == 'RowEq' else 'Le',
                  substitute(row_fact(row, typ), mapping), rowterms(row['name']))
        prove('Eq', plus(substitute(out['objective'], mapping), builder.model['objective'], -1),
              objterms)
        builder.finish(mapping, checks)
        return len(checks)

    obf = finish(f, b, forward,
                 lambda n: [[changed.get(n, cuts.get(n, row_ref(a, n) if n in a['row_index'] else None)), F(1)]],
                 [[{'RowEq': ri}, F(-1)] for ri in definition.values()])

    def rows(n):
        if n in h['removed_rows']:
            return []
        result = [[row_ref(b, n), F(1)]]
        if n in changes:
            ch = changes[n]
            result.append([{'VarLower': b['var_index'][ch['column']]},
                           F(ch['new']) - F(ch['old'])])
        return result

    obr = finish(r, a, reverse, rows, [])
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'directions': 2, 'cases': len(changes), 'rounds': len(cuts),
                   'cycle_certificates': len(h['cycle_certificates']),
                   'obligations_by_claim': [obf, obr]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test19-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test19'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test19', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {'path': str(Path(__file__).resolve()),
                                                       'sha256': sha(Path(__file__))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test19', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
