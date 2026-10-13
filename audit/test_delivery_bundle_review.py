#!/usr/bin/env python3
"""Small independent bookkeeping fixtures; none is a mathematical certificate.

Copies the reviewed tools into disposable fixture roots, so ledger tests never
write the real acceptance ledger. Fake verifier replies test process bookkeeping
only; actual model/proof acceptance remains the responsibility of kernel replay.
"""
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/fixtures/delivery_bundle_review'
TOOLS=['case_delivery.py','prepare_affine.py','prepare_test40.py','run_acceptance.py']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d): Path(p).write_text(json.dumps(d,indent=2)+'\n')
def load(p): return json.loads(Path(p).read_text())
def ident(p): return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def stats(items):
    replies=[json.loads(x['verify']['stdout'])['statistics'] for x in items]
    return {k:(max(x[k] for x in replies) if k=='peak_live_facts' else sum(x[k] for x in replies)) for k in replies[0]}

def fixture(label,bundle=True):
    root=OUT/label
    if root.exists(): shutil.rmtree(root)
    (root/'tools').mkdir(parents=True); (root/'audit').mkdir(); (root/'crates').mkdir()
    for filename in TOOLS: shutil.copy2(ROOT/'tools'/filename,root/'tools'/filename)
    (root/'Cargo.lock').write_text('BOOKKEEPING FIXTURE ONLY\n')
    kernel=root/'target/validation-fixture/release/rpx'; kernel.parent.mkdir(parents=True)
    kernel.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
