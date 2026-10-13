//! Exact objective-level input domains, constructed from the actual whole model.
//!
//! This is a caller-declared restriction, not an optimum or attainment theorem.
//! All original variables, bounds, rows and objective remain unchanged prefixes.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("objective level");
use crate::model::{check_q, Model, Row, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::verify::Limits;
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

/// Copy the actual input and append `input.objective == level` at its last row.
/// No feasibility, optimality, attainment, output inclusion or inverse conclusion
/// follows from this operation alone. The caller must bind this level to its
/// requested contract and independently prove every required mapping obligation.
pub fn prepare_domain(input: &Model, level: &Q, limits: &Limits) -> Result<LevelDomain, String> {
    if input.vars.len() > MAX_VARS || input.rows.len() >= MAX_ROWS {
        return Err(resource("expanded dimensions"));
    }
    check_q(level)?;
    let rows = SUPPORT.add(input.rows.len(), 1)?;
    let (terms, mut work) = SUPPORT.model_size(input)?;
    if SUPPORT.add(terms, input.objective.terms.len())? > MAX_TERMS {
        return Err(resource("expanded term count"));
    }
    // Copy and two validations, the generated row, exact normalization and names.
    work = SUPPORT.add(
        SUPPORT.mul(work, 3)?,
        SUPPORT.add(
            SUPPORT.mul(SUPPORT.add(input.objective.terms.len(), 1)?, 4)?,
            32,
        )?,
    )?;
    let mut budget = Budget::new(SUPPORT, limits.work);
    budget.charge(work)?;
    input.validate()?;
    // A fact reference will normalize this difference; check it before copying.
    check_q(&(&input.objective.constant - level))?;
    let mut names = SUPPORT.names(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_level_row_",
    )?;
    let name = names.fresh(&mut budget)?;
    let equality_row = u32::try_from(input.rows.len()).map_err(|_| resource("row index width"))?;
    let mut model = SUPPORT.copy_prefix(input, input.vars.len(), rows)?;
    model.rows.push(Row {
        name,
        expr: SUPPORT.copy_expr(&input.objective)?,
        lower: Some(level.clone()),
        upper: Some(level.clone()),
    });
    model.validate()?;
    Ok(LevelDomain {
        model,
        equality_row,
        statistics: LevelStatistics {
            work: budget.used(),
            generated_rows: 1,
            generated_terms: input.objective.terms.len() as u64,
        },
    })
}
