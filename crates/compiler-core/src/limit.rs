//! Shared finite budgets for the native authoring core.
use kernel_core::model::{Expr, MAX_TERMS};

pub fn invalid(message: impl Into<String>) -> String {
    format!("INVALID {}", message.into())
}

pub fn resource(message: impl Into<String>) -> String {
    format!("RESOURCE_LIMIT {}", message.into())
}

pub fn check_terms(expressions: &[&Expr]) -> Result<(), String> {
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
