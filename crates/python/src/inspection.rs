//! Explicit low-level inspection; never used to compile a proof.
use crate::{
    errors::err,
    proofs::{Core, PyScope, lock},
};
use kernel_compiler_core::proof::kind_name;
use kernel_core::{
    model::{Expr, Q},
    proof::{Block, Certificate, Derivation, DerivationEnd as CoreDerivationEnd, End, Ref, Step},
    verify::Limits,
};
use pyo3::{
    exceptions::PyIndexError,
    prelude::*,
    types::{PyDict, PyList},
};
type PyObject = Py<PyAny>;
fn q_text(q: &Q) -> String {
    q.to_string()
}
fn py_expr_from(e: &Expr, py: Python<'_>) -> PyResult<PyObject> {
    json_py(
        py,
        &serde_json::json!({"constant":e.constant.to_string(),"terms":e.terms.iter().map(|(i,q)|serde_json::json!([i,q.to_string()])).collect::<Vec<_>>()}),
    )
}
pub fn html(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
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
pub fn json_py(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
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
                list.append(json_py(py, item)?)?;
            }
            Ok(list.into_any().unbind())
        }
        serde_json::Value::Object(values) => {
            let dict = PyDict::new(py);
            for (key, item) in values {
                dict.set_item(key, json_py(py, item)?)?;
            }
            Ok(dict.into_any().unbind())
        }
    }
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
/// A native-backed proof trace. Indexing yields StepView; to_list explicitly materializes all instructions. Reading the trace does not certify the proof. Example: scope.trace[0].kind.
///
/// ## Operators
/// __getitem__: Return StepView at a nonnegative index; out-of-range raises IndexError.
/// __len__: Return current instruction count.
#[pyclass(name = "TraceView", module = "rpx.lowlevel", frozen)]
pub struct TraceView {
    pub scope: PyScope,
}
#[pymethods]
impl TraceView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> PyResult<usize> {
        Ok(lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .steps
            .len())
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
    fn __getitem__(&self, index: usize) -> PyResult<StepView> {
        if index >= self.__len__()? {
            return Err(PyIndexError::new_err("step index"));
        }
        Ok(StepView {
            source: StepSource::Trace(self.scope.clone()),
            index,
        })
    }
    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("TraceView({} steps)", self.__len__()?))
    }
    /// Explicitly materialize every entry in this view as a Python list. Prefer bounded iteration for large data.
    ///
    /// ## Returns
    /// list[dict[str, Any]]
    ///
    /// ## Example
    /// scope.trace.to_list()
    fn to_list(&self, py: Python<'_>) -> PyResult<PyObject> {
        let c = lock(&self.scope.core)?;
        let values = PyList::empty(py);
        for s in &c.scope(self.scope.id).map_err(err)?.steps {
            values.append(step_to_py(py, s)?)?;
        }
        Ok(values.into_any().unbind())
    }
}
/// A native certificate view of a completed proof. Access forward/reverse blocks by key; to_dict explicitly materializes debug data. This is not a verification report. Example: proof.certificate()["forward"].
///
/// ## Operators
/// __getitem__: Return CertificateBlockView for key forward or reverse; other keys raise KeyError.
/// __len__: Return 2, the forward/reverse block count.
#[pyclass(name = "CertificateView", module = "rpx.lowlevel", frozen)]
pub struct CertificateView {
    pub core: Core,
}
#[pymethods]
impl CertificateView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> usize {
        2
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
    fn __getitem__(&self, key: &str) -> PyResult<CertificateBlockView> {
        let reverse = match key {
            "forward" => false,
            "reverse" => true,
            _ => return Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        };
        Ok(CertificateBlockView {
            compiled: lock(&self.core)?.compile().map_err(err)?,
            reverse,
        })
    }

    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// certificate.to_dict()
    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        let c = lock(&self.core)?.compile().map_err(err)?;
        certificate_to_py(py, &c.certificate)
    }
    fn __repr__(&self) -> &'static str {
        "CertificateView(forward, reverse; call to_dict() to materialize)"
    }
}
#[pyfunction]
#[pyo3(signature=(source,target,proof,*,work=None,live_facts=None,depth=None))]
/// Verify source/target model files and proof certificate with the frozen Kernel and optional work/live_facts/depth budgets. Return a result dictionary. Inspect status before claiming certification; this low-level function does not perform Bundle artifact audits.
fn verify(
    py: Python<'_>,
    source: String,
    target: String,
    proof: String,
    work: Option<u64>,
    live_facts: Option<usize>,
    depth: Option<usize>,
) -> PyResult<PyObject> {
    let mut limits = Limits::default();
    if let Some(v) = work {
        limits.work = v;
    }
    if let Some(v) = live_facts {
        limits.live_facts = v;
    }
    if let Some(v) = depth {
        limits.depth = v;
    }
    let result = py.detach(|| kernel_core::api::verify_paths(&source, &target, &proof, &limits));
    json_py(
        py,
        &match result {
            Ok(v) => v,
            Err(e) => e.to_json(),
        },
    )
}
#[pyfunction]
/// Assemble RPA source file into RPX target file using the frozen codec. Returns None; malformed input raises CompilerError. This does not verify a certificate.
fn assemble(py: Python<'_>, source: String, target: String) -> PyResult<()> {
    py.detach(|| kernel_core::api::assemble_paths(&source, &target))
        .map(|_| ())
        .map_err(|e| err(e.message().to_string()))
}
#[pyfunction]
/// Disassemble RPX source file into RPA target file using the frozen codec. Returns None; malformed input raises CompilerError. This does not verify a certificate.
fn disassemble(py: Python<'_>, source: String, target: String) -> PyResult<()> {
    py.detach(|| kernel_core::api::disassemble_paths(&source, &target))
        .map(|_| ())
        .map_err(|e| err(e.message().to_string()))
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TraceView>()?;
    m.add_class::<StepView>()?;
    m.add_class::<CertificateBlockView>()?;
    m.add_class::<CertificateView>()?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    m.add_function(wrap_pyfunction!(assemble, m)?)?;
    m.add_function(wrap_pyfunction!(disassemble, m)?)?;
    Ok(())
}

