#!/usr/bin/env python3
"""Actual test55 auxiliary projection and local exact binary activation bounds."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test24 import split,execute,popmut


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(3872,3904,2848,2880)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];forward=[expression(0,{i:1}) for i,j in common]
    assert all(a['vars'][i]==b['vars'][j] for i,j in common)
    f=SparseBuilder(a);modified={};deleted={};ys={};bounds={};capacities=set()
    for d in h['blocks']:
        y=a['var_index'][d['removed_column']];x=a['var_index'][d['x']];us=[a['var_index'][v] for v in d['binary_columns']];M=F(d['new_M']);old=F(d['old_M']);assert old==480 and 0<M<=old and len(us) in (1,3)
        assert not a['vars'][x]['integer'] and not a['vars'][y]['integer'] and a['vars'][x]['lower']==a['vars'][y]['lower']==0 and a['vars'][y]['upper'] is None and not a['objective'][1].get(y,0)
        assert all(a['vars'][u]['integer'] and a['vars'][u]['lower']==0 and a['vars'][u]['upper']==1 for u in us)
        vub=row_ref(a,d['removed_row']);assert f.refexpr(vub)==expression(0,{x:1,y:-old})
        assert len(d['modified_rows'])==len(us)
        links={}
        for rn,u in zip(d['modified_rows'],us):
            links[u]=row_ref(a,rn);assert f.refexpr(links[u])==expression(0,{y:1,u:-1})
            assert substitute(row_fact(b['rows'][b['row_index'][rn]],'RowUpper'),forward)==expression(0,{x:1,u:-M})
            modified[rn]=(d,u,x,y,M)
        ys[y]=x;deleted[d['removed_row']]=y;bounds[y]=M
        if M==old:
            for rn,u in zip(d['modified_rows'],us):modified[rn]=f.lin('Le',[[vub,1],[links[u],old]],expression(0,{x:1,u:-M}))
            continue
        cc=d['capacity_certificate'];cap=row_ref(a,cc['row']);row=a['rows'][a['row_index'][cc['row']]];capacities.add(next(iter(cap.values())));ax=row['terms'][x]
        assert row['sense']=='L' and row['rhs']==F(cc['rhs']) and ax==F(cc['x_coefficient'])>0 and all(c>=0 and a['vars'][i]['lower']==0 for i,c in row['terms'].items())
        mandatory=sum(row['terms'].get(u,F(0)) for u in us);assert mandatory==F(cc['mandatory']) and ax*M+mandatory==row['rhs'] and M==F(cc['upper'])
        for rn,targetu in zip(d['modified_rows'],us):
            wanted=expression(0,{x:1,targetu:-M})
            def recurse(p,k,fixed):
                if k==len(us):
                    terms=[[cap,1/ax]]
                    for i,c in row['terms'].items():
                        if i==x:continue
                        if i in fixed:terms.append([fixed[i],-c/ax])
                        else:terms.append([{'VarLower':i},c/ax])
                    active=p.lin('Le',terms,expression(-M,{x:1}))
                    return p.lin('Le',[[active,1],[fixed[targetu],-M]],wanted)
                u=us[k]
                def zero(c,r):
                    # A single inactive actual activation forces x=0.
                    xzero=c.lin('Le',[[vub,1],[links[u],old],[r,old]],expression(0,{x:1}))
                    return c.lin('Le',[[xzero,1],[{'VarLower':targetu},M]],wanted)
                def one(c,r):
                    assigned=dict(fixed);assigned[u]=c.eqpair({'VarUpper':u},r);return recurse(c,k+1,assigned)
                return split(p,'Le',wanted,expression(0,{u:1}),{'VarInt':u},[zero,one])
            modified[rn]=recurse(f,0,{})
    assert len(ys)==1024 and len(modified)==1536 and len(deleted)==1024
    assert {i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}==set(ys)
    # The complete matrix check below ensures that no deleted auxiliary has hidden
    # incidence. No untrusted incidence theorem is used as a kernel premise.
    checks=[]
    for i,j in common:
        v=b['vars'][j]
        if v['lower'] is not None:checks.append({'VarLower':i})
        if v['upper'] is not None:checks.append({'VarUpper':i})
        if v['integer']:checks.append({'VarInt':i})
    for row in b['rows']:
        rn=row['name'];typ=next(iter(row_ref(b,rn)));wanted=substitute(row_fact(row,typ),forward)
        ref=modified[rn] if rn in modified else row_ref(a,rn)
        assert f.refexpr(ref)==wanted;checks.append(ref)
    assert substitute(b['objective'],forward)==a['objective'];checks+=['Exact']*(1+len(common))
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':common,'inverse':None}]
    blocks=[{'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':checks}}}]
    reverse=[]
    for i,v in enumerate(a['vars']):
        if i in ys:reverse.append(expression(0,{b['var_index'][a['vars'][ys[i]]['name']]:F(1,480)}))
        else:reverse.append(expression(0,{b['var_index'][v['name']]:1}))
    auditlinks={rn:d for d in h['blocks'] for rn in d['modified_rows']}
    for integer in (True,False):
        r=SparseBuilder(b);checks=[]
        for i,v in enumerate(a['vars']):
            j=next(iter(reverse[i][1]))
            if i in ys:checks.append(r.lin('Le',[[{'VarLower':j},F(1,480)]],mul(reverse[i],-1)))
            else:
                if v['lower'] is not None:checks.append({'VarLower':j})
                if v['upper'] is not None:checks.append({'VarUpper':j})
                if integer and v['integer']:checks.append({'VarInt':j})
        for row in a['rows']:
            rn=row['name'];typ=next(iter(row_ref(a,rn)));wanted=substitute(row_fact(row,typ),reverse)
            if rn in deleted:assert wanted==expression();checks.append('Exact')
            elif rn in auditlinks:
                d=auditlinks[rn];M=F(d['new_M']);u=next(i for i,c in wanted[1].items() if c==-1)
                checks.append(r.lin('Le',[[row_ref(b,rn),F(1,480)],[{'VarLower':u},(480-M)/480]],wanted))
            else:
                ref=row_ref(b,rn);assert r.refexpr(ref)==wanted;checks.append(ref)
        assert substitute(a['objective'],reverse)==b['objective'];checks+=['Exact']*(1+len(common))
        claims.append({'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in common],'inverse':None})
        blocks.append({'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':checks}}})
    counts={'source_variables':3872,'target_variables':2848,'source_rows':3904,'target_rows':2880,'removed_private_continuous':1024,'rewritten_links':1536,'strengthened_links':1024,'activated_capacity_certificates':512,'retained_coordinate_observations_per_claim':len(common),'claims':3,'steps_by_claim':[len(x['steps']) for x in blocks]}
    return {'claims':claims,'blocks':blocks},counts,capacities


def all_steps(block):
    for s in block['steps']:
        yield s
        if 'Cases' in s:
            yield from all_steps(s['Cases']['left']);yield from all_steps(s['Cases']['right'])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test55-nomf-B1');source=run/'input/model.mps';target=run/'output/model.mps';audit=run/'output/audit.json'
    inventory=next(c for c in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if c['case_id']=='test55');assert sha(source)==inventory['source_models'][0]['sha256'] and sha(target)==inventory['final_target_models'][0]['sha256']
    cert,counts,capacities=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    def capacity_terms(c):
        return next(s['Lin']['terms'] for s in all_steps(c['blocks'][0]) if 'Lin' in s and any(ref.get('RowUpper') in capacities for ref,q in s['Lin']['terms']))
    def wronglift(c):
        arr=c['blocks'][1]['end']['Return']['map'];i=next(i for i,e in enumerate(arr) if e['terms'][0][1]=='1/480');old=arr[i];arr[i]={'constant':'0','terms':[[old['terms'][0][0],'1/479']]};return lambda:arr.__setitem__(i,old)
    mutations=[('missing_capacity_residual_bound','Drops a nonnegative residual term from a strengthened activation capacity certificate.',popmut(capacity_terms)),('missing_inactive_guard','Drops the binary zero assumption needed to force continuous x to zero.',popmut(lambda c:next(s['Cases'] for s in c['blocks'][0]['steps'] if 'Cases' in s)['left']['steps'][0]['Lin']['terms'])),('wrong_auxiliary_lift','Reconstructs a removed y as x/479 instead of the committed exact x/480.',wronglift)]
    execute('test55',source,target,audit,Path('cases/test55').resolve(),args.kernel.resolve(),cert,counts,'Exact retained-coordinate mixed-integer projection and pointwise objective equality in both directions, with simultaneous continuous completion y=x/480; no bijection of auxiliary values. Objective-preserving target-to-source LP inclusion. Every original and target domain, row, objective and all retained coordinate observations checked; lowered capacities use only local actual binary activations.',2,mutations,start,Path(__file__).resolve())

if __name__=='__main__':main()
