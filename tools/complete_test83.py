#!/usr/bin/env python3
"""Bind test83's all-optimizer exclusion to a complete improving source tuple."""
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
import argparse, copy, json, shutil, subprocess, time
from prepare_affine import parse_mps
from prepare_test40 import expression, mul, expr_json, row_fact, sha
from prepare_test21 import combine, substitute
from prepare_test70 import SparseBuilder


def improvement(a, hints):
    assert len(a['vars']) == 65832 and len(a['rows']) == 100
    assert all(v['integer'] and v['lower'] == 0 and v['upper'] == 1 for v in a['vars'])
    assert all(r['sense'] == 'E' and r['rhs'] == 1 and set(r['terms'].values()) == {F(1)} for r in a['rows'])
    supports = [set() for _ in a['vars']]
    for ri, row in enumerate(a['rows']):
        for i in row['terms']: supports[i].add(ri)
    replacements = {a['var_index'][d['removed_variable']]: [a['var_index'][v] for v in d['replacement_variables']] for d in hints['dominance_deletions']}
    assert len(replacements) == 61
    saving = {}
    mapping = [expression() if i in replacements else expression(0, {i: 1}) for i in range(len(a['vars']))]
    for i, js in replacements.items():
        assert len(js) == 2 and not supports[js[0]] & supports[js[1]]
        assert supports[js[0]] | supports[js[1]] == supports[i]
        assert all(j not in replacements for j in js)
        saving[i] = a['objective'][1][i] - sum(a['objective'][1][j] for j in js)
        assert saving[i] > 0
        for j in js: mapping[j][1][i] = F(1)
    minimum = min(saving.values())
    positive = expression(0, {i: 1 for i in replacements})
    p = SparseBuilder(a); lower = {}; upper = {}; chosen = defaultdict(list); trace = {}
    for j, e in enumerate(mapping):
        if not e[1]: lower[j] = upper[j] = 'Exact'
        elif len(e[1]) == 1: lower[j] = {'VarLower': j}; upper[j] = {'VarUpper': j}
        else:
            lower[j] = p.lin('Le', [[{'VarLower': i}, 1] for i in e[1]], mul(e, -1))
            common = set.intersection(*(supports[i] for i in e[1])); assert common
            chosen[min(common, key=lambda ri: (len(a['rows'][ri]['terms']), ri))].append(j)
    def tree(groups):
        if len(groups) == 1: return {'leaf': groups[0], 'lower': lower[groups[0]]}
        mid = len(groups) // 2; l, r = tree(groups[:mid]), tree(groups[mid:])
        return {'left': l, 'right': r, 'lower': p.lin('Le', [[l['lower'], 1], [r['lower'], 1]])}
    def spread(node, up):
        if 'leaf' in node: upper[node['leaf']] = up; return
        l, r = node['left'], node['right']
        spread(l, p.lin('Le', [[up, 1], [r['lower'], 1]]))
        spread(r, p.lin('Le', [[up, 1], [l['lower'], 1]]))
    for ri, groups in sorted(chosen.items()):
        selected = set()
        for j in groups: assert selected.isdisjoint(mapping[j][1]); selected.update(mapping[j][1])
        node = tree(groups)
        root = p.lin('Le', [[{'RowEq': ri}, 1]] + [[{'VarLower': i}, 1] for i in a['rows'][ri]['terms'] if i not in selected], expression(-1, {i: 1 for i in selected}))
        trace.setdefault('bound_root', root['Local']); spread(node, root)
    checks = []
    for i in range(len(mapping)): checks.extend([lower[i], upper[i], 'Exact'])
    for ri, row in enumerate(a['rows']):
        assert substitute(row_fact(row, 'RowEq'), mapping) == row_fact(row, 'RowEq')
        checks.append({'RowEq': ri})
    difference = combine([(substitute(a['objective'], mapping), 1), (a['objective'], -1)])
    assert difference == expression(0, {i: -c for i, c in saving.items()})
    wanted = combine([(difference, 1), (positive, minimum)])
    terms = [[{'VarLower': i}, c - minimum] for i, c in saving.items() if c != minimum]
    objective = p.lin('Le', terms, wanted); checks.append(objective); trace['objective'] = objective['Local']
    trace['changed_coordinate'] = next(i for i, e in enumerate(mapping) if len(e[1]) > 1)
    claim = {'target': False, 'integers': True, 'positive': expr_json(positive)}
    block = {'steps': p.steps, 'end': {'ImproveReturn': {'map': [expr_json(e) for e in mapping], 'checks': checks, 'margin': {'Predicate': str(minimum)}}}}
    info = {'dominated_coordinates': sorted(replacements), 'minimum_strict_saving': str(minimum), 'saving_by_coordinate': {str(i): str(c) for i, c in saving.items()}, 'full_source_tuple_coordinates': len(mapping), 'bound_tree_rows': len(chosen), 'steps': len(p.steps), 'obligations': len(checks), 'objective_difference': expr_json(difference)}
    return {'claim': claim, 'block': block}, info, trace


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kernel', type=Path, default=Path('target/next-contracts-initial/release/rpx'))
    ap.add_argument('--out', type=Path, default=Path('cases/test83'))
    args = ap.parse_args(); kernel = args.kernel.resolve(); out = args.out.resolve(); started = time.perf_counter()
    archive = out/'attempts/submitted-v5-2026-10-11'
    if not archive.exists():
        archive.mkdir(parents=True)
        for name in ['source.mcm', 'target.mcm', 'proof.rpa', 'proof.rpx', 'request.json', 'preparation.json']:
            shutil.copy2(out/name, archive/name)
        shutil.copy2(Path(__file__).with_name('prepare_test83.py'), archive/'prepare_test83.py')
    previous = json.loads((archive/'preparation.json').read_text())
    source, target, hints = (Path(previous[k]['path']) for k in ('source', 'target', 'audit'))
    for k, path in [('source', source), ('target', target), ('audit', hints)]: assert sha(path) == previous[k]['sha256']
    inventory = next(c for c in json.loads(Path('audit/corpus_inventory.json').read_text())['cases'] if c['case_id'] == 'test83')
    assert sha(source) == inventory['source_models'][0]['sha256'] and sha(target) == inventory['final_target_models'][0]['sha256']
    cert = json.loads((archive/'proof.rpa').read_text().split('\n', 1)[1])
    witness, info, trace = improvement(parse_mps(source), json.loads(hints.read_text()))
    cert['improvements'] = [witness]
    request = {'claims': cert['claims'], 'improvements': [witness['claim']]}
    d = {'case_id': 'test83', 'status': 'PROOF_NOT_COMPLETED', 'source': previous['source'], 'target': previous['target'], 'audit': previous['audit'], 'kernel_binary_sha256': sha(kernel), 'proof_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))}, 'base_preparer': {'path': str((archive/'prepare_test83.py').resolve()), 'sha256': sha(archive/'prepare_test83.py')}, 'previous_submission': {'path': str(archive), 'receipt_sha256': sha(archive/'preparation.json')}, 'claims': 'Complete integer source-to-target NonIncreasing map and target-to-source Equal recovery with the original 152 affine observations, plus a caller-bound strict improvement in the complete actual source model whenever the sum of all 61 dominated coordinates is positive. Hence every attained source optimum has all 61 coordinates zero. No numeric optimum, nonemptiness, all-feasible-point bijection, or LP relation is asserted.', 'counts': {**previous['counts'], 'improvements': 1}, 'strict_improvement': info, 'kernel_runs': [], 'negative_checks': [], 'prior_directional_negative_checks': previous['negative_checks'], 'working_format': 'V10 FROZEN 2026-10-14'}
    def save(): (out/'preparation.json').write_text(json.dumps(d, indent=2)+'\n')
    def emit(path, c): path.write_text('RPA 10\n'+json.dumps(c, separators=(',', ':'))+'\n')
    def invoke(cmd):
        assert sha(kernel) == d['kernel_binary_sha256']
        p = subprocess.run([str(kernel), *map(str, cmd)], capture_output=True, text=True)
        return {'command': [str(kernel), *map(str, cmd)], 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    emit(out/'proof.rpa', cert); (out/'request.json').write_text(json.dumps(request, separators=(',', ':'))+'\n'); save()
    for cmd in [['canonical', source, out/'source.mcm'], ['canonical', target, out/'target.mcm'], ['assemble', out/'proof.rpa', out/'proof.rpx'], ['verify', out/'source.mcm', out/'target.mcm', out/'proof.rpx', out/'request.json']]:
        result = invoke(cmd); d['kernel_runs'].append(result); save(); assert result['exit_code'] == 0, result
    baseline = json.loads(d['kernel_runs'][-1]['stdout']); assert baseline['status'] == 'VERIFIED' and baseline['improvements'] == 1
    assert all(sha(out/name) == sha(archive/name) for name in ('source.mcm', 'target.mcm'))
    for mutation in ['zero_margin', 'lost_replacement', 'missing_partition_premise', 'incorrect_saving', 'incomplete_tuple', 'false_positive_refutation', 'weakened_caller_predicate', 'unrequested_improvement']:
        bad = copy.deepcopy(witness); b = bad['block']; ret = b['end']['ImproveReturn']; badrequest = request
        if mutation == 'zero_margin': ret['margin']['Predicate'] = '0'
        elif mutation == 'lost_replacement': ret['map'][trace['changed_coordinate']]['terms'].pop()
        elif mutation == 'missing_partition_premise': b['steps'][trace['bound_root']]['Lin']['terms'].pop(0)
        elif mutation == 'incorrect_saving':
            term = b['steps'][trace['objective']]['Lin']['terms'][0]; term[1] = str(F(term[1]) + 1)
        elif mutation == 'incomplete_tuple': ret['map'].pop()
        elif mutation == 'false_positive_refutation': b['end'] = {'PositiveRefutation': {'fact': {'Assumption': 0}}}
        elif mutation == 'weakened_caller_predicate':
            badrequest = copy.deepcopy(request); badrequest['improvements'][0]['positive']['terms'].pop()
        else: badrequest = {'claims': request['claims']}
        changed = {**cert, 'improvements': [bad]}; rp = out/(mutation+'.rpa'); rx = out/(mutation+'.rpx'); rq = out/(mutation+'.json')
        emit(rp, changed); rq.write_text(json.dumps(badrequest, separators=(',', ':'))+'\n')
        assembled = invoke(['assemble', rp, rx]); assert assembled['exit_code'] == 0, assembled
        rejected = invoke(['verify', out/'source.mcm', out/'target.mcm', rx, rq]); payload = json.loads(rejected['stdout'])
        assert rejected['exit_code'] == 2 and payload['status'] == 'INVALID', rejected
        d['negative_checks'].append({'mutation': mutation, 'assemble': assembled, 'verify': rejected, 'result': payload, 'exit_code': 2, 'rpa_sha256': sha(rp), 'rpx_sha256': sha(rx), 'request_sha256': sha(rq), 'storage': 'Temporary mutation deleted; deterministic exact recipe in complete_test83.py.'})
        rp.unlink(); rx.unlink(); rq.unlink(); save()
    again = out/'deterministic.rpx'; result = invoke(['assemble', out/'proof.rpa', again]); d['kernel_runs'].append(result); save()
    assert result['exit_code'] == 0 and sha(again) == sha(out/'proof.rpx'); again.unlink()
    stable = lambda x: {k: v for k, v in x.items() if not k.endswith('_us')}
    for _ in range(2):
        result = invoke(['verify', out/'source.mcm', out/'target.mcm', out/'proof.rpx', out/'request.json']); d['kernel_runs'].append(result); save()
        assert result['exit_code'] == 0 and stable(json.loads(result['stdout'])) == stable(baseline)
    d.update(status='VERIFIED', assemble_byte_deterministic=True, verify_semantics_deterministic=True, preparation_seconds=time.perf_counter()-started, rpa_bytes=(out/'proof.rpa').stat().st_size, rpa_sha256=sha(out/'proof.rpa'))
    d['artifacts'] = {name: {'bytes': (out/name).stat().st_size, 'sha256': sha(out/name)} for name in ['source.mcm', 'target.mcm', 'proof.rpx', 'request.json']}
    save(); print(json.dumps({'case_id': 'test83', 'status': d['status'], 'improvement': info, 'statistics': baseline['statistics']}, indent=2))


if __name__ == '__main__': main()
