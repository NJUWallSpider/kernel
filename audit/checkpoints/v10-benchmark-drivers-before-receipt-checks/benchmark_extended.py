#!/usr/bin/env python3
"""Fixed additional families, complete RPX verification and preserved raw records."""
import argparse, hashlib, json, platform, re, statistics, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--kernel', default='target/release/rpx')
parser.add_argument('--source-root', default=str(ROOT))
parser.add_argument('--label', required=True)
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
kernel = (ROOT / args.kernel).resolve()
source_root = Path(args.source_root).resolve()
config = json.loads((ROOT / 'bench/extended_workloads.json').read_text())
out = ROOT / 'bench/results' / args.label
out.mkdir(parents=True, exist_ok=True)
if (out / 'raw.json').exists():
    raise SystemExit('Refusing to overwrite a preserved result; use a fresh label.')

def invoke(command):
    start = time.perf_counter_ns()
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True)
    wall = time.perf_counter_ns() - start
    try:
        reply = json.loads(result.stdout)
    except json.JSONDecodeError:
        reply = {'status': 'IO_ERROR', 'stdout': result.stdout, 'stderr': result.stderr}
    return {'command': list(map(str, command)), 'wall_ns': wall,
            'exit_code': result.returncode, 'result': reply}

def expr(terms=(), constant='0'):
    return {'constant': str(constant), 'terms': [[i, str(c)] for i, c in terms]}

def lin(identifier, terms):
    return {'Lin': {'id': identifier, 'kind': 'Le', 'constant': '0', 'terms': terms}}

def mps(n, rows, binary=True, upper=True):
    # rows: (name, [(variable, integer coefficient)], sense, integer RHS)
    lines = ['NAME bench', 'ROWS', ' N OBJ'] + [f' {sense} {name}' for name, _, sense, _ in rows]
    lines.append('COLUMNS')
    columns = [[] for _ in range(n)]
    for name, terms, _, _ in rows:
        for i, c in terms:
            columns[i].append((name, c))
    for i, column in enumerate(columns):
        lines.append(f' x{i} OBJ 0')
        lines.extend(f' x{i} {name} {c}' for name, c in column)
    lines.append('RHS')
    lines.extend(f' rhs {name} {rhs}' for name, _, _, rhs in rows)
    lines.append('BOUNDS')
    for i in range(n):
        if binary:
            lines.append(f' BV b x{i}')
        elif upper:
            lines.append(f' UP b x{i} 1')
        else:
            lines.append(f' LO b x{i} 0')
    return '\n'.join(lines + ['ENDATA', ''])

def prepare(kind, n):
    start = time.perf_counter_ns()
    d = ROOT / 'bench/extended-generated' / f'{kind}-{n}'
    d.mkdir(parents=True, exist_ok=True)
    steps, checks, rows, target_rows = [], [], [], []
    count = n if kind in ('chain', 'local') else config['big_integer_variables'] if kind == 'bigint' else 1
    binary = kind != 'chain'
    mapping = [expr([(i, 1)]) for i in range(count)]
    if kind in ('history', 'branch'):
        for i in range(n):
            if kind == 'history':
                steps.append(lin(i, [[{'VarUpper': 0} if i == 0 else {'Local': i - 1}, '1']]))
            else:
                steps.append({'Cases': {'id': i, 'kind': 'Le', 'expression': expr([(0, 1)], -1),
                    'split': expr([(0, 1)]), 'integer': {'VarInt': 0},
                    'left': {'steps': [], 'end': {'Witness': {'VarUpper': 0}}},
                    'right': {'steps': [], 'end': {'Witness': {'VarUpper': 0}}}}})
            if i:
                steps.append({'Drop': {'ids': [i - 1]}})
        checks = [{'VarLower': 0}, {'Local': n - 1}, {'VarInt': 0}]
    elif kind == 'chain':
        rows = [(f'p{i}', [(j, 1) for j in range(i + 1)], 'L', 1) for i in range(n)]
        target_rows = [(f'd{i}', [(i - 1, -1), (i, 1)], 'G', 0) for i in range(1, n)]
        mapping = [expr([(j, 1) for j in range(i + 1)]) for i in range(n)]
        for i in range(n):
            steps.append(lin(i, [[{'VarLower': j}, '1'] for j in range(i + 1)]))
            checks.extend([{'Local': i}, {'RowUpper': i}])
        checks.extend({'VarLower': i} for i in range(1, n))
    else:
        if kind == 'local':
            rows = [(f'r{i}', [(i, 1)], 'L', 1) for i in range(n)]
            target_rows = [(f'r{i}', [(i, 2)], 'L', 2) for i in range(n)]
            steps = [lin(i, [[{'RowUpper': i}, '2']]) for i in range(n)]
        elif kind == 'bigint':
            coefficient = 2 ** n + 1
            rows = [('dense', [(i, coefficient) for i in range(count)], 'L', count * coefficient)]
            target_rows = rows
        for i in range(count):
            checks.extend([{'VarLower': i}, {'VarUpper': i}, {'VarInt': i}])
        checks.extend({'Local': i} if kind == 'local' else {'RowUpper': i} for i in range(len(rows)))
    claim = {'reverse': False, 'input_integers': binary, 'output_integers': binary,
             'objective': 'Equal', 'projection': [], 'inverse': None}
    checks.append('Exact')
    cert = {'claims': [claim], 'blocks': [{'steps': steps, 'end': {'Return': {'map': mapping, 'checks': checks}}}]}
    (d / 'source.mps').write_text(mps(count, rows, binary, upper=kind != 'chain'))
    (d / 'target.mps').write_text(mps(count, target_rows, binary, upper=True))
    (d / 'proof.rpa').write_text(f'RPA {2 if kind == "branch" else 1}\n' + json.dumps(cert, separators=(',', ':')) + '\n')
    (d / 'request.json').write_text(json.dumps([claim]) + '\n')
    generated_ns = time.perf_counter_ns() - start
    preparation = [invoke([kernel, 'canonical', d / f'{side}.mps', d / f'{side}.mcm']) for side in ('source', 'target')]
    preparation.append(invoke([kernel, 'assemble', d / 'proof.rpa', d / 'proof.rpx']))
    if any(r['exit_code'] for r in preparation):
        (out / 'failed-preparation.json').write_text(json.dumps(preparation, indent=2))
        raise SystemExit(f'Preparation failed for {d.name}; raw results saved.')
    return d, {'generation_ns': generated_ns, 'commands': preparation}, {
        'directional_claims': 1, 'map_terms': sum(len(e['terms']) for e in mapping),
        'linear_references': sum(len(s['Lin']['terms']) for s in steps if 'Lin' in s),
        'step_records': len(steps), 'branches': n if kind == 'branch' else 0}

