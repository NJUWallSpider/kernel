#!/usr/bin/env python3
"""Validate the fixed old-task A/B evidence, then report every observation.

This tool never launches a kernel, preparer, build, or benchmark process.
Missing/failed evidence produces a validation failure, not a timing report.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / 'bench/v10_regression_measurement_plan.json'
DEFAULT_ISOLATION = ROOT / 'bench/results/v10-regression-isolation.json'
DEFAULT_RAW = [ROOT / f'bench/results/v10-regression-{v}-{m}/raw.json'
               for m in ('initial', 'extended') for v in ('old', 'new')]
TIMINGS = ('read_us', 'model_decode_us', 'proof_decode_us', 'execute_us', 'total_us')


class EvidenceError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def at_root(path):
    return (ROOT / path).resolve()


def relative(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def number(value, context, positive=False):
    require(type(value) in (int, float) and math.isfinite(value), f'{context}: nonnumeric/nonfinite value')
    require(value > 0 if positive else value >= 0, f'{context}: invalid sign')
    return value


def distribution(values):
    require(bool(values), 'empty distribution')
    return {'min': min(values), 'median': statistics.median(values), 'max': max(values)}


def formatted(values, scale=1):
    d = distribution([v / scale for v in values])
    return ' / '.join(f'{d[k]:.3f}' for k in ('min', 'median', 'max'))


def change(old, new, tiny=False):
    delta = new - old
    if tiny:
        return f'{delta * 1000:+.3f} µs; tiny baseline'
    if old == 0:
        return f'{delta:+.3f} ms; zero baseline'
    return f'{delta:+.3f} ms ({(new / old - 1) * 100:+.1f}%)'


def expected_names(kind, config):
    keys = [('identity', 'identity_sizes'), ('dense', 'dense_row_sizes'), ('rational', 'rational_sizes')] if kind == 'initial' else [
        ('history', 'history_sizes'), ('branch', 'branch_sizes'), ('chain', 'affine_chain_sizes'),
        ('local', 'local_change_sizes'), ('bigint', 'big_integer_bits')]
    names = [f'{family}-{n}' for family, key in keys for n in config[key]]
    if kind == 'extended':
        names += [f'real-{n}' for n in config['real_cases']]
    return names


def verified(result, expected_stats, expected_semantics, context):
    require(result.get('status') == 'VERIFIED', f'{context}: non-VERIFIED result')
    stats = result.get('statistics')
    require(isinstance(stats, dict) and stats, f'{context}: absent statistics')
    for key, value in stats.items():
        require(type(value) is int and value >= 0, f'{context}: malformed counter {key}')
    require(stats == expected_stats, f'{context}: exact mathematical statistics differ')
    # No schema normalization: new unused counters are omitted by the kernel.
    semantics = {k: v for k, v in result.items() if k not in (*TIMINGS, 'statistics')}
    require(semantics == expected_semantics, f'{context}: claims, limits or result semantics differ')
    for key in TIMINGS:
        number(result.get(key), f'{context}/{key}')


def rss_result(record, kind, context):
    if kind == 'initial':
        samples = [{'bytes': record.get('rss_bytes'), 'exit_code': record.get('rss_exit_code'),
                    'stdout': record.get('rss_stdout'), 'stderr': record.get('rss_raw')}]
    else:
        samples = record.get('rss_samples', [])
    output = []
    for i, sample in enumerate(samples):
        c = f'{context}/RSS{i}'
        require(sample.get('exit_code') == 0, f'{c}: nonzero exit')
        amount = number(sample.get('bytes'), f'{c}/bytes', positive=True)
        match = re.search(r'(\d+)\s+maximum resident set size', sample.get('stderr', ''))
        require(match is not None and int(match.group(1)) == amount, f'{c}: RSS bytes disagree with raw stderr')
        try:
            result = json.loads(sample['stdout'])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise EvidenceError(f'{c}: missing/invalid raw stdout') from error
        output.append({'bytes': amount, 'result': result})
    return output


def validate_command(record, kernel, action, context):
    command = record.get('command', [])
    require(len(command) >= 2 and at_root(command[0]) == kernel and command[1] == action,
            f'{context}: wrong executable or command')
    require(record.get('exit_code') == 0, f'{context}: nonzero exit')
    number(record.get('wall_ns'), f'{context}/wall_ns')
    return command


def artifacts(record, kind, context):
    names = ['model.mps', 'model.mcm', 'proof.rpa', 'proof.rpx', 'request.json'] if kind == 'initial' else [
        'source.mcm', 'target.mcm', 'proof.rpa', 'proof.rpx', 'request.json']
    require(set(record.get('artifacts', {})) == set(names), f'{context}: incomplete artifact set')
    if kind == 'initial':
        require(set(record.get('bytes', {})) == set(names), f'{context}: incomplete artifact byte counts')
        result = {n: {'bytes': record['bytes'][n], 'sha256': record['artifacts'][n]} for n in names}
    else:
        result = record['artifacts']
    for name, value in result.items():
        require(type(value.get('bytes')) is int and value['bytes'] > 0, f'{context}/{name}: invalid bytes')
        require(isinstance(value.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', value['sha256']),
                f'{context}/{name}: invalid SHA-256')
    return result


def validate_preparation(record, kind, kernel, context, receipt_archive):
    prep = record['preparation']
    if record['name'].startswith('real-'):
        require(kind == 'extended' and set(prep) == {'receipt', 'receipt_sha256'}, f'{context}: actual preparation mislabeled')
        original = at_root(prep['receipt'])
        archived = receipt_archive / f'{record["name"]}.json'
        selected = archived if archived.exists() else original
        require(selected.is_file() and sha(selected) == prep['receipt_sha256'], f'{context}: actual receipt missing/changed')
        receipt = load(selected)
        require(receipt.get('status') == 'VERIFIED', f'{context}: actual preparation receipt not VERIFIED')
        return {'kind': 'archived_actual_receipt_not_remeasured', 'receipt': relative(original),
                'receipt_sha256': prep['receipt_sha256']}
    generation = record.get('preparation_generation_ns') if kind == 'initial' else prep.get('generation_ns')
    number(generation, f'{context}/generation_ns')
    commands = prep if kind == 'initial' else prep.get('commands', [])
    actions = ['canonical', 'assemble'] if kind == 'initial' else ['canonical', 'canonical', 'assemble']
    require(len(commands) == len(actions), f'{context}: incomplete preparation stages')
    rows = []
    for i, (command, action) in enumerate(zip(commands, actions)):
        argv = validate_command(command, kernel, action, f'{context}/preparation{i}')
        result = command.get('result', {})
        require(result.get('status') == ('CANONICALIZED' if action == 'canonical' else 'ASSEMBLED'),
                f'{context}: bad preparation status')
        number(result.get('total_us'), f'{context}/preparation{i}/total_us')
        if action == 'canonical':
            number(result.get('parse_us'), f'{context}/preparation{i}/parse_us')
        rows.append({'action': action, 'input': relative(argv[2]), 'process_ns': command['wall_ns'],
                     'total_us': result['total_us'], 'parse_us': result.get('parse_us')})
    return {'kind': 'one_separate_generation_canonical_assembly_observation',
            'generation_ns': generation, 'commands': rows}


def verify_live_artifacts(record, kind, expected, context):
    command = record['samples'][0]['command']
    require(len(command) == 6, f'{context}: unexpected verification arguments')
    paths = {'proof.rpx': at_root(command[4]), 'request.json': at_root(command[5])}
    if kind == 'initial':
        require(command[2] == command[3], f'{context}: initial source/target are not the same model')
        paths['model.mcm'] = at_root(command[2])
        directory = paths['model.mcm'].parent
        paths.update({'model.mps': directory / 'model.mps', 'proof.rpa': directory / 'proof.rpa'})
    else:
        paths.update({'source.mcm': at_root(command[2]), 'target.mcm': at_root(command[3]),
                      'proof.rpa': at_root(command[4]).with_suffix('.rpa')})
    for name, path in paths.items():
        require(path.is_file() and path.stat().st_size == expected[name]['bytes'] and sha(path) == expected[name]['sha256'],
                f'{context}/{name}: current reproducibility artifact missing/changed')


def validate_pair(kind, old_path, new_path, plan, receipt_archive):
    old, new = load(old_path), load(new_path)
    config_path = ROOT / ('bench/workloads.json' if kind == 'initial' else 'bench/extended_workloads.json')
    config = load(config_path)
    require(old['config'] == new['config'] == config, f'{kind}: config differs from fixed matrix')
    names = expected_names(kind, config)
    require(len(names) == plan['workload_counts'][kind], f'{kind}: plan workload count')
    for label, raw in [('old', old), ('new', new)]:
        require([w['name'] for w in raw['workloads']] == names, f'{kind}/{label}: missing, reordered or substituted workload')
        require(not raw.get('prepare_only', False), f'{kind}/{label}: diagnostic-only run')
        identity = 'old' if label == 'old' else 'candidate'
        expected_binary = plan[f'{identity}_binary_sha256']
        require(raw.get('kernel_sha256') == raw.get('kernel_sha256_after') == expected_binary,
                f'{kind}/{label}: binary before/after/fixed identity mismatch')
        source = at_root(plan[f'{identity}_source_snapshot'])
        require(at_root(raw['source_root']) == source, f'{kind}/{label}: wrong source snapshot')
        source_hashes = {str(p.relative_to(source)): sha(p) for p in sorted((source / 'crates/core/src').rglob('*.rs'))}
        require(source_hashes and raw['sources'] == source_hashes, f'{kind}/{label}: source snapshot drift')
        require(raw['lock_sha256'] == sha(source / 'Cargo.lock'), f'{kind}/{label}: source lockfile drift')
    for key in ('hardware', 'platform', 'processor', 'rustc', 'lock_sha256'):
        require(old[key] == new[key], f'{kind}: host/toolchain/dependency control differs: {key}')
    require('warm' in old['cache_condition'].lower() and 'warm' in new['cache_condition'].lower(), f'{kind}: missing warm-cache policy')
    matrix = {'kind': kind, 'raw': {'old': {'path': relative(old_path), 'sha256': sha(old_path)},
                                 'new': {'path': relative(new_path), 'sha256': sha(new_path)}},
              'hardware': old['hardware'], 'platform': old['platform'], 'rustc': old['rustc'],
              'cache': {'old': old['cache_condition'], 'new': new['cache_condition']}, 'workloads': []}
    for before, after in zip(old['workloads'], new['workloads']):
        name = before['name']; context = f'{kind}/{name}'
        art = artifacts(before, kind, context + '/old')
        require(art == artifacts(after, kind, context + '/new'), f'{context}: paired physical artifact bytes/hashes differ')
        expected_stats = before['samples'][0]['result']['statistics']
        expected_semantics = {k: v for k, v in before['samples'][0]['result'].items()
                              if k not in (*TIMINGS, 'statistics')}
        entry = {'name': name, 'artifacts': art, 'statistics': expected_stats, 'result_semantics': expected_semantics}
        for version, record in [('old', before), ('new', after)]:
            ctx = f'{context}/{version}'; kernel = at_root(plan['old_binary' if version == 'old' else 'candidate_binary'])
            samples = record['samples']
            require(len(samples) == plan['fresh_verification_repetitions'] == config['repetitions'], f'{ctx}: timing count')
            first_command = samples[0]['command']
            for i, sample in enumerate(samples):
                validate_command(sample, kernel, 'verify', f'{ctx}/sample{i}')
                require(sample['command'] == first_command, f'{ctx}: changing sample inputs')
                verified(sample['result'], expected_stats, expected_semantics, f'{ctx}/sample{i}')
            rss = rss_result(record, kind, ctx)
            require(len(rss) == plan['RSS_repetitions'][kind], f'{ctx}: RSS count')
            for i, sample in enumerate(rss):
                verified(sample['result'], expected_stats, expected_semantics, f'{ctx}/RSS{i}')
            prep = validate_preparation(record, kind, kernel, ctx, receipt_archive)
            entry[version] = {'process_ns': [s['wall_ns'] for s in samples],
                              'timings_us': {k: [s['result'][k] for s in samples] for k in TIMINGS},
                              'rss_bytes': [s['bytes'] for s in rss], 'preparation': prep}
        # Inputs are shared paths and may have been regenerated by the candidate.
        # Their hashes are already identical in both raw records; now verify the
        # surviving files, rather than silently trusting stale physical sizes.
        verify_live_artifacts(after, kind, art, context)
        if name.startswith('real-'):
            require(entry['old']['preparation'] == entry['new']['preparation'], f'{context}: actual preparation receipt drift')
        matrix['workloads'].append(entry)
    return matrix


def render(comparison):
    plan = comparison['plan']
    lines = ['# V10 regression on unchanged old workloads', '',
             'These measurements compare the same complete mathematical tasks and identical model, RPA, RPX and caller-request bytes. They are a performance regression check, not a correctness proof or a comparison against unsupported old capabilities.', '',
             f'Old executable: `{plan["old_binary"]}`, SHA-256 `{plan["old_binary_sha256"]}`. Candidate: `{plan["candidate_binary"]}`, SHA-256 `{plan["candidate_binary_sha256"]}`.', '',
             f'Fixed plan: `{comparison["plan_path"]}` (SHA-256 `{comparison["plan_sha256"]}`). Both binary hashes agree before and after each matrix. The report verifies the fixed configs/drivers, source snapshots and lockfiles, every timing/RSS exit and VERIFIED status, exact complete mathematical statistics, claims/limits, and all paired artifact sizes and hashes.', '',
             f'Orchestration receipt: `{comparison["isolation"]["path"]}` (SHA-256 `{comparison["isolation"]["sha256"]}`), with all four fixed commands completed successfully. Recorded isolation declaration: {comparison["isolation"]["declaration"]}', '',
             'Nine fresh-process timing samples per workload; one separate RSS observation in the initial matrix and three in the extended matrix. Filesystem caches are warm after preparation, with no cache flushing. The fixed order is old initial, new initial, old extended, new extended; sampling is sequential, not randomized. Coordinator isolation does not control unrelated host or OS activity. Every observation and outlier is retained.', '',
             'Times below are milliseconds, shown as min / median / max. Process includes startup and shutdown; execute is the internal verification stage. Changes are candidate minus old. Relative execute changes are suppressed below a 0.100 ms old median because tiny timings are easily dominated by timer resolution and scheduling. No confidence interval or universal speedup is inferred. RSS is median observed peak resident memory, in MiB; a single initial RSS observation is not a distribution.', '']
    regressions = {'execute': [], 'process': []}
    verified_count = 0
    for matrix in comparison['matrices']:
        kind = matrix['kind']; lines += [f'## {kind.capitalize()} matrix', '',
            f'Host: `{matrix["hardware"]}`; platform `{matrix["platform"]}`. Toolchain: `{matrix["rustc"].splitlines()[0]}`.', '',
            f'Raw old: `{matrix["raw"]["old"]["path"]}` (SHA-256 `{matrix["raw"]["old"]["sha256"]}`). Raw candidate: `{matrix["raw"]["new"]["path"]}` (SHA-256 `{matrix["raw"]["new"]["sha256"]}`).', '',
            '| Workload | Execute old | Execute new | Execute median change | Process old | Process new | Process median change | RSS old → new MiB |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
        for row in matrix['workloads']:
            a, b = row['old'], row['new']; ea, eb = [statistics.median(v['timings_us']['execute_us']) / 1000 for v in (a, b)]; pa, pb = [statistics.median(v['process_ns']) / 1e6 for v in (a, b)]
            if eb > ea: regressions['execute'].append({'matrix': kind, 'name': row['name'], 'old_ms': ea, 'new_ms': eb})
            if pb > pa: regressions['process'].append({'matrix': kind, 'name': row['name'], 'old_ms': pa, 'new_ms': pb})
            cells = [row['name'], formatted(a['timings_us']['execute_us'], 1000), formatted(b['timings_us']['execute_us'], 1000), change(ea, eb, ea < .1), formatted(a['process_ns'], 1e6), formatted(b['process_ns'], 1e6), change(pa, pb), f'{statistics.median(a["rss_bytes"])/2**20:.3f} → {statistics.median(b["rss_bytes"])/2**20:.3f}']
            lines.append('| ' + ' | '.join(cells) + ' |')
            verified_count += sum(len(v['process_ns']) + len(v['rss_bytes']) for v in (a, b))
        lines += ['', 'Physical artifact bytes and logical work are identical across the pair. Initial source and target name the same MCM file; its size is shown on both sides, not claimed as two distinct files.', '',
                  '| Workload | Source / target MCM bytes | RPA bytes | RPX bytes | Request bytes | Logical work | Obligations | Peak live facts |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for row in matrix['workloads']:
            art = row['artifacts']; src = art['model.mcm' if kind == 'initial' else 'source.mcm']['bytes']; dst = art['model.mcm' if kind == 'initial' else 'target.mcm']['bytes']; s = row['statistics']
            cells = [row['name'], f'{src} / {dst}', str(art['proof.rpa']['bytes']), str(art['proof.rpx']['bytes']), str(art['request.json']['bytes']), str(s['work']), str(s['obligations']), str(s['peak_live_facts'])]
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines += ['', '### Read/decode and complete internal time', '',
                  'Each cell is old min / median / max → candidate min / median / max, in milliseconds.', '',
                  '| Workload | Read | Model decode | Proof decode | Kernel total |', '|---|---:|---:|---:|---:|']
        for row in matrix['workloads']:
            cells = [row['name']] + [formatted(row['old']['timings_us'][k], 1000) + ' → ' + formatted(row['new']['timings_us'][k], 1000) for k in ('read_us', 'model_decode_us', 'proof_decode_us', 'total_us')]
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines += ['', '### Preparation recorded separately', '',
                  'Synthetic generation is one wall-time observation inside each benchmark driver, followed by independent canonical/assembler processes. These stages are outside verification timing and are not repeated preparation distributions. Canonical columns sum the one initial or two extended model conversions; assembly is separate. For actual cases no author, canonicalization or assembly cost was remeasured: receipt links mean unmeasured here, never zero cost.', '',
                  '| Workload / version | Generate ms | Canonical process / internal / parse ms | Assemble process / internal ms | Actual preparation receipt |',
                  '|---|---:|---:|---:|---|']
        for row in matrix['workloads']:
            for version in ('old', 'new'):
                prep = row[version]['preparation']
                if prep['kind'] == 'archived_actual_receipt_not_remeasured':
                    cells = [f'{row["name"]} / {version}', 'unmeasured', 'unmeasured', 'unmeasured', f'`{prep["archived_receipt"]}`; SHA-256 `{prep["receipt_sha256"]}`']
                else:
                    canon = [x for x in prep['commands'] if x['action'] == 'canonical']; assembly = next(x for x in prep['commands'] if x['action'] == 'assemble')
                    cells = [f'{row["name"]} / {version}', f'{prep["generation_ns"]/1e6:.3f}', f'{sum(x["process_ns"] for x in canon)/1e6:.3f} / {sum(x["total_us"] for x in canon)/1000:.3f} / {sum(x["parse_us"] for x in canon)/1000:.3f}', f'{assembly["process_ns"]/1e6:.3f} / {assembly["total_us"]/1000:.3f}', 'not applicable']
                lines.append('| ' + ' | '.join(cells) + ' |')
    lines += ['', '## Interpretation and limits', '',
              f'All {verified_count} measured verification/RSS processes passed on all 31 fixed paired workloads. No failed sample was discarded, no statistic key was normalized away, and no unsupported new task received an old/new speed ratio.', '',
              f'Candidate median execution is higher in {len(regressions["execute"])} workloads; candidate median process time is higher in {len(regressions["process"])}. Every such regression remains in the tables. These counts describe observations, not statistical significance.', '',
              'Execution regressions: ' + (', '.join(f'`{r["name"]}` ({r["new_ms"]-r["old_ms"]:+.3f} ms)' for r in regressions['execute']) or 'none observed') + '.', '',
              'Process regressions: ' + (', '.join(f'`{r["name"]}` ({r["new_ms"]-r["old_ms"]:+.3f} ms)' for r in regressions['process']) or 'none observed') + '.', '',
              'This is complete old-workload performance evidence for the fixed candidate, including startup, reads, decode, verification, memory and separately recorded preparation. It does not establish mathematical correctness, certify the entire corpus, freeze the working protocol, or measure the cost of newly supported contracts. Source changes and benchmark preparation are not hidden by reporting only inner verification time.', '',
              'Recreate this report without running any workload: `python3 tools/report_v10_regression.py`. A missing, failed or inconsistent input is a report-validation error; raw evidence is never rewritten.', '']
    comparison['regressions'] = regressions
    comparison['verified_processes'] = verified_count
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--isolation', type=Path, default=DEFAULT_ISOLATION)
    parser.add_argument('--raw', type=Path, nargs=4, default=DEFAULT_RAW,
                        metavar=('OLD_INITIAL', 'NEW_INITIAL', 'OLD_EXTENDED', 'NEW_EXTENDED'))
    parser.add_argument('--out', type=Path, default=ROOT / 'bench/V10_REGRESSION_REPORT.md')
    parser.add_argument('--json-out', type=Path, default=ROOT / 'bench/results/v10-regression-comparison.json')
    args = parser.parse_args()
    evidence = {'status': 'VALIDATION_FAILED', 'script_sha256': sha(Path(__file__)), 'raw_paths': [relative(p) for p in args.raw]}
    try:
        plan = load(args.plan); evidence.update({'plan_path': relative(args.plan), 'plan_sha256': sha(args.plan), 'plan': plan})
        require(plan['status'] == 'FIXED_BEFORE_MEASUREMENT', 'measurement plan is not fixed')
        require(plan['fresh_verification_repetitions'] == 9 and plan['RSS_repetitions'] == {'initial': 1, 'extended': 3}, 'sample policy changed')
        require(plan['workload_counts'] == {'initial': 8, 'extended': 23}, 'fixed workload counts changed')
        for path, expected in plan['matrices'].items():
            require(sha(ROOT / path) == expected, f'fixed config/driver changed: {path}')
        for identity in ('old', 'candidate'):
            require(sha(at_root(plan[f'{identity}_binary'])) == plan[f'{identity}_binary_sha256'], f'{identity}: fixed executable changed')
        receipt_path = at_root(plan['candidate_build_receipt'])
        require(sha(receipt_path) == plan['candidate_build_receipt_sha256'], 'candidate build receipt changed')
        build = load(receipt_path)
        require(build['status'] == 'PASS' and build['binary']['sha256'] == plan['candidate_binary_sha256'] and at_root(build['source_root']) == at_root(plan['candidate_source_snapshot']), 'candidate build receipt does not bind sampled source/binary')
        isolation = load(args.isolation)
        require(isolation['status'] == 'FOUR_ROUNDS_COMPLETE' and isolation['plan_sha256'] == evidence['plan_sha256'], 'isolation receipt does not bind the completed fixed plan')
        require(isinstance(isolation.get('isolation_note'), str) and isolation['isolation_note'].strip(), 'missing isolation declaration')
        require(len(isolation['commands']) == 4, 'incomplete orchestration command list')
        for i, (command, raw_path) in enumerate(zip(isolation['commands'], args.raw)):
            identity = 'old' if i % 2 == 0 else 'candidate'
            driver = 'tools/benchmark.py' if i < 2 else 'tools/benchmark_extended.py'
            wanted = ['python3', str(ROOT / driver), '--kernel', plan[f'{identity}_binary'],
                      '--source-root', plan[f'{identity}_source_snapshot'], '--label', raw_path.parent.name]
            require(command['command'] == wanted and command['exit_code'] == 0, f'orchestration command/order mismatch at {i}')
            require(sha(at_root(command['log'])) == command['log_sha256'], f'orchestration log changed at {i}')
        evidence['isolation'] = {'path': relative(args.isolation), 'sha256': sha(args.isolation),
                                 'declaration': isolation['isolation_note'],
                                 'started_utc': isolation['started_utc'], 'finished_utc': isolation['finished_utc']}
        receipt_archive = args.json_out.parent / 'v10-regression-receipts'
        matrices = [validate_pair('initial', *args.raw[:2], plan, receipt_archive), validate_pair('extended', *args.raw[2:], plan, receipt_archive)]
        # Both matrices must describe the same host/toolchain and source identities.
        for key in ('hardware', 'platform', 'rustc'):
            require(matrices[0][key] == matrices[1][key], f'matrix host/toolchain differs: {key}')
        evidence['matrices'] = matrices
        for matrix in matrices:
            for row in matrix['workloads']:
                for version in ('old', 'new'):
                    prep = row[version]['preparation']
                    if prep['kind'] == 'archived_actual_receipt_not_remeasured':
                        destination = args.json_out.parent / 'v10-regression-receipts' / f'{row["name"]}.json'
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if destination.exists():
                            require(sha(destination) == prep['receipt_sha256'], f'archived actual receipt collision: {destination}')
                        else:
                            shutil.copyfile(at_root(prep['receipt']), destination)
                        prep['archived_receipt'] = relative(destination)
        evidence['status'] = 'PASS'
        report = render(evidence)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        evidence['report'] = {'path': relative(args.out), 'sha256': sha(args.out)}
    except (EvidenceError, OSError, ValueError, TypeError, KeyError, IndexError) as error:
        evidence['status'] = 'VALIDATION_FAILED'; evidence['error'] = str(error)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps({'status': evidence['status'], 'error': str(error), 'no_timing_report_written': True}), file=sys.stderr)
        return 2
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'paired_workloads': 31, 'verified_processes': evidence['verified_processes'], 'report': relative(args.out)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
