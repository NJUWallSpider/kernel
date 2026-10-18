use crate::{errors::err, inspection::json_py, models::PyModel, proofs::PyProof};
use pyo3::prelude::*;
use std::sync::{Arc, Mutex};
#[pyclass(name = "StandardMPSAdapter", module = "rpx", frozen)]
pub struct Adapter {
    inner: kernel_compiler_core::adapter::StandardMps,
}
#[pymethods]
impl Adapter {
    #[new]
    #[pyo3(signature=(source,*,objective_auxiliary=true,objective_name="__mps_objective"))]
    fn new(source: &PyModel, objective_auxiliary: bool, objective_name: &str) -> PyResult<Self> {
        Ok(Self {
            inner: kernel_compiler_core::adapter::StandardMps::new(
                source.inner.clone(),
                objective_auxiliary,
                objective_name,
            )
            .map_err(err)?,
        })
    }
    #[getter]
    fn source(&self) -> PyModel {
        PyModel {
            inner: self.inner.source.clone(),
        }
    }
    #[getter]
    fn target(&self) -> PyModel {
        PyModel {
            inner: self.inner.target.clone(),
        }
    }
    #[getter]
    fn report(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &self.inner.report)
    }
    fn native_proof(&self) -> PyResult<PyProof> {
        Ok(PyProof {
            core: Arc::new(Mutex::new(self.inner.proof().map_err(err)?)),
        })
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Adapter>()
}
