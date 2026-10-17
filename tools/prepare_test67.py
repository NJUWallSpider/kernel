#!/usr/bin/env python3
"""Actual four activation fixes with explicit bounded local coloring refutations."""
from pathlib import Path
import argparse
import json
import time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, row_fact, sha
from prepare_native import compile_case, make_proof


def split_case(builder, wanted, var, left, right, kind='Le'):
    return builder.cases(kind, wanted, expression(0, {var: 1}),
                         integer={'VarInt': var}, left=left, right=right)


def local_setup(a, g, p):
    edges = []
    packing = []
    activation = [a['var_index'][f'c{k}'] for k in range(4)]
    for edge in g['internal_edges']:
        variables = [a['var_index'][edge['variables_by_color'][f'c{k}']]
                     for k in range(4)]
        ref = row_ref(a, edge['row'])
        assert p.kind(ref) == 'Eq' and \
            p.refexpr(ref) == expression(-1, {v: 1 for v in variables})
        edges.append((variables, ref))
    allvars = {v for vs, _ in edges for v in vs}
    assert len(allvars) == 68
    for vertex, names in sorted(g['local_vertices'].items(), key=lambda kv: int(kv[0])):
        for k in range(4):
            ref = row_ref(a, names[f'c{k}'])
            e = p.refexpr(ref)
            c = activation[k]
            assert e[0] == 0 and e[1][c] == -1 and \
                all(q == 1 for v, q in e[1].items() if v != c)
            local = sorted(set(e[1]) & allvars)
            external = set(e[1]) - allvars - {c}
            reduced = (p.lin('Le', [[ref, 1]] +
                             [[{'VarLower': v}, 1] for v in sorted(external)],
                             expression(0, {**{v: 1 for v in local}, c: -1}))
                       if external else ref)
            packed = p.lin('Le', [[reduced, 1], [{'VarUpper': c}, 1]],
                           expression(-1, {v: 1 for v in local}))
            packing.append((local, packed, reduced, k))
    return activation, edges, packing


def refute(p, disabled, zero, edges, packing, activation, stats):
    assigned = {}
    for variables, _, reduced, k in packing:
        if k != disabled:
            continue
        for x in variables:
            if x not in assigned:
                assigned[x] = (0, p.lin('Le', [[reduced, 1], [zero, 1]] +
                                       [[{'VarLower': y}, 1] for y in variables if y != x],
                                       expression(0, {x: 1})))

    def search(b, state, depth):
        stats['search_nodes'] += 1
        stats['maximum_depth'] = max(stats['maximum_depth'], depth)
        while True:
            changed = False
            for variables, eq in edges:
                ones = [v for v in variables if state.get(v, (None,))[0] == 1]
                unknown = [v for v in variables if v not in state]
                zeros = [v for v in variables if state.get(v, (None,))[0] == 0]
                if len(ones) >= 2:
                    terms = ([[eq, 1]] + [[state[v][1], 1] for v in ones] +
                             [[{'VarLower': v}, 1] for v in variables if v not in ones])
                    return {'Absurd': b.lin('Le', terms, expression(len(ones) - 1))}
                if not ones and not unknown:
                    return {'Absurd': b.lin('Le', [[eq, -1]] +
                                            [[state[v][1], 1] for v in variables],
                                            expression(1))}
                if ones:
                    for x in unknown:
                        terms = ([[eq, 1], [state[ones[0]][1], 1]] +
                                 [[{'VarLower': v}, 1]
                                  for v in variables if v not in (x, ones[0])])
                        state[x] = (0, b.lin('Le', terms, expression(0, {x: 1})))
                        changed = True
                elif len(unknown) == 1:
                    x = unknown[0]
                    state[x] = (1, b.lin('Le', [[eq, -1]] +
                                         [[state[v][1], 1] for v in zeros],
                                         expression(1, {x: -1})))
                    changed = True
            for variables, packed, _, _ in packing:
                ones = [v for v in variables if state.get(v, (None,))[0] == 1]
                unknown = [v for v in variables if v not in state]
                if len(ones) >= 2:
                    selected = ones[:2]
                    terms = ([[packed, 1]] + [[state[v][1], 1] for v in selected] +
                             [[{'VarLower': v}, 1]
                              for v in variables if v not in selected])
                    return {'Absurd': b.lin('Le', terms, expression(1))}
                if ones:
                    for x in unknown:
                        terms = ([[packed, 1], [state[ones[0]][1], 1]] +
                                 [[{'VarLower': v}, 1]
                                  for v in variables if v not in (x, ones[0])])
                        state[x] = (0, b.lin('Le', terms, expression(0, {x: 1})))
                        changed = True
            if not changed:
                break
        choices = [(len(unknown), index, unknown)
                   for index, (vs, _) in enumerate(edges)
                   if (unknown := [v for v in vs if v not in state])]
        assert choices, 'Local coloring unexpectedly feasible'
        _, _, unknown = min(choices)
        x = unknown[0]

        def branch(child, assumption, value):
            return search(child, {**state, x: (value, assumption)}, depth + 1)

        result = split_case(b, expression(1), x,
                            lambda child, assumption: branch(child, assumption, 0),
                            lambda child, assumption: branch(child, assumption, 1))
        return {'Absurd': result}

    return search(p, assigned, 0)


