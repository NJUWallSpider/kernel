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
    pub halfspace_domains:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub halfspace_generated_rows:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub halfspace_generated_terms:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_lifts:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_variables:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_rows:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub subflow_generated_terms:u64,
    #[serde(skip_serializing_if="zero_counter")]
    pub improvements:u64,
    pub obligations: u64, pub linear_terms: u64, pub substitution_terms: u64,
    pub branches: u64, pub peak_live_facts: usize, pub work: u64,
    pub points:u64,pub point_coefficient_terms:u64,pub plotkin_pairs:u64,
    pub interval_lifts:u64,pub interval_generated_variables:u64,pub interval_generated_rows:u64,pub interval_generated_terms:u64,
    pub bijections:u64,pub injectivity_coordinates:u64,pub injectivity_generated_variables:u64,pub injectivity_generated_rows:u64,pub injectivity_generated_terms:u64,
    pub signed_lifts:u64,pub signed_generated_variables:u64,pub signed_generated_rows:u64,pub signed_generated_terms:u64,
    pub objective_level_domains:u64,pub objective_level_generated_rows:u64,pub objective_level_generated_terms:u64,
    pub menu_lifts:u64,pub menu_generated_variables:u64,pub menu_generated_rows:u64,pub menu_generated_terms:u64,
    pub flow_lifts:u64,pub flow_generated_variables:u64,pub flow_generated_rows:u64,pub flow_generated_terms:u64,
}
fn zero_counter(n:&u64)->bool{*n==0}
/// Best-effort source location attached to a failed verification. Every field
/// is set only where the verifier already knows the index it works on; a field
/// stays `None` when that index is unknown for the failure being reported.
///
/// Diagnostics are written after every acceptance decision and are never read
/// by the verifier: they cannot change error strings, control flow, work
/// accounting or acceptance. On success the fields keep their last observed
/// values, which are documented as not load-bearing.
///
/// Field semantics:
/// - `claim`: index into `Request::claims` (or the [`verify`] claim slice) of
///   the directional claim currently being verified. Set for the whole
///   validation and walk of that claim; `None` for work not tied to a requested
///   claim (point witnesses, bijection injectivity, improvement witnesses,
///   standalone refutations).
/// - `point`: index into `Request::points` of the point witness currently being
///   verified; `None` while claims, injectivity, improvements or refutations run.
/// - `block`: index of the top-level certificate block under verification.
///   `Request::claims` and `Certificate::blocks` are aligned, so for a requested
///   claim this equals `claim`; `None` for blocks that are not top-level
///   certificate blocks (improvement blocks, fiber refutations, standalone
///   refutations).
/// - `step`: 0-based index of the step currently executing inside the innermost
///   active block or `Step::Cases` derivation; `None` before its first step,
///   after its step list completes, and while a terminal obligation is checked.
/// - `obligation`: 0-based index of the terminal obligation currently being
///   checked, numbered in the order the verifier emits a given block's
///   obligations: `End::Return`/`End::ImproveReturn` checks, the injectivity
///   equality checks, or the single `End::PositiveRefutation` obligation.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Location {
    #[serde(skip_serializing_if="Option::is_none")]
    pub claim: Option<u32>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub point: Option<u32>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub block: Option<u32>,
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

/// Origin of a Return obligation. Indices are zero-based. A composition's
/// `group` is its position in the supplied list of opposing forward maps.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ObligationOrigin {
    pub kind: String,
    #[serde(skip_serializing_if="Option::is_none")]
    pub index: Option<u32>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if="Option::is_none")]
    pub group: Option<u32>,
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
    kind: &'static str, index: Option<usize>, name: Option<&'a str>, group: Option<usize>,
}
impl<'a> ReturnOrigin<'a> {
    fn plain(kind: &'static str) -> Self { Self {kind,index:None,name:None,group:None} }
    fn indexed(kind: &'static str, index: usize, name: Option<&'a str>) -> Self {
        Self {kind,index:Some(index),name,group:None}
    }
    fn owned(self) -> ObligationOrigin {
        ObligationOrigin {kind:self.kind.into(),index:self.index.map(diagnostic_index),
            name:self.name.map(str::to_owned),group:self.group.map(diagnostic_index)}
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
struct Context<'a> { improvement:Option<&'a ImprovementClaim>, compositions:&'a [&'a [Expr]], refutation:bool, input: &'a Model, output: &'a Model, claim: &'a Claim, inverse: Option<&'a [Expr]>, inverse_level:Option<&'a Q>, limits: &'a Limits, stats: &'a mut Statistics, diag: &'a mut Diagnostics }
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

