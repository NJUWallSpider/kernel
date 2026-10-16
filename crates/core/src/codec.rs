//! Strict MCM 1 and RPX 11 codec.
//! See docs/FORMAT.md.
//! All bytes are interpreted before execution, including both sides of every split.
use crate::model::{Expr, Model, Q, Row, Var};
use crate::proof::*;
use num_bigint::{BigInt, Sign};
use num_traits::Zero;

pub const MAX_FILE_BYTES: usize = 1 << 30;
pub const MAX_ITEMS: usize = 10_000_000;
pub const MAX_TOTAL_ITEMS: usize = 20_000_000;
pub const MAX_INTEGER_BYTES: usize = 1700;
pub const MAX_NAME_BYTES: usize = 1 << 20;
pub const MAX_DEPTH: usize = 64;

fn invalid(s: impl AsRef<str>) -> String { format!("INVALID: {}", s.as_ref()) }
fn resource(s: impl AsRef<str>) -> String { format!("RESOURCE_LIMIT: {}", s.as_ref()) }
fn normalize_error(s: String) -> String {
    if s.starts_with("INVALID") || s.starts_with("RESOURCE_LIMIT") { s } else { invalid(s) }
}

struct Writer { data: Vec<u8>, items: usize }
impl Writer {
    fn new(magic: &[u8; 4]) -> Result<Self, String> {
        Self::new_version(magic,1)
    }
    fn new_version(magic: &[u8;4],version:u16)->Result<Self,String>{
        let mut w = Self { data: Vec::new(), items: 0 };
        w.bytes(magic)?; w.u16(version)?; w.u16(0)?; w.u64(0)?; Ok(w)
    }
    fn bytes(&mut self, b: &[u8]) -> Result<(), String> {
        let end = self.data.len().checked_add(b.len()).ok_or_else(|| resource("file size overflow"))?;
        if end > MAX_FILE_BYTES { return Err(resource("file byte limit")); }
        self.data.try_reserve(b.len()).map_err(|_| resource("allocation"))?;
        self.data.extend_from_slice(b); Ok(())
    }
    fn u8(&mut self, n: u8) -> Result<(), String> { self.bytes(&[n]) }
    fn u16(&mut self, n: u16) -> Result<(), String> { self.bytes(&n.to_le_bytes()) }
    fn u32(&mut self, n: u32) -> Result<(), String> { self.bytes(&n.to_le_bytes()) }
    fn u64(&mut self, n: u64) -> Result<(), String> { self.bytes(&n.to_le_bytes()) }
    fn count(&mut self, n: usize) -> Result<(), String> {
        self.items = self.items.checked_add(n).ok_or_else(|| resource("item count overflow"))?;
        if n > MAX_ITEMS || self.items > MAX_TOTAL_ITEMS { return Err(resource("item count limit")); }
        self.u32(u32::try_from(n).map_err(|_| resource("count width"))?)
    }
    fn name(&mut self, s: &str) -> Result<(), String> {
        if s.len() > MAX_NAME_BYTES { return Err(resource("name byte limit")); }
        self.u32(s.len() as u32)?; self.bytes(s.as_bytes())
    }
    fn tag(&mut self, tag: u8) -> Result<(), String> { self.u8(tag)?; self.u8(0)?; self.u16(0) }
    fn q(&mut self, q: &Q) -> Result<(), String> {
        if q.denom() <= &BigInt::zero() { return Err(invalid("nonpositive rational denominator")); }
        if q.numer().bits() > (MAX_INTEGER_BYTES * 8) as u64 || q.denom().bits() > (MAX_INTEGER_BYTES * 8) as u64 {
            return Err(resource("rational magnitude limit"));
        }
        crate::model::check_q(q).map_err(normalize_error)?;
        let (sign, mut n) = q.numer().to_bytes_le();
        let (_, d) = q.denom().to_bytes_le();
        if q.numer().is_zero() { n.clear(); }
        self.tag(if sign == Sign::Minus { 1 } else { 0 })?;
        self.u32(n.len() as u32)?; self.u32(d.len() as u32)?;
        self.bytes(&n)?; self.bytes(&d)
    }
    fn option_q(&mut self, q: &Option<Q>) -> Result<(), String> {
        match q { None => self.u8(0), Some(v) => { self.u8(1)?; self.q(v) } }
    }
    fn expr(&mut self, e: &Expr) -> Result<(), String> {
        validate_expr(e)?;
        self.q(&e.constant)?; self.count(e.terms.len())?;
        for (i, q) in &e.terms { self.u32(*i)?; self.q(q)?; } Ok(())
    }
    fn fact_ref(&mut self, r: &Ref) -> Result<(), String> {
        let (tag, id) = match r {
            Ref::VarLower(i) => (0, Some(*i)), Ref::VarUpper(i) => (1, Some(*i)),
            Ref::VarInt(i) => (2, Some(*i)), Ref::RowLower(i) => (3, Some(*i)),
            Ref::RowUpper(i) => (4, Some(*i)), Ref::RowEq(i) => (5, Some(*i)),
            Ref::Local(i) => (6, Some(*i)), Ref::Assumption(i) => (7, Some(*i)), Ref::Exact => (8, None),
        };
        self.tag(tag)?; if let Some(id) = id { self.u32(id)?; } Ok(())
    }
    fn steps(&mut self, steps: &[Step], depth: usize) -> Result<(), String> {
        if depth > MAX_DEPTH { return Err(resource("block depth limit")); }
        self.count(steps.len())?;
        for step in steps {
            match step {
                Step::Lin { id, kind, constant, terms } => {
                    self.tag(0)?; self.u32(*id)?;
                    self.tag(match kind { Kind::Le => 0, Kind::Eq => 1, Kind::Int => 2 })?;
                    self.q(constant)?; self.count(terms.len())?;
                    for (r, q) in terms { self.fact_ref(r)?; self.q(q)?; }
                },
                Step::Round { id, le, integer } => { self.tag(1)?; self.u32(*id)?; self.fact_ref(le)?; self.fact_ref(integer)?; },
                Step::Drop { ids } => { self.tag(2)?; self.count(ids.len())?; for id in ids { self.u32(*id)?; } },
                Step::EqPair{id,positive,negative}=>{
                    self.tag(3)?;self.u32(*id)?;self.fact_ref(positive)?;self.fact_ref(negative)?;
                },
                Step::Plotkin{id,bits,distance,variables,cliques}=>{
                    self.tag(5)?;self.u32(*id)?;self.u32(*bits)?;self.u32(*distance)?;
                    self.count(variables.len())?;for (i,label) in variables{self.u32(*i)?;self.u64(*label)?;}
                    self.count(cliques.len())?;for r in cliques{self.fact_ref(r)?;}
                },
                Step::Cases(case)=>{let CasesStep{id,kind,expression,split,integer,left,right}=case.as_ref();
                    self.tag(4)?;self.u32(*id)?;self.tag(match kind{Kind::Le=>0,Kind::Eq=>1,Kind::Int=>2})?;
                    self.expr(expression)?;self.expr(split)?;
                    match integer{None=>self.u8(0)?,Some(r)=>{self.u8(1)?;self.fact_ref(r)?;}}
                    self.derivation(left,depth+1)?;self.derivation(right,depth+1)?;
                },
            }
        }
        Ok(())
    }
    fn derivation(&mut self,d:&Derivation,depth:usize)->Result<(),String>{
        self.steps(&d.steps,depth)?;
        match &d.end{DerivationEnd::Witness(r)=>{self.tag(0)?;self.fact_ref(r)},DerivationEnd::Absurd(r)=>{self.tag(1)?;self.fact_ref(r)}}
    }
    fn block(&mut self, b: &Block, depth: usize) -> Result<(), String> {
        self.steps(&b.steps,depth)?;
        match &b.end {
            End::SubflowLift{witness,body}=>{
                self.tag(7)?;self.u32(witness.nodes)?;
                self.count(witness.arcs.len())?;for (tail,head) in &witness.arcs{self.u32(*tail)?;self.u32(*head)?;}
                self.count(witness.groups.len())?;
                for g in &witness.groups{
                    self.u32(g.source)?;self.count(g.demands.len())?;for (sink,demand) in &g.demands{self.u32(*sink)?;self.q(demand)?;}
                    self.count(g.flows.len())?;for e in &g.flows{self.expr(e)?;}
                    self.count(g.nonnegative.len())?;for r in &g.nonnegative{self.fact_ref(r)?;}
                    self.count(g.balances.len())?;for r in &g.balances{self.fact_ref(r)?;}
                }
                self.block(body,depth+1)?;
            },
            End::SignedLift{decompositions,body}=>{
                self.tag(6)?;self.count(decompositions.len())?;
                for d in decompositions{self.q(&d.capacity)?;self.expr(&d.flow)?;self.expr(&d.activation)?;self.count(d.checks.len())?;for r in &d.checks{self.fact_ref(r)?;}}
                self.block(body,depth+1)?;
            },
            End::MenuLift{menus,body}=>{
                self.tag(5)?;self.count(menus.len())?;
                for m in menus{self.u32(m.maximum_index)?;self.expr(&m.activation)?;self.expr(&m.index)?;self.count(m.checks.len())?;for r in &m.checks{self.fact_ref(r)?;}}
                self.block(body,depth+1)?;
            },
            End::IntervalLift{intervals,body}=>{
                self.tag(4)?;self.count(intervals.len())?;
                for i in intervals{
                    self.count(i.lower.len())?;for e in &i.lower{self.expr(e)?;}
                    self.count(i.upper.len())?;for e in &i.upper{self.expr(e)?;}
                    self.count(i.checks.len())?;for r in &i.checks{self.fact_ref(r)?;}
                }
                self.block(body,depth+1)?;
            },
            End::FlowLift{witness,body}=>{
                self.tag(3)?;self.u32(witness.nodes)?;
                self.count(witness.arcs.len())?;for (tail,head) in &witness.arcs{self.u32(*tail)?;self.u32(*head)?;}
                self.count(witness.groups.len())?;
                for g in &witness.groups{
                    self.u32(g.source)?;self.count(g.commodities.len())?;for (sink,demand) in &g.commodities{self.u32(*sink)?;self.q(demand)?;}
                    self.count(g.flows.len())?;for e in &g.flows{self.expr(e)?;}
                    self.count(g.nonnegative.len())?;for r in &g.nonnegative{self.fact_ref(r)?;}
                    self.count(g.balances.len())?;for r in &g.balances{self.fact_ref(r)?;}
                }
                self.block(body,depth+1)?;
            },
            End::Return { map, checks } => {
                self.tag(0)?; self.count(map.len())?; for e in map { self.expr(e)?; }
                self.count(checks.len())?; for r in checks { self.fact_ref(r)?; }
            },
            End::Split { expression, integer, left, right } => {
                self.tag(1)?; self.expr(expression)?;
                match integer { None => self.u8(0)?, Some(r) => { self.u8(1)?; self.fact_ref(r)?; } }
                self.block(left, depth + 1)?; self.block(right, depth + 1)?;
            },
            End::Absurd { fact } => { self.tag(2)?; self.fact_ref(fact)?; },
        } Ok(())
    }
    fn finish(mut self) -> Vec<u8> {
        let len = self.data.len() as u64; self.data[8..16].copy_from_slice(&len.to_le_bytes()); self.data
    }
}

