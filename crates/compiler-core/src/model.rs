//! Exact model edits and queries over the kernel's canonical model type.
use crate::error::Error;
use crate::expr;
use crate::limit::{check_terms, invalid, resource};
use kernel_core::model::{
    self, Expr, MAX_NAME_BYTES, MAX_ROWS, MAX_TERMS, MAX_VARS, Model as KernelModel, Q,
    Row as KernelRow, Var as KernelVar, check_q, parse_q,
};
use kernel_core::proof::{Kind, Ref};
use num_traits::{One, Signed, Zero};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ModelFormat {
    Auto,
    Mcm,
    Mps,
    Lp,
    Json,
}

#[derive(Clone, Debug)]
pub struct Model {
    pub space: std::sync::Arc<crate::space::Space>,
    pub inner: KernelModel,
    pub var_index: HashMap<String, u32>,
    pub row_index: HashMap<String, u32>,
}

#[derive(Clone, Debug)]
pub enum Identifier {
    Index(u32),
    Name(String),
}

fn check_name(name: &str) -> Result<(), Error> {
    if name.len() > MAX_NAME_BYTES {
        return Err(resource("name budget"));
    }
    if name.is_empty() || !name.is_ascii() || name.bytes().any(|b| b.is_ascii_control()) {
        return Err(invalid("name"));
    }
    Ok(())
}

fn names(
    vars: &[KernelVar],
    rows: &[KernelRow],
) -> Result<(HashMap<String, u32>, HashMap<String, u32>), Error> {
    let mut var_index = HashMap::new();
    let mut row_index = HashMap::new();
    var_index
        .try_reserve(vars.len())
        .map_err(|_| resource("model name allocation"))?;
    row_index
        .try_reserve(rows.len())
        .map_err(|_| resource("model name allocation"))?;
    for (index, variable) in vars.iter().enumerate() {
        if var_index
            .insert(variable.name.clone(), index as u32)
            .is_some()
        {
            return Err(invalid("duplicate variable name"));
        }
    }
    for (index, row) in rows.iter().enumerate() {
        if row_index.insert(row.name.clone(), index as u32).is_some() {
            return Err(invalid("duplicate row name"));
        }
    }
    Ok((var_index, row_index))
}

impl Model {
    pub fn new(
        name: String,
        vars: Vec<KernelVar>,
        rows: Vec<KernelRow>,
        objective: Expr,
    ) -> Result<Self, Error> {
        check_name(&name)?;
        let mut var_names = HashSet::new();
        var_names
            .try_reserve(vars.len())
            .map_err(|_| resource("model name allocation"))?;
        for variable in &vars {
            check_name(&variable.name)?;
            if !var_names.insert(&variable.name) {
                return Err(invalid("duplicate variable name"));
            }
            for value in [&variable.lower, &variable.upper].into_iter().flatten() {
                check_q(value)?;
            }
        }
        let mut row_names = HashSet::new();
        row_names
            .try_reserve(rows.len())
            .map_err(|_| resource("model row name allocation"))?;
        let mut count = objective.terms.len();
        objective.validate(vars.len())?;
        for row in &rows {
            check_name(&row.name)?;
            if !row_names.insert(&row.name) {
                return Err(invalid("duplicate row name"));
            }
            row.expr.validate(vars.len())?;
            for value in [&row.lower, &row.upper].into_iter().flatten() {
                check_q(value)?;
            }
            count = count
                .checked_add(row.expr.terms.len())
                .ok_or_else(|| resource("model term count overflow"))?;
            if count > MAX_TERMS {
                return Err(resource("model term budget"));
            }
        }
        if vars.len() > MAX_VARS || rows.len() > MAX_ROWS {
            return Err(resource("model dimension budget"));
        }
        let (var_index, row_index) = names(&vars, &rows)?;
        Ok(Self {
            space: crate::space::Space::new(
                name.clone(),
                vars.iter().map(|v| v.name.clone()).collect(),
                None,
            ),
            inner: KernelModel {
                name,
                vars,
                rows,
                objective,
            },
            var_index,
            row_index,
        })
    }

