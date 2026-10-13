#!/usr/bin/env python3
"""Exact full-model time-window certificates, with frozen V6 LP fiber evidence."""
from collections import ChainMap
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test70 import SparseBuilder,cases_le_shared


def parse(path):
    # The shared parser predates explicit OBJSENSE. Only an explicit MIN block
    # is stripped for that parser; the kernel canonicalizes the original bytes.
    class Input:
        def read_text(self):
            lines=path.read_text().splitlines();out=[];i=0
            while i<len(lines):
                if lines[i].strip()=='OBJSENSE':
                    assert lines[i+1].strip()=='MIN';i+=2
                else:out.append(lines[i]);i+=1
            return '\n'.join(out)
    return parse_mps(Input())


def zero_case(p,x,packing,old,D,upper_difference):
    wanted=expression(0,{x:1});ident=p.alloc();branches=[]
    for side in (0,1):
        guard=expression(side,{x:1 if side==0 else -1})
        child=SparseBuilder(p.model,p.counter,assumptions=p.assumptions+[guard]);child.facts=ChainMap({},p.facts);ass={'Assumption':len(p.assumptions)}
        if not side:end={'Witness':child.eqpair(ass,{'VarLower':x})}
        else:
            qzero=child.lin('Le',[[packing,1],[ass,1]])
            contradiction=child.lin('Le',[[old,1],[qzero,D],[ass,60000],[upper_difference,1]])
            e=child.refexpr(contradiction);assert not e[1] and e[0]>0
            end={'Absurd':contradiction}
        branches.append({'steps':child.steps,'end':end})
    p.steps.append({'Cases':{'id':ident,'kind':'Eq','expression':expr_json(wanted),'split':expr_json(wanted),'integer':{'VarInt':x},'left':branches[0],'right':branches[1]}});p.facts[ident]=('Eq',wanted);return {'Local':ident}


