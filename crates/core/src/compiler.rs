//! Typed proof-authoring bridge over the frozen Certificate and RPX codec.
//!
//! Inputs are data, not a proof language. The bridge never assembles RPA,
//! searches for a proof, or substitutes compilation for kernel verification.
use crate::model::Expr;
use crate::verify::{self, Limits};

mod resolve;
pub use resolve::{resolve_return, Assignment, AssignmentFact, AuthoringFact, MissingObligation, ResolveResult, ResolveReturn};

/// A terminal Return in already-oriented input/output coordinates.
#[derive(Clone, Debug)]
pub struct ReturnPlan {
    pub map: Vec<Expr>,
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
    verify::visit_return_obligations(input,output,&plan.map,limits,visitor)
}
