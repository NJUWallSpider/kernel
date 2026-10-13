#!/usr/bin/env python3
"""Independent stdlib struct writer; never calls a Rust encoder or a preparer."""
from fractions import Fraction
from pathlib import Path
import hashlib,json,struct

HERE=Path(__file__).resolve().parent
def u32(x):return struct.pack('<I',x)
def tag(x):return struct.pack('<BBH',x,0,0)
def array(items):return u32(len(items))+b''.join(items)
def natural(x):return x.to_bytes((x.bit_length()+7)//8,'little')
def q(x):
    x=Fraction(x);n=natural(abs(x.numerator));d=natural(x.denominator)
    return tag(int(x<0))+u32(len(n))+u32(len(d))+n+d
def expr(c=0,terms=()):return q(c)+array([u32(i)+q(v) for i,v in terms])
def ref(t,i=0):return tag(t)+(b'' if t==8 else u32(i))
def frame(magic,payload,version):return magic+struct.pack('<HHQ',version,0,16+len(payload))+payload
def name(s):b=s.encode();return u32(len(b))+b
def model(label,upper,cost):
    variable=name('x')+tag(1)+b'\1'+q(0)+b'\1'+q(upper)
    return frame(b'MCM\0',name(label)+array([variable])+array([])+expr(7,[(0,cost)]),1)
def returning(margin_tag,checks):
    before=array([])+tag(8)+array([expr()])+array(checks)
    return before+tag(margin_tag)+q(1),len(before)
def e(c='0',terms=()):return {'constant':str(c),'terms':[[i,str(v)] for i,v in terms]}

def main():
    point=tag(3)+bytes([0,0,0,0])+array([expr(0,[(0,1)])])+array([q(Fraction(1,2))])+b'\0'
    block1,margin1=returning(1,[ref(8)]*4)
    imp1=bytes([2,0,0,0])+expr(0,[(0,1)])+block1
    block2right,margin2=returning(0,[ref(8)]*3+[ref(7,1)])
    left=array([])+tag(9)+ref(7,1)
    split_prefix=array([])+tag(1)+expr(0,[(0,1)])+b'\1'+ref(2,0)
    block2=split_prefix+left+block2right
    imp2=bytes([2,0,0,0])+expr(0,[(0,1)])+block2
    prefix=array([])+array([])+array([point])+array([])
    payload=prefix+array([imp1,imp2]);positive=frame(b'RPX\0',payload,10)
    pointflags=16+4+4+4+4
    imp1flags=16+len(prefix)+4;imp2flags=imp1flags+len(imp1)
    margin1offset=imp1flags+4+len(expr(0,[(0,1)]))+margin1
    margin2offset=imp2flags+4+len(expr(0,[(0,1)]))+len(split_prefix)+len(left)+margin2
    improvement_claim={'target':False,'integers':True,'positive':e(terms=[(0,1)])}
    image_claim={'ImageExclusion':{'point_in_target':False,'map':[e(terms=[(0,1)])]}}
    first={'steps':[],'end':{'ImproveReturn':{'map':[e()],'checks':['Exact']*4,'margin':{'Predicate':'1'}}}}
    second={'steps':[],'end':{'Split':{'expression':e(terms=[(0,1)]),'integer':{'VarInt':0},
        'left':{'steps':[],'end':{'PositiveRefutation':{'fact':{'Assumption':1}}}},
        'right':{'steps':[],'end':{'ImproveReturn':{'map':[e()],'checks':['Exact']*3+[{'Assumption':1}],'margin':{'Constant':'1'}}}}}}}
    certificate={'claims':[],'blocks':[],'points':[{'claim':image_claim,'values':['1/2']}],
        'improvements':[{'claim':improvement_claim,'block':first},{'claim':improvement_claim,'block':second}]}
    request={'claims':[],'points':[image_claim],'improvements':[improvement_claim,improvement_claim]}
    files={'contract-v10-source.mcm':model('source',1,1),'contract-v10-target.mcm':model('target',0,3),
        'contract-v10.rpx':positive,'contract-v10.rpa':('RPA 10\n'+json.dumps(certificate,separators=(',',':'))+'\n').encode(),
        'contract-v10-request.json':(json.dumps(request,separators=(',',':'))+'\n').encode()}
    offsets={'point_flags':pointflags,'improvement_1_flags':imp1flags,'improvement_2_flags':imp2flags,
        'predicate_margin_tag':margin1offset,'constant_margin_tag':margin2offset}
    mutations={}
    for label,offset in [('point',pointflags),('improvement1',imp1flags),('improvement2',imp2flags)]:
        for j in range(4):
            b=bytearray(positive);b[offset+j]=(2 if label=='point' else 4) if j==0 else 1
            filename=f'invalid-contract-v10-{label}-flags{j}.rpx';files[filename]=bytes(b);mutations[filename]={'offset':offset+j,'value':b[offset+j]}
    for label,offset in [('predicate',margin1offset),('constant',margin2offset)]:
        for j in range(4):
            b=bytearray(positive);b[offset+j]=2 if j==0 else 1
            filename=f'invalid-contract-v10-{label}-margin{j}.rpx';files[filename]=bytes(b);mutations[filename]={'offset':offset+j,'value':b[offset+j]}
    for filename,data in files.items():(HERE/filename).write_bytes(data)
    manifest={'writer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'format':'WORKING_VERSION_10_NOT_FROZEN',
        'scope':'Raw independent Python struct bytes: source binary x in[0,1], source objective7+x; target x=0. Source LP point1/2 has identity image outside target. Two same-source improvements verify Predicate and Constant margins, with PositiveRefutation at boundary.',
        'offsets':offsets,'negative_mutations':mutations,'files':{f:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for f,b in files.items()}}
    (HERE/'contract-v10-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'files':len(files),'rpx_bytes':len(positive),'negative_flags':len(mutations)}))
if __name__=='__main__':main()
