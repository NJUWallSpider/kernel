#!/usr/bin/env python3
"""Full actual count-aggregation reconstruction via existing Interval/Menu rules."""
from collections import ChainMap,defaultdict
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,gc,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test21 import combine,substitute
from prepare_test48 import Proof as BaseProof,emit_checks
from prepare_test23 import extend


def total(es):return combine(((e,F(1)) for e in es))
def var(i):return expression(0,{i:1})
def terms(*items):return [[ref,F(coef)] for ref,coef in items if ref is not None]


class Proof(BaseProof):
    def lin(self,kind,refs,expected=None,constant=0):
        assert (kind=='Eq' and constant==0) or (kind=='Le' and constant<=0) or (kind=='Int' and F(constant).denominator==1)
        for ref,c in refs:
            k=self.kind(ref);assert k=='Eq' or (kind=='Le' and k=='Le' and c>=0) or (kind=='Int' and k=='Int' and F(c).denominator==1)
        e=combine(((self.refexpr(r),c) for r,c in refs),constant)
        if expected is not None:assert e==expected,('linear identity mismatch',kind,e,expected)
        i=self.alloc();self.steps.append({'Lin':{'id':i,'kind':kind,'constant':str(constant),'terms':[[r,str(c)] for r,c in refs]}});self.facts[i]=(kind,e);return {'Local':i}
    def cases(self,kind,wanted,bit,left,right):
        i=self.alloc();children=[]
        for side,callback in enumerate((left,right)):
            guard=bit['expr'] if side==0 else plus(expression(1),bit['expr'],-1)
            child=Proof(self.model,self.counter,self.facts,self.assumptions+[guard],self.lookup)
            end=callback(child,{'Assumption':len(self.assumptions)})
            if 'Witness' in end:
                ref=end['Witness'];assert child.refexpr(ref)==wanted and child.kind(ref) in (kind,'Eq')
            else:assert not child.refexpr(end['Absurd'])[1] and child.refexpr(end['Absurd'])[0]>0
            children.append({'steps':child.steps,'end':end})
        self.steps.append({'Cases':{'id':i,'kind':kind,'expression':expr_json(wanted),'split':expr_json(bit['expr']),'integer':bit['integer'],'left':children[0],'right':children[1]}})
        self.facts[i]=(kind,wanted);return {'Local':i}


