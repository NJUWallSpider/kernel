#!/usr/bin/env python3
"""Independent actual test58 contract/identity/point review and exact replay.

No preparer or model-reader helpers are imported. This is audit evidence, not
an alternative trusted verifier. Existing production binary only; no rebuild.
"""
import hashlib
import json
import subprocess
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def load(p): return json.loads(Path(p).read_text())

def parse(path):
    names=[]; ids={}; rows=[]; senses={}; terms={}; rhs={}; cost={}; bounds={}; section=None; objective=None
    rhs_set=None; bound_set=None
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith('*'): continue
        t=line.split()
        if not line[0].isspace():
            section=t[0]
            assert section in ('NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA'), section
            if section=='ENDATA': break
            continue
        if section=='ROWS':
            if t[0]=='N': assert objective is None; objective=t[1]
            else:
                assert t[0] in ('L','E'); assert t[1] not in senses
                rows.append(t[1]); senses[t[1]]=t[0]; terms[t[1]]={}
        elif section=='COLUMNS':
            assert t[1].strip("'")!='MARKER'
            if t[0] not in ids:
                ids[t[0]]=len(names); names.append(t[0]); bounds[t[0]]=[Q(0),None,False]
            i=ids[t[0]]
            assert len(t)%2==1
            for name,c in zip(t[1::2],t[2::2]):
                d=cost if name==objective else terms[name]; d[i]=d.get(i,Q(0))+Q(c)
        elif section=='RHS':
            if rhs_set is None: rhs_set=t[0]
            assert rhs_set==t[0] and len(t)%2==1
            for name,c in zip(t[1::2],t[2::2]):
                assert name in senses and name not in rhs; rhs[name]=Q(c)
        elif section=='BOUNDS':
            if bound_set is None: bound_set=t[1]
            assert bound_set==t[1] and t[2] in ids
            if t[0]=='BV': assert len(t)==3; bounds[t[2]]=[Q(0),Q(1),True]
            elif t[0]=='FR': assert len(t)==3; bounds[t[2]]=[None,None,False]
            elif t[0]=='FX': assert len(t)==4; bounds[t[2]]=[Q(t[3]),Q(t[3]),False]
            else: raise AssertionError(('unexpected actual bound',t))
        else: raise AssertionError(('unexpected actual record',section,t))
    return {'names':names,'ids':ids,'rows':rows,'senses':senses,'terms':terms,'rhs':rhs,'cost':cost,'bounds':bounds}

def point(model,assignment):
    assert set(assignment)<=set(model['names'])
    values=[Q(assignment.get(name,'0')) for name in model['names']]
    for name,x in zip(model['names'],values):
        lo,hi,integer=model['bounds'][name]
        assert lo is None or x>=lo; assert hi is None or x<=hi
        assert not integer or x.denominator==1
    for row in model['rows']:
        value=sum(c*values[i] for i,c in model['terms'][row].items()); rhs=model['rhs'].get(row,Q(0))
        assert (value==rhs if model['senses'][row]=='E' else value<=rhs), row
    return sum(c*values[i] for i,c in model['cost'].items())

def chain(block):
    stages=[]
    while 'Return' not in block['end']:
        assert len(block['end'])==1
        kind,args=next(iter(block['end'].items())); stages.append(kind); block=args['body']
    return stages,block['end']['Return']

