use crate::{
    errors::err,
    models::{PyModel, VariablesView},
    numbers::{PyQ, scalar},
};
use kernel_compiler_core::{
    expr,
    space::{BoundExpr, Space, pretty},
};
use kernel_core::model::{Expr, Q};
use num_traits::{One, Zero};
use pyo3::{
    exceptions::{PyIndexError, PyTypeError, PyZeroDivisionError},
    prelude::*,
    types::{PyDict, PyList},
};
use std::sync::Arc;
#[pyclass(name = "Expr", module = "rpx", frozen, subclass, from_py_object)]
#[derive(Clone)]
pub struct PyExpr {
    pub inner: BoundExpr,
}
pub fn expression(value: &Bound<'_, PyAny>) -> PyResult<BoundExpr> {
    if let Ok(e) = value.extract::<PyRef<'_, PyExpr>>() {
        return Ok(e.inner.clone());
    }
    Ok(BoundExpr::new(
        Expr {
            constant: scalar(value)?,
            terms: vec![],
        },
        None,
    ))
}
pub fn in_space(value: &Bound<'_, PyAny>, space: &Space) -> PyResult<Expr> {
    let e = expression(value)?;
    e.in_space(space).map_err(err)?;
    Ok((*e.value).clone())
}
pub fn bound(e: Expr, space: Arc<Space>) -> PyExpr {
    PyExpr {
        inner: BoundExpr::new(e, Some(space)),
    }
}
#[pymethods]
impl PyExpr {
    #[new]
    #[pyo3(signature=(constant=None))]
    fn new(constant: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        Ok(Self {
            inner: BoundExpr::new(
                Expr {
                    constant: constant.map(scalar).transpose()?.unwrap_or_else(Q::zero),
                    terms: vec![],
                },
                None,
            ),
        })
    }
    #[getter]
    fn constant(&self) -> PyQ {
        PyQ {
            value: self.inner.value.constant.clone(),
        }
    }
    #[getter]
    fn terms(&self) -> TermsView {
        TermsView {
            expr: self.inner.clone(),
        }
    }
    fn __str__(&self) -> String {
        pretty(&self.inner.value, self.inner.space.as_deref())
    }
    fn __repr__(&self) -> String {
        self.__str__()
    }
    fn __neg__(&self) -> PyResult<Self> {
        Ok(Self {
            inner: BoundExpr::new(
                expr::neg(&self.inner.value).map_err(err)?,
                self.inner.space.clone(),
            ),
        })
    }
    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let e = expression(other)?;
        let space = self.inner.combined_space(&e).map_err(err)?;
        Ok(Self {
            inner: BoundExpr::new(expr::add(&self.inner.value, &e.value).map_err(err)?, space),
        })
    }
    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__add__(other)
    }
    fn __sub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let e = expression(other)?;
        let space = self.inner.combined_space(&e).map_err(err)?;
        Ok(Self {
            inner: BoundExpr::new(
                expr::subtract(&self.inner.value, &e.value).map_err(err)?,
                space,
            ),
        })
    }
    fn __rsub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let e = expression(other)?;
        let space = self.inner.combined_space(&e).map_err(err)?;
        Ok(Self {
            inner: BoundExpr::new(
                expr::subtract(&e.value, &self.inner.value).map_err(err)?,
                space,
            ),
        })
    }
    fn __mul__(&self, factor: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            inner: BoundExpr::new(
                expr::scale(&self.inner.value, &scalar(factor)?).map_err(err)?,
                self.inner.space.clone(),
            ),
        })
    }
    fn __rmul__(&self, factor: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__mul__(factor)
    }
    fn __truediv__(&self, divisor: &Bound<'_, PyAny>) -> PyResult<Self> {
        let q = scalar(divisor)?;
        if q.is_zero() {
            return Err(PyZeroDivisionError::new_err("division by zero"));
        }
        Ok(Self {
            inner: BoundExpr::new(
                expr::scale(&self.inner.value, &q.recip()).map_err(err)?,
                self.inner.space.clone(),
            ),
        })
    }
    fn __hash__(&self) -> isize {
        if self.inner.value.terms.is_empty() {
            return crate::numbers::rational_hash(&self.inner.value.constant);
        }
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.inner.space.as_ref().map(|s| s.id).hash(&mut h);
        self.inner.value.constant.hash(&mut h);
        self.inner.value.terms.hash(&mut h);
        let hash = h.finish() as isize;
        if hash == -1 { -2 } else { hash }
    }
    fn __richcmp__(&self, other: &Bound<'_, PyAny>, op: pyo3::basic::CompareOp) -> PyResult<bool> {
        let equal = !other.is_instance_of::<pyo3::types::PyString>()
            && expression(other)
                .map(|e| {
                    e.space.as_ref().map(|s| s.id) == self.inner.space.as_ref().map(|s| s.id)
                        && e.value == self.inner.value
                })
                .unwrap_or(false);
        match op {
            pyo3::basic::CompareOp::Eq => Ok(equal),
            pyo3::basic::CompareOp::Ne => Ok(!equal),
            _ => Err(PyTypeError::new_err(
                "affine expressions are not ordered; declare row bounds explicitly",
            )),
        }
    }
    #[staticmethod]
    #[pyo3(signature=(space,indices,coefficients,constant=None))]
    fn from_terms(
        space: &PyModel,
        indices: &Bound<'_, PyAny>,
        coefficients: &Bound<'_, PyAny>,
        constant: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        use num_traits::ToPrimitive;
        let coordinates = if let Some(values) = crate::numbers::integer_buffer(indices)? {
            values
                .into_iter()
                .map(|i| {
                    i.to_u32()
                        .ok_or_else(|| PyIndexError::new_err("invalid coordinate"))
                })
                .collect::<PyResult<Vec<_>>>()?
        } else {
            indices
                .try_iter()?
                .map(|i| {
                    let i = i?;
                    if i.is_instance_of::<pyo3::types::PyBool>() {
                        return Err(PyTypeError::new_err("bool is not a coordinate"));
                    }
                    i.extract::<u32>()
                })
                .collect::<PyResult<Vec<_>>>()?
        };
        let coefficients = if let Some(values) = crate::numbers::integer_buffer(coefficients)? {
            values.into_iter().map(Q::from_integer).collect::<Vec<_>>()
        } else {
            coefficients
                .try_iter()?
                .map(|q| scalar(&q?))
                .collect::<PyResult<Vec<_>>>()?
        };
        if coordinates.len() != coefficients.len() {
            return Err(PyTypeError::new_err(
                "indices and coefficients have different lengths",
            ));
        }
        if coordinates
            .iter()
            .any(|i| *i as usize >= space.inner.inner.vars.len())
        {
            return Err(PyIndexError::new_err("coordinate outside model"));
        }
        let terms = coordinates.into_iter().zip(coefficients);
        Ok(bound(
            expr::canonical(
                constant.map(scalar).transpose()?.unwrap_or_else(Q::zero),
                terms,
            )
            .map_err(err)?,
            space.inner.space.clone(),
        ))
    }
    #[staticmethod]
    fn dot(coefficients: &Bound<'_, PyAny>, variables: &Bound<'_, PyAny>) -> PyResult<Self> {
        sum_native(variables, Some(coefficients))
    }
    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let d = PyDict::new(py);
        d.set_item("constant", self.inner.value.constant.to_string())?;
        let terms = PyList::empty(py);
        for (i, q) in &self.inner.value.terms {
            terms.append((*i, q.to_string()))?;
        }
        d.set_item("terms", terms)?;
        Ok(d.into_any().unbind())
    }
}
#[pyclass(name = "TermsView", module = "rpx", frozen)]
pub struct TermsView {
    expr: BoundExpr,
}
#[pymethods]
impl TermsView {
    fn __len__(&self) -> usize {
        self.expr.value.terms.len()
    }
    fn __getitem__(&self, index: u32) -> PyResult<PyQ> {
        self.expr
            .value
            .terms
            .binary_search_by_key(&index, |(i, _)| *i)
            .map(|i| PyQ {
                value: self.expr.value.terms[i].1.clone(),
            })
            .map_err(|_| pyo3::exceptions::PyKeyError::new_err(index))
    }
    fn __iter__(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 0,
        }
    }
    fn keys(&self) -> TermIterator {
        self.__iter__()
    }
    fn items(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 1,
        }
    }
    fn values(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 2,
        }
    }
    #[pyo3(signature=(index,default=None))]
    fn get(
        &self,
        index: u32,
        default: Option<&Bound<'_, PyAny>>,
        py: Python<'_>,
    ) -> PyResult<Py<PyAny>> {
        match self.__getitem__(index) {
            Ok(q) => Ok(Py::new(py, q)?.into_any()),
            Err(_) => Ok(default
                .map(|v| v.clone().unbind())
                .unwrap_or_else(|| py.None())),
        }
    }
    fn __repr__(&self) -> String {
        format!("TermsView({} terms)", self.expr.value.terms.len())
    }
    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let d = PyDict::new(py);
        for (i, q) in &self.expr.value.terms {
            d.set_item(*i, Py::new(py, PyQ { value: q.clone() })?)?;
        }
        Ok(d.into_any().unbind())
    }
}
#[pyclass(module = "rpx")]
pub struct TermIterator {
    expr: BoundExpr,
    at: usize,
    mode: u8,
}
#[pymethods]
impl TermIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        let Some((i, q)) = self.expr.value.terms.get(self.at) else {
            return Ok(None);
        };
        self.at += 1;
        Ok(Some(match self.mode {
            0 => i.into_pyobject(py)?.into_any().unbind(),
            1 => (*i, Py::new(py, PyQ { value: q.clone() })?)
                .into_pyobject(py)?
                .into_any()
                .unbind(),
            _ => Py::new(py, PyQ { value: q.clone() })?.into_any(),
        }))
    }
}
fn sum_native(
    items: &Bound<'_, PyAny>,
    coefficients: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyExpr> {
    use std::collections::BTreeMap;
    let mut space: Option<Arc<Space>> = None;
    let mut constant = Q::zero();
    let mut terms = BTreeMap::<u32, Q>::new();
    let integers = coefficients
        .map(crate::numbers::integer_buffer)
        .transpose()?
        .flatten();
    let mut buffered = integers.map(|v| v.into_iter());
    let mut factors = if buffered.is_none() {
        coefficients.map(|v| v.try_iter()).transpose()?
    } else {
        None
    };
    let mut add = |e: BoundExpr, q: Q| -> PyResult<()> {
        let sample = BoundExpr {
            value: Arc::new(Expr::zero()),
            space: space.clone(),
        };
        space = sample.combined_space(&e).map_err(err)?;
        constant += &e.value.constant * &q;
        for (i, c) in &e.value.terms {
            *terms.entry(*i).or_insert_with(Q::zero) += c * &q;
        }
        Ok(())
    };
    let mut factor = || -> PyResult<Q> {
        if let Some(it) = buffered.as_mut() {
            return it
                .next()
                .map(Q::from_integer)
                .ok_or_else(|| PyTypeError::new_err("too few coefficients"));
        }
        match factors.as_mut() {
            None => Ok(Q::one()),
            Some(it) => scalar(
                &it.next()
                    .ok_or_else(|| PyTypeError::new_err("too few coefficients"))??,
            ),
        }
    };
    if let Ok(view) = items.extract::<PyRef<'_, VariablesView>>() {
        for i in 0..view.inner.inner.vars.len() {
            add(
                BoundExpr::new(Expr::var(i as u32), Some(view.inner.space.clone())),
                factor()?,
            )?;
        }
    } else {
        for item in items.try_iter()? {
            add(expression(&item?)?, factor()?)?;
        }
    }
    if factors.as_mut().is_some_and(|it| it.next().is_some())
        || buffered.as_mut().is_some_and(|it| it.next().is_some())
    {
        return Err(PyTypeError::new_err("too many coefficients"));
    }
    Ok(PyExpr {
        inner: BoundExpr::new(expr::canonical(constant, terms).map_err(err)?, space),
    })
}
#[pyfunction]
fn quicksum(items: &Bound<'_, PyAny>) -> PyResult<PyExpr> {
    sum_native(items, None)
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyExpr>()?;
    m.add_class::<TermsView>()?;
    m.add_function(wrap_pyfunction!(quicksum, m)?)?;
    Ok(())
}

