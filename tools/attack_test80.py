#!/usr/bin/env python3
"""Deterministic whole-certificate rejection attacks for actual test80."""
from pathlib import Path
import argparse,copy,json,subprocess,time
from fractions import Fraction as F
from prepare_test40 import sha


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--case',type=Path,default=Path('cases/test80'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args()
    out=args.case.resolve();kernel=args.kernel.resolve();positive=json.loads((out/'proof.rpa').read_text().split('\n',1)[1]);evidence=json.loads((out/'optimal_face_structure.json').read_text());meta=json.loads((out/'preparation.json').read_text());assert meta['status']=='VERIFIED'
    attacks=out/'attacks';attacks.mkdir(exist_ok=True);start=time.perf_counter();results=[]
    descriptions={
      'negative_global_bound_multiplier':'A source lower bound is multiplied negatively in the unrestricted global bound proof.',
      'wrong_round_integer_expression':'A middle X-Y rounding step borrows INT(X), which is a different expression.',
      'lost_optimal_level_contract':'The source-face direction removes its caller-requested objective level.',
      'omitted_original_inverse_coordinate':'The forward face map omits its last original-source coordinate inverse check.',
      'omitted_inverse_level_membership':'The reverse map omits mandatory membership in the opposing objective-level domain.',
      'wrong_unlinked_reconstruction':'An independent original assignment coordinate is reconstructed from another target choice.',
      'suboptimal_attainment_point':'The claimed attaining source point changes one P from zero to one, giving objective -159.',
      'missing_middle_original_row':'A middle actual source-row obligation is omitted from the reverse proof.',
      'version_downgrade':'The RPA header is downgraded to V8 while requesting an objective-level domain.',
    }
    for name,reason in descriptions.items():
        bad=copy.deepcopy(positive);version=9
        if name=='negative_global_bound_multiplier':bad['blocks'][0]['steps'][0]['Lin']['terms'][0][1]='-1'
        elif name=='wrong_round_integer_expression':
            rounds=[s['Round'] for s in bad['blocks'][1]['steps'] if 'Round' in s];step=rounds[len(rounds)//2];step['integer']={'VarInt':evidence['source_x'][0][0]}
        elif name=='lost_optimal_level_contract':bad['claims'][1].pop('input_objective_level')
        elif name=='omitted_original_inverse_coordinate':bad['blocks'][1]['end']['Return']['checks'].pop()
        elif name=='omitted_inverse_level_membership':bad['blocks'][2]['end']['Return']['checks'].pop()
        elif name=='wrong_unlinked_reconstruction':
            i,j=evidence['unlinked_assignments'][:2];old=evidence['source_x'][i][0];other=evidence['source_x'][j][0];bad['blocks'][2]['end']['Return']['map'][old]=copy.deepcopy(bad['blocks'][2]['end']['Return']['map'][other])
        elif name=='suboptimal_attainment_point':bad['points'][0]['values'][evidence['source_p'][0][0]]='1'
        elif name=='missing_middle_original_row':
            index=3*evidence['dimensions']['source_variables']+evidence['dimensions']['source_rows']//2;bad['blocks'][2]['end']['Return']['checks'].pop(index)
        else:version=8
        rpa=attacks/f'{name}.rpa';rpx=attacks/f'{name}.rpx';rpa.write_text(f'RPA {version}\n'+json.dumps(bad,separators=(',',':'))+'\n')
        then=time.perf_counter();assembled=subprocess.run([str(kernel),'assemble',str(rpa),str(rpx)],capture_output=True,text=True);assembly=json.loads(assembled.stdout)
        entry={'mutation':name,'rule_broken':reason,'rpa_sha256':sha(rpa),'assemble_exit_code':assembled.returncode,'assembly':assembly}
        if name=='version_downgrade':assert assembled.returncode==2 and assembly['status']=='INVALID'
        else:
            assert assembled.returncode==0,(name,assembled.stdout,assembled.stderr)
            replay=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(rpx),str(out/'request.json')],capture_output=True,text=True);payload=json.loads(replay.stdout)
            assert replay.returncode==2 and payload['status']=='INVALID',(name,replay.stdout,replay.stderr)
            entry.update(exit_code=replay.returncode,result=payload,rpx_sha256=sha(rpx))
        entry['wall_seconds']=time.perf_counter()-then;results.append(entry);print(name,'INVALID',flush=True)
        rpa.unlink()
        if rpx.exists():rpx.unlink()
    meta['negative_checks']=results;meta['attack_preparer']={'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))};meta['attack_kernel_sha256']=sha(kernel);meta['attack_seconds']=time.perf_counter()-start
    meta['attack_storage']='Exact deterministic mutation recipes and full outcomes/hashes retained; large temporary mutated RPA/RPX files removed after each rejection. Positive artifacts remain unchanged.'
    (out/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'attacks':len(results),'all':'INVALID','seconds':meta['attack_seconds']},indent=2))


if __name__=='__main__':main()
