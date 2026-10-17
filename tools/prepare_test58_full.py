#!/usr/bin/env python3
"""Native complete test58 MI dominance and objective-preserving recovery.

The forward direction is one simultaneous chain of interval, signed and subflow
lifts: edge ORs, path ANDs, parallel ORs, all 305 signed direction flows, and a
demand-bounded 606-arc subflow.  The reverse direction is the established
303-path SignedLift helper from ``prepare_test58``.  All target obligations are
derived by the native obligation walker; no manual extension model, raw step
dictionary, RPA write, request file, subprocess, point, or mutation is used.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression as E, plus, mul, row_fact, substitute, sha
from prepare_test46 import finish_checks
from prepare_test58 import reverse
from prepare_test87 import sumexpr
from prepare_native import compile_case, make_proof


def network_eq(builder, a, graph, desired):
    """Exact cut identity from a complete balance-row combination."""
    for edge in graph['edges'].values():
        xf = graph['index'](edge, 'forward', 'x')
        xr = graph['index'](edge, 'reverse', 'x')
        assert desired[1].get(xr, F(0)) == -desired[1].get(xf, F(0))
    potential = {next(iter(graph['adjacency'])): F(0)}
    todo = list(potential)
    while todo:
        node = todo.pop()
        for other, x, sign in graph['adjacency'][node]:
            value = potential[node] + sign * desired[1].get(x, F(0))
            if other in potential:
                assert potential[other] == value, ('not a cut identity', node, other)
            else:
                potential[other] = value
                todo.append(other)
    assert len(potential) == len(graph['adjacency'])
    return builder.lin('Eq', [[row_ref(a, n), v] for n, v in potential.items() if v],
                       desired)


def or_data(builder, layout, x, y, xint, yint, xlo, xhi):
    """One edge activation OR over native interval rows."""
    z = layout['variable']
    lo = [{'RowLower': r} for r in layout['lower']]
    up = [{'RowUpper': r} for r in layout['upper']]
    lower = builder.lin('Le', [[lo[0], F(1)], [xlo, F(1)]], E(0, {z: -1}))

    def inactive(c, guard):
        fixed = c.eqpair(guard, xlo)
        u = c.lin('Le', [[up[1], F(1)], [fixed, F(1)]], E(0, {z: 1, y: -1}))
        eq = c.eqpair(u, lo[1])
        return {'Witness': c.lin('Int', [[eq, F(1)], [yint, F(1)]], E(0, {z: 1}))}

    def active(c, guard):
        fixed = c.eqpair(xhi, guard)
        down = c.lin('Le', [[lo[0], F(1)], [fixed, F(-1)]], E(1, {z: -1}))
        eq = c.eqpair(up[0], down)
        return {'Witness': c.lin('Int', [[eq, F(1)]], E(0, {z: 1}), constant=1)}

    integer = builder.cases('Int', E(0, {z: 1}), E(0, {x: 1}), xint, inactive, active)
    return {'id': z, 'lower': lower, 'upper': up[0], 'sum': up[1],
            'contains': lo, 'integer': integer}


def forward(f, a, b, h):
    edges = {x['id']: x for x in h['symmetric_edges']}
    paths = {x['id']: x for x in h['series_paths']}
    bridgeids = {x['edge_id'] for x in h['bridge_cut_witnesses']}
    residual = sorted(set(edges) - bridgeids)
    assert len(residual) == 426
    assert set(eid for x in paths.values() for eid, sgn in x['steps']) == set(residual)
    assert sum(len(x['steps']) for x in paths.values()) == len(residual)
    assert len(a['vars']) == 2500 and len(b['vars']) == 607
    p = f

    def variable(i):
        return E(0, {i: 1})

    def idx(edge, direction, kind):
        return a['var_index'][edge[direction][kind]]

    def net_edge(eid, sign=1):
        edge = edges[eid]
        return E(0, {idx(edge, 'forward', 'x'): sign, idx(edge, 'reverse', 'x'): -sign})

    def net_path(pid):
        return net_edge(*paths[pid]['steps'][0])

    adjacency = {n: [] for n in h['original_balances']}
    for edge in edges.values():
        x = idx(edge, 'forward', 'x')
        adjacency[edge['u']].append((edge['v'], x, 1))
        adjacency[edge['v']].append((edge['u'], x, -1))
    graph = {'edges': edges, 'adjacency': adjacency, 'index': idx}

    # Every actual bridge net is fixed by a full balance-row combination.
    bridge_cost = []
    for cut in h['bridge_cut_witnesses']:
        eid = cut['edge_id']
        edge = edges[eid]
        value = F(cut['flow'])
        eq = network_eq(p, a, graph, plus(net_edge(eid), E(-value)))
        cost = F(edge['cost'])
        assert cost >= 0
        yp, ym = idx(edge, 'forward', 'y'), idx(edge, 'reverse', 'y')
        if value:
            direction = 'forward' if value > 0 else 'reverse'
            other = 'reverse' if value > 0 else 'forward'
            y = idx(edge, direction, 'y')
            xother = idx(edge, other, 'x')
            le = p.lin('Le', [[row_ref(a, edge[direction]['row']), F(1, 82)],
                              [{'VarLower': xother}, F(1, 82)],
                              [eq, F(-1 if value > 0 else 1, 82)]],
                       E(abs(value) / 82, {y: -1}))
            integer = p.lin('Int', [[{'VarInt': y}, F(-1)]], E(0, {y: -1}))
            up = p.round(le, integer)
            assert p.refexpr(up) == E(1, {y: -1})
            bridge_cost.append([p.lin('Le', [[up, cost], [{'VarLower': idx(edge, other, 'y')}, cost]],
                                      E(cost, {yp: -cost, ym: -cost})), F(1)])
        else:
            bridge_cost.extend([[{'VarLower': yp}, cost], [{'VarLower': ym}, cost]])
    bridge_bound = p.lin('Le', bridge_cost)
    assert p.refexpr(bridge_bound)[0] == 205

    # First simultaneous interval family: OR of each original edge's binaries.
    intervals = []
    edge_order = residual
    for eid in edge_order:
        edge = edges[eid]
        x, y = idx(edge, 'forward', 'y'), idx(edge, 'reverse', 'y')
        intervals.append({
            'lower': [variable(x), variable(y)],
            'upper': [E(1), E(0, {x: 1, y: 1})],
            'checks': [{'VarUpper': x}, {'VarLower': y}, {'VarUpper': y}, {'VarLower': x}],
        })
    p = p.intervals(intervals)
    layout = p.old_layout
    ors = {}
    for eid, l in zip(edge_order, layout):
        edge = edges[eid]
        x, y = idx(edge, 'forward', 'y'), idx(edge, 'reverse', 'y')
        ors[eid] = or_data(p, l, x, y, {'VarInt': x}, {'VarInt': y},
                           {'VarLower': x}, {'VarUpper': x})

    # Each path has a constant oriented net; every identity is checked on the
    # original incidence matrix, not inferred from path metadata.
    edgecaps = {}
    for pid, path in paths.items():
        for eid, sgn in path['steps']:
            edge = edges[eid]
            same = network_eq(p, a, graph, plus(net_path(pid), net_edge(eid, sgn), -1))
            o = ors[eid]
            for sign in [1, -1]:
                direction = 'forward' if sign * sgn == 1 else 'reverse'
                other = 'reverse' if direction == 'forward' else 'forward'
                chosen = 0 if direction == 'forward' else 1
                edgecaps[(pid, eid, sign)] = p.lin(
                    'Le', [[row_ref(a, edge[direction]['row']), F(1)],
                           [{'VarLower': idx(edge, other, 'x')}, F(1)],
                           [o['contains'][chosen], F(82)], [same, F(sign)]],
                    plus(mul(net_path(pid), sign), E(0, {o['id']: -82})))

    # Second family: AND across all edge ORs of each nontrivial path.
    long = [pid for pid, path in paths.items() if len(path['steps']) > 1]
    intervals = []
    for pid in long:
        bits = [ors[eid] for eid, sgn in paths[pid]['steps']]
        n = len(bits)
        checks = [x['lower'] for x in bits]
        for j in range(n):
            checks.append(p.lin('Le', [[x['upper'], F(1)]
                                       for i, x in enumerate(bits) if i != j]))
        intervals.append({
            'lower': [E(), E(1 - n, {x['id']: 1 for x in bits})],
            'upper': [variable(x['id']) for x in bits],
            'checks': checks,
        })
    p = p.intervals(intervals)
    andlayout = dict(zip(long, p.old_layout))
    pz = {}

    def fixed(c, bit, guard, value):
        return c.eqpair(guard, bit['lower']) if value == 0 else c.eqpair(bit['upper'], guard)

    for pid, path in paths.items():
        bits = [ors[eid] for eid, sgn in path['steps']]
        if len(bits) == 1:
            pz[pid] = bits[0]
            continue
        l = andlayout[pid]
        z = l['variable']
        lo = {'RowLower': l['lower'][0]}
        sumlower = {'RowLower': l['lower'][1]}
        upper = p.lin('Le', [[{'RowUpper': l['upper'][0]}, F(1)],
                             [bits[0]['upper'], F(1)]], E(-1, {z: 1}))

        def all_one(c, fixes):
            down = c.lin('Le', [[sumlower, F(1)]] + [[r, F(-1)] for r in fixes],
                         E(1, {z: -1}))
            return c.eqpair(upper, down)

        def integer_tree(c, k, fixes):
            if k == len(bits):
                return {'Witness': c.lin('Int', [[all_one(c, fixes), F(1)]],
                                         variable(z), constant=1)}
            bit = bits[k]

            def zero(ch, guard):
                f = fixed(ch, bit, guard, 0)
                u = ch.lin('Le', [[{'RowUpper': l['upper'][k]}, F(1)], [f, F(1)]],
                           variable(z))
                eq = ch.eqpair(u, lo)
                return {'Witness': ch.lin('Int', [[eq, F(1)]], variable(z))}

            return {'Witness': c.cases(
                'Int', variable(z), variable(bit['id']), bit['integer'], zero,
                lambda ch, guard: integer_tree(ch, k + 1, fixes + [fixed(ch, bit, guard, 1)]))}

        integer = integer_tree(p, 0, [])['Witness']
        pz[pid] = {'id': z, 'lower': lo, 'upper': upper, 'integer': integer,
                   'contains': [{'RowUpper': r} for r in l['upper']]}
        for sign in [1, -1]:
            wanted = plus(mul(net_path(pid), sign), E(0, {z: -82}))
            unconditional = p.lin(
                'Le', [[edgecaps[(pid, path['steps'][0][0], sign)], F(1)],
                       [bits[0]['upper'], F(82)]],
                plus(mul(net_path(pid), sign), E(-82)))

            def bound_tree(c, k, fixes):
                if k == len(bits):
                    return {'Witness': c.lin('Le', [[unconditional, F(1)],
                                                    [all_one(c, fixes), F(-82)]], wanted)}
                bit = bits[k]
                eid = path['steps'][k][0]

                def zero(ch, guard):
                    return {'Witness': ch.lin(
                        'Le', [[edgecaps[(pid, eid, sign)], F(1)],
                               [fixed(ch, bit, guard, 0), F(82)], [lo, F(82)]], wanted)}

                return {'Witness': c.cases(
                    'Le', wanted, variable(bit['id']), bit['integer'], zero,
                    lambda ch, guard: bound_tree(ch, k + 1,
                                                 fixes + [fixed(ch, bit, guard, 1)]))}

            pz[pid][sign] = bound_tree(p, 0, [])['Witness']

    for pid, path in paths.items():
        if len(path['steps']) == 1:
            for sign in [1, -1]:
                pz[pid][sign] = edgecaps[(pid, path['steps'][0][0], sign)]

    path_cost = {}
    for pid, path in paths.items():
        terms = []
        for k, (eid, sgn) in enumerate(path['steps']):
            cost = F(edges[eid]['cost'])
            terms.append([ors[eid]['sum'], cost])
            if len(path['steps']) > 1:
                terms.append([pz[pid]['contains'][k], cost])
        path_cost[pid] = p.lin('Le', terms)
        assert F(path['cost']) == sum(F(edges[eid]['cost']) for eid, sgn in path['steps'])

    # Parallel path activation ORs; keep the complete common tuple before the
    # signed lift.
    intervals = []
    for pair in h['parallel_dominance']:
        x, y = pz[pair['kept']], pz[pair['removed']]
        intervals.append({
            'lower': [variable(x['id']), variable(y['id'])],
            'upper': [E(1), E(0, {x['id']: 1, y['id']: 1})],
            'checks': [x['upper'], y['lower'], y['upper'], x['lower']],
        })
    p = p.intervals(intervals)
    layout = p.old_layout
    targetz = {pid: pz[pid] for pid in h['retained_path_ids']}
    merged = {d['kept']: d['removed'] for d in h['parallel_dominance']}
    parallel_bounds = []
    for pair, l in zip(h['parallel_dominance'], layout):
        pid, other = pair['kept'], pair['removed']
        x, y = pz[pid], pz[other]
        targetz[pid] = or_data(p, l, x['id'], y['id'], x['integer'], y['integer'],
                               x['lower'], x['upper'])
        ck, cr = F(paths[pid]['cost']), F(paths[other]['cost'])
        assert cr >= ck >= 0 and paths[pid]['u'] == paths[other]['u']
        assert paths[pid]['v'] == paths[other]['v']
        parallel_bounds.append([targetz[pid]['sum'], ck])
        parallel_bounds.append([y['lower'], cr - ck])
    objective_bound = p.lin('Le', [[bridge_bound, F(1)]] +
                            [[path_cost[pid], F(1)] for pid in paths] + parallel_bounds)

    # Existing SignedLift creates simultaneous nonnegative direction flows.
    decompositions = []
    for pid, path in paths.items():
        z = pz[pid]
        decompositions.append({
            'capacity': F(82),
            'flow': net_path(pid),
            'activation': variable(z['id']),
            'checks': [z['lower'], z['upper'], z['integer'], z[1], z[-1]],
        })
    p = p.signed(decompositions)
    signed_layout = p.old_layout
    signed = {}
    for pid, entry in zip(paths, signed_layout):
        signed[pid] = entry

    nodes = h['retained_balance_nodes']
    ni = {n: i for i, n in enumerate(nodes)}
    arcs = []
    flows = []
    nonnegative = []
    aggregate_cap = {}
    for pid in h['retained_path_ids']:
        path = paths[pid]
        parts = [pid] + ([merged[pid]] if pid in merged else [])
        for direction in [0, 1]:
            arcs.append([ni[path['u']], ni[path['v']]] if direction == 0
                        else [ni[path['v']], ni[path['u']]])
            field = 'positive' if direction == 0 else 'negative'
            flow = E(0, {signed[qid][field]: 1 for qid in parts})
            flows.append(flow)
            nonnegative.append(p.lin('Le', [[{'VarLower': i}, F(1)]
                                            for i in flow[1]], mul(flow, -1)))
            terms = []
            for qid in parts:
                entry = signed[qid]
                capacity = entry['positive_capacity_row' if direction == 0
                                 else 'negative_capacity_row']
                activation = entry['activation_row']
                other = entry['negative_activation' if direction == 0
                              else 'positive_activation']
                terms.extend([[{'RowUpper': capacity}, F(1)],
                              [{'RowEq': activation}, F(82)],
                              [{'VarLower': other}, F(82)]])
            aggregate_cap[(pid, direction)] = p.lin(
                'Le', terms, plus(flow, E(0, {pz[qid]['id']: -82 for qid in parts})))

    demands = [[ni[n], F(h['residual_balances_after_bridge_substitution'][n])]
               for n in nodes
               if n != h['residual_source'] and F(h['residual_balances_after_bridge_substitution'][n])]
    assert all(d >= 0 for n, d in demands)
    assert sum(d for n, d in demands) == 82
    balances = []
    for node in range(len(nodes)):
        rhs = (F(82) if nodes[node] == h['residual_source']
               else -F(h['residual_balances_after_bridge_substitution'][nodes[node]]))
        desired = plus(sumexpr(mul(flow, int(u == node) - int(v == node))
                               for (u, v), flow in zip(arcs, flows)), E(-rhs))
        remaining = desired
        terms = []
        for pid, entry in signed.items():
            coefficient = remaining[1].get(entry['positive'], F(0))
            if coefficient:
                terms.append([{'RowEq': entry['flow_row']}, coefficient])
                remaining = plus(remaining, p.refexpr({'RowEq': entry['flow_row']}),
                                 -coefficient)
        terms.append([network_eq(p, a, graph, remaining), F(1)])
        balances.append(p.lin('Eq', terms, desired))
    witness = {'nodes': len(nodes), 'arcs': arcs, 'groups': [{
        'source': ni[h['residual_source']],
        'demands': demands,
        'flows': flows,
        'nonnegative': nonnegative,
        'balances': balances,
    }]}
    p = p.subflow(witness)
    subflow = p.old_layout[0]

    mapping = [None] * len(b['vars'])
    domain = {}
    rowproof = {}
    for j, pid in enumerate(h['retained_path_ids']):
        path = paths[pid]
        gp = subflow['flows'][2 * j]
        gn = subflow['flows'][2 * j + 1]
        z = targetz[pid]
        fi, zi = b['var_index'][path['flow_var']], b['var_index'][path['activation_var']]
        mapping[fi] = E(0, {gp: 1, gn: -1})
        mapping[zi] = variable(z['id'])
        domain[zi] = {'VarLower': z['lower'], 'VarUpper': z['upper'], 'VarInt': z['integer']}
        for direction, name in [(0, path['upper_row']), (1, path['lower_row'])]:
            g, other = (gp, gn) if direction == 0 else (gn, gp)
            wanted = E(0, {g: 1, other: -1, z['id']: -82})
            sub = {'RowUpper': subflow['remainder_nonnegative_rows'][2 * j + direction]}
            if pid not in merged:
                ref = p.lin('Le', [[sub, F(1)],
                                   [aggregate_cap[(pid, direction)], F(1)],
                                   [{'VarLower': other}, F(1)]], wanted)
            else:
                def inactive(c, guard):
                    f = c.eqpair(guard, z['lower'])
                    terms = [[sub, F(1)], [aggregate_cap[(pid, direction)], F(1)],
                             [{'VarLower': other}, F(1)], [f, F(82)]] + \
                            [[r, F(82)] for r in z['contains']]
                    return {'Witness': c.lin('Le', terms, wanted)}

                def active(c, guard):
                    return {'Witness': c.lin('Le', [[{'VarUpper': g}, F(1)],
                                                    [{'VarLower': other}, F(1)],
                                                    [guard, F(82)]], wanted)}

                ref = p.cases('Le', wanted, variable(z['id']), z['integer'],
                              inactive, active)
            rowproof[name] = ref
    fixed_var = b['var_index']['OBJFIX']
    mapping[fixed_var] = E(1)
    assert all(x is not None for x in mapping)
    for row in b['rows']:
        if row['sense'] == 'E':
            rowproof[row['name']] = p.lin(
                'Eq', [[{'RowEq': subflow['balance_rows'][ni[row['name']]]}, F(-1)]],
                substitute(row_fact(row, 'RowEq'), mapping))
    assert len(rowproof) == len(b['rows'])
    checks = finish_checks(
        p, b, mapping,
        lambda i, typ: domain.get(i, {}).get(typ),
        lambda i: rowproof[b['rows'][i]['name']],
        objective_bound)
    p.finish(mapping, checks)
    return {
        'edge_ors': len(residual), 'path_ands': len(long),
        'parallel_ors': 2, 'signed_paths': 305,
        'joint_subflow_arcs': len(arcs), 'joint_subflow_nodes': len(nodes),
        'complete_output_obligations': len(checks),
    }


def prepare(a, b, h):
    proof, f, r = make_proof(a, b)
    forward_counts = forward(f, a, b, h)
    reverse_counts = reverse(r, a, b, h)
    return proof, {'forward': forward_counts, 'reverse': reverse_counts,
                   'directions': 2,
                   'claims': 'MI forward NonIncreasing and reverse Equal'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test58-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test58'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    h = json.loads(audit.read_text())
    a, b = parse_mps(source), parse_mps(target)
    assert sha(source) == h['source']['sha256'] and sha(target) == h['artifact']['sha256']
    proof, counts = prepare(a, b, h)
    record = compile_case(proof, args.out, case_id='test58', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test58', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
