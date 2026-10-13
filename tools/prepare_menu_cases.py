#!/usr/bin/env python3
"""Prepare complete V7 menu bijections and both LP observation directions."""
from fractions import Fraction as F
from pathlib import Path
import argparse,copy,json,subprocess,time
from audit_menus import inspect,lp_model
from prepare_affine import parse_mps
from prepare_test40 import expression,sha
from prepare_menus import existing_components
from menu_lift_prepare import reverse_integer
from menu_injectivity import injectivity


def prepare(a,b,w):
    partial,counts=existing_components(a,b,w)
    reverse,reverse_block,reverse_counts=reverse_integer(a,b,w,partial['claims'][0])
    forward=[expression(F(e['constant']),{i:F(c) for i,c in e['terms']}) for e in partial['blocks'][0]['end']['Return']['map']]
    unique=injectivity(a,forward,w);pair={'forward_claim':0,'reverse_claim':1}
    cert={'claims':[partial['claims'][0],reverse]+partial['claims'][1:],'blocks':[partial['blocks'][0],reverse_block]+partial['blocks'][1:],'points':[],'bijections':[{'claim':pair,'injectivity':unique}]}
    counts={'source_variables':len(a['vars']),'source_rows':len(a['rows']),'target_variables':len(b['vars']),'target_rows':len(b['rows']),'menus':len(w['menus']),'source_options':sum(len(m['source_options']) for m in w['menus']),'claims':4,'bijections':1,'affine_observations_per_claim':len(b['vars']),'ordinary_component_counts':counts,'integer_reverse':reverse_counts,'injectivity_root_steps':len(unique['steps']),'injectivity_equalities':len(unique['checks'])}
    return cert,counts


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('case',type=int,choices=[59,60]);ap.add_argument('--kernel',type=Path);args=ap.parse_args();start=time.perf_counter();root=Path(__file__).resolve().parents[1];out=root/f'cases/test{args.case}';out.mkdir(parents=True,exist_ok=True)
    w=inspect(args.case);source=Path(w['source']['path']);target=Path(w['target']['path']);a=parse_mps(source);b=lp_model(target) if args.case==60 else parse_mps(target);cert,counts=prepare(a,b,w)
    rpa=out/'proof.rpa';request=out/'request.json';rpa.write_text('RPA 7\n'+json.dumps(cert,separators=(',',':'))+'\n');request.write_text(json.dumps({'claims':cert['claims'],'points':[],'bijections':[p['claim'] for p in cert['bijections']]},separators=(',',':'))+'\n')
    d={'case_id':f'test{args.case}','status':'PROOF_NOT_COMPLETED','source':w['source'],'target':w['target'],'audit':w['audit_hint'],'proof_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},'claims':'Complete objective-preserving integer bijection: affine forward, simultaneous optional-menu reverse, complete right inverse on every target coordinate, and generic doubled-source injectivity on every original coordinate including continuous auxiliaries. Both full LP directions preserve every menu activation/index aggregate and objective, hence group/resource/objective image equality. No LP point bijection claimed.','counts':counts,'preparation_seconds':time.perf_counter()-start,'rpa_sha256':sha(rpa),'rpa_bytes':rpa.stat().st_size,'kernel_runs':[]}
    if args.kernel:
        k=args.kernel.resolve();d['kernel_binary_sha256']=sha(k)
        for cmd in [['canonical',str(source),str(out/'source.mcm')],['canonical',str(target),str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
            p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';(out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
        d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};d['negative_checks']=[]
        for name,reason in [('missing_menu_premise','Omits the activation integrality premise of one optional-menu lift.'),('duplicate_recovery','Assigns two distinct source options the same generated coordinate, violating original constraints or exact moments.'),('missing_auxiliary_injectivity','Omits an original continuous auxiliary equality from the full injectivity obligation list.'),('continuous_split','Uses a continuous source auxiliary as an integer branch witness.'),('missing_right_inverse','Omits a generated full-target-coordinate right-inverse obligation.')]:
            bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['MenuLift'];eq=bad['bijections'][0]['injectivity']
            if name=='missing_menu_premise':lift['menus'][0]['checks'].pop(2)
            elif name=='duplicate_recovery':
                first=w['menus'][0]['source_options'];lift['body']['end']['Return']['map'][first[1]]=copy.deepcopy(lift['body']['end']['Return']['map'][first[0]])
            elif name=='missing_auxiliary_injectivity':eq['checks'].pop(w['objective']['source_variable'])
            elif name=='continuous_split':next(s['Cases'] for s in eq['steps'] if 'Cases' in s)['integer']={'VarInt':w['objective']['source_variable']}
            else:lift['body']['end']['Return']['checks'].pop()
            path=out/(name+'.rpa');path.write_text('RPA 7\n'+json.dumps(bad,separators=(',',':'))+'\n');encoded=out/(name+'.rpx')
            p=subprocess.run([str(k),'assemble',str(path),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
            p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
            d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(path),'rpx_sha256':sha(encoded)})
    (out/'preparation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['case_id','status','counts','preparation_seconds','rpa_bytes']},indent=2))


if __name__=='__main__':main()
