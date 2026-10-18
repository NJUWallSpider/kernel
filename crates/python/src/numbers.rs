use crate::errors::err;
use kernel_core::model::{Q, check_q, parse_q};
use num_bigint::BigInt;
use num_traits::{One, Signed, ToPrimitive, Zero};
use pyo3::{
    exceptions::{PyTypeError, PyZeroDivisionError},
    prelude::*,
    types::{PyBool, PyFloat, PyInt, PyString},
};
/// An immutable exact rational number. Accept int, exact str, Fraction, finite Decimal, or Q; reject bool, float, NaN and infinity. A zero denominator raises ZeroDivisionError. Arithmetic returns Q; int(q) truncates toward zero; bool(q) tests nonzero. Example: Q("1/3") + Q(1, 6).
///
/// ## Operators
/// Comparison accepts exact numeric operands, but not strings.
/// __add__: Add an exact scalar or compatible rational; return Q.
/// __radd__: Reversed addition; return Q.
/// __sub__: Subtract a compatible operand; return Q.
/// __rsub__: Subtract self from the left operand; return Q.
/// __mul__: Scale by an exact scalar; return Q. Nonlinear products are not accepted.
/// __rmul__: Reversed exact scalar multiplication; return Q.
/// __truediv__: Divide by a nonzero exact scalar; return Q. ZeroDivisionError on zero.
/// __neg__: Negate without deriving a fact; return Q.
/// __rtruediv__: Divide an exact scalar by this nonzero Q; return Q.
/// __abs__: Return the nonnegative exact magnitude as Q.
/// __int__: Truncate toward zero and return int.
/// __bool__: Return False exactly when zero.
/// __lt__: Compare exact numeric values: less than; return bool.
/// __le__: Compare exact numeric values: less than or equal to; return bool.
/// __gt__: Compare exact numeric values: greater than; return bool.
/// __ge__: Compare exact numeric values: greater than or equal to; return bool.
/// __eq__: Compare exact numeric values: equal to; return bool.
/// __ne__: Compare exact numeric values: unequal to; return bool.
/// __hash__: Return a hash consistent with equality.
#[pyclass(name = "Q", module = "rpx", frozen, from_py_object)]
#[derive(Clone)]
pub struct PyQ {
    pub value: Q,
}
pub fn scalar(v: &Bound<'_, PyAny>) -> PyResult<Q> {
    if v.is_instance_of::<PyBool>() || v.is_instance_of::<PyFloat>() {
        return Err(PyTypeError::new_err(
            "proof scalars must be exact; float and bool are forbidden",
        ));
    }
    let q = if let Ok(q) = v.extract::<PyRef<'_, PyQ>>() {
        q.value.clone()
    } else if v.is_instance_of::<PyInt>() {
        Q::from_integer(v.extract::<BigInt>()?)
    } else if v.is_instance_of::<PyString>() {
        parse_q(&v.extract::<String>()?).map_err(err)?
    } else {
        let py = v.py();
        if v.is_instance(&py.import("fractions")?.getattr("Fraction")?)? {
            Q::new(
                v.getattr("numerator")?.extract::<BigInt>()?,
                v.getattr("denominator")?.extract::<BigInt>()?,
            )
        } else if v.is_instance(&py.import("decimal")?.getattr("Decimal")?)? {
            if !v.call_method0("is_finite")?.extract::<bool>()? {
                return Err(PyTypeError::new_err("Decimal must be finite"));
            }
            parse_q(&v.str()?.to_string()).map_err(err)?
        } else {
            return Err(PyTypeError::new_err(
                "expected Q, int, Fraction, Decimal, or exact string",
            ));
        }
    };
    check_q(&q).map_err(err)?;
    Ok(q)
}
pub fn optional(v: Option<&Bound<'_, PyAny>>) -> PyResult<Option<Q>> {
    v.filter(|v| !v.is_none()).map(scalar).transpose()
}
#[pymethods]
impl PyQ {
    #[new]
    #[pyo3(signature=(numerator=None,denominator=None))]
    fn new(
        numerator: Option<&Bound<'_, PyAny>>,
        denominator: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let n = numerator.map(scalar).transpose()?.unwrap_or_else(Q::zero);
        let d = denominator.map(scalar).transpose()?.unwrap_or_else(Q::one);
        if d.is_zero() {
            return Err(PyZeroDivisionError::new_err("zero denominator"));
        }
        let value = n / d;
        check_q(&value).map_err(err)?;
        Ok(Self { value })
    }
    #[getter]
    /// The reduced signed integer numerator.
    ///
    /// ## Example
    /// q.numerator
    fn numerator(&self) -> BigInt {
        self.value.numer().clone()
    }
    #[getter]
    /// The reduced positive integer denominator.
    ///
    /// ## Example
    /// q.denominator
    fn denominator(&self) -> BigInt {
        self.value.denom().clone()
    }
    fn __str__(&self) -> String {
        self.value.to_string()
    }
    fn __repr__(&self) -> String {
        format!("Q('{}')", self.value)
    }
    /// Negate the operand; return Q.
    fn __neg__(&self) -> Self {
        Self {
            value: -self.value.clone(),
        }
    }
    /// Truncate toward zero and return an integer.
    fn __int__(&self) -> BigInt {
        self.value.to_integer()
    }
    /// Take the absolute value of the operand; return Q.
    fn __abs__(&self) -> Self {
        Self {
            value: self.value.abs(),
        }
    }
    /// Return whether this rational is nonzero.
    fn __bool__(&self) -> bool {
        !self.value.is_zero()
    }
    /// Return a hash consistent with numeric equality.
    fn __hash__(&self) -> isize {
        rational_hash(&self.value)
    }
    /// Compare exact numeric values and return bool; strings are not comparable.
    fn __richcmp__(
        &self,
        other: &Bound<'_, PyAny>,
        op: pyo3::basic::CompareOp,
    ) -> PyResult<Py<PyAny>> {
        let py = other.py();
        if other.is_instance_of::<PyString>() {
            return Ok(py.NotImplemented());
        }
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let v = match op {
            pyo3::basic::CompareOp::Eq => self.value == q,
            pyo3::basic::CompareOp::Ne => self.value != q,
            pyo3::basic::CompareOp::Lt => self.value < q,
            pyo3::basic::CompareOp::Le => self.value <= q,
            pyo3::basic::CompareOp::Gt => self.value > q,
            pyo3::basic::CompareOp::Ge => self.value >= q,
        };
        Ok(v.into_pyobject(py)?.to_owned().into_any().unbind())
    }
    /// Add the operand; return Q.
    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = &self.value + q;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Subtract the operand; return Q.
    fn __sub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = &self.value - q;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Multiply by an exact scalar the operand; return Q.
    fn __mul__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = &self.value * q;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Divide by a nonzero exact scalar the operand; return Q. Zero denominators raise ZeroDivisionError.
    fn __truediv__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        if q.is_zero() {
            return Err(PyZeroDivisionError::new_err("division by zero"));
        }
        let value = &self.value / q;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Add in reversed operand order the operand; return Q.
    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = q + &self.value;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Subtract in reversed operand order the operand; return Q.
    fn __rsub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = q - &self.value;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Multiply by an exact scalar in reversed order the operand; return Q.
    fn __rmul__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        let value = q * &self.value;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
    /// Divide an exact scalar by this nonzero value the operand; return Q. Zero denominators raise ZeroDivisionError.
    fn __rtruediv__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(q) = scalar(other) else {
            return Ok(py.NotImplemented());
        };
        if self.value.is_zero() {
            return Err(PyZeroDivisionError::new_err("division by zero"));
        }
        let value = q / &self.value;
        check_q(&value).map_err(err)?;
        Ok(Py::new(py, Self { value })?.into_any())
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyQ>()
}

