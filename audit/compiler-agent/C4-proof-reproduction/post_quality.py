from pathlib import Path
import hashlib,json,shutil,subprocess,time
ROOT=Path('/Users/bhz/Code/kernel');RUNS=Path('/Users/bhz/Code/reform_test/runs')
original=RUNS/'test16-nomf-compiler-batch-C4-20261015'
fresh=RUNS/'test16-nomf-proof-repro-C4-20261015'
fresh.mkdir()
for directory in ('input','output'):shutil.copytree(original/directory,fresh/directory)
(fresh/'output/verification.json').unlink()
audit=ROOT/'audit/compiler-agent/C4-test16-nomf-review';audit.mkdir()
started=time.monotonic()
with (audit/'verify.log').open('w') as log:
    result=subprocess.run(['/Users/bhz/miniforge3/envs/bigdata/bin/python','output/verify.py'],cwd=fresh,stdout=log,stderr=subprocess.STDOUT,timeout=120)
record={'original_run':str(original),'fresh_run':str(fresh),'exit_code':result.returncode,'wall_s':time.monotonic()-started,'log':str(audit/'verify.log'),
        'verifier_sha256':hashlib.sha256((original/'output/verify.py').read_bytes()).hexdigest(),
        'verification':json.loads((fresh/'output/verification.json').read_text()) if (fresh/'output/verification.json').exists() else None,
        'scope_note':'Independent code review of supplied exact ordered zero and equality witnesses is still required; this replay alone is not a Kernel certificate.'}
(audit/'replay.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'nomf_replay_status':record['verification']['status'] if record['verification'] else None,'seconds':record['wall_s']}),flush=True)
for case in ('test16','test88'):
    command=['python3','tools/evaluate_compiler_quality.py','--batch',str(RUNS/'compiler-batch-C4-20261015'),'--label',f'C4-{case}-quality','--cases',case,'--repeat-threshold','30']
    code=subprocess.run(command,cwd=ROOT).returncode
    if code:raise SystemExit(code)