def prepare(a,b,h,case=81):
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    removed=sorted(set(range(len(a['vars'])))-{i for i,j in common})
    forward=[expression(0,{i:1}) for i,j in common]
    reverse=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    assert len(a['vars'])==11090 and len(a['rows'])==4630
    assert len(removed)==(3341 if case==81 else 3315)
    windows={}
    for row in a['rows']:
        if len(row['terms'])==1:
            i,c=next(iter(row['terms'].items()))
            if not a['vars'][i]['integer']:
                assert c==1 and row['sense'] in ('G','L')
                side='lower' if row['sense']=='G' else 'upper';windows.setdefault(i,{})[side]=(row['rhs'],row_ref(a,row['name']))
    assert len(windows)==65
    for i,w in windows.items():
        assert set(w)=={'lower','upper'};j=b['var_index'][a['vars'][i]['name']]
        assert b['vars'][j]['lower']==w['lower'][0] and b['vars'][j]['upper']==w['upper'][0]
    pairs={}
    for row in a['rows']:
        if len(row['terms'])!=4 or row['sense']!='G':continue
        continuous=[i for i in row['terms'] if not a['vars'][i]['integer']]
        if len(continuous)!=2:continue
        ti=next(i for i in continuous if row['terms'][i]==-1);tj=next(i for i in continuous if row['terms'][i]==1)
        x=next(i for i in row['terms'] if row['terms'][i]==-60000);q=next(i for i in row['terms'] if i not in (ti,tj,x));D=row['terms'][q];A=row['rhs']+60000;B=windows[tj]['lower'][0]-windows[ti]['upper'][0];M=A-B
        assert D>0 and 0<=60000-M and D==A
        assignment=next(r for r in a['rows'] if r['sense']=='E' and r['rhs']==1 and q in r['terms'] and x in r['terms'])
        assert all(c==1 for c in assignment['terms'].values())
        pairs[row['name']]=(ti,tj,x,q,D,A,B,M,assignment)
    assert len(pairs)==4160
    f=SparseBuilder(a);zero={};tight={};path={};packing={}
    def difference(ti,tj,upper=False):
        key=(ti,tj,upper)
        if key not in path:
            refs=[windows[ti]['lower' if upper else 'upper'][1],windows[tj]['upper' if upper else 'lower'][1]]
            path[key]=f.lin('Le',[[r,1] for r in refs])
        return path[key]
    for rn,(ti,tj,x,q,D,A,B,M,assignment) in pairs.items():
        if x not in removed and rn not in b['row_index']:assert B>=A;continue
        assert a['vars'][q]['integer'] and a['vars'][x]['integer'] and a['vars'][q]['lower']==a['vars'][x]['lower']==0 and a['vars'][q]['upper']==a['vars'][x]['upper']==1
        pack=f.lin('Le',[[row_ref(a,assignment['name']),1]]+[[{'VarLower':i},1] for i in assignment['terms'] if i not in (q,x)],expression(-1,{q:1,x:1}));packing[rn]=pack
        if x in removed:zero[x]=zero_case(f,x,pack,row_ref(a,rn),D,difference(ti,tj,True))
        else:
            wanted=substitute(row_fact(b['rows'][b['row_index'][rn]],'RowLower'),forward)
            assert wanted==expression(B,{ti:1,tj:-1,x:M}) and M>0
            old=row_ref(a,rn);bound=difference(ti,tj)
            tight[rn]=cases_le_shared(f,wanted,x,lambda c,r,bound=bound,M=M,wanted=wanted:c.lin('Le',[[bound,1],[r,M]],wanted),lambda c,r,old=old,pack=pack,D=D,M=M,wanted=wanted:c.lin('Le',[[old,1],[pack,D],[r,60000+D-M]],wanted))
    assert set(zero)==set(removed) and len(tight)==(762 if case==81 else 792)
    observations=[[expr_json(expression(0,{i:1})),expr_json(expression())] for i in removed]
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp) if back else f;checks=[]
        bounds={i:{side:(v[side],{('VarLower' if side=='lower' else 'VarUpper'):i}) for side in ('lower','upper') if v[side] is not None} for i,v in enumerate(inp['vars'])}
        if not back:
            for i,w in windows.items():bounds[i]=w
        def prove(kind,wanted,terms=None):
            terms=[] if terms is None else list(terms);got=expression()
            for ref,c in terms:got=plus(got,p.refexpr(ref),c)
            residual=plus(wanted,got,-1)
            if not back:
                for i,c in list(residual[1].items()):
                    if i in zero:terms.append([zero[i],c]);residual=plus(residual,p.refexpr(zero[i]),-c)
            if residual==expression():
                if not terms:return 'Exact'
                if len(terms)==1 and terms[0][1]==1:return terms[0][0]
                return p.lin(kind,terms,wanted)
            assert kind=='Le',(kind,wanted,residual)
            ceiling=residual[0]
            for i,c in residual[1].items():
                value,ref=bounds[i]['upper' if c>0 else 'lower'];terms.append([ref,abs(c)]);ceiling+=c*value
            assert ceiling<=0,('positive residual',back,wanted,ceiling)
            return p.lin('Le',terms,wanted,ceiling)
        for i,v in enumerate(out['vars']):
            for side,sign in [('lower',-1),('upper',1)]:
                if v[side] is not None:checks.append(prove('Le',plus(mul(mapping[i],sign),expression(-sign*v[side]))))
            if integer and v['integer']:
                checks.append({'VarInt':next(iter(mapping[i][1]))} if mapping[i][1] else 'Exact')
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));wanted=substitute(row_fact(row,typ),mapping);kind='Eq' if typ=='RowEq' else 'Le'
            if not back and rn in tight:ref=tight[rn];assert p.refexpr(ref)==wanted
            elif rn in inp['row_index']:ref=prove(kind,wanted,[[row_ref(inp,rn),1]])
            elif back and rn=='c209':ref=prove('Eq',wanted,[[row_ref(b,f'c{k}'),1 if k<105 else -1] for k in range(209)])
            else:ref=prove(kind,wanted)
            checks.append(ref)
        objective=plus(substitute(out['objective'],mapping),inp['objective'],-1);checks.append(prove('Eq',objective))
        projection=[[j,i] for i,j in common] if back else common;affine=[pair[::-1] for pair in observations] if back else observations
        checks+=['Exact']*len(projection)
        checks+=['Exact']*len(removed) if back else [prove('Eq',expression(0,{i:-1})) for i in removed]
        inverse=1 if index==0 else 0 if index==1 else None
        if inverse is not None:
            invmap=forward if back else reverse
            for i,e in enumerate(invmap):checks.append(prove('Eq',plus(substitute(e,mapping),expression(0,{i:-1}))))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'affine_projection':affine,'inverse':inverse})
        blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    cert={'claims':claims,'blocks':blocks};request={'claims':claims}
    if case==81:
        point=[F(0)]*len(a['vars'])
        for i,v in enumerate(a['vars']):
            if v['integer']:
                n=int(v['name'][1:]);point[i]=F(n//105==n%105)
            else:point[i]=windows[i]['lower'][0]
        for name,value in h['witnesses']['fractional']['overrides'].items():point[a['var_index'][name]]=F(value)
        # Full-model arithmetic is independently replayed by the point checker.
        for row in a['rows']:
            e=row_fact(row,next(iter(row_ref(a,row['name']))));value=e[0]+sum(c*point[i] for i,c in e[1].items());assert value==0 if row['sense']=='E' else value<=0
        deleted_positive=a['var_index']['x8861'];assert deleted_positive in removed and point[deleted_positive]==F(1,10)
        fiber_row=len(b['rows'])+len(common)+removed.index(deleted_positive)
        refutation={'steps':[{'Lin':{'id':0,'kind':'Le','constant':'0','terms':[[{'RowEq':fiber_row},'-1']]}}],'end':{'Absurd':{'fact':{'Local':0}}}}
        point_claim={'FiberStrictness':{'inclusion_claim':2}};cert['points']=[{'claim':point_claim,'values':[str(z) for z in point],'refutation':refutation}];request['points']=[point_claim]
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'zero_arcs':len(zero),'conditional_M_rows':len(tight),'automatic_pair_rows':4160-len(zero)-len(tight),'window_bound_pairs':len(windows),'domain_implied_rows':130,'dependent_equality_deletions':int(case==82),'claims':3,'full_original_observations':len(a['vars']),'steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'fiber_points':int(case==81)}
    return cert,request,counts


def main(case=81):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path(f'/Users/bhz/Code/reform_test/runs/test{case}-nomf-B1'));ap.add_argument('--out',type=Path,default=Path(f'cases/test{case}'));ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';k=args.kernel.resolve()
    inventory=json.loads(Path('audit/corpus_inventory.json').read_text());entry=next(x for x in inventory['cases'] if x['case_id']==f'test{case}')
    assert sha(source)==entry['source_models'][0]['sha256'] and sha(target)==entry['final_target_models'][0]['sha256']
    cert,request,counts=prepare(parse(source),parse(target),json.loads(audit.read_text()),case)
    version=6 if case==81 else 5;rpa=out/'proof.rpa';req=out/'request.json'
    def encode(path):path.write_text(f'RPA {version}\n'+json.dumps(cert,separators=(',',':'))+'\n')
    encode(rpa);req.write_text(json.dumps(request,separators=(',',':'))+'\n')
    preparer=Path(__file__) if case==81 else Path('tools/prepare_test82.py')
    d={'case_id':f'test{case}','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(preparer.resolve()),'sha256':sha(preparer)},'claims':'Complete zero-extension integer feasible-set bijection, full original-coordinate observations, both affine inverse identities, and exact objective including constants; full target-to-source LP inclusion. '+('Strict projected LP inclusion established by the complete original 2x2-switch fractional point and an impossible deleted-arc observation fiber.' if case==81 else 'No strictness claimed; all coefficients and rows rebound to the actual distinct test82 model, including the dependent c209 equality.'),'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    def execute(command,expect=0):
        now=time.perf_counter();p=subprocess.run([str(k)]+list(map(str,command)),capture_output=True,text=True);record={'command':[str(k)]+list(map(str,command)),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'elapsed_seconds':time.perf_counter()-now};d['kernel_runs'].append(record);save()
        if p.returncode!=expect:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise RuntimeError(record)
        return record
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',req]
    for command in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],verify]:execute(command)
    verify_stdout=d['kernel_runs'][-1]['stdout'];stable_hash=sha(out/'proof.rpx')
    again=out/'deterministic.rpx';execute(['assemble',rpa,again]);assert sha(again)==stable_hash;again.unlink();d['assemble_byte_deterministic']=True
    for mutation in ('missing_zero_packing_premise','missing_active_branch_assumption','missing_inverse'):
        if mutation=='missing_zero_packing_premise':obj=cert['blocks'][0]['steps'][0]['Lin']['terms'];old=obj.pop();undo=lambda:obj.append(old)
        elif mutation=='missing_active_branch_assumption':
            case_step=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s and s['Cases']['kind']=='Le');obj=case_step['right']['steps'][-1]['Lin']['terms'];old=obj.pop();undo=lambda:obj.append(old)
        else:obj=cert['blocks'][1]['end']['Return']['checks'];old=obj.pop();undo=lambda:obj.append(old)
        bad=out/(mutation+'.rpa');encoded=out/(mutation+'.rpx');encode(bad);undo()
        assemble_record=execute(['assemble',bad,encoded]);verify_record=execute(['verify',out/'source.mcm',out/'target.mcm',encoded,req],2);result=json.loads(verify_record['stdout']);assert result['status']=='INVALID'
        d['negative_checks'].append({'mutation':mutation,'exit_code':2,'result':result,'rpa_sha256':sha(bad),'rpx_sha256':sha(encoded),'assemble':assemble_record,'verify':verify_record,'storage':'Mutated files removed; deterministic semantic recipe retained in preparer.'});bad.unlink();encoded.unlink()
    def semantic_result(stdout):return {key:value for key,value in json.loads(stdout).items() if not key.endswith('_us')}
    for _ in range(2):assert semantic_result(execute(verify)['stdout'])==semantic_result(verify_stdout)
    d['verify_replay_deterministic']=True;d['status']='VERIFIED';d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ('source.mcm','target.mcm','proof.rpx','request.json')};save()
    print(json.dumps({'case_id':d['case_id'],'status':d['status'],'counts':counts,'negative_checks':len(d['negative_checks']),'artifacts':d['artifacts']},indent=2))


if __name__=='__main__':main()
