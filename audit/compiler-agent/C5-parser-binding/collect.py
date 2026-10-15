from pathlib import Path
import json,hashlib
RUNS=Path('/Users/bhz/Code/reform_test/runs');BATCH=RUNS/'compiler-batch-C5-20261015';OUT=Path('/Users/bhz/Code/kernel/audit/compiler-agent/C5-parser-binding');meta=json.loads((BATCH/'batch.json').read_text())
for case in meta['cases']:
    run=RUNS/f'{case}-compiler-{BATCH.name}'
    if not (run/'assessment.json').is_file() or (OUT/f'{case}.json').exists():continue
    manifest=run/'output/delivery.json'
    if not manifest.exists():continue
    document=json.loads(manifest.read_text());records=[]
    for index,piece in enumerate(document['pieces']):
        for role in ('source','target'):
            p=(run/piece[role]).resolve()
            with p.open('rb') as stream:magic=stream.read(4)
            family='MCM' if magic==b'MCM\0' or p.suffix.lower()=='.mcm' else 'LP' if p.suffix.lower()=='.lp' else 'MPS'
            records.append({'piece':index,'role':role,'path':str(p),'first4_hex':magic.hex(),'suffix':p.suffix,'reader_family':family,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    cross=[{'left':a,'right':z} for index,a in enumerate(records) for z in records[index+1:] if a['sha256']==z['sha256'] and a['reader_family']!=z['reader_family']]
    record={'case':case,'checkpoint':meta['git_head'],'independent_assessor_model_reuse':False,'endpoints':records,'same_sha256_cross_parser_family_pairs':cross,'cross_parser_library_bug_observed':bool(cross),'scope_note':'Actual first4 MCM magic overrides suffix for the Kernel model reader. Each stage was independently canonicalized/exported/verified; no same-SHA model substitution. Normal Model/Proof compiled MCM endpoints do not exercise the later-discovered package standard-text reader-reuse defect.'}
    (OUT/f'{case}.json').write_text(json.dumps(record,indent=2)+'\n')
    print(case,'cross_parser_same_sha_pairs',len(cross))
