from rule_checks import assert_rules_checked
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable


class DeriveSubstitutionTests(unittest.TestCase):
    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            report = proof.verify(directory)
            assert_rules_checked(self, report)
            self.assertTrue((Path(directory) / 'proof.rpa').is_file())

    def test_le_eq_and_int_goals_restore_from_explicit_residual_facts(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model('restore', [Variable('x', False, 0, 10), Variable('y', True, 0, 1)],
                       [Row('definition', x-2*y, lower=0, upper=0)])
        target = source.with_bounds('x', upper=2).with_integrality(['x'], True).add_row('scaled', 3*x-6*y, equal=0)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map('identity'), proof.reverse.map('identity'))
        pivots = {'x': forward.row('definition')}
        upper = forward.le([(forward.upper('y'), 2)], expect=2*y-2)
        restored = forward.derive_substitution(x-2, pivots, upper)
        self.assertEqual((restored.kind, restored.expression), ('Le', x-2))
        zero = forward.eq()
        restored = forward.derive_substitution(3*x-6*y, pivots, zero)
        self.assertEqual((restored.kind, restored.expression), ('Eq', 3*x-6*y))
        integer = forward.int([(forward.integer('y'), 2)], expect=2*y)
        restored = forward.derive_substitution(x, pivots, integer)
        self.assertEqual((restored.kind, restored.expression), ('Int', x))
        # Equality premises also legally establish the same expression's
        # nonpositivity or integrality under ordinary Lin rules.
        self.assertEqual(forward.derive_substitution(3*x-6*y, pivots, zero, kind='Le').kind, 'Le')
        self.assertEqual(forward.derive_substitution(3*x-6*y, pivots, zero, kind='Int').kind, 'Int')
        forward.complete()
        reverse.le([(reverse.upper('x'), 1)], constant=-8)
        reverse.complete()
        self.verify(proof)

    def test_ordered_introductions_earlier_residuals_and_alias_positions_verify(self):
        x, y, z = (Expr.var(i) for i in range(3))
        cases = [
            ([('x', x-y), ('y', y-z)], z),
            ([('y', y-z), ('x', x-y)], y),
            ([('x', x-y), ('y', y-2*x-1)], 2*x+1),
            ([('x', x-y), ('y', y-2*x-1), (0, x-z)], 2*z+1),
        ]
        for definitions, residual in cases:
            with self.subTest(definitions=definitions):
                source = Model('order', [Variable(n, lower=None) for n in ('x', 'y', 'z')],
                               [*(Row(f'd{i}', expression, lower=0, upper=0)
                                  for i, (_, expression) in enumerate(definitions)), Row('given', residual, upper=0)])
                target = source.add_row('goal', x, upper=0)
                proof = Proof(source, target)
                forward, reverse = (proof.forward.map('identity'), proof.reverse.map('identity'))
                pivots = {pivot: forward.row(f'd{i}') for i, (pivot, _) in enumerate(definitions)}
                result = forward.derive_substitution(x, pivots, forward.row('given'))
                self.assertEqual(result.expression, x)
                forward.complete(); reverse.complete()
                self.verify(proof)

    def test_bad_residuals_scope_drop_and_kind_rules_precede_emission(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model('reject', [Variable('x', lower=None), Variable('y', True, lower=None)],
                       [Row('definition', x-y, lower=0, upper=0), Row('given', y, upper=0)])
        builder = Builder(source)
        definition = builder.row('definition')
        residual = builder.row('given')
        for kind in ('Eq', 'Int', 'Unknown'):
            with self.subTest(kind=kind), self.assertRaises(BuildError):
                builder.derive_substitution(x, {'x': definition}, residual, kind=kind)
            self.assertEqual(builder.steps, [])
        with self.assertRaisesRegex(BuildError, 'residual mismatch'):
            builder.derive_substitution(x+1, {'x': definition}, residual)
        self.assertEqual(builder.steps, [])
        unrelated = Builder(source)
        with self.assertRaises(BuildError):
            builder.derive_substitution(x, {'x': definition}, unrelated.row('given'))
        with self.assertRaises(BuildError):
            builder.derive_substitution(x, {'x': unrelated.row('definition')}, residual)
        self.assertEqual(builder.steps, [])
        integer = builder.integer('y')
        with self.assertRaises(BuildError):
            builder.derive_substitution(x, {'x': definition}, integer, kind='Le')
        self.assertEqual(builder.steps, [])
        dropped = builder.le([(residual, 1)])
        builder.drop(dropped)
        before = len(builder.steps)
        with self.assertRaises(BuildError):
            builder.derive_substitution(x, {'x': definition}, dropped)
        self.assertEqual(len(builder.steps), before)
        dropped_eq = builder.eq([(definition, 1)])
        builder.drop(dropped_eq)
        before = len(builder.steps)
        with self.assertRaises(BuildError):
            builder.derive_substitution(x, {'x': dropped_eq}, residual)
        self.assertEqual(len(builder.steps), before)

    def test_batch_defaults_to_each_residual_kind_and_explicit_kind_is_uniform(self):
        x, y = Expr.var(0), Expr.var(1)
        source = Model('mixed', [Variable('x', lower=None), Variable('y', lower=None)],
                       [Row('definition', x-y, lower=0, upper=0), Row('zero', y, lower=0, upper=0),
                        Row('cap', y, upper=1)])
        target = source.add_row('fixed', x, equal=0).add_row('upper', x, upper=1)
        proof = Proof(source, target)
        forward, reverse = (proof.forward.map('identity'), proof.reverse.map('identity'))
        items = [(x, forward.row('zero')), (x-1, forward.row('cap'))]
        result = forward.derive_substitution_many(items, {'x': forward.row('definition')})
        self.assertEqual([fact.kind for fact in result], ['Eq', 'Le'])
        weakened = forward.derive_substitution_many(items, {'x': forward.row('definition')}, kind='Le')
        self.assertEqual([fact.kind for fact in weakened], ['Le', 'Le'])
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_large_batch_reuses_validation_without_whole_expression_operations(self):
        count = 1200
        goal = Expr(7, {i: i+1 for i in range(count)})
        reduced = Expr(7, {count+i: i+1 for i in range(count)})
        source = Model('large', [Variable(f'x{i}', lower=None) for i in range(2*count)],
                       [*(Row(f'd{i}', Expr(0, {i: 1, count+i: -1}), lower=0, upper=0)
                          for i in range(count)), Row('wide', reduced, upper=0), Row('single', Expr.var(count), upper=0)])
        builder = Builder(source)
        definitions = {i: builder.row(f'd{i}') for i in range(count)}
        items = [(goal, builder.row('wide')), *([(Expr.var(0), builder.row('single'))] * 80)]
        visible, initialize = builder._visible, Expr.__init__
        calls, constructions = Counter(), []
        def counted_visible(fact):
            calls[id(fact)] += 1
            return visible(fact)
        def counted_init(expr, *args, **kwargs):
            constructions.append(1)
            initialize(expr, *args, **kwargs)
        with patch.object(builder, '_visible', counted_visible), patch.object(Expr, '__init__', counted_init), \
             patch.object(Expr, '__add__', side_effect=AssertionError('whole Expr addition')), \
             patch.object(Expr, '__mul__', side_effect=AssertionError('whole Expr scaling')):
            results = builder.derive_substitution_many(items, definitions)
        self.assertEqual(results[0].expression, goal)
        self.assertTrue(all(result.expression == Expr.var(0) for result in results[1:]))
        self.assertEqual(len(constructions), 0)
        self.assertEqual(calls[id(definitions[1])], 0)
        self.assertEqual(calls[id(definitions[0])], 0)


if __name__ == '__main__':
    unittest.main()
