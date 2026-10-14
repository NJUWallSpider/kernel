//! Bind source-level obligation names to the frozen verifier's check order.
//! Names select obligations, never create evidence or authorize acceptance.
use crate::{
    model::Model,
    proof::{BijectionClaim, Claim, Objective},
};
use serde_json::{Map, Value};
use std::collections::HashMap;

use super::{MAX_EXPANDED_NODES, MAX_SOURCE_BYTES, MAX_SOURCE_DEPTH};

fn invalid(message: impl std::fmt::Display) -> String {
    format!("INVALID RPA source named checks: {message}")
}

pub(super) fn contains_named(value: &Value) -> bool {
    match value {
        Value::Object(fields) => fields
            .iter()
            .any(|(key, value)| (key == "checks" && value.is_object()) || contains_named(value)),
        Value::Array(values) => values.iter().any(contains_named),
        _ => false,
    }
}

struct Label {
    numeric: String,
    named: Option<String>,
}
#[derive(Default)]
struct Layout {
    labels: Vec<Label>,
    bytes: usize,
}
impl Layout {
    fn push(&mut self, numeric: String, named: Option<String>) -> Result<(), String> {
        self.bytes = self
            .bytes
            .checked_add(numeric.len())
            .and_then(|n| n.checked_add(named.as_ref().map_or(0, String::len)))
            .filter(|n| *n <= MAX_SOURCE_BYTES)
            .ok_or_else(|| "RESOURCE_LIMIT RPA source obligation name bytes".to_string())?;
        if self.labels.len() >= MAX_EXPANDED_NODES {
            return Err("RESOURCE_LIMIT RPA source obligation count".into());
        }
        self.labels
            .try_reserve(1)
            .map_err(|_| "RESOURCE_LIMIT RPA source obligation allocation")?;
        self.labels.push(Label { numeric, named });
        Ok(())
    }
    fn indexed(
        &mut self,
        prefix: &str,
        index: usize,
        name: &str,
        suffix: &str,
    ) -> Result<(), String> {
        let quoted = serde_json::to_string(name).map_err(|e| invalid(e))?;
        self.push(
            format!("{prefix}[{index}]{suffix}"),
            Some(format!("{prefix}[{quoted}]{suffix}")),
        )
    }
    fn plain(&mut self, name: impl Into<String>) -> Result<(), String> {
        self.push(name.into(), None)
    }
}

struct Contracts {
    claims: Vec<Claim>,
    pairs: Vec<BijectionClaim>,
}
fn contracts(value: &Value) -> Result<Contracts, String> {
    let claims = serde_json::from_value(
        value
            .get("claims")
            .cloned()
            .ok_or_else(|| invalid("missing claims"))?,
    )
    .map_err(|e| super::classify_schema_error(e.to_string()))?;
    let mut pairs = Vec::new();
    if let Some(values) = value.get("bijections") {
        for witness in values
            .as_array()
            .ok_or_else(|| invalid("bijections must be an array"))?
        {
            let claim = witness
                .get("claim")
                .ok_or_else(|| invalid("missing bijection claim"))?;
            pairs
                .try_reserve(1)
                .map_err(|_| "RESOURCE_LIMIT RPA source bijection allocation")?;
            pairs.push(serde_json::from_value(claim.clone()).map_err(|e| invalid(e))?);
        }
    }
    Ok(Contracts { claims, pairs })
}

fn feasibility(layout: &mut Layout, output: &Model, integers: bool) -> Result<(), String> {
    for (index, variable) in output.vars.iter().enumerate() {
        if variable.lower.is_some() {
            layout.indexed("variable", index, &variable.name, ".lower")?;
        }
        if variable.upper.is_some() {
            layout.indexed("variable", index, &variable.name, ".upper")?;
        }
        if variable.integer && integers {
            layout.indexed("variable", index, &variable.name, ".integer")?;
        }
    }
    for (index, row) in output.rows.iter().enumerate() {
        if row.lower.is_some() && row.lower == row.upper {
            layout.indexed("row", index, &row.name, ".equal")?;
        } else {
            if row.lower.is_some() {
                layout.indexed("row", index, &row.name, ".lower")?;
            }
            if row.upper.is_some() {
                layout.indexed("row", index, &row.name, ".upper")?;
            }
        }
    }
    Ok(())
}

