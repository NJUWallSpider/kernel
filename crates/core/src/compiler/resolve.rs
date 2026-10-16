//! Untrusted mechanical witness reuse. No proof rule or acceptance decision is
//! added here: the real verifier checks every selected reference independently.
use super::{ReturnPlan, MAX_JSON_BYTES, json_error, visit_return};
use crate::{model::{Expr, Model, Q, MAX_Q_BITS, check_q, parse_q}, proof::{Kind, Ref}, verify::{Limits, ReturnObligation}};
use num_bigint::BigInt;
use num_traits::{One, Signed, Zero};
use serde::{Deserialize, Deserializer, Serialize, de::{self, MapAccess, Visitor, value::MapAccessDeserializer}};
use std::{collections::HashMap, hash::{Hash, Hasher}};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AuthoringFact {
    pub kind: Kind,
    #[serde(deserialize_with="authoring_expression")]
    pub expression: Expr,
    pub reference: Ref,
}

// Fact metadata describes derived Kernel expressions, which may be wider than
// any individual model/proof scalar on the wire. This parser is confined to
// untrusted authoring metadata; all actual model, map and proof inputs retain
// their existing scalar policy. Kernel intermediates serialize canonically as
// integers or numerator/denominator strings. Normal-size decimal/scientific
// strings retain the existing vocabulary through parse_q.
// ceil(MAX_Q_BITS * log10(2)) is 19,729 digits at the frozen 65,536-bit bound;
// the integer upper approximation avoids floating point in this policy.
const MAX_METADATA_DIGITS: usize=(MAX_Q_BITS as usize*30_103)/100_000+1;
fn metadata_scalar(text:&str)->Result<Q,String> {
    if text.len()>MAX_METADATA_DIGITS*2+3 {
        return Err("RESOURCE_LIMIT authoring metadata scalar text budget".into());
    }
    let original=match parse_q(text) {Ok(q)=>return Ok(q),Err(error)=>error};
    if !original.starts_with("RESOURCE_LIMIT") {return Err(original);}
    fn integer_literal(text:&str)->bool {
        let digits=text.strip_prefix(['+','-']).unwrap_or(text);
        !digits.is_empty()&&digits.bytes().all(|b|b.is_ascii_digit())
    }
    let (numerator,denominator)=text.split_once('/').unwrap_or((text,"1"));
    if !integer_literal(numerator)||!integer_literal(denominator) {return Err(original);}
    fn integer(text:&str)->Result<BigInt,String> {
        if text.strip_prefix(['+','-']).unwrap_or(text).len()>MAX_METADATA_DIGITS {
            return Err("RESOURCE_LIMIT authoring metadata integer digit budget".into());
        }
        let value=text.parse::<BigInt>().map_err(|_|"invalid authoring metadata integer")?;
        if value.bits()>MAX_Q_BITS {return Err("RESOURCE_LIMIT authoring metadata rational bit budget".into());}
        Ok(value)
    }
    let numerator=integer(numerator)?;let denominator=integer(denominator)?;
    if denominator.is_zero(){return Err("zero denominator".into());}
    let value=Q::new(numerator,denominator);check_q(&value)?;Ok(value)
}
fn authoring_expression<'de,D:Deserializer<'de>>(deserializer:D)->Result<Expr,D::Error> {
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct RawExpr {constant:String,terms:Vec<(u32,String)>}
    let raw=RawExpr::deserialize(deserializer)?;
    let constant=metadata_scalar(&raw.constant).map_err(de::Error::custom)?;
    let mut terms=Vec::new();terms.try_reserve(raw.terms.len())
        .map_err(|_|de::Error::custom("RESOURCE_LIMIT authoring metadata term allocation"))?;
    for (id,coefficient) in raw.terms {terms.push((id,metadata_scalar(&coefficient).map_err(de::Error::custom)?));}
    Ok(Expr{constant,terms})
}

