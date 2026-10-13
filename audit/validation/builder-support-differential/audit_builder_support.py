#!/usr/bin/env python3
"""Compare complete builder outputs and exact work thresholds before/after extraction.

The historical implementation is a differential reference, not a soundness
oracle. Independent Fraction semantics are exercised by the normal core suite.
"""
from pathlib import Path
from fractions import Fraction
import argparse, copy, hashlib, json, random, subprocess

ROOT = Path(__file__).resolve().parents[1]
SEED = 0x4255494C

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value): path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists(), 'refusing to replace previous audit'
    args.out.mkdir(parents=True)
    rng = random.Random(SEED)
    def q(): return str(Fraction(rng.randint(-31, 31), rng.choice([1, 2, 7, 11, 19])))
    def expr(n):
        terms = [[i, q()] for i in range(n) if rng.randrange(3) != 0]
        return {'constant': q(), 'terms': [t for t in terms if t[1] != '0']}
    def model(n, kind, variant):
        rows = rng.randrange(5)
        return {'name': '完整 parent '+str(variant), 'vars': [
            {'name': f'$rpx_{kind}_var_{n+i}', 'integer': bool(i%2),
             'lower': None if i%3 == 0 else q(), 'upper': None if i%4 == 0 else q()}
            for i in range(n)], 'rows': [
            {'name': f'$rpx_{kind}_row_{rows+i}', 'expr': expr(n),
             'lower': q(), 'upper': q()} for i in range(rows)], 'objective': expr(n)}
    fixtures = []
    for kind in ['flow', 'interval', 'menu', 'signed', 'injectivity', 'level']:
        for variant in range(96):
            n = [0, 1, 2, 4, 9][variant % 5]
            inp = model(n, kind, variant)
            f = {'kind': kind, 'input': inp}
            if kind == 'flow':
                nodes = 1 + variant % 5
                arcs = [[rng.randrange(nodes), rng.randrange(nodes)] for _ in range(variant % 8)]
                groups = []
                for _ in range(1 + variant % 3):
                    groups.append({'source':rng.randrange(nodes), 'commodities':[
                        [rng.randrange(nodes), str(abs(Fraction(q())))] for _ in range(1 + variant % 4)],
                        'flows':[expr(n) for _ in arcs], 'nonnegative':['Exact']*len(arcs), 'balances':['Exact']*nodes})
                f['witness'] = {'nodes':nodes,'arcs':arcs,'groups':groups}
            elif kind == 'interval':
                f['witness'] = []
                for _ in range(variant % 5):
                    lower = [expr(n) for _ in range(variant % 4)]
                    upper = [expr(n) for _ in range((variant // 4) % 4)]
                    f['witness'].append({'lower':lower,'upper':upper,'checks':[
                        {'Local':i} for i in range(len(lower)*len(upper))]})
            elif kind == 'menu':
                f['witness'] = [{'maximum_index':variant%13,'activation':expr(n),'index':expr(n),
                    'checks':['Exact']*6} for _ in range(variant%5)]
            elif kind == 'signed':
                f['witness'] = [{'capacity':str(abs(Fraction(q()))),'activation':expr(n),'flow':expr(n),
                    'checks':['Exact']*5} for _ in range(variant%5)]
            elif kind == 'injectivity':
                f['output'] = model(variant%5, kind, variant+1000)
                f['map'] = [expr(n) for _ in f['output']['vars']]
            else: f['level'] = q()
            fixtures.append(f)
    # Model validation must remain active after extracting prefix copying.
    invalid = []
    for f in fixtures:
        if not f['input']['vars']: continue
        bad = copy.deepcopy(f)
        bad['input']['objective']['terms'] = [[len(f['input']['vars']), '1']]
        invalid.append(bad)
    all_full = fixtures + invalid
    binaries = {}
    build_receipts = []
    for label, tree in [('baseline',args.baseline),('extracted',ROOT)]:
        project = args.out/label
        project.mkdir()
        manifest = ('[package]\nname="builder-support-probe"\nversion="0.0.0"\nedition="2024"\n'
            '[workspace]\n[dependencies]\nkernel-core={path='+json.dumps(str(tree.resolve()/'crates/core'))+'}\n'
            'serde_json="=1.0.152"\n[[bin]]\nname="probe"\npath='+json.dumps(str(ROOT/'tools/builder_support_probe.rs'))+'\n')
        (project/'Cargo.toml').write_text(manifest)
        cmd = ['cargo','build','--release','--offline','--manifest-path',str(project/'Cargo.toml')]
        r = subprocess.run(cmd, capture_output=True, text=True)
        (project/'build.log').write_text(r.stdout+r.stderr)
        build_receipts.append({'label':label,'command':cmd,'exit_code':r.returncode})
        assert r.returncode == 0, r.stderr
        binaries[label] = project/'target/release/probe'
    def run(label, data, suffix):
        raw = ''.join(json.dumps(v,separators=(',',':'))+'\n' for v in data)
        r = subprocess.run([str(binaries[label])],input=raw,capture_output=True,text=True)
        (args.out/f'{label}-{suffix}.jsonl').write_text(r.stdout)
        (args.out/f'{label}-{suffix}.stderr').write_text(r.stderr)
        assert r.returncode == 0, r.stderr
        result = [json.loads(line) for line in r.stdout.splitlines()]
        assert len(result) == len(data)
        return result
    base = run('baseline',all_full,'full')
    candidate = run('extracted',all_full,'full')
    boundary = []
    for f,result in zip(fixtures,base):
        assert result['status'] == 'PREPARED'
        work = result['data']['statistics']['work']
        for limit in [0, max(0,work-1), work]:
            probe = copy.deepcopy(f); probe['work']=limit; boundary.append(probe)
    a = run('baseline',boundary,'boundary'); b = run('extracted',boundary,'boundary')
    mismatches = []
    detail_changes = []
    for phase, left, right in [('full',base,candidate),('boundary',a,b)]:
        for i,(old,new) in enumerate(zip(left,right)):
            if old['status'] != new['status'] or (old['status']=='PREPARED' and old != new):
                mismatches.append({'phase':phase,'index':i,'baseline':old,'extracted':new})
            elif old != new:
                detail_changes.append({'phase':phase,'index':i,'baseline':old,'extracted':new})
    dump(args.out/'fixtures.json',all_full)
    dump(args.out/'boundary.json',boundary)
    dump(args.out/'result.json',{'seed':SEED,'prepared_fixtures':len(fixtures),'invalid_models':len(invalid),
        'boundary_calls_per_implementation':len(boundary),'complete_output_and_work_mismatches':mismatches,
        'error_message_changes_same_category':detail_changes,'builds':build_receipts,
        'binaries':{k:{'path':str(p),'sha256':sha(p)} for k,p in binaries.items()},
        'probe_sha256':sha(ROOT/'tools/builder_support_probe.rs'),'generator_sha256':sha(Path(__file__)),
        'status':'PASS' if not mismatches else 'FAIL','note':'Point/fiber is checked by integration and complete-corpus replays; finite differential equality is not a theorem proof.'})
    print(json.dumps({'status':'PASS' if not mismatches else 'FAIL','prepared':len(fixtures),
        'invalid':len(invalid),'boundaries':len(boundary),'mismatches':len(mismatches),'error_detail_changes':len(detail_changes)}),flush=True)
    assert not mismatches

if __name__ == '__main__': main()
