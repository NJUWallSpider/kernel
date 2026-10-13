#!/usr/bin/env python3
"""Summarize retained V7 measurements without rerunning or selecting samples."""
from pathlib import Path
import json, re, statistics

ROOT = Path(__file__).resolve().parents[1]
run = ROOT / 'bench/results/theorem-v7-quiescent'
p = json.loads((run / 'raw.json').read_text())
d = json.loads((ROOT / 'bench/results/theorem-v7-fixture-check/raw.json').read_text())
assert len(p['workloads']) == 26 and not p['diagnostic']
diagnostic = {w['name']: w for w in d['workloads']}
def median(w, key):
    return statistics.median(s['result'][key] for s in w['samples']) / 1000
def distribution(w, key):
    v = w['summary'][key]
    return '/'.join(f'{v[k]:.3f}' for k in ['min', 'median', 'max'])
for w in p['workloads']:
    assert len(w['samples']) == 9 and len(w['rss']) == 3 and w['all_verified']
    assert all(s['exit_code'] == 0 and s['result']['status'] == 'VERIFIED' for s in w['samples'])
    assert all(s['exit_code'] == 0 and json.loads(s['stdout'])['status'] == 'VERIFIED' for s in w['rss'])
    assert w['artifacts'] == diagnostic[w['name']]['artifacts']
    stats = w['samples'][0]['result']['statistics']
    assert all(s['result']['statistics'] == stats for s in w['samples'])
    assert all(json.loads(s['stdout'])['statistics'] == stats for s in w['rss'])

out = ['# V7 theorem and actual-certificate baseline', '',
'All 26 fixed workloads completed nine fresh-process timing repetitions and three separately timed RSS runs: **312/312 VERIFIED**. Every artifact hash agrees with the earlier diagnostic fixture check. No failed sample was discarded. This establishes a baseline for the newly exercised rules; it is not an optimization speedup claim.', '',
'## Conditions and reproduction', '',
'The matrix in `theorem_workloads_v7.json` was fixed before additional arithmetic or representation changes. The executable is a fresh locked release build of `audit/checkpoints/v7-source`: Apple M5, 10 CPU cores, 16 GiB RAM, macOS 26.6.2, aarch64, rustc 1.96.0. All three case workers paused computation for the full benchmark and subsequent profile. OS and unrelated application activity were not controlled. Files were warm after preparation, caches were not flushed, and each observation used a new process. Raw results retain source, lockfile, executable and input hashes. Diagnostic timings from `theorem-v7-fixture-check` overlapped other work and are excluded.', '',
'```sh', 'python3 tools/benchmark_theorems.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label theorem-v7-quiescent', 'python3 tools/report_theorems.py', '```', '',
'The runner refuses an existing label; use a new label for a fresh run. `results/theorem-v7-quiescent/raw.json` preserves every command, result and distribution; `receipts/` preserves the eight original preparation receipts. Times below are milliseconds, shown as min/median/max. Process time includes process startup, file reads, model/proof decoding and checks, verification, serialization and shutdown. Execution is the CLI verification phase. RSS is the median of three separate peak resident-set measurements, in MiB; it includes eagerly loaded models and certificates.', '',
'## Time and physical size', '',
'| Workload | RPA bytes | RPX bytes | Execute ms min/median/max | Process ms min/median/max | RSS MiB |',
'|---|---:|---:|---:|---:|---:|']
for w in p['workloads']:
    out.append(f"| {w['name']} | {w['artifacts']['proof.rpa']['bytes']} | {w['artifacts']['proof.rpx']['bytes']} | {distribution(w, 'execute_ms')} | {distribution(w, 'process_ms')} | {statistics.median(s['bytes'] for s in w['rss']) / 2**20:.3f} |")