#[derive(Clone, Debug)]
pub enum AssignmentFact { Fact(AuthoringFact), Exact }
impl<'de> Deserialize<'de> for AssignmentFact {
    fn deserialize<D:Deserializer<'de>>(deserializer:D)->Result<Self,D::Error> {
        // Deserialize the map directly, rather than buffering a JSON Value:
        // maps must retain duplicate-field rejection and scalar limit errors.
        struct FactVisitor;
        impl<'de> Visitor<'de> for FactVisitor {
            type Value=AssignmentFact;
            fn expecting(&self,f:&mut std::fmt::Formatter)->std::fmt::Result {
                f.write_str("a typed fact object or the string Exact")
            }
            fn visit_str<E:de::Error>(self,value:&str)->Result<Self::Value,E> {
                if value=="Exact"{Ok(AssignmentFact::Exact)}
                else{Err(E::invalid_value(de::Unexpected::Str(value),&self))}
            }
            fn visit_map<M:MapAccess<'de>>(self,map:M)->Result<Self::Value,M::Error> {
                AuthoringFact::deserialize(MapAccessDeserializer::new(map)).map(AssignmentFact::Fact)
            }
        }
        deserializer.deserialize_any(FactVisitor)
    }
}
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Assignment {
    #[serde(default)] pub index: Option<usize>,
    #[serde(default)] pub label: Option<String>,
    pub fact: AssignmentFact,
}
fn default_auto()->bool{true}
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResolveReturn {
    pub plan: ReturnPlan,
    #[serde(default)] pub facts: Vec<AuthoringFact>,
    #[serde(default)] pub assignments: Vec<Assignment>,
    #[serde(default="default_auto")] pub auto: bool,
}
#[derive(Debug, Serialize)]
pub struct MissingObligation {
    pub index: usize,
    #[serde(flatten)] pub obligation: ReturnObligation,
}
#[derive(Debug, Serialize)]
pub struct ResolveResult {
    pub checks: Vec<Option<Ref>>,
    pub missing: Vec<MissingObligation>,
    pub unknown_assignments: Vec<String>,
    pub obligations: usize,
}
fn invalid(message:impl std::fmt::Display)->String{format!("INVALID compiler resolve Return: {message}")}
fn resource()->String{"RESOURCE_LIMIT compiler resolve Return allocation".into()}

