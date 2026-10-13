#!/usr/bin/env python3
"""Actual test72 certificates using only checked linear, case and lift rules."""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse,json,time,subprocess,resource
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test48 import Proof,emit_checks
from prepare_test78 import rounded
from prepare_test21 import combine


def total(es):return combine(((e,F(1)) for e in es))
def var(i):return expression(0,{i:1})
def decoded(e):return expression(F(e['constant']),{i:F(c) for i,c in e['terms']})

class Layers:
    def __init__(self,model):
        self.model={**model,'vars':list(model['vars']),'rows':list(model['rows']),'var_index':dict(model['var_index']),'row_index':dict(model['row_index'])}
        self.p=Proof(self.model);self.layers=[]
    def next(self,kind,items):
        self.layers.append((self.p,kind,items));self.p=Proof(self.model,self.p.counter,self.p.facts,lookup=self.p.lookup)
    def menus(self,items):
        p=self.p;menus=[];out=[]
        for e,n,lo,hi,integer in items:
            menus.append({'maximum_index':n,'activation':expr_json(expression(1)),'index':expr_json(e),'checks':['Exact','Exact','Exact',lo,hi,integer]})
            start=len(self.model['vars'])
            for j in range(n+1):self.model['vars'].append({'name':f'menu_{start+j}','lower':F(0),'upper':F(1),'integer':True})
            refs=[]
            for row in [expression(-1,{start+j:1 for j in range(n+1)}),plus(expression(0,{start+j:j for j in range(n+1)}),e,-1)]:
                i=len(self.model['rows']);name=f'extension_row_{i}';self.model['row_index'][name]=i;self.model['rows'].append({'name':name,'sense':'E','rhs':-row[0],'terms':row[1]});refs.append({'RowEq':i})
            out.append({'start':start,'n':n,'index':e,'sum':refs[0],'moment':refs[1]})
        self.next('MenuLift',menus);return out
    def finish(self,body):
        for p,kind,items in reversed(self.layers):body={'steps':p.steps,'end':{kind:{'intervals' if kind=='IntervalLift' else 'menus':items,'body':body}}}
        return body

def integer_fact(p,e):
    if e[0]==0 and len(e[1])==1:
        i,c=next(iter(e[1].items()))
        if c==1:return {'VarInt':i}
    return p.lin('Int',[[{'VarInt':i},c] for i,c in e[1].items()],e,constant=e[0])

def bounds(p,e):
    lo=p.prove('Le',mul(e,-1));hi=p.prove('Le',plus(e,expression(-1)));it=integer_fact(p,e)
    return {'expr':e,'lower':lo,'upper':hi,'integer':it}

def fix(p,bit,v,guard):return p.eqpair(guard,bit['lower']) if v==0 else p.eqpair(bit['upper'],guard)

def exhaustive(p,kind,wanted,bits,leaf):
    def rec(cur,k,state):
        if k==len(bits):return leaf(cur,state)
        bit=bits[k]
        def side(child,g,v):return rec(child,k+1,state+[(v,fix(child,bit,v,g))])
        r=cur.cases(kind,wanted,bit,lambda q,g:side(q,g,0),lambda q,g:side(q,g,1));return {'Witness':r}
    return rec(p,0,[])['Witness']

def evaluated(p,e,state,es):
    terms=[];value=e[0]
    for (v,ref),x in zip(state,es):
        assert len(x[1])==1
        i,c=next(iter(x[1].items()));assert c==1
        coef=e[1].get(i,0);value+=coef*v
        if coef:terms.append([ref,coef])
    assert set(e[1])<=set(next(iter(x[1])) for x in es)
    return value,terms

def menu_zero(p,m,l,u,guard):
    n=m['n'];s=m['start'];out=[]
    if l>0:
        tail=expression(0,{s+j:1 for j in range(l)})
        refs=[[m['sum'],F(n,n-l+1)],[m['moment'],-F(1,n-l+1)],[guard,F(1,n-l+1)]]
        refs += [[{'VarLower':s+j},F((l-1-j) if j<l else (n-j),n-l+1)] for j in range(n+1) if ((l-1-j) if j<l else (n-j))]
        le=p.lin('Le',refs,plus(tail,expression(F(l-n,n-l+1))));integer=p.lin('Int',[[{'VarInt':i},c] for i,c in tail[1].items()],tail);out.append((rounded(p,le,integer),range(l)))
    if u<n:
        tail=expression(0,{s+j:1 for j in range(u+1,n+1)})
        refs=[[m['moment'],F(1,u+1)],[guard,F(1,u+1)]]
        refs += [[{'VarLower':s+j},F(j,u+1)-(1 if j>u else 0)] for j in range(n+1) if F(j,u+1)!=(1 if j>u else 0)]
        le=p.lin('Le',refs,plus(tail,expression(-F(u,u+1))));integer=p.lin('Int',[[{'VarInt':i},c] for i,c in tail[1].items()],tail);out.append((rounded(p,le,integer),range(u+1,n+1)))
    return out

