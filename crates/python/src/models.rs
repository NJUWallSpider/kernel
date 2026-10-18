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
#[pyclass(name="VarRef",module="rpx",extends=PyExpr,frozen)]
pub struct PyVar {
    value: Var,
    index: u32,
}
#[pymethods]
impl PyVar {
    #[getter]
    fn name(&self) -> &str {
        &self.value.name
    }
    #[getter]
    fn integer(&self) -> bool {
        self.value.integer
    }
    #[getter]
    fn lower(&self) -> Option<PyQ> {
        self.value.lower.clone().map(|value| PyQ { value })
    }
    #[getter]
    fn upper(&self) -> Option<PyQ> {
        self.value.upper.clone().map(|value| PyQ { value })
    }
    #[getter]
    fn index(&self) -> u32 {
        self.index
    }
}
#[pyclass(name = "VariablesView", module = "rpx", frozen)]
pub struct VariablesView {
    pub inner: Arc<Model>,
}
#[pymethods]
impl VariablesView {
    fn __len__(&self) -> usize {
        self.inner.inner.vars.len()
    }
    fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<Py<PyVar>> {
        let i = index(&self.inner, key, false)?;
        variable(
            key.py(),
            self.inner.space.clone(),
            i,
            self.inner.inner.vars[i as usize].clone(),
        )
    }
    fn __contains__(&self, name: &str) -> bool {
        self.inner.var_index.contains_key(name)
    }
    fn __repr__(&self) -> String {
        format!("VariablesView({} variables)", self.inner.inner.vars.len())
    }
    #[pyo3(signature=(limit=None))]
    fn iter(&self, limit: Option<usize>) -> VariableIterator {
        VariableIterator {
            inner: self.inner.clone(),
            at: 0,
            end: limit
                .unwrap_or(self.inner.inner.vars.len())
                .min(self.inner.inner.vars.len()),
        }
    }
    fn __iter__(&self) -> VariableIterator {
        self.iter(None)
    }
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
#[pyclass(name = "RowRef", module = "rpx", frozen)]
pub struct RowRef {
    pub inner: Arc<Model>,
    pub index: usize,
}
#[pymethods]
impl RowRef {
    #[getter]
    fn index(&self) -> usize {
        self.index
    }
    #[getter]
    fn name(&self) -> &str {
        &self.inner.inner.rows[self.index].name
    }
    #[getter]
    fn expression(&self) -> PyExpr {
        bound(
            self.inner.inner.rows[self.index].expr.clone(),
            self.inner.space.clone(),
        )
    }
    #[getter]
    fn lower(&self) -> Option<PyQ> {
        self.inner.inner.rows[self.index]
            .lower
            .clone()
            .map(|value| PyQ { value })
    }
    #[getter]
    fn upper(&self) -> Option<PyQ> {
        self.inner.inner.rows[self.index]
            .upper
            .clone()
            .map(|value| PyQ { value })
    }
    #[getter]
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
#[pyclass(name = "RowsView", module = "rpx", frozen)]
pub struct RowsView {
    inner: Arc<Model>,
}
#[pymethods]
impl RowsView {
    fn __len__(&self) -> usize {
        self.inner.inner.rows.len()
    }
    fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<RowRef> {
        Ok(RowRef {
            inner: self.inner.clone(),
            index: index(&self.inner, key, true)? as usize,
        })
    }
    fn __contains__(&self, name: &str) -> bool {
        self.inner.row_index.contains_key(name)
    }
    fn __repr__(&self) -> String {
        format!("RowsView({} rows)", self.inner.inner.rows.len())
    }
    #[pyo3(signature=(limit=None))]
    fn iter(&self, limit: Option<usize>) -> RowIterator {
        RowIterator {
            inner: self.inner.clone(),
            at: 0,
            end: limit
                .unwrap_or(self.inner.inner.rows.len())
                .min(self.inner.inner.rows.len()),
        }
    }
    fn __iter__(&self) -> RowIterator {
        self.iter(None)
    }
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
    fn read(path: PathBuf) -> PyResult<Self> {
        read(&path)
    }
    #[getter]
    fn name(&self) -> &str {
        &self.inner.inner.name
    }
    #[getter]
    pub fn vars(&self) -> VariablesView {
        VariablesView {
            inner: self.inner.clone(),
        }
    }
    #[getter]
    fn rows(&self) -> RowsView {
        RowsView {
            inner: self.inner.clone(),
        }
    }
    #[getter]
    fn objective(&self) -> PyExpr {
        bound(self.inner.inner.objective.clone(), self.inner.space.clone())
    }
    fn same_formulation(&self, other: &PyModel) -> bool {
        self.inner.same_formulation(&other.inner)
    }
    fn stats(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &self.inner.stats())
    }
    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &kernel_core::model::to_json(&self.inner.inner))
    }
    fn write_mcm(&self, path: PathBuf) -> PyResult<PathBuf> {
        std::fs::write(&path, self.inner.to_mcm().map_err(err)?)
            .map_err(|e| PyOSError::new_err(e.to_string()))?;
        Ok(path)
    }
    #[pyo3(signature=(path,*,rational_literals=false))]
    fn write_mps(&self, path: PathBuf, rational_literals: bool) -> PyResult<PathBuf> {
        std::fs::write(
            &path,
            kernel_compiler_core::model::mps(&self.inner, rational_literals).map_err(err)?,
        )
        .map_err(|e| PyOSError::new_err(e.to_string()))?;
        Ok(path)
    }
    #[pyo3(signature=(*,rational_literals=false))]
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
    fn renamed(&self, name: String) -> PyResult<Self> {
        Ok(Self {
            inner: Arc::new(self.inner.renamed(name).map_err(err)?),
        })
    }
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
    fn with_integrality(&self, variables: &Bound<'_, PyAny>, integer: bool) -> PyResult<Self> {
        let ids = identifiers(&self.inner, variables, false)?;
        Ok(Self {
            inner: Arc::new(self.inner.with_integrality(&ids, integer).map_err(err)?),
        })
    }
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
    fn minimize(&mut self, expression: &Bound<'_, PyAny>) -> PyResult<()> {
        let m = self.draft()?;
        let e = in_space(expression, &m.space)?;
        e.validate(m.inner.vars.len()).map_err(err)?;
        m.inner.objective = e;
        Ok(())
    }
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
    fn support(&self, row: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
        let i = index(&self.inner, row, true)?;
        self.inner.support(&Identifier::Index(i)).map_err(err)
    }
    fn row_activity(&self, row: &Bound<'_, PyAny>) -> PyResult<(Option<PyQ>, Option<PyQ>)> {
        let i = index(&self.inner, row, true)?;
        let (a, b) = self
            .inner
            .row_activity(&Identifier::Index(i))
            .map_err(err)?;
        Ok((a.map(|value| PyQ { value }), b.map(|value| PyQ { value })))
    }
}
