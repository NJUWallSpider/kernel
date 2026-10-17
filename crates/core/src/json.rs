//! Exact scalar and term helpers shared by the structured JSON schema.
use crate::model::{Q, parse_q};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

pub mod scalar {
    use super::*;
    pub fn serialize<S: Serializer>(q: &Q, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&q.to_string())
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<Q, D::Error> {
        let s = String::deserialize(d)?;
        parse_q(&s).map_err(serde::de::Error::custom)
    }
}

#[allow(dead_code)]
pub mod option_scalar {
    use super::*;
    pub fn serialize<S: Serializer>(q: &Option<Q>, s: S) -> Result<S::Ok, S::Error> {
        q.as_ref().map(ToString::to_string).serialize(s)
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<Option<Q>, D::Error> {
        Option::<String>::deserialize(d)?
            .map(|s| parse_q(&s).map_err(serde::de::Error::custom))
            .transpose()
    }
}

pub mod expr_terms {
    use super::*;
    pub fn serialize<S: Serializer>(terms: &[(u32, Q)], s: S) -> Result<S::Ok, S::Error> {
        terms
            .iter()
            .map(|(i, q)| (*i, q.to_string()))
            .collect::<Vec<_>>()
            .serialize(s)
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<Vec<(u32, Q)>, D::Error> {
        Vec::<(u32, String)>::deserialize(d)?
            .into_iter()
            .map(|(i, s)| {
                parse_q(&s)
                    .map(|q| (i, q))
                    .map_err(serde::de::Error::custom)
            })
            .collect()
    }
}