def menu_segment(p,m,values,l,u,guard,alpha,beta):
    wanted=plus(expression(0,{m['start']+j:v for j,v in enumerate(values) if v}),plus(mul(m['index'],alpha),expression(beta)),-1)
    zeros=menu_zero(p,m,l,u,guard);base=[[m['sum'],beta],[m['moment'],alpha]]
    residual={j:F(values[j])-alpha*j-beta for j in range(m['n']+1)}
    def side(sign):
        refs=[[r,sign*c] for r,c in base if c]
        for zero,indices in zeros:
            scale=max([sign*residual[j] for j in indices]+[F(0)])
            if scale:refs.append([zero,scale])
            refs += [[{'VarLower':m['start']+j},scale-sign*residual[j]] for j in indices if scale!=sign*residual[j]]
        return p.lin('Le',refs,mul(wanted,sign))
    return p.eqpair(side(1),side(-1))

def menu_function(p,m,values,cut,left,right):
    e=expression(0,{m['start']+j:v for j,v in enumerate(values) if v});wanted=plus(e,expression(),-1)
    split=plus(m['index'],expression(-cut));bit={'expr':split,'integer':integer_fact(p,split)}
    def branch(q,g,low):
        l,u,alpha,beta=(0,cut,*left) if low else (cut+1,m['n'],*right)
        eq=menu_segment(q,m,values,l,u,g,F(alpha),F(beta));return {'Witness':eq}
    return e,bit,branch

def forward(a,b,h,claim):
    p=Proof(a);mapping=[var(a['var_index'][v['name']]) if v['name'] in a['var_index'] else None for v in b['vars']];rows={}
    for d in h['capacity_blocks']:
        q=b['var_index'][d['new_variable']];mapping[q]=expression(0,{a['var_index'][x['lambda_variable']]:F(x['cost']) for x in d['terms']})
        for cut in d['cuts']:
            if not cut['retained']:continue
            t=F(cut['threshold']);refs=[[row_ref(a,d['original_row']),t]]
            for x in d['terms']:
                c=F(x['cost']);i=a['var_index'][x['lambda_variable']]
                if c<t:refs.append([row_ref(a,x['upper_row']),t-c])
                if c>t:refs.append([{'VarLower':i},c-t])
            i=b['row_index'][cut['name']];wanted=substitute(row_fact(b['rows'][i],'RowLower'),mapping);rows[i]=p.lin('Le',refs,wanted)
    for d in h['clique_rows']:
        ri=b['row_index'][d['name']];wanted=substitute(row_fact(b['rows'][ri],'RowUpper'),mapping);ids=[a['var_index'][n] for n in d['variables']];bits=[bounds(p,var(i)) for i in ids];es=[x['expr'] for x in bits]
        def leaf(q,state):
            value,ts=evaluated(q,wanted,state,es)
            if value<=0:return {'Witness':q.lin('Le',ts,wanted,constant=value)}
            for rn in d['original_edge_rows']:
                r=row_ref(a,rn);val,refs=evaluated(q,q.refexpr(r),state,es)
                if val>0:return {'Absurd':q.lin('Le',[[r,F(1)]]+[[f,-c] for f,c in refs],expression(val))}
            raise AssertionError('uncovered clique')
        rows[ri]=exhaustive(p,'Le',wanted,bits,leaf)
    return emit_checks(p,b,mapping,claim,rows=rows)

def min_eq(p,d,K,guard,low,bound):
    if d['menu'] is None:
        if low:return p.lin('Eq',[],expression())
        assert d['k']==K==bound
        return p.eqpair(d['upper'],guard)
    m=d['menu'];values=[min(j,K) for j in range(m['n']+1)]
    return menu_segment(p,m,values,0 if low else bound,bound if low else m['n'],guard,F(1 if low else 0),F(0 if low else K))

def function_fact(p,m,values,cut,left,right,kind,wanted,leaf):
    e,bit,branch=menu_function(p,m,values,cut,left,right)
    def side(q,g,low):
        eq=branch(q,g,low)['Witness'];return leaf(q,g,low,eq)
    return p.cases(kind,wanted,bit,lambda q,g:side(q,g,True),lambda q,g:side(q,g,False))