def main():
    case=ROOT/'cases/test58'; receipt=load(case/'preparation.json'); inventory=load(ROOT/'audit/corpus_inventory.json')
    actual=next(c for c in inventory['cases'] if c['case_id']=='test58'); run=Path(actual['run_directory'])
    identities={}; models={}
    for side,key in [('source','source_models'),('target','final_target_models')]:
        p=Path(receipt[side]['path']); assert p==run/actual[key][0]['path']
        assert sha(p)==receipt[side]['sha256']==actual[key][0]['sha256']; assert p.stat().st_size==actual[key][0]['bytes']
        identities[side]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}; models[side]=parse(p)
    for name,expected in receipt['artifacts'].items():
        p=case/name; assert sha(p)==expected['sha256'] and p.stat().st_size==expected['bytes']
        identities[name]={'path':str(p),**expected}
    kernel=Path(receipt['kernel_binary']['path']); assert sha(kernel)==receipt['kernel_binary']['sha256']
    assert sha(receipt['proof_preparer']['path'])==receipt['proof_preparer']['sha256']
    certificate=json.loads((case/'proof.rpa').read_text().split('\n',1)[1]); request=load(case/'request.json')
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[],'inverse':None},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}]
    assert certificate['claims']==request==claims and len(certificate['blocks'])==2
    assert not any(certificate.get(k) for k in ('points','bijections','improvements'))
    dimensions={}; obligations={}
    for side,m in models.items():
        counts={'variables':len(m['names']),'rows':len(m['rows']),'integers':sum(v[2] for v in m['bounds'].values()),'equalities':sum(x=='E' for x in m['senses'].values())}
        dimensions[side]=counts
        obligations[side]=sum(int(lo is not None)+int(hi is not None)+int(z) for lo,hi,z in m['bounds'].values())+len(m['rows'])+1
    assert dimensions=={'source':{'variables':2500,'rows':1750,'integers':1250,'equalities':500},'target':{'variables':607,'rows':785,'integers':303,'equalities':179}}
    stage_counts=[]
    for claim,block in zip(claims,certificate['blocks']):
        side='source' if claim['reverse'] else 'target'; stages,ret=chain(block)
        assert len(ret['map'])==dimensions[side]['variables'] and len(ret['checks'])==obligations[side]
        stage_counts.append({'output':side,'stages':stages,'complete_mapping_coordinates':len(ret['map']),'terminal_obligations':len(ret['checks'])})
    assert stage_counts[0]['stages']==['IntervalLift']*3+['SignedLift','SubflowLift']
    assert stage_counts[1]['stages']==['SignedLift']
    smoke=load(run/'output/smoke_witnesses.json'); assert smoke['source_sha256']==identities['source']['sha256'] and smoke['final_sha256']==identities['target']['sha256']
    points=[]
    for item in smoke['cases']:
        side='target' if item['model']=='reformulated.mps' else 'source'; assert item['model'] in ('reformulated.mps','../input/model.mps')
        value=point(models[side],item['assignment']); assert value==Q(item['objective'])
        points.append({'name':item['name'],'model':side,'all_actual_bounds_domains_rows_checked':True,'objective':str(value)})
    out=ROOT/'audit/validation/test58-complete-review'; out.mkdir(parents=True,exist_ok=True); commands=[]
    def invoke(args,wanted='VERIFIED'):
        r=subprocess.run([str(kernel)]+[str(x) for x in args],cwd=ROOT,text=True,capture_output=True)
        j=json.loads(r.stdout); commands.append({'command':[str(kernel)]+[str(x) for x in args],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        assert j['status']==wanted and r.returncode==(2 if wanted=='INVALID' else 0),(args,j)
        return j
    for side in ('source','target'):
        invoke(['canonical',identities[side]['path'],out/(side+'.mcm')],'CANONICALIZED'); assert sha(out/(side+'.mcm'))==identities[side+'.mcm']['sha256']
    invoke(['assemble',case/'proof.rpa',out/'proof.rpx'],'ASSEMBLED'); assert sha(out/'proof.rpx')==identities['proof.rpx']['sha256']
    result=invoke(['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',case/'request.json'])
    previous=json.loads(receipt['kernel_runs'][-1]['stdout']); assert previous['status']=='VERIFIED' and receipt['kernel_runs'][-1]['exit_code']==0
    assert result['claims']==2 and result['statistics']==previous['statistics'] and result['statistics']['obligations']==sum(obligations.values())==8448
    attacks=[]
    for attack in receipt['negative_checks']:
        name=attack['mutation']; assert sha(case/(name+'.rpa'))==attack['rpa_sha256'] and sha(case/(name+'.rpx'))==attack['rpx_sha256']
        assert attack['exit_code']==2 and attack['result']['status']=='INVALID'
        rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',case/(name+'.rpx'),case/'request.json'],'INVALID')
        attacks.append({'name':name,'status':rejected['status']})
    assert len(attacks)==8 and sha(kernel)==receipt['kernel_binary']['sha256']
    # Author's final verify command must bind precisely these submitted artifacts.
    argv=receipt['kernel_runs'][-1]['command']; assert argv[:2]==[str(kernel),'verify']
    assert [(ROOT/Path(x)).resolve() for x in argv[2:]]==[case/'source.mcm',case/'target.mcm',case/'proof.rpx',case/'request.json']
    report={'status':'PASS','scope':'Complete original test58 MI directional contract; independent exact MPS/point review and actual canonical/assembly/verification replay. No production edits or rebuild.',
      'protocol_status':receipt['protocol_status'],'dimensions':dimensions,'claims':claims,'stages':stage_counts,'original_report_contract_lines':[5,63,65,67],
      'interpretation':'Full feasibility equivalence and equal minimum objective; every target MI point has an equal-objective original lift. No LP relation, global bijection, or claimed optimum value.',
      'identities':identities,'kernel':receipt['kernel_binary'],'statistics':result['statistics'],'seven_independent_fraction_points':points,'eight_actual_negative_replays':attacks,
      'commands':commands,'reviewed_files':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),case/'preparation.json',ROOT/'tools/prepare_test58_full.py',ROOT/'tools/prepare_test58.py',ROOT/'audit/SUBFLOW_PRODUCTION_REVIEW.md']},
      'limits':['Subflow mathematical existence trust is covered by the separately authored production review; this is not a formal proof of the kernel.','Independent Fraction points corroborate examples; full universal claims are established by the actual kernel certificate.','Functional execution with possible concurrent work is not a benchmark.']}
    (ROOT/'audit/TEST58_COMPLETE_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({'status':report['status'],'claims':len(claims),'points':len(points),'attacks':len(attacks),'obligations':8448},indent=2))

if __name__=='__main__': main()
