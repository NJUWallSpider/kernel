#!/usr/bin/env python3
"""Exact actual conflict-clique Cases certificates and complete reverse recovery."""
from collections import ChainMap
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder


def split(builder,wanted,var,left,right,kind='Le'):
    ident=builder.alloc();branches=[];e=expression(0,{var:1})
    for side,callback in enumerate((left,right)):
        assumption=e if side==0 else expression(1,{var:-1})
        child=SparseBuilder(builder.model,builder.counter,assumptions=builder.assumptions+[assumption]);child.facts=ChainMap({},builder.facts)
        end=callback(child,{'Assumption':len(builder.assumptions)})
        if 'Witness' in end:assert child.kind(end['Witness'])==kind and child.refexpr(end['Witness'])==wanted
        else:
            c=child.refexpr(end['Absurd']);assert child.kind(end['Absurd'])=='Le' and not c[1] and c[0]>0
        branches.append({'steps':child.steps,'end':end})
    builder.steps.append({'Cases':{'id':ident,'kind':kind,'expression':expr_json(wanted),'split':expr_json(e),'integer':{'VarInt':var},'left':branches[0],'right':branches[1]}});builder.facts[ident]=(kind,wanted)
    return {'Local':ident}


def prepare(a,b,h):
    assert a['vars']==b['vars'] and a['objective']==b['objective'];n=len(a['vars']);mapping=[expr_json(expression(0,{i:1})) for i in range(n)];projection=[[i,i] for i in range(n)]
    deleted={d['name']:d for d in h['removed_conflict_rows']};redundant={d['name']:d for d in h['removed_bound_redundant_rows']};added={d['name']:d for d in h['added_clique_rows']}
    assert set(a['row_index'])-set(b['row_index'])==set(deleted)|set(redundant) and set(b['row_index'])-set(a['row_index'])==set(added)
    edges={frozenset(a['rows'][a['row_index'][rn]]['terms']):row_ref(a,rn) for rn in deleted};assert len(edges)==4802
    f=SparseBuilder(a);cliques={}
    def clique(p,vertices):
        wanted=expression(-1,{i:1 for i in vertices})
        if len(vertices)==2:
            ref=edges[frozenset(vertices)];assert p.refexpr(ref)==wanted;return ref
        x,*rest=vertices
        def left(c,zero):return {'Witness':c.lin('Le',[[clique(c,rest),1],[zero,1]],wanted)}
        def right(c,one):return {'Witness':c.lin('Le',[[edges[frozenset((x,y))],1] for y in rest]+[[one,len(rest)-1]],wanted)}
        return split(p,wanted,x,left,right)
    for rn in added:
        row=b['rows'][b['row_index'][rn]];vertices=sorted(row['terms']);assert 2<=len(vertices)<=8
        assert row_fact(row,'RowUpper')==expression(-1,{i:1 for i in vertices})
        for i in vertices:assert a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
        cliques[rn]=clique(f,vertices)
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for row in out['rows']:
            rn=row['name'];typ=next(iter(row_ref(out,rn)));wanted=row_fact(row,typ)
            if not back and rn in added:check=cliques[rn]
            elif back and rn in deleted:
                covering=deleted[rn]['covering_added_row'];support=set(b['rows'][b['row_index'][covering]]['terms']);assert set(row['terms'])<=support
                check=p.lin('Le',[[row_ref(b,covering),1]]+[[{'VarLower':i},1] for i in sorted(support-set(row['terms']))],wanted)
            elif back and rn in redundant:
                terms=[[{'VarUpper' if c>0 else 'VarLower':i},abs(c)] for i,c in row['terms'].items()];maximum=sum(c*inp['vars'][i]['upper' if c>0 else 'lower'] for i,c in row['terms'].items());check=p.lin('Le',terms,wanted,constant=maximum-row['rhs'])
            else:
                assert row==inp['rows'][inp['row_index'][rn]];check=row_ref(inp,rn)
            assert p.refexpr(check)==wanted;checks.append(check)
        checks+=['Exact']*(1+n);inverse=[1,0,None][index]
        if inverse is not None:checks+=['Exact']*n
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':p.steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':n,'target_variables':n,'source_rows':len(a['rows']),'target_rows':len(b['rows']),'cliques':len(added),'restored_edges':len(deleted),'bound_redundant_rows':len(redundant),'claims':3,'steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def execute(case,source,target,audit,cert,request,counts,contract,out,kernel,preparer,start,mutations,version=2):
    out.mkdir(parents=True,exist_ok=True);rpa=out/'proof.rpa';req=out/'request.json';prefix=f'RPA {version}\n'
    def serialize(path):path.write_text(prefix+json.dumps(cert,separators=(',',':'))+'\n')
    serialize(rpa);req.write_text(json.dumps(request,separators=(',',':'))+'\n')
    inventory=json.loads(Path('audit/corpus_inventory.json').read_text());entry=next(x for x in inventory['cases'] if x['case_id']==case)
    for path,key in [(source,'source_models'),(target,'final_target_models')]:
        identity=entry[key][0];assert str(path)==str(Path(entry['run_directory'])/identity['path']) and sha(path)==identity['sha256']
    d={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(preparer),'sha256':sha(preparer)},'claims':contract,'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[],'kernel_binary_sha256':sha(kernel),'negative_checks':[]}
    def invoke(command,expected=0,record=None):
        p=subprocess.run([str(kernel)]+list(map(str,command)),capture_output=True,text=True);item={'command':[str(kernel)]+list(map(str,command)),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};(d['kernel_runs'] if record is None else record).append(item)
        if p.returncode!=expected:
            d['status']='EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(item)
        return p
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',req]
    invoke(['canonical',source,out/'source.mcm']);invoke(['canonical',target,out/'target.mcm']);invoke(['assemble',rpa,out/'proof.rpx']);first=invoke(verify);assert json.loads(first.stdout)['status']=='VERIFIED'
    for name,reason,mutate in mutations:
        undo=mutate();path=out/(name+'.rpa');serialize(path);undo();encoded=out/(name+'.rpx');runs=[]
        invoke(['assemble',path,encoded],record=runs);p=invoke(['verify',out/'source.mcm',out/'target.mcm',encoded,req],expected=2,record=runs);assert json.loads(p.stdout)['status']=='INVALID'
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':2,'result':json.loads(p.stdout),'kernel_runs':runs,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'storage':'Temporary mutation files removed; deterministic recipe retained in preparer.'});path.unlink();encoded.unlink()
    repeat=out/'determinism.rpx';invoke(['assemble',rpa,repeat]);assert sha(repeat)==sha(out/'proof.rpx');repeat.unlink()
    def semantic(stdout):return {key:value for key,value in json.loads(stdout).items() if not key.endswith('_us')}
    for _ in range(2):assert semantic(invoke(verify).stdout)==semantic(first.stdout)
    d['status']='VERIFIED';d['determinism']={'assemble_byte_identical':True,'repeat_verify_semantic_json_identical':2,'excluded_runtime_fields':'Top-level *_us timings only; exact stdout retained for every run.'};d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':case,'status':d['status'],'counts':counts,'artifacts':d['artifacts'],'negative_checks':len(d['negative_checks'])},indent=2))
    return d


