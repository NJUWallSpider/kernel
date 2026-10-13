#!/usr/bin/env python3
"""Exact untrusted proof of actual test48 conditional-simplex normalization.

All old variables/rows/bounds/objectives are checked. Local priority choices are
joint real interval extensions; their integrality and cost bound follow only
from ordinary exhaustive binary Cases. No production theorem is added.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha,signature,facts
from prepare_test88 import Builder
from prepare_test23 import extend

class Proof(Builder):
    def __init__(self,model,counter=None,inherited=None,assumptions=None,lookup=None):
        self.model=model;self.counter=counter if counter is not None else [0]
        self.facts=ChainMap({},inherited or {});self.assumptions=list(assumptions or []);self.steps=[]
        self.lookup=lookup
        if lookup is None:self.lookup={(k,signature(e)):r for k,e,r in facts(model,True)}
    def prove(self,kind,e,terms=None,constant=0):
        if (not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0))) or (kind=='Int' and e[0].denominator==1 and all(c.denominator==1 and self.model['vars'][i]['integer'] for i,c in e[1].items())):return 'Exact'
        r=self.lookup.get((kind,signature(e))) or self.lookup.get(('Eq',signature(e)))
        if r is not None:return r
        if terms is not None:
            if len(terms)==1 and terms[0][1]==1 and self.refexpr(terms[0][0])==e and self.kind(terms[0][0]) in (kind,'Eq'):return terms[0][0]
            return self.lin(kind,terms,e,constant)
        # A finite exact bound combination; not a solver and never trusted.
        if kind=='Le':
            terms=[];bound=e[0]
            for i,c in e[1].items():
                typ='VarUpper' if c>0 else 'VarLower';v=self.model['vars'][i]['upper' if c>0 else 'lower'];assert v is not None
                bound+=c*v;terms.append([{typ:i},abs(c)])
            assert bound<=0,('no bound proof',e,bound)
            return self.lin(kind,terms,e,constant=bound)
        opposite=self.lookup.get(('Eq',signature(mul(e,-1))))
        if opposite:return self.lin(kind,[[opposite,F(-1)]],e)
        raise AssertionError(('no proof',kind,e))
    def add(self,kind,ref):self.lookup[(kind,signature(self.refexpr(ref)))]=ref;return ref
    def cases(self,kind,wanted,bit,left,right):
        i=self.alloc();branches=[]
        for side,callback in enumerate((left,right)):
            guard=bit['expr'] if side==0 else plus(expression(1),bit['expr'],-1)
            child=Proof(self.model,self.counter,self.facts,self.assumptions+[guard],self.lookup)
            end=callback(child,{'Assumption':len(self.assumptions)})
            if 'Witness' in end:
                r=end['Witness'];assert r!='Exact' or not wanted[1]
                if r!='Exact':assert child.refexpr(r)==wanted and child.kind(r) in (kind,'Eq')
            else:assert not child.refexpr(end['Absurd'])[1] and child.refexpr(end['Absurd'])[0]>0
            branches.append({'steps':child.steps,'end':end})
        self.steps.append({'Cases':{'id':i,'kind':kind,'expression':expr_json(wanted),'split':expr_json(bit['expr']),'integer':bit['integer'],'left':branches[0],'right':branches[1]}})
        self.facts[i]=(kind,wanted);return {'Local':i}

def sumexpr(es):
    result=expression()
    for e in es:result=plus(result,e)
    return result

def eliminate(builder,ref,removed,kind=None):
    raw=builder.refexpr(ref);terms=[[ref,F(1)]]
    for i,c in list(raw[1].items()):
        if i in removed:terms.append([removed[i],-c])
    return builder.lin(kind or builder.kind(ref),terms)

def source_elimination(a,b,h):
    f=Proof(a);alias={}
    for name,root in h['copy_substitutions'].items():
        i,j=a['var_index'][name],a['var_index'][root];wanted=expression(0,{i:1,j:-1})
        alias[i]=f.prove('Eq',wanted)
    fixed={}
    for name,hint in h['fixed_zero_representatives'].items():
        if hint['kind']!='original_bound_or_equality':continue
        i=a['var_index'][name];original=hint['original_fixed'][0];j=a['var_index'][original]
        assert a['vars'][j]['lower']==a['vars'][j]['upper']==0
        eq=f.eqpair({'VarUpper':j},{'VarLower':j})
        if i!=j:eq=f.lin('Eq',[[eq,F(1)],[alias[j],F(-1)]],expression(0,{i:1}))
        fixed[i]=eq
    for name,hint in h['fixed_zero_representatives'].items():
        if hint['kind']!='zero_parent':continue
        i=a['var_index'][name];j=a['var_index'][hint['parent']]
        upper=f.lin('Le',[[row_ref(a,hint['implication_row']),F(1)],[fixed[j],F(1)]],expression(0,{i:1}))
        fixed[i]=f.eqpair(upper,{'VarLower':i})
    removed=dict(fixed)
    for i,ref in alias.items():
        root=h['copy_substitutions'][a['vars'][i]['name']];j=a['var_index'][root]
        removed[i]=f.lin('Eq',[[ref,F(1)],[fixed[j],F(1)]],expression(0,{i:1})) if j in fixed else ref
    d=a['var_index'][h['free_variable_substitution']['column']];ref=row_ref(a,'R0001936');scale=1/f.refexpr(ref)[1][d]
    terms=[[ref,scale]]
    for i,c in f.refexpr(ref)[1].items():
        if i in removed:terms.append([removed[i],-c*scale])
    removed[d]=f.lin('Eq',terms)
    assert len(removed)==len(a['vars'])-len(b['vars'])
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[]
    for i,v in enumerate(a['vars']):
        if v['name'] in b['var_index']:reverse.append(expression(0,{b['var_index'][v['name']]:1}));continue
        eq=f.refexpr(removed[i]);assert eq[1][i]==1
        back=plus(expression(0,{i:1}),eq,-1)
        assert all(a['vars'][j]['name'] in b['var_index'] for j in back[1])
        reverse.append(expression(back[0],{b['var_index'][a['vars'][j]['name']]:c for j,c in back[1].items()}))
        assert plus(expression(0,{i:1}),substitute(reverse[-1],forward),-1)==eq
    return f,removed,forward,reverse

def emit_checks(p,output,mapping,claim,rows=None,domains=None,objective=None,inverse=None):
    checks=[]
    for i,v in enumerate(output['vars']):
        for typ,side,sign in [('VarLower','lower',-1),('VarUpper','upper',1)]:
            if v[side] is None:continue
            wanted=plus(mul(mapping[i],sign),expression(-sign*v[side]));ref=(domains or {}).get((i,typ))
            checks.append(p.prove('Le',wanted,[[ref,F(1)]] if ref else None))
        if v['integer'] and claim['output_integers']:
            ref=(domains or {}).get((i,'VarInt'));checks.append(p.prove('Int',mapping[i],[[ref,F(1)]] if ref else None))
    for i,row in enumerate(output['rows']):
        typ=next(iter(row_ref(output,row['name'])));wanted=substitute(row_fact(row,typ),mapping);ref=(rows or {}).get(i)
        checks.append(p.prove('Eq' if typ=='RowEq' else 'Le',wanted,[[ref,F(1)]] if ref else None))
    wanted=plus(substitute(output['objective'],mapping),p.model['objective'],-1)
    checks.append(p.prove('Eq' if claim['objective']=='Equal' else 'Le',wanted,[[objective,F(1)]] if objective else None))
    for i,o in claim['projection']:checks.append(p.prove('Eq',plus(mapping[o],expression(0,{i:1}),-1)))
    for inp,out in claim.get('affine_projection',[]):
        parse=lambda x:expression(F(x['constant']),{i:F(c) for i,c in x['terms']})
        checks.append(p.prove('Eq',plus(substitute(parse(out),mapping),parse(inp),-1)))
    if inverse:
        for i,back in enumerate(inverse):checks.append(p.prove('Eq',plus(substitute(back,mapping),expression(0,{i:1}),-1)))
    return {'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}

def linear_blocks(a,b,h,claims):
    f,removed,forward,reverse=source_elimination(a,b,h);frows={}
    for i,row in enumerate(b['rows']):
        ref=row_ref(a,row['name']);desired=substitute(row_fact(row,next(iter(row_ref(b,row['name'])))),forward)
        terms=[[ref,F(1)]]
        for j,c in f.refexpr(ref)[1].items():
            if j in removed:terms.append([removed[j],-c])
        frows[i]=f.lin('Eq' if row['sense']=='E' else 'Le',terms,desired)
    for ref in removed.values():f.add('Eq',ref)
    forward_mi=emit_checks(f,b,forward,claims[0],rows=frows)
    # Reuse independently checked valid source facts in the LP forward proof.
    f_lp=Proof(a,f.counter,f.facts);f_lp.steps=copy.deepcopy(f.steps);f_lp.lookup=f.lookup.copy()
    forward_lp=emit_checks(f_lp,b,forward,claims[2],rows=frows,inverse=reverse)
    r=Proof(b)
    reverse_lp=emit_checks(r,a,reverse,claims[3],inverse=forward)
    return [forward_mi,None,forward_lp,reverse_lp],forward,reverse

def fixed_bit(p,bit,value,assumption):
    if value==0:return p.eqpair(assumption,bit['lower'])
    return p.eqpair(bit['upper'],assumption)

def boolean_expr(p,e,lower=None,upper=None):
    if not e[1]:assert e[0] in (0,1);return {'expr':e,'value':e[0]}
    lo=p.prove('Le',mul(e,-1),lower);hi=p.prove('Le',plus(e,expression(-1)),upper)
    terms=[[{'VarInt':i},c] for i,c in e[1].items()]
    integer=p.lin('Int',terms,e,constant=e[0])
    return {'expr':e,'lower':lo,'upper':hi,'integer':integer}

def case_all(p,kind,wanted,bits,leaf):
    variable=[];assigned={}
    for bit in bits:
        key=signature(bit['expr'])
        if 'value' in bit:assigned[key]=(bit['value'],None)
        elif key not in [signature(x['expr']) for x in variable]:variable.append(bit)
    def recurse(cur,index,state):
        if index==len(variable):return {'Witness':leaf(cur,state)}
        bit=variable[index];key=signature(bit['expr'])
        def branch(child,assumption,value):return recurse(child,index+1,{**state,key:(F(value),fixed_bit(child,bit,value,assumption))})
        ref=cur.cases(kind,wanted,bit,lambda child,a:branch(child,a,0),lambda child,a:branch(child,a,1));return {'Witness':ref}
    return recurse(p,0,assigned)['Witness']

def normalize_reverse(a,b,h,claim,reverse):
    pre=Proof(b);intervals=[];groups=[]
    def target_expr(name):return expression(0,{b['var_index'][name]:1}) if name in b['var_index'] else expression()
    for block in h['local_block_certificates']:
        children=sorted(block['optional_children'],key=lambda x:F(x['objective_coefficient_after_deficit_elimination']))
        current=[x for x in children if not x['fixed_zero']]
        mandatory=sumexpr(target_expr(name) for name in block['mandatory_selectors'])
        residual=plus(expression(1),mandatory,-1)
        old_children=sumexpr(target_expr(x['column']) for x in current)
        capacity=plus(old_children,residual,-1);cap=pre.prove('Le',capacity)
        r=boolean_expr(pre,residual,[[cap,F(1)]]+[[{'VarLower':b['var_index'][x['column']]},F(1)] for x in current])
        eligible=[boolean_expr(pre,target_expr(x['selector'])) for x in current]
        g={'hint':block,'children':current,'r':r,'eligible':eligible,'capacity':cap,'interval_ids':[]}
        for j,x in enumerate(current):
            bits=[r['expr'],eligible[j]['expr']]+[plus(expression(1),y['expr'],-1) for y in eligible[:j]]
            low=plus(sumexpr(bits),expression(1-len(bits)));checks=[]
            for lower in [expression(),low]:
                for k,upper in enumerate(bits):
                    expected=plus(lower,upper,-1)
                    if lower==expression():
                        if k==0:terms=[[r['lower'],F(1)]] if 'lower' in r else []
                        elif k==1:terms=[[eligible[j]['lower'],F(1)]] if 'lower' in eligible[j] else []
                        else:terms=[[eligible[k-2]['upper'],F(1)]] if 'upper' in eligible[k-2] else []
                    else:
                        terms=[]
                        for l,bit in enumerate(bits):
                            if l==k:continue
                            desc=r if l==0 else eligible[j] if l==1 else eligible[l-2]
                            key='upper' if l<2 else 'lower'
                            if key in desc:terms.append([desc[key],F(1)])
                        # Constants 0/1 may leave a nonpositive slack.
                    computed=sumexpr(pre.refexpr(ref) for ref,c in terms)
                    slack=plus(expected,computed,-1);assert not slack[1] and slack[0]<=0
                    checks.append(pre.prove('Le',expected,terms,constant=slack[0]))
            g['interval_ids'].append(len(intervals));intervals.append({'lower':[expr_json(expression()),expr_json(low)],'upper':[expr_json(x) for x in bits],'checks':checks})
        groups.append(g)
    ext,layout=extend(b,intervals);p=Proof(ext,pre.counter,pre.facts)
    mapping=copy.deepcopy(reverse);domains={};rowproofs={};costfacts=[]
    for group in groups:
        children=group['children'];r=group['r'];eligible=group['eligible'];layouts=[layout[k] for k in group['interval_ids']]
        z=[expression(0,{l['variable']:1}) for l in layouts];allbits=[r]+eligible
        def z_fixed(cur,state):
            rr=state[signature(r['expr'])][0];ys=[state[signature(bit['expr'])][0] for bit in eligible]
            result=[]
            for j,l in enumerate(layouts):
                descriptors=[(r,False),(eligible[j],False)]+[(bit,True) for bit in eligible[:j]]
                vals=[];eqs=[]
                for bit,negated in descriptors:
                    val,ref=state[signature(bit['expr'])];vals.append(1-val if negated else val)
                    if ref is not None:eqs.append([ref,F(-1 if negated else 1)])
                chosen=int(all(vals));
                if chosen:
                    lower=cur.lin('Le',[[{'RowLower':l['lower'][1]},F(1)]]+[[ref,-c] for ref,c in eqs],plus(expression(1),z[j],-1))
                    upper=cur.lin('Le',[[{'RowUpper':l['upper'][0]},F(1)]]+([[state[signature(r['expr'])][1],F(1)]] if state[signature(r['expr'])][1] else []),plus(z[j],expression(-1)))
                else:
                    k=vals.index(0);bit,negated=descriptors[k];ref=state[signature(bit['expr'])][1]
                    upper=cur.lin('Le',[[{'RowUpper':l['upper'][k]},F(1)]]+([[ref,F(-1 if negated else 1)]] if ref else []),z[j]);lower={'RowLower':l['lower'][0]}
                result.append((F(chosen),cur.eqpair(upper,lower)))
            return rr,ys,result
        for j,(x,l) in enumerate(zip(children,layouts)):
            source_index=a['var_index'][x['column']];mapping[source_index]=z[j]
            domains[(source_index,'VarLower')]={'RowLower':l['lower'][0]}
            domains[(source_index,'VarUpper')]=p.prove('Le',plus(z[j],expression(-1)),[[{'RowUpper':l['upper'][0]},F(1)]]+([[r['upper'],F(1)]] if 'upper' in r else []))
            def integral_leaf(cur,state,j=j):
                _,_,values=z_fixed(cur,state);val,eq=values[j];return cur.lin('Int',[[eq,F(1)]],z[j],constant=val)
            domains[(source_index,'VarInt')]=case_all(p,'Int',z[j],allbits,integral_leaf)
            rowproofs[a['row_index'][x['link_row']]]={'RowUpper':l['upper'][1]}
        wanted=plus(sumexpr(z),r['expr'],-1)
        def packing_leaf(cur,state):
            rv,_,values=z_fixed(cur,state);terms=[[ref,F(1)] for _,ref in values];ref=state[signature(r['expr'])][1]
            if ref:terms.append([ref,F(-1)])
            return cur.lin('Le',terms,wanted,constant=sum(val for val,_ in values)-rv)
        rowproofs[a['row_index'][group['hint']['row']]]=case_all(p,'Le',wanted,allbits,packing_leaf) if children else p.prove('Le',wanted)
        costs=[F(x['objective_coefficient_after_deficit_elimination']) for x in children]
        wanted_cost=plus(sumexpr(mul(zz,c) for zz,c in zip(z,costs)),sumexpr(mul(expression(0,{b['var_index'][x['column']]:1}),c) for x,c in zip(children,costs)),-1)
        def cost_leaf(cur,state):
            rv,ys,values=z_fixed(cur,state);selected=[j for j,(val,_) in enumerate(values) if val]
            cstar=costs[selected[0]] if selected else min(costs) if rv==0 and costs else F(0)
            terms=[[group['capacity'],-cstar]] if cstar else []
            for j,(x,c) in enumerate(zip(children,costs)):
                vi=b['var_index'][x['column']]
                if c>=cstar:terms.append([{'VarLower':vi},c-cstar])
                else:
                    assert ys[j]==0;selector_eq=state[signature(eligible[j]['expr'])][1]
                    upper=cur.lin('Le',[[row_ref(b,x['link_row']),F(1)]]+([[selector_eq,F(1)]] if selector_eq else []),expression(0,{vi:1}))
                    zero=cur.eqpair(upper,{'VarLower':vi});terms.append([zero,cstar-c])
            residual_eq=state[signature(r['expr'])][1]
            if residual_eq and cstar:terms.append([residual_eq,-cstar])
            terms += [[ref,c] for (_,ref),c in zip(values,costs)]
            return cur.lin('Le',terms,wanted_cost)
        costfacts.append(case_all(p,'Le',wanted_cost,allbits,cost_leaf) if children else 'Exact')
    # Restore removed copies/fixed values, and both complete free coordinates.
    d=a['var_index'][h['free_variable_substitution']['column']]
    child_ids=[a['var_index'][x['column']] for g in h['local_block_certificates'] for x in g['optional_children']]
    mapping[d]=plus(expression(475),sumexpr(mapping[i] for i in child_ids),-1)
    objective_index=a['var_index']['C0001746'];row=a['rows'][a['row_index']['R0002107']];pivot=row['terms'][objective_index]
    assert pivot==1
    mapping[objective_index]=mul(substitute(plus(expression(row['rhs']),expression(0,{i:c for i,c in row['terms'].items() if i!=objective_index}),-1),mapping),1/pivot)
    # Direct unchanged rows and zero identities remain ordinary exact checks.
    obj_wanted=plus(substitute(a['objective'],mapping),b['objective'],-1)
    objective=p.lin('Le',[[ref,F(1)] for ref in costfacts if ref!='Exact']+[[row_ref(b,'R0002107'),F(-1)]],obj_wanted)
    body=emit_checks(p,a,mapping,claim,rows=rowproofs,domains=domains,objective=objective)
    return {'steps':pre.steps,'end':{'IntervalLift':{'intervals':intervals,'body':body}}},{'intervals':len(intervals),'interval_rows':len(ext['rows'])-len(b['rows']),'body_obligations':len(body['end']['Return']['checks']),'allocated_ids':p.counter[0]}

def prepare(a,b,h):
    retained=h['retained_binary_columns'];deleted=[v for v in h['fixed_zero_representatives'] if v not in {x['column'] for g in h['local_block_certificates'] for x in g['optional_children']}]
    assert len(retained)==144 and len(deleted)==6
    claims=[]
    for integer in [True,False]:
        for reverse in [False,True]:
            inp,out=(b,a) if reverse else (a,b)
            affine=[]
            for name in deleted:
                pair=[expr_json(expression(0,{a['var_index'][name]:1})),expr_json(expression())]
                affine.append(pair[::-1] if reverse else pair)
            claims.append({'reverse':reverse,'input_integers':integer,'output_integers':integer,'objective':'NonIncreasing' if integer and reverse else 'Equal','projection':[[inp['var_index'][name],out['var_index'][name]] for name in retained],'affine_projection':affine,'inverse':None if integer else 2 if reverse else 3})
    blocks,forward,reverse=linear_blocks(a,b,h,claims)
    blocks[1],counts=normalize_reverse(a,b,h,claims[1],reverse)
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'retained_selector_projections':144,'fixed_selector_affine_observations':6,'local_blocks':len(h['local_block_certificates']),**counts}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test48-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test48'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);run=args.run.resolve();source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test48','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete MI forward objective equality, MI reverse objective nonincrease, all150 selector observations both directions; complete LP objective-preserving affine bijection with both inverse identities. No equality of nonoptimal MI child tuples or objective values claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                d['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        d['negative_checks']=[]
        for name,reason in [
            ('missing_interval_pair','One middle priority interval omits a lower/upper compatibility reference.'),
            ('continuous_integer_witness','An integer Cases split cites an actually continuous target child as its integrality witness.'),
            ('fractional_child_mapping','One original binary child is mapped back to an unrounded continuous target child.'),
            ('wrong_objective_combination','The actual objective-definition equality receives the opposite multiplier in the final cost bound.'),
            ('lost_fixed_selector','An explicitly preserved deleted selector is reconstructed as one rather than zero.'),
        ]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['IntervalLift'];body=lift['body'];returned=body['end']['Return']
            if name=='missing_interval_pair':lift['intervals'][len(lift['intervals'])//2]['checks'].pop()
            elif name=='continuous_integer_witness':
                target_model=parse_mps(target);continuous=next(i for i,v in enumerate(target_model['vars']) if not v['integer'] and v['lower']==0)
                step=next(step['Cases'] for step in body['steps'] if 'Cases' in step);step['integer']={'VarInt':continuous}
            elif name=='fractional_child_mapping':
                target_model=parse_mps(target);source_model=parse_mps(source);hint=json.loads(audit.read_text());child=next(x['column'] for g in hint['local_block_certificates'] for x in g['optional_children'] if not x['fixed_zero'])
                returned['map'][source_model['var_index'][child]]=expr_json(expression(0,{target_model['var_index'][child]:1}))
            elif name=='wrong_objective_combination':
                objective_ref=returned['checks'][-151];assert set(objective_ref)=={'Local'}
                step=next(step['Lin'] for step in body['steps'] if 'Lin' in step and step['Lin']['id']==objective_ref['Local'])
                index=parse_mps(target)['row_index']['R0002107'];term=next(t for t in step['terms'] if t[0]=={'RowEq':index});assert term[1]=='-1';term[1]='1'
            elif name=='lost_fixed_selector':
                obs=bad['claims'][1]['affine_projection'][0][1];assert len(obs['terms'])==1
                returned['map'][obs['terms'][0][0]]=expr_json(expression(1))
            attack_rpa=out/(name+'.rpa');attack_rpx=out/(name+'.rpx');attack_rpa.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n')
            assembled=subprocess.run([str(k),'assemble',str(attack_rpa),str(attack_rpx)],capture_output=True,text=True);assert assembled.returncode==0,assembled.stdout+assembled.stderr
            checked=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(attack_rpx),str(request)],capture_output=True,text=True)
            result=json.loads(checked.stdout);assert checked.returncode==2 and result['status']=='INVALID',(name,checked.stdout,checked.stderr)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':checked.returncode,'result':result,'rpa_sha256':sha(attack_rpa),'rpx_sha256':sha(attack_rpx)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))
if __name__=='__main__':main()
