#!/usr/bin/env python3
"""Native test23 signed-difference proof using joint real interval extensions.

The proof is constructed through ``kernel_compiler``: the reverse direction
installs one native ``IntervalLift`` over all 2467 signed pairs and finishes the
lifted body through the owning direction. The legacy four-claim request
collapses to the two MI-OPT directions. ``extend`` and ``run_checks`` remain as
legacy helpers for preparers that have not been migrated.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import copy
import json
import time

from audit_test23 import inspect
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, substitute, sha
from prepare_native import compile_case, is_exact, make_proof


def expr_from_json(e):
    return expression(F(e['constant']), {i: F(c) for i, c in e['terms']})


def extend(model, pairs):
    """Legacy dict-model interval extension retained for unrelated preparers."""
    m = copy.deepcopy(model)
    layout = []
    for k, p in enumerate(pairs):
        i = len(m['vars'])
        name = f'interval_{k}'
        m['vars'].append({'name': name, 'lower': None, 'upper': None, 'integer': False})
        m['var_index'][name] = i
        layout.append({'variable': i, 'lower': [], 'upper': []})
    for k, p in enumerate(pairs):
        for which, sense in [('lower', 'G'), ('upper', 'L')]:
            for bound in p[which]:
                e = expr_from_json(bound)
                j = len(m['rows'])
                name = f'interval_row_{j}'
                row = plus(expression(0, {layout[k]['variable']: 1}), e, -1)
                m['rows'].append({'name': name, 'sense': sense, 'rhs': -row[0], 'terms': row[1]})
                m['row_index'][name] = j
                layout[k][which].append(j)
    return m, layout


def run_checks(builder, output, mapping, claim, domain_proof, row_proof, objective_proof):
    """Legacy step-emitting Return block retained for unrelated preparers."""
    checks = []
    def exact(kind, e):
        return not e[1] and ((kind == 'Eq' and e[0] == 0) or
                             (kind == 'Le' and e[0] <= 0) or
                             (kind == 'Int' and e[0].denominator == 1))
    def prove(kind, wanted, proof):
        if exact(kind, wanted):
            return 'Exact'
        if isinstance(proof, dict):
            assert builder.kind(proof) == kind and builder.refexpr(proof) == wanted
            return proof
        if len(proof) == 1 and proof[0][1] == 1 and builder.kind(proof[0][0]) == kind \
                and builder.refexpr(proof[0][0]) == wanted:
            return proof[0][0]
        return builder.lin(kind, proof, wanted)
    for i, v in enumerate(output['vars']):
        if v['lower'] is not None:
            wanted = plus(expression(v['lower']), mapping[i], -1)
            checks.append(prove('Le', wanted, domain_proof(i, 'VarLower')))
        if v['upper'] is not None:
            wanted = plus(mapping[i], expression(-v['upper']))
            checks.append(prove('Le', wanted, domain_proof(i, 'VarUpper')))
        if claim['output_integers'] and v['integer']:
            checks.append(prove('Int', mapping[i], domain_proof(i, 'VarInt')))
    for i, row in enumerate(output['rows']):
        typ = next(iter(row_ref(output, row['name'])))
        wanted = substitute(row_fact(row, typ), mapping)
        checks.append(prove('Eq' if typ == 'RowEq' else 'Le', wanted, row_proof(i, wanted)))
    wanted = plus(substitute(output['objective'], mapping), builder.model['objective'], -1)
    checks.append(prove('Eq', wanted, objective_proof(wanted)))
    for i, o in claim['projection']:
        assert plus(mapping[o], expression(0, {i: 1}), -1) == expression()
        checks.append('Exact')
    for inp, out in claim['affine_projection']:
        assert plus(substitute(expr_from_json(out), mapping), expr_from_json(inp), -1) == expression()
        checks.append('Exact')
    return {'steps': builder.steps, 'end': {'Return': {'map': [expr_json(e) for e in mapping],
                                                       'checks': checks}}}


def native_checks(builder, output, mapping, claim, domain_proof, row_proof, objective_proof):
    """Return the obligation witnesses in native plan order.

    MI-OPT has no projection or point claims: the map covers every output
    coordinate and the two directional returns are the whole request.
    """
    checks = []
    def prove(kind, wanted, proof):
        if is_exact(kind, wanted):
            return 'Exact'
        if not isinstance(proof, list):
            assert builder.kind(proof) in (kind, 'Eq') and builder.refexpr(proof) == wanted
            return proof
        if len(proof) == 1 and proof[0][1] == 1 and builder.kind(proof[0][0]) in (kind, 'Eq') \
                and builder.refexpr(proof[0][0]) == wanted:
            return proof[0][0]
        return builder.lin(kind, proof, wanted)
    for i, v in enumerate(output['vars']):
        if v['lower'] is not None:
            wanted = plus(expression(v['lower']), mapping[i], -1)
            checks.append(prove('Le', wanted, domain_proof(i, 'VarLower')))
        if v['upper'] is not None:
            wanted = plus(mapping[i], expression(-v['upper']))
            checks.append(prove('Le', wanted, domain_proof(i, 'VarUpper')))
        if claim['output_integers'] and v['integer']:
            checks.append(prove('Int', mapping[i], domain_proof(i, 'VarInt')))
    for i, row in enumerate(output['rows']):
        typ = next(iter(row_ref(output, row['name'])))
        wanted = substitute(row_fact(row, typ), mapping)
        checks.append(prove('Eq' if typ == 'RowEq' else 'Le', wanted, row_proof(i, wanted)))
    wanted = plus(substitute(output['objective'], mapping), builder.model['objective'], -1)
    checks.append(prove('Le', wanted, objective_proof(wanted)))
    # The requested observations are still checked exactly; MI-OPT does not
    # carry them as separate Return obligations.
    for i, o in claim['projection']:
        assert plus(mapping[o], expression(0, {i: 1}), -1) == expression()
    for inp, out in claim['affine_projection']:
        assert plus(substitute(expr_from_json(out), mapping), expr_from_json(inp), -1) == expression()
    return checks


def eq_without_fixed(builder, wanted, base, fixed):
    """Use both exact fixed bounds without creating one persistent fact per zero."""
    raw = expression()
    for ref, c in base:
        raw = plus(raw, builder.refexpr(ref), c)
    difference = plus(wanted, raw, -1)
    assert difference[0] == 0 and set(difference[1]) <= fixed
    if not difference[1]:
        if not wanted[1] and wanted[0] == 0:
            return []
        if len(base) == 1 and base[0][1] == 1:
            return base[0][0]
        return builder.lin('Eq', base, wanted)
    positive = list(base)
    negative = [[r, -c] for r, c in base]
    for i, c in difference[1].items():
        positive.append([{'VarUpper' if c > 0 else 'VarLower': i}, abs(c)])
        negative.append([{'VarLower' if c > 0 else 'VarUpper': i}, abs(c)])
    return builder.eqpair(builder.lin('Le', positive, wanted),
                          builder.lin('Le', negative, mul(wanted, -1)))


def prepare(a, b, h):
    w, samples = inspect(a, b, h)
    pairs = w['pairs']
    fixed = set(w['fixed_zero_source_variables'])
    observations = [[expr_json(expression(0, {p['source_v']: 1, p['source_w']: -1})),
                     expr_json(expression(0, {p['target_t']: 1}))] for p in pairs]
    proof, forward_builder, reverse_builder = make_proof(a, b)

    forward_claim = {'reverse': False, 'input_integers': True, 'output_integers': True,
                     'objective': 'Equal', 'projection': w['unchanged_coordinates'],
                     'affine_projection': observations, 'inverse': None}
    f = forward_builder
    mapping = [None] * len(b['vars'])
    domains = {}
    special_rows = {}
    for i, j in w['unchanged_coordinates']:
        mapping[j] = expression(0, {i: 1})
        domains[j] = {t: [[{t: i}, F(1)]] for t in ('VarLower', 'VarUpper', 'VarInt')}
    for p in pairs:
        v, z = p['source_v'], p['source_w']
        t = p['target_t']
        mapping[t] = expression(0, {v: 1, z: -1})
        domains[t] = {'VarLower': [[{'VarLower': v}, F(1)], [{'VarUpper': z}, F(1)]],
                      'VarUpper': [[{'VarUpper': v}, F(1)], [{'VarLower': z}, F(1)]]}
        rg, rl, sg, sl = p['source_rows']
        special_rows[p['target_rows'][0]] = [[row_ref(a, a['rows'][rg]['name']), F(1)],
                                             [row_ref(a, a['rows'][sl]['name']), F(1)]]
        special_rows[p['target_rows'][1]] = [[row_ref(a, a['rows'][rl]['name']), F(1)],
                                             [row_ref(a, a['rows'][sg]['name']), F(1)]]
    assert all(e is not None for e in mapping)

    def forward_row(i, wanted):
        if i in special_rows:
            return special_rows[i]
        return eq_without_fixed(f, wanted, [[row_ref(a, b['rows'][i]['name']), F(1)]], fixed)

    forward_checks = native_checks(f, b, mapping, forward_claim,
                                   lambda i, t: domains[i][t], forward_row,
                                   lambda wanted: eq_without_fixed(f, wanted, [], fixed))
    f.finish(mapping, forward_checks)

    reverse_claim = {'reverse': True, 'input_integers': True, 'output_integers': True,
                     'objective': 'Equal',
                     'projection': [[j, i] for i, j in w['unchanged_coordinates']],
                     'affine_projection': [[out, inp] for inp, out in observations],
                     'inverse': None}
    prelude = reverse_builder
    intervals = []
    for p in pairs:
        checks = []
        for terms, (lower, upper) in zip(
                p['lower_upper_proofs'],
                ((lo, hi) for lo in p['lower'] for hi in p['upper'])):
            expected = plus(expr_from_json(lower), expr_from_json(upper), -1)
            terms = [[ref, F(c)] for ref, c in terms]
            if expected == expression():
                checks.append('Exact')
            elif len(terms) == 1 and terms[0][1] == 1 and prelude.refexpr(terms[0][0]) == expected:
                checks.append(terms[0][0])
            else:
                checks.append(prelude.lin('Le', terms, expected))
        intervals.append({'lower': [expr_from_json(lo) for lo in p['lower']],
                          'upper': [expr_from_json(hi) for hi in p['upper']],
                          'checks': checks})
    r = prelude.intervals(intervals)
    layout = r.old_layout
    mapping = [None] * len(a['vars'])
    domains = {}
    rows = {}
    for i in fixed:
        mapping[i] = expression()
        domains[i] = {'VarLower': [], 'VarUpper': []}
    for i, j in w['unchanged_coordinates']:
        mapping[i] = expression(0, {j: 1})
        domains[i] = {t: [[{t: j}, F(1)]] for t in ('VarLower', 'VarUpper', 'VarInt')}
    for p, l in zip(pairs, layout):
        v, ww, y = p['source_v'], p['source_w'], p['target_y']
        t = p['target_t']
        z = l['variable']
        aa, M, bb, c = (F(p['parameters'][k]) for k in ('a', 'M', 'b', 'c'))
        mapping[v] = expression(0, {z: 1})
        mapping[ww] = expression(0, {z: 1, t: -1})
        lo0, lo1 = ({'RowLower': i} for i in l['lower'])
        up0, up1 = ({'RowUpper': i} for i in l['upper'])
        domains[v] = {'VarLower': [[lo0, F(1)], [{'VarLower': y}, aa]],
                      'VarUpper': [[up0, F(1)], [{'VarUpper': y}, M]]}
        domains[ww] = {'VarLower': [[lo1, F(1)], [{'VarUpper': y}, bb]],
                       'VarUpper': [[up1, F(1)], [{'VarLower': y}, c]]}
        for i, ref in zip(p['source_rows'], [lo0, up0, lo1, up1]):
            rows[i] = [[ref, F(1)]]
    for i, row in enumerate(a['rows']):
        if row['sense'] == 'E':
            rows[i] = [[{'RowEq': j}, F(c)]
                       for j, c in w['target_equality_combination']] \
                if i == w['dependent_source_equality'] else [[row_ref(b, row['name']), F(1)]]
    assert all(e is not None for e in mapping) and len(rows) == len(a['rows'])

    reverse_checks = native_checks(r, a, mapping, reverse_claim,
                                   lambda i, t: domains[i][t], lambda i, wanted: rows[i],
                                   lambda wanted: [])
    r.finish(mapping, reverse_checks)

    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'claims': 2, 'intervals_per_reverse': len(pairs),
              'extension_rows_per_reverse': 2 * len(pairs),
              'signed_observations': len(observations),
              'exact_local_lift_samples': samples,
              'forward_obligations': len(forward_checks),
              'reverse_obligations': len(reverse_checks)}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test23-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test23'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test23', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test23', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
