from rule_checks import assert_rules_checked
from collections import Counter
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable


class OrderedSubstitutionTests(unittest.TestCase):
    def test_sparse_rewrite_matches_one_explicit_ordered_pass(self):
        x, y, z = (Expr.var(i) for i in range(3))
        cases = [
            (x, [(0, x-y), (1, y-z)]),
            (x, [(1, y-z), (0, x-y)]),
            (x, [(0, x-y), (1, y-2*x-1)]),
            (y, [(0, x-z), (1, y-x)]),
            (x+y, [(0, x+y-z), (1, y-z)]),
            (x+y+3, [(0, -x*Fraction(2, 3)+y+1), (1, y-z/5)]),
        ]
        for expression, selected in cases:
            with self.subTest(expression=expression, selected=selected):
                model = Model('ordered', [Variable(n) for n in ('x', 'y', 'z')],
                              [*(Row(f'd{i}', eq, lower=0, upper=0) for i, (_, eq) in enumerate(selected)),
                               Row('goal', expression, upper=0)])
                builder = Builder(model)
                definitions = {pivot: builder.row(i) for i, (pivot, _) in enumerate(selected)}
                fact = builder.row('goal')
                residual, expected_terms = expression, [[fact.reference, '1']]
                for pivot, equality in definitions.items():
                    multiplier = -residual.terms.get(pivot, 0) / equality.expression.terms[pivot]
                    if multiplier:
                        residual += multiplier * equality.expression
                        expected_terms.append([equality.reference, str(multiplier)])
                rewritten = builder.rewrite(fact, definitions)
                self.assertEqual(rewritten.expression, residual)
                self.assertEqual(builder.steps[-1]['Lin']['terms'], expected_terms)

    def test_rewrite_preserves_duplicate_name_index_pivot_positions(self):
        x, y, z = (Expr.var(i) for i in range(3))
        model = Model('aliases', [Variable(n) for n in ('x', 'y', 'z')],
                      [Row('first', x-y, lower=0, upper=0),
                       Row('second', y-2*x-1, lower=0, upper=0),
                       Row('last', x-z, lower=0, upper=0), Row('goal', x, upper=0)])
        builder = Builder(model)
        result = builder.rewrite(builder.row('goal'), {
            'x': builder.row('first'), 'y': builder.row('second'), 0: builder.row('last')})
        self.assertEqual(result.expression, 2*z+1)
        self.assertEqual([term[1] for term in builder.steps[-1]['Lin']['terms']], ['1', '-1', '-1', '-2'])

    def test_claim_substitution_preserves_legacy_alias_canonicalization(self):
        x, y, z = (Expr.var(i) for i in range(3))
        model = Model('claim_aliases', [Variable(n) for n in ('x', 'y', 'z')],
                      [Row('first', x-y, lower=0, upper=0), Row('last', x-z, lower=0, upper=0),
                       Row('goal', x, upper=0)])
        claim = Proof(model, model).forward.map('identity')
        generated = claim.substitution({'x': claim.row('first'), 0: claim.row('last')})
        self.assertEqual(generated[-1].expression, z)

    def test_sparse_updates_keep_the_intermediate_rational_limit(self):
        x, y = Expr.var(0), Expr.var(1)
        largest = Fraction(1 << 65535)
        model = Model('magnitude', [Variable('x'), Variable('y')],
                      [Row('d', x-2*y, lower=0, upper=0), Row('goal', largest*x, upper=0)])
        builder = Builder(model)
        with self.assertRaisesRegex(ValueError, 'rational bit budget'):
            builder.rewrite(builder.row('goal'), {'x': builder.row('d')})
        self.assertEqual(builder.steps, [])

    def test_invalid_unused_definitions_and_expect_emit_no_steps(self):
        x, y = Expr.var(0), Expr.var(1)
        model = Model('invalid', [Variable('x'), Variable('y')],
                      [Row('d', y-x, lower=0, upper=0), Row('goal', x, upper=0)])
        builder = Builder(model)
        fact = builder.row('goal')
        with self.assertRaises(BuildError):
            builder.rewrite(fact, {'y': fact})
        self.assertEqual(builder.steps, [])
        with self.assertRaises(BuildError):
            builder.rewrite(fact, {}, expect=y)
        self.assertEqual(builder.steps, [])
        equality = builder.eq([(builder.row('d'), 1)])
        builder.drop(equality)
        before = len(builder.steps)
        with self.assertRaises(BuildError):
            builder.rewrite(fact, {'y': equality})
        self.assertEqual(len(builder.steps), before)

    def test_rewrite_many_validates_once_and_avoids_per_pivot_expr_copies(self):
        count = 1200
        definitions_expr = [Expr(0, {i: 1, count+i: -1}) for i in range(count)]
        wide = Expr(7, {i: i+1 for i in range(count)})
        model = Model('sparse', [Variable(f'x{i}') for i in range(2*count)],
                      [*(Row(f'd{i}', expr, lower=0, upper=0) for i, expr in enumerate(definitions_expr)),
                       Row('wide', wide, upper=0), Row('single', Expr.var(0), upper=0)])
        builder = Builder(model)
        definitions = {i: builder.row(i) for i in range(count)}
        facts = [builder.row('wide'), *([builder.row('single')] * 80)]
        calls, constructions = Counter(), []
        visible, initialize = builder._visible, Expr.__init__
        def counted_visible(fact):
            calls[id(fact)] += 1
            return visible(fact)
        def counted_init(expr, *args, **kwargs):
            constructions.append(1)
            initialize(expr, *args, **kwargs)
        with patch.object(builder, '_visible', counted_visible), patch.object(Expr, '__init__', counted_init), \
             patch.object(Expr, '__add__', side_effect=AssertionError('whole Expr addition')), \
             patch.object(Expr, '__mul__', side_effect=AssertionError('whole Expr scaling')):
            rewritten = builder.rewrite_many(facts, definitions)
        self.assertEqual(rewritten[0].expression, Expr(7, {count+i: i+1 for i in range(count)}))
        self.assertTrue(all(f.expression == Expr.var(count) for f in rewritten[1:]))
        self.assertEqual(len(constructions), 0)
        # Every definition is validated once; later visibility checks only
        # cover premises actually used in that fact's linear step.
        self.assertEqual(calls[id(definitions[1])], 0)
        self.assertEqual(calls[id(definitions[0])], 0)

    def test_substitution_is_available_in_generated_and_case_scopes(self):
        x = Expr.var(0)
        model = Model('scope', [Variable('x', integer=True, lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map('identity')
        scope = claim.intervals([{'lower': [x], 'upper': [x], 'checks': ['Exact']}])
        interval = scope.interval(0)
        z = interval.variable
        definition = scope.eqpair(interval.upper_rows[0], interval.lower_rows[0])
        pivot = next(iter(z.terms))
        goal = 2*(z-x)
        def branch(child, assumption):
            generated = child.substitution({pivot: definition}, goals=[goal])
            self.assertTrue(any(f.kind == 'Eq' and f.expression == goal for f in generated))
            return child.find('Eq', goal)
        scope.cases(x, kind='Eq', expect=goal, left=branch, right=branch)
        claim.complete(scope=scope, mapping='identity')
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))
            self.assertTrue((Path(directory) / 'proof.rpa').is_file())

    def test_wide_objective_and_row_substitution_verify_in_both_directions(self):
        count = 1200
        original = Expr(0, {i: i+1 for i in range(count)})
        rewritten = Expr(0, {count+i: i+1 for i in range(count)})
        model = Model('wide_proof', [Variable(f'x{i}', lower=None) for i in range(2*count)],
                      [*(Row(f'd{i}', Expr(0, {i: 1, count+i: -1}), lower=0, upper=0)
                         for i in range(count)), Row('wide', original, upper=0)], objective=original)
        target = model.replace_row('wide', expr=rewritten).with_objective(rewritten)
        proof = Proof(model, target)
        forward = proof.forward.map('identity')
        reverse = proof.reverse.map('identity')
        with patch.object(forward, 'plan', side_effect=AssertionError('full goal materialization')), \
             patch.object(reverse, 'plan', side_effect=AssertionError('full goal materialization')):
            forward.substitution({i: forward.row(f'd{i}') for i in range(count)})
            reverse.substitution({count+i: reverse.row(f'd{i}') for i in range(count)})
        forward.complete(); reverse.complete()
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))

    def test_unit_expression_variable_refs_in_a_generated_scope(self):
        x = Expr.var(0)
        model = Model('units', [Variable('x', integer=True, lower=0, upper=1)])
        proof = Proof(model, model)
        proof.reverse.map("identity").complete()
        claim = proof.forward.map('identity')
        scope = claim.menus([{'maximum_index': 1, 'activation': 1, 'index': x,
                             'checks': ['Exact', 'Exact', 'Exact', claim.lower(x), claim.upper(x), claim.integer(x)]}])
        option = scope.menu(0).options[1]
        self.assertEqual(scope.lower(option).expression, -option)
        self.assertEqual(scope.upper(option).expression, option-1)
        self.assertEqual(scope.integer(option).expression, option)
        scope.int([(scope.integer(option), 1)])
        for invalid in (Expr(0), x+1, 2*x, x+option):
            with self.assertRaises(ValueError):
                scope.lower(invalid)
        with self.assertRaises(IndexError):
            scope.upper(Expr.var(len(scope.model.vars)))
        with self.assertRaises(IndexError):
            claim.lower(option)
        with self.assertRaises(ValueError):
            scope.ref('RowEq', option)
        claim.complete(scope=scope, mapping='identity')
        with tempfile.TemporaryDirectory() as directory:
            assert_rules_checked(self, proof.verify(directory))


if __name__ == '__main__':
    unittest.main()