    pub fn from_kernel(inner: KernelModel) -> Result<Self, Error> {
        let (var_index, row_index) = names(&inner.vars, &inner.rows)?;
        Ok(Self {
            space: crate::space::Space::new(
                inner.name.clone(),
                inner.vars.iter().map(|v| v.name.clone()).collect(),
                None,
            ),
            inner,
            var_index,
            row_index,
        })
    }

    pub fn parse(text: &str, format: ModelFormat) -> Result<Self, Error> {
        let inner = match format {
            ModelFormat::Mps => model::parse_mps(text)?,
            ModelFormat::Lp => kernel_core::lp::parse_lp(text)?,
            ModelFormat::Json => {
                return Err(invalid("JSON models are decoded by the Python facade"));
            }
            ModelFormat::Auto | ModelFormat::Mcm => {
                return Err(invalid("MCM input requires bytes"));
            }
        };
        Self::from_kernel(inner)
    }

    pub fn parse_bytes(bytes: &[u8], format: ModelFormat) -> Result<Self, Error> {
        match format {
            ModelFormat::Mcm | ModelFormat::Auto => {
                let inner = kernel_core::codec::decode_model(bytes)?;
                Self::from_kernel(inner)
            }
            _ => {
                let text = std::str::from_utf8(bytes).map_err(|_| invalid("model is not UTF-8"))?;
                Self::parse(text, format)
            }
        }
    }

    pub fn index(&self, identifier: &Identifier, row: bool) -> Result<u32, Error> {
        let (table, length) = if row {
            (&self.row_index, self.inner.rows.len())
        } else {
            (&self.var_index, self.inner.vars.len())
        };
        let index = match identifier {
            Identifier::Name(name) => *table.get(name).ok_or_else(|| {
                format!("unknown {} {name:?}", if row { "row" } else { "variable" })
            })?,
            Identifier::Index(index) => *index,
        };
        if index as usize >= length {
            return Err(Error::Invalid(format!(
                "{} index {index} outside model",
                if row { "row" } else { "variable" }
            )));
        }
        Ok(index)
    }

    pub fn var(&self, identifier: &Identifier) -> Result<Expr, Error> {
        Ok(Expr::var(self.index(identifier, false)?))
    }

    pub fn row(&self, identifier: &Identifier) -> Result<KernelRow, Error> {
        let index = self.index(identifier, true)? as usize;
        self.inner
            .rows
            .get(index)
            .cloned()
            .ok_or_else(|| invalid("row index outside model"))
    }

    pub fn fact(&self, kind: &str, identifier: &Identifier) -> Result<(Kind, Expr), Error> {
        let row = kind.starts_with("Row");
        let index = self.index(identifier, row)?;
        if kind.starts_with("Var") {
            let variable = self
                .inner
                .vars
                .get(index as usize)
                .ok_or_else(|| invalid("variable index outside model"))?;
            let expression = Expr::var(index);
            if kind == "VarInt" {
                if !variable.integer {
                    return Err(Error::Invalid(format!(
                        "variable {:?} has no integer declaration",
                        variable.name
                    )));
                }
                return Ok((Kind::Int, expression));
            }
            if kind == "VarLower" {
                if let Some(bound) = &variable.lower {
                    let mut out = Expr::var(index).scaled(&(-Q::one()))?;
                    out.constant += bound;
                    out.canonicalize()?;
                    return Ok((Kind::Le, out));
                }
            }
            if kind == "VarUpper" {
                if let Some(bound) = &variable.upper {
                    let mut out = Expr::var(index);
                    out.constant = -bound.clone();
                    out.canonicalize()?;
                    return Ok((Kind::Le, out));
                }
            }
        } else if kind.starts_with("Row") {
            let row = self.row(identifier)?;
            if kind == "RowEq" {
                if let (Some(lower), Some(upper)) = (&row.lower, &row.upper) {
                    if lower == upper {
                        let mut out = row.expr.clone();
                        out.constant -= lower;
                        out.canonicalize()?;
                        return Ok((Kind::Eq, out));
                    }
                }
            }
            if kind == "RowLower" {
                if let Some(bound) = &row.lower {
                    let mut out = expr::neg(&row.expr)?;
                    out.constant += bound;
                    out.canonicalize()?;
                    return Ok((Kind::Le, out));
                }
            }
            if kind == "RowUpper" {
                if let Some(bound) = &row.upper {
                    let mut out = row.expr.clone();
                    out.constant -= bound;
                    out.canonicalize()?;
                    return Ok((Kind::Le, out));
                }
            }
        }
        Err(Error::Invalid(format!(
            "unavailable fact {kind}({})",
            match identifier {
                Identifier::Index(i) => i.to_string(),
                Identifier::Name(n) => n.clone(),
            }
        )))
    }

