#!/usr/bin/env python3
"""Independent actual test36 scope, Fraction structure, identity and replay.

No preparer/parser helper imports; no production edits or release rebuild.
Avoid materializing the 262 MB RPA as a Python proof tree: the actual assembler
and verifier already bind its complete semantics, while its bytes are hashed.
"""
from collections import Counter,defaultdict,deque
from fractions import Fraction as Q
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def parse(p):
    names=[];ids={};rows=[];senses={};terms={};rhs={};bounds={};objective=None;cost={};section=None;integer=False;rhs_set=None;bound_set=None
    for line in Path(p).read_text().splitlines():
        if not line.strip() or line.startswith('*'):continue
        t=line.split()
        if not line[0].isspace():
            section=t[0];assert section in ('NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA')
            if section=='ENDATA':break
            continue
        if section=='ROWS':
            if t[0]=='N':assert objective is None;objective=t[1]
            else:assert t[0] in ('E','L') and t[1] not in terms;rows.append(t[1]);senses[t[1]]=t[0];terms[t[1]]={}
        elif section=='COLUMNS':
            if t[1].strip("'")=='MARKER':
                tag=t[2].strip("'");assert tag in ('INTORG','INTEND') and integer!=(tag=='INTORG');integer=tag=='INTORG';continue
            if t[0] not in ids:ids[t[0]]=len(names);names.append(t[0]);bounds[t[0]]=[Q(0),None,integer]
            assert bounds[t[0]][2]==integer and len(t)%2==1
            i=ids[t[0]]
            for name,c in zip(t[1::2],t[2::2]):
                d=cost if name==objective else terms[name];d[i]=d.get(i,Q(0))+Q(c)
        elif section=='RHS':
            if rhs_set is None:rhs_set=t[0]
            assert t[0]==rhs_set and len(t)%2==1
            for name,c in zip(t[1::2],t[2::2]):assert name in terms and name not in rhs;rhs[name]=Q(c)
        elif section=='BOUNDS':
            if bound_set is None:bound_set=t[1]
            assert t[1]==bound_set and t[0]=='UP' and len(t)==4 and Q(t[3])==1
            assert bounds[t[2]][2] and bounds[t[2]][1] is None;bounds[t[2]][1]=Q(1)
        else:raise AssertionError(section)
    assert not integer
    for name in names:
        lo,hi,z=bounds[name];assert lo==0 and (hi==1 if z else hi is None)
    return {'names':names,'ids':ids,'rows':rows,'senses':senses,'terms':terms,'rhs':rhs,'bounds':bounds,'cost':cost}

def feasible(m,values):
    assert len(values)==len(m['names'])
    for name,x in zip(m['names'],values):
        lo,hi,z=m['bounds'][name];assert x>=lo and (hi is None or x<=hi) and (not z or x.denominator==1)
    for row in m['rows']:
        v=sum(c*values[i] for i,c in m['terms'][row].items())
        assert v==m['rhs'][row] if m['senses'][row]=='E' else v<=m['rhs'][row]
    return sum(c*values[i] for i,c in m['cost'].items())

