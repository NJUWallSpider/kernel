#!/usr/bin/env python3
"""Build two frozen V1 verifier representations against IDENTICAL model/codec code.

The historical raw benchmark is retained. This creates a new controlled replay,
not a claim that the later model snapshot has the historical source hash.
"""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--label',default='reconstructed-v1');a=p.parse_args()
base=ROOT/'bench/baseline-source/workspace';opt=ROOT/'bench/reconstructed-sparse-source'
if not opt.exists():
 shutil.copytree(base,opt,ignore=shutil.ignore_patterns('target'))
 file=opt/'crates/core/src/verify.rs';s=file.read_text()
 start=s.index('        let mut result=Expr::zero();result.constant=e.constant.clone();');end=s.index('\n    fn obligation',start)
 s=s[:start]+'''        let mut result=Accumulator::new(e.constant.clone());
        for (i,c) in &e.terms {
            let m=map.get(*i as usize).ok_or("INVALID incomplete mapping")?;
            self.charge(m.terms.len()+1)?;
            self.stats.substitution_terms+=m.terms.len() as u64;
            result.add(m,c)?;
        } result.finish()
    }
'''+s[end:]
 s=s.replace('let mut e=Expr::zero();e.constant=constant.clone();','let mut e=Accumulator::new(constant.clone());').replace('self.charge(e.terms.len()+f.expr.terms.len()+1)?;','self.charge(f.expr.terms.len()+1)?;').replace('e.add_scaled(&f.expr,c)?;','e.add(&f.expr,c)?;').replace('(*id,Fact{kind:*kind,expr:e})','(*id,Fact{kind:*kind,expr:e.finish()?})')
 i=s.index('struct Context');s=s[:i]+'''struct Accumulator { constant: Q, terms: HashMap<u32,Q> }
impl Accumulator {
 fn new(constant:Q)->Self{Self{constant,terms:HashMap::new()}}
 fn add(&mut self,e:&Expr,c:&Q)->Result<(),String>{
  crate::model::check_q(c)?;if c.is_zero(){return Ok(());}
  self.constant+=&e.constant*c;crate::model::check_q(&self.constant)?;
  if self.terms.len().checked_add(e.terms.len()).is_none_or(|n|n>crate::model::MAX_TERMS){return Err("RESOURCE_LIMIT accumulator terms".into());}
  self.terms.try_reserve(e.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator allocation")?;
  for(i,q)in&e.terms{let product=q*c;crate::model::check_q(&product)?;let value=self.terms.entry(*i).or_insert_with(Q::zero);*value+=product;crate::model::check_q(value)?;if value.is_zero(){self.terms.remove(i);}}Ok(())
 }
 fn finish(self)->Result<Expr,String>{let mut terms=Vec::new();terms.try_reserve(self.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator output")?;terms.extend(self.terms);terms.sort_unstable_by_key(|(i,_)|*i);Ok(Expr{constant:self.constant,terms})}
}
'''+s[i:];file.write_text(s)
manifest={}
for label,src in [('before',base),('after',opt)]:
 subprocess.run(['cargo','test','--manifest-path',str(src/'Cargo.toml'),'-p','kernel-core','--locked'],check=True)
 subprocess.run(['cargo','build','--manifest-path',str(src/'Cargo.toml'),'-p','kernel-core','--release','--locked'],check=True)
 manifest[label]={'directory':str(src),'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((src/'crates/core/src').glob('*.rs'))},'binary_sha256':hashlib.sha256((src/'target/release/rpx').read_bytes()).hexdigest()}
for name,h in manifest['before']['sources'].items():
 if name!='verify.rs':assert manifest['after']['sources'][name]==h
(ROOT/'bench/baseline-source/reconstruction.json').write_text(json.dumps(manifest,indent=2)+'\n')
if a.run:
 for label,src in [('before',base),('after',opt)]:subprocess.run(['python3',str(ROOT/'tools/benchmark.py'),'--kernel',str(src/'target/release/rpx'),'--source-root',str(src),'--label',f'{a.label}-{label}'],check=True)
print('Both variants built; only verify.rs differs. --run executes the unchanged fixed benchmark.')
