#!/usr/bin/env python3
"""Native test36 minimum preservation and objective recovery.

The forward direction proves that every retained-coordinate source lift maps to
a target point with nonincreasing objective; the reverse direction recovers the
complete source model with equal objective.  The historical caller-bound
strict/all-optimizer exclusion and the input-halfspace projection are not native
MI-OPT claims, so they are reported as explicit out-of-contract routes rather
than fabricated certificates.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter, defaultdict
import argparse
import json
import time

from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, row_fact, substitute, sha
from prepare_test46 import finish_checks
from prepare_test87 import sumexpr
from prepare_native import compile_case, legacy_from_native, make_proof, native_expr


def var(i):
    return expression(0, {i: F(1)})


def inspect(a, b, h):
    assert len(a['vars']) == 37816 and len(b['vars']) == 37616 and len(a['rows']) == len(b['rows']) == 37617
    bits = [i for i, v in enumerate(a['vars']) if v['integer']]
    assert len(bits) == 200
    assert all(a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] == 1 for i in bits)
    cardinal = next(i for i, r in enumerate(a['rows']) if r['sense'] == 'E')
    row = a['rows'][cardinal]
    assert row['rhs'] == 195 and row['terms'] == {i: F(1) for i in bits}
    records = {}
    children = Counter()
    for ri, r in enumerate(a['rows']):
        if ri == cardinal:
            continue
        assert r['sense'] == 'L' and r['rhs'] == 1
        negative = [i for i, c in r['terms'].items() if c == -1]
        positive = [i for i, c in r['terms'].items() if c == 1]
        assert len(negative) == 1 and len(positive) == 2 and len(r['terms']) == 3
        z = negative[0]
        assert z not in records and not a['vars'][z]['integer']
        assert a['vars'][z]['lower'] == 0 and a['vars'][z]['upper'] is None
        parent = [i for i in positive if i not in bits]
        xs = [i for i in positive if i in bits]
        assert len(parent) <= 1
        if parent:
            children[parent[0]] += 1
        records[z] = {'variable': z, 'row': ri, 'parent': parent[0] if parent else None, 'bits': xs}
    assert set(records) | set(bits) == set(range(len(a['vars'])))
    assert all(n == 1 for n in children.values())
    pending = set(records)
    ordered = []
    while pending:
        ready = sorted(z for z in pending if records[z]['parent'] is None or records[z]['parent'] not in pending)
        assert ready
        for z in ready:
            d = records[z]
            d['prefix'] = (records[d['parent']]['prefix'] if d['parent'] is not None else []) + d['bits']
            d['depth'] = len(d['prefix'])
            assert len(set(d['prefix'])) == d['depth']
            ordered.append(z)
        pending -= set(ready)
    terminals = set(records) - set(children)
    assert len(terminals) == 200
    retained = {i: b['var_index'][v['name']] for i, v in enumerate(a['vars']) if v['name'] in b['var_index']}
    assert set(retained) == set(range(len(a['vars']))) - terminals
    for i, j in retained.items():
        assert a['vars'][i] == b['vars'][j]
    for i, v in enumerate(a['vars']):
        assert a['objective'][1][i] == (4850 if i in terminals else 1)
    assert a['objective'][0] == b['objective'][0] == 0
    assert b['objective'][1] == {j: F(1) for j in retained.values()}
    for ar in a['rows']:
        br = b['rows'][b['row_index'][ar['name']]]
        assert br == {**ar, 'terms': {retained[i]: c for i, c in ar['terms'].items() if i in retained}}
    values = [F(0)] * len(a['vars'])
    zeros = set(h['certificate']['zero_binary_variables'])
    assert len(zeros) == 5
    for i in bits:
        values[i] = F(a['vars'][i]['name'] not in zeros)
    for z in ordered:
        d = records[z]
        values[z] = max(F(0), sum(values[i] for i in d['bits']) +
                        (values[d['parent']] if d['parent'] is not None else F(0)) - 1)
    assert all(values[z] == 0 for z in terminals)
    assert sum(values[i] * c for i, c in a['objective'][1].items()) == 6425
    return {'bits': bits, 'cardinal': cardinal, 'records': records, 'ordered': ordered,
            'terminals': terminals, 'retained': retained, 'point': values}


def lower_base(p, a, s):
    """Actual chain inequalities and a continuous top-five box bound."""
    lower = {}
    layers = defaultdict(list)
    bounds = []
    bits = s['bits']
    card = {'RowEq': s['cardinal']}
    for z in s['ordered']:
        d = s['records'][z]
        if d['depth'] > 27:
            continue
        refs = [[{'RowUpper': d['row']}, F(1)]]
        if d['parent'] is not None:
            refs.append([lower[d['parent']], F(1)])
        f = expression(1 - d['depth'], {i: F(1) for i in d['prefix']})
        lower[z] = p.lin('Le', refs, plus(f, var(z), -1))
        layers[d['depth']].append(z)
    for depth, zs in sorted(layers.items()):
        assert len(zs) == 200
        freq = Counter(i for z in zs for i in s['records'][z]['prefix'])
        weights = sorted(freq.values(), reverse=True)
        top = sum(weights[:5])
        q = F(weights[4])
        lb = 200 - top
        assert lb > 0
        refs = [[card, -q]]
        refs += [[{'VarLower': i}, F(freq[i]) - q] for i in bits if freq[i] > q]
        refs += [[{'VarUpper': i}, q - F(freq[i])] for i in bits if freq[i] < q]
        weighted = p.lin('Le', refs, expression(sum(freq.values()) - top, {i: -F(w) for i, w in freq.items()}))
        bound = p.lin('Le', [[weighted, F(1)]] + [[lower[z], F(1)] for z in zs],
                      expression(lb, {z: F(-1) for z in zs}))
        bounds.append((lb, zs, bound))
    assert sum(x[0] for x in bounds) == 2238
    used = {z for _, zs, _ in bounds for z in zs}
    refs = [[row, F(1)] for _, _, row in bounds] + [[card, F(-1)]]
    refs += [[{'VarLower': z}, F(1)] for z in s['records']
             if z not in s['terminals'] and z not in used]
    expected = plus(expression(2433), expression(0, {i: F(1) for i in range(len(a['vars']))
                                                     if i not in s['terminals']}), -1)
    return p.lin('Le', refs, expected)


def sign_value(p, item, layout, value, guard):
    """In u=0 return EQ p=0; in u=1 return EQ p-flow=0."""
    f = layout['positive']
    rr = (layout['flow_row'], layout['activation_row'],
          layout['positive_capacity_row'], layout['negative_capacity_row'])
    C = item['capacity']
    if value == 0:
        upper = p.lin('Le', [[{'RowUpper': rr[2]}, F(1)], [guard, C]], var(f))
        return p.eqpair(upper, {'VarLower': f})
    wanted = plus(var(f), item['flow'], -1)
    upper = p.lin('Le', [[{'RowEq': rr[0]}, F(1)], [{'RowUpper': rr[3]}, F(1)],
                         [{'RowEq': rr[1]}, C], [guard, C]], wanted)
    lower = p.lin('Le', [[{'RowEq': rr[0]}, F(-1)], [{'VarLower': f + 1}, F(1)]],
                  mul(wanted, -1))
    return p.eqpair(upper, lower)


def sign_cases(p, item, layout, kind, wanted, left, right):
    def low(c, g):
        return {'Witness': left(c, sign_value(c, item, layout, 0, g))}

    def high(c, g):
        return {'Witness': right(c, sign_value(c, item, layout, 1, g))}

    return p.cases(kind, wanted, var(layout['positive_activation']),
                   {'VarInt': layout['positive_activation']}, low, high)


def emit(p, output, mapping, rowproof, domainproof, objective=None):
    checks = finish_checks(p, output, mapping,
                           lambda i, typ: domainproof.get((i, typ)),
                           lambda i: rowproof.get(i), objective)
    p.finish(mapping, checks)
    return checks


def canonical_root(f, a, b, s):
    """Native forward MI direction: one stage chain of SignedLift scopes."""
    p = f
    base = lower_base(p, a, s)
    mapping = {i: var(i) for i in s['bits']}
    dom = {}
    integer = {}
    upper = {}
    layouts = {}
    layout_items = {}
    rowproof = {s['cardinal']: {'RowEq': s['cardinal']}}
    stages = defaultdict(list)
    for z in s['ordered']:
        stages[(s['records'][z]['depth'] - 2) // 10].append(z)
    anchor_set = {s['records'][z]['parent'] for z in s['ordered']
                  if (s['records'][z]['depth'] - 2) % 10 == 0 and s['records'][z]['parent'] is not None}
    need_integer = anchor_set | s['terminals']
    for stage, zs in sorted(stages.items()):
        items = []
        for z in zs:
            d = s['records'][z]
            chain = [z]
            cur = d['parent']
            while cur is not None and (s['records'][cur]['depth'] - 2) // 10 == stage:
                chain.append(cur)
                cur = s['records'][cur]['parent']
            anchor = cur
            xs = [i for old in reversed(chain) for i in s['records'][old]['bits']]
            count = len(xs) + (1 if anchor is not None else 0)
            flow = expression(1 - count, {i: F(1) for i in xs})
            if anchor is not None:
                flow = plus(flow, mapping[anchor])
            C = F(count - 1)
            assert C >= 1
            hi = p.lin('Le', [[{'VarUpper': i}, F(1)] for i in xs] +
                       ([[upper[anchor], F(1)]] if anchor is not None else []),
                       plus(flow, expression(-1)))
            hcap = p.lin('Le', [[hi, F(1)]], plus(flow, expression(-C)), constant=1 - C)
            lcap = p.lin('Le', [[{'VarLower': i}, F(1)] for i in xs] +
                         ([[{'VarLower': layouts[anchor]['positive']}, F(1)]] if anchor is not None else []),
                         plus(mul(flow, -1), expression(-C)))
            oldbound = p.lin('Le', [[{'RowUpper': s['records'][old]['row']}, F(1)] for old in chain] +
                             ([[dom[anchor], F(1)]] if anchor is not None else []),
                             plus(flow, var(z), -1))
            it = None
            if z in need_integer:
                it = p.lin('Int', [[{'VarInt': i}, F(1)] for i in xs] +
                           ([[integer[anchor], F(1)]] if anchor is not None else []),
                           flow, constant=1 - count)
            items.append({'old': z, 'capacity': C, 'flow': flow, 'hcap': hcap,
                          'lcap': lcap, 'oldbound': oldbound, 'flow_upper': hi,
                          'flow_integer': it, 'anchor': anchor})
        entries = [{'capacity': item['capacity'], 'flow': item['flow'],
                    'activation': expression(1),
                    'checks': ['Exact', 'Exact', 'Exact', item['hcap'], item['lcap']]}
                   for item in items]
        p = p.signed(entries)
        layout = p.old_layout
        assert len(layout) == len(items)
        for item, d in zip(items, layout):
            z = item['old']
            layouts[z] = d
            layout_items[z] = item
            mapping[z] = var(d['positive'])
            wanted = plus(mapping[z], var(z), -1)
            dom[z] = sign_cases(
                p, item, d, 'Le', wanted,
                lambda c, e, z=z: c.lin('Le', [[e, F(1)], [{'VarLower': z}, F(1)]], wanted),
                lambda c, e, item=item: c.lin('Le', [[e, F(1)], [item['oldbound'], F(1)]], wanted))
            if z in need_integer:
                integer[z] = sign_cases(
                    p, item, d, 'Int', mapping[z],
                    lambda c, e: c.lin('Int', [[e, F(1)]], mapping[z]),
                    lambda c, e, item=item: c.lin('Int', [[e, F(1)], [item['flow_integer'], F(1)]], mapping[z]))
            if z in anchor_set:
                want = plus(mapping[z], expression(-1))
                upper[z] = sign_cases(
                    p, item, d, 'Le', want,
                    lambda c, e, want=want: c.lin('Le', [[e, F(1)]], want, constant=-1),
                    lambda c, e, item=item: c.lin('Le', [[e, F(1)], [item['flow_upper'], F(1)]], want))
            orig = s['records'][z]
            parent = orig['parent']
            wanted = plus(substitute(expression(0, {i: F(1) for i in orig['bits'] +
                                                   ([parent] if parent is not None else [])}), mapping),
                          plus(mapping[z], expression(1)), -1)
            cur_lower = p.lin('Le', [[{'RowEq': d['flow_row']}, F(-1)],
                                     [{'VarLower': d['negative']}, F(1)]],
                              plus(item['flow'], mapping[z], -1))
            if parent is None or parent == item['anchor']:
                rowproof[orig['row']] = cur_lower
                assert p.refexpr(cur_lower) == wanted
            else:
                previous = layouts[parent]
                previous_item = layout_items[parent]
                bit = orig['bits'][0]
                rowproof[orig['row']] = sign_cases(
                    p, previous_item, previous, 'Le', wanted,
                    lambda c, e, wanted=wanted, bit=bit, d=d: c.lin(
                        'Le', [[e, F(1)], [{'VarUpper': bit}, F(1)],
                               [{'VarLower': d['positive']}, F(1)]], wanted),
                    lambda c, e, wanted=wanted, cur_lower=cur_lower: c.lin(
                        'Le', [[e, F(1)], [cur_lower, F(1)]], wanted))
        print('canonical stage', stage, 'items', len(zs), 'facts', p.counter[0], flush=True)

    terminal_sum = sumexpr(mapping[z] for z in s['terminals'])
    terminal_integer = p.lin('Int', [[integer[z], F(1)] for z in s['terminals']], terminal_sum)

    branch_obligations = []

    def inactive(child, assumption):
        q = p._child(child, legacy_from_native(child.model))
        mp = [mapping[a['var_index'][v['name']]] for v in b['vars']]
        rows = {}
        for ri, row in enumerate(b['rows']):
            ar = a['row_index'][row['name']]
            oldrow = a['rows'][ar]
            deleted = [z for z in oldrow['terms'] if z in s['terminals']]
            if deleted:
                z = deleted[0]
                others = [{'VarLower': layouts[t]['positive']}
                          for t in s['terminals'] if t != z]
                zero = q.lin('Le', [[assumption, F(1)]] +
                             [[ref, F(1)] for ref in others], mapping[z])
                rows[ri] = q.lin('Le', [[rowproof[ar], F(1)], [zero, F(1)]],
                                 substitute(row_fact(row, 'RowUpper'), mp))
            else:
                rows[ri] = rowproof[ar]
        obj = q.lin('Le', [[dom[z], F(1)] for z in s['records']
                           if z not in s['terminals']] +
                    [[{'VarLower': z}, F(4850)] for z in s['terminals']],
                    plus(substitute(b['objective'], mp), a['objective'], -1))
        branch_obligations.append(len(emit(q, b, mp, rows, {}, obj)))

    def active(child, assumption):
        q = p._child(child, legacy_from_native(child.model))
        lower = q.lin('Le', [[base, F(1)], [assumption, F(4850)]] +
                      [[dom[z], F(4850)] for z in s['terminals']],
                      plus(expression(7283), a['objective'], -1))
        mp = [expression(s['point'][a['var_index'][v['name']]]) for v in b['vars']]
        obj = q.lin('Le', [[lower, F(1)]], plus(expression(6425), a['objective'], -1),
                    constant=-858)
        branch_obligations.append(len(emit(q, b, mp, {}, {}, obj)))

    p.scope.split(native_expr(terminal_sum), left=inactive, right=active,
                  integer=p.ref(terminal_integer))
    return {'stages': len(stages), 'signed_variables': len(layouts),
            'mapping_decisions': len(mapping), 'terminal_coordinates': len(s['terminals']),
            'branch_obligations': branch_obligations}


def prepare(a, b, h):
    s = inspect(a, b, h)
    proof, f, r = make_proof(a, b)
    forward = canonical_root(f, a, b, s)
    # Complete the reverse direction on the same proof object.
    mp = [var(s['retained'][i]) if i in s['retained'] else expression()
          for i in range(len(a['vars']))]
    rows = {i: row_ref(b, row['name']) for i, row in enumerate(a['rows'])}
    reverse_checks = emit(r, a, mp, rows, {})
    return proof, {
        'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
        'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
        'terminal_coordinates': len(s['terminals']), 'directions': 2,
        'forward': forward,
        'obligations_by_direction': [forward['branch_obligations'], len(reverse_checks)],
        'strict_improvement_route': 'OUT_OF_NATIVE_MI_OPT_CONTRACT',
        'input_halfspace_projection_route': 'OUT_OF_NATIVE_MI_OPT_CONTRACT',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test36-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test36'))
    parser.add_argument('--phase',
                        choices=['inspect', 'full', 'forward', 'reverse',
                                 'improvement', 'projection'],
                        default='full')
    args = parser.parse_args()
    if args.phase in ('improvement', 'projection'):
        receipt = {
            'case_id': 'test36', 'status': 'BLOCKED', 'phase': args.phase,
            'blocker': 'NO_NATIVE_ALL_SOURCE_OPTIMIZER_EXCLUSION_CLAIM',
            'reason': ('The native Proof API has only two MI-OPT directions. '
                       'Strict-improvement and caller input-halfspace projection '
                       'obligations have no native claim form and are not fabricated.'),
            'native_port': 'prepare_test36_full.py --phase inspect',
        }
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f'blocker-{args.phase}.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
        return
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    a, b = parse_mps(source), parse_mps(target)
    h = json.loads(audit.read_text())
    if args.phase == 'inspect':
        s = inspect(a, b, h)
        print(json.dumps({'case_id': 'test36', 'status': 'INSPECTED',
                          'records': len(s['records']),
                          'terminals': len(s['terminals']),
                          'max_depth': max(d['depth'] for d in s['records'].values())},
                         indent=2))
        return
    proof, counts = prepare(a, b, h)
    record = compile_case(proof, args.out, case_id='test36', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test36', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
