#!/usr/bin/env python3
"""Complete actual test58 MI dominance and objective-preserving recovery.

Untrusted exact author: common OR/AND interval tuples, signed decomposition and
joint demand-bounded subflow; every final model obligation is emitted explicitly.
The historical failed local merge and reverse-only proof remain in attempts/.
"""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_test58 import reverse
from prepare_test46 import Proof,extend,sumexpr
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression as E,plus,mul,expr_json,row_fact,substitute,sha


def round_ref(p,le,integer):
    a,b=p.refexpr(le),p.refexpr(integer);assert a[1]==b[1]
    d=a[0]-b[0];ceil=-((-d.numerator)//d.denominator);i=p.alloc()
    p.steps.append({'Round':{'id':i,'le':le,'integer':integer}});p.facts[i]=('Le',E(b[0]+ceil,b[1]));return {'Local':i}

def forward(a,b,h):
    edges={x['id']:x for x in h['symmetric_edges']};paths={x['id']:x for x in h['series_paths']};bridgeids={x['edge_id'] for x in h['bridge_cut_witnesses']}
    residual=sorted(set(edges)-bridgeids);assert len(residual)==426
    assert set(eid for x in paths.values() for eid,sgn in x['steps'])==set(residual)
    assert sum(len(x['steps']) for x in paths.values())==len(residual)
    assert len(a['vars'])==2500 and len(b['vars'])==607
    p=Proof(a);stages=[]
    def advance(kind,args,ext):
        nonlocal p
        stages.append((p.steps,kind,args));p=Proof(ext,p.counter,p.facts)
    def variable(i):return E(0,{i:1})
    def idx(ed,direction,kind):return a['var_index'][ed[direction][kind]]
    def net_edge(eid,sign=1):
        ed=edges[eid];return E(0,{idx(ed,'forward','x'):sign,idx(ed,'reverse','x'):-sign})
    def net_path(pid):return net_edge(*paths[pid]['steps'][0])
    graph={n:[] for n in h['original_balances']}
    for ed in edges.values():
        x=idx(ed,'forward','x');graph[ed['u']].append((ed['v'],x,1));graph[ed['v']].append((ed['u'],x,-1))
    def network_eq(builder,desired):
        for ed in edges.values():assert desired[1].get(idx(ed,'reverse','x'),F(0))==-desired[1].get(idx(ed,'forward','x'),F(0))
        potential={next(iter(graph)):F(0)};todo=list(potential)
        while todo:
            node=todo.pop()
            for other,x,sgn in graph[node]:
                v=potential[node]+sgn*desired[1].get(x,F(0))
                if other in potential:assert potential[other]==v,('not a cut identity',node,other)
                else:potential[other]=v;todo.append(other)
        assert len(potential)==len(graph)
        return builder.lin('Eq',[[row_ref(a,n),v] for n,v in potential.items() if v],desired)
    # Every actual bridge net is fixed by a full balance-row combination.
    bridge_cost=[]
    for cut in h['bridge_cut_witnesses']:
        eid=cut['edge_id'];ed=edges[eid];value=F(cut['flow']);eq=network_eq(p,plus(net_edge(eid),E(-value)))
        cost=F(ed['cost']);assert cost>=0
        yp,ym=idx(ed,'forward','y'),idx(ed,'reverse','y')
        if value:
            direction='forward' if value>0 else 'reverse';other='reverse' if value>0 else 'forward';y=idx(ed,direction,'y');xother=idx(ed,other,'x')
            le=p.lin('Le',[[row_ref(a,ed[direction]['row']),F(1,82)],[{'VarLower':xother},F(1,82)],[eq,F(-1 if value>0 else 1,82)]],E(abs(value)/82,{y:-1}))
            integer=p.lin('Int',[[{'VarInt':y},F(-1)]],E(0,{y:-1}));up=round_ref(p,le,integer);assert p.refexpr(up)==E(1,{y:-1})
            bridge_cost.append([p.lin('Le',[[up,cost],[{'VarLower':idx(ed,other,'y')},cost]],E(cost,{yp:-cost,ym:-cost})),F(1)])
        else:bridge_cost.extend([[{'VarLower':yp},cost],[{'VarLower':ym},cost]])
    bridge_bound=p.lin('Le',bridge_cost);assert p.refexpr(bridge_bound)[0]==205
    # First simultaneous interval family: OR of each original edge's two binaries.
    intervals=[];edge_order=residual
    for eid in edge_order:
        ed=edges[eid];x,y=idx(ed,'forward','y'),idx(ed,'reverse','y')
        intervals.append({'lower':[expr_json(variable(x)),expr_json(variable(y))],'upper':[expr_json(E(1)),expr_json(E(0,{x:1,y:1}))],
                          'checks':[{'VarUpper':x},{'VarLower':y},{'VarUpper':y},{'VarLower':x}]})
    ext,layout=extend(p.model,intervals);advance('IntervalLift',{'intervals':intervals},ext)
    def or_data(builder,layout,x,y,xint,yint,xlo,xhi):
        z=layout['variable'];lo=[{'RowLower':r} for r in layout['lower']];up=[{'RowUpper':r} for r in layout['upper']]
        lower=builder.lin('Le',[[lo[0],F(1)],[xlo,F(1)]],E(0,{z:-1}))
        def inactive(c,g):
            fixed=c.eqpair(g,xlo);u=c.lin('Le',[[up[1],F(1)],[fixed,F(1)]],E(0,{z:1,y:-1}));eq=c.eqpair(u,lo[1])
            return {'Witness':c.lin('Int',[[eq,F(1)],[yint,F(1)]],variable(z))}
        def active(c,g):
            fixed=c.eqpair(xhi,g);down=c.lin('Le',[[lo[0],F(1)],[fixed,F(-1)]],E(1,{z:-1}));eq=c.eqpair(up[0],down)
            return {'Witness':c.lin('Int',[[eq,F(1)]],variable(z),constant=1)}
        integer=builder.cases('Int',variable(z),variable(x),xint,inactive,active)
        return {'id':z,'lower':lower,'upper':up[0],'sum':up[1],'contains':lo,'integer':integer}
    ors={}
    for eid,l in zip(edge_order,layout):
        ed=edges[eid];x,y=idx(ed,'forward','y'),idx(ed,'reverse','y')
        ors[eid]=or_data(p,l,x,y,{'VarInt':x},{'VarInt':y},{'VarLower':x},{'VarUpper':x})
    # Each path has a constant oriented net; every identity is checked on the
    # original incidence matrix, not inferred from path metadata.
    edgecaps={}
    for pid,path in paths.items():
        for eid,sgn in path['steps']:
            ed=edges[eid];same=network_eq(p,plus(net_path(pid),net_edge(eid,sgn),-1));o=ors[eid]
            for sign in [1,-1]:
                direction='forward' if sign*sgn==1 else 'reverse';other='reverse' if direction=='forward' else 'forward';chosen=0 if direction=='forward' else 1
                edgecaps[pid,eid,sign]=p.lin('Le',[[row_ref(a,ed[direction]['row']),F(1)],[{'VarLower':idx(ed,other,'x')},F(1)],[o['contains'][chosen],F(82)],[same,F(sign)]],plus(mul(net_path(pid),sign),E(0,{o['id']:-82})))
    # Second family: AND across all edge ORs of each nontrivial path.
    long=[pid for pid,path in paths.items() if len(path['steps'])>1];intervals=[]
    for pid in long:
        bits=[ors[eid] for eid,sgn in paths[pid]['steps']];n=len(bits);checks=[x['lower'] for x in bits]
        for j in range(n):checks.append(p.lin('Le',[[x['upper'],F(1)] for i,x in enumerate(bits) if i!=j]))
        intervals.append({'lower':[expr_json(E()),expr_json(E(1-n,{x['id']:1 for x in bits}))],'upper':[expr_json(variable(x['id'])) for x in bits],'checks':checks})
    ext,layout=extend(p.model,intervals);advance('IntervalLift',{'intervals':intervals},ext)
    pz={};andlayout=dict(zip(long,layout))
    def fixed(c,b,g,value):return c.eqpair(g,b['lower']) if value==0 else c.eqpair(b['upper'],g)
    for pid,path in paths.items():
        bits=[ors[eid] for eid,sgn in path['steps']]
        if len(bits)==1:pz[pid]=bits[0];continue
        l=andlayout[pid];z=l['variable'];lo={'RowLower':l['lower'][0]};sumlower={'RowLower':l['lower'][1]};upper=p.lin('Le',[[{'RowUpper':l['upper'][0]},F(1)],[bits[0]['upper'],F(1)]],E(-1,{z:1}))
        def all_one(c,fixes):
            down=c.lin('Le',[[sumlower,F(1)]]+[[r,F(-1)] for r in fixes],E(1,{z:-1}));return c.eqpair(upper,down)
        def integer_tree(c,k,fixes):
            if k==len(bits):return {'Witness':c.lin('Int',[[all_one(c,fixes),F(1)]],variable(z),constant=1)}
            bit=bits[k]
            def zero(ch,g):
                f=fixed(ch,bit,g,0);u=ch.lin('Le',[[{'RowUpper':l['upper'][k]},F(1)],[f,F(1)]],variable(z));eq=ch.eqpair(u,lo)
                return {'Witness':ch.lin('Int',[[eq,F(1)]],variable(z))}
            return {'Witness':c.cases('Int',variable(z),variable(bit['id']),bit['integer'],zero,lambda ch,g:integer_tree(ch,k+1,fixes+[fixed(ch,bit,g,1)]))}
        integer=integer_tree(p,0,[])['Witness'];pz[pid]={'id':z,'lower':lo,'upper':upper,'integer':integer,'contains':[{'RowUpper':r} for r in l['upper']]}
        for sign in [1,-1]:
            wanted=plus(mul(net_path(pid),sign),E(0,{z:-82}))
            unconditional=p.lin('Le',[[edgecaps[pid,path['steps'][0][0],sign],F(1)],[bits[0]['upper'],F(82)]],plus(mul(net_path(pid),sign),E(-82)))
            def bound_tree(c,k,fixes):
                if k==len(bits):return {'Witness':c.lin('Le',[[unconditional,F(1)],[all_one(c,fixes),F(-82)]],wanted)}
                bit=bits[k];eid=path['steps'][k][0]
                def zero(ch,g):return {'Witness':ch.lin('Le',[[edgecaps[pid,eid,sign],F(1)],[fixed(ch,bit,g,0),F(82)],[lo,F(82)]],wanted)}
                return {'Witness':c.cases('Le',wanted,variable(bit['id']),bit['integer'],zero,lambda ch,g:bound_tree(ch,k+1,fixes+[fixed(ch,bit,g,1)]))}
            pz[pid][sign]=bound_tree(p,0,[])['Witness']
    for pid,path in paths.items():
        if len(path['steps'])==1:
            for sign in [1,-1]:pz[pid][sign]=edgecaps[pid,path['steps'][0][0],sign]
    path_cost={}
    for pid,path in paths.items():
        terms=[]
        for k,(eid,sgn) in enumerate(path['steps']):
            cost=F(edges[eid]['cost']);terms.append([ors[eid]['sum'],cost])
            if len(path['steps'])>1:terms.append([pz[pid]['contains'][k],cost])
        path_cost[pid]=p.lin('Le',terms);assert F(path['cost'])==sum(F(edges[eid]['cost']) for eid,sgn in path['steps'])
    # Parallel path activation ORs; keep the complete common tuple before signed lift.
    intervals=[]
    for pair in h['parallel_dominance']:
        x,y=pz[pair['kept']],pz[pair['removed']]
        intervals.append({'lower':[expr_json(variable(x['id'])),expr_json(variable(y['id']))],'upper':[expr_json(E(1)),expr_json(E(0,{x['id']:1,y['id']:1}))],'checks':[x['upper'],y['lower'],y['upper'],x['lower']]})
    ext,layout=extend(p.model,intervals);advance('IntervalLift',{'intervals':intervals},ext)
    targetz={pid:pz[pid] for pid in h['retained_path_ids']};merged={d['kept']:d['removed'] for d in h['parallel_dominance']};parallel_bounds=[]
    for pair,l in zip(h['parallel_dominance'],layout):
        pid,other=pair['kept'],pair['removed'];x,y=pz[pid],pz[other];targetz[pid]=or_data(p,l,x['id'],y['id'],x['integer'],y['integer'],x['lower'],x['upper'])
        ck,cr=F(paths[pid]['cost']),F(paths[other]['cost']);assert cr>=ck>=0 and paths[pid]['u']==paths[other]['u'] and paths[pid]['v']==paths[other]['v']
        parallel_bounds.append([targetz[pid]['sum'],ck]);parallel_bounds.append([y['lower'],cr-ck])
    objective_bound=p.lin('Le',[[bridge_bound,F(1)]]+[[path_cost[pid],F(1)] for pid in paths]+parallel_bounds)
    # Existing SignedLift creates simultaneous nonnegative direction flows.
    decompositions=[];ext=copy.deepcopy(p.model);signed={}
    for pid,path in paths.items():
        z=pz[pid];decompositions.append({'capacity':'82','flow':expr_json(net_path(pid)),'activation':expr_json(variable(z['id'])),'checks':[z['lower'],z['upper'],z['integer'],z[1],z[-1]]})
        v=len(ext['vars']);r=len(ext['rows']);signed[pid]=(v,r)
        for k in range(4):ext['vars'].append({'name':f'sign{v+k}','lower':F(0),'upper':F(1) if k>=2 else None,'integer':k>=2})
        for expression,sense in [(plus(E(0,{v:1,v+1:-1}),net_path(pid),-1),'E'),(E(0,{v+2:1,v+3:1,z['id']:-1}),'E'),(E(0,{v:1,v+2:-82}),'L'),(E(0,{v+1:1,v+3:-82}),'L')]:ext['rows'].append({'name':f'signrow{len(ext["rows"])}','sense':sense,'rhs':-expression[0],'terms':expression[1]})
    advance('SignedLift',{'decompositions':decompositions},ext)
    nodes=h['retained_balance_nodes'];ni={n:i for i,n in enumerate(nodes)};arcs=[];flows=[];nonnegative=[];aggregate_cap={}
    for pid in h['retained_path_ids']:
        path=paths[pid];parts=[pid]+([merged[pid]] if pid in merged else [])
        for direction in [0,1]:
            arcs.append([ni[path['u']],ni[path['v']]] if direction==0 else [ni[path['v']],ni[path['u']]])
            flow=E(0,{signed[qid][0]+direction:1 for qid in parts});flows.append(flow);nonnegative.append(p.lin('Le',[[{'VarLower':i},F(1)] for i in flow[1]],mul(flow,-1)))
            # Both signed activation directions sum to the path activation.
            terms=[]
            for qid in parts:
                v,r=signed[qid];terms.extend([[{'RowUpper':r+2+direction},F(1)],[{'RowEq':r+1},F(82)],[{'VarLower':v+3-direction},F(82)]])
            aggregate_cap[pid,direction]=p.lin('Le',terms,plus(flow,E(0,{pz[qid]['id']:-82 for qid in parts})))
    demands=[[ni[n],str(F(h['residual_balances_after_bridge_substitution'][n]))] for n in nodes if n!=h['residual_source'] and F(h['residual_balances_after_bridge_substitution'][n])]
    assert all(F(d)>=0 for n,d in demands) and sum(F(d) for n,d in demands)==82
    balances=[]
    for node in range(len(nodes)):
        rhs=F(82) if nodes[node]==h['residual_source'] else -F(h['residual_balances_after_bridge_substitution'][nodes[node]])
        desired=plus(sumexpr(mul(flow,int(u==node)-int(v==node)) for (u,v),flow in zip(arcs,flows)),E(-rhs));remaining=desired;terms=[]
        for pid,(v,r) in signed.items():
            coeff=remaining[1].get(v,F(0))
            if coeff:terms.append([{'RowEq':r},coeff]);remaining=plus(remaining,p.refexpr({'RowEq':r}),-coeff)
        terms.append([network_eq(p,remaining),F(1)]);balances.append(p.lin('Eq',terms,desired))
    witness={'nodes':len(nodes),'arcs':arcs,'groups':[{'source':ni[h['residual_source']],'demands':demands,'flows':[expr_json(e) for e in flows],'nonnegative':nonnegative,'balances':balances}]}
    ext=copy.deepcopy(p.model);vbase=len(ext['vars']);rbase=len(ext['rows'])
    for i in range(len(arcs)):ext['vars'].append({'name':f'pruned{vbase+i}','lower':F(0),'upper':F(82),'integer':False})
    for node in range(len(nodes)):
        terms={vbase+i:F(int(u==node)-int(v==node)) for i,(u,v) in enumerate(arcs) if u!=v and (u==node or v==node)}
        rhs=F(82) if nodes[node]==h['residual_source'] else -F(h['residual_balances_after_bridge_substitution'][nodes[node]])
        ext['rows'].append({'name':f'prunedrow{len(ext["rows"])}','sense':'E','rhs':rhs,'terms':terms})
    for i,flow in enumerate(flows):
        ex=plus(variable(vbase+i),flow,-1);ext['rows'].append({'name':f'prunedrow{len(ext["rows"])}','sense':'L','rhs':-ex[0],'terms':ex[1]})
    advance('SubflowLift',{'witness':witness},ext)
    mapping=[None]*len(b['vars']);domain={};rowproof={}
    for j,pid in enumerate(h['retained_path_ids']):
        path=paths[pid];gp,gn=vbase+2*j,vbase+2*j+1;z=targetz[pid];fi,zi=b['var_index'][path['flow_var']],b['var_index'][path['activation_var']]
        mapping[fi]=E(0,{gp:1,gn:-1});mapping[zi]=variable(z['id']);domain[zi]={'VarLower':z['lower'],'VarUpper':z['upper'],'VarInt':z['integer']}
        for direction,name in [(0,path['upper_row']),(1,path['lower_row'])]:
            g,other=(gp,gn) if direction==0 else (gn,gp);wanted=E(0,{g:1,other:-1,z['id']:-82})
            sub={'RowUpper':rbase+len(nodes)+2*j+direction}
            if pid not in merged:ref=p.lin('Le',[[sub,F(1)],[aggregate_cap[pid,direction],F(1)],[{'VarLower':other},F(1)]],wanted)
            else:
                def inactive(c,guard):
                    fixed=c.eqpair(guard,z['lower']);terms=[[sub,F(1)],[aggregate_cap[pid,direction],F(1)],[{'VarLower':other},F(1)],[fixed,F(82)]]+[[r,F(82)] for r in z['contains']]
                    return {'Witness':c.lin('Le',terms,wanted)}
                def active(c,guard):return {'Witness':c.lin('Le',[[{'VarUpper':g},F(1)],[{'VarLower':other},F(1)],[guard,F(82)]],wanted)}
                ref=p.cases('Le',wanted,variable(z['id']),z['integer'],inactive,active)
            rowproof[name]=ref
    fixed=b['var_index']['OBJFIX'];mapping[fixed]=E(1);assert all(x is not None for x in mapping)
    checks=[]
    for i,var in enumerate(b['vars']):
        for typ,desired in [('VarLower',plus(E(var['lower']),mapping[i],-1) if var['lower'] is not None else None),('VarUpper',plus(mapping[i],E(-var['upper'])) if var['upper'] is not None else None),('VarInt',mapping[i] if var['integer'] else None)]:
            if desired is not None:checks.append(p.check('Int' if typ=='VarInt' else 'Le',desired,domain.get(i,{}).get(typ)))
    for row in b['rows']:
        typ='RowEq' if row['sense']=='E' else 'RowUpper';desired=substitute(row_fact(row,typ),mapping)
        if typ=='RowEq':ref=p.lin('Eq',[[{'RowEq':rbase+ni[row['name']]},F(-1)]],desired)
        else:ref=rowproof[row['name']]
        checks.append(p.check('Eq' if typ=='RowEq' else 'Le',desired,ref))
    desired=plus(substitute(b['objective'],mapping),a['objective'],-1);checks.append(p.check('Le',desired,objective_bound))
    block={'steps':p.steps,'end':{'Return':{'map':[expr_json(x) for x in mapping],'checks':checks}}}
    for steps,kind,args in reversed(stages):block={'steps':steps,'end':{kind:{**args,'body':block}}}
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[],'inverse':None}
    return claim,block,{'edge_ors':len(residual),'path_ands':len(long),'parallel_ors':2,'signed_paths':305,'joint_subflow_arcs':len(arcs),'joint_subflow_nodes':len(nodes),'complete_output_obligations':len(checks)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path);ap.add_argument('--out',type=Path,default=Path('cases/test58'));args=ap.parse_args()
    start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test58-nomf-B1');out=args.out;out.mkdir(exist_ok=True,parents=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';hp=run/'output/audit.json';h=json.loads(hp.read_text());a,b=parse_mps(source),parse_mps(target)
    assert sha(source)==h['source']['sha256'] and sha(target)==h['artifact']['sha256']
    claim,block,counts=forward(a,b,h);rev=reverse(a,b,h);cert={'claims':[claim,rev['claims'][0]],'blocks':[block,rev['blocks'][0]]}
    rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 10\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n')
    d={'case_id':'test58','status':'PROOF_NOT_COMPLETED','protocol_status':'WORKING_VERSION_10_NOT_FROZEN','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete MI forward NonIncreasing and reverse Equal; minimum preservation and exact recovery. No LP equivalence and no full feasible-set bijection.','counts':counts,'preparation_seconds':time.perf_counter()-start,'kernel_runs':[],'negative_checks':[]}
    def save():(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
    save()
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary']={'path':str(k),'sha256':sha(k)}
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});save()
            if p.returncode:raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']};save()
        def chain(block):
            result=[block]
            while 'Return' not in result[-1]['end']:
                result.append(next(iter(result[-1]['end'].values()))['body'])
            return result
        attacks=[('missing_middle_balance','A common node conservation premise is absent.'),
                 ('wrong_supply_node','The single supply node is changed without proving its full divergence.'),
                 ('new_coordinate_in_old_premise','The old-scope flow expression refers to a new subflow coordinate.'),
                 ('parallel_zero_branch','The merged inactive-capacity proof omits its binary branch assumption.'),
                 ('bridge_offset','The complete target OBJFIX coordinate no longer has its actual bound 1.'),
                 ('objective_cost_term','A positive path or bridge activation cost term is omitted from the full objective comparison.'),
                 ('incomplete_forward_map','A target coordinate is missing.'),
                 ('reverse_signed_recovery','A source coordinate is recovered with the opposite signed component.')]
        for name,reason in attacks:
            bad=copy.deepcopy(cert);blocks=chain(bad['blocks'][0]);sub=blocks[-2]['end']['SubflowLift'];terminal=blocks[-1]['end']['Return']
            if name=='missing_middle_balance':sub['witness']['groups'][0]['balances'].pop(90)
            elif name=='wrong_supply_node':sub['witness']['groups'][0]['source']=0
            elif name=='new_coordinate_in_old_premise':sub['witness']['groups'][0]['flows'][0]={'constant':'0','terms':[[terminal['map'][0]['terms'][0][0],'1']]}
            elif name=='parallel_zero_branch':
                local=next(s['Cases'] for s in blocks[-1]['steps'] if 'Cases' in s)['left']['steps'];eq=next(s['EqPair'] for s in local if 'EqPair' in s);eq['positive']='Exact'
            elif name=='bridge_offset':terminal['map'][b['var_index']['OBJFIX']]['constant']='2'
            elif name=='objective_cost_term':
                ident=terminal['checks'][-1]['Local'];step=next(s['Lin'] for block in blocks for s in block['steps'] if 'Lin' in s and s['Lin']['id']==ident);step['terms'].pop(0)
            elif name=='incomplete_forward_map':terminal['map'].pop()
            else:
                ret=chain(bad['blocks'][1])[-1]['end']['Return'];ex=next(x for x in ret['map'] if len(x['terms'])==1 and x['terms'][0][0]>=len(b['vars']));ex['terms'][0][0]+=1
            path=out/(name+'.rpa');path.write_text('RPA 10\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            result=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert result.returncode==0,(name,result.stdout,result.stderr)
            result=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);response=json.loads(result.stdout);assert result.returncode!=0 and response['status']=='INVALID',(name,response)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':result.returncode,'result':response,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)});save()
    print(json.dumps({'status':d['status'],'counts':counts,'preparation_seconds':d['preparation_seconds'],'rpa_bytes':rpa.stat().st_size},indent=2))
if __name__=='__main__':main()
