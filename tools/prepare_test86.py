#!/usr/bin/env python3
"""Native test86 incoming-flow cover cuts with two MI-OPT directions."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_native import compile_case, make_proof
from prepare_test66 import identity_certificate


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']),
            len(b['rows'])) == (990, 550, 990, 800)
    assert a['vars'] == b['vars'] and a['objective'] == b['objective']
    added = {d['name']: d for d in h['added_rows']}
    assert len(added) == 250
    assert set(b['row_index']) - set(a['row_index']) == set(added)
    proof, f, r = make_proof(a, b)
    derived = {}
    for rn, record in added.items():
        d = record['certificate']
        p = a['var_index'][d['production']]
        y = a['var_index'][d['binary']]
        demand = F(d['demand'])
        incoming = [a['var_index'][name] for name in d['incoming']]
        outgoing = [a['var_index'][name] for name in d['outgoing']]
        assert demand > 0
        assert len(set([p, y] + incoming + outgoing)) == 2 + len(incoming) + len(outgoing)
        assert a['vars'][y]['integer'] and a['vars'][y]['lower'] == 0 and a['vars'][y]['upper'] == 1
        assert all(a['vars'][i]['lower'] == 0 for i in [p] + incoming + outgoing)
        balance = row_ref(a, d['balance'])
        link = row_ref(a, d['link'])
        linkexpr = f.refexpr(link)
        bigm = -linkexpr[1][y]
        assert bigm > demand
        assert linkexpr == expression(0, {p: 1, y: -bigm}) and 'RowUpper' in link
        assert 'RowEq' in balance
        assert f.refexpr(balance) == expression(-demand, {p: 1,
                                                         **dict.fromkeys(incoming, F(1)),
                                                         **dict.fromkeys(outgoing, F(-1))})
        wanted = expression(demand, {**dict.fromkeys(incoming, F(-1)), y: -demand})
        assert wanted == row_fact(b['rows'][b['row_index'][rn]], 'RowLower')
        assert record['sense'] == 'G' and F(record['rhs']) == demand
        assert {a['var_index'][name]: F(c)
                for name, c in record['coefficients'].items()} == {
                    **dict.fromkeys(incoming, F(1)), y: demand}

        def left(child, zero, balance=balance, link=link, outgoing=outgoing,
                 bigm=bigm, demand=demand, wanted=wanted):
            return child.lin('Le', [[balance, F(-1)], [link, F(1)]] +
                             [[{'VarLower': i}, F(1)] for i in outgoing] +
                             [[zero, bigm - demand]], wanted)

        def right(child, one, incoming=incoming, demand=demand, wanted=wanted):
            return child.lin('Le', [[{'VarLower': i}, F(1)] for i in incoming] +
                             [[one, demand]], wanted)

        derived[rn] = f.cases('Le', wanted, expression(0, {y: 1}),
                              integer={'VarInt': y}, left=left, right=right)
    columns = identity_certificate(a, b, f, r, derived)
    columns.update(incoming_flow_cuts=len(added), binary_cases=len(added))
    return proof, columns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test86-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test86'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/model_strengthened.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test86', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test86', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
