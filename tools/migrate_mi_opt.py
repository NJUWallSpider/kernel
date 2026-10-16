#!/usr/bin/env python3
"""One-time V1–V10 corpus migration. The legacy decoder is an external binary.

Only unrestricted integer directions with Equal/NonIncreasing objectives qualify.
The new verifier must independently accept every migrated proof. Historical
receipts and original proofs are never overwritten.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path
from case_delivery import load_delivery

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def call(binary,*args):
    r=subprocess.run([str(binary),*map(str,args)],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return json.loads(r.stdout)

def trim(block,count):
    kind,end=next(iter(block['end'].items()))
    if kind=='Return':
        if len(end['checks'])<count:raise ValueError('Missing original obligations')
        end['checks']=end['checks'][:count]
    elif kind=='Split':
        trim(end['left'],count);trim(end['right'],count)
    elif kind in ('FlowLift','SubflowLift','IntervalLift','SignedLift','MenuLift'):
        trim(end['body'],count)
    elif kind!='Absurd':raise ValueError('Unsupported terminal in complete MI direction: '+kind)

def obligations(model):
    return 1+sum((v['lower'] is not None)+(v['upper'] is not None)+v['integer'] for v in model['variables'])+sum(1 if r['lower'] is not None and r['lower']==r['upper'] else (r['lower'] is not None)+(r['upper'] is not None) for r in model['rows'])

def prepare(legacy,output):
    output.mkdir(parents=True,exist_ok=True);records=[]
    for case in sorted((ROOT/'cases').iterdir()):
        receipt=case/'preparation.json'
        if not receipt.is_file():continue
        metadata=json.loads(receipt.read_text())
        if metadata.get('status')!='VERIFIED':continue
        delivery=load_delivery(case,metadata);directory=output/case.name;directory.mkdir(exist_ok=True)
        models=[]
        for role in ('source','target'):
            path=directory/(role+'.json');call(legacy,'export-model',delivery[role],path)
            models.append(json.loads(path.read_text()))
        selected={};origins=[]
        for index,piece in enumerate(delivery['pieces']):
            path=directory/f'legacy-{index}.rpa';call(legacy,'disassemble',piece['rpx'],path)
            cert=json.loads(path.read_text().split('\n',1)[1]);origins.append({'path':str(piece['rpx']),'sha256':digest(piece['rpx'])})
            for claim,block in zip(cert['claims'],cert['blocks']):
                direction='reverse' if claim['reverse'] else 'forward'
                if direction in selected or not(claim['input_integers'] and claim['output_integers'] and claim['objective'] in ('Equal','NonIncreasing')):continue
                if claim.get('input_objective_level') is not None or claim.get('input_halfspace') is not None:continue
                trim(block,obligations(models[0 if claim['reverse'] else 1]));selected[direction]=block
            del cert
            path.unlink()
        if set(selected)!={'forward','reverse'}:raise ValueError(case.name+': incomplete MI directions')
        certpath=directory/'certificate.json';certpath.write_text(json.dumps(selected,separators=(',',':'))+'\n')
        records.append({'case':case.name,'source':str(delivery['source']),'target':str(delivery['target']),
            'source_sha256':digest(delivery['source']),'target_sha256':digest(delivery['target']),
            'legacy_proofs':origins,'certificate_json':str(certpath),'certificate_sha256':digest(certpath),
            'proof':str(case/'optimization.rpx')})
        print(case.name,flush=True)
    (output/'manifest.json').write_text(json.dumps({'legacy_kernel_sha256':digest(legacy),'cases':records},indent=2)+'\n')

def finish(kernel,output):
    manifest=json.loads((output/'manifest.json').read_text())
    for item in manifest['cases']:
        certificate=Path(item['certificate_json'])
        if digest(certificate)!=item['certificate_sha256']:raise ValueError('Changed migration input')
        for role in ('source','target'):
            if digest(Path(item[role]))!=item[role+'_sha256']:raise ValueError('Changed model')
        call(kernel,'compile',certificate,item['proof'])
        report=call(kernel,'verify',item['source'],item['target'],item['proof'])
        if report.get('guarantee')!='MI_OPT':raise ValueError('Missing optimization guarantee')
        record={**item,'proof_sha256':digest(Path(item['proof'])),'verification':report}
        (ROOT/'cases'/item['case']/'optimization.json').write_text(json.dumps(record,indent=2)+'\n')
        print(item['case'],report['status'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--legacy',type=Path);p.add_argument('--kernel',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'target/mi-opt-migration');a=p.parse_args()
    if a.legacy:prepare(a.legacy.resolve(),a.out.resolve())
    if a.kernel:finish(a.kernel.resolve(),a.out.resolve())
