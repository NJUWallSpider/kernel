#![allow(non_local_definitions)]
use kernel_compiler_core::model::{Identifier, Model as ModelData, ModelFormat};
use kernel_core::model::{Expr, Q};
use num_bigint::BigInt;
use num_traits::{One, Signed, Zero};
use pyo3::exceptions::{PyIndexError, PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyList, PyTuple};
use std::collections::HashMap;
use std::path::Path;

type PyObject = Py<PyAny>;

fn q_from_py(value: &Bound<'_, PyAny>) -> PyResult<Q> {
    if value.is_instance_of::<PyBool>() {
        return Err(PyTypeError::new_err(
            "Use an integer, Fraction, or exact string; booleans are not rationals",
        ));
    }
    if let Ok(integer) = value.extract::<BigInt>() {
        let q = Q::from_integer(integer);
        kernel_core::model::check_q(&q).map_err(PyValueError::new_err)?;
        return Ok(q);
    }
    if let Ok(text) = value.extract::<String>() {
        return kernel_core::model::parse_q(&text).map_err(PyValueError::new_err);
    }
    let numerator = value.getattr("numerator").map_err(|_| {
        PyTypeError::new_err(
            "Use an integer, Fraction, or exact string (for example '0.1'); floats are forbidden",
        )
    })?;
    let denominator = value.getattr("denominator").map_err(|_| {
        PyTypeError::new_err(
            "Use an integer, Fraction, or exact string (for example '0.1'); floats are forbidden",
        )
    })?;
    let numerator = numerator.extract::<BigInt>()?;
    let denominator = denominator.extract::<BigInt>()?;
    if denominator.is_zero() {
        return Err(PyValueError::new_err("zero denominator"));
    }
    let q = Q::new(numerator, denominator);
    kernel_core::model::check_q(&q).map_err(PyValueError::new_err)?;
    Ok(q)
}

fn q_to_py(py: Python<'_>, value: &Q) -> PyResult<PyObject> {
    let fractions = py.import("fractions")?;
    let class = fractions.getattr("Fraction")?;
    let numerator = value.numer().clone().into_pyobject(py)?;
    let denominator = value.denom().clone().into_pyobject(py)?;
    Ok(class.call1((numerator, denominator))?.unbind())
}

fn q_text(value: &Q) -> String {
    value.to_string()
}

fn py_expr(value: &Bound<'_, PyAny>) -> PyResult<Expr> {
    if let Ok(item) = value.extract::<PyRef<'_, PyExpr>>() {
        return Ok(item.inner.clone());
    }
    Ok(PyExpr::new(value.py(), Some(value), None)?.inner)
}

fn mappingproxy(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    Ok(py
        .import("types")?
        .getattr("MappingProxyType")?
        .call1((value,))?
        .unbind())
}

#[pyclass(name = "Expr", module = "kernel_compiler._native", from_py_object)]
#[derive(Clone)]
struct PyExpr {
    inner: Expr,
}

#[pymethods]
impl PyExpr {
    #[new]
    #[pyo3(signature = (constant=None, terms=None))]
    fn new(
        py: Python<'_>,
        constant: Option<&Bound<'_, PyAny>>,
        terms: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let constant = match constant {
            Some(value) if !value.is_none() => q_from_py(value)?,
            _ => Q::zero(),
        };
        let mut pairs = Vec::new();
        if let Some(value) = terms {
            if !value.is_none() {
                if let Ok(dict) = value.cast::<PyDict>() {
                    for (key, item) in dict.iter() {
                        pairs.push((key.extract::<u32>()?, q_from_py(&item)?));
                    }
                } else {
                    for item in value.try_iter()? {
                        let item = item?;
                        let tuple = item
                            .cast::<PyTuple>()
                            .map_err(|_| PyTypeError::new_err("terms must be pairs"))?;
                        if tuple.len() != 2 {
                            return Err(PyTypeError::new_err("terms must be pairs"));
                        }
                        pairs.push((
                            tuple.get_item(0)?.extract::<u32>()?,
                            q_from_py(&tuple.get_item(1)?)?,
                        ));
                    }
                }
            }
        }
        let inner = kernel_compiler_core::expr::canonical(constant, pairs)
            .map_err(PyValueError::new_err)?;
        let _ = py;
        Ok(Self { inner })
    }

    #[staticmethod]
    fn var(index: u32) -> Self {
        Self {
            inner: Expr::var(index),
        }
    }

    #[staticmethod]
    fn coerce(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self {
            inner: py_expr(value)?,
        })
    }

    #[staticmethod]
    #[pyo3(signature = (data, intermediate=false))]
    fn from_json(data: &Bound<'_, PyAny>, intermediate: bool) -> PyResult<Self> {
        let dict = data.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("An expression must contain only constant and terms")
        })?;
        if dict.len() != dict.keys().len() {
            return Err(PyValueError::new_err(
                "An expression must contain only constant and terms",
            ));
        }
        for key in dict.keys() {
            let key = key.extract::<String>()?;
            if key != "constant" && key != "terms" {
                return Err(PyValueError::new_err(
                    "An expression must contain only constant and terms",
                ));
            }
        }
        let constant = match dict.get_item("constant")? {
            Some(value) => {
                if intermediate {
                    q_from_metadata(&value)?
                } else {
                    q_from_py(&value)?
                }
            }
            None => Q::zero(),
        };
        let mut pairs = Vec::new();
        if let Some(value) = dict.get_item("terms")? {
            if !value.is_none() {
                if let Ok(items) = value.cast::<PyDict>() {
                    for (key, item) in items.iter() {
                        pairs.push((key.extract::<u32>()?, q_from_metadata(&item)?));
                    }
                } else {
                    for item in value.try_iter()? {
                        let item = item?;
                        let pair = item
                            .cast::<PyList>()
                            .map_err(|_| PyValueError::new_err("terms must be pairs"))?;
                        if pair.len() != 2 {
                            return Err(PyValueError::new_err("terms must be pairs"));
                        }
                        let coefficient = if intermediate {
                            q_from_metadata(&pair.get_item(1)?)?
                        } else {
                            q_from_py(&pair.get_item(1)?)?
                        };
                        pairs.push((pair.get_item(0)?.extract::<u32>()?, coefficient));
                    }
                }
            }
        }
        let inner = kernel_compiler_core::expr::canonical(constant, pairs)
            .map_err(PyValueError::new_err)?;
        Ok(Self { inner })
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("constant", q_text(&self.inner.constant))?;
        let terms = PyList::empty(py);
        for (index, coefficient) in &self.inner.terms {
            terms.append(PyList::new(
                py,
                [
                    index.into_pyobject(py)?.into_any().unbind(),
                    q_text(coefficient).into_pyobject(py)?.into_any().unbind(),
                ],
            )?)?;
        }
        dict.set_item("terms", terms)?;
        Ok(dict.into_any().unbind())
    }

    #[getter]
    fn constant(&self, py: Python<'_>) -> PyResult<PyObject> {
        q_to_py(py, &self.inner.constant)
    }

    #[getter]
    fn terms(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        for (index, coefficient) in &self.inner.terms {
            dict.set_item(*index, q_to_py(py, coefficient)?)?;
        }
        mappingproxy(py, dict.as_any())
    }

    fn coefficient(&self, py: Python<'_>, index: u32) -> PyResult<PyObject> {
        let value = self
            .inner
            .terms
            .iter()
            .find(|(item, _)| *item == index)
            .map(|(_, value)| value.clone())
            .unwrap_or_else(Q::zero);
        q_to_py(py, &value)
    }

    fn substitute(&self, py: Python<'_>, replacements: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut mapping = Vec::new();
        if let Ok(dict) = replacements.cast::<PyDict>() {
            for (key, value) in dict.iter() {
                let index = key.extract::<u32>()?;
                if mapping.len() <= index as usize {
                    mapping.resize(index as usize + 1, None);
                }
                mapping[index as usize] = Some(py_expr(&value)?);
            }
        } else {
            for item in replacements.try_iter()? {
                mapping.push(Some(py_expr(&item?)?));
            }
        }
        let inner = kernel_compiler_core::expr::substitute(&self.inner, &mapping, true)
            .map_err(PyValueError::new_err)?;
        let _ = py;
        Ok(Self { inner })
    }

    fn evaluate(&self, values: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let mut items = Vec::new();
        for item in values.try_iter()? {
            items.push(Some(q_from_py(&item?)?));
        }
        let value = kernel_compiler_core::expr::evaluate(&self.inner, &items)
            .map_err(PyValueError::new_err)?;
        q_to_py(values.py(), &value)
    }

    #[pyo3(signature = (max_terms=8))]
    fn summary(&self, py: Python<'_>, max_terms: usize) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        let scalar = |value: &Q| -> PyObject {
            if value.numer().bits() <= 256 && value.denom().bits() <= 256 {
                q_text(value).into_pyobject(py).unwrap().into_any().unbind()
            } else {
                let item = PyDict::new(py);
                item.set_item(
                    "sign",
                    if value.is_positive() {
                        1
                    } else if value.is_negative() {
                        -1
                    } else {
                        0
                    },
                )
                .unwrap();
                item.set_item("numerator_bits", value.numer().bits())
                    .unwrap();
                item.set_item("denominator_bits", value.denom().bits())
                    .unwrap();
                item.into_any().unbind()
            }
        };
        dict.set_item("constant", scalar(&self.inner.constant))?;
        dict.set_item("term_count", self.inner.terms.len())?;
        let terms = PyList::empty(py);
        for (index, value) in self.inner.terms.iter().take(max_terms) {
            terms.append(PyList::new(
                py,
                [index.into_pyobject(py)?.into_any().unbind(), scalar(value)],
            )?)?;
        }
        dict.set_item("terms", terms)?;
        dict.set_item(
            "omitted_terms",
            self.inner.terms.len().saturating_sub(max_terms),
        )?;
        Ok(dict.into_any().unbind())
    }

    fn __hash__(&self) -> isize {
        0
    }

    fn __richcmp__(
        &self,
        other: &Bound<'_, PyAny>,
        op: pyo3::basic::CompareOp,
    ) -> PyResult<PyObject> {
        let equal = if let Ok(item) = other.extract::<PyRef<'_, PyExpr>>() {
            self.inner == item.inner
        } else if let Ok(value) = q_from_py(other) {
            self.inner.terms.is_empty() && self.inner.constant == value
        } else {
            false
        };
        let result = match op {
            pyo3::basic::CompareOp::Eq => equal,
            pyo3::basic::CompareOp::Ne => !equal,
            _ => false,
        };
        Ok(PyBool::new(other.py(), result)
            .to_owned()
            .into_any()
            .unbind())
    }

    fn __bool__(&self) -> bool {
        !self.inner.constant.is_zero() || !self.inner.terms.is_empty()
    }

    fn __add__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        let other = py_expr(other)?;
        let inner =
            kernel_compiler_core::expr::add(&self.inner, &other).map_err(PyValueError::new_err)?;
        Py::new(py, PyExpr { inner })
    }

    fn __radd__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        self.__add__(py, other)
    }

    fn __neg__(&self, py: Python<'_>) -> PyResult<Py<PyExpr>> {
        Py::new(
            py,
            PyExpr {
                inner: kernel_compiler_core::expr::neg(&self.inner)
                    .map_err(PyValueError::new_err)?,
            },
        )
    }

    fn __sub__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        let other = py_expr(other)?;
        let inner = kernel_compiler_core::expr::subtract(&self.inner, &other)
            .map_err(PyValueError::new_err)?;
        Py::new(py, PyExpr { inner })
    }

    fn __rsub__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        let other = py_expr(other)?;
        let inner = kernel_compiler_core::expr::subtract(&other, &self.inner)
            .map_err(PyValueError::new_err)?;
        Py::new(py, PyExpr { inner })
    }

    fn __mul__(&self, py: Python<'_>, scalar: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        if scalar.extract::<PyRef<'_, PyExpr>>().is_ok() {
            return Err(PyTypeError::new_err(
                "Expressions are scalar-linear; multiplication is scalar-only",
            ));
        }
        let factor = q_from_py(scalar)?;
        let inner = kernel_compiler_core::expr::scale(&self.inner, &factor)
            .map_err(PyValueError::new_err)?;
        Py::new(py, PyExpr { inner })
    }

    fn __rmul__(&self, py: Python<'_>, scalar: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        self.__mul__(py, scalar)
    }

    fn __truediv__(&self, py: Python<'_>, scalar: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        let factor = q_from_py(scalar)?;
        if factor.is_zero() {
            return Err(PyValueError::new_err("division by zero"));
        }
        self.__mul__(
            py,
            &(q_to_py(py, &Q::one())?
                .into_bound(py)
                .call_method1("__truediv__", (q_to_py(py, &factor)?,))?),
        )
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let terms = self
            .inner
            .terms
            .iter()
            .map(|(index, value)| format!("{index}: {:?}", q_text(value)))
            .collect::<Vec<_>>()
            .join(", ");
        let _ = py;
        Ok(format!(
            "Expr(constant={:?}, terms={{{terms}}})",
            q_text(&self.inner.constant)
        ))
    }
}

fn q_from_metadata(value: &Bound<'_, PyAny>) -> PyResult<Q> {
    if let Ok(text) = value.extract::<String>() {
        if text.len() > 2 * 19_729 + 3 {
            return Err(PyValueError::new_err(
                "Intermediate rational text exceeds the kernel's bit limit",
            ));
        }
        if let Ok(parsed) = kernel_core::model::parse_q(&text) {
            return Ok(parsed);
        }
        let (numerator, denominator) = text.split_once('/').unwrap_or((&text, "1"));
        let parse = |part: &str| -> PyResult<BigInt> {
            let digits = part.strip_prefix(['+', '-']).unwrap_or(part);
            if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
                return Err(PyValueError::new_err("invalid intermediate rational"));
            }
            if digits.len() > 19_729 {
                return Err(PyValueError::new_err(
                    "Intermediate integer exceeds the kernel's bit limit",
                ));
            }
            let value: BigInt = part
                .parse()
                .map_err(|_| PyValueError::new_err("invalid intermediate integer"))?;
            if value.bits() > kernel_core::model::MAX_Q_BITS {
                return Err(PyValueError::new_err(
                    "Intermediate rational exceeds the kernel's 65536-bit limit",
                ));
            }
            Ok(value)
        };
        let numerator = parse(numerator)?;
        let denominator = parse(denominator)?;
        if denominator.is_zero() {
            return Err(PyValueError::new_err("zero denominator"));
        }
        let q = Q::new(numerator, denominator);
        kernel_core::model::check_q(&q).map_err(PyValueError::new_err)?;
        return Ok(q);
    }
    q_from_py(value)
}

#[pyclass(name = "Model", module = "kernel_compiler._native", from_py_object)]
#[derive(Clone)]
struct PyModel {
    inner: ModelData,
}

