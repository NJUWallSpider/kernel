#!/usr/bin/env python3
"""Reject incomplete benchmark evidence before summarizing absolute capability costs."""
from pathlib import Path
import argparse,hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def triple(values,scale=1):
    xs=[x/scale for x in values];return f'{min(xs):.3f} / {statistics.median(xs):.3f} / {max(xs):.3f}'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('raw',type=Path,nargs='+');ap.add_argument('--out',type=Path,default=ROOT/'bench/NEXT_CAPABILITY_DRAFT_BASELINE.md');a=ap.parse_args()
    lines=['# Unified draft capability baseline','', 'Absolute measurements for newly supported complete mathematical tasks. There is no speed ratio against an older version that does not support these tasks. Each row reports min / median / max unless marked otherwise.']
    total=0;total_preparations=0
    for path in a.raw:
        d=json.loads(path.read_text());cfg=d['config'];assert d['status']=='ALL_VERIFIED_ISOLATION_DECLARED' and not d['diagnostic_nonisolated'] and d['isolation_note']
        expected=[x['name'] for x in cfg['synthetic']]+[f'test{n}' for n in cfg['actual_cases']];assert [x['name'] for x in d['workloads']]==expected
        assert d['kernel']['sha256']==cfg['kernel_sha256']==d['kernel_sha256_after'];out=path.parent
        archived_build=out/d.get('archived_build_receipt','production-receipt.json');assert sha(archived_build)==d['source_build_receipt_sha256']
        if 'build_receipt_sha256' in cfg:
            assert sha(archived_build)==cfg['build_receipt_sha256'];build=json.loads(archived_build.read_text());assert build['status']=='PASS' and build['binary']['sha256']==d['kernel']['sha256']
        fixed_path=out/'fixed-artifact-manifest.json';assert sha(fixed_path)==d['fixed_artifact_manifest_sha256'];fixed=json.loads(fixed_path.read_text())
        lines+=['',f'## {cfg["schema"]}','',f'Raw evidence: `{path.relative_to(ROOT)}` (SHA-256 `{sha(path)}`). Binary `{d["kernel"]["sha256"]}`. Isolation declaration: {d["isolation_note"]}', '',f'Host: {d["hardware"]}. Cache policy: {d["cache"]}.', '', '| Workload | Source / target vars | MCM total KiB | RPA / RPX KiB | Prepare process ms | Execute ms | Kernel total ms | Process total ms | RSS MiB |','|---|---:|---:|---:|---|---|---|---|---|']
        auxiliary=[]
        for r in d['workloads']:
            assert r['artifacts']==fixed['workloads'][r['name']]
            samples,rss=r['samples'],r['rss'];assert len(samples)==cfg['verification_repetitions'] and len(rss)==cfg['rss_repetitions'] and r['all_verified']
            for x in samples+rss:assert x['exit_code']==0 and x['result']['status']=='VERIFIED' and x['result']['statistics']==r['statistics']
            assert all(x['rss_bytes'] is not None and x['rss_bytes']>0 for x in rss);total+=len(samples)+len(rss)
            if 'generation_counts' in r:
                assert len(r['preparation'])==cfg['preparation_repetitions'];counts=r['generation_counts'];dimensions=f'{counts["source_variables"]} / {counts["target_variables"]}'
                total_preparations+=len(r['preparation'])
                for p in r['preparation']:assert p['generation']['exit_code']==p['assembly']['exit_code']==0 and p['generation']['result']['status']=='GENERATED_EXACT_CHECKED' and p['assembly']['result']['status']=='ASSEMBLED'
                prepared=triple([p['generation']['wall_ns']+p['assembly']['wall_ns'] for p in r['preparation']],1e6)
                fixture=out/'fixtures'/r['name']/f'prepare{cfg["preparation_repetitions"]-1}'
                auxiliary.append((r,counts,triple([p['generation']['result']['generation_ns'] for p in r['preparation']],1e6),triple([p['assembly']['result']['total_us'] for p in r['preparation']],1000)))
            else:
                assert not r['preparation'];receipt=out/f'{r["name"]}-preparation.json';assert sha(receipt)==r['actual_preparation_receipt_sha256']==fixed['actual_preparation_receipt_sha256'];actual=json.loads(receipt.read_text());assert actual['status']=='VERIFIED'
                prepared=f'archived author {actual["preparation_seconds"]*1000:.3f}; not remeasured';dimensions='2500 / 607';fixture=out/'fixtures'/r['name'];auxiliary.append((r,None,'archived receipt','archived receipt'))
            for name,metadata in r['artifacts'].items():assert (fixture/name).stat().st_size==metadata['bytes'] and sha(fixture/name)==metadata['sha256']
            art=r['artifacts'];mcm=(art['source.mcm']['bytes']+art['target.mcm']['bytes'])/1024;rpa=art['proof.rpa']['bytes']/1024;rpx=art['proof.rpx']['bytes']/1024
            row=[r['name'],dimensions,f'{mcm:.3f}',f'{rpa:.3f} / {rpx:.3f}',prepared,triple([x['result']['execute_us'] for x in samples],1000),triple([x['result']['total_us'] for x in samples],1000),triple([x['wall_ns'] for x in samples],1e6),triple([x['rss_bytes'] for x in rss],1024*1024)]
            lines.append('| '+' | '.join(row)+' |')
        lines+=['','| Workload | Model decode ms | Proof decode ms | Generation internal ms | Assembly ms | Logical work | Terminal obligations | Generated vars / rows |','|---|---|---|---|---|---:|---:|---:|']
        for r,counts,gen,assembly in auxiliary:
            s=r['statistics'];gv=sum(v for k,v in s.items() if k.endswith('_generated_variables'));gr=sum(v for k,v in s.items() if k.endswith('_generated_rows'))
            lines.append('| '+' | '.join([r['name'],triple([x['result']['model_decode_us'] for x in r['samples']],1000),triple([x['result']['proof_decode_us'] for x in r['samples']],1000),gen,assembly,str(s['work']),str(s['obligations']),f'{gv} / {gr}'])+' |')
        lines+=['',f'All {len(d["workloads"])} fixed workloads retain every verification and RSS sample. The report checks exact statistics equality and archived artifact hashes. It refuses failed/missing RSS samples or any non-VERIFIED result.', '', 'Synthetic preparation includes complete exact author generation and assembly, including independent nonempty-point checks; direct MCM authoring does not imply measured MPS canonicalization. The subflow author currently scans arcs per node, so its preparation cost includes that simple O(nm) construction. No preparation or scalar cost is represented as constant-time theorem logic. The actual test58 receipt retains separate source/target canonicalization and prior author/assembly times; its empty preparation array means unmeasured here, never zero cost.']
    lines+=['',f'Total successful measured fresh verification/RSS processes: {total}. Separately, {total_preparations} fresh synthetic preparations each include one author process and one assembler process. Actual test58 preparation is archived and not remeasured. These measurements establish an absolute draft baseline, not an optimization claim, formal correctness proof, protocol freeze or proof that all possible workloads fit the resource policy.','']
    a.out.write_text('\n'.join(lines));print(a.out)
if __name__=='__main__':main()
