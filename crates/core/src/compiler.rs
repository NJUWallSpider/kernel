//! Direct proof authoring bridge over the frozen Certificate and RPX codec.
//!
//! Inputs are data, not a proof language. The bridge never assembles RPA,
//! searches for a proof, or substitutes compilation for kernel verification.
use crate::{codec, model::{Expr, Q}, proof::{Certificate, Claim, ImprovementClaim, ImprovementMargin}, verify::{self, Limits}};
use serde::Deserialize;

mod resolve;
pub use resolve::{Assignment, AssignmentFact, AuthoringFact, MissingObligation, ResolveReturn, ResolveResult, resolve_return_json, resolve_return};

/// JSON input policy. The codec retains all independent wire limits.
pub const MAX_JSON_BYTES: usize = crate::api::MAX_INPUT_BYTES as usize;

/// Classify serde's bounded parser failures without turning a resource limit
/// into a mathematical rejection.
pub(crate) fn json_error(context: &str, error: serde_json::Error) -> String {
    let message = error.to_string();
    let status = if message.contains("RESOURCE_LIMIT")
        || message.starts_with("recursion limit exceeded at line ") {
        "RESOURCE_LIMIT"
    } else { "INVALID" };
    format!("{status} {context}: {message}")
}

/// Parse raw Certificate JSON directly into the existing typed proof object.
/// Exact scalars use strings; serde rejects unknown fields and floating point
/// scalars. There is no RPA header or intermediate representation.
pub fn parse_certificate_json(text: &str) -> Result<Certificate, String> {
    if text.len() > MAX_JSON_BYTES {
        return Err("RESOURCE_LIMIT certificate JSON bytes".into());
    }
    serde_json::from_str(text).map_err(|error| json_error("certificate JSON", error))
}

/// Compile raw Certificate JSON to RPX, selecting the lowest required frozen
/// wire version through the existing encoder. Success means structurally
/// encodable; the caller must independently supply models and a Request to the
/// kernel verifier to establish correctness.
pub fn compile_certificate_json(text: &str) -> Result<Vec<u8>, String> {
    codec::encode_certificate(&parse_certificate_json(text)?)
}

/// A terminal Return in already-oriented input/output coordinates. The input
/// may be an unchecked extension scope prepared by the existing builders;
/// planning obligations grants no permission to use that scope in a proof.
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReturnPlan {
    pub claim: Claim,
    pub map: Vec<Expr>,
    #[serde(default)]
    pub inverse_map: Option<Vec<Expr>>,
    #[serde(default, with = "crate::rpa::option_scalar")]
    pub inverse_level: Option<Q>,
    #[serde(default)]
    pub compositions: Vec<Vec<Expr>>,
    /// Plan V10 ImproveReturn in the immutable root improvement context.
    #[serde(default)]
    pub improvement: Option<ImprovementPlan>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImprovementPlan {
    pub claim: ImprovementClaim,
    pub margin: ImprovementMargin,
}

pub fn parse_return_plan_json(text: &str) -> Result<ReturnPlan, String> {
    if text.len() > MAX_JSON_BYTES {
        return Err("RESOURCE_LIMIT Return plan JSON bytes".into());
    }
    serde_json::from_str(text).map_err(|error| json_error("Return plan JSON", error))
}

/// Ask the verifier's own terminal walker for every required proposition, in
/// exactly the order it will check the supplied references.
pub fn plan_return(
    input: &crate::model::Model,
    output: &crate::model::Model,
    plan: &ReturnPlan,
    limits: &Limits,
) -> Result<Vec<verify::ReturnObligation>, String> {
    let mut obligations=Vec::new();
    visit_return(input,output,plan,limits,|obligation|{
        obligations.try_reserve(1).map_err(|_|"RESOURCE_LIMIT Return obligation allocation")?;
        obligations.push(obligation);Ok(())
    })?;Ok(obligations)
}

/// Stream the same Kernel-owned propositions used by [`plan_return`].
pub fn visit_return<F>(
    input: &crate::model::Model, output: &crate::model::Model,
    plan: &ReturnPlan, limits: &Limits, visitor:F,
) -> Result<(),String> where F:FnMut(verify::ReturnObligation)->Result<(),String> {
    if let Some(improvement) = &plan.improvement {
        if plan.inverse_map.is_some() || plan.inverse_level.is_some() || !plan.compositions.is_empty() {
            return Err("INVALID Return plan improvement context".into());
        }
        return verify::visit_improvement_return_obligations(input, output, &plan.claim,
            &plan.map, &improvement.claim, &improvement.margin, limits, visitor);
    }
    let compositions: Vec<&[Expr]> = plan.compositions.iter().map(Vec::as_slice).collect();
    verify::visit_return_obligations(input, output, &plan.claim, &plan.map,
        plan.inverse_map.as_deref(), plan.inverse_level.as_ref(), &compositions, limits, visitor)
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InjectivityPlan { pub map: Vec<Expr> }

pub fn parse_injectivity_plan_json(text: &str) -> Result<InjectivityPlan, String> {
    if text.len() > MAX_JSON_BYTES {
        return Err("RESOURCE_LIMIT injectivity plan JSON bytes".into());
    }
    serde_json::from_str(text).map_err(|error| json_error("injectivity plan JSON", error))
}

/// Prepare the exact paired domain and fresh-scope equality goals. A
/// noninjective map may prepare successfully; every goal still needs evidence.
pub fn prepare_injectivity_json(
    input: &crate::model::Model,
    output: &crate::model::Model,
    text: &str,
    limits: &Limits,
) -> Result<serde_json::Value, String> {
    let plan = parse_injectivity_plan_json(text)?;
    let domain = crate::injectivity::prepare_domain(input, output, &plan.map, limits)?;
    Ok(serde_json::json!({"model": crate::model::to_json(&domain.model),
        "equalities": domain.equalities, "statistics": domain.statistics}))
}
