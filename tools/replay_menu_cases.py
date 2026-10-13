#!/usr/bin/env python3
"""Replay already prepared full V7 menu artifacts and their negative mutations."""
from pathlib import Path
import argparse,copy,json,subprocess,time
from prepare_test40 import sha


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('case',type=int,choices=[59,60]);ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args();root=Path(__file__).resolve().parents[1];out=root/f'cases/test{args.case}';k=args.kernel.resolve();path=out/'preparation.json';d=json.loads(path.read_text());rpa=out/'proof.rpa';request=out/'request.json'
    assert d['rpa_sha256']==sha(rpa)
    for name in ['source','target']:assert sha(Path(d[name]['path']))==d[name]['sha256']
    text=rpa.read_text();assert text.startswith('RPA 7\n');cert=json.loads(text[6:]);del text
    expected={'claims':cert['claims'],'points':[],'bijections':[p['claim'] for p in cert['bijections']]};assert json.loads(request.read_text())==expected
    d['kernel_binary_sha256']=sha(k);d['kernel_runs']=[];d['negative_checks']=[];start=time.perf_counter()
    for cmd in [['canonical',d['source']['path'],str(out/'source.mcm')],['canonical',d['target']['path'],str(out/'target.mcm')],['assemble',str(rpa),str(out/'proof.rpx')],['verify',str(out/'source.mcm'),str(out/'target.mcm'),str(out/'proof.rpx'),str(request)]]:
        p=subprocess.run([str(k)]+cmd,capture_output=True,text=True);d['kernel_runs'].append({'command':[str(k)]+cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        if p.returncode:
            d['status']=json.loads(p.stdout).get('status','EXECUTION_FAILED') if p.stdout else 'EXECUTION_FAILED';path.write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.stdout+p.stderr)
    d['status']='VERIFIED';d['artifacts']={n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['source.mcm','target.mcm','proof.rpx','request.json']};path.write_text(json.dumps(d,indent=2)+'\n')
    print('Full requested contract VERIFIED; attacking five broken certificates.',flush=True)
    w=json.loads((out/'menu_structure.json').read_text())
    for name,reason in [('missing_menu_premise','Omits the activation integrality premise of one optional-menu lift.'),('duplicate_recovery','Assigns two distinct source options the same generated coordinate, violating original constraints or exact moments.'),('missing_auxiliary_injectivity','Omits an original continuous auxiliary equality from the full injectivity obligation list.'),('continuous_split','Uses a continuous source auxiliary as an integer branch witness.'),('missing_right_inverse','Omits a generated full-target-coordinate right-inverse obligation.')]:
        bad=copy.deepcopy(cert);lift=bad['blocks'][1]['end']['MenuLift'];eq=bad['bijections'][0]['injectivity']
        if name=='missing_menu_premise':lift['menus'][0]['checks'].pop(2)
        elif name=='duplicate_recovery':
            first=next(m['source_options'] for m in w['menus'] if m['maximum_index']>0);lift['body']['end']['Return']['map'][first[1]]=copy.deepcopy(lift['body']['end']['Return']['map'][first[0]])
        elif name=='missing_auxiliary_injectivity':eq['checks'].pop(w['objective']['source_variable'])
        elif name=='continuous_split':next(s['Cases'] for s in eq['steps'] if 'Cases' in s)['integer']={'VarInt':w['objective']['source_variable']}
        else:lift['body']['end']['Return']['checks'].pop()
        attack=out/(name+'.rpa');attack.write_text('RPA 7\n'+json.dumps(bad,separators=(',',':'))+'\n');del bad;encoded=out/(name+'.rpx')
        p=subprocess.run([str(k),'assemble',str(attack),str(encoded)],capture_output=True,text=True);assert p.returncode==0,p.stdout
        p=subprocess.run([str(k),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(encoded),str(request)],capture_output=True,text=True);result=json.loads(p.stdout);assert p.returncode!=0 and result['status']=='INVALID',(name,result)
        d['negative_checks'].append({'mutation':name,'rule_broken':reason,'exit_code':p.returncode,'result':result,'rpa_sha256':sha(attack),'rpx_sha256':sha(encoded)});path.write_text(json.dumps(d,indent=2)+'\n');print(name,result['status'],flush=True)
    d['replay_and_attack_seconds']=time.perf_counter()-start;path.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'case_id':d['case_id'],'status':d['status'],'negative_checks':len(d['negative_checks']),'replay_and_attack_seconds':d['replay_and_attack_seconds']},indent=2))


if __name__=='__main__':main()