/// Copy a one-dimensional integer buffer once; never box individual elements.
pub fn integer_buffer(v: &Bound<'_, PyAny>) -> PyResult<Option<Vec<BigInt>>> {
    let view = match v
        .py()
        .import("builtins")?
        .getattr("memoryview")?
        .call1((v,))
    {
        Ok(view) => view,
        Err(_) => return Ok(None),
    };
    if view.getattr("ndim")?.extract::<usize>()? != 1 {
        return Err(PyTypeError::new_err(
            "expected a one-dimensional integer buffer",
        ));
    }
    let format = view.getattr("format")?.extract::<String>()?;
    let code = format.trim_start_matches(['@', '=', '<', '>', '!']);
    let signed = match code {
        "b" | "h" | "i" | "l" | "q" | "n" => true,
        "B" | "H" | "I" | "L" | "Q" | "N" => false,
        _ => {
            return Err(PyTypeError::new_err(
                "only integer buffers are exact proof inputs",
            ));
        }
    };
    let width = view.getattr("itemsize")?.extract::<usize>()?;
    if ![1, 2, 4, 8].contains(&width) {
        return Err(PyTypeError::new_err("unsupported integer buffer width"));
    }
    let bytes = view.call_method0("tobytes")?;
    let bytes = bytes.cast::<pyo3::types::PyBytes>()?.as_bytes();
    let big_endian = if format.starts_with('>') || format.starts_with('!') {
        true
    } else if format.starts_with('<') {
        false
    } else {
        cfg!(target_endian = "big")
    };
    Ok(Some(
        bytes
            .chunks_exact(width)
            .map(|b| {
                if signed {
                    if big_endian {
                        BigInt::from_signed_bytes_be(b)
                    } else {
                        BigInt::from_signed_bytes_le(b)
                    }
                } else if big_endian {
                    BigInt::from_bytes_be(num_bigint::Sign::Plus, b)
                } else {
                    BigInt::from_bytes_le(num_bigint::Sign::Plus, b)
                }
            })
            .collect(),
    ))
}

/// Python's numeric hash contract, computed without a temporary Fraction object.
pub fn rational_hash(q: &Q) -> isize {
    let bits = if std::mem::size_of::<isize>() == 8 {
        61
    } else {
        31
    };
    let modulus = BigInt::from((1u64 << bits) - 1);
    let denominator = q.denom() % &modulus;
    let mut hash = if denominator.is_zero() {
        314159
    } else {
        let inverse = denominator.modpow(&(&modulus - 2), &modulus);
        ((q.numer().abs() % &modulus) * inverse % &modulus)
            .to_isize()
            .unwrap()
    };
    if q.is_negative() {
        hash = -hash;
    }
    if hash == -1 { -2 } else { hash }
}