    pub fn reference(&self, kind: &str, identifier: &Identifier) -> Result<Ref, Error> {
        self.fact(kind, identifier)?;
        let row = kind.starts_with("Row");
        let index = self.index(identifier, row)?;
        Ok(match kind {
            "VarLower" => Ref::VarLower(index),
            "VarUpper" => Ref::VarUpper(index),
            "VarInt" => Ref::VarInt(index),
            "RowLower" => Ref::RowLower(index),
            "RowUpper" => Ref::RowUpper(index),
            "RowEq" => Ref::RowEq(index),
            _ => return Err(invalid("unknown model fact")),
        })
    }

    pub fn validate(&self) -> Result<(), Error> {
        self.inner.validate().map_err(Error::from)
    }

    pub fn to_mcm(&self) -> Result<Vec<u8>, Error> {
        kernel_core::codec::encode_model(&self.inner).map_err(Error::from)
    }

    pub fn support(&self, identifier: &Identifier) -> Result<Vec<u32>, Error> {
        let row = self.row(identifier)?;
        Ok(row
            .expr
            .terms
            .iter()
            .map(|(index, _)| *index)
            .collect::<Vec<_>>())
    }

    pub fn row_activity(&self, identifier: &Identifier) -> Result<(Option<Q>, Option<Q>), Error> {
        let row = self.row(identifier)?;
        let mut lower = Some(row.expr.constant.clone());
        let mut upper = Some(row.expr.constant);
        for (index, coefficient) in &row.expr.terms {
            let variable = &self.inner.vars[*index as usize];
            let (lo, hi) = if coefficient.is_positive() {
                (variable.lower.as_ref(), variable.upper.as_ref())
            } else {
                (variable.upper.as_ref(), variable.lower.as_ref())
            };
            lower = match (lower, lo) {
                (Some(value), Some(bound)) => Some(value + coefficient * bound),
                _ => None,
            };
            upper = match (upper, hi) {
                (Some(value), Some(bound)) => Some(value + coefficient * bound),
                _ => None,
            };
        }
        Ok((lower, upper))
    }

    pub fn is_binary(&self, identifier: &Identifier) -> Result<bool, Error> {
        let index = self.index(identifier, false)? as usize;
        let variable = self
            .inner
            .vars
            .get(index)
            .ok_or_else(|| invalid("variable index outside model"))?;
        Ok(variable.integer
            && variable.lower.as_ref().is_some_and(|q| q >= &Q::zero())
            && variable
                .upper
                .as_ref()
                .is_some_and(|q| q <= &Q::from_integer(1.into())))
    }

    pub fn column_incidence(&self) -> Vec<Vec<(u32, Q)>> {
        let mut columns = vec![Vec::new(); self.inner.vars.len()];
        for (row_index, row) in self.inner.rows.iter().enumerate() {
            for (variable, coefficient) in &row.expr.terms {
                columns[*variable as usize].push((row_index as u32, coefficient.clone()));
            }
        }
        columns
    }

    pub fn stats(&self) -> serde_json::Value {
        let integers = self.inner.vars.iter().filter(|v| v.integer).count();
        let nonzeros = self
            .inner
            .rows
            .iter()
            .map(|r| r.expr.terms.len())
            .sum::<usize>();
        let equalities = self
            .inner
            .rows
            .iter()
            .filter(|r| r.lower.is_some() && r.lower == r.upper)
            .count();
        let ranged = self
            .inner
            .rows
            .iter()
            .filter(|r| r.lower.is_some() && r.upper.is_some() && r.lower != r.upper)
            .count();
        serde_json::json!({
            "variables": self.inner.vars.len(),
            "rows": self.inner.rows.len(),
            "integers": integers,
            "nonzeros": nonzeros,
            "objective_nonzeros": self.inner.objective.terms.len(),
            "equalities": equalities,
            "ranged_rows": ranged,
        })
    }

