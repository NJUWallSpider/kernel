#!/usr/bin/env python3
"""Complete MI directions for test46, composed with preserved LP reverse proof."""
from collections import ChainMap
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,gc,json,subprocess,time
from prepare_test46 import Proof,inspect,finish,target_setup,expression,plus,mul,expr_json,row_fact,parse_mps,row_ref,sha,sumexpr,substitute,extend


def round_ref(p,le,integer):
    e,z=p.refexpr(le),p.refexpr(integer);assert e[1]==z[1] and p.kind(le)=='Le' and p.kind(integer)=='Int'
    d=e[0]-z[0];c=-((-d.numerator)//d.denominator);i=p.alloc();p.steps.append({'Round':{'id':i,'le':le,'integer':integer}});p.facts[i]=('Le',expression(z[0]+c,z[1]));return {'Local':i}


def negative_tree(p,ids):
    """Each node proves minus its complete nonnegative variable sum."""
    assert ids
    if len(ids)==1:return {'ids':ids,'lower':{'VarLower':ids[0]}}
    mid=len(ids)//2;left=negative_tree(p,ids[:mid]);right=negative_tree(p,ids[mid:]);lower=p.lin('Le',[[left['lower'],F(1)],[right['lower'],F(1)]])
    return {'ids':ids,'lower':lower,'left':left,'right':right}


def zero_tree(p,node,upper,out):
    if len(node['ids'])==1:
        i=node['ids'][0];out[i]=p.eqpair(upper,node['lower']);return
    for key,sibling in [('left','right'),('right','left')]:
        child=node[key];u=p.lin('Le',[[upper,F(1)],[node[sibling]['lower'],F(1)]],expression(0,{i:F(1) for i in child['ids']}));zero_tree(p,child,u,out)


def sequence_unique(p,first,second,norm_first,norm_second,moment_difference,j):
    """EQ first[j]-second[j], two nonnegative integer one-hot sequences 0..48."""
    K=len(first)-1;assert len(second)==K+1
    wanted=plus(first[j]['expr'],second[j]['expr'],-1)
    def fixed(child,element,value,assumption):return child.eqpair(assumption,element['lower']) if value==0 else child.eqpair(element['upper'],assumption)
    def mixed(cur,one_side,one_assumption,zero_assumption):
        one,zero=(first,second) if one_side==0 else (second,first);one_norm,zero_norm=(norm_first,norm_second) if one_side==0 else (norm_second,norm_first)
        one_fixed=fixed(cur,one[j],1,one_assumption);zero_fixed=fixed(cur,zero[j],0,zero_assumption)
        others=cur.lin('Le',[[one_norm,F(1)],[one_fixed,F(-1)]])
        negative=cur.lin('Le',[[e['lower'],F(1)] for k,e in enumerate(one) if k!=j]);others_eq=cur.eqpair(others,negative)
        moment=plus(sumexpr(mul(e['expr'],F(k)) for k,e in enumerate(one)),expression(-j))
        upper=cur.lin('Le',[[one_fixed,F(j)],[others_eq,F(K)]]+[[e['lower'],F(K-k)] for k,e in enumerate(one) if k!=j and K!=k],moment)
        lower=cur.lin('Le',[[one_fixed,F(-j)]]+[[e['lower'],F(k)] for k,e in enumerate(one) if k!=j and k],mul(moment,-1))
        one_moment=cur.eqpair(upper,lower)
        zero_moment=cur.lin('Eq',[[one_moment,F(1)],[moment_difference,F(-1 if one_side==0 else 1)]])
        prefix=sumexpr(e['expr'] for e in zero[:j]);integer=cur.lin('Int',[[e['integer'],F(1)] for e in zero[:j]],prefix)
        def low(child,assumption):
            terms=[[zero_moment,F(1)],[zero_norm,F(-j-1)],[assumption,F(j+1)],[zero_fixed,F(1)]]
            terms += [[e['lower'],F(k)] for k,e in enumerate(zero) if k<j and k]
            terms += [[e['lower'],F(k-j-1)] for k,e in enumerate(zero) if k>j+1]
            return {'Absurd':child.lin('Le',terms,expression(1))}
        def high(child,assumption):
            terms=[[zero_norm,F(K)],[zero_moment,F(-1)],[assumption,F(K-j+1)]]
            terms += [[e['lower'],F(j-1-k)] for k,e in enumerate(zero) if k<j-1]
            terms += [[e['lower'],F(K-k)] for k,e in enumerate(zero) if k>=j and k<K]
            return {'Absurd':child.lin('Le',terms,expression(1))}
        return {'Witness':cur.cases('Eq',wanted,prefix,integer,low,high)}
    def same(cur,a,b,value):
        x=fixed(cur,first[j],value,a);y=fixed(cur,second[j],value,b)
        return {'Witness':cur.lin('Eq',[[x,F(1)],[y,F(-1)]],wanted)}
    def left(cur,a):return {'Witness':cur.cases('Eq',wanted,second[j]['expr'],second[j]['integer'],lambda ch,b:same(ch,a,b,0),lambda ch,b:mixed(ch,1,b,a))}
    def right(cur,a):return {'Witness':cur.cases('Eq',wanted,second[j]['expr'],second[j]['integer'],lambda ch,b:mixed(ch,0,a,b),lambda ch,b:same(ch,a,b,1))}
    return p.cases('Eq',wanted,first[j]['expr'],first[j]['integer'],left,right)


def forward_mi(a,b,s):
    p=Proof(a);forbidden=sorted(s['forbidden']);cap=F(39424)
    terms=[[{'VarUpper':s['obj']},1/cap],[row_ref(a,'p_lin_0'),-1/cap]]
    terms += [[{'RowEq':t['cost_row']},1/cap] for t in s['tables']]
    terms += [[{'VarLower':i},t['costs'][i]/cap] for t in s['tables'] for i in t['allowed'].values()]
    le=p.lin('Le',terms,expression(-F(39423)/cap,{i:F(1) for i in forbidden}))
    integer=p.lin('Int',[[{'VarInt':i},F(1)] for i in forbidden],expression(0,{i:F(1) for i in forbidden}))
    upper=round_ref(p,le,integer);tree=negative_tree(p,forbidden);fixed={};zero_tree(p,tree,upper,fixed);del tree
    print('forward: all forbidden selectors proved zero',len(fixed),flush=True)
    rows={};unary_sequences={}
    for node,t in s['unary'].items():
        seq=[]
        for j in range(49):
            i=t['coords'][(j,)];seq.append({'expr':expression(0,{i:F(1)}),'lower':{'VarLower':i},'upper':{'VarUpper':i},'integer':{'VarInt':i}})
        unary_sequences[node]=seq
        rows[b['row_index'][t['name']]]=p.lin('Eq',[[{'RowEq':t['norm']},F(1)]]+[[fixed[i],F(-1)] for i in sorted(t['forbidden'])])
    for tn,t in enumerate(s['tables']):
        if len(t['nodes'])==1 or t['constant']:continue
        for side,node in enumerate(t['nodes']):
            seq=[]
            for j in range(49):
                ids=[i for ij,i in t['coords'].items() if ij[side]==j];e=expression(0,{i:F(1) for i in ids})
                seq.append({'expr':e,'lower':p.lin('Le',[[{'VarLower':i},F(1)] for i in ids],mul(e,-1)),'integer':p.lin('Int',[[{'VarInt':i},F(1)] for i in ids],e)})
            for j in range(49):seq[j]['upper']=p.lin('Le',[[{'RowEq':t['norm']},F(1)]]+[[seq[k]['lower'],F(1)] for k in range(49) if k!=j],plus(seq[j]['expr'],expression(-1)))
            unary=s['unary'][node]
            difference=p.lin('Eq',[[{'RowEq':t['moments'][side]},F(1)],[{'RowEq':unary['moments'][0]},F(-1)]])
            for ij,u in unary['allowed'].items():
                j=ij[0];eq=sequence_unique(p,seq,unary_sequences[node],{'RowEq':t['norm']},{'RowEq':unary['norm']},difference,j)
                removed=[i for i in seq[j]['expr'][1] if i in fixed]
                ref=p.lin('Eq',[[eq,F(1)]]+[[fixed[i],F(-1)] for i in removed]) if removed else eq
                ri=s['marginals'][(t['name'],side,j)];rows[ri]=ref
        print('forward: marginal factor',tn,t['name'],'steps',len(p.steps),flush=True)
    terms=[[row_ref(a,'p_lin_0'),F(1)]]
    for t in s['tables']:
        if t['constant']:
            eq=p.lin('Eq',[[{'RowEq':t['cost_row']},F(-1)],[{'RowEq':t['norm']},F(17)]]+[[fixed[i],t['costs'][i]-17] for i in sorted(t['forbidden'])],expression(-17,{t['cost_var']:F(1)}))
            terms.append([eq,F(1)])
        else:
            terms.append([{'RowEq':t['cost_row']},F(-1)]);terms.extend([[fixed[i],t['costs'][i]] for i in sorted(t['forbidden'])])
    rows[b['row_index']['p_lin_0']]=p.lin('Eq',terms)
    mapping=[expression(0,{a['var_index'][v['name']]:F(1)}) for v in b['vars']]
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[i,j] for i,j in sorted(s['oldnew'].items())],'inverse':None}
    block=finish(p,b,mapping,claim,{},rows)
    return claim,block,{'obligations':len(block['end']['Return']['checks']),'root_steps':len(p.steps),'fixed_selectors':len(fixed),'marginals':len(s['marginals'])}


