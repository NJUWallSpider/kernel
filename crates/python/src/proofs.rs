use crate::{
    errors::{InvalidDerivationError, ScopeError, err},
    expressions::{PyExpr, bound, expression, in_space},
    inspection::json_py,
    models::{PyModel, VariablesView, index},
    numbers::scalar,
};
use kernel_compiler_core::{
    model::Identifier,
    proof::{FactId, ProofCore, ScopeId, ScopeState, kind_name, parse_kind},
    space::pretty,
};
use kernel_core::{
    model::{Expr, Q},
    proof::Kind,
};
use num_traits::{One, Signed, Zero};
use pyo3::{
    exceptions::{PyIndexError, PyKeyError, PyOSError, PyTypeError},
    prelude::*,
    types::PyDict,
};
use std::{
    collections::BTreeMap,
    path::PathBuf,
    sync::{Arc, Mutex, MutexGuard},
};
pub type Core = Arc<Mutex<ProofCore>>;
pub fn lock(core: &Core) -> PyResult<MutexGuard<'_, ProofCore>> {
    core.lock()
        .map_err(|_| ScopeError::new_err("native proof lock poisoned"))
}
#[pyclass(name = "Fact", module = "rpx", frozen, from_py_object)]
#[derive(Clone)]
pub struct PyFact {
    pub core: Core,
    pub id: FactId,
}
#[pyclass(name = "LinCombination", module = "rpx", frozen, from_py_object)]
#[derive(Clone)]
pub struct Combination {
    pub core: Option<Core>,
    pub terms: BTreeMap<FactId, Q>,
    pub constant: Q,
}
pub fn combination(v: &Bound<'_, PyAny>) -> PyResult<Combination> {
    if let Ok(c) = v.extract::<PyRef<'_, Combination>>() {
        return Ok(c.clone());
    }
    if let Ok(f) = v.extract::<PyRef<'_, PyFact>>() {
        return Ok(Combination {
            core: Some(f.core.clone()),
            terms: [(f.id, Q::one())].into_iter().collect(),
            constant: Q::zero(),
        });
    }
    Ok(Combination {
        core: None,
        terms: BTreeMap::new(),
        constant: scalar(v)?,
    })
}
impl Combination {
    fn scaled(&self, q: Q) -> PyResult<Self> {
        if q.is_negative() {
            if let Some(core) = &self.core {
                let c = lock(core)?;
                for (id, v) in &self.terms {
                    if c.fact(*id).map_err(err)?.kind == Kind::Le && !(v * &q).is_zero() {
                        return Err(InvalidDerivationError::new_err(format!(
                            "cannot multiply inequality fact by {q}; equality facts permit arbitrary rational multipliers"
                        )));
                    }
                }
            }
        }
        let mut result = self.clone();
        result.constant *= &q;
        kernel_core::model::check_q(&result.constant).map_err(err)?;
        for v in result.terms.values_mut() {
            *v *= &q;
            kernel_core::model::check_q(v).map_err(err)?;
        }
        result.terms.retain(|_, q| !q.is_zero());
        Ok(result)
    }
    fn added(&self, other: Self) -> PyResult<Self> {
        if let (Some(a), Some(b)) = (&self.core, &other.core) {
            if !Arc::ptr_eq(a, b) {
                return Err(ScopeError::new_err("facts belong to different proofs"));
            }
        }
        let mut c = self.clone();
        if c.core.is_none() {
            c.core = other.core;
        }
        c.constant += other.constant;
        kernel_core::model::check_q(&c.constant).map_err(err)?;
        for (id, q) in other.terms {
            let value = c.terms.entry(id).or_insert_with(Q::zero);
            *value += q;
            kernel_core::model::check_q(value).map_err(err)?;
        }
        c.terms.retain(|_, q| !q.is_zero());
        Ok(c)
    }
    pub fn operands(&self, core: &Core) -> PyResult<Vec<(FactId, Q)>> {
        if self.core.as_ref().is_some_and(|c| !Arc::ptr_eq(c, core)) {
            return Err(ScopeError::new_err(
                "combination belongs to a different proof",
            ));
        }
        Ok(self.terms.iter().map(|(i, q)| (*i, q.clone())).collect())
    }
}
#[pymethods]
impl Combination {
    fn __add__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.added(combination(v)?)
    }
    fn __radd__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__add__(v)
    }
    fn __sub__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.added(combination(v)?.scaled(-Q::one())?)
    }
    fn __rsub__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        combination(v)?.added(self.scaled(-Q::one())?)
    }
    fn __neg__(&self) -> PyResult<Self> {
        self.scaled(-Q::one())
    }
    fn __mul__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.scaled(scalar(v)?)
    }
    fn __rmul__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        self.__mul__(v)
    }
    fn __truediv__(&self, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        let q = scalar(v)?;
        if q.is_zero() {
            return Err(pyo3::exceptions::PyZeroDivisionError::new_err(
                "division by zero",
            ));
        }
        self.scaled(q.recip())
    }
    fn __repr__(&self) -> String {
        format!(
            "LinCombination({} premises, constant={})",
            self.terms.len(),
            self.constant
        )
    }
}
#[pymethods]
impl PyFact {
    #[getter]
    fn kind(&self) -> PyResult<&'static str> {
        Ok(kind_name(
            lock(&self.core)?.fact(self.id).map_err(err)?.kind,
        ))
    }
    #[getter]
    pub fn expression(&self) -> PyResult<PyExpr> {
        let c = lock(&self.core)?;
        let f = c.fact(self.id).map_err(err)?;
        Ok(bound(
            f.expression.clone(),
            c.scope(f.scope).map_err(err)?.model.space.clone(),
        ))
    }
    fn __repr__(&self) -> PyResult<String> {
        let c = lock(&self.core)?;
        let f = c.fact(self.id).map_err(err)?;
        Ok(format!(
            "{}: {}",
            kind_name(f.kind),
            pretty(
                &f.expression,
                Some(&c.scope(f.scope).map_err(err)?.model.space)
            )
        ))
    }
    fn _repr_html_(&self) -> PyResult<String> {
        Ok(format!(
            "<pre>{}</pre>",
            crate::inspection::html(&self.__repr__()?)
        ))
    }
    fn __hash__(&self) -> usize {
        Arc::as_ptr(&self.core) as usize ^ self.id
    }
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        other
            .extract::<PyRef<'_, Self>>()
            .is_ok_and(|f| Arc::ptr_eq(&self.core, &f.core) && self.id == f.id)
    }
    fn __neg__(&self) -> PyResult<Combination> {
        self.combo().scaled(-Q::one())
    }
    fn __mul__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.combo().scaled(scalar(v)?)
    }
    fn __rmul__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.__mul__(v)
    }
    fn __truediv__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.combo().__truediv__(v)
    }
    fn __add__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.combo().added(combination(v)?)
    }
    fn __radd__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.__add__(v)
    }
    fn __sub__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.combo().__sub__(v)
    }
    fn __rsub__(&self, v: &Bound<'_, PyAny>) -> PyResult<Combination> {
        self.combo().__rsub__(v)
    }
}
impl PyFact {
    fn combo(&self) -> Combination {
        Combination {
            core: Some(self.core.clone()),
            terms: [(self.id, Q::one())].into_iter().collect(),
            constant: Q::zero(),
        }
    }
}
#[pyclass(name = "Scope", module = "rpx", frozen, from_py_object)]
#[derive(Clone)]
pub struct PyScope {
    pub core: Core,
    pub id: ScopeId,
}
impl PyScope {
    pub fn fact_id(&self, f: &PyFact) -> PyResult<FactId> {
        if !Arc::ptr_eq(&self.core, &f.core) {
            return Err(ScopeError::new_err("fact belongs to a different proof"));
        }
        lock(&self.core)?
            .visible(self.id, f.id)
            .map_err(|e| ScopeError::new_err(e.to_string()))?;
        Ok(f.id)
    }
    pub fn raw_expr(&self, v: &Bound<'_, PyAny>) -> PyResult<Expr> {
        let space = lock(&self.core)?
            .scope(self.id)
            .map_err(err)?
            .model
            .space
            .clone();
        in_space(v, &space)
    }
    pub fn new_fact(&self, id: FactId) -> PyFact {
        PyFact {
            core: self.core.clone(),
            id,
        }
    }
    fn base(&self, kind: &str, v: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let model = lock(&self.core)?.scope(self.id).map_err(err)?.model.clone();
        let i = index(&model, v, kind.starts_with("Row"))?;
        let id = lock(&self.core)?
            .ref_fact(self.id, kind, &Identifier::Index(i))
            .map_err(err)?;
        Ok(self.new_fact(id))
    }
    pub fn view(
        &self,
        missing: bool,
        limit: Option<usize>,
        kind: Option<&str>,
    ) -> PyResult<ObligationView> {
        let mut c = lock(&self.core)?;
        let goals = c.obligations(self.id).map_err(err)?;
        if !missing && kind.is_none() {
            return Ok(ObligationView {
                scope: self.clone(),
                epoch: c.scope(self.id).map_err(err)?.map_epoch,
                indices: None,
                shown: limit.unwrap_or(goals.len()).min(goals.len()),
                count: goals.len(),
            });
        }
        let mut indices = Vec::new();
        for g in goals.iter() {
            if kind.is_some_and(|k| k != kind_name(g.kind) && !g.label.starts_with(k)) {
                continue;
            }
            if !missing || c.resolve_goal(self.id, g).map_err(err)?.is_none() {
                indices.push(g.index);
            }
        }
        let count = indices.len();
        indices.truncate(limit.unwrap_or(count));
        Ok(ObligationView {
            scope: self.clone(),
            epoch: c.scope(self.id).map_err(err)?.map_epoch,
            shown: indices.len(),
            indices: Some(indices),
            count,
        })
    }
    fn derive_lin(
        &self,
        kind: Kind,
        by: &Bound<'_, PyAny>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let combination = combination(by)?;
        let terms = combination.operands(&self.core)?;
        for (id, _) in &terms {
            self.fact_id(&self.new_fact(*id))?;
        }
        let expected = expect.map(|v| self.raw_expr(v)).transpose()?;
        let id = lock(&self.core)?
            .transaction(self.id, |c| {
                c.lin(
                    self.id,
                    kind,
                    &terms,
                    combination.constant,
                    expected.as_ref(),
                )
            })
            .map_err(err)?;
        Ok(self.new_fact(id))
    }
}
#[pymethods]
impl PyScope {
    #[getter]
    fn model(&self) -> PyResult<PyModel> {
        Ok(PyModel {
            inner: lock(&self.core)?.scope(self.id).map_err(err)?.model.clone(),
        })
    }
    #[getter]
    fn output(&self) -> PyResult<PyModel> {
        Ok(PyModel {
            inner: lock(&self.core)?
                .scope(self.id)
                .map_err(err)?
                .output_model
                .clone(),
        })
    }
    #[getter]
    fn vars(&self) -> PyResult<VariablesView> {
        Ok(self.model()?.vars())
    }
    #[getter]
    fn derive(&self) -> Derive {
        Derive {
            scope: self.clone(),
        }
    }
    #[getter]
    fn assumption(&self) -> PyResult<PyFact> {
        let c = lock(&self.core)?;
        let id = *c
            .scope(self.id)
            .map_err(err)?
            .assumptions
            .last()
            .ok_or_else(|| ScopeError::new_err("scope has no assumption"))?;
        Ok(self.new_fact(id))
    }
    #[getter]
    fn obligations(&self) -> PyResult<ObligationView> {
        self.view(false, None, None)
    }
    fn plan(&self) -> PyResult<ObligationView> {
        self.obligations()
    }
    #[pyo3(signature=(*,limit=None,kind=None))]
    fn missing(&self, limit: Option<usize>, kind: Option<&str>) -> PyResult<ObligationView> {
        self.view(true, limit, kind)
    }
    #[pyo3(signature=(overrides=None,*,default=None))]
    fn map<'py>(
        slf: PyRef<'py, Self>,
        overrides: Option<&Bound<'_, PyDict>>,
        default: Option<&str>,
    ) -> PyResult<PyRef<'py, Self>> {
        if default.is_some_and(|d| d != "same_name") {
            return Err(crate::errors::MappingError::new_err(
                "default must be 'same_name' or None",
            ));
        }
        let mut pairs = vec![];
        if let Some(values) = overrides {
            for (k, v) in values.iter() {
                pairs.push((k.extract::<String>()?, expression(&v)?));
            }
        }
        lock(&slf.core)?
            .set_mapping(slf.id, default.is_some(), pairs)
            .map_err(err)?;
        Ok(slf)
    }
    fn lower(&self, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.base("VarLower", variable)
    }
    fn upper(&self, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.base("VarUpper", variable)
    }
    fn integer(&self, variable: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        self.base("VarInt", variable)
    }
    #[pyo3(signature=(row,*,side=None))]
    fn row(&self, row: &Bound<'_, PyAny>, side: Option<&str>) -> PyResult<PyFact> {
        let tag = {
            let c = lock(&self.core)?;
            let m = &c.scope(self.id).map_err(err)?.model;
            let i = index(m, row, true)?;
            let r = &m.inner.rows[i as usize];
            match side {
                Some("lower") => "RowLower",
                Some("upper") => "RowUpper",
                Some("equal") => "RowEq",
                None if r.lower.is_some() && r.lower == r.upper => "RowEq",
                None if r.lower.is_none() => "RowUpper",
                None if r.upper.is_none() => "RowLower",
                _ => {
                    return Err(PyTypeError::new_err(
                        "ranged row requires side='lower' or 'upper'",
                    ));
                }
            }
        };
        self.base(tag, row)
    }
    #[pyo3(signature=(goal,*,by))]
    fn prove(&self, goal: &Bound<'_, PyAny>, by: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let combination = combination(by)?;
        let terms = combination.operands(&self.core)?;
        for (id, _) in &terms {
            self.fact_id(&self.new_fact(*id))?;
        }
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        let goals = c.obligations(self.id).map_err(err)?;
        let i = if let Ok(g) = goal.extract::<PyRef<'_, Goal>>() {
            g.validate(
                &self.core,
                self.id,
                c.scope(self.id).map_err(err)?.map_epoch,
            )?;
            g.index
        } else {
            let label = goal.extract::<String>()?;
            goals
                .iter()
                .position(|g| g.label == label)
                .ok_or_else(|| PyKeyError::new_err(label))?
        };
        let g = &goals[i];
        let id = c
            .transaction(self.id, |c| {
                c.lin(
                    self.id,
                    g.kind,
                    &terms,
                    combination.constant,
                    Some(&g.expression),
                )
            })
            .map_err(err)?;
        c.assign_goal(self.id, i, id).map_err(err)?;
        Ok(self.new_fact(id))
    }
    fn finish(slf: PyRef<'_, Self>) -> PyResult<PyRef<'_, Self>> {
        lock(&slf.core)?.finish(slf.id).map_err(err)?;
        Ok(slf)
    }
    fn close_absurd(&self, fact: &PyFact) -> PyResult<()> {
        let id = self.fact_id(fact)?;
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        if c.scope(self.id).map_err(err)?.derivation {
            c.absurd(self.id, id).map_err(err)?;
            let reference = c.fact(id).map_err(err)?.reference.clone();
            let item = c.scope_mut(self.id).map_err(err)?;
            item.state = ScopeState::Sealed;
            item.conclusion = Some(kernel_core::proof::DerivationEnd::Absurd(reference));
            Ok(())
        } else {
            c.close_absurd(self.id, id).map_err(err)
        }
    }
    fn drop(&self, facts: &Bound<'_, PyAny>) -> PyResult<()> {
        let ids = if let Ok(f) = facts.extract::<PyRef<'_, PyFact>>() {
            vec![self.fact_id(&f)?]
        } else {
            facts
                .try_iter()?
                .map(|v| {
                    let v = v?;
                    self.fact_id(&*v.extract::<PyRef<'_, PyFact>>()?)
                })
                .collect::<PyResult<Vec<_>>>()?
        };
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        for id in &ids {
            c.visible(self.id, *id).map_err(err)?;
        }
        c.drop_facts(self.id, &ids).map_err(err)
    }
    #[pyo3(signature=(expr,*,at=None,kind="continuous",because=None))]
    fn split(
        &self,
        expr: &Bound<'_, PyAny>,
        at: Option<&Bound<'_, PyAny>>,
        kind: &str,
        because: Option<&PyFact>,
    ) -> PyResult<(Self, Self)> {
        let original = self.raw_expr(expr)?;
        let mut expression = original.clone();
        let threshold = at.map(scalar).transpose()?.unwrap_or_else(Q::zero);
        expression.constant -= &threshold;
        let supplied = because.map(|f| self.fact_id(f)).transpose()?;
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        let integer = match kind {
            "continuous" => {
                if supplied.is_some() {
                    return Err(PyTypeError::new_err(
                        "continuous split does not take integer witness",
                    ));
                }
                None
            }
            "integer" => {
                if !threshold.is_integer() {
                    return Err(InvalidDerivationError::new_err(
                        "integer split requires an integer threshold",
                    ));
                }
                let id = if let Some(id) = supplied {
                    id
                } else {
                    if !original.constant.is_zero()
                        || original.terms.len() != 1
                        || !original.terms[0].1.is_one()
                    {
                        return Err(InvalidDerivationError::new_err(
                            "integer split requires an explicit INT witness",
                        ));
                    }
                    c.ref_fact(self.id, "VarInt", &Identifier::Index(original.terms[0].0))
                        .map_err(err)?
                };
                if c.fact(id).map_err(err)?.kind != Kind::Int
                    || c.fact(id).map_err(err)?.expression != original
                {
                    return Err(InvalidDerivationError::new_err(
                        "INT witness must prove the split expression",
                    ));
                }
                if threshold.is_zero() {
                    Some(id)
                } else {
                    Some(
                        c.lin(self.id, Kind::Int, &[(id, Q::one())], -threshold, None)
                            .map_err(err)?,
                    )
                }
            }
            _ => return Err(PyTypeError::new_err("kind must be continuous or integer")),
        };
        c.split_options(self.id, expression.clone(), integer)
            .map_err(err)?;
        let mut right = kernel_compiler_core::expr::neg(&expression).map_err(err)?;
        if integer.is_some() {
            right.constant += Q::one();
        }
        let left = c.branch(self.id, expression.clone()).map_err(err)?.0;
        let right = c.branch(self.id, right).map_err(err)?.0;
        let inherited = c.scope(self.id).map_err(err)?.mapping.clone();
        let spec = c.scope(self.id).map_err(err)?.mapping_spec.clone();
        for id in [left, right] {
            c.scope_mut(id).map_err(err)?.mapping = inherited.clone();
            c.scope_mut(id).map_err(err)?.mapping_spec = spec.clone();
        }
        c.finish_split(self.id, expression, integer, left, right)
            .map_err(err)?;
        Ok((
            Self {
                core: self.core.clone(),
                id: left,
            },
            Self {
                core: self.core.clone(),
                id: right,
            },
        ))
    }
    #[getter]
    fn trace(&self) -> crate::inspection::TraceView {
        crate::inspection::TraceView {
            scope: self.clone(),
        }
    }
    fn __repr__(&self) -> PyResult<String> {
        let c = lock(&self.core)?;
        let s = c.scope(self.id).map_err(err)?;
        Ok(format!(
            "Scope {} -> {} ({:?})",
            s.model.inner.name, s.output_model.inner.name, s.state
        ))
    }
}
#[pyclass(name = "Derive", module = "rpx", frozen)]
pub struct Derive {
    pub scope: PyScope,
}
#[pymethods]
impl Derive {
    #[pyo3(signature=(by,*,expect=None))]
    fn eq(&self, by: &Bound<'_, PyAny>, expect: Option<&Bound<'_, PyAny>>) -> PyResult<PyFact> {
        self.scope.derive_lin(Kind::Eq, by, expect)
    }
    #[pyo3(signature=(by,*,expect=None))]
    fn le(&self, by: &Bound<'_, PyAny>, expect: Option<&Bound<'_, PyAny>>) -> PyResult<PyFact> {
        self.scope.derive_lin(Kind::Le, by, expect)
    }
    #[pyo3(signature=(by,*,expect=None))]
    fn int(&self, by: &Bound<'_, PyAny>, expect: Option<&Bound<'_, PyAny>>) -> PyResult<PyFact> {
        self.scope.derive_lin(Kind::Int, by, expect)
    }
    fn round(&self, le: &PyFact, integer: &PyFact) -> PyResult<PyFact> {
        let a = self.scope.fact_id(le)?;
        let b = self.scope.fact_id(integer)?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| c.round(self.scope.id, a, b))
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    fn eqpair(&self, positive: &PyFact, negative: &PyFact) -> PyResult<PyFact> {
        let a = self.scope.fact_id(positive)?;
        let b = self.scope.fact_id(negative)?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| c.eqpair(self.scope.id, a, b))
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    fn box_le(&self, expression: &Bound<'_, PyAny>) -> PyResult<PyFact> {
        let e = self.scope.raw_expr(expression)?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| c.box_le(self.scope.id, e))
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    #[pyo3(signature=(expression,fixes=None))]
    fn eq_on_fixed(
        &self,
        expression: &Bound<'_, PyAny>,
        fixes: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyFact> {
        let e = self.scope.raw_expr(expression)?;
        let defs = self.definitions(fixes)?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| {
                c.eq_on_fixed(self.scope.id, e, &defs.into_iter().collect())
            })
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    #[pyo3(signature=(fact,definitions,*,expect=None))]
    fn rewrite(
        &self,
        fact: &PyFact,
        definitions: &Bound<'_, PyDict>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let f = self.scope.fact_id(fact)?;
        let defs = self.definitions(Some(definitions))?;
        let e = expect.map(|e| self.scope.raw_expr(e)).transpose()?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| c.rewrite(self.scope.id, f, &defs, e))
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    #[pyo3(signature=(definitions,*,goals=None))]
    fn substitution(
        &self,
        definitions: &Bound<'_, PyDict>,
        goals: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Vec<PyFact>> {
        let defs = self.definitions(Some(definitions))?;
        let mut expressions = Vec::new();
        if let Some(goals) = goals {
            for g in goals.try_iter()? {
                expressions.push(self.scope.raw_expr(&g?)?);
            }
        }
        let mut c = lock(&self.scope.core)?;
        if c.scope(self.scope.id).map_err(err)?.mapping.is_some() {
            for g in c.obligations(self.scope.id).map_err(err)?.iter() {
                if g.kind == Kind::Eq || g.label == "objective.non_increasing" {
                    expressions.push(g.expression.clone());
                }
            }
        }
        let ids = c
            .transaction(self.scope.id, |c| {
                c.substitution(self.scope.id, &defs, &expressions)
            })
            .map_err(err)?;
        Ok(ids.into_iter().map(|id| self.scope.new_fact(id)).collect())
    }
    fn parity_fix(&self, variable: &Bound<'_, PyAny>, equality: &PyFact) -> PyResult<PyFact> {
        let f = self.scope.fact_id(equality)?;
        let mut c = lock(&self.scope.core)?;
        let i = index(&c.scope(self.scope.id).map_err(err)?.model, variable, false)?;
        let id = c
            .transaction(self.scope.id, |c| c.parity_fix(self.scope.id, i, f))
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
}
impl Derive {
    pub fn definitions(&self, defs: Option<&Bound<'_, PyDict>>) -> PyResult<Vec<(u32, FactId)>> {
        let mut out = vec![];
        if let Some(defs) = defs {
            for (k, v) in defs.iter() {
                let f = v.extract::<PyRef<'_, PyFact>>()?;
                let id = self.scope.fact_id(&f)?;
                let c = lock(&self.scope.core)?;
                out.push((
                    index(&c.scope(self.scope.id).map_err(err)?.model, &k, false)?,
                    id,
                ));
            }
        }
        Ok(out)
    }
}
#[pyclass(name = "Goal", module = "rpx", frozen)]
pub struct Goal {
    scope: PyScope,
    epoch: u64,
    index: usize,
}
impl Goal {
    fn validate(&self, core: &Core, scope: usize, epoch: u64) -> PyResult<()> {
        if !Arc::ptr_eq(&self.scope.core, core) || self.scope.id != scope {
            return Err(ScopeError::new_err(
                "goal belongs to another proof or scope",
            ));
        }
        if self.epoch != epoch {
            return Err(ScopeError::new_err("goal is stale after mapping change"));
        }
        Ok(())
    }
    fn data(&self) -> PyResult<kernel_compiler_core::complete::Obligation> {
        let mut c = lock(&self.scope.core)?;
        self.validate(
            &self.scope.core,
            self.scope.id,
            c.scope(self.scope.id).map_err(err)?.map_epoch,
        )?;
        Ok(c.obligations(self.scope.id).map_err(err)?[self.index].clone())
    }
}
#[pymethods]
impl Goal {
    #[getter]
    fn label(&self) -> PyResult<String> {
        Ok(self.data()?.label)
    }
    #[getter]
    fn kind(&self) -> PyResult<&'static str> {
        Ok(kind_name(self.data()?.kind))
    }
    #[getter]
    fn expression(&self) -> PyResult<PyExpr> {
        let g = self.data()?;
        Ok(bound(
            g.expression,
            lock(&self.scope.core)?
                .scope(self.scope.id)
                .map_err(err)?
                .model
                .space
                .clone(),
        ))
    }
    #[getter]
    fn discharged(&self) -> PyResult<bool> {
        let g = self.data()?;
        Ok(lock(&self.scope.core)?
            .resolve_goal(self.scope.id, &g)
            .map_err(err)?
            .is_some())
    }
    fn __repr__(&self) -> PyResult<String> {
        let g = self.data()?;
        let c = lock(&self.scope.core)?;
        Ok(format!(
            "{}: {} {}",
            g.label,
            pretty(
                &g.expression,
                Some(&c.scope(self.scope.id).map_err(err)?.model.space)
            ),
            match g.kind {
                Kind::Eq => "= 0",
                Kind::Le => "<= 0",
                Kind::Int => "is integer",
            }
        ))
    }
}
#[pyclass(name = "ObligationView", module = "rpx", frozen)]
pub struct ObligationView {
    scope: PyScope,
    epoch: u64,
    indices: Option<Vec<usize>>,
    shown: usize,
    count: usize,
}
impl ObligationView {
    fn selected(&self) -> impl Iterator<Item = usize> + '_ {
        (0..self.shown).map(|i| self.indices.as_ref().map_or(i, |v| v[i]))
    }
}
#[pymethods]
impl ObligationView {
    fn __len__(&self) -> usize {
        self.shown
    }
    #[getter]
    fn count(&self) -> usize {
        self.count
    }
    fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<Goal> {
        let c = lock(&self.scope.core)?;
        if c.scope(self.scope.id).map_err(err)?.map_epoch != self.epoch {
            return Err(ScopeError::new_err("view is stale after mapping change"));
        }
        let index = if let Ok(i) = key.extract::<usize>() {
            if i >= self.shown {
                return Err(PyIndexError::new_err("goal index"));
            }
            self.indices.as_ref().map_or(i, |v| v[i])
        } else {
            let label = key.extract::<String>()?;
            let goals = c.scope(self.scope.id).map_err(err)?.goals.as_ref().unwrap();
            self.selected()
                .find(|i| goals[*i].label == label)
                .ok_or_else(|| PyKeyError::new_err(label))?
        };
        Ok(Goal {
            scope: self.scope.clone(),
            epoch: self.epoch,
            index,
        })
    }
    fn to_list(&self) -> PyResult<Vec<Goal>> {
        let c = lock(&self.scope.core)?;
        if c.scope(self.scope.id).map_err(err)?.map_epoch != self.epoch {
            return Err(ScopeError::new_err("view is stale after mapping change"));
        }
        Ok(self
            .selected()
            .map(|index| Goal {
                scope: self.scope.clone(),
                epoch: self.epoch,
                index,
            })
            .collect())
    }
    fn summary(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let mut c = lock(&self.scope.core)?;
        if c.scope(self.scope.id).map_err(err)?.map_epoch != self.epoch {
            return Err(ScopeError::new_err("view is stale after mapping change"));
        }
        let goals = c.obligations(self.scope.id).map_err(err)?;
        let mut missing = 0;
        for i in self.selected() {
            if c.resolve_goal(self.scope.id, &goals[i])
                .map_err(err)?
                .is_none()
            {
                missing += 1;
            }
        }
        json_py(
            py,
            &serde_json::json!({"count":self.count,"shown":self.shown,"missing":missing,"discharged":self.shown-missing}),
        )
    }
    fn __repr__(&self) -> PyResult<String> {
        let mut c = lock(&self.scope.core)?;
        if c.scope(self.scope.id).map_err(err)?.map_epoch != self.epoch {
            return Err(ScopeError::new_err("view is stale after mapping change"));
        }
        let goals = c.obligations(self.scope.id).map_err(err)?;
        let space = c.scope(self.scope.id).map_err(err)?.model.space.clone();
        let mut text = format!("Obligations: {}\n", self.count);
        for i in self.selected().take(20) {
            let g = &goals[i];
            let done = c.resolve_goal(self.scope.id, g).map_err(err)?.is_some();
            text.push_str(&format!(
                "  {} {}\n    {}\n",
                if done { "✓" } else { "✗" },
                g.label,
                pretty(&g.expression, Some(&space))
            ));
        }
        Ok(text)
    }
    fn _repr_html_(&self) -> PyResult<String> {
        Ok(format!(
            "<pre>{}</pre>",
            crate::inspection::html(&self.__repr__()?)
        ))
    }
}
#[pyclass(name = "Proof", module = "rpx._native", frozen)]
pub struct PyProof {
    pub core: Core,
}
#[pymethods]
impl PyProof {
    #[new]
    fn new(source: &PyModel, target: &PyModel) -> PyResult<Self> {
        Ok(Self {
            core: Arc::new(Mutex::new(
                ProofCore::new(source.inner.clone(), target.inner.clone()).map_err(err)?,
            )),
        })
    }
    #[getter]
    fn forward(&self) -> PyResult<PyScope> {
        Ok(PyScope {
            core: self.core.clone(),
            id: lock(&self.core)?.forward,
        })
    }
    #[getter]
    fn reverse(&self) -> PyResult<PyScope> {
        Ok(PyScope {
            core: self.core.clone(),
            id: lock(&self.core)?.reverse,
        })
    }
    fn preflight(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        json_py(py, &lock(&self.core)?.preflight().map_err(err)?)
    }
    #[getter]
    fn lowering_count(&self) -> PyResult<u64> {
        Ok(lock(&self.core)?.lowering_count)
    }
    fn write(&self, directory: PathBuf) -> PyResult<()> {
        let mut c = lock(&self.core)?;
        let compiled = c.compile().map_err(err)?;
        for (name, bytes) in [
            ("source.mcm", &compiled.source),
            ("target.mcm", &compiled.target),
        ] {
            std::fs::write(directory.join(name), bytes)
                .map_err(|e| PyOSError::new_err(e.to_string()))?;
        }
        std::fs::write(directory.join("proof.rpa"), compiled.rpa.as_bytes())
            .map_err(|e| PyOSError::new_err(e.to_string()))?;
        std::fs::write(directory.join("proof.rpx"), &compiled.rpx)
            .map_err(|e| PyOSError::new_err(e.to_string()))?;
        Ok(())
    }
    fn certificate(&self) -> crate::inspection::CertificateView {
        crate::inspection::CertificateView {
            core: self.core.clone(),
        }
    }
}
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyProof>()?;
    m.add_class::<Cases>()?;
    m.add_class::<MappingView>()?;
    m.add_class::<Assembler>()?;
    m.add_class::<PyScope>()?;
    m.add_class::<PyFact>()?;
    m.add_class::<Combination>()?;
    m.add_class::<Derive>()?;
    m.add_class::<Goal>()?;
    m.add_class::<ObligationView>()?;
    Ok(())
}

