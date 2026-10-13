#!/usr/bin/env python3
"""Assemble/replay the full draft test36 contract; retain concrete attacks."""
from pathlib import Path
import json,hashlib,subprocess,time,gc,argparse
from prepare_affine import parse_mps

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(d,k,v):
    old=d[k];d[k]=v
    return lambda:d.__setitem__(k,old)
def remove(x,i):
    v=x.pop(i)
    return lambda:x.insert(i,v)
def terminal(c):
    b=c['improvements'][0]['block']
    while 'SignedLift' in b['end']:b=b['end']['SignedLift']['body']
    return b['end']['Split']
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/conditional-domain-production/release/rpx'));ap.add_argument('--expected-sha256',default='96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8');ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
    root=Path('cases/test36');k=args.kernel.resolve();expected=args.expected_sha256;assert sha(k)==expected
    parts=[root/'complete-forward',root/'complete-reverse',root/'complete-projection',root/'complete-improvement'];assert all((p/'proof.rpa').exists() and (p/'request.json').exists() for p in parts)
    claims=[json.loads((p/'request.json').read_text())['claims'][0] for p in parts[:3]];improvement=json.loads((parts[3]/'request.json').read_text())['improvements'][0]
    request={'claims':claims,'improvements':[improvement]};(root/'request.json').write_text(json.dumps(request,separators=(',',':'))+'\n')
    with (root/'proof.rpa').open('wb') as f:
        f.write(b'RPA 10\n{"claims":'+json.dumps(claims,separators=(',',':')).encode()+b',"blocks":[')
        for i,p in enumerate(parts[:3]):
            raw=(p/'proof.rpa').read_bytes().rstrip();tag=b',"blocks":[';start=raw.index(tag)+len(tag);assert raw.endswith(b']}')
            if i:f.write(b',')
            f.write(raw[start:-2])
        raw=(parts[3]/'proof.rpa').read_bytes().rstrip();tag=b',"improvements":[';start=raw.index(tag)+len(tag);f.write(b'],"improvements":['+raw[start:-2]+b']}\n')
    print(json.dumps({'complete_rpa_bytes':(root/'proof.rpa').stat().st_size,'text_limit_bytes':268435456}),flush=True)
    assert (root/'proof.rpa').stat().st_size<=268435456,'Complete RPA would exceed the unchanged text limit'
    if args.prepare_only:return
    run=Path('/Users/bhz/Code/reform_test/runs/test36-nomf-B1');meta={'case_id':'test36','status':'PROOF_NOT_COMPLETED','contract':'Complete source-MI to target-MI nonincreasing map; equal-objective target-MI to source-MI recovery preserving all 37616 retained coordinates; caller-bound source-MI input halfspace P<=0 to target-MI equal-objective identity projection on all 37616 retained coordinates; and caller-bound strict source improvement whenever P, the sum of all 200 original nonnegative continuous terminals, is positive. Together these certify minimum preservation and retained-coordinate projection/recovery of every optimizer. No numerical optimum or LP relation asserted.','protocol_status':'Working draft RPA/RPX 10 improvement and generic input-halfspace contracts; not a new freeze or release.','source':{'path':str(run/'input/model.mps'),'sha256':sha(run/'input/model.mps')},'target':{'path':str(run/'output/reformulated.mps'),'sha256':sha(run/'output/reformulated.mps')},'kernel_binary':{'path':str(k),'sha256':expected},'kernel_binary_sha256':expected,'kernel_runs':[],'negative_checks':[],'work_policy':1000000000,'timing_context':'Functional verification; not an isolated performance benchmark.'}
    def save():(root/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
    def call(args):
        before=sha(k);assert before==expected;t=time.perf_counter();r=subprocess.run([str(k)]+list(map(str,args)),capture_output=True,text=True);after=sha(k);assert before==after
        return {'command':[str(k)]+list(map(str,args)),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'wall_seconds':time.perf_counter()-t,'binary_sha256_before':before,'binary_sha256_after':after}
    save()
    for cmd in [['assemble',root/'proof.rpa',root/'proof.rpx'],['verify',root/'source.mcm',root/'target.mcm',root/'proof.rpx',root/'request.json']]:
        r=call(cmd);meta['kernel_runs'].append(r);save();assert r['exit_code']==0,r
    result=json.loads(meta['kernel_runs'][-1]['stdout']);assert result['claims']==3 and result['improvements']==1;meta['status']='VERIFIED';meta['statistics']=result['statistics'];meta['former_100m_run']=call(['verify','--work','100000000',root/'source.mcm',root/'target.mcm',root/'proof.rpx',root/'request.json']);save()
    control=call(['verify',root/'source.mcm',root/'target.mcm',root/'attempts/positive_terminal.rpx',root/'attempts/positive_terminal_request.json']);assert control['exit_code']==0;meta['positive_noninteger_terminal_control']=control;save()
    # Each mutation is a complete source-model improvement request, not a toy.
    c=json.loads((parts[3]/'proof.rpa').read_text().split('\n',1)[1]);a=parse_mps(run/'input/model.mps');firstbit=next(i for i,v in enumerate(a['vars']) if v['integer']);oldterminal=improvement['positive']['terms'][0][0];basevars=len(a['vars']);del a;gc.collect()
    attacks=[
      ('zero_strict_margin','A zero predicate multiplier does not certify a strict decrease.',lambda:replace(terminal(c)['left']['end']['ImproveReturn']['margin'],'Predicate','0')),
      ('gap_too_large','858 saving is changed to859 without a stronger objective proof.',lambda:replace(terminal(c)['right']['end']['ImproveReturn']['margin'],'Constant','859')),
      ('wrong_positive_predicate','The certificate changes the caller-bound positive terminal predicate.',lambda:replace(c['improvements'][0]['claim']['positive']['terms'][0],1,'2')),
      ('continuous_terminal_integer','An original continuous terminal is used as the integer split fact.',lambda:replace(terminal(c),'integer',{'VarInt':oldterminal})),
      ('missing_actual_chain_row','One actual original source chain obligation is removed.',lambda:remove(terminal(c)['left']['end']['ImproveReturn']['checks'],38216+20000)),
      ('new_scope_premise','A generated sign binary is borrowed to justify its own parent extension.',lambda:replace(c['improvements'][0]['block']['end']['SignedLift']['decompositions'][0]['checks'],2,{'VarInt':basevars+2})),
      ('infeasible_constant_return','The fixed feasible return point is changed to have binary value2.',lambda:replace(terminal(c)['right']['end']['ImproveReturn']['map'][firstbit],'constant','2')),
      ('weak_assumption_refutation','The weak closure fact -P<=0 is used to refute the root P>0.',lambda:replace(terminal(c)['left'],'end',{'PositiveRefutation':{'fact':{'Assumption':0}}})),
    ]
    dest=root/'attacks';dest.mkdir(exist_ok=True);rq=parts[3]/'request.json'
    for name,reason,mutate in attacks:
        undo=mutate();pa=dest/(name+'.rpa');px=dest/(name+'.rpx');pa.write_text('RPA 10\n'+json.dumps(c,separators=(',',':'))+'\n');undo()
        records=[call(['assemble',pa,px])]
        if records[-1]['exit_code']==0:records.append(call(['verify',root/'source.mcm',root/'target.mcm',px,rq]))
        res=json.loads(records[-1]['stdout']);assert res['status']=='INVALID',(name,res)
        evidence={'mutation':name,'rule_broken':reason,'status':'INVALID','runs':records,'rpa_sha256':sha(pa),'rpx_sha256':sha(px) if px.exists() else None,'request':str(rq),'request_sha256':sha(rq)};(dest/(name+'.json')).write_text(json.dumps(evidence,indent=2)+'\n');meta['negative_checks'].append({'mutation':name,'status':'INVALID','receipt':str(dest/(name+'.json'))});save();print(name,'INVALID',flush=True)
    del c;gc.collect()
    conditional=json.loads((parts[2]/'proof.rpa').read_text().split('\n',1)[1]);conditional_request=json.loads((parts[2]/'request.json').read_text())
    reverse_cert=json.loads((parts[1]/'proof.rpa').read_text().split('\n',1)[1]);reverse_request=json.loads((parts[1]/'request.json').read_text())
    more=[
      ('missing_halfspace','Removing the domain restriction must not permit the identity projection from arbitrary source points.','conditional',lambda c:c['claims'][0].pop('input_halfspace'),True),
      ('reversed_halfspace','The reversed halfspace P>=0 does not force the nonnegative terminals to vanish.','conditional',lambda c:[t.__setitem__(1,'-1') for t in c['claims'][0]['input_halfspace']['terms']],True),
      ('incomplete_terminal_halfspace','The caller restriction omits one actual original terminal.','conditional',lambda c:c['claims'][0]['input_halfspace']['terms'].pop(),True),
      ('missing_projection_obligation','A required retained-coordinate projection check is omitted.','conditional',lambda c:c['blocks'][0]['end']['Return']['checks'].pop(),False),
      ('borrow_old_row_as_halfspace','An actual chain row is borrowed as the appended caller-domain bound.','conditional',lambda c:c['blocks'][0]['steps'][1]['EqPair'].__setitem__('positive',{'RowUpper':37616}),False),
      ('wrong_reverse_projection','The reverse map fails a caller-requested retained coordinate observation.','reverse',lambda c:c['claims'][0]['projection'][0].__setitem__(1,c['claims'][0]['projection'][1][1]),True),
    ]
    for name,reason,which,mutate,match_request in more:
        c=json.loads(json.dumps(conditional if which=='conditional' else reverse_cert));rqobj=json.loads(json.dumps(conditional_request if which=='conditional' else reverse_request));mutate(c)
        if match_request:rqobj['claims']=c['claims']
        pa=dest/(name+'.rpa');px=dest/(name+'.rpx');rq=dest/(name+'.request.json');pa.write_text('RPA 10\n'+json.dumps(c,separators=(',',':'))+'\n');rq.write_text(json.dumps(rqobj,separators=(',',':'))+'\n')
        records=[call(['assemble',pa,px])]
        if records[-1]['exit_code']==0:records.append(call(['verify',root/'source.mcm',root/'target.mcm',px,rq]))
        res=json.loads(records[-1]['stdout']);assert res['status']=='INVALID',(name,res)
        evidence={'mutation':name,'rule_broken':reason,'status':'INVALID','runs':records,'rpa_sha256':sha(pa),'rpx_sha256':sha(px) if px.exists() else None,'request':str(rq),'request_sha256':sha(rq),'caller_request_matches_mutated_claim':match_request};(dest/(name+'.json')).write_text(json.dumps(evidence,indent=2)+'\n');meta['negative_checks'].append({'mutation':name,'status':'INVALID','receipt':str(dest/(name+'.json'))});save();print(name,'INVALID',flush=True)
    meta['artifacts']={n:{'bytes':(root/n).stat().st_size,'sha256':sha(root/n)} for n in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json','oracle.json']};meta['rpa_sha256']=meta['artifacts']['proof.rpa']['sha256'];meta['preparers']={str(p):sha(p) for p in map(Path,['tools/prepare_test36_full.py','tools/finalize_test36.py','tools/oracle_test36.py'])};meta['completion_kind']='single-certificate-with-improvement-and-optimizer-projection';meta['attack_status']='ALL_'+str(len(meta['negative_checks']))+'_INVALID';meta['full_scope_status']='VERIFIED_ALL_OPTIMIZER_RETAINED_PROJECTION';meta['counts']={'source_variables':37816,'target_variables':37616,'source_rows':37617,'target_rows':37617,'original_binary_coordinates':200,'original_continuous_terminals':200,'signed_stages_per_canonical_root':19,'maximum_original_prefix_length':191,'directional_claims':3,'strict_improvement_claims':1,'unconditional_reverse_projection':37616,'zero_terminal_face_forward_projection':37616};meta['preserved_attempts']=['cases/test36/attempts','cases/test36/first-verbose-forward','cases/test36/pre-projection-completion'];meta['exceeds_former_100m_work']=meta['statistics']['work']>100000000;meta['independent_read_review']='audit/test36_read_review.md';allruns=meta['kernel_runs']+[meta['former_100m_run'],meta['positive_noninteger_terminal_control']]+[r for n in meta['negative_checks'] for r in json.loads(Path(n['receipt']).read_text())['runs']];assert all(r['binary_sha256_before']==r['binary_sha256_after']==expected for r in allruns);meta['fixed_identity_validation']={'status':'PASS','commands':len(allruns),'binary_sha256':expected};save();print(json.dumps({'status':meta['status'],'statistics':meta['statistics'],'attacks':len(meta['negative_checks'])}),flush=True)
if __name__=='__main__':main()