/// A native certificate block view. Index instructions to obtain StepView; to_dict includes instructions and the block end. Example: proof.certificate()["forward"].to_dict().
///
/// ## Operators
/// __getitem__: Return StepView at a nonnegative index; out-of-range raises IndexError.
/// __len__: Return instruction count in this block.
#[pyclass(name = "CertificateBlockView", module = "rpx.lowlevel", frozen)]
pub struct CertificateBlockView {
    compiled: std::sync::Arc<kernel_compiler_core::compile::CompiledProof>,
    reverse: bool,
}
impl CertificateBlockView {
    fn block(&self) -> &Block {
        if self.reverse {
            &self.compiled.certificate.reverse
        } else {
            &self.compiled.certificate.forward
        }
    }
}
#[pymethods]
impl CertificateBlockView {
    /// Return the native entry count without materializing entries.
    fn __len__(&self) -> usize {
        self.block().steps.len()
    }
    /// Return the entry selected by key/index. Unknown names raise KeyError; out-of-range positions raise IndexError.
    fn __getitem__(&self, index: usize) -> PyResult<StepView> {
        if index >= self.block().steps.len() {
            return Err(PyIndexError::new_err("step index"));
        }
        Ok(StepView {
            source: StepSource::Certificate(self.compiled.clone(), self.reverse),
            index,
        })
    }
    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// block.to_dict()
    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        block_to_py(py, self.block())
    }
    fn __repr__(&self) -> String {
        format!("CertificateBlockView({} steps)", self.block().steps.len())
    }
}

/// Indexing a trace must not recursively materialize a Cases subtree or a large Lin.
enum StepSource {
    Trace(PyScope),
    Certificate(
        std::sync::Arc<kernel_compiler_core::compile::CompiledProof>,
        bool,
    ),
}
/// A native view of one instruction. kind identifies the instruction; to_dict explicitly materializes its certificate-debug fields. Example: scope.trace[0].to_dict().
#[pyclass(name = "StepView", module = "rpx.lowlevel", frozen)]
pub struct StepView {
    source: StepSource,
    index: usize,
}
impl StepView {
    fn with_step<T>(&self, run: impl FnOnce(&Step) -> PyResult<T>) -> PyResult<T> {
        match &self.source {
            StepSource::Trace(scope) => {
                let core = lock(&scope.core)?;
                let step = core
                    .scope(scope.id)
                    .map_err(err)?
                    .steps
                    .get(self.index)
                    .ok_or_else(|| PyIndexError::new_err("step index"))?;
                run(step)
            }
            StepSource::Certificate(compiled, reverse) => {
                let block = if *reverse {
                    &compiled.certificate.reverse
                } else {
                    &compiled.certificate.forward
                };
                run(&block.steps[self.index])
            }
        }
    }
}
#[pymethods]
impl StepView {
    #[getter]
    /// The assertion or instruction kind.
    ///
    /// ## Example
    /// step.kind
    fn kind(&self) -> PyResult<&'static str> {
        self.with_step(|step| {
            Ok(match step {
                Step::Lin { .. } => "Lin",
                Step::Round { .. } => "Round",
                Step::Drop { .. } => "Drop",
                Step::EqPair { .. } => "EqPair",
                Step::Cases(..) => "Cases",
                Step::Plotkin { .. } => "Plotkin",
            })
        })
    }
    /// Explicitly materialize this object as a Python dictionary. This may allocate model/proof-sized data.
    ///
    /// ## Returns
    /// dict[str, Any]
    ///
    /// ## Example
    /// step.to_dict()
    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        self.with_step(|step| step_to_py(py, step))
    }
    fn __repr__(&self) -> PyResult<String> {
        Ok(format!(
            "StepView({}; call to_dict() to materialize)",
            self.kind()?
        ))
    }
}
