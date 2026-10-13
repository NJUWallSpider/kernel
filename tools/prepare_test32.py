#!/usr/bin/env python3
"""Actual test32: binary one-hot exclusions and complete zero-extension proof."""
from fractions import Fraction as F
from pathlib import Path
from collections import ChainMap
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test54 import fact,box


def cases_zero(builder,variable,right):
    ident=builder.alloc();wanted=expression(0,{variable:1});branches=[]
    for side in (0,1):
        assumption=wanted if side==0 else expression(1,{variable:-1})
        child=SparseBuilder(builder.model,builder.counter,assumptions=builder.assumptions+[assumption]);child.facts=ChainMap({},builder.facts);ref={'Assumption':len(builder.assumptions)}
        end={'Witness':child.eqpair(ref,{'VarLower':variable})} if side==0 else {'Absurd':right(child,ref)}
        if side:assert child.kind(end['Absurd'])=='Le' and not child.refexpr(end['Absurd'])[1] and child.refexpr(end['Absurd'])[0]>0
        else:assert child.refexpr(end['Witness'])==wanted
        branches.append({'steps':child.steps,'end':end})
    builder.steps.append({'Cases':{'id':ident,'kind':'Eq','expression':expr_json(wanted),'split':expr_json(wanted),'integer':{'VarInt':variable},'left':branches[0],'right':branches[1]}});builder.facts[ident]=('Eq',wanted);return {'Local':ident}


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(18380,576,4792,382)
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])];relaxed=set(h['relaxed_integer_variables']);removed={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    for i,j in common:
        av,bv=a['vars'][i],b['vars'][j];assert av['name']==bv['name'] and av['lower']==bv['lower'] and av['upper']==bv['upper'] and av['integer'] and bv['integer']==(bv['name'] not in relaxed)
    forward=[expression(0,{i:1}) for i,j in common];reverse=[expression() if i in removed else expression(0,{b['var_index'][v['name']]:1}) for i,v in enumerate(a['vars'])]
    f=SparseBuilder(a);zero={}
    initial={a['var_index'][n] for n in h['removed_original_fixed_zero']}
    for i in sorted(initial):
        assert a['vars'][i]['lower']==a['vars'][i]['upper']==0;zero[i]=f.eqpair({'VarUpper':i},{'VarLower':i})
    groups={};group_of={};definition={};time_row={};tree_cache={};tree_count=0
    for g in h['choice_groups']:
        ref=row_ref(a,g['onehot_row']);e=f.refexpr(ref);assert e[0]==-1 and all(c==1 for c in e[1].values())
        members=sorted(set(e[1])-initial);assert members
        for i in members:assert i not in group_of and a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1;group_of[i]=g['job']
        reduced=f.lin('Eq',[[ref,1]]+[[zero[i],-1] for i in e[1] if i in initial],expression(-1,{i:1 for i in members}));groups[g['job']]=(members,reduced,{i:p for p,i in enumerate(members)})
        for rn,vn in [(g['start_row'],g['start_variable']),(g['completion_row'],g['completion_variable'])]:
            t=a['var_index'][vn];ref=row_ref(a,rn);e=f.refexpr(ref);assert e[0]==0 and e[1][t]==-1 and set(e[1])-{t}<=set(a['rows'][a['row_index'][g['onehot_row']]]['terms'])
            # Normalize the actual defining row to T-sum c*x=0 and remove FX zeros.
            desired=expression(0,{i:-c for i,c in e[1].items() if i not in initial});d=f.lin('Eq',[[ref,-1]]+[[zero[i],c] for i,c in e[1].items() if i in initial],desired)
            coefficients={i:-desired[1].get(i,F(0)) for i in members};definition[t]=(d,coefficients,min(coefficients.values()),max(coefficients.values()));time_row[vn]=rn
    def weighted_subset(t,side,members,lo,hi):
        nonlocal tree_count
        key=t,side,lo,hi
        if key in tree_cache:return tree_cache[key]
        _,coefficients,minimum,maximum=definition[t]
        if hi-lo==1:
            i=members[lo];w=coefficients[i]-minimum if side=='above' else maximum-coefficients[i]
            ref=None if not w else {'VarLower':i} if w==1 else f.lin('Le',[[{'VarLower':i},w]])
        else:
            mid=(lo+hi)//2;left=weighted_subset(t,side,members,lo,mid);right=weighted_subset(t,side,members,mid,hi)
            ref=right if left is None else left if right is None else f.lin('Le',[[left,1],[right,1]])
        tree_cache[key]=ref;tree_count+=1;return ref
    def all_except(t,side,members,position,lo,hi):
        if position<lo or position>=hi:
            r=weighted_subset(t,side,members,lo,hi);return [] if r is None else [[r,1]]
        if hi-lo==1:return []
        mid=(lo+hi)//2;return all_except(t,side,members,position,lo,mid)+all_except(t,side,members,position,mid,hi)
    for name,witnesses in h['removed_onehot_bound_excluded'].items():
        i=a['var_index'][name];assert i not in zero;members,onehot,positions=groups[group_of[i]];vn,side,cvalue,bvalue=witnesses[0];t=a['var_index'][vn];d,coefficients,minimum,maximum=definition[t];cv=coefficients[i];assert cv==F(cvalue)
        if side=='above':
            bound=a['vars'][t]['upper'];assert bound==F(bvalue) and cv>bound;terms=[[d,-1],[onehot,-minimum],[{'VarUpper':t},1]];k=cv-minimum;contradiction=cv-bound
        else:
            assert side=='below';bound=a['vars'][t]['lower'];assert bound==F(bvalue) and cv<bound;terms=[[d,1],[onehot,maximum],[{'VarLower':t},1]];k=maximum-cv;contradiction=bound-cv
        terms+=all_except(t,side,members,positions[i],0,len(members))
        zero[i]=cases_zero(f,i,lambda child,assumption:child.lin('Le',terms+[[assumption,k]],expression(contradiction)))
    assert set(zero)==removed and len(initial)==7282 and len(zero)-len(initial)==6306
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;other=forward if back else reverse;p=SparseBuilder(inp) if back else f;checks=[];time_integer={};duration={}
        if back:
            for g in h['choice_groups']:
                for rn,vn in [(g['start_row'],g['start_variable']),(g['completion_row'],g['completion_variable'])]:
                    t=b['var_index'][vn];ref=row_ref(b,rn);e=p.refexpr(ref);assert e[0]==0 and e[1][t]==-1
                    if integer:time_integer[t]=p.lin('Int',[[ref,-1]]+[[{'VarInt':j},c] for j,c in e[1].items() if j!=t],expression(0,{t:1}))
                start=row_ref(b,g['start_row']);completion=row_ref(b,g['completion_row']);raw=plus(p.refexpr(completion),p.refexpr(start),-1);s=b['var_index'][g['start_variable']];c=b['var_index'][g['completion_variable']];assert raw[1][s]==1 and raw[1][c]==-1
                weights={j:q for j,q in raw[1].items() if j not in (s,c)};assert all(q>0 for q in weights.values());duration[g['job']]=p.lin('Le',[[completion,1],[start,-1]]+[[{'VarLower':j},q] for j,q in weights.items()],expression(0,{s:1,c:-1}))
        for i,v in enumerate(out['vars']):
            e=mapping[i]
            for value,sign in [(v['lower'],-1),(v['upper'],1)]:
                if value is not None:checks.append(box(p,plus(mul(e,sign),expression(-sign*value)),True))
            if integer and v['integer']:
                if back and e[1] and next(iter(e[1])) in time_integer:check=time_integer[next(iter(e[1]))]
                else:check=fact(p,'Int',e,[[{'VarInt':j},q] for j,q in e[1].items()],e[0],True)
                checks.append(check)
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if not back:
                ref=row_ref(a,rn);check=fact(p,kind,wanted,[[ref,1]]+[[zero[i],-c] for i,c in p.refexpr(ref)[1].items() if i in removed],terminal=True)
            elif rn in b['row_index']:
                check=row_ref(b,rn);assert p.refexpr(check)==wanted
            elif rn in h['removed_capacity_rows']:
                ref=row_ref(b,h['removed_capacity_rows'][rn]);delta=plus(wanted,p.refexpr(ref),-1);check=p.lin('Le',[[ref,1],[box(p,delta),1]],wanted)
            else:
                witness=h['removed_precedence_rows'][rn];assert witness['type']=='retained_path';check=p.lin('Le',[[row_ref(b,n),1] for n in witness['rows']]+[[duration[j],1] for j in witness['jobs'][1:-1]],wanted)
            checks.append(check)
        wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1);assert wanted==expression();checks.append('Exact')
        projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=[1,0,None][index]
        if inverse is not None:
            for i,e in enumerate(other):
                wanted=plus(substitute(e,mapping),expression(0,{i:1}),-1);checks.append(fact(p,'Eq',wanted,[[zero[i],-1]] if not back and i in removed else [],terminal=True))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':18380,'target_variables':4792,'source_rows':576,'target_rows':382,'original_fixed_zero':7282,'binary_onehot_exclusions':6306,'restored_time_integrality':60,'removed_capacity_rows':168,'removed_precedence_rows':26,'weighted_subset_nodes':tree_count,'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'steps_by_claim':[len(x['steps']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test32-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test32'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test32','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer zero-extension affine bijection with all retained-coordinate observations, exact objective and both inverse identities, plus objective-preserving target LP inclusion. Explicit Cases refute 6306 out-of-bound one-hot selections, all 60 original integer time coordinates follow from actual target definitions, and every deleted capacity/precedence row is restored. No forward LP equivalence or global strictness is asserted.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_binary_domain','Replaces a binary split with a sign split whose right assumption is weaker.'),('missing_time_bound','Omits the explicit time bound from a refuted selection branch.'),('missing_duration_premise','Omits a nonnegative choice contribution from a duration proof.'),('missing_time_integrality','Discards an integer-choice premise needed to recover an original integer time coordinate.'),('missing_inverse','Omits one complete inverse-coordinate obligation.')]:
            undo=None
            if name=='missing_binary_domain':obj=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s);old=obj['integer'];obj['integer']=None;undo=lambda:obj.update(integer=old)
            elif name=='missing_time_bound':obj=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s)['right']['steps'][-1]['Lin']['terms'];idx=next(j for j,(r,c) in enumerate(obj) if isinstance(r,dict) and ('VarUpper' in r or 'VarLower' in r));old=obj.pop(idx);undo=lambda:obj.insert(idx,old)
            elif name=='missing_duration_premise':
                hint=json.loads(audit.read_text());used=set(next(iter(hint['removed_precedence_rows'].values()))['jobs'][1:-1]);gindex=next(j for j,g in enumerate(hint['choice_groups']) if g['job'] in used);obj=cert['blocks'][1]['steps'][3*gindex+2]['Lin']['terms'];old=obj.pop();undo=lambda:obj.append(old)
            elif name=='missing_time_integrality':obj=next(s['Lin']['terms'] for s in cert['blocks'][1]['steps'] if 'Lin' in s and s['Lin']['kind']=='Int');old=obj.pop();undo=lambda:obj.append(old)
            else:obj=cert['blocks'][1]['end']['Return']['checks'];old=obj.pop();undo=lambda:obj.append(old)
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');undo();encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'storage':'Temporary full mutated files removed after hash and result capture; deterministic recipe retained in preparer.'});path.unlink();encoded.unlink()
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
