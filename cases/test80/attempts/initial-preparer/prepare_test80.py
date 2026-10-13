#!/usr/bin/env python3
"""Full actual test80 optimizer bijection; untrusted exact proof preparation.

Uses the working objective-level contract, not a replacement cropped source.
No new rule or production edit is made by this preparer. Version 9 is not frozen.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time,traceback
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,sha
from prepare_test87 import Proof,sumexpr,substitute
from audit_test80 import inspect


def parse_expr(e):return expression(F(e['constant']),{i:F(c) for i,c in e['terms']})
def var(i):return expression(0,{i:1})
def rounded(p,le,integer):
    left,right=p.refexpr(le),p.refexpr(integer);assert left[1]==right[1]
    d=left[0]-right[0];ceiling=-(-d.numerator//d.denominator)
    result=plus(right,expression(ceiling));i=p.alloc();p.steps.append({'Round':{'id':i,'le':le,'integer':integer}});p.facts[i]=('Le',result);return {'Local':i}


def emit(p,output,mapping,claim,rows=None,inverse=None,inverse_level=None):
    checks=[]
    for i,v in enumerate(output['vars']):
        for side,sign in [('lower',-1),('upper',1)]:
            if v[side] is not None:checks.append(p.prove('Le',plus(mul(mapping[i],sign),expression(-sign*v[side]))))
        if v['integer'] and claim['output_integers']:checks.append(p.prove('Int',mapping[i]))
    for i,r in enumerate(output['rows']):
        which={'E':'RowEq','L':'RowUpper','G':'RowLower'}[r['sense']];expected=substitute(row_fact(r,which),mapping);ref=(rows or {}).get(i)
        checks.append(p.prove('Eq' if which=='RowEq' else 'Le',expected,[[ref,F(1)]] if ref else None))
    if claim['objective']!='None':checks.append(p.prove('Eq' if claim['objective']=='Equal' else 'Le',plus(substitute(output['objective'],mapping),p.model['objective'],-1)))
    assert not claim['projection'] and not claim.get('affine_projection')
    if inverse is not None:
        for i,e in enumerate(inverse):checks.append(p.prove('Eq',plus(substitute(e,mapping),var(i),-1)))
    if inverse_level is not None:checks.append(p.prove('Eq',plus(substitute(output['objective'],mapping),expression(-inverse_level))))
    if claim.get('input_objective_lower') is not None:checks.append(p.prove('Le',plus(expression(F(claim['input_objective_lower'])),p.model['objective'],-1)))
    return {'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}


def zero_components(p,evidence,level_ref):
    """Balanced nonnegative sum tree, then exact equality descent to each term."""
    leaves=[]
    for group in evidence['source_p']:
        for i in group:leaves.append({'coordinate':i,'scale':F(1),'neg':{'VarLower':i},'positive':var(i)})
    for i in evidence['source_b']:
        e=expression(10,{i:-10});negative=p.lin('Le',[[{'VarUpper':i},F(10)]],mul(e,-1))
        leaves.append({'coordinate':i,'scale':F(-1,10),'neg':negative,'positive':e})
    def tree(items):
        if len(items)==1:return items[0]
        mid=len(items)//2;left,right=tree(items[:mid]),tree(items[mid:])
        positive=plus(left['positive'],right['positive']);negative=p.lin('Le',[[left['neg'],F(1)],[right['neg'],F(1)]],mul(positive,-1))
        return {'positive':positive,'neg':negative,'children':(left,right)}
    root=tree(leaves);assert root['positive']==p.refexpr(level_ref)
    fixed={}
    def visit(node,eq):
        if 'children' not in node:
            ref=eq if node['scale']==1 else p.lin('Eq',[[eq,node['scale']]])
            expected=var(node['coordinate']) if node['scale']==1 else expression(-1,{node['coordinate']:1})
            assert p.refexpr(ref)==expected;fixed[node['coordinate']]=p.add('Eq',ref);return
        left,right=node['children']
        for child,other in [(left,right),(right,left)]:
            upper=p.lin('Le',[[eq,F(1)],[other['neg'],F(1)]],child['positive'])
            visit(child,p.eqpair(upper,child['neg']))
    visit(root,level_ref)
    assert len(fixed)==3331
    return fixed


def forward_face(a,b,evidence,claim,forward,reverse):
    model=copy.deepcopy(a);level=F(claim['input_objective_level']);ri=len(model['rows']);name=f'$rpx_level_row_{ri}'
    assert name not in model['row_index'];model['row_index'][name]=ri
    model['rows'].append({'name':name,'sense':'E','rhs':level-model['objective'][0],'terms':model['objective'][1].copy()})
    p=Proof(model);fixed=zero_components(p,evidence,{'RowEq':ri})
    xs,ys,ps=evidence['source_x'],evidence['source_y'],evidence['source_p']
    sets={int(i):members for i,members in evidence['linked_sets'].items()};links={int(i):rows for i,rows in evidence['link_rows'].items()}
    pairs={};onehot={}
    def pair(i,t):
        key=(i,t)
        if key in pairs:return pairs[key]
        members=sets[i];k=len(members);assert t in members;implies=[]
        for j in range(16):
            terms=[[{'RowLower':links[i][j][1]},F(1,k)]]+[[{'VarUpper':ys[u][j]},F(1,k)] for u in members if u!=t]
            if k>1:terms.append([{'VarLower':ys[t][j]},F(k-1,k)])
            difference=expression(0,{xs[i][j]:1,ys[t][j]:-1})
            upper=p.lin('Le',terms,plus(difference,expression(-F(k-1,k))))
            integer=p.lin('Int',[[{'VarInt':xs[i][j]},F(1)],[{'VarInt':ys[t][j]},F(-1)]],difference)
            rounded_ref=rounded(p,upper,integer);assert p.refexpr(rounded_ref)==difference;implies.append(rounded_ref)
        assignment={'RowEq':evidence['assignment_rows'][i]}
        if t not in onehot:
            upper=p.lin('Le',[[{'RowUpper':evidence['pass_rows'][t][2]},F(1)]]+[[fixed[v],F(1)] for v in ps[t]],expression(-1,dict.fromkeys(ys[t],F(1))))
            lower=p.lin('Le',[[assignment,F(-1)]]+[[r,F(1)] for r in implies],expression(1,dict.fromkeys(ys[t],F(-1))))
            onehot[t]=p.add('Eq',p.eqpair(upper,lower))
        equals=[]
        for j in range(16):
            reverse_le=p.lin('Le',[[onehot[t],F(1)],[assignment,F(-1)]]+[[r,F(1)] for z,r in enumerate(implies) if z!=j],expression(0,{ys[t][j]:1,xs[i][j]:-1}))
            equals.append(p.add('Eq',p.eqpair(implies[j],reverse_le)))
        pairs[key]=equals;return equals
    # Every Y receives a genuine source-row proof of its sum, independent of
    # the chosen spanning forest. All original rows are checked again in G.
    for t in range(221):pair(next(i for i,members in sets.items() if t in members),t)
    rooted={min(c):[None]*16 for c in evidence['components']}
    component={t:min(c) for c in evidence['components'] for t in c}
    for edge in evidence['spanning_edges']:
        u,v,i=edge['from'],edge['to'],edge['assignment'];assert u in rooted and v not in rooted
        up,down=pair(i,u),pair(i,v);rooted[v]=[]
        for j in range(16):
            terms=[[up[j],F(1)],[down[j],F(-1)]]+([[rooted[u][j],F(1)]] if rooted[u][j] else [])
            rooted[v].append(p.add('Eq',p.lin('Eq',terms,expression(0,{ys[v][j]:1,ys[component[v]][j]:-1}))))
    assert set(rooted)==set(range(221))
    for i,members in sets.items():
        t=members[0];base=pair(i,t)
        for j in range(16):
            terms=[[base[j],F(1)]]+([[rooted[t][j],F(1)]] if rooted[t][j] else [])
            p.add('Eq',p.lin('Eq',terms,expression(0,{xs[i][j]:1,ys[component[t]][j]:-1})))
    block=emit(p,b,forward,claim,inverse=reverse)
    return block,{'proven_link_vector_pairs':len(pairs),'proven_onehot_y_vectors':len(onehot),'fixed_original_coordinates':len(fixed),'allocated_ids':p.counter[0]}


def reverse_all(a,b,evidence,claim,forward,reverse):
    p=Proof(b);fixed=b['var_index']['obj_constant'];p.add('Eq',p.eqpair({'VarUpper':fixed},{'VarLower':fixed}));rows={}
    for cert in evidence['reverse_row_certificates']:
        terms=[[{'RowEq':i},F(c)] for i,c in cert['target_equalities']];residual=parse_expr(cert['residual']);maximum=F(cert['residual_maximum'])
        if cert['kind']=='Eq':assert residual==expression() and maximum==0
        else:
            for i,c in residual[1].items():terms.append([{'VarUpper' if c>0 else 'VarLower':i},abs(c)])
        row=a['rows'][cert['source_row']];wanted=substitute(row_fact(row,{'E':'RowEq','L':'RowUpper','G':'RowLower'}[row['sense']]),reverse)
        rows[cert['source_row']]=p.prove(cert['kind'],wanted,terms,constant=maximum)
    return emit(p,a,reverse,claim,rows=rows,inverse=forward,inverse_level=F(-160))


def prepare(a,b,evidence):
    forward=list(map(parse_expr,evidence['forward_map']));reverse=list(map(parse_expr,evidence['reverse_map']))
    base={'input_integers':True,'output_integers':True,'projection':[],'inverse':None,'objective':'Equal'}
    claims=[{**base,'reverse':False,'objective':'NonIncreasing','input_objective_lower':'-160'},
            {**base,'reverse':False,'input_objective_level':'-160','inverse':2},
            {**base,'reverse':True,'inverse':1}]
    point=[F(z) for z in evidence['source_attainment_values']]
    constant=[expression(e[0]+sum((c*point[i] for i,c in e[1].items()),F(0))) for e in forward]
    p=Proof(a);terms=[[{'VarLower':i},F(1)] for group in evidence['source_p'] for i in group]+[[{'VarUpper':i},F(10)] for i in evidence['source_b']]
    lower=p.lin('Le',terms,plus(expression(-160),a['objective'],-1));p.add('Le',lower)
    global_block=emit(p,b,constant,claims[0]);print('unrestricted bound block complete',flush=True)
    f,details=forward_face(a,b,evidence,claims[1],forward,reverse);print('complete optimal-face forward block',details,flush=True)
    g=reverse_all(a,b,evidence,claims[2],forward,reverse);print('complete original-model reverse block',flush=True)
    point_claim={'Feasible':{'target':False,'integers':True,'objective':'-160'}}
    certificate={'claims':claims,'blocks':[global_block,f,g],'points':[{'claim':point_claim,'values':[str(z) for z in point]}]}
    request={'claims':claims,'points':[point_claim]}
    details.update(obligations_by_claim=[len(block['end']['Return']['checks']) for block in certificate['blocks']],steps_by_claim=[len(block['steps']) for block in certificate['blocks']])
    return certificate,request,details


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test80-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test80'));ap.add_argument('--kernel',type=Path);args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hint=run/'output/audit.json'
    a,b=parse_mps(source),parse_mps(target);evidence=inspect(a,b,json.loads(hint.read_text()));cert,request,details=prepare(a,b,evidence)
    rpa=out/'proof.rpa';req=out/'request.json';rpa.write_text('RPA 9\n'+json.dumps(cert,separators=(',',':'))+'\n');req.write_text(json.dumps(request,separators=(',',':'))+'\n')
    metadata={'case_id':'test80','status':'PROOF_NOT_COMPLETED','protocol_status':'WORKING_VERSION_9_NOT_FROZEN','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Global original minimum -160 with complete source attainment; complete affine inverse bijection between every original integer optimizer and every integer feasible point of the actual target. Suboptimal original points and LP equivalence are not claimed.','counts':{**evidence['dimensions'],**details},'preparation_seconds':time.perf_counter()-start,'rpa_bytes':rpa.stat().st_size,'rpa_sha256':sha(rpa),'kernel_runs':[]}
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    if args.kernel:
        kernel=args.kernel.resolve();metadata['kernel_binary_sha256']=sha(kernel)
        for command in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(req)]]:
            then=time.perf_counter();p=subprocess.run([str(kernel)]+command,capture_output=True,text=True);metadata['kernel_runs'].append({'command':[str(kernel)]+command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'wall_seconds':time.perf_counter()-then})
            payload=json.loads(p.stdout) if p.stdout else {'status':'IO_ERROR'}
            if p.returncode:
                metadata['status']=payload['status'];(out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        assert payload['status']=='VERIFIED';metadata['status']='VERIFIED'
        metadata['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','proof.rpx','request.json']}
        (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({k:metadata[k] for k in ['status','protocol_status','counts','preparation_seconds','rpa_bytes']},indent=2),flush=True)


if __name__=='__main__':main()
