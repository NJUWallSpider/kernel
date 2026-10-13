//! Complete paired domain for a specified affine map's injectivity proof.
//!
//! This builder does not establish any equality goal or bind a certificate claim.
//! The caller must bind the same actual directional models/map, preserve the
//! original input integer mode, and prove every returned equality in fresh scope.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("injectivity");
use crate::model::{Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::verify::Limits;
use num_traits::{One, Zero};
use serde::Serialize;

fn invalid(s: &str) -> String {
    format!("INVALID injectivity: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT injectivity: {s}")
}
fn shifted(e: &Expr, offset: usize) -> Result<Expr, String> {
    let mut terms = SUPPORT.reserved(e.terms.len())?;
    for (i, c) in &e.terms {
        terms.push((
            u32::try_from(SUPPORT.add(*i as usize, offset)?)
                .map_err(|_| resource("shifted index width"))?,
            c.clone(),
        ));
    }
    Ok(Expr {
        constant: e.constant.clone(),
        terms,
    })
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct InjectivityStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct InjectivityDomain {
    pub model: Model,
    pub equalities: Vec<Expr>,
    pub statistics: InjectivityStatistics,
}
fn model_work(model: &Model) -> Result<(usize, usize), String> {
    if model.vars.len() > MAX_VARS || model.rows.len() > MAX_ROWS {
        return Err(resource("model dimension"));
    }
    let (terms, work) = SUPPORT.model_size(model)?;
    if terms > MAX_TERMS {
        return Err(resource("model term count"));
    }
    Ok((terms, work))
}

/// Construct two complete input-domain copies, followed by equality of every
/// actual output coordinate of the specified full affine map. Success is only
/// construction; in particular a noninjective map has a valid paired domain.
pub fn prepare_domain(
    input: &Model,
    output: &Model,
    forward_map: &[Expr],
    limits: &Limits,
) -> Result<InjectivityDomain, String> {
    let mut budget = Budget::new(SUPPORT, limits.work);
    if forward_map.len() != output.vars.len() {
        return Err(invalid("incomplete affine map"));
    }
    let variables = SUPPORT.mul(input.vars.len(), 2)?;
    let rows = SUPPORT.add(SUPPORT.mul(input.rows.len(), 2)?, output.vars.len())?;
    if variables > MAX_VARS || rows > MAX_ROWS {
        return Err(resource("paired dimension"));
    }
    let (_, input_work) = model_work(input)?;
    let (_, output_work) = model_work(output)?;
    budget.charge(SUPPORT.add(SUPPORT.mul(input_work, 3)?, output_work)?)?;
    input.validate()?;
    output.validate()?;
    let mut map_terms = 0usize;
    for e in forward_map {
        budget.charge(SUPPORT.add(e.terms.len(), 1)?)?;
        e.validate(input.vars.len())?;
        map_terms = SUPPORT.add(map_terms, e.terms.len())?;
    }
    let input_row_terms = input
        .rows
        .iter()
        .try_fold(0usize, |n, r| SUPPORT.add(n, r.expr.terms.len()))?;
    let terms = SUPPORT.mul(SUPPORT.add(input_row_terms, map_terms)?, 2)?;
    let goal_terms = SUPPORT.mul(input.vars.len(), 2)?;
    if SUPPORT.add(terms, goal_terms)? > MAX_TERMS {
        return Err(resource("paired and goal term count"));
    }
    budget.charge(SUPPORT.add(
        SUPPORT.mul(SUPPORT.add(variables, rows)?, 32)?,
        SUPPORT.mul(SUPPORT.add(terms, goal_terms)?, 4)?,
    )?)?;
    let mut model = Model {
        name: "$rpx_injectivity".into(),
        vars: SUPPORT.reserved(variables)?,
        rows: SUPPORT.reserved(rows)?,
        objective: Expr::zero(),
    };
    for (copy, prefix) in ["$rpx_pair_left_var_", "$rpx_pair_right_var_"]
        .into_iter()
        .enumerate()
    {
        for (i, v) in input.vars.iter().enumerate() {
            model.vars.push(Var {
                name: SUPPORT.name(prefix, i)?,
                integer: v.integer,
                lower: v.lower.clone(),
                upper: v.upper.clone(),
            });
        }
        let offset = SUPPORT.mul(copy, input.vars.len())?;
        let row_prefix = if copy == 0 {
            "$rpx_pair_left_row_"
        } else {
            "$rpx_pair_right_row_"
        };
        for (i, r) in input.rows.iter().enumerate() {
            model.rows.push(Row {
                name: SUPPORT.name(row_prefix, i)?,
                expr: shifted(&r.expr, offset)?,
                lower: r.lower.clone(),
                upper: r.upper.clone(),
            });
        }
    }
    for (j, e) in forward_map.iter().enumerate() {
        let mut row_terms = SUPPORT.reserved(SUPPORT.mul(e.terms.len(), 2)?)?;
        row_terms.extend(e.terms.iter().cloned());
        for (i, c) in &e.terms {
            row_terms.push((
                u32::try_from(SUPPORT.add(*i as usize, input.vars.len())?)
                    .map_err(|_| resource("observation index width"))?,
                -c,
            ));
        }
        // Both copies use exactly this expression: its constant cancels exactly.
        model.rows.push(Row {
            name: SUPPORT.name("$rpx_pair_observation_", j)?,
            expr: Expr {
                constant: Q::zero(),
                terms: row_terms,
            },
            lower: Some(Q::zero()),
            upper: Some(Q::zero()),
        });
    }
    let mut equalities = SUPPORT.reserved(input.vars.len())?;
    for i in 0..input.vars.len() {
        let mut eq_terms = SUPPORT.reserved(2)?;
        eq_terms.push((
            u32::try_from(i).map_err(|_| resource("goal index width"))?,
            Q::one(),
        ));
        eq_terms.push((
            u32::try_from(SUPPORT.add(i, input.vars.len())?).map_err(|_| resource("goal shifted width"))?,
            -Q::one(),
        ));
        equalities.push(Expr {
            constant: Q::zero(),
            terms: eq_terms,
        });
    }
    model.validate()?;
    if model.vars.len() != variables
        || model.rows.len() != rows
        || equalities.len() != input.vars.len()
        || model.rows.iter().map(|r| r.expr.terms.len()).sum::<usize>() != terms
    {
        return Err(invalid("internal paired layout mismatch"));
    }
    Ok(InjectivityDomain {
        model,
        equalities,
        statistics: InjectivityStatistics {
            work: budget.used(),
            generated_variables: variables as u64,
            generated_rows: rows as u64,
            generated_terms: terms as u64,
        },
    })
}
