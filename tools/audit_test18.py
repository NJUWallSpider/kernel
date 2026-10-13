#!/usr/bin/env python3
"""Audit actual test18 noninjective projected LP strictness with exact evidence.

No future V6 schema is assumed. A complete relaxed source point and an explicit
linear contradiction for its target observation fiber are untrusted witnesses.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,expr_json,row_fact,substitute,sha
from prepare_test71 import evaluate


def inspect(a,b,h):
    retained=h['retained_variables'];assert set(retained)==set(b['var_index'])
    assert len(retained)==len(set(retained))
    assert all(v['lower']==0 and v['upper']==1 for v in a['vars'])
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in b['vars'])
    mapping=[None]*len(a['vars']);projection=[];source_rows={};saturation=[];edge_owner={}
    for v in b['vars']:
        name=v['name'];i=a['var_index'][name];j=b['var_index'][name]
        assert a['vars'][i]==v;mapping[i]=expression(0,{j:1});projection.append([j,i])
    for name in h['removed_budget_only_variables']:
        i=a['var_index'][name];assert a['vars'][i]['integer'] and mapping[i] is None;mapping[i]=expression()
    for rowname,hint in h['saturation_certificates'].items():
        row=a['rows'][a['row_index'][rowname]];name=hint['binary_variable'];i=a['var_index'][name]
        assert name in b['var_index'] and row['sense']=='E' and row['rhs']==0
        edges={j:c for j,c in row['terms'].items() if j!=i};degree=len(edges)
        assert degree==hint['incident_edge_count'] and row['terms'][i]==-degree==F(hint['negative_coefficient'])
        assert degree>0 and all(c==1 and not a['vars'][j]['integer'] for j,c in edges.items())
        for j in edges:
            assert j not in edge_owner and mapping[j] is None;edge_owner[j]=i;mapping[j]=expression(0,{b['var_index'][name]:1})
            assert h['eliminated_continuous_substitution'][a['vars'][j]['name']]==name
        source_rows[rowname]=row;saturation.append({'row':a['row_index'][rowname],'binary':i,'edges':list(edges)})
    assert set(h['eliminated_continuous_substitution'])=={a['vars'][i]['name'] for i in edge_owner}=={v['name'] for v in a['vars'] if not v['integer']}
    y_records=[];edge_y={}
    expected_target={}
    for rowname,p in h['packing_rows_before_redundancy_removal'].items():
        y=a['var_index'][p['eliminated_binary']];assert a['vars'][y]['integer'] and mapping[y] is None
        row=a['rows'][a['row_index'][rowname]];assert row['sense']=='E' and row['rhs']==0 and row['terms'][y]==-1
        edges={i:c for i,c in row['terms'].items() if i!=y};assert all(i in edge_owner and c==1 for i,c in edges.items())
        for i in edges:assert i not in edge_y;edge_y[i]=y
        support=[b['var_index'][a['vars'][edge_owner[i]]['name']] for i in edges]
        assert len(support)==len(set(support)) and set(p['support'])=={b['vars'][j]['name'] for j in support}
        mapping[y]=expression(0,{j:1 for j in support})
        assert mapping[y]==expression(0,{b['var_index'][n]:F(c) for n,c in h['eliminated_binary_substitution'][p['eliminated_binary']].items()})
        retained_row=rowname if rowname in b['row_index'] else h['removed_packing_rows_superset_witness'][rowname]
        targetrow=b['rows'][b['row_index'][retained_row]]
        assert targetrow['sense']=='L' and targetrow['rhs']==1 and all(c==1 for c in targetrow['terms'].values()) and set(support)<=set(targetrow['terms'])
        if rowname in b['row_index']:expected_target[rowname]={'name':rowname,'sense':'L','rhs':F(1),'terms':{j:F(1) for j in support}}
        source_rows[rowname]=row;y_records.append({'source_variable':y,'source_row':a['row_index'][rowname],'edges':list(edges),'support':support,'target_superset_row':b['row_index'][retained_row]})
    assert set(edge_owner)==set(edge_y) and all(e is not None for e in mapping)
    budget=h['retained_budget']['row'];old=a['rows'][a['row_index'][budget]];new=b['rows'][b['row_index'][budget]]
    assert old['sense']=='L' and old['rhs']==20 and old['terms']=={a['var_index'][n]:F(1) for n in retained+h['removed_budget_only_variables']}
    source_rows[budget]=old;expected_target[budget]={'name':budget,'sense':'L','rhs':F(20),'terms':{j:F(1) for j in range(len(b['vars']))}}
    assert set(source_rows)==set(a['row_index']) and set(expected_target)==set(b['row_index'])
    assert all(expected_target[r['name']]==r for r in b['rows'])
    for row in a['rows']:
        if row['sense']=='E':assert substitute(row_fact(row,'RowEq'),mapping)==expression()
        else:assert substitute(row_fact(row,'RowUpper'),mapping)==row_fact(new,'RowUpper')
    assert substitute(a['objective'],mapping)==b['objective']
    raw=h['strict_relaxation_strengthening_witness']['original_nonzero_values'];assert set(raw)<=set(a['var_index'])
    point=[F(raw.get(v['name'],'0')) for v in a['vars']];source_check=evaluate(a,point,False);assert not source_check['violations']
    projected=[point[a['var_index'][v['name']]] for v in b['vars']];target_check=evaluate(b,projected,False)
    assert target_check['violations']==[{'kind':'RowUpper','index':b['row_index']['R2035'],'residual':'1/21'}]
    fixings=[expression(-projected[j],{j:1}) for j in range(len(projected))]
    row=b['rows'][b['row_index']['R2035']];contradiction=row_fact(row,'RowUpper')
    for j,c in row['terms'].items():contradiction=plus(contradiction,fixings[j],-c)
    assert contradiction==expression(F(1,21))
    return {'reverse_projection':projection,'reverse_map':[expr_json(e) for e in mapping],'saturation':saturation,'eliminated_y':y_records,
            'source_lp_point':[str(v) for v in point],'projected_target_point':[str(v) for v in projected],
            'fiber_equalities':[expr_json(e) for e in fixings],
            'fiber_contradiction':{'target_premise':{'RowUpper':b['row_index']['R2035']},'observation_multipliers':[[j,str(-c)] for j,c in row['terms'].items()],'conclusion':expr_json(contradiction)},
            'source_check':source_check,'projected_target_check':target_check}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test18-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test18'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    a=parse_mps(source);b=parse_mps(target);w=inspect(a,b,json.loads(audit.read_text()));(out/'projection_witness.json').write_text(json.dumps(w,indent=2)+'\n')
    d={'case_id':'test18','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
       'claims':'Same retained-coordinate integer projection and every objective value; strict containment of the reduced LP in the projected original LP. Projection is not injective because four zero-cost budget-only binaries are removed. No LP objective-bound improvement claimed.',
       'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'saturation_groups':len(w['saturation']),'eliminated_continuous':sum(len(g['edges']) for g in w['saturation']),'eliminated_y':len(w['eliminated_y']),'observed_coordinates':len(w['reverse_projection'])},
       'independent_checks':'Complete actual structure and affine reverse lifting identities, source LP point feasibility, projected actual target violation and exact infeasibility of the observation fiber checked with Fraction. None substitutes for kernel certification.',
       'source_lp_objective':w['source_check']['objective'],'projected_target_objective':w['projected_target_check']['objective'],'target_row_violation':'1/21','preparation_seconds':time.perf_counter()-start,'kernel_runs':[],
       'required_kernel_work':['Complete integer forward saturation proof, integer reverse map, and LP reverse inclusion with the actual1146 retained-coordinate observations.','Complete source LP witness and an actual core proof of empty target fiber after fixing all requested observations, under a defined future point-claim schema.']}
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','source_lp_objective','projected_target_objective','target_row_violation','preparation_seconds']},indent=2))


if __name__=='__main__':main()
