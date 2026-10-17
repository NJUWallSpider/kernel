#!/usr/bin/env python3
"""Native test21 dominance certificate, using ordinary linear rules.

The forward MI-OPT direction is objective non-increasing; the reverse direction
is objective equality. The legacy LP duplicate is not part of the two-direction
contract, so only the two integer directions are emitted.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, mul, row_fact, sha
from prepare_native import compile_case, make_proof


def add_term(terms, i, c):
    if not c:
        return
    value = terms.get(i, F(0)) + c
    if value:
        terms[i] = value
    else:
        terms.pop(i, None)


def combine(items, constant=0):
    out = {}
    constant = F(constant)
    for e, c in items:
        if not c:
            continue
        constant += e[0] * c
        for i, q in e[1].items():
            add_term(out, i, q if c == 1 else -q if c == -1 else q * c)
    return constant, out


def substitute(e, mapping):
    return combine(((mapping[i], c) for i, c in e[1].items()), e[0])


def maps(a, b, hints):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == (87482, 36, 46168, 35)
    for model in [a, b]:
        assert all(v['integer'] and v['lower'] == 0 and v['upper'] == 1 for v in model['vars'])
        assert all(r['sense'] == 'E' and r['rhs'] == 1 and set(r['terms'].values()) == {F(1)}
                   for r in model['rows'])
    duplicate = {x['removed']: x['representative'] for x in hints['duplicate_columns']}
    replace = {x['removed']: x['replacements'] for x in hints['disjoint_replacement_dominance']}
    assert len(duplicate) == 41292 and len(replace) == 21
    support = [set() for _ in a['vars']]
    for r, row in enumerate(a['rows']):
        for i in row['terms']:
            support[i].add(r)
    for removed, representative in duplicate.items():
        i, j = a['var_index'][removed], a['var_index'][representative]
        assert support[i] == support[j] and a['objective'][1][i] >= a['objective'][1][j]
        assert representative not in duplicate
    for removed, replacements in replace.items():
        assert removed not in duplicate and removed not in b['var_index']
        total = set()
        for name in replacements:
            assert name in b['var_index'] and name not in replace
            ids = support[a['var_index'][name]]
            assert total.isdisjoint(ids)
            total |= ids
        assert total == support[a['var_index'][removed]]
        assert sum(a['objective'][1][a['var_index'][name]] for name in replacements) <= \
            a['objective'][1][a['var_index'][removed]]
    forward = [expression() for _ in b['vars']]
    for i, var in enumerate(a['vars']):
        if var['name'] == 'x600':
            continue
        representative = duplicate.get(var['name'], var['name'])
        for name in replace.get(representative, [representative]):
            assert name in b['var_index']
            forward[b['var_index'][name]][1][i] = F(1)
    reverse = []
    for var in a['vars']:
        name = 'x599' if var['name'] == 'x600' else var['name']
        reverse.append(expression(0, {b['var_index'][name]: 1})
                       if name in b['var_index'] else expression())
    assert all(e[1] for e in forward)
    return forward, reverse, support


def forward_proof(p, a, b, forward, support):
    lower = {}
    upper = {}
    chosen = defaultdict(list)
    for j, e in enumerate(forward):
        if len(e[1]) == 1:
            i = next(iter(e[1]))
            lower[j] = {'VarLower': i}
            upper[j] = {'VarUpper': i}
        else:
            lower[j] = p.lin('Le', [[{'VarLower': i}, F(1)] for i in e[1]], mul(e, -1))
            common = set.intersection(*(support[i] for i in e[1]))
            assert common
            row = min(common, key=lambda r: (len(a['rows'][r]['terms']), r))
            chosen[row].append(j)

    def build_tree(leaves):
        if len(leaves) == 1:
            return {'leaf': leaves[0], 'lower': lower[leaves[0]]}
        half = len(leaves) // 2
        left = build_tree(leaves[:half])
        right = build_tree(leaves[half:])
        lo = p.lin('Le', [[left['lower'], F(1)], [right['lower'], F(1)]])
        return {'left': left, 'right': right, 'lower': lo}

    def spread(node, up):
        if 'leaf' in node:
            j = node['leaf']
            assert p.refexpr(up) == combine([(forward[j], F(1))], -1)
            upper[j] = up
            return
        l, r = node['left'], node['right']
        lu = p.lin('Le', [[up, F(1)], [r['lower'], F(1)]])
        ru = p.lin('Le', [[up, F(1)], [l['lower'], F(1)]])
        spread(l, lu)
        spread(r, ru)

    for row, groups in sorted(chosen.items()):
        selected = set()
        for j in groups:
            assert selected.isdisjoint(forward[j][1])
            selected.update(forward[j][1])
        assert selected <= a['rows'][row]['terms'].keys()
        tree = build_tree(groups)
        terms = [[{'RowEq': row}, F(1)]] + \
                [[{'VarLower': i}, F(1)] for i in a['rows'][row]['terms'] if i not in selected]
        root = p.lin('Le', terms, expression(-1, {i: 1 for i in selected}))
        spread(tree, root)

    alias = p.lin('Eq', [[row_ref(a, 'c1'), F(1)], [row_ref(a, 'c2'), F(-1)]],
                  expression(0, {a['var_index']['x599']: 1, a['var_index']['x600']: -1}))
    objective = combine([(substitute(b['objective'], forward), F(1)), (a['objective'], F(-1))])
    alias_scale = objective[1].get(a['var_index']['x599'], F(0))
    remainder = combine([(objective, F(1)), (p.refexpr(alias), -alias_scale)])
    assert remainder[0] == 0 and all(c <= 0 for c in remainder[1].values())
    obj = p.lin('Le', [[alias, alias_scale]] +
                [[{'VarLower': i}, -c] for i, c in remainder[1].items()], objective)
    info = {'multiple_contributor_groups': len(lower) - sum(len(e[1]) == 1 for e in forward),
            'bound_tree_source_rows': len(chosen),
            'largest_contributor_group': max(len(e[1]) for e in forward),
            'forward_nonzeros': sum(len(e[1]) for e in forward),
            'proof_local_terms': sum(len(e[1]) for k, e in p.facts.values())}
    return lower, upper, obj, info


def block(p, out, mapping, reverse, lower=None, upper=None, objective=None):
    checks = []
    for j, (v, e) in enumerate(zip(out['vars'], mapping)):
        if reverse:
            if not e[1]:
                lo = hi = 'Exact'
            else:
                i = next(iter(e[1]))
                lo = {'VarLower': i}
                hi = {'VarUpper': i}
        else:
            lo, hi = lower[j], upper[j]
        checks.append(p.check('Le', mul(e, -1), lo))
        checks.append(p.check('Le', combine([(e, F(1))], -1), hi))
        if v['integer']:
            checks.append(p.check('Int', e, 'Exact'))
    for row in out['rows']:
        name = 'c1' if reverse and row['name'] == 'c2' else row['name']
        checks.append(p.check('Eq', substitute(row_fact(row, 'RowEq'), mapping),
                              row_ref(p.model, name)))
    difference = combine([(substitute(out['objective'], mapping), F(1)),
                          (p.model['objective'], F(-1))])
    checks.append(p.check('Eq' if reverse else 'Le', difference,
                          'Exact' if reverse else objective))
    p.finish(mapping, checks)
    return len(checks)


def prepare(a, b, hints):
    forward, reverse, support = maps(a, b, hints)
    proof, f, r = make_proof(a, b)
    lower, upper, obj, info = forward_proof(f, a, b, forward, support)
    obf = block(f, b, forward, False, lower, upper, obj)
    obr = block(r, a, reverse, True)
    return proof, {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'directions': 2, 'obligations_by_claim': [obf, obr], **info}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test21-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test21'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source, target = run / 'input/model.mps', run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target), json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test21', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'proof_preparer': {'path': str(Path(__file__).resolve()),
                                                       'sha256': sha(Path(__file__))},
                                    'preparer_dependencies': {
                                        name: sha(Path(__file__).with_name(name))
                                        for name in ['prepare_affine.py', 'prepare_test40.py']},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test21', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations']}))


if __name__ == '__main__':
    main()
