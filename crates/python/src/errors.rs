use kernel_compiler_core::error::Error;
use pyo3::{create_exception, exceptions::PyValueError, prelude::*};
create_exception!(rpx, CompilerError, PyValueError);
create_exception!(rpx, CoordinateSpaceError, CompilerError);
create_exception!(rpx, ScopeError, CompilerError);
create_exception!(rpx, MappingError, CompilerError);
create_exception!(rpx, InvalidDerivationError, CompilerError);
create_exception!(rpx, UnprovedGoalError, CompilerError);
create_exception!(rpx, ResourceLimitError, CompilerError);
create_exception!(rpx, ArtifactMismatchError, CompilerError);
create_exception!(rpx, KernelRejectedError, CompilerError);
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
