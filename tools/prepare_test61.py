#!/usr/bin/env python3
"""Exact test61 Boolean bijection and continuous interval completion.

Fourier-Motzkin elimination and small exact conic searches are untrusted
preparation. Every multiplier is checked before ordinary Lin, Cases and
IntervalLift certificates are emitted. Actual retained cycles are untouched.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import ChainMap
import argparse,copy,itertools,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test70 import SparseBuilder
from prepare_test88 import fix_binary
from prepare_test84 import rounded
from menu_injectivity import make_paired_model


def key(e):return tuple(sorted(e[1].items()))
def normalize(e):
    if not e[1]:return e,F(1)
    scale=abs(next(c for i,c in sorted(e[1].items())))
    return mul(e,1/scale),scale

def dedup(es):
    result={}
    for e in es:
        e,_=normalize(e);k=key(e)
        if k not in result or e[0]>result[k][0]:result[k]=e
    return list(result.values())


def cases(p,kind,wanted,variables,leaf):
    def recurse(q,j,assigned):
        if j==len(variables):return leaf(q,assigned)
        v=variables[j];ident=q.alloc();branches=[];split=expression(0,{v:1})
        for value in (0,1):
            assumption=split if value==0 else expression(1,{v:-1});child=SparseBuilder(q.model,q.counter,assumptions=q.assumptions+[assumption]);child.facts=ChainMap({},q.facts)
            fixed=fix_binary(child,v,value,{'Assumption':len(q.assumptions)});end=recurse(child,j+1,{**assigned,v:(F(value),fixed)});branches.append({'steps':child.steps,'end':end})
        q.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),'split':expr_json(split),'integer':{'VarInt':v},'left':branches[0],'right':branches[1]}});q.facts[ident]=(kind,wanted);return {'Witness':{'Local':ident}}
    return recurse(p,0,{})['Witness']


def fixed_expr(p,e,assigned,kind='Le'):
    value=e[0]+sum(c*assigned[i][0] for i,c in e[1].items());assert kind!='Eq' or value==0
    assert kind!='Le' or value<=0,(e,value)
    return p.lin(kind,[[assigned[i][1],c] for i,c in e[1].items()],e,constant=value)


def reduce_ref(p,ref,assigned):
    e=p.refexpr(ref);return p.lin(p.kind(ref),[[ref,1]]+[[assigned[i][1],-c] for i,c in e[1].items() if i in assigned])


def source_pattern(p,a,d,name,assigned,voffset=0,roffset=0):
    v=a['var_index'][name]+voffset
    if name in d['fixed_zero_terms']:
        rn=next(r['name'] for r in a['rows'] if r['sense']=='E' and set(r['terms'])=={a['var_index'][name]});ref={'RowEq':a['row_index'][rn]+roffset};assert p.refexpr(ref)==expression(0,{v:1});return F(0),ref
    term=d['active_terms'][name];value=F(all(assigned[a['var_index'][vn]+voffset][0]==(1 if F(sign)>0 else 0) for vn,sign in term['inputs'].items()))
    refs=[]
    for rn in term['rows']:
        ref=row_ref(a,rn);typ,ri=next(iter(ref.items()));refs.append(reduce_ref(p,{typ:ri+roffset},assigned))
    if value:
        lower=next(r for r in refs if p.refexpr(r)[1].get(v)==-1);assert p.refexpr(lower)==expression(1,{v:-1});upper={'VarUpper':v}
    else:
        upper=next(r for r in refs if p.refexpr(r)[1].get(v)==1);upper=rounded(p,upper,{'VarInt':v});assert p.refexpr(upper)==expression(0,{v:1});lower={'VarLower':v}
    return value,p.eqpair(upper,lower)


def target_local_refs(b,h):
    out={root:[] for root in h['blocks']}
    for d in h['all_facet_translation_records']:
        if d['generated_row'] is not None:out[d['root']].append(row_ref(b,d['generated_row']))
    return out


def solve_columns(columns,goal):
    """Solve a full-column-rank rectangular system with exact small elimination."""
    if not columns:return None
    width=len(columns);matrix=[[columns[j][i] for j in range(width)]+[goal[i]] for i in range(len(goal))];pivot=0
    for j in range(width):
        row=next((i for i in range(pivot,len(matrix)) if matrix[i][j]),None)
        if row is None:return None
        matrix[pivot],matrix[row]=matrix[row],matrix[pivot];scale=matrix[pivot][j];matrix[pivot]=[x/scale for x in matrix[pivot]]
        for i in range(len(matrix)):
            if i!=pivot and matrix[i][j]:
                scale=matrix[i][j];matrix[i]=[a-scale*b for a,b in zip(matrix[i],matrix[pivot])]
        pivot+=1
    if any(not any(row[:-1]) and row[-1] for row in matrix):return None
    return [matrix[j][-1] for j in range(width)]


class Dual:
    def __init__(self):self.cache={};self.calls=0
    def prove(self,p,e,refs):
        if not e[1] and e[0]<=0:return 'Exact'
        # Box support certificates need no numerical proposal.
        if all(p.model['vars'][i]['lower'] is not None and p.model['vars'][i]['upper'] is not None for i in e[1]):
            maximum=e[0]+sum(c*p.model['vars'][i]['upper' if c>0 else 'lower'] for i,c in e[1].items())
            if maximum<=0:return p.lin('Le',[[{'VarUpper' if c>0 else 'VarLower':i},abs(c)] for i,c in e[1].items()],e,constant=maximum)
        facts=[p.refexpr(r) for r in refs];coords=sorted(set(e[1])|{i for f in facts for i in f[1]});pos={i:j for j,i in enumerate(coords)}
        cachekey=(tuple((p.kind(r),f[0],tuple((pos[i],c) for i,c in sorted(f[1].items()))) for r,f in zip(refs,facts)),e[0],tuple((pos[i],c) for i,c in sorted(e[1].items())))
        if cachekey in self.cache:mult,constant=self.cache[cachekey]
        else:
            columns=[[f[1].get(i,F(0)) for i in coords] for f in facts];goal=[e[1].get(i,F(0)) for i in coords];self.calls+=1;answer=None;tried=set()
            # Corner maximizers commonly expose a tiny conic basis. Their use is
            # only a search heuristic; the eventual rational Lin identity is authority.
            candidates=[]
            for values in itertools.product((F(0),F(1)),repeat=len(coords)):
                activities=[f[0]+sum(c*x for c,x in zip(column,values)) for f,column in zip(facts,columns)]
                if all(activity==0 if p.kind(ref)=='Eq' else activity<=0 for ref,activity in zip(refs,activities)):
                    candidates.append((e[0]+sum(c*x for c,x in zip(goal,values)),tuple(j for j,activity in enumerate(activities) if activity==0)))
            sets=[active for value,active in sorted(candidates,reverse=True)]+[tuple(range(len(refs)))]
            for active in sets:
                for size in range(1,min(len(coords),len(active))+1):
                    for chosen in itertools.combinations(active,size):
                        if chosen in tried:continue
                        tried.add(chosen);coeff=solve_columns([columns[j] for j in chosen],goal)
                        if coeff is None or any(c<0 and p.kind(refs[j])!='Eq' for j,c in zip(chosen,coeff)):continue
                        constant=e[0]-sum(facts[j][0]*c for j,c in zip(chosen,coeff))
                        if constant>0:continue
                        mult=[F(0)]*len(refs)
                        for j,c in zip(chosen,coeff):mult[j]=c
                        answer=(mult,constant);break
                    if answer is not None:break
                if answer is not None:break
            assert answer is not None,('no exact conic certificate',e)
            mult,constant=answer
            self.cache[cachekey]=(mult,constant)
        return p.lin('Le',[[r,c] for r,c in zip(refs,mult) if c],e,constant=constant)


def forward(a,b,h):
    p=SparseBuilder(a);mapping=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];checks=[];byrow={d['generated_row']:d['root'] for d in h['all_facet_translation_records'] if d['generated_row']}
    for e in mapping:
        i=next(iter(e[1]));checks.extend([{'VarLower':i},{'VarUpper':i},{'VarInt':i}])
    for row in b['rows']:
        root=byrow[row['name']];d=h['blocks'][root];typ='RowEq' if row['sense']=='E' else 'RowUpper';wanted=substitute(row_fact(row,typ),mapping);kind='Eq' if typ=='RowEq' else 'Le';variables=sorted({a['var_index'][v] for v in d['original_inputs']})
        def leaf(q,assigned):
            assigned=dict(assigned)
            for name in d['original_terms']:assigned[a['var_index'][name]]=source_pattern(q,a,d,name,assigned)
            rv=a['var_index'][root];value=F(any(assigned[a['var_index'][vn]][0] for vn in d['original_terms']))
            if rv not in assigned:
                bound=next(reduce_ref(q,row_ref(a,rn),assigned) for rn in d['original_or_rows'] if q.refexpr(row_ref(a,rn))[1][rv]==(1 if value==0 else -1))
                if value:bound=rounded(q,bound,q.lin('Int',[[{'VarInt':rv},-1]],expression(0,{rv:-1})));assert q.refexpr(bound)==expression(1,{rv:-1});eq=q.eqpair({'VarUpper':rv},bound)
                else:assert q.refexpr(bound)==expression(0,{rv:1});eq=q.eqpair(bound,{'VarLower':rv})
                assigned[rv]=(value,eq)
            elif assigned[rv][0]!=value:
                for rn in d['original_or_rows']:
                    ref=reduce_ref(q,row_ref(a,rn),assigned);e=q.refexpr(ref)
                    if not e[1] and e[0]>0:return {'Absurd':ref}
                raise AssertionError('self-dependent source contradiction missing')
            return {'Witness':fixed_expr(q,wanted,assigned,kind)}
        checks.append(cases(p,kind,wanted,variables,leaf))
    checks.append('Exact');checks+=['Exact']*len(mapping)
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[next(iter(e[1])),j] for j,e in enumerate(mapping)],'inverse':None}
    return claim,{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}},mapping


def add_interval_model(model,intervals):
    generated=[]
    for lower,upper in intervals:
        v=len(model['vars']);model['vars'].append({'name':f'$interval{v}','integer':False,'lower':None,'upper':None});refs=[]
        for bounds,is_lower in [(lower,True),(upper,False)]:
            for e in bounds:
                terms=mul(e,-1)[1];terms={**terms,v:F(1)};ri=len(model['rows']);model['rows'].append({'name':f'$interval{ri}','sense':'G' if is_lower else 'L','rhs':e[0],'terms':terms});refs.append({'RowLower' if is_lower else 'RowUpper':ri})
        generated.append((v,refs))
    return generated


def integer_reverse(a,b,h,local):
    model=copy.deepcopy(b);parent=SparseBuilder(model);intervals=[];private=[];mapping=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    for root,d in h['blocks'].items():
        for name,td in d['active_terms'].items():
            literals=[expression(0,{b['var_index'][vn]:1}) if F(sign)>0 else expression(1,{b['var_index'][vn]:-1}) for vn,sign in td['inputs'].items()];total=expression(-2)
            for e in literals:total=plus(total,e)
            lower=[expression(),total];upper=literals;refs=[parent.lin('Le',[[{'VarUpper' if c>0 else 'VarLower':i},abs(c)] for i,c in plus(lo,up,-1)[1].items()],plus(lo,up,-1),constant=plus(lo,up,-1)[0]+sum(max(F(0),c) for c in plus(lo,up,-1)[1].values())) for lo in lower for up in upper]
            intervals.append({'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':refs});private.append((root,name,lower,upper))
    generated=add_interval_model(model,[(lo,up) for _,_,lo,up in private]);p=SparseBuilder(model,parent.counter,facts=parent.facts);bounds={};ints={};liftrefs={}
    for (root,name,lower,upper),(v,refs) in zip(private,generated):mapping[a['var_index'][name]]=expression(0,{v:1});liftrefs[name]=(v,refs,lower,upper)
    def fixed_private(q,name,d,assigned):
        if name in d['fixed_zero_terms']:return F(0),None
        v,refs,lo,up=liftrefs[name];td=d['active_terms'][name];value=F(all(assigned[b['var_index'][vn]][0]==(1 if F(sign)>0 else 0) for vn,sign in td['inputs'].items()))
        lower=reduce_ref(q,refs[1] if value else refs[0],assigned);upper=next(reduce_ref(q,r,assigned) for r in refs[2:] if reduce_value(q,r,assigned)==expression(-value,{v:1}))
        assert q.refexpr(lower)==expression(value,{v:-1});return value,q.eqpair(upper,lower)
    for root,name,_,_ in private:
        d=h['blocks'][root];v=liftrefs[name][0];variables=sorted({b['var_index'][vn] for vn in d['active_terms'][name]['inputs']});wanted=expression(0,{v:1})
        def leaf(q,assigned):
            value,ref=fixed_private(q,name,d,assigned);return {'Witness':q.lin('Int',[[ref,1]],wanted,constant=value)}
        ints[name]=cases(p,'Int',wanted,variables,leaf)
    # Domain and conjunction inequalities are direct combinations of interval rows.
    dual=Dual();checks=[]
    for i,var in enumerate(a['vars']):
        e=mapping[i];name=var['name']
        if name in b['var_index']:
            v=b['var_index'][name];checks.extend([{'VarLower':v},{'VarUpper':v},{'VarInt':v}])
        elif name not in liftrefs:checks+=['Exact']*3
        else:
            v,refs,_,_=liftrefs[name];checks.append(refs[0]);upper=dual.prove(p,plus(e,expression(-1)),refs+[{'VarLower':j} for j in set().union(*(set(x[1]) for x in liftrefs[name][3]))]+[{'VarUpper':j} for j in set().union(*(set(x[1]) for x in liftrefs[name][3]))]);checks.append(upper);checks.append(ints[name])
    orrows={rn:root for root,d in h['blocks'].items() for rn in d['original_or_rows']};termrows={rn:name for d in h['blocks'].values() for name,td in d['active_terms'].items() for rn in td['rows']}
    for row in a['rows']:
        typ=next(iter(row_ref(a,row['name'])));wanted=substitute(row_fact(row,typ),mapping)
        if row['sense']=='E':checks.append('Exact');continue
        if row['name'] in termrows:
            name=termrows[row['name']];_,refs,_,upper=liftrefs[name];coords=set().union(*(set(e[1]) for e in upper));checks.append(dual.prove(p,wanted,refs+[{'VarLower':i} for i in sorted(coords)]+[{'VarUpper':i} for i in sorted(coords)]));continue
        root=orrows[row['name']];d=h['blocks'][root];variables=sorted({b['var_index'][vn] for vn in d['original_inputs']+[root]})
        def leaf(q,assigned):
            val={vn:assigned[b['var_index'][vn]][0] for vn in d['original_inputs']};result=any(all(val[vn]==(1 if F(sign)>0 else 0) for vn,sign in td['inputs'].items()) for td in d['active_terms'].values())
            if assigned[b['var_index'][root]][0]!=int(result):
                for ref in local[root]:
                    e=q.refexpr(ref);value=e[0]+sum(c*assigned[i][0] for i,c in e[1].items())
                    if value>0 or q.kind(ref)=='Eq' and value!=0:return {'Absurd':reduce_ref(q,ref,assigned)}
                raise AssertionError(('target local assignment not excluded',root,val))
            assignment=dict(assigned)
            for name in d['active_terms']:
                v=liftrefs[name][0];assignment[v]=fixed_private(q,name,d,assigned)
            return {'Witness':fixed_expr(q,wanted,assignment)}
        checks.append(cases(p,'Le',wanted,variables,leaf))
    checks.append('Exact');projection=[[b['var_index'][v['name']],i] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']];checks+=['Exact']*len(projection)
    # A bijection asks for F(G(y))=y independently of the injectivity proof.
    checks+=['Exact']*len(b['vars'])
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':None}
    return claim,{'steps':parent.steps,'end':{'IntervalLift':{'intervals':intervals,'body':{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}}}}


def reduce_value(p,ref,assigned):
    e=p.refexpr(ref);return expression(e[0]+sum(c*assigned[i][0] for i,c in e[1].items() if i in assigned),{i:c for i,c in e[1].items() if i not in assigned})


def injectivity(a,b,h,forward_map):
    model=make_paired_model(a,forward_map);p=SparseBuilder(model);n=len(a['vars']);r=len(a['rows']);equal={};core={a['var_index'][v['name']]:{'RowEq':2*r+j} for j,v in enumerate(b['vars'])}
    equal.update(core)
    for root,d in h['blocks'].items():
        for name in d['original_terms']:
            v=a['var_index'][name];wanted=expression(0,{v:1,v+n:-1})
            if name in d['fixed_zero_terms']:
                left=source_pattern(p,a,d,name,{});right=source_pattern(p,a,d,name,{},n,r);equal[v]=p.lin('Eq',[[left[1],1],[right[1],-1]],wanted);continue
            variables=sorted({a['var_index'][vn] for vn in d['active_terms'][name]['inputs']})
            def leaf(q,assigned):
                other={}
                for i,(value,ref) in assigned.items():other[i+n]=(value,q.lin('Eq',[[ref,1],[core[i],-1]],expression(-value,{i+n:1})))
                value,left=source_pattern(q,a,d,name,assigned);value2,right=source_pattern(q,a,d,name,other,n,r);assert value==value2;return {'Witness':q.lin('Eq',[[left,1],[right,-1]],wanted)}
            equal[v]=cases(p,'Eq',wanted,variables,leaf)
    assert len(equal)==n
    return {'steps':p.steps,'checks':[equal[i] for i in range(n)]}


def eliminate(es,v):
    positive=[mul(e,1/e[1][v]) for e in es if e[1].get(v,0)>0];negative=[mul(e,-1/e[1][v]) for e in es if e[1].get(v,0)<0];zero=[e for e in es if not e[1].get(v)]
    return dedup(zero+[plus(p,n) for p in positive for n in negative]),len(positive)*len(negative)


def lp_reverse(a,b,h,local):
    model=copy.deepcopy(b);mapping=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']];blocks=[];maxwidth=0;fmwork=0;wave_sizes=[]
    for root,d in h['blocks'].items():
        names=list(d['active_terms']);variables=[a['var_index'][vn] for vn in names];fixed={a['var_index'][vn] for vn in d['fixed_zero_terms']};rnames=d['original_or_rows']+[rn for td in d['active_terms'].values() for rn in td['rows']];es=[row_fact(a['rows'][a['row_index'][rn]],next(iter(row_ref(a,rn)))) for rn in rnames];es=[expression(e[0],{i:c for i,c in e[1].items() if i not in fixed}) for e in es]
        for v in variables:es += [expression(0,{v:-1}),expression(-1,{v:1})]
        es=dedup(es);stages=[None]*len(variables)
        for j in reversed(range(len(variables))):
            stages[j]=es;maxwidth=max(maxwidth,len(es));es,work=eliminate(es,variables[j]);fmwork+=work
        maxwidth=max(maxwidth,len(es));blocks.append({'root':root,'names':names,'variables':variables,'stages':stages,'core':es,'known':{}})
    # Allocate in synchronized extension-wave order, exactly as the kernel does.
    nextvar=len(b['vars'])
    for wave in range(8):
        size=0
        for d in blocks:
            if wave<len(d['variables']):mapping[d['variables'][wave]]=expression(0,{nextvar:1});nextvar+=1;size+=1
        wave_sizes.append(size)
    dual=Dual();p=SparseBuilder(model);top=p;tails=[];premises=0;maxlower=maxupper=0
    def remember(d,e,ref):
        norm,scale=normalize(e);k=key(norm);old=d['known'].get(k)
        if old is None or norm[0]>old[0]:d['known'][k]=(norm[0],ref,scale)
    def known(d,e):
        norm,scale=normalize(e);k=key(norm);old=d['known'].get(k)
        if old is None or old[0]<norm[0]:raise AssertionError(('FM reverse premise absent',d['root'],e,old))
        c,ref,oldscale=old
        if c==norm[0] and scale==oldscale:return ref
        return p.lin('Le',[[ref,scale/oldscale]],e,constant=scale*(norm[0]-c))
    # These are consequences of the actual committed hull and retained boxes.
    for d in blocks:
        coords=sorted({b['var_index'][vn] for vn in h['blocks'][d['root']]['original_inputs']+[d['root']]});refs=local[d['root']]+[{'VarLower':i} for i in coords]+[{'VarUpper':i} for i in coords]
        for original in d['core']:
            e=substitute(original,mapping);ref=dual.prove(p,e,refs);remember(d,e,ref)
    for wave,size in enumerate(wave_sizes):
        if not size:continue
        intervals=[];payload=[]
        for d in blocks:
            if wave>=len(d['variables']):continue
            originalvar=d['variables'][wave];v=next(iter(mapping[originalvar][1]));lower=[];upper=[]
            for original in d['stages'][wave]:
                c=original[1].get(originalvar,0)
                if not c:continue
                rest=expression(original[0],{i:q for i,q in original[1].items() if i!=originalvar});e=substitute(mul(rest,-1/c),mapping);(lower if c<0 else upper).append(e)
            maxlower=max(maxlower,len(lower));maxupper=max(maxupper,len(upper));checks=[known(d,plus(lo,up,-1)) for lo in lower for up in upper];premises+=len(checks);intervals.append({'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':checks});payload.append((d,v,lower,upper))
        tail={'steps':p.steps,'end':None};tails.append((tail,intervals));newmodel=copy.deepcopy(model);generated=add_interval_model(newmodel,[(lo,up) for _,_,lo,up in payload]);newp=SparseBuilder(newmodel,p.counter,facts=p.facts);model=newmodel
        for (d,v,lo,up),(generatedvar,refs) in zip(payload,generated):
            assert v==generatedvar
            for ref in refs:remember(d,newp.refexpr(ref),ref)
        p=newp
    checks=[];aux_block={a['var_index'][vn]:d for d in blocks for vn in d['names']};rowblock={rn:d for d in blocks for rn in h['blocks'][d['root']]['original_or_rows']+[rn for td in h['blocks'][d['root']]['active_terms'].values() for rn in td['rows']]}
    for i,var in enumerate(a['vars']):
        e=mapping[i]
        if var['name'] in b['var_index']:
            v=b['var_index'][var['name']];checks.extend([{'VarLower':v},{'VarUpper':v}])
        elif i in aux_block:checks.extend([known(aux_block[i],mul(e,-1)),known(aux_block[i],plus(e,expression(-1)))])
        else:checks+=['Exact']*2
    for row in a['rows']:
        if row['sense']=='E':checks.append('Exact')
        else:checks.append(known(rowblock[row['name']],substitute(row_fact(row,next(iter(row_ref(a,row['name'])))),mapping)))
    checks.append('Exact');projection=[[b['var_index'][v['name']],i] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']];checks+=['Exact']*len(projection);body={'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}
    for tail,intervals in reversed(tails):tail['end']={'IntervalLift':{'intervals':intervals,'body':body}};body=tail
    claim={'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':projection,'inverse':None}
    return claim,body,{'fourier_motzkin_max_rows_per_block':maxwidth,'fourier_motzkin_pair_operations':fmwork,'interval_pair_premises':premises,'interval_max_lower_width':maxlower,'interval_max_upper_width':maxupper,'extension_wave_sizes':wave_sizes,'dual_proposal_solves':dual.calls}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test61-nomf-B1');out=Path('cases/test61').resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';a=parse_mps(source);b=parse_mps(target);h=json.loads(audit.read_text());local=target_local_refs(b,h)
    cf,bf,fmap=forward(a,b,h);cr,br=integer_reverse(a,b,h,local);cl,bl,counts=lp_reverse(a,b,h,local);pair={'forward_claim':0,'reverse_claim':1};cert={'claims':[cf,cr,cl],'blocks':[bf,br,bl],'bijections':[{'claim':pair,'injectivity':injectivity(a,b,h,fmap)}]};requestobj={'claims':cert['claims'],'bijections':[pair],'points':[]};rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(requestobj,separators=(',',':'))+'\n');k=args.kernel.resolve();d={'case_id':'test61','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Unique Boolean reconstruction of all 3200 private auxiliaries, equal objective, complete integer projection bijection on the unchanged common retained model including cyclic/self-dependent variables; full projected target-to-source LP containment. No global LP strictness.','counts':{'source_variables':3600,'target_variables':400,'source_rows':5614,'target_rows':2070,'private_auxiliaries':3200,'active_private_auxiliaries':1614,'claims':3,'bijections':1,**counts},'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def execute(cmd):
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);entry={'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(entry)
        if p.returncode:(out/'attempts').mkdir(exist_ok=True);(out/'attempts/failure.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(entry)
        return entry
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:execute(cmd)
    def mathematical_result(run):
        return {key:value for key,value in json.loads(run['stdout']).items() if not key.endswith('_us')}
    baseline=mathematical_result(d['kernel_runs'][-1])
    for _ in range(2):assert mathematical_result(execute(['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]))==baseline
    deterministic=out/'determinism.rpx';execute(['assemble',str(rpa),str(deterministic)]);assert sha(deterministic)==sha(out/'proof.rpx');deterministic.unlink()
    for name,reason in [('missing_interval_premise','Drops an old-scope lower/upper consistency premise.'),('wrong_binary_split','Uses a private real interval coordinate as a binary split witness.'),('missing_injectivity_coordinate','Omits a private original-coordinate uniqueness equality.'),('missing_lp_capacity','Omits an original continuous conjunction obligation.')]:
        if name=='missing_interval_premise':obj=cert['blocks'][1]['end']['IntervalLift']['intervals'][0]['checks'];old=obj.pop();undo=lambda:obj.append(old)
        elif name=='wrong_binary_split':obj=next(s['Cases'] for s in cert['blocks'][1]['end']['IntervalLift']['body']['steps'] if 'Cases' in s);old=obj['integer'];obj['integer']={'VarInt':400};undo=lambda:obj.update(integer=old)
        elif name=='missing_injectivity_coordinate':obj=cert['bijections'][0]['injectivity']['checks'];old=obj.pop();undo=lambda:obj.append(old)
        else:
            block=cert['blocks'][2]
            while 'IntervalLift' in block['end']:block=block['end']['IntervalLift']['body']
            obj=block['end']['Return']['checks'];index=7200+next(i for i,r in enumerate(a['rows']) if r['sense']!='E');old=obj[index];obj[index]='Exact';undo=lambda:obj.__setitem__(index,old)
        path=out/(name+'.rpa');encoded=out/(name+'.rpx');path.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout;ass={'command':[str(k),'assemble',str(path),str(encoded)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode==2 and result['status']=='INVALID',(name,result);d['negative_checks'].append({'mutation':name,'rule_broken':reason,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'assemble':ass,'verify':{'command':[str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr},'exit_code':p.returncode,'result':result,'storage':'Temporary files deleted; deterministic mutation recipe retained in preparer.'});path.unlink();encoded.unlink()
    execute(['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]);d['status']='VERIFIED';d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};d['preparation_seconds']=time.perf_counter()-start;(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({key:d[key] for key in ['case_id','status','counts','rpa_bytes','preparation_seconds']},indent=2))

if __name__=='__main__':main()
