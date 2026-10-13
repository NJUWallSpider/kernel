#!/usr/bin/env python3
"""Materialize narrow exact-rational shortcuts from frozen V7, never production.

Refuses to overwrite evidence. Test-only arithmetic oracle files are copied from
audit/ after independent Python Fraction generation. Build/run separately so the
parent can schedule isolated benchmark windows.
"""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "audit/checkpoints/v7-source"
DEST = ROOT / "bench/rational-shortcuts-prototype"
if DEST.exists():
    raise SystemExit("Prototype already exists; refusing to overwrite evidence")
shutil.copytree(SOURCE, DEST)

model = DEST / "crates/core/src/model.rs"
text = model.read_text()
old = '''    if q.denom() <= &BigInt::zero() || q.numer().gcd(q.denom()) != BigInt::one() {'''
new = '''    // Every integer, including zero and negative integers, has a canonical
    // denominator of one. The bit checks above still precede this shortcut.
    if q.denom().is_one() {
        return Ok(());
    }
    if q.denom() <= &BigInt::zero() || q.numer().gcd(q.denom()) != BigInt::one() {'''
assert text.count(old) == 1
text = text.replace(old, new)
old = '''        let mut out = Self {
            constant: &self.constant * scale,
            terms: Vec::new(),
        };'''
new = '''        let one = scale.is_one();
        let minus_one = scale.denom().is_one()
            && scale.numer().is_negative() && scale.numer().magnitude().is_one();
        let product = |q: &Q| {
            if one { q.clone() } else if minus_one { -q } else { q * scale }
        };
        let mut out = Self {
            constant: product(&self.constant),
            terms: Vec::new(),
        };'''
assert text.count(old) == 1
text = text.replace(old, new)
old = '''        for (id, q) in &self.terms {
            let q = q * scale;
            check_q(&q)?;
            out.terms.push((*id, q));
        }'''
new = old.replace('let q = q * scale;', 'let q = product(q);')
assert text.count(old) == 1
text = text.replace(old, new)
model.write_text(text)

verify = DEST / "crates/core/src/verify.rs"
text = verify.read_text()
old = '''        let constant_product=&e.constant*c;check_q(&constant_product)?;
        self.constant+=constant_product;check_q(&self.constant)?;'''
new = '''        let one=c.is_one();
        let minus_one=c.denom().is_one() && c.numer().is_negative() && c.numer().magnitude().is_one();
        let product=|q:&Q| {if one {q.clone()}else if minus_one {-q}else{q*c}};
        let constant_product=product(&e.constant);check_q(&constant_product)?;
        if self.constant.is_zero(){self.constant=constant_product;}
        else if !constant_product.is_zero(){self.constant+=constant_product;}
        check_q(&self.constant)?;'''
assert text.count(old) == 1
text = text.replace(old, new)
old = '''            let product=q*c;check_q(&product)?;
            let value=self.terms.entry(*i).or_insert_with(Q::zero);
            *value+=product;check_q(value)?;
            if value.is_zero(){self.terms.remove(i);}'''
new = '''            let product=product(q);check_q(&product)?;
            match self.terms.entry(*i) {
                std::collections::hash_map::Entry::Vacant(slot)=>{
                    // The result is exactly the checked product, with no sum.
                    if !product.is_zero(){slot.insert(product);}
                },
                std::collections::hash_map::Entry::Occupied(mut slot)=>{
                    *slot.get_mut()+=product;check_q(slot.get())?;
                    if slot.get().is_zero(){slot.remove();}
                },
            }'''
assert text.count(old) == 1
text = text.replace(old, new)
text += '\n#[cfg(test)]\n#[path="rational_shortcuts_audit.rs"]\nmod rational_shortcuts_audit;\n'
verify.write_text(text)
shutil.copy2(ROOT / 'audit/rational_shortcuts_audit.rs', DEST / 'crates/core/src/rational_shortcuts_audit.rs')
shutil.copy2(ROOT / 'audit/rational_shortcuts_oracle.json', DEST / 'tests/vectors/rational_shortcuts_oracle.json')

manifest = {'baseline': str(SOURCE), 'prototype': str(DEST), 'changed': {}, 'added': {}}
diff = []
for relative in ['crates/core/src/model.rs', 'crates/core/src/verify.rs',
                 'crates/core/src/rational_shortcuts_audit.rs', 'tests/vectors/rational_shortcuts_oracle.json']:
    before, after = SOURCE / relative, DEST / relative
    after_hash = hashlib.sha256(after.read_bytes()).hexdigest()
    if before.exists():
        manifest['changed'][relative] = {'before': hashlib.sha256(before.read_bytes()).hexdigest(), 'after': after_hash}
        diff.extend(difflib.unified_diff(before.read_text().splitlines(True), after.read_text().splitlines(True),
                                         fromfile='v7-source/' + relative, tofile='rational-shortcuts-prototype/' + relative))
    else:
        manifest['added'][relative] = after_hash
manifest['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(DEST / 'experiment.json').write_text(json.dumps(manifest, indent=2) + '\n')
(DEST / 'source.diff').write_text(''.join(diff))
print(DEST)
