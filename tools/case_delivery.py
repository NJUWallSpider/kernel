"""Read and bind single or bundled actual-case receipts (bookkeeping, not TCB).

A bundle is a conjunction of independently complete requests against identical
full model files. It introduces no cross-file inference or reference scope.
"""
import hashlib
import json
from pathlib import Path

if not __debug__:
    raise RuntimeError('Delivery validation requires assertions; Python -O/-OO is unsupported.')

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def absolute(path):
    p = Path(path)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def identity(path):
    p = absolute(path)
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}


def check_identity(path, expected):
    observed = identity(path)
    assert observed['sha256'] == expected['sha256'], (path, 'hash mismatch')
    if 'bytes' in expected: assert observed['bytes'] == expected['bytes'], (path, 'size mismatch')
    return observed


def normalize_request(request):
    return {'claims': request} if isinstance(request, list) else request


def bind_verify(run, source, target, rpx, request):
    assert run['exit_code'] == 0 and run['command'][1] == 'verify'
    # All accepted author receipts here use the explicitly echoed default policy.
    # Supporting configurable policy commands must preserve the four bound paths.
    operands = []; args = iter(run['command'][2:])
    for arg in args:
        if arg in ('--work', '--live-facts'): next(args)
        else: operands.append(absolute(arg))
    assert operands == [absolute(p) for p in (source, target, rpx, request)]
    result = json.loads(run['stdout']); assert result['status'] == 'VERIFIED'
    q = json.loads(absolute(request).read_text()); normalized = normalize_request(q)
    for name in ('claims', 'points', 'bijections', 'improvements'):
        assert result.get(name, 0) == len(normalized.get(name, [])), (request, name)
    return q, result


def load_delivery(case, receipt=None):
    case = absolute(case); d = receipt or json.loads((case/'preparation.json').read_text())
    assert d['status'] == 'VERIFIED'
    source = case/'source.mcm'; target = case/'target.mcm'
    artifacts = {name: check_identity(case/name, d['artifacts'][name]) for name in ('source.mcm', 'target.mcm')}
    if 'bundle' not in d:
        for name in ('proof.rpx', 'request.json'): artifacts[name] = check_identity(case/name, d['artifacts'][name])
        rpa = d['artifacts'].get('proof.rpa', {'sha256': d.get('rpa_sha256'), 'bytes': d.get('rpa_bytes')})
        if rpa.get('bytes') is None: rpa = {'sha256': rpa['sha256']}
        artifacts['proof.rpa'] = check_identity(case/'proof.rpa', rpa)
        q, result = bind_verify(d['kernel_runs'][-1], source, target, case/'proof.rpx', case/'request.json')
        piece = {'id': 'complete', 'rpa': case/'proof.rpa', 'rpx': case/'proof.rpx', 'request': case/'request.json', 'claims': q, 'result': result}
        return {'kind': 'single', 'source': source, 'target': target, 'pieces': [piece], 'request': q, 'artifacts': artifacts, 'verification': result}
    manifest_path = absolute(d['bundle']); manifest = json.loads(manifest_path.read_text())
    assert manifest['format'] == 'actual-model-direction-bundle-v1' and manifest['case_id'] == d['case_id']
    assert d['completion_kind'] == 'same-model-pair-directional-bundle'
    artifacts['bundle.json'] = check_identity(manifest_path, d['artifacts']['bundle.json'])
    for role, p in [('source', source), ('target', target)]:
        assert absolute(manifest[role]['path']) == p
        check_identity(p, manifest[role])
    pieces = []; combined = []; stats = {}
    assert manifest['directions'] and manifest['directions'] == d['directional_replays']
    for index, item in enumerate(manifest['directions']):
        assert item['direction'] == index
        files = {key: absolute(item[key]) for key in ('rpa', 'rpx', 'request')}
        for key, filename in [('rpa', 'proof.rpa'), ('rpx', 'proof.rpx'), ('request', 'request.json')]:
            artifacts[f'direction-{index}/{filename}'] = check_identity(files[key], item['artifacts'][filename])
        q, result = bind_verify(item['verify'], source, target, files['rpx'], files['request'])
        nq = normalize_request(q)
        # Cross-file contract indices have no interpretation. Each piece here
        # carries one standalone direction, with no lost supplementary claims.
        assert len(nq['claims']) == 1 and not any(nq.get(k) for k in ('points', 'bijections', 'improvements'))
        assert nq['claims'][0].get('inverse') is None
        combined.extend(nq['claims'])
        for key, value in result['statistics'].items():
            stats[key] = max(stats.get(key, 0), value) if key == 'peak_live_facts' else stats.get(key, 0) + value
        pieces.append({'id': str(index), **files, 'claims': q, 'result': result})
    # The separately preserved complete requested conjunction prevents dropping
    # a middle direction while still reporting the original complete request.
    caller_path = case/'combined-request.json'
    artifacts['combined-request.json'] = check_identity(caller_path, d['artifacts']['combined-request.json'])
    expected = json.loads(caller_path.read_text())
    assert expected == combined and len(combined) == d['complete_claim_count']
    assert stats == d['statistics']
    verification = {'status': 'VERIFIED', 'kind': 'conjunction-of-independent-complete-requests', 'not_a_single_kernel_invocation': True, 'claims': len(combined), 'direction_results': [p['result'] for p in pieces], 'statistics_sum_and_peak_max': stats}
    return {'kind': 'bundle', 'source': source, 'target': target, 'pieces': pieces, 'request': combined, 'artifacts': artifacts, 'verification': verification}


def load_optimization(case):
    """Bind one migrated two-block proof to its unchanged complete models."""
    case = absolute(case)
    record = json.loads((case/'optimization.json').read_text())
    artifacts = {}
    for role in ('source', 'target', 'proof'):
        path = absolute(record[role])
        artifacts[role] = check_identity(path, {'sha256': record[role+'_sha256']})
    return {role: absolute(record[role]) for role in ('source','target','proof')} | {'artifacts': artifacts}
