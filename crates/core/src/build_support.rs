//! Shared checked mechanics for trusted model builders.
//!
//! These helpers do not establish a theorem or discharge a premise. Callers own
//! the rule-specific dimensions, preflight charges, validation order and lemma.
//! Prefix copying preserves every old field and does not charge work a second
//! time. Name allocation charges each attempted suffix, including collisions.
use crate::model::{check_q, Expr, Model, Row, Var};
use num_traits::Zero;
use std::collections::HashSet;
use std::fmt::Write;

#[derive(Clone, Copy)]
pub(crate) struct Support {
    label: &'static str,
}

impl Support {
    pub(crate) const fn new(label: &'static str) -> Self {
        Self { label }
    }

    pub(crate) fn resource(self, message: &str) -> String {
        format!("RESOURCE_LIMIT {}: {message}", self.label)
    }

    pub(crate) fn add(self, a: usize, b: usize) -> Result<usize, String> {
        a.checked_add(b)
            .ok_or_else(|| self.resource("count addition"))
    }

    pub(crate) fn mul(self, a: usize, b: usize) -> Result<usize, String> {
        a.checked_mul(b)
            .ok_or_else(|| self.resource("count multiplication"))
    }

    pub(crate) fn reserved<T>(self, n: usize) -> Result<Vec<T>, String> {
        let mut result = Vec::new();
        result
            .try_reserve_exact(n)
            .map_err(|_| self.resource("allocation"))?;
        Ok(result)
    }

    pub(crate) fn string(self, s: &str) -> Result<String, String> {
        let mut result = String::new();
        result
            .try_reserve_exact(s.len())
            .map_err(|_| self.resource("string allocation"))?;
        result.push_str(s);
        Ok(result)
    }

    pub(crate) fn copy_expr(self, expression: &Expr) -> Result<Expr, String> {
        let mut terms = self.reserved(expression.terms.len())?;
        terms.extend(expression.terms.iter().cloned());
        Ok(Expr {
            constant: expression.constant.clone(),
            terms,
        })
    }

    /// Counts the exact old-model scan used by the builders' preflight policies.
    /// Dimension/term ceilings and how many scans to charge remain with callers.
    pub(crate) fn model_size(self, model: &Model) -> Result<(usize, usize), String> {
        let mut terms = model.objective.terms.len();
        let mut work = self.add(model.name.len(), self.add(terms, 1)?)?;
        for var in &model.vars {
            work = self.add(work, self.add(var.name.len(), 3)?)?;
        }
        for row in &model.rows {
            terms = self.add(terms, row.expr.terms.len())?;
            work = self.add(
                work,
                self.add(row.name.len(), self.add(row.expr.terms.len(), 4)?)?,
            )?;
        }
        Ok((terms, work))
    }

    /// Preserve the full model prefix, with preflighted room for appended data.
    pub(crate) fn copy_prefix(
        self,
        input: &Model,
        vars: usize,
        rows: usize,
    ) -> Result<Model, String> {
        if vars < input.vars.len() || rows < input.rows.len() {
            return Err(self.resource("prefix capacity"));
        }
        let mut model = Model {
            name: self.string(&input.name)?,
            vars: self.reserved(vars)?,
            rows: self.reserved(rows)?,
            objective: self.copy_expr(&input.objective)?,
        };
        for var in &input.vars {
            model.vars.push(Var {
                name: self.string(&var.name)?,
                integer: var.integer,
                lower: var.lower.clone(),
                upper: var.upper.clone(),
            });
        }
        for row in &input.rows {
            model.rows.push(Row {
                name: self.string(&row.name)?,
                expr: self.copy_expr(&row.expr)?,
                lower: row.lower.clone(),
                upper: row.upper.clone(),
            });
        }
        Ok(model)
    }

