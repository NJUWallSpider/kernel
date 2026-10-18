//! Thin Python bindings. All proof state and mathematics live in Rust.
mod adapter;
mod errors;
mod expressions;
mod extensions;
mod inspection;
mod models;
mod numbers;
mod proofs;
use pyo3::prelude::*;
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    errors::register(m)?;
    numbers::register(m)?;
    expressions::register(m)?;
    models::register(m)?;
    proofs::register(m)?;
    extensions::register(m)?;
    inspection::register(m)?;
    adapter::register(m)?;
    Ok(())
}