#[pyclass(name = "Cases", module = "rpx", frozen)]
pub struct Cases {
    core: Core,
    id: usize,
}
#[pymethods]
impl Cases {
    #[getter]
    fn left(&self) -> PyResult<PyScope> {
        Ok(PyScope {
            core: self.core.clone(),
            id: lock(&self.core)?.cases[self.id].left,
        })
    }
    #[getter]
    fn right(&self) -> PyResult<PyScope> {
        Ok(PyScope {
            core: self.core.clone(),
            id: lock(&self.core)?.cases[self.id].right,
        })
    }
    fn finish(&self) -> PyResult<PyFact> {
        let mut c = lock(&self.core)?;
        let case = c.cases[self.id].clone();
        if let Some(id) = case.result {
            return Ok(PyFact {
                core: self.core.clone(),
                id,
            });
        }
        let mut branches = Vec::new();
        for id in [case.left, case.right] {
            let s = c.scope(id).map_err(err)?;
            let conclusion = s.conclusion.clone().ok_or_else(|| {
                crate::errors::UnprovedGoalError::new_err("Cases branch has no conclusion")
            })?;
            branches.push(kernel_core::proof::Derivation {
                steps: s.steps.clone(),
                end: conclusion,
            });
        }
        c.scope_mut(case.parent).map_err(err)?.state = ScopeState::Open;
        let result = c.transaction(case.parent, |c| {
            c.install_cases(
                case.parent,
                case.kind,
                case.goal,
                case.split,
                case.integer,
                branches.remove(0),
                branches.remove(0),
            )
        });
        match result {
            Ok(id) => {
                c.cases[self.id].result = Some(id);
                Ok(PyFact {
                    core: self.core.clone(),
                    id,
                })
            }
            Err(e) => {
                c.scope_mut(case.parent).map_err(err)?.state = ScopeState::Suspended;
                Err(err(e))
            }
        }
    }
}
#[pymethods]
impl Derive {
    #[pyo3(signature=(split,*,kind,expect,integer=None))]
    fn cases(
        &self,
        split: &Bound<'_, PyAny>,
        kind: &str,
        expect: &Bound<'_, PyAny>,
        integer: Option<&PyFact>,
    ) -> PyResult<Cases> {
        let expression = self.scope.raw_expr(split)?;
        let goal = self.scope.raw_expr(expect)?;
        let kind = parse_kind(kind).map_err(err)?;
        let integer = integer.map(|f| self.scope.fact_id(f)).transpose()?;
        let mut c = lock(&self.scope.core)?;
        c.ensure_open(self.scope.id).map_err(err)?;
        c.split_options(self.scope.id, expression.clone(), integer)
            .map_err(err)?;
        let mut right = kernel_compiler_core::expr::neg(&expression).map_err(err)?;
        if integer.is_some() {
            right.constant += Q::one();
        }
        let left = c.branch(self.scope.id, expression.clone()).map_err(err)?.0;
        let right = c.branch(self.scope.id, right).map_err(err)?.0;
        c.scope_mut(left).map_err(err)?.derivation = true;
        c.scope_mut(right).map_err(err)?.derivation = true;
        c.scope_mut(self.scope.id).map_err(err)?.state = ScopeState::Suspended;
        let id = c.cases.len();
        c.cases.push(kernel_compiler_core::proof::CaseSession {
            parent: self.scope.id,
            left,
            right,
            kind,
            goal,
            split: expression,
            integer,
            result: None,
        });
        Ok(Cases {
            core: self.scope.core.clone(),
            id,
        })
    }
    #[pyo3(signature=(fact,*,zeros=None,scale=None,coordinates=None))]
    fn zero_sum(
        &self,
        py: Python<'_>,
        fact: &PyFact,
        zeros: Option<&Bound<'_, PyDict>>,
        scale: Option<&Bound<'_, PyAny>>,
        coordinates: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let f = self.scope.fact_id(fact)?;
        let zeros = self.definitions(zeros)?.into_iter().collect();
        let scale = scale.map(scalar).transpose()?.unwrap_or_else(Q::one);
        let model = lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .model
            .clone();
        let coordinates = coordinates
            .map(|v| crate::models::identifiers(&model, v, false))
            .transpose()?;
        let mut c = lock(&self.scope.core)?;
        let result = c
            .transaction(self.scope.id, |c| {
                c.zero_sum(self.scope.id, f, &zeros, scale, coordinates.as_deref())
            })
            .map_err(err)?;
        let out = PyDict::new(py);
        let mut values: Vec<_> = result.into_iter().collect();
        values.sort_by_key(|(i, _)| *i);
        for (i, id) in values {
            out.set_item(
                c.scope(self.scope.id).map_err(err)?.model.inner.vars[i as usize]
                    .name
                    .clone(),
                Py::new(py, self.scope.new_fact(id))?,
            )?;
        }
        Ok(out.into_any().unbind())
    }
    #[pyo3(signature=(goal,definitions,residual,*,kind=None))]
    fn substitution_fact(
        &self,
        goal: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyDict>,
        residual: &PyFact,
        kind: Option<&str>,
    ) -> PyResult<PyFact> {
        let goal = self.scope.raw_expr(goal)?;
        let defs = self.definitions(Some(definitions))?;
        let residual = self.scope.fact_id(residual)?;
        let kind = kind.map(parse_kind).transpose().map_err(err)?;
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| {
                c.derive_substitution(self.scope.id, goal, &defs, residual, kind)
            })
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    fn rewrite_many(
        &self,
        facts: &Bound<'_, PyAny>,
        definitions: &Bound<'_, PyDict>,
    ) -> PyResult<Vec<PyFact>> {
        let defs = self.definitions(Some(definitions))?;
        let ids = facts
            .try_iter()?
            .map(|v| self.scope.fact_id(&*v?.extract::<PyRef<'_, PyFact>>()?))
            .collect::<PyResult<Vec<_>>>()?;
        let result: Vec<FactId> = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| {
                let plan = kernel_compiler_core::proof::PivotPlan::new(c, self.scope.id, &defs)?;
                ids.into_iter()
                    .map(|id| c.rewrite_plan(self.scope.id, id, &plan, None))
                    .collect()
            })
            .map_err(err)?;
        Ok(result
            .into_iter()
            .map(|id| self.scope.new_fact(id))
            .collect())
    }
    #[pyo3(signature=(*,bits,distance,variables,cliques))]
    fn plotkin(
        &self,
        bits: u32,
        distance: u32,
        variables: &Bound<'_, PyAny>,
        cliques: &Bound<'_, PyAny>,
    ) -> PyResult<PyFact> {
        let facts = cliques
            .try_iter()?
            .map(|v| self.scope.fact_id(&*v?.extract::<PyRef<'_, PyFact>>()?))
            .collect::<PyResult<Vec<_>>>()?;
        let model = lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .model
            .clone();
        let mut pairs = Vec::new();
        for v in variables.try_iter()? {
            let v = v?;
            pairs.push((
                index(&model, &v.get_item(0)?, false)?,
                v.get_item(1)?.extract::<u64>()?,
            ));
        }
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| {
                c.plotkin(self.scope.id, bits, distance, &pairs, &facts)
            })
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    fn subset_bounds(&self, fact: &PyFact, subsets: &Bound<'_, PyAny>) -> PyResult<Vec<PyFact>> {
        let f = self.scope.fact_id(fact)?;
        let model = lock(&self.scope.core)?
            .scope(self.scope.id)
            .map_err(err)?
            .model
            .clone();
        let mut sets = Vec::new();
        for subset in subsets.try_iter()? {
            sets.push(
                crate::models::identifiers(&model, &subset?, false)?
                    .into_iter()
                    .collect(),
            );
        }
        let ids = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| c.subset_bounds(self.scope.id, f, &sets))
            .map_err(err)?;
        Ok(ids.into_iter().map(|id| self.scope.new_fact(id)).collect())
    }
}
#[pymethods]
impl PyScope {
    fn conclude(&self, fact: &PyFact) -> PyResult<()> {
        let id = self.fact_id(fact)?;
        let mut c = lock(&self.core)?;
        c.ensure_open(self.id).map_err(err)?;
        let case = c
            .cases
            .iter()
            .find(|case| case.left == self.id || case.right == self.id)
            .ok_or_else(|| ScopeError::new_err("conclude is only valid inside Cases"))?;
        let f = c.fact(id).map_err(err)?;
        if f.expression != case.goal || (f.kind != case.kind && f.kind != Kind::Eq) {
            return Err(InvalidDerivationError::new_err(
                "branch conclusion does not prove the common Cases goal",
            ));
        }
        let reference = f.reference.clone();
        let s = c.scope_mut(self.id).map_err(err)?;
        s.conclusion = Some(kernel_core::proof::DerivationEnd::Witness(reference));
        s.state = ScopeState::Sealed;
        Ok(())
    }
}

/// Expert operand lists; uses exactly the same ownership checks and state machine.
#[pyclass(name = "Assembler", module = "rpx.lowlevel", frozen)]
pub struct Assembler {
    scope: PyScope,
}
#[pymethods]
impl Assembler {
    #[new]
    fn new(scope: &PyScope) -> Self {
        Self {
            scope: scope.clone(),
        }
    }
    #[pyo3(signature=(kind,terms,*,constant=None,expect=None))]
    fn linear(
        &self,
        kind: &str,
        terms: &Bound<'_, PyAny>,
        constant: Option<&Bound<'_, PyAny>>,
        expect: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyFact> {
        let kind = parse_kind(kind).map_err(err)?;
        let constant = constant.map(scalar).transpose()?.unwrap_or_else(Q::zero);
        let expected = expect.map(|v| self.scope.raw_expr(v)).transpose()?;
        let mut values = Vec::new();
        for term in terms.try_iter()? {
            let term = term?;
            let fact = term.get_item(0)?;
            let fact = fact.extract::<PyRef<'_, PyFact>>()?;
            values.push((self.scope.fact_id(&fact)?, scalar(&term.get_item(1)?)?));
        }
        let id = lock(&self.scope.core)?
            .transaction(self.scope.id, |c| {
                c.lin(self.scope.id, kind, &values, constant, expected.as_ref())
            })
            .map_err(err)?;
        Ok(self.scope.new_fact(id))
    }
    fn assign(&self, checks: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut facts = Vec::new();
        for v in checks.try_iter()? {
            let v = v?;
            facts.push(if v.is_none() {
                None
            } else {
                Some(self.scope.fact_id(&*v.extract::<PyRef<'_, PyFact>>()?)?)
            });
        }
        let mut c = lock(&self.scope.core)?;
        c.ensure_open(self.scope.id).map_err(err)?;
        let goals = c.obligations(self.scope.id).map_err(err)?;
        if goals.len() != facts.len() {
            return Err(InvalidDerivationError::new_err(
                "ordered witnesses must cover every obligation",
            ));
        }
        for (g, f) in goals.iter().zip(&facts) {
            if let Some(id) = f {
                let f = c.fact(*id).map_err(err)?;
                if f.expression != g.expression || (f.kind != g.kind && f.kind != Kind::Eq) {
                    return Err(InvalidDerivationError::new_err(format!(
                        "witness does not prove {}",
                        g.label
                    )));
                }
            } else if !matches!(
                c.find(self.scope.id, g.kind, &g.expression).map_err(err)?,
                kernel_compiler_core::proof::FindResult::Exact
            ) {
                return Err(InvalidDerivationError::new_err(format!(
                    "{} is not literal Exact",
                    g.label
                )));
            }
        }
        for (i, f) in facts.into_iter().enumerate() {
            if let Some(id) = f {
                c.assign_goal(self.scope.id, i, id).map_err(err)?;
            }
        }
        Ok(())
    }
}

#[pyclass(name = "MappingView", module = "rpx", frozen)]
pub struct MappingView {
    pub scope: PyScope,
    epoch: u64,
}
impl MappingView {
    pub fn substitute(&self, e: &kernel_compiler_core::space::BoundExpr) -> PyResult<PyExpr> {
        let c = lock(&self.scope.core)?;
        let s = c.scope(self.scope.id).map_err(err)?;
        if s.map_epoch != self.epoch {
            return Err(ScopeError::new_err("mapping view is stale"));
        }
        e.in_space(&s.output_model.space).map_err(err)?;
        let values = s
            .mapping
            .as_ref()
            .ok_or_else(|| crate::errors::MappingError::new_err("declare a map"))?;
        let mut constant = e.value.constant.clone();
        let mut terms = std::collections::BTreeMap::<u32, Q>::new();
        for (i, q) in &e.value.terms {
            let value = &values[*i as usize];
            constant += &value.constant * q;
            for (j, v) in &value.terms {
                *terms.entry(*j).or_insert_with(Q::zero) += q * v;
            }
        }
        Ok(bound(
            kernel_compiler_core::expr::canonical(constant, terms).map_err(err)?,
            s.model.space.clone(),
        ))
    }
}
#[pymethods]
impl MappingView {
    fn __len__(&self) -> PyResult<usize> {
        let c = lock(&self.scope.core)?;
        let s = c.scope(self.scope.id).map_err(err)?;
        if s.map_epoch != self.epoch {
            return Err(ScopeError::new_err("mapping view is stale"));
        }
        Ok(s.mapping
            .as_ref()
            .ok_or_else(|| crate::errors::MappingError::new_err("declare a map"))?
            .len())
    }
    fn __getitem__(&self, index: usize) -> PyResult<PyExpr> {
        let c = lock(&self.scope.core)?;
        let s = c.scope(self.scope.id).map_err(err)?;
        if s.map_epoch != self.epoch {
            return Err(ScopeError::new_err("mapping view is stale"));
        }
        let e = s
            .mapping
            .as_ref()
            .and_then(|v| v.get(index))
            .ok_or_else(|| PyIndexError::new_err("output coordinate"))?;
        Ok(bound(e.clone(), s.model.space.clone()))
    }
}
#[pymethods]
impl PyScope {
    #[getter]
    fn mapping(&self) -> PyResult<MappingView> {
        Ok(MappingView {
            scope: self.clone(),
            epoch: lock(&self.core)?.scope(self.id).map_err(err)?.map_epoch,
        })
    }
    fn pullback(&self, expression: &Bound<'_, PyAny>) -> PyResult<PyExpr> {
        self.mapping()?
            .substitute(&crate::expressions::expression(expression)?)
    }
}
