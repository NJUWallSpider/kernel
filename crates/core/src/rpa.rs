//! Versioned RPA: header followed by a JSON proof object with exact scalars.
use crate::model::{parse_q,Q};
use crate::proof::{Certificate,Ref};
use serde::{Deserialize,Deserializer,Serialize,Serializer};

pub mod scalar {
    use super::*;
    pub fn serialize<S:Serializer>(q:&Q,s:S)->Result<S::Ok,S::Error>{s.serialize_str(&q.to_string())}
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<Q,D::Error>{let s=String::deserialize(d)?;parse_q(&s).map_err(serde::de::Error::custom)}
}
pub mod option_scalar {
    use super::*;
    pub fn serialize<S:Serializer>(q:&Option<Q>,s:S)->Result<S::Ok,S::Error>{q.as_ref().map(ToString::to_string).serialize(s)}
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<Option<Q>,D::Error>{Option::<String>::deserialize(d)?.map(|s|parse_q(&s).map_err(serde::de::Error::custom)).transpose()}
}
pub mod scalar_vec {
    use super::*;
    pub fn serialize<S:Serializer>(values:&[Q],s:S)->Result<S::Ok,S::Error>{values.iter().map(ToString::to_string).collect::<Vec<_>>().serialize(s)}
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<Vec<Q>,D::Error>{Vec::<String>::deserialize(d)?.into_iter().map(|s|parse_q(&s).map_err(serde::de::Error::custom)).collect()}
}
pub mod expr_terms {
    use super::*;
    pub fn serialize<S:Serializer>(terms:&[(u32,Q)],s:S)->Result<S::Ok,S::Error>{terms.iter().map(|(i,q)|(*i,q.to_string())).collect::<Vec<_>>().serialize(s)}
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<Vec<(u32,Q)>,D::Error>{Vec::<(u32,String)>::deserialize(d)?.into_iter().map(|(i,s)|parse_q(&s).map(|q|(i,q)).map_err(serde::de::Error::custom)).collect()}
}
pub mod ref_terms {
    use super::*;
    pub fn serialize<S:Serializer>(terms:&[(Ref,Q)],s:S)->Result<S::Ok,S::Error>{terms.iter().map(|(r,q)|(r,q.to_string())).collect::<Vec<_>>().serialize(s)}
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<Vec<(Ref,Q)>,D::Error>{Vec::<(Ref,String)>::deserialize(d)?.into_iter().map(|(r,s)|parse_q(&s).map(|q|(r,q)).map_err(serde::de::Error::custom)).collect()}
}
fn json_error(context:&str,error:serde_json::Error)->String {
    let message=error.to_string();
    // Keep serde's bounded parser. Exhausting its nesting capacity is not a
    // mathematical rejection and must retain the resource-limit outcome.
    let resource=message.contains("RESOURCE_LIMIT") || message.starts_with("recursion limit exceeded at line ");
    format!("{} {context}: {message}",if resource {"RESOURCE_LIMIT"}else{"INVALID"})
}
pub fn assemble(text:&str)->Result<Certificate,String>{
    if text.len()>256*1024*1024{return Err("RESOURCE_LIMIT RPA bytes".into());}
    let (version,body)=if let Some(body)=text.strip_prefix("RPA 1\n"){(1,body)}else if let Some(body)=text.strip_prefix("RPA 2\n"){(2,body)}else if let Some(body)=text.strip_prefix("RPA 3\n"){(3,body)}else if let Some(body)=text.strip_prefix("RPA 4\n"){(4,body)}else if let Some(body)=text.strip_prefix("RPA 5\n"){(5,body)}else if let Some(body)=text.strip_prefix("RPA 6\n"){(6,body)}else if let Some(body)=text.strip_prefix("RPA 7\n"){(7,body)}else if let Some(body)=text.strip_prefix("RPA 8\n"){(8,body)}else if let Some(body)=text.strip_prefix("RPA 9\n"){(9,body)}else if let Some(body)=text.strip_prefix("RPA 10\n"){(10,body)}else{return Err("INVALID RPA version/header".into())};
    let c:Certificate=serde_json::from_str(body).map_err(|e|json_error("RPA",e))?;
    if crate::codec::certificate_version(&c)?>version{return Err("INVALID RPA version does not allow requested extension".into());}
    Ok(c)
}
pub fn disassemble(c:&Certificate)->Result<String,String>{let version=crate::codec::certificate_version(c)?;serde_json::to_string_pretty(c).map(|s|format!("RPA {version}\n{s}\n")).map_err(|e|format!("INVALID RPA output: {e}"))}

/// Caller-owned contracts may use the legacy claim array or a V3 request object.
pub fn parse_request(text:&str)->Result<crate::proof::Request,String>{
    if text.len()>256*1024*1024{return Err("RESOURCE_LIMIT request bytes".into());}
    let parsed=if text.trim_start().starts_with('['){
        serde_json::from_str::<Vec<crate::proof::Claim>>(text).map(|claims|crate::proof::Request { improvements:vec![], bijections:vec![],claims,points:vec![]})
    }else{serde_json::from_str::<crate::proof::Request>(text)};
    parsed.map_err(|e|json_error("request",e))
}
