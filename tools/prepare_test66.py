#!/usr/bin/env python3
"""Certify all actual conditional five-cycle cuts and strict LP strengthening."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder,cases_le_shared
from prepare_test84 import rounded


def identity_certificate(a,b,f,derived,values):
    assert a['vars']==b['vars'] and a['objective']==b['objective']
    n=len(a['vars']);mapping=[expr_json(expression(0,{i:1})) for i in range(n)];projection=[[i,i] for i in range(n)]
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);p=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for row in out['rows']:
            rn=row['name']
            if not back and rn in derived:ref=derived[rn]
            else:
                assert row==inp['rows'][inp['row_index'][rn]];ref=row_ref(inp,rn)
            assert p.refexpr(ref)==row_fact(row,next(iter(row_ref(out,rn))));checks.append(ref)
        inverse=[1,0,None][index];checks+=['Exact']*(1+n+(n if inverse is not None else 0))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse})
        blocks.append({'steps':p.steps,'end':{'Return':{'map':mapping,'checks':checks}}})
    return {'claims':claims,'blocks':blocks,'points':[{'claim':{'Strictness':{'inclusion_claim':2}},'values':[str(x) for x in values]}]}


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(73728,67583,73728,88067)
    assert a['vars']==b['vars'] and a['objective']==b['objective']
    cuts={d['row']:d for d in h['cuts']};assert len(cuts)==20484 and set(b['row_index'])-set(a['row_index'])==set(cuts)
    f=SparseBuilder(a);derived={}
    for rn,d in cuts.items():
        y=a['var_index'][d['activation']];v=a['vars'][y];assert v['integer'] and v['lower']==0 and v['upper']==1
        target=row_fact(b['rows'][b['row_index'][rn]],'RowUpper');support=set(target[1])-{y}
        assert target==expression(0,{**dict.fromkeys(support,F(1)),y:F(-2)}) and len(support)==5
        assert {a['var_index'][name]:F(c) for name,c in d['coefficients'].items()}==target[1]
        assert len(d['source_vertex_rows'])==5 and len(set(d['source_vertex_rows']))==5
        totals={};terms=[]
        for name in d['source_vertex_rows']:
            ref=row_ref(a,name);e=f.refexpr(ref);assert 'RowUpper' in ref and e[0]==0 and e[1][y]==-1
            assert all(c==1 for i,c in e[1].items() if i!=y)
            terms.append([ref,F(1,2)])
            for i,c in e[1].items():totals[i]=totals.get(i,F(0))+c
        assert totals[y]==-5 and all(totals[i]==2 for i in support)
        spokes=set(totals)-support-{y};assert all(totals[i]==1 and a['vars'][i]['lower']==0 for i in spokes)
        terms += [[{'VarLower':i},F(1,2)] for i in sorted(spokes)]
        base=f.lin('Le',terms,expression(0,{**dict.fromkeys(support,F(1)),y:F(-5,2)}))
        integer=f.lin('Int',[[{'VarInt':i},F(1)] for i in sorted(support)],expression(0,dict.fromkeys(support,F(1))))
        def left(child,zero):return child.lin('Le',[[base,F(1)],[zero,F(1,2)]],target)
        def right(child,one):
            bound=child.lin('Le',[[base,F(1)],[{'VarUpper':y},F(5,2)]],expression(F(-5,2),dict.fromkeys(support,F(1))))
            cut=rounded(child,bound,integer)
            return child.lin('Le',[[cut,F(1)],[one,F(2)]],target)
        derived[rn]=cases_le_shared(f,target,y,left,right)
    w=h['strict_relaxation_witness'];y=a['var_index'][w['distinguished_activation']];activation={a['var_index'][name] for name in w['activation_values']};owner={}
    for row in a['rows']:
        if row['sense']=='L':
            control=[i for i,c in row['terms'].items() if c==-1];assert len(control)==1 and control[0] in activation
            for i,c in row['terms'].items():
                if c==1:assert owner.setdefault(i,control[0])==control[0]
    values=[None]*len(a['vars'])
    for name,value in w['activation_values'].items():values[a['var_index'][name]]=F(value)
    cycle=set(w['cycle_edge_rows']);spokes=set(w['spoke_edge_rows'])
    for row in a['rows']:
        if row['sense']!='E':continue
        assert row['rhs']==1 and len(row['terms'])==4 and set(row['terms'].values())=={F(1)}
        value=F(1,2) if row['name'] in cycle else F(0) if row['name'] in spokes else F(1,4)
        for i in row['terms']:
            assert values[i] is None;values[i]=value if owner[i]==y else (1-value)/3
    assert all(x is not None for x in values)
    cert=identity_certificate(a,b,f,derived,values)
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'five_cycles':5121,'cuts':len(cuts),'integer_rounds':len(cuts),'binary_cases':len(cuts),'claims':3,'points':1,'steps_by_claim':[len(x['steps']) for x in cert['blocks']],'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']]}
    return cert,counts


def execute(case,source,target,audit,extra,cert,counts,out,kernel,start,contract,mutations):
    out.mkdir(parents=True,exist_ok=True);rpa=out/'proof.rpa';request=out/'request.json'
    def encode(path):path.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n')
    encode(rpa);request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n')
    metadata={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(extra).resolve()),'sha256':sha(Path(extra))},'claims':contract,'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_binary_sha256':sha(kernel),'kernel_runs':[],'negative_checks':[]}
    receipt=out/'preparation.json'
    def run(args,expected=0):
        command=[str(kernel)]+[str(x) for x in args];p=subprocess.run(command,capture_output=True,text=True)
        record={'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};metadata['kernel_runs'].append(record)
        if p.returncode!=expected:
            metadata['status']='EXECUTION_FAILED';receipt.write_text(json.dumps(metadata,indent=2)+'\n');raise RuntimeError(record)
        return record
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]
    for args in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],verify]:run(args)
    artifacts={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
    repeated=out/'determinism.rpx';run(['assemble',rpa,repeated]);assert sha(repeated)==artifacts['proof.rpx']['sha256'];repeated.unlink();metadata['assemble_byte_deterministic']=True
    for name,reason,mutate in mutations:
        undo=mutate(cert);path=out/(name+'.rpa');encoded=out/(name+'.rpx')
        try:encode(path)
        finally:undo()
        assembled=run(['assemble',path,encoded]);checked=run(['verify',out/'source.mcm',out/'target.mcm',encoded,request],2);result=json.loads(checked['stdout']);assert result['status']=='INVALID'
        metadata['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':2,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'kernel_runs':[assembled,checked],'storage':'Temporary mutations removed; deterministic mutation recipe in proof preparer.'});path.unlink();encoded.unlink()
    for _ in range(2):assert json.loads(run(verify)['stdout'])['status']=='VERIFIED'
    assert all(sha(out/name)==data['sha256'] for name,data in artifacts.items()) and sha(rpa)==metadata['rpa_sha256']
    metadata.update(status='VERIFIED',artifacts=artifacts,verify_deterministic=True);receipt.write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({'case_id':case,'status':'VERIFIED','counts':counts,'negative_checks':len(mutations),'artifacts':artifacts},indent=2))


def remove_term(cert):
    terms=cert['blocks'][0]['steps'][0]['Lin']['terms'];old=terms.pop();return lambda:terms.append(old)


def wrong_integer(cert):
    obj=next(s['Lin'] for s in cert['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Int');old=obj['terms'][0][0];obj['terms'][0][0]={'VarInt':0};return lambda:obj['terms'][0].__setitem__(0,old)


def missing_inverse(cert):
    checks=cert['blocks'][1]['end']['Return']['checks'];old=checks.pop();return lambda:checks.append(old)


def invalid_point(cert):
    values=cert['points'][0]['values'];old=values[0];values[0]='-1';return lambda:values.__setitem__(0,old)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test66-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test66'));ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();source=run/'input/model.mps';target=run/'output/model_odd5.mps';audit=run/'output/verification.json'
    inventory=next(x for x in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if x['case_id']=='test66')
    assert sha(source)==inventory['source_models'][0]['sha256'] and sha(target)==inventory['final_target_models'][0]['sha256']
    verification=json.loads(audit.read_text());assert verification['original_sha256']==sha(source) and verification['final_sha256']==sha(target)
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads((run/'output/audit.json').read_text()))
    execute('test66',source,target,audit,__file__,cert,counts,args.out.resolve(),args.kernel.resolve(),start,'Complete same-coordinate integer feasible-set equality and exact pointwise objective equality after all 20,484 five-cycle cuts, with both full inverse identities. Complete objective-preserving target LP inclusion and a full 73,728-coordinate fractional source-feasible point excluded by the target establish strict target LP subset. All actual original rows, bounds, integer domains, and added rows are checked.',[('missing_spoke_nonnegativity','Drops a nonnegative spoke cancellation from the sum of actual vertex rows.',remove_term),('wrong_cycle_integrality','Replaces a cycle integer premise with an unrelated coordinate.',wrong_integer),('missing_inverse','Omits a requested complete inverse coordinate.',missing_inverse),('infeasible_strictness_point','Violates a source variable lower bound in the full fractional witness.',invalid_point)])


if __name__=='__main__':main()
