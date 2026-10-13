#!/usr/bin/env python3
"""Complete untrusted exchange normalization using only existing exact rules.

Each stage extends one current point by prefix AND intervals, proves all new
binary facts with Cases, and preserves every original covering inequality.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time,sys
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test48 import Proof,sumexpr,emit_checks,fixed_bit
from prepare_test23 import extend


def bit(p,e,lo,hi,integer):return {'expr':e,'lower':lo,'upper':hi,'integer':integer}


def and_integrality(p,z,layout,bits):
    """An exhaustive short-circuit tree, not 2**len(bits) assignments."""
    def recurse(cur,index,fixed):
        if index==len(bits):
            lower=cur.lin('Le',[[{'RowLower':layout['lower'][1]},F(1)]]+[[r,F(-1)] for r in fixed],plus(expression(1),z,-1))
            upper=cur.lin('Le',[[{'RowUpper':layout['upper'][0]},F(1)],[fixed[0],F(1)]],plus(z,expression(-1)))
            eq=cur.eqpair(upper,lower)
            return {'Witness':cur.lin('Int',[[eq,F(1)]],z,constant=1)}
        b=bits[index]
        def zero(child,assumption):
            eq=fixed_bit(child,b,0,assumption)
            upper=child.lin('Le',[[{'RowUpper':layout['upper'][index]},F(1)],[eq,F(1)]],z)
            fixed_zero=child.eqpair(upper,{'RowLower':layout['lower'][0]})
            return {'Witness':child.lin('Int',[[fixed_zero,F(1)]],z)}
        def one(child,assumption):return recurse(child,index+1,fixed+[fixed_bit(child,b,1,assumption)])
        return {'Witness':cur.cases('Int',z,b,zero,one)}
    return recurse(p,0,[])['Witness']


def factors_one(p,z_eq,layout,bits):
    """If z=1, each factor equals one, using its actual upper bound."""
    result=[]
    for k,b in enumerate(bits):
        lower=p.lin('Le',[[{'RowUpper':layout['upper'][k]},F(1)],[z_eq,F(-1)]],plus(expression(1),b['expr'],-1))
        result.append(p.eqpair(b['upper'],lower))
    return result


def normalized_forward(a,b,h,claim):
    binary=[i for i,v in enumerate(a['vars']) if v['integer']]
    p=Proof(a);current=[expression(0,{i:1}) for i in range(len(a['vars']))]
    bits={i:bit(p,current[i],{'VarLower':i},{'VarUpper':i},{'VarInt':i}) for i in binary}
    old_count=sumexpr(current[i] for i in binary);count_eq=p.lin('Eq',[],expression())
    cover={a['row_index'][name]:row_ref(a,name) for name in h['covering_rows']}
    cardinality=row_ref(a,h['cardinality_row']);stages=[];count=h['cardinality_limit'];assert count==20
    for stage,removed_name in enumerate(h['removed_binary_variables']):
        removed=a['var_index'][removed_name];candidates=[a['var_index'][name] for name in h['retained_dominator_witnesses'][removed_name]]
        assert len(candidates)==len(set(candidates))==count and removed not in candidates
        factors=[bits[removed]]+[bits[i] for i in candidates]
        intervals=[]
        for j in range(1,count+1):
            prefix=factors[:j+1];lower=plus(sumexpr(x['expr'] for x in prefix),expression(1-len(prefix)));checks=[]
            for is_sum in [False,True]:
                for k,x in enumerate(prefix):
                    wanted=plus(lower if is_sum else expression(),x['expr'],-1)
                    terms=[[v['upper'],F(1)] for l,v in enumerate(prefix) if l!=k] if is_sum else [[x['lower'],F(1)]]
                    checks.append(p.prove('Le',wanted,terms))
            intervals.append({'lower':[expr_json(expression()),expr_json(lower)],'upper':[expr_json(x['expr']) for x in prefix],'checks':checks})
        pre_steps=p.steps;ext,layout=extend(p.model,intervals)
        for j,l in enumerate(layout):
            name=f'normalization_{stage}_{j}';ext['vars'][l['variable']]['name']=name;ext['var_index'][name]=l['variable']
        p=Proof(ext,p.counter,p.facts);prefix_bits=[bits[removed]]
        for j,l in enumerate(layout):
            z=expression(0,{l['variable']:1});old_factors=factors[:j+2]
            integer=and_integrality(p,z,l,old_factors)
            upper=p.lin('Le',[[{'RowUpper':l['upper'][0]},F(1)],[factors[0]['upper'],F(1)]],plus(z,expression(-1)))
            prefix_bits.append(bit(p,z,{'RowLower':l['lower'][0]},upper,integer))
        last=prefix_bits[-1];subset={removed,*candidates}
        subset_upper=p.lin('Le',[[cardinality,F(1)]]+[[bits[i]['lower'],F(1)] for i in binary if i not in subset],plus(sumexpr(current[i] for i in subset),expression(-count)))
        scaled=p.lin('Le',[[subset_upper,F(1)]]+[[{'RowUpper':ri},F(1)] for ri in layout[-1]['upper']],plus(mul(last['expr'],count+1),expression(-count)))
        fractional=p.lin('Le',[[scaled,F(1,count+1)]],plus(last['expr'],expression(F(-count,count+1))))
        ident=p.alloc();p.steps.append({'Round':{'id':ident,'le':fractional,'integer':last['integer']}});p.facts[ident]=('Le',last['expr'])
        last_zero=p.eqpair({'Local':ident},last['lower'])
        swap_nonnegative=[]
        for j,candidate in enumerate(candidates):
            prev,nxt=prefix_bits[j:j+2];w=bits[candidate];difference=plus(nxt['expr'],prev['expr'],-1)
            if j==0:nonnegative={'RowUpper':layout[j]['upper'][0]}
            else:
                def next_zero(cur,assumption):
                    eq=fixed_bit(cur,nxt,0,assumption)
                    return {'Witness':cur.lin('Le',[[eq,F(1)],[prev['lower'],F(1)]],difference)}
                def next_one(cur,assumption):
                    eq=fixed_bit(cur,nxt,1,assumption)
                    fixed=factors_one(cur,eq,layout[j],factors[:j+2])
                    terms=[[{'RowLower':layout[j-1]['lower'][1]},F(1)]]+[[r,F(-1)] for r in fixed[:-1]]+[[eq,F(1)]]
                    return {'Witness':cur.lin('Le',terms,difference)}
                nonnegative=p.cases('Le',difference,nxt,next_zero,next_one)
            swap_nonnegative.append(nonnegative)
            updated=plus(w['expr'],difference,-1);wanted=plus(updated,expression(-1))
            def w_zero(cur,assumption):
                weq=fixed_bit(cur,w,0,assumption)
                nupper=cur.lin('Le',[[{'RowUpper':layout[j]['upper'][-1]},F(1)],[weq,F(1)]],nxt['expr'])
                neq=cur.eqpair(nupper,nxt['lower'])
                return {'Witness':cur.lin('Le',[[prev['upper'],F(1)],[weq,F(1)],[neq,F(-1)]],wanted)}
            def w_one(cur,assumption):
                weq=fixed_bit(cur,w,1,assumption)
                def p_zero(child,guard):
                    peq=fixed_bit(child,prev,0,guard)
                    return {'Witness':child.lin('Le',[[weq,F(1)],[peq,F(1)],[nxt['lower'],F(1)]],wanted)}
                def p_one(child,guard):
                    peq=fixed_bit(child,prev,1,guard)
                    fixed=[peq] if j==0 else factors_one(child,peq,layout[j-1],factors[:j+1])
                    lower=child.lin('Le',[[{'RowLower':layout[j]['lower'][1]},F(1)]]+[[r,F(-1)] for r in fixed]+[[weq,F(-1)]],plus(expression(1),nxt['expr'],-1))
                    return {'Witness':child.lin('Le',[[lower,F(1)],[peq,F(1)],[weq,F(1)]],wanted)}
                return {'Witness':cur.cases('Le',wanted,prev,p_zero,p_one)}
            upper=p.cases('Le',wanted,w,w_zero,w_one)
            lower=p.lin('Le',[[w['lower'],F(1)],[nonnegative,F(1)]],mul(updated,-1))
            integer=p.lin('Int',[[w['integer'],F(1)],[prev['integer'],F(1)],[nxt['integer'],F(-1)]],updated)
            current[candidate]=updated;bits[candidate]=bit(p,updated,lower,upper,integer)
        current[removed]=expression()
        bits[removed]=bit(p,expression(),p.lin('Le',[],expression()),p.lin('Le',[],expression(-1),constant=-1),p.lin('Int',[],expression()))
        count_eq=p.lin('Eq',[[count_eq,F(1)],[last_zero,F(-1)]],plus(sumexpr(current[i] for i in binary),old_count,-1))
        cardinality=p.lin('Le',[[row_ref(a,h['cardinality_row']),F(1)],[count_eq,F(1)]],plus(sumexpr(current[i] for i in binary),expression(-count)))
        for ri,old_ref in list(cover.items()):
            row=a['rows'][ri];av=row['terms'].get(removed,F(0));terms=[[old_ref,F(1)],[last_zero,av]]
            for candidate,ref in zip(candidates,swap_nonnegative):
                delta=row['terms'].get(candidate,F(0))-av;assert delta>=0
                if delta:terms.append([ref,delta])
            wanted=substitute(row_fact(row,'RowLower'),current)
            cover[ri]=p.lin('Le',terms,wanted)
        stages.append({'steps':pre_steps,'intervals':intervals})
    group_members=h['aggregated_binary_groups'];mapping=[];domains={};source_y=a['var_index']['x151']
    for oi,var in enumerate(b['vars']):
        ids=[a['var_index'][name] for name in group_members[var['name']]] if var['name'] in group_members else [a['var_index'][var['name']]]
        mapping.append(sumexpr(current[i] for i in ids))
        if ids==[source_y]:continue
        for typ,key in [('VarLower','lower'),('VarUpper','upper'),('VarInt','integer')]:
            kind='Int' if typ=='VarInt' else 'Le';expected=mapping[-1] if kind=='Int' else mul(mapping[-1],-1) if typ=='VarLower' else plus(mapping[-1],expression(-len(ids)))
            domains[(oi,typ)]=p.lin(kind,[[bits[i][key],F(1)] for i in ids],expected)
    rows={b['row_index'][name]:cover[a['row_index'][name]] for name in h['covering_rows']};rows[b['row_index'][h['cardinality_row']]]=cardinality
    objective=p.lin('Eq',[[count_eq,F('0.00001')]],plus(substitute(b['objective'],mapping),a['objective'],-1));p.add('Eq',count_eq)
    body=emit_checks(p,b,mapping,claim,rows=rows,domains=domains,objective=objective)
    for stage in reversed(stages):body={'steps':stage['steps'],'end':{'IntervalLift':{'intervals':stage['intervals'],'body':body}}}
    return body,{'stages':len(stages),'intervals':20*len(stages),'rows':len(p.model['rows'])-len(a['rows']),'allocated_ids':p.counter[0]}


def reverse_aggregation(a,b,h,claim):
    m=copy.deepcopy(b);menus=[];groups={};pre=Proof(b)
    for name,names in h['aggregated_binary_groups'].items():
        target=b['var_index'][name];start=len(m['vars']);menus.append({'maximum_index':2,'activation':expr_json(expression(1)),'index':expr_json(expression(0,{target:1})),'checks':['Exact','Exact','Exact',{'VarLower':target},{'VarUpper':target},'Exact']})
        for j in range(3):m['vars'].append({'name':f'menu_{target}_{j}','integer':True,'lower':F(0),'upper':F(1)})
        rows=[]
        for terms,rhs in [({start:F(1),start+1:F(1),start+2:F(1)},F(1)),({target:F(-1),start+1:F(1),start+2:F(2)},F(0))]:
            ri=len(m['rows']);n=f'menu_row_{ri}';m['rows'].append({'name':n,'sense':'E','rhs':rhs,'terms':terms});m['row_index'][n]=ri;rows.append(ri)
        groups[name]={'start':start,'rows':rows,'names':names}
    p=Proof(m);mapping=[];domains={};removed=set(h['removed_binary_variables']);member={n:(g,j) for g in groups.values() for j,n in enumerate(g['names'])}
    for i,var in enumerate(a['vars']):
        name=var['name']
        if name in removed:mapping.append(expression())
        elif name in member:
            g,j=member[name];s=g['start'];mapping.append(expression(0,{s+1:F(1),s+2:F(1)}) if j==0 else expression(0,{s+2:F(1)}))
            if j==0:
                domains[(i,'VarLower')]=p.lin('Le',[[{'VarLower':s+1},F(1)],[{'VarLower':s+2},F(1)]],mul(mapping[-1],-1))
                domains[(i,'VarUpper')]=p.lin('Le',[[{'RowEq':g['rows'][0]},F(1)],[{'VarLower':s},F(1)]],plus(mapping[-1],expression(-1)))
        else:mapping.append(expression(0,{b['var_index'][name]:F(1)}))
    rows={}
    for i,row in enumerate(a['rows']):
        typ=next(iter(row_ref(a,row['name'])));raw=row_fact(row,typ);wanted=substitute(raw,mapping)
        terms=[[row_ref(b,row['name']),F(1)]]
        for g in groups.values():
            coefficient=raw[1].get(a['var_index'][g['names'][0]],F(0));assert coefficient==raw[1].get(a['var_index'][g['names'][1]],F(0))
            if coefficient:terms.append([{'RowEq':g['rows'][1]},coefficient])
        rows[i]=p.lin('Le' if typ!='RowEq' else 'Eq',terms,wanted)
    objective=p.lin('Eq',[[{'RowEq':g['rows'][1]},F('0.00001')] for g in groups.values()],plus(substitute(a['objective'],mapping),b['objective'],-1))
    count=p.lin('Eq',[[{'RowEq':g['rows'][1]},F(1)] for g in groups.values()],plus(sumexpr(mapping[i] for i,v in enumerate(a['vars']) if v['integer']),sumexpr(expression(0,{i:F(1)}) for i,v in enumerate(b['vars']) if v['integer']),-1));p.add('Eq',count)
    body=emit_checks(p,a,mapping,claim,rows=rows,domains=domains,objective=objective)
    return {'steps':pre.steps,'end':{'MenuLift':{'menus':menus,'body':body}}}


def prepare(a,b,h):
    ca=sumexpr(expression(0,{i:1}) for i,v in enumerate(a['vars']) if v['integer']);cb=sumexpr(expression(0,{i:1}) for i,v in enumerate(b['vars']) if v['integer']);y=(a['var_index']['x151'],b['var_index']['x151'])
    forward={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[list(y)],'affine_projection':[[expr_json(ca),expr_json(cb)]],'inverse':None}
    reverse={**forward,'reverse':True,'projection':[list(y[::-1])],'affine_projection':[[expr_json(cb),expr_json(ca)]]}
    f,counts=normalized_forward(a,b,h,forward);r=reverse_aggregation(a,b,h,reverse)
    return {'claims':[forward,reverse],'blocks':[f,r]},counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test47-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test47'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'));from audit_normalization_47_48 import inspect47
    a,b=parse_mps(source),parse_mps(target);h=json.loads(audit.read_text());inspect47(a,b,h)
    cert,counts=prepare(a,b,h);rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    receipt={'case_id':'test47','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Both integer directions preserve every attainable objective value, original continuous y and total binary cardinality; no named-choice identity, bijection or LP claim.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        kernel=args.kernel.resolve();receipt['kernel_binary_sha256']=sha(kernel)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            proc=subprocess.run([str(kernel)]+cmd,capture_output=True,text=True);receipt['kernel_runs'].append({'command':[str(kernel)]+cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                receipt['status']=json.loads(proc.stdout).get('status','EXECUTION_FAILED') if proc.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');raise SystemExit(proc.stdout+proc.stderr)
        receipt['status']='VERIFIED';receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