def pop_mutation(values,index=-1):
    value=values.pop(index)
    return lambda:values.insert(index if index>=0 else len(values),value)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test73-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test73'));ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    first=next(s['Cases'] for s in cert['blocks'][0]['steps'] if 'Cases' in s)
    edge=next(s['Lin'] for s in cert['blocks'][2]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>1)
    mutations=[('missing_selected_clique_assumption','Drops the selected binary assumption needed for the clique bound.',lambda:pop_mutation(first['right']['steps'][0]['Lin']['terms'])),('missing_reverse_nonnegativity','Drops a nonnegativity premise from a deleted bound-redundant row restoration.',lambda:pop_mutation(edge['terms'])),('missing_inverse_coordinate','Drops a complete identity-inverse obligation.',lambda:pop_mutation(cert['blocks'][0]['end']['Return']['checks']))]
    execute('test73',source,target,audit,cert,cert['claims'],counts,'Same complete original-coordinate integer feasible vectors and pointwise objective, with full identity observations and inverse identities; objective-preserving target-to-source continuous relaxation inclusion. All 1,339 actual cliques use local binary Cases and supplied pairwise conflict rows, all 4,802 source edges are recovered, and all 24 bound-redundant deletions are justified. No full-model strict LP inclusion is asserted.',args.out.resolve(),args.kernel.resolve(),Path(__file__).resolve(),start,mutations)

if __name__=='__main__':main()
