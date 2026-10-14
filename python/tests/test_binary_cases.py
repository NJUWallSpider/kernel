import tempfile
import unittest

from kernel_compiler import Builder, BuildError, Expr, Model, Proof, Row, Variable


class BinaryCasesTests(unittest.TestCase):
    def verify(self, proof):
        with tempfile.TemporaryDirectory() as directory:
            report = proof.verify(directory)
            self.assertEqual(report['status'], 'VERIFIED', report)

    def test_explicit_product_leaves_prove_integrality_of_continuous_auxiliary(self):
        x, y, t = (Expr.var(i) for i in range(3))
        source = Model('product', [Variable('x', True, 0, 1), Variable('y', True, 0, 1),
                                   Variable('t', False, 0, 1)],
                       [Row('first', t-x, upper=0), Row('second', t-y, upper=0),
                        Row('both', x+y-t-1, upper=0)])
        target = source.with_integrality(['t'], True)
        proof = Proof(source, target)
        forward, reverse = proof.bijection('identity', 'identity')
        leaves, leaf_facts = [], []
        def prove(scope, fixes):
            values = {name: -fact.expression.constant for name, fact in fixes.items()}
            leaves.append(tuple(values[name] for name in ('x', 'y')))
            leaf_facts.append(fixes['x'])
            if not values['x'] or not values['y']:
                name = 'first' if not values['x'] else 'second'
                upper = scope.rewrite(scope.row(name), fixes, expect=t)
                equality = scope.eqpair(upper, scope.lower('t'))
                value = 0
            else:
                lower = scope.rewrite(scope.row('both'), fixes, expect=1-t)
                equality = scope.eqpair(scope.upper('t'), lower)
                value = 1
            return scope.int([(equality, 1)], constant=value, expect=t)
        derived = forward.binary_cases(['x', y], kind='Int', expect=t, prove=prove)
        self.assertEqual((derived.kind, derived.expression), ('Int', t))
        self.assertEqual(leaves, [(0, 0), (0, 1), (1, 0), (1, 1)])
        with self.assertRaises(BuildError):
            forward.le([(leaf_facts[0], 1)])
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_supplied_integer_fact_for_a_continuous_coordinate(self):
        x, b = Expr.var(0), Expr.var(1)
        source = Model('proved_integer', [Variable('x', False, 0, 1), Variable('b', True, 0, 1)],
                       [Row('definition', x-b, lower=0, upper=0)])
        target = source.with_integrality(['x'], True)
        proof = Proof(source, target)
        forward, reverse = proof.bijection('identity', 'identity')
        integer = forward.int([(forward.row('definition'), 1), (forward.integer('b'), 1)], expect=x)
        leaves = []
        def prove(scope, fixes):
            value = -fixes['x'].expression.constant
            leaves.append(value)
            return scope.int([(fixes['x'], 1)], constant=value, expect=x)
        forward.binary_cases([x], kind='Int', expect=x, prove=prove, integers={'x': integer})
        self.assertEqual(leaves, [0, 1])
        forward.complete(); reverse.complete()
        self.verify(proof)

    def test_narrow_bounds_weaken_to_binary_equalities_without_pruning(self):
        x = Expr.var(0)
        for lower, upper, value in [('1/4', 1, 1), (0, '3/4', 0), (0, 0, 0), (1, 1, 1)]:
            with self.subTest(lower=lower, upper=upper):
                source = Model('narrow', [Variable('x', True, lower, upper)])
                goal = x-value
                target = source.add_row('fixed', goal, equal=0)
                proof = Proof(source, target)
                forward, reverse = proof.bijection('identity', 'identity')
                leaves = []
                def prove(scope, fixes):
                    bit = -fixes['x'].expression.constant
                    leaves.append(bit)
                    if bit == value:
                        return fixes['x']
                    bound = scope.lower('x') if bit == 0 else scope.upper('x')
                    contradiction = scope.rewrite(bound, fixes)
                    return scope.absurd(contradiction)
                forward.binary_cases(['x'], kind='Eq', expect=goal, prove=prove)
                self.assertEqual(leaves, [0, 1])
                forward.complete(); reverse.complete()
                self.verify(proof)

    def test_provided_integrality_is_available_in_relaxed_input_mode(self):
        x = Expr.var(0)
        model = Model('fixed_continuous', [Variable('x', False, 1, 1)])
        proof = Proof(model, model)
        claim = proof.claim(integers=False, mapping='identity')
        equality = claim.eqpair(claim.upper('x'), claim.lower('x'))
        integer = claim.int([(equality, 1)], constant=1, expect=x)
        def prove(scope, fixes):
            if fixes['x'].expression == x-1:
                return fixes['x']
            return scope.absurd(scope.rewrite(scope.lower('x'), fixes))
        claim.binary_cases(['x'], kind='Eq', expect=x-1, prove=prove, integers={0: integer})
        claim.complete()
        self.verify(proof)

    def test_validation_rejects_bad_inputs_before_any_case_steps(self):
        x, y = Expr.var(0), Expr.var(1)
        model = Model('validation', [Variable('x', True, 0, 1), Variable('y', False, 0, 1)])
        builder = Builder(model)
        callback = lambda scope, fixes: scope.eq()
        bad = [(['x', x], {}), ([x+1], {}), (['y'], {}), (['x'], {'integers': False}),
               (['x'], {'integers': {'x': builder.integer('x'), 0: builder.integer('x')}}),
               (['y'], {'integers': {'y': builder.integer('x')}}),
               (['x'], {'integers': {'x': Builder(model).integer('x')}})]
        for variables, options in bad:
            with self.subTest(variables=variables, options=options):
                with self.assertRaises((BuildError, ValueError)):
                    builder.binary_cases(variables, kind='Eq', expect=0, prove=callback, **options)
                self.assertEqual(builder.steps, [])
        with self.assertRaises(BuildError):
            Builder(model, integers=False).binary_cases(['x'], kind='Eq', expect=0, prove=callback)
        wide = Builder(Model('wide', [Variable('x', True, 0, 2)]))
        with self.assertRaises(BuildError):
            wide.binary_cases(['x'], kind='Eq', expect=0, prove=callback)
        with self.assertRaises(BuildError):
            builder.binary_cases(['x'], kind='Eq', expect=0, prove=None)
        self.assertEqual(builder.steps, [])

    def test_zero_variables_call_the_provided_proof_once_and_check_its_conclusion(self):
        builder = Builder(Model('empty'))
        calls = []
        def prove(scope, fixes):
            calls.append((scope, fixes))
            return scope.eq()
        result = builder.binary_cases([], kind='Eq', expect=0, prove=prove)
        self.assertEqual(calls, [(builder, {})])
        self.assertEqual(result.expression, 0)
        self.assertNotIn('Cases', builder.steps[0])
        with self.assertRaises(BuildError):
            builder.binary_cases([], kind='Eq', expect=1, prove=lambda scope, fixes: result)


if __name__ == '__main__':
    unittest.main()