out += ['', '## Decode, sparse work and generated domains', '',
'These are medians of the same nine runs, not additional timing samples. Logical obligations and branches, visited linear/substitution coefficient terms, and metered work are distinct from physical bytes. Generated variables/rows are cumulative across extensions and paired-domain checks; they do not measure peak live memory. Work is an explicit sparse-operation budget rather than CPU instructions or bigint bit complexity.', '',
'| Workload | Read ms | Model decode ms | Proof decode ms | Obligations | Branches | Linear/substitution terms | Work | Generated vars/rows |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for w in p['workloads']:
    s = w['samples'][0]['result']['statistics']
    variables = sum(s.get(x+'_generated_variables', 0) for x in ['menu','interval','flow','injectivity'])
    rows = sum(s.get(x+'_generated_rows', 0) for x in ['menu','interval','flow','injectivity'])
    out.append(f"| {w['name']} | {median(w,'read_us'):.3f} | {median(w,'model_decode_us'):.3f} | {median(w,'proof_decode_us'):.3f} | {s['obligations']} | {s['branches']} | {s['linear_terms']}/{s['substitution_terms']} | {s['work']} | {variables}/{rows} |")
out += ['', '## Separate preparation costs', '',
'Synthetic construction, canonicalization and assembly were measured once each in the same preparation run. They are neither repeated distributions nor part of verification latency. The Python generator is untrusted; its output is checked by the same complete model-bound verifier.', '',
'| Synthetic workload | Generate RPA/models ms | Two canonical processes ms | Assembly process ms |',
'|---|---:|---:|---:|']
for w in p['workloads']:
    if w['name'].startswith('test'): continue
    out.append(f"| {w['name']} | {w['generation_ns']/1e6:.3f} | {sum(s['wall_ns'] for s in w['preparation'][:2])/1e6:.3f} | {w['preparation'][2]['wall_ns']/1e6:.3f} |")
out += ['', 'The actual-case values below are historical single preparation observations, copied from bound receipts. They may have different build modes and concurrent preparation activity; **do not compare them as controlled performance results**. They disclose work done before verification. Receipt generation time excludes the subsequent canonical/assembly/verify commands; canonical and assembly are the CLI internal totals, excluding process startup. Each receipt retains its exact executable path/hash. Case19 used the preserved original-scope executable; cases23/28 used debug binaries. The newer release values are still single observations.', '',
'| Actual workload | RPA generation seconds | Two canonical totals ms | Assembly total ms |',
'|---|---:|---:|---:|']
for w in p['workloads']:
    if not w['name'].startswith('test'): continue
    q = json.loads((run/'receipts'/f"{w['name']}.json").read_text())
    stages = [(r['command'][1],json.loads(r['stdout'])) for r in q['kernel_runs']]
    canonical = sum(s['total_us'] for cmd,s in stages if cmd=='canonical')/1000
    assembly = sum(s['total_us'] for cmd,s in stages if cmd=='assemble')/1000
    out.append(f"| {w['name']} | {q['preparation_seconds']:.3f} | {canonical:.3f} | {assembly:.3f} |")
out += ['', '## Interpretation and remaining costs', '',
'Menu scaling checks K=0,2,12 and 1,64,512 independent menus. Every optional-menu activation/index premise, output coordinate and observation is proved; K=0 retains the zero-index equality. Interval scaling checks 1,128,1024 simultaneous equality intervals. Flow scaling uses 1,16,128 common-source groups, each containing two zero-demand commodities on a loop: the full observation preserves arbitrary nonnegative circulation. Paired-domain scaling proves complete identity bijections on 1,64,512 binary coordinates. These selected structures expose checker scaling; they do not establish linear cost for arbitrary real proofs.', '',
'The real cases retain their full original caller contracts, including fiber strictness (18/19), independent intervals (23), common-source flow (28), shared switch aliases (38), integer/LP inverse maps (57), and integer bijection plus LP projection (59/60). Cases59/60 still contain large scalar injectivity proofs: 78,835/67,750 branches and roughly 91.7/90.5 MB RPX. Their resident-set costs remain substantial. Shared fact scopes reduce branch state copying but do not remove eager decoding, complete paired models or the physical proof tree. Further improvements must retain every obligation and actual model binding.', '',
'## External sampling of exact arithmetic', '',
'`profiles/v7-test57-quiescent/run.json` records a successful diagnostic OS sample of the same executable and test57 inputs. The verifier independently returned VERIFIED. `sample.txt` retains the complete stacks. The sampler observed only our child process, starting 0.8 seconds after launch, sampling for two seconds at a requested 1 ms interval. The resulting 1,519 main-thread observations cover a portion of execution, not the complete run; they exclude most initial decoding. Sampling perturbs execution and its elapsed time is not used in the benchmark distributions.', '',
'```sh', 'python3 tools/profile_verifier.py --kernel target/validation-checkpoint-v7/release/rpx --case 57 --label v7-test57-quiescent', '```', '',
'Summing inclusive call-tree entries gives 829 observations under `Context::substitute`, 974 under `Accumulator::add`, 383 under `Context::steps`, 232 under `Context::get`, 381 under rational validation, and 168 under expression scaling. These sets overlap; they must not be added or reported as disjoint CPU percentages. Inlining also means an absent symbol does not imply zero cost. Exclusive top-of-stack examples include bigint right shift (198), gcd (151), trailing-zero counting (122), signed division (114), rational multiplication (35), and accumulator code (32). This supports investigating repeated rational multiplication/reduction and validation before introducing a new number representation. It does not justify weakening canonical-rational checks, using approximate arithmetic, or claiming state maintenance is free.', '',
'The baseline retains full source and unchanged certificate bytes. Any candidate arithmetic shortcut must be tested against an independent exact oracle, preserve intermediate resource checks, pass existing semantic/byte attacks and then rerun fixed workloads with the same mathematical requests. No such optimization is included in this baseline.', '']
(ROOT/'bench/THEOREM_V7_REPORT.md').write_text('\n'.join(out))
print('Validated 312 successful observations and matching diagnostic artifact hashes; wrote bench/THEOREM_V7_REPORT.md')
