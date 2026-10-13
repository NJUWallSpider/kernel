#!/usr/bin/env python3
"""Complete actual test21 dominance certificate, using ordinary linear rules.

This untrusted preparer uses sparse mutable accumulation and balanced sum bounds
so it does not copy a large partition row once for every retained column.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import defaultdict
import argparse,copy,gc,json,subprocess,time
from prepare_affine import parse_mps,row_ref,get_fact
from prepare_test40 import expression,mul,expr_json,row_fact,sha


def add_term(terms,i,c):
    if not c:return
    value=terms.get(i,F(0))+c
    if value:terms[i]=value
    else:terms.pop(i,None)


def combine(items,constant=0):
    out={};constant=F(constant)
    for e,c in items:
        if not c:continue
        constant+=e[0]*c
        for i,q in e[1].items():add_term(out,i,q if c==1 else -q if c==-1 else q*c)
    return constant,out


def substitute(e,mapping):
    return combine(((mapping[i],c) for i,c in e[1].items()),e[0])


class Proof:
    def __init__(self,model):self.model=model;self.facts={};self.steps=[];self.next_id=0
    def refexpr(self,r):
        return self.facts[r['Local']][1] if 'Local' in r else get_fact(self.model,r,{})
    def kind(self,r):return self.facts[r['Local']][0] if 'Local' in r else 'Eq' if 'RowEq' in r else 'Int' if 'VarInt' in r else 'Le'
    def lin(self,kind,terms,expected=None,constant=0):
        assert (kind=='Eq' and constant==0) or (kind=='Le' and constant<=0)
        for r,c in terms:assert self.kind(r)=='Eq' or (kind=='Le' and self.kind(r)=='Le' and c>=0)
        result=combine(((self.refexpr(r),c) for r,c in terms),constant)
        if expected is not None:assert result==expected,'exact sparse linear combination mismatch'
        i=self.next_id;self.next_id+=1;self.facts[i]=(kind,result)
        self.steps.append({'Lin':{'id':i,'kind':kind,'constant':str(constant),'terms':[[r,str(c)] for r,c in terms]}})
        return {'Local':i}
    def check(self,kind,e,r,integer):
        if r=='Exact':
            valid=(not e[1] and ((kind=='Eq' and e[0]==0) or (kind=='Le' and e[0]<=0))) or (kind=='Int' and e[0].denominator==1 and all(c.denominator==1 and integer and self.model['vars'][i]['integer'] for i,c in e[1].items()))
            assert valid,(kind,e)
        else:assert self.kind(r) in (kind,'Eq') and self.refexpr(r)==e,'complete-model obligation mismatch'
        return r


def maps(a,b,hints):
    assert (len(a['vars']),len(a['rows']),len(b['vars']),len(b['rows']))==(87482,36,46168,35)
    for model in [a,b]:
        assert all(v['integer'] and v['lower']==0 and v['upper']==1 for v in model['vars'])
        assert all(r['sense']=='E' and r['rhs']==1 and set(r['terms'].values())=={F(1)} for r in model['rows'])
    duplicate={x['removed']:x['representative'] for x in hints['duplicate_columns']}
    replace={x['removed']:x['replacements'] for x in hints['disjoint_replacement_dominance']}
    assert len(duplicate)==41292 and len(replace)==21
    support=[set() for _ in a['vars']]
    for r,row in enumerate(a['rows']):
        for i in row['terms']:support[i].add(r)
    for removed,representative in duplicate.items():
        i,j=a['var_index'][removed],a['var_index'][representative]
        assert support[i]==support[j] and a['objective'][1][i]>=a['objective'][1][j]
        assert representative not in duplicate
    for removed,replacements in replace.items():
        assert removed not in duplicate and removed not in b['var_index']
        total=set()
        for name in replacements:
            assert name in b['var_index'] and name not in replace
            ids=support[a['var_index'][name]];assert total.isdisjoint(ids);total|=ids
        assert total==support[a['var_index'][removed]]
        assert sum(a['objective'][1][a['var_index'][name]] for name in replacements)<=a['objective'][1][a['var_index'][removed]]
    forward=[expression() for _ in b['vars']]
    for i,var in enumerate(a['vars']):
        if var['name']=='x600':continue
        representative=duplicate.get(var['name'],var['name'])
        for name in replace.get(representative,[representative]):
            assert name in b['var_index']
            forward[b['var_index'][name]][1][i]=F(1)
    reverse=[]
    for var in a['vars']:
        name='x599' if var['name']=='x600' else var['name']
        reverse.append(expression(0,{b['var_index'][name]:1}) if name in b['var_index'] else expression())
    assert all(e[1] for e in forward)
    return forward,reverse,support


def forward_proof(a,b,forward,support):
    p=Proof(a);lower={};upper={};chosen=defaultdict(list);trace={}
    for j,e in enumerate(forward):
        if len(e[1])==1:
            i=next(iter(e[1]));lower[j]={'VarLower':i};upper[j]={'VarUpper':i}
        else:
            lower[j]=p.lin('Le',[[{'VarLower':i},F(1)] for i in e[1]],mul(e,-1))
            common=set.intersection(*(support[i] for i in e[1]));assert common
            row=min(common,key=lambda r:(len(a['rows'][r]['terms']),r));chosen[row].append(j)

    def build_tree(leaves):
        if len(leaves)==1:return {'leaf':leaves[0],'lower':lower[leaves[0]]}
        half=len(leaves)//2;left=build_tree(leaves[:half]);right=build_tree(leaves[half:])
        lo=p.lin('Le',[[left['lower'],F(1)],[right['lower'],F(1)]])
        return {'left':left,'right':right,'lower':lo}

    def spread(node,up):
        if 'leaf' in node:
            j=node['leaf'];assert p.refexpr(up)==combine([(forward[j],F(1))],-1);upper[j]=up;return
        l,r=node['left'],node['right']
        lu=p.lin('Le',[[up,F(1)],[r['lower'],F(1)]]);ru=p.lin('Le',[[up,F(1)],[l['lower'],F(1)]])
        trace.setdefault('tree_child_fact',lu['Local'])
        spread(l,lu);spread(r,ru)

    for row,groups in sorted(chosen.items()):
        selected=set()
        for j in groups:
            assert selected.isdisjoint(forward[j][1]);selected.update(forward[j][1])
        assert selected <= a['rows'][row]['terms'].keys()
        tree=build_tree(groups)
        terms=[[{'RowEq':row},F(1)]]+[[{'VarLower':i},F(1)] for i in a['rows'][row]['terms'] if i not in selected]
        root=p.lin('Le',terms,expression(-1,{i:1 for i in selected}));trace.setdefault('tree_root_fact',root['Local'])
        spread(tree,root)

    alias=p.lin('Eq',[[row_ref(a,'c1'),F(1)],[row_ref(a,'c2'),F(-1)]],expression(0,{a['var_index']['x599']:1,a['var_index']['x600']:-1}))
    objective=combine([(substitute(b['objective'],forward),F(1)),(a['objective'],F(-1))])
    alias_scale=objective[1].get(a['var_index']['x599'],F(0))
    remainder=combine([(objective,F(1)),(p.refexpr(alias),-alias_scale)])
    assert remainder[0]==0 and all(c<=0 for c in remainder[1].values())
    obj=p.lin('Le',[[alias,alias_scale]]+[[{'VarLower':i},-c] for i,c in remainder[1].items()],objective)
    trace.update(objective_fact=obj['Local'],alias_fact=alias['Local'])
    info={'multiple_contributor_groups':len(lower)-sum(len(e[1])==1 for e in forward),'bound_tree_source_rows':len(chosen),
          'largest_contributor_group':max(len(e[1]) for e in forward),'forward_nonzeros':sum(len(e[1]) for e in forward),
          'linear_steps':len(p.steps),'proof_local_terms':sum(len(e[1]) for k,e in p.facts.values())}
    return p,lower,upper,obj,trace,info


def block(p,out,mapping,integer,reverse,lower=None,upper=None,objective=None):
    checks=[]
    for j,(v,e) in enumerate(zip(out['vars'],mapping)):
        if reverse:
            if not e[1]:lo=hi='Exact'
            else:i=next(iter(e[1]));lo={'VarLower':i};hi={'VarUpper':i}
        else:lo,hi=lower[j],upper[j]
        checks.append(p.check('Le',mul(e,-1),lo,integer))
        checks.append(p.check('Le',combine([(e,F(1))],-1),hi,integer))
        if integer:checks.append(p.check('Int',e,'Exact',integer))
    for row in out['rows']:
        name='c1' if reverse and row['name']=='c2' else row['name']
        checks.append(p.check('Eq',substitute(row_fact(row,'RowEq'),mapping),row_ref(p.model,name),integer))
    difference=combine([(substitute(out['objective'],mapping),F(1)),(p.model['objective'],F(-1))])
    checks.append(p.check('Eq' if reverse else 'Le',difference,'Exact' if reverse else objective,integer))
    return {'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def prepare(source,target,audit):
    a,b=parse_mps(source),parse_mps(target);hints=json.loads(audit.read_text())
    forward,reverse,support=maps(a,b,hints)
    p,lower,upper,obj,trace,info=forward_proof(a,b,forward,support);r=Proof(b)
    claims=[];blocks=[]
    for integer in [True,False]:
        for backward in [False,True]:
            claims.append({'reverse':backward,'input_integers':integer,'output_integers':integer,
                           'objective':'Equal' if backward else 'NonIncreasing','projection':[],'inverse':None})
            blocks.append(block(r,a,reverse,integer,True) if backward else block(p,b,forward,integer,False,lower,upper,obj))
    return a,b,{'claims':claims,'blocks':blocks},trace,info


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test21-nomf-B1'))
    ap.add_argument('--out',type=Path,default=Path('cases/test21'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    started=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source,target,audit=run/'input/model.mps',run/'output/reformulated.mps',run/'output/audit.json'
    a,b,cert,trace,info=prepare(source,target,audit);gc.collect()
    rpa,request=out/'proof.rpa',out/'request.json';rpa.write_text('RPA 1\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    receipt={'case_id':'test21','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},
             'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'preparer_dependencies':{name:sha(Path(__file__).with_name(name)) for name in ['prepare_affine.py','prepare_test40.py']},
             'claims':'MI and LP source-to-target objective nonincrease, target-to-source objective equality; complete feasibility maps. No bijection, original-coordinate projection or numeric optimum claimed.',
             'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'claims':4,'obligations_by_claim':[len(x['end']['Return']['checks']) for x in cert['blocks']],**info},
             'preparation_seconds':time.perf_counter()-started,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    (out/'coordinate_index.json').write_text(json.dumps({'source_variables':[v['name'] for v in a['vars']],'target_variables':[v['name'] for v in b['vars']],'source_rows':[r['name'] for r in a['rows']],'target_rows':[r['name'] for r in b['rows']]},separators=(',',':'))+'\n')
    if args.kernel:
        kernel=args.kernel.resolve()
        def invoke(command):
            result=subprocess.run([str(kernel),*map(str,command)],capture_output=True,text=True)
            return {'command':[str(kernel),*map(str,command)],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        for command in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'proof.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'proof.rpx',request]]:
            result=invoke(command);receipt['kernel_runs'].append(result)
            if result['exit_code']:
                receipt['status']=json.loads(result['stdout']).get('status','FAILED');break
        else:
            receipt['status']='VERIFIED';receipt['kernel_binary_sha256']=sha(kernel)
            receipt['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
            receipt['negative_checks']=[]
            attacks=[('lost_contributor','Omit one original contributor from a target aggregate.'),('missing_sibling_lower','Omit the sibling nonnegative sum from a balanced upper-bound inference.'),
                     ('wrong_partition_root','Reverse the actual partition equality multiplier at a tree root.'),('wrong_alias_cost','Drop the cost correction from the actual x599-x600 equality.'),
                     ('lost_reverse_alias','Lift x600 as zero instead of x599.'),('weakened_objective_claim','Change the certified objective claim without changing the caller request.')]
            for name,why in attacks:
                bad=copy.deepcopy(cert);forward=bad['blocks'][0];steps={s['Lin']['id']:s['Lin'] for s in forward['steps']}
                if name=='lost_contributor':
                    e=next(e for e in forward['end']['Return']['map'] if len(e['terms'])>1);e['terms'].pop()
                elif name=='missing_sibling_lower':steps[trace['tree_child_fact']]['terms'].pop()
                elif name=='wrong_partition_root':steps[trace['tree_root_fact']]['terms'][0][1]='-1'
                elif name=='wrong_alias_cost':steps[trace['objective_fact']]['terms'][0][1]='0'
                elif name=='lost_reverse_alias':bad['blocks'][1]['end']['Return']['map'][a['var_index']['x600']]=expr_json(expression())
                else:bad['claims'][0]['objective']='None'
                path=out/(name+'.rpa');binary=out/(name+'.rpx');path.write_text('RPA 1\n'+json.dumps(bad,separators=(',',':'))+'\n')
                assembled=invoke(['assemble',path,binary]);assert assembled['exit_code']==0,assembled
                rejected=invoke(['verify',out/'source.mcm',out/'target.mcm',binary,request]);result=json.loads(rejected['stdout'])
                assert rejected['exit_code']==2 and result['status']=='INVALID',(name,rejected)
                receipt['negative_checks'].append({'mutation':name,'rule_broken':why,'exit_code':rejected['exit_code'],'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(binary)})
                del bad;gc.collect()
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))
    if args.kernel and receipt['status']!='VERIFIED':raise SystemExit(1)


if __name__=='__main__':main()
