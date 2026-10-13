#!/usr/bin/env python3
"""Actual test44 capacity cuts as ordinary finite local Cases, never a theorem."""
from pathlib import Path
from fractions import Fraction as F
import argparse, copy, json, subprocess, time
from prepare_affine import parse_mps, row_ref
from prepare_test40 import expression, plus, mul, expr_json, row_fact, substitute, sha
from prepare_test88 import Builder, fix_binary


def le_cases(b,wanted,var,left,right):
    i=b.alloc();split=expression(0,{var:1});children=[]
    for side,callback in enumerate([left,right]):
        assumption=split if side==0 else expression(1,{var:-1})
        child=Builder(b.model,b.counter,b.facts,b.assumptions+[assumption])
        end=callback(child,{'Assumption':len(b.assumptions)})
        if 'Witness' in end:assert child.kind(end['Witness'])=='Le' and child.refexpr(end['Witness'])==wanted
        else:
            fact=child.refexpr(end['Absurd']);assert child.kind(end['Absurd'])=='Le' and not fact[1] and fact[0]>0
        children.append({'steps':child.steps,'end':end})
    b.steps.append({'Cases':{'id':i,'kind':'Le','expression':expr_json(wanted),'split':expr_json(split),
                            'integer':{'VarInt':var},'left':children[0],'right':children[1]}})
    b.facts[i]=('Le',wanted);return {'Local':i}


def cut(b,wanted,h):
    m=b.model;unit=F(7560);groups=[];terms=[]
    for name in h['edges']:
        r=m['rows'][m['row_index'][name]];assert r['sense']=='L'
        ids=[i for i,c in r['terms'].items() if c<0]
        assert len(ids)==3 and sorted(-r['terms'][i]/unit for i in ids)==[1,4,16]
        assert all(m['vars'][i]['integer'] and m['vars'][i]['lower']==0 and m['vars'][i]['upper']==1 for i in ids)
        choice=expression(-1,{i:1 for i in ids});choices=[]
        for other in m['rows']:
            if other['sense']=='G' and row_fact(other,'RowLower')==choice:choices.append(row_ref(m,other['name']))
        assert len(choices)==1
        groups.append((ids,choices[0]));terms.append([row_ref(m,name),1/unit])
    balances=[r for r in m['rows'] if r['name'].startswith('FC(') and r['name'].endswith('IntDS__'+h['node']+')')]
    assert len(balances)==36 and all(r['sense']=='E' for r in balances)
    terms += [[row_ref(m,r['name']),-F((r['rhs']>0)-(r['rhs']<0))/unit] for r in balances if r['rhs']]
    e=expression()
    for ref,c in terms:e=plus(e,b.refexpr(ref),c)
    for i,c in list(e[1].items()):
        if not m['vars'][i]['integer']:
            assert c>=0 and m['vars'][i]['lower']==0
            terms.append([{'VarLower':i},c]);e=plus(e,b.refexpr({'VarLower':i}),c)
    assert e[0]==F(h['demand'])/unit and set(e[1])==set(i for ids,_ in groups for i in ids)
    capacity=b.lin('Le',terms,e)

    def recurse(child,group,assigned):
        residual=wanted[0]+sum(c*assigned[i][0] for i,c in wanted[1].items() if i in assigned)
        # Every unassigned cut coefficient is nonpositive: its variable lower
        # bound suffices as soon as the already selected options meet the cut.
        if residual<=0:
            proof=[[assigned[i][1],c] if i in assigned else [{'VarLower':i},-c] for i,c in wanted[1].items()]
            assert all(c<=0 for i,c in wanted[1].items() if i not in assigned)
            return {'Witness':child.lin('Le',proof,wanted,constant=residual)}
        if group==len(groups):
            residual_cap=e[0]+sum(c*assigned[i][0] for i,c in e[1].items())
            assert residual_cap>0,('actual local design would refute committed cut',h['row'],assigned)
            contradiction=child.lin('Le',[[capacity,F(1)]]+[[assigned[i][1],-c] for i,c in e[1].items()],expression(residual_cap))
            return {'Absurd':contradiction}
        ids,choice=groups[group]
        def select(bb,index,state):
            if index==len(ids):return recurse(bb,group+1,state)
            var=ids[index]
            def branch(cc,assumption,value):
                eq=fix_binary(cc,var,value,assumption);nextstate={**state,var:(F(value),eq)}
                if value==0:return select(cc,index+1,nextstate)
                # The actual packing row forces every other option to zero.
                for other in ids:
                    if other==var or other in nextstate:continue
                    upper=cc.lin('Le',[[choice,F(1)],[eq,F(-1)]]+[[{'VarLower':j},F(1)] for j in ids if j not in [var,other]],expression(0,{other:1}))
                    nextstate[other]=(F(0),cc.eqpair(upper,{'VarLower':other}))
                return recurse(cc,group+1,nextstate)
            return {'Witness':le_cases(bb,wanted,var,lambda cc,r:branch(cc,r,0),lambda cc,r:branch(cc,r,1))}
        return select(child,0,assigned)
    return recurse(b,0,{})['Witness']


