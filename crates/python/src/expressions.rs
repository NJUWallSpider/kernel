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
/// An immutable affine expression with coordinate ownership. Scalars are space-free; variables from independent models cannot be mixed. Parent expressions embed in lift children, never the reverse or across siblings. Arithmetic returns Expr, not a proof. Example: 2 * model.vars["x"] - 1. Use Expr(0) for a constant; use from_terms for indexed construction.
///
/// ## Operators
/// __add__: Add an exact scalar or compatible affine expression; return Expr.
/// __radd__: Reversed addition; return Expr.
/// __sub__: Subtract a compatible operand; return Expr.
/// __rsub__: Subtract self from the left operand; return Expr.
/// __mul__: Scale by an exact scalar; return Expr. Nonlinear products are not accepted.
/// __rmul__: Reversed exact scalar multiplication; return Expr.
/// __truediv__: Divide by a nonzero exact scalar; return Expr. ZeroDivisionError on zero.
/// __neg__: Negate without deriving a fact; return Expr.
/// __eq__: Compare exact coefficients and identical space identity; return bool, not a constraint.
/// __ne__: Negate exact expression equality; return bool, not a constraint.
/// __hash__: Return a hash consistent with equality.
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
    /// The exact constant term as Q.
    ///
    /// ## Example
    /// expr.constant
    fn constant(&self) -> PyQ {
        PyQ {
            value: self.inner.value.constant.clone(),
        }
    }
    #[getter]
    /// The native-backed sparse coefficient view.
    ///
    /// ## Example
    /// expr.terms
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
    /// Negate the operand; return Expr.
    fn __neg__(&self) -> PyResult<Self> {
        Ok(Self {
            inner: BoundExpr::new(
                expr::neg(&self.inner.value).map_err(err)?,
                self.inner.space.clone(),
            ),
        })
    }
    /// Add the operand; return Expr.
    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let e = expression(other)?;
        let space = self.inner.combined_space(&e).map_err(err)?;
        Ok(Self {
            inner: BoundExpr::new(expr::add(&self.inner.value, &e.value).map_err(err)?, space),
        })
    }
    /// Add in reversed operand order the operand; return Expr.
    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__add__(other)
    }
    /// Subtract the operand; return Expr.
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
    /// Subtract in reversed operand order the operand; return Expr.
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
    /// Multiply by an exact scalar the operand; return Expr.
    fn __mul__(&self, factor: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            inner: BoundExpr::new(
                expr::scale(&self.inner.value, &scalar(factor)?).map_err(err)?,
                self.inner.space.clone(),
            ),
        })
    }
    /// Multiply by an exact scalar in reversed order the operand; return Expr.
    fn __rmul__(&self, factor: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__mul__(factor)
    }
    /// Divide by a nonzero exact scalar the operand; return Expr. Zero denominators raise ZeroDivisionError.
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
    /// Return a hash consistent with expression equality.
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
    /// Compare exact space identity and affine coefficients for equality. Ordering raises TypeError.
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
    /// Accumulate sparse indices and coefficients once in native code, with explicit model space and optional constant. Lengths must match; invalid coordinates fail. Integer buffers use a batch path.
    ///
    /// ## Parameters
    /// space: Model
    /// indices: Iterable[int]
    /// coefficients: Iterable[Scalar]
    /// constant: Scalar | None; None uses zero.
    ///
    /// ## Returns
    /// Expr
    ///
    /// ## Example
    /// Expr.from_terms(model, [0], [2], constant=1)
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
    /// Return the exact affine dot product of equally sized coefficients and variables. Native variable views and integer buffers use batch paths. Cross-space variables raise CoordinateSpaceError.
    ///
    /// ## Parameters
    /// coefficients: Iterable[Scalar]
    /// variables: Iterable[Affine]
    ///
    /// ## Returns
    /// Expr
    ///
    /// ## Example
    /// Expr.dot([2, 3], model.vars)
    fn dot(coefficients: &Bound<'_, PyAny>, variables: &Bound<'_, PyAny>) -> PyResult<Self> {
        sum_native(variables, Some(coefficients))
    }
    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// expr.to_dict()
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
/// A sparse native coefficient view keyed by coordinate index. Missing coefficients raise KeyError on indexing; get accepts a default. Iteration yields indices; items and values are lazy. Example: expr.terms.get(0, 0).
///
/// ## Operators
/// __getitem__: Return Q coefficient at a stored coordinate; absent indices raise KeyError.
/// __len__: Return stored nonzero term count.
/// __iter__: Iterate coordinate indices lazily.
#[pyclass(name = "TermsView", module = "rpx", frozen)]
pub struct TermsView {
    expr: BoundExpr,
}
#[pymethods]
impl TermsView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> usize {
        self.expr.value.terms.len()
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
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
    /// Return a lazy iterator over this view. Use bounded inspection for large models.
    fn __iter__(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 0,
        }
    }
    /// Iterate stored coordinate indices lazily.
    ///
    /// ## Returns
    /// Iterator[int]
    ///
    /// ## Example
    /// expr.terms.keys()
    fn keys(&self) -> TermIterator {
        self.__iter__()
    }
    /// Iterate stored (coordinate index, Q coefficient) pairs lazily.
    ///
    /// ## Returns
    /// Iterator[tuple[int, Q]]
    ///
    /// ## Example
    /// expr.terms.items()
    fn items(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 1,
        }
    }
    /// Iterate stored Q coefficients lazily.
    ///
    /// ## Returns
    /// Iterator[Q]
    ///
    /// ## Example
    /// expr.terms.values()
    fn values(&self) -> TermIterator {
        TermIterator {
            expr: self.expr.clone(),
            at: 0,
            mode: 2,
        }
    }
    #[pyo3(signature=(index,default=None))]
    /// Return the coefficient at index, or default when absent.
    ///
    /// ## Parameters
    /// index: int
    /// default: Any
    ///
    /// ## Returns
    /// Any
    ///
    /// ## Example
    /// expr.terms.get(0, 0)
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
    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[int, Q]
    ///
    /// ## Example
    /// expr.terms.to_dict()
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
/// Return the affine sum of items with one native accumulator. The empty sum is Expr(0). Inputs must have compatible coordinate spaces; native views avoid per-coordinate Python construction. Example: quicksum(model.vars).
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
    /// Return an expression after explicit coordinate replacement. Use a MappingView or complete sequence for mapping; a mapping of indices selects replacements. Replacement expressions must have compatible spaces.
    ///
    /// ## Parameters
    /// replacements: Mapping[int, Affine] | Sequence[Affine] | MappingView
    ///
    /// ## Returns
    /// Expr
    ///
    /// ## Example
    /// expr.substitute(scope.mapping)
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
    /// Return Q at an exact coordinate sequence or variable-name mapping; missing coordinates fail.
    ///
    /// ## Parameters
    /// values: Mapping[str, Scalar] | Sequence[Scalar]
    ///
    /// ## Returns
    /// Q
    ///
    /// ## Example
    /// expr.evaluate({"x": 1})
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