def rounded(p,le,integer):
    e,ie=p.refexpr(le),p.refexpr(integer);assert e[1]==ie[1]
    d=e[0]-ie[0];ceil=-(-d.numerator//d.denominator);wanted=plus(ie,expression(ceil))
    i=p.alloc();p.steps.append({'Round':{'id':i,'le':le,'integer':integer}});p.facts[i]=('Le',wanted);return {'Local':i}


def inspect(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(3472,4633,2720,3881)
    assert a['objective'][0]==b['objective'][0]==0
    sources=set(a['objective'][1]);assert len(sources)==2048 and set(a['objective'][1].values())=={F(-1)}
    auxiliaries=set(range(len(a['vars'])))-sources;assert len(auxiliaries)==1424
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in a['vars'])
    outgoing=defaultdict(list);capacity={};packing=[]
    for ri,row in enumerate(a['rows']):
        assert row['sense']=='L';ts=row['terms']
        if len(ts)==2 and row['rhs']==0:
            s=next(i for i,c in ts.items() if c==1);z=next(i for i,c in ts.items() if c==-1)
            assert s in sources and z in auxiliaries;outgoing[s].append((z,ri))
        elif row['rhs']==9:
            assert len(ts)==128 and set(ts)<=sources and set(ts.values())=={F(1)};capacity[row['name']]=sorted(ts)
        else:
            assert row['rhs']==1 and len(ts)==16 and set(ts)<=auxiliaries and set(ts.values())=={F(1)};packing.append(ri)
    assert set(outgoing)==sources and sum(map(len,outgoing.values()))==4528
    assert len(capacity)==16 and len(packing)==89
    assert sorted(i for ids in capacity.values() for i in ids)==sorted(sources)
    assert sorted(i for r in packing for i in a['rows'][r]['terms'])==sorted(auxiliaries)
    leaves={i for i,refs in outgoing.items() if len(refs)==1}
    assert len(leaves)==768 and {a['vars'][i]['name'] for i in leaves}==set(h['removed_variables'])
    pools={x['capacity_row']:x for x in h['pools']};assert set(pools)==set(capacity)
    for name,ids in capacity.items():
        assert {a['var_index'][n] for n in pools[name]['members']}==set(ids)&leaves
        assert len(pools[name]['members'])==48
    assert set(b['var_index'])=={a['vars'][i]['name'] for i in set(range(len(a['vars'])))-leaves}|{x['variable'] for x in pools.values()}
    for i in set(range(len(a['vars'])))-leaves:
        v=b['vars'][b['var_index'][a['vars'][i]['name']]]
        assert v['lower']==0 and v['upper']==1 and v['integer']==(i in auxiliaries)
    for pool in pools.values():
        v=b['vars'][b['var_index'][pool['variable']]];assert v['lower']==0 and v['upper']==48 and not v['integer']
    return {'sources':sources,'aux':auxiliaries,'outgoing':outgoing,'capacities':capacity,'packing':packing,'leaves':leaves,'pools':pools}


def forward(a,b,h,claim):
    p=Proof(a);mapping=[];domains={};rows={};pool_by_name={v['variable']:(name,v) for name,v in h['pools'].items()}
    for j,v in enumerate(b['vars']):
        if v['name'] in a['var_index']:mapping.append(var(a['var_index'][v['name']]));continue
        name,pool=pool_by_name[v['name']];ids=[a['var_index'][n] for n in pool['members']];mapping.append(total(var(i) for i in ids))
        domains[(j,'VarLower')]=p.lin('Le',[[{'VarLower':i},F(1)] for i in ids],mul(mapping[-1],-1))
        domains[(j,'VarUpper')]=p.lin('Le',[[{'VarUpper':i},F(1)] for i in ids],plus(mapping[-1],expression(-48)))
        ri=b['row_index'][pool['row']]
        rows[ri]=p.lin('Le',[[{'RowUpper':h['outgoing'][i][0][1]},F(1)] for i in ids])
    for i,row in enumerate(b['rows']):
        if i in rows:continue
        ref=row_ref(a,row['name']);assert p.refexpr(ref)==substitute(row_fact(row,'RowUpper'),mapping);rows[i]=ref
    return emit_checks(p,b,mapping,claim,rows=rows,domains=domains)


def availability(a,b,h):
    pre=Proof(b);intervals=[];original=[];factors={}
    for i in sorted(h['sources']):
        bits=[]
        for z,ri in h['outgoing'][i]:
            ti=b['var_index'][a['vars'][z]['name']]
            bits.append({'expr':var(ti),'lower':{'VarLower':ti},'upper':{'VarUpper':ti},'integer':{'VarInt':ti},'row':a['rows'][ri]['name']})
        factors[i]=bits
        if len(bits)==1:continue
        low=plus(total(x['expr'] for x in bits),expression(1-len(bits)));checks=[]
        for lower in [expression(),low]:
            for k,bit in enumerate(bits):
                checks.append(bit['lower'] if not lower[1] else pre.lin('Le',[[x['upper'],F(1)] for j,x in enumerate(bits) if j!=k],plus(low,bit['expr'],-1)))
        intervals.append({'lower':[expr_json(expression()),expr_json(low)],'upper':[expr_json(x['expr']) for x in bits],'checks':checks});original.append(i)
    m,layouts=extend(b,intervals);p=Proof(m,pre.counter,pre.facts,lookup=pre.lookup);available={};old_bound={}
    for i,bits in factors.items():
        if len(bits)==1:available[i]=bits[0];continue
    for i,l in zip(original,layouts):
        bits=factors[i];z=var(l['variable']);old=var(b['var_index'][a['vars'][i]['name']]);lo={'RowLower':l['lower'][0]}
        def derive(kind,wanted):
            def walk(cur,k,fixed):
                if k==len(bits):
                    one=cur.lin('Le',[[{'RowLower':l['lower'][1]},F(1)]]+[[r,F(-1)] for r in fixed],plus(expression(1),z,-1))
                    if kind=='Le':ref=cur.lin('Le',[[one,F(1)],[{'VarUpper':next(iter(old[1]))},F(1)]],wanted)
                    else:
                        upper=cur.lin('Le',[[{'RowUpper':l['upper'][0]},F(1)],[fixed[0],F(1)]],plus(z,expression(-1)))
                        eq=cur.eqpair(upper,one);ref=cur.lin('Int',[[eq,F(1)]],z,constant=1)
                    return {'Witness':ref}
                bit=bits[k]
                def zero(child,guard):
                    eq=child.eqpair(guard,bit['lower'])
                    if kind=='Le':ref=child.lin('Le',[[row_ref(b,bit['row']),F(1)],[eq,F(1)],[lo,F(1)]],wanted)
                    else:
                        upper=child.lin('Le',[[{'RowUpper':l['upper'][k]},F(1)],[eq,F(1)]],z)
                        eqz=child.eqpair(upper,lo);ref=child.lin('Int',[[eqz,F(1)]],z)
                    return {'Witness':ref}
                def one(child,guard):return walk(child,k+1,fixed+[child.eqpair(bit['upper'],guard)])
                return {'Witness':cur.cases(kind,wanted,bit,zero,one)}
            return walk(p,0,[])['Witness']
        integer=derive('Int',z);old_bound[i]=derive('Le',plus(old,z,-1))
        hi=p.lin('Le',[[{'RowUpper':l['upper'][0]},F(1)],[bits[0]['upper'],F(1)]],plus(z,expression(-1)))
        available[i]={'expr':z,'lower':lo,'upper':hi,'integer':integer,'links':{bit['row']:{'RowUpper':l['upper'][k]} for k,bit in enumerate(bits)}}
    return pre,p,intervals,available,old_bound


def menus_for_prefixes(p,h,available):
    menus=[];prefix={};m=copy.deepcopy(p.model)
    for group,ids in h['capacities'].items():
        previous={'expr':expression(),'lower':None,'upper':None,'integer':None,'count':expression(),'count_int':None,'k':0,'menu':None}
        prefix[group]=[previous]
        for k,i in enumerate(ids,1):
            bit=available[i];s=plus(previous['expr'],bit['expr'])
            lo=p.lin('Le',terms((previous['lower'],1),(bit['lower'],1)),mul(s,-1))
            hi=p.lin('Le',terms((previous['upper'],1),(bit['upper'],1)),plus(s,expression(-k)))
            integer=p.lin('Int',terms((previous['integer'],1),(bit['integer'],1)),s)
            cur={'expr':s,'lower':lo,'upper':hi,'integer':integer,'k':k,'menu':None,'count':s,'count_int':integer}
            if k>9:
                menus.append({'maximum_index':k,'activation':expr_json(expression(1)),'index':expr_json(s),'checks':['Exact','Exact','Exact',lo,hi,integer]})
                start=len(m['vars'])
                for j in range(k+1):m['vars'].append({'name':f'choice_{start+j}','integer':True,'lower':F(0),'upper':F(1)})
                count=expression(0,{start+j:min(j,9) for j in range(k+1)})
                eqs=[]
                for e in [expression(-1,{start+j:1 for j in range(k+1)}),plus(expression(0,{start+j:j for j in range(k+1)}),s,-1)]:
                    ri=len(m['rows']);name=f'menu_row_{ri}';m['row_index'][name]=ri
                    m['rows'].append({'name':name,'sense':'E','rhs':-e[0],'terms':e[1]});eqs.append({'RowEq':ri})
                cur['count']=count;cur['menu']={'start':start,'sum':eqs[0],'moment':eqs[1]}
            prefix[group].append(cur);previous=cur
    q=Proof(m,p.counter,p.facts,lookup=p.lookup)
    for seq in prefix.values():
        for d in seq[10:]:d['count_int']=q.lin('Int',[[{'VarInt':i},c] for i,c in d['count'][1].items()],d['count'])
    return q,menus,prefix


def menu_upper(p,d):
    if d['menu'] is None:
        if d['k']==0:return p.lin('Le',[],expression(-9),constant=-9)
        return p.lin('Le',[[d['upper'],F(1)]],plus(d['count'],expression(-9)),constant=d['k']-9)
    m=d['menu'];start=m['start']
    return p.lin('Le',[[m['sum'],F(9)]]+[[{'VarLower':start+j},F(9-j)] for j in range(9)],plus(d['count'],expression(-9)))


def min_low(p,d,guard,bound):
    """Given S<=bound<=9, prove C-S=0, or None for an exact identity."""
    assert bound<=9
    if d['menu'] is None:return None
    m=d['menu'];k=d['k'];start=m['start'];tail=expression(0,{start+j:1 for j in range(10,k+1)})
    refs=[[m['moment'],F(1,10)],[guard,F(1,10)]]
    refs += [[{'VarLower':start+j},F(j,10)-(1 if j>=10 else 0)] for j in range(k+1) if F(j,10)!=(1 if j>=10 else 0)]
    upper=p.lin('Le',refs,plus(tail,expression(-F(bound,10))))
    integer=p.lin('Int',[[{'VarInt':i},c] for i,c in tail[1].items()],tail);zero=rounded(p,upper,integer);assert p.refexpr(zero)==tail
    wanted=plus(d['count'],d['expr'],-1)
    first=p.lin('Le',[[m['moment'],F(1)]]+[[{'VarLower':start+j},F(j-9)] for j in range(10,k+1)],wanted)
    second=p.lin('Le',[[m['moment'],F(-1)],[zero,F(k-9)]]+[[{'VarLower':start+j},F(k-j)] for j in range(10,k)],mul(wanted,-1))
    return p.eqpair(first,second)


def min_high(p,d,guard,bound=9):
    """Given 9<=bound<=S, prove C-9=0."""
    assert 9<=bound<=d['k']
    if d['menu'] is None:
        assert d['k']==bound==9
        return p.eqpair(d['upper'],guard)
    m=d['menu'];k=d['k'];start=m['start'];low=expression(0,{start+j:1 for j in range(9)})
    refs=[[m['sum'],F(k,k-8)],[m['moment'],F(-1,k-8)],[guard,F(1,k-8)]]
    refs += [[{'VarLower':start+j},F(8-j if j<=8 else k-j,k-8)] for j in range(k+1) if (8-j if j<=8 else k-j)]
    upper=p.lin('Le',refs,plus(low,expression(F(bound-k,k-8))))
    integer=p.lin('Int',[[{'VarInt':i},c] for i,c in low[1].items()],low);zero=rounded(p,upper,integer);assert p.refexpr(zero)==low
    first=menu_upper(p,d)
    second=p.lin('Le',[[m['sum'],F(-9)],[zero,F(9)]]+[[{'VarLower':start+j},F(j)] for j in range(1,9)],plus(expression(9),d['count'],-1))
    return p.eqpair(first,second)


def reverse(a,b,h,claim):
    pre,old,intervals,available,old_bound=availability(a,b,h)
    p,menus,prefix=menus_for_prefixes(old,h,available)
    mapping=[None]*len(a['vars']);domains={};rows={};group_cost=[];count_steps=0
    for i in h['aux']:mapping[i]=var(b['var_index'][a['vars'][i]['name']])
    for group,ids in h['capacities'].items():
        seq=prefix[group];chosen=[]
        for k,i in enumerate(ids,1):
            cur,previous=seq[k],seq[k-1];bit=available[i];w=plus(cur['count'],previous['count'],-1);mapping[i]=w;chosen.append(w)
            if k<=9:low=bit['lower'];link=None;integer=bit['integer']
            else:
                split=plus(previous['expr'],expression(-8));split_int=p.lin('Int',[[previous['integer'],F(1)]],split,constant=-8)
                descriptor={'expr':split,'integer':split_int}
                def prove_delta(lower):
                    wanted=mul(w,-1) if lower else plus(w,bit['expr'],-1)
                    def left(child,guard):
                        up=child.lin('Le',[[guard,F(1)],[bit['upper'],F(1)]],plus(cur['expr'],expression(-9)))
                        ei=min_low(child,cur,up,9);ep=min_low(child,previous,guard,8)
                        refs=terms((ei,-1 if lower else 1),(ep,1 if lower else -1))
                        if lower:refs.append([bit['lower'],F(1)])
                        return {'Witness':child.lin('Le',refs,wanted)}
                    def right(child,guard):
                        down=child.lin('Le',[[guard,F(1)],[bit['lower'],F(1)]],plus(expression(9),cur['expr'],-1))
                        ei=min_high(child,cur,down);ep=min_high(child,previous,guard)
                        refs=terms((ei,-1 if lower else 1),(ep,1 if lower else -1))
                        if not lower:refs.append([bit['lower'],F(1)])
                        return {'Witness':child.lin('Le',refs,wanted)}
                    return p.cases('Le',wanted,descriptor,left,right)
                low=prove_delta(True);link=prove_delta(False)
                integer=p.lin('Int',[[cur['count_int'],F(1)],[previous['count_int'],F(-1)]],w)
            domains[(i,'VarLower')]=low;domains[(i,'VarInt')]=integer
            domains[(i,'VarUpper')]=bit['upper'] if link is None else p.lin('Le',[[link,F(1)],[bit['upper'],F(1)]],plus(w,expression(-1)))
            for aux,ri in h['outgoing'][i]:
                if i in h['leaves']:
                    if link is None:rows[ri]='Exact'
                    else:rows[ri]=link
                else:
                    ref=bit['links'][a['rows'][ri]['name']]
                    rows[ri]=ref if link is None else p.lin('Le',[[link,F(1)],[ref,F(1)]],plus(w,var(b['var_index'][a['vars'][aux]['name']]),-1))
        ri=a['row_index'][group];rows[ri]=menu_upper(p,seq[-1]);assert p.refexpr(rows[ri])==plus(total(chosen),expression(-9))
        pool=h['pools'][group];old_total=total([var(b['var_index'][a['vars'][i]['name']]) for i in ids if i not in h['leaves']]+[var(b['var_index'][pool['variable']])])
        available_upper=p.lin('Le',[[row_ref(b,pool['row']),F(1)]]+[[old_bound[i],F(1)] for i in ids if i not in h['leaves']],plus(old_total,seq[-1]['expr'],-1))
        end=seq[-1];split=plus(end['expr'],expression(-9));sint=p.lin('Int',[[end['integer'],F(1)]],split,constant=-9)
        wanted=plus(old_total,end['count'],-1)
        def left(child,guard):
            eq=min_low(child,end,guard,9);return {'Witness':child.lin('Le',[[available_upper,F(1)],[eq,F(-1)]],wanted)}
        def right(child,guard):
            eq=min_high(child,end,guard,10);return {'Witness':child.lin('Le',[[row_ref(b,group),F(1)],[eq,F(-1)]],wanted)}
        group_cost.append(p.cases('Le',wanted,{'expr':split,'integer':sint},left,right))
        print(json.dumps({'capacity':group,'proof_ids':p.counter[0]}),flush=True)
    for ri in h['packing']:rows[ri]=row_ref(b,a['rows'][ri]['name'])
    objective=p.lin('Le',[[r,F(1)] for r in group_cost],plus(substitute(a['objective'],mapping),b['objective'],-1))
    # Generic emitter accepts explicit Exact for tautological leaf implications.
    for ri,ref in list(rows.items()):
        if ref=='Exact':del rows[ri]
    body=emit_checks(p,a,mapping,claim,rows=rows,domains=domains,objective=objective)
    info={'availability_intervals':len(intervals),'prefix_menus':len(menus),'generated_menu_variables':sum(m['maximum_index']+1 for m in menus),'allocated_ids':p.counter[0],'reverse_obligations':len(body['end']['Return']['checks'])}
    return {'steps':pre.steps,'end':{'IntervalLift':{'intervals':intervals,'body':{'steps':old.steps,'end':{'MenuLift':{'menus':menus,'body':body}}}}}},info


def prepare(source,target,audit):
    a,b=parse_mps(source),parse_mps(target);h=inspect(a,b,json.loads(audit.read_text()))
    projection=[[i,b['var_index'][a['vars'][i]['name']]] for i in sorted(h['aux'])]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':None},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[[j,i] for i,j in projection],'inverse':None}]
    f=forward(a,b,h,claims[0]);r,info=reverse(a,b,h,claims[1])
    info['forward_obligations']=len(f['end']['Return']['checks'])
    return a,b,h,{'claims':claims,'blocks':[f,r]},info


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test78-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test78'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source,target,audit=run/'input/model.mps',run/'output/reformulated.mps',run/'output/audit.json'
    a,b,h,cert,info=prepare(source,target,audit);gc.collect()
    rpa,request=out/'proof.rpa',out/'request.json';rpa.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    receipt={'case_id':'test78','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},
             'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'preparer_dependencies':{name:sha(Path(__file__).with_name(name)) for name in ['prepare_affine.py','prepare_test40.py','prepare_test21.py','prepare_test48.py','prepare_test23.py','prepare_test88.py']},
             'claims':'Complete mixed-integer maps: source-to-target objective equality; target-to-source objective nonincrease; preserve all 1424 auxiliary decisions in both directions. No LP equivalence, bijection or numerical optimum claimed.',
             'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':2,'auxiliary_projection':len(h['aux']),**info},
             'preparation_seconds':time.perf_counter()-started,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    def save(): (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    if args.kernel:
        kernel=args.kernel.resolve();receipt['kernel_binary_sha256']=sha(kernel)
        def invoke(command):
            result=subprocess.run([str(kernel),*map(str,command)],capture_output=True,text=True)
            return {'command':[str(kernel),*map(str,command)],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        for command in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]:
            result=invoke(command);receipt['kernel_runs'].append(result);save();print(json.dumps(result),flush=True)
            if result['exit_code']:
                receipt['status']=json.loads(result['stdout']).get('status','FAILED');break
        else:
            receipt['status']='VERIFIED';receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};receipt['negative_checks']=[];save()
            f=cert['blocks'][0]['end']['Return'];lift=cert['blocks'][1]['end']['IntervalLift'];menu=lift['body']['end']['MenuLift'];body=menu['body'];r=body['end']['Return']
            tests=[]
            def mutation(name,why,container,key,value):tests.append((name,why,container,key,value))
            poolindex=b['var_index'][next(iter(h['pools'].values()))['variable']]
            omitted=copy.deepcopy(f['map'][poolindex]);omitted['terms'].pop()
            mutation('lost_pool_member','Omit an actual original contributor from the forward count.',f['map'],poolindex,omitted)
            first_choice=next(i for i in sorted(h['sources']) if a['vars'][i]['name'] in b['var_index'])
            mutation('continuous_as_integer','Use the relaxed continuous choice as the old-scope integer witness for a menu index.',menu['menus'][0]['checks'],5,{'VarInt':b['var_index'][a['vars'][first_choice]['name']]})
            mutation('missing_interval_pair','Omit a middle lower/upper compatibility premise.',lift['intervals'][0],'checks',lift['intervals'][0]['checks'][:-1])
            mutation('wrong_prefix_menu','Change the prefix menu capacity without changing its checked witness.',menu['menus'][0],'maximum_index',9)
            wrong=expr_json(expression());mutation('lost_choice_reconstruction','Set one reconstructed original choice to zero while retaining its mandatory full output checks.',r['map'],sorted(h['sources'])[10],wrong)
            mutation('caller_objective_mismatch','Weaken the certificate objective while preserving the caller request.',cert['claims'][0],'objective','None')
            for name,why,container,key,value in tests:
                previous=container[key];container[key]=value
                path=out/(name+'.rpa');binary=out/(name+'.rpx');path.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');container[key]=previous
                assembled=invoke(['assemble',path,binary]);assert assembled['exit_code']==0,assembled
                rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',binary,request]);result=json.loads(rejected['stdout'])
                assert rejected['exit_code']==2 and result['status']=='INVALID',(name,rejected)
                receipt['negative_checks'].append({'mutation':name,'rule_broken':why,'exit_code':rejected['exit_code'],'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(binary)});save();print(json.dumps({'attack':name,'result':result}),flush=True)
    save();print(json.dumps({k:receipt[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))
    if args.kernel and receipt['status']!='VERIFIED':raise SystemExit(1)


if __name__=='__main__':main()
