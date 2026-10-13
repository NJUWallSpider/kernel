//! Caller-bound affine restrictions on the actual complete input model.
//!
//! This construction establishes no feasibility, optimality or attainment claim.
//! The original variables, bounds, rows and objective remain unchanged prefixes.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("objective level");
use crate::model::{Expr, MAX_ROWS, MAX_TERMS, MAX_VARS, Model, Q, Row, check_q};
use crate::verify::Limits;
use num_traits::Zero;
use serde::Serialize;

fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT objective level: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct LevelStatistics {
    pub work: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct LevelDomain {
    pub model: Model,
    pub equality_row: u32,
    pub statistics: LevelStatistics,
}
#[derive(Debug)]
pub struct RestrictedDomain {
    pub model: Model,
    pub equality_row: Option<u32>,
    pub statistics: LevelStatistics,
}

/// Preserve the V9 level-only API, row layout, naming and work accounting.
pub fn prepare_domain(input: &Model, level: &Q, limits: &Limits) -> Result<LevelDomain, String> {
    let domain = prepare_restricted_domain(input, Some(level), None, limits)?;
    Ok(LevelDomain {
        model: domain.model,
        equality_row: domain.equality_row.ok_or("INVALID missing level row")?,
        statistics: domain.statistics,
    })
}

/// Copy the complete input once, append the optional actual-objective equality,
/// then append the optional caller-specified affine halfspace `expression <= 0`.
/// Both restrictions refer exclusively to the original input coordinates.
/// No whole-model, nonempty-domain or optimum conclusion follows from this alone.
pub fn prepare_restricted_domain(
    input: &Model,
    level: Option<&Q>,
    halfspace: Option<&Expr>,
    limits: &Limits,
) -> Result<RestrictedDomain, String> {
    let generated_rows = usize::from(level.is_some()) + usize::from(halfspace.is_some());
    if generated_rows == 0 {
        return Err("INVALID empty input restriction".into());
    }
    let rows = SUPPORT.add(input.rows.len(), generated_rows)?;
    if input.vars.len() > MAX_VARS || rows > MAX_ROWS {
        return Err(resource("expanded dimensions"));
    }
    if let Some(level) = level {
        check_q(level)?;
    }
    let level_terms = if level.is_some() {
        input.objective.terms.len()
    } else {
        0
    };
    let halfspace_terms = halfspace.map_or(0, |expression| expression.terms.len());
    let generated_terms = SUPPORT.add(level_terms, halfspace_terms)?;
    let (terms, mut work) = SUPPORT.model_size(input)?;
    if SUPPORT.add(terms, generated_terms)? > MAX_TERMS {
        return Err(resource("expanded term count"));
    }
    // Prefix copy and two model validations, generated expressions and names.
    // With one objective-level row this is the original V9 budget formula.
    work = SUPPORT.add(
        SUPPORT.mul(work, 3)?,
        SUPPORT.add(
            SUPPORT.mul(SUPPORT.add(generated_terms, generated_rows)?, 4)?,
            SUPPORT.mul(32, generated_rows)?,
        )?,
    )?;
    let mut budget = Budget::new(SUPPORT, limits.work);
    budget.charge(work)?;
    input.validate()?;
    if let Some(level) = level {
        // A fact reference normalizes this difference; reject an oversized
        // intermediate before allocating the copied model.
        check_q(&(&input.objective.constant - level))?;
    }
    if let Some(expression) = halfspace {
        expression.validate(input.vars.len())?;
    }
    let mut model = SUPPORT.copy_prefix(input, input.vars.len(), rows)?;
    let mut equality_row = None;
    if let Some(level) = level {
        let mut names = SUPPORT.names(
            input.rows.iter().map(|r| r.name.as_str()),
            input.rows.len(),
            "$rpx_level_row_",
        )?;
        equality_row =
            Some(u32::try_from(model.rows.len()).map_err(|_| resource("row index width"))?);
        model.rows.push(Row {
            name: names.fresh(&mut budget)?,
            expr: SUPPORT.copy_expr(&input.objective)?,
            lower: Some(level.clone()),
            upper: Some(level.clone()),
        });
    }
    if let Some(expression) = halfspace {
        let mut names = SUPPORT.names(
            input.rows.iter().map(|r| r.name.as_str()),
            input.rows.len(),
            "$rpx_halfspace_row_",
        )?;
        model.rows.push(Row {
            name: names.fresh(&mut budget)?,
            expr: SUPPORT.copy_expr(expression)?,
            lower: None,
            upper: Some(Q::zero()),
        });
    }
    model.validate()?;
    Ok(RestrictedDomain {
        model,
        equality_row,
        statistics: LevelStatistics {
            work: budget.used(),
            generated_rows: generated_rows as u64,
            generated_terms: generated_terms as u64,
        },
    })
}
