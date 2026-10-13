#!/usr/bin/env python3
"""Independent Fraction/MPS review of actual test83's strict tuple; no helpers."""
import hashlib,json
from collections import defaultdict
from fractions import Fraction as Q
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def parse(path):
    names=[];ids={};rows=[];terms={};rhs={};cost={};marked={};section=None;integer=False;objective=None
    with Path(path).open() as f:
        for line in f:
            if not line.strip() or line.startswith('*'):continue
            t=line.split()
            if not line[0].isspace():
                section=t[0]
                assert section not in ('BOUNDS','RANGES'), 'This independent reader intentionally requires this actual no-explicit-bound/no-range model.'
                if section=='ENDATA':break
                continue
            if section=='ROWS':
                if t[0]=='N':assert objective is None;objective=t[1]
                else:assert t[0]=='E';rows.append(t[1]);terms[t[1]]={}
            elif section=='COLUMNS':
                if t[1].strip("'")=='MARKER':integer=t[2].strip("'")=='INTORG';continue
                if t[0] not in ids:ids[t[0]]=len(names);names.append(t[0]);marked[ids[t[0]]]=integer
                i=ids[t[0]]
                for name,c in zip(t[1::2],t[2::2]):
                    d=cost if name==objective else terms[name];d[i]=d.get(i,Q(0))+Q(c)
            elif section=='RHS':
                for name,c in zip(t[1::2],t[2::2]):assert name not in rhs;rhs[name]=Q(c)
    assert len(names)==65832 and len(rows)==100 and all(marked.values())
    assert all(rhs[name]==1 and all(c==1 for c in terms[name].values()) for name in rows)
    assert rhs.get(objective,Q(0))==0
    return names,ids,rows,terms,cost
def decode_expr(e):
    terms=[(i,Q(c)) for i,c in e['terms']];assert all(c for _,c in terms)
    assert all(i<j for (i,_),(j,_) in zip(terms,terms[1:]));return Q(e['constant']),dict(terms)

def main():
    folder=ROOT/'cases/test83';d=load(folder/'preparation.json');h=load(d['audit']['path'])
    iv=next(x for x in load(ROOT/'audit/corpus_inventory.json')['cases'] if x['case_id']=='test83')
    for side,key in [('source','source_models'),('target','final_target_models')]:assert sha(d[side]['path'])==d[side]['sha256']==iv[key][0]['sha256']
    for name,a in d['artifacts'].items():assert sha(folder/name)==a['sha256'] and (folder/name).stat().st_size==a['bytes']
    assert sha(folder/'proof.rpa')==d['rpa_sha256']
    certificate=json.loads((folder/'proof.rpa').read_text().split('\n',1)[1]);request=load(folder/'request.json')
    oldfolder=Path(d['previous_submission']['path']);old=json.loads((oldfolder/'proof.rpa').read_text().split('\n',1)[1])
    assert certificate['claims']==old['claims'] and certificate['blocks']==old['blocks'];del old
    w,=certificate['improvements'];assert request['improvements']==[w['claim']]
    assert w['claim']['target'] is False and w['claim']['integers'] is True
    names,ids,rows,terms,cost=parse(d['source']['path']);n=len(names)
    expected={ids[x['removed_variable']]:[ids[v] for v in x['replacement_variables']] for x in h['dominance_deletions']}
    assert len(expected)==61
    p0,p=decode_expr(w['claim']['positive']);assert p0==0 and p=={i:Q(1) for i in expected}
    ret=w['block']['end']['ImproveReturn'];mapping=[decode_expr(e) for e in ret['map']]
    assert len(mapping)==n and len(ret['checks'])==3*n+100+1
    supports=[set() for _ in range(n)]
    for ri,name in enumerate(rows):
        for i in terms[name]:supports[i].add(ri)
    reconstructed=[{} if i in expected else {i:Q(1)} for i in range(n)]
    savings={}
    for i,pair in expected.items():
        assert len(pair)==2 and not (supports[pair[0]]&supports[pair[1]]) and supports[pair[0]]|supports[pair[1]]==supports[i]
        assert all(j not in expected for j in pair)
        savings[i]=cost[i]-sum(cost[j] for j in pair);assert savings[i]>0
        for j in pair:reconstructed[j][i]=Q(1)
    for i,(constant,e) in enumerate(mapping):
        assert constant==0 and e==reconstructed[i]
        if len(e)>1:assert set.intersection(*(supports[j] for j in e))
        # Nonnegative unit terms plus one common partition row give [0,1];
        # declared integer coordinates give integrality of their sum.
    for name in rows:
        composed=defaultdict(Q)
        for j,c in terms[name].items():
            for i,v in mapping[j][1].items():composed[i]+=c*v
        assert dict(composed)==terms[name],name
    changed=defaultdict(Q)
    for j,c in cost.items():
        changed[j]-=c
        for i,v in mapping[j][1].items():changed[i]+=c*v
    difference={i:c for i,c in changed.items() if c}
    assert difference=={i:-c for i,c in savings.items()}
    delta=Q(ret['margin']['Predicate']);assert delta==min(savings.values())==Q(161497,1000000)
    assert {i:Q(v) for i,v in d['strict_improvement']['saving_by_coordinate'].items()}=={str(i):v for i,v in savings.items()}
    final=d['kernel_runs'][-1];result=json.loads(final['stdout']);assert final['exit_code']==0 and result['status']=='VERIFIED' and result['improvements']==1
    assert len(d['negative_checks'])==8 and all(x['exit_code']==2 and x['result']['status']=='INVALID' for x in d['negative_checks'])
    out={'status':'PASS','method':'Independent stdlib Fraction reader over complete original MPS; exact complete tuple/domain/row/objective review. No preparer/parser import and no new kernel replay.',
        'source_variables':n,'source_rows':100,'positive_coordinates':61,'delta':str(delta),'complete_tuple_domains_and_integrality':True,'all100_partition_equalities_unchanged':True,'objective_difference_exactly_negative_savings':True,
        'original_directional_claims_and_blocks_unchanged':True,'kernel_receipt_status':result['status'],'eight_recorded_attacks':'ALL_INVALID',
        'savings':{str(i):str(v) for i,v in sorted(savings.items())},'identity':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),folder/'proof.rpa',folder/'proof.rpx',folder/'request.json',folder/'preparation.json',ROOT/'tools/complete_test83.py']}}
    (ROOT/'audit/TEST83_STRICT_REVIEW.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('savings','identity')},indent=2))
if __name__=='__main__':main()