def grouped_negative_tree(p,items):
    # Leaves carry arbitrary nonnegative sums; each internal node has a sparse
    # sum certificate, so a component bound costs only logarithmically many refs.
    assert items
    if len(items)==1:return {'key':items[0][0],'lower':items[0][1]}
    mid=len(items)//2;l=grouped_negative_tree(p,items[:mid]);r=grouped_negative_tree(p,items[mid:])
    return {'left':l,'right':r,'lower':p.lin('Le',[[l['lower'],F(1)],[r['lower'],F(1)]])}


def distribute_upper(p,tree,upper,out):
    if 'key' in tree:out[tree['key']]=upper;return
    for key,other in [('left','right'),('right','left')]:
        bound=p.lin('Le',[[upper,F(1)],[tree[other]['lower'],F(1)]])
        distribute_upper(p,tree[key],bound,out)


def and_integer(p,e,xa,xb,lower,upper_a,upper_b,and_lower):
    def inactive(c,g):
        fixed=c.eqpair(g,{'VarLower':xa});up=c.lin('Le',[[upper_a,F(1)],[fixed,F(1)]],e)
        eq=c.eqpair(up,lower)
        return {'Witness':c.lin('Int',[[eq,F(1)]],e)}
    def active(c,g):
        fixed=c.eqpair({'VarUpper':xa},g)
        opposite=c.lin('Le',[[and_lower,F(1)],[fixed,F(-1)]],plus(expression(0,{xb:F(1)}),e,-1))
        eq=c.eqpair(upper_b,opposite)
        return {'Witness':c.lin('Int',[[eq,F(1)],[{'VarInt':xb},F(1)]],e)}
    return p.cases('Int',e,expression(0,{xa:F(1)}),{'VarInt':xa},inactive,active)


