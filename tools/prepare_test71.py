#!/usr/bin/env python3
"""Prepare complete test71 RPA3 and independent exact input-witness evidence.

This script does not certify a Plotkin theorem. Required kernel theorem, complete
point/separation checks, and objective-bound obligations must execute before the
case can be marked VERIFIED. No source corpus files are modified.
"""
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,sha


def evaluate(model,point,integer):
    assert len(point)==len(model['vars']);violations=[]
    for i,(v,x) in enumerate(zip(model['vars'],point)):
        if v['lower'] is not None and x<v['lower']:violations.append({'kind':'VarLower','index':i,'residual':str(v['lower']-x)})
        if v['upper'] is not None and x>v['upper']:violations.append({'kind':'VarUpper','index':i,'residual':str(x-v['upper'])})
        if integer and v['integer'] and x.denominator!=1:violations.append({'kind':'VarInt','index':i})
    for i,row in enumerate(model['rows']):
        activity=sum(c*point[j] for j,c in row['terms'].items());rhs=row['rhs']
        if row['sense'] in ('L','E') and activity>rhs:violations.append({'kind':'RowUpper','index':i,'residual':str(activity-rhs)})
        if row['sense'] in ('G','E') and activity<rhs:violations.append({'kind':'RowLower','index':i,'residual':str(rhs-activity)})
    objective=model['objective'][0]+sum(c*point[i] for i,c in model['objective'][1].items())
    return {'objective':str(objective),'violations':violations,'checked_variables':len(model['vars']),'checked_rows':len(model['rows'])}


