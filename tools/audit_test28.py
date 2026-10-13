#!/usr/bin/env python3
"""Independent exact structure and joint-lifting audit of the actual test28.

This is untrusted evidence preparation, not a universal kernel theorem. It
reconstructs every actual model field and independently decomposes complete
grouped smoke points, including all residual circulation. Corpus files are read
only; no legacy verifier is executed.
"""
from collections import deque
from fractions import Fraction as F
from pathlib import Path
import argparse,json,time
from prepare_affine import parse_mps
from prepare_test40 import expression,sha
from prepare_test71 import evaluate


def inspect(a,b,h):
    nodes=h['node_order'];assert len(nodes)==len(set(nodes))
    ni={n:i for i,n in enumerate(nodes)};arcs=h['arcs'];groups=h['groups']
    assert arcs and groups
    oldrows={};newrows={};oldvars={};newvars={};oldobj={};newobj={}
    retained=h['retained_integer_variables'];assert len(retained)==len(set(retained))
    witness={'nodes':len(nodes),'arcs':[],'groups':[],'retained':[[a['var_index'][v],b['var_index'][v]] for v in retained],
             'aggregate_balance_rows':[a['row_index'][n] for n in nodes]}
    def var(model,dest,name,integer,lower,upper):
        assert name not in dest;v=model['vars'][model['var_index'][name]]
        assert (v['integer'],v['lower'],v['upper'])==(integer,lower,upper)
        dest[name]=v
    def row(dest,name,sense,rhs,terms=None):
        assert name not in dest;dest[name]={'name':name,'sense':sense,'rhs':F(rhs),'terms':dict(terms or {})}
        return dest[name]['terms']
    def add(d,j,c):
        d[j]=d.get(j,F(0))+F(c)
        if not d[j]:del d[j]
    for v in retained:
        x=a['vars'][a['var_index'][v]];assert x['integer']
        var(a,oldvars,v,x['integer'],x['lower'],x['upper']);var(b,newvars,v,x['integer'],x['lower'],x['upper'])
        oc=a['objective'][1].get(a['var_index'][v],F(0))
        if oc:oldobj[a['var_index'][v]]=oc;newobj[b['var_index'][v]]=oc
    for n in nodes:row(oldrows,n,'E',0)
    first=groups[0]['components'][0]
    for arc in arcs:
        z=arc['z'];tail=arc['tail'];head=arc['head'];assert tail in ni and head in ni and tail!=head
        var(a,oldvars,z,False,F(0),None);zi=a['var_index'][z]
        row(oldrows,arc['link'],'E',0,{zi:F(-1)})
        row(oldrows,arc['capacity'],'L',0)
        row(oldrows,arc['aggregate_capacity'],'L',0,{zi:F(1)})
        row(newrows,arc['new_capacity_row'],'L',0)
        add(oldrows[tail]['terms'],zi,-1);add(oldrows[head]['terms'],zi,1)
        cap=[]
        for y,coef in arc['integers'].items():
            assert y in retained;coef=F(coef)
            add(oldrows[arc['capacity']]['terms'],a['var_index'][y],coef)
            add(oldrows[arc['aggregate_capacity']]['terms'],a['var_index'][y],coef)
            add(newrows[arc['new_capacity_row']]['terms'],b['var_index'][y],coef)
            cap.append([a['var_index'][y],str(coef)])
        cost=a['objective'][1].get(a['var_index'][first['arc_flow'][z]],F(0))
        witness['arcs'].append({'tail':ni[tail],'head':ni[head],'aggregate':zi,'link':a['row_index'][arc['link']],
                               'source_capacity':a['row_index'][arc['capacity']],'aggregate_capacity':a['row_index'][arc['aggregate_capacity']],
                               'target_capacity':b['row_index'][arc['new_capacity_row']],'capacity_terms':cap,'common_flow_cost':str(cost)})
    zset={arc['z'] for arc in arcs};assert len(zset)==len(arcs)
    for g in groups:
        source=g['source'];assert source in ni and g['components']
        rhs={n:F(0) for n in nodes};components=[]
        for c in g['components']:
            assert c['source']==source and c['sink'] in ni and c['sink']!=source
            d=F(c['demand']);assert d>0;rhs[source]-=d;rhs[c['sink']]+=d
            oldrows[source]['rhs']-=d;oldrows[c['sink']]['rhs']+=d
            inverse={n:r for r,n in c['node_rows'].items()};assert len(inverse)==len(c['node_rows'])==len(nodes) and set(inverse)==set(nodes)
            for n,r in inverse.items():row(oldrows,r,'E',-d if n==source else d if n==c['sink'] else 0)
            assert set(c['arc_flow'])==zset
            flows=[]
            for j,arc in enumerate(arcs):
                name=c['arc_flow'][arc['z']];var(a,oldvars,name,False,F(0),None);i=a['var_index'][name];flows.append(i)
                add(oldrows[inverse[arc['tail']]]['terms'],i,-1);add(oldrows[inverse[arc['head']]]['terms'],i,1)
                add(oldrows[arc['link']]['terms'],i,1);add(oldrows[arc['capacity']]['terms'],i,1)
                cost=F(witness['arcs'][j]['common_flow_cost'])
                if cost:oldobj[i]=cost
            components.append({'sink':ni[c['sink']],'demand':str(d),'flows':flows,'balance_rows':[a['row_index'][inverse[n]] for n in nodes]})
        assert rhs=={n:F(v) for n,v in g['rhs'].items()}
        assert sum(rhs.values())==0 and rhs[source]<0 and all(rhs[n]>=0 for n in nodes if n!=source)
        assert set(g['new_balance_rows'])==set(nodes)-{h['omitted_balance_node']}
        for n,r in g['new_balance_rows'].items():row(newrows,r,'E',rhs[n])
        assert set(g['new_flow'])==zset
        grouped=[]
        for j,arc in enumerate(arcs):
            name=g['new_flow'][arc['z']];var(b,newvars,name,False,F(0),None);i=b['var_index'][name];grouped.append(i)
            add(newrows[arc['new_capacity_row']]['terms'],i,1)
            for n,coef in [(arc['tail'],-1),(arc['head'],1)]:
                if n in g['new_balance_rows']:add(newrows[g['new_balance_rows'][n]]['terms'],i,coef)
            cost=F(witness['arcs'][j]['common_flow_cost'])
            if cost:newobj[i]=cost
        witness['groups'].append({'source':ni[source],'grouped_flows':grouped,'components':components,
                                   'balance_rows':[b['row_index'][g['new_balance_rows'][n]] if n in g['new_balance_rows'] else None for n in nodes]})
    # Exact whole-model coverage rejects every extra/missing domain, row,
    # coefficient, bound, integrality bit, objective coefficient, and constant.
    for model,vars,rows,obj in [(a,oldvars,oldrows,oldobj),(b,newvars,newrows,newobj)]:
        assert set(vars)==set(model['var_index']) and set(rows)==set(model['row_index'])
        assert all(rows[r['name']]==r for r in model['rows'])
        assert model['objective']==expression(0,obj)
    return witness