    /// Exact sorted sparse subtraction; operands must already be canonical.
    /// Every newly formed scalar is checked before cancellation can hide it.
    pub(crate) fn difference(self, a: &Expr, b: &Expr) -> Result<Expr, String> {
        let constant = &a.constant - &b.constant;
        check_q(&constant)?;
        let mut terms = self.reserved(self.add(a.terms.len(), b.terms.len())?)?;
        let (mut i, mut j) = (0, 0);
        while i < a.terms.len() || j < b.terms.len() {
            let term = match (a.terms.get(i), b.terms.get(j)) {
                (Some((ai, aq)), Some((bi, bq))) if ai == bi => {
                    i += 1;
                    j += 1;
                    let q = aq - bq;
                    check_q(&q)?;
                    (*ai, q)
                }
                (Some((ai, aq)), Some((bi, _))) if ai < bi => {
                    i += 1;
                    (*ai, aq.clone())
                }
                (Some(_), Some((bi, bq))) => {
                    j += 1;
                    (*bi, -bq)
                }
                (Some((ai, aq)), None) => {
                    i += 1;
                    (*ai, aq.clone())
                }
                (None, Some((bi, bq))) => {
                    j += 1;
                    (*bi, -bq)
                }
                (None, None) => break,
            };
            if !term.1.is_zero() {
                terms.push(term);
            }
        }
        Ok(Expr { constant, terms })
    }

    pub(crate) fn charge(
        self,
        used: &mut u64,
        limit: u64,
        n: usize,
        message: &str,
    ) -> Result<(), String> {
        *used = used
            .checked_add(u64::try_from(n).map_err(|_| self.resource("work width"))?)
            .ok_or_else(|| self.resource("work overflow"))?;
        if *used > limit {
            return Err(self.resource(message));
        }
        Ok(())
    }

    pub(crate) fn name(self, prefix: &str, index: usize) -> Result<String, String> {
        let mut result = String::new();
        result
            .try_reserve_exact(self.add(prefix.len(), 32)?)
            .map_err(|_| self.resource("name allocation"))?;
        write!(&mut result, "{prefix}{index}").map_err(|_| self.resource("name formatting"))?;
        Ok(result)
    }

    pub(crate) fn names<'a>(
        self,
        names: impl Iterator<Item = &'a str>,
        count: usize,
        prefix: &'static str,
    ) -> Result<Names<'a>, String> {
        let mut old = HashSet::new();
        old.try_reserve(count)
            .map_err(|_| self.resource("name index allocation"))?;
        old.extend(names);
        Ok(Names {
            support: self,
            old,
            next: count,
            prefix,
        })
    }
}

pub(crate) struct Budget {
    support: Support,
    used: u64,
    limit: u64,
}

impl Budget {
    pub(crate) fn new(support: Support, limit: u64) -> Self {
        Self {
            support,
            used: 0,
            limit,
        }
    }
    pub(crate) fn used(&self) -> u64 {
        self.used
    }
    pub(crate) fn charge(&mut self, n: usize) -> Result<(), String> {
        self.support
            .charge(&mut self.used, self.limit, n, "preparation work budget")
    }
    pub(crate) fn sort(&mut self, n: usize) -> Result<(), String> {
        let log = usize::BITS - n.leading_zeros();
        self.charge(self.support.mul(n, log as usize + 1)?)
    }
}

pub(crate) struct Names<'a> {
    support: Support,
    old: HashSet<&'a str>,
    next: usize,
    prefix: &'static str,
}

impl Names<'_> {
    pub(crate) fn fresh(&mut self, budget: &mut Budget) -> Result<String, String> {
        self.fresh_with(|n| budget.charge(n))
    }

    /// The callback lets point checks retain their existing shared statistics.
    pub(crate) fn fresh_with(
        &mut self,
        mut charge: impl FnMut(usize) -> Result<(), String>,
    ) -> Result<String, String> {
        loop {
            charge(1)?;
            let candidate = self.support.name(self.prefix, self.next)?;
            // Monotone checked suffixes also prevent generated/generated clashes.
            self.next = self.support.add(self.next, 1)?;
            if !self.old.contains(candidate.as_str()) {
                return Ok(candidate);
            }
        }
    }
}
