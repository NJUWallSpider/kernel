#!/usr/bin/env python3
"""Reproduce test58's complete reverse map and expose the forward rerouting gap.

The failed forward is an explicitly labelled local-merge attempt, not a proof of
the committed contract. No kernel rule or authoritative model is changed.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse,copy,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,plus,mul,expr_json,row_fact,substitute,sha
from prepare_test70 import SparseBuilder


def key(e):return e[0],tuple(sorted(e[1].items()))
def exact(e):return not e[1] and e[0]<=0

def reverse(a,b,h):
    extended=copy.deepcopy(b); mapping=[None]*len(a['vars']); decompositions=[];paths={p['id']:p for p in h['series_paths']};edges={e['id']:e for e in h['symmetric_edges']};rbase=len(b['rows']);vbase=len(b['vars'])
    for j,pid in enumerate(h['retained_path_ids']):
        p=paths[pid];fi=b['var_index'][p['flow_var']];zi=b['var_index'][p['activation_var']];decompositions.append({'capacity':'82','flow':expr_json(expression(0,{fi:1})),'activation':expr_json(expression(0,{zi:1})),'checks':[{'VarLower':zi},{'VarUpper':zi},{'VarInt':zi},row_ref(b,p['upper_row']),row_ref(b,p['lower_row'])]})
        v=vbase+4*j;r=rbase+4*j
        for k in range(4):extended['vars'].append({'name':f'$signed{v+k}','lower':F(0),'upper':F(1) if k>=2 else None,'integer':k>=2})
        for terms,sense in [({v:1,v+1:-1,fi:-1},'E'),({v+2:1,v+3:1,zi:-1},'E'),({v:1,v+2:-82},'L'),({v+1:1,v+3:-82},'L')]:extended['rows'].append({'name':f'$signed{len(extended["rows"])}','sense':sense,'rhs':F(0),'terms':{i:F(c) for i,c in terms.items()}})
        for eid,sign in p['steps']:
            e=edges[eid]
            for direction,k in [('forward',0),('reverse',1)]:
                offset=k if sign==1 else 1-k;mapping[a['var_index'][e[direction]['x']]]=expression(0,{v+offset:1});mapping[a['var_index'][e[direction]['y']]]=expression(0,{v+2+offset:1})
    for d in h['parallel_dominance']:
        for eid,_ in paths[d['removed']]['steps']:
            for direction in ('forward','reverse'):
                for t in ('x','y'):mapping[a['var_index'][edges[eid][direction][t]]]=expression()
    for cut in h['bridge_cut_witnesses']:
        flow=F(cut['flow']);e=edges[cut['edge_id']]
        for direction,sign in [('forward',1),('reverse',-1)]:
            value=max(F(0),flow*sign);mapping[a['var_index'][e[direction]['x']]]=expression(value);mapping[a['var_index'][e[direction]['y']]]=expression(int(value>0))
    assert all(e is not None for e in mapping)
    p=SparseBuilder(extended);eqs={key(row_fact(r,'RowEq')):{'RowEq':i} for i,r in enumerate(extended['rows']) if r['sense']=='E'}
    omitted=p.lin('Eq',[[{'RowEq':i},-1] for i,r in enumerate(b['rows']) if r['sense']=='E']);eqs[key(p.refexpr(omitted))]=omitted
    def equal(e):
        terms=[];reduced=e
        for j,pid in enumerate(h['retained_path_ids']):
            v=vbase+4*j;ref={'RowEq':rbase+4*j};c=reduced[1].get(v,F(0))
            if c:terms.append([ref,c]);reduced=plus(reduced,p.refexpr(ref),-c)
        if reduced[1] or reduced[0]:
            if key(reduced) in eqs:terms.append([eqs[key(reduced)],1])
            elif key(mul(reduced,-1)) in eqs:terms.append([eqs[key(mul(reduced,-1))],-1])
            else:raise AssertionError(('unmatched balance',reduced))
        if not terms:return 'Exact'
        return p.lin('Eq',terms,e)
    facts={key(p.refexpr({'RowUpper':i})):{'RowUpper':i} for i,r in enumerate(extended['rows']) if r['sense']=='L'};checks=[]
    for i,v in enumerate(a['vars']):
        e=mapping[i]
        for typ,desired in [('VarLower',plus(expression(v['lower']),e,-1)),('VarUpper',plus(e,expression(-v['upper'])) if v['upper'] is not None else None),('VarInt',e if v['integer'] else None)]:
            if desired is None:continue
            if not e[1]:checks.append('Exact')
            else:checks.append({typ:next(iter(e[1]))})
    for row in a['rows']:
        typ='RowEq' if row['sense']=='E' else 'RowUpper';e=substitute(row_fact(row,typ),mapping)
        checks.append(equal(e) if typ=='RowEq' else 'Exact' if exact(e) else facts[key(e)])
    obj=plus(substitute(a['objective'],mapping),b['objective'],-1);terms=[]
    for j,pid in enumerate(h['retained_path_ids']):terms.append([{'RowEq':rbase+4*j+1},F(paths[pid]['cost'])])
    fixed=b['var_index']['OBJFIX'];fix=p.eqpair({'VarUpper':fixed},{'VarLower':fixed});terms.append([fix,-205]);checks.append(p.lin('Eq',terms,obj))
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}
    return {'claims':[claim],'blocks':[{'steps':[],'end':{'SignedLift':{'decompositions':decompositions,'body':{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}}}}]}


def forward_attempt(a,b,h):
    p=SparseBuilder(a);edges={e['id']:e for e in h['symmetric_edges']};paths={d['id']:d for d in h['series_paths']};mapping=[expression(1) for _ in b['vars']];bounds={}
    def net(pid):
        eid,sign=paths[pid]['steps'][0];e=edges[eid];xp=a['var_index'][e['forward']['x']];xm=a['var_index'][e['reverse']['x']];return expression(0,{xp:sign,xm:-sign})
    parallel={d['kept']:d['removed'] for d in h['parallel_dominance']}
    for pid in h['retained_path_ids']:
        e=net(pid)
        if pid in parallel:e=plus(e,net(parallel[pid]))
        mapping[b['var_index'][paths[pid]['flow_var']]]=e
        for sign,typ in [(1,'upper_row'),(-1,'lower_row')]:
            terms=[]
            for qid in [pid]+([parallel[pid]] if pid in parallel else []):
                eid,s=paths[qid]['steps'][0];ed=edges[eid];chosen='forward' if sign*s==1 else 'reverse';other='reverse' if chosen=='forward' else 'forward';terms.extend([[row_ref(a,ed[chosen]['row']),1],[{'VarUpper':a['var_index'][ed[chosen]['y']]},82],[{'VarLower':a['var_index'][ed[other]['x']]},1]])
            bounds[paths[pid][typ]]=p.lin('Le',terms)
    graph={n:[] for n in h['original_balances']}
    for ed in edges.values():
        xp=a['var_index'][ed['forward']['x']];graph[ed['u']].append((ed['v'],xp,1));graph[ed['v']].append((ed['u'],xp,-1))
    cuts=[]
    for cut in h['bridge_cut_witnesses']:cuts.append(p.lin('Eq',[[row_ref(a,n),1] for n in cut['side']]))
    checks=[]
    for i,v in enumerate(b['vars']):
        for bound in ('lower','upper'):
            if v[bound] is not None:checks.append('Exact')
        if v['integer']:checks.append('Exact')
    for row in b['rows']:
        if row['sense']=='L':checks.append(bounds[row['name']]);continue
        desired=substitute(row_fact(row,'RowEq'),mapping);potential={next(iter(graph)):F(0)};todo=list(potential)
        while todo:
            node=todo.pop()
            for other,xp,sign in graph[node]:
                q=potential[node]+sign*desired[1].get(xp,F(0))
                if other in potential:assert potential[other]==q
                else:potential[other]=q;todo.append(other)
        checks.append(p.lin('Eq',[[row_ref(a,n),v] for n,v in potential.items() if v],desired))
    checks.append('Exact')
    claim={'reverse':False,'input_integers':True,'output_integers':True,'objective':'NonIncreasing','projection':[],'inverse':None}
    return {'claims':[claim],'blocks':[{'steps':p.steps,'end':{'Return':{'map':[expr_json(e) for e in mapping],'checks':checks}}}]}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();start=time.perf_counter();run=Path('/Users/bhz/Code/reform_test/runs/test58-nomf-B1');out=Path('cases/test58/attempts').resolve();out.mkdir(parents=True,exist_ok=True);source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';a=parse_mps(source);b=parse_mps(target);h=json.loads(audit.read_text());k=args.kernel.resolve();d={'case_id':'test58','status':'BLOCKED','acceptance':False,'source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'kernel_binary_sha256':sha(k),'claims':'Feasibility and minimum objective preservation via complete MI forward NonIncreasing and reverse Equal maps; no full LP relation and no all-point bijection.','kernel_runs':[],'negative_checks':[]}
    def execute(cmd):
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);entry={'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(entry);return entry
    for model,name in [(source,'source'),(target,'target')]:assert execute(['canonical',str(model),str(out/(name+'.mcm'))])['exit_code']==0
    for label,cert in [('reverse',reverse(a,b,h)),('local_merge_attempt',forward_attempt(a,b,h))]:
        rpa=out/(label+'.rpa');rpx=out/(label+'.rpx');request=out/(label+'_request.json');rpa.write_text('RPA 8\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps(cert['claims'],separators=(',',':'))+'\n');assert execute(['assemble',str(rpa),str(rpx)])['exit_code']==0;result=execute(['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(rpx),str(request)]);d[label]=result
        assert result['exit_code']==(0 if label=='reverse' else 2),result
    d['blocker']={'kind':'practical_joint_existence_gap_not_ISA_inexpressibility_theorem','obligation':'After merging paths 143 into 142 and 228 into 226, jointly reroute within activated support, preserve all balances and impose |F_p|<=82 Z_p without increasing activation cost. Local arithmetic provides only |merged flow|<=164.','lemma_needed':'For common-source nonnegative flow f with nonnegative sink demands totaling B, choose g with identical balances, 0<=g_e<=f_e and g_e<=B on every arc, allowing loops/disconnected circulations.','alternative_attempt':'FlowLift commodity decomposition was inspected: generated arc-total equalities require sum_k f[k,e]=f[e], not <=f[e], so circulations remain and no per-commodity or aggregate B bound is generated. SignedLift only preserves signed net flows and activated capacities; it cannot change balances by cycle cancellation. Per-arc interval choices are not independent because conservation couples them.','smallest_local_merge_counterexample':{'nodes':['s','t'],'arcs':[['s','t'],['s','t'],['t','s']],'B':82,'flows':[82,82,82],'balances':{'s':82,'t':-82},'merged_forward_flow':164,'capacity':82,'circulation_free_solution':[82,0,0]},'qualification':'The lemma is mathematically true by path/circulation decomposition; existing Split/Lin can in principle encode explicit cycle cancellation or spanning-tree cases. No proof of fundamental ISA impossibility is claimed. A compact complete such route was not established.'}
    fixture={'status':'REGRESSION_FIXTURE_NOT_ACCEPTANCE','lemma':d['blocker']['lemma_needed'],'nodes':2,'arcs':[[0,1],[0,1],[1,0]],'B':82,'f':[82,82,82],'g':[82,0,0],'balances':[82,-82],'merged_f':[164,82],'merged_g':[82,0]}
    assert [fixture['f'][0]+fixture['f'][1]-fixture['f'][2],fixture['f'][2]-fixture['f'][0]-fixture['f'][1]]==fixture['balances']
    assert [fixture['g'][0]+fixture['g'][1]-fixture['g'][2],fixture['g'][2]-fixture['g'][0]-fixture['g'][1]]==fixture['balances']
    assert all(0<=g<=f and g<=fixture['B'] for f,g in zip(fixture['f'],fixture['g']))
    assert fixture['merged_f'][0]>fixture['B']
    for name,variables in [('counterexample_input',[('a',82),('b',82),('r',82)]),('counterexample_merged',[('a',164),('r',82)])]:
        lines=['NAME '+name,'ROWS',' N obj',' E balance']+[' L cap_'+v for v,value in variables]+['COLUMNS']
        for v,value in variables:lines.append('    '+v+' balance '+('-1' if v=='r' else '1')+' cap_'+v+' 1')
        lines+=['RHS','    rhs balance 82']+['    rhs cap_'+v+' 82' for v,value in variables]+['BOUNDS']
        for v,value in variables:lines+=[' FX bound '+v+' '+str(value)]
        lines+=['ENDATA'];(out/(name+'.mps')).write_text('\n'.join(lines)+'\n')
        assert execute(['canonical',str(out/(name+'.mps')),str(out/(name+'.mcm'))])['exit_code']==0
    fixture['kernel_checks']=[]
    for target_point,values in [(False,['82','82','82']),(True,['164','82'])]:
        label='merged_point' if target_point else 'input_point';claim={'Feasible':{'target':target_point,'integers':False,'objective':'0'}};cert={'claims':[],'blocks':[],'points':[{'claim':claim,'values':values}]};rpa=out/(label+'.rpa');rpx=out/(label+'.rpx');request=out/(label+'_request.json');rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':[],'points':[claim]},separators=(',',':'))+'\n');assert execute(['assemble',str(rpa),str(rpx)])['exit_code']==0
        result=execute(['verify',str(out/'counterexample_input.mcm'),str(out/'counterexample_merged.mcm'),str(rpx),str(request)]);assert result['exit_code']==(2 if target_point else 0);fixture['kernel_checks'].append(result)
    (out/'circulation_counterexample.json').write_text(json.dumps(fixture,indent=2)+'\n')
    (out/'reverse_partial.json').write_text(json.dumps({'status':'PARTIAL','acceptance':False,'scope':'Only target-to-source MI Equal; does not discharge the full test58 contract.','kernel_verify':d['reverse']},indent=2)+'\n')
    d['counts']={'original_edges':625,'bridge_cut_equalities_checked':199,'series_internal_nodes':121,'retained_paths':303,'reverse_signed_decompositions':303};d['artifacts']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.iterdir() if p.is_file() and p.name!='blocker.json'};d['preparation_seconds']=time.perf_counter()-start;(out/'blocker.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':'test58','status':'BLOCKED','reverse_status':json.loads(d['reverse']['stdout'])['status'],'forward_error':d['local_merge_attempt']['stdout']},indent=2))

if __name__=='__main__':main()
