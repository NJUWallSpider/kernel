#!/usr/bin/env python3
"""Exact actual test46 table/marginal certificates; no host solver or real products."""
from collections import ChainMap
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time,gc
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha,signature
from prepare_test87 import sumexpr,substitute
from prepare_test23 import extend

class Proof:
    def __init__(self,model,counter=None,facts=None,assumptions=None):
        self.model=model;self.counter=counter if counter is not None else [0];self.facts=ChainMap({},facts or {});self.assumptions=list(assumptions or []);self.steps=[]
    def alloc(self):i=self.counter[0];self.counter[0]+=1;return i
    def refexpr(self,r):
        typ,i=next(iter(r.items()))
        if typ=='Local':return self.facts[i][1]
        if typ=='Assumption':return self.assumptions[i]
        return get_fact(self.model,r,{})
    def kind(self,r):
        typ,i=next(iter(r.items()))
        if typ=='Local':return self.facts[i][0]
        return 'Eq' if typ=='RowEq' else 'Int' if typ=='VarInt' else 'Le'
    def lin(self,kind,terms,expected=None,constant=0):
        assert (kind=='Eq' and constant==0) or (kind=='Le' and constant<=0) or (kind=='Int' and F(constant).denominator==1)
        es=[expression(constant)]
        for ref,q in terms:
            k=self.kind(ref);assert k=='Eq' or (kind=='Le' and k=='Le' and q>=0) or (kind=='Int' and k=='Int' and F(q).denominator==1)
            es.append(mul(self.refexpr(ref),q))
        e=sumexpr(es)
        if expected is not None:assert e==expected,('lin mismatch',kind,e,expected)
        i=self.alloc();self.steps.append({'Lin':{'id':i,'kind':kind,'constant':str(constant),'terms':[[r,str(q)] for r,q in terms]}});self.facts[i]=(kind,e);return {'Local':i}
    def eqpair(self,pos,neg):
        assert self.kind(pos)==self.kind(neg)=='Le' and self.refexpr(pos)==mul(self.refexpr(neg),-1)
        i=self.alloc();self.steps.append({'EqPair':{'id':i,'positive':pos,'negative':neg}});self.facts[i]=('Eq',self.refexpr(pos));return {'Local':i}
    def check(self,kind,e,r=None):
        if not e[1] and ((kind=='Eq' and not e[0]) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):return 'Exact'
        if kind=='Int' and e[0].denominator==1 and all(c.denominator==1 and self.model['vars'][i]['integer'] for i,c in e[1].items()):return 'Exact'
        assert r is not None and self.kind(r) in (kind,'Eq') and self.refexpr(r)==e,('missing proof',kind,e,r)
        return r
    def cases(self,kind,wanted,split,integer,left,right):
        i=self.alloc();children=[]
        for side,callback in enumerate((left,right)):
            guard=split if side==0 else plus(expression(1),split,-1)
            child=Proof(self.model,self.counter,self.facts,self.assumptions+[guard]);end=callback(child,{'Assumption':len(self.assumptions)})
            if 'Witness' in end:assert child.check(kind,wanted,end['Witness'])==end['Witness']
            else:assert child.kind(end['Absurd'])=='Le' and not child.refexpr(end['Absurd'])[1] and child.refexpr(end['Absurd'])[0]>0
            children.append({'steps':child.steps,'end':end})
        self.steps.append({'Cases':{'id':i,'kind':kind,'expression':expr_json(wanted),'split':expr_json(split),'integer':integer,'left':children[0],'right':children[1]}});self.facts[i]=(kind,wanted);return {'Local':i}


