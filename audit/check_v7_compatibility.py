#!/usr/bin/env python3
"""Assemble existing V1--V6 actual RPA with V7, without modifying any artifact."""
from pathlib import Path
import subprocess, tempfile, hashlib, json, time
ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
binary=ROOT/'target/release/rpx'; results=[]
with tempfile.TemporaryDirectory(prefix='rpx-v7-compat-') as tmp:
    for rpa in sorted((ROOT/'cases').glob('*/proof.rpa')):
        with rpa.open('rb') as f: header=f.readline().decode().strip()
        if header not in [f'RPA {v}' for v in range(1,7)]: continue
        prior=rpa.with_suffix('.rpx')
        if not prior.exists(): continue
        out=Path(tmp)/(rpa.parent.name+'.rpx');start=time.monotonic()
        proc=subprocess.run([str(binary),'assemble',str(rpa),str(out)],capture_output=True,text=True)
        entry={'case':rpa.parent.name,'version':header,'rpa_sha256':sha(rpa),'prior_rpx_sha256':sha(prior),'exit_code':proc.returncode,'seconds':time.monotonic()-start,'stdout':proc.stdout,'stderr':proc.stderr}
        entry['byte_identical']=proc.returncode==0 and out.read_bytes()==prior.read_bytes()
        if out.exists(): entry.update(new_rpx_sha256=sha(out),rpx_bytes=out.stat().st_size)
        results.append(entry)
        print(entry['case'],entry['byte_identical'],flush=True)
report={'status':'PASS' if all(r['byte_identical'] for r in results) else 'FAIL','binary':str(binary),'binary_sha256':sha(binary),'cases':results}
(ROOT/'audit/v7_compatibility.json').write_text(json.dumps(report,indent=2)+'\n')
if report['status']!='PASS': raise SystemExit(1)