def reverse_integer(a,b,h,claim):
    L=Layers(b);p=L.p;mapping=[var(b['var_index'][v['name']]) if v['name'] in b['var_index'] else None for v in a['vars']];domains={};rows={};menus=[];prefixes=[];special=[]
    for d in h['capacity_blocks']:
        K=d['K'];S=expression();seq=[{'expr':S,'count':S,'k':0,'menu':None,'lower':None,'upper':None}]
        for k,x in enumerate(sorted(d['terms'],key=lambda x:-x['cost']),1):
            y=var(b['var_index'][x['primary_variable']]);S=plus(S,y)
            lo=p.prove('Le',mul(S,-1));hi=p.prove('Le',plus(S,expression(-k)));integer=p.prove('Int',S);cur={'expr':S,'k':k,'menu':None,'lower':lo,'upper':hi,'term':x}
            if k>K:cur['menu_index']=len(menus);menus.append((S,k,lo,hi,integer))
            else:cur['count']=S
            seq.append(cur)
        prefixes.append((d,seq))
    incidence=defaultdict(list)
    for row in a['rows']:
        for i in row['terms']:incidence[i].append(row['name'])
    for name in h['relaxed_integer_variables']:
        i=a['var_index'][name];vi=b['var_index'][name];v=a['vars'][i];rs=incidence[i]
        if len(rs)==2 and v['upper']==1 and a['objective'][1].get(i,0)==0:
            link=next(rn for rn in rs if a['rows'][a['row_index'][rn]]['sense']=='L');row=a['rows'][a['row_index'][link]];ids=[b['var_index'][a['vars'][j]['name']] for j in row['terms'] if j!=i];e=expression(0,{j:1 for j in ids});n=len(ids);typ='day';values=[min(j,1) for j in range(n+1)];cut=0;left=(1,0);right=(0,1);req=e
        elif v['upper']==1 and a['objective'][1].get(i,0)==2:
            if not rs:mapping[i]=expression();continue
            assert len(rs)==1;link=rs[0];row=a['rows'][a['row_index'][link]];assert row['sense']=='G' and row['rhs']==0
            coeff={b['var_index'][a['vars'][j]['name']]:c for j,c in row['terms'].items() if j!=i};nneg=sum(c<0 for c in coeff.values());n=len(coeff);e=expression(nneg,coeff);typ='isolation';values=[max(0,nneg-j) for j in range(n+1)];cut=nneg-1;left=(-1,nneg);right=(0,0);req=expression(0,{j:-c for j,c in coeff.items()})
            if cut<0:mapping[i]=expression();continue
        else:mapping[i]=None;continue
        if n==0:
            mapping[i]=expression();special.append({'i':i,'vi':vi,'type':'day','menu_index':None,'dominate':row_ref(b,link)});continue
        mi=len(menus);menus.append((e,n,p.prove('Le',mul(e,-1)),p.prove('Le',plus(e,expression(-n))),p.prove('Int',e)));special.append({'i':i,'vi':vi,'link':link,'menu_index':mi,'type':typ,'values':values,'cut':cut,'left':left,'right':right,'req':req})
    ms=L.menus(menus);p=L.p
    for d,seq in prefixes:
        K=d['K']
        for cur in seq[1:]:
            if 'menu_index' in cur:
                m=ms[cur['menu_index']];cur['menu']=m;cur['count']=expression(0,{m['start']+j:min(j,K) for j in range(m['n']+1) if j})
                cur['prefix_upper']=p.lin('Le',[[m['moment'],1]]+[[{'VarLower':m['start']+j},j-K] for j in range(K+1,m['n']+1)],plus(cur['count'],cur['expr'],-1))
                cur['cap_upper']=p.lin('Le',[[m['sum'],K]]+[[{'VarLower':m['start']+j},K-j] for j in range(K)],plus(cur['count'],expression(-K)))
            else:
                cur['prefix_upper']=p.lin('Le',[],expression())
                cur['cap_upper']=p.lin('Le',[[cur['upper'],1]],plus(cur['count'],expression(-K)),constant=cur['k']-K)
        for prev,cur in zip(seq,seq[1:]):
            x=cur['term'];i=a['var_index'][x['lambda_variable']];y=var(b['var_index'][x['primary_variable']]);lam=plus(y,plus(cur['count'],prev['count'],-1),-1);mapping[i]=lam
            if prev['k']<K:
                # Both counts equal their actual prefixes.
                assert lam==expression();continue
            split=plus(prev['expr'],expression(1-K));bit={'expr':split,'integer':integer_fact(p,split)}
            wanted=mul(lam,-1)
            def lowerside(q,g,low):
                if low:
                    eq=min_eq(q,prev,K,g,True,K-1);refs=[[cur['prefix_upper'],1],[eq,-1]]
                else:
                    eq=min_eq(q,prev,K,g,False,K);refs=[[cur['cap_upper'],1],[eq,-1],[{'VarLower':b['var_index'][x['primary_variable']]},1]]
                return {'Witness':q.lin('Le',refs,wanted)}
            domains[(i,'VarLower')]=p.cases('Le',wanted,bit,lambda q,g:lowerside(q,g,True),lambda q,g:lowerside(q,g,False))
            ri=a['row_index'][x['upper_row']];wanted=plus(lam,y,-1)
            def linkside(q,g,low):
                if low:
                    gc=q.lin('Le',[[g,1],[{'VarUpper':b['var_index'][x['primary_variable']]},1]],plus(cur['expr'],expression(-K)));ec=min_eq(q,cur,K,gc,True,K);return {'Witness':q.lin('Le',[[prev['prefix_upper'],1],[ec,-1],[{'VarLower':b['var_index'][x['primary_variable']]},1]],wanted)}
                gc=q.lin('Le',[[g,1],[{'VarLower':b['var_index'][x['primary_variable']]},1]],plus(expression(K),cur['expr'],-1));ec=min_eq(q,cur,K,gc,False,K);return {'Witness':q.lin('Le',[[prev['cap_upper'],1],[ec,-1]],wanted)}
            rows[ri]=p.cases('Le',wanted,bit,lambda q,g:linkside(q,g,True),lambda q,g:linkside(q,g,False))
            domains[(i,'VarUpper')]=p.lin('Le',[[rows[ri],1],[{'VarUpper':b['var_index'][x['primary_variable']]},1]],plus(lam,expression(-1)))
        last=seq[-1];cap=plus(last['count'],expression(-K))
        if last['menu']:
            m=last['menu'];rows[a['row_index'][d['original_row']]]=p.lin('Le',[[m['sum'],K]]+[[{'VarLower':m['start']+j},K-min(j,K)] for j in range(m['n']+1) if j<K],cap)
        else:rows[a['row_index'][d['original_row']]]=p.prove('Le',cap)
    # Local retained integer reconstructions from exact menu moments.
    for z in special:
        if z['menu_index'] is None:continue
        m=ms[z['menu_index']];i=z['i'];vi=z['vi'];e=expression(0,{m['start']+j:v for j,v in enumerate(z['values']) if v});mapping[i]=e
        def prove_wanted(kind,wanted,which):
            def leaf(q,g,low,eq):
                alpha,beta=z['left'] if low else z['right'];aff=plus(mul(m['index'],alpha),expression(beta));refs=[[eq,1 if which in ('upper','dominate','linkiso') else -1]]
                if which=='upper':
                    if z['type']=='day':return {'Witness':q.prove('Le',wanted,[[m['sum'],1]]+[[{'VarLower':m['start']+j},1-z['values'][j]] for j in range(m['n']+1) if z['values'][j]!=1])}
                    if low:refs.append([row_ref(b,z['link']),1]);refs.append([{'VarUpper':vi},1])
                    else:refs=[];return {'Witness':q.lin('Le',[[eq,1]],wanted,constant=-1)}
                elif which=='dominate':
                    if z['type']=='day':
                        if low:refs=[[eq,-1],[row_ref(b,z['link']),1]]
                        else:refs=[[eq,-1],[{'VarUpper':vi},1]]
                    else:
                        if low:refs.append([row_ref(b,z['link']),1])
                        else:refs.append([{'VarLower':vi},1])
                elif which=='linkday':
                    if low:refs=[[eq,1]]
                    else:refs=[[eq,1],[g,1]]
                elif which=='linkiso':
                    if low:refs=[[eq,-1]]
                    else:refs=[[eq,-1],[g,1]]
                return {'Witness':q.lin('Le',refs,wanted)}
            return function_fact(p,m,z['values'],z['cut'],z['left'],z['right'],kind,wanted,leaf)
        # Positive menu combinations certify nonnegativity and integrality directly.
        domains[(i,'VarLower')]=p.lin('Le',[[{'VarLower':m['start']+j},v] for j,v in enumerate(z['values']) if v],mul(e,-1))
        domains[(i,'VarInt')]=p.prove('Int',e);domains[(i,'VarUpper')]=prove_wanted('Le',plus(e,expression(-1)),'upper')
        dominate=plus(var(vi),e,-1) if z['type']=='day' else plus(e,var(vi),-1);z['dominate']=prove_wanted('Le',dominate,'dominate')
        wanted=plus(e,z['req'],-1) if z['type']=='day' else plus(z['req'],e,-1);rows[a['row_index'][z['link']]]=prove_wanted('Le',wanted,'linkday' if z['type']=='day' else 'linkiso')
    shortmenus=[];shorts=[]
    for name in h['relaxed_integer_variables']:
        i=a['var_index'][name]
        if mapping[i] is None:
            assert a['objective'][1].get(i,0)==5
            rn=incidence[i][0];row=a['rows'][a['row_index'][rn]];days=[j for j in row['terms'] if j!=i];nonempty=[j for j in days if mapping[j]!=expression()];e=total(mapping[j] for j in days);n=len(days)
            lo=p.prove('Le',mul(e,-1),[[domains[(j,'VarLower')],1] for j in nonempty]);hi=p.prove('Le',plus(e,expression(-n)),[[domains[(j,'VarUpper')],1] for j in nonempty],constant=len(nonempty)-n);integer=p.prove('Int',e);shortmenus.append((e,n,lo,hi,integer));shorts.append({'i':i,'vi':b['var_index'][name],'rn':rn,'days':days,'m':int(row['rhs'])})
    sm=L.menus(shortmenus);p=L.p
    for z,m in zip(shorts,sm):
        values=[max(0,z['m']-j) for j in range(m['n']+1)];e=expression(0,{m['start']+j:v for j,v in enumerate(values) if v});i=z['i'];mapping[i]=e;domains[(i,'VarLower')]=p.lin('Le',[[{'VarLower':m['start']+j},v] for j,v in enumerate(values) if v],mul(e,-1));domains[(i,'VarInt')]=p.prove('Int',e)
        old=p.lin('Le',[[row_ref(b,z['rn']),1]]+[[next(t for t in special if t['i']==j)['dominate'],1] for j in z['days']],plus(expression(z['m']),plus(m['index'],var(z['vi'])),-1))
        def leaf(q,g,low,eq):
            refs=[[eq,1]]+([[old,1]] if low else [[{'VarLower':z['vi']},1]])
            return {'Witness':q.lin('Le',refs,plus(e,var(z['vi']),-1))}
        z['dominate']=function_fact(p,m,values,z['m']-1,(-1,z['m']),(0,0),'Le',plus(e,var(z['vi']),-1),leaf)
        domains[(i,'VarUpper')]=p.lin('Le',[[z['dominate'],1],[{'VarUpper':z['vi']},1]],plus(e,expression(-a['vars'][i]['upper'])))
        wanted=plus(expression(z['m']),plus(m['index'],e),-1)
        def rowleaf(q,g,low,eq):return {'Witness':q.lin('Le',[[eq,-1]]+([] if low else [[g,1]]),wanted)}
        rows[a['row_index'][z['rn']]]=function_fact(p,m,values,z['m']-1,(-1,z['m']),(0,0),'Le',wanted,rowleaf)
    # Each capacity cost is a threshold at the first cost-group prefix reaching K.
    costrefs=[]
    for d,seq in prefixes:
        K=d['K'];qidx=b['var_index'][d['new_variable']];cost=expression(0,{})
        for cur in seq[1:]:cost=plus(cost,mapping[a['var_index'][cur['term']['lambda_variable']]],cur['term']['cost'])
        wanted=plus(cost,var(qidx),-1);boundaries=[j for j in range(1,len(seq)) if j==len(seq)-1 or seq[j]['term']['cost']!=seq[j+1]['term']['cost']]
        coeffs={j:F(seq[j]['term']['cost']-(seq[j+1]['term']['cost'] if j<len(seq)-1 else 0)) for j in boundaries}
        def rec(curp,pos,lows):
            if pos==len(boundaries):
                refs=[[{'VarLower':qidx},1]]
                refs += [[eq,-coeffs[j]] for j,eq in lows.items()]
                return {'Witness':curp.lin('Le',refs,wanted)}
            j=boundaries[pos];node=seq[j];t=F(node['term']['cost']);split=plus(node['expr'],expression(1-K));bit={'expr':split,'integer':integer_fact(curp,split)}
            def low(child,g):
                eq=min_eq(child,node,K,g,True,K-1);return rec(child,pos+1,{**lows,j:eq})
            def high(child,g):
                if node['k']<K:return {'Absurd':child.lin('Le',[[g,1],[node['upper'],1]],expression(K-node['k']))}
                guard=child.lin('Le',[[g,1]],plus(expression(K),node['expr'],-1));eqs=dict(lows)
                for jj in boundaries[pos:]:
                    gg=guard if jj==j else child.lin('Le',[[guard,1]]+[[{'VarLower':b['var_index'][seq[k]['term']['primary_variable']]},1] for k in range(j+1,jj+1)],plus(expression(K),seq[jj]['expr'],-1));eqs[jj]=min_eq(child,seq[jj],K,gg,False,K)
                cut=next(x for x in d['cuts'] if x['threshold']==t);threshold=expression(-K*t,{b['var_index'][x['primary_variable']]:min(F(x['cost']),t) for x in d['terms']});threshold=plus(threshold,var(qidx),-1)
                tr=row_ref(b,cut['name']) if cut['retained'] else child.prove('Le',threshold,[[{'VarUpper':b['var_index'][x['primary_variable']]},min(F(x['cost']),t)] for x in d['terms']]+[[{'VarLower':qidx},1]],constant=cut['maximum_rhs_over_box'])
                return {'Witness':child.lin('Le',[[tr,1]]+[[eq,-coeffs[jj]] for jj,eq in eqs.items()],wanted)}
            ref=curp.cases('Le',wanted,bit,low,high);return {'Witness':ref}
        costrefs.append(rec(p,0,{})['Witness'])
    # Cliques imply all removed source edges by ordinary nonnegativity.
    for rn in h['removed_rows']:
        if rn in rows or rn not in a['row_index']:continue
        row=a['rows'][a['row_index'][rn]]
        if rn.startswith('CourseConflicts'):
            ids=set(row['terms']);cl=next(d for d in h['clique_rows'] if rn in d['original_edge_rows']);refs=[[row_ref(b,cl['name']),1]]+[[{'VarLower':b['var_index'][n]},1] for n in cl['variables'] if a['var_index'][n] not in ids];rows[a['row_index'][rn]]=p.lin('Le',refs,substitute(row_fact(row,'RowUpper'),mapping))
    objterms=[[r,1] for r in costrefs]+[[z['dominate'],2] for z in special if z['type']=='isolation']+[[z['dominate'],5] for z in shorts]
    # Objective-only isolation variables were set to zero.
    objterms += [[{'VarLower':b['var_index'][name]},2] for name in h['relaxed_integer_variables'] if a['objective'][1].get(a['var_index'][name],0)==2 and not incidence[a['var_index'][name]]]
    objective=p.lin('Le',objterms,plus(substitute(a['objective'],mapping),b['objective'],-1))
    body=emit_checks(p,a,mapping,claim,rows=rows,domains=domains,objective=objective)
    return L.finish(body)

