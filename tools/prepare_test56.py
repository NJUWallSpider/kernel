#!/usr/bin/env python3
"""Actual test56 zero-extension proof using shared partition and sparse residuals."""
from fractions import Fraction as F
from prepare_test29 import execute,prove,zero_extension
from prepare_affine import row_ref
from prepare_test40 import expression,plus
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test84 import rounded


def prepare(a,b,h):
    f=SparseBuilder(a);zeros={}
    for d in h['forced_zero_proof_steps']:
        ref=row_ref(a,d['row']);e=f.refexpr(ref);variables={a['var_index'][n] for n in d['variables']};assert e[0]==0 and not variables&zeros.keys()
        if d['rule']=='binary_2u_minus_v':
            assert f.kind(ref)=='Eq' and set(e[1])==variables
            u=next(i for i,c in e[1].items() if c==2);v=next(i for i,c in e[1].items() if c==-1)
            upper=f.lin('Le',[[ref,F(1,2)],[{'VarUpper':v},F(1,2)]],expression(F(-1,2),{u:1}));zeros[u]=f.eqpair(rounded(f,upper,{'VarInt':u}),{'VarLower':u});zeros[v]=f.lin('Eq',[[zeros[u],2],[ref,-1]],expression(0,{v:1}))
        else:
            assert d['rule']=='zero_nonnegative_sum';remaining={i:c for i,c in e[1].items() if i not in zeros};assert set(remaining)==variables
            sign=1 if all(c>0 for c in remaining.values()) else -1;assert all(sign*c>0 for c in remaining.values()) and (sign==1 or f.kind(ref)=='Eq')
            total=f.lin('Le',[[ref,sign]]+[[zeros[i],-sign*c] for i,c in e[1].items() if i in zeros],expression(0,{i:sign*c for i,c in remaining.items()}))
            for i,c in remaining.items():
                c*=sign;upper=f.lin('Le',[[total,1/c]]+[[{'VarLower':j},sign*q/c] for j,q in remaining.items() if j!=i],expression(0,{i:1}));zeros[i]=f.eqpair(upper,{'VarLower':i})
    assert len(zeros)==1664
    forward_mapping=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];reverse_mapping=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    cardinalities={};opposites={};partition=set()
    for d in h['cardinality_pairs']:
        rn=d['retained_row'];opp=d['deleted_opposite_row'];lower=row_ref(a,rn);upper=row_ref(a,opp);le=f.refexpr(lower);ue=f.refexpr(upper);support=set(le[1]);assert le[1]=={i:-8 for i in support} and ue[1]=={i:8 for i in support} and not support&zeros.keys() and not partition&support;partition|=support
        negint=f.lin('Int',[[{'VarInt':i},-1] for i in sorted(support)],expression(0,{i:-1 for i in support}));posint=f.lin('Int',[[negint,-1]],expression(0,{i:1 for i in support}))
        lo=rounded(f,f.lin('Le',[[lower,F(1,8)]]),negint);up=rounded(f,f.lin('Le',[[upper,F(1,8)]]),posint);eq=f.eqpair(up,lo);assert f.refexpr(eq)==expression(-d['cardinality'],{i:1 for i in support});cardinalities[rn]=eq;opposites[opp]=rn
    total=f.lin('Eq',[[r,1] for r in cardinalities.values()],expression(-350,{i:1 for i in partition}));assert len(partition)==101656
    dense={d['row']:d for d in h['dense_replacement_derivations']};forward={}
    for row in b['rows']:
        rn=row['name'];wanted=substitute(SparseBuilder(b).refexpr(row_ref(b,rn)),forward_mapping)
        if rn in cardinalities:check=cardinalities[rn];assert f.refexpr(check)==wanted
        elif rn in dense:
            d=dense[rn];av=F(d['selected_original_coefficient']);bv=F(d['other_original_coefficient']);scale=F(d['new_coefficient'])/(av-bv);assert scale>0
            raw=f.lin('Le',[[row_ref(a,rn),scale],[total,-bv*scale]]);assert f.refexpr(raw)[1]==wanted[1]
            integer=f.lin('Int',[[{'VarInt':i},c] for i,c in wanted[1].items()],expression(0,wanted[1]));check=rounded(f,raw,integer);assert f.refexpr(check)==wanted
        else:
            ref=row_ref(a,rn);e=f.refexpr(ref);check=prove(f,f.kind(ref),wanted,[[ref,1]]+[[zeros[i],-c] for i,c in e[1].items() if i in zeros])
        forward[rn]=check
    r=SparseBuilder(b);rtotal=r.lin('Eq',[[row_ref(b,rn),1] for rn in cardinalities],expression(-350,{b['var_index'][a['vars'][i]['name']]:1 for i in partition}));deleted={d['row']:d for d in h['deleted_rows']};reverse={}
    for row in a['rows']:
        rn=row['name'];ref=row_ref(a,rn);wanted=substitute(f.refexpr(ref),reverse_mapping);kind=f.kind(ref)
        if rn in cardinalities or rn in opposites:
            eqname=opposites.get(rn,rn);scale=8 if rn in opposites else -8;terms=[[row_ref(b,eqname),scale]];constant=wanted[0]-scale*r.refexpr(terms[0][0])[0];check=prove(r,'Le',wanted,terms,constant)
        elif rn in dense:
            d=dense[rn];av=F(d['selected_original_coefficient']);bv=F(d['other_original_coefficient']);scale=(av-bv)/F(d['new_coefficient']);terms=[[row_ref(b,rn),scale],[rtotal,bv]];constant=wanted[0]-scale*r.refexpr(terms[0][0])[0]-bv*r.refexpr(rtotal)[0];check=prove(r,'Le',wanted,terms,constant)
        elif rn in deleted and deleted[rn]['reason']=='subset_of_fixed_cardinality_support':
            d=deleted[rn];eq=row_ref(b,d['witness_equality_row']);ee=r.refexpr(eq);assert wanted[1]=={i:1 for i in wanted[1]} and wanted[1].keys()<=ee[1].keys();terms=[[eq,1]]+[[{'VarLower':i},1] for i in sorted(set(ee[1])-set(wanted[1]))];check=prove(r,'Le',wanted,terms,wanted[0]-ee[0])
        elif rn not in b['row_index']:check=prove(r,kind,wanted,constant=wanted[0])
        else:check=prove(r,kind,wanted,[[row_ref(b,rn),1]])
        reverse[rn]=check
    cert,counts=zero_extension(a,b,f,zeros,forward,r,reverse);counts.update(binary_rounding_seeds=48,cardinality_equalities=78,partition_variables=101656,partition_cardinality=350,dense_replacements=8,subset_deletions=120);return cert,counts


if __name__=='__main__':execute(56,prepare,__file__)
