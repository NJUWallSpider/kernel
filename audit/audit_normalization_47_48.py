#!/usr/bin/env python3
"""Read-only exact full-field and incidence audit; no RPX acceptance authority."""
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path
import hashlib, json, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_affine import parse_mps
from prepare_test40 import expression,plus,substitute,expr_json


def identity(path):
    data=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}


def summary(path,m):
    return {**identity(path),'variables':len(m['vars']),'rows':len(m['rows']),'integer_variables':sum(v['integer'] for v in m['vars']),'row_terms':sum(len(r['terms']) for r in m['rows']),'objective_terms':len(m['objective'][1]),'objective_constant':str(m['objective'][0])}


def bound_range(e,m):
    lo=hi=e[0]
    for i,c in e[1].items():
        v=m['vars'][i];a,b=(v['lower'],v['upper']) if c>0 else (v['upper'],v['lower'])
        lo=None if lo is None or a is None else lo+c*a
        hi=None if hi is None or b is None else hi+c*b
    return lo,hi


def inspect47(a,b,h):
    binary={i for i,v in enumerate(a['vars']) if v['integer']};continuous=set(range(len(a['vars'])))-binary
    assert len(binary)==150 and len(continuous)==1
    y=next(iter(continuous));assert a['vars'][y]['name']=='x151' and a['vars'][y]['lower']==0 and a['vars'][y]['upper']==10**12
    assert all(a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1 for i in binary)
    card=a['rows'][a['row_index'][h['cardinality_row']]];limit=h['cardinality_limit']
    assert card['sense']=='L' and card['rhs']==limit==20 and card['terms']==dict.fromkeys(binary,F(1))
    covers=[a['rows'][a['row_index'][r]] for r in h['covering_rows']]
    assert len(covers)==12 and set(a['row_index'])==set(h['covering_rows'])|{card['name']}
    assert all(r['sense']=='G' and r['terms'][y]==1 and all(c>=0 for c in r['terms'].values()) for r in covers)
    assert a['objective']==expression(0,{**dict.fromkeys(binary,F('0.00001')),y:F(1)})
    removed={a['var_index'][v] for v in h['removed_binary_variables']};retained=binary-removed
    assert len(removed)==31 and set(h['retained_dominator_witnesses'])==set(h['removed_binary_variables'])
    witness={};checks=0
    for v,names in h['retained_dominator_witnesses'].items():
        i=a['var_index'][v];ids=[a['var_index'][w] for w in names]
        assert len(ids)==len(set(ids))==20 and set(ids)<=retained
        for j in ids:
            for row in covers:assert row['terms'].get(j,F(0))>=row['terms'].get(i,F(0));checks+=1
        witness[i]=ids
    groups={name:[a['var_index'][v] for v in names] for name,names in h['aggregated_binary_groups'].items()}
    members=[i for ids in groups.values() for i in ids];assert len(members)==len(set(members))==4 and set(members)<=retained
    for ids in groups.values():
        assert len(ids)==2
        assert all(r['terms'].get(ids[0],0)==r['terms'].get(ids[1],0) for r in a['rows'])
        assert a['objective'][1][ids[0]]==a['objective'][1][ids[1]]
    expected_names={v['name'] for i,v in enumerate(a['vars']) if i not in removed|set(members)}|set(groups)
    assert set(b['var_index'])==expected_names and set(b['row_index'])==set(a['row_index'])
    old_to_new={i:b['var_index'][v['name']] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']}
    for name,ids in groups.items():old_to_new[ids[0]]=b['var_index'][name]
    for row in a['rows']:
        expected={old_to_new[i]:c for i,c in row['terms'].items() if i in old_to_new}
        actual=b['rows'][b['row_index'][row['name']]];assert (actual['sense'],actual['rhs'],actual['terms'])==(row['sense'],row['rhs'],expected)
    assert b['objective']==expression(a['objective'][0],{old_to_new[i]:c for i,c in a['objective'][1].items() if i in old_to_new})
    for v in b['vars']:
        assert v==({'name':v['name'],'integer':True,'lower':F(0),'upper':F(2)} if v['name'] in groups else a['vars'][a['var_index'][v['name']]])
    return {'all_actual_target_fields':'ALL_FIELDS_EQUAL','coefficient_dominance_checks':checks,'removed_source_variables':sorted(removed),'retained_dominators':witness,'aggregate_groups':{b['var_index'][k]:v for k,v in groups.items()},'cardinality_row':a['row_index'][card['name']],'cover_rows':[a['row_index'][r['name']] for r in covers],'preserved_source_continuous_coordinate':y,'required_contract':'Both integer directions Objective Equal; preserve y and total selected-binary count. No named-binary feasible-set equality or LP claim.','existing_rule_path':'31 IntervalLift prefix-AND exchange stages; exact affine aggregation; reverse MenuLift splits two integer [0,2] counts.'}


def inspect48(a,b,h):
    copies=h['copy_substitutions'];fixed=h['fixed_zero_representatives'];children=[];block_rows=set();links=set();mandatory=[];selectors=set()
    for name,root in copies.items():
        i,j=a['var_index'][name],a['var_index'][root]
        matches=[r for r in a['rows'] if r['sense']=='E' and r['rhs']==0 and r['terms']=={i:F(1),j:F(-1)}]
        assert len(matches)==1 and matches[0]['name'] in h['explicit_copy_equality_rows']
    for name,w in fixed.items():
        i=a['var_index'][name]
        if w['kind']=='original_bound_or_equality':
            assert any(a['vars'][a['var_index'][v]]['lower']==a['vars'][a['var_index'][v]]['upper']==0 and copies.get(v,v)==name for v in w['original_fixed'])
        else:
            assert w['kind']=='zero_parent' and w['parent'] in fixed
            r=a['rows'][a['row_index'][w['implication_row']]];j=a['var_index'][w['parent']]
            assert r['sense']=='L' and r['rhs']==0 and r['terms']=={i:F(1),j:F(-1)} and a['vars'][i]['lower']==0
    incidence=defaultdict(set)
    for row in a['rows']:
        for i in row['terms']:incidence[i].add(row['name'])
    objective_row=a['rows'][a['row_index']['R0002107']]
    deficit_row=a['rows'][a['row_index']['R0001936']]
    sorted_blocks=[];unsorted=0
    for block in h['local_block_certificates']:
        row=a['rows'][a['row_index'][block['row']]];assert row['name'] not in block_rows;block_rows.add(row['name'])
        assert row['sense']=='L' and row['rhs']==1 and all(c==1 for c in row['terms'].values())
        options=[];childids=[]
        for c in block['optional_children']:
            i=a['var_index'][c['column']];y=a['var_index'][c['selector']];children.append(i);childids.append(i);selectors.add(y)
            link=a['rows'][a['row_index'][c['link_row']]];links.add(link['name'])
            assert link['sense']=='L' and link['rhs']==0 and link['terms']=={i:F(1),y:F(-1)}
            assert incidence[i]=={row['name'],link['name'],'R0001936','R0002107'}
            cost=-objective_row['terms'][i]-1000;assert cost==F(c['objective_coefficient_after_deficit_elimination'])
            assert c['fixed_zero']==(c['column'] in fixed)
            options.append({'source_child':i,'source_selector':y,'link_row':a['row_index'][link['name']],'cost':str(cost),'fixed_zero':c['fixed_zero']})
        assert len(options)==3 and sorted(F(o['cost']) for o in options)==[F(-999),F(-998),F(-997)]
        remaining=set(row['terms'])-set(childids);assert all(a['vars'][i]['name'] in copies for i in remaining)
        mandatory.extend(remaining);roots=[copies[a['vars'][i]['name']] for i in remaining];selectors.update(a['var_index'][name] for name in roots)
        assert Counter(roots)==Counter(block['mandatory_selectors'])
        ordered=sorted(options,key=lambda x:F(x['cost']));unsorted+=ordered!=options
        sorted_blocks.append({'source_row':a['row_index'][row['name']],'children_by_cost':ordered,'mandatory_selectors':[a['var_index'][name] for name in block['mandatory_selectors']]})
    assert len(children)==len(set(children))==1425 and len(mandatory)==len(set(mandatory))==170
    assert set(mandatory)=={a['var_index'][name] for name in copies}
    binary={i for i,v in enumerate(a['vars']) if v['integer']};selectors=binary-set(children)-set(mandatory)
    assert len(selectors)==150 and all(a['vars'][i]['lower']==0 and a['vars'][i]['upper'] in (0,1) for i in binary)
    d=a['var_index']['C0001747'];z=a['var_index']['C0001746'];assert a['objective']==expression(0,{z:F(1)})
    assert deficit_row['sense']=='E' and deficit_row['rhs']==475 and deficit_row['terms']=={d:F(1),**dict.fromkeys(children,F(1))}
    assert objective_row['sense']=='E' and objective_row['rhs']==0 and objective_row['terms'][z]==1 and objective_row['terms'][d]==-1000
    assert incidence[d]=={'R0001936','R0002107'} and incidence[z]=={'R0002107'}
    for i in (d,z):assert a['vars'][i]['lower'] is None and a['vars'][i]['upper'] is None and not a['vars'][i]['integer']
    covered=block_rows|links|set(h['explicit_copy_equality_rows'])|{'R0001936','R0002107'}
    remaining=[r for r in a['rows'] if r['name'] not in covered]
    onehot=[r for r in remaining if r['sense']=='E'];capacity=[r for r in remaining if r['sense']=='L']
    assert len(onehot)==30 and len(capacity)==5 and len(covered)+len(remaining)==len(a['rows'])
    assert all(r['rhs']==1 and len(r['terms'])==5 and all(c==1 for c in r['terms'].values()) for r in onehot)
    assert Counter(i for r in onehot for i in r['terms'])==Counter(dict.fromkeys(selectors,1))
    assert all(r['rhs']==6 and len(r['terms'])==30 and all(c==1 for c in r['terms'].values()) for r in capacity)
    assert Counter(i for r in capacity for i in r['terms'])==Counter(dict.fromkeys(selectors,1))
    def map_name(name):
        name=copies.get(name,name)
        return expression() if name in fixed else expression(0,{b['var_index'][name]:F(1)})
    mapping=[]
    for v in a['vars']:
        if v['name']=='C0001747':
            e=expression(475)
            for i in children:e=plus(e,map_name(a['vars'][i]['name']),-1)
            mapping.append(e)
        else:mapping.append(map_name(v['name']))
    assert set(b['var_index'])==set(a['var_index'])-set(h['removed_original_columns'])
    assert set(b['row_index'])==set(a['row_index'])-set(h['removed_rows'])
    relax=set(h['integrality_removed_from_surviving_columns']);assert len(relax)==1357
    for v in b['vars']:
        expected=dict(a['vars'][a['var_index'][v['name']]])
        if v['name'] in relax:expected['integer']=False
        assert v==expected
    for i,v in enumerate(a['vars']):
        lo,hi=bound_range(mapping[i],b)
        assert v['lower'] is None or (lo is not None and lo>=v['lower'])
        assert v['upper'] is None or (hi is not None and hi<=v['upper'])
    for r in a['rows']:
        e=substitute(expression(0,r['terms']),mapping)
        if r['name'] in b['row_index']:
            actual=b['rows'][b['row_index'][r['name']]];assert (actual['sense'],actual['rhs'],actual['terms'])==(r['sense'],r['rhs']-e[0],e[1])
        else:
            lo,hi=bound_range(e,b)
            assert (r['sense']=='L' and hi is not None and hi<=r['rhs']) or (r['sense']=='G' and lo is not None and lo>=r['rhs']) or (r['sense']=='E' and lo==hi==r['rhs'])
    assert substitute(a['objective'],mapping)==b['objective']
    return {'all_actual_target_fields':'ALL_FIELDS_EQUAL','source_rows_accounted':len(a['rows']),'source_bounds_checked':len(a['vars']),'conditional_blocks':len(sorted_blocks),'complete_child_incidence_checks':len(children),'audit_child_arrays_not_cost_sorted':unsorted,'blocks':sorted_blocks,'source_selectors':sorted(selectors),'target_to_source_lp_lift':[expr_json(e) for e in mapping],'required_contract':'MI forward Equal, reverse NonIncreasing, preserve all 150 selectors (144 retained plus six fixed zero); LP both directions Equal with complete affine inverse identities.','existing_rule_path':'One simultaneous IntervalLift batch of priority Boolean ANDs, existing local Cases for integrality/packing/cost; complete original d/objective reconstruction. No new trusted rule.'}


def main():
    result=[]
    for case,inspect in [(47,inspect47),(48,inspect48)]:
        run=Path(f'/Users/bhz/Code/reform_test/runs/test{case}-nomf-B1');source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json'
        a,b=parse_mps(source),parse_mps(target);h=json.loads(hint.read_text());evidence=inspect(a,b,h)
        item={'case_id':f'test{case}','status':'STRUCTURALLY_AUDITED_NOT_CERTIFIED','source':summary(source,a),'target':summary(target,b),'hints':identity(hint),'report':identity(run/'output/report.md'),'missing_material':[],'remaining_proof_obligations':['Execute full requested RPX certificate and targeted attacks'],'evidence':evidence}
        receipt=ROOT/f'cases/test{case}/preparation.json'
        if receipt.exists():
            saved=json.loads(receipt.read_text())
            if saved.get('status')=='VERIFIED':
                assert saved['source']['sha256']==identity(source)['sha256'] and saved['target']['sha256']==identity(target)['sha256']
                for name,data in saved['artifacts'].items():assert identity(receipt.parent/name)['sha256']==data['sha256']
                assert identity(receipt.parent/'proof.rpa')['sha256']==saved['rpa_sha256']
                assert all(check['result']['status']=='INVALID' for check in saved['negative_checks']) and len(saved['negative_checks'])>=5
                checked=json.loads(saved['kernel_runs'][-1]['stdout']);assert checked['status']=='VERIFIED'
                item.update(status='VERIFIED',remaining_proof_obligations=[],certificate_evidence={'receipt':identity(receipt),'full_kernel_result':checked,'negative_checks':len(saved['negative_checks'])})
        result.append(item)
    destination=ROOT/'audit/normalization_47_48_inventory.json';destination.write_text(json.dumps({'trust':'Untrusted exact preparation evidence; actual kernel acceptance remains required.','cases':result},indent=2)+'\n')
    print(json.dumps({'status':'PASS_FULL_FIELD_AND_INCIDENCE_AUDIT','cases':[{k:v for k,v in c.items() if k!='evidence'}|{'binding':c['evidence']['all_actual_target_fields']} for c in result]},indent=2))


if __name__=='__main__':main()