    pub fn check_point(
        &self,
        values: &[Q],
        integers: bool,
    ) -> Result<Vec<serde_json::Value>, Error> {
        if values.len() != self.inner.vars.len() {
            return Err(invalid("a point must specify every coordinate"));
        }
        let mut violations = Vec::new();
        for (index, (variable, value)) in self.inner.vars.iter().zip(values).enumerate() {
            if let Some(bound) = &variable.lower {
                if value < bound {
                    violations.push(serde_json::json!({"kind":"VarLower","index":index,"name":variable.name,"value":value.to_string(),"bound":bound.to_string()}));
                }
            }
            if let Some(bound) = &variable.upper {
                if value > bound {
                    violations.push(serde_json::json!({"kind":"VarUpper","index":index,"name":variable.name,"value":value.to_string(),"bound":bound.to_string()}));
                }
            }
            if integers && variable.integer && !value.is_integer() {
                violations.push(serde_json::json!({"kind":"VarInt","index":index,"name":variable.name,"value":value.to_string()}));
            }
        }
        let coordinates = values.iter().cloned().map(Some).collect::<Vec<_>>();
        for (index, row) in self.inner.rows.iter().enumerate() {
            let value = expr::evaluate(&row.expr, &coordinates)?;
            if let Some(bound) = &row.lower {
                if value < *bound {
                    violations.push(serde_json::json!({"kind":"RowLower","index":index,"name":row.name,"value":value.to_string(),"bound":bound.to_string()}));
                }
            }
            if let Some(bound) = &row.upper {
                if value > *bound {
                    violations.push(serde_json::json!({"kind":"RowUpper","index":index,"name":row.name,"value":value.to_string(),"bound":bound.to_string()}));
                }
            }
        }
        Ok(violations)
    }

    pub fn same_formulation(&self, other: &Model) -> bool {
        if self.inner.vars.len() != other.inner.vars.len()
            || self.inner.rows.len() != other.inner.rows.len()
        {
            return false;
        }
        let left: HashMap<_, _> = self
            .inner
            .vars
            .iter()
            .map(|v| (v.name.as_str(), v))
            .collect();
        let right: HashMap<_, _> = other
            .inner
            .vars
            .iter()
            .map(|v| (v.name.as_str(), v))
            .collect();
        if left != right {
            return false;
        }
        let terms = |expression: &Expr, model: &Model| {
            expression
                .terms
                .iter()
                .map(|(index, coefficient)| {
                    (
                        model.inner.vars[*index as usize].name.clone(),
                        coefficient.clone(),
                    )
                })
                .collect::<HashMap<_, _>>()
        };
        if self.inner.objective.constant != other.inner.objective.constant
            || terms(&self.inner.objective, self) != terms(&other.inner.objective, other)
        {
            return false;
        }
        for row in &self.inner.rows {
            let other_row = match other.row_index.get(&row.name) {
                Some(index) => &other.inner.rows[*index as usize],
                None => return false,
            };
            if terms(&row.expr, self) != terms(&other_row.expr, other) {
                return false;
            }
            for (left, right) in [
                (&row.lower, &other_row.lower),
                (&row.upper, &other_row.upper),
            ] {
                let a = left.as_ref().map(|q| q - &row.expr.constant);
                let b = right.as_ref().map(|q| q - &other_row.expr.constant);
                if a != b {
                    return false;
                }
            }
        }
        true
    }

    pub fn renamed(&self, name: String) -> Result<Self, Error> {
        Self::new(
            name,
            self.inner.vars.clone(),
            self.inner.rows.clone(),
            self.inner.objective.clone(),
        )
    }

    pub fn delete_rows(&self, indices: &HashSet<u32>) -> Result<Self, Error> {
        let rows = self
            .inner
            .rows
            .iter()
            .enumerate()
            .filter(|(index, _)| !indices.contains(&(*index as u32)))
            .map(|(_, row)| row.clone())
            .collect();
        Self::new(
            self.inner.name.clone(),
            self.inner.vars.clone(),
            rows,
            self.inner.objective.clone(),
        )
    }

    pub fn add_rows(&self, rows: Vec<KernelRow>) -> Result<Self, Error> {
        let mut all = self.inner.rows.clone();
        all.extend(rows);
        Self::new(
            self.inner.name.clone(),
            self.inner.vars.clone(),
            all,
            self.inner.objective.clone(),
        )
    }

