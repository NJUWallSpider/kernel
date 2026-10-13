#!/usr/bin/env python3
"""Bind final evidence after, not instead of, executed acceptance and benchmarks."""
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from case_delivery import identity, sha

def read(name):
    return json.loads((ROOT/name).read_text())

def main():
    destination=ROOT/'audit/final_delivery_manifest.json'
    if destination.exists():raise SystemExit('Final immutable manifest already exists.')
    ledger=read('audit/acceptance.json')
    summary=ledger['summary']
    assert summary['total_runs']==summary['model_pairs_present']==81
    assert summary['statuses']=={'VERIFIED':81} and summary['functional_delivery_complete']
    assert set(summary['verified_cases'])=={f'test{n}' for n in range(8,89)}
    assert set(summary['families_with_certified_example'])==set(summary['all_families']) and len(summary['all_families'])==11
    del ledger
    cold=read('audit/validation/v10-complete-cold-build.json')
    assert cold['status']=='PASS' and all(c['exit_code']==0 for c in cold['commands'])
    assert sum(c.get('tests_passed',0) for c in cold['commands'])==262
    assert identity(cold['binary']['path'])['sha256']==cold['binary']['sha256']
    source=read('audit/checkpoints/v10-complete-source.json')
    for name,expected in source['files'].items():
        actual=identity(ROOT/'audit/checkpoints/v10-complete-source'/name)
        assert all(actual[k]==v for k,v in expected.items())
        if name.startswith('crates/'):
            assert sha(ROOT/name)==expected['sha256'],'Production/test source changed after cold build'
    replay=read('audit/validation/v10-complete/run.json')
    assert replay['kernel_sha256']==cold['binary']['sha256'] and replay['all_replayed_verified']
    assert {x['case'] for x in replay['replayed']}==set(summary['verified_cases'])
    kernel_calls=0
    for case in replay['replayed']:
        assert case['exit_code']==0 and case['result']['status']=='VERIFIED'
        for piece in case.get('pieces',[case]):
            assert piece['exit_code']==0 and piece['result']['status']=='VERIFIED'
            kernel_calls+=1
    assert kernel_calls==83
    old=read('audit/validation/v10-complete-old-78-compatibility.json')
    assert old['status']=='PASS' and old['passed']==78 and old['kernel']['sha256']==cold['binary']['sha256']
    gates=read('audit/contract_scope_gates.json')
    for gate in gates['cases'].values():
        assert gate['status']=='REVIEWED_COMPLETE_REQUEST'
        for item in gate['requests']+gate['evidence']:assert sha(item['path'])==item['sha256']
    comparison=read('bench/results/v10-regression-comparison.json')
    assert comparison['status']=='PASS'
    isolation=read('bench/results/v10-regression-isolation.json')
    assert isolation['status']=='FOUR_ROUNDS_COMPLETE' and all(x['exit_code']==0 for x in isolation['commands'])
    capabilities=[]
    for label in ['subflow','strict-image','halfspace']:
        name=f'bench/results/{label}-v10-complete-quiescent/raw.json'
        result=read(name)
        assert result['status']=='ALL_VERIFIED_ISOLATION_DECLARED' and not result['diagnostic_nonisolated']
        assert result['kernel']['sha256']==result['kernel_sha256_after']==cold['binary']['sha256']
        capabilities.extend(result['workloads'])
    assert len(capabilities)==22
    assert sum(len(w['samples'])+len(w['rss']) for w in capabilities)==264
    for workload in capabilities:
        for sample in workload['samples']+workload['rss']:
            assert sample['exit_code']==0 and sample['result']['status']=='VERIFIED'
    followup=read('bench/results/v10-order-sensitivity/raw.json')
    assert followup['status']=='ALL_VERIFIED_ONE_BOUNDED_FOLLOWUP'
    assert followup['timed_calls']==72 and followup['warmup_calls']==8
    files=[
        'audit/acceptance.json','audit/contract_scope_gates.json','audit/corpus_inventory.json',
        'audit/FINAL_DELIVERY_REPORT.md','audit/TRUST_REPORT.md','audit/WORK_LOG.md',
        'audit/checkpoints/v10-complete-source.json','audit/validation/v10-complete-cold-build.json',
        'audit/validation/v10-complete/run.json','audit/validation/acceptance-final-81.log',
        'audit/validation/v10-complete-old-78-compatibility.json',
        'audit/validation/completed-36-projection-independent.json',
        'audit/validation/completed-46-62-83-independent.json','audit/validation/completed-58-independent.json',
        'audit/TEST36_COMPLETE_REVIEW.json','audit/TEST58_COMPLETE_REVIEW.json','audit/TEST83_STRICT_REVIEW.json',
        'audit/CONDITIONAL_DOMAIN_REVIEW.md','audit/CONDITIONAL_WIRE_REVIEW.json',
        'audit/DELIVERY_BUNDLE_FIXTURES.json','audit/SUBFLOW_PRODUCTION_REVIEW.md',
        'docs/CURRENT_FORMAT.md','docs/FORMAT_V10_DRAFT.md','docs/SUBFLOW_DRAFT.md',
        'bench/V10_REGRESSION_REPORT.md','bench/NEXT_CAPABILITY_DRAFT_BASELINE.md',
        'bench/results/v10-regression-comparison.json','bench/results/v10-regression-isolation.json',
        'bench/results/v10-order-sensitivity/raw.json',
        'bench/results/v10-order-sensitivity/ORDER_SENSITIVITY_REPORT.md',
        'tools/cold_checkpoint.py','tools/run_acceptance.py','tools/check_delivery.py',
        'tools/case_delivery.py','tools/prepare_affine.py','tools/run_v10_regression.py',
        'tools/report_v10_regression.py','tools/report_next_capabilities.py',
        'tools/check_v10_order_sensitivity.py','audit/finalize_delivery_manifest.py',
    ]
    result={'status':'DELIVERED_WITH_DOCUMENTED_LIMITATIONS',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'functional_delivery_complete':True,'summary':summary,'cold_tests':262,
            'final_corpus_kernel_calls':83,'historical_compatible_requests':78,
            'fixed_regression_processes':712,'new_capability_processes':264,
            'supplementary_timed_calls':72,'excluded_followup_warmups':8,
            'kernel':cold['binary'],
            'scope':'Evidence index, not a proof authority or protocol freeze. Retains test65 performance regression and trusted-builder/formal-proof limitations.',
            'evidence':{name:identity(ROOT/name) for name in files}}
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('evidence','summary')},indent=2))

if __name__=='__main__':main()
