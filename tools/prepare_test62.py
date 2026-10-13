#!/usr/bin/env python3
"""Complete Boolean projection, injectivity, and caller-bound LP image exclusion."""
from pathlib import Path
from fractions import Fraction as F
from collections import ChainMap
import argparse,json
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact
from prepare_test70 import SparseBuilder
from prepare_test88 import fix_binary
from prepare_test23 import extend
from prepare_test57 import substitute
from prepare_test54 import box
from prepare_test84 import rounded
from menu_injectivity import make_paired_model
from prepare_test8 import execute


def cases(p,kind,wanted,variables,leaf,state=None):
    state={} if state is None else state
    if not variables:return leaf(p,state)
    variable=variables[0];ident=p.alloc();branches=[];split=expression(0,{variable:1})
    for value in (0,1):
        assumption=split if value==0 else expression(1,{variable:-1});child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[assumption]);child.facts=ChainMap({},p.facts)
        fixed=fix_binary(child,variable,value,{'Assumption':len(p.assumptions)});end=cases(child,kind,wanted,variables[1:],leaf,{**state,variable:(F(value),fixed)})
        if 'Witness' in end:assert child.kind(end['Witness'])==kind and child.refexpr(end['Witness'])==wanted
        else:assert child.kind(end['Absurd'])=='Le' and not child.refexpr(end['Absurd'])[1] and child.refexpr(end['Absurd'])[0]>0
        branches.append({'steps':child.steps,'end':end})
    p.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),'split':expr_json(split),'integer':{'VarInt':variable},'left':branches[0],'right':branches[1]}});p.facts[ident]=(kind,wanted);return {'Witness':{'Local':ident}}


def under(p,kind,wanted,state):
    value=wanted[0]+sum(c*state[i][0] for i,c in wanted[1].items());terms=[[state[i][1],c] for i,c in wanted[1].items()]
    assert (kind=='Le' and value<=0) or (kind=='Eq' and value==0) or (kind=='Int' and value.denominator==1)
    return p.lin(kind,terms,wanted,constant=value)


def reduced(p,ref,state):
    e=p.refexpr(ref);assert set(e[1])<=set(state)
    return p.lin(p.kind(ref),[[ref,1]]+[[state[i][1],-c] for i,c in e[1].items()])


def source_indicator(p,pattern,state,offset=0,rowoffset=0):
    a=pattern['a'];variable=a['var_index'][pattern['aux']]+offset;match=all(state[a['var_index'][name]+offset][0]==value for name,value in pattern['pattern'].items());value=F(int(match));refs=[]
    for name in pattern['rows']:
        r=row_ref(a,name);key,index=next(iter(r.items()));ref={key:index+rowoffset};e=p.refexpr(ref);terms=[[ref,1]]+[[state[i][1],-c] for i,c in e[1].items() if i!=variable];bound=p.lin('Le',terms);assert set(p.refexpr(bound)[1])=={variable};refs.append(bound)
    lower=next(r for r in refs if p.refexpr(r)[1][variable]==-1);upper=next(r for r in refs if p.refexpr(r)[1][variable]==1)
    if match:
        assert p.refexpr(lower)==expression(1,{variable:-1});eq=p.eqpair({'VarUpper':variable},lower)
    else:
        rounded_upper=rounded(p,upper,{'VarInt':variable});assert p.refexpr(rounded_upper)==expression(0,{variable:1});eq=p.eqpair(rounded_upper,{'VarLower':variable})
    assert p.refexpr(eq)==expression(-value,{variable:1});return value,eq


