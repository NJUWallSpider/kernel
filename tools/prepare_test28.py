#!/usr/bin/env python3
"""Native complete common-source flow aggregation/lifting proof for test28.

The forward map is affine.  The reverse map is one joint existential FlowLift
extension followed by the kernel-derived complete-model obligations.  The
external audit supplies only structural indices, never trusted conclusions.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse
import json
import time

from audit_test28 import inspect
from prepare_affine import parse_mps
from prepare_test40 import expression, plus, row_fact, sha, substitute
from prepare_native import compile_case, make_proof


def obligations(builder, output, mapping, claim, domain_terms, row_terms, objective_terms):
    """Kernel-order Return witnesses: domains, rows, nonincreasing objective."""
    result = []
    def prove(kind, wanted, terms):
        if not wanted[1] and ((kind == 'Eq' and wanted[0] == 0) or
                              (kind == 'Le' and wanted[0] <= 0) or
                              (kind == 'Int' and wanted[0].denominator == 1)):
            return 'Exact'
        if (len(terms) == 1 and terms[0][1] == 1 and builder.kind(terms[0][0]) == kind
                and builder.refexpr(terms[0][0]) == wanted):
            return terms[0][0]
        return builder.lin(kind, terms, wanted)
    for i, v in enumerate(output['vars']):
        if v['lower'] is not None:
            result.append(prove('Le', plus(expression(v['lower']), mapping[i], -1),
                                domain_terms(i, 'VarLower')))
        if v['upper'] is not None:
            result.append(prove('Le', plus(mapping[i], expression(-v['upper'])),
                                domain_terms(i, 'VarUpper')))
        if claim['output_integers'] and v['integer']:
            result.append(prove('Int', mapping[i], domain_terms(i, 'VarInt')))
    for i, row in enumerate(output['rows']):
        typ = {'E': 'RowEq', 'L': 'RowUpper', 'G': 'RowLower'}[row['sense']]
        result.append(prove('Eq' if typ == 'RowEq' else 'Le',
                            substitute(row_fact(row, typ), mapping), row_terms(i)))
    result.append(prove('Eq', plus(substitute(output['objective'], mapping),
                                  builder.model['objective'], -1), objective_terms))
    return result


def prepare(a, b, h):
    w = inspect(a, b, h)
    claims = [{'reverse': False, 'input_integers': True, 'output_integers': True,
               'objective': 'Equal', 'projection': w['retained'], 'inverse': None},
              {'reverse': True, 'input_integers': True, 'output_integers': True,
               'objective': 'Equal', 'projection': [[j, i] for i, j in w['retained']],
               'inverse': None}]
    proof, f, r = make_proof(a, b)

    fmap = [None] * len(b['vars'])
    fdomains = {}
    frows = {}
    for i, j in w['retained']:
        fmap[j] = expression(0, {i: 1})
        fdomains[j] = [i]
    for arc in w['arcs']:
        frows[arc['target_capacity']] = [[{'RowUpper': arc['source_capacity']}, F(1)]]
    for g in w['groups']:
        for ei, j in enumerate(g['grouped_flows']):
            ids = [c['flows'][ei] for c in g['components']]
            fmap[j] = expression(0, {i: 1 for i in ids})
            fdomains[j] = ids
        for node, row in enumerate(g['balance_rows']):
            if row is not None:
                frows[row] = [[{'RowEq': c['balance_rows'][node]}, F(1)]
                              for c in g['components']]
    assert all(e is not None for e in fmap) and len(frows) == len(b['rows'])
    fchecks = obligations(f, b, fmap, claims[0],
                          lambda i, t: [[{t: j}, F(1)] for j in fdomains[i]],
                          lambda i: frows[i], [])
    f.finish(fmap, fchecks)

    flowgroups = []
    input_balances = []
    for g in w['groups']:
        conservations = []
        signed = []
        for node, row in enumerate(g['balance_rows']):
            wanted = expression(-sum(F(c['demand']) * (int(g['source'] == node) - int(c['sink'] == node))
                                     for c in g['components']))
            for ei, arc in enumerate(w['arcs']):
                wanted = plus(wanted, expression(0, {g['grouped_flows'][ei]: 1}),
                              int(arc['tail'] == node) - int(arc['head'] == node))
            terms = ([[{'RowEq': row}, F(-1)]] if row is not None else
                     [[{'RowEq': ri}, F(1)] for ri in g['balance_rows'] if ri is not None])
            ref = r.ref(r.lin('Eq', terms, wanted))
            conservations.append(ref)
            signed.append([[ref, F(-1)]])
        input_balances.append(signed)
        flowgroups.append({'source': g['source'],
                           'commodities': [[c['sink'], c['demand']] for c in g['components']],
                           'flows': [expression(0, {i: 1}) for i in g['grouped_flows']],
                           'nonnegative': [r.ref({'VarLower': i}) for i in g['grouped_flows']],
                           'balances': conservations})

    witness = {'nodes': w['nodes'],
               'arcs': [[arc['tail'], arc['head']] for arc in w['arcs']],
               'groups': flowgroups}
    child = r.flow(witness)
    layout = child.old_layout

    rmap = [None] * len(a['vars'])
    rdomains = {}
    rrows = {}
    objective_terms = []
    for i, j in w['retained']:
        rmap[i] = expression(0, {j: 1})
        rdomains[i] = [j]
    for gi, g in enumerate(w['groups']):
        for ki, c in enumerate(g['components']):
            entry = layout[gi]['commodities'][ki]
            for ei, i in enumerate(c['flows']):
                j = entry['flows'][ei]
                rmap[i] = expression(0, {j: 1})
                rdomains[i] = [j]
            for node, i in enumerate(c['balance_rows']):
                rrows[i] = [[{'RowEq': entry['balance_rows'][node]}, F(-1)]]
    for ei, arc in enumerate(w['arcs']):
        rmap[arc['aggregate']] = expression(0, {g['grouped_flows'][ei]: 1
                                                for g in w['groups']})
        rdomains[arc['aggregate']] = [g['grouped_flows'][ei] for g in w['groups']]
        totals = [[{'RowEq': group['recovery_rows'][ei]}, F(1)] for group in layout]
        rrows[arc['link']] = totals
        rrows[arc['source_capacity']] = [[{'RowUpper': arc['target_capacity']}, F(1)]] + totals
        rrows[arc['aggregate_capacity']] = [[{'RowUpper': arc['target_capacity']}, F(1)]]
        objective_terms += [[ref, F(arc['common_flow_cost']) * coefficient]
                            for ref, coefficient in totals
                            if F(arc['common_flow_cost']) * coefficient]
    for node, i in enumerate(w['aggregate_balance_rows']):
        rrows[i] = [term for g in input_balances for term in g[node]]
    assert all(e is not None for e in rmap) and len(rrows) == len(a['rows'])
    rchecks = obligations(child, a, rmap, claims[1],
                          lambda i, t: [[{t: j}, F(1)] for j in rdomains[i]],
                          lambda i: rrows[i], objective_terms)
    child.finish(rmap, rchecks)

    counts = {'source_variables': len(a['vars']), 'target_variables': len(b['vars']),
              'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
              'claims': 2, 'extension_variables': len(child.scope.generated_variables),
              'extension_rows': len(child.scope.generated_rows),
              'obligations_by_claim': [len(fchecks), len(rchecks)],
              'linear_steps_forward': len(f.steps),
              'linear_steps_reverse_prelude': len(r.steps),
              'linear_steps_reverse_body': len(child.scope.steps)}
    return proof, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path,
                        default=Path('/Users/bhz/Code/reform_test/runs/test28-nomf-B1'))
    parser.add_argument('--out', type=Path, default=Path('cases/test28'))
    args = parser.parse_args()
    started = time.perf_counter()
    run = args.run.resolve()
    source = run / 'input/model.mps'
    target = run / 'output/reformulated.mps'
    audit = run / 'output/audit.json'
    proof, counts = prepare(parse_mps(source), parse_mps(target),
                            json.loads(audit.read_text()))
    record = compile_case(proof, args.out, case_id='test28', source=source, target=target,
                          metadata={'audit': {'path': str(audit), 'sha256': sha(audit)},
                                    'counts': counts,
                                    'preparation_seconds': time.perf_counter() - started})
    (args.out / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'case_id': 'test28', 'status': record['status'],
                      'guarantee': record['verification'].get('guarantee'),
                      'obligations': record['verification']['statistics']['obligations'],
                      'counts': counts,
                      'preparation_seconds': record['preparation_seconds']}, indent=2))


if __name__ == '__main__':
    main()
