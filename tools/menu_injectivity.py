#!/usr/bin/env python3
"""Ordinary Lin/EqPair/Cases proof of exact menu-aggregation injectivity.

This is untrusted proof preparation. The V7 kernel independently builds both
actual source copies and the equality of every actual forward-map coordinate.
No one-hot uniqueness theorem is used by this proof.
"""
from fractions import Fraction as F
from prepare_test40 import expression,plus,mul,expr_json
from prepare_test88 import Builder


def make_paired_model(source,forward):
    n=len(source['vars']);variables=[dict(v) for v in source['vars']]+[{**v,'name':'paired_'+v['name']} for v in source['vars']]
    rows=[{**r,'terms':r['terms'].copy()} for r in source['rows']]
    rows += [{**r,'name':'paired_'+r['name'],'terms':{i+n:c for i,c in r['terms'].items()}} for r in source['rows']]
    for j,e in enumerate(forward):
        # Equal constants cancel between the two evaluations of the same map.
        rows.append({'name':f'aggregation_{j}','sense':'E','rhs':F(0),'terms':{**e[1],**{i+n:-c for i,c in e[1].items()}}})
    return {'vars':variables,'var_index':{v['name']:i for i,v in enumerate(variables)},'rows':rows,'row_index':{r['name']:i for i,r in enumerate(rows)},'objective':expression()}


def split_expression(builder,desired,split,integer,left,right):
    ident=builder.alloc();branches=[]
    for side,callback in enumerate((left,right)):
        assumption=split if side==0 else plus(expression(1),split,-1)
        child=Builder(builder.model,builder.counter,builder.facts,builder.assumptions+[assumption]);end=callback(child,{'Assumption':len(builder.assumptions)})
        if 'Witness' in end:assert child.kind(end['Witness'])=='Eq' and child.refexpr(end['Witness'])==desired
        else:
            fact=child.refexpr(end['Absurd']);assert child.kind(end['Absurd'])=='Le' and not fact[1] and fact[0]>0
        branches.append({'steps':child.steps,'end':end})
    builder.steps.append({'Cases':{'id':ident,'kind':'Eq','expression':expr_json(desired),'split':expr_json(split),'integer':integer,'left':branches[0],'right':branches[1]}});builder.facts[ident]=('Eq',desired);return {'Local':ident}


