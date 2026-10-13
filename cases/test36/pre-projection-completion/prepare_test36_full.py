#!/usr/bin/env python3
"""Full actual test36 minimum preservation and caller-bound optimizer exclusion.
Untrusted author code; all maps, joint lifts and strict margins are kernel checked.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter,defaultdict
import argparse,json,subprocess,time,copy,gc
from prepare_test46 import Proof,parse_mps,row_ref,row_fact,expression,plus,mul,expr_json,sumexpr,substitute,sha

def var(i):return expression(0,{i:F(1)})
def inspect(a,b,h):
    assert len(a['vars'])==37816 and len(b['vars'])==37616 and len(a['rows'])==len(b['rows'])==37617
    bits=[i for i,v in enumerate(a['vars']) if v['integer']];assert len(bits)==200
    assert all(a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1 for i in bits)
    cardinal=next(i for i,r in enumerate(a['rows']) if r['sense']=='E');r=a['rows'][cardinal];assert r['rhs']==195 and r['terms']=={i:F(1) for i in bits}
    records={};children=Counter()
    for ri,r in enumerate(a['rows']):
        if ri==cardinal:continue
        assert r['sense']=='L' and r['rhs']==1
        negative=[i for i,c in r['terms'].items() if c==-1];positive=[i for i,c in r['terms'].items() if c==1]
        assert len(negative)==1 and len(positive)==2 and len(r['terms'])==3
        z=negative[0];assert z not in records and not a['vars'][z]['integer'] and a['vars'][z]['lower']==0 and a['vars'][z]['upper'] is None
        parent=[i for i in positive if i not in bits];xs=[i for i in positive if i in bits];assert len(parent)<=1
        if parent:children[parent[0]]+=1
        records[z]={'variable':z,'row':ri,'parent':parent[0] if parent else None,'bits':xs}
    assert set(records)|set(bits)==set(range(len(a['vars']))) and all(n==1 for n in children.values())
    pending=set(records);ordered=[]
    while pending:
        ready=sorted(z for z in pending if records[z]['parent'] is None or records[z]['parent'] not in pending);assert ready
        for z in ready:
            d=records[z];d['prefix']=(records[d['parent']]['prefix'] if d['parent'] is not None else [])+d['bits'];d['depth']=len(d['prefix']);assert len(set(d['prefix']))==d['depth'];ordered.append(z)
        pending-=set(ready)
    terminals=set(records)-set(children);assert len(terminals)==200
    retained={i:b['var_index'][v['name']] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']};assert set(retained)==set(range(len(a['vars'])))-terminals
    for i,j in retained.items():assert a['vars'][i]==b['vars'][j]
    for i,v in enumerate(a['vars']):assert a['objective'][1][i]==(4850 if i in terminals else 1)
    assert a['objective'][0]==b['objective'][0]==0 and b['objective'][1]=={j:F(1) for j in retained.values()}
    for ar in a['rows']:
        br=b['rows'][b['row_index'][ar['name']]];assert br=={**ar,'terms':{retained[i]:c for i,c in ar['terms'].items() if i in retained}}
    values=[F(0)]*len(a['vars']);zeros=set(h['certificate']['zero_binary_variables']);assert len(zeros)==5
    for i in bits:values[i]=F(a['vars'][i]['name'] not in zeros)
    for z in ordered:
        d=records[z];values[z]=max(F(0),sum(values[i] for i in d['bits'])+(values[d['parent']] if d['parent'] is not None else F(0))-1)
    assert all(values[z]==0 for z in terminals) and sum(values[i]*c for i,c in a['objective'][1].items())==6425
    return {'bits':bits,'cardinal':cardinal,'records':records,'ordered':ordered,'terminals':terminals,'retained':retained,'point':values}


def lower_base(p,a,s):
    """Actual chain inequalities and a continuous top-five box bound; no oracle facts."""
    lower={};layers=defaultdict(list);bounds=[];bits=s['bits'];card={'RowEq':s['cardinal']}
    for z in s['ordered']:
        d=s['records'][z]
        if d['depth']>27:continue
        refs=[[{'RowUpper':d['row']},F(1)]]
        if d['parent'] is not None:refs.append([lower[d['parent']],F(1)])
        f=expression(1-d['depth'],{i:F(1) for i in d['prefix']});lower[z]=p.lin('Le',refs,plus(f,var(z),-1));layers[d['depth']].append(z)
    for depth,zs in sorted(layers.items()):
        assert len(zs)==200;freq=Counter(i for z in zs for i in s['records'][z]['prefix']);weights=sorted(freq.values(),reverse=True);top=sum(weights[:5]);q=F(weights[4]);lb=200-top
        assert lb>0
        refs=[[card,-q]]
        refs += [[{'VarLower':i},F(freq[i])-q] for i in bits if freq[i]>q]
        refs += [[{'VarUpper':i},q-F(freq[i])] for i in bits if freq[i]<q]
        weighted=p.lin('Le',refs,expression(sum(freq.values())-top,{i:-F(w) for i,w in freq.items()}))
        bound=p.lin('Le',[[weighted,F(1)]]+[[lower[z],F(1)] for z in zs],expression(lb,{z:F(-1) for z in zs}));bounds.append((lb,zs,bound))
    assert sum(x[0] for x in bounds)==2238
    used={z for _,zs,_ in bounds for z in zs};refs=[[r,F(1)] for _,_,r in bounds]+[[card,F(-1)]]
    refs += [[{'VarLower':z},F(1)] for z in s['records'] if z not in s['terminals'] and z not in used]
    expected=plus(expression(2433),expression(0,{i:F(1) for i in range(len(a['vars'])) if i not in s['terminals']}),-1)
    return p.lin('Le',refs,expected)


def append_signed(m,items):
    layout=[]
    for item in items:
        first=len(m['vars']);rows=[]
        for k in range(4):
            name=f'author_signed_{first+k}';m['var_index'][name]=first+k;m['vars'].append({'name':name,'integer':k>=2,'lower':F(0),'upper':F(1) if k>=2 else None})
        flow=item['flow'];cap=item['capacity']
        es=[plus(expression(0,{first:F(1),first+1:F(-1)}),flow,-1),expression(-1,{first+2:F(1),first+3:F(1)}),expression(0,{first:F(1),first+2:-cap}),expression(0,{first+1:F(1),first+3:-cap})]
        for k,e in enumerate(es):
            ri=len(m['rows']);name=f'author_signed_row_{ri}';m['row_index'][name]=ri;m['rows'].append({'name':name,'sense':'E' if k<2 else 'L','rhs':-e[0],'terms':e[1]});rows.append(ri)
        layout.append({'first':first,'rows':rows,**item})
    return layout


def sign_value(p,d,value,guard):
    """In u=0 return EQ p=0; in u=1 return EQ p-flow=0."""
    f=d['first'];rr=d['rows'];C=d['capacity'];u=f+2;v=f+3
    if value==0:
        upper=p.lin('Le',[[{'RowUpper':rr[2]},F(1)],[guard,C]],var(f));return p.eqpair(upper,{'VarLower':f})
    wanted=plus(var(f),d['flow'],-1)
    upper=p.lin('Le',[[{'RowEq':rr[0]},F(1)],[{'RowUpper':rr[3]},F(1)],[{'RowEq':rr[1]},C],[guard,C]],wanted)
    lower=p.lin('Le',[[{'RowEq':rr[0]},F(-1)],[{'VarLower':f+1},F(1)]],mul(wanted,-1))
    return p.eqpair(upper,lower)


def sign_cases(p,d,kind,wanted,left,right):
    def low(c,g):return {'Witness':left(c,sign_value(c,d,0,g))}
    def high(c,g):return {'Witness':right(c,sign_value(c,d,1,g))}
    return p.cases(kind,wanted,var(d['first']+2),{'VarInt':d['first']+2},low,high)


def emit(p,output,mapping,rowproof,domainproof,objective,mode='Return',margin=None):
    checks=[]
    for i,v in enumerate(output['vars']):
        for side,typ,sgn in [('lower','VarLower',-1),('upper','VarUpper',1)]:
            if v[side] is not None:
                wanted=plus(mul(mapping[i],sgn),expression(-sgn*v[side]));ref=domainproof.get((i,typ))
                if ref is None and mapping[i][0]==0 and len(mapping[i][1])==1:
                    j,c=next(iter(mapping[i][1].items()))
                    if c==1 and p.model['vars'][j][side]==v[side]:ref={typ:j}
                checks.append(p.check('Le',wanted,ref))
        if v['integer']:checks.append(p.check('Int',mapping[i],domainproof.get((i,'VarInt'))))
    for ri,r in enumerate(output['rows']):
        typ='RowEq' if r['sense']=='E' else 'RowUpper';e=substitute(row_fact(r,typ),mapping);checks.append(p.check('Eq' if typ=='RowEq' else 'Le',e,rowproof.get(ri)))
    wanted=plus(substitute(output['objective'],mapping),p.model['objective'],-1)
    if margin is not None:wanted=plus(wanted,margin[1])
    checks.append(p.check('Eq' if mode=='EqualReturn' else 'Le',wanted,objective))
    end={'map':[expr_json(e) for e in mapping],'checks':checks}
    if mode=='ImproveReturn':end['margin']=margin[0]
    return {'steps':p.steps,'end':{'Return' if mode=='EqualReturn' else mode:end}}


def canonical_root(a,b,s,improvement=False,chunk=10):
    m={**a,'vars':list(a['vars']),'rows':list(a['rows']),'var_index':dict(a['var_index']),'row_index':dict(a['row_index'])}
    positive=expression(0,{i:F(1) for i in s['terminals']});p=Proof(m,assumptions=[mul(positive,-1)] if improvement else []);base=lower_base(p,a,s)
    mapping={i:var(i) for i in s['bits']};dom={};integer={};upper={};layouts={};rowproof={s['cardinal']:{'RowEq':s['cardinal']}};layers=[]
    stages=defaultdict(list)
    for z in s['ordered']:stages[(s['records'][z]['depth']-2)//chunk].append(z)
    anchor_set={s['records'][z]['parent'] for z in s['ordered'] if (s['records'][z]['depth']-2)%chunk==0 and s['records'][z]['parent'] is not None}
    need_integer=anchor_set|s['terminals']
    for stage,zs in sorted(stages.items()):
        items=[];wire=[]
        for z in zs:
            d=s['records'][z];chain=[z];cur=d['parent']
            while cur is not None and (s['records'][cur]['depth']-2)//chunk==stage:chain.append(cur);cur=s['records'][cur]['parent']
            anchor=cur;xs=[i for old in reversed(chain) for i in s['records'][old]['bits']];count=len(xs)+(1 if anchor is not None else 0);flow=expression(1-count,{i:F(1) for i in xs})
            if anchor is not None:flow=plus(flow,mapping[anchor])
            C=F(count-1);assert C>=1
            hi=p.lin('Le',[[{'VarUpper':i},F(1)] for i in xs]+([[upper[anchor],F(1)]] if anchor is not None else []),plus(flow,expression(-1)))
            hcap=p.lin('Le',[[hi,F(1)]],plus(flow,expression(-C)),constant=1-C)
            lcap=p.lin('Le',[[{'VarLower':i},F(1)] for i in xs]+([[{'VarLower':layouts[anchor]['first']},F(1)]] if anchor is not None else []),plus(mul(flow,-1),expression(-C)))
            oldbound=p.lin('Le',[[{'RowUpper':s['records'][old]['row']},F(1)] for old in chain]+([[dom[anchor],F(1)]] if anchor is not None else []),plus(flow,var(z),-1))
            it=None
            if z in need_integer:it=p.lin('Int',[[{'VarInt':i},F(1)] for i in xs]+([[integer[anchor],F(1)]] if anchor is not None else []),flow,constant=1-count)
            items.append({'flow':flow,'capacity':C,'old':z,'oldbound':oldbound,'flow_upper':hi,'flow_integer':it,'anchor':anchor})
            wire.append({'capacity':str(C),'flow':expr_json(flow),'activation':expr_json(expression(1)),'checks':['Exact','Exact','Exact',hcap,lcap]})
        newlayouts=append_signed(m,items);layers.append((p,wire));p=Proof(m,p.counter,p.facts,p.assumptions)
        for d in newlayouts:
            z=d['old'];layouts[z]=d;mapping[z]=var(d['first']);wanted=plus(mapping[z],var(z),-1)
            dom[z]=sign_cases(p,d,'Le',wanted,lambda c,e:c.lin('Le',[[e,F(1)],[{'VarLower':z},F(1)]],wanted),lambda c,e:c.lin('Le',[[e,F(1)],[d['oldbound'],F(1)]],wanted))
            if z in need_integer:
                integer[z]=sign_cases(p,d,'Int',mapping[z],lambda c,e:c.lin('Int',[[e,F(1)]],mapping[z]),lambda c,e:c.lin('Int',[[e,F(1)],[d['flow_integer'],F(1)]],mapping[z]))
            if z in anchor_set:
                want=plus(mapping[z],expression(-1));upper[z]=sign_cases(p,d,'Le',want,lambda c,e:c.lin('Le',[[e,F(1)]],want,constant=-1),lambda c,e:c.lin('Le',[[e,F(1)],[d['flow_upper'],F(1)]],want))
            orig=s['records'][z];parent=orig['parent'];wanted=plus(sumexpr(mapping[i] for i in orig['bits']+([parent] if parent is not None else [])),plus(mapping[z],expression(1)),-1)
            cur_lower=p.lin('Le',[[{'RowEq':d['rows'][0]},F(-1)],[{'VarLower':d['first']+1},F(1)]],plus(d['flow'],mapping[z],-1))
            if parent is None or parent==d['anchor']:rowproof[orig['row']]=cur_lower;assert p.refexpr(cur_lower)==wanted
            else:
                previous=layouts[parent];bit=orig['bits'][0]
                rowproof[orig['row']]=sign_cases(p,previous,'Le',wanted,lambda c,e:c.lin('Le',[[e,F(1)],[{'VarUpper':bit},F(1)],[{'VarLower':d['first']},F(1)]],wanted),lambda c,e:c.lin('Le',[[e,F(1)],[cur_lower,F(1)]],wanted))
        print('canonical stage',stage,'items',len(zs),'vars',len(m['vars']),'facts',p.counter[0],flush=True)
    terminal_sum=sumexpr(mapping[z] for z in s['terminals']);terminal_integer=p.lin('Int',[[integer[z],F(1)] for z in s['terminals']],terminal_sum)
    children=[]
    for active in [False,True]:
        guard=plus(expression(1),terminal_sum,-1) if active else terminal_sum;q=Proof(m,p.counter,p.facts,p.assumptions+[guard]);g={'Assumption':len(p.assumptions)}
        if active:
            lower=q.lin('Le',[[base,F(1)],[g,F(4850)]]+[[dom[z],F(4850)] for z in s['terminals']],plus(expression(7283),a['objective'],-1))
            output=a if improvement else b;mp=[expression(s['point'][i]) for i in range(len(a['vars']))] if improvement else [expression(s['point'][a['var_index'][v['name']]]) for v in b['vars']]
            obj=lower if improvement else q.lin('Le',[[lower,F(1)]],plus(expression(6425),a['objective'],-1),constant=-858)
            children.append(emit(q,output,mp,{}, {},obj,'ImproveReturn' if improvement else 'Return',({'Constant':'858'},expression(858)) if improvement else None))
        else:
            if improvement:
                mp=[mapping[i] for i in range(len(a['vars']))];obj=q.lin('Le',[[dom[z],F(1)] for z in s['records'] if z not in s['terminals']]+[[g,F(4850)]],plus(plus(substitute(a['objective'],mp),a['objective'],-1),mul(positive,4850)))
                children.append(emit(q,a,mp,rowproof,{},obj,'ImproveReturn',({'Predicate':'4850'},mul(positive,4850))))
            else:
                mp=[mapping[a['var_index'][v['name']]] for v in b['vars']];rows={}
                for ri,r in enumerate(b['rows']):
                    ar=a['row_index'][r['name']];oldrow=a['rows'][ar];deleted=[z for z in oldrow['terms'] if z in s['terminals']]
                    if deleted:
                        z=deleted[0];others=[{'VarLower':layouts[t]['first']} for t in s['terminals'] if t!=z];zero=q.lin('Le',[[g,F(1)]]+[[r,F(1)] for r in others],mapping[z]);rows[ri]=q.lin('Le',[[rowproof[ar],F(1)],[zero,F(1)]],substitute(row_fact(r,'RowUpper'),mp))
                    else:rows[ri]=rowproof[ar]
                obj=q.lin('Le',[[dom[z],F(1)] for z in s['records'] if z not in s['terminals']]+[[{'VarLower':z},F(4850)] for z in s['terminals']],plus(substitute(b['objective'],mp),a['objective'],-1))
                children.append(emit(q,b,mp,rows,{},obj))
    block={'steps':p.steps,'end':{'Split':{'expression':expr_json(terminal_sum),'integer':terminal_integer,'left':children[0],'right':children[1]}}}
    for pre,wire in reversed(layers):block={'steps':pre.steps,'end':{'SignedLift':{'decompositions':wire,'body':block}}}
    return block


def reverse(a,b,s):
    p=Proof(b);mp=[var(s['retained'][i]) if i in s['retained'] else expression() for i in range(len(a['vars']))];rows={i:row_ref(b,r['name']) for i,r in enumerate(a['rows'])}
    return emit(p,a,mp,rows,{},None,'EqualReturn')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/next-contracts-initial/release/rpx'));ap.add_argument('--phase',choices=['inspect','forward','improvement','reverse'],default='inspect');args=ap.parse_args();run=Path('/Users/bhz/Code/reform_test/runs/test36-nomf-B1');root=Path('cases/test36');start=time.perf_counter();a=parse_mps(run/'input/model.mps');b=parse_mps(run/'output/reformulated.mps');h=json.loads((run/'output/audit.json').read_text());s=inspect(a,b,h);print('all actual fields classified',len(s['records']),len(s['terminals']),max(d['depth'] for d in s['records'].values()),flush=True)
    if args.phase=='inspect':return
    phase=args.phase;dest=root/('complete-'+phase);dest.mkdir(exist_ok=True);k=args.kernel.resolve();claim={'reverse':phase=='reverse','input_integers':True,'output_integers':True,'objective':'Equal' if phase=='reverse' else 'NonIncreasing','projection':[],'inverse':None}
    if phase=='improvement':
        improve={'target':False,'integers':True,'positive':expr_json(expression(0,{z:F(1) for z in s['terminals']}))};cert={'claims':[],'blocks':[],'improvements':[{'claim':improve,'block':canonical_root(a,b,s,True)}]};request={'claims':[],'improvements':[improve]}
    else:cert={'claims':[claim],'blocks':[reverse(a,b,s) if phase=='reverse' else canonical_root(a,b,s)]};request={'claims':[claim]}
    rp=dest/'proof.rpa';rp.write_text('RPA 10\n'+json.dumps(cert,separators=(',',':'))+'\n');(dest/'request.json').write_text(json.dumps(request,separators=(',',':'))+'\n');meta={'case_id':'test36','status':'PROOF_NOT_COMPLETED','scope':phase,'kernel_binary':{'path':str(k),'sha256':sha(k)},'preparation_seconds':time.perf_counter()-start,'kernel_runs':[]}
    def save():(dest/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
    save()
    commands=([['canonical',run/'input/model.mps',root/'source.mcm'],['canonical',run/'output/reformulated.mps',root/'target.mcm']] if not (root/'source.mcm').exists() or not (root/'target.mcm').exists() else [])+[['assemble',rp,dest/'proof.rpx'],['verify',root/'source.mcm',root/'target.mcm',dest/'proof.rpx',dest/'request.json']]
    for cmd in commands:
        before=sha(k);r=subprocess.run([str(k)]+list(map(str,cmd)),capture_output=True,text=True);meta['kernel_runs'].append({'command':[str(k)]+list(map(str,cmd)),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'binary_sha256_before':before,'binary_sha256_after':sha(k)});save()
        if r.returncode:raise SystemExit(r.stdout+r.stderr)
    meta['partial_status']='VERIFIED';meta['artifacts']={n:{'bytes':(dest/n).stat().st_size,'sha256':sha(dest/n)} for n in ['proof.rpa','proof.rpx','request.json']};save();print(meta['kernel_runs'][-1]['stdout'],flush=True)
if __name__=='__main__':main()
