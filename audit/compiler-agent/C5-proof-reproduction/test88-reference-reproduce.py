from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
ROOT=Path('/Users/bhz/Code/kernel');RUNS=Path('/Users/bhz/Code/reform_test/runs');AUDIT=ROOT/'audit/compiler-agent/C5-proof-reproduction'
original=RUNS/'test88-compiler-compiler-batch-C5-20261015';fresh=RUNS/'test88-compiler-proof-repro-C5-reference-20261015';fresh.mkdir()
for directory in ('input','compiler','output'):shutil.copytree(original/directory,fresh/directory)
files=['source.mcm','target.mcm','proof.rpx','request.json','reformulated.mps']
for relative in files:
    if relative!='target.mcm':(fresh/'output'/relative).unlink()
for relative in ['delivery.json','verification.json','certificate.json']:
    p=fresh/'output'/relative
    if p.exists():p.unlink()
started=time.monotonic();command=['/Users/bhz/miniforge3/envs/bigdata/bin/python','output/proof.py'];env={**os.environ,'PYTHONPATH':str(fresh/'compiler/python'),'KERNEL_RPX':str(fresh/'compiler/bin/rpx')}
with (AUDIT/'test88-reference.log').open('w') as log:process=subprocess.run(command,cwd=fresh,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={relative:{'original_sha256':digest(original/'output'/relative),'reproduced_sha256':digest(fresh/'output'/relative) if (fresh/'output'/relative).exists() else None} for relative in files}
for check in checks.values():check['byte_identical']=check['original_sha256']==check['reproduced_sha256']
verifications=[]
for i in range(1):
    stage=fresh/'output'
    p=subprocess.run([str(fresh/'compiler/bin/rpx'),'verify',str(stage/'source.mcm'),str(stage/'target.mcm'),str(stage/'proof.rpx'),str(stage/'request.json')],capture_output=True,text=True)
    verifications.append({'stage':i,'exit_code':p.returncode,'result':json.loads(p.stdout)})
record={'case':'test88','retained_reference_artifact':{'path':str(fresh/'output/target.mcm'),'original_sha256':digest(original/'output/target.mcm'),'role':'Expected-target comparison only at author script line54; independently reconstructed target then recompilation rewrites this file. No prior RPX/request/source/MPS/receipt retained.'},'original_run':str(original),'fresh_run':str(fresh),'command':command,'exit_code':process.returncode,'wall_s':round(time.monotonic()-started,6),'files':checks,'all_byte_identical':all(c['byte_identical'] for c in checks.values()),'independent_stage_verifications':verifications,'kernel_verified':process.returncode==0 and all(v['exit_code']==0 and v['result'].get('status')=='VERIFIED' for v in verifications),'log':str(AUDIT/'test88-reference.log')}
(AUDIT/'test88-reference.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('case','wall_s','exit_code','all_byte_identical','kernel_verified')}),flush=True)