def checked_intervals(L,specs):
    layout=[]
    for d in specs:
        i=len(L.model['vars']);L.model['vars'].append({'name':f'free_{i}','integer':False,'lower':None,'upper':None});cur={'expr':var(i),'lower':[],'upper':[]}
        for side,sense in [('lower','G'),('upper','L')]:
            for bound in d[side]:
                e=plus(var(i),decoded(bound),-1);ri=len(L.model['rows']);name=f'extension_row_{ri}';L.model['row_index'][name]=ri;L.model['rows'].append({'name':name,'sense':sense,'rhs':-e[0],'terms':e[1]});cur[side].append({('RowLower' if sense=='G' else 'RowUpper'):ri})
        layout.append(cur)
    L.next('IntervalLift',specs);return layout

def reverse_lp(a,b,h,claim):
    L=Layers(b);p=L.p;mapping=[var(b['var_index'][v['name']]) if v['name'] in b['var_index'] else None for v in a['vars']];states=[];rows={};domains={};allocations=[];distribution_eq=[]
    def ys(xs):return expression(0,{b['var_index'][x['primary_variable']]:1 for x in xs})
    for d in h['capacity_blocks']:
        groups=defaultdict(list)
        for x in d['terms']:groups[F(x['cost'])].append(x)
        gs=[{'cost':c,'members':groups[c]} for c in sorted(groups,reverse=True)];q=var(b['var_index'][d['new_variable']]);K=expression(d['K']);thresholds={F(0):{'VarLower':b['var_index'][d['new_variable']]}}
        for cut in d['cuts']:
            t=F(cut['threshold']);e=plus(expression(-d['K']*t,{b['var_index'][x['primary_variable']]:min(F(x['cost']),t) for x in d['terms']}),q,-1)
            thresholds[t]=row_ref(b,cut['name']) if cut['retained'] else p.prove('Le',e)
        states.append({'d':d,'groups':gs,'K':K,'q':q,'thresholds':thresholds,'nonnegative_K':p.lin('Le',[],mul(K,-1),constant=-d['K'])})
    for k in range(max(len(s['groups']) for s in states)):
        specs=[];active=[]
        for s in states:
            if k>=len(s['groups']):continue
            g=s['groups'][k];y=ys(g['members']);c=g['cost'];remaining=s['groups'][k+1:];needed={F(0)}|{z['cost'] for z in remaining};lowers=[expression()];lower_t=[]
            for t in sorted(needed):
                assert t<c
                et=p.refexpr(s['thresholds'][t]);lowers.append(plus(y,mul(et,F(1,c-t))));lower_t.append(t)
            upper=[y,s['K']];checks=[]
            for j,lo in enumerate(lowers):
                if j==0:checks.extend([p.prove('Le',mul(y,-1)),s['nonnegative_K']])
                else:
                    t=lower_t[j-1];checks.append(p.lin('Le',[[s['thresholds'][t],F(1,c-t)]],plus(lo,y,-1)))
                    refs=[[s['thresholds'][c],F(1,c-t)]]+[[{'VarLower':b['var_index'][x['primary_variable']]},F(z['cost']-min(z['cost'],t),c-t)] for z in remaining for x in z['members'] if z['cost']!=min(z['cost'],t)]
                    checks.append(p.lin('Le',refs,plus(lo,s['K'],-1)))
            specs.append({'lower':[expr_json(e) for e in lowers],'upper':[expr_json(e) for e in upper],'checks':checks});active.append((s,g,y,c,remaining,needed,lower_t))
        layout=checked_intervals(L,specs);p=L.p
        for (s,g,y,c,remaining,needed,lower_t),cur in zip(active,layout):
            free=cur['expr'];allocations.append({'members':g['members'],'amount':free,'lower':cur['lower'][0],'upper':cur['upper'][0]})
            K=plus(s['K'],free,-1);q=plus(s['q'],mul(plus(y,free,-1),c),-1);thresholds={}
            for t in needed:
                et=plus(total(mul(ys(z['members']),min(z['cost'],t)) for z in remaining),plus(mul(K,t),q),-1)
                thresholds[t]=p.lin('Le',[[cur['lower'][1+lower_t.index(t)],c-t]],et)
            s.update(K=K,q=q,thresholds=thresholds,nonnegative_K=cur['upper'][1])
    costrefs=[s['thresholds'][F(0)] for s in states]
    # Balanced bounded-sum distribution uses logarithmic, not 78, lift depth.
    for _ in range(7):
        specs=[];split=[]
        for d in allocations:
            if len(d['members'])<=1:continue
            mid=len(d['members'])//2;left,right=d['members'][:mid],d['members'][mid:];yl,yr=ys(left),ys(right);amount=d['amount'];lower=[expression(),plus(amount,yr,-1)];upper=[yl,amount]
            checks=[p.prove('Le',mul(yl,-1)),d['lower'],d['upper'],p.prove('Le',mul(yr,-1))]
            specs.append({'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':checks});split.append((d,left,right,yl,yr))
        if not specs:break
        layout=checked_intervals(L,specs);p=L.p;new=[d for d in allocations if len(d['members'])<=1]
        for (d,left,right,yl,yr),cur in zip(split,layout):
            x=cur['expr'];new.extend([{'members':left,'amount':x,'lower':cur['lower'][0],'upper':cur['upper'][0]},{'members':right,'amount':plus(d['amount'],x,-1),'lower':cur['upper'][1],'upper':cur['lower'][1]}])
        allocations=new
    assert all(len(d['members'])==1 for d in allocations)
    for d in allocations:
        x=d['members'][0];i=a['var_index'][x['lambda_variable']];y=ys(d['members']);lam=plus(y,d['amount'],-1);mapping[i]=lam;domains[(i,'VarLower')]=d['upper'];domains[(i,'VarUpper')]=p.lin('Le',[[d['lower'],1],[{'VarUpper':b['var_index'][x['primary_variable']]},1]],plus(lam,expression(-1)));rows[a['row_index'][x['upper_row']]]=d['lower']
    for s in states:rows[a['row_index'][s['d']['original_row']]]=s['nonnegative_K']
    for d in h['clique_rows']:
        for rn in d['original_edge_rows']:
            if a['row_index'][rn] in rows:continue
            row=a['rows'][a['row_index'][rn]];ids=set(row['terms']);refs=[[row_ref(b,d['name']),1]]+[[{'VarLower':b['var_index'][name]},1] for name in d['variables'] if a['var_index'][name] not in ids];rows[a['row_index'][rn]]=p.lin('Le',refs,substitute(row_fact(row,'RowUpper'),mapping))
    objective=p.lin('Le',[[r,1] for r in costrefs],plus(substitute(a['objective'],mapping),b['objective'],-1))
    body=emit_checks(p,a,mapping,claim,rows=rows,domains=domains,objective=objective)
    return L.finish(body)