// Hash exact typed rationals/terms directly. A goal owns this temporary key, so
// lookups do not clone its expression or allocate a JSON/string fingerprint.
#[derive(PartialEq, Eq)]
struct Key {kind:Kind,expression:Expr}
impl Hash for Key {
    fn hash<H:Hasher>(&self,state:&mut H){
        match self.kind{Kind::Le=>0u8,Kind::Eq=>1,Kind::Int=>2}.hash(state);
        self.expression.constant.hash(state);self.expression.terms.hash(state);
    }
}
fn insert(index:&mut HashMap<Key,Ref>,fact:AuthoringFact)->Result<(),String>{
    index.try_reserve(1).map_err(|_|resource())?;
    index.insert(Key{kind:fact.kind,expression:fact.expression},fact.reference);Ok(())
}
fn base_fact(input:&Model,integers:bool,reference:&Ref)->Result<AuthoringFact,String>{
    let bad=||invalid("unavailable source-model reference");
    let (kind,expression)=match reference {
        Ref::VarLower(i)=>{let v=input.vars.get(*i as usize).ok_or_else(bad)?;let mut e=Expr::var(*i).scaled(&(-Q::one()))?;e.constant=v.lower.clone().ok_or_else(bad)?;(Kind::Le,e)},
        Ref::VarUpper(i)=>{let v=input.vars.get(*i as usize).ok_or_else(bad)?;let mut e=Expr::var(*i);e.constant=-v.upper.clone().ok_or_else(bad)?;(Kind::Le,e)},
        Ref::VarInt(i)=>{let v=input.vars.get(*i as usize).ok_or_else(bad)?;if !integers||!v.integer{return Err(bad());}(Kind::Int,Expr::var(*i))},
        Ref::RowLower(i)=>{let row=input.rows.get(*i as usize).ok_or_else(bad)?;let mut e=row.expr.scaled(&(-Q::one()))?;e.constant+=row.lower.clone().ok_or_else(bad)?;(Kind::Le,e)},
        Ref::RowUpper(i)=>{let row=input.rows.get(*i as usize).ok_or_else(bad)?;let mut e=row.expr.clone();e.constant-=row.upper.clone().ok_or_else(bad)?;(Kind::Le,e)},
        Ref::RowEq(i)=>{let row=input.rows.get(*i as usize).ok_or_else(bad)?;let b=row.lower.as_ref().ok_or_else(bad)?;if row.upper.as_ref()!=Some(b){return Err(bad());}let mut e=row.expr.clone();e.constant-=b;(Kind::Eq,e)},
        _=>return Err(bad()),
    };
    expression.validate(input.vars.len())?;Ok(AuthoringFact{kind,expression,reference:reference.clone()})
}
fn source_index(input:&Model,integers:bool)->Result<HashMap<Key,Ref>,String>{
    let mut index=HashMap::new();
    for (i,v) in input.vars.iter().enumerate(){
        if v.lower.is_some(){insert(&mut index,base_fact(input,integers,&Ref::VarLower(i as u32))?)?;}
        if v.upper.is_some(){insert(&mut index,base_fact(input,integers,&Ref::VarUpper(i as u32))?)?;}
        if v.integer&&integers{insert(&mut index,base_fact(input,integers,&Ref::VarInt(i as u32))?)?;}
    }
    for (i,row) in input.rows.iter().enumerate(){
        if row.lower.is_some()&&row.lower==row.upper{insert(&mut index,base_fact(input,integers,&Ref::RowEq(i as u32))?)?;}
        else{
            if row.lower.is_some(){insert(&mut index,base_fact(input,integers,&Ref::RowLower(i as u32))?)?;}
            if row.upper.is_some(){insert(&mut index,base_fact(input,integers,&Ref::RowUpper(i as u32))?)?;}
        }
    }Ok(index)
}
fn exact(input:&Model,integers:bool,kind:Kind,e:&Expr)->bool{
    match kind{
        Kind::Eq=>e.terms.is_empty()&&e.constant.is_zero(),
        Kind::Le=>e.terms.is_empty()&&!e.constant.is_positive(),
        Kind::Int=>e.constant.is_integer()&&e.terms.iter().all(|(i,c)|c.is_integer()&&integers&&input.vars[*i as usize].integer),
    }
}
fn label(obligation:&ReturnObligation)->String{
    let origin=&obligation.origin;let mut label=origin.kind.clone();
    if let Some(name)=&origin.name{label.push('[');label.push_str(name);label.push(']');}
    else if let Some(index)=origin.index{label.push_str(&format!("[{index}]"));}
    label
}
fn validate_fact(input:&Model,integers:bool,fact:&AuthoringFact,local_only:bool)->Result<(),String>{
    fact.expression.validate(input.vars.len())?;
    match &fact.reference{
        Ref::Local(_)|Ref::Assumption(_)=>Ok(()),
        Ref::Exact=>Err(invalid("Exact must be a terminal assignment string")),
        _ if local_only=>Err(invalid("facts must reference visible Local or Assumption handles")),
        _=>{let actual=base_fact(input,integers,&fact.reference)?;
            if actual.kind!=fact.kind||actual.expression!=fact.expression{return Err(invalid("assignment source fact mismatch"));}Ok(())},
    }
}

