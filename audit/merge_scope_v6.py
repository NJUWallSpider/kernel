#!/usr/bin/env python3
"""Reproduce the scope port from a preserved V6 boxed source overlay."""
from pathlib import Path
import hashlib, json, shutil, difflib
ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / 'audit/checkpoints/v6-boxed-before-scope'
FILES = ['crates/core/src/proof.rs', 'crates/core/src/codec.rs', 'crates/core/src/verify.rs', 'crates/core/tests/local_cases.rs', 'crates/core/tests/plotkin.rs', 'crates/core/tests/refutation.rs']
def sha(data): return hashlib.sha256(data).hexdigest()
BACKUP.mkdir(parents=True, exist_ok=True)
before = {}
for name in FILES:
    source = ROOT / name
    target = BACKUP / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes()!=source.read_bytes(): raise SystemExit('Refusing to replace different pre-merge backup: '+name)
    else:
        shutil.copy2(source, target)
    before[name] = sha(source.read_bytes())
(BACKUP / 'manifest.json').write_text(json.dumps({'base_checkpoint':'audit/checkpoints/v6-original-scopes-source','purpose':'Six-file boxed Cases overlay before persistent scopes; overlay these files onto the base checkpoint to recover exact pre-scope source.','files':before}, indent=2)+'\n')
prototype = ROOT / 'bench/shared-scope-prototype/crates/core/src/verify.rs'
test_source = ROOT / 'bench/shared-scope-prototype/crates/core/src/scope_state_audit.rs'
text = (ROOT / FILES[2]).read_text()
p = prototype.read_text()
start = p.index('// Each child borrows an immutable parent')
end = p.index("struct Context<'a>", start)
assert "struct Facts<'a>" not in text
text = text.replace("struct Context<'a>", p[start:end]+"struct Context<'a>", 1)
def replace(old,new,count):
    global text
    assert text.count(old)==count, (old,text.count(old),count)
    text=text.replace(old,new)
replace('HashMap<u32,Fact>', "Facts<'_>", 10)
replace('Ref::Local(i)=>live.get(i).cloned().ok_or_else(bad)?,','Ref::Local(i)=>{let (fact,probes)=live.lookup(i);self.charge(probes)?;fact.cloned().ok_or_else(bad)?},',1)
replace('Step::Drop{ids}=>{self.charge(ids.len())?;for id in ids {if live.remove(id).is_none(){return Err("INVALID drop of absent fact".into());}}continue},','Step::Drop{ids}=>{self.charge(ids.len())?;for id in ids {let (removed,probes)=live.remove(id)?;self.charge(probes)?;if !removed{return Err("INVALID drop of absent fact".into());}}continue},',1)
replace('self.charge(live.values().map(|f|f.expr.terms.len()+1).sum())?;', 'self.charge(1)?; // constant-size child scope', 3)
replace('live.clone()', 'live.fork()', 3)
replace('if live.contains_key(&id) {return Err("INVALID live fact register overwritten".into());}','let (existing,probes)=live.lookup(&id);self.charge(probes)?;if existing.is_some() {return Err("INVALID live fact register overwritten".into());}',1)
replace('.run(block,HashMap::new(),&mut Vec::new(),1)?;', '.run(block,Facts::new(),&mut Vec::new(),1)?;',2)
# The broad type replacement includes the new local-map field. Restore just it.
replace("local: Facts<'_>,", 'local: HashMap<u32,Fact>,', 1)
text+='\n#[cfg(test)]\n#[path="scope_state_audit.rs"]\nmod scope_state_audit;\n'
# Mechanically compare all pre-V6 code with the audited candidate. Only the boxed
# Cases representation and the explicit V6 refutation differences may remain.
compare=text[:text.index('\n/// Establish infeasibility')]
compare=compare.replace('refutation:bool, ', '').replace('refutation:false,','')
compare=compare.replace('        if self.refutation && !matches!(block.end,End::Absurd{..}|End::Split{..}){return Err("INVALID refutation requires only Absurd/Split endpoints".into());}\n','')
compare=compare.replace('Step::Cases(case)=>{let CasesStep{id,kind,expression,split,integer,left,right}=case.as_ref();','Step::Cases{id,kind,expression,split,integer,left,right}=>{')
assert compare.strip()==p.strip(), ''.join(difflib.unified_diff(p.splitlines(True),compare.splitlines(True)))
(ROOT / FILES[2]).write_text(text)
shutil.copy2(test_source, ROOT / 'crates/core/src/scope_state_audit.rs')
after={name:sha((ROOT/name).read_bytes()) for name in FILES}
after['crates/core/src/scope_state_audit.rs']=sha(test_source.read_bytes())
report={'status':'MERGED_PENDING_TESTS','base_checkpoint':'audit/checkpoints/v6-original-scopes-source','pre_merge_backup':str(BACKUP.relative_to(ROOT)),'reproducer':'audit/merge_scope_v6.py','prototype':str(prototype.relative_to(ROOT)),'prototype_sha256':sha(prototype.read_bytes()),'independent_scope_test_sha256':sha(test_source.read_bytes()),'before_sha256':before,'after_sha256':after,'source_equivalence':'All prototype code matches exactly after removing V6 refutation additions and unboxing Cases pattern; both V6 root initializations independently use Facts::new.','format_semantics':'Unchanged. Codec, proof types and all existing tests are byte-identical to pre-merge files. Work accounting now charges actual ancestor probes instead of whole-map copying.','validation':[]}
(ROOT/'audit/scope_v6_merge.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'backup':report['pre_merge_backup'],'prototype_sha256':report['prototype_sha256'],'after_sha256':after},indent=2))
