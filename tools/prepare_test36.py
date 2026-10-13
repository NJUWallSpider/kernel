#!/usr/bin/env python3
"""Reproduce test36's caller-contract blocker without weakening all-optima scope."""
from pathlib import Path
from fractions import Fraction as F
import argparse,json,subprocess,time
from prepare_affine import parse_mps,row_ref
from prepare_test40 import expression,expr_json,row_fact,sha
from prepare_test21 import substitute


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,default=Path('target/release/rpx'));args=ap.parse_args();started=time.perf_counter()
    run=Path('/Users/bhz/Code/reform_test/runs/test36-nomf-B1');root=Path('cases/test36').resolve();out=root/'attempts';out.mkdir(parents=True,exist_ok=True);k=args.kernel.resolve()
    source=run/'input/model.mps';target=run/'output/reformulated.mps';audit=run/'output/audit.json';a,b=parse_mps(source),parse_mps(target);h=json.loads(audit.read_text())
    inventory=json.loads(Path('audit/corpus_inventory.json').read_text());entry=next(c for c in inventory['cases'] if c['case_id']=='test36')
    for path,key in [(source,'source_models'),(target,'final_target_models')]:assert str(path)==str(run/entry[key][0]['path']) and sha(path)==entry[key][0]['sha256']
    reverse=[expression(0,{b['var_index'][v['name']]:1}) if v['name'] in b['var_index'] else expression() for v in a['vars']]
    checks=[]
    for v,e in zip(a['vars'],reverse):
        i=next(iter(e[1])) if e[1] else None
        if v['lower'] is not None:checks.append({'VarLower':i} if i is not None else 'Exact')
        if v['upper'] is not None:checks.append({'VarUpper':i} if i is not None else 'Exact')
        if v['integer']:checks.append({'VarInt':i})
    for row in a['rows']:
        ref=row_ref(b,row['name']);assert substitute(row_fact(row,next(iter(ref))),reverse)==row_fact(b['rows'][b['row_index'][row['name']]],next(iter(ref)));checks.append(ref)
    assert substitute(a['objective'],reverse)==b['objective'];checks.append('Exact')
    values=[F(0) if v['name'] in h['certificate']['zero_binary_variables'] else F(1) if v['integer'] else None for v in a['vars']]
    pending=list(a['rows'][1:])
    while pending:
        rest=[]
        for row in pending:
            neg=[i for i,c in row['terms'].items() if c==-1];assert len(neg)==1;z=neg[0];pos=[i for i,c in row['terms'].items() if c==1]
            if any(values[i] is None for i in pos):rest.append(row);continue
            values[z]=max(F(0),sum(values[i] for i in pos)-1)
        assert len(rest)<len(pending);pending=rest
    point={'Feasible':{'target':False,'integers':True,'objective':'6425'}}
    claim={'reverse':True,'input_integers':True,'output_integers':True,'objective':'Equal','projection':[],'inverse':None}
    cert={'claims':[claim],'blocks':[{'steps':[],'end':{'Return':{'map':[expr_json(e) for e in reverse],'checks':checks}}}],'points':[{'claim':point,'values':[str(v) for v in values]}]}
    request={'claims':[claim],'points':[point]};rpa=out/'reachable.rpa';rpa.write_text('RPA 3\n'+json.dumps(cert,separators=(',',':'))+'\n');req=out/'reachable_request.json';req.write_text(json.dumps(request,separators=(',',':'))+'\n')
    d={'case_id':'test36','status':'BLOCKED','source':{'path':str(source),'sha256':sha(source)},'target':{'path':str(target),'sha256':sha(target)},'audit':{'path':str(audit),'sha256':sha(audit)},'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Minimum objective preserved and every source integer optimizer has all 200 terminal coordinates zero; no LP claim. This full contract is NOT certified.','kernel_binary_sha256':sha(k),'kernel_runs':[],'negative_checks':[]}
    def invoke(cmd):
        p=subprocess.run([str(k),*map(str,cmd)],capture_output=True,text=True);r={'command':[str(k),*map(str,cmd)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr};d['kernel_runs'].append(r);return r
    for cmd in [['canonical',source,out/'source.mcm'],['canonical',target,out/'target.mcm'],['assemble',rpa,out/'reachable.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'reachable.rpx',req]]:
        result=invoke(cmd);assert result['exit_code']==0,result
    # Intended strong contract is not a recognized caller-bound Claim.
    strong={**claim,'all_source_optimizer_coordinates_zero':[i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']]};request['claims']=[strong];(out/'strong_request.json').write_text(json.dumps(request,separators=(',',':'))+'\n');schema=invoke(['verify',out/'source.mcm',out/'target.mcm',out/'reachable.rpx',out/'strong_request.json']);assert schema['exit_code']!=0,schema
    # Alternative V9 route: the witness value is an upper bound, not an optimum.
    # Source feasible lifts at this fixed level can have positive terminals, so
    # objective-level restriction cannot identify the unknown optimal face.
    terminal=next(i for i,v in enumerate(a['vars']) if v['name'] not in b['var_index']);positive=[*values];positive[terminal]=F(1,4850)
    counter={'claims':[],'blocks':[],'points':[{'claim':{'Feasible':{'target':False,'integers':True,'objective':'6426'}},'values':[str(v) for v in positive]}]};crpa=out/'positive_terminal.rpa';crpa.write_text('RPA 3\n'+json.dumps(counter,separators=(',',':'))+'\n');creq=out/'positive_terminal_request.json';creq.write_text(json.dumps({'claims':[],'points':[counter['points'][0]['claim']]},separators=(',',':'))+'\n')
    for cmd in [['assemble',crpa,out/'positive_terminal.rpx'],['verify',out/'source.mcm',out/'target.mcm',out/'positive_terminal.rpx',creq]]:result=invoke(cmd);assert result['exit_code']==0,result
    d['blocker']={'failing_command':schema['command'],'kernel_error':schema['stdout']+schema['stderr'],'missing_contract':'Caller-bound universal strict-improvement/optimality exclusion with a condition on source terminal positivity or noncanonical lift.','why_existing_rules_do_not_suffice':'Lin/Cases/IntervalLift/Round/Feasible discharge directional obligations only. Objective::NonIncreasing does not bind strict improvement to terminal positivity. V9 input_objective_level accepts one known rational and explicitly asserts neither optimality nor attainment. Here the optimum is unknown; 6425 is only a feasible upper bound, and noncanonical continuous source lifts have a continuum of objective levels. Thus fixed-level V9 optimizer bijection as in test80 is not applicable without a new caller contract.','routes_examined':['Intended all-optimizer caller statement rejected as unknown Claim field.','V9 fixed objective level: cannot bind unknown optimum; independently certified feasible noncanonical positive terminal 1/4850 at objective 6426 demonstrates no unrestricted terminal-integrality assertion.'],'v9_usage':'Not used in any accepted certificate; examined its exact semantics in proof.rs and level.rs.'}
    d['reachable_evidence']='NON-ACCEPTANCE subset: complete objective-equal target-to-source zero extension and source feasible witness objective 6425 VERIFIED; positive-terminal source counterexample at 6426 VERIFIED. Forward minimum-preservation map is not certified here, and these checks do not imply the full requested contract.'
    d['counts']={'source_variables':len(a['vars']),'target_variables':len(b['vars']),'terminal_coordinates':200};d['preparation_seconds']=time.perf_counter()-started;d['artifacts']={name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ['source.mcm','target.mcm','reachable.rpx','reachable_request.json','positive_terminal.rpx']}
    d['schema_gap_sketch']=[
        'Proposed caller-bound contract: Exclusion(input=source integer feasible set, condition=P(x)).',
        'Meaning: every feasible x satisfying P has an actual source-feasible y with f(y)<f(x).',
        'The proof must supply a complete y map (possibly case-split or existential lift).',
        'Every source row, variable domain, and integrality obligation for y must be checked.',
        'The strict objective obligation must be independently bound to the caller condition.',
        'For dominated columns use P(x): sum(deleted integer coordinates)>0.',
        'An exact gap identity f(y)-f(x)=-sum(strict_saving_i*x_i) suffices there.',
        'For test36 use P(x): some terminal>0 or the lift is noncanonical.',
        'A noncanonical lift needs a source-feasible smaller lift and a strictly positive saving.',
        'The canonical active-terminal branch can use the 6425 witness against the 7283 bound.',
        'Composition proves every source optimizer avoids P without knowing the optimum.',
        'Claim currently declares only directional inclusion plus equality/nonincrease and observations.',
        'Objective has no strict or condition-indexed relation.',
        'PointClaim only certifies a particular point or strict LP image inclusion.',
        'input_objective_lower is a universal numerical lower bound, not an improving-map contract.',
        'input_objective_level restricts to one fixed rational; it does not bind an existential optimum.',
        'test80 uses V9 with proved known optimum -160 and attainment; test36 lacks that premise.',
        'No new trusted chain-AND theorem is necessarily needed; the missing piece is caller semantics.'
    ]
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');(root/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':'test36','status':'BLOCKED','schema_error':schema},indent=2))

if __name__=='__main__':main()