fn variable_parts(value: &Bound<'_, PyAny>) -> PyResult<(String, bool, Option<Q>, Option<Q>)> {
    let name = value.getattr("name")?.extract::<String>()?;
    let integer = value.getattr("integer")?.extract::<bool>()?;
    let lower = value.getattr("lower")?;
    let upper = value.getattr("upper")?;
    Ok((
        name,
        integer,
        if lower.is_none() {
            None
        } else {
            Some(q_from_py(&lower)?)
        },
        if upper.is_none() {
            None
        } else {
            Some(q_from_py(&upper)?)
        },
    ))
}

fn row_parts(value: &Bound<'_, PyAny>) -> PyResult<(String, Expr, Option<Q>, Option<Q>)> {
    let name = value.getattr("name")?.extract::<String>()?;
    let expression = value.getattr("expr")?;
    let lower = value.getattr("lower")?;
    let upper = value.getattr("upper")?;
    Ok((
        name,
        py_expr(&expression)?,
        if lower.is_none() {
            None
        } else {
            Some(q_from_py(&lower)?)
        },
        if upper.is_none() {
            None
        } else {
            Some(q_from_py(&upper)?)
        },
    ))
}

impl PyModel {
    fn index(&self, identifier: &Bound<'_, PyAny>, row: bool) -> PyResult<u32> {
        let identifier = if let Ok(index) = identifier.extract::<u32>() {
            Identifier::Index(index)
        } else if let Ok(text) = identifier.extract::<String>() {
            Identifier::Name(text)
        } else if let Ok(expr) = identifier.extract::<PyRef<'_, PyExpr>>() {
            if expr.inner.constant != Q::zero()
                || expr.inner.terms.len() != 1
                || expr.inner.terms[0].1 != Q::one()
            {
                return Err(PyValueError::new_err(
                    "A variable reference expression must be exactly one unit coordinate",
                ));
            }
            Identifier::Index(expr.inner.terms[0].0)
        } else if let Ok(name) = identifier.getattr("name") {
            Identifier::Name(name.extract::<String>()?)
        } else {
            return Err(PyTypeError::new_err("Invalid model identifier"));
        };
        self.inner.index(&identifier, row).map_err(|error| {
            if error.starts_with("unknown") {
                PyKeyError::new_err(error)
            } else if error.starts_with("INVALID") {
                PyValueError::new_err(error)
            } else {
                PyIndexError::new_err(error)
            }
        })
    }

    fn wrap(&self, value: Result<ModelData, String>) -> PyResult<Self> {
        Ok(Self {
            inner: value.map_err(PyValueError::new_err)?,
        })
    }
}

#[pymethods]
impl PyModel {
    #[new]
    #[pyo3(signature = (name="MODEL", variables=None, rows=None, objective=None))]
    fn new(
        py: Python<'_>,
        name: &str,
        variables: Option<&Bound<'_, PyAny>>,
        rows: Option<&Bound<'_, PyAny>>,
        objective: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let mut vars = Vec::new();
        if let Some(values) = variables {
            for value in values.try_iter()? {
                let (name, integer, lower, upper) = variable_parts(&value?)?;
                vars.push(
                    kernel_compiler_core::model::var_from_parts(name, integer, lower, upper)
                        .map_err(PyValueError::new_err)?,
                );
            }
        }
        let mut row_values = Vec::new();
        if let Some(values) = rows {
            for value in values.try_iter()? {
                let (name, expression, lower, upper) = row_parts(&value?)?;
                row_values.push(
                    kernel_compiler_core::model::row_from_parts(
                        name,
                        expression,
                        lower,
                        upper,
                        vars.len(),
                    )
                    .map_err(PyValueError::new_err)?,
                );
            }
        }
        let objective = match objective {
            Some(value) if !value.is_none() => py_expr(value)?,
            _ => Expr::zero(),
        };
        let inner = ModelData::new(name.to_string(), vars, row_values, objective)
            .map_err(PyValueError::new_err)?;
        let _ = py;
        Ok(Self { inner })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.inner.name
    }

    #[getter]
    fn vars(&self, py: Python<'_>) -> PyResult<PyObject> {
        let values = PyList::empty(py);
        for variable in &self.inner.inner.vars {
            values.append((
                variable.name.clone(),
                variable.integer,
                variable
                    .lower
                    .as_ref()
                    .map(|q| q_to_py(py, q))
                    .transpose()?,
                variable
                    .upper
                    .as_ref()
                    .map(|q| q_to_py(py, q))
                    .transpose()?,
            ))?;
        }
        Ok(values.into_any().unbind())
    }

    #[getter]
    fn rows(&self, py: Python<'_>) -> PyResult<PyObject> {
        let values = PyList::empty(py);
        for row in &self.inner.inner.rows {
            values.append((
                row.name.clone(),
                Py::new(
                    py,
                    PyExpr {
                        inner: row.expr.clone(),
                    },
                )?,
                row.lower.as_ref().map(|q| q_to_py(py, q)).transpose()?,
                row.upper.as_ref().map(|q| q_to_py(py, q)).transpose()?,
            ))?;
        }
        Ok(values.into_any().unbind())
    }

    #[getter]
    fn objective(&self, py: Python<'_>) -> PyResult<Py<PyExpr>> {
        Py::new(
            py,
            PyExpr {
                inner: self.inner.inner.objective.clone(),
            },
        )
    }

    #[getter]
    fn var_index(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        for (name, index) in &self.inner.var_index {
            dict.set_item(name, *index)?;
        }
        Ok(dict.into_any().unbind())
    }

    #[getter]
    fn row_index(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        for (name, index) in &self.inner.row_index {
            dict.set_item(name, *index)?;
        }
        Ok(dict.into_any().unbind())
    }

    fn var(&self, py: Python<'_>, identifier: &Bound<'_, PyAny>) -> PyResult<Py<PyExpr>> {
        let index = self.index(identifier, false)?;
        Py::new(
            py,
            PyExpr {
                inner: Expr::var(index),
            },
        )
    }

    fn row(&self, py: Python<'_>, identifier: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let index = self.index(identifier, true)?;
        let row = self.inner.inner.rows[index as usize].clone();
        Ok(PyTuple::new(
            py,
            [
                row.name.into_pyobject(py)?.into_any(),
                Py::new(py, PyExpr { inner: row.expr })?
                    .into_bound(py)
                    .into_any(),
                row.lower.map(|q| q_text(&q)).into_pyobject(py)?.into_any(),
                row.upper.map(|q| q_text(&q)).into_pyobject(py)?.into_any(),
            ],
        )?
        .into_any()
        .unbind())
    }

    fn fact(
        &self,
        py: Python<'_>,
        kind: &str,
        identifier: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let identifier = if let Ok(index) = identifier.extract::<u32>() {
            Identifier::Index(index)
        } else if let Ok(text) = identifier.extract::<String>() {
            Identifier::Name(text)
        } else {
            Identifier::Index(self.index(identifier, kind.starts_with("Row"))?)
        };
        let (kind, expression) = self
            .inner
            .fact(kind, &identifier)
            .map_err(PyValueError::new_err)?;
        Ok(PyTuple::new(
            py,
            [
                kernel_compiler_core::proof::kind_name(kind)
                    .into_pyobject(py)?
                    .into_any(),
                Py::new(py, PyExpr { inner: expression })?
                    .into_bound(py)
                    .into_any(),
            ],
        )?
        .into_any()
        .unbind())
    }

    fn ref_(
        &self,
        py: Python<'_>,
        kind: &str,
        identifier: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let index = self.index(identifier, kind.starts_with("Row"))?;
        let reference = self
            .inner
            .reference(kind, &Identifier::Index(index))
            .map_err(PyValueError::new_err)?;
        Ok(ref_to_py(py, &reference))
    }

    fn support(&self, identifier: &Bound<'_, PyAny>, names: bool) -> PyResult<Vec<u32>> {
        let index = self.index(identifier, true)?;
        self.inner
            .support(&Identifier::Index(index), names)
            .map_err(PyValueError::new_err)
    }

    fn row_activity(&self, py: Python<'_>, identifier: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let index = self.index(identifier, true)?;
        let (lower, upper) = self
            .inner
            .row_activity(&Identifier::Index(index))
            .map_err(PyValueError::new_err)?;
        Ok(PyTuple::new(
            py,
            [
                lower.map(|q| q_text(&q)).into_pyobject(py)?.into_any(),
                upper.map(|q| q_text(&q)).into_pyobject(py)?.into_any(),
            ],
        )?
        .into_any()
        .unbind())
    }

    fn is_binary(&self, identifier: &Bound<'_, PyAny>) -> PyResult<bool> {
        let index = self.index(identifier, false)?;
        self.inner
            .is_binary(&Identifier::Index(index))
            .map_err(PyValueError::new_err)
    }

    fn column_incidence(&self, py: Python<'_>) -> PyResult<PyObject> {
        let values = PyList::empty(py);
        for column in self.inner.column_incidence() {
            let items = PyList::empty(py);
            for (index, coefficient) in column {
                items.append((index, q_text(&coefficient)))?;
            }
            values.append(items)?;
        }
        Ok(values.into_any().unbind())
    }

    fn stats(&self, py: Python<'_>) -> PyResult<PyObject> {
        json_to_py(py, &self.inner.stats())
    }

    fn check_point(
        &self,
        py: Python<'_>,
        values: &Bound<'_, PyAny>,
        integers: bool,
    ) -> PyResult<PyObject> {
        let mut items = Vec::new();
        for value in values.try_iter()? {
            items.push(q_from_py(&value?)?);
        }
        let result = self
            .inner
            .check_point(&items, integers)
            .map_err(PyValueError::new_err)?;
        json_to_py(py, &serde_json::Value::Array(result))
    }

    fn same_formulation(&self, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let other = other.extract::<PyRef<'_, PyModel>>()?;
        Ok(self.inner.same_formulation(&other.inner))
    }

    fn to_mcm<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyBytes>> {
        let bytes = self.inner.to_mcm().map_err(PyValueError::new_err)?;
        Ok(pyo3::types::PyBytes::new(py, &bytes))
    }

    fn write_mcm(&self, path: &str) -> PyResult<()> {
        let bytes = self.inner.to_mcm().map_err(PyValueError::new_err)?;
        std::fs::write(path, bytes).map_err(|error| PyValueError::new_err(error.to_string()))
    }

    fn validate(&self) -> PyResult<()> {
        self.inner.validate().map_err(PyValueError::new_err)
    }

    fn renamed(&self, name: &str) -> PyResult<Self> {
        self.wrap(self.inner.renamed(name.to_string()))
    }

    fn delete_rows(&self, identifiers: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut indices = std::collections::HashSet::new();
        for item in identifiers.try_iter()? {
            indices.insert(self.index(&item?, true)?);
        }
        self.wrap(self.inner.delete_rows(&indices))
    }

    fn add_rows(&self, rows: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut values = Vec::new();
        for item in rows.try_iter()? {
            let (name, expression, lower, upper) = row_parts(&item?)?;
            values.push(
                kernel_compiler_core::model::row_from_parts(
                    name,
                    expression,
                    lower,
                    upper,
                    self.inner.inner.vars.len(),
                )
                .map_err(PyValueError::new_err)?,
            );
        }
        self.wrap(self.inner.add_rows(values))
    }

    fn replace_row(&self, identifier: &Bound<'_, PyAny>, row: &Bound<'_, PyAny>) -> PyResult<Self> {
        let index = self.index(identifier, true)?;
        let (name, expression, lower, upper) = row_parts(row)?;
        let row = kernel_compiler_core::model::row_from_parts(
            name,
            expression,
            lower,
            upper,
            self.inner.inner.vars.len(),
        )
        .map_err(PyValueError::new_err)?;
        self.wrap(self.inner.replace_row(index, row))
    }

    fn add_variable(&self, variable: &Bound<'_, PyAny>) -> PyResult<Self> {
        let (name, integer, lower, upper) = variable_parts(variable)?;
        let variable = kernel_compiler_core::model::var_from_parts(name, integer, lower, upper)
            .map_err(PyValueError::new_err)?;
        self.wrap(self.inner.add_variable(variable))
    }

    fn with_objective(&self, objective: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.wrap(self.inner.with_objective(py_expr(objective)?))
    }

    fn with_bounds(
        &self,
        identifier: &Bound<'_, PyAny>,
        lower: Option<&Bound<'_, PyAny>>,
        upper: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let index = self.index(identifier, false)?;
        let lower = lower
            .map(|value| {
                if value.is_none() {
                    Ok(None)
                } else {
                    q_from_py(value).map(Some)
                }
            })
            .transpose()?;
        let upper = upper
            .map(|value| {
                if value.is_none() {
                    Ok(None)
                } else {
                    q_from_py(value).map(Some)
                }
            })
            .transpose()?;
        self.wrap(self.inner.with_bounds(index, lower, upper))
    }

    fn with_integrality(&self, identifiers: &Bound<'_, PyAny>, integer: bool) -> PyResult<Self> {
        let mut indices = Vec::new();
        for item in identifiers.try_iter()? {
            indices.push(self.index(&item?, false)?);
        }
        indices.sort_unstable();
        indices.dedup();
        self.wrap(self.inner.with_integrality(&indices, integer))
    }

    fn substitute(
        &self,
        replacements: &Bound<'_, PyAny>,
        remove: bool,
        drop_rows: &Bound<'_, PyAny>,
        preserve_bounds: bool,
    ) -> PyResult<Self> {
        let dict = replacements
            .cast::<PyDict>()
            .map_err(|_| PyTypeError::new_err("replacements must be a mapping"))?;
        let mut values = HashMap::new();
        for (key, value) in dict.iter() {
            values.insert(self.index(&key, false)?, py_expr(&value)?);
        }
        let mut dropped = std::collections::HashSet::new();
        for item in drop_rows.try_iter()? {
            dropped.insert(self.index(&item?, true)?);
        }
        let (model, _) = self
            .inner
            .substitute(&values, remove, &dropped, preserve_bounds)
            .map_err(PyValueError::new_err)?;
        Ok(Self { inner: model })
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<PyObject> {
        json_to_py(py, &kernel_core::model::to_json(&self.inner.inner))
    }

    #[staticmethod]
    fn load(path: &str) -> PyResult<Self> {
        let path = Path::new(path);
        let suffix = path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let bytes =
            std::fs::read(path).map_err(|error| PyValueError::new_err(error.to_string()))?;
        let format = if bytes.starts_with(b"MCM\0") {
            ModelFormat::Mcm
        } else {
            match suffix.as_str() {
                "mcm" => ModelFormat::Mcm,
                "mps" => ModelFormat::Mps,
                "lp" => ModelFormat::Lp,
                "json" => ModelFormat::Json,
                _ => ModelFormat::Mps,
            }
        };
        let inner = ModelData::parse_bytes(&bytes, format).map_err(PyValueError::new_err)?;
        Ok(Self { inner })
    }
}

fn ref_to_py(py: Python<'_>, reference: &kernel_core::proof::Ref) -> PyObject {
    use kernel_core::proof::Ref::*;
    let dict = PyDict::new(py);
    let (name, index) = match reference {
        VarLower(i) => ("VarLower", Some(*i)),
        VarUpper(i) => ("VarUpper", Some(*i)),
        VarInt(i) => ("VarInt", Some(*i)),
        RowLower(i) => ("RowLower", Some(*i)),
        RowUpper(i) => ("RowUpper", Some(*i)),
        RowEq(i) => ("RowEq", Some(*i)),
        Local(i) => ("Local", Some(*i)),
        Assumption(i) => ("Assumption", Some(*i)),
        Exact => ("Exact", None),
    };
    if let Some(index) = index {
        dict.set_item(name, index).unwrap();
    } else {
        return "Exact".into_pyobject(py).unwrap().into_any().unbind();
    }
    dict.into_any().unbind()
}

fn json_to_py(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(value) => {
            Ok(value.into_pyobject(py)?.to_owned().into_any().unbind())
        }
        serde_json::Value::Number(value) => {
            if let Some(item) = value.as_i64() {
                Ok(item.into_pyobject(py)?.into_any().unbind())
            } else if let Some(item) = value.as_u64() {
                Ok(item.into_pyobject(py)?.into_any().unbind())
            } else {
                Ok(value.to_string().into_pyobject(py)?.into_any().unbind())
            }
        }
        serde_json::Value::String(value) => Ok(value.into_pyobject(py)?.into_any().unbind()),
        serde_json::Value::Array(values) => {
            let list = PyList::empty(py);
            for item in values {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into_any().unbind())
        }
        serde_json::Value::Object(values) => {
            let dict = PyDict::new(py);
            for (key, item) in values {
                dict.set_item(key, json_to_py(py, item)?)?;
            }
            Ok(dict.into_any().unbind())
        }
    }
}

