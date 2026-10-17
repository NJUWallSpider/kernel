#!/usr/bin/env python3
"""Native test83 integer dominance/recovery maps, with exact MI-OPT directions."""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, mul, row_fact, sha
from prepare_test21 import combine, substitute
from prepare_native import compile_case, make_proof


def prepare(a, b, h):
    assert (len(a['vars']), len(b['vars']), len(a['rows']),
            len(b['rows'])) == (65832, 65671, 100, 100)
    assert all(v['integer'] and v['lower'] == 0 and v['upper'] == 1
               for m in [a, b] for v in m['vars'])
    assert all(r['sense'] == 'E' and r['rhs'] == 1 and set(r['terms'].values()) == {F(1)}
               for r in a['rows'])
    support = [set() for _ in a['vars']]
    for ri, row in enumerate(a['rows']):
        for i in row['terms']:
            support[i].add(ri)
    replacements = {a['var_index'][d['removed_variable']]:
                    [a['var_index'][v] for v in d['replacement_variables']]
                    for d in h['dominance_deletions']}
    singletons = {a['var_index'][d['variable']]: a['row_index'][d['row']]
                  for d in h['singleton_eliminations']}
    assert len(replacements) == 61 and len(singletons) == 100
    savings = {}
    for i, js in replacements.items():
        assert len(js) == 2 and not (support[js[0]] & support[js[1]])
        assert support[js[0]] | support[js[1]] == support[i]
        assert not any(j in replacements for j in js)
        savings[i] = a['objective'][1][i] - sum(a['objective'][1][j] for j in js)
        assert savings[i] > 0
    for i, ri in singletons.items():
        assert support[i] == {ri}
    assert set(a['var_index']) - set(b['var_index']) == {
        a['vars'][i]['name'] for i in set(replacements) | set(singletons)}
    aggregates = {i: expression(0, {i: 1}) for i in range(len(a['vars']))
                  if i not in replacements}
    for i, js in replacements.items():
        for j in js:
            aggregates[j][1][i] = F(1)
    forward = [aggregates[a['var_index'][v['name']]] for v in b['vars']]
    reverse = []
    for i, v in enumerate(a['vars']):
        if i in replacements:
            e = expression()
        elif i in singletons:
            ri = singletons[i]
            row = b['rows'][b['row_index'][a['rows'][ri]['name']]]
            e = expression(1, {j: -1 for j in row['terms']})
        else:
            e = expression(0, {b['var_index'][v['name']]: 1})
        reverse.append(e)
    proof, p, r = make_proof(a, b)
    lower = {}
    upper = {}
    integer = {}
    chosen = defaultdict(list)
    for j, e in enumerate(forward):
        if len(e[1]) == 1:
            i = next(iter(e[1]))
            lower[j] = {'VarLower': i}
            upper[j] = {'VarUpper': i}
            integer[j] = {'VarInt': i}
        else:
            lower[j] = p.lin('Le', [[{'VarLower': i}, 1] for i in e[1]], mul(e, -1))
            integer[j] = p.lin('Int', [[{'VarInt': i}, c] for i, c in e[1].items()], e)
            common = set.intersection(*(support[i] for i in e[1]))
            assert common
            chosen[min(common, key=lambda ri: (len(a['rows'][ri]['terms']), ri))].append(j)

    def tree(groups):
        if len(groups) == 1:
            return {'leaf': groups[0], 'lower': lower[groups[0]]}
        mid = len(groups) // 2
        left, right = tree(groups[:mid]), tree(groups[mid:])
        return {'left': left, 'right': right,
                'lower': p.lin('Le', [[left['lower'], 1], [right['lower'], 1]])}

    def spread(node, up):
        if 'leaf' in node:
            upper[node['leaf']] = up
            return
        left, right = node['left'], node['right']
        lu = p.lin('Le', [[up, 1], [right['lower'], 1]])
        ru = p.lin('Le', [[up, 1], [left['lower'], 1]])
        spread(left, lu)
        spread(right, ru)

    for ri, groups in sorted(chosen.items()):
        selected = set()
        for j in groups:
            assert selected.isdisjoint(forward[j][1])
            selected.update(forward[j][1])
        node = tree(groups)
        root = p.lin('Le', [[{'RowEq': ri}, 1]] +
                     [[{'VarLower': i}, 1] for i in a['rows'][ri]['terms']
                      if i not in selected],
                     expression(-1, {i: 1 for i in selected}))
        spread(node, root)
    costs = {ri: a['objective'][1][i] for i, ri in singletons.items()}
    wanted = combine([(substitute(b['objective'], forward), 1), (a['objective'], -1)])
    eqterms = [[{'RowEq': ri}, -costs[ri]] for ri in range(100)]
    residual = combine([(wanted, 1)] +
                       [(p.refexpr(fact), -c) for fact, c in eqterms])
    assert residual == expression(0, {i: -c for i, c in savings.items()})
    objective = p.lin('Le', eqterms + [[{'VarLower': i}, saving]
                                       for i, saving in savings.items()], wanted)
    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': 100, 'target_rows': 100,
              'dominated_columns': len(replacements),
              'singleton_substitutions': len(singletons),
              'objective_constant': str(b['objective'][0]),
              'directions': 2, 'multi_contributor_groups': sum(len(e[1]) > 1 for e in forward),
              'bound_tree_rows': len(chosen),
              'minimum_strict_saving': str(min(savings.values())),
              'maximum_strict_saving': str(max(savings.values())),
              'obligations_by_direction': {}}
    checks = []
    for j in range(len(forward)):
        checks.extend([lower[j], upper[j], integer[j]])
    singleton_by_row = {ri: i for i, ri in singletons.items()}
    for row in b['rows']:
        ri = a['row_index'][row['name']]
        i = singleton_by_row[ri]
        expected = substitute(row_fact(row, 'RowUpper'), forward)
        checks.append(p.lin('Le', [[{'RowEq': ri}, 1]] +
                            [[{'VarLower': q}, 1] for q in aggregates[i][1]], expected))
    checks.append(objective)
    p.finish(forward, checks)
    counts['obligations_by_direction']['forward'] = len(checks)
    checks = []
    for i, (v, e) in enumerate(zip(a['vars'], reverse)):
        if i in replacements:
            checks.extend(['Exact', 'Exact', 'Exact'])
        elif i in singletons:
            ri = singletons[i]
            rn = a['rows'][ri]['name']
            checks.extend([row_ref(b, rn),
                           r.lin('Le', [[{'VarLower': j}, 1] for j in e[1]],
                                 expression(0, e[1])),
                           r.lin('Int', [[{'VarInt': j}, c] for j, c in e[1].items()],
                                 e, constant=e[0])])
        else:
            j = next(iter(e[1]))
            checks.extend([{'VarLower': j}, {'VarUpper': j}, {'VarInt': j}])
    for row in a['rows']:
        assert substitute(row_fact(row, 'RowEq'), reverse) == expression()
        checks.append('Exact')
    assert substitute(a['objective'], reverse) == b['objective']
    checks.append('Exact')
    r.finish(reverse, checks)
    counts['obligations_by_direction']['reverse'] = len(checks)
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test83-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test83'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test83', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test83', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