def discard_new_except(p,initial,keep):
    ids=[i for i in list(p.facts.maps[0]) if i>=initial and i not in keep]
    if ids:p.steps.append({'Drop':{'ids':ids}})
    for i in ids:del p.facts.maps[0][i]


def reverse_mi(a,b,s):
    p=Proof(b);setup=target_setup(a,b,s,p);oldnew=s['oldnew'];pairints={};costints={}
    for ti,t in enumerate(s['tables']):
        if len(t['nodes'])==1 or t['constant']:continue
        initial=p.counter[0];ua={};ub={};an={};groups=[{},{}]
        for side in range(2):
            for ij,u in s['unary'][t['nodes'][side]]['allowed'].items():
                state=ij[0];ids=[oldnew[i] for pos,i in t['allowed'].items() if pos[side]==state];assert ids
                groups[side][state]=ids
                tree=grouped_negative_tree(p,[(i,{'VarLower':i}) for i in ids]);upper=p.lin('Le',[[{'RowEq':s['marginals'][(t['name'],side,state)]},F(1)]])
                distribute_upper(p,tree,upper,ua if side==0 else ub)
        for state,ids in groups[0].items():
            # Total off-row mass is 1-x_a. Split that sum by column; adding
            # each column equality yields the Fréchet lower bound for its cell.
            root=p.lin('Le',[[setup['norms'][t['name']],F(1)],[{'RowEq':s['marginals'][(t['name'],0,state)]},F(-1)]])
            excluded=set(ids);items=[]
            for other,colids in groups[1].items():
                off=[i for i in colids if i not in excluded]
                lo=p.lin('Le',[[{'VarLower':i},F(1)] for i in off])
                items.append((other,lo))
            tree=grouped_negative_tree(p,items);column_bounds={};distribute_upper(p,tree,root,column_bounds)
            for pos,old in t['allowed'].items():
                if pos[0]!=state:continue
                i=oldnew[old];an[i]=p.lin('Le',[[column_bounds[pos[1]],F(1)],[{'RowEq':s['marginals'][(t['name'],1,pos[1])]},F(-1)]])
        keep=set()
        for pos,old in t['allowed'].items():
            i=oldnew[old];xa=oldnew[s['unary'][t['nodes'][0]]['allowed'][(pos[0],)]];xb=oldnew[s['unary'][t['nodes'][1]]['allowed'][(pos[1],)]]
            r=and_integer(p,expression(0,{i:F(1)}),xa,xb,{'VarLower':i},ua[i],ub[i],an[i]);pairints[old]=r;keep.add(r['Local'])
        cr=p.lin('Int',[[pairints[i],t['costs'][i]] for i in t['allowed'].values()],setup['costs'][t['cost_var']]);costints[t['cost_var']]=cr;keep.add(cr['Local'])
        discard_new_except(p,initial,keep)
        print('reverse: continuous pair table integrality',ti,t['name'],len(pairints),'live',len(p.facts.maps[0]),flush=True)
    intervals=[];lifted=[]
    for t in s['tables']:
        if not t['constant']:continue
        for pos,old in t['allowed'].items():
            xa=oldnew[s['unary'][t['nodes'][0]]['allowed'][(pos[0],)]];xb=oldnew[s['unary'][t['nodes'][1]]['allowed'][(pos[1],)]]
            intervals.append({'lower':[expr_json(expression()),expr_json(expression(-1,{xa:F(1),xb:F(1)}))],'upper':[expr_json(expression(0,{xa:F(1)})),expr_json(expression(0,{xb:F(1)}))],'checks':[{'VarLower':xa},{'VarLower':xb},{'VarUpper':xb},{'VarUpper':xa}]})
            lifted.append((t,pos,old,xa,xb))
    ext,layout=extend(b,intervals);q=Proof(ext,p.counter,p.facts);mapping=[expression()]*len(a['vars']);domains={};rows={};lift_refs={};lift_index={}
    for old,new in oldnew.items():mapping[old]=expression(0,{new:F(1)})
    for old,r in pairints.items():domains[(old,'VarInt')]=r
    for node,e in setup['means'].items():mapping[node]=e;domains[(node,'VarLower')],domains[(node,'VarUpper')]=setup['meanbounds'][node]
    for (t,pos,old,xa,xb),l in zip(lifted,layout):
        z=expression(0,{l['variable']:F(1)});mapping[old]=z;lo={'RowLower':l['lower'][0]};ua={'RowUpper':l['upper'][0]};ub={'RowUpper':l['upper'][1]};al={'RowLower':l['lower'][1]}
        domains[(old,'VarLower')]=lo;domains[(old,'VarUpper')]=q.lin('Le',[[ua,F(1)],[{'VarUpper':xa},F(1)]],plus(z,expression(-1)))
        domains[(old,'VarInt')]=and_integer(q,z,xa,xb,lo,ua,ub,al)
        lift_refs[old]=(lo,ua,ub,al);lift_index[(t['name'],pos)]=old
    for t in s['tables']:
        cv=t['cost_var'];mapping[cv]=setup['costs'][cv]
        if not t['constant']:
            lo,hi=setup['costbounds'][cv];domains[(cv,'VarLower')]=lo;domains[(cv,'VarUpper')]=q.lin('Le',[[hi,F(1)]],plus(mapping[cv],expression(-39424)),constant=t['max']-39424)
            if len(t['nodes'])==2:domains[(cv,'VarInt')]=costints[cv]
            rows[t['norm']]=setup['norms'][t['name']]
            for side in range(len(t['nodes'])):
                if len(t['nodes'])==2:rows[t['moments'][side]]=setup['moments'][(t['name'],side)]
            continue
        marg={}
        for side,node in enumerate(t['nodes']):
            opposite=s['unary'][t['nodes'][1-side]];oppnorm=setup['norms'][opposite['name']]
            for pos0,u in s['unary'][node]['allowed'].items():
                state=pos0[0];x=oldnew[u];ids=[old for pos,old in t['allowed'].items() if pos[side]==state];count=len(ids)
                wanted=plus(sumexpr(mapping[i] for i in ids),expression(0,{x:F(1)}),-1)
                def inactive(c,g):
                    fixed=c.eqpair(g,{'VarLower':x})
                    upper=c.lin('Le',[[lift_refs[i][1+side],F(1)] for i in ids]+[[fixed,F(count-1)]],wanted)
                    lower=c.lin('Le',[[lift_refs[i][0],F(1)] for i in ids]+[[fixed,F(1)]],mul(wanted,-1))
                    return {'Witness':c.eqpair(upper,lower)}
                def active(c,g):
                    fixed=c.eqpair({'VarUpper':x},g)
                    upper=c.lin('Le',[[lift_refs[i][2-side],F(1)] for i in ids]+[[oppnorm,F(1)],[fixed,F(-1)]],wanted)
                    lower=c.lin('Le',[[lift_refs[i][3],F(1)] for i in ids]+[[oppnorm,F(-1)],[fixed,F(1-count)]],mul(wanted,-1))
                    return {'Witness':c.eqpair(upper,lower)}
                marg[(side,state)]=q.cases('Eq',wanted,expression(0,{x:F(1)}),{'VarInt':x},inactive,active)
        norm=q.lin('Eq',[[r,F(1)] for (side,j),r in marg.items() if side==0]+[[setup['norms'][s['unary'][t['nodes'][0]]['name']],F(1)]])
        rows[t['norm']]=norm;rows[t['cost_row']]=q.lin('Eq',[[norm,F(17)]])
        for side in range(2):rows[t['moments'][side]]=q.lin('Eq',[[r,F(state)] for (si,state),r in marg.items() if si==side and state])
    obj_terms=[[row_ref(b,'p_lin_0'),F(1)]]
    for t in s['tables']:
        if t['constant']:continue
        if len(t['nodes'])==2:obj_terms.append([costints[t['cost_var']],F(1)])
        else:obj_terms.extend([[{'VarInt':oldnew[i]},t['costs'][i]] for i in t['allowed'].values()])
    domains[(s['obj'],'VarInt')]=q.lin('Int',obj_terms,expression(0,{oldnew[s['obj']]:F(1)}),constant=289)
    domains[(s['obj'],'VarUpper')]=setup['objupper'];rows[a['row_index']['p_lin_0']]=row_ref(b,'p_lin_0')
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in sorted(oldnew.items())],'inverse':None}
    body=finish(q,a,mapping,claim,domains,rows)
    return claim,{'steps':p.steps,'end':{'IntervalLift':{'intervals':intervals,'body':body}}},{'obligations':len(body['end']['Return']['checks']),'root_steps':len(p.steps),'body_steps':len(q.steps),'continuous_pair_integer_proofs':len(pairints),'intervals':len(intervals)}


