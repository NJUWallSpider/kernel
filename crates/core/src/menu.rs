//! Conditional optional-menu extension. Preparation is not proof acceptance.
//!
//! The caller must prove all six premises in the parent scope and require its
//! integer input mode before exposing any generated integer domain or row.
//! The premise formulas and joint-extension model are trusted inference code;
//! no independent runtime checker proves their existential-extension lemma.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("menu");
use crate::model::{check_q, Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::proof::{Kind, MenuWitness, Ref};
use crate::verify::Limits;
use num_traits::{One, Zero};
use serde::Serialize;

fn invalid(s: &str) -> String {
    format!("INVALID menu: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT menu: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct MenuStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct MenuPremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// References and integer input mode remain unchecked by this structural helper.
#[derive(Debug)]
pub struct UncheckedMenuExtension {
    pub model: Model,
    pub premises: Vec<MenuPremise>,
    pub statistics: MenuStatistics,
}
/// Build every premise and the complete simultaneous candidate extension.
/// The premises are LE(-A), LE(A-1), INT(A), LE(-I), LE(I-K*A), INT(I).
/// False premises can be returned successfully; only the proof engine accepts.
pub fn prepare_unchecked_extension(
    input: &Model,
    menus: &[MenuWitness],
    limits: &Limits,
) -> Result<UncheckedMenuExtension, String> {
    let mut budget = Budget::new(SUPPORT, limits.work);
    if input.vars.len() > MAX_VARS || input.rows.len() > MAX_ROWS || menus.len() > MAX_VARS {
        return Err(resource("dimension limit"));
    }
    let rows = SUPPORT.mul(menus.len(), 2)?;
    let premise_count = SUPPORT.mul(menus.len(), 6)?;
    if SUPPORT.add(input.rows.len(), rows)? > MAX_ROWS || premise_count > MAX_ROWS {
        return Err(resource("expanded rows or premise count"));
    }
    budget.charge(menus.len())?;
    let (old_terms, copy_work) = SUPPORT.model_size(input)?;
    if old_terms > MAX_TERMS {
        return Err(resource("input term count"));
    }
    budget.charge(SUPPORT.mul(copy_work, 2)?)?;
    input.validate()?;
    let mut new_vars = 0usize;
    let mut generated_terms = 0usize;
    let mut premise_terms = 0usize;
    for menu in menus {
        if menu.checks.len() != 6 {
            return Err(invalid("exactly six premise references required"));
        }
        let k = usize::try_from(menu.maximum_index).map_err(|_| resource("index width"))?;
        new_vars = SUPPORT.add(new_vars, SUPPORT.add(k, 1)?)?;
        if SUPPORT.add(input.vars.len(), new_vars)? > MAX_VARS {
            return Err(resource("expanded variable count"));
        }
        for e in [&menu.activation, &menu.index] {
            budget.charge(SUPPORT.add(e.terms.len(), 1)?)?;
            e.validate(input.vars.len())?;
        }
        generated_terms = SUPPORT.add(
            generated_terms,
            SUPPORT.add(
                SUPPORT.add(menu.activation.terms.len(), menu.index.terms.len())?,
                SUPPORT.add(k, SUPPORT.add(k, 1)?)?,
            )?,
        )?;
        premise_terms = SUPPORT.add(
            premise_terms,
            SUPPORT.add(
                SUPPORT.mul(menu.activation.terms.len(), 4)?,
                SUPPORT.mul(menu.index.terms.len(), 3)?,
            )?,
        )?;
        if SUPPORT.add(old_terms, SUPPORT.add(generated_terms, premise_terms)?)? > MAX_TERMS {
            return Err(resource("combined model and premise terms"));
        }
    }
    budget.charge(SUPPORT.add(
        SUPPORT.mul(SUPPORT.add(new_vars, rows)?, 32)?,
        SUPPORT.add(
            SUPPORT.mul(SUPPORT.add(generated_terms, premise_terms)?, 4)?,
            SUPPORT.mul(premise_count, 4)?,
        )?,
    )?)?;
    let mut model = SUPPORT.copy_prefix(input, SUPPORT.add(input.vars.len(), new_vars)?, SUPPORT.add(input.rows.len(), rows)?)?;
    let mut variable_names = SUPPORT.names(
        input.vars.iter().map(|v| v.name.as_str()),
        input.vars.len(),
        "$rpx_menu_var_",
    )?;
    let mut row_names = SUPPORT.names(
        input.rows.iter().map(|r| r.name.as_str()),
        input.rows.len(),
        "$rpx_menu_row_",
    )?;
    let mut premises = SUPPORT.reserved(premise_count)?;
    let mut actual_terms = 0usize;
    for menu in menus {
        let mut upper_a = SUPPORT.copy_expr(&menu.activation)?;
        upper_a.constant -= Q::one();
        check_q(&upper_a.constant)?;
        let scaled = menu
            .activation
            .scaled(&Q::from_integer(menu.maximum_index.into()))?;
        let expressions = [
            (Kind::Le, menu.activation.scaled(&(-Q::one()))?),
            (Kind::Le, upper_a),
            (Kind::Int, SUPPORT.copy_expr(&menu.activation)?),
            (Kind::Le, menu.index.scaled(&(-Q::one()))?),
            (Kind::Le, SUPPORT.difference(&menu.index, &scaled)?),
            (Kind::Int, SUPPORT.copy_expr(&menu.index)?),
        ];
        for ((kind, expression), reference) in expressions.into_iter().zip(&menu.checks) {
            premises.push(MenuPremise {
                kind,
                expression,
                reference: reference.clone(),
            });
        }
        let first = model.vars.len();
        let count = SUPPORT.add(menu.maximum_index as usize, 1)?;
        for _ in 0..count {
            model.vars.push(Var {
                name: variable_names.fresh(&mut budget)?,
                integer: true,
                lower: Some(Q::zero()),
                upper: Some(Q::one()),
            });
        }
        for (observation, moment) in [(&menu.activation, false), (&menu.index, true)] {
            let mut terms = SUPPORT.reserved(SUPPORT.add(observation.terms.len(), count)?)?;
            terms.extend(observation.terms.iter().map(|(i, c)| (*i, -c)));
            for j in 0..count {
                if moment && j == 0 {
                    continue;
                }
                let variable =
                    u32::try_from(SUPPORT.add(first, j)?).map_err(|_| resource("variable index width"))?;
                terms.push((
                    variable,
                    if moment {
                        Q::from_integer(j.into())
                    } else {
                        Q::one()
                    },
                ));
            }
            actual_terms = SUPPORT.add(actual_terms, terms.len())?;
            model.rows.push(Row {
                name: row_names.fresh(&mut budget)?,
                expr: Expr {
                    constant: -&observation.constant,
                    terms,
                },
                lower: Some(Q::zero()),
                upper: Some(Q::zero()),
            });
        }
    }
    model.validate()?;
    if model.vars.len() != SUPPORT.add(input.vars.len(), new_vars)?
        || model.rows.len() != SUPPORT.add(input.rows.len(), rows)?
        || premises.len() != premise_count
        || actual_terms != generated_terms
    {
        return Err(invalid("internal extension layout mismatch"));
    }
    Ok(UncheckedMenuExtension {
        model,
        premises,
        statistics: MenuStatistics {
            work: budget.used(),
            generated_variables: new_vars as u64,
            generated_rows: rows as u64,
            generated_terms: actual_terms as u64,
        },
    })
}
