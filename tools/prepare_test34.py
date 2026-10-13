#!/usr/bin/env python3
"""Actual test34 one-hot weighted aggregation through balanced local Cases."""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse,csv,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder


def forward_tree(p,members,weights):
    if len(members)==1:
        i=members[0];w=weights.get(i,F(0));return {'members':members,'sum':expression(0,{i:1}),'weights':expression(0,{i:w}),'maximum':w,'nonnegative':{'VarLower':i},'integer':{'VarInt':i},'complement':None}
    mid=len(members)//2;left=forward_tree(p,members[:mid],weights);right=forward_tree(p,members[mid:],weights);maximum=max(left['maximum'],right['maximum']);summed=plus(left['sum'],right['sum']);weighted=plus(left['weights'],right['weights']);terms=[[{'VarLower':i},maximum-weights.get(i,F(0))] for i in members if maximum!=weights.get(i,F(0))]
    return {'members':members,'sum':summed,'weights':weighted,'maximum':maximum,'nonnegative':p.lin('Le',[[left['nonnegative'],1],[right['nonnegative'],1]],mul(summed,-1)),'integer':p.lin('Int',[[left['integer'],1],[right['integer'],1]],summed),'complement':p.lin('Le',terms) if terms else None,'left':left,'right':right}


def weighted_zero(p,node,zero):
    terms=[[zero,node['maximum']]]
    if node['complement'] is not None:terms.append([node['complement'],1])
    return p.lin('Le',terms,node['weights'])


def aggregate_cases(p,node,selected,z,individual):
    wanted=plus(node['weights'],expression(0,{z:-1}))
    if 'left' not in node:
        i=node['members'][0];ref=individual.get(i,{'VarLower':z});assert p.refexpr(ref)==wanted;return ref
    left,right=node['left'],node['right'];ident=p.alloc();split=left['sum'];branches=[]
    for side in (0,1):
        assumption=split if side==0 else plus(expression(1),split,-1);child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[assumption]);child.facts=ChainMap({},p.facts);assumption_ref={'Assumption':len(p.assumptions)}
        if side==0:
            zero=child.eqpair(assumption_ref,left['nonnegative']);chosen=child.lin('Eq',[[selected,1],[zero,-1]],plus(right['sum'],expression(-1)));subbound=aggregate_cases(child,right,chosen,z,individual);other=weighted_zero(child,left,zero)
        else:
            upper=child.lin('Le',[[selected,1],[right['nonnegative'],1]],plus(left['sum'],expression(-1)));chosen=child.eqpair(upper,assumption_ref);zero=child.lin('Eq',[[selected,1],[chosen,-1]],right['sum']);subbound=aggregate_cases(child,left,chosen,z,individual);other=weighted_zero(child,right,zero)
        bound=child.lin('Le',[[subbound,1],[other,1]],wanted);branches.append({'steps':child.steps,'end':{'Witness':bound}})
    p.steps.append({'Cases':{'id':ident,'kind':'Le','expression':expr_json(wanted),'split':expr_json(split),'integer':left['integer'],'left':branches[0],'right':branches[1]}});p.facts[ident]=('Le',wanted);return {'Local':ident}


def reverse_tree(p,members,weights):
    if len(members)==1:
        i=members[0];wanted=expression(0,{i:-weights.get(i,F(0))});ref=p.lin('Le',[[{'VarLower':i},weights.get(i,F(0))]],wanted);return {'members':members,'negative':ref,'weights':mul(wanted,-1)}
    mid=len(members)//2;left=reverse_tree(p,members[:mid],weights);right=reverse_tree(p,members[mid:],weights);weighted=plus(left['weights'],right['weights']);return {'members':members,'weights':weighted,'negative':p.lin('Le',[[left['negative'],1],[right['negative'],1]],mul(weighted,-1)),'left':left,'right':right}


def split_upper(p,node,upper,z,result):
    if 'left' not in node:
        result[node['members'][0]]=upper;return
    left,right=node['left'],node['right'];l=p.lin('Le',[[upper,1],[right['negative'],1]],plus(left['weights'],expression(0,{z:-1})));r=p.lin('Le',[[upper,1],[left['negative'],1]],plus(right['weights'],expression(0,{z:-1})));split_upper(p,left,l,z,result);split_upper(p,right,r,z,result)