    /// Single shared ordering/formula walk for verification and authoring.
    /// The callback checks a witness immediately during verification, retaining
    /// the historical interleaving of substitution charges and fact checks.
    fn walk_return<F>(&mut self,map:&[Expr],margin:Option<&Expr>,mut emit:F)->Result<(),String>
    where F: FnMut(&mut Self,Kind,Expr,ReturnOrigin<'_>)->Result<(),String> {
        let output=self.output;
        let input=self.input;
        let claim=self.claim;
        if map.len()!=output.vars.len(){return Err("INVALID incomplete mapping".into());}
        for e in map {e.validate(input.vars.len())?;self.charge(e.terms.len()+1)?;}
        for (i,v) in output.vars.iter().enumerate() {
            if let Some(b)=&v.lower {let mut e=map[i].scaled(&(-Q::one()))?;e.constant+=b;emit(self,Kind::Le,e,ReturnOrigin::indexed("variable.lower",i,Some(&v.name)))?;}
            if let Some(b)=&v.upper {let mut e=map[i].clone();e.constant-=b;emit(self,Kind::Le,e,ReturnOrigin::indexed("variable.upper",i,Some(&v.name)))?;}
            if v.integer && claim.output_integers {emit(self,Kind::Int,map[i].clone(),ReturnOrigin::indexed("variable.integer",i,Some(&v.name)))?;}
        }
        for (i,row) in output.rows.iter().enumerate() {
            let e=self.substitute(&row.expr,map)?;
            if let Some(b)=&row.lower {if row.upper.as_ref()==Some(b){let mut eq=e;eq.constant-=b;emit(self,Kind::Eq,eq,ReturnOrigin::indexed("row.equal",i,Some(&row.name)))?;continue;}}
            if let Some(b)=&row.lower {let mut lo=e.scaled(&(-Q::one()))?;lo.constant+=b;emit(self,Kind::Le,lo,ReturnOrigin::indexed("row.lower",i,Some(&row.name)))?;}
            if let Some(b)=&row.upper {let mut hi=e;hi.constant-=b;emit(self,Kind::Le,hi,ReturnOrigin::indexed("row.upper",i,Some(&row.name)))?;}
        }
        if claim.objective!=Objective::None {
            let mut e=self.substitute(&output.objective,map)?;e.add_scaled(&input.objective,&(-Q::one()))?;
            if let Some(margin)=margin{self.charge(margin.terms.len()+1)?;e.add_scaled(margin,&Q::one())?;}
            let (kind,origin)=if claim.objective==Objective::Equal{(Kind::Eq,"objective.equal")}else{(Kind::Le,"objective.non_increasing")};
            emit(self,kind,e,ReturnOrigin::plain(origin))?;
        }
        for (j,(i,o)) in claim.projection.iter().enumerate() {let mut e=map[*o as usize].clone();e.add_scaled(&Expr::var(*i),&(-Q::one()))?;emit(self,Kind::Eq,e,ReturnOrigin::indexed("projection",j,None))?;}
        for (j,(input_expr,output_expr)) in claim.affine_projection.iter().enumerate(){let mut e=self.substitute(output_expr,map)?;e.add_scaled(input_expr,&(-Q::one()))?;emit(self,Kind::Eq,e,ReturnOrigin::indexed("affine_projection",j,None))?;}
        if let Some(inverse)=self.inverse {for (i,back) in inverse.iter().enumerate(){let mut e=self.substitute(back,map)?;e.add_scaled(&Expr::var(i as u32),&(-Q::one()))?;emit(self,Kind::Eq,e,ReturnOrigin::indexed("inverse.coordinate",i,Some(&input.vars[i].name)))?;}}
        // Composition must land in the independently proved opposing domain.
        if let Some(level)=self.inverse_level {let mut e=self.substitute(&output.objective,map)?;e.constant-=level;emit(self,Kind::Eq,e,ReturnOrigin::plain("inverse.objective_level"))?;}
        if let Some(lower)=&claim.input_objective_lower{let mut e=input.objective.scaled(&(-Q::one()))?;e.constant+=lower;emit(self,Kind::Le,e,ReturnOrigin::plain("input.objective_lower"))?;}
        // Original input coordinates stay prefixes through every extension.
        for (group,forward) in self.compositions.iter().enumerate(){for (j,e) in forward.iter().enumerate(){let mut e=self.substitute(e,map)?;e.add_scaled(&Expr::var(j as u32),&(-Q::one()))?;let mut origin=ReturnOrigin::indexed("bijection.coordinate",j,input.vars.get(j).map(|v|v.name.as_str()));origin.group=Some(group);emit(self,Kind::Eq,e,origin)?;}}
        Ok(())
    }

