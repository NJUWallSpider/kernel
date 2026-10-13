#!/usr/bin/env python3
"""Untrusted V7 simultaneous-menu reverse map with complete output obligations."""
from fractions import Fraction as F
from prepare_test40 import expression,plus,expr_json,row_fact
from prepare_affine import row_ref
from prepare_test88 import Builder
from prepare_test57 import substitute


def reverse_integer(source,target,structure,forward_claim):
    variables=[dict(v) for v in target['vars']];rows=[{**r,'terms':r['terms'].copy()} for r in target['rows']];witnesses=[];mapping=[None]*len(source['vars']);menu_laws={};source_options={}
    for mi,m in enumerate(structure['menus']):
        K=m['maximum_index'];y=m['target_activation'];z=m['target_index'];first=len(variables);sr=len(rows)
        for j in range(K+1):variables.append({'name':f'menu_{mi}_{j}','lower':F(0),'upper':F(1),'integer':True})
        rows.append({'name':f'menu_{mi}_sum','sense':'E','rhs':F(0),'terms':{**{first+j:F(1) for j in range(K+1)},y:F(-1)}})
        rows.append({'name':f'menu_{mi}_moment','sense':'E','rhs':F(0),'terms':{**{first+j:F(j) for j in range(1,K+1)},**({z:F(-1)} if z is not None else {})}})
        menu_laws[y]={'RowEq':sr}
        if z is not None:menu_laws[z]={'RowEq':sr+1}
        for j,i in enumerate(m['source_options']):mapping[i]=expression(0,{first+j:1});source_options[i]=first+j
        witnesses.append({'maximum_index':K,'activation':expr_json(expression(0,{y:1})),'index':expr_json(expression(0,{z:1}) if z is not None else expression()),'checks':[{'VarLower':y},{'VarUpper':y},{'VarInt':y},{'VarLower':z} if z is not None else 'Exact',{'RowUpper':m['target_link_row']} if z is not None else 'Exact',{'VarInt':z} if z is not None else 'Exact']})
    aux={};definition_rows={}
    for v in structure['resources']+[structure['objective']]:
        i=v['source_variable'];ri=v.get('source_row',v.get('source_definition_row'));e=v['target_expression'];mapping[i]=expression(F(e['constant']),{j:F(c) for j,c in e['terms']});aux[i]=v;definition_rows[ri]=i
    assert all(e is not None for e in mapping)
    model={'vars':variables,'var_index':{v['name']:i for i,v in enumerate(variables)},'rows':rows,'row_index':{r['name']:i for i,r in enumerate(rows)},'objective':target['objective']}
    builder=Builder(model);checks=[]
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'affine_projection':[[y,x] for x,y in forward_claim['affine_projection']],'inverse':None}
    def prove(kind,e,terms):
        if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):checks.append('Exact');return
        if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:checks.append(terms[0][0]);return
        checks.append(builder.lin(kind,terms,e))
    for i,v in enumerate(source['vars']):
        if i in source_options:
            j=source_options[i];assert v['lower']==0 and v['upper']==1 and v['integer'];checks.extend([{'VarLower':j},{'VarUpper':j},{'VarInt':j}]);continue
        for typ,enabled in [('VarLower',v['lower'] is not None),('VarUpper',v['upper'] is not None)]:
            if not enabled:continue
            e=plus(expression(v['lower']),mapping[i],-1) if typ=='VarLower' else plus(mapping[i],expression(-v['upper']));terms=None
            for ri in aux[i]['target_rows']:
                row=target['rows'][ri]
                if row['sense']=='E':terms=[[{'RowEq':ri},F(-1 if typ=='VarLower' else 1)]];break
                if (typ=='VarLower' and row['sense']=='G') or (typ=='VarUpper' and row['sense']=='L'):terms=[[row_ref(target,row['name']),F(1)]];break
            assert terms is not None;prove('Le',e,terms)
    group_rows={g['source_row']:g for g in structure['groups']}
    for ri,row in enumerate(source['rows']):
        typ=next(iter(row_ref(source,row['name'])));e=substitute(row_fact(row,typ),mapping)
        if ri in definition_rows:
            i=definition_rows[ri];pivot=row['terms'][i];terms=[[menu_laws[j],-pivot*c] for j,c in mapping[i][1].items()]
        else:
            group=group_rows[ri];terms=[[{'RowUpper':group['target_row']},F(1)]]+[[menu_laws[structure['menus'][mi]['target_activation']],F(1)] for mi in group['menu_indices']]
        prove('Eq' if typ=='RowEq' else 'Le',e,terms)
    prove('Eq',plus(substitute(source['objective'],mapping),target['objective'],-1),[])
    for j,(inp,out) in enumerate(claim['affine_projection']):
        e=expression(F(out['constant']),{i:F(c) for i,c in out['terms']});left=expression(F(inp['constant']),{i:F(c) for i,c in inp['terms']});expected=plus(substitute(e,mapping),left,-1)
        prove('Eq',expected,[[menu_laws[j],F(1)]])
    # The V7 pair contract appends every full target coordinate right-inverse
    # obligation after the ordinary V6 Return obligations.
    checks.extend(menu_laws[j] for j in range(len(target['vars'])))
    body={'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}
    return claim,{'steps':[],'end':{'MenuLift':{'menus':witnesses,'body':body}}},{'generated_variables':len(variables)-len(target['vars']),'generated_rows':len(rows)-len(target['rows']),'body_steps':len(builder.steps),'obligations':len(checks)}
