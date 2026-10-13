#!/usr/bin/env python3
"""Compare a new working kernel with all 78 submitted historical requests."""
import argparse, json, subprocess, tempfile, time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from case_delivery import sha,identity

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();kernel=a.kernel.resolve();out=a.out.resolve();assert not out.exists()
 wave=ROOT/'audit/validation/wave-rpx-2026-10-11/run.json';prior=json.loads(wave.read_text());assert len(prior['replayed'])==78
 report={'status':'RUNNING','scope':'Reassemble and replay the exact historical 78 caller requests; supplementary V10 requests are separate. Byte equality and complete non-timing JSON equality required.','kernel':identity(kernel),'historical_wave':identity(wave),'driver':identity(__file__),'cases':[]};start=time.perf_counter()
 def save():out.with_suffix('.progress.json').write_text(json.dumps(report,indent=2)+'\n')
 stable=lambda x:{k:v for k,v in x.items() if not k.endswith('_us')}
 for old in prior['replayed']:
  name=old['case'];folder=ROOT/'cases'/name
  if name=='test62':folder=folder/'attempts/submitted-v7-2026-10-11'
  if name=='test83':folder=folder/'attempts/submitted-v5-2026-10-11'
  before={p:sha(folder/p) for p in ['source.mcm','target.mcm','proof.rpa','proof.rpx','request.json']}
  assert all(before[p]==h for p,h in old['artifacts'].items()),name
  entry={'case':name,'historical_artifacts':before,'commands':[]};report['cases'].append(entry)
  with tempfile.TemporaryDirectory(prefix='rpx-v10-old-') as directory:
   generated=Path(directory)/'proof.rpx'
   for cmd in [['assemble',folder/'proof.rpa',generated],['verify',folder/'source.mcm',folder/'target.mcm',generated,folder/'request.json']]:
    assert sha(kernel)==report['kernel']['sha256'];t=time.perf_counter();r=subprocess.run([str(kernel),*map(str,cmd)],capture_output=True,text=True)
    entry['commands'].append({'command':[str(kernel),*map(str,cmd)],'exit_code':r.returncode,'seconds':time.perf_counter()-t,'stdout':r.stdout,'stderr':r.stderr});save();assert r.returncode==0,(name,r.stdout,r.stderr)
    if cmd[0]=='verify':assert stable(json.loads(r.stdout))==stable(old['result']),name
   assert sha(generated)==before['proof.rpx'],name
  assert all(sha(folder/p)==h for p,h in before.items());entry['status']='PASS';save();print(name,'PASS',flush=True)
 assert sha(kernel)==report['kernel']['sha256'];report.update(status='PASS',passed=len(report['cases']),wall_seconds=time.perf_counter()-start);out.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
