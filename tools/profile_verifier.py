#!/usr/bin/env python3
"""Diagnostic OS stack sampling of our own exact verifier, never an acceptance path."""
from pathlib import Path
import argparse,subprocess,time,json,hashlib,platform
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--kernel',required=True,type=Path);p.add_argument('--case',type=int,default=57);p.add_argument('--label',required=True);a=p.parse_args();d=ROOT/'cases'/f'test{a.case}';out=ROOT/'bench/profiles'/a.label
 if out.exists():raise SystemExit('Refusing to overwrite profile evidence')
 out.mkdir(parents=True);kernel=a.kernel.resolve();command=list(map(str,[kernel,'verify',d/'source.mcm',d/'target.mcm',d/'proof.rpx',d/'request.json']));start=time.perf_counter();child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 time.sleep(.8)
 sampler=['/usr/bin/sample',str(child.pid),'2','1','-file',str(out/'sample.txt')]
 sample=subprocess.run(sampler,capture_output=True,text=True);stdout,stderr=child.communicate();result=json.loads(stdout)
 record={'command':command,'pid':child.pid,'exit_code':child.returncode,'seconds':time.perf_counter()-start,'result':result,'stderr':stderr,'sampling_command':sampler,'sampling_exit_code':sample.returncode,'sampling_stdout':sample.stdout,'sampling_stderr':sample.stderr,'platform':platform.platform(),'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'input_sha256':{f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in ['source.mcm','target.mcm','proof.rpx','request.json']},'interpretation':'External diagnostic stack samples for bottleneck attribution; inclusive stack counts overlap. Sampling perturbs execution and these elapsed times are excluded from fixed benchmark distributions. This observes only our own child process, and its full exact contract must independently return VERIFIED.'}
 (out/'run.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'verification':result['status'],'sampling_exit_code':sample.returncode,'sample_path':str(out/'sample.txt')}))
 if result['status']!='VERIFIED' or child.returncode:raise SystemExit(1)
if __name__=='__main__':main()