pub fn resolve_return_json(input:&Model,output:&Model,text:&str,limits:&Limits)->Result<ResolveResult,String>{
    if text.len()>MAX_JSON_BYTES{return Err("RESOURCE_LIMIT resolve Return JSON bytes".into());}
    let spec:ResolveReturn=serde_json::from_str(text).map_err(|e|json_error("resolve Return JSON",e))?;
    resolve_return(input,output,spec,limits)
}
/// Reuse exact propositions only. Caller-supplied local expressions are
/// untrusted metadata; this function does not execute or validate proof steps.
pub fn resolve_return(input:&Model,output:&Model,spec:ResolveReturn,limits:&Limits)->Result<ResolveResult,String>{
    input.validate()?;output.validate()?;
    let integers=true;
    let mut facts=if spec.auto{source_index(input,integers)?}else{HashMap::new()};
    for fact in spec.facts{
        validate_fact(input,integers,&fact,true)?;if spec.auto{insert(&mut facts,fact)?;}
    }
    let mut by_index=HashMap::new();let mut by_label=HashMap::new();
    by_index.try_reserve(spec.assignments.len()).map_err(|_|resource())?;
    by_label.try_reserve(spec.assignments.len()).map_err(|_|resource())?;
    let mut used=Vec::new();used.try_reserve(spec.assignments.len()).map_err(|_|resource())?;
    used.resize(spec.assignments.len(),false);
    for (i,assignment) in spec.assignments.iter().enumerate(){
        if let AssignmentFact::Fact(fact)=&assignment.fact{validate_fact(input,integers,fact,false)?;}
        match (&assignment.index,&assignment.label){
            (Some(index),None)=>{if by_index.insert(*index,i).is_some(){return Err(invalid("duplicate assignment index"));}},
            (None,Some(label))=>{if by_label.insert(label.as_str(),i).is_some(){return Err(invalid("duplicate assignment label"));}},
            _=>return Err(invalid("assignment requires exactly one index or label selector")),
        }
    }
    let mut result=ResolveResult{checks:Vec::new(),missing:Vec::new(),unknown_assignments:Vec::new(),obligations:0};
    visit_return(input,output,&spec.plan,limits,|obligation|{
        let index=result.obligations;result.obligations+=1;
        let indexed=by_index.get(&index).copied();
        let named=if by_label.is_empty(){None}else{by_label.get(label(&obligation).as_str()).copied()};
        if indexed.is_some()&&named.is_some(){return Err(invalid(format!("duplicate assignment for obligation {index}")));}
        let original_kind=obligation.kind;
        let mut key=Key{kind:original_kind,expression:obligation.expression};
        let check=if let Some(assignment)=indexed.or(named){
            used[assignment]=true;
            match &spec.assignments[assignment].fact{
                AssignmentFact::Exact=>{if !exact(input,integers,original_kind,&key.expression){return Err(invalid(format!("non-tautological Exact assignment for obligation {index}")));}Some(Ref::Exact)},
                AssignmentFact::Fact(fact)=>{
                    if (fact.kind!=original_kind&&fact.kind!=Kind::Eq)||fact.expression!=key.expression{return Err(invalid(format!("assignment proposition mismatch for obligation {index}")));}
                    Some(fact.reference.clone())
                },
            }
        }else if spec.auto{
            if exact(input,integers,original_kind,&key.expression){Some(Ref::Exact)}
            else{let found=facts.get(&key).cloned();if found.is_some(){found}else{key.kind=Kind::Eq;facts.get(&key).cloned()}}
        }else{None};
        if check.is_none(){
            result.missing.try_reserve(1).map_err(|_|resource())?;
            result.missing.push(MissingObligation{index,obligation:ReturnObligation{kind:original_kind,expression:key.expression,origin:obligation.origin}});
        }
        result.checks.try_reserve(1).map_err(|_|resource())?;result.checks.push(check);Ok(())
    })?;
    for (i,assignment) in spec.assignments.iter().enumerate(){
        if !used[i]{return Err(invalid(format!("unknown assignment {}",assignment.label.as_deref().map(str::to_owned).unwrap_or_else(||assignment.index.unwrap().to_string()))));}
    }Ok(result)
}