def generated_indicator(p,pattern,state,layout):
    variable=layout['variable'];match=all(state[p.model['var_index'][name]][0]==value for name,value in pattern['pattern'].items());value=F(int(match))
    if match:
        ref={'RowLower':layout['lower'][1]};e=p.refexpr(ref);lower=p.lin('Le',[[ref,1]]+[[state[i][1],-c] for i,c in e[1].items() if i!=variable],expression(1,{variable:-1}));upper={'RowUpper':layout['upper'][0]};e=p.refexpr(upper);upper=p.lin('Le',[[upper,1]]+[[state[i][1],-c] for i,c in e[1].items() if i!=variable],expression(-1,{variable:1}))
    else:
        index=next(j for j,(name,v) in enumerate(pattern['pattern'].items()) if state[p.model['var_index'][name]][0]!=v);ref={'RowUpper':layout['upper'][index]};e=p.refexpr(ref);upper=p.lin('Le',[[ref,1]]+[[state[i][1],-c] for i,c in e[1].items() if i!=variable],expression(0,{variable:1}));lower={'RowLower':layout['lower'][0]}
    return value,p.eqpair(upper,lower)


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(4500,7029,500,2539)
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in a['vars']+b['vars'])
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];common=[[next(iter(e[1])),j] for j,e in enumerate(forward)];assert substitute(b['objective'],forward)==a['objective']
    patterns=[];fixed={};groupbyrow={};allrows=[]
    for g in h['groups']:
        for name,row in g['fixed_zero_auxiliaries'].items():
            i=a['var_index'][name];ref=row_ref(a,row);assert row_fact(a['rows'][ref['RowEq']],'RowEq')==expression(0,{i:1});fixed[i]=ref;allrows.append(row)
        for pat in g['active_patterns']:
            pat={**pat,'a':a};patterns.append(pat);allrows+=pat['rows'];T=expression(sum(1 for v in pat['pattern'].values() if v==1),{a['var_index'][name]:1 if v==0 else -1 for name,v in pat['pattern'].items()});i=a['var_index'][pat['aux']]
            refs={a['rows'][a['row_index'][name]]['sense']:row_fact(a['rows'][a['row_index'][name]],'RowLower' if a['rows'][a['row_index'][name]]['sense']=='G' else 'RowUpper') for name in pat['rows']}
            assert refs['G']==plus(expression(1,{i:-1}),T,-1);assert refs['L']==plus(expression(F(-1099,1000),{i:1}),T,F(333,1000))
        allrows+=g['original_or_rows']
        for name in g['replacement_rows']:assert name not in groupbyrow;groupbyrow[name]=g
    assert len(allrows)==len(set(allrows))==7029 and set(allrows)==set(a['row_index']) and set(groupbyrow)==set(b['row_index'])
    patbyname={pat['aux']:pat for pat in patterns}
    def completed_source(p,g,state):
        result=dict(state)
        for name in g['auxiliary_variables']:
            i=a['var_index'][name];result[i]=(F(0),fixed[i]) if i in fixed else source_indicator(p,patbyname[name],state)
        return result
    f=SparseBuilder(a);fchecks=[]
    for i,j in common:fchecks += [{'VarLower':i},{'VarUpper':i},{'VarInt':i}]
    for row in b['rows']:
        g=groupbyrow[row['name']];wanted=substitute(row_fact(row,'RowLower'),forward);variables=[a['var_index'][name] for name in g['relation_variables']]
        def leaf(p,state,g=g,wanted=wanted):
            value=wanted[0]+sum(c*state[i][0] for i,c in wanted[1].items())
            if value<=0:return {'Witness':under(p,'Le',wanted,state)}
            full=completed_source(p,g,state)
            for name in g['original_or_rows']:
                ref=row_ref(a,name);e=p.refexpr(ref);v=e[0]+sum(c*full[i][0] for i,c in e[1].items())
                if v>0:return {'Absurd':reduced(p,ref,full)}
            raise AssertionError(('original admits forbidden clause cube',g['output'],state))
        fchecks.append(cases(f,'Le',wanted,variables,leaf)['Witness'])
    fchecks+=['Exact']*(1+500);claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':common,'inverse':None}];blocks=[{'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':fchecks}}}]
    pre=SparseBuilder(b);intervals=[]
    for pat in patterns:
        literals=[expression(0,{b['var_index'][name]:1}) if value else expression(1,{b['var_index'][name]:-1}) for name,value in pat['pattern'].items()];total=expression(-2)
        for e in literals:total=plus(total,e)
        lows=[expression(),total];highs=literals;checks=[box(pre,plus(lo,hi,-1)) for lo in lows for hi in highs];intervals.append({'lower':[expr_json(e) for e in lows],'upper':[expr_json(e) for e in highs],'checks':checks})
    extended,layouts=extend(b,intervals);p=SparseBuilder(extended,pre.counter,pre.facts);layoutbyname={pat['aux']:layout for pat,layout in zip(patterns,layouts)}
    mapping=[];domain={};rchecks=[]
    for i,v in enumerate(a['vars']):
        name=v['name']
        if name in b['var_index']:
            j=b['var_index'][name];mapping.append(expression(0,{j:1}));domain[i]=({'VarLower':j},{'VarUpper':j},{'VarInt':j})
        elif i in fixed:mapping.append(expression());domain[i]=('Exact','Exact','Exact')
        else:
            layout=layoutbyname[name];variable=layout['variable'];mapping.append(expression(0,{variable:1}));lower={'RowLower':layout['lower'][0]};upperref={'RowUpper':layout['upper'][0]};residual=plus(expression(-1,{variable:1}),p.refexpr(upperref),-1);upper=p.lin('Le',[[upperref,1],[box(p,residual),1]],expression(-1,{variable:1}));pat=patbyname[name]
            def leaf(child,state,pat=pat,layout=layout,variable=variable):
                value,eq=generated_indicator(child,pat,state,layout);return {'Witness':child.lin('Int',[[eq,1]],expression(0,{variable:1}),constant=value)}
            integer=cases(p,'Int',expression(0,{variable:1}),[b['var_index'][n] for n in pat['pattern']],leaf)['Witness'];domain[i]=(lower,upper,integer)
        rchecks+=list(domain[i])
    originalproof={}
    for i,ref in fixed.items():originalproof[ref['RowEq']]='Exact'
    for pat in patterns:
        layout=layoutbyname[pat['aux']]
        for name in pat['rows']:
            ri=a['row_index'][name];row=a['rows'][ri];wanted=substitute(row_fact(row,'RowLower' if row['sense']=='G' else 'RowUpper'),mapping)
            if row['sense']=='G':ref={'RowLower':layout['lower'][1]};assert p.refexpr(ref)==wanted
            else:
                base=p.lin('Le',[[{'RowUpper':index},F(1,3)] for index in layout['upper']]);residual=plus(wanted,p.refexpr(base),-1);ref=p.lin('Le',[[base,1],[box(p,residual),1]],wanted)
            originalproof[ri]=ref
    for g in h['groups']:
        variables=[b['var_index'][name] for name in g['relation_variables']]
        for name in g['original_or_rows']:
            ri=a['row_index'][name];row=a['rows'][ri];wanted=substitute(row_fact(row,'RowLower' if row['sense']=='G' else 'RowUpper'),mapping)
            def leaf(child,state,g=g,wanted=wanted):
                for targetname in g['replacement_rows']:
                    ref=row_ref(b,targetname);e=child.refexpr(ref);value=e[0]+sum(c*state[i][0] for i,c in e[1].items())
                    if value>0:return {'Absurd':reduced(child,ref,state)}
                full=dict(state)
                for aux in g['auxiliary_variables']:
                    if aux in layoutbyname:
                        layout=layoutbyname[aux];full[layout['variable']]=generated_indicator(child,patbyname[aux],state,layout)
                return {'Witness':under(child,'Le',wanted,full)}
            originalproof[ri]=cases(p,'Le',wanted,variables,leaf)['Witness']
    assert set(originalproof)==set(range(7029));rchecks += [originalproof[i] for i in range(7029)];rchecks+=['Exact']*(1+500+500)
    claims.append({'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in common],'inverse':None});blocks.append({'steps':pre.steps,'end':{'IntervalLift':{'intervals':intervals,'body':{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':rchecks}}}}}})
    paired=make_paired_model(a,forward);q=SparseBuilder(paired);n=4500;r=7029;equal={i:{'RowEq':2*r+j} for i,j in common}
    for i,ref in fixed.items():equal[i]=q.lin('Eq',[[ref,1],[{'RowEq':ref['RowEq']+r},-1]],expression(0,{i:1,i+n:-1}))
    for pat in patterns:
        variable=a['var_index'][pat['aux']];wanted=expression(0,{variable:1,variable+n:-1});variables=[a['var_index'][name] for name in pat['pattern']]
        def leaf(child,state,pat=pat,wanted=wanted,variables=variables):
            full=dict(state)
            for i in variables:full[i+n]=(state[i][0],child.lin('Eq',[[state[i][1],1],[equal[i],-1]],expression(-state[i][0],{i+n:1})))
            leftvalue,left=source_indicator(child,pat,full);rightvalue,right=source_indicator(child,pat,full,n,r);assert leftvalue==rightvalue;return {'Witness':child.lin('Eq',[[left,1],[right,-1]],wanted)}
        equal[variable]=cases(q,'Eq',wanted,variables,leaf)['Witness']
    assert set(equal)==set(range(4500));bijection={'claim':{'forward_claim':0,'reverse_claim':1},'injectivity':{'steps':q.steps,'checks':[equal[i] for i in range(4500)]}}
    point=[F(1,2) if v['name'] in b['var_index'] else F(0) for v in a['vars']]
    for g in h['groups']:
        for pat in g['active_patterns']:point[a['var_index'][pat['aux']]]=F(1,2*len(g['active_patterns']))
    violations=[]
    for row in b['rows']:
        e=row_fact(row,'RowLower');residual=e[0]+sum(c*F(1,2) for c in e[1].values())
        if residual>0:violations.append({'row':row['name'],'source_retained_image_residual':str(residual),'target_row':expr_json(e)})
    assert len(violations)==7
    cert={'claims':claims,'blocks':blocks,'bijections':[bijection],'points':[{'claim':{'ImageExclusion':{'point_in_target':False,'map':[expr_json(e) for e in forward]}},'values':[str(x) for x in point]}]}
    counts={'source_variables':4500,'target_variables':500,'source_rows':7029,'target_rows':2539,'local_groups':500,'eliminated_auxiliaries':4000,'active_pattern_intervals':len(patterns),'fixed_zero_auxiliaries':len(fixed),'claims':2,'bijections':1,'points':1,'injectivity_coordinates':4500,'root_steps_by_claim':[len(f.steps),len(pre.steps)],'reverse_body_steps':len(p.steps),'injectivity_steps':len(q.steps)}
    residual={'contract':'The complete source LP point is feasible, and its complete caller-bound retained-coordinate image violates an actual target LP bound or row. No containment is requested or inferred.','point_dimensions':4500,'image_dimensions':500,'evidence_scope':'The ImageExclusion claim checks complete source LP feasibility, every image expression, and existence of an actual target LP violation. The list of seven row labels/residuals is supplementary preparer arithmetic; the kernel contract does not assert the exact number of violations.','violations':violations}
    return cert,counts,residual


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));ap.add_argument('--out',type=Path,default=Path('cases/test62'));args=ap.parse_args();run=Path('/Users/bhz/Code/reform_test/runs/test62-nomf-B1');source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';cert,counts,residual=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    def bad_injectivity(c):next(s['Cases'] for s in c['bijections'][0]['injectivity']['steps'] if 'Cases' in s)['integer']=None
    mutations=[('missing_interval_compatibility','Omits one lower-upper compatibility obligation.',lambda c:c['blocks'][1]['end']['IntervalLift']['intervals'][0]['checks'].pop()),('wrong_reconstruction','Maps an active source auxiliary to constant zero instead of its Boolean completion.',lambda c:c['blocks'][1]['end']['IntervalLift']['body']['end']['Return']['map'].__setitem__(7,expr_json(expression()))),('missing_injectivity_integer','Uses a non-exhaustive continuous split in Boolean uniqueness.',bad_injectivity),('infeasible_source_point','Makes the complete source witness violate a variable lower bound.',lambda c:c['points'][0]['values'].__setitem__(0,'-1')),('wrong_exclusion_map','Changes an affine image expression bound by the caller request.',lambda c:c['points'][0]['claim']['ImageExclusion']['map'].__setitem__(0,expr_json(expression()))),('surplus_point_refutation','Adds a forbidden refutation to a direct image-exclusion point.',lambda c:c['points'][0].update(refutation={'steps':[],'end':{'Absurd':{'fact':'Exact'}}}))]
    execute('test62',source,target,audit,cert,counts,'Complete integer feasible-set projection equivalence on all 500 retained original Boolean coordinates, unique jointly compatible Boolean reconstruction of all 4000 removed auxiliaries, and exact pointwise objective equality. Both directional claims check all actual model rows and domains; the caller-bound V7 bijection checks all4500 original-coordinate injectivity obligations. A caller-bound ImageExclusion claim checks the complete source-LP fractional witness and its complete actual-target image, proving that image violates an actual target LP bound or row. No global LP containment, global strict inclusion, global integer feasible point, numeric optimum, or solver-performance claim is certified.',mutations,args.out,args.kernel,version=10,extra={'image_exclusion_contract':residual,'protocol_status':'WORKING_VERSION_10_NOT_FROZEN'})


if __name__=='__main__':main()
