#!/usr/bin/env python3
"""Prepare actual test28 complete common-source flow aggregation/lifting proof.

The forward map is affine. The reverse map is one joint existential FlowLift
extension followed by ordinary complete-model obligations. The current external
audit supplies only structural indices, never trusted conclusions.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from audit_test28 import inspect
from prepare_affine import parse_mps
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def extend_model(model,w):
    """Untrusted mirror of the documented group/commodity/arc and row ordering."""
    extended=copy.deepcopy(model);groups=[]
    for gi,g in enumerate(w['groups']):
        comps=[]
        for ki,c in enumerate(g['components']):
            ids=[]
            for ei in range(len(w['arcs'])):
                i=len(extended['vars']);name=f'flow_lift_{gi}_{ki}_{ei}'
                extended['vars'].append({'name':name,'integer':False,'lower':F(0),'upper':None});extended['var_index'][name]=i;ids.append(i)
            comps.append({'vars':ids,'rows':[]})
        groups.append({'components':comps,'total_rows':[]})
    def addrow(terms,rhs):
        i=len(extended['rows']);name=f'flow_lift_row_{i}'
        extended['rows'].append({'name':name,'sense':'E','terms':expression(0,terms)[1],'rhs':F(rhs)});extended['row_index'][name]=i;return i
    for gi,g in enumerate(w['groups']):
        for ki,c in enumerate(g['components']):
            ids=groups[gi]['components'][ki]['vars']
            for node in range(w['nodes']):
                terms={}
                for ei,arc in enumerate(w['arcs']):
                    coefficient=int(arc['tail']==node)-int(arc['head']==node)
                    if coefficient:terms[ids[ei]]=F(coefficient)
                rhs=F(c['demand'])*(int(g['source']==node)-int(c['sink']==node))
                groups[gi]['components'][ki]['rows'].append(addrow(terms,rhs))
        for ei,flow in enumerate(g['grouped_flows']):
            terms={c['vars'][ei]:F(1) for c in groups[gi]['components']};terms[flow]=F(-1)
            groups[gi]['total_rows'].append(addrow(terms,0))
    return extended,groups


def obligations(builder,output,mapping,claim,domain_terms,row_terms,objective_terms):
    result=[]
    def prove(kind,wanted,terms):
        if not wanted[1] and ((kind=='Eq' and wanted[0]==0) or (kind=='Le' and wanted[0]<=0) or (kind=='Int' and wanted[0].denominator==1)):
            result.append('Exact');return
        if len(terms)==1 and terms[0][1]==1 and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==wanted:
            result.append(terms[0][0]);return
        result.append(builder.lin(kind,terms,wanted))
    for i,v in enumerate(output['vars']):
        if v['lower'] is not None:prove('Le',plus(expression(v['lower']),mapping[i],-1),domain_terms(i,'VarLower'))
        if v['upper'] is not None:prove('Le',plus(mapping[i],expression(-v['upper'])),domain_terms(i,'VarUpper'))
        if claim['output_integers'] and v['integer']:prove('Int',mapping[i],domain_terms(i,'VarInt'))
    for i,row in enumerate(output['rows']):
        typ={'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]
        prove('Eq' if typ=='RowEq' else 'Le',substitute(row_fact(row,typ),mapping),row_terms(i))
    prove('Eq',plus(substitute(output['objective'],mapping),builder.model['objective'],-1),objective_terms)
    for i,o in claim['projection']:prove('Eq',plus(mapping[o],expression(0,{i:1}),-1),[])
    return {'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':result}}}


def prepare(a,b,h):
    w=inspect(a,b,h)
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':w['retained'],'inverse':None},
            {'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[[j,i] for i,j in w['retained']],'inverse':None}]
    f=Builder(a);fmap=[None]*len(b['vars']);fdomains={};frows={}
    for i,j in w['retained']:
        fmap[j]=expression(0,{i:1});fdomains[j]=[i]
    for arc in w['arcs']:frows[arc['target_capacity']]=[[{'RowUpper':arc['source_capacity']},F(1)]]
    for g in w['groups']:
        for ei,j in enumerate(g['grouped_flows']):
            ids=[c['flows'][ei] for c in g['components']];fmap[j]=expression(0,{i:1 for i in ids});fdomains[j]=ids
        for node,row in enumerate(g['balance_rows']):
            if row is not None:frows[row]=[[{'RowEq':c['balance_rows'][node]},F(1)] for c in g['components']]
    assert all(e is not None for e in fmap) and len(frows)==len(b['rows'])
    forward=obligations(f,b,fmap,claims[0],lambda i,t:[[{t:j},F(1)] for j in fdomains[i]],lambda i:frows[i],[])

    r=Builder(b);flowgroups=[];input_balances=[]
    for g in w['groups']:
        conservations=[];signed=[]
        for node,row in enumerate(g['balance_rows']):
            wanted=expression(-sum(F(c['demand'])*(int(g['source']==node)-int(c['sink']==node)) for c in g['components']))
            for ei,arc in enumerate(w['arcs']):
                wanted=plus(wanted,expression(0,{g['grouped_flows'][ei]:1}),int(arc['tail']==node)-int(arc['head']==node))
            terms=[[{'RowEq':row},F(-1)]] if row is not None else [[{'RowEq':ri},F(1)] for ri in g['balance_rows'] if ri is not None]
            ref=r.lin('Eq',terms,wanted);conservations.append(ref);signed.append([[ref,F(-1)]])
        input_balances.append(signed)
        flowgroups.append({'source':g['source'],'commodities':[[c['sink'],c['demand']] for c in g['components']],
                           'flows':[expr_json(expression(0,{i:1})) for i in g['grouped_flows']],
                           'nonnegative':[{'VarLower':i} for i in g['grouped_flows']],'balances':conservations})
    extension,layout=extend_model(b,w);body=Builder(extension,r.counter,r.facts)
    rmap=[None]*len(a['vars']);rdomains={};rrows={};objective_terms=[]
    for i,j in w['retained']:rmap[i]=expression(0,{j:1});rdomains[i]=[j]
    for gi,g in enumerate(w['groups']):
        for ki,c in enumerate(g['components']):
            for ei,i in enumerate(c['flows']):
                j=layout[gi]['components'][ki]['vars'][ei];rmap[i]=expression(0,{j:1});rdomains[i]=[j]
            for node,i in enumerate(c['balance_rows']):rrows[i]=[[{'RowEq':layout[gi]['components'][ki]['rows'][node]},F(-1)]]
    for ei,arc in enumerate(w['arcs']):
        rmap[arc['aggregate']]=expression(0,{g['grouped_flows'][ei]:1 for g in w['groups']});rdomains[arc['aggregate']]=[g['grouped_flows'][ei] for g in w['groups']]
        totals=[[{'RowEq':group['total_rows'][ei]},F(1)] for group in layout]
        rrows[arc['link']]=totals
        rrows[arc['source_capacity']]=[[{'RowUpper':arc['target_capacity']},F(1)]]+totals
        rrows[arc['aggregate_capacity']]=[[{'RowUpper':arc['target_capacity']},F(1)]]
        objective_terms += [[ref,F(arc['common_flow_cost'])*coef] for ref,coef in totals if F(arc['common_flow_cost'])*coef]
    for node,i in enumerate(w['aggregate_balance_rows']):rrows[i]=[term for g in input_balances for term in g[node]]
    assert all(e is not None for e in rmap) and len(rrows)==len(a['rows'])
    child=obligations(body,a,rmap,claims[1],lambda i,t:[[{t:j},F(1)] for j in rdomains[i]],lambda i:rrows[i],objective_terms)
    witness={'nodes':w['nodes'],'arcs':[[a['tail'],a['head']] for a in w['arcs']],'groups':flowgroups}
    reverse={'steps':r.steps,'end':{'FlowLift':{'witness':witness,'body':child}}}
    return {'claims':claims,'blocks':[forward,reverse]}, {'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
            'claims':2,'extension_variables':len(extension['vars'])-len(b['vars']),'extension_rows':len(extension['rows'])-len(b['rows']),
            'obligations_by_claim':[len(forward['end']['Return']['checks']),len(child['end']['Return']['checks'])],
            'linear_steps_forward':len(f.steps),'linear_steps_reverse_prelude':len(r.steps),'linear_steps_reverse_body':len(body.steps)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test28-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test28'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 4\n'+json.dumps(cert,indent=2)+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n')
    d={'case_id':'test28','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Preserve all150 original integer coordinates and each attainable objective value for every fixed integer assignment, via complete affine aggregation and simultaneous common-source flow lift preserving all directed-arc totals, including residual circulation. Continuous feasible points are not claimed bijective.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                d['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        d['negative_checks']=[]
        for name,reason in [('missing_node','Removes a middle conservation premise from a joint-flow group.'),('wrong_demand','Changes a commodity demand without proving the new aggregate conservation premises.'),('missing_nonnegative','Removes a middle arc nonnegativity premise.'),('lost_arc_total','Changes a reconstructed source commodity coordinate to zero, discarding flow needed by the complete output obligations.')]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['FlowLift']
            if name=='missing_node':lift['witness']['groups'][0]['balances'].pop(5)
            elif name=='wrong_demand':lift['witness']['groups'][0]['commodities'][0][1]='11'
            elif name=='missing_nonnegative':lift['witness']['groups'][0]['nonnegative'].pop(25)
            else:lift['body']['end']['Return']['map'][0]=expr_json(expression())
            path=out/(name+'.rpa');path.write_text('RPA 4\n'+json.dumps(bad,indent=2)+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
