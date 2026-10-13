#!/usr/bin/env python3
"""Complete test23 signed-difference proof using joint real interval extensions."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from audit_test23 import inspect
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def expr_from_json(e):return expression(F(e['constant']),{i:F(c) for i,c in e['terms']})


def extend(model,pairs):
    m=copy.deepcopy(model);layout=[]
    for k,p in enumerate(pairs):
        i=len(m['vars']);name=f'interval_{k}'
        m['vars'].append({'name':name,'lower':None,'upper':None,'integer':False});m['var_index'][name]=i
        layout.append({'variable':i,'lower':[],'upper':[]})
    for k,p in enumerate(pairs):
        for which,sense in [('lower','G'),('upper','L')]:
            for bound in p[which]:
                e=expr_from_json(bound);j=len(m['rows']);name=f'interval_row_{j}'
                row=plus(expression(0,{layout[k]['variable']:1}),e,-1)
                m['rows'].append({'name':name,'sense':sense,'rhs':-row[0],'terms':row[1]});m['row_index'][name]=j
                layout[k][which].append(j)
    return m,layout


def run_checks(builder,output,mapping,claim,domain_proof,row_proof,objective_proof):
    checks=[]
    def exact(kind,e):return not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1))
    def prove(kind,wanted,proof):
        if exact(kind,wanted):return 'Exact'
        if isinstance(proof,dict):
            assert builder.kind(proof)==kind and builder.refexpr(proof)==wanted
            return proof
        if len(proof)==1 and proof[0][1]==1 and builder.kind(proof[0][0])==kind and builder.refexpr(proof[0][0])==wanted:return proof[0][0]
        return builder.lin(kind,proof,wanted)
    for i,v in enumerate(output['vars']):
        if v['lower'] is not None:
            wanted=plus(expression(v['lower']),mapping[i],-1);checks.append(prove('Le',wanted,domain_proof(i,'VarLower')))
        if v['upper'] is not None:
            wanted=plus(mapping[i],expression(-v['upper']));checks.append(prove('Le',wanted,domain_proof(i,'VarUpper')))
        if claim['output_integers'] and v['integer']:checks.append(prove('Int',mapping[i],domain_proof(i,'VarInt')))
    for i,row in enumerate(output['rows']):
        typ=next(iter(row_ref(output,row['name'])));wanted=substitute(row_fact(row,typ),mapping)
        checks.append(prove('Eq' if typ=='RowEq' else 'Le',wanted,row_proof(i,wanted)))
    wanted=plus(substitute(output['objective'],mapping),builder.model['objective'],-1)
    checks.append(prove('Eq',wanted,objective_proof(wanted)))
    for i,o in claim['projection']:
        assert plus(mapping[o],expression(0,{i:1}),-1)==expression();checks.append('Exact')
    for inp,out in claim['affine_projection']:
        assert plus(substitute(expr_from_json(out),mapping),expr_from_json(inp),-1)==expression();checks.append('Exact')
    return {'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def eq_without_fixed(builder,wanted,base,fixed):
    """Use both exact fixed bounds without creating one persistent fact per zero."""
    raw=expression()
    for ref,c in base:raw=plus(raw,builder.refexpr(ref),c)
    difference=plus(wanted,raw,-1);assert difference[0]==0 and set(difference[1])<=fixed
    if not difference[1]:
        if not wanted[1] and wanted[0]==0:return []
        if len(base)==1 and base[0][1]==1:return base[0][0]
        return builder.lin('Eq',base,wanted)
    positive=list(base);negative=[[r,-c] for r,c in base]
    for i,c in difference[1].items():
        positive.append([{'VarUpper' if c>0 else 'VarLower':i},abs(c)])
        negative.append([{'VarLower' if c>0 else 'VarUpper':i},abs(c)])
    return builder.eqpair(builder.lin('Le',positive,wanted),builder.lin('Le',negative,mul(wanted,-1)))


def prepare(a,b,h):
    w,samples=inspect(a,b,h);pairs=w['pairs'];fixed=set(w['fixed_zero_source_variables']);ext,layout=extend(b,pairs)
    observations=[[expr_json(expression(0,{p['source_v']:1,p['source_w']:-1})),expr_json(expression(0,{p['target_t']:1}))] for p in pairs]
    claims=[];blocks=[];counts=[]
    for integer in [True,False]:
        forward_claim={'reverse':False,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':w['unchanged_coordinates'],'affine_projection':observations,'inverse':None}
        f=Builder(a);mapping=[None]*len(b['vars']);domains={};special_rows={}
        for i,j in w['unchanged_coordinates']:mapping[j]=expression(0,{i:1});domains[j]={t:[[{t:i},F(1)]] for t in ('VarLower','VarUpper','VarInt')}
        for p in pairs:
            v,z=p['source_v'],p['source_w'];t=p['target_t'];mapping[t]=expression(0,{v:1,z:-1})
            domains[t]={'VarLower':[[{'VarLower':v},F(1)],[{'VarUpper':z},F(1)]],
                        'VarUpper':[[{'VarUpper':v},F(1)],[{'VarLower':z},F(1)]]}
            rg,rl,sg,sl=p['source_rows']
            special_rows[p['target_rows'][0]]=[[row_ref(a,a['rows'][rg]['name']),F(1)],[row_ref(a,a['rows'][sl]['name']),F(1)]]
            special_rows[p['target_rows'][1]]=[[row_ref(a,a['rows'][rl]['name']),F(1)],[row_ref(a,a['rows'][sg]['name']),F(1)]]
        assert all(e is not None for e in mapping)
        def frow(i,wanted):
            if i in special_rows:return special_rows[i]
            return eq_without_fixed(f,wanted,[[row_ref(a,b['rows'][i]['name']),F(1)]],fixed)
        forward=run_checks(f,b,mapping,forward_claim,lambda i,t:domains[i][t],frow,lambda wanted:eq_without_fixed(f,wanted,[],fixed))
        claims.append(forward_claim);blocks.append(forward)

        reverse_claim={'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in w['unchanged_coordinates']],
                       'affine_projection':[[out,inp] for inp,out in observations],'inverse':None}
        prelude=Builder(b);intervals=[]
        for p in pairs:
            checks=[]
            for terms,(lower,upper) in zip(p['lower_upper_proofs'],((lo,hi) for lo in p['lower'] for hi in p['upper'])):
                expected=plus(expr_from_json(lower),expr_from_json(upper),-1);terms=[[ref,F(c)] for ref,c in terms]
                if expected==expression():checks.append('Exact')
                elif len(terms)==1 and terms[0][1]==1 and prelude.refexpr(terms[0][0])==expected:checks.append(terms[0][0])
                else:checks.append(prelude.lin('Le',terms,expected))
            intervals.append({'lower':p['lower'],'upper':p['upper'],'checks':checks})
        r=Builder(ext,prelude.counter,prelude.facts);mapping=[None]*len(a['vars']);domains={};rows={}
        for i in fixed:mapping[i]=expression();domains[i]={'VarLower':[],'VarUpper':[]}
        for i,j in w['unchanged_coordinates']:mapping[i]=expression(0,{j:1});domains[i]={t:[[{t:j},F(1)]] for t in ('VarLower','VarUpper','VarInt')}
        for p,l in zip(pairs,layout):
            v,ww,y=p['source_v'],p['source_w'],p['target_y'];t=p['target_t'];z=l['variable'];aa,M,bb,c=(F(p['parameters'][k]) for k in ('a','M','b','c'))
            mapping[v]=expression(0,{z:1});mapping[ww]=expression(0,{z:1,t:-1})
            lo0,lo1=({'RowLower':i} for i in l['lower']);up0,up1=({'RowUpper':i} for i in l['upper'])
            domains[v]={'VarLower':[[lo0,F(1)],[{'VarLower':y},aa]],'VarUpper':[[up0,F(1)],[{'VarUpper':y},M]]}
            domains[ww]={'VarLower':[[lo1,F(1)],[{'VarUpper':y},bb]],'VarUpper':[[up1,F(1)],[{'VarLower':y},c]]}
            for i,ref in zip(p['source_rows'],[lo0,up0,lo1,up1]):rows[i]=[[ref,F(1)]]
        for i,row in enumerate(a['rows']):
            if row['sense']=='E':
                rows[i]=[[{'RowEq':j},F(c)] for j,c in w['target_equality_combination']] if i==w['dependent_source_equality'] else [[row_ref(b,row['name']),F(1)]]
        assert all(e is not None for e in mapping) and len(rows)==len(a['rows'])
        body=run_checks(r,a,mapping,reverse_claim,lambda i,t:domains[i][t],lambda i,wanted:rows[i],lambda wanted:[])
        reverse={'steps':prelude.steps,'end':{'IntervalLift':{'intervals':intervals,'body':body}}}
        claims.append(reverse_claim);blocks.append(reverse)
        counts.append({'integer':integer,'forward_obligations':len(forward['end']['Return']['checks']),'reverse_obligations':len(body['end']['Return']['checks']),
                       'forward_steps':len(f.steps),'reverse_prelude_steps':len(prelude.steps),'reverse_body_steps':len(r.steps)})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),
             'claims':4,'independent_intervals_per_reverse_claim':len(pairs),'extension_rows_per_reverse_claim':len(ext['rows'])-len(b['rows']),'affine_observations_per_claim':len(pairs),'exact_local_lift_samples':samples,'details':counts}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test23-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test23'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json'
    rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test23','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
       'claims':'Complete integer and LP correspondence with all3359 unchanged coordinates and all2467 signed observations t=v-w explicitly requested in both directions, and pointwise objective equality. All2467real interval lifts form one complete output point; no continuous bijection claimed.',
       'counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                d['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        d['negative_checks']=[]
        for name,reason in [('missing_middle_pair','Omits a lower-to-upper compatibility obligation in a middle independent interval.'),('wrong_lower','Changes a lower affine bound without establishing all exact compatibility pairs.'),('wrong_signed_lift','Restores w=z+t instead of w=z-t, violating the requested signed observation and complete original constraints.'),('wrong_signed_contract','Changes an affine observation while the independently supplied requested contract remains unchanged.')]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['IntervalLift']
            if name=='missing_middle_pair':lift['intervals'][1234]['checks'].pop(2)
            elif name=='wrong_lower':lift['intervals'][1234]['lower'][0]['constant']='1'
            elif name=='wrong_signed_lift':
                e=next(e for e in lift['body']['end']['Return']['map'] if len(e['terms'])==2 and any(c=='-1' for _,c in e['terms']))
                for term in e['terms']:
                    if term[1]=='-1':term[1]='1'
            else:bad['claims'][1]['affine_projection'][0][0]['constant']='1'
            path=out/(name+'.rpa');path.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
