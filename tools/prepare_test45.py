#!/usr/bin/env python3
"""Actual test45: exact integer and LP retained projections with affine completion.

Only the native MI-OPT forward/reverse directions are emitted; the shared
``execute`` helper binds the proof to the corpus inventory without a request
JSON or a child process.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, sha
from prepare_test57 import substitute
from prepare_test54 import box, exact
from prepare_native import compile_case, make_proof


def prepare(a, b, h):
    proof, f, r = make_proof(a, b)
    common = [[a['var_index'][v['name']], j] for j, v in enumerate(b['vars'])]
    assert len(common) == 693 and len(a['vars']) == 1533
    forward = [expression(0, {i: 1}) for i, j in common]
    slack = {d['variable']: d for d in h['slack_eliminations']}
    binary = {d['variable']: d for d in h['binary_projections']}
    reverse = []
    for v in a['vars']:
        n = v['name']
        if n in b['var_index']:
            e = expression(0, {b['var_index'][n]: 1})
        elif n in slack:
            e = expression(0, {b['var_index'][x]: F(c)
                               for x, c in slack[n]['reconstruction'].items()})
        else:
            assert n in binary
            e = expression(1)
        reverse.append(e)
    changed = {d['row']: d for d in h['changed_rows']}
    duplicates = {d['removed_row']: d['kept_row'] for d in h['duplicate_rows']}
    slackrows = {d['row']: d for d in h['slack_eliminations']}
    implied = {d['row']: d for d in h['equality_implied_inequalities']}
    dominance = {d['row']: d for d in h['dominated_projected_rows']}

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        mapping = reverse if back else forward
        p = r if back else f
        checks = []
        cache = {}
        for i, v in enumerate(out['vars']):
            e = mapping[i]
            for typ, bound, sign in [('VarLower', v['lower'], -1), ('VarUpper', v['upper'], 1)]:
                if bound is not None:
                    wanted = plus(mul(e, sign), expression(-sign * bound))
                    checks.append(box(p, wanted, True))
            if v['integer']:
                if exact('Int', e):
                    ref = 'Exact'
                else:
                    ref = p.lin('Int', [[{'VarInt': j}, c] for j, c in e[1].items()], e, e[0])
                checks.append(ref)

        def restore(n):
            if n in cache:
                return cache[n]
            row = out['rows'][out['row_index'][n]]
            typ = next(iter(row_ref(out, n)))
            wanted = substitute(row_fact(row, typ), mapping)
            if exact('Eq' if typ == 'RowEq' else 'Le', wanted):
                ref = 'Exact'
            elif not back:
                ref = row_ref(a, n)
                if n in changed:
                    d = changed[n]
                    ref = p.lin('Le', [[ref, 1],
                                       [{'VarUpper': a['var_index'][d['removed_variable']]},
                                        -F(d['removed_coefficient'])]], wanted)
            elif n in duplicates:
                ref = restore(duplicates[n])
            elif n in slackrows:
                ref = row_ref(b, slackrows[n]['base_row'])
            elif n in implied:
                d = implied[n]
                ref = p.lin('Le', [[row_ref(b, d['base_row']), F(d['multiplier'])]]
                            + [[{'VarLower': b['var_index'][v]}, -F(c)]
                               for v, c in d['residual'].items()], wanted)
            elif n in dominance:
                d = dominance[n]
                terms = [[row_ref(b, d['witness_row']), 1]] + \
                        [[{'VarLower': b['var_index'][v]}, F(c)]
                         for v, c in d['residual'].items()]
                if not d['witness_projected']:
                    terms.append([{'VarUpper': b['var_index'][d['witness_binary']]},
                                  F(d['witness_rhs'])])
                ref = p.lin('Le', terms, wanted, F(d['witness_rhs']) - F(d['rhs']))
            else:
                ref = row_ref(b, n)
            assert ref == 'Exact' or p.refexpr(ref) == wanted, (back, n)
            cache[n] = ref
            return ref

        for row in out['rows']:
            checks.append(restore(row['name']))
        assert substitute(out['objective'], mapping) == inp['objective']
        checks.append('Exact')
        p.finish(mapping, checks)
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'slack_reconstructions': len(slack),
                   'canonical_binary_completions': len(binary),
                   'duplicates': len(duplicates),
                   'equality_implications': len(implied),
                   'dominated_capacities': len(dominance),
                   'changed_projected_rows': len(changed), 'directions': 2}


def execute(case, prepare, script):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('cases') / case)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    inventory = Path(__file__).resolve().parent.parent / 'audit/corpus_inventory.json'
    entry = next(e for e in json.loads(inventory.read_text())['cases']
                 if e['case_id'] == case)
    run = Path(entry['run_directory']) if args.run is None else args.run.resolve()
    source = run / entry['source_models'][0]['path']
    target = run / entry['final_target_models'][0]['path']
    audit = run / 'output/audit.json'
    assert sha(source) == entry['source_models'][0]['sha256']
    assert sha(target) == entry['final_target_models'][0]['sha256']
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id=case, source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {
                                        'path': str(Path(script).resolve()),
                                        'sha256': sha(Path(script))},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': record['case_id'], 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


def main():
    execute('test45', prepare, __file__)


if __name__ == '__main__':
    main()
