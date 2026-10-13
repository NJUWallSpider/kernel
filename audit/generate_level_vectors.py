#!/usr/bin/env python3
"""Independent documented V9 writer; never calls the Rust codec or assembler."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/vectors'))
from generate_vectors import u32,tag,array,name,q,optional,expression,ref,frame,linear

def claim(reverse=False,objective=1,inverse=None,lower=None,level=None):
    return bytes([6|int(reverse),objective,0,0])+array([])+optional(None if inverse is None else u32(inverse))+optional(None if lower is None else q(lower))+array([])+optional(None if level is None else q(level))
def block(steps,mapping,checks):return array(steps)+tag(0)+array(mapping)+array(checks)
def model(n,upper):
    var=name('x')+tag(1)+optional(q(0))+optional(q(upper))
    return frame(b'MCM\0',name(n)+array([var])+array([])+expression(3,[(0,1,1)]))
def main():
    claims=[claim(objective=2,lower=3),claim(inverse=2,level=3),claim(reverse=True,inverse=1)]
    blocks=[block([],[expression()],[ref(8),ref(8),ref(8),ref(0),ref(0)]),block([],[expression(0,[(0,1,1)])],[ref(0),ref(5),ref(2),ref(8),ref(8)]),block([linear(0,0,-2,[(1,0,1,1)]),tag(3)+u32(1)+ref(1)+ref(0)],[expression(0,[(0,1,1)])],[ref(0),ref(6,0),ref(2),ref(8),ref(8),ref(6,1)])]
    point=tag(0)+bytes([2,0,0,0])+optional(q(3))+array([q(0)])+optional(None)
    cert=frame(b'RPX\0',array(claims)+array(blocks)+array([point])+array([]),9)
    bad=bytearray(cert);offset=16+4+len(claims[0])+len(claims[1])-len(q(3))-1;assert bad[offset]==1;bad[offset]=2
    values={'level-source.mcm':model('source',2),'level-target.mcm':model('target',0),'level-v9.rpx':cert,'invalid-level-option-v9.rpx':bytes(bad)}
    report={}
    for filename,data in values.items():(ROOT/'tests/vectors'/filename).write_bytes(data);report[filename]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    (ROOT/'audit/level_vectors.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
