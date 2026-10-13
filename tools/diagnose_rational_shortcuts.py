#!/usr/bin/env python3
"""One fresh baseline/candidate test57 replay, explicitly not a benchmark.

Run only after the prototype has passed tests and a locked release build. Parent
schedules fixed matrix repetitions separately. Refuse to replace old evidence.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'bench/rational-shortcuts-prototype'
OUTPUT = DEST / 'diagnostic.json'
if OUTPUT.exists():
    raise SystemExit('Diagnostic exists; preserve it rather than overwriting')
baseline = ROOT / 'target/validation-checkpoint-v7/release/rpx'
candidate = DEST / 'target/release/rpx'
inputs = [ROOT / 'cases/test57' / name for name in ['source.mcm','target.mcm','proof.rpx','request.json']]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
document = {'diagnostic_only':True,
            'conditions':'One baseline then one candidate fresh process; files warm, no cache flush, other agents/apps may be active. Not an isolated speedup claim.',
            'inputs':{str(path.relative_to(ROOT)): {'sha256':sha(path),'bytes':path.stat().st_size} for path in inputs},
            'runs':[]}
baseline_receipt = json.loads((ROOT/'bench/results/theorem-v7-quiescent/raw.json').read_text())
assert sha(baseline) == baseline_receipt['kernel_sha256']
for label, kernel in [('baseline',baseline),('candidate',candidate)]:
    command = [str(kernel),'verify',*[str(path) for path in inputs]]
    started = time.perf_counter_ns()
    result = subprocess.run(command,capture_output=True,text=True)
    elapsed = time.perf_counter_ns()-started
    observation = {'label':label,'command':command,'kernel_sha256':sha(kernel),
                   'exit_code':result.returncode,'process_ns':elapsed,'stdout':result.stdout,'stderr':result.stderr}
    try:
        observation['result'] = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    document['runs'].append(observation)
    OUTPUT.write_text(json.dumps(document,indent=2)+'\n')
    if result.returncode or observation.get('result',{}).get('status') != 'VERIFIED':
        raise SystemExit(f'{label} failed; diagnostic saved')
first,second = document['runs']
document['identical_mathematical_statistics'] = first['result']['statistics']==second['result']['statistics']
assert document['identical_mathematical_statistics']
document['candidate_over_baseline_execute'] = second['result']['execute_us']/first['result']['execute_us']
document['candidate_over_baseline_process'] = second['process_ns']/first['process_ns']
OUTPUT.write_text(json.dumps(document,indent=2)+'\n')
print(json.dumps({key:document[key] for key in ['identical_mathematical_statistics','candidate_over_baseline_execute','candidate_over_baseline_process']}))