def certificate(a,b,labels,integer,uniform,new_index):
    """Every obligation binds to actual parsed model indices, including all rows."""
    projection=[[i,i] for i in range(len(a['vars']))]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':1,'input_objective_lower':'-12'},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':0},
            {'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':projection,'inverse':None,'input_objective_lower':'-12'}]
    mapping=[expr_json(expression(0,{i:1})) for i in range(len(a['vars']))]
    blocks=[]
    for claim in claims:
        inp,out=(b,a) if claim['reverse'] else (a,b)
        steps=[];checks=[]
        if not claim['reverse']:
            steps.append({'Plotkin':{'id':0,'bits':11,'distance':6,'variables':[[i,label] for i,label in enumerate(labels)],'cliques':[row_ref(a,r['name']) for r in a['rows']]}})
        for i,v in enumerate(out['vars']):
            assert v==inp['vars'][i]
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if claim['output_integers'] and v['integer']:checks.append({'VarInt':i})
        for row in out['rows']:
            if row['name'] in inp['row_index']:
                assert row==inp['rows'][inp['row_index'][row['name']]]
                checks.append(row_ref(inp,row['name']))
            else:
                assert not claim['reverse'] and b['row_index'][row['name']]==new_index
                assert row['sense']=='L' and row['rhs']==12 and row['terms']=={i:F(1) for i in range(len(a['vars']))}
                checks.append({'Local':0})
        assert a['objective']==b['objective'];checks.append('Exact')
        checks+=['Exact']*len(projection)
        if claim['inverse'] is not None:checks+=['Exact']*len(inp['vars'])
        if 'input_objective_lower' in claim:checks.append({'RowUpper':new_index} if claim['reverse'] else {'Local':0})
        blocks.append({'steps':steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    points=[{'claim':{'Feasible':{'target':False,'integers':True,'objective':'-12'}},'values':[str(x) for x in integer]},
            {'claim':{'Feasible':{'target':True,'integers':False,'objective':'-12'}},'values':[str(x) for x in integer]},
            {'claim':{'Strictness':{'inclusion_claim':2}},'values':[str(x) for x in uniform]}]
    return {'claims':claims,'blocks':blocks,'points':points}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test71-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test71'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';geometry_path=run/'output/geometry_certificate.json';geometry=json.loads(geometry_path.read_text());a=parse_mps(source);b=parse_mps(target)
    assert len(a['vars'])==len(b['vars'])==1024 and len(a['rows'])==1024 and len(b['rows'])==1025
    assert a['var_index']==b['var_index'] and a['vars']==b['vars'] and a['objective']==b['objective']
    assert a['objective']==expression(0,{i:-1 for i in range(1024)})
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in a['vars'])
    for row in a['rows']:assert row==b['rows'][b['row_index'][row['name']]]
    new=[r for r in b['rows'] if r['name'] not in a['row_index']];assert len(new)==1
    assert new[0]['sense']=='L' and new[0]['rhs']==12 and new[0]['terms']=={i:F(1) for i in range(1024)}
    new_index=b['row_index'][new[0]['name']]
    assert set(geometry['variables'])==set(a['var_index'])
    labels=[geometry['variables'][v['name']] for v in a['vars']]
    assert len(set(labels))==1024 and all(0<=v<2**11 for v in labels)
    incidence=[set() for _ in range(1024)]
    for i,row in enumerate(a['rows']):
        assert row['sense']=='L' and row['rhs']==1 and len(row['terms'])==56 and all(c==1 for c in row['terms'].values())
        for j in row['terms']:incidence[j].add(i)
    histogram=Counter();bad_pairs=0
    for i in range(1024):
        for j in range(i+1,1024):
            d=bin(labels[i]^labels[j]).count('1');histogram[d]+=1
            if d<6:assert incidence[i]&incidence[j];bad_pairs+=1
    uniform=[F(1,56)]*1024;chosen=set(geometry['optimal_binary_witness']);assert len(chosen)==12 and chosen<=set(a['var_index'])
    integer=[F(int(v['name'] in chosen)) for v in a['vars']]
    evidence={'source_relaxed_uniform':evaluate(a,uniform,False),'target_relaxed_uniform':evaluate(b,uniform,False),'source_integer_optimal':evaluate(a,integer,True),'target_integer_optimal':evaluate(b,integer,True),'target_relaxed_optimal':evaluate(b,integer,False)}
    assert evidence['source_relaxed_uniform']['violations']==[] and evidence['source_relaxed_uniform']['objective']=='-128/7'
    assert evidence['target_relaxed_uniform']['violations']==[{'kind':'RowUpper','index':new_index,'residual':'44/7'}]
    for name in ['source_integer_optimal','target_integer_optimal','target_relaxed_optimal']:assert evidence[name]['violations']==[] and evidence[name]['objective']=='-12'
    witness={'kind':'plotkin_cardinality','bits':11,'distance':6,'variables':[[i,label] for i,label in enumerate(labels)],'clique_rows':[{'RowUpper':i} for i in range(1024)],'expected_conclusion':{'constant':'-12','terms':[[i,'1'] for i in range(1024)]}}
    points={'schema':'test71-exact-point-evidence-v1','source_relaxed':{'coordinates':[str(x) for x in uniform],'integer':False,'objective':'-128/7'},'source_integer':{'coordinates':[str(x) for x in integer],'integer':True,'objective':'-12'},'target_integer':{'coordinates':[str(x) for x in integer],'integer':True,'objective':'-12'},'target_relaxed':{'coordinates':[str(x) for x in integer],'integer':False,'objective':'-12'},'separation':{'source_point':'source_relaxed','map':'identity','target_violation':{'RowUpper':new_index},'positive_residual':'44/7'},'lower_bounds':{'source_integer':{'value':'-12','fact':'plotkin_cardinality'},'target_relaxed':{'value':'-12','fact':{'RowUpper':new_index}}},'trust':'These are input witnesses. Kernel acceptance must re-evaluate complete model constraints/domains/objectives and validate the universal lower bounds.'}
    (out/'plotkin_witness.json').write_text(json.dumps(witness,indent=2)+'\n');(out/'points.json').write_text(json.dumps(points,indent=2)+'\n');(out/'independent_exact_checks.json').write_text(json.dumps({'status':'INDEPENDENT_CHECKED_NOT_KERNEL_CERTIFIED','checks':evidence,'hamming_distance_pair_histogram':dict(sorted(histogram.items())),'all_pairs_examined':sum(histogram.values()),'low_distance_pairs_with_actual_common_row':bad_pairs},indent=2)+'\n')
    cert=certificate(a,b,labels,integer,uniform,new_index)
    rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 3\n'+json.dumps(cert,indent=2)+'\n')
    request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},indent=2)+'\n')
    metadata={'case_id':'test71','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'geometry':{'path':str(geometry_path),'sha256':sha(geometry_path)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Same complete binary feasible set and objective, identity bijection both directions; strictly stronger LP relaxation via full target-to-source LP containment and exact separating point; original and target integer optimum -12 and target LP optimum -12 via universal lower bounds and feasible objective witnesses.','counts':{'source_variables':1024,'target_variables':1024,'source_rows':1024,'target_rows':1025,'all_label_pairs':sum(histogram.values()),'low_distance_pairs':bad_pairs,'claims':len(cert['claims']),'point_claims':len(cert['points']),'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]},'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();metadata['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);metadata['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                metadata['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        assert json.loads(metadata['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';metadata['status']='VERIFIED';metadata['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        metadata['negative_checks']=[]
        for name,reason in [('missing_cliques','Removes all actual close-pair at-most-one premises from the universal Plotkin proof.'),('duplicate_label','Changes pair distances so an actual close pair lacks a checked at-most-one premise.'),('false_strictness','Uses a point feasible in both LP models as the strict-separation witness.'),('wrong_optimum_point','Deletes one selected coordinate from a feasible point, changing its exact objective from -12 to -11.'),('missing_objective_bound','Omits the final universally quantified source objective-bound obligation.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_cliques':bad['blocks'][0]['steps'][0]['Plotkin']['cliques']=[]
            elif name=='duplicate_label':bad['blocks'][0]['steps'][0]['Plotkin']['variables'][1][1]=labels[0]
            elif name=='false_strictness':bad['points'][2]['values']=[str(x) for x in integer]
            elif name=='wrong_optimum_point':bad['points'][0]['values'][integer.index(F(1))]='0'
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 3\n'+json.dumps(bad,indent=2)+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            metadata['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({k:metadata[k] for k in ['case_id','status','counts','preparation_seconds']},indent=2))

if __name__=='__main__':main()
