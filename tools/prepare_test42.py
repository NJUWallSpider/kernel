#!/usr/bin/env python3
"""Actual test42 full activation-prefix aggregation with complete LP strictness witness."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder,fix_binary
from prepare_test70 import SparseBuilder,cases_le_shared
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(167056,169576,167056,3076)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];forward=[expression(0,{i:1}) for i,j in common];reverse=[expression(0,{b['var_index'][v['name']]:1}) for v in a['vars']]
    fixed={a['var_index'][d['variable']] for d in h['edits']['bound_changes']};assert len(fixed)==189
    for i,j in common:
        av,bv=a['vars'][i],b['vars'][j];assert av['integer'] and bv['integer'] and av['lower']==0 and av['upper']==1 and bv['upper']==1 and bv['lower']==(1 if i in fixed else 0)
    changes={d['row']:d for d in h['edits']['modified_group_rows']};deleted=set(a['row_index'])-set(b['row_index']);assert len(deleted)==166500
    links={};link_by_row={}
    for rn in deleted:
        row=a['rows'][a['row_index'][rn]];assert row['sense']=='G' and row['rhs']==0 and len(row['terms'])==2
        x=next(i for i,c in row['terms'].items() if c==-1);y=next(i for i,c in row['terms'].items() if c==1);assert x not in links;links[x]=(y,rn);link_by_row[rn]=(x,y)
    group_for_x={};groups={}
    for row in a['rows']:
        if row['sense']=='L' and row['rhs']==1 and len(row['terms'])==100 and all(c==1 for c in row['terms'].values()) and all(i in links for i in row['terms']):
            members=sorted(row['terms']);ys={links[i][0] for i in members};assert len(ys)==1;y=next(iter(ys));groups[row['name']]=(members,y)
            for i in members:assert i not in group_for_x;group_for_x[i]=row['name']
    assert len(groups)==1665 and set(group_for_x)==set(links)
    f=SparseBuilder(a);hint=h['certificates']['objective_bound'];ys=[a['var_index'][n] for n in hint['result_coefficients']['variables']];assert len(ys)==556 and set(ys[:189])==fixed
    terms=[[row_ref(a,n),F(1,4)] for n in hint['capacity_rows']]+[[row_ref(a,d['row']),-F(d['multiplier'],4)] for d in hint['subtract_equalities']]
    demand=f.lin('Le',terms,expression(F(753,4),{i:-1 for i in ys}));chain=[row_ref(a,n) for n in hint['chain_rows']]
    for j,ref in enumerate(chain):assert f.refexpr(ref)==expression(0,{ys[j+1]:1,ys[j]:-1})
    pivot=ys[188]
    def impossible(child,assumption):
        terms=[[demand,F(1)]]+[[{'VarUpper':i},F(1)] for i in ys[:188]]+[[chain[k],F(555-k)] for k in range(188,555)]+[[assumption,F(368)]]
        return {'Absurd':child.lin('Le',terms,expression(F(1,4)))}
    last_fixed=f.cases(expression(-1,{pivot:1}),pivot,impossible,lambda child,assumption:{'Witness':fix_binary(child,pivot,F(1),assumption)})
    fixed_eq={pivot:last_fixed}
    for j in range(188):
        lower=f.lin('Le',[[chain[k],F(1)] for k in range(j,188)]+[[last_fixed,F(-1)]],expression(1,{ys[j]:-1}));fixed_eq[ys[j]]=f.eqpair({'VarUpper':ys[j]},lower)
    aggregate={}
    for rn,d in changes.items():
        members,y=groups[rn];wanted=substitute(row_fact(b['rows'][b['row_index'][rn]],'RowUpper'),forward);assert wanted==expression(0,{**{i:1 for i in members},y:-1})
        aggregate[rn]=cases_le_shared(f,wanted,y,lambda child,assumption:child.lin('Le',[[row_ref(a,links[i][1]),F(1)] for i in members]+[[assumption,F(99)]],wanted),lambda child,assumption:child.lin('Le',[[row_ref(a,rn),F(1)],[assumption,F(1)]],wanted))
    claims=[];blocks=[];step_counts=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp) if back else f;checks=[];restored={}
        if back:
            # Every leaf link follows through checked subset bounds. Shared binary
            # trees avoid expanding all other 99 members for every leaf.
            for rn,(source_members,sy) in groups.items():
                if sy in fixed:continue
                members=[b['var_index'][a['vars'][i]['name']] for i in source_members];y=b['var_index'][a['vars'][sy]['name']];negative={}
                def nonpositive(lo,hi):
                    if hi-lo==1:return {'VarLower':members[lo]}
                    key=(lo,hi)
                    if key not in negative:
                        mid=(lo+hi)//2;negative[key]=p.lin('Le',[[nonpositive(lo,mid),F(1)],[nonpositive(mid,hi),F(1)]])
                    return negative[key]
                def descend(lo,hi,upper):
                    if hi-lo==1:restored[links[source_members[lo]][1]]=upper;return
                    mid=(lo+hi)//2
                    left=p.lin('Le',[[upper,F(1)],[nonpositive(mid,hi),F(1)]],expression(0,{**{members[k]:1 for k in range(lo,mid)},y:-1}))
                    right=p.lin('Le',[[upper,F(1)],[nonpositive(lo,mid),F(1)]],expression(0,{**{members[k]:1 for k in range(mid,hi)},y:-1}))
                    descend(lo,mid,left);descend(mid,hi,right)
                descend(0,len(members),row_ref(b,rn))
        for i,v in enumerate(out['vars']):
            j=next(iter(mapping[i][1]))
            if not back and j in fixed:checks.append(fact(p,'Le',expression(1,{j:-1}),[[fixed_eq[j],F(-1)]]))
            else:checks.append(box(p,expression(v['lower'],{j:-1}),True))
            checks.append({'VarUpper':j})
            if integer:checks.append({'VarInt':j})
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));wanted=substitute(row_fact(row,typ),mapping)
            if not back and rn in aggregate:check=aggregate[rn];assert p.refexpr(check)==wanted
            elif back and rn in deleted:
                x,y=link_by_row[rn]
                if y in fixed:
                    tx=b['var_index'][a['vars'][x]['name']];ty=b['var_index'][a['vars'][y]['name']];check=fact(p,'Le',wanted,[[{'VarUpper':tx},F(1)],[{'VarLower':ty},F(1)]])
                else:check=restored[rn];assert p.refexpr(check)==wanted
            elif back and rn in changes:
                y=b['var_index'][a['vars'][groups[rn][1]]['name']];check=fact(p,'Le',wanted,[[row_ref(b,rn),F(1)],[{'VarUpper':y},F(1)]])
            else:check=row_ref(inp,rn);assert p.refexpr(check)==wanted
            checks.append(check)
        assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact');projection=[[j,i] for i,j in common] if back else common;checks.extend(['Exact']*len(projection));inverse=[1,0,None][index]
        if inverse is not None:checks.extend(['Exact']*len(inp['vars']))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}});step_counts.append(len(p.steps))
    witness=h['certificates']['strict_relaxation_witness'];target=set(groups[witness['target_group']][0]);values=[None]*len(a['vars'])
    for i in ys:values[i]=F(1) if i in fixed else F(9,10)
    equalities=[row for row in a['rows'] if row['sense']=='E'];assert len(equalities)==300
    for row in equalities:
        members=set(row['terms']);hit=members&target;assert row['rhs']==1 and all(c==1 for c in row['terms'].values()) and len(hit)<=1;n=len(members)
        for i in members:assert values[i] is None;values[i]=F(1,100) if i in hit else F(99,100*(n-1)) if hit else F(1,n)
    assert all(v is not None for v in values)
    point={'claim':{'Strictness':{'inclusion_claim':2}},'values':[str(v) for v in values]}
    return {'claims':claims,'blocks':blocks,'points':[point]},{'source_variables':167056,'target_variables':167056,'source_rows':169576,'target_rows':3076,'fixed_activation_prefix':189,'strengthened_groups':1101,'restored_individual_links':166500,'claims':3,'points':1,'linear_and_case_steps_by_claim':step_counts,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test42-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test42'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n')
    d={'case_id':'test42','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete same-coordinate integer affine bijection with exact objective and both full inverse identities, plus target LP inclusion and a complete exact source-LP point establishing strict containment. Actual capacity/equality rows and chain imply the fixed prefix; ordinary binary Cases prove aggregate activation; checked subset derivations restore every original link.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_prefix_integrality','Removes integrality from the prefix-fixing split.'),('missing_aggregate_link','Omits a source link required for a strengthened aggregate.'),('missing_subset_bound','Drops a nonnegative subset premise in reverse link restoration.'),('incomplete_strictness_point','Changes a complete witness coordinate so its assignment equality fails.'),('missing_inverse','Omits a requested complete affine inverse coordinate.')]:
            bad=cert;restore=[]
            def change(container,key,value):restore.append((container,key,container[key]));container[key]=value
            if name=='missing_prefix_integrality':case=next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s and s['Cases']['kind']=='Eq');change(case,'integer',None)
            elif name=='missing_aggregate_link':lin=next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s and s['Cases']['kind']=='Le')['left']['steps'][0]['Lin'];change(lin,'terms',lin['terms'][1:])
            elif name=='missing_subset_bound':lin=bad['blocks'][2]['steps'][0]['Lin'];change(lin,'terms',lin['terms'][1:])
            elif name=='incomplete_strictness_point':change(bad['points'][0]['values'],0,'2')
            else:ret=bad['blocks'][1]['end']['Return'];change(ret,'checks',ret['checks'][:-1])
            path=out/(name+'.rpa');path.write_text('RPA 3\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');
            for container,key,value in reversed(restore):container[key]=value
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'temporary_artifacts_removed':True});path.unlink();encoded.unlink()
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
