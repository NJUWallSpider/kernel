#!/usr/bin/env python3
"""Independent Python struct V10 conditional-domain vectors, no Rust encoder."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json,struct

HERE=Path(__file__).resolve().parent
def u32(n):return struct.pack('<I',n)
def tag(n):return struct.pack('<BBH',n,0,0)
def array(items):return u32(len(items))+b''.join(items)
def natural(n):return n.to_bytes((n.bit_length()+7)//8,'little')
def q(x):
    x=Q(x);n=natural(abs(x.numerator));d=natural(x.denominator)
    return tag(int(x<0))+u32(len(n))+u32(len(d))+n+d
def expr(c=0,terms=()):return q(c)+array([u32(i)+q(v) for i,v in terms])
def ref(t,i=0):return tag(t)+(b'' if t==8 else u32(i))
def frame(magic,payload,version):return magic+struct.pack('<HHQ',version,0,16+len(payload))+payload
def name(s):b=s.encode();return u32(len(b))+b
def model(label,upper):
    variable=name('x')+tag(0)+b'\1'+q(0)+b'\1'+q(upper)
    return frame(b'MCM\0',name(label)+array([variable])+array([])+expr(7,[(0,1)]),1)
def e(c=0,terms=()):return {'constant':str(c),'terms':[[i,str(v)] for i,v in terms]}

def main():
    files={'conditional-source.mcm':model('conditional-source',1),'conditional-target.mcm':model('conditional-target',Q(1,2))};details={}
    for label,level in [('halfspace',None),('level-halfspace',Q(15,2))]:
        # Byte 3 of the prior flags byte was reserved. Some adds exactly one
        # Expr after the existing objective-level option, without an option tag.
        level_bytes=b'\0' if level is None else b'\1'+q(level)
        prefix=bytes([8,1,0,0])+array([u32(0)+u32(0)])+b'\0'+b'\0'+array([])+level_bytes
        halfspace=expr(Q(-1,2),[(0,1)]);claim=prefix+halfspace
        row=0 if level is None else 1
        block=array([])+tag(0)+array([expr(0,[(0,1)])])+array([ref(0,0),ref(4,row),ref(8),ref(8)])
        proof=frame(b'RPX\0',array([claim])+array([block])+array([])+array([])+array([]),10)
        c={'reverse':False,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[0,0]],'inverse':None,'input_halfspace':e('-1/2',[(0,1)])}
        if level is not None:c['input_objective_level']=str(level)
        b={'steps':[],'end':{'Return':{'map':[e(0,[(0,1)])],'checks':[{'VarLower':0},{'RowUpper':row},'Exact','Exact']}}}
        basename='conditional-'+label
        files[basename+'.rpx']=proof
        files[basename+'.rpa']=('RPA 10\n'+json.dumps({'claims':[c],'blocks':[b]},separators=(',',':'))+'\n').encode()
        files[basename+'-request.json']=(json.dumps({'claims':[c]},separators=(',',':'))+'\n').encode()
        details[label]={'claim_flags_offset':20,'halfspace_expr_offset':20+len(prefix),'rpx_bytes':len(proof),'conditional_row_index':row}
    # An independently written pre-halfspace V10 certificate with a real claim
    # (not an empty claim list): reverse LP identity and a source image witness.
    oldclaim=bytes([1,1,0,0])+array([u32(0)+u32(0)])+b'\0'+b'\0'+array([])+b'\0'
    lin=tag(0)+u32(0)+tag(0)+q(Q(-1,2))+array([ref(1,0)+q(1)])
    oldblock=array([lin])+tag(0)+array([expr(0,[(0,1)])])+array([ref(0,0),ref(6,0),ref(8),ref(8)])
    point=tag(3)+bytes([0,0,0,0])+array([expr(0,[(0,1)])])+array([q(Q(3,4))])+b'\0'
    old=frame(b'RPX\0',array([oldclaim])+array([oldblock])+array([point])+array([])+array([]),10)
    oc={'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[0,0]],'inverse':None}
    op={'ImageExclusion':{'point_in_target':False,'map':[e(0,[(0,1)])]}}
    ob={'steps':[{'Lin':{'id':0,'kind':'Le','constant':'-1/2','terms':[[{'VarUpper':0},'1']]}}],
        'end':{'Return':{'map':[e(0,[(0,1)])],'checks':[{'VarLower':0},{'Local':0},'Exact','Exact']}}}
    files['conditional-old-none.rpx']=old
    files['conditional-old-none.rpa']=('RPA 10\n'+json.dumps({'claims':[oc],'blocks':[ob],'points':[{'claim':op,'values':['3/4']}]},separators=(',',':'))+'\n').encode()
    files['conditional-old-none-request.json']=(json.dumps({'claims':[oc],'points':[op]},separators=(',',':'))+'\n').encode()
    base=files['conditional-halfspace.rpx'];mutations={}
    for label,offset,value in [('flags',20,16),('reserved2',22,1),('reserved3',23,1),('header6',6,1),('header7',7,1),('cleared_presence_flag',20,0)]:
        b=bytearray(base);b[offset]=value;fn='invalid-conditional-'+label+'.rpx';files[fn]=bytes(b);mutations[fn]={'kind':'byte','offset':offset,'value':value}
    for version in range(1,10):
        b=bytearray(base);b[4:6]=struct.pack('<H',version);fn=f'invalid-conditional-version{version}.rpx';files[fn]=bytes(b);mutations[fn]={'kind':'version','version':version}
    pos=details['halfspace']['halfspace_expr_offset'];b=bytearray(base[:pos]+b'\0'+base[pos:]);b[8:16]=struct.pack('<Q',len(b));fn='invalid-conditional-inserted-option-tag.rpx';files[fn]=bytes(b);mutations[fn]={'kind':'inserted-option-tag','offset':pos}
    for filename,data in files.items():(HERE/filename).write_bytes(data)
    manifest={'writer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'format':'WORKING_VERSION_10_NOT_FROZEN',
      'scope':'Continuous x∈[0,1] to x∈[0,1/2] with equal 7+x objective and identity projection, conditional on x−1/2<=0. Second vector also restricts input objective=15/2 and uses appended halfspace row1 after level row0.',
      'wire':details,'mutations':mutations,'all_truncations_tested_by':'crates/core/tests/conditional_wire.rs','files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}
    (HERE/'conditional-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'files':len(files),'vectors':details,'persisted_mutations':len(mutations)}))
if __name__=='__main__':main()
