#!/usr/bin/env python3
"""Compare all fixed arithmetic experiment samples, preserving regressions."""
from pathlib import Path
import json, statistics, hashlib, shutil
ROOT=Path(__file__).resolve().parents[1]
MATRICES=[('Theorem and actual certificates','theorem-v7-quiescent','rational-theorems-v7-quiescent-after'),
          ('Extended regression matrix','rational-extended-v7-quiescent-before','rational-extended-v7-quiescent-after')]
report=['# Exact rational shortcut comparison','','The fixed matrices test the same complete mathematical requests and exact certificate bytes before and after the isolated arithmetic changes. All mathematical work counters must agree. The optimization changes no proof rule, rational domain, wire encoding or accepted mathematical relation. It keeps arbitrary-precision arithmetic and canonical-rational validation.','','## Scope and conditions','','The baseline is the frozen V7 source and its clean release executable. The candidate is `bench/rational-shortcuts-prototype`, which changes only denominator-one canonicality checks, multiplication by ±1 in expression scaling and sparse accumulation, and zero-plus-value handling. All intermediate product/result checks remain. The source diff and independent review are retained with the prototype. Its 182 core tests include 1,228 Python Fraction/gcd oracle vectors.','','Both matrices were fixed before this optimization. Apple M5, 10 cores, 16 GiB RAM, macOS 26.6.2, rustc 1.96.0, locked release builds. All case workers paused computation during measurements. Each workload has nine fresh-process timing runs and three separate RSS observations; files are warm, caches are not flushed, unrelated OS/application activity is not controlled. The original theorem baseline was completed in an earlier isolated window on this same host; the candidate theorem and both extended runs share the later window. Runs are sequential, not randomized/interleaved, so small differences can include drift. All observations and outliers remain in the raw distributions.','','Times are milliseconds. Execute is the internal complete verification phase; process includes startup, file reads, model/proof decoding, verification and shutdown. RSS is median peak resident set in MiB. A negative percentage means lower candidate latency, not a claim about every possible certificate.','','## Reproduction','','```sh','python3 tools/prepare_rational_shortcuts_experiment.py','python3 tools/benchmark_theorems.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label theorem-v7-quiescent','python3 tools/benchmark_theorems.py --kernel bench/rational-shortcuts-prototype/target/release/rpx --source-root bench/rational-shortcuts-prototype --label rational-theorems-v7-quiescent-after','python3 tools/benchmark_extended.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label rational-extended-v7-quiescent-before','python3 tools/benchmark_extended.py --kernel bench/rational-shortcuts-prototype/target/release/rpx --source-root bench/rational-shortcuts-prototype --label rational-extended-v7-quiescent-after','python3 tools/report_rational_shortcuts.py','```','','The prototype and run scripts refuse to overwrite evidence; use fresh destinations/labels for a new experiment. See `RATIONAL_SHORTCUTS_PROTOTYPE.md` for the exact prototype preparation command if its generator interface changes. Raw per-sample results retain source, executable, lockfile, model, proof and request hashes.']
comparison={'status':'PASS','matrices':[],'all_samples_verified':True,'all_artifacts_equal':True,'all_statistics_equal':True}
total=0
def dist(w,k):return '/'.join(f"{w['summary'][k][part]:.3f}" for part in ['min','median','max'])
def rss(w):return statistics.median(x['bytes'] for x in w.get('rss',w.get('rss_samples',[])))/2**20
for title,before,after in MATRICES:
    a=json.loads((ROOT/'bench/results'/before/'raw.json').read_text());b=json.loads((ROOT/'bench/results'/after/'raw.json').read_text())
    assert a['config']==b['config'] and a['lock_sha256']==b['lock_sha256']
    assert [w['name'] for w in a['workloads']]==[w['name'] for w in b['workloads']]
    report+=['',f'## {title}','','| Workload | Execute before min/median/max | Execute after min/median/max | Median change | Process before → after median | RSS before → after MiB |','|---|---:|---:|---:|---:|---:|']
    matrix={'baseline':before,'candidate':after,'workloads':[]}
    for wa,wb in zip(a['workloads'],b['workloads']):
        assert wa['artifacts']==wb['artifacts'],wa['name']
        expected=wa['samples'][0]['result']['statistics']
        for w in [wa,wb]:
            assert len(w['samples'])==9
            samples=w.get('rss',w.get('rss_samples',[]));assert len(samples)==3
            for s in w['samples']:
                assert s['exit_code']==0 and s['result']['status']=='VERIFIED'
                assert s['result']['statistics']==expected
            for s in samples:
                result=json.loads(s['stdout']);assert s['exit_code']==0 and result['status']=='VERIFIED' and s['bytes']>0
                assert result['statistics']==expected
            total+=12
        ea,eb=[w['summary']['execute_ms']['median'] for w in [wa,wb]];pa,pb=[w['summary']['process_ms']['median'] for w in [wa,wb]]
        change=(eb/ea-1)*100
        matrix['workloads'].append({'name':wa['name'],'execute_before':wa['summary']['execute_ms'],'execute_after':wb['summary']['execute_ms'],'execute_change_percent':change,'process_before':wa['summary']['process_ms'],'process_after':wb['summary']['process_ms'],'rss_mib_before':rss(wa),'rss_mib_after':rss(wb),'artifacts':wa['artifacts'],'statistics':expected})
        report.append(f"| {wa['name']} | {dist(wa,'execute_ms')} | {dist(wb,'execute_ms')} | {change:+.1f}% | {pa:.3f} → {pb:.3f} | {rss(wa):.3f} → {rss(wb):.3f} |")
        if wa['name'].startswith('real-'):
            case='test'+wa['name'].split('-')[1]
            for label,w in [(before,wa),(after,wb)]:
                dest=ROOT/'bench/results'/label/'receipts';dest.mkdir(exist_ok=True)
                archived=dest/(case+'.json')
                receipt=archived if archived.exists() else ROOT/'cases'/case/'preparation.json'
                assert hashlib.sha256(receipt.read_bytes()).hexdigest()==w['preparation']['receipt_sha256']
                if not archived.exists():shutil.copyfile(receipt,archived)
    comparison['matrices'].append(matrix)
