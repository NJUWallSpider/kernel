#!/usr/bin/env python3
"""Native test84 parity fixation using generic Lin/Int/Round/EqPair.

The side-audit supplies only selected original row names. Every parity identity,
fixed value, remaining variable and actual model is checked exactly. Only the two
MI-OPT directions are emitted; the legacy inverse contract is native bookkeeping.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, row_fact, substitute, sha
from prepare_native import compile_case, make_proof


def rounded(builder, le, integer):
    """Native Round step; keeps the legacy helper name for the shared preparers."""
    le_ref = builder.refexpr(le)
    int_ref = builder.refexpr(integer)
    assert builder.kind(le) == 'Le' and builder.kind(integer) == 'Int' and le_ref[1] == int_ref[1]
    difference = le_ref[0] - int_ref[0]
    ceiling = -((-difference.numerator) // difference.denominator)
    expected = expression(int_ref[0] + ceiling, int_ref[1])
    result = builder.round(le, integer)
    assert builder.refexpr(result) == expected
    return result


def prepare(a, b, audit):
    assert len(a['vars']) == 200 and len(a['rows']) == 100 and len(b['vars']) == len(b['rows']) == 1
    proof, f, r = make_proof(a, b)
    fixed = {}
    values = {}
    for hint in audit['modular_certificates']:
        j = a['var_index'][hint['variable']]
        assert a['vars'][j]['integer'] and a['vars'][j]['lower'] == 0 and a['vars'][j]['upper'] == 1
        combined = expression()
        row_terms = []
        for name in hint['rows']:
            ref = row_ref(a, name)
            assert 'RowEq' in ref
            combined = plus(combined, f.refexpr(ref))
            row_terms.append([ref, F(1, 2)])
        assert combined[0].denominator == 1 and all(c.denominator == 1 for c in combined[1].values())
        rhs = -combined[0]
        value = int(rhs) % 2
        assert combined[1][j].numerator % 2 == 1 and all(i == j or c.numerator % 2 == 0 for i, c in combined[1].items())
        assert rhs == F(hint['combined_rhs']) and value == hint['forced_value']
        terms = row_terms
        for i, c in combined[1].items():
            multiplier = (F(1) - c) / 2 if i == j else -c / 2
            assert multiplier.denominator == 1
            if multiplier:
                terms.append([{'VarInt': i}, multiplier])
        integer = f.lin('Int', terms, expression(-F(value, 2), {j: F(1, 2)}), constant=(rhs - value) / 2)
        if value == 0:
            le = f.lin('Le', [[{'VarUpper': j}, F(1, 2)]])
            rounded_le = rounded(f, le, integer)
            upper = f.lin('Le', [[rounded_le, F(2)]], expression(0, {j: 1}))
            fixed[j] = f.eqpair(upper, {'VarLower': j})
        else:
            negative_int = f.lin('Int', [[integer, F(-1)]], expression(F(1, 2), {j: F(-1, 2)}))
            le = f.lin('Le', [[{'VarLower': j}, F(1, 2)]])
            rounded_le = rounded(f, le, negative_int)
            lower = f.lin('Le', [[rounded_le, F(2)]], expression(1, {j: -1}))
            fixed[j] = f.eqpair({'VarUpper': j}, lower)
        values[j] = F(value)
    assert len(fixed) == 100
    # Every remaining source coordinate is solved from an actual equality with
    # one unproved coordinate; no numerical solve or parity theorem is trusted.
    for row in a['rows']:
        unknown = [i for i in row['terms'] if i not in fixed]
        assert len(unknown) == 1 and row['sense'] == 'E'
        j = unknown[0]
        pivot = row['terms'][j]
        value = (row['rhs'] - sum(c * values[i] for i, c in row['terms'].items() if i != j)) / pivot
        terms = [[row_ref(a, row['name']), 1 / pivot]] + \
                [[fixed[i], -c / pivot] for i, c in row['terms'].items() if i != j]
        fixed[j] = f.lin('Eq', terms, expression(-value, {j: 1}))
        values[j] = value
    assert len(fixed) == len(a['vars'])
    assert {a['vars'][i]['name']: str(v) for i, v in values.items()} == \
        {n: str(F(v)) for n, v in audit['original_unique_assignment'].items()}
    optimum = a['objective'][0] + sum(c * values[i] for i, c in a['objective'][1].items())
    assert optimum == 37
    forward = [expression(optimum)]
    reverse = [expression(values[i]) for i in range(len(a['vars']))]

    def checks(builder, output, mapping, fixes):
        inp = builder.model
        result = []

        def check(kind, e):
            if not e[1] and ((kind == 'Eq' and e[0] == 0) or (kind == 'Le' and e[0] <= 0) or
                             (kind == 'Int' and e[0].denominator == 1)):
                result.append('Exact')
                return
            terms = [[fixes[i], c] for i, c in e[1].items()]
            result.append(builder.lin(kind, terms, e))

        for i, v in enumerate(output['vars']):
            if v['lower'] is not None:
                check('Le', plus(expression(v['lower']), mapping[i], -1))
            if v['upper'] is not None:
                check('Le', plus(mapping[i], expression(-v['upper'])))
            if v['integer']:
                check('Int', mapping[i])
        for row in output['rows']:
            typ = next(iter(row_ref(output, row['name'])))
            check('Eq' if row['sense'] == 'E' else 'Le', substitute(row_fact(row, typ), mapping))
        check('Eq', plus(substitute(output['objective'], mapping), inp['objective'], -1))
        return result

    fchecks = checks(f, b, forward, fixed)
    targetfix = row_ref(b, b['rows'][0]['name'])
    assert r.refexpr(targetfix) == expression(-37, {0: 1})
    rchecks = checks(r, a, reverse, {0: targetfix})
    f.finish(forward, fchecks)
    r.finish(reverse, rchecks)
    return proof, {'source_variables': 200, 'target_variables': 1,
                   'source_rows': 100, 'target_rows': 1, 'directions': 2,
                   'parity_fixings': 100, 'equality_fixings': 100,
                   'obligations_by_claim': [len(fchecks), len(rchecks)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test84-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test84'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test84', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {'path': str(Path(__file__).resolve()),
                                                       'sha256': sha(Path(__file__))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test84', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