    fn improvement_margin(&mut self,margin:&ImprovementMargin)->Result<Expr,String> {
        let claim=self.improvement.ok_or("INVALID improvement return context")?;
        let q=match margin{ImprovementMargin::Constant(q)|ImprovementMargin::Predicate(q)=>q};
        check_q(q)?;if !q.is_positive(){return Err("INVALID improvement margin must be strictly positive".into());}
        match margin {
            ImprovementMargin::Constant(q)=>Ok(Expr{constant:q.clone(),terms:vec![]}),
            ImprovementMargin::Predicate(q)=>{self.charge(claim.positive.terms.len()+1)?;claim.positive.scaled(q)},
        }
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
                Kind::Int=>e.constant.is_integer() && e.terms.iter().all(|(i,c)| c.is_integer() && self.claim.input_integers && self.input.vars[*i as usize].integer),
            }; if valid {return Ok(());} return Err("INVALID non-tautological exact obligation".into());
        }
        let f=self.get(r,live,assumptions)?;
        if (f.kind==kind || f.kind==Kind::Eq) && f.expr==e {Ok(())} else {Err(format!("INVALID obligation mismatch: expected {kind:?}"))}
    }
    fn plotkin(&mut self,bits:u32,distance:u32,variables:&[(u32,u64)],cliques:&[Ref],live:&Facts<'_>,assumptions:&[Fact])->Result<Fact,String>{
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
        if self.refutation && !matches!(block.end,End::Absurd{..}|End::Split{..}){return Err("INVALID refutation requires only Absurd/Split endpoints".into());}
        self.steps(&block.steps,&mut live,assumptions,depth)?;
        match &block.end {
            End::SubflowLift{witness,body}=>{
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
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
                Context{improvement:self.improvement,compositions:self.compositions,refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,inverse_level:self.inverse_level,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::PositiveRefutation{fact}=>{
                let claim=self.improvement.ok_or("INVALID positive refutation outside improvement")?;
                self.diag.location.obligation=Some(0);
                self.obligation(Kind::Le,claim.positive.clone(),fact,&live,assumptions)
            },
            End::SignedLift{decompositions,body}=>{
                if !self.claim.input_integers{return Err("INVALID SignedLift requires integer input mode".into());}
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=remaining_limits(self.limits,self.stats.work)?;
                let extension=crate::signed::prepare_unchecked_extension(self.input,decompositions,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT signed work width")?)?;
                for premise in extension.premises{self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;}
                self.stats.signed_lifts+=1;
                self.stats.signed_generated_variables=self.stats.signed_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT signed variable counter")?;
                self.stats.signed_generated_rows=self.stats.signed_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT signed row counter")?;
                self.stats.signed_generated_terms=self.stats.signed_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT signed term counter")?;
                Context{improvement:self.improvement,compositions:self.compositions,refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,inverse_level:self.inverse_level,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::MenuLift{menus,body}=>{
                if !self.claim.input_integers{return Err("INVALID MenuLift requires integer input mode".into());}
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
                if depth>=self.limits.depth{return Err("RESOURCE_LIMIT branch depth".into());}
                let remaining=remaining_limits(self.limits,self.stats.work)?;
                let extension=crate::menu::prepare_unchecked_extension(self.input,menus,&remaining)?;
                self.charge(usize::try_from(extension.statistics.work).map_err(|_|"RESOURCE_LIMIT menu work width")?)?;
                for premise in extension.premises{self.check_fact(premise.kind,premise.expression,&premise.reference,&live,assumptions)?;}
                self.stats.menu_lifts+=1;
                self.stats.menu_generated_variables=self.stats.menu_generated_variables.checked_add(extension.statistics.generated_variables).ok_or("RESOURCE_LIMIT menu variable counter")?;
                self.stats.menu_generated_rows=self.stats.menu_generated_rows.checked_add(extension.statistics.generated_rows).ok_or("RESOURCE_LIMIT menu row counter")?;
                self.stats.menu_generated_terms=self.stats.menu_generated_terms.checked_add(extension.statistics.generated_terms).ok_or("RESOURCE_LIMIT menu term counter")?;
                Context{improvement:self.improvement,compositions:self.compositions,refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,inverse_level:self.inverse_level,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
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
                Context{improvement:self.improvement,compositions:self.compositions,refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,inverse_level:self.inverse_level,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
            },
            End::FlowLift{witness,body}=>{
                if self.inverse.is_some(){return Err("INVALID inverse requires affine terminal maps".into());}
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
                Context{improvement:self.improvement,compositions:self.compositions,refutation:false,input:&extension.model,output:self.output,claim:self.claim,inverse:None,inverse_level:self.inverse_level,limits:self.limits,stats:self.stats,diag:self.diag}.run(body,live,assumptions,depth+1)
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
            End::Return{map,checks}|End::ImproveReturn{map,checks,..}=>{
                let margin=match (&block.end,self.improvement){
                    (End::Return{..},None)=>None,
                    (End::ImproveReturn{margin,..},Some(_))=>Some(self.improvement_margin(margin)?),
                    _=>return Err("INVALID improvement return context".into()),
                };
                let mut k=0;
                self.walk_return(map,margin.as_ref(),|context,kind,e,_origin|{
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

/// Requested claims are supplied by the caller, never weakened by certificate declarations.
/// Enumerate a terminal Return using the verifier's own formula/order walk.
/// `input` and `output` are already oriented for the direction and include the
/// current input scope. No witness is created or accepted by this function.
pub fn plan_return_obligations(
    input:&Model, output:&Model, claim:&Claim, map:&[Expr],
    inverse:Option<&[Expr]>, inverse_level:Option<&Q>,
    compositions:&[&[Expr]], limits:&Limits,
)->Result<Vec<ReturnObligation>,String> {
    let mut obligations=Vec::new();
    visit_return_obligations(input,output,claim,map,inverse,inverse_level,compositions,limits,|obligation|{
        obligations.try_reserve(1).map_err(|_|"RESOURCE_LIMIT Return obligation allocation")?;
        obligations.push(obligation);Ok(())
    })?;Ok(obligations)
}

/// Stream authoring propositions without retaining the complete goal array.
/// The verifier's acceptance path does not call this planning entry point.
pub fn visit_return_obligations<F>(
    input:&Model, output:&Model, claim:&Claim, map:&[Expr],
    inverse:Option<&[Expr]>, inverse_level:Option<&Q>, compositions:&[&[Expr]],
    limits:&Limits, visitor:F,
)->Result<(),String> where F:FnMut(ReturnObligation)->Result<(),String> {
    visit_return_obligations_context(input,output,claim,map,inverse,inverse_level,compositions,None,limits,visitor)
}

/// Plan ImproveReturn in the same immutable strict-improvement context used by
/// the verifier. The ordinary Claim must be its exact internal directional
/// context, and the output must be the original actual input-model prefix.
pub fn plan_improvement_return_obligations(
    input:&Model, output:&Model, claim:&Claim, map:&[Expr],
    improvement:&ImprovementClaim, margin:&ImprovementMargin, limits:&Limits,
)->Result<Vec<ReturnObligation>,String> {
    let mut obligations=Vec::new();
    visit_improvement_return_obligations(input,output,claim,map,improvement,margin,limits,|obligation|{
        obligations.try_reserve(1).map_err(|_|"RESOURCE_LIMIT Return obligation allocation")?;
        obligations.push(obligation);Ok(())
    })?;Ok(obligations)
}

/// Streaming counterpart of [`plan_improvement_return_obligations`].
pub fn visit_improvement_return_obligations<F>(
    input:&Model, output:&Model, claim:&Claim, map:&[Expr],
    improvement:&ImprovementClaim, margin:&ImprovementMargin, limits:&Limits, visitor:F,
)->Result<(),String> where F:FnMut(ReturnObligation)->Result<(),String> {
    let expected=Claim{reverse:false,input_integers:improvement.integers,output_integers:improvement.integers,
        objective:Objective::NonIncreasing,projection:vec![],affine_projection:vec![],inverse:None,
        input_objective_lower:None,input_objective_level:None,input_halfspace:None};
    if claim!=&expected{return Err("INVALID Return plan improvement claim context".into());}
    if input.vars.get(..output.vars.len())!=Some(output.vars.as_slice())
        || input.rows.get(..output.rows.len())!=Some(output.rows.as_slice())
        || input.objective!=output.objective {
        return Err("INVALID Return plan improvement model context".into());
    }
    improvement.positive.validate(output.vars.len())?;
    visit_return_obligations_context(input,output,claim,map,None,None,&[],Some((improvement,margin)),limits,visitor)
}

fn visit_return_obligations_context<F>(
    input:&Model, output:&Model, claim:&Claim, map:&[Expr],
    inverse:Option<&[Expr]>, inverse_level:Option<&Q>, compositions:&[&[Expr]],
    improvement:Option<(&ImprovementClaim,&ImprovementMargin)>, limits:&Limits, mut visitor:F,
)->Result<(),String> where F:FnMut(ReturnObligation)->Result<(),String> {
    input.validate()?;output.validate()?;
    if let Some(lower)=&claim.input_objective_lower{check_q(lower)?;}
    if let Some(level)=&claim.input_objective_level{check_q(level)?;}
    if let Some(expression)=&claim.input_halfspace{expression.validate(input.vars.len())?;}
    for (i,o) in &claim.affine_projection{i.validate(input.vars.len())?;o.validate(output.vars.len())?;}
    let mut seen=std::collections::HashSet::new();
    for &(i,o) in &claim.projection {
        if i as usize>=input.vars.len() || o as usize>=output.vars.len() || !seen.insert((i,o)){
            return Err("INVALID projection coordinate".into());
        }
    }
    if claim.inverse.is_some()!=inverse.is_some(){return Err("INVALID Return plan inverse mapping context".into());}
    if let Some(inverse)=inverse {
        if claim.input_halfspace.is_some(){return Err("INVALID inverse with input halfspace is unsupported".into());}
        if inverse.len()!=input.vars.len(){return Err("INVALID inverse mapping dimension".into());}
        for e in inverse{e.validate(output.vars.len())?;}
    }
    if let Some(level)=inverse_level{check_q(level)?;if inverse.is_none(){return Err("INVALID Return plan inverse level context".into());}}
    for forward in compositions {
        if forward.len()>input.vars.len(){return Err("INVALID Return plan composition dimension".into());}
        for e in *forward{e.validate(output.vars.len())?;}
    }
    let mut stats=Statistics::default();
    let mut diag=Diagnostics::default();
    let mut count=0;
    let mut context=Context{improvement:improvement.map(|(claim,_)|claim),compositions,refutation:false,input,output,claim,inverse,inverse_level,limits,stats:&mut stats,diag:&mut diag};
    let margin=if let Some((claim,margin))=improvement {
        context.charge(claim.positive.terms.len()+1)?;Some(context.improvement_margin(margin)?)
    }else{None};
    context.walk_return(map,margin.as_ref(),|context,kind,expression,origin|{
            expression.validate(input.vars.len())?;context.charge(expression.terms.len()+1)?;
            if count>=crate::codec::MAX_ITEMS{return Err("RESOURCE_LIMIT Return obligation count".into());}
            count+=1;visitor(ReturnObligation{kind,expression,origin:origin.owned()})
        })
}

/// The entire input/output models are validated and used for every proof obligation.
pub fn verify(source:&Model,target:&Model,cert:&Certificate,requested:&[Claim],limits:&Limits)->Result<Statistics,String> {
    verify_with_diagnostics(source,target,cert,requested,limits,&mut Diagnostics::default())
}

/// [`verify`] with best-effort [`Location`] reporting on the error path.
/// `claim` and `block` index the supplied claim list and `cert.blocks`, which
/// are aligned exactly as in [`verify_request_with_diagnostics`].
pub fn verify_with_diagnostics(source:&Model,target:&Model,cert:&Certificate,requested:&[Claim],limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String> {
    diag.location=Location::default();
    if requested.is_empty()||!cert.points.is_empty()||!cert.bijections.is_empty()||!cert.improvements.is_empty(){return Err("INVALID requested contract mismatch".into());}
    verify_claims(source,target,cert,requested,&[],limits,diag)
}

/// All directional claims are proved before any point strictness witness is used.
pub fn verify_request(source:&Model,target:&Model,cert:&Certificate,requested:&Request,limits:&Limits)->Result<Statistics,String>{
    verify_request_with_diagnostics(source,target,cert,requested,limits,&mut Diagnostics::default())
}

/// [`verify_request`] with best-effort [`Location`] reporting on the error path.
/// The location is cleared at entry and between the internal phases (claims,
/// bijections, point witnesses, improvements), so a reported index is never
/// attributed to an earlier phase. Diagnostics cannot change error strings,
/// control flow, [`Statistics`] or the acceptance decision.
pub fn verify_request_with_diagnostics(source:&Model,target:&Model,cert:&Certificate,requested:&Request,limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String>{
    diag.location=Location::default();
    if requested.claims.is_empty()&&requested.points.is_empty()&&requested.improvements.is_empty(){return Err("INVALID empty request".into());}
    if cert.improvements.len()!=requested.improvements.len()||cert.improvements.iter().zip(&requested.improvements).any(|(w,r)|w.claim!=*r){return Err("INVALID requested improvement contract mismatch".into());}
    if cert.points.len()!=requested.points.len()||cert.points.iter().zip(&requested.points).any(|(p,r)|p.claim!=*r){return Err("INVALID requested point contract mismatch".into());}
    if cert.bijections.len()!=requested.bijections.len()||cert.bijections.iter().zip(&requested.bijections).any(|(b,r)|b.claim!=*r){return Err("INVALID requested bijection contract mismatch".into());}
    // Existing strictness contracts refer to whole actual LP models. Reject a
    // restricted inclusion before accepting any directional proof in this call.
    for point in &requested.points{if let PointClaim::Strictness{inclusion_claim}|PointClaim::FiberStrictness{inclusion_claim}=point{
        let claim=requested.claims.get(*inclusion_claim as usize).ok_or("INVALID strictness inclusion claim index")?;
        if claim.input_objective_level.is_some()||claim.input_halfspace.is_some(){return Err("INVALID strictness requires unrestricted inclusion domain".into());}
    }}
    let mut stats=verify_claims(source,target,cert,&requested.claims,&requested.bijections,limits,diag)?;
    diag.location=Location::default();
    for witness in &cert.bijections{
        let claim=&requested.claims[witness.claim.forward_claim as usize];
        let (input,output)=if claim.reverse{(target,source)}else{(source,target)};
        let End::Return{map,..}=&cert.blocks[witness.claim.forward_claim as usize].end else{unreachable!()};
        let result=verify_injectivity_with_diagnostics(input,output,map,claim.input_integers,&witness.injectivity,&remaining_limits(limits,stats.work)?,diag)?;
        merge_statistics(&mut stats,result)?;
    }
    diag.location=Location::default();
    let remaining=Limits{work:limits.work.checked_sub(stats.work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:limits.live_facts,depth:limits.depth};
    let points=crate::point::verify_points_with_diagnostics(source,target,cert,requested,&remaining,diag)?;
    stats.points=points.points;stats.point_coefficient_terms=points.coefficient_terms;
    stats.work=stats.work.checked_add(points.work).ok_or("RESOURCE_LIMIT work overflow")?;
    diag.location=Location::default();
    for witness in &cert.improvements{
        let input=if witness.claim.target{target}else{source};
        witness.claim.positive.validate(input.vars.len())?;
        let claim=Claim{reverse:false,input_integers:witness.claim.integers,output_integers:witness.claim.integers,objective:Objective::NonIncreasing,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None,input_objective_level:None,input_halfspace:None};
        let mut context=Context{improvement:Some(&witness.claim),compositions:&[],refutation:false,input,output:input,claim:&claim,inverse:None,inverse_level:None,limits,stats:&mut stats,diag};
        context.charge(witness.claim.positive.terms.len()+1)?;
        let mut assumptions=Vec::new();assumptions.try_reserve_exact(1).map_err(|_|"RESOURCE_LIMIT improvement assumption allocation")?;
        // Strict positivity entails this weak fact. The strict part is retained
        // separately by the immutable root contract, never exported as a fact.
        assumptions.push(Fact{kind:Kind::Le,expr:witness.claim.positive.scaled(&(-Q::one()))?});
        context.run(&witness.block,Facts::new(),&mut assumptions,1)?;
        stats.improvements=stats.improvements.checked_add(1).ok_or("RESOURCE_LIMIT improvement counter")?;
    }
    if stats.work>limits.work{return Err("RESOURCE_LIMIT proof work budget".into());}Ok(stats)
}
fn verify_claims(source:&Model,target:&Model,cert:&Certificate,requested:&[Claim],bijections:&[BijectionClaim],limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String> {
    source.validate()?;target.validate()?;
    if cert.claims!=requested || cert.blocks.len()!=requested.len(){return Err("INVALID requested contract mismatch".into());}
    let mut stats=Statistics::default();
    let mut compositions:Vec<Vec<&[Expr]>>=Vec::new();
    // Allocate only after charging this new per-contract bookkeeping.
    if !bijections.is_empty(){
        let work=requested.len().checked_add(bijections.len()).ok_or("RESOURCE_LIMIT bijection count")?;
        stats.work=u64::try_from(work).map_err(|_|"RESOURCE_LIMIT bijection work width")?;
        if stats.work>limits.work{return Err("RESOURCE_LIMIT proof work budget".into());}
        compositions.try_reserve(requested.len()).map_err(|_|"RESOURCE_LIMIT bijection allocation")?;
        compositions.resize_with(requested.len(),Vec::new);
    }
    let mut seen_pairs=std::collections::HashSet::new();
    seen_pairs.try_reserve(bijections.len()).map_err(|_|"RESOURCE_LIMIT bijection allocation")?;
    for pair in bijections{
        if pair.forward_claim==pair.reverse_claim||!seen_pairs.insert((pair.forward_claim,pair.reverse_claim)){return Err("INVALID duplicate or self bijection pair".into());}
        let forward=requested.get(pair.forward_claim as usize).ok_or("INVALID bijection forward index")?;
        let reverse=requested.get(pair.reverse_claim as usize).ok_or("INVALID bijection reverse index")?;
        if forward.input_objective_level.is_some()||reverse.input_objective_level.is_some()||forward.input_halfspace.is_some()||reverse.input_halfspace.is_some(){return Err("INVALID V7 bijection requires unrestricted domains".into());}
        if forward.reverse==reverse.reverse||forward.input_integers!=reverse.output_integers||forward.output_integers!=reverse.input_integers{return Err("INVALID bijection direction or domain".into());}
        let End::Return{map,..}=&cert.blocks[pair.forward_claim as usize].end else{return Err("INVALID bijection forward requires root affine Return".into());};
        let (input,output)=if forward.reverse{(target,source)}else{(source,target)};
        if map.len()!=output.vars.len(){return Err("INVALID bijection forward map dimension".into());}
        for e in map{e.validate(input.vars.len())?;stats.work=stats.work.checked_add((e.terms.len()+1) as u64).ok_or("RESOURCE_LIMIT work overflow")?;if stats.work>limits.work{return Err("RESOURCE_LIMIT proof work budget".into());}}
        let list=&mut compositions[pair.reverse_claim as usize];list.try_reserve(1).map_err(|_|"RESOURCE_LIMIT bijection allocation")?;list.push(map);
    }
    for (claim_index,(claim,block)) in requested.iter().zip(&cert.blocks).enumerate() {
        diag.location=Location{claim:Some(diagnostic_index(claim_index)),block:Some(diagnostic_index(claim_index)),..Location::default()};
        if let Some(lower)=&claim.input_objective_lower{check_q(lower)?;}
        if let Some(level)=&claim.input_objective_level{check_q(level)?;}
        let (input,output)=if claim.reverse{(target,source)}else{(source,target)};
        if let Some(expression)=&claim.input_halfspace{expression.validate(input.vars.len())?;}
        for (i,o) in &claim.affine_projection{i.validate(input.vars.len())?;o.validate(output.vars.len())?;}
        let mut seen=std::collections::HashSet::new();
        for &(i,o) in &claim.projection {if i as usize>=input.vars.len() || o as usize>=output.vars.len() || !seen.insert((i,o)){return Err("INVALID projection coordinate".into());}}
        let inverse=if let Some(j)=claim.inverse {
            let other=requested.get(j as usize).ok_or("INVALID inverse claim reference")?;
            if claim.input_halfspace.is_some()||other.input_halfspace.is_some(){return Err("INVALID inverse with input halfspace is unsupported".into());}
            if other.reverse==claim.reverse || other.input_integers!=claim.output_integers || other.output_integers!=claim.input_integers {return Err("INVALID inverse claim direction/domain".into());}
            if !matches!(block.end,End::Return{..}) {return Err("INVALID inverse requires affine terminal maps".into());}
            let End::Return{map,..}=&cert.blocks[j as usize].end else{return Err("INVALID inverse requires affine terminal maps".into());};
            if map.len()!=input.vars.len(){return Err("INVALID inverse mapping dimension".into());}
            for e in map {e.validate(output.vars.len())?;}
            Some(map.as_slice())
        }else{None};
        let inverse_level=claim.inverse.and_then(|i|requested[i as usize].input_objective_level.as_ref());
        if let Some(level)=inverse_level{check_q(level)?;}
        let domain=if claim.input_objective_level.is_some()||claim.input_halfspace.is_some(){Some(crate::level::prepare_restricted_domain(input,claim.input_objective_level.as_ref(),claim.input_halfspace.as_ref(),&remaining_limits(limits,stats.work)?)?)}else{None};
        if let Some(domain)=&domain{
            stats.work=stats.work.checked_add(domain.statistics.work).ok_or("RESOURCE_LIMIT objective level work")?;
            if claim.input_objective_level.is_some(){
            stats.objective_level_domains=stats.objective_level_domains.checked_add(1).ok_or("RESOURCE_LIMIT objective level counter")?;
            stats.objective_level_generated_rows=stats.objective_level_generated_rows.checked_add(1).ok_or("RESOURCE_LIMIT objective level row counter")?;
            stats.objective_level_generated_terms=stats.objective_level_generated_terms.checked_add(input.objective.terms.len() as u64).ok_or("RESOURCE_LIMIT objective level term counter")?;
            }
            if let Some(expression)=&claim.input_halfspace{
                stats.halfspace_domains=stats.halfspace_domains.checked_add(1).ok_or("RESOURCE_LIMIT halfspace counter")?;
                stats.halfspace_generated_rows=stats.halfspace_generated_rows.checked_add(1).ok_or("RESOURCE_LIMIT halfspace row counter")?;
                stats.halfspace_generated_terms=stats.halfspace_generated_terms.checked_add(expression.terms.len() as u64).ok_or("RESOURCE_LIMIT halfspace term counter")?;
            }
        }
        let input=domain.as_ref().map(|d|&d.model).unwrap_or(input);
        Context{improvement:None,compositions:compositions.get(claim_index).map(Vec::as_slice).unwrap_or(&[]),refutation:false,input,output,claim,inverse,inverse_level,limits,stats:&mut stats,diag}.run(block,Facts::new(),&mut Vec::new(),1)?;
    }Ok(stats)
}

/// Establish infeasibility of an actual LP model using only contradiction leaves.
/// This entry point has fresh fact/assumption state and never verifies a mapping.
pub fn verify_lp_refutation(model:&Model,block:&Block,limits:&Limits)->Result<Statistics,String>{
    verify_lp_refutation_with_diagnostics(model,block,limits,&mut Diagnostics::default())
}

/// [`verify_lp_refutation`] with best-effort [`Location`] reporting on the error
/// path. Only `step` and `obligation` can be reported: a refutation block is not
/// a top-level certificate block, so `claim`, `point` and `block` are untouched.
pub fn verify_lp_refutation_with_diagnostics(model:&Model,block:&Block,limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String>{
    diag.location.step=None;diag.location.obligation=None;
    model.validate()?;
    let claim=Claim{input_halfspace:None,input_objective_level:None,reverse:false,input_integers:false,output_integers:false,objective:Objective::None,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None};
    let mut stats=Statistics::default();
    Context{improvement:None,compositions:&[],refutation:true,input:model,output:model,claim:&claim,inverse:None,inverse_level:None,limits,stats:&mut stats,diag}.run(block,Facts::new(),&mut Vec::new(),1)?;
    Ok(stats)
}

fn remaining_limits(limits:&Limits,work:u64)->Result<Limits,String>{
    Ok(Limits{work:limits.work.checked_sub(work).ok_or("RESOURCE_LIMIT proof work budget")?,live_facts:limits.live_facts,depth:limits.depth})
}
fn merge_statistics(stats:&mut Statistics,other:Statistics)->Result<(),String>{
    macro_rules! add{($($f:ident),*)=>{$(stats.$f=stats.$f.checked_add(other.$f).ok_or("RESOURCE_LIMIT statistics overflow")?;)*}}
    add!(halfspace_domains,halfspace_generated_rows,halfspace_generated_terms,subflow_lifts,subflow_generated_variables,subflow_generated_rows,subflow_generated_terms,improvements,objective_level_domains,objective_level_generated_rows,objective_level_generated_terms,signed_lifts,signed_generated_variables,signed_generated_rows,signed_generated_terms,obligations,linear_terms,substitution_terms,branches,work,bijections,injectivity_coordinates,injectivity_generated_variables,injectivity_generated_rows,injectivity_generated_terms,menu_lifts,menu_generated_variables,menu_generated_rows,menu_generated_terms,flow_lifts,flow_generated_variables,flow_generated_rows,flow_generated_terms,interval_lifts,interval_generated_variables,interval_generated_rows,interval_generated_terms,plotkin_pairs,points,point_coefficient_terms);
    stats.peak_live_facts=stats.peak_live_facts.max(other.peak_live_facts);Ok(())
}
/// Check injectivity of the supplied complete affine map on the actual input
/// domain. Directional totality is a separate obligation established by the caller
/// before this helper is used to accept a requested bijection.
pub fn verify_injectivity(input:&Model,output:&Model,forward_map:&[Expr],input_integers:bool,proof:&EqualityProof,limits:&Limits)->Result<Statistics,String>{
    verify_injectivity_with_diagnostics(input,output,forward_map,input_integers,proof,limits,&mut Diagnostics::default())
}

/// [`verify_injectivity`] with best-effort [`Location`] reporting on the error
/// path: `step` inside the proof's step list and `obligation` (0-based) for the
/// equality checks in the order they are verified. `claim`, `point` and `block`
/// are untouched because this work is not tied to a top-level certificate block.
pub fn verify_injectivity_with_diagnostics(input:&Model,output:&Model,forward_map:&[Expr],input_integers:bool,proof:&EqualityProof,limits:&Limits,diag:&mut Diagnostics)->Result<Statistics,String>{
    diag.location.step=None;diag.location.obligation=None;
    let domain=crate::injectivity::prepare_domain(input,output,forward_map,limits)?;
    if proof.checks.len()!=domain.equalities.len(){return Err("INVALID injectivity equality check count".into());}
    let mut stats=Statistics{work:domain.statistics.work,bijections:1,injectivity_coordinates:domain.equalities.len() as u64,injectivity_generated_variables:domain.statistics.generated_variables,injectivity_generated_rows:domain.statistics.generated_rows,injectivity_generated_terms:domain.statistics.generated_terms,..Statistics::default()};
    if stats.work>limits.work{return Err("RESOURCE_LIMIT proof work budget".into());}
    let claim=Claim{input_halfspace:None,input_objective_level:None,reverse:false,input_integers,output_integers:false,objective:Objective::None,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None};
    let mut context=Context{improvement:None,compositions:&[],refutation:false,input:&domain.model,output:&domain.model,claim:&claim,inverse:None,inverse_level:None,limits,stats:&mut stats,diag};
    let mut facts=Facts::new();let mut assumptions=Vec::new();
    context.steps(&proof.steps,&mut facts,&mut assumptions,1)?;
    for (index,(e,r)) in domain.equalities.into_iter().zip(&proof.checks).enumerate(){context.diag.location.obligation=Some(diagnostic_index(index));context.obligation(Kind::Eq,e,r,&facts,&assumptions)?;}
    Ok(stats)
}

#[cfg(test)]
#[path="scope_state_audit.rs"]
mod scope_state_audit;

#[cfg(test)]
#[path="rational_shortcuts_audit.rs"]
mod rational_shortcuts_audit;
