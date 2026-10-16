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
/// Default work and live-fact budgets are resource policy, not semantics; depth remains format-coupled.
impl Default for Limits { fn default()->Self { Self { work: 1_000_000_000, live_facts: 1_000_000, depth:64 } } }
#[derive(Default, Debug, PartialEq, Eq, Serialize)]
pub struct Statistics {
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_lifts:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_variables:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_rows:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_terms:u64,
    pub plotkin_pairs:u64,
    pub obligations: u64, pub linear_terms: u64, pub substitution_terms: u64,
    pub branches: u64, pub peak_live_facts: usize, pub work: u64,
    pub interval_lifts:u64,pub interval_generated_variables:u64,pub interval_generated_rows:u64,pub interval_generated_terms:u64,
    pub signed_lifts:u64,pub signed_generated_variables:u64,pub signed_generated_rows:u64,pub signed_generated_terms:u64,
    pub menu_lifts:u64,pub menu_generated_variables:u64,pub menu_generated_rows:u64,pub menu_generated_terms:u64,
    pub flow_lifts:u64,pub flow_generated_variables:u64,pub flow_generated_rows:u64,pub flow_generated_terms:u64,
}
fn zero_counter(n:&u64)->bool{*n==0}
/// Best-effort diagnostics; never read to decide acceptance.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Location {
    #[serde(skip_serializing_if="Option::is_none")]
    pub direction: Option<&'static str>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub step: Option<u32>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub obligation: Option<u32>,
}
/// Caller-owned scratch space for [`Location`] reporting. `_with_diagnostics`
/// entry points write the fields they learn and leave the others untouched;
/// pass `Diagnostics::default()` for an isolated report.
#[derive(Clone, Debug, Default, Serialize)]
pub struct Diagnostics { pub location: Location }

/// Origin of a Return obligation. Indices are zero-based.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ObligationOrigin {
    pub kind: String,
    #[serde(skip_serializing_if="Option::is_none")]
    pub index: Option<u32>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub name: Option<String>,
}

/// One proposition the kernel will require at the terminal Return. This is
/// planning data only; the verifier checks its independently supplied witness.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ReturnObligation {
    pub kind: Kind,
    pub expression: Expr,
    pub origin: ObligationOrigin,
}

