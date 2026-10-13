//! Trusted conditional simultaneous interval-extension construction.
//!
//! Every lower/upper pair is returned as an explicit LE premise. The proof
//! engine must establish all of them in the original context before using the
//! extended model. All new interval coordinates are continuous and independent.
//! The premise-to-joint-extension lemma and its model construction remain trusted;
//! checking the returned premises does not independently verify that lemma.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("interval");
use crate::model::{Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::proof::{IntervalWitness, Kind, Ref};
use crate::verify::Limits;
use num_traits::{One, Zero};
use serde::Serialize;

fn invalid(s: &str) -> String {
    format!("INVALID interval: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT interval: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct IntervalStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct IntervalPremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// The supplied references are carried through, not checked. Establish every
/// returned premise before making the candidate model available to a proof.
#[derive(Debug)]
pub struct UncheckedIntervalExtension {
    pub model: Model,
    pub premises: Vec<IntervalPremise>,
    pub statistics: IntervalStatistics,
}
/// Prepare complete lower-major pair premises and a candidate extended model.
/// Success is only structural preparation. Supplied checks can be false or have
/// invalid references; the caller must prove them all on the pre-extension scope.
pub fn prepare_unchecked_extension(
    input: &Model,
    intervals: &[IntervalWitness],
    limits: &Limits,
) -> Result<UncheckedIntervalExtension, String> {
    let mut budget = Budget::new(SUPPORT, limits.work);
    if input.vars.len() > MAX_VARS || input.rows.len() > MAX_ROWS || intervals.len() > MAX_VARS {
        return Err(resource("dimension limit"));
    }
    let variables = SUPPORT.add(input.vars.len(), intervals.len())?;
    if variables > MAX_VARS {
        return Err(resource("expanded variable count"));
    }
    budget.charge(intervals.len())?;
    let (old_terms, copy_work) = SUPPORT.model_size(input)?;
    if old_terms > MAX_TERMS {
        return Err(resource("input term count"));
    }
    budget.charge(SUPPORT.mul(copy_work, 2)?)?;
    input.validate()?;
    let mut rows = 0usize;
    let mut generated_terms = 0usize;
    let mut premise_terms = 0usize;
    let mut pairs = 0usize;
    for interval in intervals {
        let pair_count = SUPPORT.mul(interval.lower.len(), interval.upper.len())?;
        if interval.checks.len() != pair_count {
            return Err(invalid("missing or surplus lower-upper pair checks"));
        }
        pairs = SUPPORT.add(pairs, pair_count)?;
        rows = SUPPORT.add(rows, SUPPORT.add(interval.lower.len(), interval.upper.len())?)?;
        if pairs > MAX_ROWS || SUPPORT.add(input.rows.len(), rows)? > MAX_ROWS {
            return Err(resource("expanded rows or pair count"));
        }
        // Charge the Cartesian product before visiting or allocating its entries.
        budget.charge(pair_count)?;
        let mut low_terms = 0usize;
        let mut high_terms = 0usize;
        for (bounds, total) in [
            (&interval.lower, &mut low_terms),
            (&interval.upper, &mut high_terms),
        ] {
            for bound in bounds {
                budget.charge(SUPPORT.add(bound.terms.len(), 1)?)?;
                bound.validate(input.vars.len())?;
                *total = SUPPORT.add(*total, bound.terms.len())?;
                generated_terms = SUPPORT.add(generated_terms, SUPPORT.add(bound.terms.len(), 1)?)?;
            }
        }
        premise_terms = SUPPORT.add(
            premise_terms,
            SUPPORT.add(
                SUPPORT.mul(interval.upper.len(), low_terms)?,
                SUPPORT.mul(interval.lower.len(), high_terms)?,
            )?,
        )?;
        if SUPPORT.add(old_terms, SUPPORT.add(generated_terms, premise_terms)?)? > MAX_TERMS {
            return Err(resource("combined model and premise term count"));
        }
    }
    // Conservative storage/arithmetic charge before any expanded buffer reserve.
    budget.charge(SUPPORT.add(
        SUPPORT.mul(SUPPORT.add(intervals.len(), rows)?, 32)?,
        SUPPORT.add(
            SUPPORT.mul(SUPPORT.add(generated_terms, premise_terms)?, 4)?,
            SUPPORT.mul(pairs, 4)?,
        )?,
    )?)?;
    let mut model = SUPPORT.copy_prefix(input, variables, SUPPORT.add(input.rows.len(), rows)?)?;
    let mut variable_names = SUPPORT.names(
        input.vars.iter().map(|v| v.name.as_str()),
        input.vars.len(),
        "$rpx_interval_var_",
    )?;
    let mut row_names = SUPPORT.names(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_interval_row_",
    )?;
    let mut premises = SUPPORT.reserved(pairs)?;
    let mut actual_terms = 0usize;
    for interval in intervals {
        let mut pair = 0usize;
        for lower in &interval.lower {
            for upper in &interval.upper {
                premises.push(IntervalPremise {
                    kind: Kind::Le,
                    expression: SUPPORT.difference(lower, upper)?,
                    reference: interval.checks[pair].clone(),
                });
                pair += 1;
            }
        }
        let variable =
            u32::try_from(model.vars.len()).map_err(|_| resource("variable index width"))?;
        model.vars.push(Var {
            name: variable_names.fresh(&mut budget)?,
            integer: false,
            lower: None,
            upper: None,
        });
        for (bounds, is_lower) in [(&interval.lower, true), (&interval.upper, false)] {
            for bound in bounds {
                let mut terms = SUPPORT.reserved(SUPPORT.add(bound.terms.len(), 1)?)?;
                terms.extend(bound.terms.iter().map(|(id, c)| (*id, -c)));
                terms.push((variable, Q::one()));
                actual_terms = SUPPORT.add(actual_terms, terms.len())?;
                model.rows.push(Row {
                    name: row_names.fresh(&mut budget)?,
                    expr: Expr {
                        constant: -&bound.constant,
                        terms,
                    },
                    lower: if is_lower { Some(Q::zero()) } else { None },
                    upper: if is_lower { None } else { Some(Q::zero()) },
                });
            }
        }
    }
    model.validate()?;
    if model.vars.len() != variables
        || model.rows.len() != SUPPORT.add(input.rows.len(), rows)?
        || premises.len() != pairs
        || actual_terms != generated_terms
    {
        return Err(invalid("internal extension layout mismatch"));
    }
    Ok(UncheckedIntervalExtension {
        model,
        premises,
        statistics: IntervalStatistics {
            work: budget.used(),
            generated_variables: intervals.len() as u64,
            generated_rows: rows as u64,
            generated_terms: actual_terms as u64,
        },
    })
}
