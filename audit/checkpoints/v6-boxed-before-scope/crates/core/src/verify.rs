//! Exact checking, with all obligations generated from the actual output model.
use crate::model::{Expr, Model, Q, check_q};
use crate::proof::*;
use num_integer::Integer;
use num_traits::{One, Zero, Signed};
use serde::Serialize;
use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Fact { kind: Kind, expr: Expr }
#[derive(Clone, Debug)]
pub struct Limits { pub work: u64, pub live_facts: usize, pub depth: usize }
impl Default for Limits { fn default()->Self { Self { work: 100_000_000, live_facts: 1_000_000, depth:64 } } }
#[derive(Default, Debug, Serialize)]
pub struct Statistics {
    pub obligations: u64, pub linear_terms: u64, pub substitution_terms: u64,
    pub branches: u64, pub peak_live_facts: usize, pub work: u64,
    pub points:u64,pub point_coefficient_terms:u64,pub plotkin_pairs:u64,
    pub interval_lifts:u64,pub interval_generated_variables:u64,pub interval_generated_rows:u64,pub interval_generated_terms:u64,
    pub flow_lifts:u64,pub flow_generated_variables:u64,pub flow_generated_rows:u64,pub flow_generated_terms:u64,
}
// Accumulate a sum once, then sort once. Hashes choose buckets only; exact keys
// and BigRational equality decide all mathematical results.
struct Accumulator { constant: Q, terms: HashMap<u32,Q> }
impl Accumulator {
    fn new(constant:Q)->Self {Self{constant,terms:HashMap::new()}}
    fn add(&mut self,e:&Expr,c:&Q)->Result<(),String> {
        check_q(c)?;
        if c.is_zero(){return Ok(());}
        let constant_product=&e.constant*c;check_q(&constant_product)?;
        self.constant+=constant_product;check_q(&self.constant)?;
        if self.terms.len().checked_add(e.terms.len()).is_none_or(|n|n>crate::model::MAX_TERMS){return Err("RESOURCE_LIMIT accumulator terms".into());}
        self.terms.try_reserve(e.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator allocation")?;
        for (i,q) in &e.terms {
            let product=q*c;check_q(&product)?;
            let value=self.terms.entry(*i).or_insert_with(Q::zero);
            *value+=product;check_q(value)?;
            if value.is_zero(){self.terms.remove(i);}
        }Ok(())
    }
    fn finish(self)->Result<Expr,String>{
        check_q(&self.constant)?;
        let mut terms=Vec::new();terms.try_reserve(self.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator output")?;
        terms.extend(self.terms);terms.sort_unstable_by_key(|(i,_)|*i);
        Ok(Expr{constant:self.constant,terms})
    }
}
struct Context<'a> { refutation:bool, input: &'a Model, output: &'a Model, claim: &'a Claim, inverse: Option<&'a [Expr]>, limits: &'a Limits, stats: &'a mut Statistics }
impl Context<'_> {
    fn charge(&mut self,n:usize)->Result<(),String> {
        self.stats.work=self.stats.work.checked_add(n as u64).ok_or("RESOURCE_LIMIT work overflow")?;
        if self.stats.work>self.limits.work { return Err("RESOURCE_LIMIT proof work budget".into()); } Ok(())
    }
    fn get(&mut self,r:&Ref, live:&HashMap<u32,Fact>, assumptions:&[Fact])->Result<Fact,String> {
        let bad=||"INVALID fact reference or type".to_string();
        let f=match r {
            Ref::Local(i)=>live.get(i).cloned().ok_or_else(bad)?,
            Ref::Assumption(i)=>assumptions.get(*i as usize).cloned().ok_or_else(bad)?,
            Ref::VarLower(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; let mut e=Expr::var(*i).scaled(&(-Q::one()))?; e.constant=v.lower.clone().ok_or_else(bad)?; Fact{kind:Kind::Le,expr:e} },
            Ref::VarUpper(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; let mut e=Expr::var(*i); e.constant=-v.upper.clone().ok_or_else(bad)?; Fact{kind:Kind::Le,expr:e} },
            Ref::VarInt(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; if !v.integer || !self.claim.input_integers {return Err(bad());} Fact{kind:Kind::Int,expr:Expr::var(*i)} },
            Ref::RowLower(i)=>{let row=self.input.rows.get(*i as usize).ok_or_else(bad)?;let mut e=row.expr.scaled(&(-Q::one()))?;e.constant+=row.lower.clone().ok_or_else(bad)?;Fact{kind:Kind::Le,expr:e}},
            Ref::RowUpper(i)=>{let row=self.input.rows.get(*i as usize).ok_or_else(bad)?;let mut e=row.expr.clone();e.constant-=row.upper.clone().ok_or_else(bad)?;Fact{kind:Kind::Le,expr:e}},
            Ref::RowEq(i)=>{let row=self.input.rows.get(*i as usize).ok_or_else(bad)?;let b=row.lower.clone().ok_or_else(bad)?;if row.upper.as_ref()!=Some(&b){return Err(bad());}let mut e=row.expr.clone();e.constant-=b;Fact{kind:Kind::Eq,expr:e}},
            Ref::Exact=>return Err("INVALID exact is only a terminal obligation witness".into()),
        }; f.expr.validate(self.input.vars.len())?; self.charge(f.expr.terms.len()+1)?; Ok(f)
    }
    fn substitute(&mut self,e:&Expr,map:&[Expr])->Result<Expr,String> {
        let mut result=Accumulator::new(e.constant.clone());
        for (i,c) in &e.terms {
            let m=map.get(*i as usize).ok_or("INVALID incomplete mapping")?;
            self.charge(m.terms.len()+1)?;
            self.stats.substitution_terms+=m.terms.len() as u64;
            result.add(m,c)?;
        } result.finish()
    }

    fn obligation(&mut self,kind:Kind,e:Expr,r:&Ref,live:&HashMap<u32,Fact>,assumptions:&[Fact])->Result<(),String> {
        self.stats.obligations+=1;
        self.check_fact(kind,e,r,live,assumptions)
    }
    fn check_fact(&mut self,kind:Kind,e:Expr,r:&Ref,live:&HashMap<u32,Fact>,assumptions:&[Fact])->Result<(),String> {
        e.validate(self.input.vars.len())?;self.charge(e.terms.len()+1)?;
        if *r==Ref::Exact {
            let valid=match kind {
                Kind::Eq=>e.terms.is_empty() && e.constant.is_zero(),
                Kind::Le=>e.terms.is_empty() && !e.constant.is_positive(),
                Kind::Int=>e.constant.is_integer() && e.terms.iter().all(|(i,c)| c.is_integer() && self.claim.input_integers && self.input.vars[*i as usize].integer),
            }; if valid {return Ok(());} return Err("INVALID non-tautological exact obligation".into());
        }
        let f=self.get(r,live,assumptions)?;
        if (f.kind==kind || f.kind==Kind::Eq) && f.expr==e {Ok(())} else {Err(format!("INVALID obligation mismatch: expected {kind:?}"))}
    }
    fn plotkin(&mut self,bits:u32,distance:u32,variables:&[(u32,u64)],cliques:&[Ref],live:&HashMap<u32,Fact>,assumptions:&[Fact])->Result<Fact,String>{
        if !(1..=64).contains(&bits)||!(1..=64).contains(&distance)||2*distance<=bits{
            return Err("INVALID Plotkin parameters".into());
        }
        if !self.claim.input_integers{return Err("INVALID Plotkin requires integer input domain".into());}
        let n=variables.len();
        self.charge(n)?;
        let pairs=n.checked_mul(n.saturating_sub(1)).and_then(|v|v.checked_div(2)).ok_or("RESOURCE_LIMIT Plotkin pair count")?;
        self.charge(pairs)?;self.stats.plotkin_pairs+=pairs as u64;
        let words=cliques.len().checked_add(63).ok_or("RESOURCE_LIMIT Plotkin clique count")?/64;
        let cells=n.checked_mul(words).ok_or("RESOURCE_LIMIT Plotkin membership size")?;
        if cells>8_000_000{return Err("RESOURCE_LIMIT Plotkin membership words".into());}
        self.charge(cells)?;
        let mut membership=Vec::new();membership.try_reserve_exact(cells).map_err(|_|"RESOURCE_LIMIT Plotkin allocation")?;membership.resize(cells,0u64);
        let mut index=HashMap::new();index.try_reserve(n).map_err(|_|"RESOURCE_LIMIT Plotkin index allocation")?;
        for (j,(i,label)) in variables.iter().enumerate(){
            let v=self.input.vars.get(*i as usize).ok_or("INVALID Plotkin variable")?;
            if !v.integer||v.lower.as_ref().is_none_or(|q|q.is_negative())||v.upper.as_ref().is_none_or(|q|q>&Q::one()){
                return Err("INVALID Plotkin binary domain".into());
            }
            if (bits<64 && *label>>bits!=0)||index.insert(*i,j).is_some(){return Err("INVALID Plotkin label or repeated variable".into());}
        }
        for (r,reference) in cliques.iter().enumerate(){
            let fact=self.get(reference,live,assumptions)?;
            if fact.kind!=Kind::Le||fact.expr.constant!= -Q::one(){return Err("INVALID Plotkin clique constant or kind".into());}
            self.charge(fact.expr.terms.len()+1)?;
            for (i,coefficient) in &fact.expr.terms{
                if coefficient!=&Q::one()||self.input.vars[*i as usize].lower.as_ref().is_none_or(|q|q.is_negative()){
                    return Err("INVALID Plotkin clique coefficient or nonnegative domain".into());
                }
                if let Some(j)=index.get(i){membership[*j*words+r/64]|=1u64<<(r%64);}
            }
        }
        for i in 0..n{for j in i+1..n{
            if (variables[i].1^variables[j].1).count_ones()<distance{
                let mut covered=false;
                for w in 0..words{self.charge(1)?;if membership[i*words+w]&membership[j*words+w]!=0{covered=true;break;}}
                if !covered{return Err("INVALID Plotkin close pair lacks checked clique".into());}
            }
        }}
        let bound=2*distance/(2*distance-bits);
        let mut terms=Vec::new();terms.try_reserve(n).map_err(|_|"RESOURCE_LIMIT Plotkin fact allocation")?;
        terms.extend(variables.iter().map(|(i,_)|(*i,Q::one())));terms.sort_unstable_by_key(|(i,_)|*i);
        Ok(Fact{kind:Kind::Le,expr:Expr{constant:-Q::from_integer(bound.into()),terms}})
    }
    fn steps(&mut self,steps:&[Step],live:&mut HashMap<u32,Fact>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String> {
        if depth>self.limits.depth {return Err("RESOURCE_LIMIT branch depth".into());}
        for step in steps {
            self.charge(1)?;
            let (id,f)=match step {
                Step::Lin{id,kind,constant,terms}=>{
                    check_q(constant)?;
                    let allowed=match kind {Kind::Le=>!constant.is_positive(),Kind::Eq=>constant.is_zero(),Kind::Int=>constant.is_integer()};
                    if !allowed{return Err("INVALID linear constant".into());}
                    let mut e=Accumulator::new(constant.clone());
                    for (r,c) in terms {
                        check_q(c)?;
                        let f=self.get(r,&live,assumptions)?;
                        let allowed=match kind {Kind::Le=>f.kind==Kind::Eq || (f.kind==Kind::Le && !c.is_negative()),Kind::Eq=>f.kind==Kind::Eq,Kind::Int=>f.kind==Kind::Eq || (f.kind==Kind::Int && c.is_integer())};
                        if !allowed {return Err("INVALID linear premise kind or multiplier".into());}
                        self.charge(f.expr.terms.len()+1)?;
                        self.stats.linear_terms+=f.expr.terms.len() as u64;
                        e.add(&f.expr,c)?;
                    }
                    (*id,Fact{kind:*kind,expr:e.finish()?})
                },
                Step::Plotkin{id,bits,distance,variables,cliques}=>(*id,self.plotkin(*bits,*distance,variables,cliques,live,assumptions)?),
                Step::Round{id,le,integer}=>{
                    let a=self.get(le,&live,assumptions)?;let z=self.get(integer,&live,assumptions)?;
                    if a.kind!=Kind::Le || z.kind!=Kind::Int || a.expr.terms!=z.expr.terms {return Err("INVALID rounding premises".into());}
                    let d=&a.expr.constant-&z.expr.constant;
                    check_q(&d)?;
                    let ceil=d.numer().div_ceil(d.denom());
                    let mut e=z.expr;e.constant+=Q::from_integer(ceil);
                    (*id,Fact{kind:Kind::Le,expr:e})
                },
                Step::Drop{ids}=>{self.charge(ids.len())?;for id in ids {if live.remove(id).is_none(){return Err("INVALID drop of absent fact".into());}}continue},
                Step::EqPair{id,positive,negative}=>{
                    let a=self.get(positive,live,assumptions)?;let b=self.get(negative,live,assumptions)?;
                    if a.kind!=Kind::Le || b.kind!=Kind::Le || a.expr.scaled(&(-Q::one()))?!=b.expr {return Err("INVALID equality pair".into());}
                    (*id,Fact{kind:Kind::Eq,expr:a.expr})
                },
                Step::Cases(case)=>{let CasesStep{id,kind,expression,split,integer,left,right}=case.as_ref();
                    expression.validate(self.input.vars.len())?;
                    if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                    self.charge(expression.terms.len()+split.terms.len()+1)?;
                    let (a,b)=self.split_facts(split,integer,live,assumptions)?;
                    self.charge(live.values().map(|f|f.expr.terms.len()+1).sum())?;
                    self.stats.branches+=1;
                    assumptions.push(a);
                    self.derivation(left,*kind,expression,live.clone(),assumptions,depth+1)?;assumptions.pop();
                    self.charge(live.values().map(|f|f.expr.terms.len()+1).sum())?;
                    assumptions.push(b);
                    self.derivation(right,*kind,expression,live.clone(),assumptions,depth+1)?;assumptions.pop();
                    (*id,Fact{kind:*kind,expr:expression.clone()})
                },
            };
            f.expr.validate(self.input.vars.len())?;
            if live.contains_key(&id) {return Err("INVALID live fact register overwritten".into());}
            if live.len()>=self.limits.live_facts {return Err("RESOURCE_LIMIT live facts".into());}
            live.try_reserve(1).map_err(|_|"RESOURCE_LIMIT fact allocation")?; live.insert(id,f);
            self.stats.peak_live_facts=self.stats.peak_live_facts.max(live.len());
        }
        Ok(())
    }
    fn split_facts(&mut self,expression:&Expr,integer:&Option<Ref>,live:&HashMap<u32,Fact>,assumptions:&[Fact])->Result<(Fact,Fact),String>{
        expression.validate(self.input.vars.len())?;
        if let Some(r)=integer {let f=self.get(r,live,assumptions)?;if f.kind!=Kind::Int || f.expr!=*expression{return Err("INVALID integer split witness".into());}}
        let mut e=expression.scaled(&(-Q::one()))?;if integer.is_some(){e.constant+=Q::one();}e.validate(self.input.vars.len())?;
        Ok((Fact{kind:Kind::Le,expr:expression.clone()},Fact{kind:Kind::Le,expr:e}))
    }
    fn absurd(&mut self,r:&Ref,live:&HashMap<u32,Fact>,assumptions:&[Fact])->Result<(),String>{
        let f=self.get(r,live,assumptions)?;
        if f.expr.terms.is_empty() && ((f.kind==Kind::Le && f.expr.constant.is_positive()) || (f.kind==Kind::Eq && !f.expr.constant.is_zero())) {Ok(())} else {Err("INVALID contradiction witness".into())}
    }
    fn derivation(&mut self,d:&Derivation,kind:Kind,expression:&Expr,mut live:HashMap<u32,Fact>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String>{
        self.steps(&d.steps,&mut live,assumptions,depth)?;
        match &d.end {
            DerivationEnd::Witness(r)=>self.check_fact(kind,expression.clone(),r,&live,assumptions),
            DerivationEnd::Absurd(r)=>self.absurd(r,&live,assumptions),
        }
    }
    fn run(&mut self,block:&Block,mut live:HashMap<u32,Fact>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String> {
        if self.refutation && !matches!(block.end,End::Absurd{..}|End::Split{..}){return Err("INVALID refutation requires only Absurd/Split endpoints".into());}
        self.steps(&block.steps,&mut live,assumptions,depth)?;
        match &block.end {
            End::IntervalLift{intervals,body}=>{
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=Limits{work:self.limits.work.checked_sub(self.stats.work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:self.limits.live_facts,depth:self.limits.depth};
                let extension=crate::interval::prepare_unchecked_extension(self.input,intervals,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT interval work width")?)?;
                for premise in extension.premises{
                    self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;
                }
                self.stats.interval_lifts+=1;
                self.stats.interval_generated_variables=self.stats.interval_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT interval variable counter")?;
                self.stats.interval_generated_rows=self.stats.interval_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT interval row counter")?;
                self.stats.interval_generated_terms=self.stats.interval_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT interval term counter")?;
                Context{refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,limits:self.limits,stats:self.stats}.run(body,live,assumptions,depth+1)
            },
            End::FlowLift{witness,body}=>{
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=Limits{work:self.limits.work.checked_sub(self.stats.work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:self.limits.live_facts,depth:self.limits.depth};
                let extension=crate::flow::prepare_unchecked_extension(self.input,witness,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT flow work width")?)?;
                // The model builder is deliberately not a proof authority. Every
                // premise is checked in the OLD scope before any new row is usable.
                for premise in extension.premises{
                    self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;
                }
                self.stats.flow_lifts+=1;
                self.stats.flow_generated_variables=self.stats.flow_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT flow variable counter")?;
                self.stats.flow_generated_rows=self.stats.flow_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT flow row counter")?;
                self.stats.flow_generated_terms=self.stats.flow_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT flow term counter")?;
                Context{refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,limits:self.limits,stats:self.stats}.run(body,live,assumptions,depth+1)
            },
            End::Absurd{fact}=>self.absurd(fact,&live,assumptions),
            End::Split{expression,integer,left,right}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let (a,b)=self.split_facts(expression,integer,&live,assumptions)?;
                self.charge(live.values().map(|f|f.expr.terms.len()+1).sum())?;
                self.stats.branches+=1;
                assumptions.push(a);
                self.run(left,live.clone(),assumptions,depth+1)?;assumptions.pop();
                assumptions.push(b);
                self.run(right,live,assumptions,depth+1)?;assumptions.pop();Ok(())
            },
            End::Return{map,checks}=>{
                if map.len()!=self.output.vars.len(){return Err("INVALID incomplete mapping".into());}
                for e in map {e.validate(self.input.vars.len())?;self.charge(e.terms.len()+1)?;}
                let mut k=0;
                macro_rules! check {($kind:expr,$e:expr)=>{{let e=$e;let r=checks.get(k).ok_or("INVALID missing obligation")?;self.obligation($kind,e,r,&live,assumptions).map_err(|err|format!("{err}; obligation {k}"))?;k+=1;}}}
                for (i,v) in self.output.vars.iter().enumerate() {
                    if let Some(b)=&v.lower {let mut e=map[i].scaled(&(-Q::one()))?;e.constant+=b;check!(Kind::Le,e);}
                    if let Some(b)=&v.upper {let mut e=map[i].clone();e.constant-=b;check!(Kind::Le,e);}
                    if v.integer && self.claim.output_integers {check!(Kind::Int,map[i].clone());}
                }
                for row in &self.output.rows {
                    let e=self.substitute(&row.expr,map)?;
                    if let Some(b)=&row.lower {if row.upper.as_ref()==Some(b){let mut eq=e;eq.constant-=b;check!(Kind::Eq,eq);continue;}}
                    if let Some(b)=&row.lower {let mut lo=e.scaled(&(-Q::one()))?;lo.constant+=b;check!(Kind::Le,lo);}
                    if let Some(b)=&row.upper {let mut hi=e;hi.constant-=b;check!(Kind::Le,hi);}
                }
                if self.claim.objective!=Objective::None {let mut e=self.substitute(&self.output.objective,map)?;e.add_scaled(&self.input.objective,&(-Q::one()))?;check!(if self.claim.objective==Objective::Equal{Kind::Eq}else{Kind::Le},e);}
                for (i,o) in &self.claim.projection {let mut e=map[*o as usize].clone();e.add_scaled(&Expr::var(*i),&(-Q::one()))?;check!(Kind::Eq,e);}
                for (input_expr,output_expr) in &self.claim.affine_projection{let mut e=self.substitute(output_expr,map)?;e.add_scaled(input_expr,&(-Q::one()))?;check!(Kind::Eq,e);}
                if let Some(inverse)=self.inverse {for (i,back) in inverse.iter().enumerate(){let mut e=self.substitute(back,map)?;e.add_scaled(&Expr::var(i as u32),&(-Q::one()))?;check!(Kind::Eq,e);}}
                if let Some(lower)=&self.claim.input_objective_lower{let mut e=self.input.objective.scaled(&(-Q::one()))?;e.constant+=lower;check!(Kind::Le,e);}
                if k!=checks.len(){return Err("INVALID surplus obligation witnesses".into());}Ok(())
            }
        }
    }
}

/// Requested claims are supplied by the caller, never weakened by certificate declarations.
/// The entire input/output models are validated and used for every proof obligation.
pub fn verify(source:&Model,target:&Model,cert:&Certificate,requested:&[Claim],limits:&Limits)->Result<Statistics,String> {
    if requested.is_empty()||!cert.points.is_empty(){return Err("INVALID requested contract mismatch".into());}
    verify_claims(source,target,cert,requested,limits)
}

/// All directional claims are proved before any point strictness witness is used.
pub fn verify_request(source:&Model,target:&Model,cert:&Certificate,requested:&Request,limits:&Limits)->Result<Statistics,String>{
    if requested.claims.is_empty()&&requested.points.is_empty(){return Err("INVALID empty request".into());}
    if cert.points.len()!=requested.points.len()||cert.points.iter().zip(&requested.points).any(|(p,r)|p.claim!=*r){return Err("INVALID requested point contract mismatch".into());}
    let mut stats=verify_claims(source,target,cert,&requested.claims,limits)?;
    let remaining=Limits{work:limits.work.checked_sub(stats.work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:limits.live_facts,depth:limits.depth};
    let points=crate::point::verify_points(source,target,cert,requested,&remaining)?;
    stats.points=points.points;stats.point_coefficient_terms=points.coefficient_terms;
    stats.work=stats.work.checked_add(points.work).ok_or("RESOURCE_LIMIT work overflow")?;
    if stats.work>limits.work{return Err("RESOURCE_LIMIT proof work budget".into());}Ok(stats)
}
fn verify_claims(source:&Model,target:&Model,cert:&Certificate,requested:&[Claim],limits:&Limits)->Result<Statistics,String> {
    source.validate()?;target.validate()?;
    if cert.claims!=requested || cert.blocks.len()!=requested.len(){return Err("INVALID requested contract mismatch".into());}
    let mut stats=Statistics::default();
    for (claim,block) in requested.iter().zip(&cert.blocks) {
        if let Some(lower)=&claim.input_objective_lower{check_q(lower)?;}
        let (input,output)=if claim.reverse{(target,source)}else{(source,target)};
        for (i,o) in &claim.affine_projection{i.validate(input.vars.len())?;o.validate(output.vars.len())?;}
        let mut seen=std::collections::HashSet::new();
        for &(i,o) in &claim.projection {if i as usize>=input.vars.len() || o as usize>=output.vars.len() || !seen.insert((i,o)){return Err("INVALID projection coordinate".into());}}
        let inverse=if let Some(j)=claim.inverse {
            let other=requested.get(j as usize).ok_or("INVALID inverse claim reference")?;
            if other.reverse==claim.reverse || other.input_integers!=claim.output_integers || other.output_integers!=claim.input_integers {return Err("INVALID inverse claim direction/domain".into());}
            if !matches!(block.end,End::Return{..}) {return Err("INVALID inverse requires affine terminal maps".into());}
            let End::Return{map,..}=&cert.blocks[j as usize].end else{return Err("INVALID inverse requires affine terminal maps".into());};
            if map.len()!=input.vars.len(){return Err("INVALID inverse mapping dimension".into());}
            for e in map {e.validate(output.vars.len())?;}
            Some(map.as_slice())
        }else{None};
        Context{refutation:false,input,output,claim,inverse,limits,stats:&mut stats}.run(block,HashMap::new(),&mut Vec::new(),1)?;
    }Ok(stats)
}

/// Establish infeasibility of an actual LP model using only contradiction leaves.
/// This entry point has fresh fact/assumption state and never verifies a mapping.
pub fn verify_lp_refutation(model:&Model,block:&Block,limits:&Limits)->Result<Statistics,String>{
    model.validate()?;
    let claim=Claim{reverse:false,input_integers:false,output_integers:false,objective:Objective::None,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None};
    let mut stats=Statistics::default();
    Context{refutation:true,input:model,output:model,claim:&claim,inverse:None,limits,stats:&mut stats}.run(block,HashMap::new(),&mut Vec::new(),1)?;
    Ok(stats)
}
