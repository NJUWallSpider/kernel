#!/usr/bin/env python3
"""Native test44 capacity cuts as ordinary finite local Cases, never a theorem.

Only the two MI-OPT directions are emitted; the legacy LP strictness point and
the projection/inverse bookkeeping are outside that contract.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact, substitute, sha
from prepare_test88 import fix_binary
from prepare_native import compile_case, make_proof


def le_cases(b, wanted, var, left, right):
    return b.cases('Le', wanted, expression(0, {var: 1}),
                   integer={'VarInt': var}, left=left, right=right)


def cut(b, wanted, h):
    m = b.model
    unit = F(7560)
    groups = []
    terms = []
    for name in h['edges']:
        r = m['rows'][m['row_index'][name]]
        assert r['sense'] == 'L'
        ids = [i for i, c in r['terms'].items() if c < 0]
        assert len(ids) == 3 and sorted(-r['terms'][i] / unit for i in ids) == [1, 4, 16]
        assert all(m['vars'][i]['integer'] and m['vars'][i]['lower'] == 0 and
                   m['vars'][i]['upper'] == 1 for i in ids)
        choice = expression(-1, {i: 1 for i in ids})
        choices = []
        for other in m['rows']:
            if other['sense'] == 'G' and row_fact(other, 'RowLower') == choice:
                choices.append(row_ref(m, other['name']))
        assert len(choices) == 1
        groups.append((ids, choices[0]))
        terms.append([row_ref(m, name), 1 / unit])
    balances = [r for r in m['rows']
                if r['name'].startswith('FC(') and r['name'].endswith('IntDS__' + h['node'] + ')')]
    assert len(balances) == 36 and all(r['sense'] == 'E' for r in balances)
    terms += [[row_ref(m, r['name']), -F((r['rhs'] > 0) - (r['rhs'] < 0)) / unit]
              for r in balances if r['rhs']]
    e = expression()
    for ref, c in terms:
        e = plus(e, b.refexpr(ref), c)
    for i, c in list(e[1].items()):
        if not m['vars'][i]['integer']:
            assert c >= 0 and m['vars'][i]['lower'] == 0
            terms.append([{'VarLower': i}, c])
            e = plus(e, b.refexpr({'VarLower': i}), c)
    assert e[0] == F(h['demand']) / unit and set(e[1]) == set(i for ids, _ in groups for i in ids)
    capacity = b.lin('Le', terms, e)

    def recurse(child, group, assigned):
        residual = wanted[0] + sum(c * assigned[i][0] for i, c in wanted[1].items() if i in assigned)
        # Every unassigned cut coefficient is nonpositive: its variable lower
        # bound suffices as soon as the already selected options meet the cut.
        if residual <= 0:
            proof = [[assigned[i][1], c] if i in assigned else [{'VarLower': i}, -c]
                     for i, c in wanted[1].items()]
            assert all(c <= 0 for i, c in wanted[1].items() if i not in assigned)
            return {'Witness': child.lin('Le', proof, wanted, constant=residual)}
        if group == len(groups):
            residual_cap = e[0] + sum(c * assigned[i][0] for i, c in e[1].items())
            assert residual_cap > 0, ('actual local design would refute committed cut', h['row'], assigned)
            contradiction = child.lin('Le', [[capacity, F(1)]] +
                                      [[assigned[i][1], -c] for i, c in e[1].items()],
                                      expression(residual_cap))
            return {'Absurd': contradiction}
        ids, choice = groups[group]

        def select(bb, index, state):
            if index == len(ids):
                return recurse(bb, group + 1, state)
            var = ids[index]

            def branch(cc, assumption, value):
                eq = fix_binary(cc, var, value, assumption)
                nextstate = {**state, var: (F(value), eq)}
                if value == 0:
                    return select(cc, index + 1, nextstate)
                # The actual packing row forces every other option to zero.
                for other in ids:
                    if other == var or other in nextstate:
                        continue
                    upper = cc.lin('Le', [[choice, F(1)], [eq, F(-1)]] +
                                   [[{'VarLower': j}, F(1)] for j in ids if j not in [var, other]],
                                   expression(0, {other: 1}))
                    nextstate[other] = (F(0), cc.eqpair(upper, {'VarLower': other}))
                return recurse(cc, group + 1, nextstate)

            return {'Witness': le_cases(bb, wanted, var,
                                        lambda cc, r: branch(cc, r, 0),
                                        lambda cc, r: branch(cc, r, 1))}
        return select(child, 0, assigned)
    return recurse(b, 0, {})['Witness']


def block(inp, out, builder, back, h):
    mapping = [expression(0, {inp['var_index'][v['name']]: 1}) for v in out['vars']]
    checks = []
    for v in out['vars']:
        i = inp['var_index'][v['name']]
        assert v == inp['vars'][i]
        if v['lower'] is not None:
            checks.append({'VarLower': i})
        if v['upper'] is not None:
            checks.append({'VarUpper': i})
        if v['integer']:
            checks.append('Exact')
    removed = {r['removed_row']: r for r in h['removed_rows']}
    added = {r['row']: r for r in h['added_rows']}
    for row in out['rows']:
        name = row['name']
        typ = {'L': 'RowUpper', 'G': 'RowLower', 'E': 'RowEq'}[row['sense']]
        wanted = substitute(row_fact(row, typ), mapping)
        if name in inp['row_index']:
            ref = row_ref(inp, name)
            assert builder.refexpr(ref) == wanted
        elif back:
            assert name in removed
            ref = builder.lin('Eq', [[row_ref(inp, n), F(-1)]
                                     for n in removed[name]['other_rows']], wanted)
        else:
            assert name in added
            ref = cut(builder, wanted, added[name])
        checks.append(ref)
    assert substitute(out['objective'], mapping) == inp['objective']
    checks.append('Exact')
    builder.finish(mapping, checks)
    return len(checks)


def prepare(a, b, h):
    proof, f, r = make_proof(a, b)
    obligations = []
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        obligations.append(block(inp, out, r if back else f, back, h))
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'removed_rows': len(h['removed_rows']), 'added_rows': len(h['added_rows']),
                   'directions': 2, 'obligations_by_claim': obligations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test44-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test44'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test44', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {'path': str(Path(__file__).resolve()),
                                                       'sha256': sha(Path(__file__))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test44', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