def prepare(source,target,audit):
    a,b=parse_mps(source),parse_mps(target);h=json.loads(audit.read_text());proj=[[a['var_index'][n],b['var_index'][n]] for n in h['primary_binary_variables']]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':proj,'inverse':None},{'reverse':True,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[[j,i] for i,j in proj],'inverse':None},{'reverse':True,'input_integers':False,'output_integers':False,'objective':'NonIncreasing','projection':[[j,i] for i,j in proj],'inverse':None}]
    cert={'claims':claims,'blocks':[forward(a,b,h,claims[0]),reverse_integer(a,b,h,claims[1]),reverse_lp(a,b,h,claims[2])]}
    return cert,{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'primary_observations':len(proj),'capacity_blocks':len(h['capacity_blocks']),'largest_capacity_block':max(len(d['terms']) for d in h['capacity_blocks']),'claims':3},'Forward integer Equal and reverse integer NonIncreasing maps preserve all 2608 primary binary observations. Opposing nonincreasing maps establish equality of extended infima for EACH integer primary assignment (the minimum-completion-cost epigraph is a derived consequence, not an additional kernel claim). Reverse continuous NonIncreasing inclusion also preserves the primary coordinates and reconstructs all eliminated fractional capacity auxiliaries by checked exact interval premises. Forward capacity threshold identities are independent of integrality, but no source-LP-to-target-LP map or full-model LP equality is certified: the forward clique proof requires binary Cases and excludes fractional edge-box points locally. Auxiliary completions are not claimed unique.'