    pub fn replace_row(&self, index: u32, row: KernelRow) -> Result<Self, Error> {
        let mut rows = self.inner.rows.clone();
        let slot = rows
            .get_mut(index as usize)
            .ok_or_else(|| invalid("row index outside model"))?;
        *slot = row;
        Self::new(
            self.inner.name.clone(),
            self.inner.vars.clone(),
            rows,
            self.inner.objective.clone(),
        )
    }

    pub fn add_variable(&self, variable: KernelVar) -> Result<Self, Error> {
        let mut vars = self.inner.vars.clone();
        vars.push(variable);
        Self::new(
            self.inner.name.clone(),
            vars,
            self.inner.rows.clone(),
            self.inner.objective.clone(),
        )
    }

    pub fn with_objective(&self, objective: Expr) -> Result<Self, Error> {
        Self::new(
            self.inner.name.clone(),
            self.inner.vars.clone(),
            self.inner.rows.clone(),
            objective,
        )
    }

    pub fn with_bounds(
        &self,
        index: u32,
        lower: Option<Option<Q>>,
        upper: Option<Option<Q>>,
    ) -> Result<Self, Error> {
        let mut vars = self.inner.vars.clone();
        let variable = vars
            .get_mut(index as usize)
            .ok_or_else(|| invalid("variable index outside model"))?;
        if let Some(value) = lower {
            variable.lower = value;
        }
        if let Some(value) = upper {
            variable.upper = value;
        }
        Self::new(
            self.inner.name.clone(),
            vars,
            self.inner.rows.clone(),
            self.inner.objective.clone(),
        )
    }

    pub fn with_integrality(&self, indices: &[u32], integer: bool) -> Result<Self, Error> {
        let mut vars = self.inner.vars.clone();
        for index in indices {
            vars.get_mut(*index as usize)
                .ok_or_else(|| invalid("variable index outside model"))?
                .integer = integer;
        }
        Self::new(
            self.inner.name.clone(),
            vars,
            self.inner.rows.clone(),
            self.inner.objective.clone(),
        )
    }

    pub fn substitute(
        &self,
        replacements: &HashMap<u32, Expr>,
        remove: bool,
        dropped: &HashSet<u32>,
        preserve_bounds: bool,
    ) -> Result<(Self, Vec<(String, KernelRow)>), Error> {
        let removed: HashSet<u32> = if remove {
            replacements.keys().copied().collect()
        } else {
            HashSet::new()
        };
        for expression in replacements.values() {
            for (index, _) in &expression.terms {
                if removed.contains(index) {
                    return Err(invalid(
                        "an elimination map must only reference retained variables",
                    ));
                }
                if *index as usize >= self.inner.vars.len() {
                    return Err(invalid(
                        "substitution references a coordinate outside this model",
                    ));
                }
            }
        }
        let keep: Vec<u32> = (0..self.inner.vars.len() as u32)
            .filter(|index| !removed.contains(index))
            .collect();
        let renumber: HashMap<u32, Expr> = keep
            .iter()
            .enumerate()
            .map(|(new, old)| (*old, Expr::var(new as u32)))
            .collect();
        let mut mapping: Vec<Option<Expr>> = vec![None; self.inner.vars.len()];
        for old in 0..self.inner.vars.len() as u32 {
            mapping[old as usize] = Some(if let Some(expression) = replacements.get(&old) {
                expr::canonical(
                    expression.constant.clone(),
                    expression
                        .terms
                        .iter()
                        .map(|(i, q)| (renumber[i].terms[0].0, q.clone())),
                )?
            } else {
                renumber
                    .get(&old)
                    .cloned()
                    .unwrap_or_else(|| Expr::var(old))
            });
        }
        let rows = self
            .inner
            .rows
            .iter()
            .enumerate()
            .filter(|(index, _)| !dropped.contains(&(*index as u32)))
            .map(|(_, row)| {
                let mut out = row.clone();
                out.expr = substitute_expr(&row.expr, &mapping)?;
                Ok(out)
            })
            .collect::<Result<Vec<_>, Error>>()?;
        let objective = substitute_expr(&self.inner.objective, &mapping)?;
        let mut result = Self::new(
            self.inner.name.clone(),
            keep.iter()
                .map(|index| self.inner.vars[*index as usize].clone())
                .collect(),
            rows,
            objective,
        )?;
        let mut added = Vec::new();
        let mut names: HashSet<String> = result.inner.rows.iter().map(|r| r.name.clone()).collect();
        for index in 0..self.inner.vars.len() as u32 {
            if !removed.contains(&index) {
                continue;
            }
            if let Some((_, mut row)) = added_bound(self, index, preserve_bounds, remove, &mapping)?
            {
                let base = row.name.clone();
                let mut suffix = 1;
                while names.contains(&row.name) {
                    row.name = format!("{base}_{suffix}");
                    suffix += 1;
                }
                names.insert(row.name.clone());
                result.inner.rows.push(row.clone());
                added.push((self.inner.vars[index as usize].name.clone(), row));
            }
        }
        result = Self::from_kernel(result.inner)?;
        result.validate()?;
        Ok((result, added))
    }
}

