#!/usr/bin/env python3
"""Independent Fraction/gcd oracle for narrow V7 rational shortcuts.

All payload integers use hexadecimal strings to avoid decimal-parser limits;
boundary cases exercise the arithmetic 65,536-bit budget through direct APIs.
The oracle imports no kernel/preparer arithmetic or model helpers.
"""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import math
import random

BITS = 65536
rng = random.Random(0x52505837)

def pair(q):
    return [format(q.numerator, 'x'), format(q.denominator, 'x')]

def valid(q):
    return abs(q.numerator).bit_length() <= BITS and q.denominator.bit_length() <= BITS

def expression(c, terms):
    return {'constant': pair(c), 'terms': [[i, pair(q)] for i, q in sorted(terms.items()) if q]}

def scaled_case(name, c, terms, scale):
    result = {'name': name, 'expr': expression(c, terms), 'scale': pair(scale)}
    if not all(valid(q) for q in [c, scale, *terms.values()]):
        result['status'] = 'RESOURCE_LIMIT'
    elif not scale:
        result.update(status='OK', expected=expression(F(0), {}))
    else:
        out_c = c * scale
        out_terms = {i: q * scale for i, q in terms.items()}
        if all(valid(q) for q in [out_c, *out_terms.values()]):
            result.update(status='OK', expected=expression(out_c, out_terms))
        else:
            result['status'] = 'RESOURCE_LIMIT'
    return result

def accumulator_case(name, initial, adds):
    result = {'name': name, 'initial': pair(initial),
              'adds': [{'expr': expression(c, ts), 'scale': pair(scale)} for c, ts, scale in adds]}
    constant, terms = initial, {}
    try:
        def check(q):
            if not valid(q):
                raise OverflowError
        for c, ts, scale in adds:
            check(scale)
            if not scale:
                continue
            product = c * scale
            check(product)
            constant += product
            check(constant)
            for i, q in sorted(ts.items()):
                if not q:
                    continue
                product = q * scale
                check(product)
                terms[i] = terms.get(i, F(0)) + product
                check(terms[i])
                if not terms[i]:
                    del terms[i]
        check(constant)
        result.update(status='OK', expected=expression(constant, terms))
    except OverflowError:
        result['status'] = 'RESOURCE_LIMIT'
    return result

def small():
    return F(rng.randint(-200, 200), rng.randint(1, 97))

scalars = [F(0), F(1), F(-1), F(2, 3), F(-3, 2), F(7), F(-11)]
scaled, accumulators = [], []
for i in range(700):
    terms = {j: small() for j in sorted(rng.sample(range(24), rng.randrange(0, 12)))}
    c = small() if i % 3 else F(0)
    scale = scalars[i % len(scalars)] if i % 2 else small()
    scaled.append(scaled_case(f'random-{i}', c, terms, scale))
for i in range(350):
    adds = []
    for j in range(rng.randrange(1, 15)):
        terms = {k: small() for k in sorted(rng.sample(range(16), rng.randrange(0, 9)))}
        c = small() if j % 3 else F(0)
        scale = scalars[(i + j) % len(scalars)]
        adds.append((c, terms, scale))
        if j % 4 == 0:
            adds.append((c, terms, -scale))
    accumulators.append(accumulator_case(f'random-sum-{i}', small() if i % 2 else F(0), adds))

for exponent in [127, 1024, 8192, 65534, 65535]:
    large = 1 << exponent
    for sign in [-1, 1]:
        for scale in scalars:
            q = F(sign * (large - 1), large + 1)
            scaled.append(scaled_case(f'large-{exponent}-{sign}-{scale}', F(sign * large), {0:q, 17:F(sign * large)}, scale))
            accumulators.append(accumulator_case(f'cancel-{exponent}-{sign}-{scale}', F(0), [
                (q, {0:F(sign * large), 17:q}, scale),
                (q, {0:F(sign * large), 17:q}, -scale),
                (F(0), {4:F(3, 7)}, F(-1)),
            ]))

top = F(1 << (BITS - 1))
max_q = F((1 << BITS) - 1)
outside = F(1 << BITS)
scaled += [
    scaled_case('integer-positive-boundary', max_q, {0:top}, F(1)),
    scaled_case('integer-negative-boundary', -max_q, {0:-top}, F(-1)),
    scaled_case('zero-scale-still-validates-input', outside, {}, F(0)),
    scaled_case('unit-scale-rejects-too-wide', outside, {}, F(1)),
    scaled_case('negative-unit-rejects-too-wide', outside, {}, F(-1)),
    scaled_case('constant-product-overflow', top, {}, F(2)),
    scaled_case('term-product-overflow', F(0), {0:top}, F(2)),
    scaled_case('denominator-boundary', F(1, (1 << BITS) - 1), {}, F(-1)),
    scaled_case('denominator-product-overflow', F(1, 1 << (BITS - 1)), {}, F(1, 2)),
]
accumulators += [
    accumulator_case('constant-product-before-cancellation', -top, [(top, {}, F(2))]),
    accumulator_case('term-product-before-cancellation', F(0), [(F(0), {0:-top}, F(1)), (F(0), {0:top}, F(2))]),
    accumulator_case('constant-result-overflow', top, [(top, {}, F(1))]),
    accumulator_case('term-result-overflow', F(0), [(F(0), {0:top}, F(1)), (F(0), {0:top}, F(1))]),
    accumulator_case('vacant-noninteger-product', F(0), [(F(0), {3:F(4, 7)}, F(-1))]),
    accumulator_case('initial-too-wide-finish', outside, []),
    accumulator_case('initial-too-wide-plus-zero', outside, [(F(0), {}, F(1))]),
    accumulator_case('zero-scale-then-finish', outside, [(F(0), {}, F(0))]),
    accumulator_case('cancel-unit-boundary', max_q, [(-max_q, {0:max_q}, F(1)), (F(0), {0:max_q}, F(-1))]),
]

raw = []
for n, d in [(0, 1), (1, 1), (-1, 1), (17, 1), (-17, 1), (0, 2), (2, 4), (-2, 4),
             (1, 0), (0, 0), (1, -1), (-1, -1), (1, 7), (-7, 11),
             ((1<<BITS)-1,1), (-(1<<BITS)+1,1), (1<<BITS,1), (-(1<<BITS),1),
             (1,(1<<BITS)-1), (1,1<<BITS)]:
    status = 'RESOURCE_LIMIT' if max(abs(n).bit_length(),abs(d).bit_length()) > BITS else (
        'OK' if d > 0 and math.gcd(n,d) == 1 else 'INVALID')
    raw.append({'value':[format(n,'x'),format(d,'x')], 'status':status})

document = {'oracle':'Python fractions.Fraction and math.gcd; no production imports',
            'seed':0x52505837, 'max_q_bits':BITS, 'scaled':scaled, 'accumulators':accumulators, 'raw':raw}
path = Path(__file__).with_name('rational_shortcuts_oracle.json')
path.write_text(json.dumps(document,separators=(',',':'))+'\n')
print(json.dumps({'scaled':len(scaled),'accumulators':len(accumulators),'raw':len(raw),
                  'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
