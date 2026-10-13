#!/usr/bin/env python3
"""Actual test22 exact ranged-row projection, identical-cost aggregation and encoded objective offset."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test57 import substitute
from prepare_test88 import Builder
from prepare_test54 import fact,box,exact


def parse_ranged_target(path):
    lines=[];ranges={};inside=False;vectors=set()
    for line in path.read_text().splitlines():
        if line and not line[0].isspace() and not line.startswith('*'):
            inside=line.split()[0]=='RANGES'
            if inside:continue
        if inside:
            if not line.strip() or line.startswith('*'):continue
            t=line.split();assert len(t) in (3,5);vectors.add(t[0])
            for n,v in zip(t[1::2],t[2::2]):assert n not in ranges;ranges[n]=F(v)
        else:lines.append(line)
    class MemoryMPS:
        def read_text(self):return '\n'.join(lines)+'\n'
        def __str__(self):return str(path)
    model=parse_mps(MemoryMPS());assert len(vectors)==1 and len(ranges)==171
    for row in model['rows']:
        assert row['sense']=='G' and row['name'] in ranges and ranges[row['name']]>0;row['upper']=row['rhs']+ranges[row['name']]
    return model


class RangedBuilder(Builder):
    def refexpr(self,ref):
        typ,i=next(iter(ref.items()))
        if typ=='RowUpper' and 'upper' in self.model['rows'][i]:
            row=self.model['rows'][i];return expression(-row['upper'],row['terms'])
        return super().refexpr(ref)


def prepare(a,b,h):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(397,171,213,171)
    pivots={a['var_index'][d['eliminated_continuous_variable']]:a['row_index'][d['row']] for d in h['row_edits']};zeros={a['var_index'][n] for n in h['fixed_zero_integers_removed']};pair=[a['var_index'][n] for n in h['aggregation']['old_variables']];aggregate=b['var_index']['agg107'];offset=b['var_index']['objconst'];removed=set(pivots)|zeros|set(pair)
    assert len(removed)==186 and len(pair)==2 and len(pivots)==171 and len(zeros)==13
    common=[[a['var_index'][v['name']],j] for j,v in enumerate(b['vars']) if v['name'] in a['var_index']]
    for i,j in common:assert a['vars'][i]==b['vars'][j]
    forward=[expression(1) if j==offset else expression(0,{i:1 for i in pair}) if j==aggregate else expression(0,{a['var_index'][v['name']]:1}) for j,v in enumerate(b['vars'])]
    reverse=[None]*len(a['vars'])
    for i,v in enumerate(a['vars']):
        if i in zeros:reverse[i]=expression()
        elif i in pair:reverse[i]=expression(0,{aggregate:F(1,2)});assert v['lower']==0 and v['upper']==4 and not v['integer']
        elif i not in pivots:reverse[i]=expression(0,{b['var_index'][v['name']]:1})
    for i,ri in pivots.items():
        row=a['rows'][ri];assert row['sense']=='E' and row['terms'][i]==1 and not a['vars'][i]['integer'] and a['vars'][i]['lower']==0
        assert all(reverse[j] is not None for j in row['terms'] if j!=i)
        e=expression(row['rhs'])
        for j,c in row['terms'].items():
            if j!=i:e=plus(e,reverse[j],-c)
        reverse[i]=e
    claims=[];blocks=[]
    for integer in (True,False):
        for back in (False,True):
            inp,out=(b,a) if back else (a,b);mapping=reverse if back else forward;p=RangedBuilder(inp);checks=[];zeroeq={}
            if not back:
                for i in zeros:assert a['vars'][i]['lower']==a['vars'][i]['upper']==0;zeroeq[i]=p.eqpair({'VarUpper':i},{'VarLower':i})
            else:offset_eq=p.eqpair({'VarUpper':offset},{'VarLower':offset})
            def corrected(kind,wanted,terms):
                raw=expression()
                for r,c in terms:raw=plus(raw,p.refexpr(r),c)
                delta=plus(wanted,raw,-1);assert delta[0]==0 and set(delta[1])<=zeros
                return fact(p,kind,wanted,terms+[[zeroeq[i],c] for i,c in delta[1].items()],terminal=True)
            for i,v in enumerate(out['vars']):
                e=mapping[i]
                for typ,value,sign in [('VarLower',v['lower'],-1),('VarUpper',v['upper'],1)]:
                    if value is None:continue
                    wanted=plus(mul(e,sign),expression(-sign*value))
                    if back and i in pivots:ri=b['row_index'][a['rows'][pivots[i]]['name']];ref={'RowUpper' if typ=='VarLower' else 'RowLower':ri};assert p.refexpr(ref)==wanted
                    else:ref=box(p,wanted,True)
                    checks.append(ref)
                if integer and v['integer']:checks.append(fact(p,'Int',e,[[{'VarInt':j},c] for j,c in e[1].items()],e[0],True))
            if back:
                for row in a['rows']:assert substitute(row_fact(row,'RowEq'),mapping)==expression();checks.append('Exact')
            else:
                byrow={a['rows'][ri]['name']:i for i,ri in pivots.items()}
                for row in b['rows']:
                    name=row['name'];i=byrow[name];ref=row_ref(a,name)
                    lower=substitute(expression(row['rhs'],{j:-c for j,c in row['terms'].items()}),mapping);upper=substitute(expression(-row['upper'],row['terms']),mapping)
                    checks.append(corrected('Le',lower,[[ref,F(-1)],[{'VarUpper':i},F(1)]]));checks.append(corrected('Le',upper,[[ref,F(1)],[{'VarLower':i},F(1)]]))
            wanted=plus(substitute(out['objective'],mapping),inp['objective'],-1)
            if back:checks.append(fact(p,'Eq',wanted,[[offset_eq,-b['objective'][1][offset]]],terminal=True))
            else:checks.append(corrected('Eq',wanted,[[{'RowEq':ri},-a['objective'][1].get(i,F(0))] for i,ri in pivots.items() if a['objective'][1].get(i,F(0))]))
            projection=[[j,i] for i,j in common] if back else common
            for i,j in projection:assert mapping[j]==expression(0,{i:1});checks.append('Exact')
            obs=[expr_json(expression(0,{i:1 for i in pair})),expr_json(expression(0,{aggregate:1}))];affine=[list(reversed(obs)) if back else obs];checks.append('Exact')
            claims.append({'reverse':back,'input_integers':integer,'output_integers':integer,'objective':'Equal','projection':projection,'affine_projection':affine,'inverse':None});blocks.append({'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}})
    return {'claims':claims,'blocks':blocks},{'source_variables':397,'target_variables':213,'source_rows':171,'target_ranged_rows':171,'private_pivots':171,'fixed_zero_integers':13,'aggregate_pair':2,'retained_coordinate_observations':211,'sum_observations':1,'claims':4,'exact_objective_offset':str(b['objective'][1][offset]),'obligations_by_claim':[len(x['end']['Return']['checks']) for x in blocks]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test22-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test22'));ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json'
    cert,counts=prepare(parse_mps(source),parse_ranged_target(target),json.loads(audit.read_text()));rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 5\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test22','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Four complete integer and LP projection directions with all retained coordinates and the aggregate sum observation, exact objective equality including the encoded fixed offset, every original domain/equality and both bounds of every actual target ranged row. The aggregate pair is split equally; no bijection is claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('wrong_offset','Maps the actual fixed objective-offset column to zero.'),('missing_pivot_bound','Drops a pivot bound needed for a target ranged-row endpoint.'),('wrong_recovery','Changes a removed pivot recovery constant.'),('missing_sum_observation','Omits the aggregate-sum observation.')]:
            bad=copy.deepcopy(cert)
            if name=='wrong_offset':next(e for e in bad['blocks'][0]['end']['Return']['map'] if not e['terms'])['constant']='0'
            elif name=='missing_pivot_bound':next(s['Lin'] for s in bad['blocks'][0]['steps'] if 'Lin' in s and s['Lin']['kind']=='Le' and any(isinstance(r,dict) and 'RowEq' in r for r,c in s['Lin']['terms']))['terms'].pop(1)
            elif name=='wrong_recovery':next(e for e in bad['blocks'][1]['end']['Return']['map'] if len(e['terms'])>1)['constant']='2'
            else:bad['blocks'][1]['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 5\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx');p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