fn added_bound(
    source: &Model,
    index: u32,
    preserve_bounds: bool,
    remove: bool,
    mapping: &[Option<Expr>],
) -> Result<Option<(String, KernelRow)>, Error> {
    if !remove || !preserve_bounds {
        return Ok(None);
    }
    let variable = &source.inner.vars[index as usize];
    if variable.lower.is_none() && variable.upper.is_none() {
        return Ok(None);
    }
    let mut base = format!("__bound_{}", variable.name);
    if base.len() > 1000 {
        base.truncate(1000);
    }
    let expression = mapping
        .get(index as usize)
        .and_then(|item| item.clone())
        .ok_or_else(|| invalid("missing substitution mapping"))?;
    Ok(Some((
        variable.name.clone(),
        KernelRow {
            name: base,
            expr: expression,
            lower: variable.lower.clone(),
            upper: variable.upper.clone(),
        },
    )))
}

fn substitute_expr(value: &Expr, mapping: &[Option<Expr>]) -> Result<Expr, Error> {
    let replacements = mapping;
    expr::substitute(value, replacements)
}

pub fn parse_identifier_index(index: u32, length: usize, row: bool) -> Result<u32, Error> {
    if index as usize >= length {
        return Err(Error::Invalid(format!(
            "{} index {index} outside model",
            if row { "row" } else { "variable" }
        )));
    }
    Ok(index)
}

pub fn parse_value(text: &str) -> Result<Q, Error> {
    parse_q(text).map_err(Error::from)
}

pub fn check_term_budget(expressions: &[&Expr]) -> Result<(), Error> {
    check_terms(expressions)
}

pub fn kernel_name_ok(name: &str) -> bool {
    check_name(name).is_ok()
}

pub fn var_from_parts(
    name: String,
    integer: bool,
    lower: Option<Q>,
    upper: Option<Q>,
) -> Result<KernelVar, Error> {
    check_name(&name)?;
    for value in [&lower, &upper].into_iter().flatten() {
        check_q(value)?;
    }
    Ok(KernelVar {
        name,
        integer,
        lower,
        upper,
    })
}

pub fn row_from_parts(
    name: String,
    expr: Expr,
    lower: Option<Q>,
    upper: Option<Q>,
    nvars: usize,
) -> Result<KernelRow, Error> {
    check_name(&name)?;
    expr.validate(nvars)?;
    for value in [&lower, &upper].into_iter().flatten() {
        check_q(value)?;
    }
    Ok(KernelRow {
        name,
        expr,
        lower,
        upper,
    })
}

