#!/usr/bin/env python3
"""Derive real test84 parity fixation using generic Lin/Int/Round/EqPair.

The side-audit supplies only selected original row names. Every parity identity,
fixed value, remaining variable, actual model and inverse map is checked exactly.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test88 import Builder


def rounded(builder,le,integer):
    a=builder.refexpr(le);z=builder.refexpr(integer)
    assert builder.kind(le)=='Le' and builder.kind(integer)=='Int' and a[1]==z[1]
    d=a[0]-z[0];ceil=-((-d.numerator)//d.denominator)
    e=expression(z[0]+ceil,z[1]);i=builder.alloc();builder.steps.append({'Round':{'id':i,'le':le,'integer':integer}});builder.facts[i]=('Le',e);return {'Local':i}


def prepare(source,target,audit):
    a=parse_mps(source);b=parse_mps(target);assert len(a['vars'])==200 and len(a['rows'])==100 and len(b['vars'])==len(b['rows'])==1
    f=Builder(a);fixed={};values={}
    for hint in audit['modular_certificates']:
        j=a['var_index'][hint['variable']];assert a['vars'][j]['integer'] and a['vars'][j]['lower']==0 and a['vars'][j]['upper']==1
        combined=expression();row_terms=[]
        for name in hint['rows']:
            ref=row_ref(a,name);assert 'RowEq' in ref;combined=plus(combined,f.refexpr(ref));row_terms.append([ref,F(1,2)])
        assert combined[0].denominator==1 and all(c.denominator==1 for c in combined[1].values())
        rhs=-combined[0];v=int(rhs)%2
        assert combined[1][j].numerator%2==1 and all(i==j or c.numerator%2==0 for i,c in combined[1].items())
        assert rhs==F(hint['combined_rhs']) and v==hint['forced_value']
        terms=row_terms
        for i,c in combined[1].items():
            m=(F(1)-c)/2 if i==j else -c/2
            assert m.denominator==1
            if m:terms.append([{'VarInt':i},m])
        integer=f.lin('Int',terms,expression(-F(v,2),{j:F(1,2)}),constant=(rhs-v)/2)
        if v==0:
            le=f.lin('Le',[[{'VarUpper':j},F(1,2)]])
            rounded_le=rounded(f,le,integer)
            upper=f.lin('Le',[[rounded_le,F(2)]],expression(0,{j:1}))
            fixed[j]=f.eqpair(upper,{'VarLower':j})
        else:
            negative_int=f.lin('Int',[[integer,F(-1)]],expression(F(1,2),{j:F(-1,2)}))
            le=f.lin('Le',[[{'VarLower':j},F(1,2)]])
            rounded_le=rounded(f,le,negative_int)
            lower=f.lin('Le',[[rounded_le,F(2)]],expression(1,{j:-1}))
            fixed[j]=f.eqpair({'VarUpper':j},lower)
        values[j]=F(v)
    assert len(fixed)==100
    # Every remaining source coordinate is solved from an actual equality with
    # one unproved coordinate; no numerical solve or parity theorem is trusted.
    for row in a['rows']:
        unknown=[i for i in row['terms'] if i not in fixed]
        assert len(unknown)==1 and row['sense']=='E'
        j=unknown[0];pivot=row['terms'][j]
        value=(row['rhs']-sum(c*values[i] for i,c in row['terms'].items() if i!=j))/pivot
        terms=[[row_ref(a,row['name']),1/pivot]]+[[fixed[i],-c/pivot] for i,c in row['terms'].items() if i!=j]
        fixed[j]=f.lin('Eq',terms,expression(-value,{j:1}));values[j]=value
    assert len(fixed)==len(a['vars'])
    assert {a['vars'][i]['name']:str(v) for i,v in values.items()}=={n:str(F(v)) for n,v in audit['original_unique_assignment'].items()}
    optimum=a['objective'][0]+sum(c*values[i] for i,c in a['objective'][1].items());assert optimum==37
    forward=[expression(optimum)];reverse=[expression(values[i]) for i in range(len(a['vars']))]
    r=Builder(b)
    def checks(builder,output,mapping,fixes,inverse_map):
        inp=builder.model;result=[]
        def check(kind,e):
            if not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1)):
                result.append('Exact');return
            terms=[[fixes[i],c] for i,c in e[1].items()]
            result.append(builder.lin(kind,terms,e))
        for i,v in enumerate(output['vars']):
            if v['lower'] is not None:check('Le',plus(expression(v['lower']),mapping[i],-1))
            if v['upper'] is not None:check('Le',plus(mapping[i],expression(-v['upper'])))
            if v['integer']:check('Int',mapping[i])
        for row in output['rows']:
            typ=next(iter(row_ref(output,row['name'])))
            check('Eq' if row['sense']=='E' else 'Le',substitute(row_fact(row,typ),mapping))
        check('Eq',plus(substitute(output['objective'],mapping),inp['objective'],-1))
        for i,e in enumerate(inverse_map):check('Eq',plus(substitute(e,mapping),expression(0,{i:1}),-1))
        return result
    fchecks=checks(f,b,forward,fixed,reverse)
    targetfix=row_ref(b,b['rows'][0]['name']);assert r.refexpr(targetfix)==expression(-37,{0:1})
    rchecks=checks(r,a,reverse,{0:targetfix},forward)
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':1},{'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':0}]
    cert={'claims':claims,'blocks':[{'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':fchecks}}},{'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':rchecks}}}]}
    return cert,{'source_variables':200,'target_variables':1,'source_rows':100,'target_rows':1,'claims':2,'parity_fixings':100,'equality_fixings':100,'obligations_by_claim':[len(fchecks),len(rchecks)],'steps_by_claim':[len(f.steps),len(r.steps)]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test84-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test84'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(source,target,json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,indent=2)+'\n');request.write_text(json.dumps(cert['claims'],indent=2)+'\n')
    d={'case_id':'test84','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Mixed-integer feasible-set bijection to the actual singleton target; pointwise objective equality and both inverse identities. Source uniqueness established by exact parity/rounding and equality deductions, not by a parity theorem or an unverified assignment. LP equality is not requested.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                d['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']}
        d['negative_checks']=[]
        for name,reason in [('bad_parity_multiplier','Changes one selected original equality multiplier, destroying the integer rounding identity.'),('bad_reconstruction','Changes one reverse-map original coordinate, violating the complete source obligations or inverse identity.')]:
            bad=copy.deepcopy(cert)
            if name=='bad_parity_multiplier':bad['blocks'][0]['steps'][0]['Lin']['terms'][0][1]='0'
            else:bad['blocks'][1]['end']['Return']['map'][0]['constant']='1'
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,indent=2)+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID'
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))

if __name__=='__main__':main()
