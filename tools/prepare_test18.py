#!/usr/bin/env python3
"""Complete test18 saturation/projection/strict-fiber proof.

The initial certificate deliberately retains the direct scalar saturation
proofs. Any kernel state-copy optimization must replay these unchanged bytes.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from audit_test18 import inspect
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def alias(builder,group,edge):
    x=group['binary'];d=len(group['edges']);desired=expression(0,{edge:1,x:-1});eq={'RowEq':group['row']}
    if d==1:
        assert builder.refexpr(eq)==desired;return eq
    others=[i for i in group['edges'] if i!=edge]
    def zero(b,assumption):
        pos=b.lin('Le',[[eq,F(1)],[assumption,F(d-1)]]+[[{'VarLower':i},F(1)] for i in others],desired)
        neg=b.lin('Le',[[assumption,F(1)],[{'VarLower':edge},F(1)]],mul(desired,-1))
        return {'Witness':b.eqpair(pos,neg)}
    def one(b,assumption):
        pos=b.lin('Le',[[{'VarUpper':edge},F(1)],[assumption,F(1)]],desired)
        neg=b.lin('Le',[[eq,F(-1)],[assumption,F(d-1)]]+[[{'VarUpper':i},F(1)] for i in others],mul(desired,-1))
        return {'Witness':b.eqpair(pos,neg)}
    return builder.cases(desired,x,zero,one)


def finish(builder,output,mapping,claim,domain_proof,row_proof,objective_proof):
    checks=[]
    def prove(kind,e,terms):
        if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):
            checks.append('Exact');return
        if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:checks.append(terms[0][0]);return
        checks.append(builder.lin(kind,terms,e))
    for i,v in enumerate(output['vars']):
        if v['lower'] is not None:prove('Le',plus(expression(v['lower']),mapping[i],-1),domain_proof(i,'VarLower'))
        if v['upper'] is not None:prove('Le',plus(mapping[i],expression(-v['upper'])),domain_proof(i,'VarUpper'))
        if claim['output_integers'] and v['integer']:prove('Int',mapping[i],domain_proof(i,'VarInt'))
    for i,row in enumerate(output['rows']):
        typ=next(iter(row_ref(output,row['name'])));prove('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),row_proof(i))
    prove('Eq',plus(substitute(output['objective'],mapping),builder.model['objective'],-1),objective_proof)
    for i,o in claim['projection']:assert mapping[o]==expression(0,{i:1});checks.append('Exact')
    return {'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def prepare(a,b,h):
    w=inspect(a,b,h);projection=w['reverse_projection'];forward_projection=[[j,i] for i,j in projection]
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':forward_projection,'inverse':None},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':projection,'inverse':None},
            {'reverse':True,'input_integers':False,'output_integers':False,'objective':'Equal','projection':projection,'inverse':None}]
    f=Builder(a);aliases={}
    for g in w['saturation']:
        for edge in g['edges']:aliases[edge]=alias(f,g,edge)
    y_eq={};packing={}
    for y in w['eliminated_y']:
        desired=expression(0,{y['source_variable']:1})
        for target_i in y['support']:desired=plus(desired,expression(0,{projection[target_i][1]:1}),-1)
        y_eq[y['source_variable']]=f.lin('Eq',[[{'RowEq':y['source_row']},F(-1)]]+[[aliases[i],F(1)] for i in y['edges']],desired)
        name=a['rows'][y['source_row']]['name']
        if name in b['row_index']:packing[b['row_index'][name]]=[[{'VarUpper':y['source_variable']},F(1)],[y_eq[y['source_variable']],F(-1)]]
    budget=b['row_index'][h['retained_budget']['row']]
    packing[budget]=[[row_ref(a,h['retained_budget']['row']),F(1)]]+[[{'VarLower':a['var_index'][n]},F(1)] for n in h['removed_budget_only_variables']]
    mapping=[expression(0,{j:1}) for i,j in projection]
    forward=finish(f,b,mapping,claims[0],lambda i,t:[[{t:projection[i][1]},F(1)]],lambda i:packing[i],[[y_eq[i],-c] for i,c in a['objective'][1].items()])
    reverse_mapping=[expression(F(e['constant']),{i:F(c) for i,c in e['terms']}) for e in w['reverse_map']]
    y_lookup={y['source_variable']:y for y in w['eliminated_y']};blocks=[forward]
    for claim in claims[1:]:
        r=Builder(b)
        def domain(i,kind):
            e=reverse_mapping[i]
            if not e[1]:return []
            if i in y_lookup and kind=='VarUpper':
                y=y_lookup[i];row=b['rows'][y['target_superset_row']]
                return [[{'RowUpper':y['target_superset_row']},F(1)]]+[[{'VarLower':j},F(1)] for j in row['terms'] if j not in e[1]]
            return [[{kind:j},c] for j,c in e[1].items()]
        blocks.append(finish(r,a,reverse_mapping,claim,domain,lambda i:[] if a['rows'][i]['sense']=='E' else [[{'RowUpper':budget},F(1)]],[]))
    separator=w['fiber_contradiction'];terms=[[separator['target_premise'],'1']]+[[{'RowEq':len(b['rows'])+j},coef] for j,coef in separator['observation_multipliers']]
    # Every observation is kernel-generated in this order, not authored as an
    # unchecked row. Their complete point values come from the actual source.
    point={'claim':{'FiberStrictness':{'inclusion_claim':2}},'values':w['source_lp_point'],
           'refutation':{'steps':[{'Lin':{'id':0,'kind':'Le','constant':'0','terms':terms}}],'end':{'Absurd':{'fact':{'Local':0}}}}}
    cert={'claims':claims,'blocks':blocks,'points':[point]}
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
            'claims':3,'points':1,'saturation_aliases':len(aliases),'saturation_branches':sum(len(g['edges']) for g in w['saturation'] if len(g['edges'])>1),
            'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks],'root_steps_by_claim':[len(x['steps']) for x in blocks],'fiber_equalities':len(projection),'fiber_contradiction':'1/21'}
    return cert,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test18-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test18'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 6\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[p['claim'] for p in cert['points']]},separators=(',',':'))+'\n')
    d={'case_id':'test18','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
       'claims':'Same complete retained-coordinate integer projection with pointwise objective preservation both directions; strict containment of the target LP in the projected source LP through a complete source witness and exact target fiber refutation. Four removed budget-only binaries make the projection noninjective; no continuous equivalence or LP objective-bound improvement claimed.',
       'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                d['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED'
                if all((out/n).exists() for n in ['source.mcm','target.mcm','proof.rpx','request.json']):d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
                (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
                if d['status']=='RESOURCE_LIMIT' and not (out/'preparation.naive-resource-baseline.json').exists():(out/'preparation.naive-resource-baseline.json').write_text(json.dumps(d,indent=2)+'\n')
                raise SystemExit(proc.stdout+proc.stderr)
        assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        d['negative_checks']=[]
        for name,reason in [('continuous_split','Uses a continuous edge as the integer witness for a binary saturation split.'),('infeasible_separator','Changes one nonzero edge of the source LP witness, violating complete source feasibility.'),('wrong_fiber_constant','Cancels the derived positive fiber contradiction so the Absurd leaf has no contradiction.'),('integer_inclusion','Points strictness at a mixed-integer claim instead of an established LP inclusion.'),('missing_refutation','Removes the mandatory exact target-fiber refutation.')]:
            bad=copy.deepcopy(cert)
            if name=='continuous_split':
                case=next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s);case['integer']={'VarInt':0}
            elif name=='infeasible_separator':
                i=next(i for i,v in enumerate(bad['points'][0]['values']) if v=='3/5');bad['points'][0]['values'][i]='0'
            elif name=='wrong_fiber_constant':bad['points'][0]['refutation']['steps'][0]['Lin']['constant']='-1/21'
            elif name=='integer_inclusion':bad['points'][0]['claim']['FiberStrictness']['inclusion_claim']=1
            else:bad['points'][0]['refutation']=None
            path=out/(name+'.rpa');path.write_text('RPA 6\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