/// Exact free MPS export; all model-sized work stays native.
pub fn mps(model: &Model, rational_literals: bool) -> Result<String, Error> {
    use num_integer::Integer;
    fn decimal(q: &Q) -> Result<String, Error> {
        let mut d = q.denom().clone();
        let mut two = 0u32;
        let mut five = 0u32;
        while d.is_even() {
            d /= 2;
            two += 1;
        }
        while (&d % 5u32).is_zero() {
            d /= 5;
            five += 1;
        }
        if !d.is_one() {
            return Err(Error::Invalid(format!(
                "{q} has no finite exact decimal; use MCM or rational_literals=True"
            )));
        }
        let n = two.max(five);
        let v = q.numer().abs()
            * num_bigint::BigInt::from(2).pow(n - two)
            * num_bigint::BigInt::from(5).pow(n - five);
        let mut s = format!("{:0>width$}", v.to_string(), width = n as usize + 1);
        if n > 0 {
            s.insert(s.len() - n as usize, '.');
            s = s.trim_end_matches('0').trim_end_matches('.').into();
        }
        if q.is_negative() {
            s.insert(0, '-');
        }
        Ok(s)
    }
    let number = |q: &Q| {
        if rational_literals {
            Ok(q.to_string())
        } else {
            decimal(q)
        }
    };
    let m = &model.inner;
    for name in std::iter::once(&m.name)
        .chain(m.vars.iter().map(|v| &v.name))
        .chain(m.rows.iter().map(|r| &r.name))
    {
        if name.chars().any(char::is_whitespace) || name.starts_with('$') {
            return Err(invalid(
                "MPS names must be whitespace-free and cannot start with '$'",
            ));
        }
    }
    let mut objective = "__objective".to_string();
    while model.row_index.contains_key(&objective) {
        objective.push('_');
    }
    let mut lines = vec![
        format!("NAME {}", m.name),
        "ROWS".into(),
        format!(" N {objective}"),
    ];
    let mut rhs = vec![];
    let mut ranges = vec![];
    for r in &m.rows {
        let lo = r.lower.as_ref().map(|q| q - &r.expr.constant);
        let hi = r.upper.as_ref().map(|q| q - &r.expr.constant);
        let (sense, bound) = match (&lo, &hi) {
            (None, None) => return Err(invalid("unbounded row has no MPS encoding")),
            (Some(l), Some(h)) if l > h => {
                return Err(invalid("contradictory row has no MPS range encoding"));
            }
            (Some(l), Some(h)) if l == h => ("E", l),
            (l, Some(h)) => {
                if let Some(l) = l {
                    ranges.push(format!(" rng {} {}", r.name, number(&(h - l))?));
                }
                ("L", h)
            }
            (Some(l), None) => ("G", l),
        };
        lines.push(format!(" {sense} {}", r.name));
        rhs.push(format!(" rhs {} {}", r.name, number(bound)?));
    }
    lines.push("COLUMNS".into());
    let columns = model.column_incidence();
    let costs: HashMap<_, _> = m.objective.terms.iter().map(|(i, q)| (*i, q)).collect();
    let zero = Q::zero();
    let mut integer = false;
    let mut marker = 0;
    for (i, v) in m.vars.iter().enumerate() {
        if v.integer != integer {
            lines.push(format!(
                " M{marker} 'MARKER' '{}'",
                if v.integer { "INTORG" } else { "INTEND" }
            ));
            marker += 1;
            integer = v.integer;
        }
        lines.push(format!(
            " {} {objective} {}",
            v.name,
            number(costs.get(&(i as u32)).copied().unwrap_or(&zero))?
        ));
        for (r, q) in &columns[i] {
            lines.push(format!(
                " {} {} {}",
                v.name,
                m.rows[*r as usize].name,
                number(q)?
            ));
        }
    }
    if integer {
        lines.push(format!(" M{marker} 'MARKER' 'INTEND'"));
    }
    lines.push("RHS".into());
    lines.push(format!(
        " rhs {objective} {}",
        number(&(-m.objective.constant.clone()))?
    ));
    lines.extend(rhs);
    if !ranges.is_empty() {
        lines.push("RANGES".into());
        lines.extend(ranges);
    }
    lines.push("BOUNDS".into());
    for v in &m.vars {
        match (&v.lower, &v.upper) {
            (None, None) => lines.push(format!(" FR bnd {}", v.name)),
            (Some(l), Some(h)) if l == h => {
                lines.push(format!(" FX bnd {} {}", v.name, number(l)?))
            }
            (lo, hi) => {
                lines.push(match lo {
                    Some(l) => format!(" LO bnd {} {}", v.name, number(l)?),
                    None => format!(" MI bnd {}", v.name),
                });
                if let Some(h) = hi {
                    lines.push(format!(" UP bnd {} {}", v.name, number(h)?));
                }
            }
        }
    }
    lines.push("ENDATA".into());
    Ok(lines.join("\n") + "\n")
}
