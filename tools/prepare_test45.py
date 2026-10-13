#!/usr/bin/env python3
"""Actual test45: exact integer and LP retained projections with affine completion."""
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, sha
from prepare_test57 import substitute
from prepare_test70 import SparseBuilder
from prepare_test54 import box, exact


def run_receipt(case, prepare, contract, mutations, version=2):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=Path(f'/Users/bhz/Code/reform_test/runs/{case}-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases')/case)
    ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'))
    args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    inv=next(c for c in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if c['case_id']==case)
    source=run/inv['source_models'][0]['path'];target=run/inv['final_target_models'][0]['path'];audit=run/'output/audit.json'
    assert sha(source)==inv['source_models'][0]['sha256'] and sha(target)==inv['final_target_models'][0]['sha256']
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()))
    rpa=out/'proof.rpa';request=out/'request.json'
    def emit(obj,path):path.write_text(f'RPA {version}\n'+json.dumps(obj,separators=(',',':'))+'\n')
    emit(cert,rpa);request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    k=args.kernel.resolve();script=Path('tools')/f'prepare_{case}.py'
    d={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(script.resolve()),'sha256':sha(script)},'claims':contract,'counts':counts,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def command(cmd,expected=0):
        p=subprocess.run([str(k)]+[str(x) for x in cmd],capture_output=True,text=True)
        record={'command':[str(k)]+[str(x) for x in cmd],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(record)
        if p.returncode!=expected:
            d['status']='EXECUTION_FAILED';d['preparation_seconds']=time.perf_counter()-start;(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(record)
        return record
    command(['canonical',source,out/'source.mcm']);command(['canonical',target,out/'target.mcm']);command(['assemble',rpa,out/'proof.rpx'])
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]
    first=command(verify);assert json.loads(first['stdout'])['status']=='VERIFIED'
    deterministic=out/'deterministic.rpx';command(['assemble',rpa,deterministic]);assert sha(deterministic)==sha(out/'proof.rpx');deterministic.unlink()
    for name,reason,mutate in mutations:
        bad=copy.deepcopy(cert);mutate(bad);path=out/(name+'.rpa');encoded=out/(name+'.rpx');emit(bad,path)
        assembled=command(['assemble',path,encoded]);checked=command(['verify',out/'source.mcm',out/'target.mcm',encoded,request],2)
        result=json.loads(checked['stdout']);assert result['status']=='INVALID'
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'exit_code':2,'result':result,'assemble':assembled,'verify':checked,'storage':'Mutated files deleted; deterministic recipe in proof preparer.'});path.unlink();encoded.unlink()
    def stable(record):return {key:value for key,value in json.loads(record['stdout']).items() if not key.endswith('_us')}
    for _ in range(2):
        repeated=command(verify);assert stable(repeated)==stable(first) and repeated['stderr']==first['stderr']
    d['status']='VERIFIED';d['determinism']={'assemble_byte_identical':True,'additional_verify_runs':2,'verify_result_and_statistics_identical':True,'excluded_nondeterministic_fields':'Top-level *_us timing measurements'}
    d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['preparation_seconds']=time.perf_counter()-start
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':case,'status':d['status'],'counts':counts,'rpa_bytes':d['rpa_bytes'],'negative_checks':len(d['negative_checks'])}),flush=True)


