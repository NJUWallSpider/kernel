#!/usr/bin/env python3
"""Complete original test69 normalization through simultaneous real intervals."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test19 import cases_le
from prepare_test23 import extend,run_checks
from prepare_test54 import fact,box,exact


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(11697,16381,8697,8885)
    common=[[i,b['var_index'][v['name']]] for i,v in enumerate(a['vars']) if v['name'] in b['var_index']]
    assert len(common)==7197 and sum(a['vars'][i]['integer'] for i,j in common)==7196
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    p=Builder(a);graph={};anchoreq={};components={}
    for w in h['equality_pair_witnesses']:
        i,j=a['var_index'][w['positive_variable']],a['var_index'][w['negative_variable']]
        r=p.eqpair(row_ref(a,w['forward_row']),row_ref(a,w['reverse_row']));scale=1/p.refexpr(r)[1][i]
        r=fact(p,'Eq',expression(-F(w['difference']),{i:1,j:-1}),[[r,scale]])
        graph.setdefault(i,[]).append((j,r,F(-1)));graph.setdefault(j,[]).append((i,r,F(1)))
    for component in h['equality_components']:
        root=a['var_index'][component['root']];offsets={a['var_index'][n]:F(v) for n,v in component['variables'].items()}
        assert offsets[root]==0;seen={root};pending=[root];anchoreq[root]=None
        while pending:
            parent=pending.pop()
            for child,r,c in graph[parent]:
                if child in seen:continue
                assert child in offsets;seen.add(child);pending.append(child)
                terms=[[r,c]]+([[anchoreq[parent],F(1)]] if anchoreq[parent] is not None else [])
                anchoreq[child]=fact(p,'Eq',expression(-offsets[child],{child:1,root:-1}),terms)
        assert seen==set(offsets)
        components.update({i:(root,c) for i,c in offsets.items()})
    assert len(components)==1500
    intervals=[];endpoints={};placements={}
    for n,w in enumerate(h['intervals']):
        lo,up,anchor=[a['var_index'][w[k]] for k in ('lower','upper','anchor')];L=F(w['length']);assert lo not in endpoints and up not in endpoints
        lower=[expression(),expression(L,{lo:1,anchor:-1})];upper=[expression(L),expression(0,{up:1,anchor:-1})]
        sources=[row_ref(a,v) for v in w['contain_rows']+[w['length_row']]];checks=[]
        for le in lower:
            for ue in upper:
                e=plus(le,ue,-1)
                if exact('Le',e):checks.append('Exact')
                else:
                    matches=[r for r in sources if p.refexpr(r)==e];assert len(matches)==1;checks.append(matches[0])
        intervals.append({'lower':[expr_json(e) for e in lower],'upper':[expr_json(e) for e in upper],'checks':checks})
        endpoints[lo]=(n,'lower',anchor,L);endpoints[up]=(n,'upper',anchor,L);placements[b['var_index'][w['new_variable']]]=n
    assert len(endpoints)==3000 and set(endpoints).isdisjoint(components)
    ext,layout=extend(a,intervals);f=Builder(ext,p.counter,p.facts);forward=[None]*len(b['vars']);domains={}
    for i,j in common:forward[j]=expression(0,{i:1});domains[i]={'VarLower':{'VarLower':i},'VarUpper':{'VarUpper':i},'VarInt':{'VarInt':i}}
    for j,n in placements.items():
        v=layout[n]['variable'];forward[j]=expression(0,{v:1});domains[v]={'VarLower':{'RowLower':layout[n]['lower'][0]},'VarUpper':{'RowUpper':layout[n]['upper'][0]}}
        assert b['vars'][j]['lower']==0 and b['vars'][j]['upper']==F(h['intervals'][n]['length']) and not b['vars'][j]['integer']
    assert all(e is not None for e in forward)
    changes={x['row']:x for x in h['indicator_tightening']};assert len(changes)==6446
    def normalized(n):
        r=row_ref(a,n);e=f.refexpr(r);terms=[[r,F(1)]]
        for i,c in list(e[1].items()):
            if i not in endpoints:continue
            k,which,anchor,L=endpoints[i]
            if which=='lower':assert c<=0;ref={'RowLower':layout[k]['lower'][1]};scale=-c
            else:assert c>=0;ref={'RowUpper':layout[k]['upper'][1]};scale=c
            terms.append([ref,scale]);e=plus(e,f.refexpr(ref),scale)
        for i,c in list(e[1].items()):
            if i not in anchoreq or anchoreq[i] is None:continue
            terms.append([anchoreq[i],-c]);e=plus(e,f.refexpr(anchoreq[i]),-c)
        assert not(set(e[1])&set(components)),('translation residual',n,e)
        return e,terms
    def frow(i,wanted):
        n=b['rows'][i]['name'];old,terms=normalized(n);kind='Eq' if b['rows'][i]['sense']=='E' else 'Le'
        if n not in changes:assert old==wanted;return terms
        w=changes[n];binary=a['var_index'][w['binary']];assert plus(old,expression(1,{binary:-1}))==wanted
        oldref=fact(f,'Le',old,terms)
        def inactive(child,assumption):
            remaining=expression(wanted[0],{j:c for j,c in wanted[1].items() if j!=binary});terms=[];ceiling=remaining[0]
            for j,c in remaining[1].items():
                typ='VarUpper' if c>0 else 'VarLower';r=domains[j][typ];terms.append([r,abs(c)])
                bound=-child.refexpr(r)[0] if c>0 else child.refexpr(r)[0];ceiling+=c*bound
            assert ceiling<=0 and wanted[1][binary]>0
            terms.append([assumption,wanted[1][binary]])
            return fact(child,'Le',wanted,terms,ceiling)
        return cases_le(f,wanted,binary,inactive,lambda child,assumption:fact(child,'Le',wanted,[[oldref,F(1)],[assumption,F(1)]]))
    fc={'reverse':False,'input_integers':True,'output_integers':True,'objective':'Equal','projection':common,'affine_projection':[],'inverse':None}
    forwardbody=run_checks(f,b,forward,fc,lambda i,t:domains[next(iter(forward[i][1]))][t],frow,lambda e:[])
    blocks=[{'steps':p.steps,'end':{'IntervalLift':{'intervals':intervals,'body':forwardbody}}}];claims=[fc]
    reverse=[]
    for v in a['vars']:
        x=h['expansion_map'][v['name']];terms={b['var_index'][x['variable']]:F(1)} if x.get('variable') is not None else {}
        reverse.append(expression(F(x['constant']),terms))
    assert substitute(a['objective'],reverse)==b['objective']
    for integer in (True,False):
        r=Builder(b);rc={'reverse':True,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[j,i] for i,j in common],'affine_projection':[],'inverse':None}
        def rdomain(i,typ):
            e=reverse[i];v=a['vars'][i]
            if typ=='VarInt':return [[{'VarInt':j},c] for j,c in e[1].items()]
            sign=-1 if typ=='VarLower' else 1;expected=plus(mul(e,sign),expression(-sign*v['lower' if sign==-1 else 'upper']))
            if exact('Le',expected):return []
            return box(r,expected)
        def rrow(i,wanted):
            n=a['rows'][i]['name']
            if n not in b['row_index']:
                if exact('Le',wanted):return []
                return box(r,wanted)
            terms=[[row_ref(b,n),F(1)]]
            if n in changes:terms.append([{'VarUpper':b['var_index'][changes[n]['binary']]},F(1)])
            return terms
        blocks.append(run_checks(r,a,reverse,rc,rdomain,rrow,lambda e:[]));claims.append(rc)
    counts={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'simultaneous_intervals':len(intervals),'affine_component_variables':len(components),'tightened_gates':len(changes),'preserved_original_binaries':7196,'claims':3,'obligations_by_claim':[len(forwardbody['end']['Return']['checks'])]+[len(x['end']['Return']['checks']) for x in blocks[1:]]}
    return {'claims':claims,'blocks':blocks},counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test69-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test69'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';cert,counts=prepare(parse_mps(source),parse_mps(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test69','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete original-binary projection and all attainable objective values in both integer directions, plus complete target LP to source LP objective-preserving recovery. Interval shortening and translations do not assert a continuous bijection; global strict LP strengthening is not claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_interval_pair','Omits one compatibility obligation from a middle simultaneous interval.'),('wrong_gate_integrality','Uses a continuous variable as the integer gate split premise.'),('wrong_recovery','Changes an expanded continuous endpoint constant without corresponding complete-model evidence.'),('missing_binary_observation','Omits a required original binary coordinate observation.')]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][0]['end']['IntervalLift']
            if name=='missing_interval_pair':lift['intervals'][750]['checks'].pop()
            elif name=='wrong_gate_integrality':next(s['Cases'] for s in lift['body']['steps'] if 'Cases' in s)['integer']={'VarInt':len(parse_mps(source)['vars'])}
            elif name=='wrong_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if e['constant'] not in ('0','1000'))['constant']='-1'
            else:bad['blocks'][2]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
