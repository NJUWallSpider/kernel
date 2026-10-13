#!/usr/bin/env python3
"""Actual test83 complete integer dominance/recovery maps, with scoped observations."""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,mul,expr_json,row_fact,sha
from prepare_test21 import combine,substitute
from prepare_test70 import SparseBuilder


def prepare(a,b,h):
    assert (len(a['vars']),len(b['vars']),len(a['rows']),len(b['rows']))==(65832,65671,100,100)
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for m in [a,b] for v in m['vars'])
    assert all(r['sense']=='E' and r['rhs']==1 and set(r['terms'].values())=={F(1)} for r in a['rows'])
    support=[set() for _ in a['vars']]
    for ri,r in enumerate(a['rows']):
        for i in r['terms']:support[i].add(ri)
    replacements={a['var_index'][d['removed_variable']]:[a['var_index'][v] for v in d['replacement_variables']] for d in h['dominance_deletions']}
    singletons={a['var_index'][d['variable']]:a['row_index'][d['row']] for d in h['singleton_eliminations']};assert len(replacements)==61 and len(singletons)==100
    savings={}
    for i,js in replacements.items():
        assert len(js)==2 and not (support[js[0]]&support[js[1]]) and support[js[0]]|support[js[1]]==support[i]
        assert not any(j in replacements for j in js);savings[i]=a['objective'][1][i]-sum(a['objective'][1][j] for j in js);assert savings[i]>0
    for i,ri in singletons.items():assert support[i]=={ri}
    assert set(a['var_index'])-set(b['var_index'])=={a['vars'][i]['name'] for i in set(replacements)|set(singletons)}
    aggregates={i:expression(0,{i:1}) for i in range(len(a['vars'])) if i not in replacements}
    for i,js in replacements.items():
        for j in js:aggregates[j][1][i]=F(1)
    forward=[aggregates[a['var_index'][v['name']]] for v in b['vars']];reverse=[]
    for i,v in enumerate(a['vars']):
        if i in replacements:e=expression()
        elif i in singletons:
            ri=singletons[i];r=b['rows'][b['row_index'][a['rows'][ri]['name']]];e=expression(1,{j:-1 for j in r['terms']})
        else:e=expression(0,{b['var_index'][v['name']]:1})
        reverse.append(e)
    p=SparseBuilder(a);lower={};upper={};chosen=defaultdict(list);trace={}
    for j,e in enumerate(forward):
        if len(e[1])==1:i=next(iter(e[1]));lower[j]={'VarLower':i};upper[j]={'VarUpper':i}
        else:
            lower[j]=p.lin('Le',[[{'VarLower':i},1] for i in e[1]],mul(e,-1));common=set.intersection(*(support[i] for i in e[1]));assert common;chosen[min(common,key=lambda ri:(len(a['rows'][ri]['terms']),ri))].append(j)
    def tree(groups):
        if len(groups)==1:return {'leaf':groups[0],'lower':lower[groups[0]]}
        mid=len(groups)//2;l,r=tree(groups[:mid]),tree(groups[mid:]);return {'left':l,'right':r,'lower':p.lin('Le',[[l['lower'],1],[r['lower'],1]])}
    def spread(node,up):
        if 'leaf' in node:upper[node['leaf']]=up;return
        l,r=node['left'],node['right'];lu=p.lin('Le',[[up,1],[r['lower'],1]]);ru=p.lin('Le',[[up,1],[l['lower'],1]]);trace.setdefault('child',lu['Local']);spread(l,lu);spread(r,ru)
    for ri,groups in sorted(chosen.items()):
        selected=set()
        for j in groups:assert selected.isdisjoint(forward[j][1]);selected.update(forward[j][1])
        node=tree(groups);root=p.lin('Le',[[{'RowEq':ri},1]]+[[{'VarLower':i},1] for i in a['rows'][ri]['terms'] if i not in selected],expression(-1,{i:1 for i in selected}));trace.setdefault('root',root['Local']);spread(node,root)
    costs={ri:a['objective'][1][i] for i,ri in singletons.items()}
    wanted=combine([(substitute(b['objective'],forward),1),(a['objective'],-1)])
    eqterms=[[{'RowEq':ri},-costs[ri]] for ri in range(100)];residual=combine([(wanted,1)]+[(p.refexpr(r),-c) for r,c in eqterms]);assert residual==expression(0,{i:-c for i,c in savings.items()})
    objective=p.lin('Le',eqterms+[[{'VarLower':i},saving] for i,saving in savings.items()],wanted);trace['objective']=objective['Local']
    obs=[]
    for j,e in enumerate(forward):
        if len(e[1])>1:obs.append((e,expression(0,{j:1}),None))
    for i,ri in singletons.items():obs.append((aggregates[i],reverse[i],ri))
    base={'input_integers':True,'output_integers':True,'projection':[],'inverse':None}
    claims=[{**base,'reverse':False,'objective':'NonIncreasing','affine_projection':[[expr_json(x),expr_json(y)] for x,y,_ in obs]}, {**base,'reverse':True,'objective':'Equal','affine_projection':[[expr_json(y),expr_json(x)] for x,y,_ in obs]}]
    checks=[]
    for j,e in enumerate(forward):checks.extend([lower[j],upper[j],'Exact'])
    singleton_by_row={ri:i for i,ri in singletons.items()}
    for row in b['rows']:
        ri=a['row_index'][row['name']];i=singleton_by_row[ri];expected=substitute(row_fact(row,'RowUpper'),forward);checks.append(p.lin('Le',[[{'RowEq':ri},1]]+[[{'VarLower':q},1] for q in aggregates[i][1]],expected))
    checks.append(objective)
    for x,y,ri in obs:
        expected=combine([(substitute(y,forward),1),(x,-1)]);checks.append('Exact' if ri is None else p.lin('Eq',[[{'RowEq':ri},-1]],expected))
    f={'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':checks}}};r=SparseBuilder(b);checks=[]
    for i,(v,e) in enumerate(zip(a['vars'],reverse)):
        if i in replacements:checks.extend(['Exact','Exact','Exact'])
        elif i in singletons:
            ri=singletons[i];rn=a['rows'][ri]['name'];checks.extend([row_ref(b,rn),r.lin('Le',[[{'VarLower':j},1] for j in e[1]],expression(0,e[1])),'Exact'])
        else:j=next(iter(e[1]));checks.extend([{'VarLower':j},{'VarUpper':j},'Exact'])
    for row in a['rows']:assert substitute(row_fact(row,'RowEq'),reverse)==expression();checks.append('Exact')
    assert substitute(a['objective'],reverse)==b['objective'];checks.append('Exact')
    for x,y,_ in obs:assert combine([(substitute(x,reverse),1),(y,-1)])==expression();checks.append('Exact')
    g={'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':checks}}}
    info={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':100,'target_rows':100,'dominated_columns':61,'singleton_substitutions':100,'objective_constant':str(b['objective'][0]),'claims':2,'affine_observations':len(obs),'multi_contributor_groups':sum(len(e[1])>1 for e in forward),'bound_tree_rows':len(chosen),'steps_by_claim':[len(p.steps),len(r.steps)],'obligations_by_claim':[len(f['end']['Return']['checks']),len(g['end']['Return']['checks'])]}
    ancillary={'status':'DOCUMENTED_NON_CLAIM_NOT_CALLER_BOUND','statement':'No original optimum selects any of the 61 dominated columns is not separately machine-certified by this request.','exact_objective_difference_modulo_source_equalities':expr_json(residual),'source_equality_multipliers':[[ri,str(-costs[ri])] for ri in range(100)],'saving_by_removed_variable':{a['vars'][i]['name']:str(c) for i,c in savings.items()},'minimum_strict_saving':str(min(savings.values())),'maximum_strict_saving':str(max(savings.values())),'deterministic_recipe':'Parse actual source supports and exact costs; validate disjoint replacement support identities; form F_j=x_j+sum(removed assigned to j), singleton q_s likewise. Substituted target objective minus source objective minus sum(-singleton_cost_r*source_row_eq_r) equals -sum(strict_saving_i*x_i). prepare() asserts the full exact residual and emits its nonpositive bound via original VarLower premises. This is residual evidence, not an optimizer-exclusion caller contract.'}
    return {'claims':claims,'blocks':[f,g]},info,trace,ancillary


def finish(out,kernel,d):
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    def invoke(cmd):
        p=subprocess.run([str(kernel),*map(str,cmd)],capture_output=True,text=True);return {'command':[str(kernel),*map(str,cmd)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    d['proof_preparer']['sha256']=sha(Path(__file__))
    if not d.get('assemble_byte_deterministic'):
        again=out/'deterministic.rpx';result=invoke(['assemble',out/'proof.rpa',again]);d['kernel_runs'].append(result);save();assert result['exit_code']==0 and sha(again)==sha(out/'proof.rpx');again.unlink();d['assemble_byte_deterministic']=True;save()
    baseline=json.loads(d['kernel_runs'][3]['stdout'])
    # Timing fields are observations, not deterministic execution semantics.
    stable=lambda payload:{key:value for key,value in payload.items() if not key.endswith('_us')}
    for _ in range(2):
        result=invoke(['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',out/'request.json']);d['kernel_runs'].append(result);save();payload=json.loads(result['stdout']);assert result['exit_code']==0 and payload['status']=='VERIFIED';assert stable(payload)==stable(baseline)
    d['status']='VERIFIED';d['verify_semantics_deterministic']=True;d['determinism_comparison']='Exact status, claim counts and complete execution statistics; wall-clock *_us fields intentionally excluded.'
    d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};save();print(json.dumps({key:d[key] for key in ['case_id','status','counts','rpa_bytes','artifacts']},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));ap.add_argument('--out',type=Path,default=Path('cases/test83'));ap.add_argument('--finalize-existing',action='store_true');args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test83-nomf-B1');out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);kernel=args.kernel.resolve();source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    if args.finalize_existing:
        finish(out,kernel,json.loads((out/'preparation.json').read_text()));return
    entry=next(c for c in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if c['case_id']=='test83')
    for path,key in [(source,'source_models'),(target,'final_target_models')]:assert str(path)==str(run/entry[key][0]['path']) and sha(path)==entry[key][0]['sha256']
    cert,counts,trace,ancillary=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test83','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer source-to-target feasible map with objective NonIncreasing and complete target-to-source feasible recovery with objective Equal. Minimum objective and optimal-solution recovery follow. Exact affine observations preserve affected retained contributor sums and recover aggregate singleton coordinates; all 61 dominance replacements and 100 singleton substitutions checked. No bijection of all source feasible points, original-coordinate projection, LP relation, numeric optimum, or separately caller-bound all-optimizer dominated-column exclusion claimed. Ancillary exact negative-saving residual is documented as a non-claim.','counts':counts,'ancillary_dominated_column_exclusion':ancillary,'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rpa.stat().st_size,'rpa_sha256':sha(rpa),'kernel_binary_sha256':sha(kernel),'kernel_runs':[],'negative_checks':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    def invoke(cmd):
        p=subprocess.run([str(kernel),*map(str,cmd)],capture_output=True,text=True);return {'command':[str(kernel),*map(str,cmd)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    save()
    for cmd in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]:
        result=invoke(cmd);d['kernel_runs'].append(result);save();assert result['exit_code']==0,result
    steps={s['Lin']['id']:s['Lin'] for s in cert['blocks'][0]['steps']}
    attacks=[('lost_contributor','Omits a dominated source contributor from a target aggregate.'),('missing_partition_premise','Drops a true partition equality from a shared aggregate upper bound.'),('wrong_saving','Changes a strict-saving multiplier needed for complete objective nonincrease.'),('wrong_singleton_recovery','Changes the exact constant in a recovered singleton.')]
    for name,why in attacks:
        if name=='lost_contributor':obj=next(e['terms'] for e in cert['blocks'][0]['end']['Return']['map'] if len(e['terms'])>1);old=obj.pop();undo=lambda:obj.append(old)
        elif name=='missing_partition_premise':obj=steps[trace['root']]['terms'];old=obj.pop(0);undo=lambda:obj.insert(0,old)
        elif name=='wrong_saving':obj=steps[trace['objective']]['terms'][-1];old=obj[1];obj[1]='0';undo=lambda:obj.__setitem__(1,old)
        else:obj=next(e for e in cert['blocks'][1]['end']['Return']['map'] if e['constant']=='1');old=obj['constant'];obj['constant']='0';undo=lambda:obj.__setitem__('constant',old)
        bad=out/(name+'.rpa');encoded=out/(name+'.rpx');bad.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();assembled=invoke(['assemble',bad,encoded]);assert assembled['exit_code']==0,assembled;rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',encoded,request]);payload=json.loads(rejected['stdout']);assert rejected['exit_code']==2 and payload['status']=='INVALID',rejected
        d['negative_checks'].append({'mutation':name,'rule_broken':why,'exit_code':2,'result':payload,'assemble':assembled,'verify':rejected,'rpa_sha256':sha(bad),'rpx_sha256':sha(encoded),'storage':'Temporary mutations deleted; deterministic recipe in preparer.'});bad.unlink();encoded.unlink();save()
    finish(out,kernel,d)

if __name__=='__main__':main()
