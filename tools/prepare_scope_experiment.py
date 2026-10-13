#!/usr/bin/env python3
"""Isolated borrowed-scope prototype; production and frozen checkpoints untouched."""
from pathlib import Path
import hashlib, json, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'audit/checkpoints/v5-source'
destination = ROOT / 'bench/shared-scope-prototype'
if destination.exists():
    raise SystemExit('Prototype exists; refusing to overwrite.')
shutil.copytree(source, destination)
path = destination / 'crates/core/src/verify.rs'
text = path.read_text()
marker = 'struct Context<'
assert text.count(marker) == 1
scope = '''// Each child borrows an immutable parent and stores only its own changes.
// Deleted inherited IDs are masked locally; a reused ID is visible in local first.
// No child can mutate a sibling or parent. All parent borrows end before a Cases
// conclusion is inserted. Whole Split's right branch may consume its parent state.
struct Facts<'a> {
    parent: Option<&'a Facts<'a>>,
    local: HashMap<u32,Fact>,
    deleted: std::collections::HashSet<u32>,
    count: usize,
}
impl<'a> Facts<'a> {
    fn new()->Self {Self{parent:None,local:HashMap::new(),deleted:Default::default(),count:0}}
    fn fork(&self)->Facts<'_> {Facts{parent:Some(self),local:HashMap::new(),deleted:Default::default(),count:self.count}}
    fn lookup(&self,id:&u32)->(Option<&Fact>,usize) {
        if let Some(f)=self.local.get(id){return (Some(f),1);}
        if self.deleted.contains(id){return (None,2);}
        match self.parent {None=>(None,2),Some(parent)=>{let (fact,probes)=parent.lookup(id);(fact,probes+2)}}
    }
    fn len(&self)->usize {self.count}
    fn try_reserve(&mut self,n:usize)->Result<(),std::collections::TryReserveError> {self.local.try_reserve(n)}
    fn insert(&mut self,id:u32,f:Fact) {self.local.insert(id,f);self.count+=1;}
    fn remove(&mut self,id:&u32)->Result<(bool,usize),String> {
        let (found,mut probes)=self.lookup(id);
        if found.is_none(){return Ok((false,probes));}
        let inherited=if let Some(parent)=self.parent {let (fact,p)=parent.lookup(id);probes+=p;fact.is_some()}else{false};
        if inherited && !self.deleted.contains(id) {
            self.deleted.try_reserve(1).map_err(|_|"RESOURCE_LIMIT scope deletion allocation")?;
            self.deleted.insert(*id);
        }
        self.local.remove(id);self.count-=1;Ok((true,probes))
    }
}
'''
text = text.replace(marker, scope + marker)
text = text.replace('live:&HashMap<u32,Fact>', "live:&Facts<'_>")
text = text.replace('live:&mut HashMap<u32,Fact>', "live:&mut Facts<'_>")
text = text.replace('mut live:HashMap<u32,Fact>', "mut live:Facts<'_>")
assert text.count('live.remove(id).is_none()') == 1
text = text.replace('if live.remove(id).is_none()', 'let (removed,probes)=live.remove(id)?;self.charge(probes)?;if !removed')
text = text.replace('Ref::Local(i)=>live.get(i).cloned().ok_or_else(bad)?,', 'Ref::Local(i)=>{let (fact,probes)=live.lookup(i);self.charge(probes)?;fact.cloned().ok_or_else(bad)?},')
text = text.replace('if live.contains_key(&id)', 'let (existing,probes)=live.lookup(&id);self.charge(probes)?;if existing.is_some()')
clone_charge = 'self.charge(live.values().map(|f|f.expr.terms.len()+1).sum())?;'
assert text.count(clone_charge) == 3
text = text.replace(clone_charge, 'self.charge(1)?; // constant-size child scope')
assert text.count('live.clone()') == 3
text = text.replace('live.clone()', 'live.fork()')
assert text.count('.run(block,HashMap::new(),') == 1
text = text.replace('.run(block,HashMap::new(),', '.run(block,Facts::new(),')
path.write_text(text)
manifest = {'baseline': str(source), 'candidate': str(destination), 'only_changed_source': str(path.relative_to(destination)),
            'before_sha256': hashlib.sha256((source / path.relative_to(destination)).read_bytes()).hexdigest(),
            'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'note': 'No mathematical rule, codec, schema, parser or dependency changes. Work counts remove actual eliminated copies.'}
(destination / 'experiment.json').write_text(json.dumps(manifest, indent=2) + '\n')
for action in ['test', 'build']:
    command = ['cargo', action, '--manifest-path', str(destination / 'Cargo.toml'), '-p', 'kernel-core', '--locked']
    if action == 'build': command.append('--release')
    result = subprocess.run(command, capture_output=True, text=True)
    (destination / (action + '.log')).write_text(result.stdout + '\n' + result.stderr)
    if result.returncode: raise SystemExit(f'{action} failed; log preserved.')
print('Shared-scope prototype built and all existing tests passed:', destination)
