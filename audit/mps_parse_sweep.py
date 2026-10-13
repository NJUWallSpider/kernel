#!/usr/bin/env python3
"""Run the trusted canonicalizer on every corpus MPS, reusing one temporary MCM."""
import argparse, hashlib, json, pathlib, subprocess, tempfile, time
p=argparse.ArgumentParser()
p.add_argument('corpus',type=pathlib.Path)
p.add_argument('--rpx',type=pathlib.Path,default=pathlib.Path('target/release/rpx'))
p.add_argument('--output',type=pathlib.Path,default=pathlib.Path('audit/mps_parse_sweep.json'))
a=p.parse_args(); results=[]; start=time.time()
a.output.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='rpx-mps-sweep-') as tmp:
 for f in sorted(a.corpus.rglob('*.mps')):
  stamp=time.perf_counter(); sha=hashlib.sha256()
  with f.open('rb') as src:
   for chunk in iter(lambda:src.read(1024*1024),b''):sha.update(chunk)
  result=subprocess.run([str(a.rpx.resolve()),'canonical',str(f),str(pathlib.Path(tmp)/'model.mcm')],capture_output=True,text=True)
  try: payload=json.loads(result.stdout)
  except (ValueError,TypeError):payload={'status':'PROCESS_FAILURE','stdout':result.stdout[-3000:],'stderr':result.stderr[-3000:]}
  payload.update(path=str(f),sha256=sha.hexdigest(),input_bytes=f.stat().st_size,exit_code=result.returncode,wall_seconds=time.perf_counter()-stamp)
  results.append(payload)
  report={'command':'python3 audit/mps_parse_sweep.py '+str(a.corpus),'corpus':str(a.corpus),'files':len(results),'elapsed_seconds':time.time()-start,'counts':{s:sum(r['status']==s for r in results) for s in sorted({r['status'] for r in results})},'results':results}
  a.output.write_text(json.dumps(report,indent=2)+'\n')
  print(f"{len(results):3d} {payload['status']:<14} {f.parent.parent.name}/{f.parent.name}/{f.name} {payload.get('message','')}",flush=True)
print(json.dumps(report['counts']))
