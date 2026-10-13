#!/usr/bin/env python3
"""Independent, stdlib-only writer for the documented v1 through v8 binary vectors."""
from fractions import Fraction
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent

def u8(x): return struct.pack('<B', x)
def u32(x): return struct.pack('<I', x)
def tag(x): return struct.pack('<BBH', x, 0, 0)
def array(items): return u32(len(items)) + b''.join(items)
def name(x):
    raw = x.encode('utf8')
    return u32(len(raw)) + raw
def integer(x): return x.to_bytes((x.bit_length() + 7) // 8, 'little')
def q(n, d=1):
    value = Fraction(n, d)
    nbytes, dbytes = integer(abs(value.numerator)), integer(value.denominator)
    return tag(int(value < 0)) + u32(len(nbytes)) + u32(len(dbytes)) + nbytes + dbytes
def optional(value): return b'\0' if value is None else b'\1' + value
def expression(constant=0, terms=()):
    return q(constant) + array([u32(i) + q(a, b) for i, a, b in terms])
def ref(t, i=0): return tag(t) + (b'' if t == 8 else u32(i))
def frame(magic, payload, version=1): return magic + struct.pack('<HHQ', version, 0, 16 + len(payload)) + payload
def claim(reverse=False, inverse=None):
    return bytes([6 | int(reverse), 1, 0, 0]) + array([u32(0) + u32(0)]) + optional(None if inverse is None else u32(inverse))
def linear(i, kind, constant, terms=()):
    return tag(0) + u32(i) + tag(kind) + q(constant) + array([ref(t, j) + q(a, b) for t, j, a, b in terms])
def round_step(i): return tag(1) + u32(i) + ref(1, 0) + ref(2, 0)
def drop(i): return tag(2) + array([u32(i)])
def returned(checks): return tag(0) + array([expression(0, [(0, 1, 1)])]) + array(checks)
def ordinary(inverse=True):
    steps = [linear(0, 0, 0, [(0, 0, 1, 1)]), round_step(1), linear(2, 1, 0), drop(0)]
    checks = [ref(0), ref(6, 1), ref(2), ref(6, 2), ref(6, 2)]
    if inverse: checks.append(ref(6, 2))
    return array(steps) + returned(checks)
def split(left, right, integral=False):
    expr = expression(0, [(0, 1, 1)])
    return array([]) + tag(1) + expr + optional(ref(2) if integral else None) + left + right
def certificate(claims, blocks): return frame(b'RPX\0', array(claims) + array(blocks))
def local_v2():
    pair = tag(3) + u32(2) + ref(6, 0) + ref(6, 1)
    child = array([]) + tag(0) + ref(6, 2)
    cases = tag(4) + u32(3) + tag(1) + expression() + expression(0, [(0, 1, 1)]) + optional(ref(2)) + child + child
    return array([linear(0, 0, 0), linear(1, 0, 0), pair, cases]) + returned([ref(0), ref(1), ref(2), ref(6, 2), ref(6, 3), ref(6, 2)])

def main():
    v = name('x') + tag(1) + optional(q(0)) + optional(q(1))
    payload = name('binary_identity') + array([v]) + array([]) + expression(3, [(0, 2, 5)])
    model = frame(b'MCM\0', payload)
    simple = certificate([claim(False, 1), claim(True, 0)], [ordinary(), ordinary()])
    contradiction = array([linear(42, 0, 0, [(7, 0, 1, 1), (7, 1, 1, 1)])]) + tag(2) + ref(6, 42)
    nested = split(split(ordinary(False), contradiction, True), ordinary(False))
    nesting = certificate([claim(), claim(True)], [nested, ordinary(False)])
    vectors = {
        'identity.mcm': model,
        'identity-ordinary.rpx': simple,
        'identity-nested.rpx': nesting,
        'empty.mcm': frame(b'MCM\0', name('M') + array([]) + array([]) + expression()),
        'empty-syntax.rpx': certificate([], []),
        'invalid-unknown-step.rpx': certificate([claim()], [array([tag(0x80)]) + returned([])]),
        'invalid-unknown-theorem.rpx': certificate([claim()], [array([tag(0xF0)]) + returned([])]),
    }
    v2 = frame(b'RPX\0', array([claim(False, 1), claim(True, 0)]) + array([local_v2(), local_v2()]), 2)
    vectors['identity-local-v2.rpx'] = v2
    plotkin = tag(5) + u32(9) + u32(1) + u32(1) + array([u32(0) + struct.pack('<Q', 0)]) + array([])
    lower = linear(10, 0, 0, [(0, 0, 2, 5)])
    v3block = array([plotkin, lower]) + returned([ref(0), ref(1), ref(2), ref(8), ref(8), ref(6, 10)])
    point = tag(0) + bytes([2, 0, 0, 0]) + optional(q(17, 5)) + array([q(1)])
    v3 = frame(b'RPX\0', array([claim() + optional(q(3))]) + array([v3block]) + array([point]), 3)
    vectors['identity-plotkin-v3.rpx'] = v3
    vectors['invalid-v3-step-v2.rpx'] = frame(b'RPX\0', array([claim()]) + array([v3block]), 2)
    bad = bytearray(v3); bad[-len(point)] = 2
    vectors['invalid-v3-point-tag.rpx'] = bytes(bad)
    z = name('z') + tag(0) + optional(q(0)) + optional(None)
    law = name('same') + expression(0, [(0, -1, 1), (1, 1, 1)]) + optional(q(0)) + optional(q(0))
    vectors['flow-target.mcm'] = frame(b'MCM\0', name('flow_target') + array([v, z]) + array([law]) + expression(3, [(0, 2, 5)]))
    group = u32(0) + array([u32(0) + q(0)]) + array([expression(0, [(0, 1, 1)])]) + array([ref(0)]) + array([ref(8)])
    witness = u32(1) + array([u32(0) + u32(0)]) + array([group])
    body = array([]) + tag(0) + array([expression(0, [(0, 1, 1)]), expression(0, [(1, 1, 1)])]) + array([ref(0), ref(1), ref(2), ref(0, 1), ref(5, 1), ref(8), ref(8)])
    block = array([]) + tag(3) + witness + body
    v4 = frame(b'RPX\0', array([claim() + optional(None)]) + array([block]) + array([]), 4)
    vectors['flow-v4.rpx'] = v4
    bad = bytearray(v4); bad[4] = 3
    vectors['invalid-v4-terminal-v3.rpx'] = bytes(bad)
    interval = array([expression(0, [(0, 1, 1)])]) + array([expression(0, [(0, 1, 1)])]) + array([ref(8)])
    pair = tag(3) + u32(9) + ref(4, 1) + ref(3, 0)
    lower_z = linear(10, 0, 0, [(3, 0, 1, 1), (0, 0, 1, 1)])
    body = array([pair, lower_z]) + tag(0) + array([expression(0, [(0, 1, 1)]), expression(0, [(1, 1, 1)])]) + array([ref(0), ref(1), ref(2), ref(6, 10), ref(6, 9), ref(8), ref(8), ref(6, 9)])
    block = array([]) + tag(4) + array([interval]) + body
    v5claim = claim() + optional(None) + array([expression(0, [(0, 1, 1)]) + expression(0, [(1, 1, 1)])])
    vectors['interval-v5.rpx'] = frame(b'RPX\0', array([v5claim]) + array([block]) + array([]), 5)
    vectors['invalid-v5-terminal-v4.rpx'] = frame(b'RPX\0', array([claim() + optional(None)]) + array([block]) + array([]), 4)
    fixed = name('x') + tag(0) + optional(q(0)) + optional(q(0))
    vectors['fiber-source.mcm'] = frame(b'MCM\0', name('fixed_zero') + array([fixed]) + array([]) + expression())
    inclusion_claim = bytes([0, 0, 0, 0]) + array([u32(0)+u32(0)]) + optional(None) + optional(None) + array([])
    inclusion = array([linear(0, 0, -1, [(1, 0, 1, 1)])]) + returned([ref(0), ref(6, 0), ref(8)])
    refutation = array([linear(1, 0, 0, [(1, 0, 1, 1), (5, 0, -1, 1)])]) + tag(2) + ref(6, 1)
    fiber_point = tag(2) + u32(0) + array([q(1)]) + optional(refutation)
    vectors['fiber-v6.rpx'] = frame(b'RPX\0', array([inclusion_claim]) + array([inclusion]) + array([fiber_point]), 6)
    vectors['invalid-v6-point-v5.rpx'] = frame(b'RPX\0', array([inclusion_claim]) + array([inclusion]) + array([fiber_point]), 5)
    # V7 singleton menu plus full bijection. Uses actual identity.mcm on both sides.
    claim7 = lambda reverse: claim(reverse) + optional(None) + array([])
    forward7 = array([]) + returned([ref(0), ref(1), ref(2), ref(8), ref(8)])
    menu = u32(0) + expression(0, [(0, 1, 1)]) + expression() + array([ref(0), ref(1), ref(2), ref(8), ref(8), ref(8)])
    body7 = array([linear(0, 1, 0, [(5, 0, 2, 5)])]) + tag(0) + array([expression(0, [(1, 1, 1)])]) + array([ref(0, 1), ref(1, 1), ref(2, 1), ref(6, 0), ref(5, 0), ref(5, 0)])
    reverse7 = array([]) + tag(5) + array([menu]) + body7
    bijection = u32(0) + u32(1) + array([]) + array([ref(5, 0)])
    v7 = frame(b'RPX\0', array([claim7(False), claim7(True)]) + array([forward7, reverse7]) + array([]) + array([bijection]), 7)
    vectors['menu-v7.rpx'] = v7
    bad = bytearray(v7); bad[4] = 6
    vectors['invalid-v7-terminal-v6.rpx'] = bytes(bad)
    vectors['invalid-v7-count.rpx'] = frame(b'RPX\0', array([]) + array([]) + array([]) + u32(0xFFFFFFFF), 7)
    # Independent V8 nonzero signed real flow and binary activation, full target.
    vv=lambda n,it,lo,hi:name(n)+tag(it)+optional(None if lo is None else q(lo))+optional(None if hi is None else q(hi))
    rr=lambda n,t:name(n)+expression(0,t)+optional(None)+optional(q(0))
    sv=[vv('f',0,None,None),vv('z',1,0,1)]
    sr=[rr('upper',[(0,1,1),(1,-2,1)]),rr('lower',[(0,-1,1),(1,-2,1)])]
    vectors['signed-source.mcm']=frame(b'MCM\0',name('signed_input')+array(sv)+array(sr)+expression(5,[(1,3,1)]))
    tv=[vv('p',0,0,None),vv('n',0,0,None),vv('u',1,0,1),vv('v',1,0,1)]
    tr=[rr('upper_p',[(0,1,1),(2,-2,1)]),rr('upper_n',[(1,1,1),(3,-2,1)])]
    vectors['signed-target.mcm']=frame(b'MCM\0',name('direction_pair')+array(tv)+array(tr)+expression(5,[(2,3,1),(3,3,1)]))
    ap=[expression(0,[(0,1,1)])+expression(0,[(0,1,1),(1,-1,1)]),expression(0,[(1,1,1)])+expression(0,[(2,1,1),(3,1,1)])]
    c8=bytes([6,1,0,0])+array([])+optional(None)+optional(None)+array(ap)
    d8=q(2)+expression(0,[(0,1,1)])+expression(0,[(1,1,1)])+array([ref(0,1),ref(1,1),ref(2,1),ref(4,0),ref(4,1)])
    body8=array([linear(0,1,0,[(5,3,3,1)])])+tag(0)+array([expression(0,[(j,1,1)]) for j in range(2,6)])+array([ref(0,2),ref(0,3),ref(0,4),ref(1,4),ref(2,4),ref(0,5),ref(1,5),ref(2,5),ref(4,4),ref(4,5),ref(6,0),ref(5,2),ref(5,3)])
    block8=array([])+tag(6)+array([d8])+body8
    v8=frame(b'RPX\0',array([c8])+array([block8])+array([])+array([]),8)
    vectors['signed-v8.rpx']=v8
    bad=bytearray(v8);bad[4]=7;vectors['invalid-v8-terminal-v7.rpx']=bytes(bad)
    badblock8=array([])+tag(6)+u32(0xffffffff)
    vectors['invalid-v8-count.rpx']=frame(b'RPX\0',array([c8])+array([badblock8])+array([])+array([]),8)
    bad = bytearray(v2); bad[4] = 1
    vectors['invalid-v2-downgrade.rpx'] = bytes(bad)
    bad = bytearray(simple); bad[6] = 1
    vectors['invalid-reserved.rpx'] = bytes(bad)
    bad = bytearray(simple + b'\0'); bad[8:16] = struct.pack('<Q', len(bad))
    vectors['invalid-trailing.rpx'] = bytes(bad)
    bad = bytearray(simple[:-1]); bad[8:16] = struct.pack('<Q', len(bad))
    vectors['invalid-truncated.rpx'] = bytes(bad)
    bad = bytearray(certificate([], [])); bad[16:20] = u32(0xFFFFFFFF)
    vectors['resource-count.rpx'] = bytes(bad)
    for filename, data in vectors.items():
        (HERE / filename).write_bytes(data)
        print(f'{filename}: {len(data)} bytes')

if __name__ == '__main__': main()