def prepare(a,b,h):
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    assert len(common)==693 and len(a['vars'])==1533
    forward=[expression(0,{i:1}) for i,j in common]
    slack={d['variable']:d for d in h['slack_eliminations']};binary={d['variable']:d for d in h['binary_projections']}
    reverse=[]
    for v in a['vars']:
        n=v['name']
        if n in b['var_index']:e=expression(0,{b['var_index'][n]:1})
        elif n in slack:e=expression(0,{b['var_index'][x]:F(c) for x,c in slack[n]['reconstruction'].items()})
        else:assert n in binary;e=expression(1)
        reverse.append(e)
    changed={d['row']:d for d in h['changed_rows']};duplicates={d['removed_row']:d['kept_row'] for d in h['duplicate_rows']};slackrows={d['row']:d for d in h['slack_eliminations']};implied={d['row']:d for d in h['equality_implied_inequalities']};dominance={d['row']:d for d in h['dominated_projected_rows']}
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=SparseBuilder(inp);checks=[];cache={}
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,bound,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if bound is not None:
                        wanted=plus(mul(e,sign),expression(-sign*bound));checks.append(box(p,wanted,True))
                if integer and v['integer']:
                    if exact('Int',e):ref='Exact'
                    else:ref=p.lin('Int',[[{'VarInt':j},c] for j,c in e[1].items()],e,e[0])
                    checks.append(ref)
            def restore(n):
                if n in cache:return cache[n]
                row=out['rows'][out['row_index'][n]];typ=next(iter(row_ref(out,n)));wanted=substitute(row_fact(row,typ),mapping)
                if exact('Eq' if typ=='RowEq' else 'Le',wanted):ref='Exact'
                elif not back:
                    ref=row_ref(a,n)
                    if n in changed:
                        d=changed[n];ref=p.lin('Le',[[ref,1],[{'VarUpper':a['var_index'][d['removed_variable']]},-F(d['removed_coefficient'])]],wanted)
                elif n in duplicates:ref=restore(duplicates[n])
                elif n in slackrows:ref=row_ref(b,slackrows[n]['base_row'])
                elif n in implied:
                    d=implied[n];ref=p.lin('Le',[[row_ref(b,d['base_row']),F(d['multiplier'])]]+[[{'VarLower':b['var_index'][v]},-F(c)] for v,c in d['residual'].items()],wanted)
                elif n in dominance:
                    d=dominance[n];terms=[[row_ref(b,d['witness_row']),1]]+[[{'VarLower':b['var_index'][v]},F(c)] for v,c in d['residual'].items()]
                    if not d['witness_projected']:terms.append([{'VarUpper':b['var_index'][d['witness_binary']]},F(d['witness_rhs'])])
                    ref=p.lin('Le',terms,wanted,F(d['witness_rhs'])-F(d['rhs']))
                else:ref=row_ref(b,n)
                assert ref=='Exact' or p.refexpr(ref)==wanted,(back,n);cache[n]=ref;return ref
            for row in out['rows']:checks.append(restore(row['name']))
            assert substitute(out['objective'],mapping)==inp['objective'];checks+=['Exact']*(1+len(common))
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in common] if back else common,'inverse':None})
            blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'slack_reconstructions':len(slack),'canonical_binary_completions':len(binary),'duplicates':len(duplicates),'equality_implications':len(implied),'dominated_capacities':len(dominance),'changed_projected_rows':len(changed),'claims':4,'steps_by_claim':[len(x['steps']) for x in blocks],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


if __name__=='__main__':
    mutations=[('missing_binary_upper','Drops z<=1 from a forward projected capacity.',lambda c:c['blocks'][0]['steps'][-1]['Lin']['terms'].pop()),('missing_capacity_bound','Drops a nonnegativity premise from a reconstructed slack lower bound.',lambda c:next(s['Lin'] for s in c['blocks'][1]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>=3)['terms'].pop()),('wrong_completion','Sets a removed capacity binary to zero instead of one.',lambda c:next(e for e in c['blocks'][1]['end']['Return']['map'] if e['constant']=='1').update(constant='0'))]
    run_receipt('test45',prepare,'Both directions of exact retained-coordinate integer and LP feasible-set projection, with pointwise objective equality and every retained coordinate observed. All 378 continuous slacks have nonnegative affine reconstruction; all 462 single-use zero-cost binaries are completed canonically to one (not claimed unique); 651 duplicates, 21 equality implications, 441 dominated capacities and 21 projected capacities are checked. The 42 coupled binaries remain unchanged. No full inverse or LP strengthening claim.',mutations)
