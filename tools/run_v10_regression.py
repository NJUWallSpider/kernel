#!/usr/bin/env python3
"""Run the predeclared four final A/B rounds; never overwrite raw evidence.

Start only after other task workers and acceptance work are idle. The explicit
isolation argument records that operational condition; it is not inferred from
the absence of an individual process name.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--isolation-note',required=True)
    a=ap.parse_args()
    plan_path=ROOT/'bench/v10_regression_measurement_plan.json'
    plan=json.loads(plan_path.read_text())
    out=ROOT/'bench/results/v10-regression-isolation.json'
    if out.exists():raise SystemExit('Preserve existing evidence; this fixed run is already recorded.')
    for name,digest in plan['matrices'].items():
        if sha(ROOT/name)!=digest:raise SystemExit('Fixed workload/driver changed: '+name)
    for version in ['old','candidate']:
        if sha(ROOT/plan[version+'_binary'])!=plan[version+'_binary_sha256']:
            raise SystemExit('Fixed binary changed: '+version)
    record={'status':'RUNNING','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'isolation_note':a.isolation_note,'plan_sha256':sha(plan_path),'commands':[]}
    def save():out.write_text(json.dumps(record,indent=2)+'\n')
    save()
    for item in plan['order']:
        version,kind=item.split('-');label='v10-regression-'+('new' if version=='candidate' else version)+'-'+kind
        script='benchmark.py' if kind=='initial' else 'benchmark_extended.py'
        command=['python3',str(ROOT/'tools'/script),'--kernel',plan[version+'_binary'],
                 '--source-root',plan[version+'_source_snapshot'],'--label',label]
        log=ROOT/'bench/results'/(label+'.log')
        start=time.perf_counter()
        with log.open('x') as stream:r=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        record['commands'].append({'command':command,'exit_code':r.returncode,'seconds':time.perf_counter()-start,
                                   'log':str(log),'log_sha256':sha(log)})
        save();print(label,r.returncode,flush=True)
        if r.returncode:
            record['status']='FAILED';save();raise SystemExit(r.returncode)
    for version in ['old','candidate']:
        if sha(ROOT/plan[version+'_binary'])!=plan[version+'_binary_sha256']:
            record['status']='BINARY_CHANGED';save();raise SystemExit(1)
    record.update(status='FOUR_ROUNDS_COMPLETE',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()

if __name__=='__main__':main()
