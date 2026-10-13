#!/usr/bin/env python3
"""Actual LP pair: complete integer identity and strict relaxation tightening."""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import argparse,copy,json,subprocess,time
from audit_menus import lp_model
from prepare_affine import row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test70 import SparseBuilder,cases_le_shared


def prepare(a,b):
    n=len(a['vars']);assert (n,len(a['rows']),len(b['vars']),len(b['rows']))==(4914,13206,4914,12450)
    ids=[a['var_index'][v['name']] for v in b['vars']];rev=[b['var_index'][v['name']] for v in a['vars']]
    def rename(e,indices):return expression(e[0],{indices[i]:c for i,c in e[1].items()})
    assert all(a['vars'][i]==b['vars'][j] for j,i in enumerate(ids)) and rename(b['objective'],ids)==a['objective']
    resources=[r for r in a['rows'] if r['rhs']==3 and all(not a['vars'][i]['integer'] and c==1 for i,c in r['terms'].items())]
    incident=defaultdict(list)
    for r in resources:
        for i in r['terms']:incident[i].append(r)
    pairs={frozenset(r['terms']):r['name'] for r in a['rows'] if r['rhs']==1 and len(r['terms'])==2 and all(a['vars'][i]['integer'] and c==1 for i,c in r['terms'].items())}
    gates={r['name']:r for r in a['rows'] if r['rhs']==1200};links={r['name']:r for r in a['rows'] if r['rhs']==0}
    assert len(resources)==2646 and len(pairs)==4977 and len(gates)==len(links)==2457
    deleted=set(a['row_index'])-set(b['row_index'])-{r['name'][6:] for r in b['rows'] if r['name'].startswith('tight_')}
    deleted_gates=deleted&set(gates);deleted_cards=deleted-deleted_gates;assert len(deleted_gates)==441 and len(deleted_cards)==315
    f=SparseBuilder(a);cache={}
    def restricted(p,model,r,support,indices=None):
        actual={model['var_index'][a['vars'][i]['name']] for i in support};rr=model['rows'][model['row_index'][r['name']]]
        key=(r['name'],frozenset(actual))
        if p is f and key in cache:return cache[key]
        terms=[[row_ref(model,r['name']),1]]+[[{'VarLower':i},1] for i in sorted(set(rr['terms'])-actual)]
        ref=p.lin('Le',terms,expression(-3,{i:1 for i in actual}))
        if p is f:cache[key]=ref
        return ref
    activity={i:restricted(f,a,incident[i][0],{i}) for i in range(n) if not a['vars'][i]['integer']}
    forward={};covers={}
    for name,r in links.items():
        x=next(i for i,c in r['terms'].items() if c==1);y=next(i for i,c in r['terms'].items() if c==-8);wanted=expression(0,{x:1,y:-3})
        forward['tight_'+name]=cases_le_shared(f,wanted,y,lambda p,z,r=r:p.lin('Le',[[row_ref(a,r['name']),1],[z,5]],wanted),lambda p,o,x=x:p.lin('Le',[[activity[x],1],[o,3]],wanted))
    for name,r in gates.items():
        y=next(i for i,c in r['terms'].items() if c==1197);support=set(r['terms'])-{y}
        if name in deleted_gates:
            cover=next(rr for rr in incident[min(support)] if support<=set(rr['terms']));covers[name]=[(cover,support)];continue
        target=b['rows'][b['row_index']['tight_'+name]];u=target['rhs'];assert u in (6,9,12)
        remaining=set(support);chosen=[]
        while remaining:
            candidates={rr['name']:rr for i in remaining for rr in incident[i]};rr=max(candidates.values(),key=lambda rr:(len(remaining&set(rr['terms'])),-a['row_index'][rr['name']]))
            part=remaining&set(rr['terms']);chosen.append((rr,part));remaining-=part
        assert len(chosen)*3<=u,(name,len(chosen),u)
        covers[name]=chosen;bound=f.lin('Le',[[restricted(f,a,rr,part),1] for rr,part in chosen],expression(-u,{i:1 for i in support}),constant=3*len(chosen)-u)
        wanted=rename(row_fact(target,'RowUpper'),ids)
        forward['tight_'+name]=cases_le_shared(f,wanted,y,lambda p,z:p.lin('Le',[[bound,1],[z,u-3]],wanted),lambda p,o,r=r:p.lin('Le',[[row_ref(a,r['name']),1],[o,1200-u]],wanted))
    def matching(support):
        if not support:return []
        i=min(support);best=[({'VarUpper':i},1)]+matching(support-{i})
        for j in sorted(support-{i}):
            pair=frozenset((i,j))
            if pair in pairs:
                candidate=[(pairs[pair],1)]+matching(support-{i,j})
                if len(candidate)<len(best):best=candidate
        return best
    cardcovers={name:matching(set(a['rows'][a['row_index'][name]]['terms'])) for name in deleted_cards};assert all(len(x)<=3 for x in cardcovers.values())
    claims=[];blocks=[]
    for index,(back,integer) in enumerate([(False,True),(True,True),(True,False)]):
        inp,out=(b,a) if back else (a,b);p=SparseBuilder(inp) if back else f;indices=rev if back else ids;checks=[]
        for j,v in enumerate(out['vars']):
            i=indices[j]
            for key,field in [('VarLower','lower'),('VarUpper','upper')]:
                if v[field] is not None:checks.append({key:i})
            if integer and v['integer']:checks.append({'VarInt':i})
        for r in out['rows']:
            name=r['name'];wanted=rename(row_fact(r,'RowUpper'),indices)
            if not back and name.startswith('tight_'):ref=forward[name]
            elif back and name in deleted_gates:
                rr,support=covers[name][0];y=next(i for i,c in r['terms'].items() if c==1197);ref=p.lin('Le',[[restricted(p,b,rr,support),1],[{'VarUpper':rev[y]},1197]],wanted)
            elif back and name in deleted_cards:
                terms=[[row_ref(b,x) if isinstance(x,str) else {'VarUpper':rev[x['VarUpper']]},c] for x,c in cardcovers[name]];ref=p.lin('Le',terms,wanted,constant=len(terms)-3)
            elif back and name in gates:
                tr=b['rows'][b['row_index']['tight_'+name]];y=next(i for i,c in r['terms'].items() if c==1197);ref=p.lin('Le',[[row_ref(b,'tight_'+name),1],[{'VarUpper':rev[y]},1200-tr['rhs']]],wanted)
            elif back and name in links:
                y=next(i for i,c in r['terms'].items() if c==-8);ref=p.lin('Le',[[row_ref(b,'tight_'+name),1],[{'VarLower':rev[y]},5]],wanted)
            else:ref=row_ref(inp,name)
            assert p.refexpr(ref)==wanted;checks.append(ref)
        checks+=['Exact']*(1+n+(n if integer else 0));projection=[[i,j] for j,i in enumerate(indices)]
        claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'inverse':1-index if integer else None});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(expression(0,{i:1})) for i in indices],'checks':checks}}})
    point=[str(F(3) if v['name']=='C0001' else F(3,8) if v['name']=='C2458' else F(0)) for v in a['vars']]
    return {'claims':claims,'blocks':blocks,'points':[{'claim':{'Strictness':{'inclusion_claim':2}},'values':point}]},{'source_variables':n,'target_variables':n,'source_rows':13206,'target_rows':12450,'tightened_links':2457,'tightened_gates':2016,'deleted_resource_gates':441,'deleted_cardinalities':315,'shared_resource_restrictions':len(cache),'claims':3,'points':1}


