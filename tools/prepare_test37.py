#!/usr/bin/env python3
"""Full actual test37 integer inverse and strict LP projection certificate.

Audit entries locate rows/paths only. Every numerical bound is recomputed from
actual Fraction model coefficients, and all proof expressions are checked before
assembly. Kernel acceptance checks the complete actual models independently.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, subprocess, sys, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, substitute, sha
from prepare_test48 import Proof, emit_checks
from prepare_test44 import le_cases
from prepare_test88 import fix_binary


def round_fact(p, le, integer):
    e,z=p.refexpr(le),p.refexpr(integer)
    assert p.kind(le)=='Le' and p.kind(integer)=='Int' and e[1]==z[1]
    d=e[0]-z[0];ceil=-((-d.numerator)//d.denominator)
    result=expression(z[0]+ceil,z[1]);i=p.alloc()
    p.steps.append({'Round':{'id':i,'le':le,'integer':integer}});p.facts[i]=('Le',result)
    return {'Local':i}


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
    claims=[]
    for reverse_flag,integer,inverse in [(False,True,1),(True,True,0),(True,False,None)]:
        projection=[[i,a['var_index'][v['name']]] for i,v in enumerate(b['vars'])]
        if not reverse_flag:projection=[[j,i] for i,j in projection]
        claims.append({'reverse':reverse_flag,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse})
    f=Proof(a);fixed={};impossible=[]
    for hint in h['impossible_selectors']:
        row=a['rows'][a['row_index'][hint['row']]];y,M,A=activity(a,row)
        assert a['vars'][y]['name']==hint['selector'];U,upper=box(a,A,True);L,_=box(a,A,False)
        bound=(U-row['rhs'])/M;assert 0<bound<1
        le=f.lin('Le',[[row_ref(a,row['name']),1/M]]+[[r,c/M] for r,c in upper],expression(-bound,{y:1}))
        zero=round_fact(f,le,{'VarInt':y});assert f.refexpr(zero)==expression(0,{y:1})
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
        rows[oi]=le_cases(f,wanted,y,branch0,branch1)
        lower_bounds.append({'row':name,'selector':a['vars'][y]['name'],'old_M':str(M),'new_M':str(newM),'derived_lower':str(L),'new_rhs':str(target['rhs']),'lower_slack':str(L-target['rhs'])})
    blocks=[emit_checks(f,b,forward,claims[0],rows=rows,inverse=reverse)]
    for claim in claims[1:]:
        p=Proof(b);backrows={}
        for i,row in enumerate(a['rows']):
            name=row['name'];wanted=substitute(row_fact(row,next(iter(row_ref(a,name)))),reverse)
            if name not in b['row_index']:
                backrows[i]=p.prove('Le',wanted)
            elif name in h['tightened_rows']:
                y,M,_=activity(a,row);yi=b['var_index'][a['vars'][y]['name']];target=b['rows'][b['row_index'][name]];newM=-target['terms'][yi]
                backrows[i]=p.lin('Le',[[row_ref(b,name),F(1)],[{'VarUpper':yi},M-newM]],wanted)
            else:
                ref=row_ref(b,name);assert p.refexpr(ref)==wanted;backrows[i]=ref
        blocks.append(emit_checks(p,a,reverse,claim,rows=backrows,inverse=forward if claim['inverse'] is not None else None))
    assert set(h['relaxation_witness'])==set(a['var_index'])
    point=[F(h['relaxation_witness'][v['name']]) for v in a['vars']]
    def eval_expr(e,point):return e[0]+sum(c*point[i] for i,c in e[1].items())
    for i,v in enumerate(a['vars']):
        assert v['lower'] is None or point[i]>=v['lower'];assert v['upper'] is None or point[i]<=v['upper']
    for row in a['rows']:
        val=eval_expr(row_fact(row,next(iter(row_ref(a,row['name'])))),point)
        assert val==0 if row['sense']=='E' else val<=0
    target_point=[point[a['var_index'][v['name']]] for v in b['vars']]
    separating=b['rows'][b['row_index'][h['witness_violation']['row']]]
    violation=eval_expr(row_fact(separating,'RowLower'),target_point);assert violation>0
    terms=[[row_ref(b,separating['name']),'1']]
    for i,c in separating['terms'].items():terms.append([{'RowEq':len(b['rows'])+i},str(c)])
    refutation={'steps':[{'Lin':{'id':0,'kind':'Le','constant':'0','terms':terms}}],'end':{'Absurd':{'fact':{'Local':0}}}}
    points=[{'claim':{'FiberStrictness':{'inclusion_claim':2}},'values':[str(v) for v in point],'refutation':refutation}]
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
            'claims':3,'point_claims':1,'fixed_coordinates':len(fixed),'direct_paths':len(direct),'path_bounds':len(paths),'tightened_rows':len(lower_bounds),
            'unchanged_asymmetric_rows':len(h['unchanged_unbalanced_rows']),'case_splits':len(lower_bounds),'fiber_equalities':len(b['vars']),
            'separating_row':separating['name'],'fiber_contradiction':str(violation),
            'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'root_steps_by_claim':[len(x['steps']) for x in blocks]}
    evidence={'status':'ALL_ACTUAL_FIELDS_AND_PROOF_EXPRESSIONS_CHECKED','source_sha256':h['original_sha256'],'target_sha256':h['final_sha256'],
              'impossible_selectors':impossible,'direct_bounds':{k:str(v) for k,v in direct_values.items()},'path_bounds':{k:str(v) for k,v in path_values.items()},
              'activity_lower_bounds':lower_bounds,'asymmetric_rows_preserved':h['unchanged_unbalanced_rows'],
              'complete_source_lp_point':[str(v) for v in point],'separating_target_row':separating['name'],'fiber_contradiction':str(violation)}
    return {'claims':claims,'blocks':blocks,'points':points},counts,evidence


def attack(cert,a,b):
    """Exact recipes; each mutation invalidates a specified required check."""
    recipes=[]
    bad=copy.deepcopy(cert);bad['blocks'][0]['steps'][0]['Lin']['terms'][0][1]='1/8400001'
    recipes.append(('wrong_big_m_multiplier','Changes the actual row scaling before fixing a selector.',bad,None))
    bad=copy.deepcopy(cert);case=next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)
    branch=case['left']['steps'][-1]['Lin'];branch['terms'][0][1]='2'
    recipes.append(('wrong_activity_path_scale','Corrupts the certified activity lower bound used in a tightened-row branch.',bad,None))
    bad=copy.deepcopy(cert)
    # Keep caller/certificate agreement, remove inverses so the first arithmetic
    # integer premise itself must reject under the LP input mode.
    for c in bad['claims'][:2]:c['inverse']=None
    bad['claims'][0]['input_integers']=False;bad['claims'][0]['output_integers']=False
    recipes.append(('lp_borrows_integrality','Reuses a source VarInt rounding premise in an LP claim.',bad,{'claims':bad['claims'],'points':[x['claim'] for x in bad['points']]}))
    bad=copy.deepcopy(cert);bad['blocks'][1]['end']['Return']['checks'].pop(len(bad['blocks'][1]['end']['Return']['checks'])//2)
    recipes.append(('missing_middle_obligation','Deletes one complete reverse-model obligation.',bad,None))
    bad=copy.deepcopy(cert);bad['blocks'][1]['end']['Return']['map'][a['var_index']['x20']]=expr_json(expression())
    recipes.append(('wrong_fixed_inverse','Maps the actual fixed x20=1 coordinate to zero.',bad,None))
    bad=copy.deepcopy(cert);bad['points'][0]['values'][a['var_index']['x10']]='0'
    recipes.append(('infeasible_full_separator','Changes the full source LP point so an actual source row fails.',bad,None))
    bad=copy.deepcopy(cert);bad['points'][0]['refutation']['steps'][0]['Lin']['terms'].pop(1)
    recipes.append(('missing_fiber_cancellation','Omits one generated observation equality from the contradiction.',bad,None))
    bad=copy.deepcopy(cert);bad['points'][0]['claim']={'Strictness':{'inclusion_claim':2}}
    bad['points'][0].pop('refutation');req={'claims':bad['claims'],'points':[x['claim'] for x in bad['points']]}
    recipes.append(('false_permutation_strictness','Claims complete-coordinate permutation strictness despite five missing coordinates.',bad,req))
    return recipes


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test37-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test37'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);k=args.kernel.resolve()
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json';h=json.loads(hint.read_text());a,b=parse_mps(source),parse_mps(target)
    assert sha(source)==h['original_sha256'] and sha(target)==h['final_sha256']
    cert,counts,evidence=prepare(a,b,h);rp=out/'proof.rpa';request=out/'request.json'
    rp.write_text('RPA 6\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},indent=2)+'\n')
    (out/'exact_structure.json').write_text(json.dumps(evidence,indent=2)+'\n')
    metadata={'case_id':'test37','status':'PROOF_NOT_COMPLETED','protocol_status':'FROZEN_V8_VERIFIER_RPA6_INPUT','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit_hint':{'path':str(hint),'sha256':sha(hint)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'kernel_binary':{'path':str(k),'sha256':sha(k)},'counts':counts,'preparation_seconds':time.perf_counter()-start,'kernel_runs':[],
              'claims':'Complete retained-coordinate mixed-integer feasible-set and objective equality with both full affine inverse identities; target LP inclusion in source under the fixed-coordinate lift; strict target LP containment under all 317 retained observations via complete source point and target fiber refutation. No LP optimum-gap or integer attainment claimed.'}
    def save():(out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    save()
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);metadata['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr});save()
        if proc.returncode:metadata['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';save();raise SystemExit(proc.stdout+proc.stderr)
    assert json.loads(metadata['kernel_runs'][-1]['stdout'])['status']=='VERIFIED'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'));from lp_parse_sweep import Reader
    for name,model in [('source',a),('target',b)]:assert Reader((out/(name+'.mcm')).read_bytes()).model()==canonical_dict(model)
    metadata['independent_mcm_comparison']='ALL_FIELDS_EQUAL';metadata['status']='VERIFIED';metadata['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json','exact_structure.json']};metadata['negative_checks']=[];save()
    attack_start=time.perf_counter();mutants=out/'negative';mutants.mkdir(exist_ok=True)
    for name,reason,bad,req in attack(cert,a,b):
        text=mutants/(name+'.rpa');binary=mutants/(name+'.rpx');text.write_text('RPA 6\n'+json.dumps(bad,separators=(',',':'))+'\n');request_path=request
        if req is not None:request_path=mutants/(name+'.request.json');request_path.write_text(json.dumps(req,indent=2)+'\n')
        proc=subprocess.run([str(k),'assemble',str(text),str(binary)],capture_output=True,text=True);assert proc.returncode==0,(name,proc.stdout,proc.stderr)
        proc=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request_path)],capture_output=True,text=True);result=json.loads(proc.stdout)
        assert proc.returncode and result['status']=='INVALID',(name,result)
        metadata['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':proc.returncode,'result':result,'rpa_sha256':sha(text),'rpx_sha256':sha(binary),'request_sha256':sha(request_path)})
        save()
    metadata['attack_seconds']=time.perf_counter()-attack_start;save()
    print(json.dumps({'status':metadata['status'],'case':'test37','counts':counts,'negative_checks':len(metadata['negative_checks']),'kernel_result':json.loads(metadata['kernel_runs'][-1]['stdout'])},indent=2))

if __name__=='__main__':main()