fn directional(
    meta: &Contracts,
    index: usize,
    source: &Model,
    target: &Model,
) -> Result<Layout, String> {
    let claim = &meta.claims[index];
    let (input, output) = if claim.reverse {
        (target, source)
    } else {
        (source, target)
    };
    let mut layout = Layout::default();
    feasibility(&mut layout, output, claim.output_integers)?;
    match claim.objective {
        Objective::None => {}
        Objective::Equal => layout.plain("objective.equal")?,
        Objective::NonIncreasing => layout.plain("objective.non_increasing")?,
    }
    for i in 0..claim.projection.len() {
        layout.plain(format!("projection[{i}]"))?;
    }
    for i in 0..claim.affine_projection.len() {
        layout.plain(format!("affine_projection[{i}]"))?;
    }
    if let Some(other) = claim.inverse {
        let inverse = meta
            .claims
            .get(other as usize)
            .ok_or_else(|| invalid("inverse claim index out of range"))?;
        for (i, variable) in input.vars.iter().enumerate() {
            layout.indexed("inverse.coordinate", i, &variable.name, "")?;
        }
        if inverse.input_objective_level.is_some() {
            layout.plain("inverse.objective_level")?;
        }
    }
    if claim.input_objective_lower.is_some() {
        layout.plain("input.objective_lower")?;
    }
    for (pair_index, pair) in meta.pairs.iter().enumerate() {
        if pair.reverse_claim as usize != index {
            continue;
        }
        let forward = meta
            .claims
            .get(pair.forward_claim as usize)
            .ok_or_else(|| invalid("bijection forward index out of range"))?;
        let output = if forward.reverse { source } else { target };
        for (i, variable) in output.vars.iter().enumerate() {
            layout.indexed(
                &format!("bijection[{pair_index}].coordinate"),
                i,
                &variable.name,
                "",
            )?;
        }
    }
    Ok(layout)
}

#[derive(Clone, Copy)]
pub(super) enum Mode {
    Lower,
    Name,
}

fn bind(
    checks: &mut Value,
    layout: &Layout,
    mode: Mode,
    location: &str,
    name_bytes: &mut usize,
) -> Result<(), String> {
    match mode {
        Mode::Lower if checks.is_object() => {
            let mut index = HashMap::new();
            index
                .try_reserve(layout.labels.len().saturating_mul(2))
                .map_err(|_| "RESOURCE_LIMIT RPA source obligation index allocation")?;
            for (i, label) in layout.labels.iter().enumerate() {
                index.insert(label.numeric.as_str(), i);
                if let Some(name) = &label.named {
                    index.insert(name.as_str(), i);
                }
            }
            let mut ordered = Vec::new();
            ordered
                .try_reserve_exact(layout.labels.len())
                .map_err(|_| "RESOURCE_LIMIT RPA source check allocation")?;
            ordered.resize_with(layout.labels.len(), || None);
            let Value::Object(fields) = std::mem::take(checks) else {
                unreachable!()
            };
            for (name, reference) in fields {
                let Some(&i) = index.get(name.as_str()) else {
                    return Err(invalid(format!(
                        "{location}: unknown or inapplicable obligation {name}"
                    )));
                };
                if ordered[i].replace(reference).is_some() {
                    return Err(invalid(format!(
                        "{location}: duplicate obligation {}",
                        layout.labels[i].numeric
                    )));
                }
            }
            let mut values = Vec::new();
            values
                .try_reserve_exact(ordered.len())
                .map_err(|_| "RESOURCE_LIMIT RPA source check allocation")?;
            for (i, reference) in ordered.into_iter().enumerate() {
                values.push(reference.ok_or_else(|| {
                    invalid(format!(
                        "{location}: missing obligation {}",
                        layout.labels[i]
                            .named
                            .as_ref()
                            .unwrap_or(&layout.labels[i].numeric)
                    ))
                })?);
            }
            *checks = Value::Array(values);
        }
        Mode::Name => {
            let values = checks.as_array().ok_or_else(|| {
                invalid(format!(
                    "{location}: expected positional certificate checks"
                ))
            })?;
            if values.len() != layout.labels.len() {
                return Err(invalid(format!(
                    "{location}: expected {} obligations, got {}",
                    layout.labels.len(),
                    values.len()
                )));
            }
            // Bound all added field names across the entire certificate before
            // allocating the next map. The original JSON bytes are charged too.
            for label in &layout.labels {
                let key = label.named.as_ref().unwrap_or(&label.numeric);
                let bytes = serde_json::to_string(key).map_err(|e| invalid(e))?.len() + 1;
                *name_bytes = name_bytes
                    .checked_add(bytes)
                    .filter(|n| *n <= MAX_SOURCE_BYTES)
                    .ok_or_else(|| "RESOURCE_LIMIT RPA source named output bytes".to_string())?;
            }
            let Value::Array(values) = std::mem::take(checks) else {
                unreachable!()
            };
            let mut fields = Map::new();
            for (reference, label) in values.into_iter().zip(&layout.labels) {
                fields.insert(
                    label.named.as_ref().unwrap_or(&label.numeric).clone(),
                    reference,
                );
            }
            *checks = Value::Object(fields);
        }
        _ => {} // Existing explicitly positional arrays remain accepted.
    }
    Ok(())
}