#[pymethods]
impl PyExpr {
    fn substitute(&self, replacements: &Bound<'_, PyAny>) -> PyResult<Self> {
        if let Ok(view) = replacements.extract::<PyRef<'_, crate::proofs::MappingView>>() {
            return view.substitute(&self.inner);
        }
        let mut terms = Vec::new();
        let mut constant = self.inner.value.constant.clone();
        let mut space = None;
        for (i, q) in &self.inner.value.terms {
            let value = if let Ok(dict) = replacements.cast::<PyDict>() {
                match dict.get_item(*i)? {
                    Some(v) => expression(&v)?,
                    None => BoundExpr::new(Expr::var(*i), self.inner.space.clone()),
                }
            } else {
                expression(&replacements.get_item(*i)?)?
            };
            let current = BoundExpr {
                value: Arc::new(Expr::zero()),
                space,
            };
            space = current.combined_space(&value).map_err(err)?;
            constant += q * &value.value.constant;
            terms.extend(value.value.terms.iter().map(|(i, c)| (*i, c * q)));
        }
        Ok(Self {
            inner: BoundExpr::new(expr::canonical(constant, terms).map_err(err)?, space),
        })
    }
}

#[pymethods]
impl PyExpr {
    fn evaluate(&self, values: &Bound<'_, PyAny>) -> PyResult<PyQ> {
        let mut result = self.inner.value.constant.clone();
        for (i, q) in &self.inner.value.terms {
            let value = if let Ok(d) = values.cast::<PyDict>() {
                let name = self.inner.space.as_ref().unwrap().name_at(*i);
                d.get_item(name)?
                    .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(*i))?
            } else {
                values.get_item(*i)?
            };
            result += q * scalar(&value)?;
        }
        kernel_core::model::check_q(&result).map_err(err)?;
        Ok(PyQ { value: result })
    }
    fn _repr_html_(&self) -> String {
        format!("<pre>{}</pre>", crate::inspection::html(&self.__str__()))
    }
}
