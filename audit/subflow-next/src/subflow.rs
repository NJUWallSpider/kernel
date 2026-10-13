//! Trusted joint-existence builder candidate, isolated from production.
//! Every returned premise must be checked in the old scope before the appended
//! domain is used. The mathematical lemma is in CAPABILITY_CLOSURE_REVIEW.md.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("subflow");
use crate::model::{Expr, MAX_ROWS, MAX_TERMS, MAX_VARS, Model, Q, Row, Var, check_q};
use crate::proof::{Kind, Ref, SubflowWitness};
use crate::verify::Limits;
use num_traits::{One, Signed, Zero};
use serde::Serialize;
fn invalid(s: &str) -> String {
    format!("INVALID subflow: {s}")
}
fn resource(s: &str) -> String {
    SUPPORT.resource(s)
}
fn classify(s: String) -> String {
    if s.starts_with("RESOURCE_LIMIT") || s.starts_with("INVALID") {
        s
    } else {
        invalid(&s)
    }
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct SubflowStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct SubflowPremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// Conditional construction only: callers must establish every premise first.
#[derive(Debug)]
pub struct UncheckedSubflowExtension {
    pub model: Model,
    pub premises: Vec<SubflowPremise>,
    pub statistics: SubflowStatistics,
}
/// Prepare bounded expressions, references and a candidate extended model.
/// This is not an acceptance entry point: none of the supplied references are
/// trusted or checked here. The caller must verify every returned premise using
/// the pre-extension input and facts before recursively checking the child body.
pub fn prepare_unchecked_extension(
    input: &Model,
    witness: &SubflowWitness,
    limits: &Limits,
) -> Result<UncheckedSubflowExtension, String> {
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
    input.validate().map_err(classify)?;
    let mut new_vars = 0usize;
    let mut new_rows = 0usize;
    let mut new_terms = 0usize;
    let mut premise_terms = 0usize;
    let mut premises_count = 0usize;
    for group in &witness.groups {
        if group.source as usize >= n {
            return Err(invalid("group source"));
        }
        if group.demands.len() > MAX_ROWS {
            return Err(resource("demand count"));
        }
        if group.flows.len() != m || group.nonnegative.len() != m || group.balances.len() != n {
            return Err(invalid("missing or surplus arc/node premises"));
        }
        let k = group.demands.len();
        budget.charge(SUPPORT.mul(k, 6)?)?;
        for &(sink, ref demand) in &group.demands {
            if sink as usize >= n || sink == group.source {
                return Err(invalid(
                    "demand sink must be in range and differ from source",
                ));
            }
            check_q(demand).map_err(classify)?;
            if demand.is_negative() {
                return Err(invalid("negative demand"));
            }
        }
        new_vars = SUPPORT.add(new_vars, m)?;
        new_rows = SUPPORT.add(new_rows, SUPPORT.add(n, m)?)?;
        premises_count = SUPPORT.add(premises_count, SUPPORT.add(m, n)?)?;
        // Node rows contain two entries per non-loop edge; subflow rows
        // contain one generated coordinate and the old affine flow terms.
        new_terms = SUPPORT.add(new_terms, SUPPORT.add(SUPPORT.mul(nonloops, 2)?, m)?)?;
        for (edge, flow) in group.flows.iter().enumerate() {
            budget.charge(SUPPORT.add(flow.terms.len(), 1)?)?;
            flow.validate(input.vars.len()).map_err(classify)?;
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
        "$rpx_subflow_var_",
    )?;
    let mut row_names = SUPPORT.names(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_subflow_row_",
    )?;
    let mut premises = SUPPORT.reserved(premises_count)?;
    let mut actual_generated_terms = 0usize;
    for group in &witness.groups {
        let start = extended.vars.len();
        let mut bound = Q::zero();
        let mut rhs = SUPPORT.reserved(n)?;
        rhs.resize(n, Q::zero());
        for &(sink, ref demand) in &group.demands {
            bound += demand;
            check_q(&bound).map_err(classify)?;
            if sink != group.source {
                rhs[group.source as usize] += demand;
                check_q(&rhs[group.source as usize]).map_err(classify)?;
                rhs[sink as usize] -= demand;
                check_q(&rhs[sink as usize]).map_err(classify)?;
            }
        }
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
        for &(sink, ref demand) in &group.demands {
            if sink != group.source {
                let s = group.source as usize;
                divergence[s].constant -= demand;
                check_q(&divergence[s].constant).map_err(classify)?;
                divergence[sink as usize].constant += demand;
                check_q(&divergence[sink as usize].constant).map_err(classify)?;
            }
        }
        for (edge, (&(tail, head), flow)) in witness.arcs.iter().zip(&group.flows).enumerate() {
            premises.push(SubflowPremise {
                kind: Kind::Le,
                expression: flow.scaled(&(-Q::one())).map_err(classify)?,
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
                    check_q(&d.constant).map_err(classify)?;
                    d.terms.extend(
                        flow.terms
                            .iter()
                            .map(|(id, c)| (*id, if positive { c.clone() } else { -c })),
                    );
                }
            }
        }
        for (node, mut expression) in divergence.into_iter().enumerate() {
            expression.canonicalize().map_err(classify)?;
            premises.push(SubflowPremise {
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
        for (node, incidence) in incident.iter().enumerate() {
            let mut terms = SUPPORT.reserved(incidence.len())?;
            for &(edge, positive) in incidence {
                let id = SUPPORT.add(start, edge)?;
                terms.push((
                    u32::try_from(id).map_err(|_| resource("variable index width"))?,
                    if positive { Q::one() } else { -Q::one() },
                ));
            }
            actual_generated_terms = SUPPORT.add(actual_generated_terms, terms.len())?;
            extended.rows.push(Row {
                name: row_names.fresh(&mut budget)?,
                expr: Expr {
                    constant: Q::zero(),
                    terms,
                },
                lower: Some(rhs[node].clone()),
                upper: Some(rhs[node].clone()),
            });
        }
        for (edge, flow) in group.flows.iter().enumerate() {
            let mut terms = SUPPORT.reserved(SUPPORT.add(flow.terms.len(), 1)?)?;
            terms.extend(flow.terms.iter().map(|(id, c)| (*id, -c)));
            let id = SUPPORT.add(start, edge)?;
            terms.push((
                u32::try_from(id).map_err(|_| resource("variable index width"))?,
                Q::one(),
            ));
            actual_generated_terms = SUPPORT.add(actual_generated_terms, terms.len())?;
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
    extended.validate().map_err(classify)?;
    if extended.vars.len() != vars
        || extended.rows.len() != rows
        || premises.len() != premises_count
        || actual_generated_terms != new_terms
    {
        return Err(invalid("internal extension layout mismatch"));
    }
    Ok(UncheckedSubflowExtension {
        model: extended,
        premises,
        statistics: SubflowStatistics {
            work: budget.used(),
            generated_variables: new_vars as u64,
            generated_rows: new_rows as u64,
            generated_terms: actual_generated_terms as u64,
        },
    })
}