def inspect(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(159145,301,61036,3615)
    assert all(r['sense']=='E' for r in a['rows']+b['rows'])
    tables=[];selectors=set();helpers=set();classified_rows=set();unary={};marginals={}
    for hint in h['certificates']['table_cost_bounds']:
        norm=a['rows'][a['row_index'][hint['selection_row']]];assert norm['rhs']==1 and set(norm['terms'].values())=={F(1)}
        entries=set(norm['terms']);assert not selectors&entries;selectors|=entries
        cv=a['var_index'][hint['cost_variable']];helpers.add(cv)
        costrow=a['rows'][a['row_index'][hint['cost_row']]];assert costrow['rhs']==0 and costrow['terms'][cv]==-1 and set(costrow['terms'])==entries|{cv}
        costs={i:costrow['terms'][i] for i in entries};assert all(c>=0 and c.denominator==1 for c in costs.values())
        nodes=[a['var_index'][n] for n in hint['endpoint_variables']];states=[]
        for name,node in zip(hint['endpoint_index_rows'],nodes):
            helpers.add(node);r=a['rows'][a['row_index'][name]];assert r['rhs']==0 and r['terms'][node]==-1 and set(r['terms'])<=(entries|{node})
            st={i:r['terms'].get(i,F(0)) for i in entries};assert all(q.denominator==1 and 0<=q<=48 for q in st.values());states.append(st)
        assert len(nodes) in (1,2) and len(set(nodes))==len(nodes)
        coordinates={tuple(int(st[i]) for st in states):i for i in entries};assert len(coordinates)==len(entries)
        assert set(coordinates)==({(j,) for j in range(49)} if len(nodes)==1 else {(i,j) for i in range(49) for j in range(49)})
        retained={ij:i for ij,i in coordinates.items() if costs[i]!=39424};forbidden=entries-set(retained.values())
        constant=hint['selection_row'] in h['edits']['eliminated_constant_factors']
        t={'name':hint['selection_row'],'norm':a['row_index'][hint['selection_row']],'cost_row':a['row_index'][hint['cost_row']],'cost_var':cv,'moments':[a['row_index'][n] for n in hint['endpoint_index_rows']],'nodes':nodes,'states':states,'entries':entries,'coords':coordinates,'costs':costs,'allowed':retained,'forbidden':forbidden,'constant':constant,'max':max(costs[i] for i in retained.values()),'min':min(costs[i] for i in retained.values())}
        tables.append(t);classified_rows|={t['norm'],t['cost_row'],*t['moments']}
        if len(nodes)==1:assert nodes[0] not in unary;unary[nodes[0]]=t
    obj=a['var_index']['objective'];assert a['objective']==expression(0,{obj:1})
    assert classified_rows==set(range(len(a['rows'])))-{a['row_index']['p_lin_0']}
    assert selectors|helpers|{obj}==set(range(len(a['vars']))) and not selectors&helpers and obj not in helpers
    assert a['rows'][a['row_index']['p_lin_0']]['rhs']==0 and a['rows'][a['row_index']['p_lin_0']]['terms']=={obj:F(1),**{t['cost_var']:F(-1) for t in tables}}
    assert all(a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1 and a['vars'][i]['integer'] for i in selectors)
    assert a['vars'][obj]['lower']==0 and a['vars'][obj]['upper']==39423 and a['vars'][obj]['integer']
    assert all(a['vars'][t['cost_var']]['lower']==0 and a['vars'][t['cost_var']]['upper']==39424 and a['vars'][t['cost_var']]['integer'] for t in tables)
    assert all(a['vars'][n]['lower']==0 and a['vars'][n]['upper']==48 and a['vars'][n]['integer'] for n in unary)
    removed_constant=set();forbidden=set();retained=set()
    for t in tables:
        forbidden|=t['forbidden']
        if len(t['nodes'])==2:
            domains=[set(j[0] for j in unary[n]['allowed']) for n in t['nodes']]
            assert set(t['allowed'])<={(i,j) for i in domains[0] for j in domains[1]}
            if t['constant']:
                assert set(t['allowed'])=={(i,j) for i in domains[0] for j in domains[1]}
                assert {t['costs'][i] for i in t['allowed'].values()}=={F(17)};removed_constant|=set(t['allowed'].values())
        if not t['constant']:retained|=set(t['allowed'].values())
    assert {a['vars'][i]['name'] for i in retained|{obj}}==set(b['var_index'])
    assert len(forbidden)==80785 and len(removed_constant)==17234 and len(helpers)==90
    assert sum(t['max'] for t in tables)==39389 and sum(t['min'] for t in tables)==1417
    oldnew={i:b['var_index'][a['vars'][i]['name']] for i in retained|{obj}}
    binaries={i for t in unary.values() for i in t['allowed'].values()}
    for i,j in oldnew.items():
        expected={**a['vars'][i],'integer':i in binaries,'upper':None if i==obj else F(1)}
        assert b['vars'][j]==expected
    assert b['objective']==expression(0,{oldnew[obj]:1})
    expectedrows={};objterms={oldnew[obj]:F(1)}
    for t in tables:
        if t['constant']:continue
        for i in t['allowed'].values():objterms[oldnew[i]]=-t['costs'][i]
        if len(t['nodes'])==1:expectedrows[t['name']]={'name':t['name'],'sense':'E','rhs':F(1),'terms':{oldnew[i]:F(1) for i in t['allowed'].values()}}
    expectedrows['p_lin_0']={'name':'p_lin_0','sense':'E','rhs':F(289),'terms':objterms}
    byname={t['name']:t for t in tables}
    for name,hint in h['edits']['new_marginal_rows'].items():
        t=byname[hint['original_pair_selection_row']];assert not t['constant'];node=a['var_index'][hint['node']];side=t['nodes'].index(node);state=hint['state'];u=unary[node]['allowed'][(state,)]
        ids=[i for ij,i in t['allowed'].items() if ij[side]==state];assert ids
        expectedrows[name]={'name':name,'sense':'E','rhs':F(0),'terms':{**{oldnew[i]:F(1) for i in ids},oldnew[u]:F(-1)}}
        marginals[(t['name'],side,state)]=b['row_index'][name]
    assert set(expectedrows)==set(b['row_index'])
    for r in b['rows']:assert r==expectedrows[r['name']],('target row changed',r['name'])
    return {'tables':tables,'unary':unary,'obj':obj,'forbidden':forbidden,'oldnew':oldnew,'marginals':marginals,'constant_entries':removed_constant}


def finish(p,output,mapping,claim,domains,rows,objective=None):
    checks=[]
    for i,v in enumerate(output['vars']):
        e=mapping[i]
        for typ,side,sign in [('VarLower','lower',-1),('VarUpper','upper',1)]:
            if v[side] is None:continue
            wanted=plus(mul(e,sign),expression(-sign*v[side]));r=domains.get((i,typ))
            if r is None and e[0]==0 and len(e[1])==1:
                j,c=next(iter(e[1].items()))
                if c==1 and p.model['vars'][j][side]==v[side]:r={typ:j}
            checks.append(p.check('Le',wanted,r))
        if v['integer'] and claim['output_integers']:checks.append(p.check('Int',e,domains.get((i,'VarInt'))))
    for i,row in enumerate(output['rows']):checks.append(p.check('Eq',substitute(row_fact(row,'RowEq'),mapping),rows.get(i)))
    if claim['objective']!='None':checks.append(p.check('Eq',plus(substitute(output['objective'],mapping),p.model['objective'],-1),objective))
    for i,o in claim['projection']:checks.append(p.check('Eq',plus(mapping[o],expression(0,{i:1}),-1)))
    return {'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def target_setup(a,b,s,p):
    """Actual normalization/moment/cost facts shared by both reverse modes."""
    norms={};means={};meanbounds={};costs={};costbounds={};moments={};oldnew=s['oldnew']
    for node,t in s['unary'].items():
        norm=row_ref(b,t['name']);norms[t['name']]=norm
        mean=expression(0,{oldnew[i]:F(ij[0]) for ij,i in t['allowed'].items() if ij[0]});means[node]=mean
        lo=p.lin('Le',[[{'VarLower':j},c] for j,c in mean[1].items()],mul(mean,-1))
        hi=p.lin('Le',[[norm,F(48)]]+[[{'VarLower':oldnew[i]},48-F(ij[0])] for ij,i in t['allowed'].items() if ij[0]!=48],plus(mean,expression(-48)))
        meanbounds[node]=(lo,hi)
    for t in s['tables']:
        if t['constant']:costs[t['cost_var']]=expression(17);continue
        if len(t['nodes'])==2:
            terms=[[{'RowEq':s['marginals'][(t['name'],0,ij[0])]},F(1)] for ij in s['unary'][t['nodes'][0]]['allowed']]
            terms.append([norms[s['unary'][t['nodes'][0]]['name']],F(1)])
            norms[t['name']]=p.lin('Eq',terms,expression(-1,{oldnew[i]:F(1) for i in t['allowed'].values()}))
            for side,node in enumerate(t['nodes']):
                wanted=plus(expression(0,{oldnew[i]:F(ij[side]) for ij,i in t['allowed'].items() if ij[side]}),means[node],-1)
                moments[(t['name'],side)]=p.lin('Eq',[[{'RowEq':s['marginals'][(t['name'],side,ij[0])]},F(ij[0])] for ij in s['unary'][node]['allowed'] if ij[0]],wanted)
        cost=expression(0,{oldnew[i]:t['costs'][i] for i in t['allowed'].values()});costs[t['cost_var']]=cost
        lo=p.lin('Le',[[{'VarLower':i},c] for i,c in cost[1].items()],mul(cost,-1))
        hi=p.lin('Le',[[norms[t['name']],t['max']]]+[[{'VarLower':oldnew[i]},t['max']-t['costs'][i]] for i in t['allowed'].values() if t['max']!=t['costs'][i]],plus(cost,expression(-t['max'])))
        costbounds[t['cost_var']]=(lo,hi)
    objupper=p.lin('Le',[[row_ref(b,'p_lin_0'),F(1)]]+[[hi,F(1)] for lo,hi in costbounds.values()],expression(-39423,{oldnew[s['obj']]:F(1)}),constant=F(39389-39423))
    return {'norms':norms,'means':means,'meanbounds':meanbounds,'costs':costs,'costbounds':costbounds,'moments':moments,'objupper':objupper}


def reverse_lp(a,b,s):
    p=Proof(b);setup=target_setup(a,b,s,p);intervals=[];corners=[]
    for t in s['tables']:
        if not t['constant']:continue
        es=[];bounds=[];extremes=[]
        for node in t['nodes']:
            u=s['unary'][node];low=min(ij[0] for ij in u['allowed']);high=max(ij[0] for ij in u['allowed']);assert high>low
            span=F(high-low);e=mul(plus(setup['means'][node],expression(-low)),1/span)
            lower=p.lin('Le',[[setup['norms'][u['name']],-F(low)/span]]+[[{'VarLower':s['oldnew'][i]},F(ij[0]-low)/span] for ij,i in u['allowed'].items() if ij[0]!=low],mul(e,-1))
            upper=p.lin('Le',[[setup['norms'][u['name']],F(high)/span]]+[[{'VarLower':s['oldnew'][i]},F(high-ij[0])/span] for ij,i in u['allowed'].items() if ij[0]!=high],plus(e,expression(-1)))
            es.append(e);bounds.append((lower,upper));extremes.append((low,high))
        alpha,beta=es
        intervals.append({'lower':[expr_json(expression()),expr_json(plus(plus(alpha,beta),expression(-1)))],'upper':[expr_json(alpha),expr_json(beta)],'checks':[bounds[0][0],bounds[1][0],bounds[1][1],bounds[0][1]]})
        corners.append((t,extremes,alpha,beta))
    ext,layout=extend(b,intervals);q=Proof(ext,p.counter,p.facts);zero=expression();mapping=[zero]*len(a['vars']);domains={};rows={}
    for i,j in s['oldnew'].items():mapping[i]=expression(0,{j:F(1)})
    for node,e in setup['means'].items():mapping[node]=e;domains[(node,'VarLower')],domains[(node,'VarUpper')]=setup['meanbounds'][node]
    for t in s['tables']:
        cv=t['cost_var'];mapping[cv]=setup['costs'][cv]
        if not t['constant']:
            lo,hi=setup['costbounds'][cv];domains[(cv,'VarLower')]=lo;domains[(cv,'VarUpper')]=q.lin('Le',[[hi,F(1)]],plus(mapping[cv],expression(-39424)),constant=t['max']-39424)
            rows[t['norm']]=setup['norms'][t['name']]
            for side in range(len(t['nodes'])):
                if len(t['nodes'])==2:rows[t['moments'][side]]=setup['moments'][(t['name'],side)]
    for (t,extremes,alpha,beta),l in zip(corners,layout):
        z=expression(0,{l['variable']:F(1)});weights=[z,plus(alpha,z,-1),plus(beta,z,-1),plus(plus(plus(expression(1),alpha,-1),beta,-1),z)]
        indices=[(extremes[0][1],extremes[1][1]),(extremes[0][1],extremes[1][0]),(extremes[0][0],extremes[1][1]),(extremes[0][0],extremes[1][0])]
        lower=[{'RowLower':l['lower'][0]},{'RowUpper':l['upper'][0]},{'RowUpper':l['upper'][1]},{'RowLower':l['lower'][1]}]
        assert sumexpr(weights)==expression(1)
        for k,(ij,e) in enumerate(zip(indices,weights)):
            i=t['allowed'][ij];mapping[i]=e;assert q.refexpr(lower[k])==mul(e,-1)
            domains[(i,'VarLower')]=lower[k];domains[(i,'VarUpper')]=q.lin('Le',[[ref,F(1)] for j,ref in enumerate(lower) if j!=k],plus(e,expression(-1)))
    domains[(s['obj'],'VarUpper')]=setup['objupper'];rows[a['row_index']['p_lin_0']]=row_ref(b,'p_lin_0')
    claim={'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':[[j,i] for i,j in s['oldnew'].items()],'inverse':None}
    # All constant-factor cost/moment/normalization equations cancel exactly;
    # every surviving row and every source domain remains an explicit obligation.
    block=finish(q,a,mapping,claim,domains,rows)
    return claim,{'steps':p.steps,'end':{'IntervalLift':{'intervals':intervals,'body':block}}},{'intervals':len(intervals),'obligations':len(block['end']['Return']['checks']),'root_steps':len(p.steps),'body_steps':len(q.steps)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test46-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test46'));ap.add_argument('--kernel',type=Path,required=True);ap.add_argument('--phase',choices=['lp'],default='lp');args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json';h=json.loads(hint.read_text());k=args.kernel.resolve()
    a,b=parse_mps(source),parse_mps(target);print('models parsed',flush=True);s=inspect(a,b,h);print('complete matrix classified',flush=True)
    assert sha(source)==h['input']['sha256'] and sha(target)==h['output']['sha256']
    (out/'structure.json').write_text(json.dumps({'status':'ALL_ACTUAL_FIELDS_CLASSIFIED','source_sha256':sha(source),'target_sha256':sha(target),'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'tables':len(s['tables']),'unary_tables':len(s['unary']),'constant_factors':sum(t['constant'] for t in s['tables']),'forbidden_selectors':len(s['forbidden']),'constant_factor_selectors':len(s['constant_entries']),'tablewise_upper_cost':str(sum(t['max'] for t in s['tables']))},indent=2)+'\n')
    claim,block,counts=reverse_lp(a,b,s);print('complete LP proof prepared',flush=True);cert={'claims':[claim],'blocks':[block]};destination=out/'lp-only';destination.mkdir(exist_ok=True);rp=destination/'proof.rpa';request=destination/'request.json';rp.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps([claim],separators=(',',':'))+'\n')
    meta={'case_id':'test46','status':'PROOF_NOT_COMPLETED','scope':'LP reverse complete only; MI forward/reverse still pending','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'kernel_binary':{'path':str(k),'sha256':sha(k)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'counts':counts,'preparation_seconds':time.perf_counter()-start,'kernel_runs':[]}
    def save():(destination/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
    save()
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(destination/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(destination/'proof.rpx'),str(request)]]:
        proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);meta['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr});save()
        if proc.returncode:raise SystemExit(proc.stdout+proc.stderr)
    meta['partial_claim_status']='VERIFIED';meta['artifacts']={n:{'bytes':(destination/n).stat().st_size,'sha256':sha(destination/n)} for n in ['proof.rpa','proof.rpx','request.json']};save();print(json.dumps(meta['kernel_runs'][-1],indent=2))

if __name__=='__main__':main()
