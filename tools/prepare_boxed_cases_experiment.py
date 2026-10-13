#!/usr/bin/env python3
"""Create an isolated V3 layout prototype; never edit the accepted production tree.

Boxing the rare Cases payload keeps the much more frequent Lin/Drop enum slots
smaller. Mathematical fields, serde schema and RPX encoding are unchanged.
"""
from pathlib import Path
import hashlib, json, re, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'audit/checkpoints/v3-source'
destination = ROOT / 'bench/boxed-cases-prototype'
if destination.exists():
    raise SystemExit('Prototype already exists; refusing to overwrite evidence.')
shutil.copytree(source, destination)
proof = destination / 'crates/core/src/proof.rs'
text = proof.read_text()
old = 'Cases { id: u32, kind: Kind, expression: Expr, split: Expr, integer: Option<Ref>, left: Box<Derivation>, right: Box<Derivation> },'
assert text.count(old) == 1
text = text.replace(old, 'Cases(Box<CasesStep>),')
marker = '#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]\n#[serde(deny_unknown_fields)]\npub struct Derivation '
assert text.count(marker) == 1
text = text.replace(marker, '''#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CasesStep {
    pub id: u32, pub kind: Kind, pub expression: Expr, pub split: Expr,
    pub integer: Option<Ref>, pub left: Box<Derivation>, pub right: Box<Derivation>,
}
''' + marker)
proof.write_text(text)
for path in (destination / 'crates/core').rglob('*.rs'):
    text = path.read_text()
    text = text.replace('use crate::proof::{Block,', 'use crate::proof::{CasesStep,Block,')
    for fields in ['id,kind,expression,split,integer,left,right', 'left,right,..']:
        text = text.replace('Step::Cases{' + fields + '}=>{',
                            'Step::Cases(case)=>{let CasesStep{' + fields + '}=case.as_ref();')
    text = re.sub(r'if let Step::Cases\{([^{}]+)\}=([^{}]+)\{',
                  lambda m: 'if let Step::Cases(case)=' + m[2] + '{let CasesStep{' + m[1] + '}=case.as_mut();', text)
    start = 0
    while True:
        start = text.find('Step::Cases{', start)
        if start == -1:
            break
        end = start + len('Step::Cases')
        depth = 0
        while end < len(text):
            if text[end] == '{': depth += 1
            if text[end] == '}':
                depth -= 1
                if depth == 0: break
            end += 1
        assert depth == 0
        payload = text[start + len('Step::Cases'):end + 1]
        replacement = 'Step::Cases(Box::new(CasesStep' + payload + '))'
        text = text[:start] + replacement + text[end + 1:]
        start += len(replacement)
    path.write_text(text)
manifest = {'baseline': str(source), 'prototype': str(destination), 'changed': {}}
for path in sorted((destination / 'crates/core').rglob('*.rs')):
    relative = path.relative_to(destination)
    old = source / relative
    before = hashlib.sha256(old.read_bytes()).hexdigest()
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != after:
        manifest['changed'][str(relative)] = {'before': before, 'after': after}
(destination / 'experiment.json').write_text(json.dumps(manifest, indent=2) + '\n')
for action in ['test', 'build']:
    command = ['cargo', action, '--manifest-path', str(destination / 'Cargo.toml'), '-p', 'kernel-core', '--locked']
    if action == 'build': command.append('--release')
    result = subprocess.run(command, capture_output=True, text=True)
    (destination / (action + '.log')).write_text(result.stdout + '\n' + result.stderr)
    if result.returncode:
        raise SystemExit(f'{action} failed; log preserved in {destination}')
print('Prototype built and existing exact/semantic/byte tests passed:', destination)
