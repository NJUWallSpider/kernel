#!/usr/bin/env python3
"""Read-only full structural audit of the actual test59/60 menu model pairs.

This is an untrusted preparation audit, not a certificate or trusted recognizer.
It reads all actual model fields and never promotes either case to VERIFIED.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import Counter,defaultdict
import json,sys,time
from prepare_affine import parse_mps
from prepare_test40 import expression,expr_json,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'))
from lp_parse_sweep import reference_lp


def lp_model(path):
    m=reference_lp(path);rows=[]
    for r in m['rows']:
        assert r['expr']['constant']=='0'
        lo=None if r['lower'] is None else F(r['lower']);hi=None if r['upper'] is None else F(r['upper'])
        assert lo is None or hi is None or lo==hi
        rows.append({'name':r['name'],'sense':'L' if lo is None else 'G' if hi is None else 'E','rhs':hi if lo is None else lo,'terms':{i:F(c) for i,c in r['expr']['terms']}})
    variables=[{**v,'lower':None if v['lower'] is None else F(v['lower']),'upper':None if v['upper'] is None else F(v['upper'])} for v in m['vars']]
    return {'vars':variables,'var_index':{v['name']:i for i,v in enumerate(variables)},'rows':rows,'row_index':{r['name']:i for i,r in enumerate(rows)},'objective':expression(F(m['objective']['constant']),{i:F(c) for i,c in m['objective']['terms']})}


def inspect(num):
    run=Path(f'/Users/bhz/Code/reform_test/runs/test{num}-nomf-B1');source=run/'input/model.mps';target=run/('output/reformulated.lp' if num==60 else 'output/reformulated.mps');hint=run/'output/audit.json'
    a=parse_mps(source);b=lp_model(target) if num==60 else parse_mps(target);h=json.loads(hint.read_text())
    binaries={i for i,v in enumerate(a['vars']) if v['integer']};aux=set(range(len(a['vars'])))-binaries
    assert all(a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1 for i in binaries)
    incidence=defaultdict(list)
    for ri,r in enumerate(a['rows']):
        for i in r['terms']:incidence[i].append(ri)
    groups={};definitions={};definition_rows=set()
    for i in aux:
        assert len(incidence[i])==1;ri=incidence[i][0];r=a['rows'][ri]
        assert r['sense']=='E' and r['rhs']==0 and r['terms'][i] in (-1,1) and set(r['terms'])-{i}<=binaries
        definitions[i]={'source_row':ri,'expression':expression(0,{j:-q/r['terms'][i] for j,q in r['terms'].items() if j!=i})};definition_rows.add(ri)
    assert len(definition_rows)==len(aux)
    partition=[]
    for ri,r in enumerate(a['rows']):
        if ri in definition_rows:continue
        assert r['sense']=='L' and r['rhs']==1 and set(r['terms'])<=binaries and all(q==1 for q in r['terms'].values())
        groups[r['name']]={'source_row':ri,'options':set(r['terms']),'menus':[]};partition.extend(r['terms'])
    assert len(partition)==len(binaries) and set(partition)==binaries
    assert a['objective'][0]==0 and len(a['objective'][1])==1
    obj_i,objective_multiplier=next(iter(a['objective'][1].items()));assert obj_i in aux and objective_multiplier==1
    assert a['vars'][obj_i]['lower'] is None and a['vars'][obj_i]['upper'] is None
    menus=[];alloptions=[];alltarget=[]
    for index,v in enumerate(h['blocks'] if num==60 else h['menus']):
        names=v['originals_in_index_order'] if num==60 else v['options_by_index'];K=v['N'] if num==60 else v['maximum_index'];assert len(names)==K+1 and K>=0
        group=v['group'] if num==60 else v['group_row'];ys=v['activation'] if num==60 else v['binary'];zs=v['option_index'] if num==60 else v['integer_index']
        y=b['var_index'][ys];z=None if zs is None else b['var_index'][zs];options=[a['var_index'][n] for n in names]
        assert len(set(options))==len(options) and set(options)<=groups[group]['options'] and (K==0)==(z is None)
        assert b['vars'][y]=={'name':ys,'lower':F(0),'upper':F(1),'integer':True}
        if z is not None:assert b['vars'][z]=={'name':zs,'lower':F(0),'upper':F(K),'integer':True}
        alltarget.append(y)
        if z is not None:alltarget.append(z)
        alloptions.extend(options);groups[group]['menus'].append(index)
        menus.append({'maximum_index':K,'target_activation':y,'target_index':z,'source_options':options,'source_group_row':groups[group]['source_row'],'target_link_row':None})
    assert len(set(alloptions))==len(alloptions)==len(binaries) and set(alloptions)==binaries
    assert len(set(alltarget))==len(alltarget)==len(b['vars'])
    projected={};progression_comparisons=0
    for i,d in definitions.items():
        old=d['expression'][1];terms={}
        for menu in menus:
            options=menu['source_options'];K=menu['maximum_index'];base=old.get(options[0],F(0));step=old.get(options[1],F(0))-base if K else F(0)
            for j,var in enumerate(options):assert old.get(var,F(0))==base+j*step;progression_comparisons+=1
            if base:terms[menu['target_activation']]=base
            if step:assert menu['target_index'] is not None;terms[menu['target_index']]=step
        projected[i]=expression(0,terms)
    assert b['objective']==projected[obj_i]
    expected={};resource_witness=[]
    for name,g in groups.items():
        names=h['original_row_to_new_rows'][name] if num==60 else [name];assert len(names)==1
        expected[names[0]]=('L',F(1),{menus[j]['target_activation']:F(1) for j in g['menus']})
        g['target_row']=b['row_index'][names[0]]
    for item in h['eliminated_resource_definitions'] if num==60 else h['projected_row_mapping']:
        i=a['var_index'][item['eliminated_variable']];assert i!=obj_i and definitions[i]['source_row']==a['row_index'][item['original_row']]
        v=a['vars'][i];lower=v['lower'];upper=v['upper'];names=item['new_rows'];indices=[]
        assert (None if item['lower'] is None else F(item['lower']))==lower and (None if item['upper'] is None else F(item['upper']))==upper
        if lower is not None and lower==upper:
            assert len(names)==1;expected[names[0]]=('E',lower,projected[i][1]);indices=[b['row_index'][names[0]]]
        else:
            restrictions=[('G',lower)] if lower is not None else []
            if upper is not None:restrictions.append(('L',upper))
            assert len(names)==len(restrictions)
            for n,(sense,rhs) in zip(names,restrictions):expected[n]=(sense,rhs,projected[i][1]);indices.append(b['row_index'][n])
        resource_witness.append({'source_variable':i,'source_row':definitions[i]['source_row'],'target_rows':indices,'target_expression':expr_json(projected[i])})
    assert {w['source_variable'] for w in resource_witness}==aux-{obj_i}
    remaining={r['name']:r for r in b['rows'] if r['name'] not in expected}
    link_lookup={tuple(sorted(r['terms'].items())):r for r in remaining.values()}
    assert len(link_lookup)==len(remaining)
    for menu in menus:
        K=menu['maximum_index'];z=menu['target_index'];y=menu['target_activation']
        if z is None:continue
        terms={z:F(1),y:F(-K)};row=link_lookup[tuple(sorted(terms.items()))];assert row['sense']=='L' and row['rhs']==0
        expected[row['name']]=('L',F(0),terms);menu['target_link_row']=b['row_index'][row['name']]
    assert set(expected)==set(b['row_index'])
    for row in b['rows']:assert expected[row['name']]==(row['sense'],row['rhs'],row['terms'])
    # Every menu state is enumerated to independently test uniqueness of the
    # (activation,index) observations and the endpoint LP section identities.
    states=0;interpolation=0
    for menu in menus:
        K=menu['maximum_index'];seen={(0,0):[F(0)]*(K+1)}
        for j in range(K+1):
            point=[F(int(q==j)) for q in range(K+1)];key=(sum(point),sum(q*x for q,x in enumerate(point)));assert key not in seen;seen[key]=point
        assert len(seen)==K+2;states+=len(seen)
        for A in [F(0),F(1,3),F(1)]:
            for ratio in [F(0),F(1,2),F(1)]:
                I=A*K*ratio;endpoint=[F(0)]*(K+1)
                if K:endpoint[0]=A-I/K;endpoint[K]=I/K
                else:endpoint[0]=A
                assert all(0<=x<=1 for x in endpoint) and sum(endpoint)==A and sum(j*x for j,x in enumerate(endpoint))==I;interpolation+=1
    return {'case_id':f'test{num}','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit_hint':{'path':str(hint),'sha256':sha(hint)},'counts':{'source_variables':len(a['vars']),'source_rows':len(a['rows']),'target_variables':len(b['vars']),'target_rows':len(b['rows']),'menus':len(menus),'packing_groups':len(groups),'options':len(binaries),'auxiliary_definitions':len(aux),'singleton_menus':sum(m['maximum_index']==0 for m in menus),'maximum_index_histogram':dict(sorted(Counter(m['maximum_index'] for m in menus).items())),'complete_progression_comparisons_including_zeros_and_objective':progression_comparisons,'integer_local_states':states,'lp_interpolation_checks':interpolation},'complete_actual_model_reconstruction':'ALL_FIELDS_EQUAL','menus':menus,'groups':[{'source_row':g['source_row'],'target_row':g['target_row'],'menu_indices':g['menus']} for g in groups.values()],'resources':resource_witness,'objective':{'source_variable':obj_i,'source_definition_row':definitions[obj_i]['source_row'],'target_expression':expr_json(projected[obj_i])},'required_contract':'Objective-preserving integer feasible-set bijection, plus equal LP image in every group-usage, frequency, capacity and objective coordinate. Inactive menus are included. All original choices are distinct integer states even if some resource/cost columns coincide.','trust':'All calculations are untrusted preparation evidence. No theorem or full-model Rust certificate has yet executed for this case.'}


def main():
    root=Path(__file__).resolve().parents[1];start=time.perf_counter();results=[]
    for num in [59,60]:
        data=inspect(num);out=root/f'cases/test{num}';out.mkdir(parents=True,exist_ok=True);(out/'menu_structure.json').write_text(json.dumps(data,indent=2)+'\n');results.append({k:data[k] for k in ['case_id','status','source','target','counts','complete_actual_model_reconstruction','required_contract']})
    report={'status':'STRUCTURAL_AUDIT_NOT_KERNEL_CERTIFICATION','preparer':str(Path(__file__).resolve()),'elapsed_seconds':time.perf_counter()-start,'cases':results};(root/'audit/menu_structure.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
