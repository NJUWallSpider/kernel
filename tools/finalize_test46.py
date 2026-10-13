#!/usr/bin/env python3
"""Join all actual test46 directions, replay fixed request and preserve attacks."""
import argparse,gc,hashlib,json,subprocess,time
from fractions import Fraction as Q
from pathlib import Path


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/validation-wave-rpx-2026-10-11/release/rpx'));args=ap.parse_args();root=Path('cases/test46');kernel=args.kernel.resolve();parts=[root/'mi-forward',root/'mi-reverse',root/'lp-only']
    assert all(json.loads((p/'preparation.json').read_text()).get('partial_claim_status')=='VERIFIED' for p in parts)
    claims=[json.loads((p/'request.json').read_text())[0] for p in parts];request=root/'request.json';request.write_text(json.dumps(claims,separators=(',',':'))+'\n')
    # Preserve exact author-emitted block text without simultaneously loading
    # the large three proof object trees into the Python heap.
    with (root/'proof.rpa').open('wb') as out:
        out.write(b'RPA 5\n{"claims":');out.write(json.dumps(claims,separators=(',',':')).encode());out.write(b',"blocks":[')
        for k,p in enumerate(parts):
            raw=(p/'proof.rpa').read_bytes();tag=b',"blocks":[';start=raw.index(tag)+len(tag);suffix=raw.rstrip();assert suffix.endswith(b']}')
            if k:out.write(b',')
            out.write(suffix[start:-2])
        out.write(b']}\n')
    runpath=Path('/Users/bhz/Code/reform_test/runs/test46-nomf-B1')
    meta={'case_id':'test46','status':'PROOF_NOT_COMPLETED','contract':'Complete actual MI retained-coordinate projection equality with equal objective in both directions; complete actual LP target-to-source inclusion with equal objective. No strict LP or optimum claim.','protocol_status':'Existing RPA/RPX 5 interval semantics; no new production rule or version.','source':{'path':str(runpath/'input/model.mps'),'sha256':sha(runpath/'input/model.mps')},'target':{'path':str(runpath/'output/reformulated.mps'),'sha256':sha(runpath/'output/reformulated.mps')},'kernel_binary':{'path':str(kernel),'sha256':sha(kernel)},'work_policy':1000000000,'kernel_runs':[],'partial_receipts':[str(p/'preparation.json') for p in parts],'attacks':[],'timing_context':'Functional replay while author work may run concurrently; not an isolated benchmark.'}
    def save():(root/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
    def run(argv):
        before=sha(kernel);t=time.perf_counter();r=subprocess.run([str(kernel)]+[str(a) for a in argv],capture_output=True,text=True);x={'command':[str(kernel)]+[str(a) for a in argv],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'wall_seconds':time.perf_counter()-t,'binary_sha256_before':before,'binary_sha256_after':sha(kernel)};assert x['binary_sha256_before']==x['binary_sha256_after'];return x
    ar=run(['assemble',root/'proof.rpa',root/'proof.rpx']);meta['kernel_runs'].append(ar);save()
    if ar['exit_code']:
        assert json.loads(ar['stdout'])['status']=='RESOURCE_LIMIT',ar
        assert (root/'proof.rpa').stat().st_size>256*1024*1024,ar
        (root/'proof.rpa').rename(root/'combined-attempt.rpa')
        request.rename(root/'combined-request.json')
        meta['delivery']='Three complete directional certificates bound to one actual source/target pair; combined RPA exceeds the unchanged 256 MiB assembler text limit.'
        meta['combined_attempt']={'path':str(root/'combined-attempt.rpa'),'bytes':(root/'combined-attempt.rpa').stat().st_size,'sha256':sha(root/'combined-attempt.rpa'),'assembly':ar}
        directions=[];stats={}
        for k,p in enumerate(parts):
            r=run(['verify',root/'source.mcm',root/'target.mcm',p/'proof.rpx',p/'request.json']);meta['kernel_runs'].append(r);save();assert r['exit_code']==0,r
            result=json.loads(r['stdout']);stat=result['statistics']
            for name,value in stat.items():stats[name]=max(stats.get(name,0),value) if name=='peak_live_facts' else stats.get(name,0)+value
            old=run(['verify','--work','100000000',root/'source.mcm',root/'target.mcm',p/'proof.rpx',p/'request.json'])
            directions.append({'direction':k,'claim_summary':{**{key:value for key,value in claims[k].items() if key!='projection'},'projection_count':len(claims[k]['projection'])},'rpa':str(p/'proof.rpa'),'rpx':str(p/'proof.rpx'),'request':str(p/'request.json'),'artifacts':{f:{'bytes':(p/f).stat().st_size,'sha256':sha(p/f)} for f in ['proof.rpa','proof.rpx','request.json']},'verify':r,'former_100m_run':old})
        bundle={'format':'actual-model-direction-bundle-v1','case_id':'test46','source':{'path':str(root/'source.mcm'),'sha256':sha(root/'source.mcm')},'target':{'path':str(root/'target.mcm'),'sha256':sha(root/'target.mcm')},'directions':directions,'meaning':'All three listed complete claims must pass against the same exact source and target; no single direction represents the whole contract.'}
        (root/'bundle.json').write_text(json.dumps(bundle,indent=2)+'\n');meta['bundle']='cases/test46/bundle.json';meta['directional_replays']=directions;meta['former_100m_runs']=[d['former_100m_run'] for d in directions]
    else:
        r=run(['verify',root/'source.mcm',root/'target.mcm',root/'proof.rpx',request]);meta['kernel_runs'].append(r);save();assert not r['exit_code'],r
        stats=json.loads(r['stdout'])['statistics'];meta['former_100m_run']=run(['verify','--work','100000000',root/'source.mcm',root/'target.mcm',root/'proof.rpx',request])
    meta['status']='VERIFIED';meta['statistics']=stats;meta['exceeds_former_100m_work']=stats['work']>100000000;save()
    attackdir=root/'attacks';attackdir.mkdir(exist_ok=True)
    specs=[
      ('wrong_round_integrality',0,'The aggregate forbidden-selector rounding uses an unrelated single variable INT.',lambda c: replace(next(s['Round'] for s in c['blocks'][0]['steps'] if 'Round' in s),'integer',{'VarInt':0})),
      ('missing_target_row',0,'One complete target row/observation check is removed.',lambda c: remove(c['blocks'][0]['end']['Return']['checks'],122498+12)),
      ('lp_borrow_integer',0,'The forward claim is switched to LP input while retaining source-integer proof premises.',lambda c: replace(c['claims'][0],'input_integers',False)),
      ('missing_interval_premise',1,'One middle joint interval omits an upper-versus-lower premise.',lambda c: remove(c['blocks'][0]['end']['IntervalLift']['intervals'][8000]['checks'],2)),
      ('wrong_constant_helper',1,'One removed source constant table cost helper is mapped to 18 instead of 17.',lambda c: replace(next(e for e in c['blocks'][0]['end']['IntervalLift']['body']['end']['Return']['map'] if e['constant']=='17' and not e['terms']),'constant','18')),
      ('wrong_lp_corner',2,'One LP corner reconstruction constant is perturbed, breaking its source table.',lambda c: perturb_corner(c)),
    ]
    cert=None;loaded=None
    for name,idx,reason,mutate in specs:
        if loaded!=idx:
            cert=None;gc.collect();cert=json.loads((parts[idx]/'proof.rpa').read_text().split('\n',1)[1]);loaded=idx
        undo=mutate(cert);pa=attackdir/(name+'.rpa');px=attackdir/(name+'.rpx');rq=attackdir/(name+'.request.json')
        with pa.open('w') as f:f.write('RPA 5\n');json.dump(cert,f,separators=(',',':'));f.write('\n')
        rq.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n');undo()
        ar=run(['assemble',pa,px]);runs=[ar]
        if ar['exit_code']==0:runs.append(run(['verify',root/'source.mcm',root/'target.mcm',px,rq]))
        result=json.loads(runs[-1]['stdout']);assert result['status']=='INVALID',(name,runs)
        receipt={'name':name,'reason':reason,'base_direction':idx,'status':'INVALID','runs':runs,'artifacts':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in (pa,rq,px) if p.exists()}}
        (attackdir/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');meta['attacks'].append({'name':name,'status':'INVALID','receipt':str(attackdir/(name+'.json'))});save();print(name,'INVALID',flush=True)
    meta['artifacts']={n:{'bytes':(root/n).stat().st_size,'sha256':sha(root/n)} for n in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json','oracle.json','structure.json','bundle.json','combined-attempt.rpa','combined-request.json'] if (root/n).exists()};meta['kernel_binary_sha256']=sha(kernel);meta['preparers']={str(p):sha(p) for p in [Path('tools/prepare_test46.py'),Path('tools/prepare_test46_full.py'),Path(__file__),Path('tools/oracle_test46.py')]};meta['attack_status']='ALL_6_INVALID';meta['completion_kind']='same-model-pair-directional-bundle' if 'bundle' in meta else 'single-certificate';meta['complete_claim_count']=3;meta['verification_results']={'kind':'three-independent-complete-request-replays' if 'bundle' in meta else 'single-complete-request-replay','manifest':meta.get('bundle'),'all_directions_verified':True,'all_actual_models_identical':True,'not_a_single_kernel_invocation':'bundle' in meta};save();print(json.dumps({'status':meta['status'],'statistics':stats,'attacks':len(meta['attacks'])}),flush=True)
def perturb_corner(c):
    e=next(e for e in c['blocks'][0]['end']['IntervalLift']['body']['end']['Return']['map'] if len(e['terms'])>2 and any(i>=61036 for i,v in e['terms']))
    return replace(e,'constant',str(Q(e['constant'])+1))
def replace(obj,key,new):
    old=obj[key];obj[key]=new
    return lambda:obj.__setitem__(key,old)
def remove(seq,idx):
    old=seq.pop(idx)
    return lambda:seq.insert(idx,old)
if __name__=='__main__':main()
