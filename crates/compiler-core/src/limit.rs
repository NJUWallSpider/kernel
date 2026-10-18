//! Shared finite budgets for the native authoring core.
use crate::error::Error;
use kernel_core::model::{Expr, MAX_TERMS};

pub fn invalid(message: impl Into<String>) -> Error {
    Error::Invalid(message.into())
}

pub fn resource(message: impl Into<String>) -> Error {
    Error::Resource(message.into())
}

pub fn check_terms(expressions: &[&Expr]) -> Result<(), Error> {
    let mut total = 0usize;
    for expression in expressions {
        total = total
            .checked_add(expression.terms.len())
            .ok_or_else(|| resource("model term count overflow"))?;
        if total > MAX_TERMS {
            return Err(resource("model term budget"));
        }
    }
    Ok(())
}
