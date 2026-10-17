#!/usr/bin/env python3
"""Actual test37 retained-coordinate integer projection on the native contract.

Audit entries locate rows/paths only. Every numerical bound is recomputed from
actual Fraction model coefficients, and all proof expressions are checked before
assembly. Only the two native MI-OPT directions are emitted; the legacy LP
duplicate, affine projection/inverse pairs and the strictness point claim are
not expressible in the native certificate.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, sys, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, expr_json, row_fact, substitute, sha
from prepare_test48 import emit_checks, rounded
from prepare_native import compile_case, make_proof
from prepare_test88 import fix_binary


def box(model, coefficients, upper):
    """Return exact extremum and nonnegative bound combination for box activity."""
    value=F(0);terms=[]
    for i,c in coefficients.items():
        assert not model['vars'][i]['integer']
        side='upper' if (c>0)==upper else 'lower';v=model['vars'][i][side]
        assert v is not None,('infinite box',model['vars'][i]['name'],side)
        value+=c*v;terms.append([{'VarUpper' if side=='upper' else 'VarLower':i},abs(c)])
    return value,terms


def activity(model,row):
    assert row['sense']=='G'
    integers=[i for i,c in row['terms'].items() if model['vars'][i]['integer']]
    assert len(integers)==1
    y=integers[0];M=-row['terms'][y]
    assert M>0 and model['vars'][y]['lower']==0 and model['vars'][y]['upper']==1
    return y,M,{i:c for i,c in row['terms'].items() if i!=y}


def canonical_dict(model):
    return {'name':model['name'],'vars':[{k:(str(v) if isinstance(v,F) else v) for k,v in x.items()} for x in model['vars']],
            'rows':[{'name':r['name'],'expr':expr_json(expression(0,r['terms'])),
                     'lower':str(r['rhs']) if r['sense'] in ('G','E') else None,
                     'upper':str(r['rhs']) if r['sense'] in ('L','E') else None} for r in model['rows']],
            'objective':expr_json(model['objective'])}


def independent_full_target(a,b,h):
    """Reconstruct every target field from explicitly located actual edits."""
    removed=set(h['removed_variables']);deleted=set(h['removed_rows']);tight=h['tightened_rows']
    assert removed==set(a['var_index'])-set(b['var_index']) and deleted==set(a['row_index'])-set(b['row_index'])
    assert len(removed)==5 and len(deleted)==4 and len(tight)==262
    expected=copy.deepcopy(a);expected['name']=b['name']
    expected['vars']=[copy.deepcopy(v) for v in a['vars'] if v['name'] not in removed]
    expected['var_index']={v['name']:i for i,v in enumerate(expected['vars'])}
    old_new={a['var_index'][name]:i for name,i in expected['var_index'].items()}
    assert all(a['objective'][1].get(a['var_index'][name],0)==0 for name in removed)
    expected['objective']=expression(a['objective'][0],{old_new[i]:c for i,c in a['objective'][1].items()})
    rows=[]
    for source in a['rows']:
        if source['name'] in deleted:continue
        r=copy.deepcopy(source)
        if r['name'] in tight:
            target=b['rows'][b['row_index'][r['name']]];y,M,A=activity(a,r)
            target_y=b['var_index'][a['vars'][y]['name']];newM=-target['terms'][target_y]
            assert 0<=newM<M and target['rhs']+newM==r['rhs']+M
            assert h['tightened_rows'][r['name']]['selector']==a['vars'][y]['name']
            r['terms'][y]=-newM;r['rhs']=target['rhs']
        # Fixed x20 is unused; all other removed coordinates will be proved zero.
        for i in list(r['terms']):
            if a['vars'][i]['name'] in removed:
                assert a['vars'][i]['name']!='x20';del r['terms'][i]
        r['terms']={old_new[i]:c for i,c in r['terms'].items() if c}
        rows.append(r)
    expected['rows']=rows;expected['row_index']={r['name']:i for i,r in enumerate(rows)}
    assert canonical_dict(expected)==canonical_dict(b)
    for name in h['unchanged_unbalanced_rows']:
        row=a['rows'][a['row_index'][name]]
        csum=sum(c for i,c in row['terms'].items() if a['vars'][i]['name'] in h['position_variables'])
        assert csum and name not in tight and name not in deleted
    assert len(h['unchanged_unbalanced_rows'])==12


def prepare(a,b,h):
    independent_full_target(a,b,h)
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression(1 if v['name']=='x20' else 0) for v in a['vars']]
    proof,f,r=make_proof(a,b);fixed={};impossible=[]
    for hint in h['impossible_selectors']:
        row=a['rows'][a['row_index'][hint['row']]];y,M,A=activity(a,row)
        assert a['vars'][y]['name']==hint['selector'];U,upper=box(a,A,True);L,_=box(a,A,False)
        bound=(U-row['rhs'])/M;assert 0<bound<1
        le=f.lin('Le',[[row_ref(a,row['name']),1/M]]+[[r,c/M] for r,c in upper],expression(-bound,{y:1}))
        zero=rounded(f,le,{'VarInt':y});assert f.refexpr(zero)==expression(0,{y:1})
        fixed[y]=f.eqpair(zero,{'VarLower':y});f.add('Eq',fixed[y])
        impossible.append({'selector':hint['selector'],'row':row['name'],'actual_M':str(M),'actual_box_lower':str(L),'actual_box_upper':str(U),'round_upper':str(bound)})
    i=a['var_index']['x20'];assert a['vars'][i]['lower']==a['vars'][i]['upper']==1
    fixed[i]=f.eqpair({'VarUpper':i},{'VarLower':i});f.add('Eq',fixed[i])
    assert set(fixed)==set(a['var_index'][n] for n in h['removed_variables'])
    positions={a['var_index'][n] for n in h['position_variables']}
    direct={};direct_values={}
    for key,hint in h['direct_difference_bounds'].items():
        u,v=[a['var_index'][n] for n in key.split('|')];row=a['rows'][a['row_index'][hint['row']]];y,M,A=activity(a,row)
        pos={i:c for i,c in A.items() if i in positions};c=A[v]
        assert c>0 and pos=={u:-c,v:c}
        horizontal={i:q for i,q in A.items() if i not in positions};H,terms=box(a,horizontal,True)
        D=(H-row['rhs'])/c
        direct[key]=f.lin('Le',[[row_ref(a,row['name']),1/c],[{'VarLower':y},M/c]]+[[ref,q/c] for ref,q in terms],expression(-D,{u:1,v:-1}))
        direct_values[key]=D
    assert len(direct)==72
    paths={};path_values={}
    for key,hint in h['path_difference_bounds'].items():
        u,v=[a['var_index'][n] for n in key.split('|')];D=sum(direct_values[e] for e in hint['edges'])
        paths[key]=f.lin('Le',[[direct[e],F(1)] for e in hint['edges']],expression(-D,{u:1,v:-1}));path_values[key]=D
    assert len(paths)==72
    rows={};lower_bounds=[]
    for oi,target in enumerate(b['rows']):
        name=target['name'];row=a['rows'][a['row_index'][name]];wanted=substitute(row_fact(target,next(iter(row_ref(b,name)))),forward)
        if name not in h['tightened_rows']:
            ref=row_ref(a,name);terms=[[ref,F(1)]]+[[fixed[i],-c] for i,c in f.refexpr(ref)[1].items() if i in fixed]
            rows[oi]=f.lin('Eq' if row['sense']=='E' else 'Le',terms,wanted);continue
        y,M,A=activity(a,row);newM=-target['terms'][b['var_index'][a['vars'][y]['name']]]
        horizontal={i:c for i,c in A.items() if i not in positions};H,terms=box(a,horizontal,False)
        pos={i:c for i,c in A.items() if i in positions};L=H
        if pos:
            assert len(pos)==2
            u=next(i for i,c in pos.items() if c<0);v=next(i for i,c in pos.items() if c>0);c=pos[v];assert pos[u]==-c
            key=a['vars'][u]['name']+'|'+a['vars'][v]['name'];terms.append([paths[key],c]);L-=c*path_values[key]
        lower=f.lin('Le',terms,expression(L,{i:-c for i,c in A.items()}))
        assert target['rhs']<=L and target['rhs']+newM==row['rhs']+M
        def branch0(child,assumption,y=y,newM=newM,L=L,lower=lower,wanted=wanted,rhs=target['rhs']):
            eq=fix_binary(child,y,0,assumption)
            return {'Witness':child.lin('Le',[[lower,F(1)],[eq,newM]],wanted,constant=rhs-L)}
        def branch1(child,assumption,y=y,newM=newM,M=M,row=row,wanted=wanted):
            eq=fix_binary(child,y,1,assumption)
            return {'Witness':child.lin('Le',[[row_ref(a,row['name']),F(1)],[eq,newM-M]],wanted)}
        rows[oi]=f.cases('Le',wanted,expression(0,{y:1}),integer={'VarInt':y},left=branch0,right=branch1)
        lower_bounds.append({'row':name,'selector':a['vars'][y]['name'],'old_M':str(M),'new_M':str(newM),'derived_lower':str(L),'new_rhs':str(target['rhs']),'lower_slack':str(L-target['rhs'])})
    f.finish(forward,emit_checks(f,b,forward,rows=rows))
    backrows={}
    for i,row in enumerate(a['rows']):
        name=row['name'];wanted=substitute(row_fact(row,next(iter(row_ref(a,name)))),reverse)
        if name not in b['row_index']:
            backrows[i]=r.prove('Le',wanted)
        elif name in h['tightened_rows']:
            y,M,_=activity(a,row);yi=b['var_index'][a['vars'][y]['name']];target=b['rows'][b['row_index'][name]];newM=-target['terms'][yi]
            backrows[i]=r.lin('Le',[[row_ref(b,name),F(1)],[{'VarUpper':yi},M-newM]],wanted)
        else:
            ref=row_ref(b,name);assert r.refexpr(ref)==wanted;backrows[i]=ref
    r.finish(reverse,emit_checks(r,a,reverse,rows=backrows))
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
            'fixed_coordinates':len(fixed),'direct_paths':len(direct),'path_bounds':len(paths),'tightened_rows':len(lower_bounds),
            'unchanged_asymmetric_rows':len(h['unchanged_unbalanced_rows']),'case_splits':len(lower_bounds),'directions':2}
    evidence={'status':'ALL_ACTUAL_FIELDS_AND_PROOF_EXPRESSIONS_CHECKED','source_sha256':h['original_sha256'],'target_sha256':h['final_sha256'],
              'impossible_selectors':impossible,'direct_bounds':{k:str(v) for k,v in direct_values.items()},'path_bounds':{k:str(v) for k,v in path_values.items()},
              'activity_lower_bounds':lower_bounds,'asymmetric_rows_preserved':h['unchanged_unbalanced_rows']}
    return proof,counts,evidence


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test37-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test37'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json';h=json.loads(hint.read_text());a,b=parse_mps(source),parse_mps(target)
    assert sha(source)==h['original_sha256'] and sha(target)==h['final_sha256']
    proof,counts,evidence=prepare(a,b,h)
    (out/'exact_structure.json').write_text(json.dumps(evidence,indent=2)+'\n')
    record=compile_case(proof,out,case_id='test37',source=source,target=target,
                        metadata={'protocol_status':'NATIVE_MI_OPT_ONLY',
                                  'audit_hint':{'path':str(hint),'sha256':sha(hint)},
                                  'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
                                  'counts':counts,'preparation_seconds':time.perf_counter()-start,
                                  'claims':'Two native MI-OPT directions: every retained target coordinate, bound and row follows from the actual source rows with fixed selectors, and every original source row, bound and integer coordinate follows from the actual target under the retained-coordinate lift. LP duplicates, projection pairs, inverse identities and the strictness point claim are not emitted.'})
    from lp_parse_sweep import Reader
    for name,model in [('source',a),('target',b)]:assert Reader((out/(name+'.mcm')).read_bytes()).model()==canonical_dict(model)
    record['independent_mcm_comparison']='ALL_FIELDS_EQUAL'
    structure=out/'exact_structure.json'
    record['artifacts']['exact_structure']={'path':str(structure),'bytes':structure.stat().st_size,'sha256':sha(structure)}
    (out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'case_id':record['case_id'],'status':record['status'],'guarantee':record['verification'].get('guarantee'),'counts':counts,'obligations':record['verification']['statistics']['obligations'],'seconds':record['preparation_seconds']},indent=2))

if __name__=='__main__':main()
