#!/usr/bin/env python3
"""Untrusted exact proof of test54's full projection/objective correspondence.

All endpoint replacements are justified as one-sided inequalities. They are not
asserted forced, and no inverse or feasible-point bijection is requested.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder


def exact(kind,e):
    return not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0) or (kind=='Int' and e[0].denominator==1))


def fact(builder,kind,e,terms=(),constant=0,terminal=False):
    if terminal and exact(kind,e):return 'Exact'
    if len(terms)==1 and terms[0][1]==1 and not constant and builder.kind(terms[0][0])==kind and builder.refexpr(terms[0][0])==e:return terms[0][0]
    return builder.lin(kind,terms,e,constant)


def box(builder,e,terminal=False):
    terms=[];ceiling=e[0]
    for i,c in e[1].items():
        v=builder.model['vars'][i];bound=v['upper'] if c>0 else v['lower'];assert bound is not None,('unbounded box',v['name'],c)
        ceiling+=c*bound;terms.append([{'VarUpper' if c>0 else 'VarLower':i},abs(c)])
    assert ceiling<=0,('box not valid',e,ceiling)
    return fact(builder,'Le',e,terms,ceiling,terminal)


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(48738,21732,32793,20252)
    zeros={a['var_index'][n] for n in h['forced_zero_variables']}
    endpoints={a['var_index'][n]:F(v['value']) for n,v in h['endpoint_eliminations'].items()}
    aliases={a['var_index'][n]:a['var_index'][v] for n,v in h['merged_variables'].items()}
    leaves={a['var_index'][n]:v for n,v in h['leaf_definitions'].items()}
    removed=zeros|set(endpoints)|set(aliases)|set(leaves)
    assert len(removed)==15945 and removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']]
    reverse={}
    def recovery(i):
        if i in reverse:return reverse[i]
        n=a['vars'][i]['name']
        if n in b['var_index']:
            j=b['var_index'][n];assert a['vars'][i]==b['vars'][j];e=expression(0,{j:1})
        elif i in zeros:e=expression()
        elif i in endpoints:e=expression(endpoints[i])
        elif i in aliases:e=recovery(aliases[i])
        else:
            d=leaves[i];e=expression(F(d['constant']))
            for v,c in d['coefficients'].items():e=plus(e,recovery(a['var_index'][v]),F(c))
        reverse[i]=e;return e
    reverse=[recovery(i) for i in range(len(a['vars']))]
    f=Builder(a);zeroeq={}
    for n in h['original_fixed_zero_variables']:
        i=a['var_index'][n];assert a['vars'][i]['lower']==a['vars'][i]['upper']==0
        zeroeq[i]=f.eqpair({'VarUpper':i},{'VarLower':i})
    for hint in h['zero_sum_steps']:
        r=row_ref(a,hint['row']);e=f.refexpr(r);assert e[0]==0
        for n in hint['new_zeros']:
            i=a['var_index'][n];assert i not in zeroeq;c=e[1][i];terms=[[r,1/c]]
            for j,q in e[1].items():
                if j==i:continue
                if j in zeroeq:terms.append([zeroeq[j],-q/c])
                else:
                    assert a['vars'][j]['lower']==0 and q/c>=0
                    terms.append([{'VarLower':j},q/c])
            upper=f.lin('Le',terms,expression(0,{i:1}));zeroeq[i]=f.eqpair(upper,{'VarLower':i})
    assert set(zeroeq)==zeros
    graph={}
    for name,v,w in h['binary_identity_rows']:
        i,j=a['var_index'][v],a['var_index'][w];r=row_ref(a,name);e=f.refexpr(r);assert f.kind(r)=='Eq'
        c=e[1][i];terms=[[r,1/c]]+[[zeroeq[k],-q/c] for k,q in e[1].items() if k in zeroeq]
        eq=f.lin('Eq',terms,expression(0,{i:1,j:-1}))
        graph.setdefault(i,[]).append((j,eq,F(1)));graph.setdefault(j,[]).append((i,eq,F(-1)))
    aliaseq={}
    for i,j in aliases.items():
        pending=[(i,[])];seen=set()
        while pending:
            k,path=pending.pop()
            if k==j:break
            if k in seen:continue
            seen.add(k);pending.extend((n,path+[[r,c]]) for n,r,c in graph[k] if n not in seen)
        else:raise AssertionError(('missing identity path',i,j))
        aliaseq[i]=fact(f,'Eq',expression(0,{i:1,j:-1}),path)
    leafeq={}
    for i,d in leaves.items():
        r=row_ref(a,d['row']);e=f.refexpr(r);c=e[1][i]
        expected=expression(-F(d['constant']),{i:1,**{a['var_index'][n]:-F(q) for n,q in d['coefficients'].items()}})
        terms=[[r,1/c]]+[[zeroeq[j],-q/c] for j,q in e[1].items() if j in zeroeq]
        leafeq[i]=f.lin('Eq',terms,expected)

    def folded(e,terms,kind):
        # Each equality eliminates only its own coordinate; zero/leaf terms may
        # expose aliases, and aliases may expose monotone endpoint coordinates.
        constant=e[0];coefficients=dict(e[1])
        def add(r,m):
            nonlocal constant
            q=f.refexpr(r);constant+=m*q[0]
            for j,c in q[1].items():
                coefficients[j]=coefficients.get(j,F(0))+m*c
                if not coefficients[j]:del coefficients[j]
        for table in (zeroeq,leafeq,aliaseq):
            for i in list(coefficients):
                if i in table:
                    c=coefficients[i];r=table[i];terms.append([r,-c]);add(r,-c)
        for i,c in list(coefficients.items()):
            if i not in endpoints:continue
            assert kind=='Le',('endpoint in equality',i,c)
            value=endpoints[i];v=a['vars'][i]
            r={'VarLower':i} if c>0 else {'VarUpper':i}
            assert value==(v['lower'] if c>0 else v['upper'])
            terms.append([r,abs(c)]);add(r,abs(c))
        return expression(constant,coefficients),terms

    fbase=list(f.steps);ffacts=f.facts.copy();fcounter=f.counter[0]
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward
            builder=Builder(inp) if back else Builder(a,[fcounter],ffacts)
            if not back:builder.steps=list(fbase)
            checks=[];varbounds={};rowchecks={}
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    expected=plus(mul(e,sign),expression(-sign*value))
                    if not back:r={typ:next(iter(e[1]))}
                    elif exact('Le',expected):r='Exact'
                    else:r=box(builder,expected,True)
                    checks.append(r);varbounds[typ,i]=r
                if integer and v['integer']:
                    terms=[[{'VarInt':j},c] for j,c in e[1].items()]
                    checks.append(fact(builder,'Int',e,terms,e[0],True))
            def prove_row(n):
                if n in rowchecks:return rowchecks[n]
                row=out['rows'][out['row_index'][n]];typ=next(iter(row_ref(out,n)));kind='Eq' if typ=='RowEq' else 'Le'
                expected=substitute(row_fact(row,typ),mapping)
                if not back:
                    r=row_ref(a,n);computed,terms=folded(f.refexpr(r),[[r,F(1)]],kind)
                    assert computed==expected,('forward row',n,computed,expected)
                    result=fact(builder,kind,expected,terms,terminal=True)
                elif n in b['row_index']:
                    r=row_ref(b,n);assert builder.refexpr(r)==expected,('reverse retained row',n)
                    result=r
                elif exact(kind,expected):result='Exact'
                elif n in h['aggregate_row_certificates']:
                    d=h['aggregate_row_certificates'][n];terms=[]
                    for support,c in d['support_rows']:
                        r=prove_row(support)
                        if r=='Exact':r=fact(builder,'Le',substitute(row_fact(a['rows'][a['row_index'][support]],'RowUpper'),reverse),[],substitute(row_fact(a['rows'][a['row_index'][support]],'RowUpper'),reverse)[0])
                        terms.append([r,F(c)])
                    j=a['var_index'][d['nonnegative_variable']];r=varbounds['VarLower',j]
                    if r=='Exact':r=fact(builder,'Le',mul(reverse[j],-1),[], -reverse[j][0])
                    terms.append([r,F(d['slack_coefficient'])]);result=fact(builder,'Le',expected,terms,terminal=True)
                elif kind=='Le':result=box(builder,expected,True)
                else:result=builder.eqpair(box(builder,expected),box(builder,mul(expected,-1)))
                rowchecks[n]=result;return result
            checks.extend(prove_row(r['name']) for r in out['rows'])
            residual=plus(substitute(out['objective'],mapping),inp['objective'],-1)
            if back:assert exact('Eq',residual);checks.append('Exact')
            else:
                folded_objective,terms=folded(a['objective'],[],'Eq')
                assert folded_objective==substitute(b['objective'],forward)
                checks.append(fact(builder,'Eq',residual,terms,terminal=True))
            projection=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
            if back:projection=[[j,i] for i,j in projection]
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':None})
            blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'forced_zeros':len(zeros),'merged_copies':len(aliases),'leaf_definitions':len(leaves),'monotone_endpoints':len(endpoints),'obligations_by_claim':[len(b['end']['Return']['checks']) for b in blocks],'steps_by_claim':[len(b['steps']) for b in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test54-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test54'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test54','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete integer and continuous-relaxation projection correspondence on every retained original coordinate, preserving every attainable objective value in both directions. Monotone endpoints are canonical recoveries; no point bijection or affine inverse is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('wrong_endpoint','Changes the reverse recovery for an eliminated bounded coordinate.'),('missing_zero_premise','Omits a source-row premise establishing a forced zero.'),('missing_projection','Omits a required retained-coordinate observation.'),('wrong_objective','Omits a nonzero equality term from the complete objective correspondence proof.')]:
            bad=copy.deepcopy(cert)
            if name=='wrong_endpoint':next(e for e in bad['blocks'][1]['end']['Return']['map'] if not e['terms'] and e['constant']!='0')['constant']='-1'
            elif name=='missing_zero_premise':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and any(next(iter(r)).startswith('Row') for r,c in s['Lin']['terms']))['terms'].pop(0)
            elif name=='missing_projection':bad['blocks'][3]['end']['Return']['checks'].pop()
            else:next(s['Lin'] for s in reversed(bad['blocks'][0]['steps']) if 'Lin' in s)['terms'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