cfg=json.loads((root/'mock-control.json').read_text())
request=Path(sys.argv[-1]); q=json.loads(request.read_text()); q={'claims':q} if isinstance(q,list) else q
bad=request.parent.name==cfg.get('piece')
result={'status':cfg.get('status','VERIFIED') if bad else 'VERIFIED','statistics':{'work':1,'obligations':1,'peak_live_facts':1}}
result.update({k:len(q.get(k,[])) for k in ('claims','points','bijections','improvements')})
print(json.dumps(result));sys.exit(cfg.get('exit_code',0) if bad else 0)
'''); kernel.chmod(0o755);dump(root/'mock-control.json',{})
    case=root/'cases/mock';case.mkdir(parents=True)
    for name in ['source.mcm','target.mcm','source.mps','target.mps']:(case/name).write_text('MOCK BOOKKEEPING BYTES '+name+'\n')
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None},
            {'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[],'inverse':None}]
    items=[]
    for j in range(3 if bundle else 1):
        piece=case/f'p{j}' if bundle else case;piece.mkdir(exist_ok=True)
        (piece/'proof.rpa').write_text('MOCK RPA '+str(j)+'\n');(piece/'proof.rpx').write_bytes(b'MOCK RPX '+bytes([j]))
        dump(piece/'request.json',[claims[j]])
        reply={'status':'VERIFIED','claims':1,'points':0,'bijections':0,'improvements':0,'statistics':{'work':[2,5,7][j],'obligations':[3,4,5][j],'peak_live_facts':[11,17,13][j]}}
        item={'direction':j,**{k:str(piece/name) for k,name in [('rpa','proof.rpa'),('rpx','proof.rpx'),('request','request.json')]},
              'artifacts':{name:ident(piece/name) for name in ['proof.rpa','proof.rpx','request.json']},
              'verify':{'command':[str(kernel),'verify',str(case/'source.mcm'),str(case/'target.mcm'),str(piece/'proof.rpx'),str(piece/'request.json')],'exit_code':0,'stdout':json.dumps(reply),'stderr':''}}
        items.append(item)
    d={'case_id':'mock','status':'VERIFIED','source':ident(case/'source.mps'),'target':ident(case/'target.mps'),'kernel_binary':ident(kernel),
       'artifacts':{name:ident(case/name) for name in ['source.mcm','target.mcm']},'kernel_runs':[items[-1]['verify']]}
    if bundle:
        dump(case/'combined-request.json',claims)
        d.update(bundle=str(case/'bundle.json'),completion_kind='same-model-pair-directional-bundle',directional_replays=items,complete_claim_count=3,statistics=stats(items))
        manifest={'format':'actual-model-direction-bundle-v1','case_id':'mock','source':ident(case/'source.mcm'),'target':ident(case/'target.mcm'),'directions':items}
        dump(case/'bundle.json',manifest);d['artifacts'].update({n:ident(case/n) for n in ['combined-request.json','bundle.json']})
    else: d['artifacts'].update(items[0]['artifacts'])
    dump(case/'preparation.json',d)
    inv={'cases':[{'case_id':'mock','run_name':'mock','families':['fixture'],'status':'PROOF_NOT_COMPLETED','status_reason':'synthetic bookkeeping only','source_models':[ident(case/'source.mps')],'final_target_models':[ident(case/'target.mps')]}],
         'summary':{'model_pair_present_count':1},'family_definitions':{'fixture':'mock'}}
    dump(root/'audit/corpus_inventory.json',inv)
    request_paths=[Path(x['request']) for x in items]+([case/'combined-request.json'] if bundle else [])
    gate={'status':'REVIEWED_COMPLETE_REQUEST','requests':[ident(p) for p in request_paths]}
    dump(root/'audit/contract_scope_gates.json',{'schema':'rpx-original-contract-scope-gates-v1','cases':{'mock':gate}})
    return root,case,d

def sync(case,d,items=None):
    if items is not None:
        d['directional_replays']=items;m=load(case/'bundle.json');m['directions']=items;dump(case/'bundle.json',m);d['artifacts']['bundle.json']=ident(case/'bundle.json')
    dump(case/'preparation.json',d)

def module(root):
    spec=importlib.util.spec_from_file_location('delivery_'+root.name,root/'tools/case_delivery.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def invoke(root,script,*args):
    r=subprocess.run([sys.executable,str(root/'tools'/script),*args],cwd=root,capture_output=True,text=True)
    return {'command':[sys.executable,str(root/'tools'/script),*args],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'README.md').write_text('# Delivery bookkeeping fixtures\n\nAll model/proof bytes and verifier replies in this directory are deliberately synthetic. They test receipt/ledger/replay control flow only. They are not kernel certificates and are never included in the real cases directory or ledger.\n')
    results=[]
    root,case,d=fixture('valid_three_directions');delivery=module(root).load_delivery(case)
    assert len(delivery['pieces'])==3 and delivery['request']==load(case/'combined-request.json')
    assert delivery['verification']['not_a_single_kernel_invocation'] is True
    assert delivery['verification']['statistics_sum_and_peak_max']=={'work':14,'obligations':12,'peak_live_facts':17}
    results.append({'fixture':root.name,'expected':'valid complete three-piece conjunction','status':'PASS'})

    def reject(label,mutate):
        root,case,d=fixture(label);mutate(case,d);sync(case,d)
        try: module(root).load_delivery(case)
        except (AssertionError,FileNotFoundError,KeyError,ValueError) as e:
            results.append({'fixture':label,'expected':'metadata rejection','status':'PASS','exception':type(e).__name__,'detail':str(e)});return
        raise AssertionError(('unexpected bookkeeping acceptance',label))

    def drop_middle(case,d):
        items=[d['directional_replays'][0],d['directional_replays'][2]];items[1]['direction']=1;d['statistics']=stats(items);sync(case,d,items)
    reject('missing_middle_direction_renumbered',drop_middle)
    def only_manifest(case,d):
        m=load(case/'bundle.json');m['directions'].pop(1);dump(case/'bundle.json',m);d['artifacts']['bundle.json']=ident(case/'bundle.json')
    reject('missing_middle_manifest_only',only_manifest)
    def request_changed(case,d,rehash):
        item=d['directional_replays'][1];path=Path(item['request']);q=load(path);q[0]['objective']='NonIncreasing';dump(path,q)
        if rehash:item['artifacts']['request.json']=ident(path);sync(case,d,d['directional_replays'])
    reject('changed_request_stale_hash',lambda c,d:request_changed(c,d,False))
    reject('changed_request_rehashed_but_complete_request_fixed',lambda c,d:request_changed(c,d,True))
    def wrong_path(case,d):
        item=d['directional_replays'][1];p=case/'same-bytes-other-proof.rpx';shutil.copy2(item['rpx'],p);item['rpx']=str(p);item['artifacts']['proof.rpx']=ident(p);sync(case,d,d['directional_replays'])
    reject('same_bytes_changed_path_receipt_unbound',wrong_path)
    def run_change(case,d,change):
        change(d['directional_replays'][1]['verify']);sync(case,d,d['directional_replays'])
    reject('receipt_wrong_source',lambda c,d:run_change(c,d,lambda r:r['command'].__setitem__(2,str(c/'target.mcm'))))
    reject('receipt_nonzero_exit',lambda c,d:run_change(c,d,lambda r:r.__setitem__('exit_code',2)))
    def response(run,key,value):
        q=json.loads(run['stdout']);q[key]=value;run['stdout']=json.dumps(q)
    reject('receipt_wrong_status',lambda c,d:run_change(c,d,lambda r:response(r,'status','INVALID')))
    reject('receipt_wrong_claim_count',lambda c,d:run_change(c,d,lambda r:response(r,'claims',0)))
    reject('aggregate_peak_was_summed',lambda c,d:d['statistics'].__setitem__('peak_live_facts',41))
    reject('missing_middle_rpa',lambda c,d:Path(d['directional_replays'][1]['rpa']).unlink())
    def cross_file_inverse(case,d):
        item=d['directional_replays'][1];p=Path(item['request']);q=load(p);q[0]['inverse']=0;dump(p,q);item['artifacts']['request.json']=ident(p)
        combined=load(case/'combined-request.json');combined[1]=q[0];dump(case/'combined-request.json',combined);d['artifacts']['combined-request.json']=ident(case/'combined-request.json');sync(case,d,d['directional_replays'])
    reject('cross_file_inverse_is_not_standalone',cross_file_inverse)

    # Execute copied real refresh_acceptance, with only fake isolated ledgers.
    for label,variant in [('scope_exact_piece_set','exact'),('scope_empty_requests','empty'),('scope_unrelated_intact_request','unrelated'),('scope_omits_middle_request','missing')]:
        root,case,d=fixture(label);sp=root/'audit/contract_scope_gates.json';scope=load(sp);gate=scope['cases']['mock']
        if variant=='empty':gate['requests']=[]
        elif variant=='unrelated':
            p=root/'formerly-reviewed-request.json';dump(p,[{'old_scope':'intact but unrelated'}]);gate['requests']=[ident(p)]
        elif variant=='missing':gate['requests'].pop(1)
        dump(sp,scope)
        # Literal prior predicate from the reviewed source before root's fix.
        before=gate['status']=='REVIEWED_COMPLETE_REQUEST' and all(Path(x['path']).exists() and sha(x['path'])==x['sha256'] for x in gate.get('requests',[]))
        r=invoke(root,'prepare_affine.py','--acceptance');assert r['exit_code']==0,r
        accepted=load(root/'audit/acceptance.json')['cases'][0]['status'];assert accepted==('VERIFIED' if variant=='exact' else 'PROOF_NOT_COMPLETED')
        assert before is True
        results.append({'fixture':label,'status':'PASS','old_predicate_scope_complete':before,'new_actual_refresh_status':accepted,'run':r})

    # Replay every direction and expose nonzero exits rather than relying solely
    # on a result string. Mock executable is clearly scoped to these fixtures.
    for label,cfg,bundle in [('runner_complete_bundle',{},True),('runner_middle_invalid',{'piece':'p1','status':'INVALID','exit_code':2},True),('runner_middle_nonzero_verified',{'piece':'p1','status':'VERIFIED','exit_code':1},True),('runner_single_nonzero_verified',{'piece':'mock','status':'VERIFIED','exit_code':1},False)]:
        root,case,d=fixture(label,bundle);dump(root/'mock-control.json',cfg);r=invoke(root,'run_acceptance.py','--label','fixture','--skip-build');report=load(root/'audit/validation/fixture/run.json')
        assert len(report['commands'])==(3 if bundle else 1)
        observed=report['all_replayed_verified'];expected=not cfg
        entry={'fixture':label,'status':'PASS' if observed==expected else 'FINDING','expected_all_replayed_verified':expected,'observed_all_replayed_verified':observed,'process_exit':r['exit_code'],'run':r}
        if bundle:
            item=report['replayed'][0];assert len(item['pieces'])==3 and item['result']['not_a_single_kernel_invocation'] is True
            assert (r['exit_code']==0)==expected
        results.append(entry)
    # Python optimization must not silently erase receipt validation. The old
    # helper snapshot is kept by the author; exercise it only on synthetic bytes.
    root,case,d=fixture('optimized_mode_rejected');request_changed(case,d,False);sync(case,d)
    old=ROOT/'audit/checkpoints/case_delivery-before-optimized-mode-guard.py'
    source='import importlib.util,sys; s=importlib.util.spec_from_file_location("review",sys.argv[1]); m=importlib.util.module_from_spec(s);s.loader.exec_module(m); print(m.load_delivery(sys.argv[2])["verification"]["status"])'
    before=subprocess.run([sys.executable,'-O','-c',source,str(old),str(case)],capture_output=True,text=True)
    assert before.returncode==0 and before.stdout.strip()=='VERIFIED'
    for entry,args in [('helper',['-c',source,str(root/'tools/case_delivery.py'),str(case)]),('refresh',[str(root/'tools/prepare_affine.py'),'--acceptance']),('replay',[str(root/'tools/run_acceptance.py'),'--label','fixture','--skip-build'])]:
        command=[sys.executable,'-O',*args];r=subprocess.run(command,cwd=root,capture_output=True,text=True)
        assert r.returncode!=0 and 'RuntimeError' in r.stderr and not (root/'audit/acceptance.json').exists()
        results.append({'fixture':'optimized_mode_'+entry,'status':'PASS','before_guard_accepts_changed_request':True,'after_guard_exit':r.returncode,'command':command,'stdout':r.stdout,'stderr':r.stderr,'old_helper_sha256':sha(old)})
    identities={str(ROOT/'tools'/name):sha(ROOT/'tools'/name) for name in TOOLS}
    report={'status':'PASS' if all(x['status']=='PASS' for x in results) else 'FINDINGS','scope':'Independent synthetic bookkeeping fixtures only; no fake receipt is mathematical evidence or placed in actual corpus acceptance.','reviewed_tools':identities,'tests':results,'fixture_count':len(results)}
    dump(ROOT/'audit/DELIVERY_BUNDLE_FIXTURES.json',report);print(json.dumps({'status':report['status'],'fixtures':len(results),'findings':[x['fixture'] for x in results if x['status']=='FINDING']},indent=2))

if __name__=='__main__':main()
