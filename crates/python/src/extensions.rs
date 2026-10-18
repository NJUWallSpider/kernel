//! Typed extension specifications are lowered only after all parent premises check.
use crate::{
    errors::{InvalidDerivationError, err},
    inspection::json_py,
    numbers::{PyQ, scalar},
    proofs::{PyFact, PyScope, lock},
};
use kernel_compiler_core::model::{Identifier, Model};
use kernel_core::{
    authoring::Extension,
    model::{Expr, Q},
    proof::{
        FlowGroup, FlowWitness, IntervalWitness, MenuWitness, Ref, SignedWitness, SubflowGroup,
        SubflowWitness,
    },
    verify::Limits,
};
use pyo3::{
    exceptions::{PyAttributeError, PyIndexError, PyTypeError},
    prelude::*,
};
fn exprs(scope: &PyScope, value: &Bound<'_, PyAny>) -> PyResult<Vec<Expr>> {
    value.try_iter()?.map(|v| scope.raw_expr(&v?)).collect()
}
fn refs(scope: &PyScope, value: &Bound<'_, PyAny>) -> PyResult<Vec<Ref>> {
    value
        .try_iter()?
        .map(|v| {
            let v = v?;
            if v.is_none() {
                return Ok(Ref::Exact);
            }
            let f = v.extract::<PyRef<'_, PyFact>>()?;
            let id = scope.fact_id(&f)?;
            Ok(lock(&scope.core)?.fact(id).map_err(err)?.reference.clone())
        })
        .collect()
}
fn copy_extension(e: &Extension) -> Extension {
    match e {
        Extension::Interval(v) => Extension::Interval(v.clone()),
        Extension::Menu(v) => Extension::Menu(v.clone()),
        Extension::Signed(v) => Extension::Signed(v.clone()),
        Extension::Flow(v) => Extension::Flow(v.clone()),
        Extension::Subflow(v) => Extension::Subflow(v.clone()),
    }
}
impl PyScope {
    fn extension(&self, extension: Extension) -> PyResult<LiftResult> {
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        let model = c.scope(self.id).map_err(err)?.model.clone();
        let prepared = kernel_core::authoring::prepare_extension(
            &model.inner,
            copy_extension(&extension),
            &Limits::default(),
        )
        .map_err(crate::errors::kernel_err)?;
        for premise in &prepared.premises {
            let valid = c
                .check_witness(
                    self.id,
                    &premise.reference,
                    premise.kind,
                    &premise.expression,
                )
                .map_err(err)?;
            if !valid {
                return Err(InvalidDerivationError::new_err(format!(
                    "lift premise is unproved: {}",
                    kernel_compiler_core::space::pretty(&premise.expression, Some(&model.space))
                )));
            }
        }
        let child_model = Model::from_kernel(prepared.model).map_err(err)?;
        let layout = prepared
            .layout
            .as_array()
            .cloned()
            .ok_or_else(|| InvalidDerivationError::new_err("invalid generated layout"))?;
        let child = c
            .install_lift_extension(self.id, child_model, extension)
            .map_err(err)?;
        c.scope_mut(child).map_err(err)?.layout = Some(layout);
        Ok(LiftResult {
            scope: Self {
                core: self.core.clone(),
                id: child,
            },
        })
    }
}
#[pymethods]
impl PyScope {
    #[pyo3(signature=(*,lower,upper,because=None))]
    fn lift_interval(
        &self,
        lower: &Bound<'_, PyAny>,
        upper: &Bound<'_, PyAny>,
        because: Option<&PyFact>,
    ) -> PyResult<LiftResult> {
        let reference = if let Some(f) = because {
            let id = self.fact_id(f)?;
            lock(&self.core)?.fact(id).map_err(err)?.reference.clone()
        } else {
            Ref::Exact
        };
        self.extension(Extension::Interval(vec![IntervalWitness {
            lower: vec![self.raw_expr(lower)?],
            upper: vec![self.raw_expr(upper)?],
            checks: vec![reference],
        }]))
    }
    fn lift_intervals(&self, specs: &Bound<'_, PyAny>) -> PyResult<LiftResult> {
        let mut values = vec![];
        for s in specs.try_iter()? {
            let s = s?;
            values.push(IntervalWitness {
                lower: exprs(self, &s.getattr("lower")?)?,
                upper: exprs(self, &s.getattr("upper")?)?,
                checks: refs(self, &s.getattr("because")?)?,
            });
        }
        self.extension(Extension::Interval(values))
    }
    fn lift_menus(&self, specs: &Bound<'_, PyAny>) -> PyResult<LiftResult> {
        let mut values = vec![];
        for s in specs.try_iter()? {
            let s = s?;
            values.push(MenuWitness {
                maximum_index: s.getattr("maximum_index")?.extract()?,
                activation: self.raw_expr(&s.getattr("activation")?)?,
                index: self.raw_expr(&s.getattr("index")?)?,
                checks: refs(self, &s.getattr("because")?)?,
            });
        }
        self.extension(Extension::Menu(values))
    }
    fn lift_signed(&self, specs: &Bound<'_, PyAny>) -> PyResult<LiftResult> {
        let mut values = vec![];
        for s in specs.try_iter()? {
            let s = s?;
            values.push(SignedWitness {
                capacity: scalar(&s.getattr("capacity")?)?,
                flow: self.raw_expr(&s.getattr("flow")?)?,
                activation: self.raw_expr(&s.getattr("activation")?)?,
                checks: refs(self, &s.getattr("because")?)?,
            });
        }
        self.extension(Extension::Signed(values))
    }
    fn lift_flow(&self, spec: &Bound<'_, PyAny>) -> PyResult<LiftResult> {
        let nodes = spec.getattr("nodes")?.extract()?;
        let arcs = spec.getattr("arcs")?.extract::<Vec<(u32, u32)>>()?;
        let mut groups = vec![];
        for g in spec.getattr("groups")?.try_iter()? {
            let g = g?;
            groups.push(FlowGroup {
                source: g.getattr("source")?.extract()?,
                commodities: pairs(&g.getattr("commodities")?)?,
                flows: exprs(self, &g.getattr("flows")?)?,
                nonnegative: refs(self, &g.getattr("nonnegative")?)?,
                balances: refs(self, &g.getattr("balances")?)?,
            });
        }
        self.extension(Extension::Flow(FlowWitness {
            nodes,
            arcs,
            groups,
        }))
    }
    fn lift_subflow(&self, spec: &Bound<'_, PyAny>) -> PyResult<LiftResult> {
        let nodes = spec.getattr("nodes")?.extract()?;
        let arcs = spec.getattr("arcs")?.extract::<Vec<(u32, u32)>>()?;
        let mut groups = vec![];
        for g in spec.getattr("groups")?.try_iter()? {
            let g = g?;
            groups.push(SubflowGroup {
                source: g.getattr("source")?.extract()?,
                demands: pairs(&g.getattr("demands")?)?,
                flows: exprs(self, &g.getattr("flows")?)?,
                nonnegative: refs(self, &g.getattr("nonnegative")?)?,
                balances: refs(self, &g.getattr("balances")?)?,
            });
        }
        self.extension(Extension::Subflow(SubflowWitness {
            nodes,
            arcs,
            groups,
        }))
    }
}
fn pairs(v: &Bound<'_, PyAny>) -> PyResult<Vec<(u32, Q)>> {
    v.try_iter()?
        .map(|p| {
            let p = p?;
            Ok((p.get_item(0)?.extract()?, scalar(&p.get_item(1)?)?))
        })
        .collect()
}
#[pyclass(name = "LiftResult", module = "rpx", frozen)]
pub struct LiftResult {
    pub scope: PyScope,
}
#[pymethods]
impl LiftResult {
    #[getter]
    fn scope(&self) -> PyScope {
        self.scope.clone()
    }
    #[getter]
    fn variable(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if self.__len__()? != 1 {
            return Err(PyTypeError::new_err(
                "select an interval before requesting its variable",
            ));
        }
        self.__getitem__(0)?.__getattr__(py, "variable")
    }
    fn __len__(&self) -> PyResult<usize> {
        Ok(lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .layout
            .as_ref()
            .unwrap()
            .len())
    }
    fn __getitem__(&self, index: usize) -> PyResult<Generated> {
        let c = lock(&self.scope.core)?;
        let data = c
            .scope(self.scope.id)
            .map_err(err)?
            .layout
            .as_ref()
            .unwrap()
            .get(index)
            .cloned()
            .ok_or_else(|| PyIndexError::new_err("generated instance index"))?;
        Ok(Generated {
            scope: self.scope.clone(),
            data,
        })
    }
}
#[pyclass(name = "Generated", module = "rpx", frozen)]
pub struct Generated {
    scope: PyScope,
    data: serde_json::Value,
}
#[pymethods]
impl Generated {
    fn __getattr__(&self, py: Python<'_>, name: &str) -> PyResult<Py<PyAny>> {
        let aliases = [
            ("sum", "sum_row"),
            ("moment", "moment_row"),
            ("flow", "flow_row"),
            ("activation", "activation_row"),
            ("positive_capacity", "positive_capacity_row"),
            ("negative_capacity", "negative_capacity_row"),
            ("balances", "balance_rows"),
            ("recovery", "recovery_rows"),
            ("remainder_nonnegative", "remainder_nonnegative_rows"),
        ];
        let key = aliases
            .iter()
            .find(|(a, _)| *a == name)
            .map(|(_, b)| *b)
            .unwrap_or(name);
        let value = self
            .data
            .get(key)
            .ok_or_else(|| PyAttributeError::new_err(name.to_string()))?;
        if key == "commodities" {
            return Ok(Py::new(
                py,
                GeneratedGroups {
                    scope: self.scope.clone(),
                    values: value.as_array().unwrap().clone(),
                },
            )?
            .into_any());
        }
        if key == "demand" {
            return Ok(Py::new(
                py,
                PyQ {
                    value: kernel_core::model::parse_q(value.as_str().unwrap()).map_err(err)?,
                },
            )?
            .into_any());
        }
        if key == "source" || key == "sink" {
            return json_py(py, value);
        }
        if let Some(i) = value.as_u64() {
            return generated_item(py, &self.scope, i as u32, key.ends_with("_row"));
        }
        if let Some(values) = value.as_array() {
            let indices = values.iter().map(|v| v.as_u64().unwrap() as u32).collect();
            return Ok(Py::new(
                py,
                GeneratedSelection {
                    scope: self.scope.clone(),
                    indices,
                    rows: key.ends_with("_rows"),
                },
            )?
            .into_any());
        }
        Err(PyAttributeError::new_err(name.to_string()))
    }
}
fn generated_item(py: Python<'_>, scope: &PyScope, i: u32, row: bool) -> PyResult<Py<PyAny>> {
    let mut c = lock(&scope.core)?;
    let model = c.scope(scope.id).map_err(err)?.model.clone();
    if row {
        let r = &model.inner.rows[i as usize];
        let tag = if r.lower.is_some() && r.lower == r.upper {
            "RowEq"
        } else if r.upper.is_some() {
            "RowUpper"
        } else {
            "RowLower"
        };
        let id = c
            .ref_fact(scope.id, tag, &Identifier::Index(i))
            .map_err(err)?;
        Ok(Py::new(py, scope.new_fact(id))?.into_any())
    } else {
        Ok(crate::models::variable(
            py,
            model.space.clone(),
            i,
            model.inner.vars[i as usize].clone(),
        )?
        .into_any())
    }
}
#[pyclass(module = "rpx", frozen)]
struct GeneratedSelection {
    scope: PyScope,
    indices: Vec<u32>,
    rows: bool,
}
#[pymethods]
impl GeneratedSelection {
    fn __len__(&self) -> usize {
        self.indices.len()
    }
    fn __getitem__(&self, py: Python<'_>, index: usize) -> PyResult<Py<PyAny>> {
        generated_item(
            py,
            &self.scope,
            *self
                .indices
                .get(index)
                .ok_or_else(|| PyIndexError::new_err("generated coordinate index"))?,
            self.rows,
        )
    }
}
#[pyclass(module = "rpx", frozen)]
struct GeneratedGroups {
    scope: PyScope,
    values: Vec<serde_json::Value>,
}
#[pymethods]
impl GeneratedGroups {
    fn __len__(&self) -> usize {
        self.values.len()
    }
    fn __getitem__(&self, index: usize) -> PyResult<Generated> {
        Ok(Generated {
            scope: self.scope.clone(),
            data: self
                .values
                .get(index)
                .cloned()
                .ok_or_else(|| PyIndexError::new_err("commodity index"))?,
        })
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<LiftResult>()?;
    m.add_class::<Generated>()?;
    Ok(())
}
