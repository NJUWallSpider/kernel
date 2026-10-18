use crate::{
    errors::{ScopeError, err},
    expressions::{PyExpr, bound, in_space},
    inspection::json_py,
    numbers::{PyQ, optional},
};
use kernel_compiler_core::{
    model::{Identifier, Model, ModelFormat, row_from_parts, var_from_parts},
    space::Space,
};
use kernel_core::model::{Expr, Q, Var};
use num_traits::{One, Zero};
use pyo3::{
    exceptions::{PyIndexError, PyKeyError, PyOSError, PyTypeError},
    prelude::*,
    types::{PyBool, PyInt},
};
use std::{
    collections::{HashMap, HashSet},
    path::{Path, PathBuf},
    sync::Arc,
};
/// An immutable exact model. Use Model.read(path) for LP, MPS or MCM, or ModelBuilder for construction. Edits return a new model with a new coordinate identity, even if names match. Example: model.vars["x"]. Inspect native views before materializing data.
#[pyclass(name = "Model", module = "rpx", frozen, from_py_object)]
#[derive(Clone)]
pub struct PyModel {
    pub inner: Arc<Model>,
}
pub fn index(model: &Model, v: &Bound<'_, PyAny>, row: bool) -> PyResult<u32> {
    if v.is_instance_of::<PyBool>() {
        return Err(PyTypeError::new_err("bool is not a coordinate"));
    }
    let id = if let Ok(name) = v.extract::<String>() {
        Identifier::Name(name)
    } else if v.is_instance_of::<PyInt>() {
        Identifier::Index(v.extract::<u32>()?)
    } else if !row && v.is_instance_of::<PyExpr>() {
        let e = in_space(v, &model.space)?;
        if !e.constant.is_zero() || e.terms.len() != 1 || !e.terms[0].1.is_one() {
            return Err(PyTypeError::new_err("expected one variable"));
        }
        Identifier::Index(e.terms[0].0)
    } else {
        return Err(PyTypeError::new_err("expected row name or index"));
    };
    model.index(&id, row).map_err(|e| {
        let e = e.to_string();
        if e.starts_with("unknown") {
            PyKeyError::new_err(e)
        } else {
            PyIndexError::new_err(e)
        }
    })
}
pub fn read(path: &Path) -> PyResult<PyModel> {
    let bytes = std::fs::read(path).map_err(|e| PyOSError::new_err(e.to_string()))?;
    let format = if bytes.starts_with(b"MCM\0") {
        ModelFormat::Mcm
    } else {
        match path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase()
            .as_str()
        {
            "lp" => ModelFormat::Lp,
            "mps" => ModelFormat::Mps,
            _ => return Err(PyTypeError::new_err("Model.read accepts MCM, LP, or MPS")),
        }
    };
    Ok(PyModel {
        inner: Arc::new(Model::parse_bytes(&bytes, format).map_err(err)?),
    })
}
pub fn variable(py: Python<'_>, space: Arc<Space>, i: u32, v: Var) -> PyResult<Py<PyVar>> {
    Py::new(
        py,
        (PyVar { value: v, index: i }, bound(Expr::var(i), space)),
    )
}
/// A variable expression bound to its builder or model coordinate space. Obtain it with model.vars["x"] or builder.add_var("x"); do not construct by index alone. Model edits produce a new space: obtain fresh handles from the edited model. Inherits affine arithmetic from Expr.
#[pyclass(name="VarRef",module="rpx",extends=PyExpr,frozen)]
pub struct PyVar {
    value: Var,
    index: u32,
}
#[pymethods]
impl PyVar {
    #[getter]
    /// The declared name.
    ///
    /// ## Example
    /// variable.name
    fn name(&self) -> &str {
        &self.value.name
    }
    #[getter]
    /// Whether the variable is declared integral.
    ///
    /// ## Example
    /// variable.integer
    fn integer(&self) -> bool {
        self.value.integer
    }
    #[getter]
    /// The exact lower bound, or None if unbounded.
    ///
    /// ## Example
    /// variable.lower
    fn lower(&self) -> Option<PyQ> {
        self.value.lower.clone().map(|value| PyQ { value })
    }
    #[getter]
    /// The exact upper bound, or None if unbounded.
    ///
    /// ## Example
    /// variable.upper
    fn upper(&self) -> Option<PyQ> {
        self.value.upper.clone().map(|value| PyQ { value })
    }
    #[getter]
    /// The zero-based coordinate position; this alone does not carry ownership.
    ///
    /// ## Example
    /// variable.index
    fn index(&self) -> u32 {
        self.index
    }
}
/// A native-backed variable view. Lookup by name, index or an owned VarRef; iteration wraps only visited items. Use iter(limit=20) for bounded inspection and to_list only for explicit full materialization. Example: model.vars["x"].
///
/// ## Operators
/// __getitem__: Return VarRef by variable name, index or owned VarRef. Invalid names/indices fail.
/// __len__: Return variable count without materialization.
/// __contains__: Test a variable name.
/// __iter__: Iterate VarRef values lazily.
#[pyclass(name = "VariablesView", module = "rpx", frozen)]
pub struct VariablesView {
    pub inner: Arc<Model>,
}
#[pymethods]
impl VariablesView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> usize {
        self.inner.inner.vars.len()
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
    fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<Py<PyVar>> {
        let i = index(&self.inner, key, false)?;
        variable(
            key.py(),
            self.inner.space.clone(),
            i,
            self.inner.inner.vars[i as usize].clone(),
        )
    }
    /// Test whether the view contains the supplied name.
    fn __contains__(&self, name: &str) -> bool {
        self.inner.var_index.contains_key(name)
    }
    fn __repr__(&self) -> String {
        format!("VariablesView({} variables)", self.inner.inner.vars.len())
    }
    #[pyo3(signature=(limit=None))]
    /// Return an iterator over at most limit entries; None means all. Only visited entries get Python wrappers.
    ///
    /// ## Parameters
    /// limit: int | None
    ///
    /// ## Returns
    /// Iterator[VarRef]
    ///
    /// ## Example
    /// model.vars.iter(limit=20)
    fn iter(&self, limit: Option<usize>) -> VariableIterator {
        VariableIterator {
            inner: self.inner.clone(),
            at: 0,
            end: limit
                .unwrap_or(self.inner.inner.vars.len())
                .min(self.inner.inner.vars.len()),
        }
    }
    /// Return a lazy iterator over this view. Use bounded inspection for large models.
    fn __iter__(&self) -> VariableIterator {
        self.iter(None)
    }
    /// Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.
    ///
    /// ## Returns
    /// list[VarRef]
    ///
    /// ## Example
    /// model.vars.to_list()
    fn to_list(&self, py: Python<'_>) -> PyResult<Vec<Py<PyVar>>> {
        (0..self.inner.inner.vars.len())
            .map(|i| {
                variable(
                    py,
                    self.inner.space.clone(),
                    i as u32,
                    self.inner.inner.vars[i].clone(),
                )
            })
            .collect()
    }
}
#[pyclass(module = "rpx")]
pub struct VariableIterator {
    inner: Arc<Model>,
    at: usize,
    end: usize,
}
#[pymethods]
impl VariableIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyVar>>> {
        if self.at >= self.end {
            return Ok(None);
        }
        let i = self.at;
        self.at += 1;
        variable(
            py,
            self.inner.space.clone(),
            i as u32,
            self.inner.inner.vars[i].clone(),
        )
        .map(Some)
    }
}
/// A read-only named model row, with affine expression and optional lower/upper bounds. This is model data, not a proof Fact: use scope.row(row.name) for a witness. Example: model.rows[0].expression.
#[pyclass(name = "RowRef", module = "rpx", frozen)]
pub struct RowRef {
    pub inner: Arc<Model>,
    pub index: usize,
}
#[pymethods]
impl RowRef {
    #[getter]
    /// The zero-based coordinate position; this alone does not carry ownership.
    ///
    /// ## Example
    /// row.index
    fn index(&self) -> usize {
        self.index
    }
    #[getter]
    /// The declared name.
    ///
    /// ## Example
    /// row.name
    fn name(&self) -> &str {
        &self.inner.inner.rows[self.index].name
    }
    #[getter]
    /// The exact owned affine expression.
    ///
    /// ## Example
    /// row.expression
    fn expression(&self) -> PyExpr {
        bound(
            self.inner.inner.rows[self.index].expr.clone(),
            self.inner.space.clone(),
        )
    }
    #[getter]
    /// The exact lower bound, or None if unbounded.
    ///
    /// ## Example
    /// row.lower
    fn lower(&self) -> Option<PyQ> {
        self.inner.inner.rows[self.index]
            .lower
            .clone()
            .map(|value| PyQ { value })
    }
    #[getter]
    /// The exact upper bound, or None if unbounded.
    ///
    /// ## Example
    /// row.upper
    fn upper(&self) -> Option<PyQ> {
        self.inner.inner.rows[self.index]
            .upper
            .clone()
            .map(|value| PyQ { value })
    }
    #[getter]
    /// Whether both row bounds coincide.
    ///
    /// ## Example
    /// row.equality
    fn equality(&self) -> bool {
        let r = &self.inner.inner.rows[self.index];
        r.lower.is_some() && r.lower == r.upper
    }
    fn __repr__(&self) -> String {
        format!(
            "{}: {}",
            self.name(),
            kernel_compiler_core::space::pretty(
                &self.inner.inner.rows[self.index].expr,
                Some(&self.inner.space)
            )
        )
    }
}
/// A native-backed row view indexed by name or position. Use iter(limit=20) for bounded inspection; to_list materializes every RowRef. Unknown names raise KeyError and invalid positions raise IndexError. Example: model.rows["balance"].
///
/// ## Operators
/// __getitem__: Return RowRef by name or index; unknown names/indices fail.
/// __len__: Return row count without materialization.
/// __contains__: Test a row name.
/// __iter__: Iterate RowRef values lazily.
#[pyclass(name = "RowsView", module = "rpx", frozen)]
pub struct RowsView {
    inner: Arc<Model>,
}
#[pymethods]
impl RowsView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> usize {
        self.inner.inner.rows.len()
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
    fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<RowRef> {
        Ok(RowRef {
            inner: self.inner.clone(),
            index: index(&self.inner, key, true)? as usize,
        })
    }
    /// Test whether the view contains the supplied name.
    fn __contains__(&self, name: &str) -> bool {
        self.inner.row_index.contains_key(name)
    }
    fn __repr__(&self) -> String {
        format!("RowsView({} rows)", self.inner.inner.rows.len())
    }
    #[pyo3(signature=(limit=None))]
    /// Return an iterator over at most limit entries; None means all. Only visited entries get Python wrappers.
    ///
    /// ## Parameters
    /// limit: int | None
    ///
    /// ## Returns
    /// Iterator[RowRef]
    ///
    /// ## Example
    /// model.rows.iter(limit=20)
    fn iter(&self, limit: Option<usize>) -> RowIterator {
        RowIterator {
            inner: self.inner.clone(),
            at: 0,
            end: limit
                .unwrap_or(self.inner.inner.rows.len())
                .min(self.inner.inner.rows.len()),
        }
    }
    /// Return a lazy iterator over this view. Use bounded inspection for large models.
    fn __iter__(&self) -> RowIterator {
        self.iter(None)
    }
    /// Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.
    ///
    /// ## Returns
    /// list[RowRef]
    ///
    /// ## Example
    /// model.rows.to_list()
    fn to_list(&self) -> Vec<RowRef> {
        (0..self.inner.inner.rows.len())
            .map(|index| RowRef {
                inner: self.inner.clone(),
                index,
            })
            .collect()
    }
}
#[pyclass(module = "rpx")]
pub struct RowIterator {
    inner: Arc<Model>,
    at: usize,
    end: usize,
}
#[pymethods]
impl RowIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(&mut self) -> Option<RowRef> {
        if self.at >= self.end {
            return None;
        }
        let index = self.at;
        self.at += 1;
        Some(RowRef {
            inner: self.inner.clone(),
            index,
        })
    }
}
#[pymethods]
impl PyModel {
    #[staticmethod]
    /// Read exact MCM, LP or MPS from path; return a new Model. Unknown formats raise TypeError and I/O failures raise OSError.
    ///
    /// ## Parameters
    /// path: Path
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// Model.read("model.mps")
    fn read(path: PathBuf) -> PyResult<Self> {
        read(&path)
    }
    #[getter]
    /// The declared name.
    ///
    /// ## Example
    /// model.name
    fn name(&self) -> &str {
        &self.inner.inner.name
    }
    #[getter]
    /// The native-backed input variable view.
    ///
    /// ## Example
    /// model.vars
    pub fn vars(&self) -> VariablesView {
        VariablesView {
            inner: self.inner.clone(),
        }
    }
    #[getter]
    /// The native-backed row view.
    ///
    /// ## Example
    /// model.rows
    fn rows(&self) -> RowsView {
        RowsView {
            inner: self.inner.clone(),
        }
    }
    #[getter]
    /// The exact affine minimization objective.
    ///
    /// ## Example
    /// model.objective
    fn objective(&self) -> PyExpr {
        bound(self.inner.inner.objective.clone(), self.inner.space.clone())
    }
    /// Compare exact model formulation data, independent of coordinate identity.
    ///
    /// ## Parameters
    /// other: Model
    ///
    /// ## Returns
    /// bool
    ///
    /// ## Example
    /// model.same_formulation(other_model)
    fn same_formulation(&self, other: &PyModel) -> bool {
        self.inner.same_formulation(&other.inner)
    }
    /// Return model size and sparsity statistics without materializing all rows.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// model.stats()
    fn stats(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &self.inner.stats())
    }
    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// model.to_dict()
    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &kernel_core::model::to_json(&self.inner.inner))
    }
    /// Write canonical MCM to path and return that path.
    ///
    /// ## Parameters
    /// path: Path
    ///
    /// ## Returns
    /// PathLike[str]
    ///
    /// ## Example
    /// model.write_mcm("model.mcm")
    fn write_mcm(&self, path: PathBuf) -> PyResult<PathBuf> {
        std::fs::write(&path, self.inner.to_mcm().map_err(err)?)
            .map_err(|e| PyOSError::new_err(e.to_string()))?;
        Ok(path)
    }
    #[pyo3(signature=(path,*,rational_literals=false))]
    /// Write the exact MPS representation to path and return that path. See to_mps for rational_literals.
    ///
    /// ## Parameters
    /// path: Path
    /// rational_literals: bool
    ///
    /// ## Returns
    /// PathLike[str]
    ///
    /// ## Example
    /// model.write_mps("model.mps")
    fn write_mps(&self, path: PathBuf, rational_literals: bool) -> PyResult<PathBuf> {
        std::fs::write(
            &path,
            kernel_compiler_core::model::mps(&self.inner, rational_literals).map_err(err)?,
        )
        .map_err(|e| PyOSError::new_err(e.to_string()))?;
        Ok(path)
    }
    #[pyo3(signature=(*,rational_literals=false))]
    /// Return an exact MPS string. rational_literals opts into rational literals; standard output requires representable coefficients or an explicit StandardMPSAdapter.
    ///
    /// ## Parameters
    /// rational_literals: bool
    ///
    /// ## Returns
    /// str
    ///
    /// ## Example
    /// model.to_mps()
    fn to_mps(&self, rational_literals: bool) -> PyResult<String> {
        kernel_compiler_core::model::mps(&self.inner, rational_literals).map_err(err)
    }
    fn __repr__(&self) -> String {
        let m = &self.inner.inner;
        format!(
            "Model {}\n  {} variables · {} rows · {} nonzeros\n  objective: {}",
            m.name,
            m.vars.len(),
            m.rows.len(),
            m.rows.iter().map(|r| r.expr.terms.len()).sum::<usize>(),
            kernel_compiler_core::space::pretty(&m.objective, Some(&self.inner.space))
        )
    }
    fn _repr_html_(&self) -> String {
        format!("<pre>{}</pre>", crate::inspection::html(&self.__repr__()))
    }
    /// Return a new model named name, with a fresh coordinate space.
    ///
    /// ## Parameters
    /// name: str
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.renamed("revised")
    fn renamed(&self, name: String) -> PyResult<Self> {
        Ok(Self {
            inner: Arc::new(self.inner.renamed(name).map_err(err)?),
        })
    }
    /// Return a new model minimizing expression from this model space.
    ///
    /// ## Parameters
    /// expression: Affine
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.with_objective(model.vars["x"])
    fn with_objective(&self, expression: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            inner: Arc::new(
                self.inner
                    .with_objective(in_space(expression, &self.inner.space)?)
                    .map_err(err)?,
            ),
        })
    }
    #[pyo3(signature=(variable,**bounds))]
    /// Return a new model with the selected variable bounds replaced. Omitted bounds stay unchanged; explicit None removes a bound.
    ///
    /// ## Parameters
    /// variable: Variable
    /// lower: Scalar | None
    /// upper: Scalar | None
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.with_bounds("x", upper=1)
    fn with_bounds(
        &self,
        variable: &Bound<'_, PyAny>,
        bounds: Option<&Bound<'_, pyo3::types::PyDict>>,
    ) -> PyResult<Self> {
        let i = index(&self.inner, variable, false)?;
        let mut lower = None;
        let mut upper = None;
        if let Some(bounds) = bounds {
            for (k, v) in bounds.iter() {
                match k.extract::<String>()?.as_str() {
                    "lower" => lower = Some(optional(Some(&v))?),
                    "upper" => upper = Some(optional(Some(&v))?),
                    _ => return Err(PyTypeError::new_err("expected lower or upper")),
                }
            }
        }
        Ok(Self {
            inner: Arc::new(self.inner.with_bounds(i, lower, upper).map_err(err)?),
        })
    }
    /// Return a new model with integer flags set for the selected variables.
    ///
    /// ## Parameters
    /// variables: Variable | Iterable[Variable]
    /// integer: bool
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.with_integrality(["x"], True)
    fn with_integrality(&self, variables: &Bound<'_, PyAny>, integer: bool) -> PyResult<Self> {
        let ids = identifiers(&self.inner, variables, false)?;
        Ok(Self {
            inner: Arc::new(self.inner.with_integrality(&ids, integer).map_err(err)?),
        })
    }
    /// Return a new model without the named/indexed rows.
    ///
    /// ## Parameters
    /// rows: str | int | Iterable[str | int]
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.delete_rows(["cap"])
    fn delete_rows(&self, rows: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            inner: Arc::new(
                self.inner
                    .delete_rows(&identifiers(&self.inner, rows, true)?.into_iter().collect())
                    .map_err(err)?,
            ),
        })
    }
    #[pyo3(signature=(name,expression,*,lower=None,upper=None,equal=None))]
    /// Return a new model with the named bounded expression row. equal cannot be combined with lower/upper.
    ///
    /// ## Parameters
    /// name: str
    /// expression: Affine
    /// lower: Scalar | None
    /// upper: Scalar | None
    /// equal: Scalar | None
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.add_row("cap", model.vars["x"], upper=1)
    fn add_row(
        &self,
        name: String,
        expression: &Bound<'_, PyAny>,
        lower: Option<&Bound<'_, PyAny>>,
        upper: Option<&Bound<'_, PyAny>>,
        equal: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let (lo, hi) = bounds(lower, upper, equal)?;
        let row = row_from_parts(
            name,
            in_space(expression, &self.inner.space)?,
            lo,
            hi,
            self.inner.inner.vars.len(),
        )
        .map_err(err)?;
        Ok(Self {
            inner: Arc::new(self.inner.add_rows(vec![row]).map_err(err)?),
        })
    }
    #[pyo3(signature=(replacements,*,remove=true,drop_rows=None,preserve_bounds=true))]
    /// Return an edited model after explicit affine replacement. remove deletes substituted variables; drop_rows selects rows to remove; preserve_bounds retains replaced-variable bounds as constraints. Reacquire variable handles from the result.
    ///
    /// ## Parameters
    /// replacements: dict[Variable, Affine]
    /// remove: bool
    /// drop_rows: Iterable[str | int] | None
    /// preserve_bounds: bool
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.substitute({"x": 1-model.vars["y"]}, drop_rows=["balance"])
    fn substitute(
        &self,
        replacements: &Bound<'_, pyo3::types::PyDict>,
        remove: bool,
        drop_rows: Option<&Bound<'_, PyAny>>,
        preserve_bounds: bool,
    ) -> PyResult<Self> {
        let mut values = HashMap::new();
        for (k, v) in replacements.iter() {
            values.insert(
                index(&self.inner, &k, false)?,
                in_space(&v, &self.inner.space)?,
            );
        }
        let dropped = drop_rows
            .map(|r| identifiers(&self.inner, r, true))
            .transpose()?
            .unwrap_or_default()
            .into_iter()
            .collect::<HashSet<_>>();
        Ok(Self {
            inner: Arc::new(
                self.inner
                    .substitute(&values, remove, &dropped, preserve_bounds)
                    .map_err(err)?
                    .0,
            ),
        })
    }
    /// Test whether the selected variable is integral with bounds contained in [0, 1].
    ///
    /// ## Parameters
    /// variable: Variable
    ///
    /// ## Returns
    /// bool
    ///
    /// ## Example
    /// model.is_binary("x")
    fn is_binary(&self, variable: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.inner
            .is_binary(&Identifier::Index(index(&self.inner, variable, false)?))
            .map_err(err)
    }
}
pub fn identifiers(model: &Model, values: &Bound<'_, PyAny>, row: bool) -> PyResult<Vec<u32>> {
    if values.extract::<String>().is_ok()
        || values.is_instance_of::<PyInt>()
        || values.extract::<PyRef<'_, PyExpr>>().is_ok()
    {
        return Ok(vec![index(model, values, row)?]);
    }
    values.try_iter()?.map(|v| index(model, &v?, row)).collect()
}
fn bounds(
    lower: Option<&Bound<'_, PyAny>>,
    upper: Option<&Bound<'_, PyAny>>,
    equal: Option<&Bound<'_, PyAny>>,
) -> PyResult<(Option<Q>, Option<Q>)> {
    if let Some(e) = equal {
        if lower.is_some() || upper.is_some() {
            return Err(PyTypeError::new_err("use equal or lower/upper"));
        }
        let q = optional(Some(e))?;
        return Ok((q.clone(), q));
    }
    Ok((optional(lower)?, optional(upper)?))
}
/// Construct a model in one owned coordinate space. add_var returns usable VarRef handles immediately. build seals the builder and preserves these handles in the resulting model; later mutation raises ScopeError. Example: b = ModelBuilder("demo"); x = b.add_var("x", lower=0); b.minimize(x); model = b.build().
#[pyclass(name = "ModelBuilder", module = "rpx")]
pub struct ModelBuilder {
    draft: Option<Model>,
}
impl ModelBuilder {
    fn draft(&mut self) -> PyResult<&mut Model> {
        self.draft
            .as_mut()
            .ok_or_else(|| ScopeError::new_err("ModelBuilder has been built"))
    }
}
#[pymethods]
impl ModelBuilder {
    #[new]
    #[pyo3(signature=(name="MODEL"))]
    fn new(name: &str) -> PyResult<Self> {
        Ok(Self {
            draft: Some(Model::new(name.into(), vec![], vec![], Expr::zero()).map_err(err)?),
        })
    }
    #[pyo3(signature=(name,*,integer=false,lower=None,upper=None))]
    /// Add a named variable and return its owned VarRef. integer sets integrality; lower/upper are exact optional bounds.
    ///
    /// ## Parameters
    /// name: str
    /// integer: bool
    /// lower: Scalar | None
    /// upper: Scalar | None
    ///
    /// ## Returns
    /// VarRef
    ///
    /// ## Example
    /// builder.add_var("x", lower=0, upper=1)
    fn add_var(
        &mut self,
        py: Python<'_>,
        name: String,
        integer: bool,
        lower: Option<&Bound<'_, PyAny>>,
        upper: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<PyVar>> {
        let m = self.draft()?;
        if m.var_index.contains_key(&name) {
            return Err(PyKeyError::new_err("duplicate variable name"));
        }
        let v = var_from_parts(name.clone(), integer, optional(lower)?, optional(upper)?)
            .map_err(err)?;
        if m.inner.vars.len() >= kernel_core::model::MAX_VARS {
            return Err(crate::errors::ResourceLimitError::new_err(
                "model variable budget",
            ));
        }
        let i = m.inner.vars.len() as u32;
        m.var_index.insert(name.clone(), i);
        m.space.add_name(name);
        m.inner.vars.push(v.clone());
        variable(py, m.space.clone(), i, v)
    }
    #[pyo3(signature=(name,expression,*,lower=None,upper=None,equal=None))]
    /// Add a named affine row to this builder. equal specifies equality; do not combine it with lower/upper. Return None.
    ///
    /// ## Parameters
    /// name: str
    /// expression: Affine
    /// lower: Scalar | None
    /// upper: Scalar | None
    /// equal: Scalar | None
    ///
    /// ## Returns
    /// None
    ///
    /// ## Example
    /// builder.add_row("balance", x+y, equal=1)
    fn add_row(
        &mut self,
        name: String,
        expression: &Bound<'_, PyAny>,
        lower: Option<&Bound<'_, PyAny>>,
        upper: Option<&Bound<'_, PyAny>>,
        equal: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let m = self.draft()?;
        if m.row_index.contains_key(&name) {
            return Err(PyKeyError::new_err("duplicate row name"));
        }
        let (lo, hi) = bounds(lower, upper, equal)?;
        let row = row_from_parts(
            name.clone(),
            in_space(expression, &m.space)?,
            lo,
            hi,
            m.inner.vars.len(),
        )
        .map_err(err)?;
        if m.inner.rows.len() >= kernel_core::model::MAX_ROWS {
            return Err(crate::errors::ResourceLimitError::new_err(
                "model row budget",
            ));
        }
        m.row_index.insert(name, m.inner.rows.len() as u32);
        m.inner.rows.push(row);
        Ok(())
    }
    /// Set the exact affine minimization objective in this builder; return None.
    ///
    /// ## Parameters
    /// expression: Affine
    ///
    /// ## Returns
    /// None
    ///
    /// ## Example
    /// builder.minimize(x)
    fn minimize(&mut self, expression: &Bound<'_, PyAny>) -> PyResult<()> {
        let m = self.draft()?;
        let e = in_space(expression, &m.space)?;
        e.validate(m.inner.vars.len()).map_err(err)?;
        m.inner.objective = e;
        Ok(())
    }
    /// Seal this builder and return an immutable Model. Previously returned variable handles remain valid.
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// builder.build()
    fn build(&mut self) -> PyResult<PyModel> {
        self.draft()?.validate().map_err(err)?;
        Ok(PyModel {
            inner: Arc::new(self.draft.take().unwrap()),
        })
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyModel>()?;
    m.add_class::<PyVar>()?;
    m.add_class::<VariablesView>()?;
    m.add_class::<RowsView>()?;
    m.add_class::<RowRef>()?;
    m.add_class::<ModelBuilder>()?;
    Ok(())
}

#[pymethods]
impl PyModel {
    #[pyo3(signature=(name,*,integer=false,lower=None,upper=None))]
    /// Return a new model with one named variable; obtain its handle from the returned vars view.
    ///
    /// ## Parameters
    /// name: str
    /// integer: bool
    /// lower: Scalar | None
    /// upper: Scalar | None
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.add_variable("slack", lower=0)
    fn add_variable(
        &self,
        name: String,
        integer: bool,
        lower: Option<&Bound<'_, PyAny>>,
        upper: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let variable =
            var_from_parts(name, integer, optional(lower)?, optional(upper)?).map_err(err)?;
        Ok(Self {
            inner: Arc::new(self.inner.add_variable(variable).map_err(err)?),
        })
    }
    #[pyo3(signature=(row,**changes))]
    /// Return a new model replacing only supplied row fields. Omitted fields stay unchanged; explicit None removes a bound.
    ///
    /// ## Parameters
    /// row: str | int
    /// expression: Affine
    /// lower: Scalar | None
    /// upper: Scalar | None
    ///
    /// ## Returns
    /// Model
    ///
    /// ## Example
    /// model.replace_row("cap", upper=2)
    fn replace_row(
        &self,
        row: &Bound<'_, PyAny>,
        changes: Option<&Bound<'_, pyo3::types::PyDict>>,
    ) -> PyResult<Self> {
        let i = index(&self.inner, row, true)?;
        let mut r = self.inner.inner.rows[i as usize].clone();
        if let Some(changes) = changes {
            for (k, v) in changes.iter() {
                match k.extract::<String>()?.as_str() {
                    "expression" => r.expr = in_space(&v, &self.inner.space)?,
                    "lower" => r.lower = optional(Some(&v))?,
                    "upper" => r.upper = optional(Some(&v))?,
                    _ => return Err(PyTypeError::new_err("expected expression, lower, or upper")),
                }
            }
        }
        Ok(Self {
            inner: Arc::new(self.inner.replace_row(i, r).map_err(err)?),
        })
    }
    #[pyo3(signature=(values,*,integers=true))]
    /// Return violations for supplied name-to-value mapping or coordinate sequence. integers controls integrality checking. An empty list means the point meets the checked model conditions, not proof certification.
    ///
    /// ## Parameters
    /// values: Mapping[str, Scalar] | Sequence[Scalar]
    /// integers: bool
    ///
    /// ## Returns
    /// list[dict[str, Any]]
    ///
    /// ## Example
    /// model.check_point({"x": 0})
    fn check_point(
        &self,
        py: Python<'_>,
        values: &Bound<'_, PyAny>,
        integers: bool,
    ) -> PyResult<Py<PyAny>> {
        let mut point = Vec::new();
        if let Ok(d) = values.cast::<pyo3::types::PyDict>() {
            for v in &self.inner.inner.vars {
                point.push(crate::numbers::scalar(
                    &d.get_item(&v.name)?
                        .ok_or_else(|| PyKeyError::new_err(v.name.clone()))?,
                )?);
            }
        } else if let Some(values) = crate::numbers::integer_buffer(values)? {
            point = values.into_iter().map(Q::from_integer).collect();
        } else {
            for value in values.try_iter()? {
                point.push(crate::numbers::scalar(&value?)?);
            }
        }
        json_py(
            py,
            &serde_json::json!(self.inner.check_point(&point, integers).map_err(err)?),
        )
    }
    /// Return the coordinate indices with nonzero coefficients in the selected row.
    ///
    /// ## Parameters
    /// row: str | int
    ///
    /// ## Returns
    /// list[int]
    ///
    /// ## Example
    /// model.support("cap")
    fn support(&self, row: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
        let i = index(&self.inner, row, true)?;
        self.inner.support(&Identifier::Index(i)).map_err(err)
    }
    /// Return exact lower/upper box activity for the selected row, using None for an unbounded side.
    ///
    /// ## Parameters
    /// row: str | int
    ///
    /// ## Returns
    /// tuple[Q | None, Q | None]
    ///
    /// ## Example
    /// model.row_activity("cap")
    fn row_activity(&self, row: &Bound<'_, PyAny>) -> PyResult<(Option<PyQ>, Option<PyQ>)> {
        let i = index(&self.inner, row, true)?;
        let (a, b) = self
            .inner
            .row_activity(&Identifier::Index(i))
            .map_err(err)?;
        Ok((a.map(|value| PyQ { value }), b.map(|value| PyQ { value })))
    }
}