def injectivity(source,forward,structure):
    n=len(source['vars']);r=len(source['rows']);model=make_paired_model(source,forward);builder=Builder(model);equal={}
    for menu in structure['menus']:
        options=menu['source_options'];K=menu['maximum_index'];A={'RowEq':2*r+menu['target_activation']}
        if K==0:
            i=options[0];assert builder.refexpr(A)==expression(0,{i:1,i+n:-1});equal[i]=A;continue
        I={'RowEq':2*r+menu['target_index']}
        group=source['rows'][menu['source_group_row']]
        for j,variable in enumerate(options):
            desired=expression(0,{variable:1,variable+n:-1})
            def mixed(b,one,zero,one_assumption,zero_assumption):
                # one/zero say which source copy contains the selected option j.
                one_var=variable+one*n;zero_var=variable+zero*n;op=[i+one*n for i in options];zp=[i+zero*n for i in options]
                fixed=b.eqpair({'VarUpper':one_var},one_assumption)
                zero_fixed=b.eqpair(zero_assumption,{'VarLower':zero_var})
                other=[i for q,i in enumerate(op) if q!=j];outside=[i+one*n for i in group['terms'] if i not in options]
                zupper=b.lin('Le',[[{'RowUpper':menu['source_group_row']+one*r},F(1)],[one_assumption,F(1)]]+[[{'VarLower':i},F(1)] for i in outside],expression(0,{i:1 for i in other}))
                zlower=b.lin('Le',[[{'VarLower':i},F(1)] for i in other],expression(0,{i:-1 for i in other}))
                z_eq=b.eqpair(zupper,zlower)
                a_one=b.lin('Eq',[[fixed,F(1)],[z_eq,F(1)]],expression(-1,{i:1 for i in op}))
                m_expr=expression(-j,{i:F(q) for q,i in enumerate(op) if q})
                m_upper=b.lin('Le',[[fixed,F(j)],[z_eq,F(K)]]+[[{'VarLower':i},F(K-q)] for q,i in enumerate(op) if q!=j and K!=q],m_expr)
                m_lower=b.lin('Le',[[fixed,F(-j)]]+[[{'VarLower':i},F(q)] for q,i in enumerate(op) if q!=j and q],mul(m_expr,-1))
                m_one=b.eqpair(m_upper,m_lower)
                sign=F(-1 if one==0 else 1)
                a_other=b.lin('Eq',[[a_one,F(1)],[A,sign]],expression(-1,{i:1 for i in zp}))
                m_other=b.lin('Eq',[[m_one,F(1)],[I,sign]],expression(-j,{i:F(q) for q,i in enumerate(zp) if q}))
                lower_indices=expression(0,{i:1 for q,i in enumerate(zp) if q<j})
                integer=b.lin('Int',[[{'VarInt':i},F(1)] for q,i in enumerate(zp) if q<j],lower_indices)
                def below_none(child,assumption):
                    terms=[[m_other,F(1)],[a_other,F(-j-1)],[assumption,F(j+1)],[zero_fixed,F(1)]]
                    terms += [[{'VarLower':i},F(q)] for q,i in enumerate(zp) if q<j and q]
                    terms += [[{'VarLower':i},F(q-j-1)] for q,i in enumerate(zp) if q>j+1]
                    return {'Absurd':child.lin('Le',terms,expression(1))}
                def below_selected(child,assumption):
                    terms=[[a_other,F(K)],[m_other,F(-1)],[assumption,F(K-j+1)]]
                    terms += [[{'VarLower':i},F(j-1-q)] for q,i in enumerate(zp) if q<j-1]
                    terms += [[{'VarLower':i},F(K-q)] for q,i in enumerate(zp) if q>=j and q<K]
                    return {'Absurd':child.lin('Le',terms,expression(1))}
                return {'Witness':split_expression(b,desired,lower_indices,integer,below_none,below_selected)}
            def first_zero(b,first_assumption):
                def second_zero(child,second_assumption):
                    pos=child.lin('Le',[[first_assumption,F(1)],[{'VarLower':variable+n},F(1)]],desired)
                    neg=child.lin('Le',[[second_assumption,F(1)],[{'VarLower':variable},F(1)]],mul(desired,-1))
                    return {'Witness':child.eqpair(pos,neg)}
                return {'Witness':b.cases(desired,variable+n,second_zero,lambda child,second:mixed(child,1,0,second,first_assumption))}
            def first_one(b,first_assumption):
                def second_one(child,second_assumption):
                    pos=child.lin('Le',[[{'VarUpper':variable},F(1)],[second_assumption,F(1)]],desired)
                    neg=child.lin('Le',[[{'VarUpper':variable+n},F(1)],[first_assumption,F(1)]],mul(desired,-1))
                    return {'Witness':child.eqpair(pos,neg)}
                return {'Witness':b.cases(desired,variable+n,lambda child,second:mixed(child,0,1,first_assumption,second),second_one)}
            equal[variable]=builder.cases(desired,variable,first_zero,first_one)
    # Every continuous source coordinate is handled using both actual defining
    # equations; it is not silently omitted from the injectivity contract.
    for record in structure['resources']+[structure['objective']]:
        i=record['source_variable'];ri=record.get('source_row',record.get('source_definition_row'));row=source['rows'][ri];pivot=row['terms'][i]
        terms=[[{'RowEq':ri},1/pivot],[{'RowEq':ri+r},-1/pivot]]+[[equal[j],-c/pivot] for j,c in row['terms'].items() if j!=i]
        equal[i]=builder.lin('Eq',terms,expression(0,{i:1,i+n:-1}))
    assert set(equal)==set(range(n))
    return {'steps':builder.steps,'checks':[equal[i] for i in range(n)]}