fn pair_items<'py>(item: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    if let Ok(pair) = item.cast::<PyList>() {
        if pair.len() == 2 {
            return Ok((pair.get_item(0)?, pair.get_item(1)?));
        }
    }
    let pair = item
        .cast::<PyTuple>()
        .map_err(|_| PyValueError::new_err("expected a two-item pair"))?;
    if pair.len() != 2 {
        return Err(PyValueError::new_err("expected a two-item pair"));
    }
    Ok((pair.get_item(0)?, pair.get_item(1)?))
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyExpr>()?;
    module.add_class::<PyModel>()?;
    module.add_class::<PyFact>()?;
    module.add_class::<PyContradiction>()?;
    module.add_class::<PyBuilder>()?;
    module.add_class::<PyProof>()?;
    module.add_class::<PyCompiled>()?;
    module.add_class::<PyKernel>()?;
    module.add_function(wrap_pyfunction!(prepare_extension, module)?)?;
    Ok(())
}

use kernel_compiler_core::complete::Obligation;
use kernel_compiler_core::proof::{
    AssignmentValue, FactId, ProofCore, ScopeEnd, ScopeId, Selector, kind_name, parse_kind,
};
use kernel_core::proof::{
    Block, Certificate, Derivation, DerivationEnd as CoreDerivationEnd, End, Kind, Ref, Step,
};
use kernel_core::verify::Limits;
use std::sync::{Arc, Mutex};

fn parse_limit(work: Option<u64>, live: Option<usize>, depth: Option<usize>) -> Limits {
    let mut limits = Limits::default();
    if let Some(value) = work {
        limits.work = value;
    }
    if let Some(value) = live {
        limits.live_facts = value;
    }
    if let Some(value) = depth {
        limits.depth = value;
    }
    limits
}

fn lock_core(core: &Arc<Mutex<ProofCore>>) -> PyResult<std::sync::MutexGuard<'_, ProofCore>> {
    core.lock()
        .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("native proof lock poisoned"))
}

fn fact_ref(py: Python<'_>, reference: &Ref) -> PyObject {
    ref_to_py(py, reference)
}

fn py_fact(core: &Arc<Mutex<ProofCore>>, id: FactId) -> PyResult<PyFact> {
    let _ = core;
    Ok(PyFact {
        core: Arc::clone(core),
        id,
    })
}

fn py_expr_from(value: &Expr, py: Python<'_>) -> PyResult<Py<PyExpr>> {
    Py::new(
        py,
        PyExpr {
            inner: value.clone(),
        },
    )
}

#[pyclass(name = "Contradiction", module = "kernel_compiler._native")]
struct PyContradiction {
    #[pyo3(get)]
    fact: Py<PyFact>,
}

#[pyclass(name = "Fact", module = "kernel_compiler._native")]
struct PyFact {
    core: Arc<Mutex<ProofCore>>,
    id: FactId,
}

#[pymethods]
impl PyFact {
    #[getter]
    fn kind(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        Ok(
            kind_name(core.fact(self.id).map_err(PyValueError::new_err)?.kind)
                .into_pyobject(py)?
                .into_any()
                .unbind(),
        )
    }

    #[getter]
    fn id(&self) -> usize {
        self.id
    }

    #[getter]
    fn expression(&self, py: Python<'_>) -> PyResult<Py<PyExpr>> {
        let core = lock_core(&self.core)?;
        py_expr_from(
            &core
                .fact(self.id)
                .map_err(PyValueError::new_err)?
                .expression,
            py,
        )
    }

    #[getter]
    fn expr(&self, py: Python<'_>) -> PyResult<Py<PyExpr>> {
        self.expression(py)
    }

    #[getter]
    fn reference(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        Ok(fact_ref(
            py,
            &core.fact(self.id).map_err(PyValueError::new_err)?.reference,
        ))
    }

    #[getter]
    fn scope(&self) -> usize {
        self.core
            .lock()
            .map(|core| core.facts[self.id].scope)
            .unwrap_or(usize::MAX)
    }

    fn __hash__(&self) -> isize {
        self.id as isize
    }

    fn __richcmp__(
        &self,
        other: &Bound<'_, PyAny>,
        op: pyo3::basic::CompareOp,
    ) -> PyResult<PyObject> {
        let equal = other
            .extract::<PyRef<'_, PyFact>>()
            .map(|item| item.id == self.id && Arc::ptr_eq(&item.core, &self.core))
            .unwrap_or(false);
        let result = match op {
            pyo3::basic::CompareOp::Eq => equal,
            pyo3::basic::CompareOp::Ne => !equal,
            _ => false,
        };
        Ok(PyBool::new(other.py(), result)
            .to_owned()
            .into_any()
            .unbind())
    }

    fn __repr__(&self) -> String {
        format!("Fact(id={})", self.id)
    }
}

fn selector_from(value: &Bound<'_, PyAny>) -> PyResult<Selector> {
    if let Ok(index) = value.extract::<usize>() {
        Ok(Selector::Index(index))
    } else if let Ok(label) = value.extract::<String>() {
        Ok(Selector::Label(label))
    } else {
        Err(PyTypeError::new_err(
            "An obligation selector must be an index or label",
        ))
    }
}

fn assignment_from(value: &Bound<'_, PyAny>) -> PyResult<AssignmentValue> {
    if let Ok(fact) = value.extract::<PyRef<'_, PyFact>>() {
        Ok(AssignmentValue::Fact(fact.id))
    } else if let Ok(text) = value.extract::<String>() {
        if text == "Exact" {
            Ok(AssignmentValue::Exact)
        } else {
            Err(PyValueError::new_err(
                "expected a Fact or Exact terminal witness",
            ))
        }
    } else {
        Err(PyValueError::new_err(
            "expected a Fact or Exact terminal witness",
        ))
    }
}

fn definitions_from(
    core: &ProofCore,
    scope: ScopeId,
    definitions: &Bound<'_, PyAny>,
) -> PyResult<Vec<(u32, FactId)>> {
    let model = &core.scope(scope).map_err(PyValueError::new_err)?.model;
    let resolve = |key: &Bound<'_, PyAny>, value: &Bound<'_, PyAny>| -> PyResult<(u32, FactId)> {
        let fact = value.extract::<PyRef<'_, PyFact>>()?;
        let index = if let Ok(index) = key.extract::<u32>() {
            index
        } else if let Ok(expr) = key.extract::<PyRef<'_, PyExpr>>() {
            if expr.inner.constant != Q::zero()
                || expr.inner.terms.len() != 1
                || expr.inner.terms[0].1 != Q::one()
            {
                return Err(PyValueError::new_err(
                    "A pivot must be a coordinate or unit expression",
                ));
            }
            expr.inner.terms[0].0
        } else if let Ok(name) = key.extract::<String>() {
            *model
                .var_index
                .get(&name)
                .ok_or_else(|| PyKeyError::new_err(format!("Unknown variable {name:?}")))?
        } else {
            return Err(PyTypeError::new_err(
                "A pivot must be a coordinate, name, or unit expression",
            ));
        };
        Ok((index, fact.id))
    };
    let mut values = Vec::new();
    if let Ok(dict) = definitions.cast::<PyDict>() {
        for (key, value) in dict.iter() {
            values.push(resolve(&key, &value)?);
        }
    } else {
        for item in definitions.try_iter()? {
            let item = item?;
            let pair = item.cast::<PyTuple>().map_err(|_| {
                PyTypeError::new_err("definitions must be a mapping or pair sequence")
            })?;
            if pair.len() != 2 {
                return Err(PyTypeError::new_err(
                    "definitions must be a mapping or pair sequence",
                ));
            }
            values.push(resolve(&pair.get_item(0)?, &pair.get_item(1)?)?);
        }
    }
    Ok(values)
}

fn terms_from(core: &ProofCore, value: &Bound<'_, PyAny>) -> PyResult<Vec<(FactId, Q)>> {
    let _ = core;
    let mut terms = Vec::new();
    for item in value.try_iter()? {
        let item = item?;
        let pair = item
            .cast::<PyTuple>()
            .map_err(|_| PyTypeError::new_err("linear terms must be (Fact, multiplier) pairs"))?;
        if pair.len() != 2 {
            return Err(PyTypeError::new_err(
                "linear terms must be (Fact, multiplier) pairs",
            ));
        }
        let fact = pair.get_item(0)?.extract::<PyRef<'_, PyFact>>()?;
        terms.push((fact.id, q_from_py(&pair.get_item(1)?)?));
    }
    Ok(terms)
}

