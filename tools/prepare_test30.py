#!/usr/bin/env python3
"""Full actual absolute-value/alias/private-binary projection, checked by the RPX kernel."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test54 import fact,box,exact
from prepare_test70 import SparseBuilder
from prepare_test23 import extend


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(35378,16516,32337,14717)
    aliases={a['var_index'][n]:a['var_index'][r] for n,r in h['alias_eliminations']['column_to_representative'].items() if n!=r};assert len(aliases)==620
    aux={a['var_index'][d['variable']]:d for d in h['auxiliary_eliminations']};singles={a['var_index'][n] for d in h['singleton_eliminations'] for n in d['removed_variables']};removed=set(aliases)|set(aux)|singles
    assert (len(aux),len(singles),len(removed))==(961,1460,3041) and removed=={i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']}
    assert not removed&set(a['objective'][1]);common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars'])]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(0,{i:1}) for i,j in common];reverse=[None]*len(a['vars'])
    for i,v in enumerate(a['vars']):
        if i not in removed:reverse[i]=expression(0,{b['var_index'][v['name']]:1})
        elif i in aliases:reverse[i]=expression(0,{b['var_index'][a['vars'][aliases[i]]['name']]:1})
        else:reverse[i]=expression()
    projected={};singleton_domains={}
    for d in h['singleton_eliminations']:
        row=a['rows'][a['row_index'][d['row']]];ids={a['var_index'][n] for n in d['removed_variables']};first=a['var_index'][d['reconstruction_variable']]
        assert row['sense']=='E' and row['rhs']==0 and first in ids and all(row['terms'][i]==1 for i in ids)
        e=substitute(expression(0,{i:-c for i,c in row['terms'].items() if i not in ids}),reverse);reverse[first]=e;singleton_domains[first]=d['row'];projected[d['row']]=ids
    duplicates={d['removed_row']:d['retained_row'] for d in h['duplicate_row_removals']}
    def retained_name(n):
        while n in duplicates:n=duplicates[n]
        return n
    interval_specs=[];interval_by_aux={};special_forward={};aux_reverse_rows={}
    for i,d in aux.items():
        ur=a['rows'][a['row_index'][d['upper_row']]];assert ur['sense']=='G' and ur['terms'][i]==-1
        upper=substitute(expression(-ur['rhs'],{j:c for j,c in ur['terms'].items() if j!=i}),reverse)
        if not d['lower_rows']:
            assert a['vars'][i]['lower']==0 and a['vars'][i]['upper'] is None
            special_forward[d['upper_row']]=[[row_ref(a,d['upper_row']),F(1)],[{'VarLower':i},F(1)]];continue
        assert len(d['lower_rows'])==2 and a['vars'][i]['lower'] is None and a['vars'][i]['upper'] is None
        lowers=[]
        for rn in d['lower_rows']:
            lr=a['rows'][a['row_index'][rn]];assert lr['sense']=='L' and lr['terms'][i]==-1
            lowers.append(substitute(expression(-lr['rhs'],{j:c for j,c in lr['terms'].items() if j!=i}),reverse))
        assert lowers[0]==mul(lowers[1],-1)
        interval_by_aux[i]=len(interval_specs);interval_specs.append((lowers,[upper],[d['upper_row'],d['additional_row']]))
        for name,lr in zip([d['upper_row'],d['additional_row']],d['lower_rows']):special_forward[name]=[[row_ref(a,d['upper_row']),F(1)],[row_ref(a,lr),F(1)]]
    assert len(interval_specs)==930
    claims=[];blocks=[]
    for integer in (True,False):
        f=SparseBuilder(a);alias_eq={};graph={}
        for rn in h['alias_eliminations']['removed_equality_rows']:
            ref=row_ref(a,rn);e=f.refexpr(ref);assert f.kind(ref)=='Eq' and e[0]==0 and len(e[1])==2;(i,c),(j,d)=e[1].items();assert c==-d and abs(c)==1
            graph.setdefault(i,[]).append((j,ref,1/c));graph.setdefault(j,[]).append((i,ref,1/d))
        for root in sorted(set(aliases.values())):
            seen={root};todo=[root]
            while todo:
                j=todo.pop()
                for i,ref,scale_at_j in graph.get(j,[]):
                    if i in seen:continue
                    assert aliases[i]==root;terms=[[ref,-scale_at_j]]
                    if j!=root:terms.append([alias_eq[j],F(1)])
                    alias_eq[i]=fact(f,'Eq',expression(0,{i:1,root:-1}),terms);seen.add(i);todo.append(i)
        assert set(alias_eq)==set(aliases)
        def corrected(kind,wanted,terms):
            raw=expression()
            for r,c in terms:raw=plus(raw,f.refexpr(r),c)
            terms=terms+[[alias_eq[i],-c] for i,c in raw[1].items() if i in aliases]
            return fact(f,kind,wanted,terms,terminal=True)
        checks=[]
        for j,v in enumerate(b['vars']):
            i=common[j][0]
            if v['lower'] is not None:checks.append({'VarLower':i})
            if v['upper'] is not None:checks.append({'VarUpper':i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for row in b['rows']:
            rn=row['name'];typ=next(iter(row_ref(b,rn)));wanted=substitute(row_fact(row,typ),forward);kind='Eq' if typ=='RowEq' else 'Le'
            if rn in special_forward:terms=special_forward[rn]
            elif rn in projected:terms=[[row_ref(a,rn),F(1)]]+[[{'VarLower':i},F(1)] for i in sorted(projected[rn])]
            else:terms=[[row_ref(a,rn),F(1)]]
            checks.append(corrected(kind,wanted,terms))
        assert substitute(b['objective'],forward)==a['objective'];checks.append('Exact');checks.extend(['Exact']*len(common))
        claim={'reverse':False,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':common,'inverse':None};claims.append(claim);blocks.append({'steps':f.steps,'end':{'Return':{'map':[expr_json(e) for e in forward],'checks':checks}}})
        pre=SparseBuilder(b);intervals=[]
        for lows,ups,names in interval_specs:
            refs=[]
            for lower,name in zip(lows,names):
                wanted=plus(lower,ups[0],-1);ref=row_ref(b,retained_name(name));assert pre.refexpr(ref)==wanted;refs.append(ref)
            intervals.append({'lower':[expr_json(e) for e in lows],'upper':[expr_json(e) for e in ups],'checks':refs})
        extended,layout=extend(b,intervals);r=SparseBuilder(extended,pre.counter,pre.facts);mapping=list(reverse);rowproof={}
        for i,d in aux.items():
            if i not in interval_by_aux:continue
            k=interval_by_aux[i];mapping[i]=expression(0,{layout[k]['variable']:1});rowproof[d['upper_row']]={'RowUpper':layout[k]['upper'][0]}
            for rn,ri in zip(d['lower_rows'],layout[k]['lower']):rowproof[rn]={'RowLower':ri}
        checks=[]
        for i,v in enumerate(a['vars']):
            e=mapping[i]
            for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                if value is None:continue
                wanted=plus(mul(e,sign),expression(-sign*value))
                if i in singleton_domains and typ=='VarLower':
                    rn=retained_name(singleton_domains[i])
                    if rn in b['row_index']:ref=row_ref(b,rn);assert r.refexpr(ref)==wanted
                    else:ref=box(r,wanted,True)
                else:ref=box(r,wanted,True)
                checks.append(ref)
            if integer and v['integer']:checks.append(fact(r,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
        for row in a['rows']:
            rn=row['name'];typ=next(iter(row_ref(a,rn)));kind='Eq' if typ=='RowEq' else 'Le';wanted=substitute(row_fact(row,typ),mapping)
            if exact(kind,wanted):ref='Exact'
            elif rn in rowproof:ref=rowproof[rn];assert r.refexpr(ref)==wanted
            else:
                name=retained_name(rn);ref=row_ref(b,name);assert r.kind(ref)==kind and r.refexpr(ref)==wanted,(rn,name,kind)
            checks.append(ref)
        assert substitute(a['objective'],mapping)==b['objective'];checks.append('Exact');checks.extend(['Exact']*len(common))
        claim={'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in common],'inverse':None};claims.append(claim);body={'steps':r.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}};blocks.append({'steps':pre.steps,'end':{'IntervalLift':{'intervals':intervals,'body':body}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':35378,'target_variables':32337,'source_rows':16516,'target_rows':14717,'free_auxiliary_intervals':930,'nonnegative_auxiliaries':31,'aliases':620,'private_binaries':1460,'singleton_rows':640,'box_redundancies':220,'duplicates':29,'claims':4}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test30-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test30'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test30','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Four complete objective-preserving integer and LP projection directions with every retained-coordinate observation. Actual source equalities prove aliases and private-binary projection; checked joint real intervals restore all 930 free auxiliaries. Every source domain and row is checked; no bijection is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_alias','Drops an actual alias equality premise.'),('wrong_interval','Changes an interval endpoint while keeping its checked premise unchanged.'),('missing_private_bound','Omits a nonnegative private-variable premise from a projected row.'),('missing_projection','Omits a requested retained-coordinate observation.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_alias':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Eq' and len(s['Lin']['terms'])>1)['terms'].pop()
            elif name=='wrong_interval':bad['blocks'][1]['end']['IntervalLift']['intervals'][0]['lower'][0]['constant']='1'
            elif name=='missing_private_bound':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le' and any(isinstance(r,dict) and 'VarLower' in r for r,c in s['Lin']['terms']))['terms'].pop()
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
