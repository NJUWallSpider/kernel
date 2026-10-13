#!/usr/bin/env python3
"""Complete actual aggregate-gate tightening with explicit exact cover proofs."""
from fractions import Fraction as F
from pathlib import Path
from collections import Counter,ChainMap
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test19 import cases_le


class SparseBuilder(Builder):
    """Untrusted exact accumulator; avoids repeated copies of large support maps."""
    def lin(self,kind,terms,expected=None,constant=0):
        assert (kind=='Eq' and constant==0) or (kind=='Le' and constant<=0) or (kind=='Int' and F(constant).denominator==1)
        total=F(constant);coefficients={}
        for r,c in terms:
            c=F(c);k=self.kind(r);assert k=='Eq' or (kind=='Le' and k=='Le' and c>=0) or (kind=='Int' and k=='Int' and c.denominator==1)
            e=self.refexpr(r)
            if e[0]:total+=c*e[0]
            multiplier=c.numerator if c.denominator==1 else c
            for i,q in e[1].items():
                value=q.numerator if q.denominator==1 else q
                coefficients[i]=coefficients.get(i,0)+multiplier*value
        e=expression(total,coefficients)
        if expected is not None:assert e==expected,('exact sparse residual mismatch',e[0],expected[0],len(e[1]),len(expected[1]))
        ident=self.alloc();self.steps.append({'Lin':{'id':ident,'kind':kind,'constant':str(constant),'terms':[[r,str(c)] for r,c in terms]}});self.facts[ident]=(kind,e);return {'Local':ident}


