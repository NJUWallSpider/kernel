#!/usr/bin/env python3
"""Six full-certificate attacks against unchanged actual test87 models/request."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,subprocess,tempfile,time
from prepare_test40 import sha


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=Path('cases/test87'));ap.add_argument('--kernel',type=Path,required=True);args=ap.parse_args();out=args.out.resolve();kernel=args.kernel.resolve();receipt=json.loads((out/'preparation.json').read_text());assert receipt['status']=='VERIFIED';proof=out/'proof.rpa';header,body=proof.read_text().split('\n',1);cert=json.loads(body);del body
    first=cert['blocks'][0]['end']['IntervalLift'];last=first['body']
    while 'IntervalLift' in last['end']:last=last['end']['IntervalLift']['body']
    results=[];start=time.perf_counter()
    for name,why in [
        ('missing_interval_pair','One actual OR lift omits a lower-upper compatibility check.'),
        ('continuous_integrality_witness','An integer split cites a new continuous lift coordinate as its integrality witness.'),
        ('wrong_round_integer','A covering-row rounding step is supplied an integer expression with one coefficient sign reversed.'),
        ('negative_cost_multiplier','The global cost combination negates a genuine OR upper inequality multiplier.'),
        ('nonzero_removed_reconstruction','The reverse map restores one removed original variable as one instead of zero.'),
        ('missing_original_row_check','The reverse Return omits a middle original-row obligation.'),
    ]:
        if name=='missing_interval_pair':
            sequence=first['intervals'][len(first['intervals'])//2]['checks'];old=sequence.pop();undo=lambda:sequence.append(old)
        elif name=='continuous_integrality_witness':
            step=next(x['Cases'] for x in first['body']['steps'] if 'Cases' in x);old=step['integer'];step['integer']={'VarInt':63009};undo=lambda:step.__setitem__('integer',old)
        elif name=='wrong_round_integer':
            rounded=next(x['Round'] for x in first['body']['steps'] if 'Round' in x);step=next(x['Lin'] for x in first['body']['steps'] if 'Lin' in x and x['Lin']['id']==rounded['integer']['Local']);term=step['terms'][0];old=term[1];term[1]=str(-F(old));undo=lambda:term.__setitem__(1,old)
        elif name=='negative_cost_multiplier':
            ident=last['end']['Return']['checks'][-1]['Local'];step=next(x['Lin'] for x in last['steps'] if 'Lin' in x and x['Lin']['id']==ident);term=next(t for t in step['terms'] if 'RowUpper' in t[0]);old=term[1];assert F(old)>0;term[1]=str(-F(old));undo=lambda:term.__setitem__(1,old)
        elif name=='nonzero_removed_reconstruction':
            item=next(e for e in cert['blocks'][1]['end']['Return']['map'] if e=={'constant':'0','terms':[]});item['constant']='1';undo=lambda:item.__setitem__('constant','0')
        else:
            sequence=cert['blocks'][1]['end']['Return']['checks'];position=3*63009+507//2;old=sequence.pop(position);undo=lambda:sequence.insert(position,old)
        with tempfile.TemporaryDirectory(prefix='mutation-',dir=out) as tmp:
            rpa=Path(tmp)/'proof.rpa';rpx=Path(tmp)/'proof.rpx';rpa.write_text(header+'\n'+json.dumps(cert,separators=(',',':'))+'\n')
            assembled=subprocess.run([str(kernel),'assemble',str(rpa),str(rpx)],capture_output=True,text=True);assert assembled.returncode==0,(name,assembled.stdout,assembled.stderr)
            result=subprocess.run([str(kernel),'verify',str(out/'source.mcm'),str(out/'target.mcm'),str(rpx),str(out/'request.json')],capture_output=True,text=True);value=json.loads(result.stdout);assert result.returncode==2 and value['status']=='INVALID',(name,result.stdout,result.stderr)
            results.append({'mutation':name,'rule_broken':why,'exit_code':result.returncode,'result':value,'rpa_sha256':sha(rpa),'rpx_sha256':sha(rpx),'storage':'Temporary full artifacts removed after rejection; this deterministic script reproduces exact bytes from the bound positive RPA.'})
        undo();print(json.dumps({'mutation':name,'status':value['status'],'message':value.get('message')}),flush=True)
    receipt['negative_checks']=results;receipt['attack_preparer']={'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))};receipt['attack_kernel_binary_sha256']=sha(kernel);receipt['attack_seconds']=time.perf_counter()-start;(out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert sha(proof)==receipt['rpa_sha256'];print(json.dumps({'status':'PASS','negative_checks':len(results),'seconds':receipt['attack_seconds']}))
if __name__=='__main__':main()