def run_part(args,a,b,s,phase):
    start=time.perf_counter();out=args.out.resolve();dest=out/('mi-'+phase);dest.mkdir(exist_ok=True);kernel=args.kernel.resolve()
    fn=forward_mi if phase=='forward' else reverse_mi
    claim,block,counts=fn(a,b,s);cert={'claims':[claim],'blocks':[block]};rp=dest/'proof.rpa';request=dest/'request.json'
    with rp.open('w') as f:f.write('RPA 5\n');json.dump(cert,f,separators=(',',':'));f.write('\n')
    request.write_text(json.dumps([claim],separators=(',',':'))+'\n')
    meta={'case_id':'test46','status':'PROOF_NOT_COMPLETED','scope':'Complete MI '+phase+' direction only; full bundle pending','partial_claim_status':'PROOF_NOT_COMPLETED','counts':counts,'preparation_seconds':time.perf_counter()-start,'kernel_binary':{'path':str(kernel),'sha256':sha(kernel)},'work_policy':1000000000,'preparer_sha256':sha(Path(__file__)),'kernel_runs':[]}
    def save():(dest/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
    save()
    for cmd in [['assemble',str(rp),str(dest/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(dest/'proof.rpx'),str(request)]]:
        result=subprocess.run([str(kernel)]+cmd,capture_output=True,text=True);meta['kernel_runs'].append({'command':[str(kernel)]+cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr});save()
        if result.returncode:raise SystemExit(result.stdout+result.stderr)
    meta['partial_claim_status']='VERIFIED';meta['artifacts']={n:{'bytes':(dest/n).stat().st_size,'sha256':sha(dest/n)} for n in ['proof.rpa','proof.rpx','request.json']};save();print(meta['kernel_runs'][-1]['stdout'],flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test46-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test46'));ap.add_argument('--kernel',type=Path,default=Path('target/validation-wave-rpx-2026-10-11/release/rpx'));ap.add_argument('--phase',choices=['forward','reverse'],required=True);args=ap.parse_args()
    a=parse_mps(args.run/'input/model.mps');b=parse_mps(args.run/'output/reformulated.mps');h=json.loads((args.run/'output/audit.json').read_text());s=inspect(a,b,h);print('complete original/final models classified',flush=True)
    run_part(args,a,b,s,args.phase)

if __name__=='__main__':main()
