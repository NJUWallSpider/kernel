#!/usr/bin/env python3
"""Actual signed-flow/shared-activation certificate, full untrusted preparation."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha,signature
from prepare_test48 import Proof,case_all,boolean_expr
from prepare_test23 import extend


def signed_extend(model,items):
    m=copy.deepcopy(model);layout=[]
    for j,d in enumerate(items):
        first=len(m['vars']);rows=[]
        for k in range(4):
            name=f'signed_{j}_{k}';m['var_index'][name]=len(m['vars']);m['vars'].append({'name':name,'integer':k>=2,'lower':F(0),'upper':F(1) if k>=2 else None})
        f,z=d['flow'],d['activation'];c=d['capacity']
        expressions=[plus(expression(0,{first:1,first+1:-1}),f,-1),plus(expression(0,{first+2:1,first+3:1}),z,-1),expression(0,{first:1,first+2:-c}),expression(0,{first+1:1,first+3:-c})]
        for k,e in enumerate(expressions):
            ri=len(m['rows']);name=f'signed_row_{ri}';m['row_index'][name]=ri;m['rows'].append({'name':name,'sense':'E' if k<2 else 'L','rhs':-e[0],'terms':e[1]});rows.append(ri)
        layout.append({'first':first,'rows':rows})
    return m,layout


def checks(p,output,mapping,claim,domains,rows,objective):
    result=[]
    for i,v in enumerate(output['vars']):
        for kind,typ,bound in [('Le','VarLower',v['lower']),('Le','VarUpper',v['upper']),('Int','VarInt',None)]:
            if typ=='VarInt':
                if not claim['output_integers'] or not v['integer']:continue
                wanted=mapping[i]
            else:
                if bound is None:continue
                wanted=plus(expression(bound),mapping[i],-1) if typ=='VarLower' else plus(mapping[i],expression(-bound))
            ref=domains[(i,typ)];assert ref=='Exact' or (p.kind(ref) in (kind,'Eq') and p.refexpr(ref)==wanted),(i,typ);result.append(ref)
    for i,row in enumerate(output['rows']):
        wanted=substitute(row_fact(row,next(iter(row_ref(output,row['name'])))),mapping);ref=rows[i]
        assert p.refexpr(ref)==wanted;result.append(ref)
    wanted=plus(substitute(output['objective'],mapping),p.model['objective'],-1);assert p.refexpr(objective)==wanted;result.append(objective)
    for inp,out in claim['affine_projection']:
        ie=expression(F(inp['constant']),{i:F(c) for i,c in inp['terms']});oe=expression(F(out['constant']),{i:F(c) for i,c in out['terms']});wanted=plus(substitute(oe,mapping),ie,-1)
        result.append(p.prove('Eq',wanted))
    return {'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':result}}}


def prepare(a,b,h):
    pairs=h['pairs'];C=F(h['capacity']);assert len(pairs)==760
    observations=[[expr_json(expression(0,{a['var_index'][d['forward_flow']]:1,a['var_index'][d['reverse_flow']]:-1})),expr_json(expression(0,{b['var_index'][d['flow']]:1}))] for d in pairs]
    claims=[{'reverse':rev,'input_integers':True,'output_integers':True,'objective':'Equal' if rev else 'NonIncreasing','projection':[],'affine_projection':[[y,x] for x,y in observations] if rev else observations,'inverse':None} for rev in [False,True]]
    pre=Proof(a);intervals=[]
    for d in pairs:
        u,v=[a['var_index'][d[k]] for k in ['forward_activation','reverse_activation']]
        assert all(a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1 for i in [u,v])
        intervals.append({'lower':[expr_json(expression(0,{u:1})),expr_json(expression(0,{v:1}))],'upper':[expr_json(expression(0,{u:1,v:1})),expr_json(expression(1))], 'checks':[{'VarLower':v},{'VarUpper':u},{'VarLower':u},{'VarUpper':v}]})
    ext,layout=extend(a,intervals);p=Proof(ext);mapping=[None]*len(b['vars']);domains={};rows={};cost=[]
    for d,l in zip(pairs,layout):
        aa,bb,u,v=[a['var_index'][d[k]] for k in ['forward_flow','reverse_flow','forward_activation','reverse_activation']];f,z=[b['var_index'][d[k]] for k in ['flow','activation']];zz=l['variable'];ze=expression(0,{zz:1});lo=[{'RowLower':r} for r in l['lower']];hi=[{'RowUpper':r} for r in l['upper']]
        mapping[f]=expression(0,{aa:1,bb:-1});mapping[z]=ze
        lower=p.lin('Le',[[lo[0],F(1)],[{'VarLower':u},F(1)]],mul(ze,-1));upper=hi[1]
        bits=[boolean_expr(p,expression(0,{i:1})) for i in [u,v]]
        def leaf(child,state):
            uv=[state[signature(bit['expr'])] for bit in bits];value=max(x[0] for x in uv)
            if value:
                j=next(j for j,x in enumerate(uv) if x[0]==1);lower1=child.lin('Le',[[lo[j],F(1)],[uv[j][1],F(-1)]],plus(expression(1),ze,-1));eq=child.eqpair(upper,lower1)
            else:
                upper0=child.lin('Le',[[hi[0],F(1)]]+[[x[1],F(1)] for x in uv],ze);eq=child.eqpair(upper0,lower)
            return child.lin('Int',[[eq,F(1)]],ze,constant=value)
        integer=case_all(p,'Int',ze,bits,leaf);domains[(z,'VarLower')]=lower;domains[(z,'VarUpper')]=upper;domains[(z,'VarInt')]=integer
        rows[b['row_index'][d['upper_link']]]=p.lin('Le',[[row_ref(a,d['forward_link']),F(1)],[lo[0],C],[{'VarLower':bb},F(1)]],plus(mapping[f],ze,-C))
        rows[b['row_index'][d['lower_link']]]=p.lin('Le',[[row_ref(a,d['reverse_link']),F(1)],[lo[1],C],[{'VarLower':aa},F(1)]],plus(mul(mapping[f],-1),ze,-C))
        cost.append([hi[0],F(d['cost'])])
    for i,row in enumerate(b['rows']):
        if i not in rows:
            ref=row_ref(a,row['name']);assert p.refexpr(ref)==substitute(row_fact(row,'RowEq'),mapping);rows[i]=ref
    obj=p.lin('Le',cost,plus(substitute(b['objective'],mapping),a['objective'],-1));body=checks(p,b,mapping,claims[0],domains,rows,obj);forward={'steps':[],'end':{'IntervalLift':{'intervals':intervals,'body':body}}}
    items=[];wire=[]
    for d in pairs:
        f,z=[b['var_index'][d[k]] for k in ['flow','activation']];item={'capacity':C,'flow':expression(0,{f:1}),'activation':expression(0,{z:1})};items.append(item);wire.append({'capacity':str(C),'flow':expr_json(item['flow']),'activation':expr_json(item['activation']),'checks':[{'VarLower':z},{'VarUpper':z},{'VarInt':z},row_ref(b,d['upper_link']),row_ref(b,d['lower_link'])]})
    ext,layout=signed_extend(b,items);p=Proof(ext);mapping=[None]*len(a['vars']);domains={};rows={};cost=[];flowalias={}
    for d,l in zip(pairs,layout):
        aa,bb,u,v=[a['var_index'][d[k]] for k in ['forward_flow','reverse_flow','forward_activation','reverse_activation']];first=l['first'];rr=l['rows']
        for old,new in zip([aa,bb,u,v],range(first,first+4)):
            mapping[old]=expression(0,{new:1});domains[(old,'VarLower')]={'VarLower':new}
            if a['vars'][old]['upper'] is not None:domains[(old,'VarUpper')]={'VarUpper':new}
            if a['vars'][old]['integer']:domains[(old,'VarInt')]={'VarInt':new}
        rows[a['row_index'][d['forward_link']]]={'RowUpper':rr[2]};rows[a['row_index'][d['reverse_link']]]={'RowUpper':rr[3]};cost.append([{'RowEq':rr[1]},F(d['cost'])]);flowalias[b['var_index'][d['flow']]]={'RowEq':rr[0]};p.add('Eq',{'RowEq':rr[0]})
    for i,row in enumerate(a['rows']):
        if i in rows:continue
        if row['name']==h['deleted_balance']['row']:
            terms=[[row_ref(b,n),F(-1)] for n in h['retained_balances']];base=p.lin('Eq',terms)
        else:base=row_ref(b,row['name'])
        raw=p.refexpr(base);terms=[[base,F(1)]]+[[flowalias[j],c] for j,c in raw[1].items()];wanted=substitute(row_fact(row,'RowEq'),mapping);rows[i]=p.lin('Eq',terms,wanted)
    obj=p.lin('Eq',cost,plus(substitute(a['objective'],mapping),b['objective'],-1));body=checks(p,a,mapping,claims[1],domains,rows,obj);reverse={'steps':[],'end':{'SignedLift':{'decompositions':wire,'body':body}}}
    return {'claims':claims,'blocks':[forward,reverse]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test27-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test27'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hints=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target);cert=prepare(a,b,json.loads(hints.read_text()));rp=out/'proof.rpa';request=out/'request.json';rp.write_text('RPA 8\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n');k=args.kernel.resolve()
    d={'case_id':'test27','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(hints),'sha256':sha(hints)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete MI feasible-set correspondence with source-to-target nonincreasing objective, target-to-source equal objective and all760 signed-flow observations preserved in both directions. Feasibility and extended minimum agree; original dominated objective levels and full feasible-point bijection are not asserted.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':2,'signed_pairs':760},'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rp.stat().st_size,'rpa_sha256':sha(rp),'kernel_binary_sha256':sha(k),'kernel_runs':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        t=time.perf_counter();p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'elapsed_seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[];save()
    for name,reason in [('missing_capacity','Removes a middle signed decomposition capacity premise.'),('wrong_capacity','Changes one signed capacity from the actually proved coefficient.'),('new_scope_reference','Uses a generated binary coordinate to justify its own parent integrality.'),('lost_active_zero','Drops a reverse activation coordinate, violating objective and full domain laws.'),('missing_balance','Drops one middle original balance obligation.'),('wrong_observation','Changes a requested signed-flow observation while caller remains unchanged.')]:
        bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['SignedLift'];ret=lift['body']['end']['Return']
        if name=='missing_capacity':lift['decompositions'][380]['checks'].pop(3)
        elif name=='wrong_capacity':lift['decompositions'][380]['capacity']='213'
        elif name=='new_scope_reference':lift['decompositions'][380]['checks'][2]={'VarInt':len(b['vars'])+2}
        elif name=='lost_active_zero':ret['map'][a['var_index']['y...0001']]=expr_json(expression())
        elif name=='missing_balance':ret['checks'].pop(6400)
        else:bad['claims'][0]['affine_projection'][380][0]['terms'][0][1]='2'
        text=out/(name+'.rpa');binary=out/(name+'.rpx');text.write_text('RPA 8\n'+json.dumps(bad,separators=(',',':'))+'\n');p=subprocess.run([str(k),'assemble',str(text),str(binary)],capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(text),'rpx_sha256':sha(binary)});save()
    print(json.dumps({'case':d['case_id'],'status':d['status'],'verification':json.loads(d['kernel_runs'][-1]['stdout']),'attacks':len(d['negative_checks'])},indent=2))

if __name__=='__main__':main()