def prepare(a, b, g, h):
    assert [v['name'] for v in a['vars']] == [v['name'] for v in b['vars']] and \
        a['objective'] == b['objective']
    n = len(a['vars'])
    proof, f, r = make_proof(a, b)
    activation, edges, packing = local_setup(a, g, f)
    fixed = {}
    stats = {'search_nodes': 0, 'maximum_depth': 0}
    for k, c in enumerate(activation):
        wanted = expression(1, {c: -1})
        fixed[c] = split_case(
            f, wanted, c,
            lambda child, zero, k=k: refute(child, k, zero, edges, packing,
                                            activation, stats),
            lambda child, one: {'Witness': one})
    mapping = [expression(0, {i: 1}) for i in range(n)]

    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        p = r if back else f
        checks = []
        for i, v in enumerate(out['vars']):
            assert v['integer'] and v['upper'] == 1
            if not back and i in fixed:
                checks.append(fixed[i])
            elif back and i in fixed:
                checks.append(p.lin('Le', [[{'VarLower': i}, 1]],
                                    expression(0, {i: -1}), constant=-1))
            else:
                checks.append({'VarLower': i})
            checks.extend([{'VarUpper': i}, {'VarInt': i}])
        for row in out['rows']:
            rn = row['name']
            typ = next(iter(row_ref(out, rn)))
            wanted = row_fact(row, typ)
            original = inp['rows'][inp['row_index'][rn]]
            if row == original:
                ref = row_ref(inp, rn)
            else:
                control = next(i for i in activation
                               if i in a['rows'][a['row_index'][rn]]['terms'])
                assert row['sense'] == 'L'
                # Forward: -c is removed using c<=1. Reverse: restore it using c>=1.
                ref = p.lin('Le', [[row_ref(inp, rn), 1],
                                   [{'VarUpper' if not back else 'VarLower': control}, 1]],
                            wanted)
            checks.append(ref)
        checks.append('Exact')
        p.finish(mapping, checks)

    return proof, {'source_variables': n, 'target_variables': n,
                   'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
                   'fixed_activations': 4,
                   'substituted_rows': sum(len(v['rows']) for v in h['substitutions'].values()),
                   'local_edges': 17, 'local_binary_variables': 68, **stats,
                   'directions': 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('cases/test67'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = Path('/Users/bhz/Code/reform_test/runs/test67-nomf-B1')
    source = run / 'input/model.mps'
    target = run / 'output/model.mps'
    audit = run / 'output/audit.json'
    g = json.loads((run / 'output/certificate.json').read_text())
    h = json.loads(audit.read_text())
    proof, counts = prepare(parse_mps(source), parse_mps(target), g, h)
    record = compile_case(proof, args.out, case_id='test67', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test67', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'counts': counts,
                      'obligations': record['verification']['statistics']['obligations'],
                      'seconds': record['preparation_seconds']}))


if __name__ == '__main__':
    main()
