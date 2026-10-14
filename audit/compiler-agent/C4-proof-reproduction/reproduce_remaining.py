from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
ROOT=Path('/Users/bhz/Code/kernel')
RUNS=Path('/Users/bhz/Code/reform_test/runs')
AUDIT=ROOT/'audit/compiler-agent/C4-proof-reproduction'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((AUDIT/'reproduction.json').read_text())
for case in ('test16','test88'):
    original=RUNS/f'{case}-compiler-compiler-batch-C4-20261015'
    fresh=RUNS/f'{case}-compiler-proof-repro-C4-20261015'
    fresh.mkdir()
    for directory in ('input','compiler','output'):shutil.copytree(original/directory,fresh/directory)
    # Remove old receipts and the generated files we will compare, so an
    # interrupted author cannot inherit success from the delivered workspace.
    roles=['source.mcm','target.mcm','proof.rpx','request.json']
    files=([f'{stage}/{name}' for stage in ('affine','magnitude') for name in roles]
           if case=='test88' else [])+roles+['reformulated.mps']
    for relative in files:(fresh/'output'/relative).unlink()
    for relative in ('verification.json','verification-all.json','delivery.json',
                     'affine/verification.json','affine/delivery.json',
                     'magnitude/verification.json','magnitude/delivery.json'):
        path=fresh/'output'/relative
        if path.exists():path.unlink()
    command=['/Users/bhz/miniforge3/envs/bigdata/bin/python','output/proof.py']
    started=time.monotonic()
    env={**os.environ,'PYTHONPATH':str(fresh/'compiler/python'),'KERNEL_RPX':str(fresh/'compiler/bin/rpx')}
    print(json.dumps({'event':'reproduction_start','case':case,'fresh':str(fresh)}),flush=True)
    timed_out=False
    with (AUDIT/f'{case}.log').open('w') as log:
        try:proc=subprocess.run(command,cwd=fresh,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=450)
        except subprocess.TimeoutExpired:timed_out=True;proc=None
    receipts=[fresh/'output/verification.json'] if case=='test16' else [fresh/'output'/stage/'verification.json' for stage in ('affine','magnitude')]+[fresh/'output/verification.json']
    statuses=[json.loads(path.read_text()).get('status') if path.exists() else 'MISSING' for path in receipts]
    checks={relative:{'original_sha256':digest(original/'output'/relative),'reproduced_sha256':digest(fresh/'output'/relative) if (fresh/'output'/relative).is_file() else None} for relative in files}
    for check in checks.values():check['byte_identical']=check['original_sha256']==check['reproduced_sha256']
    result={'case':case,'original_run':str(original),'fresh_run':str(fresh),'command':command,
            'exit_code':None if proc is None else proc.returncode,'timed_out':timed_out,'wall_s':round(time.monotonic()-started,6),
            'kernel_statuses':statuses,'kernel_verified':not timed_out and proc.returncode==0 and all(s=='VERIFIED' for s in statuses),
            'files':checks,'all_byte_identical':all(x['byte_identical'] for x in checks.values()),'log':str(AUDIT/f'{case}.log')}
    record['cases'][case]=result
    (AUDIT/'reproduction.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'event':'reproduction_end','case':case,'seconds':result['wall_s'],'kernel_verified':result['kernel_verified'],'byte_identical':result['all_byte_identical']}),flush=True)
