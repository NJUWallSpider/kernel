//! Direct proof authoring bridge over the frozen Certificate and RPX codec.
//!
//! Inputs are data, not a proof language. The bridge never assembles RPA,
//! searches for a proof, or substitutes compilation for kernel verification.
use crate::{codec, model::Expr, proof::Certificate, verify::{self, Limits}};
use serde::Deserialize;

mod resolve;
pub use resolve::{Assignment, AssignmentFact, AuthoringFact, MissingObligation, ResolveReturn, ResolveResult, resolve_return_json, resolve_return};

/// Input policy for planning/authoring JSON. Certificate compilation has its
/// own explicit budget; the codec retains all independent wire limits.
pub const MAX_JSON_BYTES: usize = crate::api::MAX_INPUT_BYTES as usize;

/// Default Certificate JSON budget, independent of the general file reader
/// and every RPX encoding/verification limit.
pub const DEFAULT_CERTIFICATE_JSON_BYTES: u64 = 1024 * 1024 * 1024;

/// Resource policy for direct Certificate JSON compilation, never proof rules.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CompileOptions {
    pub max_json_bytes: u64,
}

impl Default for CompileOptions {
    fn default() -> Self {
        Self { max_json_bytes: DEFAULT_CERTIFICATE_JSON_BYTES }
    }
}

impl CompileOptions {
    pub fn new(max_json_bytes: u64) -> Result<Self, String> {
        let options = Self { max_json_bytes };
        options.validate()?;
        Ok(options)
    }

    pub(crate) fn validate(&self) -> Result<(), String> {
        if self.max_json_bytes == 0 {
            return Err("INVALID certificate JSON byte budget must be positive".into());
        }
        Ok(())
    }
}

/// A nested Cases derivation adds at most four JSON containers per wire
/// depth. The extra envelope/step/expression tuple containers fit below this
/// margin. This is an independent finite parser policy; the codec still owns
/// the exact block-depth limit and rejects structurally excessive proofs.
pub const MAX_CERTIFICATE_JSON_DEPTH: usize = crate::codec::MAX_DEPTH * 4 + 16;

fn check_certificate_json_depth(text: &str) -> Result<(), String> {
    let mut depth=0usize;let mut string=false;let mut escaped=false;
    for byte in text.bytes() {
        if string {
            if escaped {escaped=false;}
            else if byte==b'\\' {escaped=true;}
            else if byte==b'"' {string=false;}
        } else {
            match byte {
                b'"'=>string=true,
                b'{'|b'['=>{
                    depth+=1;
                    if depth>MAX_CERTIFICATE_JSON_DEPTH {
                        return Err("RESOURCE_LIMIT certificate JSON container depth".into());
                    }
                },
                b'}'|b']'=>{depth=depth.checked_sub(1).ok_or("INVALID certificate JSON unbalanced container")?;},
                _=>{},
            }
        }
    }
    // The typed parser independently checks closing types, string escapes,
    // termination and all schema fields. This scan only limits stack depth.
    Ok(())
}

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
    parse_certificate_json_with_options(text, &CompileOptions::default())
}

/// Parse a Certificate under an explicit finite byte budget. All structural,
/// scalar, nesting and wire checks are unchanged.
pub fn parse_certificate_json_with_options(text: &str, options: &CompileOptions) -> Result<Certificate, String> {
    options.validate()?;
    if text.len() as u128 > u128::from(options.max_json_bytes) {
        return Err("RESOURCE_LIMIT certificate JSON bytes".into());
    }
    check_certificate_json_depth(text)?;
    let mut deserializer=serde_json::Deserializer::from_str(text);
    // Bounded above before invoking the recursive typed parser. Its generic
    // 128-container cap otherwise prevents valid frozen depth64 proof trees.
    deserializer.disable_recursion_limit();
    let certificate=Certificate::deserialize(&mut deserializer)
        .map_err(|error|json_error("certificate JSON",error))?;
    deserializer.end().map_err(|error|json_error("certificate JSON",error))?;
    Ok(certificate)
}

/// Compile raw Certificate JSON to RPX, selecting the lowest required frozen
/// wire version through the existing encoder. Success means structurally
/// encodable; the caller must supply complete models to the
/// kernel verifier to establish correctness.
pub fn compile_certificate_json(text: &str) -> Result<Vec<u8>, String> {
    compile_certificate_json_with_options(text, &CompileOptions::default())
}

/// Compile with a Certificate JSON byte budget; the existing encoder remains
/// responsible for every RPX item, magnitude, nesting and byte limit.
pub fn compile_certificate_json_with_options(text: &str, options: &CompileOptions) -> Result<Vec<u8>, String> {
    codec::encode_certificate(&parse_certificate_json_with_options(text, options)?)
}

/// A terminal Return in already-oriented input/output coordinates. The input
/// may be an unchecked extension scope prepared by the existing builders;
/// planning obligations grants no permission to use that scope in a proof.
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReturnPlan {
    pub map: Vec<Expr>,
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
    verify::visit_return_obligations(input,output,&plan.map,limits,visitor)
}