def prepare(a,b,h,manifest):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(53593,106954,53593,53824)
    assert a['vars']==b['vars'] and a['objective']==b['objective'];z=a['var_index']['z'];assert not a['vars'][z]['integer'] and a['vars'][z]['lower']==0;changes={d['original_row']:d for d in manifest};aggregates={d['row']:d for d in h['aggregates']};assert set(a['row_index'])-set(b['row_index'])==set(changes) and set(b['row_index'])-set(a['row_index'])==set(aggregates)
    individual={};zero_rows=set()
    for rn,d in changes.items():
        ref=row_ref(a,rn);e=row_fact(a['rows'][a['row_index'][rn]],'RowUpper')
        if d['action']=='delete_redundant':assert e==expression(0,{z:-1});zero_rows.add(rn)
        else:
            assert d['action']=='replace_with_group_aggregate';i=a['var_index'][d['variable']];weight=F(d['exact_distance']);assert weight>0 and e==expression(0,{i:weight,z:-1});assert i not in individual;individual[i]=ref
    f=SparseBuilder(a);r=SparseBuilder(b);forward={};reverse={};all_members=set();maximum_depth=0
    for rn,d in aggregates.items():
        onehot=row_ref(a,d['one_hot_row']);g=f.refexpr(onehot);assert g[0]==-1 and len(g[1])==231 and all(c==1 for c in g[1].values());members=sorted(g[1]);assert not all_members&set(members);all_members.update(members)
        for i in members:assert a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
        target=row_fact(b['rows'][b['row_index'][rn]],'RowUpper');assert target[0]==0 and target[1][z]==-1 and set(target[1])-{z}<=set(members);weights={i:c for i,c in target[1].items() if i!=z};assert len(weights)==230 and all(c>0 for c in weights.values())
        for i in members:
            if i in weights:assert f.refexpr(individual[i])==expression(0,{i:weights[i],z:-1});change=changes[a['rows'][individual[i]['RowUpper']]['name']];assert change['replacement_row']==rn and change['assignment_row']==d['one_hot_row']
            else:assert i not in individual
        node=forward_tree(f,members,weights);forward[rn]=aggregate_cases(f,node,onehot,z,individual);assert f.refexpr(forward[rn])==target;maximum_depth=max(maximum_depth,(len(members)-1).bit_length())
        reverse_node=reverse_tree(r,members,weights);split_upper(r,reverse_node,row_ref(b,rn),z,reverse)
    assert len(all_members)==53361 and len(zero_rows)==231
    n=len(a['vars']);mapping=[expr_json(expression(0,{i:1})) for i in range(n)];projection=[[i,i] for i in range(n)];claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);p=r if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for row in out['rows']:
            rn=row['name']
            if not back and rn in forward:check=forward[rn]
            elif back and rn in changes:
                if rn in zero_rows:check={'VarLower':z}
                else:check=reverse[a['var_index'][changes[rn]['variable']]]
                assert p.refexpr(check)==row_fact(row,'RowUpper')
            else:assert row==inp['rows'][inp['row_index'][rn]];check=row_ref(inp,rn)
            checks.append(check)
        checks.append('Exact');checks+=['Exact']*n;inverse=[1,0,None][index]
        if inverse is not None:checks+=['Exact']*n
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    witness=h['verification']['strict_relaxation_witness'];values=[str(F(witness['z'])) if i==z else str(F(witness['assignment_value'])) if i in all_members else str(F(witness['facility_value'])) for i in range(n)];point={'Strictness':{'inclusion_claim':2}}
    return {'claims':claims,'blocks':blocks,'points':[{'claim':point,'values':values}]},{'source_variables':53593,'target_variables':53593,'source_rows':106954,'target_rows':53824,'onehot_groups':231,'exhaustive_choice_leaves':53361,'local_integer_cases':53130,'maximum_case_depth':maximum_depth,'deleted_zero_distance_rows':231,'claims':3,'points':1,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'root_steps_by_claim':[len(x['steps']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test34-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test34'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';manifest=run/'output/row_changes.csv'
    with manifest.open() as file:rows=list(csv.DictReader(file))
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()),rows);rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n')
    d={'case_id':'test34','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'row_manifest':{'path':str(manifest),'sha256':sha(manifest)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete original-coordinate mixed-integer feasible-set equality, exact objective and reciprocal full identity inverse; target LP inclusion and a complete source LP point outside target LP certify strict strengthening. All 231 weighted one-hot aggregations use balanced local integer Cases over all53361 choices, checked zero-sibling contributions, and actual individual rows. Every original row, variable domain and observation is checked; no optimum restriction or objective monotonicity is assumed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_subset_integrality','Weakens an integer subset split to a sign split.'),('missing_zero_weight_premise','Omits a checked nonnegative weighted sibling contribution.'),('missing_reverse_nonnegativity','Omits a nonnegative weighted contribution needed to recover an individual bound.'),('infeasible_strictness_point','Makes the complete source LP witness violate the z lower bound.'),('missing_inverse','Omits a full original-coordinate inverse obligation.')]:
            if name=='missing_subset_integrality':obj=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s);old=obj['integer'];obj['integer']=None;undo=lambda:obj.update(integer=old)
            elif name=='missing_zero_weight_premise':obj=next(s['Lin']['terms'] for s in cert['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le' and any(c!='1' for _,c in s['Lin']['terms']));old=obj.pop();undo=lambda:obj.append(old)
            elif name=='missing_reverse_nonnegativity':obj=next(s['Lin']['terms'] for s in cert['blocks'][1]['steps'] if 'Lin' in s and len(s['Lin']['terms'])==2);old=obj.pop();undo=lambda:obj.append(old)
            elif name=='infeasible_strictness_point':obj=cert['points'][0]['values'];i=next(j for j,v in enumerate(obj) if v not in ('1/231','13/231'));old=obj[i];obj[i]='-1';undo=lambda:obj.__setitem__(i,old)
            else:obj=cert['blocks'][0]['end']['Return']['checks'];old=obj.pop();undo=lambda:obj.append(old)
            path=out/(name+'.rpa');path.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'storage':'Temporary large mutated files removed after hash and outcome recording; deterministic recipe retained.'});path.unlink();encoded.unlink()
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
