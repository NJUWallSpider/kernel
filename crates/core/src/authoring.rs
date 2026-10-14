//! Untrusted compiler preparation over existing checked extension builders.
//! Success prepares a candidate scope; it does not establish any premise.
use crate::{api, codec, model::{self, Expr, Q}, proof::*, verify::Limits};
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::Path;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
enum Extension {
    Interval(Vec<IntervalWitness>),
    Menu(Vec<MenuWitness>),
    Signed(Vec<SignedWitness>),
    Flow(FlowWitness),
    Subflow(SubflowWitness),
    Restricted {
        #[serde(default, with="crate::rpa::option_scalar")]
        level: Option<Q>,
        #[serde(default)]
        halfspace: Option<Expr>,
    },
}

/// Return the exact kernel-created scope and old-scope proof obligations.
/// No supplied reference is accepted here: verification checks all of them later.
pub fn prepare_extension_json(input: &model::Model, text: &str, limits: &Limits) -> Result<Value, api::Error> {
    if text.len() > crate::compiler::MAX_JSON_BYTES {
        return Err(api::Error::from_message("RESOURCE_LIMIT compiler extension JSON bytes".into()));
    }
    let spec: Extension = serde_json::from_str(text)
        .map_err(|e| api::Error::from_message(crate::compiler::json_error("compiler extension schema", e)))?;
    macro_rules! prepare {
        ($module:ident, $witness:expr) => {{
            let extension = crate::$module::prepare_unchecked_extension(input, $witness, limits)
                .map_err(api::Error::from_message)?;
            let premises: Vec<Value> = extension.premises.into_iter().map(|p| json!({
                "kind":p.kind,"expression":p.expression,"reference":p.reference
            })).collect();
            json!({"model":model::to_json(&extension.model),"premises":premises,"statistics":extension.statistics})
        }};
    }
    let result = match spec {
        Extension::Interval(w) => prepare!(interval, &w),
        Extension::Menu(w) => prepare!(menu, &w),
        Extension::Signed(w) => prepare!(signed, &w),
        Extension::Flow(w) => prepare!(flow, &w),
        Extension::Subflow(w) => prepare!(subflow, &w),
        Extension::Restricted {level, halfspace} => {
            let extension = crate::level::prepare_restricted_domain(input, level.as_ref(), halfspace.as_ref(), limits)
                .map_err(api::Error::from_message)?;
            json!({"model":model::to_json(&extension.model),"premises":[],
                   "equality_row":extension.equality_row,"statistics":extension.statistics})
        }
    };
    Ok(result)
}

pub fn prepare_extension_paths(input: impl AsRef<Path>, spec: impl AsRef<Path>, output: impl AsRef<Path>) -> Result<Value, api::Error> {
    fn path(p: &Path) -> Result<&str, api::Error> {
        p.to_str().ok_or_else(|| api::Error::from_message("INVALID non-UTF8 compiler path".into()))
    }
    let model = codec::decode_model(&api::read_input(path(input.as_ref())?)?).map_err(api::Error::from_message)?;
    let prepared = prepare_extension_json(&model, &api::read_text(path(spec.as_ref())?)?, &Limits::default())?;
    let text = serde_json::to_vec(&prepared).map_err(|e| api::Error::from_message(format!("INVALID compiler output: {e}")))?;
    api::write_output(path(output.as_ref())?, &text)?;
    Ok(json!({"status":"PREPARED","premises":prepared["premises"].as_array().map(Vec::len),
              "statistics":prepared["statistics"]}))
}
