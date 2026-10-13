#!/usr/bin/env python3
"""Complete exact affine slack/difference proof for immutable actual test63."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test48 import Proof,emit_checks


def inspect(a,b,h):
    old=a['var_index'];new=b['var_index'];fixed=old['x2'];height=old['h'];slacks=h['new_slack_variables']
    assert a['vars'][fixed]=={'name':'x2','integer':False,'lower':F(0),'upper':F(0)}
    assert a['vars'][height]=={'name':'h','integer':False,'lower':F(0),'upper':None}
    assert a['objective']==expression(0,{height:1,fixed:1}) and b['objective']==expression(0,{new['h']:1})
    assert len(slacks)==91 and len(a['vars'])==1456 and len(b['vars'])==1546
    assert len(a['rows'])==len(b['rows'])==111 and set(a['row_index'])==set(b['row_index'])
    assert set(new)==(set(old)-{'x2'})|{x['name'] for x in slacks}
    for var in b['vars']:
        if var['name'] in old:assert var==a['vars'][old[var['name']]]
        else:assert var=={'name':var['name'],'integer':False,'lower':F(0),'upper':None}
    reverse=[expression() if i==fixed else expression(0,{new[v['name']]:1}) for i,v in enumerate(a['vars'])]
    source_loads=[];previous=expression();load_names={x['row'] for x in slacks};seen_slacks=set()
    for item in slacks:
        name,row_name=item['name'],item['row'];assert name not in seen_slacks;seen_slacks.add(name)
        row=a['rows'][a['row_index'][row_name]];assert row['sense']=='L' and row['rhs']==0 and row['terms'][height]==-1
        assert all(c>0 for i,c in row['terms'].items() if i!=height) and fixed not in row['terms']
        load=substitute(row_fact(row,'RowUpper'),reverse);law=plus(load,expression(0,{new[name]:1}))
        expected=plus(law,previous,-1);actual=b['rows'][b['row_index'][row_name]]
        assert actual['sense']=='E' and row_fact(actual,'RowEq')==expected;previous=law;source_loads.append((row_name,name,row))
    assignment_variables=[]
    for row in a['rows']:
        if row['name'] in load_names:continue
        assert row['sense']=='E' and row['rhs']==1 and all(c==1 for c in row['terms'].values())
        assignment_variables+=list(row['terms'])
        actual=b['rows'][b['row_index'][row['name']]];assert actual['sense']=='E' and row_fact(actual,'RowEq')==substitute(row_fact(row,'RowEq'),reverse)
    integer={i for i,v in enumerate(a['vars']) if v['integer']};assert len(integer)==1454 and set(assignment_variables)==integer and len(assignment_variables)==len(integer)
    for i in integer:assert a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
    intervals=[]
    for i in sorted(integer):
        support=[j for j,(_,_,row) in enumerate(source_loads) if i in row['terms']];assert support and support==list(range(min(support),max(support)+1))
        weights={source_loads[j][2]['terms'][i] for j in support};assert len(weights)==1
        intervals.append({'variable':i,'start':min(support),'end':max(support),'weight':str(next(iter(weights)))})
    forward=[];slack_rows={s:a['rows'][a['row_index'][r]] for r,s,_ in source_loads}
    for var in b['vars']:
        name=var['name'];forward.append(mul(row_fact(slack_rows[name],'RowUpper'),-1) if name in slack_rows else expression(0,{old[name]:1}))
    return forward,reverse,source_loads,{'status':'ALL_FIELDS_EQUAL','source_variables':len(a['vars']),'target_variables':len(b['vars']),'rows':len(a['rows']),'interval_columns':intervals,'source_load_terms':sum(len(r['terms']) for _,_,r in source_loads),'target_load_terms':sum(len(b['rows'][b['row_index'][r]]['terms']) for r,_,_ in source_loads)}


def prepare(a,b,h):
    forward,reverse,loads,evidence=inspect(a,b,h);pairs=[[i,b['var_index'][v['name']]] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']];fixed=a['var_index']['x2']
    claims=[]
    for integer in [True,False]:
        base=len(claims)
        claims.extend([
            {'reverse':False,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':pairs,'affine_projection':[[expr_json(expression(0,{fixed:1})),expr_json(expression())]],'inverse':base+1},
            {'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in pairs],'affine_projection':[[expr_json(expression()),expr_json(expression(0,{fixed:1}))]],'inverse':base},
        ])
    blocks=[]
    for integer in [True,False]:
        p=Proof(a);zero=p.eqpair({'VarUpper':fixed},{'VarLower':fixed});p.add('Eq',zero)
        f=emit_checks(p,b,forward,claims[len(blocks)],inverse=reverse);blocks.append(f)
        p=Proof(b);prefix=None;rows={}
        for row_name,slack,row in loads:
            ref=row_ref(b,row_name);terms=[[ref,F(1)]]+([[prefix,F(1)]] if prefix else [])
            prefix=p.lin('Eq',terms,plus(substitute(row_fact(row,'RowUpper'),reverse),expression(0,{b['var_index'][slack]:1})));p.add('Eq',prefix)
            rows[a['row_index'][row_name]]=p.lin('Le',[[prefix,F(1)],[{'VarLower':b['var_index'][slack]},F(1)]],substitute(row_fact(row,'RowUpper'),reverse))
        r=emit_checks(p,a,reverse,claims[len(blocks)],rows=rows,inverse=forward);blocks.append(r)
    return {'claims':claims,'blocks':blocks},evidence


def attacks(cert,out,kernel,request,b):
    checks=[]
    for name,reason in [
        ('negative_slack_map','A forward slack has its sign reversed, violating its actual lower bound.'),
        ('broken_prefix','A middle reverse prefix equality omits its predecessor, so a complete original load row no longer follows.'),
        ('wrong_fixed_zero','The eliminated original fixed-zero coordinate is reconstructed as one.'),
        ('missing_last_inverse','The LP reverse Return omits the last complete affine inverse coordinate check.'),
        ('wrong_original_objective','The source objective-preservation check cites a nonzero constant equality.'),
    ]:
        bad=copy.deepcopy(cert)
        if name=='negative_slack_map':
            e=bad['blocks'][0]['end']['Return']['map'][b['var_index']['S045']];e['constant']=str(-F(e['constant']));e['terms']=[[i,str(-F(c))] for i,c in e['terms']]
        elif name=='broken_prefix':
            eqs=[x['Lin'] for x in bad['blocks'][1]['steps'] if 'Lin' in x and x['Lin']['kind']=='Eq'];step=eqs[45];assert len(step['terms'])==2;step['terms'].pop()
        elif name=='wrong_fixed_zero':
            source_fixed=cert['claims'][1]['affine_projection'][0][1]['terms'][0][0];bad['blocks'][1]['end']['Return']['map'][source_fixed]=expr_json(expression(1))
        elif name=='missing_last_inverse':bad['blocks'][3]['end']['Return']['checks'].pop()
        elif name=='wrong_original_objective':
            block=bad['blocks'][0];objective_index=sum((v['lower'] is not None)+(v['upper'] is not None)+v['integer'] for v in b['vars'])+len(b['rows']);ref=block['end']['Return']['checks'][objective_index];step=next(s['Lin'] for s in block['steps'] if 'Lin' in s and s['Lin']['id']==ref['Local']);step['constant']='1'
        directory=out/'attacks';directory.mkdir(exist_ok=True);rpa=directory/(name+'.rpa');rpx=directory/(name+'.rpx');rpa.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n')
        assembled=subprocess.run([str(kernel),'assemble',str(rpa),str(rpx)],capture_output=True,text=True);assert assembled.returncode==0,(assembled.stdout,assembled.stderr)
        result=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(rpx),str(request)],capture_output=True,text=True);value=json.loads(result.stdout);assert result.returncode==2 and value['status']=='INVALID',(name,result.stdout,result.stderr)
        checks.append({'mutation':name,'rule_broken':reason,'exit_code':result.returncode,'result':value,'rpa_sha256':sha(rpa),'rpx_sha256':sha(rpx)})
    return checks


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test63-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test63'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target);cert,evidence=prepare(a,b,json.loads(hint.read_text()))
    rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n');(out/'independent_structure.json').write_text(json.dumps(evidence,indent=2)+'\n')
    receipt={'case_id':'test63','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete objective-preserving affine bijection in both mixed-integer and LP modes, with every retained named coordinate and fixed-zero observation explicit.','preparation_seconds':time.perf_counter()-start,'rpa_bytes':rpa.stat().st_size,'rpa_sha256':sha(rpa),'kernel_runs':[]}
    if args.kernel:
        kernel=args.kernel.resolve();receipt['kernel_binary_sha256']=sha(kernel)
        for command in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(kernel)]+command,capture_output=True,text=True);receipt['kernel_runs'].append({'command':[str(kernel)]+command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                receipt['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        receipt['negative_checks']=attacks(cert,out,kernel,request,b);receipt['status']='VERIFIED';receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['case_id','status','preparation_seconds','rpa_bytes']},indent=2))
if __name__=='__main__':main()
