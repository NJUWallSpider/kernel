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
    /// Create one variable between lower and upper in an extended child. because proves lower-upper <= 0; None requests literal truth only. Return LiftResult; success fixes the parent, failure leaves it editable.
    ///
    /// ## Parameters
    /// lower: Affine
    /// upper: Affine
    /// because: Fact | None
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
    /// Apply ordered IntervalSpec inputs atomically and return LiftResult. See IntervalSpec for lower-major premise ordering and Generated for fields.
    ///
    /// ## Parameters
    /// specs: Iterable[Any]
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
    /// Apply ordered MenuSpec inputs atomically and return LiftResult. Six ordered premises are required per item; see MenuSpec.
    ///
    /// ## Parameters
    /// specs: Iterable[Any]
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
    /// Apply ordered SignedSpec inputs atomically and return LiftResult. Five ordered premises are required per item; see SignedSpec.
    ///
    /// ## Parameters
    /// specs: Iterable[Any]
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
    /// Apply FlowSpec with explicit graph and group witnesses; return LiftResult. See FlowGroup for arc/node ordering and Generated for commodity fields.
    ///
    /// ## Parameters
    /// spec: Any
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
    /// Apply SubflowSpec with explicit graph and group witnesses; return LiftResult. See SubflowGroup for arc/node ordering and Generated for remainder fields.
    ///
    /// ## Parameters
    /// spec: Any
    ///
    /// ## Returns
    /// LiftResult
    ///
    /// ## Requirements and errors
    /// The scope must be editable; facts must be visible and belong to this Proof. Wrong ownership raises ScopeError or CoordinateSpaceError. Invalid selected witnesses raise InvalidDerivationError. See the owning class for lifecycle rules.
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
/// A successful constructive extension. scope is the editable extended child; parent is fixed. Indexing yields family-specific Generated records. variable is a convenience only for a single Interval item; otherwise it raises TypeError. Example: lift = scope.lift_interval(lower=0, upper=1); lift.scope.map(default="same_name").finish().
///
/// ## Operators
/// __getitem__: Return family-specific Generated record at a nonnegative index; out-of-range raises IndexError.
/// __len__: Return generated item/group count.
#[pyclass(name = "LiftResult", module = "rpx", frozen)]
pub struct LiftResult {
    pub scope: PyScope,
}
#[pymethods]
impl LiftResult {
    #[getter]
    /// The editable child Scope created by this lift.
    ///
    /// ## Example
    /// lift.scope
    fn scope(&self) -> PyScope {
        self.scope.clone()
    }
    #[getter]
    /// The generated VarRef for a single Interval lift; other layouts raise TypeError.
    ///
    /// ## Example
    /// lift.variable
    fn variable(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if self.__len__()? != 1 {
            return Err(PyTypeError::new_err(
                "select an interval before requesting its variable",
            ));
        }
        self.__getitem__(0)?.__getattr__(py, "variable")
    }
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> PyResult<usize> {
        Ok(lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .layout
            .as_ref()
            .unwrap()
            .len())
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
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
/// A native layout record returned by lift[index]. Available fields depend on the construction; unavailable fields raise AttributeError. Variables belong to the child coordinate space and cannot escape to parents or sibling extensions. Fact fields belong to the same Proof. See Fields for the exact per-family layout.
///
/// ## Fields
/// variable: Interval only: generated VarRef.
/// lower_rows: Interval only: Le facts L[i]-variable in lower input order.
/// upper_rows: Interval only: Le facts variable-U[j] in upper input order.
/// options: Menu only: K+1 binary VarRef values in option-index order.
/// sum: Menu only: Eq(sum(options)-activation).
/// moment: Menu only: Eq(sum(j*options[j])-index).
/// positive: Signed only: nonnegative positive-flow VarRef.
/// negative: Signed only: nonnegative negative-flow VarRef.
/// positive_activation: Signed only: binary positive activation VarRef.
/// negative_activation: Signed only: binary negative activation VarRef.
/// flow: Signed only: Eq(positive-negative-input_flow).
/// activation: Signed only: Eq(positive_activation+negative_activation-input_activation).
/// positive_capacity: Signed only: Le(positive-capacity*positive_activation).
/// negative_capacity: Signed only: Le(negative-capacity*negative_activation).
/// source: Flow/Subflow group only: source node index.
/// sink: Flow commodity only: sink node index.
/// demand: Flow commodity only: exact demand Q.
/// flows: Flow commodity or Subflow group: generated VarRef sequence in arc order.
/// commodities: Flow group only: Generated records in input commodity order.
/// balances: Flow commodity or Subflow group: Eq conservation facts in node order.
/// recovery: Flow group only: Eq(sum(commodity flows)-input flow) per arc.
/// remainder_nonnegative: Subflow group only: Le(generated flow-input flow) per arc.
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
