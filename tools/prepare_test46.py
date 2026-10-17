#!/usr/bin/env python3
"""Test46 table/marginal classification and native MI-OPT proof helpers.

The historical LP reverse certificate has no native MI-OPT equivalent: the
native proof API exposes exactly one forward and one reverse optimization
direction.  This module keeps the untrusted structural analysis, plus the
shared native linear-rule helpers used by ``prepare_test46_full``.  It never
writes an RPA/request pair and never invokes a kernel subprocess.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute
from prepare_native import is_exact, legacy_expr


def prove(builder, kind, wanted, support):
    """Return one native obligation witness for ``kind wanted``."""
    if is_exact(kind, wanted):
        return "Exact"
    if support is None:
        return builder.prove(kind, wanted)
    if isinstance(support, list):
        if len(support) == 1 and support[0][1] == 1:
            fact = builder.ref(support[0][0])
            if fact.kind in (kind, "Eq") and legacy_expr(fact.expression) == wanted:
                return support[0][0]
        return builder.lin(kind, support, wanted)
    fact = builder.ref(support)
    if fact.kind not in (kind, "Eq") or legacy_expr(fact.expression) != wanted:
        raise AssertionError(("bad witness", kind, wanted, fact.expression))
    return support


def finish_checks(builder, output, mapping, domain_terms, row_terms, objective_terms):
    """Build Return witnesses in the native obligation-walker order.

    The order is: each output variable's lower/upper/integer domain, each
    output row, then the single nonincreasing-objective obligation.  MI-OPT
    has no projection or point claims.
    """
    checks = []
    for i, variable in enumerate(output["vars"]):
        if variable["lower"] is not None:
            wanted = plus(expression(variable["lower"]), mapping[i], -1)
            checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarLower")))
        if variable["upper"] is not None:
            wanted = plus(mapping[i], expression(-variable["upper"]))
            checks.append(prove(builder, "Le", wanted, domain_terms(i, "VarUpper")))
        if variable["integer"]:
            checks.append(prove(builder, "Int", mapping[i], domain_terms(i, "VarInt")))
    for i, row in enumerate(output["rows"]):
        typ = next(iter(row_ref(output, row["name"])))
        wanted = substitute(row_fact(row, typ), mapping)
        checks.append(prove(builder, "Eq" if typ == "RowEq" else "Le",
                            wanted, row_terms(i)))
    residual = plus(substitute(output["objective"], mapping),
                    builder.model["objective"], -1)
    checks.append(prove(builder, "Le", residual, objective_terms))
    return checks


def inspect(a, b, h):
    assert (len(a['vars']), len(a['rows']), len(b['vars']), len(b['rows'])) == (159145, 301, 61036, 3615)
    assert all(r['sense'] == 'E' for r in a['rows'] + b['rows'])
    tables = []; selectors = set(); helpers = set(); classified_rows = set(); unary = {}; marginals = {}
    for hint in h['certificates']['table_cost_bounds']:
        norm = a['rows'][a['row_index'][hint['selection_row']]]; assert norm['rhs'] == 1 and set(norm['terms'].values()) == {F(1)}
        entries = set(norm['terms']); assert not selectors & entries; selectors |= entries
        cv = a['var_index'][hint['cost_variable']]; helpers.add(cv)
        costrow = a['rows'][a['row_index'][hint['cost_row']]]; assert costrow['rhs'] == 0 and costrow['terms'][cv] == -1 and set(costrow['terms']) == entries | {cv}
        costs = {i: costrow['terms'][i] for i in entries}; assert all(c >= 0 and c.denominator == 1 for c in costs.values())
        nodes = [a['var_index'][n] for n in hint['endpoint_variables']]; states = []
        for name, node in zip(hint['endpoint_index_rows'], nodes):
            helpers.add(node); r = a['rows'][a['row_index'][name]]; assert r['rhs'] == 0 and r['terms'][node] == -1 and set(r['terms']) <= (entries | {node})
            st = {i: r['terms'].get(i, F(0)) for i in entries}; assert all(q.denominator == 1 and 0 <= q <= 48 for q in st.values()); states.append(st)
        assert len(nodes) in (1, 2) and len(set(nodes)) == len(nodes)
        coordinates = {tuple(int(st[i]) for st in states): i for i in entries}; assert len(coordinates) == len(entries)
        assert set(coordinates) == ({(j,) for j in range(49)} if len(nodes) == 1 else {(i, j) for i in range(49) for j in range(49)})
        retained = {ij: i for ij, i in coordinates.items() if costs[i] != 39424}; forbidden = entries - set(retained.values())
        constant = hint['selection_row'] in h['edits']['eliminated_constant_factors']
        t = {'name': hint['selection_row'], 'norm': a['row_index'][hint['selection_row']], 'cost_row': a['row_index'][hint['cost_row']],
             'cost_var': cv, 'moments': [a['row_index'][n] for n in hint['endpoint_index_rows']], 'nodes': nodes,
             'states': states, 'entries': entries, 'coords': coordinates, 'costs': costs,
             'allowed': retained, 'forbidden': forbidden, 'constant': constant,
             'max': max(costs[i] for i in retained.values()), 'min': min(costs[i] for i in retained.values())}
        tables.append(t); classified_rows |= {t['norm'], t['cost_row'], *t['moments']}
        if len(nodes) == 1: assert nodes[0] not in unary; unary[nodes[0]] = t
    obj = a['var_index']['objective']; assert a['objective'] == expression(0, {obj: 1})
    assert classified_rows == set(range(len(a['rows']))) - {a['row_index']['p_lin_0']}
    assert selectors | helpers | {obj} == set(range(len(a['vars']))) and not selectors & helpers and obj not in helpers
    assert a['rows'][a['row_index']['p_lin_0']]['rhs'] == 0 and a['rows'][a['row_index']['p_lin_0']]['terms'] == {obj: F(1), **{t['cost_var']: F(-1) for t in tables}}
    assert all(a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] == 1 and a['vars'][i]['integer'] for i in selectors)
    assert a['vars'][obj]['lower'] == 0 and a['vars'][obj]['upper'] == 39423 and a['vars'][obj]['integer']
    assert all(a['vars'][t['cost_var']]['lower'] == 0 and a['vars'][t['cost_var']]['upper'] == 39424 and a['vars'][t['cost_var']]['integer'] for t in tables)
    assert all(a['vars'][n]['lower'] == 0 and a['vars'][n]['upper'] == 48 and a['vars'][n]['integer'] for n in unary)
    removed_constant = set(); forbidden = set(); retained = set()
    for t in tables:
        forbidden |= t['forbidden']
        if len(t['nodes']) == 2:
            domains = [set(j[0] for j in unary[n]['allowed']) for n in t['nodes']]
            assert set(t['allowed']) <= {(i, j) for i in domains[0] for j in domains[1]}
            if t['constant']:
                assert set(t['allowed']) == {(i, j) for i in domains[0] for j in domains[1]}
                assert {t['costs'][i] for i in t['allowed'].values()} == {F(17)}; removed_constant |= set(t['allowed'].values())
        if not t['constant']: retained |= set(t['allowed'].values())
    assert {a['vars'][i]['name'] for i in retained | {obj}} == set(b['var_index'])
    assert len(forbidden) == 80785 and len(removed_constant) == 17234 and len(helpers) == 90
    assert sum(t['max'] for t in tables) == 39389 and sum(t['min'] for t in tables) == 1417
    oldnew = {i: b['var_index'][a['vars'][i]['name']] for i in retained | {obj}}
    binaries = {i for t in unary.values() for i in t['allowed'].values()}
    for i, j in oldnew.items():
        expected = {**a['vars'][i], 'integer': i in binaries, 'upper': None if i == obj else F(1)}
        assert b['vars'][j] == expected
    assert b['objective'] == expression(0, {oldnew[obj]: 1})
    expectedrows = {}; objterms = {oldnew[obj]: F(1)}
    for t in tables:
        if t['constant']: continue
        for i in t['allowed'].values(): objterms[oldnew[i]] = -t['costs'][i]
        if len(t['nodes']) == 1:
            expectedrows[t['name']] = {'name': t['name'], 'sense': 'E', 'rhs': F(1), 'terms': {oldnew[i]: F(1) for i in t['allowed'].values()}}
    expectedrows['p_lin_0'] = {'name': 'p_lin_0', 'sense': 'E', 'rhs': F(289), 'terms': objterms}
    byname = {t['name']: t for t in tables}
    for name, hint in h['edits']['new_marginal_rows'].items():
        t = byname[hint['original_pair_selection_row']]; assert not t['constant']; node = a['var_index'][hint['node']]
        side = t['nodes'].index(node); state = hint['state']; u = unary[node]['allowed'][(state,)]
        ids = [i for ij, i in t['allowed'].items() if ij[side] == state]; assert ids
        expectedrows[name] = {'name': name, 'sense': 'E', 'rhs': F(0), 'terms': {**{oldnew[i]: F(1) for i in ids}, oldnew[u]: F(-1)}}
        marginals[(t['name'], side, state)] = b['row_index'][name]
    assert set(expectedrows) == set(b['row_index'])
    for r in b['rows']: assert r == expectedrows[r['name']], ('target row changed', r['name'])
    return {'tables': tables, 'unary': unary, 'obj': obj, 'forbidden': forbidden,
            'oldnew': oldnew, 'marginals': marginals, 'constant_entries': removed_constant}


def target_setup(a, b, s, p):
    """Exact normalization/moment/cost facts shared by both MI directions."""
    norms = {}; means = {}; meanbounds = {}; costs = {}; costbounds = {}; moments = {}; oldnew = s['oldnew']
    for node, t in s['unary'].items():
        norm = row_ref(b, t['name']); norms[t['name']] = norm
        mean = expression(0, {oldnew[i]: F(ij[0]) for ij, i in t['allowed'].items() if ij[0]})
        means[node] = mean
        lo = p.lin('Le', [[{'VarLower': j}, c] for j, c in mean[1].items()], mul(mean, -1))
        hi = p.lin('Le', [[norm, F(48)]] + [[{'VarLower': oldnew[i]}, 48 - F(ij[0])] for ij, i in t['allowed'].items() if ij[0] != 48], plus(mean, expression(-48)))
        meanbounds[node] = (lo, hi)
    for t in s['tables']:
        if t['constant']: costs[t['cost_var']] = expression(17); continue
        if len(t['nodes']) == 2:
            terms = [[{'RowEq': s['marginals'][(t['name'], 0, ij[0])]}, F(1)] for ij in s['unary'][t['nodes'][0]]['allowed']]
            terms.append([norms[s['unary'][t['nodes'][0]]['name']], F(1)])
            norms[t['name']] = p.lin('Eq', terms, expression(-1, {oldnew[i]: F(1) for i in t['allowed'].values()}))
            for side, node in enumerate(t['nodes']):
                wanted = plus(expression(0, {oldnew[i]: F(ij[side]) for ij, i in t['allowed'].items() if ij[side]}), means[node], -1)
                moments[(t['name'], side)] = p.lin('Eq', [[{'RowEq': s['marginals'][(t['name'], side, ij[0])]}, F(ij[0])] for ij in s['unary'][node]['allowed'] if ij[0]], wanted)
        cost = expression(0, {oldnew[i]: t['costs'][i] for i in t['allowed'].values()}); costs[t['cost_var']] = cost
        lo = p.lin('Le', [[{'VarLower': i}, c] for i, c in cost[1].items()], mul(cost, -1))
        hi = p.lin('Le', [[norms[t['name']], t['max']]] + [[{'VarLower': oldnew[i]}, t['max'] - t['costs'][i]] for i in t['allowed'].values() if t['max'] != t['costs'][i]], plus(cost, expression(-t['max'])))
        costbounds[t['cost_var']] = (lo, hi)
    objupper = p.lin('Le', [[row_ref(b, 'p_lin_0'), F(1)]] + [[hi, F(1)] for lo, hi in costbounds.values()], expression(-39423, {oldnew[s['obj']]: F(1)}), constant=F(39389 - 39423))
    return {'norms': norms, 'means': means, 'meanbounds': meanbounds, 'costs': costs,
            'costbounds': costbounds, 'moments': moments, 'objupper': objupper}


def lp_blocker():
    """The historical LP-only reverse direction has no native MI-OPT form."""
    return {
        'case_id': 'test46',
        'status': 'BLOCKED',
        'blocker': 'LP_ONLY_DIRECTION_NOT_IN_NATIVE_MI_OPT',
        'reason': ('The native Proof contract contains exactly one forward and one reverse '
                   'MI_OPT direction.  The historical test46 lp phase is a target-LP-to-'
                   'source-LP reverse consequence, not an MI direction, so it cannot be '
                   'emitted as a native proof.  No replacement proof is fabricated.'),
        'native_port': 'prepare_test46_full.py',
        'native_directions': ['forward_mi', 'reverse_mi'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=Path('/Users/bhz/Code/reform_test/runs/test46-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test46'))
    parser.add_argument('--kernel', type=Path)
    parser.add_argument('--phase', choices=['lp'], default='lp')
    args = parser.parse_args()
    run = args.run.resolve()
    if args.out:
        args.out.resolve().mkdir(parents=True, exist_ok=True)
        receipt = lp_blocker()
        receipt['source'] = str(run / 'input/model.mps')
        receipt['target'] = str(run / 'output/reformulated.mps')
        (args.out.resolve() / 'lp-blocker.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(lp_blocker(), indent=2))


if __name__ == '__main__':
    main()
