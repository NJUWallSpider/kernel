#!/usr/bin/env python3
"""Native test73 conflict-clique Cases proofs and complete reverse recovery."""
from fractions import Fraction as F
from prepare_affine import row_ref
from prepare_test29 import execute
from prepare_test40 import expression, row_fact, substitute
from prepare_native import make_proof


def split(builder, wanted, var, left, right, kind='Le'):
    return builder.cases(kind, wanted, expression(0, {var: 1}),
                         integer={'VarInt': var}, left=left, right=right)


def pop_mutation(values, index=-1):
    value = values.pop(index)
    return lambda: values.insert(index if index >= 0 else len(values), value)


def prepare(a, b, h):
    assert a['vars'] == b['vars'] and a['objective'] == b['objective']
    n = len(a['vars'])
    mapping = [expression(0, {i: 1}) for i in range(n)]
    deleted = {d['name']: d for d in h['removed_conflict_rows']}
    redundant = {d['name']: d for d in h['removed_bound_redundant_rows']}
    added = {d['name']: d for d in h['added_clique_rows']}
    assert set(a['row_index']) - set(b['row_index']) == set(deleted) | set(redundant)
    assert set(b['row_index']) - set(a['row_index']) == set(added)
    edges = {frozenset(a['rows'][a['row_index'][rn]]['terms']): row_ref(a, rn)
             for rn in deleted}
    assert len(edges) == 4802
    proof, f, r = make_proof(a, b)
    cliques = {}

    def clique(p, vertices):
        wanted = expression(-1, {i: 1 for i in vertices})
        if len(vertices) == 2:
            ref = edges[frozenset(vertices)]
            assert p.refexpr(ref) == wanted
            return ref
        x, *rest = vertices

        def left(c, zero, rest=rest, wanted=wanted):
            return {'Witness': c.lin('Le', [[clique(c, rest), 1], [zero, 1]], wanted)}

        def right(c, one, x=x, rest=rest, wanted=wanted):
            return {'Witness': c.lin('Le', [[edges[frozenset((x, y))], 1] for y in rest] +
                                     [[one, len(rest) - 1]], wanted)}

        return split(p, wanted, x, left, right)

    for rn in added:
        row = b['rows'][b['row_index'][rn]]
        vertices = sorted(row['terms'])
        assert 2 <= len(vertices) <= 8
        assert row_fact(row, 'RowUpper') == expression(-1, {i: 1 for i in vertices})
        for i in vertices:
            assert a['vars'][i]['integer']
            assert a['vars'][i]['lower'] == 0 and a['vars'][i]['upper'] == 1
        cliques[rn] = clique(f, vertices)
    columns = {'source_variables': n, 'target_variables': n,
               'source_rows': len(a['rows']), 'target_rows': len(b['rows']),
               'cliques': len(added), 'restored_edges': len(deleted),
               'bound_redundant_rows': len(redundant), 'directions': 2,
               'obligations_by_direction': {}}
    for back in (False, True):
        inp, out = (b, a) if back else (a, b)
        builder = r if back else f
        checks = []
        for i, v in enumerate(out['vars']):
            if v['lower'] is not None:
                checks.append({'VarLower': i})
            if v['upper'] is not None:
                checks.append({'VarUpper': i})
            if v['integer']:
                assert inp['vars'][i]['integer']
                checks.append({'VarInt': i})
        for row in out['rows']:
            rn = row['name']
            typ = next(iter(row_ref(out, rn)))
            wanted = row_fact(row, typ)
            if not back and rn in added:
                check = cliques[rn]
            elif back and rn in deleted:
                covering = deleted[rn]['covering_added_row']
                support = set(b['rows'][b['row_index'][covering]]['terms'])
                assert set(row['terms']) <= support
                check = builder.lin('Le', [[row_ref(b, covering), 1]] +
                                    [[{'VarLower': i}, 1]
                                     for i in sorted(support - set(row['terms']))], wanted)
            elif back and rn in redundant:
                terms = [[{'VarUpper' if c > 0 else 'VarLower': i}, abs(c)]
                         for i, c in row['terms'].items()]
                maximum = sum(c * inp['vars'][i]['upper' if c > 0 else 'lower']
                              for i, c in row['terms'].items())
                check = builder.lin('Le', terms, wanted, constant=maximum - row['rhs'])
            else:
                assert row == inp['rows'][inp['row_index'][rn]]
                check = row_ref(inp, rn)
            assert builder.refexpr(check) == wanted
            checks.append(check)
        assert substitute(out['objective'], mapping) == inp['objective']
        checks.append('Exact')
        builder.finish(mapping, checks)
        columns['obligations_by_direction']['forward' if not back else 'reverse'] = len(checks)
    return proof, columns


def main():
    execute(73, prepare, __file__)


if __name__ == '__main__':
    main()