// Borrow model names on the verification path: planning metadata does not add
// allocation or work charges to ordinary verification.
struct ReturnOrigin<'a> {
    kind: &'static str, index: Option<usize>, name: Option<&'a str>,
}
impl<'a> ReturnOrigin<'a> {
    fn plain(kind: &'static str) -> Self { Self {kind,index:None,name:None} }
    fn indexed(kind: &'static str, index: usize, name: Option<&'a str>) -> Self {
        Self {kind,index:Some(index),name}
    }
    fn owned(self) -> ObligationOrigin {
        ObligationOrigin {kind:self.kind.into(),index:self.index.map(diagnostic_index),
            name:self.name.map(str::to_owned)}
    }
}

/// Diagnostic indices saturate rather than truncate; they never affect a decision.
pub(crate) fn diagnostic_index(i:usize)->u32{u32::try_from(i).unwrap_or(u32::MAX)}
// Accumulate a sum once, then sort once. Hashes choose buckets only; exact keys
// and BigRational equality decide all mathematical results.
struct Accumulator { constant: Q, terms: HashMap<u32,Q> }
impl Accumulator {
    fn new(constant:Q)->Self {Self{constant,terms:HashMap::new()}}
    fn add(&mut self,e:&Expr,c:&Q)->Result<(),String> {
        check_q(c)?;
        if c.is_zero(){return Ok(());}
        let one=c.is_one();
        let minus_one=c.denom().is_one() && c.numer().is_negative() && c.numer().magnitude().is_one();
        let product=|q:&Q| {if one {q.clone()}else if minus_one {-q}else{q*c}};
        let constant_product=product(&e.constant);check_q(&constant_product)?;
        if self.constant.is_zero(){self.constant=constant_product;}
        else if !constant_product.is_zero(){self.constant+=constant_product;}
        check_q(&self.constant)?;
        if self.terms.len().checked_add(e.terms.len()).is_none_or(|n|n>crate::model::MAX_TERMS){return Err("RESOURCE_LIMIT accumulator terms".into());}
        self.terms.try_reserve(e.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator allocation")?;
        for (i,q) in &e.terms {
            let product=product(q);check_q(&product)?;
            match self.terms.entry(*i) {
                std::collections::hash_map::Entry::Vacant(slot)=>{
                    // The result is exactly the checked product, with no sum.
                    if !product.is_zero(){slot.insert(product);}
                },
                std::collections::hash_map::Entry::Occupied(mut slot)=>{
                    *slot.get_mut()+=product;check_q(slot.get())?;
                    if slot.get().is_zero(){slot.remove();}
                },
            }
        }Ok(())
    }
    fn finish(self)->Result<Expr,String>{
        check_q(&self.constant)?;
        let mut terms=Vec::new();terms.try_reserve(self.terms.len()).map_err(|_|"RESOURCE_LIMIT accumulator output")?;
        terms.extend(self.terms);terms.sort_unstable_by_key(|(i,_)|*i);
        Ok(Expr{constant:self.constant,terms})
    }
}
// Each child borrows an immutable parent and stores only its own changes.
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
struct Context<'a> { input: &'a Model, output: &'a Model, limits: &'a Limits, stats: &'a mut Statistics, diag: &'a mut Diagnostics }
impl Context<'_> {
    fn charge(&mut self,n:usize)->Result<(),String> {
        self.stats.work=self.stats.work.checked_add(n as u64).ok_or("RESOURCE_LIMIT work overflow")?;
        if self.stats.work>self.limits.work { return Err("RESOURCE_LIMIT proof work budget".into()); } Ok(())
    }
    /// A fresh block or derivation owns the innermost step and obligation indices.
    fn begin_block(&mut self){self.diag.location.step=None;self.diag.location.obligation=None;}
    fn get(&mut self,r:&Ref, live:&Facts<'_>, assumptions:&[Fact])->Result<Fact,String> {
        let bad=||"INVALID fact reference or type".to_string();
        let f=match r {
            Ref::Local(i)=>{let (fact,probes)=live.lookup(i);self.charge(probes)?;fact.cloned().ok_or_else(bad)?},
            Ref::Assumption(i)=>assumptions.get(*i as usize).cloned().ok_or_else(bad)?,
            Ref::VarLower(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; let mut e=Expr::var(*i).scaled(&(-Q::one()))?; e.constant=v.lower.clone().ok_or_else(bad)?; Fact{kind:Kind::Le,expr:e} },
            Ref::VarUpper(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; let mut e=Expr::var(*i); e.constant=-v.upper.clone().ok_or_else(bad)?; Fact{kind:Kind::Le,expr:e} },
            Ref::VarInt(i)=>{ let v=self.input.vars.get(*i as usize).ok_or_else(bad)?; if !v.integer {return Err(bad());} Fact{kind:Kind::Int,expr:Expr::var(*i)} },
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

    /// Single shared ordering/formula walk for verification and authoring.
    /// The callback checks a witness immediately during verification, retaining
    /// the historical interleaving of substitution charges and fact checks.
    fn walk_return<F>(&mut self,map:&[Expr],mut emit:F)->Result<(),String>
    where F: FnMut(&mut Self,Kind,Expr,ReturnOrigin<'_>)->Result<(),String> {
        let output=self.output;
        let input=self.input;
        if map.len()!=output.vars.len(){return Err("INVALID incomplete mapping".into());}
        for e in map {e.validate(input.vars.len())?;self.charge(e.terms.len()+1)?;}
        for (i,v) in output.vars.iter().enumerate() {
            if let Some(b)=&v.lower {let mut e=map[i].scaled(&(-Q::one()))?;e.constant+=b;emit(self,Kind::Le,e,ReturnOrigin::indexed("variable.lower",i,Some(&v.name)))?;}
            if let Some(b)=&v.upper {let mut e=map[i].clone();e.constant-=b;emit(self,Kind::Le,e,ReturnOrigin::indexed("variable.upper",i,Some(&v.name)))?;}
            if v.integer {emit(self,Kind::Int,map[i].clone(),ReturnOrigin::indexed("variable.integer",i,Some(&v.name)))?;}
        }
        for (i,row) in output.rows.iter().enumerate() {
            let e=self.substitute(&row.expr,map)?;
            if let Some(b)=&row.lower {if row.upper.as_ref()==Some(b){let mut eq=e;eq.constant-=b;emit(self,Kind::Eq,eq,ReturnOrigin::indexed("row.equal",i,Some(&row.name)))?;continue;}}
            if let Some(b)=&row.lower {let mut lo=e.scaled(&(-Q::one()))?;lo.constant+=b;emit(self,Kind::Le,lo,ReturnOrigin::indexed("row.lower",i,Some(&row.name)))?;}
            if let Some(b)=&row.upper {let mut hi=e;hi.constant-=b;emit(self,Kind::Le,hi,ReturnOrigin::indexed("row.upper",i,Some(&row.name)))?;}
        }
        let mut e=self.substitute(&output.objective,map)?;
        e.add_scaled(&input.objective,&(-Q::one()))?;
        emit(self,Kind::Le,e,ReturnOrigin::plain("objective.non_increasing"))?;
        Ok(())
    }

    fn obligation(&mut self,kind:Kind,e:Expr,r:&Ref,live:&Facts<'_>,assumptions:&[Fact])->Result<(),String> {
        self.stats.obligations+=1;
        self.check_fact(kind,e,r,live,assumptions)
    }
    fn check_fact(&mut self,kind:Kind,e:Expr,r:&Ref,live:&Facts<'_>,assumptions:&[Fact])->Result<(),String> {
        e.validate(self.input.vars.len())?;self.charge(e.terms.len()+1)?;
        if *r==Ref::Exact {
            let valid=match kind {
                Kind::Eq=>e.terms.is_empty() && e.constant.is_zero(),
                Kind::Le=>e.terms.is_empty() && !e.constant.is_positive(),
                Kind::Int=>e.constant.is_integer() && e.terms.iter().all(|(i,c)| c.is_integer() && self.input.vars[*i as usize].integer),
            }; if valid {return Ok(());} return Err("INVALID non-tautological exact obligation".into());
        }
        let f=self.get(r,live,assumptions)?;
        if (f.kind==kind || f.kind==Kind::Eq) && f.expr==e {Ok(())} else {Err(format!("INVALID obligation mismatch: expected {kind:?}"))}
    }
    fn plotkin(&mut self,bits:u32,distance:u32,variables:&[(u32,u64)],cliques:&[Ref],live:&Facts<'_>,assumptions:&[Fact])->Result<Fact,String>{
        if !(1..=64).contains(&bits)||!(1..=64).contains(&distance)||2*distance<=bits{
            return Err("INVALID Plotkin parameters".into());
        }
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
    fn steps(&mut self,steps:&[Step],live:&mut Facts<'_>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String> {
        if depth>self.limits.depth {return Err("RESOURCE_LIMIT branch depth".into());}
        for (index,step) in steps.iter().enumerate() {
            self.diag.location.step=Some(diagnostic_index(index));
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
                Step::Drop{ids}=>{self.charge(ids.len())?;for id in ids {let (removed,probes)=live.remove(id)?;self.charge(probes)?;if !removed{return Err("INVALID drop of absent fact".into());}}continue},
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
                    self.charge(1)?; // constant-size child scope
                    self.stats.branches+=1;
                    assumptions.push(a);
                    self.derivation(left,*kind,expression,live.fork(),assumptions,depth+1)?;assumptions.pop();
                    self.charge(1)?; // constant-size child scope
                    assumptions.push(b);
                    self.derivation(right,*kind,expression,live.fork(),assumptions,depth+1)?;assumptions.pop();
                    (*id,Fact{kind:*kind,expr:expression.clone()})
                },
            };
            f.expr.validate(self.input.vars.len())?;
            let (existing,probes)=live.lookup(&id);self.charge(probes)?;if existing.is_some() {return Err("INVALID live fact register overwritten".into());}
            if live.len()>=self.limits.live_facts {return Err("RESOURCE_LIMIT live facts".into());}
            live.try_reserve(1).map_err(|_|"RESOURCE_LIMIT fact allocation")?; live.insert(id,f);
            self.stats.peak_live_facts=self.stats.peak_live_facts.max(live.len());
        }
        // No step is executing once a block's step list has completed.
        self.diag.location.step=None;
        Ok(())
    }
    fn split_facts(&mut self,expression:&Expr,integer:&Option<Ref>,live:&Facts<'_>,assumptions:&[Fact])->Result<(Fact,Fact),String>{
        expression.validate(self.input.vars.len())?;
        if let Some(r)=integer {let f=self.get(r,live,assumptions)?;if f.kind!=Kind::Int || f.expr!=*expression{return Err("INVALID integer split witness".into());}}
        let mut e=expression.scaled(&(-Q::one()))?;if integer.is_some(){e.constant+=Q::one();}e.validate(self.input.vars.len())?;
        Ok((Fact{kind:Kind::Le,expr:expression.clone()},Fact{kind:Kind::Le,expr:e}))
    }
    fn absurd(&mut self,r:&Ref,live:&Facts<'_>,assumptions:&[Fact])->Result<(),String>{
        let f=self.get(r,live,assumptions)?;
        if f.expr.terms.is_empty() && ((f.kind==Kind::Le && f.expr.constant.is_positive()) || (f.kind==Kind::Eq && !f.expr.constant.is_zero())) {Ok(())} else {Err("INVALID contradiction witness".into())}
    }
    fn derivation(&mut self,d:&Derivation,kind:Kind,expression:&Expr,mut live:Facts<'_>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String>{
        self.begin_block();
        self.steps(&d.steps,&mut live,assumptions,depth)?;
        match &d.end {
            DerivationEnd::Witness(r)=>self.check_fact(kind,expression.clone(),r,&live,assumptions),
            DerivationEnd::Absurd(r)=>self.absurd(r,&live,assumptions),
        }
    }
    fn run(&mut self,block:&Block,mut live:Facts<'_>,assumptions:&mut Vec<Fact>,depth:usize)->Result<(),String> {
        self.begin_block();
        self.steps(&block.steps,&mut live,assumptions,depth)?;
        match &block.end {
            End::SubflowLift{witness,body}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=remaining_limits(self.limits,self.stats.work)?;
                let extension=crate::subflow::prepare_unchecked_extension(self.input,witness,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT subflow work width")?)?;
                // The joint-existence lemma and generated laws remain trusted.
                // Only references already valid in the old scope can establish
                // the premises; no appended bound or row is visible here.
                for premise in extension.premises{self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;}
                self.stats.subflow_lifts=self.stats.subflow_lifts.checked_add(1).ok_or("RESOURCE_LIMIT subflow lift counter")?;
                self.stats.subflow_generated_variables=self.stats.subflow_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT subflow variable counter")?;
                self.stats.subflow_generated_rows=self.stats.subflow_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT subflow row counter")?;
                self.stats.subflow_generated_terms=self.stats.subflow_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT subflow term counter")?;
                Context{input:&extension.model,output:self.output,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::SignedLift{decompositions,body}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=remaining_limits(self.limits,self.stats.work)?;
                let extension=crate::signed::prepare_unchecked_extension(self.input,decompositions,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT signed work width")?)?;
                for premise in extension.premises{self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;}
                self.stats.signed_lifts+=1;
                self.stats.signed_generated_variables=self.stats.signed_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT signed variable counter")?;
                self.stats.signed_generated_rows=self.stats.signed_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT signed row counter")?;
                self.stats.signed_generated_terms=self.stats.signed_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT signed term counter")?;
                Context{input:&extension.model,output:self.output,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::MenuLift{menus,body}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=remaining_limits(self.limits,self.stats.work)?;
                let extension=crate::menu::prepare_unchecked_extension(self.input,menus,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT menu work width")?)?;
                for premise in extension.premises{self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;}
                self.stats.menu_lifts+=1;
                self.stats.menu_generated_variables=self.stats.menu_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT menu variable counter")?;
                self.stats.menu_generated_rows=self.stats.menu_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT menu row counter")?;
                self.stats.menu_generated_terms=self.stats.menu_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT menu term counter")?;
                Context{input:&extension.model,output:self.output,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::IntervalLift{intervals,body}=>{
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
                Context{input:&extension.model,output:self.output,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::FlowLift{witness,body}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=Limits{work:self.limits.work.checked_sub(self.stats.work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:self.limits.live_facts,depth:self.limits.depth};
                let extension=crate::flow::prepare_unchecked_extension(self.input,witness,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT flow work width")?)?;
                // The builder is trusted for the joint-existence lemma and its
                // generated model. Here we check its premises in the OLD scope;
                // this does not independently prove the extension lemma.
                for premise in extension.premises{
                    self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;
                }
                self.stats.flow_lifts+=1;
                self.stats.flow_generated_variables=self.stats.flow_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT flow variable counter")?;
                self.stats.flow_generated_rows=self.stats.flow_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT flow row counter")?;
                self.stats.flow_generated_terms=self.stats.flow_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT flow term counter")?;
                Context{input:&extension.model,output:self.output,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::Absurd{fact}=>self.absurd(fact,&live,assumptions),
            End::Split{expression,integer,left,right}=>{
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let (a,b)=self.split_facts(expression,integer,&live,assumptions)?;
                self.charge(1)?; // constant-size child scope
                self.stats.branches+=1;
                assumptions.push(a);
                self.run(left,live.fork(),assumptions,depth+1)?;assumptions.pop();
                assumptions.push(b);
                self.run(right,live,assumptions,depth+1)?;assumptions.pop();Ok(())
            },
            End::Return{map,checks}=>{
                let mut k=0;
                self.walk_return(map,|context,kind,e,_origin|{
                    let r=checks.get(k).ok_or("INVALID missing obligation")?;
                    context.diag.location.obligation=Some(diagnostic_index(k));
                    context.obligation(kind,e,r,&live,assumptions).map_err(|err|format!("{err}; obligation {k}"))?;
                    k+=1;Ok(())
                })?;
                if k!=checks.len(){return Err("INVALID surplus obligation witnesses".into());}Ok(())
            }
        }
    }
}

/// Enumerate exactly the obligations checked by Return; models are already oriented.
pub fn plan_return_obligations(input:&Model,output:&Model,map:&[Expr],limits:&Limits)->Result<Vec<ReturnObligation>,String>{
    let mut obligations=Vec::new();
    visit_return_obligations(input,output,map,limits,|obligation|{
        obligations.try_reserve(1).map_err(|_|"RESOURCE_LIMIT Return obligation allocation")?;
        obligations.push(obligation);Ok(())
    })?;Ok(obligations)
}
pub fn visit_return_obligations<F>(input:&Model,output:&Model,map:&[Expr],limits:&Limits,mut visitor:F)->Result<(),String>
where F:FnMut(ReturnObligation)->Result<(),String>{
    input.validate()?;output.validate()?;
    let mut stats=Statistics::default();let mut diag=Diagnostics::default();let mut count=0;
    Context{input,output,limits,stats:&mut stats,diag:&mut diag}.walk_return(map,|context,kind,expression,origin|{
        expression.validate(input.vars.len())?;context.charge(expression.terms.len()+1)?;
        if count>=crate::codec::MAX_ITEMS{return Err("RESOURCE_LIMIT Return obligation count".into());}
        count+=1;visitor(ReturnObligation{kind,expression,origin:origin.owned()})
    })
}

/// Prove optimization equivalence on two complete MILPs. Both directions use
/// their actual integer declarations and require a nonincreasing objective.
pub fn verify(source:&Model,target:&Model,certificate:&Certificate,limits:&Limits)->Result<Statistics,String>{
    verify_with_diagnostics(source,target,certificate,limits,&mut Diagnostics::default())
}
pub fn verify_with_diagnostics(source:&Model,target:&Model,certificate:&Certificate,limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String>{
    diag.location=Location::default();source.validate()?;target.validate()?;
    let mut stats=Statistics::default();
    for (direction,input,output,block) in [("forward",source,target,&certificate.forward),("reverse",target,source,&certificate.reverse)]{
        diag.location=Location{direction:Some(direction),..Location::default()};
        Context{input,output,limits,stats:&mut stats,diag}.run(block,Facts::new(),&mut Vec::new(),1)?;
    }
    diag.location=Location::default();Ok(stats)
}
fn remaining_limits(limits:&Limits,work:u64)->Result<Limits,String>{
    Ok(Limits{work:limits.work.checked_sub(work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:limits.live_facts,depth:limits.depth})
}

// Unit tests for individual proof rules do not expose a partial certification API.
#[cfg(test)]
pub(crate) fn check_block(input:&Model,output:&Model,block:&Block,limits:&Limits)->Result<Statistics,String>{
    input.validate()?;output.validate()?;
    let mut stats=Statistics::default();let mut diag=Diagnostics::default();
    Context{input,output,limits,stats:&mut stats,diag:&mut diag}.run(block,Facts::new(),&mut Vec::new(),1)?;
    Ok(stats)
}

#[cfg(test)]
#[path="scope_state_audit.rs"]
mod scope_state_audit;

#[cfg(test)]
#[path="rational_shortcuts_audit.rs"]
mod rational_shortcuts_audit;