meta = {'config': config, 'label': args.label, 'source_root': str(source_root),
        'kernel_sha256': hashlib.sha256(kernel.read_bytes()).hexdigest(),
        'hardware': {k: subprocess.check_output(['sysctl','-n',k],text=True).strip() for k in ['machdep.cpu.brand_string','hw.memsize','hw.ncpu']} if platform.system()=='Darwin' else {},'platform': platform.platform(), 'processor': platform.processor(),
        'rustc': subprocess.check_output(['rustc', '-Vv'], text=True),
        'sources': {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((source_root / 'crates/core/src').rglob('*.rs'))},
        'lock_sha256': hashlib.sha256((source_root / 'Cargo.lock').read_bytes()).hexdigest(),
        'cache_condition': 'warm filesystem after preparation; fresh process per sample, no flushing',
        'prepare_only': args.prepare_only, 'workloads': []}
workloads = [(kind, n) for kind, key in [('history', 'history_sizes'), ('branch', 'branch_sizes'),
              ('chain', 'affine_chain_sizes'), ('local', 'local_change_sizes'), ('bigint', 'big_integer_bits')]
             for n in config[key]] + [('real', n) for n in config['real_cases']]
for kind, n in workloads:
    if kind == 'real':
        d = ROOT / 'cases' / f'test{n}'
        preparation = {'receipt': str(d / 'preparation.json'),
                       'receipt_sha256': hashlib.sha256((d / 'preparation.json').read_bytes()).hexdigest()}
        logical = {'note': 'Actual unchanged full caller contract; kernel counts recorded per sample.'}
    else:
        d, preparation, logical = prepare(kind, n)
    record = {'name': f'{kind}-{n}', 'preparation': preparation, 'logical_representation': logical,
              'artifacts': {f: {'bytes': (d / f).stat().st_size, 'sha256': hashlib.sha256((d / f).read_bytes()).hexdigest()}
                            for f in ['source.mcm', 'target.mcm', 'proof.rpa', 'proof.rpx', 'request.json']},
              'samples': [], 'rss_samples': []}
    command = [kernel, 'verify', d / 'source.mcm', d / 'target.mcm', d / 'proof.rpx', d / 'request.json']
    for _ in range(1 if args.prepare_only else config['repetitions']):
        record['samples'].append(invoke(command))
    if not args.prepare_only and platform.system() == 'Darwin':
        for _ in range(3):
            result = subprocess.run(['/usr/bin/time', '-l', *map(str, command)], capture_output=True, text=True)
            match = re.search(r'(\d+)\s+maximum resident set size', result.stderr)
            record['rss_samples'].append({'bytes': int(match.group(1)) if match else None,
                                          'exit_code': result.returncode, 'stderr': result.stderr, 'stdout': result.stdout})
    record['summary'] = {}
    for name, values in [('process_ms', [s['wall_ns'] / 1e6 for s in record['samples']]),
                         ('execute_ms', [s['result']['execute_us'] / 1000 for s in record['samples'] if s['result']['status'] == 'VERIFIED'])]:
        if values:
            record['summary'][name] = {'min': min(values), 'median': statistics.median(values), 'max': max(values)}
    record['summary']['verified'] = sum(s['result']['status'] == 'VERIFIED' for s in record['samples'])
    meta['workloads'].append(record)
    (out / 'raw.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(record['name'], json.dumps(record['summary']), flush=True)
    if record['summary']['verified'] != len(record['samples']):
        raise SystemExit('Verification failure preserved; refusing to summarize failed workload as a timing success.')
print(out / 'raw.json')