fn visit_block(
    block: &mut Value,
    layout: &Layout,
    mode: Mode,
    location: &str,
    depth: usize,
    name_bytes: &mut usize,
) -> Result<(), String> {
    if depth > MAX_SOURCE_DEPTH {
        return Err("RESOURCE_LIMIT RPA source named block depth".into());
    }
    let end = block
        .get_mut("end")
        .and_then(Value::as_object_mut)
        .ok_or_else(|| invalid(format!("{location}: missing block end")))?;
    if end.len() != 1 {
        return Err(invalid(format!(
            "{location}: expected one terminal variant"
        )));
    }
    let (variant, payload) = end.iter_mut().next().unwrap();
    match variant.as_str() {
        "Return" | "ImproveReturn" => {
            let checks = payload
                .get_mut("checks")
                .ok_or_else(|| invalid(format!("{location}: missing checks")))?;
            bind(checks, layout, mode, location, name_bytes)
        }
        "Split" => {
            for branch in ["left", "right"] {
                let child = payload
                    .get_mut(branch)
                    .ok_or_else(|| invalid(format!("{location}: missing {branch} block")))?;
                visit_block(
                    child,
                    layout,
                    mode,
                    &format!("{location}.{branch}"),
                    depth + 1,
                    name_bytes,
                )?;
            }
            Ok(())
        }
        "FlowLift" | "IntervalLift" | "MenuLift" | "SignedLift" | "SubflowLift" => {
            let child = payload
                .get_mut("body")
                .ok_or_else(|| invalid(format!("{location}: missing lift body")))?;
            visit_block(
                child,
                layout,
                mode,
                &format!("{location}.body"),
                depth + 1,
                name_bytes,
            )
        }
        _ => Ok(()),
    }
}

pub(super) fn transform(
    value: &mut Value,
    source: &Model,
    target: &Model,
    mode: Mode,
) -> Result<(), String> {
    let mut name_bytes = if matches!(mode, Mode::Name) {
        super::expanded_bytes(value)?
    } else {
        0
    };
    source.validate().map_err(|e| {
        if e.starts_with("RESOURCE_LIMIT") {
            e
        } else {
            invalid(e)
        }
    })?;
    target.validate().map_err(|e| {
        if e.starts_with("RESOURCE_LIMIT") {
            e
        } else {
            invalid(e)
        }
    })?;
    let meta = contracts(value)?;
    let blocks = value
        .get_mut("blocks")
        .and_then(Value::as_array_mut)
        .ok_or_else(|| invalid("missing blocks"))?;
    if blocks.len() != meta.claims.len() {
        return Err(invalid("claim/block count mismatch"));
    }
    for (index, block) in blocks.iter_mut().enumerate() {
        let layout = directional(&meta, index, source, target)?;
        visit_block(
            block,
            &layout,
            mode,
            &format!("claim[{index}]"),
            1,
            &mut name_bytes,
        )?;
    }
    if let Some(witnesses) = value.get_mut("bijections").and_then(Value::as_array_mut) {
        for (index, (witness, pair)) in witnesses.iter_mut().zip(&meta.pairs).enumerate() {
            let forward = meta
                .claims
                .get(pair.forward_claim as usize)
                .ok_or_else(|| invalid("bijection forward index out of range"))?;
            let input = if forward.reverse { target } else { source };
            let mut layout = Layout::default();
            for (i, variable) in input.vars.iter().enumerate() {
                layout.indexed("injectivity.coordinate", i, &variable.name, "")?;
            }
            let checks = witness
                .get_mut("injectivity")
                .and_then(|p| p.get_mut("checks"))
                .ok_or_else(|| invalid("missing injectivity checks"))?;
            bind(
                checks,
                &layout,
                mode,
                &format!("bijection[{index}].injectivity"),
                &mut name_bytes,
            )?;
        }
    }
    if let Some(witnesses) = value.get_mut("improvements").and_then(Value::as_array_mut) {
        for (index, witness) in witnesses.iter_mut().enumerate() {
            let claim: crate::proof::ImprovementClaim = serde_json::from_value(
                witness
                    .get("claim")
                    .cloned()
                    .ok_or_else(|| invalid("missing improvement claim"))?,
            )
            .map_err(|e| super::classify_schema_error(e.to_string()))?;
            let output = if claim.target { target } else { source };
            let mut layout = Layout::default();
            feasibility(&mut layout, output, claim.integers)?;
            layout.plain("objective.improve")?;
            let block = witness
                .get_mut("block")
                .ok_or_else(|| invalid("missing improvement block"))?;
            visit_block(
                block,
                &layout,
                mode,
                &format!("improvement[{index}]"),
                1,
                &mut name_bytes,
            )?;
        }
    }
    Ok(())
}