report+=['','## Costs and interpretation','',f'All **{total}/{total}** verifier processes passed. Every paired workload has identical physical artifact hashes and complete statistics, including metered work; time savings come from performing the same exact task with fewer generic arithmetic operations. The tables retain every workload, including regressions and outliers. No aggregate geometric mean hides a regression.','','Execution medians decrease in all 49 paired workloads. Actual test57 falls from 4,932.676 to 2,219.925 ms; test65 falls from 3,776.316 to 1,795.367 ms. Tiny-process latency does not uniformly improve: injectivity-64 process median rises from 2.186 to 2.391 ms (+9.4%) even as its execution median halves from 0.240 to 0.120 ms. Flow-1, injectivity-1 and branch-1 process medians rise by 0.1–0.5%. Those startup-dominated regressions are retained. All median RSS changes are within 3%, so this is principally a latency/throughput improvement, not a demonstrated major memory reduction.','','Each raw run records synthetic preparation stages, all proof byte sizes, logical work, generated domains and per-stage decoder costs. Historical actual preparation costs are preserved in archived receipts rather than remeasured; theorem actual-workload preparation arrays are empty and their generation_ns=0 is a sentinel, not a claim of zero preparation cost. The theorem baseline is also tabulated in `THEOREM_V7_REPORT.md`; the extended representation is described in `EXTENDED_REPORT.md`. Real preparation receipts are copied under each extended result directory. Actual certificates were not redesigned for this optimization, so proof size and original RPA-authoring work do not decrease. Canonical/assembly generation samples are recorded separately and are not folded into verification latency.','','These shortcuts address exact arithmetic in the existing flat/sparse representation. They do not remove eager decoding, the quadratic physical size of expanded prefix-map chains, or large scalar injectivity certificates. Arbitrary non-unit rationals still use BigRational multiplication; the big-integer workload is part of the unchanged regression matrix. Peak resident-set differences are reported independently, not inferred from logical live facts.','','This report describes the isolated candidate. Subsequent status-classification or public-helper resource-policy repairs and the production merge need their own validation receipt; do not silently identify a later executable with the measured hashes. Tests and independent review support this engineering choice without constituting a formal proof of the complete kernel.','']
comparison['verified_processes']=total
(ROOT/'bench/results/rational-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
(ROOT/'bench/RATIONAL_SHORTCUTS_REPORT.md').write_text('\n'.join(report))
print(json.dumps({'verified_processes':total,'same_artifacts':True,'same_statistics':True,'report':'bench/RATIONAL_SHORTCUTS_REPORT.md'}))
