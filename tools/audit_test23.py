#!/usr/bin/env python3
"""Independent complete-model audit of test23 interval reconstruction demand.

Produces untrusted indexed witnesses only. Every original block occurrence and
all actual final matrix/domain/objective fields are checked with Fraction.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha


def inspect(a,b,h):
    fixed=set(h['fixed_zero_variables_removed']);pairs=h['pairs'];removed=h['dependent_equality_removed']
    assert fixed=={v['name'] for v in a['vars'] if v['lower']==v['upper']==0}
    pair_names=[p[k] for p in pairs for k in ('v','w','y')];assert len(set(pair_names))==len(pair_names) and not fixed.intersection(pair_names)
    deleted=fixed|{p['w'] for p in pairs};expected_names=set(a['var_index'])-deleted
    assert set(b['var_index'])==expected_names
    fixed_ids={a['var_index'][n] for n in fixed};delete_ids={a['var_index'][n] for n in deleted}
    binary_names={p['y'] for p in pairs};assert binary_names=={v['name'] for v in a['vars'] if v['integer']}
    inequalities=set();expected_rows={};witness=[];old_to_new={a['var_index'][n]:b['var_index'][n] for n in sorted(expected_names,key=a['var_index'].__getitem__)}
    expected_domains={v['name']:v.copy() for v in a['vars'] if v['name'] in expected_names}
    def actual_fact(model,name):return get_fact(model,row_ref(model,name),{})
    for p in pairs:
        v,w,y=(a['var_index'][p[k]] for k in ('v','w','y'));t,yy=(b['var_index'][p[k]] for k in ('v','y'))
        aa,M,bb,c=(F(p[k]) for k in ('a','M','b','c'));assert 0<aa<=M and 0<bb<=c
        assert not a['vars'][v]['integer'] and not a['vars'][w]['integer']
        assert (a['vars'][v]['lower'],a['vars'][v]['upper'])==(0,M)
        assert (a['vars'][w]['lower'],a['vars'][w]['upper'])==(0,c)
        assert (a['vars'][y]['lower'],a['vars'][y]['upper'],a['vars'][y]['integer'])==(0,1,True)
        assert not any(a['objective'][1].get(i,0) for i in (v,w,y))
        assert actual_fact(a,p['rg'])==expression(0,{y:aa,v:-1})
        assert actual_fact(a,p['rl'])==expression(0,{v:1,y:-M})
        assert actual_fact(a,p['sg'])==expression(bb,{y:-bb,w:-1})
        assert actual_fact(a,p['sl'])==expression(-c,{w:1,y:c})
        for key in ('rg','rl','sg','sl'):
            assert p[key] not in inequalities;inequalities.add(p[key])
        expected_rows[p['rg']]={'name':p['rg'],'sense':'G','rhs':-c,'terms':{t:F(1),yy:-(aa+c)}}
        expected_rows[p['rl']]={'name':p['rl'],'sense':'L','rhs':-bb,'terms':{t:F(1),yy:-(M+bb)}}
        expected_domains[p['v']]['lower']=-c
        lower=[expression(0,{yy:aa}),expression(bb,{t:1,yy:-bb})]
        upper=[expression(0,{yy:M}),expression(c,{t:1,yy:-c})]
        proofs=[
            [[{'VarLower':yy},M-aa]],
            [[row_ref(b,p['rg']),F(1)]],
            [[row_ref(b,p['rl']),F(1)]],
            [[{'VarUpper':yy},c-bb]],
        ]
        for k,(lo,hi) in enumerate((lo,hi) for lo in lower for hi in upper):
            got=expression()
            for ref,coef in proofs[k]:got=plus(got,get_fact(b,ref,{}),coef)
            assert got==plus(lo,hi,-1)
        witness.append({'source_v':v,'source_w':w,'source_y':y,'target_t':t,'target_y':yy,
                        'source_rows':[a['row_index'][p[k]] for k in ('rg','rl','sg','sl')],
                        'target_rows':[b['row_index'][p[k]] for k in ('rg','rl')],
                        'parameters':{k:str(F(p[k])) for k in ('a','M','b','c')},
                        'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],
                        'lower_upper_proofs':[[[ref,str(q)] for ref,q in terms] for terms in proofs]})
    eqs=[r for r in a['rows'] if r['sense']=='E'];assert {r['name'] for r in a['rows'] if r['sense']!='E'}==inequalities
    dependency=expression()
    for row in eqs:
        assert row['name'] in h['equality_dependency_weights']
        for p in pairs:
            v,w,y=(a['var_index'][p[k]] for k in ('v','w','y'))
            assert row['terms'].get(v,0)==-row['terms'].get(w,0) and row['terms'].get(y,0)==0
        reduced=expression(-row['rhs'],{old_to_new[i]:coef for i,coef in row['terms'].items() if i not in delete_ids})
        dependency=plus(dependency,reduced,F(h['equality_dependency_weights'][row['name']]))
        if row['name']!=removed:expected_rows[row['name']]={'name':row['name'],'sense':'E','rhs':row['rhs'],'terms':reduced[1]}
    assert set(h['equality_dependency_weights'])=={r['name'] for r in eqs} and h['equality_dependency_weights'][removed]!=0 and dependency==expression()
    assert set(expected_rows)==set(b['row_index']) and all(expected_rows[r['name']]==r for r in b['rows'])
    assert all(expected_domains[v['name']]==v for v in b['vars'])
    assert b['objective']==expression(a['objective'][0],{old_to_new[i]:c for i,c in a['objective'][1].items() if i not in fixed_ids})
    samples=0
    for p in witness:
        aa,M,bb,c=(F(p['parameters'][k]) for k in ('a','M','b','c'))
        for y in [F(0),F(1,4),F(1,2),F(3,4),F(1)]:
            tlo=aa*y-c*(1-y);thi=M*y-bb*(1-y)
            for t in [tlo,(tlo+thi)/2,thi]:
                v=max(aa*y,t+bb*(1-y));w=v-t
                assert aa*y<=v<=M*y and bb*(1-y)<=w<=c*(1-y) and 0<=v<=M and 0<=w<=c
                assert v-w==t
                if y==0:assert v==0
                if y==1:assert w==0
                samples+=1
    return {'pairs':witness,'fixed_zero_source_variables':sorted(fixed_ids),'unchanged_coordinates':[[i,j] for i,j in old_to_new.items() if a['vars'][i]['name'] not in {p['v'] for p in pairs}],
            'dependent_source_equality':a['row_index'][removed],'target_equality_combination':[[b['row_index'][r],str(-F(coef)/F(h['equality_dependency_weights'][removed]))] for r,coef in h['equality_dependency_weights'].items() if r!=removed]},samples


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test23-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test23'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    a=parse_mps(source);b=parse_mps(target);w,samples=inspect(a,b,json.loads(audit.read_text()))
    (out/'interval_witness.json').write_text(json.dumps(w,indent=2)+'\n')
    d={'case_id':'test23','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
       'claims':'Complete integer and LP correspondence under signed differences t=v-w, retaining allbinary and other nonfixed continuous coordinates; all objective values preserved. All2467local reconstructed pairs must coexist in one complete source point. Continuous lifts are not bijective.',
       'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'independent_continuous_intervals':len(w['pairs']),'fixed_zero_variables':len(w['fixed_zero_source_variables']),'unchanged_coordinates':len(w['unchanged_coordinates']),'pairwise_interval_premises':4*len(w['pairs']),'exact_local_lift_samples':samples},
       'independent_checks':'Every actual source inequality belongs to exactly one interval block; all external coupling equality columns are opposite; all source/target model fields match exact transformation; all interval lower/upper pair implications match actual bounds or target rows. This is untrusted independent evidence, not kernel certification.',
       'preparation_seconds':time.perf_counter()-start,'kernel_runs':[],
       'required_kernel_work':['Simultaneous continuous interval extension with every lower-upper implication checked; no integrality condition is required for the new real coordinates.','Explicit affine projection relation t=v-w in both requested directions, in addition to the3359 unchanged coordinates.','Complete output obligations for all24793source variables/10112rows and all5826target variables/5177rows, for both integer and LP directions.']}
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':'test23','status':d['status'],'counts':d['counts'],'seconds':d['preparation_seconds']},indent=2))


if __name__=='__main__':main()
