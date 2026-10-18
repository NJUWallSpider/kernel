use kernel_compiler_core::error::Error;
use pyo3::{create_exception, exceptions::PyValueError, prelude::*};
create_exception!(
    rpx,
    CompilerError,
    PyValueError,
    "Base class for invalid compiler input. Inspect the specific subclass and the troubleshooting topic."
);
create_exception!(
    rpx,
    CoordinateSpaceError,
    CompilerError,
    "Expressions belong to incompatible coordinate spaces. Reacquire handles from the intended model; never rebind by name implicitly."
);
create_exception!(
    rpx,
    ScopeError,
    CompilerError,
    "Wrong Proof/scope ownership, stale Goal, sealed scope or invisible Fact. Inspect the current scope and reacquire goals after mapping replacement; rebuild sealed proofs."
);
create_exception!(
    rpx,
    MappingError,
    CompilerError,
    "Unknown output name or incomplete mapping. Supply every output coordinate or use default=\"same_name\" with explicit overrides."
);
create_exception!(
    rpx,
    InvalidDerivationError,
    CompilerError,
    "Selected premises do not prove the requested assertion. Inspect fact.kind, fact.expression and the exact goal; correct multipliers or select matching witnesses."
);
create_exception!(
    rpx,
    UnprovedGoalError,
    CompilerError,
    "finish found unresolved obligations. Inspect scope.missing(limit=20), supply selected witnesses and retry."
);
create_exception!(
    rpx,
    ResourceLimitError,
    CompilerError,
    "A configured resource budget was exhausted. Inspect report.statistics and retry verification with an explicit sufficient budget; this is not a proof rejection or certification."
);
create_exception!(
    rpx,
    ArtifactMismatchError,
    CompilerError,
    "Artifact bytes, manifest hashes, model formulation or publication destination disagree. Restore the intended inputs or publish to a fresh directory, then audit again."
);
create_exception!(
    rpx,
    KernelRejectedError,
    CompilerError,
    "Verification did not report VERIFIED. Inspect report.kernel and report.artifact_audit; never claim certification from compilation alone."
);
pub fn err(e: impl Into<Error>) -> PyErr {
    match e.into() {
        Error::Coordinate(s) => CoordinateSpaceError::new_err(s),
        Error::Scope(s) => ScopeError::new_err(s),
        Error::Mapping(s) => MappingError::new_err(s),
        Error::Derivation(s) => InvalidDerivationError::new_err(s),
        Error::Unproved(s) => UnprovedGoalError::new_err(s),
        Error::Resource(s) => ResourceLimitError::new_err(s),
        Error::Artifact(s) => ArtifactMismatchError::new_err(s),
        Error::Invalid(s) => CompilerError::new_err(s),
    }
}
pub fn kernel_err(e: kernel_core::api::Error) -> PyErr {
    match e.status() {
        kernel_core::api::Status::ResourceLimit => {
            ResourceLimitError::new_err(e.message().to_owned())
        }
        _ => InvalidDerivationError::new_err(e.message().to_owned()),
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    m.add("CompilerError", py.get_type::<CompilerError>())?;
    m.add(
        "CoordinateSpaceError",
        py.get_type::<CoordinateSpaceError>(),
    )?;
    m.add("ScopeError", py.get_type::<ScopeError>())?;
    m.add("MappingError", py.get_type::<MappingError>())?;
    m.add(
        "InvalidDerivationError",
        py.get_type::<InvalidDerivationError>(),
    )?;
    m.add("UnprovedGoalError", py.get_type::<UnprovedGoalError>())?;
    m.add("ResourceLimitError", py.get_type::<ResourceLimitError>())?;
    m.add(
        "ArtifactMismatchError",
        py.get_type::<ArtifactMismatchError>(),
    )?;
    m.add("KernelRejectedError", py.get_type::<KernelRejectedError>())?;
    Ok(())
}
