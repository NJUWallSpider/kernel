//! Preparation of a bounded common-source subflow extension (V10 proposal).
//!
//! This module does NOT prove its returned premises. The proof engine must check
//! every premise against the original input and current proof scope before the
//! returned model can be used. See docs/FLOW_PRUNE_DESIGN.md for the construction.
use crate::model::{check_q, Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::proof::{FlowWitness, Kind, Ref};
use crate::verify::Limits;
use num_traits::{One, Signed, Zero};
use serde::Serialize;
use std::collections::HashSet;

fn invalid(s: &str) -> String {
    format!("INVALID flow prune: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT flow prune: {s}")
}
fn add(a: usize, b: usize) -> Result<usize, String> {
    a.checked_add(b).ok_or_else(|| resource("count addition"))
}
fn mul(a: usize, b: usize) -> Result<usize, String> {
    a.checked_mul(b)
        .ok_or_else(|| resource("count multiplication"))
}
fn reserved<T>(n: usize) -> Result<Vec<T>, String> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| resource("allocation"))?;
    Ok(v)
}
fn string(s: &str) -> Result<String, String> {
    let mut out = String::new();
    out.try_reserve_exact(s.len())
        .map_err(|_| resource("string allocation"))?;
    out.push_str(s);
    Ok(out)
}
fn copy_expr(e: &Expr) -> Result<Expr, String> {
    let mut terms = reserved(e.terms.len())?;
    terms.extend(e.terms.iter().cloned());
    Ok(Expr {
        constant: e.constant.clone(),
        terms,
    })
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct PruneStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct PrunePremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// Conditional construction only: callers must establish every premise first.
#[derive(Debug)]
pub struct UncheckedPruneExtension {
    pub model: Model,
    pub premises: Vec<PrunePremise>,
    pub statistics: PruneStatistics,
}
struct Budget {
    used: u64,
    limit: u64,
}
impl Budget {
    fn charge(&mut self, n: usize) -> Result<(), String> {
        self.used = self
            .used
            .checked_add(u64::try_from(n).map_err(|_| resource("work width"))?)
            .ok_or_else(|| resource("work overflow"))?;
        if self.used > self.limit {
            return Err(resource("preparation work budget"));
        }
        Ok(())
    }
    fn sort(&mut self, n: usize) -> Result<(), String> {
        let log = usize::BITS - n.leading_zeros();
        self.charge(mul(n, log as usize + 1)?)
    }
}

struct Names<'a> {
    old: HashSet<&'a str>,
    next: usize,
    prefix: &'static str,
}
impl<'a> Names<'a> {
    fn new(
        names: impl Iterator<Item = &'a str>,
        count: usize,
        prefix: &'static str,
    ) -> Result<Self, String> {
        let mut old = HashSet::new();
        old.try_reserve(count)
            .map_err(|_| resource("name index allocation"))?;
        old.extend(names);
        Ok(Self {
            old,
            next: count,
            prefix,
        })
    }
    fn fresh(&mut self, budget: &mut Budget) -> Result<String, String> {
        loop {
            budget.charge(1)?;
            let candidate = format!("{}{}", self.prefix, self.next);
            self.next = add(self.next, 1)?;
            if !self.old.contains(candidate.as_str()) {
                return Ok(candidate);
            }
        }
    }
}