def block_depth(block):
    children=[]
    for s in block['steps']:
        if 'Cases' in s:children.extend([s['Cases']['left'],s['Cases']['right']])
    for kind in ['IntervalLift','MenuLift']:
        if kind in block['end']:children.append(block['end'][kind]['body'])
    return 1+max([block_depth(c) for c in children]+[0])

def wave_schedule(block):
    result=[]
    while 'Return' not in block['end']:
        kind=next(iter(block['end']));lift=block['end'][kind];result.append({'kind':kind,'witnesses':len(lift['intervals' if kind=='IntervalLift' else 'menus'])});block=lift['body']
    return result

def write_rpa(path,cert):
    with path.open('w') as stream:
        stream.write('RPA 7\n');json.dump(cert,stream,separators=(',',':'));stream.write('\n')

def execute(case,run,out,kernel,preparer,work=None):
    started=time.perf_counter();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';cert,counts,contract=preparer(source,target,audit);rpa=out/'proof.rpa';request=out/'request.json';write_rpa(rpa,cert);request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    counts['block_depths']=[block_depth(c) for c in cert['blocks']];counts['lift_wave_schedule_by_claim']=[wave_schedule(c) for c in cert['blocks']]
    script=Path(__file__) if case=='test72' else Path(__file__).with_name('prepare_'+case+'.py')
    receipt={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(script.resolve()),'sha256':sha(script)},'claims':contract,'counts':counts,'preparation_seconds':time.perf_counter()-started,'peak_preparer_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[],'negative_checks':[]}
    kernel=kernel.resolve();receipt['kernel_binary_sha256']=sha(kernel)
    if case=='test72' and (out/'work_profile.json').exists():receipt['per_claim_work_profile']={'path':str(out/'work_profile.json'),'sha256':sha(out/'work_profile.json'),'results':json.loads((out/'work_profile.json').read_text())}
    receipt['kernel_limits_note']='Default work limit 1000000000; '+(f'this run uses explicit --work {work}.' if work is not None else 'this run uses the default limits.')
    def save():(out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def invoke(args,use_override=True):
        if args[0]=='verify' and work is not None and use_override:args=['verify','--work',str(work),*args[1:]]
        begin=time.perf_counter();p=subprocess.run([str(kernel),*map(str,args)],capture_output=True,text=True);d={'command':[str(kernel),*map(str,args)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'seconds':time.perf_counter()-begin};receipt['kernel_runs'].append(d);save();print(json.dumps(d),flush=True);return d
    save()
    for args in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]:
        result=invoke(args)
        if result['exit_code']:
            receipt['status']=json.loads(result['stdout']).get('status','EXECUTION_FAILED');save();raise RuntimeError(result)
    receipt['status']='VERIFIED';receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};save()
    verified=json.loads(result['stdout']);receipt['limits']=verified['limits'];receipt['verify_statistics']=verified['statistics']
    receipt['rpx_bytes']=(out/'proof.rpx').stat().st_size
    tests=[('lost_primary_observation','Change a mapped retained primary while retaining its observation obligations.',cert['blocks'][0]['end']['Return']['map'],cert['claims'][0]['projection'][0][1],expr_json(expression())),('caller_objective_mismatch','Weaken objective relation in certificate without changing the caller request.',cert['claims'][0],'objective','None'),('lost_source_premise','Drop a substantive source row premise from a forward derivation.',next(step['Lin']['terms'] for step in cert['blocks'][0]['steps'] if 'Lin' in step and step['Lin']['terms']),0,None)]
    for name,why,container,key,value in tests:
        old=container[key]
        if value is None:container[key]=[old[0],'0']
        else:container[key]=value
        mutant=out/(name+'.rpa');encoded=out/(name+'.rpx');write_rpa(mutant,cert);container[key]=old
        assembled=invoke(['assemble',mutant,encoded]);assert assembled['exit_code']==0,assembled
        rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',encoded,request]);j=json.loads(rejected['stdout']);assert rejected['exit_code']==2 and j['status']=='INVALID',rejected
        receipt['negative_checks'].append({'mutation':name,'rule_broken':why,'exit_code':2,'result':j,'rpa_sha256':sha(mutant),'rpx_sha256':sha(encoded),'storage':'Mutated files deleted; deterministic recipe retained in preparer.'});mutant.unlink();encoded.unlink();save()
    if case=='test72':
        old=cert['claims'][0];cert['claims'][0]={**old,'input_integers':False,'output_integers':False};mutant=out/'false_forward_lp.rpa';encoded=out/'false_forward_lp.rpx';badrequest=out/'false_forward_lp.request.json'
        write_rpa(mutant,cert);badrequest.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n');cert['claims'][0]=old
        assert invoke(['assemble',mutant,encoded])['exit_code']==0
        rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',encoded,badrequest]);j=json.loads(rejected['stdout']);assert rejected['exit_code']==2 and j['status']=='INVALID',rejected
        receipt['negative_checks'].append({'mutation':'false_forward_lp','rule_broken':'Request and certificate both claim the unsupported source LP direction; integer clique Cases cannot justify the LP map.','exit_code':2,'result':j,'rpa_sha256':sha(mutant),'rpx_sha256':sha(encoded),'request_sha256':sha(badrequest)});mutant.unlink();encoded.unlink();badrequest.unlink();save()
    again=out/'determinism.rpx';assert invoke(['assemble',rpa,again])['exit_code']==0;assert sha(again)==sha(out/'proof.rpx');again.unlink();receipt['assemble_byte_deterministic']=True
    if work is None and verified['statistics']['work']>100000000:
        budget=((verified['statistics']['work']*115+999999999)//1000000000)*10000000
        override=invoke(['verify','--work',str(budget),out/'source.mcm',out/'target.mcm',out/'proof.rpx',request],False);assert override['exit_code']==0
        receipt['recorded_override_limits']=json.loads(override['stdout'])['limits']
    for _ in range(2):
        v=invoke(['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]);assert v['exit_code']==0 and json.loads(v['stdout'])['status']=='VERIFIED'
    receipt['deterministic_reverify_count']=2
    if work is not None:
        default=invoke(['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request],False);assert default['exit_code']==0
        receipt['recorded_override_limits']=receipt['limits'];receipt['limits']=json.loads(default['stdout'])['limits']
        receipt['kernel_limits_note']=f'Default work limit 1000000000; no override is required. Explicit --work {work} additionally verified as a comfortable measured work margin. The final run uses no flags for generic replay.'
    assert sha(rpa)==receipt['rpa_sha256']
    assert all(sha(out/name)==info['sha256'] for name,info in receipt['artifacts'].items())
    assert sha(kernel)==receipt['kernel_binary_sha256']
    receipt['artifact_hashes_stable_after_receipt']=True;save()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));ap.add_argument('--work',type=int);args=ap.parse_args();run=Path('/Users/bhz/Code/reform_test/runs/test72-nomf-B1');out=Path('cases/test72');execute('test72',run,out,args.kernel,prepare,args.work)

if __name__=='__main__':main()