fn expr_vec(_py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Vec<Expr>> {
    let mut values = Vec::new();
    for item in value.try_iter()? {
        values.push(py_expr(&item?)?);
    }
    Ok(values)
}

#[pyclass(name = "Builder", module = "kernel_compiler._native")]
struct PyBuilder {
    core: Arc<Mutex<ProofCore>>,
    scope: ScopeId,
    direction: Option<bool>,
}

impl PyBuilder {
    fn new_handle(core: Arc<Mutex<ProofCore>>, scope: ScopeId, direction: Option<bool>) -> Self {
        Self {
            core,
            scope,
            direction,
        }
    }
}

#[pymethods]
impl PyBuilder {
    #[new]
    fn new(model: &Bound<'_, PyAny>) -> PyResult<Self> {
        let model = model.extract::<PyRef<'_, PyModel>>()?;
        let core = ProofCore::standalone(model.inner.clone()).map_err(PyValueError::new_err)?;
        Ok(Self::new_handle(Arc::new(Mutex::new(core)), 0, None))
    }

    #[getter]
    fn model(&self, py: Python<'_>) -> PyResult<Py<PyModel>> {
        let core = lock_core(&self.core)?;
        Py::new(
            py,
            PyModel {
                inner: (*core.scope(self.scope).map_err(PyValueError::new_err)?.model).clone(),
            },
        )
    }

    #[getter]
    fn parent(&self) -> PyResult<Option<PyBuilder>> {
        let core = lock_core(&self.core)?;
        Ok(core
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .parent
            .map(|parent| Self::new_handle(Arc::clone(&self.core), parent, self.direction)))
    }

    #[getter]
    fn assumptions(&self) -> PyResult<Vec<PyFact>> {
        let core = lock_core(&self.core)?;
        core.scope(self.scope)
            .map_err(PyValueError::new_err)?
            .assumptions
            .iter()
            .map(|id| py_fact(&self.core, *id))
            .collect()
    }

    #[getter]
    fn steps(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        let values = PyList::empty(py);
        for step in &core.scope(self.scope).map_err(PyValueError::new_err)?.steps {
            values.append(step_to_py(py, step)?)?;
        }
        Ok(values.into_any().unbind())
    }

    #[getter]
    fn end(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        match &core.scope(self.scope).map_err(PyValueError::new_err)?.end {
            None => Ok(py.None()),
            Some(end) => end_to_py(py, end, &core),
        }
    }

    #[getter]
    fn children(&self) -> PyResult<Option<Vec<PyBuilder>>> {
        let core = lock_core(&self.core)?;
        Ok(core
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .children
            .as_ref()
            .map(|children| {
                children
                    .iter()
                    .map(|id| Self::new_handle(Arc::clone(&self.core), *id, self.direction))
                    .collect()
            }))
    }

    fn ref_(&self, py: Python<'_>, kind: &str, site: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let mut core = lock_core(&self.core)?;
        let identifier = if let Ok(index) = site.extract::<u32>() {
            Identifier::Index(index)
        } else if let Ok(name) = site.extract::<String>() {
            Identifier::Name(name)
        } else if let Ok(expr) = site.extract::<PyRef<'_, PyExpr>>() {
            if expr.inner.constant != Q::zero()
                || expr.inner.terms.len() != 1
                || expr.inner.terms[0].1 != Q::one()
            {
                return Err(PyValueError::new_err(
                    "A variable reference expression must be exactly one unit coordinate",
                ));
            }
            Identifier::Index(expr.inner.terms[0].0)
        } else {
            return Err(PyTypeError::new_err("Invalid model identifier"));
        };
        let id = core
            .ref_fact(self.scope, kind, &identifier)
            .map_err(PyValueError::new_err)?;
        let _ = py;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn lower(&self, py: Python<'_>, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.ref_(py, "VarLower", variable)
    }

    fn upper(&self, py: Python<'_>, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.ref_(py, "VarUpper", variable)
    }

    fn integer(&self, py: Python<'_>, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.ref_(py, "VarInt", variable)
    }

    #[pyo3(signature = (row, side=None))]
    fn row(&self, py: Python<'_>, row: &Bound<'_, PyAny>, side: Option<&str>) -> PyResult<PyFact> {
        let side = match side {
            None => None,
            Some(value) => Some(value.to_string()),
        };
        let (kind, index) = {
            let core = lock_core(&self.core)?;
            let model = &core.scope(self.scope).map_err(PyValueError::new_err)?.model;
            let index = if let Ok(index) = row.extract::<u32>() {
                index
            } else if let Ok(name) = row.extract::<String>() {
                *model
                    .row_index
                    .get(&name)
                    .ok_or_else(|| PyKeyError::new_err(format!("Unknown row {name:?}")))?
            } else {
                return Err(PyTypeError::new_err("Invalid row identifier"));
            };
            let row = model
                .inner
                .rows
                .get(index as usize)
                .ok_or_else(|| PyIndexError::new_err("row index outside model"))?;
            let side = match side.as_deref() {
                Some("Lower") => "Lower",
                Some("Upper") => "Upper",
                Some("Eq") => "Eq",
                Some(other) => {
                    return Err(PyValueError::new_err(format!("Unknown row side {other:?}")));
                }
                None => {
                    if row.lower.is_some() && row.lower == row.upper {
                        "Eq"
                    } else if row.lower.is_some() && row.upper.is_some() {
                        return Err(PyValueError::new_err(
                            "A ranged row needs side='Lower' or side='Upper'",
                        ));
                    } else if row.lower.is_some() {
                        "Lower"
                    } else {
                        "Upper"
                    }
                }
            };
            (format!("Row{side}"), index)
        };
        self.ref_(py, &kind, &index.into_pyobject(py)?.into_any())
    }

    fn find(
        &self,
        py: Python<'_>,
        kind: &str,
        expression: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let kind = parse_kind(kind).map_err(PyValueError::new_err)?;
        let expression = py_expr(expression)?;
        let mut core = lock_core(&self.core)?;
        match core
            .find(self.scope, kind, &expression)
            .map_err(PyValueError::new_err)?
        {
            kernel_compiler_core::proof::FindResult::Exact => {
                Ok("Exact".into_pyobject(py)?.into_any().unbind())
            }
            kernel_compiler_core::proof::FindResult::Missing => Ok(py.None()),
            kernel_compiler_core::proof::FindResult::Fact(id) => Ok(py_fact(&self.core, id)?
                .into_pyobject(py)?
                .into_any()
                .unbind()),
        }
    }

    #[pyo3(signature = (kind, terms=None, constant=None, expect=None))]
    fn lin(
        &self,
        _py: Python<'_>,
        kind: &str,
        terms: Option<&Bound<'_, PyAny>>,
        constant: Option<&Bound<'_, PyAny>>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let kind = parse_kind(kind).map_err(PyValueError::new_err)?;
        let terms = match terms {
            Some(value) => terms_from(&*lock_core(&self.core)?, value)?,
            None => Vec::new(),
        };
        let constant = match constant {
            Some(value) if !value.is_none() => q_from_py(value)?,
            _ => Q::zero(),
        };
        let expect = expect.map(py_expr).transpose()?;
        let id = lock_core(&self.core)?
            .lin(self.scope, kind, &terms, constant, expect.as_ref())
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    #[pyo3(signature = (terms=None, constant=None, expect=None))]
    fn eq(
        &self,
        py: Python<'_>,
        terms: Option<&Bound<'_, PyAny>>,
        constant: Option<&Bound<'_, PyAny>>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        self.lin(py, "Eq", terms, constant, expect)
    }

    #[pyo3(signature = (terms=None, constant=None, expect=None))]
    fn le(
        &self,
        py: Python<'_>,
        terms: Option<&Bound<'_, PyAny>>,
        constant: Option<&Bound<'_, PyAny>>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        self.lin(py, "Le", terms, constant, expect)
    }

    #[pyo3(signature = (terms=None, constant=None, expect=None))]
    fn int(
        &self,
        py: Python<'_>,
        terms: Option<&Bound<'_, PyAny>>,
        constant: Option<&Bound<'_, PyAny>>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        self.lin(py, "Int", terms, constant, expect)
    }

    fn box_le(&self, expression: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let expression = py_expr(expression)?;
        let id = lock_core(&self.core)?
            .box_le(self.scope, expression)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn eq_on_fixed(
        &self,
        expression: &Bound<'_, PyAny>,
        fixes: &Bound<'_, PyAny>,
    ) -> PyResult<PyFact> {
        let expression = py_expr(expression)?;
        let dict = fixes
            .cast::<PyDict>()
            .map_err(|_| PyTypeError::new_err("fixes must be a mapping"))?;
        let mut values = HashMap::new();
        for (key, value) in dict.iter() {
            let index = if let Ok(index) = key.extract::<u32>() {
                index
            } else if let Ok(name) = key.extract::<String>() {
                let core = lock_core(&self.core)?;
                *core
                    .scope(self.scope)
                    .map_err(PyValueError::new_err)?
                    .model
                    .var_index
                    .get(&name)
                    .ok_or_else(|| PyKeyError::new_err(format!("Unknown variable {name:?}")))?
            } else {
                return Err(PyTypeError::new_err("Invalid fixing coordinate"));
            };
            values.insert(index, value.extract::<PyRef<'_, PyFact>>()?.id);
        }
        let id = lock_core(&self.core)?
            .eq_on_fixed(self.scope, expression, &values)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn zero_sum(
        &self,
        py: Python<'_>,
        fact: &Bound<'_, PyAny>,
        zeros: &Bound<'_, PyAny>,
        scale: &Bound<'_, PyAny>,
        coordinates: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?.id;
        let dict = zeros
            .cast::<PyDict>()
            .map_err(|_| PyTypeError::new_err("zeros must be a mapping"))?;
        let mut values = HashMap::new();
        for (key, value) in dict.iter() {
            let index = if let Ok(index) = key.extract::<u32>() {
                index
            } else if let Ok(name) = key.extract::<String>() {
                let core = lock_core(&self.core)?;
                *core
                    .scope(self.scope)
                    .map_err(PyValueError::new_err)?
                    .model
                    .var_index
                    .get(&name)
                    .ok_or_else(|| PyKeyError::new_err(format!("Unknown variable {name:?}")))?
            } else {
                return Err(PyTypeError::new_err("Invalid zero coordinate"));
            };
            values.insert(index, value.extract::<PyRef<'_, PyFact>>()?.id);
        }
        let scale = q_from_py(scale)?;
        let coordinates = coordinates.map(|items| expr_indices(items)).transpose()?;
        let result = lock_core(&self.core)?
            .zero_sum(self.scope, fact, &values, scale, coordinates.as_deref())
            .map_err(PyValueError::new_err)?;
        let dict = PyDict::new(py);
        for (index, id) in result {
            dict.set_item(
                index,
                py_fact(&self.core, id)?
                    .into_pyobject(py)?
                    .into_any()
                    .unbind(),
            )?;
        }
        Ok(dict.into_any().unbind())
    }

    fn round(&self, le: &Bound<'_, PyAny>, integer: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let le = le.extract::<PyRef<'_, PyFact>>()?.id;
        let integer = integer.extract::<PyRef<'_, PyFact>>()?.id;
        let id = lock_core(&self.core)?
            .round(self.scope, le, integer)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn parity_fix(
        &self,
        variable: &Bound<'_, PyAny>,
        equality: &Bound<'_, PyAny>,
    ) -> PyResult<PyFact> {
        let variable = if let Ok(index) = variable.extract::<u32>() {
            index
        } else if let Ok(name) = variable.extract::<String>() {
            *lock_core(&self.core)?
                .scope(self.scope)
                .map_err(PyValueError::new_err)?
                .model
                .var_index
                .get(&name)
                .ok_or_else(|| PyKeyError::new_err(format!("Unknown variable {name:?}")))?
        } else {
            expr_index(variable)?
        };
        let equality = equality.extract::<PyRef<'_, PyFact>>()?.id;
        let id = lock_core(&self.core)?
            .parity_fix(self.scope, variable, equality)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn eqpair(&self, positive: &Bound<'_, PyAny>, negative: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let positive = positive.extract::<PyRef<'_, PyFact>>()?.id;
        let negative = negative.extract::<PyRef<'_, PyFact>>()?.id;
        let id = lock_core(&self.core)?
            .eqpair(self.scope, positive, negative)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    #[pyo3(signature = (fact, definitions, expect=None))]
    fn rewrite(
        &self,
        fact: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyAny>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?.id;
        let definitions = {
            let core = lock_core(&self.core)?;
            definitions_from(&core, self.scope, definitions)?
        };
        let expect = expect.map(py_expr).transpose()?;
        let id = lock_core(&self.core)?
            .rewrite(self.scope, fact, &definitions, expect)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn rewrite_many(
        &self,
        facts: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<PyFact>> {
        let mut values = Vec::new();
        for fact in facts.try_iter()? {
            values.push(fact?.extract::<PyRef<'_, PyFact>>()?.id);
        }
        let definitions = {
            let core = lock_core(&self.core)?;
            definitions_from(&core, self.scope, definitions)?
        };
        let plan = {
            let core = lock_core(&self.core)?;
            kernel_compiler_core::proof::PivotPlan::new(&core, self.scope, &definitions)
                .map_err(PyValueError::new_err)?
        };
        let mut result = Vec::new();
        for fact in values {
            let id = lock_core(&self.core)?
                .rewrite_plan(self.scope, fact, &plan, None)
                .map_err(PyValueError::new_err)?;
            result.push(PyFact {
                core: Arc::clone(&self.core),
                id,
            });
        }
        Ok(result)
    }

    fn derive_substitution(
        &self,
        goal: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyAny>,
        residual: &Bound<'_, PyAny>,
        kind: Option<&str>,
    ) -> PyResult<PyFact> {
        let goal = py_expr(goal)?;
        let definitions = {
            let core = lock_core(&self.core)?;
            definitions_from(&core, self.scope, definitions)?
        };
        let residual = residual.extract::<PyRef<'_, PyFact>>()?.id;
        let kind = kind
            .map(parse_kind)
            .transpose()
            .map_err(PyValueError::new_err)?;
        let id = lock_core(&self.core)?
            .derive_substitution(self.scope, goal, &definitions, residual, kind)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn derive_substitution_many(
        &self,
        items: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyAny>,
        kind: Option<&str>,
    ) -> PyResult<Vec<PyFact>> {
        let definitions = {
            let core = lock_core(&self.core)?;
            definitions_from(&core, self.scope, definitions)?
        };
        let plan = {
            let core = lock_core(&self.core)?;
            kernel_compiler_core::proof::PivotPlan::new(&core, self.scope, &definitions)
                .map_err(PyValueError::new_err)?
        };
        let kind = kind
            .map(parse_kind)
            .transpose()
            .map_err(PyValueError::new_err)?;
        let mut result = Vec::new();
        for item in items.try_iter()? {
            let item = item?;
            let pair = item
                .cast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("items must be (goal, residual) pairs"))?;
            let goal = py_expr(&pair.get_item(0)?)?;
            let residual = pair.get_item(1)?.extract::<PyRef<'_, PyFact>>()?.id;
            let id = lock_core(&self.core)?
                .derive_substitution_plan(self.scope, goal, &plan, residual, kind)
                .map_err(PyValueError::new_err)?;
            result.push(PyFact {
                core: Arc::clone(&self.core),
                id,
            });
        }
        Ok(result)
    }

    fn substitution(
        &self,
        py: Python<'_>,
        definitions: &Bound<'_, PyAny>,
        goals: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<PyFact>> {
        let definitions = {
            let core = lock_core(&self.core)?;
            definitions_from(&core, self.scope, definitions)?
        };
        let goals = expr_vec(py, goals)?;
        let ids = lock_core(&self.core)?
            .substitution(self.scope, &definitions, &goals)
            .map_err(PyValueError::new_err)?;
        Ok(ids
            .into_iter()
            .map(|id| PyFact {
                core: Arc::clone(&self.core),
                id,
            })
            .collect())
    }

    fn drop(&self, facts: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut ids = Vec::new();
        for fact in facts.try_iter()? {
            ids.push(fact?.extract::<PyRef<'_, PyFact>>()?.id);
        }
        lock_core(&self.core)?
            .drop_facts(self.scope, &ids)
            .map_err(PyValueError::new_err)
    }

    fn absurd(&self, py: Python<'_>, fact: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?.id;
        lock_core(&self.core)?
            .absurd(self.scope, fact)
            .map_err(PyValueError::new_err)?;
        let handle = Py::new(
            py,
            PyFact {
                core: Arc::clone(&self.core),
                id: fact,
            },
        )?;
        Ok(Py::new(py, PyContradiction { fact: handle })?
            .into_bound(py)
            .into_any()
            .unbind())
    }

    fn branch(
        &self,
        _py: Python<'_>,
        expression: &Bound<'_, PyAny>,
    ) -> PyResult<(PyBuilder, PyFact)> {
        let expression = py_expr(expression)?;
        let (child, fact) = lock_core(&self.core)?
            .branch(self.scope, expression)
            .map_err(PyValueError::new_err)?;
        Ok((
            PyBuilder::new_handle(Arc::clone(&self.core), child, self.direction),
            PyFact {
                core: Arc::clone(&self.core),
                id: fact,
            },
        ))
    }

    fn split_options(
        &self,
        py: Python<'_>,
        expression: &Bound<'_, PyAny>,
        integer: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<(PyObject, Option<PyFact>)> {
        // Callers pass either a Fact, True, False, or None. The Python facade handles
        // the boolean shorthands before calling this native primitive.
        let expression = py_expr(expression)?;
        let integer = integer
            .map(|value| value.extract::<PyRef<'_, PyFact>>())
            .transpose()?;
        let (expression, integer) = {
            let mut core = lock_core(&self.core)?;
            core.split_options(self.scope, expression, integer.map(|item| item.id))
                .map_err(PyValueError::new_err)?
        };
        let expression = py_expr_from(&expression, py)?;
        let fact = integer.map(|id| PyFact {
            core: Arc::clone(&self.core),
            id,
        });
        Ok((expression.into_bound(py).into_any().unbind(), fact))
    }

    fn finish_split(
        &self,
        expression: &Bound<'_, PyAny>,
        integer: Option<&Bound<'_, PyAny>>,
        left: &Bound<'_, PyAny>,
        right: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let expression = py_expr(expression)?;
        let integer = integer
            .map(|value| value.extract::<PyRef<'_, PyFact>>())
            .transpose()?
            .map(|fact| fact.id);
        let left = left.extract::<PyRef<'_, PyBuilder>>()?.scope;
        let right = right.extract::<PyRef<'_, PyBuilder>>()?.scope;
        lock_core(&self.core)?
            .finish_split(self.scope, expression, integer, left, right)
            .map_err(PyValueError::new_err)
    }

    fn close_absurd(&self, fact: &Bound<'_, PyAny>) -> PyResult<()> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?.id;
        lock_core(&self.core)?
            .close_absurd(self.scope, fact)
            .map_err(PyValueError::new_err)
    }

    fn plotkin(
        &self,
        bits: u32,
        distance: u32,
        variables: &Bound<'_, PyAny>,
        cliques: &Bound<'_, PyAny>,
    ) -> PyResult<PyFact> {
        let mut values = Vec::new();
        for item in variables.try_iter()? {
            let pair = item?
                .cast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("variables must be (index, label) pairs"))?
                .clone();
            values.push((
                pair.get_item(0)?.extract::<u32>()?,
                pair.get_item(1)?.extract::<u64>()?,
            ));
        }
        let mut facts = Vec::new();
        for item in cliques.try_iter()? {
            facts.push(item?.extract::<PyRef<'_, PyFact>>()?.id);
        }
        let id = lock_core(&self.core)?
            .plotkin(self.scope, bits, distance, &values, &facts)
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn cases(
        &self,
        py: Python<'_>,
        expression: &Bound<'_, PyAny>,
        kind: &str,
        expect: &Bound<'_, PyAny>,
        left: &Bound<'_, PyAny>,
        right: &Bound<'_, PyAny>,
        integer: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let kind = parse_kind(kind).map_err(PyValueError::new_err)?;
        let expression = py_expr(expression)?;
        let expect = py_expr(expect)?;
        let integer = integer
            .map(|value| value.extract::<PyRef<'_, PyFact>>())
            .transpose()?
            .map(|fact| fact.id);
        let (expression, integer) = {
            let mut core = lock_core(&self.core)?;
            core.split_options(self.scope, expression, integer)
                .map_err(PyValueError::new_err)?
        };
        let mut branches = Vec::new();
        let split_expression = expression.clone();
        let second = if integer.is_some() {
            kernel_compiler_core::expr::subtract(
                &Expr {
                    constant: Q::one(),
                    terms: Vec::new(),
                },
                &expression,
            )
            .map_err(PyValueError::new_err)?
        } else {
            expression.clone()
        };
        for (index, (branch_expression, callback)) in [(expression, left), (second, right)]
            .into_iter()
            .enumerate()
        {
            let (child, assumption) = {
                let mut core = lock_core(&self.core)?;
                core.branch(self.scope, branch_expression)
                    .map_err(PyValueError::new_err)?
            };
            let child_builder = Py::new(
                py,
                PyBuilder::new_handle(Arc::clone(&self.core), child, self.direction),
            )?;
            let assumption_fact = Py::new(
                py,
                PyFact {
                    core: Arc::clone(&self.core),
                    id: assumption,
                },
            )?;
            let conclusion = callback.call1((child_builder.clone_ref(py), assumption_fact))?;
            let (end, branch_expression) =
                if let Ok(fact) = conclusion.extract::<PyRef<'_, PyFact>>() {
                    lock_core(&self.core)?
                        .visible(child, fact.id)
                        .map_err(PyValueError::new_err)?;
                    let data = lock_core(&self.core)?
                        .fact(fact.id)
                        .map_err(PyValueError::new_err)?
                        .clone();
                    if data.expression != expect || (data.kind != kind && data.kind != Kind::Eq) {
                        return Err(PyValueError::new_err(
                            "case branch must prove the common requested expression and kind",
                        ));
                    }
                    (CoreDerivationEnd::Witness(data.reference), data.expression)
                } else if let Ok(contradiction) = conclusion.getattr("fact") {
                    let fact = contradiction.extract::<PyRef<'_, PyFact>>()?;
                    lock_core(&self.core)?
                        .absurd(child, fact.id)
                        .map_err(PyValueError::new_err)?;
                    let reference = lock_core(&self.core)?
                        .fact(fact.id)
                        .map_err(PyValueError::new_err)?
                        .reference
                        .clone();
                    (CoreDerivationEnd::Absurd(reference), Expr::zero())
                } else {
                    return Err(PyTypeError::new_err(
                        "case callback must return a Fact or Contradiction",
                    ));
                };
            let (steps, end) = {
                let core = lock_core(&self.core)?;
                (
                    core.scope(child)
                        .map_err(PyValueError::new_err)?
                        .steps
                        .clone(),
                    end,
                )
            };
            branches.push((Derivation { steps, end }, branch_expression));
            let _ = index;
        }
        let (left_branch, right_branch) = (branches.remove(0), branches.remove(0));
        let _ = right_branch;
        let id = lock_core(&self.core)?
            .install_cases(
                self.scope,
                kind,
                expect,
                split_expression,
                integer,
                left_branch.0,
                right_branch.0,
            )
            .map_err(PyValueError::new_err)?;
        Ok(PyFact {
            core: Arc::clone(&self.core),
            id,
        })
    }

    fn split(
        &self,
        py: Python<'_>,
        expression: &Bound<'_, PyAny>,
        left: &Bound<'_, PyAny>,
        right: &Bound<'_, PyAny>,
        integer: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Vec<PyBuilder>> {
        let expression = py_expr(expression)?;
        let integer = integer
            .map(|value| value.extract::<PyRef<'_, PyFact>>())
            .transpose()?
            .map(|fact| fact.id);
        let (expression, integer) = {
            let mut core = lock_core(&self.core)?;
            core.split_options(self.scope, expression, integer)
                .map_err(PyValueError::new_err)?
        };
        let second = if integer.is_some() {
            kernel_compiler_core::expr::subtract(
                &Expr {
                    constant: Q::one(),
                    terms: Vec::new(),
                },
                &expression,
            )
            .map_err(PyValueError::new_err)?
        } else {
            expression.clone()
        };
        let mut children = Vec::new();
        for (branch_expression, callback) in [(expression.clone(), left), (second, right)] {
            let (child, assumption) = {
                let mut core = lock_core(&self.core)?;
                core.branch(self.scope, branch_expression)
                    .map_err(PyValueError::new_err)?
            };
            let child_builder = Py::new(
                py,
                PyBuilder::new_handle(Arc::clone(&self.core), child, self.direction),
            )?;
            let assumption = Py::new(
                py,
                PyFact {
                    core: Arc::clone(&self.core),
                    id: assumption,
                },
            )?;
            callback.call1((child_builder.clone_ref(py), assumption))?;
            if lock_core(&self.core)?
                .scope(child)
                .map_err(PyValueError::new_err)?
                .end
                .is_none()
            {
                return Err(PyValueError::new_err(
                    "Each terminal split branch must return a complete map or close Absurd",
                ));
            }
            children.push(PyBuilder::new_handle(
                Arc::clone(&self.core),
                child,
                self.direction,
            ));
        }
        lock_core(&self.core)?
            .finish_split(
                self.scope,
                expression,
                integer,
                children[0].scope,
                children[1].scope,
            )
            .map_err(PyValueError::new_err)?;
        Ok(children)
    }

    fn map(&self, mapping: &Bound<'_, PyAny>) -> PyResult<()> {
        let values = expr_vec(mapping.py(), mapping)?;
        let mut core = lock_core(&self.core)?;
        core.scope_mut(self.scope)
            .map_err(PyValueError::new_err)?
            .mapping = Some(values);
        Ok(())
    }

    fn check(&self, selector: &Bound<'_, PyAny>, fact: &Bound<'_, PyAny>) -> PyResult<()> {
        let selector = selector_from(selector)?;
        let value = assignment_from(fact)?;
        lock_core(&self.core)?
            .scope_mut(self.scope)
            .map_err(PyValueError::new_err)?
            .assigned
            .insert(selector, value);
        Ok(())
    }

    #[pyo3(signature = (scope=None, mapping=None))]
    fn plan(
        &self,
        py: Python<'_>,
        scope: Option<&Bound<'_, PyAny>>,
        mapping: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        let scope = scope
            .map(|value| {
                value
                    .extract::<PyRef<'_, PyBuilder>>()
                    .map(|item| item.scope)
            })
            .transpose()?
            .unwrap_or(self.scope);
        let mapping = match mapping {
            Some(value) => expr_vec(py, value)?,
            None => lock_core(&self.core)?.mapping(self.scope).ok_or_else(|| {
                PyValueError::new_err("Declare the complete output map before planning obligations")
            })?,
        };
        let values = lock_core(&self.core)?
            .plan(scope, &mapping, &Limits::default())
            .map_err(PyValueError::new_err)?;
        let list = PyList::empty(py);
        for item in values {
            list.append(obligation_to_py(py, &item)?)?;
        }
        Ok(list.into_any().unbind())
    }

    #[pyo3(signature = (scope=None, mapping=None, witnesses=None, auto=true))]
    fn missing(
        &self,
        py: Python<'_>,
        scope: Option<&Bound<'_, PyAny>>,
        mapping: Option<&Bound<'_, PyAny>>,
        witnesses: Option<&Bound<'_, PyAny>>,
        auto: bool,
    ) -> PyResult<PyObject> {
        let scope = scope
            .map(|value| {
                value
                    .extract::<PyRef<'_, PyBuilder>>()
                    .map(|item| item.scope)
            })
            .transpose()?
            .unwrap_or(self.scope);
        let mapping = match mapping {
            Some(value) => expr_vec(py, value)?,
            None => lock_core(&self.core)?.mapping(self.scope).ok_or_else(|| {
                PyValueError::new_err("Declare the complete output map before planning obligations")
            })?,
        };
        let witnesses = witnesses_from(witnesses)?;
        let result = lock_core(&self.core)?
            .resolve(scope, &mapping, &witnesses, auto, &Limits::default())
            .map_err(PyValueError::new_err)?;
        let list = PyList::empty(py);
        for item in result.missing {
            let value = obligation_to_py(
                py,
                &Obligation {
                    index: item.index,
                    kind: item.obligation.kind,
                    expression: item.obligation.expression,
                    origin: item.obligation.origin,
                },
            )?;
            let dict = value.cast_bound::<PyDict>(py)?;
            dict.set_item("index", item.index)?;
            list.append(dict)?;
        }
        Ok(list.into_any().unbind())
    }

    #[pyo3(signature = (mapping=None, witnesses=None, scope=None, auto=true))]
    fn complete(
        &self,
        py: Python<'_>,
        mapping: Option<&Bound<'_, PyAny>>,
        witnesses: Option<&Bound<'_, PyAny>>,
        scope: Option<&Bound<'_, PyAny>>,
        auto: bool,
    ) -> PyResult<()> {
        let scope = scope
            .map(|value| {
                value
                    .extract::<PyRef<'_, PyBuilder>>()
                    .map(|item| item.scope)
            })
            .transpose()?
            .unwrap_or(self.scope);
        let mapping = match mapping {
            Some(value) => expr_vec(py, value)?,
            None => lock_core(&self.core)?.mapping(self.scope).ok_or_else(|| {
                PyValueError::new_err("Declare the complete map before complete()")
            })?,
        };
        let witnesses = witnesses_from(witnesses)?;
        lock_core(&self.core)?
            .complete(scope, &mapping, &witnesses, auto, &Limits::default())
            .map_err(PyValueError::new_err)
    }

    #[pyo3(signature = (mapping, checks, scope=None, auto=true))]
    fn complete_ordered(
        &self,
        py: Python<'_>,
        mapping: &Bound<'_, PyAny>,
        checks: &Bound<'_, PyAny>,
        scope: Option<&Bound<'_, PyAny>>,
        auto: bool,
    ) -> PyResult<()> {
        let scope = scope
            .map(|value| {
                value
                    .extract::<PyRef<'_, PyBuilder>>()
                    .map(|item| item.scope)
            })
            .transpose()?
            .unwrap_or(self.scope);
        let mapping = expr_vec(py, mapping)?;
        let mut values = Vec::new();
        for item in checks.try_iter()? {
            values.push(assignment_from(&item?)?);
        }
        lock_core(&self.core)?
            .complete_ordered(scope, &mapping, &values, auto, &Limits::default())
            .map_err(PyValueError::new_err)
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        let block = core.to_block(self.scope).map_err(PyValueError::new_err)?;
        block_to_py(py, &block)
    }
}

fn witnesses_from(value: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<(Selector, AssignmentValue)>> {
    let Some(value) = value else {
        return Ok(Vec::new());
    };
    let dict = value
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("witnesses must be a mapping"))?;
    let mut values = Vec::new();
    for (key, fact) in dict.iter() {
        values.push((selector_from(&key)?, assignment_from(&fact)?));
    }
    Ok(values)
}

fn expr_indices(value: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
    let mut values = Vec::new();
    for item in value.try_iter()? {
        values.push(expr_index(&item?)?);
    }
    Ok(values)
}

fn expr_index(value: &Bound<'_, PyAny>) -> PyResult<u32> {
    if let Ok(index) = value.extract::<u32>() {
        Ok(index)
    } else if let Ok(expr) = value.extract::<PyRef<'_, PyExpr>>() {
        if expr.inner.constant != Q::zero()
            || expr.inner.terms.len() != 1
            || expr.inner.terms[0].1 != Q::one()
        {
            return Err(PyValueError::new_err(
                "A variable reference expression must be exactly one unit coordinate",
            ));
        }
        Ok(expr.inner.terms[0].0)
    } else if let Ok(name) = value.extract::<String>() {
        Err(PyValueError::new_err(format!(
            "unresolved coordinate name {name:?}"
        )))
    } else {
        Err(PyTypeError::new_err("Invalid coordinate identifier"))
    }
}

fn obligation_to_py(py: Python<'_>, item: &Obligation) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    dict.set_item("index", item.index)?;
    dict.set_item("kind", kind_name(item.kind))?;
    dict.set_item("expression", py_expr_from(&item.expression, py)?)?;
    dict.set_item(
        "origin",
        json_to_py(py, &serde_json::to_value(&item.origin).unwrap())?,
    )?;
    Ok(dict.into_any().unbind())
}

fn block_to_py(py: Python<'_>, block: &Block) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    let steps = PyList::empty(py);
    for step in &block.steps {
        steps.append(step_to_py(py, step)?)?;
    }
    dict.set_item("steps", steps)?;
    dict.set_item("end", end_to_block_py(py, &block.end)?)?;
    Ok(dict.into_any().unbind())
}

fn step_to_py(py: Python<'_>, step: &Step) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    match step {
        Step::Lin {
            id,
            kind,
            constant,
            terms,
        } => {
            let item = PyDict::new(py);
            item.set_item("id", id)?;
            item.set_item("kind", kind_name(*kind))?;
            item.set_item("constant", q_text(constant))?;
            let values = PyList::empty(py);
            for (reference, multiplier) in terms {
                values.append(PyList::new(
                    py,
                    [
                        ref_to_py(py, reference),
                        q_text(multiplier).into_pyobject(py)?.into_any().unbind(),
                    ],
                )?)?;
            }
            item.set_item("terms", values)?;
            dict.set_item("Lin", item)?;
        }
        Step::Round { id, le, integer } => {
            let item = PyDict::new(py);
            item.set_item("id", id)?;
            item.set_item("le", ref_to_py(py, le))?;
            item.set_item("integer", ref_to_py(py, integer))?;
            dict.set_item("Round", item)?;
        }
        Step::Drop { ids } => {
            let item = PyDict::new(py);
            item.set_item("ids", ids)?;
            dict.set_item("Drop", item)?;
        }
        Step::EqPair {
            id,
            positive,
            negative,
        } => {
            let item = PyDict::new(py);
            item.set_item("id", id)?;
            item.set_item("positive", ref_to_py(py, positive))?;
            item.set_item("negative", ref_to_py(py, negative))?;
            dict.set_item("EqPair", item)?;
        }
        Step::Cases(case) => {
            let item = PyDict::new(py);
            item.set_item("id", case.id)?;
            item.set_item("kind", kind_name(case.kind))?;
            item.set_item("expression", py_expr_from(&case.expression, py)?)?;
            item.set_item("split", py_expr_from(&case.split, py)?)?;
            item.set_item(
                "integer",
                case.integer
                    .as_ref()
                    .map(|r| ref_to_py(py, r))
                    .unwrap_or_else(|| py.None()),
            )?;
            item.set_item("left", derivation_to_py(py, &case.left)?)?;
            item.set_item("right", derivation_to_py(py, &case.right)?)?;
            dict.set_item("Cases", item)?;
        }
        Step::Plotkin {
            id,
            bits,
            distance,
            variables,
            cliques,
        } => {
            let item = PyDict::new(py);
            item.set_item("id", id)?;
            item.set_item("bits", bits)?;
            item.set_item("distance", distance)?;
            let values = PyList::empty(py);
            for (index, label) in variables {
                values.append((*index, *label))?;
            }
            item.set_item("variables", values)?;
            item.set_item(
                "cliques",
                cliques.iter().map(|r| ref_to_py(py, r)).collect::<Vec<_>>(),
            )?;
            dict.set_item("Plotkin", item)?;
        }
    }
    Ok(dict.into_any().unbind())
}

fn derivation_to_py(py: Python<'_>, derivation: &Derivation) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    let steps = PyList::empty(py);
    for step in &derivation.steps {
        steps.append(step_to_py(py, step)?)?;
    }
    dict.set_item("steps", steps)?;
    dict.set_item(
        "end",
        match &derivation.end {
            CoreDerivationEnd::Witness(reference) => {
                let item = PyDict::new(py);
                item.set_item("Witness", ref_to_py(py, reference))?;
                item.into_any().unbind()
            }
            CoreDerivationEnd::Absurd(reference) => {
                let item = PyDict::new(py);
                item.set_item("Absurd", ref_to_py(py, reference))?;
                item.into_any().unbind()
            }
        },
    )?;
    Ok(dict.into_any().unbind())
}

fn end_to_block_py(py: Python<'_>, end: &End) -> PyResult<PyObject> {
    end_to_block_py_full(py, end)
}

fn end_to_py(py: Python<'_>, end: &ScopeEnd, _core: &ProofCore) -> PyResult<PyObject> {
    match end {
        ScopeEnd::Return { map, checks } => {
            let item = PyDict::new(py);
            let values = PyList::empty(py);
            for expression in map {
                values.append(py_expr_from(expression, py)?)?;
            }
            item.set_item("map", values)?;
            item.set_item(
                "checks",
                checks.iter().map(|r| ref_to_py(py, r)).collect::<Vec<_>>(),
            )?;
            let dict = PyDict::new(py);
            dict.set_item("Return", item)?;
            Ok(dict.into_any().unbind())
        }
        ScopeEnd::Split {
            expression,
            integer,
            left,
            right,
        } => {
            let item = PyDict::new(py);
            item.set_item("expression", py_expr_from(expression, py)?)?;
            item.set_item(
                "integer",
                integer
                    .as_ref()
                    .map(|r| ref_to_py(py, r))
                    .unwrap_or_else(|| py.None()),
            )?;
            let dict = PyDict::new(py);
            dict.set_item("Split", item)?;
            let _ = (left, right);
            Ok(dict.into_any().unbind())
        }
        ScopeEnd::Absurd { fact } => {
            let item = PyDict::new(py);
            item.set_item("fact", ref_to_py(py, fact))?;
            let dict = PyDict::new(py);
            dict.set_item("Absurd", item)?;
            Ok(dict.into_any().unbind())
        }
        _ => Ok(py.None()),
    }
}

#[pyclass(name = "Compiled", module = "kernel_compiler._native")]
struct PyCompiled {
    #[pyo3(get)]
    rpa: String,
    #[pyo3(get)]
    rpx: Py<pyo3::types::PyBytes>,
}

#[pyclass(name = "Proof", module = "kernel_compiler._native")]
struct PyProof {
    core: Arc<Mutex<ProofCore>>,
}

#[pymethods]
impl PyProof {
    #[new]
    fn new(source: &Bound<'_, PyAny>, target: &Bound<'_, PyAny>) -> PyResult<Self> {
        let source = source.extract::<PyRef<'_, PyModel>>()?;
        let target = target.extract::<PyRef<'_, PyModel>>()?;
        let core = ProofCore::new(source.inner.clone(), target.inner.clone())
            .map_err(PyValueError::new_err)?;
        Ok(Self {
            core: Arc::new(Mutex::new(core)),
        })
    }

    #[getter]
    fn source(&self, py: Python<'_>) -> PyResult<Py<PyModel>> {
        let core = lock_core(&self.core)?;
        Py::new(
            py,
            PyModel {
                inner: (*core.source).clone(),
            },
        )
    }

    #[getter]
    fn target(&self, py: Python<'_>) -> PyResult<Py<PyModel>> {
        let core = lock_core(&self.core)?;
        Py::new(
            py,
            PyModel {
                inner: (*core.target).clone(),
            },
        )
    }

    #[getter]
    fn forward(&self) -> PyBuilder {
        let scope = self.core.lock().map(|core| core.forward).unwrap_or(0);
        PyBuilder::new_handle(Arc::clone(&self.core), scope, Some(false))
    }

    #[getter]
    fn reverse(&self) -> PyBuilder {
        let scope = self.core.lock().map(|core| core.reverse).unwrap_or(0);
        PyBuilder::new_handle(Arc::clone(&self.core), scope, Some(true))
    }

    #[pyo3(signature = (work=None, live_facts=None, depth=None))]
    fn compile(
        &self,
        py: Python<'_>,
        work: Option<u64>,
        live_facts: Option<usize>,
        depth: Option<usize>,
    ) -> PyResult<PyCompiled> {
        let limits = parse_limit(work, live_facts, depth);
        let compiled = lock_core(&self.core)?
            .compile(&limits)
            .map_err(PyValueError::new_err)?;
        Ok(PyCompiled {
            rpa: compiled.rpa,
            rpx: pyo3::types::PyBytes::new(py, &compiled.rpx).unbind(),
        })
    }

    #[pyo3(signature = (work=None, live_facts=None, depth=None))]
    fn verify(
        &self,
        py: Python<'_>,
        work: Option<u64>,
        live_facts: Option<usize>,
        depth: Option<usize>,
    ) -> PyResult<PyObject> {
        let limits = parse_limit(work, live_facts, depth);
        let stats = lock_core(&self.core)?
            .verify(&limits)
            .map_err(PyValueError::new_err)?;
        json_to_py(py, &serde_json::to_value(stats).unwrap())
    }

    #[pyo3(signature = (work=None, live_facts=None, depth=None))]
    fn preflight(
        &self,
        py: Python<'_>,
        work: Option<u64>,
        live_facts: Option<usize>,
        depth: Option<usize>,
    ) -> PyResult<PyObject> {
        let limits = parse_limit(work, live_facts, depth);
        let value = lock_core(&self.core)?
            .preflight(&limits)
            .map_err(PyValueError::new_err)?;
        json_to_py(py, &value)
    }

    fn certificate(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        certificate_to_py(py, &core.certificate().map_err(PyValueError::new_err)?)
    }

    fn close(&self) {}

    fn revision(&self, scope: usize) -> PyResult<u64> {
        let core = lock_core(&self.core)?;
        core.scopes
            .get(scope)
            .map(|item| item.revision)
            .ok_or_else(|| PyValueError::new_err("unknown proof scope"))
    }

    fn ancestor_revisions(&self, scope: usize) -> PyResult<Vec<(usize, u64)>> {
        let core = lock_core(&self.core)?;
        if scope >= core.scopes.len() {
            return Err(PyValueError::new_err("unknown proof scope"));
        }
        Ok(core.ancestor_revisions(scope))
    }

    fn completion_current(&self, scope: usize) -> PyResult<bool> {
        let core = lock_core(&self.core)?;
        Ok(core.completion_current(scope))
    }
}

fn certificate_to_py(py: Python<'_>, certificate: &Certificate) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    dict.set_item("forward", block_to_py(py, &certificate.forward)?)?;
    dict.set_item("reverse", block_to_py(py, &certificate.reverse)?)?;
    Ok(dict.into_any().unbind())
}

fn witness_exprs(py: Python<'_>, values: &[Expr]) -> PyResult<PyObject> {
    let list = PyList::empty(py);
    for expression in values {
        list.append(py_expr_from(expression, py)?)?;
    }
    Ok(list.into_any().unbind())
}

fn refs_to_py(py: Python<'_>, values: &[Ref]) -> PyObject {
    let list = PyList::empty(py);
    for reference in values {
        list.append(ref_to_py(py, reference)).unwrap();
    }
    list.into_any().unbind()
}

fn end_to_block_py_full(py: Python<'_>, end: &End) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    match end {
        End::Return { map, checks } => {
            let item = PyDict::new(py);
            item.set_item("map", witness_exprs(py, map)?)?;
            item.set_item("checks", refs_to_py(py, checks))?;
            dict.set_item("Return", item)?;
        }
        End::Split {
            expression,
            integer,
            left,
            right,
        } => {
            let item = PyDict::new(py);
            item.set_item("expression", py_expr_from(expression, py)?)?;
            item.set_item(
                "integer",
                integer
                    .as_ref()
                    .map(|r| ref_to_py(py, r))
                    .unwrap_or_else(|| py.None()),
            )?;
            item.set_item("left", block_to_py(py, left)?)?;
            item.set_item("right", block_to_py(py, right)?)?;
            dict.set_item("Split", item)?;
        }
        End::Absurd { fact } => {
            let item = PyDict::new(py);
            item.set_item("fact", ref_to_py(py, fact))?;
            dict.set_item("Absurd", item)?;
        }
        End::IntervalLift { intervals, body } => {
            let item = PyDict::new(py);
            let values = PyList::empty(py);
            for interval in intervals {
                let entry = PyDict::new(py);
                entry.set_item("lower", witness_exprs(py, &interval.lower)?)?;
                entry.set_item("upper", witness_exprs(py, &interval.upper)?)?;
                entry.set_item("checks", refs_to_py(py, &interval.checks))?;
                values.append(entry)?;
            }
            item.set_item("intervals", values)?;
            item.set_item("body", block_to_py(py, body)?)?;
            dict.set_item("IntervalLift", item)?;
        }
        End::MenuLift { menus, body } => {
            let item = PyDict::new(py);
            let values = PyList::empty(py);
            for menu in menus {
                let entry = PyDict::new(py);
                entry.set_item("maximum_index", menu.maximum_index)?;
                entry.set_item("activation", py_expr_from(&menu.activation, py)?)?;
                entry.set_item("index", py_expr_from(&menu.index, py)?)?;
                entry.set_item("checks", refs_to_py(py, &menu.checks))?;
                values.append(entry)?;
            }
            item.set_item("menus", values)?;
            item.set_item("body", block_to_py(py, body)?)?;
            dict.set_item("MenuLift", item)?;
        }
        End::SignedLift {
            decompositions,
            body,
        } => {
            let item = PyDict::new(py);
            let values = PyList::empty(py);
            for decomposition in decompositions {
                let entry = PyDict::new(py);
                entry.set_item("capacity", q_text(&decomposition.capacity))?;
                entry.set_item("flow", py_expr_from(&decomposition.flow, py)?)?;
                entry.set_item("activation", py_expr_from(&decomposition.activation, py)?)?;
                entry.set_item("checks", refs_to_py(py, &decomposition.checks))?;
                values.append(entry)?;
            }
            item.set_item("decompositions", values)?;
            item.set_item("body", block_to_py(py, body)?)?;
            dict.set_item("SignedLift", item)?;
        }
        End::FlowLift { witness, body } => {
            let item = PyDict::new(py);
            item.set_item("nodes", witness.nodes)?;
            item.set_item(
                "arcs",
                witness
                    .arcs
                    .iter()
                    .map(|(a, b)| (*a, *b))
                    .collect::<Vec<_>>(),
            )?;
            let groups = PyList::empty(py);
            for group in &witness.groups {
                let entry = PyDict::new(py);
                entry.set_item("source", group.source)?;
                entry.set_item(
                    "commodities",
                    group
                        .commodities
                        .iter()
                        .map(|(a, b)| (*a, q_text(b)))
                        .collect::<Vec<_>>(),
                )?;
                entry.set_item("flows", witness_exprs(py, &group.flows)?)?;
                entry.set_item("nonnegative", refs_to_py(py, &group.nonnegative))?;
                entry.set_item("balances", refs_to_py(py, &group.balances))?;
                groups.append(entry)?;
            }
            item.set_item("groups", groups)?;
            item.set_item("body", block_to_py(py, body)?)?;
            dict.set_item("FlowLift", item)?;
        }
        End::SubflowLift { witness, body } => {
            let item = PyDict::new(py);
            item.set_item("nodes", witness.nodes)?;
            item.set_item(
                "arcs",
                witness
                    .arcs
                    .iter()
                    .map(|(a, b)| (*a, *b))
                    .collect::<Vec<_>>(),
            )?;
            let groups = PyList::empty(py);
            for group in &witness.groups {
                let entry = PyDict::new(py);
                entry.set_item("source", group.source)?;
                entry.set_item(
                    "demands",
                    group
                        .demands
                        .iter()
                        .map(|(a, b)| (*a, q_text(b)))
                        .collect::<Vec<_>>(),
                )?;
                entry.set_item("flows", witness_exprs(py, &group.flows)?)?;
                entry.set_item("nonnegative", refs_to_py(py, &group.nonnegative))?;
                entry.set_item("balances", refs_to_py(py, &group.balances))?;
                groups.append(entry)?;
            }
            item.set_item("groups", groups)?;
            item.set_item("body", block_to_py(py, body)?)?;
            dict.set_item("SubflowLift", item)?;
        }
    }
    Ok(dict.into_any().unbind())
}

#[pymethods]
impl PyModel {
    fn index_of(&self, identifier: &Bound<'_, PyAny>, row: bool) -> PyResult<u32> {
        self.index(identifier, row)
    }

    fn with_bound(
        &self,
        identifier: &Bound<'_, PyAny>,
        side: &str,
        value: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let index = self.index(identifier, false)?;
        let lower = if side == "lower" {
            Some(
                value
                    .map(|item| {
                        if item.is_none() {
                            Ok(None)
                        } else {
                            q_from_py(item).map(Some)
                        }
                    })
                    .transpose()?,
            )
        } else {
            None
        };
        let upper = if side == "upper" {
            Some(
                value
                    .map(|item| {
                        if item.is_none() {
                            Ok(None)
                        } else {
                            q_from_py(item).map(Some)
                        }
                    })
                    .transpose()?,
            )
        } else {
            None
        };
        let lower = lower.flatten();
        let upper = upper.flatten();
        if side != "lower" && side != "upper" {
            return Err(PyValueError::new_err(
                "bound side must be 'lower' or 'upper'",
            ));
        }
        self.wrap(self.inner.with_bounds(index, lower, upper))
    }
}

#[pymethods]
impl PyBuilder {
    #[getter]
    fn layout(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        match &core
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .layout
        {
            None => Ok(py.None()),
            Some(values) => json_to_py(py, &serde_json::Value::Array(values.clone())),
        }
    }

    #[getter]
    fn generated_variables(&self) -> PyResult<Vec<u32>> {
        Ok(lock_core(&self.core)?
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .generated_variables
            .clone())
    }

    #[getter]
    fn generated_rows(&self) -> PyResult<Vec<u32>> {
        Ok(lock_core(&self.core)?
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .generated_rows
            .clone())
    }

    #[getter]
    fn layout_kind(&self) -> PyResult<Option<String>> {
        Ok(lock_core(&self.core)?
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .layout_kind
            .map(str::to_string))
    }

    fn install_lift(
        &self,
        model: &Bound<'_, PyAny>,
        specification: &Bound<'_, PyAny>,
        layout: &str,
    ) -> PyResult<PyBuilder> {
        let model = model.extract::<PyRef<'_, PyModel>>()?;
        let extension = extension_from_py(specification)?;
        let scope = {
            let mut core = lock_core(&self.core)?;
            let child = core
                .install_lift_extension(self.scope, model.inner.clone(), extension)
                .map_err(PyValueError::new_err)?;
            let values: Vec<serde_json::Value> = serde_json::from_str(layout)
                .map_err(|error| PyValueError::new_err(error.to_string()))?;
            core.scope_mut(child).map_err(PyValueError::new_err)?.layout = Some(values);
            child
        };
        Ok(PyBuilder::new_handle(
            Arc::clone(&self.core),
            scope,
            self.direction,
        ))
    }
}

#[pyfunction]
fn prepare_extension(
    py: Python<'_>,
    model: &Bound<'_, PyAny>,
    specification: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let model = model.extract::<PyRef<'_, PyModel>>()?;
    let extension = extension_from_py(specification)?;
    let prepared = kernel_core::authoring::prepare_extension(
        &model.inner.inner,
        extension,
        &Limits::default(),
    )
    .map_err(|error| PyValueError::new_err(error.message().to_string()))?;
    let dict = PyDict::new(py);
    dict.set_item(
        "model",
        json_to_py(py, &kernel_core::model::to_json(&prepared.model))?,
    )?;
    let premises = PyList::empty(py);
    for premise in prepared.premises {
        let item = PyDict::new(py);
        item.set_item("kind", kind_name(premise.kind))?;
        item.set_item("expression", py_expr_from(&premise.expression, py)?)?;
        item.set_item("reference", ref_to_py(py, &premise.reference))?;
        premises.append(item)?;
    }
    dict.set_item("premises", premises)?;
    dict.set_item("statistics", json_to_py(py, &prepared.statistics)?)?;
    dict.set_item("layout", json_to_py(py, &prepared.layout)?)?;
    Ok(dict.into_any().unbind())
}

fn extension_from_py(value: &Bound<'_, PyAny>) -> PyResult<kernel_core::authoring::Extension> {
    use kernel_core::proof::{
        FlowGroup, FlowWitness, IntervalWitness, MenuWitness, SignedWitness, SubflowGroup,
        SubflowWitness,
    };
    let dict = value
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("extension must be a mapping"))?;
    if dict.len() != 1 {
        return Err(PyValueError::new_err(
            "extension requires exactly one variant",
        ));
    }
    let (tag, payload) = dict
        .iter()
        .next()
        .ok_or_else(|| PyValueError::new_err("empty extension"))?;
    let tag = tag.extract::<String>()?;
    let exprs = |value: &Bound<'_, PyAny>| -> PyResult<Vec<Expr>> {
        let mut out = Vec::new();
        for item in value.try_iter()? {
            out.push(expr_from_json_py(&item?)?);
        }
        Ok(out)
    };
    let refs = |value: &Bound<'_, PyAny>| -> PyResult<Vec<Ref>> {
        let mut out = Vec::new();
        for item in value.try_iter()? {
            out.push(ref_from_py(&item?)?);
        }
        Ok(out)
    };
    match tag.as_str() {
        "Interval" => {
            let mut values = Vec::new();
            for item in payload.try_iter()? {
                let item = item?;
                let map = item
                    .cast::<PyDict>()
                    .map_err(|_| PyValueError::new_err("interval must be a mapping"))?;
                values.push(IntervalWitness {
                    lower: exprs(
                        map.get_item("lower")?
                            .ok_or_else(|| PyValueError::new_err("interval lower missing"))?
                            .as_any(),
                    )?,
                    upper: exprs(
                        map.get_item("upper")?
                            .ok_or_else(|| PyValueError::new_err("interval upper missing"))?
                            .as_any(),
                    )?,
                    checks: refs(
                        map.get_item("checks")?
                            .ok_or_else(|| PyValueError::new_err("interval checks missing"))?
                            .as_any(),
                    )?,
                });
            }
            Ok(kernel_core::authoring::Extension::Interval(values))
        }
        "Menu" => {
            let mut values = Vec::new();
            for item in payload.try_iter()? {
                let item = item?;
                let map = item
                    .cast::<PyDict>()
                    .map_err(|_| PyValueError::new_err("menu must be a mapping"))?;
                values.push(MenuWitness {
                    maximum_index: map
                        .get_item("maximum_index")?
                        .ok_or_else(|| PyValueError::new_err("menu maximum_index missing"))?
                        .extract::<u32>()?,
                    activation: expr_from_json_py(
                        &map.get_item("activation")?
                            .ok_or_else(|| PyValueError::new_err("menu activation missing"))?,
                    )?,
                    index: expr_from_json_py(
                        &map.get_item("index")?
                            .ok_or_else(|| PyValueError::new_err("menu index missing"))?,
                    )?,
                    checks: refs(
                        map.get_item("checks")?
                            .ok_or_else(|| PyValueError::new_err("menu checks missing"))?
                            .as_any(),
                    )?,
                });
            }
            Ok(kernel_core::authoring::Extension::Menu(values))
        }
        "Signed" => {
            let mut values = Vec::new();
            for item in payload.try_iter()? {
                let item = item?;
                let map = item
                    .cast::<PyDict>()
                    .map_err(|_| PyValueError::new_err("signed must be a mapping"))?;
                values.push(SignedWitness {
                    capacity: q_from_py(
                        &map.get_item("capacity")?
                            .ok_or_else(|| PyValueError::new_err("signed capacity missing"))?,
                    )?,
                    flow: expr_from_json_py(
                        &map.get_item("flow")?
                            .ok_or_else(|| PyValueError::new_err("signed flow missing"))?,
                    )?,
                    activation: expr_from_json_py(
                        &map.get_item("activation")?
                            .ok_or_else(|| PyValueError::new_err("signed activation missing"))?,
                    )?,
                    checks: refs(
                        map.get_item("checks")?
                            .ok_or_else(|| PyValueError::new_err("signed checks missing"))?
                            .as_any(),
                    )?,
                });
            }
            Ok(kernel_core::authoring::Extension::Signed(values))
        }
        "Flow" | "Subflow" => {
            let map = payload
                .cast::<PyDict>()
                .map_err(|_| PyValueError::new_err("flow witness must be a mapping"))?;
            let nodes = map
                .get_item("nodes")?
                .ok_or_else(|| PyValueError::new_err("flow nodes missing"))?
                .extract::<u32>()?;
            let mut arcs = Vec::new();
            for item in map
                .get_item("arcs")?
                .ok_or_else(|| PyValueError::new_err("flow arcs missing"))?
                .try_iter()?
            {
                let pair = pair_items(&item?)?;
                arcs.push((pair.0.extract::<u32>()?, pair.1.extract::<u32>()?));
            }
            if tag == "Flow" {
                let mut groups = Vec::new();
                for item in map
                    .get_item("groups")?
                    .ok_or_else(|| PyValueError::new_err("flow groups missing"))?
                    .try_iter()?
                {
                    let item = item?;
                    let group = item
                        .cast::<PyDict>()
                        .map_err(|_| PyValueError::new_err("flow group must be a mapping"))?;
                    let mut commodities = Vec::new();
                    for pair in group
                        .get_item("commodities")?
                        .ok_or_else(|| PyValueError::new_err("flow commodities missing"))?
                        .try_iter()?
                    {
                        let pair = pair_items(&pair?)?;
                        commodities.push((pair.0.extract::<u32>()?, q_from_py(&pair.1)?));
                    }
                    groups.push(FlowGroup {
                        source: group
                            .get_item("source")?
                            .ok_or_else(|| PyValueError::new_err("flow source missing"))?
                            .extract::<u32>()?,
                        commodities,
                        flows: exprs(
                            group
                                .get_item("flows")?
                                .ok_or_else(|| PyValueError::new_err("flow flows missing"))?
                                .as_any(),
                        )?,
                        nonnegative: refs(
                            group
                                .get_item("nonnegative")?
                                .ok_or_else(|| PyValueError::new_err("flow nonnegative missing"))?
                                .as_any(),
                        )?,
                        balances: refs(
                            group
                                .get_item("balances")?
                                .ok_or_else(|| PyValueError::new_err("flow balances missing"))?
                                .as_any(),
                        )?,
                    });
                }
                Ok(kernel_core::authoring::Extension::Flow(FlowWitness {
                    nodes,
                    arcs,
                    groups,
                }))
            } else {
                let mut groups = Vec::new();
                for item in map
                    .get_item("groups")?
                    .ok_or_else(|| PyValueError::new_err("subflow groups missing"))?
                    .try_iter()?
                {
                    let item = item?;
                    let group = item
                        .cast::<PyDict>()
                        .map_err(|_| PyValueError::new_err("subflow group must be a mapping"))?;
                    let mut demands = Vec::new();
                    for pair in group
                        .get_item("demands")?
                        .ok_or_else(|| PyValueError::new_err("subflow demands missing"))?
                        .try_iter()?
                    {
                        let pair = pair_items(&pair?)?;
                        demands.push((pair.0.extract::<u32>()?, q_from_py(&pair.1)?));
                    }
                    groups.push(SubflowGroup {
                        source: group
                            .get_item("source")?
                            .ok_or_else(|| PyValueError::new_err("subflow source missing"))?
                            .extract::<u32>()?,
                        demands,
                        flows: exprs(
                            group
                                .get_item("flows")?
                                .ok_or_else(|| PyValueError::new_err("subflow flows missing"))?
                                .as_any(),
                        )?,
                        nonnegative: refs(
                            group
                                .get_item("nonnegative")?
                                .ok_or_else(|| {
                                    PyValueError::new_err("subflow nonnegative missing")
                                })?
                                .as_any(),
                        )?,
                        balances: refs(
                            group
                                .get_item("balances")?
                                .ok_or_else(|| PyValueError::new_err("subflow balances missing"))?
                                .as_any(),
                        )?,
                    });
                }
                Ok(kernel_core::authoring::Extension::Subflow(SubflowWitness {
                    nodes,
                    arcs,
                    groups,
                }))
            }
        }
        _ => Err(PyValueError::new_err(format!(
            "unknown extension variant {tag:?}"
        ))),
    }
}

#[pyclass(name = "Kernel", module = "kernel_compiler._native")]
struct PyKernel;

#[pymethods]
impl PyKernel {
    #[new]
    fn new() -> Self {
        Self
    }

    fn call(&self, py: Python<'_>, args: Vec<String>) -> PyResult<PyObject> {
        if args.is_empty() {
            return Err(PyValueError::new_err("native command requires a name"));
        }
        let result = match args[0].as_str() {
            "canonical" if args.len() == 3 => {
                kernel_core::api::canonicalize_path(&args[1], &args[2])
            }
            "inspect-model" if args.len() == 2 => kernel_core::api::inspect_model_path(&args[1]),
            "export-model" if args.len() == 3 => {
                kernel_core::api::export_model_paths(&args[1], &args[2])
            }
            "assemble" if args.len() == 3 => kernel_core::api::assemble_paths(&args[1], &args[2]),
            "disassemble" if args.len() == 3 => {
                kernel_core::api::disassemble_paths(&args[1], &args[2])
            }
            command => {
                return Err(PyValueError::new_err(format!(
                    "unsupported native command {command:?}"
                )));
            }
        };
        match result {
            Ok(value) => json_to_py(py, &value),
            Err(error) => json_to_py(py, &error.to_json()),
        }
    }

    #[pyo3(signature = (source, target, proof, work=None, live_facts=None))]
    fn verify(
        &self,
        py: Python<'_>,
        source: &str,
        target: &str,
        proof: &str,
        work: Option<u64>,
        live_facts: Option<usize>,
    ) -> PyResult<PyObject> {
        let mut limits = Limits::default();
        if let Some(value) = work {
            limits.work = value;
        }
        if let Some(value) = live_facts {
            limits.live_facts = value;
        }
        match kernel_core::api::verify_paths(source, target, proof, &limits) {
            Ok(value) => json_to_py(py, &value),
            Err(error) => json_to_py(py, &error.to_json()),
        }
    }
}

fn expr_from_json_py(value: &Bound<'_, PyAny>) -> PyResult<Expr> {
    let dict = value
        .cast::<PyDict>()
        .map_err(|_| PyValueError::new_err("expected an expression object"))?;
    let constant = match dict.get_item("constant")? {
        Some(item) => q_from_py(&item)?,
        None => Q::zero(),
    };
    let mut terms = Vec::new();
    if let Some(items) = dict.get_item("terms")? {
        if !items.is_none() {
            for item in items.try_iter()? {
                let item = item?;
                if let Ok(pair) = item.cast::<PyList>() {
                    if pair.len() != 2 {
                        return Err(PyValueError::new_err("terms must be pairs"));
                    }
                    terms.push((
                        pair.get_item(0)?.extract::<u32>()?,
                        q_from_py(&pair.get_item(1)?)?,
                    ));
                } else {
                    let pair = item
                        .cast::<PyTuple>()
                        .map_err(|_| PyValueError::new_err("terms must be pairs"))?;
                    if pair.len() != 2 {
                        return Err(PyValueError::new_err("terms must be pairs"));
                    }
                    terms.push((
                        pair.get_item(0)?.extract::<u32>()?,
                        q_from_py(&pair.get_item(1)?)?,
                    ));
                }
            }
        }
    }
    kernel_compiler_core::expr::canonical(constant, terms).map_err(PyValueError::new_err)
}

fn ref_from_py(value: &Bound<'_, PyAny>) -> PyResult<Ref> {
    if let Ok(text) = value.extract::<String>() {
        if text == "Exact" {
            return Ok(Ref::Exact);
        }
        return Err(PyValueError::new_err(
            "expected a reference object or Exact",
        ));
    }
    let dict = value
        .cast::<PyDict>()
        .map_err(|_| PyValueError::new_err("expected a reference object"))?;
    if dict.len() != 1 {
        return Err(PyValueError::new_err("a reference must have one tag"));
    }
    for (key, item) in dict.iter() {
        let tag = key.extract::<String>()?;
        let index = item.extract::<u32>()?;
        return Ok(match tag.as_str() {
            "VarLower" => Ref::VarLower(index),
            "VarUpper" => Ref::VarUpper(index),
            "VarInt" => Ref::VarInt(index),
            "RowLower" => Ref::RowLower(index),
            "RowUpper" => Ref::RowUpper(index),
            "RowEq" => Ref::RowEq(index),
            "Local" => Ref::Local(index),
            "Assumption" => Ref::Assumption(index),
            _ => return Err(PyValueError::new_err("unknown reference tag")),
        });
    }
    Err(PyValueError::new_err("empty reference object"))
}

fn path_index(segment: &str) -> PyResult<usize> {
    segment
        .parse::<usize>()
        .map_err(|_| PyValueError::new_err(format!("invalid mutation index {segment:?}")))
}

fn remove_at<T>(items: &mut Vec<T>, index: usize) -> PyResult<()> {
    if index >= items.len() {
        return Err(PyValueError::new_err("mutation index outside container"));
    }
    items.remove(index);
    Ok(())
}

fn mutate_block(
    block: &mut Block,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
    delete: bool,
) -> PyResult<()> {
    let (head, rest) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("mutation path ends at a block"))?;
    match head.as_str() {
        "steps" => {
            let (index, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("steps requires an index"))?;
            let index = path_index(index)?;
            if tail.is_empty() {
                if delete {
                    return remove_at(&mut block.steps, index);
                }
                return Err(PyValueError::new_err(
                    "step replacement requires a field path",
                ));
            }
            let step = block
                .steps
                .get_mut(index)
                .ok_or_else(|| PyValueError::new_err("step index outside block"))?;
            mutate_step(step, tail, replacement, delete)
        }
        "end" => mutate_end(&mut block.end, rest, replacement, delete),
        _ => Err(PyValueError::new_err(format!(
            "unsupported block mutation {head:?}"
        ))),
    }
}

fn mutate_step(
    step: &mut Step,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
    delete: bool,
) -> PyResult<()> {
    let (tag, rest) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("step mutation requires a tag"))?;
    match (step, tag.as_str()) {
        (
            Step::Lin {
                constant,
                terms,
                kind,
                ..
            },
            "Lin",
        ) => {
            let (field, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("Lin requires a field"))?;
            match field.as_str() {
                "constant" if tail.is_empty() => {
                    *constant = q_from_py(replacement)?;
                    Ok(())
                }
                "kind" if tail.is_empty() => {
                    *kind = parse_kind(&replacement.extract::<String>()?)
                        .map_err(PyValueError::new_err)?;
                    Ok(())
                }
                "terms" => {
                    let (index, which) = tail
                        .split_first()
                        .ok_or_else(|| PyValueError::new_err("terms requires an index"))?;
                    let index = path_index(index)?;
                    let which = which
                        .first()
                        .ok_or_else(|| PyValueError::new_err("terms requires a component"))?;
                    if which == "0" && tail.len() == 2 {
                        if delete {
                            return remove_at(terms, index);
                        }
                        terms[index].0 = ref_from_py(replacement)?;
                        Ok(())
                    } else if which == "1" && tail.len() == 2 {
                        if delete {
                            return remove_at(terms, index);
                        }
                        terms[index].1 = q_from_py(replacement)?;
                        Ok(())
                    } else {
                        Err(PyValueError::new_err("unsupported Lin terms mutation"))
                    }
                }
                _ => Err(PyValueError::new_err("unsupported Lin mutation")),
            }
        }
        (Step::Round { le, integer, .. }, "Round") => {
            let field = rest
                .first()
                .ok_or_else(|| PyValueError::new_err("Round requires a field"))?;
            match field.as_str() {
                "le" => {
                    *le = ref_from_py(replacement)?;
                    Ok(())
                }
                "integer" => {
                    *integer = ref_from_py(replacement)?;
                    Ok(())
                }
                _ => Err(PyValueError::new_err("unsupported Round mutation")),
            }
        }
        (
            Step::EqPair {
                positive, negative, ..
            },
            "EqPair",
        ) => {
            let field = rest
                .first()
                .ok_or_else(|| PyValueError::new_err("EqPair requires a field"))?;
            match field.as_str() {
                "positive" => {
                    *positive = ref_from_py(replacement)?;
                    Ok(())
                }
                "negative" => {
                    *negative = ref_from_py(replacement)?;
                    Ok(())
                }
                _ => Err(PyValueError::new_err("unsupported EqPair mutation")),
            }
        }
        (Step::Drop { ids }, "Drop") => {
            let (field, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("Drop requires a field"))?;
            if field != "ids" {
                return Err(PyValueError::new_err("unsupported Drop mutation"));
            }
            let index = path_index(
                tail.first()
                    .ok_or_else(|| PyValueError::new_err("Drop ids requires an index"))?,
            )?;
            if delete {
                remove_at(ids, index)
            } else {
                ids[index] = replacement.extract::<u32>()?;
                Ok(())
            }
        }
        (Step::Cases(case), "Cases") => {
            let (field, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("Cases requires a field"))?;
            match field.as_str() {
                "expression" if tail.is_empty() => {
                    case.expression = expr_from_json_py(replacement)?;
                    Ok(())
                }
                "split" if tail.is_empty() => {
                    case.split = expr_from_json_py(replacement)?;
                    Ok(())
                }
                "kind" if tail.is_empty() => {
                    case.kind = parse_kind(&replacement.extract::<String>()?)
                        .map_err(PyValueError::new_err)?;
                    Ok(())
                }
                "integer" if tail.is_empty() => {
                    case.integer = Some(ref_from_py(replacement)?);
                    Ok(())
                }
                "left" => mutate_derivation(&mut case.left, tail, replacement, delete),
                "right" => mutate_derivation(&mut case.right, tail, replacement, delete),
                _ => Err(PyValueError::new_err("unsupported Cases mutation")),
            }
        }
        _ => Err(PyValueError::new_err(format!(
            "unsupported step mutation {tag:?}"
        ))),
    }
}

fn mutate_derivation(
    derivation: &mut Derivation,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
    delete: bool,
) -> PyResult<()> {
    let (head, rest) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("derivation mutation requires a field"))?;
    match head.as_str() {
        "steps" => {
            let index = path_index(
                rest.first()
                    .ok_or_else(|| PyValueError::new_err("steps requires an index"))?,
            )?;
            if rest.len() == 1 {
                if delete {
                    remove_at(&mut derivation.steps, index)
                } else {
                    Err(PyValueError::new_err(
                        "step replacement requires a field path",
                    ))
                }
            } else {
                let step = derivation
                    .steps
                    .get_mut(index)
                    .ok_or_else(|| PyValueError::new_err("step index outside derivation"))?;
                mutate_step(step, &rest[1..], replacement, delete)
            }
        }
        "end" => {
            let (tag, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("derivation end requires a tag"))?;
            match (tag.as_str(), tail.is_empty()) {
                ("Witness", true) => match &mut derivation.end {
                    CoreDerivationEnd::Witness(reference) => {
                        *reference = ref_from_py(replacement)?;
                        Ok(())
                    }
                    CoreDerivationEnd::Absurd(reference) => {
                        *reference = ref_from_py(replacement)?;
                        derivation.end = CoreDerivationEnd::Witness(reference.clone());
                        Ok(())
                    }
                },
                ("Absurd", true) => match &mut derivation.end {
                    CoreDerivationEnd::Absurd(reference) => {
                        *reference = ref_from_py(replacement)?;
                        Ok(())
                    }
                    CoreDerivationEnd::Witness(reference) => {
                        *reference = ref_from_py(replacement)?;
                        derivation.end = CoreDerivationEnd::Absurd(reference.clone());
                        Ok(())
                    }
                },
                _ => Err(PyValueError::new_err("unsupported derivation end mutation")),
            }
        }
        _ => Err(PyValueError::new_err("unsupported derivation mutation")),
    }
}

fn mutate_end(
    end: &mut End,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
    delete: bool,
) -> PyResult<()> {
    let (tag, rest) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("end mutation requires a tag"))?;
    match (end, tag.as_str()) {
        (End::Return { map, checks }, "Return") => {
            let (field, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("Return requires a field"))?;
            let index = path_index(
                tail.first()
                    .ok_or_else(|| PyValueError::new_err("Return field requires an index"))?,
            )?;
            match field.as_str() {
                "map" => {
                    if delete {
                        remove_at(map, index)
                    } else if tail.len() == 1 {
                        map[index] = expr_from_json_py(replacement)?;
                        Ok(())
                    } else {
                        return mutate_expr(&mut map[index], &tail[1..], replacement);
                    }
                }
                "checks" => {
                    if delete {
                        remove_at(checks, index)
                    } else if tail.len() == 1 {
                        checks[index] = ref_from_py(replacement)?;
                        Ok(())
                    } else {
                        Err(PyValueError::new_err("unsupported check mutation"))
                    }
                }
                _ => Err(PyValueError::new_err("unsupported Return mutation")),
            }
        }
        (
            End::Split {
                expression,
                integer,
                left,
                right,
            },
            "Split",
        ) => {
            let (field, tail) = rest
                .split_first()
                .ok_or_else(|| PyValueError::new_err("Split requires a field"))?;
            match field.as_str() {
                "expression" if tail.is_empty() => {
                    *expression = expr_from_json_py(replacement)?;
                    Ok(())
                }
                "integer" if tail.is_empty() => {
                    *integer = Some(ref_from_py(replacement)?);
                    Ok(())
                }
                "left" => mutate_block(left, tail, replacement, delete),
                "right" => mutate_block(right, tail, replacement, delete),
                _ => Err(PyValueError::new_err("unsupported Split mutation")),
            }
        }
        (End::Absurd { fact }, "Absurd") => {
            if rest.first().map(String::as_str) != Some("fact") {
                return Err(PyValueError::new_err("Absurd requires fact"));
            }
            *fact = ref_from_py(replacement)?;
            Ok(())
        }
        _ => Err(PyValueError::new_err(format!(
            "unsupported end mutation {tag:?}"
        ))),
    }
}

fn mutate_expr(
    expression: &mut Expr,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
) -> PyResult<()> {
    let (field, tail) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("expression mutation requires a field"))?;
    match field.as_str() {
        "constant" if tail.is_empty() => {
            expression.constant = q_from_py(replacement)?;
            Ok(())
        }
        "terms" => {
            let index = path_index(
                tail.first()
                    .ok_or_else(|| PyValueError::new_err("terms requires an index"))?,
            )?;
            let which = tail
                .get(1)
                .ok_or_else(|| PyValueError::new_err("terms requires a component"))?;
            if which == "0" {
                expression.terms[index].0 = replacement.extract::<u32>()?;
            } else if which == "1" {
                expression.terms[index].1 = q_from_py(replacement)?;
            } else {
                return Err(PyValueError::new_err(
                    "unsupported expression term mutation",
                ));
            }
            Ok(())
        }
        _ => Err(PyValueError::new_err("unsupported expression mutation")),
    }
}

fn mutate_certificate(
    certificate: &mut Certificate,
    path: &[String],
    replacement: &Bound<'_, PyAny>,
    delete: bool,
) -> PyResult<()> {
    let (direction, rest) = path
        .split_first()
        .ok_or_else(|| PyValueError::new_err("mutation path is empty"))?;
    let block = match direction.as_str() {
        "forward" => &mut certificate.forward,
        "reverse" => &mut certificate.reverse,
        _ => {
            return Err(PyValueError::new_err(
                "mutation direction must be forward or reverse",
            ));
        }
    };
    mutate_block(block, rest, replacement, delete)
}

#[pymethods]
impl PyProof {
    fn attack(
        &self,
        py: Python<'_>,
        path: Vec<String>,
        replacement: &Bound<'_, PyAny>,
        delete: bool,
    ) -> PyResult<PyCompiled> {
        let mut certificate = {
            let mut core = lock_core(&self.core)?;
            core.refresh_completions(&Limits::default())
                .map_err(PyValueError::new_err)?;
            core.certificate().map_err(PyValueError::new_err)?
        };
        mutate_certificate(&mut certificate, &path, replacement, delete)?;
        let rpa = kernel_core::rpa::disassemble(&certificate).map_err(PyValueError::new_err)?;
        let certificate = kernel_core::rpa::assemble(&rpa).map_err(PyValueError::new_err)?;
        let rpx =
            kernel_core::codec::encode_certificate(&certificate).map_err(PyValueError::new_err)?;
        Ok(PyCompiled {
            rpa,
            rpx: pyo3::types::PyBytes::new(py, &rpx).unbind(),
        })
    }
}

#[pymethods]
impl PyBuilder {
    #[getter]
    fn scope_id(&self) -> usize {
        self.scope
    }

    #[getter]
    fn revision(&self) -> PyResult<u64> {
        Ok(lock_core(&self.core)?
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .revision)
    }

    fn owns(&self, fact: &Bound<'_, PyAny>) -> PyResult<bool> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?;
        Ok(Arc::ptr_eq(&self.core, &fact.core))
    }

    fn descends_from(&self, ancestor: &Bound<'_, PyAny>) -> PyResult<bool> {
        let ancestor = ancestor.extract::<PyRef<'_, PyBuilder>>()?;
        if !Arc::ptr_eq(&self.core, &ancestor.core) {
            return Ok(false);
        }
        let core = lock_core(&self.core)?;
        let mut current = Some(self.scope);
        while let Some(id) = current {
            if id == ancestor.scope {
                return Ok(true);
            }
            current = core.scope(id).map_err(PyValueError::new_err)?.parent;
        }
        Ok(false)
    }

    fn clear_assignments(&self) -> PyResult<()> {
        lock_core(&self.core)?
            .scope_mut(self.scope)
            .map_err(PyValueError::new_err)?
            .assigned
            .clear();
        Ok(())
    }
}

#[pymethods]
impl PyBuilder {
    fn same_model(&self, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let other = other.extract::<PyRef<'_, PyBuilder>>()?;
        if !Arc::ptr_eq(&self.core, &other.core) {
            return Ok(false);
        }
        let core = lock_core(&self.core)?;
        Ok(core
            .scope(self.scope)
            .map_err(PyValueError::new_err)?
            .model
            .inner
            == core
                .scope(other.scope)
                .map_err(PyValueError::new_err)?
                .model
                .inner)
    }
}

#[pymethods]
impl PyBuilder {
    fn visible_fact(&self, fact: &Bound<'_, PyAny>) -> PyResult<()> {
        let fact = fact.extract::<PyRef<'_, PyFact>>()?;
        if !Arc::ptr_eq(&self.core, &fact.core) {
            return Err(PyValueError::new_err(
                "Fact belongs to a sibling or unrelated proof scope",
            ));
        }
        lock_core(&self.core)?
            .visible(self.scope, fact.id)
            .map_err(PyValueError::new_err)
    }
}

#[pymethods]
impl PyBuilder {
    fn map_identity(&self) -> PyResult<()> {
        let mut core = lock_core(&self.core)?;
        let item = core.scope(self.scope).map_err(PyValueError::new_err)?;
        let count = item.output_model.inner.vars.len();
        let mapping = (0..count as u32).map(Expr::var).collect();
        core.scope_mut(self.scope)
            .map_err(PyValueError::new_err)?
            .mapping = Some(mapping);
        Ok(())
    }

    #[getter]
    fn mapping(&self, py: Python<'_>) -> PyResult<PyObject> {
        let core = lock_core(&self.core)?;
        match core.mapping(self.scope).as_ref() {
            None => Ok(py.None()),
            Some(values) => {
                let list = PyList::empty(py);
                for value in values {
                    list.append(Py::new(
                        py,
                        PyExpr {
                            inner: value.clone(),
                        },
                    )?)?;
                }
                Ok(list.into_any().unbind())
            }
        }
    }
}