struct Reader<'a> { bytes: &'a [u8], pos: usize, items: usize }
impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8], magic: &[u8; 4]) -> Result<Self, String> {
        if bytes.len() > MAX_FILE_BYTES { return Err(resource("file byte limit")); }
        let mut r = Self { bytes, pos: 0, items: 0 };
        if r.take(4)? != magic { return Err(invalid("magic")); }
        let version=r.u16()?;
        if version != if magic==b"RPX\0" {RPX_VERSION} else {1} { return Err(invalid("unsupported version")); }
        if r.u16()? != 0 { return Err(invalid("header reserved flags")); }
        if r.u64()? != bytes.len() as u64 { return Err(invalid("file length")); } Ok(r)
    }
    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        let end = self.pos.checked_add(n).ok_or_else(|| invalid("offset overflow"))?;
        let b = self.bytes.get(self.pos..end).ok_or_else(|| invalid("truncated payload"))?;
        self.pos = end; Ok(b)
    }
    fn u8(&mut self) -> Result<u8, String> { Ok(self.take(1)?[0]) }
    fn u16(&mut self) -> Result<u16, String> { Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap())) }
    fn u32(&mut self) -> Result<u32, String> { Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap())) }
    fn u64(&mut self) -> Result<u64, String> { Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap())) }
    fn count(&mut self, min_bytes: usize) -> Result<usize, String> {
        let n = usize::try_from(self.u32()?).map_err(|_| resource("count width"))?;
        self.items = self.items.checked_add(n).ok_or_else(|| resource("item count overflow"))?;
        if n > MAX_ITEMS || self.items > MAX_TOTAL_ITEMS { return Err(resource("item count limit")); }
        if n > (self.bytes.len() - self.pos) / min_bytes.max(1) { return Err(invalid("count exceeds available payload")); }
        Ok(n)
    }
    fn name(&mut self) -> Result<String, String> {
        let n = self.u32()? as usize;
        if n > MAX_NAME_BYTES { return Err(resource("name byte limit")); }
        let bytes = self.take(n)?;
        let s = std::str::from_utf8(bytes).map_err(|_| invalid("name is not UTF-8"))?;
        let mut out = String::new(); out.try_reserve(n).map_err(|_| resource("allocation"))?;
        out.push_str(s); Ok(out)
    }
    fn tag(&mut self) -> Result<u8, String> {
        let tag = self.u8()?;
        if self.u8()? != 0 || self.u16()? != 0 { return Err(invalid("record reserved flags")); } Ok(tag)
    }
    fn q(&mut self) -> Result<Q, String> {
        let sign = self.tag()?;
        if sign > 1 { return Err(invalid("rational sign")); }
        let nlen = self.u32()? as usize; let dlen = self.u32()? as usize;
        if nlen > MAX_INTEGER_BYTES || dlen > MAX_INTEGER_BYTES { return Err(resource("rational magnitude limit")); }
        if dlen == 0 { return Err(invalid("zero denominator length")); }
        let n = self.take(nlen)?; let d = self.take(dlen)?;
        if (nlen > 0 && n.last() == Some(&0)) || d.last() == Some(&0) { return Err(invalid("nonminimal magnitude")); }
        if nlen == 0 && (sign != 0 || d != [1]) { return Err(invalid("noncanonical zero")); }
        let numerator = BigInt::from_bytes_le(if sign == 1 { Sign::Minus } else { Sign::Plus }, n);
        let denominator = BigInt::from_bytes_le(Sign::Plus, d);
        if denominator.is_zero() { return Err(invalid("zero denominator")); }
        let q = Q::new(numerator.clone(), denominator.clone());
        if q.numer() != &numerator || q.denom() != &denominator { return Err(invalid("unreduced rational")); }
        Ok(q)
    }
    fn option_q(&mut self) -> Result<Option<Q>, String> {
        match self.u8()? { 0 => Ok(None), 1 => Ok(Some(self.q()?)), _ => Err(invalid("optional rational tag")) }
    }
    fn expr(&mut self) -> Result<Expr, String> {
        let constant = self.q()?; let n = self.count(17)?; let mut terms = reserve(n)?;
        for _ in 0..n { terms.push((self.u32()?, self.q()?)); }
        let e = Expr { constant, terms }; validate_expr(&e)?; Ok(e)
    }
    fn fact_ref(&mut self) -> Result<Ref, String> {
        let tag = self.tag()?; if tag == 8 { return Ok(Ref::Exact); }
        if tag > 8 { return Err(invalid("unknown fact reference tag")); }
        let id = self.u32()?;
        Ok(match tag { 0 => Ref::VarLower(id), 1 => Ref::VarUpper(id), 2 => Ref::VarInt(id),
            3 => Ref::RowLower(id), 4 => Ref::RowUpper(id), 5 => Ref::RowEq(id),
            6 => Ref::Local(id), 7 => Ref::Assumption(id), _ => unreachable!() })
    }
    fn steps(&mut self,depth:usize)->Result<Vec<Step>,String>{
        if depth > MAX_DEPTH { return Err(resource("block depth limit")); }
        let n = self.count(8)?; let mut steps = reserve(n)?;
        for _ in 0..n {
            steps.push(match self.tag()? {
                0 => {
                    let id = self.u32()?;
                    let kind = match self.tag()? { 0 => Kind::Le, 1 => Kind::Eq, 2 => Kind::Int, _ => return Err(invalid("fact kind")) };
                    let constant = self.q()?; let n = self.count(17)?; let mut terms = reserve(n)?;
                    for _ in 0..n { terms.push((self.fact_ref()?, self.q()?)); }
                    Step::Lin { id, kind, constant, terms }
                },
                1 => Step::Round { id: self.u32()?, le: self.fact_ref()?, integer: self.fact_ref()? },
                2 => { let n = self.count(4)?; let mut ids = reserve(n)?; for _ in 0..n { ids.push(self.u32()?); } Step::Drop { ids } },
                t @ (3|4)=>{
                    let id=self.u32()?;
                    if t==3{Step::EqPair{id,positive:self.fact_ref()?,negative:self.fact_ref()?}}
                    else{
                        let kind=match self.tag()?{0=>Kind::Le,1=>Kind::Eq,2=>Kind::Int,_=>return Err(invalid("fact kind"))};
                        let expression=self.expr()?;let split=self.expr()?;
                        let integer=match self.u8()?{0=>None,1=>Some(self.fact_ref()?),_=>return Err(invalid("optional reference tag"))};
                        let left=Box::new(self.derivation(depth+1)?);let right=Box::new(self.derivation(depth+1)?);
                        Step::Cases(Box::new(CasesStep{id,kind,expression,split,integer,left,right}))
                    }
                },
                5=>{
                    let id=self.u32()?;let bits=self.u32()?;let distance=self.u32()?;
                    let n=self.count(12)?;let mut variables=reserve(n)?;
                    for _ in 0..n{variables.push((self.u32()?,self.u64()?));}
                    let n=self.count(4)?;let mut cliques=reserve(n)?;
                    for _ in 0..n{cliques.push(self.fact_ref()?);}
                    Step::Plotkin{id,bits,distance,variables,cliques}
                },
                _ => return Err(invalid("unknown step tag")),
            });
        }
        Ok(steps)
    }
    fn derivation(&mut self,depth:usize)->Result<Derivation,String>{
        let steps=self.steps(depth)?;
        let end=match self.tag()?{0=>DerivationEnd::Witness(self.fact_ref()?),1=>DerivationEnd::Absurd(self.fact_ref()?),_=>return Err(invalid("unknown derivation terminal"))};
        Ok(Derivation{steps,end})
    }
    fn block(&mut self, depth: usize) -> Result<Block, String> {
        let steps=self.steps(depth)?;
        let end = match self.tag()? {
            0 => {
                let n = self.count(17)?; let mut map = reserve(n)?; for _ in 0..n { map.push(self.expr()?); }
                let n = self.count(4)?; let mut checks = reserve(n)?; for _ in 0..n { checks.push(self.fact_ref()?); }
                End::Return { map, checks }
            },
            1 => {
                let expression = self.expr()?;
                let integer = match self.u8()? { 0 => None, 1 => Some(self.fact_ref()?), _ => return Err(invalid("optional reference tag")) };
                let left = Box::new(self.block(depth + 1)?); let right = Box::new(self.block(depth + 1)?);
                End::Split { expression, integer, left, right }
            },
            2 => End::Absurd { fact: self.fact_ref()? },
            7=>{
                let nodes=self.u32()?;let n=self.count(8)?;let mut arcs=reserve(n)?;
                for _ in 0..n{arcs.push((self.u32()?,self.u32()?));}
                let n=self.count(20)?;let mut groups=reserve(n)?;
                for _ in 0..n{
                    let source=self.u32()?;let n=self.count(17)?;let mut demands=reserve(n)?;
                    for _ in 0..n{demands.push((self.u32()?,self.q()?));}
                    let n=self.count(17)?;let mut flows=reserve(n)?;for _ in 0..n{flows.push(self.expr()?);}
                    let n=self.count(4)?;let mut nonnegative=reserve(n)?;for _ in 0..n{nonnegative.push(self.fact_ref()?);}
                    let n=self.count(4)?;let mut balances=reserve(n)?;for _ in 0..n{balances.push(self.fact_ref()?);}
                    groups.push(SubflowGroup{source,demands,flows,nonnegative,balances});
                }
                let body=Box::new(self.block(depth+1)?);End::SubflowLift{witness:SubflowWitness{nodes,arcs,groups},body}
            },
            3=>{
                let nodes=self.u32()?;let n=self.count(8)?;let mut arcs=reserve(n)?;
                for _ in 0..n{arcs.push((self.u32()?,self.u32()?));}
                let n=self.count(20)?;let mut groups=reserve(n)?;
                for _ in 0..n{
                    let source=self.u32()?;let n=self.count(17)?;let mut commodities=reserve(n)?;
                    for _ in 0..n{commodities.push((self.u32()?,self.q()?));}
                    let n=self.count(17)?;let mut flows=reserve(n)?;for _ in 0..n{flows.push(self.expr()?);}
                    let n=self.count(4)?;let mut nonnegative=reserve(n)?;for _ in 0..n{nonnegative.push(self.fact_ref()?);}
                    let n=self.count(4)?;let mut balances=reserve(n)?;for _ in 0..n{balances.push(self.fact_ref()?);}
                    groups.push(FlowGroup{source,commodities,flows,nonnegative,balances});
                }
                let body=Box::new(self.block(depth+1)?);End::FlowLift{witness:FlowWitness{nodes,arcs,groups},body}
            },
            4=>{
                let n=self.count(12)?;let mut intervals=reserve(n)?;
                for _ in 0..n{
                    let n=self.count(17)?;let mut lower=reserve(n)?;for _ in 0..n{lower.push(self.expr()?);}
                    let n=self.count(17)?;let mut upper=reserve(n)?;for _ in 0..n{upper.push(self.expr()?);}
                    let n=self.count(4)?;let mut checks=reserve(n)?;for _ in 0..n{checks.push(self.fact_ref()?);}
                    intervals.push(IntervalWitness{lower,upper,checks});
                }
                let body=Box::new(self.block(depth+1)?);End::IntervalLift{intervals,body}
            },
            5=>{
                let n=self.count(42)?;let mut menus=reserve(n)?;
                for _ in 0..n{let maximum_index=self.u32()?;let activation=self.expr()?;let index=self.expr()?;let n=self.count(4)?;let mut checks=reserve(n)?;for _ in 0..n{checks.push(self.fact_ref()?);}menus.push(MenuWitness{maximum_index,activation,index,checks});}
                End::MenuLift{menus,body:Box::new(self.block(depth+1)?)}
            },
            6=>{
                let n=self.count(51)?;let mut decompositions=reserve(n)?;
                for _ in 0..n{let capacity=self.q()?;let flow=self.expr()?;let activation=self.expr()?;let n=self.count(4)?;let mut checks=reserve(n)?;for _ in 0..n{checks.push(self.fact_ref()?);}decompositions.push(SignedWitness{capacity,flow,activation,checks});}
                End::SignedLift{decompositions,body:Box::new(self.block(depth+1)?)}
            },
            _ => return Err(invalid("unknown terminal tag")),
        }; Ok(Block { steps, end })
    }
    fn finish(self) -> Result<(), String> { if self.pos == self.bytes.len() { Ok(()) } else { Err(invalid("trailing bytes")) } }
}

