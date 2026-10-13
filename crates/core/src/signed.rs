//! Joint binary-gated signed-flow decomposition; preparation is not proof acceptance.
//!
//! The caller must prove all five premises in the parent scope and require its
//! integer input mode before exposing any generated integer domain or row.
//! The premise formulas and joint-extension model are trusted inference code;
//! no independent runtime checker proves their existential-extension lemma.
use crate::build_support::{Budget, Support};
const SUPPORT: Support = Support::new("signed");
use crate::model::{check_q, Expr, Model, Row, Var, MAX_ROWS, MAX_TERMS, MAX_VARS, Q};
use crate::proof::{Kind, SignedWitness, Ref};
use crate::verify::Limits;
use num_traits::{One, Zero};
use serde::Serialize;

fn invalid(s: &str) -> String {
    format!("INVALID signed: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT signed: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct SignedStatistics {
    pub work: u64,
    pub generated_variables: u64,
    pub generated_rows: u64,
    pub generated_terms: u64,
}
#[derive(Debug)]
pub struct SignedPremise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}
/// References and integer input mode remain unchecked by this structural helper.
#[derive(Debug)]
pub struct UncheckedSignedExtension {
    pub model: Model,
    pub premises: Vec<SignedPremise>,
    pub statistics: SignedStatistics,
}
/// For every old-scope pair (F,Z), capacity C>=0, return five required facts:
/// LE(-Z), LE(Z-1), INT(Z), LE(F-C*Z), LE(-F-C*Z).
/// Once proved, append p,n>=0 and binary u,v with p-n=F, u+v=Z,
/// p<=C*u and n<=C*v. All items have one simultaneous feasible extension.
/// This helper does not accept premise references or the integer input mode.
pub fn prepare_unchecked_extension(
    input: &Model,
    decompositions: &[SignedWitness],
    limits: &Limits,
) -> Result<UncheckedSignedExtension, String> {
    let mut budget = Budget::new(SUPPORT, limits.work);
    if input.vars.len() > MAX_VARS || input.rows.len() > MAX_ROWS || decompositions.len() > MAX_VARS {
        return Err(resource("dimension limit"));
    }
    let new_vars = SUPPORT.mul(decompositions.len(), 4)?;
    let rows = new_vars;
    let premise_count = SUPPORT.mul(decompositions.len(), 5)?;
    if SUPPORT.add(input.vars.len(),new_vars)? > MAX_VARS || SUPPORT.add(input.rows.len(),rows)? > MAX_ROWS || premise_count > MAX_ROWS {
        return Err(resource("expanded variables, rows or premise count"));
    }
    budget.charge(decompositions.len())?;
    let (old_terms, copy_work) = SUPPORT.model_size(input)?;
    if old_terms > MAX_TERMS { return Err(resource("input term count")); }
    budget.charge(SUPPORT.mul(copy_work,2)?)?;
    input.validate()?;
    let mut generated_terms=0usize;
    let mut premise_terms=0usize;
    for d in decompositions {
        if d.checks.len()!=5 { return Err(invalid("exactly five premise references required")); }
        check_q(&d.capacity)?;
        if d.capacity < Q::zero() { return Err(invalid("negative capacity")); }
        for e in [&d.flow,&d.activation] {
            budget.charge(SUPPORT.add(e.terms.len(),1)?)?;
            e.validate(input.vars.len())?;
        }
        generated_terms=SUPPORT.add(generated_terms,SUPPORT.add(SUPPORT.add(d.flow.terms.len(),d.activation.terms.len())?,if d.capacity.is_zero(){6}else{8})?)?;
        // Upper bound includes terms that cancel in the two capacity premises.
        premise_terms=SUPPORT.add(premise_terms,SUPPORT.add(SUPPORT.mul(d.flow.terms.len(),2)?,SUPPORT.mul(d.activation.terms.len(),5)?)?)?;
        if SUPPORT.add(old_terms,SUPPORT.add(generated_terms,premise_terms)?)?>MAX_TERMS { return Err(resource("combined model and premise terms")); }
    }
    budget.charge(SUPPORT.add(SUPPORT.mul(SUPPORT.add(new_vars,rows)?,32)?,SUPPORT.add(SUPPORT.mul(SUPPORT.add(generated_terms,premise_terms)?,4)?,SUPPORT.mul(premise_count,4)?)?)?)?;
    let mut model = SUPPORT.copy_prefix(input, SUPPORT.add(input.vars.len(), new_vars)?, SUPPORT.add(input.rows.len(), rows)?)?;
    let mut variable_names=SUPPORT.names(input.vars.iter().map(|v|v.name.as_str()),input.vars.len(),"$rpx_signed_var_")?;
    let mut row_names=SUPPORT.names(input.rows.iter().map(|r|r.name.as_str()),input.rows.len(),"$rpx_signed_row_")?;
    let mut premises=SUPPORT.reserved(premise_count)?;
    let mut actual_terms=0usize;
    for d in decompositions {
        let mut upper_z=SUPPORT.copy_expr(&d.activation)?;
        upper_z.constant-=Q::one();check_q(&upper_z.constant)?;
        let scaled=d.activation.scaled(&d.capacity)?;
        let neg_flow=d.flow.scaled(&(-Q::one()))?;
        let expressions=[
            (Kind::Le,d.activation.scaled(&(-Q::one()))?),
            (Kind::Le,upper_z),
            (Kind::Int,SUPPORT.copy_expr(&d.activation)?),
            (Kind::Le,SUPPORT.difference(&d.flow,&scaled)?),
            (Kind::Le,SUPPORT.difference(&neg_flow,&scaled)?),
        ];
        for ((kind,expression),reference) in expressions.into_iter().zip(&d.checks) {
            premises.push(SignedPremise{kind,expression,reference:reference.clone()});
        }
        let first=u32::try_from(model.vars.len()).map_err(|_|resource("variable index width"))?;
        for j in 0..4 { model.vars.push(Var{name:variable_names.fresh(&mut budget)?,integer:j>=2,lower:Some(Q::zero()),upper:if j>=2{Some(Q::one())}else{None}}); }
        for (observation,offset,last_coefficient) in [(&d.flow,0,-Q::one()),(&d.activation,2,Q::one())] {
            let mut terms=SUPPORT.reserved(SUPPORT.add(observation.terms.len(),2)?)?;
            terms.extend(observation.terms.iter().map(|(i,c)|(*i,-c)));
            terms.push((first+offset,Q::one()));terms.push((first+offset+1,last_coefficient));
            actual_terms=SUPPORT.add(actual_terms,terms.len())?;
            model.rows.push(Row{name:row_names.fresh(&mut budget)?,expr:Expr{constant:-&observation.constant,terms},lower:Some(Q::zero()),upper:Some(Q::zero())});
        }
        for offset in 0..2 {
            let mut terms=SUPPORT.reserved(2)?;terms.push((first+offset,Q::one()));
            if !d.capacity.is_zero() { terms.push((first+offset+2,-&d.capacity)); }
            actual_terms=SUPPORT.add(actual_terms,terms.len())?;
            model.rows.push(Row{name:row_names.fresh(&mut budget)?,expr:Expr{constant:Q::zero(),terms},lower:None,upper:Some(Q::zero())});
        }
    }
    model.validate()?;
    if model.vars.len()!=SUPPORT.add(input.vars.len(),new_vars)? || model.rows.len()!=SUPPORT.add(input.rows.len(),rows)? || premises.len()!=premise_count || actual_terms!=generated_terms { return Err(invalid("internal extension layout mismatch")); }
    Ok(UncheckedSignedExtension{model,premises,statistics:SignedStatistics{work:budget.used(),generated_variables:new_vars as u64,generated_rows:rows as u64,generated_terms:actual_terms as u64}})
}