def lift(w,target_point,source_dimension):
    """Deterministic exact finite construction; all commodity coordinates agree."""
    old=[None]*source_dimension;arcs=w['arcs'];adj=[[] for _ in range(w['nodes'])]
    for j,arc in enumerate(arcs):adj[arc['tail']].append(j)
    for i,j in w['retained']:old[i]=target_point[j]
    extraction_count=0;circulation_total=F(0)
    for g in w['groups']:
        remaining=[target_point[i] for i in g['grouped_flows']]
        assert all(x>=0 for x in remaining)
        component_flows=[[F(0)]*len(arcs) for _ in g['components']]
        extractions=0
        for k,c in enumerate(g['components']):
            demand=F(c['demand'])
            while demand:
                parent={g['source']:None};q=deque([g['source']])
                while q and c['sink'] not in parent:
                    u=q.popleft()
                    for j in adj[u]:
                        v=arcs[j]['head']
                        if remaining[j]>0 and v not in parent:parent[v]=j;q.append(v)
                assert c['sink'] in parent,('unreachable unsatisfied demand',g['source'],c['sink'],str(demand))
                path=[];node=c['sink']
                while node!=g['source']:
                    j=parent[node];path.append(j);node=arcs[j]['tail']
                amount=min([demand]+[remaining[j] for j in path]);assert amount>0
                for j in path:remaining[j]-=amount;component_flows[k][j]+=amount
                demand-=amount;extractions+=1
                assert extractions<=len(arcs)+len(g['components'])
        balance=[F(0)]*w['nodes']
        for j,arc in enumerate(arcs):balance[arc['tail']]-=remaining[j];balance[arc['head']]+=remaining[j]
        assert all(x==0 for x in balance)
        circulation_total+=sum(remaining);extraction_count+=extractions
        for j,x in enumerate(remaining):component_flows[0][j]+=x
        for c,flow in zip(g['components'],component_flows):
            for i,x in zip(c['flows'],flow):assert old[i] is None;old[i]=x
        for j in range(len(arcs)):assert sum(f[j] for f in component_flows)==target_point[g['grouped_flows'][j]]
    for j,arc in enumerate(arcs):
        i=arc['aggregate'];assert old[i] is None;old[i]=sum(target_point[g['grouped_flows'][j]] for g in w['groups'])
    assert all(x is not None for x in old)
    return old,{'path_extractions':extraction_count,'residual_circulation_arc_flow_preserved':str(circulation_total)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,default=Path('/Users/bhz/Code/reform_test/runs/test28-nomf-B1'));ap.add_argument('--out',type=Path,default=Path('cases/test28'));args=ap.parse_args()
    start=time.perf_counter();run=args.run.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';smoke=run/'output/verification.json'
    a=parse_mps(source);b=parse_mps(target);h=json.loads(audit.read_text());w=inspect(a,b,h)
    results=[]
    for case in json.loads(smoke.read_text())['scenarios']:
        raw=case['new_assignment'];assert set(raw)==set(b['var_index']);point=[F(raw[v['name']]) for v in b['vars']]
        old,trace=lift(w,point,len(a['vars']));se=evaluate(a,old,True);te=evaluate(b,point,True)
        assert not se['violations'] and not te['violations'] and se['objective']==te['objective']
        results.append({'scenario':case['scenario'],'source_checks':se,'target_checks':te,'trace':trace,
                        'target_point':[str(v) for v in point],'constructed_source_point':[str(v) for v in old]})
    (out/'flow_witness.json').write_text(json.dumps(w,indent=2)+'\n')
    (out/'independent_exact_checks.json').write_text(json.dumps({'status':'INDEPENDENT_CHECKED_NOT_KERNEL_CERTIFIED','complete_model_pattern_checked':True,'scenarios':results},indent=2)+'\n')
    metadata={'case_id':'test28','status':'PROOF_NOT_COMPLETED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},
              'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
              'claims':'Preserve all original integer coordinates and each attainable objective value for every fixed integer assignment; complete simultaneous reverse lift preserves all directed-arc totals. Continuous feasible points are not claimed bijective.',
              'counts':{'source_variables':len(a['vars']),'target_variables':len(b['vars']),'source_rows':len(a['rows']),'target_rows':len(b['rows']),'nodes':w['nodes'],'arcs':len(w['arcs']),'groups':len(w['groups']),'commodities':sum(len(g['components']) for g in w['groups']),'retained_integer_coordinates':len(w['retained'])},
              'preparation_seconds':time.perf_counter()-start,'kernel_runs':[],
              'required_kernel_work':['Universal total common-source joint-flow decomposition map, including residual circulation, as a checked reconstruction terminator or equivalent defined semantics.','Complete actual-model binding for all source/target variables, rows, bounds, common arc costs and retained integer coordinates.','Actual RPA/RPX representation and execution of both objective-preserving directions, including all original auxiliary aggregate variables.']}
    (out/'preparation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'case_id':'test28','status':metadata['status'],'counts':metadata['counts'],'scenarios':[{'objective':x['source_checks']['objective'],**x['trace']} for x in results],'seconds':metadata['preparation_seconds']},indent=2))


if __name__=='__main__':main()