fn reserve<T>(n: usize) -> Result<Vec<T>, String> {
    let mut v = Vec::new(); v.try_reserve(n).map_err(|_| resource("allocation"))?; Ok(v)
}
fn validate_expr(e: &Expr) -> Result<(), String> {
    let mut prev = None;
    for (id, q) in &e.terms {
        if prev.is_some_and(|p| p >= *id) || q.is_zero() { return Err(invalid("noncanonical expression terms")); }
        prev = Some(*id);
    } Ok(())
}

pub fn encode_model(model: &Model) -> Result<Vec<u8>, String> {
    model.validate().map_err(normalize_error)?;
    let mut w = Writer::new(b"MCM\0")?; w.name(&model.name)?; w.count(model.vars.len())?;
    for v in &model.vars {
        w.name(&v.name)?; w.tag(u8::from(v.integer))?; w.option_q(&v.lower)?; w.option_q(&v.upper)?;
    }
    w.count(model.rows.len())?;
    for r in &model.rows { w.name(&r.name)?; w.expr(&r.expr)?; w.option_q(&r.lower)?; w.option_q(&r.upper)?; }
    w.expr(&model.objective)?; Ok(w.finish())
}
pub fn decode_model(bytes: &[u8]) -> Result<Model, String> {
    let mut r = Reader::new(bytes, b"MCM\0")?; let name = r.name()?;
    let n = r.count(10)?; let mut vars = reserve(n)?;
    for _ in 0..n {
        let name = r.name()?; let integer = match r.tag()? { 0 => false, 1 => true, _ => return Err(invalid("variable domain tag")) };
        vars.push(Var { name, integer, lower: r.option_q()?, upper: r.option_q()? });
    }
    let n = r.count(23)?; let mut rows = reserve(n)?;
    for _ in 0..n { rows.push(Row { name: r.name()?, expr: r.expr()?, lower: r.option_q()?, upper: r.option_q()? }); }
    let model = Model { name, vars, rows, objective: r.expr()? }; r.finish()?;
    model.validate().map_err(normalize_error)?; Ok(model)
}
pub const RPX_VERSION:u16=11;
pub fn encode_certificate(c:&Certificate)->Result<Vec<u8>,String>{
    let mut w=Writer::new_version(b"RPX\0",RPX_VERSION)?;
    w.block(&c.forward,1)?;w.block(&c.reverse,1)?;Ok(w.finish())
}
pub fn decode_certificate(bytes:&[u8])->Result<Certificate,String>{
    let mut r=Reader::new(bytes,b"RPX\0")?;
    let certificate=Certificate{forward:r.block(1)?,reverse:r.block(1)?};
    r.finish()?;Ok(certificate)
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_traits::One;
    fn q(n: i64, d: i64) -> Q { Q::new(n.into(), d.into()) }
    fn expr(n: i64) -> Expr { Expr { constant: q(n, 1), terms: Vec::new() } }
    fn certificate() -> Certificate {
        let block=Block { steps: vec![Step::Lin { id: 3, kind: Kind::Le, constant: q(-1, 3), terms: vec![(Ref::VarLower(0), q(1, 2))] }, Step::Round { id: 4, le: Ref::Local(3), integer: Ref::VarInt(0) }, Step::Drop { ids: vec![3] }], end: End::Split { expression: expr(0), integer: Some(Ref::VarInt(0)), left: Box::new(Block { steps: vec![], end: End::Return { map: vec![expr(0)], checks: vec![Ref::Exact] } }), right: Box::new(Block { steps: vec![], end: End::Absurd { fact: Ref::Assumption(0) } }) } };
        Certificate{forward:block.clone(),reverse:block}
    }
    #[test] fn all_proof_variants_roundtrip() {
        let c = certificate(); let bytes = encode_certificate(&c).unwrap(); assert_eq!(decode_certificate(&bytes).unwrap(), c);
        for n in 0..bytes.len() {
            assert!(decode_certificate(&bytes[..n]).is_err(), "truncation {n}");
            if n >= 16 { let mut truncated = bytes[..n].to_vec(); truncated[8..16].copy_from_slice(&(n as u64).to_le_bytes()); assert!(decode_certificate(&truncated).is_err(), "adjusted truncation {n}"); }
        }
        let mut extra = bytes.clone(); extra.push(0); let len = extra.len() as u64; extra[8..16].copy_from_slice(&len.to_le_bytes());
        assert!(decode_certificate(&extra).unwrap_err().contains("trailing"));
    }
    #[test] fn model_roundtrip() {
        let m = Model { name: "model".into(), vars: vec![Var { name: "x".into(), integer: true, lower: Some(q(-4, 3)), upper: None }], rows: vec![Row { name: "r".into(), expr: Expr { constant: q(0, 1), terms: vec![(0, q(-1, 2))] }, lower: None, upper: Some(q(3, 4)) }], objective: Expr { constant: q(-7, 1), terms: vec![(0, q(2, 5))] } };
        let bytes = encode_model(&m).unwrap(); assert_eq!(decode_model(&bytes).unwrap(), m);
        for n in 0..bytes.len() { assert!(decode_model(&bytes[..n]).is_err()); if n >= 16 { let mut truncated = bytes[..n].to_vec(); truncated[8..16].copy_from_slice(&(n as u64).to_le_bytes()); assert!(decode_model(&truncated).is_err()); } }
    }
    #[test] fn golden_two_blocks() {
        let b=Block{steps:vec![],end:End::Absurd{fact:Ref::Exact}};
        let c=Certificate{forward:b.clone(),reverse:b};
        let expected=[82,80,88,0,11,0,0,0,40,0,0,0,0,0,0,0,
            0,0,0,0,2,0,0,0,8,0,0,0,0,0,0,0,2,0,0,0,8,0,0,0];
        assert_eq!(encode_certificate(&c).unwrap(),expected);
        assert_eq!(decode_certificate(&expected).unwrap(),c);
        for version in 1..11 {let mut old=expected;old[4]=version;assert!(decode_certificate(&old).unwrap_err().contains("unsupported version"));}
    }
    #[test] fn scalar_vectors_and_canonical_failures() {
        let mut w = Writer::new(b"TEST").unwrap(); w.q(&q(-1, 2)).unwrap(); let b = w.finish();
        assert_eq!(&b[16..], &[1,0,0,0,1,0,0,0,1,0,0,0,1,2]);
        assert_eq!(Reader::new(&b, b"TEST").unwrap().q().unwrap(), q(-1,2));
        let mut unreduced = b.clone(); unreduced[28] = 2; unreduced[29] = 4;
        assert!(Reader::new(&unreduced, b"TEST").unwrap().q().unwrap_err().contains("unreduced"));
        let mut bad = b.clone(); bad[29] = 0; assert!(Reader::new(&bad, b"TEST").unwrap().q().is_err());
        let mut zero = Writer::new(b"TEST").unwrap(); zero.q(&Q::zero()).unwrap(); let mut zero = zero.finish(); zero[16] = 1;
        assert!(Reader::new(&zero, b"TEST").unwrap().q().unwrap_err().contains("noncanonical zero"));
    }
    #[test] fn count_unknown_tag_and_reserved_rejected() {
        let mut b=encode_certificate(&certificate()).unwrap();b[16..20].copy_from_slice(&u32::MAX.to_le_bytes());
        assert!(decode_certificate(&b).unwrap_err().starts_with("RESOURCE_LIMIT"));
        let block=Block{steps:vec![],end:End::Absurd{fact:Ref::Exact}};
        let c=Certificate{forward:block.clone(),reverse:block};
        for (offset,value) in [(20,255),(21,1),(32,8),(32,9),(33,1),(7,1)] {
            let mut b=encode_certificate(&c).unwrap();b[offset]=value;assert!(decode_certificate(&b).is_err());
        }
    }
    #[test] fn noncanonical_expression_rejected() {
        let c = certificate(); assert!(encode_certificate(&c).is_ok());
        assert!(validate_expr(&Expr { constant: Q::zero(), terms: vec![(0, Q::one()), (0, Q::one())] }).is_err());
        assert!(validate_expr(&Expr { constant: Q::zero(), terms: vec![(0, Q::zero())] }).is_err());
        let mut w = Writer::new(b"TEST").unwrap();
        assert!(w.q(&Q::new_raw(2.into(), 4.into())).is_err());
    }
    #[test] fn nested_unknown_tags_and_depth_budget() {
        let c = certificate(); let mut b = encode_certificate(&c).unwrap();
        // Last record is the right child's assumption reference. Decoding must
        // visit it even though a semantic checker may close the other branch.
        let last = b.len() - 8; b[last] = 255;
        assert!(decode_certificate(&b).unwrap_err().contains("unknown fact reference"));
        fn leaf() -> Block { Block { steps: vec![], end: End::Return { map: vec![], checks: vec![] } } }
        let mut b = leaf();
        for _ in 0..MAX_DEPTH { b = Block { steps: vec![], end: End::Split { expression: expr(0), integer: None, left: Box::new(b), right: Box::new(leaf()) } }; }
        let c = Certificate{forward:b,reverse:leaf()};
        assert!(encode_certificate(&c).unwrap_err().starts_with("RESOURCE_LIMIT:"));
        // Hand-construct nested bytes independently of Writer::block, whose
        // encoder budget must not prevent exercising the decoder's own guard.
        let mut w = Writer::new_version(b"RPX\0",11).unwrap();
        for _ in 0..MAX_DEPTH { w.count(0).unwrap(); w.tag(1).unwrap(); w.expr(&expr(0)).unwrap(); w.u8(0).unwrap(); }
        for _ in 0..=MAX_DEPTH { w.count(0).unwrap(); w.tag(0).unwrap(); w.count(0).unwrap(); w.count(0).unwrap(); }
        assert!(decode_certificate(&w.finish()).unwrap_err().contains("block depth limit"));
    }
    #[test] fn deterministic_byte_mutations_are_total_and_canonical() {
        let source = encode_certificate(&certificate()).unwrap();
        for i in 0..source.len() {
            for v in [0, 1, 127, 128, 254, 255] {
                let mut b = source.clone(); b[i] = v;
                if let Ok(decoded) = decode_certificate(&b) {
                    // Valid mutations are allowed; every accepted syntax has
                    // exactly the same canonical byte encoding on round-trip.
                    assert_eq!(encode_certificate(&decoded).unwrap(), b);
                }
            }
        }
        let mut state = 0x726f757465_u64;
        for iteration in 0..2048usize {
            let len = 16 + iteration % 257;
            let mut b = vec![0u8; len];
            for byte in &mut b { state ^= state << 13; state ^= state >> 7; state ^= state << 17; *byte = state as u8; }
            b[0..4].copy_from_slice(b"RPX\0"); b[4..8].copy_from_slice(&[11,0,0,0]); b[8..16].copy_from_slice(&(len as u64).to_le_bytes());
            let _ = decode_certificate(&b);
        }
    }
}
