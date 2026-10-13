//! Preparation of a jointly satisfiable common-source flow extension.
//!
//! This is trusted inference code: the premise formulas and generated model
//! implement the joint-existence lemma. No independent runtime checker proves
//! that lemma. This module does NOT prove its returned premises; the proof engine
//! must check each in the old scope before using the model. See docs/FLOW_V4.md.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("flow");
use crate::model::{check_q, Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::proof::{FlowWitness, Kind, Ref};
use crate::verify::Limits;
use num_traits::{One, Signed, Zero};
use serde::Serialize;

fn invalid(s: &str) -> String {
    format!("INVALID flow: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT flow: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct FlowStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct FlowPremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// Conditional construction only: callers must establish every premise first.
#[derive(Debug)]
pub struct UncheckedFlowExtension {
    pub model: Model,
    pub premises: Vec<FlowPremise>,
    pub statistics: FlowStatistics,
}
/// Prepare bounded expressions, references and a candidate extended model.
/// This is not an acceptance entry point: none of the supplied references are
/// trusted or checked here. The caller must verify every returned premise using
/// the pre-extension input and facts before recursively checking the child body.
pub fn prepare_unchecked_extension(
    input: &Model,
    witness: &FlowWitness,
    limits: &Limits,
) -> Result<UncheckedFlowExtension, String> {
    let mut budget = Budget::new(SUPPORT, limits.work);
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
    budget.charge(SUPPORT.add(n, SUPPORT.add(m, witness.groups.len())?)?)?;
    let mut nonloops = 0usize;
    for &(tail, head) in &witness.arcs {
        if tail as usize >= n || head as usize >= n {
            return Err(invalid("arc endpoint"));
        }
        if tail != head {
            nonloops = SUPPORT.add(nonloops, 1)?;
        }
    }
    let (old_terms, copy_work) = SUPPORT.model_size(input)?;
    if old_terms > MAX_TERMS {
        return Err(resource("input term limit"));
    }
    budget.charge(SUPPORT.mul(copy_work, 2)?)?; // Validate and copy the entire input prefix.
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
        budget.charge(SUPPORT.mul(k, 2)?)?;
        for &(sink, ref demand) in &group.commodities {
            if sink as usize >= n {
                return Err(invalid("commodity sink"));
            }
            check_q(demand)?;
            if demand.is_negative() {
                return Err(invalid("negative demand"));
            }
        }
        let km = SUPPORT.mul(k, m)?;
        new_vars = SUPPORT.add(new_vars, km)?;
        new_rows = SUPPORT.add(new_rows, SUPPORT.add(SUPPORT.mul(k, n)?, m)?)?;
        premises_count = SUPPORT.add(premises_count, SUPPORT.add(m, n)?)?;
        // Balance rows contain two entries per non-loop edge/commodity; arc
        // total rows contain one entry per commodity and the old flow terms.
        new_terms = SUPPORT.add(new_terms, SUPPORT.add(SUPPORT.mul(SUPPORT.mul(k, nonloops)?, 2)?, km)?)?;
        for (edge, flow) in group.flows.iter().enumerate() {
            budget.charge(SUPPORT.add(flow.terms.len(), 1)?)?;
            flow.validate(input.vars.len())?;
            new_terms = SUPPORT.add(new_terms, flow.terms.len())?;
            let factor = if witness.arcs[edge].0 == witness.arcs[edge].1 {
                1
            } else {
                3
            };
            premise_terms = SUPPORT.add(premise_terms, SUPPORT.mul(flow.terms.len(), factor)?)?;
        }
    }
    let vars = SUPPORT.add(input.vars.len(), new_vars)?;
    let rows = SUPPORT.add(input.rows.len(), new_rows)?;
    if vars > MAX_VARS || rows > MAX_ROWS || premises_count > MAX_ROWS {
        return Err(resource("expanded dimensions"));
    }
    if SUPPORT.add(old_terms, SUPPORT.add(new_terms, premise_terms)?)? > MAX_TERMS {
        return Err(resource("combined model and premise terms"));
    }
    // Charge all expanded storage and coefficient work before reserving it.
    // Canonical sorting and collision checks are charged additionally below.
    budget.charge(SUPPORT.add(
        SUPPORT.mul(SUPPORT.add(new_vars, new_rows)?, 32)?,
        SUPPORT.add(
            SUPPORT.mul(SUPPORT.add(new_terms, premise_terms)?, 4)?,
            SUPPORT.mul(premises_count, 4)?,
        )?,
    )?)?;

    let mut extended = SUPPORT.copy_prefix(input, vars, rows)?;
    let mut variable_names = SUPPORT.names(
        input.vars.iter().map(|v| v.name.as_str()),
        input.vars.len(),
        "$rpx_flow_var_",
    )?;
    let mut row_names = SUPPORT.names(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_flow_row_",
    )?;
    let mut premises = SUPPORT.reserved(premises_count)?;
    let mut actual_generated_terms = 0usize;
    for group in &witness.groups {
        let start = extended.vars.len();
        let k = group.commodities.len();
        // Pre-count sparse divergence entries, so building one wide row never
        // repeatedly merges and copies its accumulated sparse expression.
        let mut sizes = SUPPORT.reserved(n)?;
        sizes.resize(n, 0usize);
        for (&(tail, head), flow) in witness.arcs.iter().zip(&group.flows) {
            if tail != head {
                sizes[tail as usize] = SUPPORT.add(sizes[tail as usize], flow.terms.len())?;
                sizes[head as usize] = SUPPORT.add(sizes[head as usize], flow.terms.len())?;
            }
        }
        let mut divergence = SUPPORT.reserved(n)?;
        for size in sizes {
            budget.sort(size)?;
            divergence.push(Expr {
                constant: Q::zero(),
                terms: SUPPORT.reserved(size)?,
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
            premises.push(FlowPremise {
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
            premises.push(FlowPremise {
                kind: Kind::Eq,
                expression,
                reference: group.balances[node].clone(),
            });
        }
        for _ in 0..SUPPORT.mul(k, m)? {
            extended.vars.push(Var {
                name: variable_names.fresh(&mut budget)?,
                integer: false,
                lower: Some(Q::zero()),
                upper: None,
            });
        }

        // Precompute incidence once, including explicit cancellation of loops.
        let mut incident_sizes = SUPPORT.reserved(n)?;
        incident_sizes.resize(n, 0usize);
        for &(tail, head) in &witness.arcs {
            if tail != head {
                incident_sizes[tail as usize] += 1;
                incident_sizes[head as usize] += 1;
            }
        }
        let mut incident = SUPPORT.reserved(n)?;
        for size in incident_sizes {
            incident.push(SUPPORT.reserved(size)?);
        }
        for (edge, &(tail, head)) in witness.arcs.iter().enumerate() {
            if tail != head {
                incident[tail as usize].push((edge, true));
                incident[head as usize].push((edge, false));
            }
        }
        for (commodity, &(sink, ref demand)) in group.commodities.iter().enumerate() {
            for (node, incidence) in incident.iter().enumerate() {
                let mut terms = SUPPORT.reserved(incidence.len())?;
                for &(edge, positive) in incidence {
                    let id = SUPPORT.add(start, SUPPORT.add(SUPPORT.mul(commodity, m)?, edge)?)?;
                    terms.push((
                        u32::try_from(id).map_err(|_| resource("variable index width"))?,
                        if positive { Q::one() } else { -Q::one() },
                    ));
                }
                let rhs = if group.source == sink {
                    Q::zero()
                } else if node == group.source as usize {
                    demand.clone()
                } else if node == sink as usize {
                    -demand
                } else {
                    Q::zero()
                };
                actual_generated_terms = SUPPORT.add(actual_generated_terms, terms.len())?;
                extended.rows.push(Row {
                    name: row_names.fresh(&mut budget)?,
                    expr: Expr {
                        constant: Q::zero(),
                        terms,
                    },
                    lower: Some(rhs.clone()),
                    upper: Some(rhs),
                });
            }
        }
        for (edge, flow) in group.flows.iter().enumerate() {
            let mut terms = SUPPORT.reserved(SUPPORT.add(flow.terms.len(), k)?)?;
            terms.extend(flow.terms.iter().map(|(id, c)| (*id, -c)));
            for commodity in 0..k {
                let id = SUPPORT.add(start, SUPPORT.add(SUPPORT.mul(commodity, m)?, edge)?)?;
                terms.push((
                    u32::try_from(id).map_err(|_| resource("variable index width"))?,
                    Q::one(),
                ));
            }
            actual_generated_terms = SUPPORT.add(actual_generated_terms, terms.len())?;
            extended.rows.push(Row {
                name: row_names.fresh(&mut budget)?,
                expr: Expr {
                    constant: -&flow.constant,
                    terms,
                },
                lower: Some(Q::zero()),
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
    Ok(UncheckedFlowExtension {
        model: extended,
        premises,
        statistics: FlowStatistics {
            work: budget.used(),
            generated_variables: new_vars as u64,
            generated_rows: new_rows as u64,
            generated_terms: actual_generated_terms as u64,
        },
    })
}
