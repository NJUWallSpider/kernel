#!/usr/bin/env python3
"""Native test22 pivot elimination, ranged-row projection and cost aggregation.

The target MPS ``RANGES`` section is collapsed into explicit row lower/upper
bounds before the native model is built, so both target-row endpoints are
checked by the ordinary obligation walker.  The aggregate pair is split
equally; no all-point bijection, point claim, or LP-only duplicate is emitted.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_native import compile_case, is_exact, legacy_expr, make_proof


def parse_ranged_target(path):
    """Read the fixed target MPS and collapse its RANGES section explicitly."""
    lines = []
    ranges = {}
    inside = False
    vectors = set()
    for line in path.read_text().splitlines():
        if line and not line[0].isspace() and not line.startswith('*'):
            inside = line.split()[0] == 'RANGES'
            if inside:
                continue
        if inside:
            if not line.strip() or line.startswith('*'):
                continue
            tokens = line.split()
            assert len(tokens) in (3, 5)
            vectors.add(tokens[0])
            for name, value in zip(tokens[1::2], tokens[2::2]):
                assert name not in ranges
                ranges[name] = F(value)
        else:
            lines.append(line)

    class MemoryMPS:
        def read_text(self):
            return '\n'.join(lines) + '\n'

        def __str__(self):
            return str(path)

    model = parse_mps(MemoryMPS())
    assert len(vectors) == 1 and len(ranges) == 171
    for row in model['rows']:
        assert row['sense'] == 'G' and row['name'] in ranges and ranges[row['name']] > 0
        row['lower'] = row['rhs']
        row['upper'] = row['rhs'] + ranges[row['name']]
        assert row['lower'] < row['upper']
        del row['sense']
        del row['rhs']
    return model


def exact(kind, e):
    return is_exact(kind, e)


def fact(builder, kind, e, terms=(), constant=0, terminal=False):
    if terminal and exact(kind, e):
        return 'Exact'
    return builder.lin(kind, terms, e, constant)


def box(builder, e, terminal=False):
    """One-sided box inequality for a linear expression in the input model."""
    terms = []
    ceiling = e[0]
    for i, c in e[1].items():
        variable = builder.model['vars'][i]
        bound = variable['upper'] if c > 0 else variable['lower']
        assert bound is not None, ('unbounded box', variable['name'], c)
        ceiling += c * bound
        terms.append([{'VarUpper' if c > 0 else 'VarLower': i}, abs(c)])
    assert ceiling <= 0, ('box not valid', e, ceiling)
    return fact(builder, 'Le', e, terms, ceiling, terminal)


def prepare(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == (397, 171, 213, 171)
    pivots = {a['var_index'][d['eliminated_continuous_variable']]: a['row_index'][d['row']]
              for d in h['row_edits']}
    zeros = {a['var_index'][n] for n in h['fixed_zero_integers_removed']}
    pair = [a['var_index'][n] for n in h['aggregation']['old_variables']]
    aggregate = b['var_index']['agg107']
    offset = b['var_index']['objconst']
    removed = set(pivots) | zeros | set(pair)
    assert len(removed) == 186 and len(pair) == 2 and len(pivots) == 171 and len(zeros) == 13
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])
              if v['name'] in a['var_index']]
    for i, j in common:
        assert a['vars'][i] == b['vars'][j]

    forward = [expression(1) if j == offset
               else expression(0, {i: 1 for i in pair}) if j == aggregate
               else expression(0, {a['var_index'][v['name']]: 1})
               for j, v in enumerate(b['vars'])]
    reverse = [None] * len(a['vars'])
    for i, v in enumerate(a['vars']):
        if i in zeros:
            reverse[i] = expression()
        elif i in pair:
            reverse[i] = expression(0, {aggregate: F(1, 2)})
            assert v['lower'] == 0 and v['upper'] == 4 and not v['integer']
        elif i not in pivots:
            reverse[i] = expression(0, {b['var_index'][v['name']]: 1})
    for i, ri in pivots.items():
        row = a['rows'][ri]
        assert row['sense'] == 'E' and row['terms'][i] == 1 and not a['vars'][i]['integer'] and a['vars'][i]['lower'] == 0
        assert all(reverse[j] is not None for j in row['terms'] if j != i)
        e = expression(row['rhs'])
        for j, c in row['terms'].items():
            if j != i:
                e = plus(e, reverse[j], -c)
        reverse[i] = e
    assert all(e is not None for e in reverse)

    proof, f, r = make_proof(a, b)

    # Forward: exact pivot elimination, both endpoints of every ranged row, and
    # the encoded fixed objective offset.
    zeroeq = {}
    for i in zeros:
        assert a['vars'][i]['lower'] == a['vars'][i]['upper'] == 0
        zeroeq[i] = f.eqpair({'VarUpper': i}, {'VarLower': i})

    def corrected(kind, wanted, terms):
        raw = expression()
        for ref, c in terms:
            raw = plus(raw, f.refexpr(ref), c)
        delta = plus(wanted, raw, -1)
        assert delta[0] == 0 and set(delta[1]) <= zeros
        return fact(f, kind, wanted,
                    terms + [[zeroeq[i], c] for i, c in delta[1].items()],
                    terminal=True)

    checks = []
    for i, v in enumerate(b['vars']):
        e = mapping = forward[i]
        for typ, value, sign in [('VarLower', v['lower'], -1), ('VarUpper', v['upper'], 1)]:
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            checks.append(box(f, wanted, True))
        if v['integer']:
            checks.append(fact(f, 'Int', e, [[{'VarInt': j}, c] for j, c in e[1].items()],
                               e[0], True))
    byrow = {a['rows'][ri]['name']: i for i, ri in pivots.items()}
    for row in b['rows']:
        name = row['name']
        i = byrow[name]
        ref = row_ref(a, name)
        lower = substitute(expression(row['lower'], {j: -c for j, c in row['terms'].items()}), forward)
        upper = substitute(expression(-row['upper'], row['terms']), forward)
        checks.append(corrected('Le', lower, [[ref, F(-1)], [{'VarUpper': i}, F(1)]]))
        checks.append(corrected('Le', upper, [[ref, F(1)], [{'VarLower': i}, F(1)]]))
    wanted = plus(substitute(b['objective'], forward), a['objective'], -1)
    checks.append(corrected('Eq', wanted,
                            [[{'RowEq': ri}, -a['objective'][1].get(i, F(0))]
                             for i, ri in pivots.items() if a['objective'][1].get(i, F(0))]))
    for i, j in common:
        assert forward[j] == expression(0, {i: 1})
    f.finish(forward, checks)

    # Reverse: recover every pivot from its source equality, split the
    # aggregate pair equally, and use both endpoints of each target range.
    offset_eq = r.eqpair({'VarUpper': offset}, {'VarLower': offset})
    checks = []
    for i, v in enumerate(a['vars']):
        e = reverse[i]
        for typ, value, sign in [('VarLower', v['lower'], -1), ('VarUpper', v['upper'], 1)]:
            if value is None:
                continue
            wanted = plus(mul(e, sign), expression(-sign * value))
            if i in pivots:
                ri = b['row_index'][a['rows'][pivots[i]]['name']]
                ref = {'RowUpper' if typ == 'VarLower' else 'RowLower': ri}
                checks.append(prove(r, 'Le', wanted, ref))
            else:
                checks.append(box(r, wanted, True))
        if v['integer']:
            checks.append(fact(r, 'Int', e, [[{'VarInt': j}, c] for j, c in e[1].items()],
                               e[0], True))
    for row in a['rows']:
        assert substitute(row_fact(row, 'RowEq'), reverse) == expression()
        checks.append('Exact')
    wanted = plus(substitute(a['objective'], reverse), b['objective'], -1)
    checks.append(fact(r, 'Eq', wanted,
                       [[offset_eq, -b['objective'][1][offset]]], terminal=True))
    for i, j in common:
        assert reverse[i] == expression(0, {j: 1})
    r.finish(reverse, checks)

    return proof, {
        'source_variables': 397, 'target_variables': 213,
        'source_rows': 171, 'target_ranged_rows': 171,
        'private_pivots': 171, 'fixed_zero_integers': 13,
        'aggregate_pair': 2, 'retained_coordinate_observations': len(common),
        'directions': 2, 'legacy_claims_collapsed': 4,
        'legacy_continuous_directions_omitted': 2,
        'legacy_projection_observations_omitted': len(common) + 1,
        'exact_objective_offset': str(b['objective'][1][offset]),
        'obligations_by_direction': [len(checks), len(checks)],
    }


def prove(builder, kind, wanted, support):
    if is_exact(kind, wanted):
        return 'Exact'
    if isinstance(support, dict):
        ref = builder.ref(support)
        assert ref.kind in (kind, 'Eq') and legacy_expr(ref.expression) == wanted
        return support
    return builder.lin(kind, support, wanted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test22-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test22'))
    parser.add_argument('--kernel', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_ranged_target(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test22', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test22', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
