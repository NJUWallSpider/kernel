//! Exact sparse affine expression operations over the kernel representation.
use crate::error::Error;
use kernel_core::model::{Expr, Q, check_q};
use num_traits::Zero;
use std::collections::BTreeMap;

fn invalid(message: impl Into<String>) -> Error {
    Error::Invalid(message.into())
}

pub fn canonical(constant: Q, terms: impl IntoIterator<Item = (u32, Q)>) -> Result<Expr, Error> {
    check_q(&constant)?;
    let mut out = Expr {
        constant,
        terms: Vec::new(),
    };
    for (index, coefficient) in terms {
        check_q(&coefficient)?;
        out.terms.push((index, coefficient));
    }
    out.canonicalize()?;
    Ok(out)
}

pub fn add(left: &Expr, right: &Expr) -> Result<Expr, Error> {
    left.validate(u32::MAX as usize)?;
    right.validate(u32::MAX as usize)?;
    let mut terms: BTreeMap<u32, Q> = left.terms.iter().cloned().collect();
    for (index, coefficient) in &right.terms {
        *terms.entry(*index).or_insert_with(Q::zero) += coefficient;
    }
    canonical(&left.constant + &right.constant, terms)
}

pub fn neg(value: &Expr) -> Result<Expr, Error> {
    Ok(Expr {
        constant: -value.constant.clone(),
        terms: value
            .terms
            .iter()
            .map(|(index, coefficient)| (*index, -coefficient))
            .collect(),
    })
}

pub fn scale(value: &Expr, factor: &Q) -> Result<Expr, Error> {
    value.scaled(factor).map_err(Error::from)
}

pub fn subtract(left: &Expr, right: &Expr) -> Result<Expr, Error> {
    add(left, &neg(right)?)
}

pub fn substitute(value: &Expr, replacements: &[Option<Expr>]) -> Result<Expr, Error> {
    let mut constant = value.constant.clone();
    let mut terms: BTreeMap<u32, Q> = BTreeMap::new();
    for (index, coefficient) in &value.terms {
        let replacement = replacements
            .get(*index as usize)
            .and_then(|item| item.as_ref())
            .cloned()
            .unwrap_or_else(|| Expr::var(*index));
        constant += coefficient * &replacement.constant;
        for (new_index, new_coefficient) in replacement.terms {
            *terms.entry(new_index).or_insert_with(Q::zero) += coefficient * new_coefficient;
        }
    }
    canonical(constant, terms)
}

pub fn evaluate(value: &Expr, values: &[Option<Q>]) -> Result<Q, Error> {
    let mut result = value.constant.clone();
    for (index, coefficient) in &value.terms {
        let item = values
            .get(*index as usize)
            .and_then(|item| item.as_ref())
            .ok_or_else(|| invalid("missing coordinate in evaluation"))?;
        result += coefficient * item;
    }
    Ok(result)
}