def cases_le_shared(builder,wanted,variable,left,right):
    # Only the untrusted Python generator shares lookup dictionaries. The emitted
    # certificate still contains complete sibling derivations and ordinary refs.
    ident=builder.alloc();branches=[];split=expression(0,{variable:1})
    for side,callback in enumerate((left,right)):
        assumption=split if side==0 else expression(1,{variable:-1})
        child=SparseBuilder(builder.model,builder.counter,assumptions=builder.assumptions+[assumption]);child.facts=ChainMap({},builder.facts)
        ref=callback(child,{'Assumption':len(builder.assumptions)});assert child.kind(ref)=='Le' and child.refexpr(ref)==wanted
        branches.append({'steps':child.steps,'end':{'Witness':ref}})
    builder.steps.append({'Cases':{'id':ident,'kind':'Le','expression':expr_json(wanted),'split':expr_json(split),'integer':{'VarInt':variable},'left':branches[0],'right':branches[1]}});builder.facts[ident]=('Le',wanted);return {'Local':ident}


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(48417,2187,48417,2187)
    assert set(a['var_index'])==set(b['var_index']) and set(a['row_index'])==set(b['row_index'])
    forward=[expression(0,{a['var_index'][v['name']]:1}) for v in b['vars']];reverse=[expression(0,{b['var_index'][v['name']]:1}) for v in a['vars']];common=[[next(iter(e[1])),j] for j,e in enumerate(forward)]
    forward_ids=[next(iter(e[1])) for e in forward];reverse_ids=[next(iter(e[1])) for e in reverse]
    def rename(e,ids):return e[0],{ids[i]:c for i,c in e[1].items()}
    for i,j in common:assert a['vars'][i]==b['vars'][j] and a['vars'][i]['integer'] and a['vars'][i]['lower']==0 and a['vars'][i]['upper']==1
    assert rename(b['objective'],forward_ids)==a['objective']
    changes={d['row']:d for d in h['changes']};assert len(changes)==1975
    f=SparseBuilder(a);packing={}
    for d in h['packing_sources']:
        ref=row_ref(a,d['row']);row=a['rows'][a['row_index'][d['row']]];assert row['sense']=='E'
        if d['kind']=='unit_assignment_equality':assert row['rhs']==1 and all(c==1 for c in row['terms'].values());packing[d['row']]=(ref,set(row['terms']))
        else:
            negative=[i for i,c in row['terms'].items() if c==-1];assert len(negative)==1 and row['rhs']==0;z=negative[0];support={i for i,c in row['terms'].items() if c==1};assert len(support)+1==len(row['terms'])
            packing[d['row']]=(f.lin('Le',[[ref,F(1)],[{'VarUpper':z},F(1)]],expression(-1,{i:1 for i in support})),support)
    gatefacts={};subset_cache={};naive_cancellations=0;shared_cancellations=0
    def nonnegative_subset(base,width,mask):
        assert mask and mask.bit_length()<=width
        if mask&(mask-1)==0:return {'VarLower':base+mask.bit_length()-1}
        key=(base,width,mask)
        if key in subset_cache:return subset_cache[key]
        half=width//2;lower=mask&((1<<half)-1);upper=mask>>half
        if not lower:ref=nonnegative_subset(base+half,half,upper)
        elif not upper:ref=nonnegative_subset(base,half,lower)
        else:ref=f.lin('Le',[[nonnegative_subset(base,half,lower),F(1)],[nonnegative_subset(base+half,half,upper),F(1)]])
        subset_cache[key]=ref;return ref
    for name,d in changes.items():
        control=a['var_index'][d['control']];old=-F(d['old_coefficient']);new=-F(d['new_coefficient']);ref=row_ref(a,name);row=a['rows'][a['row_index'][name]];support=set(row['terms'])-{control}
        assert row['sense']=='L' and row['rhs']==0 and row['terms'][control]==-old and old==len(support) and 0<new<old and all(row['terms'][i]==1 for i in support)
        cover=Counter();terms=[]
        for rn in d['cover_rows']:
            r,S=packing[rn];terms.append([r,F(1)]);cover.update(S)
        for vn in d['individual_upper_bounds']:
            i=a['var_index'][vn];terms.append([{'VarUpper':i},F(1)]);cover[i]+=1
        assert len(d['cover_rows'])+len(d['individual_upper_bounds'])==new
        assert all(cover[i]>=1 for i in support)
        masks={}
        for i,c in cover.items():
            excess=c-(1 if i in support else 0)
            if excess:
                naive_cancellations+=1;key=(i//64,excess);masks[key]=masks.get(key,0)|(1<<(i%64))
        shared_cancellations+=len(masks)
        for (chunk,multiplier),mask in sorted(masks.items()):terms.append([nonnegative_subset(chunk*64,64,mask),F(multiplier)])
        bound=f.lin('Le',terms,expression(-new,{i:1 for i in support}));wanted=expression(0,{**{i:1 for i in support},control:-new})
        assert wanted==rename(row_fact(b['rows'][b['row_index'][name]],'RowUpper'),forward_ids)
        gatefacts[name]=cases_le_shared(f,wanted,control,lambda child,zero:child.lin('Le',[[ref,F(1)],[zero,old-new]],wanted),lambda child,one:child.lin('Le',[[bound,F(1)],[one,new]],wanted))
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;builder=SparseBuilder(inp) if back else f;checks=[]
        for i,v in enumerate(out['vars']):
            j=next(iter(mapping[i][1]));checks.extend([{'VarLower':j},{'VarUpper':j}])
            if integer:checks.append({'VarInt':j})
        for row in out['rows']:
            n=row['name'];typ=next(iter(row_ref(out,n)));wanted=rename(row_fact(row,typ),reverse_ids if back else forward_ids)
            if not back and n in changes:check=gatefacts[n];assert builder.refexpr(check)==wanted
            elif back and n in changes:
                d=changes[n];control=b['var_index'][d['control']];check=builder.lin('Le',[[row_ref(b,n),F(1)],[{'VarLower':control},F(d['new_coefficient'])-F(d['old_coefficient'])]],wanted)
            else:check=row_ref(inp,n);assert builder.refexpr(check)==wanted
            checks.append(check)
        assert rename(out['objective'],reverse_ids if back else forward_ids)==inp['objective'];checks.append('Exact')
        projection=[[j,i] for i,j in common] if back else common
        for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
        inverse=1 if index==0 else 0 if index==1 else None
        if inverse is not None:checks.extend(['Exact']*len(inp['vars']))
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':inverse});blocks.append({'steps':builder.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':48417,'target_variables':48417,'source_rows':2187,'target_rows':2187,'gate_tightenings':1975,'packing_sources':82,'naive_cancellation_refs':naive_cancellations,'shared_cancellation_refs':shared_cancellations,'subset_cache_entries':len(subset_cache),'forward_steps':len(f.steps),'claims':3,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test70-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test70'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 2\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test70','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete same-coordinate integer feasible-set bijection with exact objective and full inverse identities, plus objective-preserving target-LP inclusion into source LP. Every gate cover is an explicit linear combination of actual unchanged rows and bounds; no global strict LP claim.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_cover_premise','Drops a packing-cover premise, so the complete support upper bound no longer follows.'),('wrong_gate_branch','Omits the active binary assumption needed to scale the unconditional support bound.'),('missing_lp_nonnegativity','Omits the control lower bound required for LP reverse inclusion.'),('missing_inverse','Omits a coordinate from a requested full inverse identity.')]:
            bad=copy.deepcopy(cert)
            if name=='missing_cover_premise':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and len(s['Lin']['terms'])>100)['terms'].pop(0)
            elif name=='wrong_gate_branch':next(s['Cases'] for s in bad['blocks'][0]['steps'] if 'Cases' in s)['right']['steps'][0]['Lin']['terms'].pop()
            elif name=='missing_lp_nonnegativity':bad['blocks'][2]['steps'][0]['Lin']['terms'].pop()
            else:bad['blocks'][0]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 2\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