def block(inp,out,claim,h):
    b=Builder(inp);mapping=[expression(0,{inp['var_index'][v['name']]:1}) for v in out['vars']];checks=[]
    for v in out['vars']:
        i=inp['var_index'][v['name']];assert v==inp['vars'][i]
        if v['lower'] is not None:checks.append({'VarLower':i})
        if v['upper'] is not None:checks.append({'VarUpper':i})
        if v['integer'] and claim['output_integers']:checks.append('Exact')
    removed={r['removed_row']:r for r in h['removed_rows']};added={r['row']:r for r in h['added_rows']}
    for row in out['rows']:
        name=row['name'];typ={'L':'RowUpper','G':'RowLower','E':'RowEq'}[row['sense']];wanted=substitute(row_fact(row,typ),mapping)
        if name in inp['row_index']:
            ref=row_ref(inp,name);assert b.refexpr(ref)==wanted
        elif name in removed:
            assert claim['reverse'];ref=b.lin('Eq',[[row_ref(inp,n),F(-1)] for n in removed[name]['other_rows']],wanted)
        else:
            assert not claim['reverse'] and claim['input_integers'];ref=cut(b,wanted,added[name])
        checks.append(ref)
    assert substitute(out['objective'],mapping)==inp['objective'];checks.append('Exact')
    checks+=['Exact']*len(claim['projection'])
    if claim['inverse'] is not None:checks+=['Exact']*len(inp['vars'])
    return {'steps':b.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test44-nomf-B1'));p.add_argument('--out',type=Path,default=Path('cases/test44'));p.add_argument('--kernel',type=Path,required=True);args=p.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';witness=run/'output/witness.json';a,b=parse_mps(source),parse_mps(target);h=json.loads(audit.read_text());w=json.loads(witness.read_text())
    claims=[];blocks=[]
    for reverse,integer,inverse in [(False,True,1),(True,True,0),(True,False,None)]:
        inp,output=(b,a) if reverse else (a,b)
        c={'reverse':reverse,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':[[i,output['var_index'][v['name']]] for i,v in enumerate(inp['vars'])],'inverse':inverse}
        claims.append(c);blocks.append(block(inp,output,c,h))
    assert set(w['values'])==set(a['var_index'])
    points=[{'claim':{'Strictness':{'inclusion_claim':2}},'values':[w['values'][v['name']] for v in a['vars']]}]
    for target_flag,m in [(False,a),(True,b)]:
        values=[F(w['values'][v['name']]) if not v['integer'] else F(int('120960.000000' in v['name'])) for v in m['vars']]
        points.append({'claim':{'Feasible':{'target':target_flag,'integers':True,'objective':None}},'values':[str(x) for x in values]})
    cert={'claims':claims,'blocks':blocks,'points':points};rp=out/'proof.rpa';request=out/'request.json';rp.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':claims,'points':[p['claim'] for p in points]},indent=2)+'\n');k=args.kernel.resolve()
    d={'case_id':'test44','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'witness_input':{'path':str(witness),'sha256':sha(witness)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete named-coordinate integer feasible-set and objective equality with both affine inverse identities. Target LP strictly contained in source LP, proved by complete reverse inclusion and full source rational separating point. Full integer point checked on both actual models; no optimality or LP bound improvement claimed.','counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':3,'point_claims':3,'local_design_cuts':37,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]},'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rp.stat().st_size,'rpa_sha256':sha(rp),'kernel_binary_sha256':sha(k),'kernel_runs':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rp),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';save();raise SystemExit(p.stdout+p.stderr)
    assert json.loads(d['kernel_runs'][-1]['stdout'])['status']=='VERIFIED';d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[];save()
    for name,reason in [('wrong_capacity','Corrupts an actual aggregate-capacity multiplier.'),('continuous_split','Replaces a binary Case integrality premise with a continuous coordinate.'),('false_strictness','Uses the complete point feasible in both integer models as a separating point.'),('missing_middle','Deletes a middle output-model obligation.'),('wrong_inverse','Changes a mapped coordinate with both original inverse contracts retained.')]:
        bad=copy.deepcopy(cert)
        if name=='wrong_capacity':bad['blocks'][0]['steps'][0]['Lin']['terms'][0][1]='1/7559'
        elif name=='continuous_split':bad['blocks'][0]['steps'][1]['Cases']['integer']={'VarInt':next(i for i,v in enumerate(a['vars']) if not v['integer'])}
        elif name=='false_strictness':bad['points'][0]['values']=bad['points'][1]['values'][:]
        elif name=='missing_middle':bad['blocks'][1]['end']['Return']['checks'].pop(2100)
        else:bad['blocks'][0]['end']['Return']['map'][300]=expr_json(expression())
        text=out/(name+'.rpa');binary=out/(name+'.rpx');text.write_text('RPA 3\n'+json.dumps(bad,separators=(',',':'))+'\n')
        p=subprocess.run([str(k),'assemble',str(text),str(binary)],capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(binary),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(text),'rpx_sha256':sha(binary)});save()
    print(json.dumps({'case':d['case_id'],'status':d['status'],'counts':d['counts'],'verification':json.loads(d['kernel_runs'][-1]['stdout']),'attacks':len(d['negative_checks'])},indent=2))

if __name__=='__main__':main()