def main():
    case=ROOT/'cases/test36';d=load(case/'preparation.json');inv=next(c for c in load(ROOT/'audit/corpus_inventory.json')['cases'] if c['case_id']=='test36')
    identities={}
    for side,key in [('source','source_models'),('target','final_target_models')]:
        p=Path(d[side]['path']);assert p==Path(inv['run_directory'])/inv[key][0]['path'];assert sha(p)==d[side]['sha256']==inv[key][0]['sha256'];identities[side]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
    for name,item in d['artifacts'].items():
        p=case/name;assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'];identities[name]={'path':str(p),**item}
    for name,digest in d['preparers'].items():assert sha(ROOT/name)==digest
    a,b=parse(d['source']['path']),parse(d['target']['path']);assert (len(a['names']),len(b['names']),len(a['rows']),len(b['rows']))==(37816,37616,37617,37617)
    bits={i for i,name in enumerate(a['names']) if a['bounds'][name][2]};assert len(bits)==200
    eq=[r for r in a['rows'] if a['senses'][r]=='E'];assert len(eq)==1 and a['rhs'][eq[0]]==195 and a['terms'][eq[0]]=={i:Q(1) for i in bits}
    records={};successors={}
    for row in a['rows']:
        if row==eq[0]:continue
        t=a['terms'][row];assert a['senses'][row]=='L' and a['rhs'][row]==1 and len(t)==3
        negative=[i for i,c in t.items() if c==-1];positive=[i for i,c in t.items() if c==1];assert len(negative)==1 and len(positive)==2
        z=negative[0];assert z not in records and z not in bits
        parent=[i for i in positive if i not in bits];assert len(parent)<=1
        parent=parent[0] if parent else None
        if parent is not None:assert parent not in successors;successors[parent]=z
        records[z]={'row':row,'parent':parent,'bits':[i for i in positive if i in bits]}
    assert set(records)|bits==set(range(len(a['names']))) and set(successors)<=set(records)
    terminals=set(records)-set(successors);assert len(terminals)==200
    retained={i:b['ids'][name] for i,name in enumerate(a['names']) if name in b['ids']}
    assert set(retained)==set(range(len(a['names'])))-terminals
    for i,j in retained.items():assert a['bounds'][a['names'][i]]==b['bounds'][b['names'][j]]
    assert all(a['bounds'][a['names'][z]]==[Q(0),None,False] for z in terminals)
    assert a['cost']=={i:Q(4850 if i in terminals else 1) for i in range(len(a['names']))} and b['cost']=={j:Q(1) for j in range(len(b['names']))}
    assert a['rows']==b['rows'] and a['senses']==b['senses'] and a['rhs']==b['rhs']
    for row in a['rows']:assert b['terms'][row]=={retained[i]:c for i,c in a['terms'][row].items() if i in retained},row
    # Full-field equality proves the target is exactly the source's zero-terminal
    # face in retained coordinates; it is not an added global projection claim.
    order=[];ready=deque(z for z,r in records.items() if r['parent'] is None);prefix={};bitpos={i:j for j,i in enumerate(sorted(bits))};layers=defaultdict(list)
    while ready:
        z=ready.popleft();r=records[z];mask=0 if r['parent'] is None else prefix[r['parent']]
        for i in r['bits']:assert not mask&(1<<bitpos[i]);mask|=1<<bitpos[i]
        prefix[z]=mask;layers[bin(mask).count('1')].append(z);order.append(z)
        if z in successors:ready.append(successors[z])
    assert len(order)==len(records) and max(layers)==191
    layer_bounds=[]
    for depth in range(2,28):
        zs=layers[depth];assert len(zs)==200
        freq=[sum(bool(prefix[z]&(1<<bitpos[i])) for z in zs) for i in sorted(bits)];top=sorted(freq,reverse=True)[:5]
        layer_bounds.append({'prefix_size':depth,'prefix_count':len(zs),'top_five':top,'lower_bound':200-sum(top)})
    assert sum(x['lower_bound'] for x in layer_bounds)==2238 and 2238+195+4850-6425==858
    zeros={'x96','x115','x74','x45','x149'};assert zeros<=set(a['names'])
    values=[Q(0)]*len(a['names'])
    for i in bits:values[i]=Q(a['names'][i] not in zeros)
    for z in order:
        r=records[z];values[z]=max(Q(0),sum(values[i] for i in r['bits'])+(values[r['parent']] if r['parent'] is not None else 0)-1)
    assert all(values[z]==0 for z in terminals) and feasible(a,values)==6425
    target_values=[Q(0)]*len(b['names'])
    for i,j in retained.items():target_values[j]=values[i]
    assert feasible(b,target_values)==6425
    request=load(case/'request.json');assert len(request['claims'])==3 and len(request['improvements'])==1 and not request.get('points') and not request.get('bijections')
    expected=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[],'inverse':None},{'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}]
    ic=request['improvements'][0];assert ic=={'target':False,'integers':True,'positive':{'constant':'0','terms':[[z,'1'] for z in sorted(terminals)]}}
    expected[1]['projection']=[[j,i] for i,j in retained.items()]
    expected.append({'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[i,j] for i,j in retained.items()],'inverse':None,'input_halfspace':ic['positive']})
    assert request['claims']==expected and len(expected[1]['projection'])==len(expected[2]['projection'])==37616
    control_path=case/'attempts/positive_terminal.rpa';control=json.loads(control_path.read_text().split('\n',1)[1]);cv=[Q(x) for x in control['points'][0]['values']]
    assert feasible(a,cv)==6426 and sum(cv[z] for z in terminals)==Q(1,4850)
    kernel=Path(d['kernel_binary']['path']);assert sha(kernel)==d['kernel_binary']['sha256'];commands=[]
    out=ROOT/'audit/validation/test36-complete-review';out.mkdir(parents=True,exist_ok=True)
    def invoke(args,status='VERIFIED'):
        r=subprocess.run([str(kernel)]+[str(x) for x in args],cwd=ROOT,capture_output=True,text=True);j=json.loads(r.stdout)
        commands.append({'command':[str(kernel)]+[str(x) for x in args],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        assert r.returncode==0 and j['status']==status,(args,j);return j
    for side in ('source','target'):
        invoke(['canonical',d[side]['path'],out/(side+'.mcm')],'CANONICALIZED');assert sha(out/(side+'.mcm'))==d['artifacts'][side+'.mcm']['sha256']
    result=invoke(['verify',out/'source.mcm',out/'target.mcm',case/'proof.rpx',case/'request.json'])
    assert result['claims']==3 and result['improvements']==1 and result['statistics']==d['statistics']
    source_checks=600+37616+37617+1;target_checks=600+37416+37617+1
    assert 3*source_checks+3*target_checks+2*37616==result['statistics']['obligations']==529636
    invoke(['assemble',control_path,out/'positive_terminal.rpx'],'ASSEMBLED');assert sha(out/'positive_terminal.rpx')==sha(case/'attempts/positive_terminal.rpx')
    invoke(['verify',out/'source.mcm',out/'target.mcm',out/'positive_terminal.rpx',case/'attempts/positive_terminal_request.json'])
    attacks=[];small_replayed=0
    for item in d['negative_checks']:
        ar=load(ROOT/item['receipt']);last=ar['runs'][-1];assert item['status']==ar['status']==json.loads(last['stdout'])['status']=='INVALID' and last['exit_code']!=0
        assert sha(ROOT/ar['request'])==ar['request_sha256']
        for run in ar['runs']:assert run['binary_sha256_before']==run['binary_sha256_after']==d['kernel_binary']['sha256']
        replayed=False
        if item['mutation'] in ('missing_halfspace','reversed_halfspace','incomplete_terminal_halfspace','missing_projection_obligation','borrow_old_row_as_halfspace','wrong_reverse_projection'):
            command=last['command'];assert command[0]==str(kernel) and command[1]=='verify'
            p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);answer=json.loads(p.stdout)
            assert p.returncode==2 and answer['status']=='INVALID'
            commands.append({'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});replayed=True;small_replayed+=1
        attacks.append({'mutation':item['mutation'],'status':'INVALID','receipt_sha256':sha(ROOT/item['receipt']),'independently_replayed':replayed})
    assert len(attacks)==15 and small_replayed==6 and sha(kernel)==d['kernel_binary']['sha256']
    last=d['kernel_runs'][-1];assert last['exit_code']==0 and json.loads(last['stdout'])['statistics']==result['statistics']
    assert last['command']==[str(kernel),'verify','cases/test36/source.mcm','cases/test36/target.mcm','cases/test36/proof.rpx','cases/test36/request.json']
    report={'status':'PASS_COMPLETE_ORIGINAL_CONTRACT','protocol_status':d['protocol_status'],'scope':'Complete minimum-preserving directions, universal original-terminal optimizer exclusion, and caller-bound exact retained-coordinate optimal projection/recovery.','identity':identities,'kernel':d['kernel_binary'],
      'request':request,'all200_original_terminal_coordinates_continuous_nonnegative':True,'target_exactly_source_zero_terminal_face_all_fields':True,
      'optimal_projection_consequence':'Strict improvement rules out P>0 at every attained source minimizer. The additional caller-bound P<=0 direction therefore applies to every such point and supplies one complete target point with equal objective and all 37616 original retained coordinates unchanged. Unconditional minimum/recovery directions identify optimum values; reverse Equal with every retained observation sends each target minimizer back to a source minimizer. This uses the explicit kernel claims, not the auxiliary external zero-face matrix comparison.',
      'previous_scope_gap_closed_by':'Claim index2 has the complete original-terminal predicate as input_halfspace, Equal objective, and all37616 retained coordinate observations; claim index1 now includes all37616 reverse observations. Original strict predicate and unconditional forward direction are retained.',
      'layer_bounds':layer_bounds,'nonterminal_lower_bound':2433,'positive_canonical_terminal_objective_lower_bound':7283,'complete_feasible_point_objective':6425,'constant_strict_margin':858,'zero_canonical_terminal_predicate_margin':'4850 * sum(original 200 continuous terminals)',
      'positive_fractional_terminal_control':{'objective':6426,'terminal_sum':'1/4850','independent_fraction_evaluation':'PASS','kernel_replay':'VERIFIED'},
      'statistics':result['statistics'],'commands':commands,'fifteen_recorded_attacks':attacks,'six_conditional_and_projection_attacks_independently_replayed':small_replayed,
      'limitations':['This independently repeats one full certificate, the fractional positive control and six small conditional/projection mutations, not all nine other large negative certificates. Their recorded receipts and request/binary bindings were checked.','No claim that 6425 is optimal, no LP equivalence and no full feasible-set bijection.','The RPA is hash-bound; this review did not independently reassemble the 267 MB text. The author recorded the successful exact assembly and root may replay it in final delivery.','Working draft V10; not a version-freeze announcement.'],
      'reviewed_files':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),case/'preparation.json',ROOT/'tools/prepare_test36_full.py',ROOT/'tools/finalize_test36.py']}}
    (ROOT/'audit/TEST36_COMPLETE_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'directions':3,'improvements':1,'original_continuous_terminals':200,'explicit_retained_projections_each_direction':37616,'obligations':529636,'work':result['statistics']['work']},indent=2))

if __name__=='__main__':main()
