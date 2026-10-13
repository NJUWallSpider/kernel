#!/usr/bin/env python3
"""Exact staged set-cover normalization, expanded into existing kernel rules."""
from collections import Counter,defaultdict
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test48 import Proof,emit_checks,sumexpr
from prepare_test23 import extend


def inspect(a,b,h):
    assert len(a['vars'])==63009 and len(a['rows'])==507
    assert a['objective'][0]==b['objective'][0]==0
    assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in a['vars'])
    assert len(a['objective'][1])==len(a['vars']) and set(a['objective'][1].values())=={F(1),F(2)}
    assert all(r['sense']=='G' and r['rhs']==1 and all(c==1 for c in r['terms'].values()) for r in a['rows'])
    supports=[set() for _ in a['vars']]
    for ri,row in enumerate(a['rows']):
        for i in row['terms']:supports[i].add(ri)
    active=set(range(len(a['vars'])));rows=set(range(len(a['rows'])));fixed=set();stages=[];counts=Counter()
    for hint in h['stages']:
        assert (len(rows),len(active))==(hint['input_rows'],hint['input_variables'])
        rowsets={r:set(a['rows'][r]['terms'])&active for r in rows};assert all(rowsets.values())
        singleton={a['row_index'][r]:a['var_index'][v] for r,v in hint['singleton_witnesses'].items()}
        assert singleton=={r:next(iter(vs)) for r,vs in rowsets.items() if len(vs)==1}
        newfixed={a['var_index'][v] for v in hint['fixed_one']};assert newfixed==set(singleton.values()) and not fixed&newfixed
        covered={a['row_index'][r] for r in hint['covered_rows']};assert covered=={r for r,vs in rowsets.items() if vs&newfixed}
        redundant={a['row_index'][r]:a['row_index'][w] for r,w in hint['redundant_row_witnesses'].items()};nextrows=rows-covered-set(redundant)
        assert set(redundant)<=rows-covered and all(w in nextrows and rowsets[w]<=rowsets[r] for r,w in redundant.items())
        empty={a['var_index'][v] for v in hint['empty_columns']};replacement={a['var_index'][v]:a['var_index'][w] for v,w in hint['column_replacements'].items()};following=active-newfixed-empty-set(replacement)
        assert len(newfixed)+len(empty)+len(replacement)+len(following)==len(active)
        assert empty=={v for v in active-newfixed if not supports[v]&nextrows}
        groups=defaultdict(list)
        for v,w in replacement.items():
            assert w in following and supports[v]&nextrows<=supports[w]&nextrows and a['objective'][1][w]<=a['objective'][1][v]
            groups[w].append(v)
        groups={w:[w]+sorted(vs) for w,vs in sorted(groups.items())}
        assert (len(nextrows),len(following))==(hint['output_rows'],hint['output_variables'])
        assert sum(len(supports[v]&nextrows) for v in following)==hint['output_nonzeros']
        stages.append({'active':active,'rows':rows,'rowsets':rowsets,'singleton':singleton,'fixed':newfixed,'covered':covered,'redundant':redundant,'empty':empty,'replacement':replacement,'following':following,'nextrows':nextrows,'groups':groups})
        counts.update(singleton_rows=len(singleton),covered_rows=len(covered),redundant_rows=len(redundant),empty_columns=len(empty),replacement_columns=len(replacement));active,rows=following,nextrows;fixed|=newfixed
    assert dict(counts)==h['certificate_checks']
    assert {a['vars'][i]['name'] for i in active}==set(h['final_unfixed_variables']) and {a['vars'][i]['name'] for i in fixed}==set(h['final_fixed_one_variables'])
    assert set(b['var_index'])=={a['vars'][i]['name'] for i in active|fixed} and set(b['row_index'])=={a['rows'][i]['name'] for i in rows}
    for var in b['vars']:
        i=a['var_index'][var['name']];assert var=={**a['vars'][i],'lower':F(1) if i in fixed else F(0)}
        assert b['objective'][1][b['var_index'][var['name']]]==a['objective'][1][i]
    for row in b['rows']:
        original=a['rows'][a['row_index'][row['name']]];expected={b['var_index'][a['vars'][i]['name']]:c for i,c in original['terms'].items() if i in active}
        assert row['sense']=='G' and row['rhs']==1 and row['terms']==expected
    evidence={'status':'ALL_FIELDS_EQUAL','source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'checked':dict(counts),'stages':[{'groups':len(s['groups']),'group_factors':sum(map(len,s['groups'].values())),'largest_group':max(map(len,s['groups'].values())),'following_variables':len(s['following']),'following_rows':len(s['nextrows'])} for s in stages]}
    return stages,evidence


def or_integer(p,z,layout,bits):
    # A balanced sum search finds a selected factor on the positive-sum branch.
    def split(cur,ids):
        total=sumexpr(bits[k]['expr'] for k in ids);integer=cur.lin('Int',[[bits[k]['integer'],F(1)] for k in ids],total)
        return {'expr':total,'integer':integer}
    def positive(cur,ids,guard):
        if len(ids)==1:
            k=ids[0];lower=cur.lin('Le',[[{'RowLower':layout['lower'][k]},F(1)],[guard,F(1)]],plus(expression(1),z,-1));eq=cur.eqpair({'RowUpper':layout['upper'][0]},lower)
            return {'Witness':cur.lin('Int',[[eq,F(1)]],z,constant=1)}
        mid=len(ids)//2;left,right=ids[:mid],ids[mid:]
        def zero(child,assumption):
            remaining=plus(expression(1),sumexpr(bits[k]['expr'] for k in right),-1);ref=child.lin('Le',[[guard,F(1)],[assumption,F(1)]],remaining)
            return positive(child,right,ref)
        return {'Witness':cur.cases('Int',z,split(cur,left),zero,lambda child,a:positive(child,left,a))}
    lo=p.lin('Le',[[{'RowLower':layout['lower'][0]},F(1)],[bits[0]['lower'],F(1)]],mul(z,-1))
    def zero(cur,guard):
        upper=cur.lin('Le',[[{'RowUpper':layout['upper'][1]},F(1)],[guard,F(1)]],z);eq=cur.eqpair(upper,lo)
        return {'Witness':cur.lin('Int',[[eq,F(1)]],z)}
    ids=list(range(len(bits)));integer=p.cases('Int',z,split(p,ids),zero,lambda cur,g:positive(cur,ids,g))
    return {'expr':z,'lower':lo,'upper':{'RowUpper':layout['upper'][0]},'integer':integer}


def forward_proof(a,b,stages,claim):
    p=Proof(a);current=[expression(0,{i:1}) for i in range(len(a['vars']))];bits={i:{'expr':e,'lower':{'VarLower':i},'upper':{'VarUpper':i},'integer':{'VarInt':i}} for i,e in enumerate(current)}
    rowfacts={i:{'RowLower':i} for i in range(len(a['rows']))};cost=p.lin('Le',[],expression());nested=[];c=a['objective'][1]
    for stage_no,s in enumerate(stages):
        fixed_eq={}
        for r,i in s['singleton'].items():
            if i not in fixed_eq:fixed_eq[i]=p.eqpair(bits[i]['upper'],rowfacts[r])
        intervals=[];group_order=list(s['groups']);oldbits={w:[bits[i] for i in s['groups'][w]] for w in group_order}
        for w in group_order:
            members=oldbits[w];total=sumexpr(v['expr'] for v in members);checks=[]
            for k,v in enumerate(members):
                checks.append(v['upper'])
                wanted=plus(v['expr'],total,-1);checks.append(p.prove('Le',wanted,[[other['lower'],F(1)] for j,other in enumerate(members) if j!=k]))
            intervals.append({'lower':[expr_json(v['expr']) for v in members],'upper':[expr_json(expression(1)),expr_json(total)],'checks':checks})
        previous_steps=p.steps;extended,layouts=extend(p.model,intervals);p=Proof(extended,p.counter,p.facts);dominance={};group_upper={}
        for w,layout in zip(group_order,layouts):
            z=expression(0,{layout['variable']:1});bits[w]=or_integer(p,z,layout,oldbits[w]);current[w]=z;group_upper[w]={'RowUpper':layout['upper'][1]}
            for k,i in enumerate(s['groups'][w]):dominance[i]={'RowLower':layout['lower'][k]}
        for i in s['fixed']:current[i]=expression(1)
        for i in s['empty']|set(s['replacement']):current[i]=expression()
        nextfacts={}
        for r in sorted(s['nextrows']):
            oldvars=s['rowsets'][r];multiplicity=Counter(s['replacement'].get(i,i) for i in oldvars);terms=[[rowfacts[r],F(1)]]+[[dominance[i],F(1)] for i in sorted(oldvars) if i in dominance]
            raw=plus(expression(1),sumexpr(mul(current[i],n) for i,n in multiplicity.items()),-1);ref=p.lin('Le',terms,raw);largest=max(multiplicity.values())
            wanted=plus(expression(1),sumexpr(current[i] for i in multiplicity),-1)
            if largest==1:nextfacts[r]=ref
            else:
                scaled=p.lin('Le',[[ref,F(1,largest)]]+[[bits[i]['lower'],1-F(n,largest)] for i,n in multiplicity.items() if n<largest],plus(expression(F(1,largest)),sumexpr(current[i] for i in multiplicity),-1))
                integer=p.lin('Int',[[bits[i]['integer'],F(-1)] for i in multiplicity],plus(wanted,expression(-1)))
                ident=p.alloc();p.steps.append({'Round':{'id':ident,'le':scaled,'integer':integer}});p.facts[ident]=('Le',wanted);nextfacts[r]={'Local':ident}
        terms=[[cost,F(1)]]+[[fixed_eq[i],-c[i]] for i in sorted(s['fixed'])]+[[bits[i]['lower'],c[i]] for i in sorted(s['empty'])]
        for w in group_order:
            terms.append([group_upper[w],c[w]])
            for i,oldbit in zip(s['groups'][w],oldbits[w]):
                if c[i]>c[w]:terms.append([oldbit['lower'],c[i]-c[w]])
        wanted=plus(sumexpr(mul(current[i],c[i]) for i in range(len(current))),a['objective'],-1);cost=p.lin('Le',terms,wanted)
        rowfacts=nextfacts;nested.append({'steps':previous_steps,'intervals':intervals})
        print(json.dumps({'stage':stage_no+1,'variables':len(p.model['vars']),'rows':len(p.model['rows']),'allocated_ids':p.counter[0]}),flush=True)
    mapping=[current[a['var_index'][v['name']]] for v in b['vars']];domains={}
    for i,v in enumerate(b['vars']):
        original=a['var_index'][v['name']]
        if v['lower']==v['upper']==1:continue
        for typ,key in [('VarLower','lower'),('VarUpper','upper'),('VarInt','integer')]:domains[(i,typ)]=bits[original][key]
    rows={i:rowfacts[a['row_index'][r['name']]] for i,r in enumerate(b['rows'])};body=emit_checks(p,b,mapping,claim,rows=rows,domains=domains,objective=cost)
    for stage in reversed(nested):body={'steps':stage['steps'],'end':{'IntervalLift':{'intervals':stage['intervals'],'body':body}}}
    return body,{'allocated_ids':p.counter[0],'intervals':sum(len(s['groups']) for s in stages),'generated_rows':len(p.model['rows'])-len(a['rows'])}


def reverse_proof(a,b,stages,claim):
    p=Proof(b);mapping=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']];refs={};removed={}
    for stage in stages:
        removed.update({r:('covered',None) for r in stage['covered']});removed.update({r:('redundant',w) for r,w in stage['redundant'].items()})
    def rowproof(ri):
        if ri in refs:return refs[ri]
        row=a['rows'][ri];wanted=substitute(row_fact(row,'RowLower'),mapping)
        if row['name'] in b['row_index']:result=p.prove('Le',wanted,[[row_ref(b,row['name']),F(1)]])
        elif removed[ri][0]=='covered':result=p.prove('Le',wanted)
        else:
            witness=rowproof(removed[ri][1]);extra=plus(wanted,p.refexpr(witness),-1);extra_ref=p.prove('Le',extra);result=p.lin('Le',[[witness,F(1)],[extra_ref,F(1)]],wanted)
        refs[ri]=result;return result
    rows={i:rowproof(i) for i in range(len(a['rows']))}
    return emit_checks(p,a,mapping,claim,rows=rows)


def prepare(a,b,h):
    stages,evidence=inspect(a,b,h)
    claims=[{'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[],'inverse':None},{'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}]
    f,counts=forward_proof(a,b,stages,claims[0]);r=reverse_proof(a,b,stages,claims[1]);return {'claims':claims,'blocks':[f,r]},evidence,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test87-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test87'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';a,b=parse_mps(source),parse_mps(target);h=json.loads((run/'output/audit.json').read_text());cert,evidence,counts=prepare(a,b,h)
    (out/'independent_structure.json').write_text(json.dumps(evidence,indent=2)+'\n');rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    receipt={'case_id':'test87','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Integer forward NonIncreasing and reverse Equal, complete actual models. Feasibility and infimum preservation, not all source choices or nonoptimal objective values.','counts':counts,'preparation_seconds':time.perf_counter()-started,'rpa_bytes':rpa.stat().st_size,'rpa_sha256':sha(rpa),'kernel_runs':[]}
    if args.kernel:
        kernel=args.kernel.resolve();receipt['kernel_binary_sha256']=sha(kernel)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(kernel)]+cmd,capture_output=True,text=True);receipt['kernel_runs'].append({'command':[str(kernel)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                receipt['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        receipt['status']='VERIFIED';receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))
if __name__=='__main__':main()