/// Prepare bounded expressions, references and a candidate extended model.
/// This is not an acceptance entry point: none of the supplied references are
/// trusted or checked here. The caller must verify every returned premise using
/// the pre-extension input and facts before recursively checking the child body.
pub fn prepare_unchecked_extension(
    input: &Model,
    witness: &FlowWitness,
    limits: &Limits,
) -> Result<UncheckedPruneExtension, String> {
    let mut budget = Budget {
        used: 0,
        limit: limits.work,
    };
    let n = witness.nodes as usize;
    let m = witness.arcs.len();
    if n == 0 || witness.groups.is_empty() {
        return Err(invalid("nonempty node and group sets required"));
    }
    if n > MAX_ROWS
        || m > MAX_VARS
        || witness.groups.len() > MAX_ROWS
        || input.vars.len() > MAX_VARS
        || input.rows.len() > MAX_ROWS
    {
        return Err(resource("dimension limit"));
    }
    budget.charge(add(n, add(m, witness.groups.len())?)?)?;
    let mut nonloops = 0usize;
    for &(tail, head) in &witness.arcs {
        if tail as usize >= n || head as usize >= n {
            return Err(invalid("arc endpoint"));
        }
        if tail != head {
            nonloops = add(nonloops, 1)?;
        }
    }
    let mut old_terms = input.objective.terms.len();
    let mut copy_work = add(input.name.len(), add(input.objective.terms.len(), 1)?)?;
    for var in &input.vars {
        copy_work = add(copy_work, add(var.name.len(), 3)?)?;
    }
    for row in &input.rows {
        old_terms = add(old_terms, row.expr.terms.len())?;
        copy_work = add(
            copy_work,
            add(row.name.len(), add(row.expr.terms.len(), 4)?)?,
        )?;
    }
    if old_terms > MAX_TERMS {
        return Err(resource("input term limit"));
    }
    budget.charge(mul(copy_work, 2)?)?; // Validate and copy the entire input prefix.
    input.validate()?;
    let mut new_vars = 0usize;
    let mut new_rows = 0usize;
    let mut new_terms = 0usize;
    let mut premise_terms = 0usize;
    let mut premises_count = 0usize;
    for group in &witness.groups {
        if group.source as usize >= n || group.commodities.is_empty() {
            return Err(invalid("group source or empty commodity set"));
        }
        if group.commodities.len() > MAX_ROWS {
            return Err(resource("commodity count"));
        }
        if group.flows.len() != m || group.nonnegative.len() != m || group.balances.len() != n {
            return Err(invalid("missing or surplus arc/node premises"));
        }
        let k = group.commodities.len();
        budget.charge(mul(k, 6)?)?;
        for &(sink, ref demand) in &group.commodities {
            if sink as usize >= n {
                return Err(invalid("commodity sink"));
            }
            check_q(demand)?;
            if demand.is_negative() {
                return Err(invalid("negative demand"));
            }
        }
        new_vars = add(new_vars, m)?;
        new_rows = add(new_rows, add(n, m)?)?;
        premises_count = add(premises_count, add(m, n)?)?;
        // Node rows contain two entries per non-loop edge; subflow rows
        // contain one generated coordinate and the old affine flow terms.
        new_terms = add(new_terms, add(mul(nonloops, 2)?, m)?)?;
        for (edge, flow) in group.flows.iter().enumerate() {
            budget.charge(add(flow.terms.len(), 1)?)?;
            flow.validate(input.vars.len())?;
            new_terms = add(new_terms, flow.terms.len())?;
            let factor = if witness.arcs[edge].0 == witness.arcs[edge].1 {
                1
            } else {
                3
            };
            premise_terms = add(premise_terms, mul(flow.terms.len(), factor)?)?;
        }
    }
    let vars = add(input.vars.len(), new_vars)?;
    let rows = add(input.rows.len(), new_rows)?;
    if vars > MAX_VARS || rows > MAX_ROWS || premises_count > MAX_ROWS {
        return Err(resource("expanded dimensions"));
    }
    if add(old_terms, add(new_terms, premise_terms)?)? > MAX_TERMS {
        return Err(resource("combined model and premise terms"));
    }
    // Charge all expanded storage and coefficient work before reserving it.
    // Canonical sorting and collision checks are charged additionally below.
    budget.charge(add(
        mul(add(new_vars, new_rows)?, 32)?,
        add(
            mul(add(new_terms, premise_terms)?, 4)?,
            mul(premises_count, 4)?,
        )?,
    )?)?;

    let mut extended = Model {
        name: string(&input.name)?,
        vars: reserved(vars)?,
        rows: reserved(rows)?,
        objective: copy_expr(&input.objective)?,
    };
    for v in &input.vars {
        extended.vars.push(Var {
            name: string(&v.name)?,
            integer: v.integer,
            lower: v.lower.clone(),
            upper: v.upper.clone(),
        });
    }
    for r in &input.rows {
        extended.rows.push(Row {
            name: string(&r.name)?,
            expr: copy_expr(&r.expr)?,
            lower: r.lower.clone(),
            upper: r.upper.clone(),
        });
    }
    let mut variable_names = Names::new(
        input.vars.iter().map(|v| v.name.as_str()),
        input.vars.len(),
        "$rpx_prune_var_",
    )?;
    let mut row_names = Names::new(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_prune_row_",
    )?;
    let mut premises = reserved(premises_count)?;
    let mut actual_generated_terms = 0usize;
    for group in &witness.groups {
        let start = extended.vars.len();
        let mut bound = Q::zero();
        let mut rhs = reserved(n)?;
        rhs.resize(n, Q::zero());
        for &(sink, ref demand) in &group.commodities {
            bound += demand;
            check_q(&bound)?;
            if sink != group.source {
                rhs[group.source as usize] += demand;
                check_q(&rhs[group.source as usize])?;
                rhs[sink as usize] -= demand;
                check_q(&rhs[sink as usize])?;
            }
        }
        // Pre-count sparse divergence entries, so building one wide row never
        // repeatedly merges and copies its accumulated sparse expression.
        let mut sizes = reserved(n)?;
        sizes.resize(n, 0usize);
        for (&(tail, head), flow) in witness.arcs.iter().zip(&group.flows) {
            if tail != head {
                sizes[tail as usize] = add(sizes[tail as usize], flow.terms.len())?;
                sizes[head as usize] = add(sizes[head as usize], flow.terms.len())?;
            }
        }
        let mut divergence = reserved(n)?;
        for size in sizes {
            budget.sort(size)?;
            divergence.push(Expr {
                constant: Q::zero(),
                terms: reserved(size)?,
            });
        }
        for &(sink, ref demand) in &group.commodities {
            if sink != group.source {
                let s = group.source as usize;
                divergence[s].constant -= demand;
                check_q(&divergence[s].constant)?;
                divergence[sink as usize].constant += demand;
                check_q(&divergence[sink as usize].constant)?;
            }
        }
        for (edge, (&(tail, head), flow)) in witness.arcs.iter().zip(&group.flows).enumerate() {
            premises.push(PrunePremise {
                kind: Kind::Le,
                expression: flow.scaled(&(-Q::one()))?,
                reference: group.nonnegative[edge].clone(),
            });
            if tail != head {
                for (node, positive) in [(tail, true), (head, false)] {
                    let d = &mut divergence[node as usize];
                    if positive {
                        d.constant += &flow.constant;
                    } else {
                        d.constant -= &flow.constant;
                    }
                    check_q(&d.constant)?;
                    d.terms.extend(
                        flow.terms
                            .iter()
                            .map(|(id, c)| (*id, if positive { c.clone() } else { -c })),
                    );
                }
            }
        }
        for (node, mut expression) in divergence.into_iter().enumerate() {
            expression.canonicalize()?;
            premises.push(PrunePremise {
                kind: Kind::Eq,
                expression,
                reference: group.balances[node].clone(),
            });
        }
        for _ in 0..m {
            extended.vars.push(Var {
                name: variable_names.fresh(&mut budget)?,
                integer: false,
                lower: Some(Q::zero()),
                upper: Some(bound.clone()),
            });
        }

        // Precompute incidence once, including explicit cancellation of loops.
        let mut incident_sizes = reserved(n)?;
        incident_sizes.resize(n, 0usize);
        for &(tail, head) in &witness.arcs {
            if tail != head {
                incident_sizes[tail as usize] += 1;
                incident_sizes[head as usize] += 1;
            }
        }
        let mut incident = reserved(n)?;
        for size in incident_sizes {
            incident.push(reserved(size)?);
        }
        for (edge, &(tail, head)) in witness.arcs.iter().enumerate() {
            if tail != head {
                incident[tail as usize].push((edge, true));
                incident[head as usize].push((edge, false));
            }
        }
        for (node, incidence) in incident.iter().enumerate() {
            let mut terms = reserved(incidence.len())?;
            for &(edge, positive) in incidence {
                let id = add(start, edge)?;
                terms.push((
                    u32::try_from(id).map_err(|_| resource("variable index width"))?,
                    if positive { Q::one() } else { -Q::one() },
                ));
            }
            actual_generated_terms = add(actual_generated_terms, terms.len())?;
            extended.rows.push(Row {
                name: row_names.fresh(&mut budget)?,
                expr: Expr { constant: Q::zero(), terms },
                lower: Some(rhs[node].clone()),
                upper: Some(rhs[node].clone()),
            });
        }
        for (edge, flow) in group.flows.iter().enumerate() {
            let mut terms = reserved(add(flow.terms.len(), 1)?)?;
            terms.extend(flow.terms.iter().map(|(id, c)| (*id, -c)));
            let id = add(start, edge)?;
            terms.push((
                u32::try_from(id).map_err(|_| resource("variable index width"))?,
                Q::one(),
            ));
            actual_generated_terms = add(actual_generated_terms, terms.len())?;
            extended.rows.push(Row {
                name: row_names.fresh(&mut budget)?,
                expr: Expr {
                    constant: -&flow.constant,
                    terms,
                },
                lower: None,
                upper: Some(Q::zero()),
            });
        }
    }
    // All generated scalar operations were checked, while these final structural
    // checks independently assert canonical ordering and complete dimensions.
    extended.validate()?;
    if extended.vars.len() != vars
        || extended.rows.len() != rows
        || premises.len() != premises_count
        || actual_generated_terms != new_terms
    {
        return Err(invalid("internal extension layout mismatch"));
    }
    Ok(UncheckedPruneExtension {
        model: extended,
        premises,
        statistics: PruneStatistics {
            work: budget.used,
            generated_variables: new_vars as u64,
            generated_rows: new_rows as u64,
            generated_terms: actual_generated_terms as u64,
        },
    })
}