def execute(case,source,target,audit,cert,counts,contract,mutations,out,kernel,version=3,extra=None):
    start=time.perf_counter();out=out.resolve();out.mkdir(parents=True,exist_ok=True);kernel=kernel.resolve()
    rpa=out/'proof.rpa';request=out/'request.json'
    def save(obj,path):path.write_text('RPA '+str(version)+'\n'+json.dumps(obj,separators=(',',':'))+'\n')
    save(cert,rpa);req={'claims':cert['claims'],'points':[p['claim'] for p in cert.get('points',[])],'bijections':[w['claim'] for w in cert.get('bijections',[])]};request.write_text(json.dumps(req,separators=(',',':'))+'\n')
    d={'case_id':case,'status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve() if case=='test8' else Path('tools/prepare_test62.py').resolve()),'sha256':sha(Path(__file__) if case=='test8' else Path('tools/prepare_test62.py'))},'claims':contract,'counts':counts,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[],'kernel_binary_sha256':sha(kernel),'negative_checks':[]}
    if extra:d.update(extra)
    def run(cmd,expected=0):
        p=subprocess.run([str(kernel)]+list(map(str,cmd)),capture_output=True,text=True);record={'command':[str(kernel)]+list(map(str,cmd)),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(record)
        if p.returncode!=expected:
            d['status']='EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise RuntimeError(record)
        return record
    verify=['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]
    run(['canonical',source,out/'source.mcm']);run(['canonical',target,out/'target.mcm']);run(['assemble',rpa,out/'proof.rpx']);first=run(verify);assert json.loads(first['stdout'])['status']=='VERIFIED'
    stable={name:sha(out/name) for name in ['source.mcm','target.mcm','proof.rpx','request.json','proof.rpa']}
    run(['assemble',rpa,out/'deterministic.rpx']);assert sha(out/'deterministic.rpx')==stable['proof.rpx'];(out/'deterministic.rpx').unlink()
    for name,reason,mutate in mutations:
        bad=copy.deepcopy(cert);mutate(bad);path=out/(name+'.rpa');encoded=out/(name+'.rpx');save(bad,path);assemble=run(['assemble',path,encoded]);v=run(['verify',out/'source.mcm',out/'target.mcm',encoded,request],2);result=json.loads(v['stdout']);assert result['status']=='INVALID';d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':2,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded),'assemble':assemble,'verify':v,'storage':'Temporary mutation files removed; deterministic recipe in preparer.'});path.unlink();encoded.unlink()
    repeats=[run(verify),run(verify)]
    def semantic(record):return {key:value for key,value in json.loads(record['stdout']).items() if not key.endswith('_us')}
    assert all(semantic(x)==semantic(first) for x in repeats)
    assert all(sha(out/name)==digest for name,digest in stable.items())
    d['status']='VERIFIED';d['preparation_seconds']=time.perf_counter()-start;d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':stable[name]} for name in ['source.mcm','target.mcm','proof.rpx','request.json']};d['determinism']={'assemble_byte_identical':True,'two_repeat_verifications_semantically_identical':True,'artifacts_byte_stable':True};(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':case,'status':d['status'],'counts':counts,'negative_checks':len(d['negative_checks'])}),flush=True)
    return d


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));ap.add_argument('--out',type=Path,default=Path('cases/test8'));args=ap.parse_args();run=Path('/Users/bhz/Code/reform_test/runs/test8-20261003-213957');source=run/'input/model.lp';target=run/'output/reformulated.lp';audit=run/'output/report.md';cert,counts=prepare(lp_model(source),lp_model(target))
    mutations=[('missing_resource_cover','Omits an actual resource premise.',lambda c:c['blocks'][0]['steps'][0]['Lin']['terms'].pop(0)),('missing_binary_branch','Omits the inactive switch branch premise.',lambda c:next(s['Cases'] for s in c['blocks'][0]['steps'] if 'Cases' in s)['left']['steps'][0]['Lin']['terms'].pop()),('missing_inverse','Omits a requested full inverse coordinate.',lambda c:c['blocks'][1]['end']['Return']['checks'].pop()),('false_strictness_point','Changes the exclusion witness to the common zero point.',lambda c:c['points'][0].update(values=['0']*4914))]
    execute('test8',source,target,audit,cert,counts,'Same complete integer vectors and pointwise objective in both directions, full original-coordinate identity observations and inverse identities; target LP is a strict subset of source LP on the same coordinates. All 441 deleted gates,315 deleted cardinalities,2457 tightened links,2016 tightened gates,all domains and actual rows are checked; full fractional strictness witness is checked.',mutations,args.out,args.kernel)


if __name__=='__main__':main()
