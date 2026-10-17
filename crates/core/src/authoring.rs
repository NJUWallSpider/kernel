//! Untrusted compiler preparation over existing checked extension builders.
//! Success prepares a candidate scope; it does not establish any premise.
use crate::{
    api,
    model::{self, Expr},
    proof::{
        FlowWitness, IntervalWitness, Kind, MenuWitness, Ref, SignedWitness, SubflowWitness,
    },
    verify::Limits,
};
use serde_json::{json, Value};

pub enum Extension {
    Interval(Vec<IntervalWitness>),
    Menu(Vec<MenuWitness>),
    Signed(Vec<SignedWitness>),
    Flow(FlowWitness),
    Subflow(SubflowWitness),
}

pub struct Premise {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
}

pub struct PreparedExtension {
    pub model: model::Model,
    pub premises: Vec<Premise>,
    pub statistics: Value,
    pub layout: Value,
}

/// Return the exact kernel-created scope and old-scope proof obligations.
/// No supplied reference is accepted here: verification checks all of them later.
pub fn prepare_extension(
    input: &model::Model,
    extension: Extension,
    limits: &Limits,
) -> Result<PreparedExtension, api::Error> {
    macro_rules! prepare {
        ($module:ident, $witness:expr, $layout:ident) => {{
            let prepared = crate::$module::prepare_unchecked_extension(input, $witness, limits)
                .map_err(api::Error::from_message)?;
            let layout = $layout(input, &prepared.model, $witness)?;
            let premises = prepared
                .premises
                .into_iter()
                .map(|p| Premise {
                    kind: p.kind,
                    expression: p.expression,
                    reference: p.reference,
                })
                .collect();
            PreparedExtension {
                model: prepared.model,
                premises,
                statistics: serde_json::to_value(&prepared.statistics).map_err(|error| api::Error::from_message(format!("INVALID compiler statistics: {error}")))?,
                layout,
            }
        }};
    }
    Ok(match extension {
        Extension::Interval(w) => prepare!(interval, &w, interval_layout),
        Extension::Menu(w) => prepare!(menu, &w, menu_layout),
        Extension::Signed(w) => prepare!(signed, &w, signed_layout),
        Extension::Flow(w) => prepare!(flow, &w, flow_layout),
        Extension::Subflow(w) => prepare!(subflow, &w, subflow_layout),
    })
}

// Authoring metadata only. These cursors describe the existing frozen builder
// layouts after construction; the verifier never reads them. Bounds and final
// cursor equality are checked against the complete actual prepared model.
struct LayoutCursor {
    variable: usize,
    row: usize,
    variables: usize,
    rows: usize,
}
fn layout_error() -> api::Error {
    api::Error::from_message("INVALID compiler extension layout mismatch".into())
}
fn layout_allocation() -> api::Error {
    api::Error::from_message("RESOURCE_LIMIT compiler extension layout allocation".into())
}
impl LayoutCursor {
    fn new(input: &model::Model, prepared: &model::Model) -> Result<Self, api::Error> {
        if prepared.vars.get(..input.vars.len()) != Some(input.vars.as_slice())
            || prepared.rows.get(..input.rows.len()) != Some(input.rows.as_slice())
        {
            return Err(layout_error());
        }
        Ok(Self {
            variable: input.vars.len(),
            row: input.rows.len(),
            variables: prepared.vars.len(),
            rows: prepared.rows.len(),
        })
    }
    fn take(cursor: &mut usize, count: usize, total: usize) -> Result<Vec<usize>, api::Error> {
        let end = cursor
            .checked_add(count)
            .filter(|end| *end <= total)
            .ok_or_else(layout_error)?;
        let mut ids = Vec::new();
        ids.try_reserve_exact(count).map_err(|_| layout_allocation())?;
        ids.extend(*cursor..end);
        *cursor = end;
        Ok(ids)
    }
    fn variables(&mut self, count: usize) -> Result<Vec<usize>, api::Error> {
        Self::take(&mut self.variable, count, self.variables)
    }
    fn rows(&mut self, count: usize) -> Result<Vec<usize>, api::Error> {
        Self::take(&mut self.row, count, self.rows)
    }
    fn finish(self) -> Result<(), api::Error> {
        if self.variable != self.variables || self.row != self.rows {
            return Err(layout_error());
        }
        Ok(())
    }
}
fn layout_entries(count: usize) -> Result<Vec<Value>, api::Error> {
    let mut values = Vec::new();
    values.try_reserve_exact(count).map_err(|_| layout_allocation())?;
    Ok(values)
}
fn interval_layout(
    input: &model::Model,
    prepared: &model::Model,
    intervals: &[IntervalWitness],
) -> Result<Value, api::Error> {
    let mut cursor = LayoutCursor::new(input, prepared)?;
    let mut entries = layout_entries(intervals.len())?;
    for witness in intervals {
        let variable = cursor.variables(1)?[0];
        entries.push(json!({"variable":variable,"lower_rows":cursor.rows(witness.lower.len())?,"upper_rows":cursor.rows(witness.upper.len())?}));
    }
    cursor.finish()?;
    Ok(json!(entries))
}
fn menu_layout(
    input: &model::Model,
    prepared: &model::Model,
    menus: &[MenuWitness],
) -> Result<Value, api::Error> {
    let mut cursor = LayoutCursor::new(input, prepared)?;
    let mut entries = layout_entries(menus.len())?;
    for witness in menus {
        let options = cursor.variables(witness.maximum_index as usize + 1)?;
        let rows = cursor.rows(2)?;
        entries.push(json!({"options":options,"sum_row":rows[0],"moment_row":rows[1]}));
    }
    cursor.finish()?;
    Ok(json!(entries))
}
fn signed_layout(
    input: &model::Model,
    prepared: &model::Model,
    decompositions: &[SignedWitness],
) -> Result<Value, api::Error> {
    let mut cursor = LayoutCursor::new(input, prepared)?;
    let mut entries = layout_entries(decompositions.len())?;
    for _ in decompositions {
        let vars = cursor.variables(4)?;
        let rows = cursor.rows(4)?;
        entries.push(json!({"positive":vars[0],"negative":vars[1],"positive_activation":vars[2],"negative_activation":vars[3],
            "flow_row":rows[0],"activation_row":rows[1],"positive_capacity_row":rows[2],"negative_capacity_row":rows[3]}));
    }
    cursor.finish()?;
    Ok(json!(entries))
}
fn flow_layout(
    input: &model::Model,
    prepared: &model::Model,
    witness: &FlowWitness,
) -> Result<Value, api::Error> {
    let mut cursor = LayoutCursor::new(input, prepared)?;
    let mut entries = layout_entries(witness.groups.len())?;
    for group in &witness.groups {
        let mut commodities = layout_entries(group.commodities.len())?;
        for (sink, demand) in &group.commodities {
            commodities.push(json!({"sink":sink,"demand":demand.to_string(),"flows":cursor.variables(witness.arcs.len())?,"balance_rows":cursor.rows(witness.nodes as usize)?}));
        }
        entries.push(json!({"source":group.source,"commodities":commodities,"recovery_rows":cursor.rows(witness.arcs.len())?}));
    }
    cursor.finish()?;
    Ok(json!(entries))
}
fn subflow_layout(
    input: &model::Model,
    prepared: &model::Model,
    witness: &SubflowWitness,
) -> Result<Value, api::Error> {
    let mut cursor = LayoutCursor::new(input, prepared)?;
    let mut entries = layout_entries(witness.groups.len())?;
    for group in &witness.groups {
        entries.push(json!({"source":group.source,"flows":cursor.variables(witness.arcs.len())?,"balance_rows":cursor.rows(witness.nodes as usize)?,
            "remainder_nonnegative_rows":cursor.rows(witness.arcs.len())?}));
    }
    cursor.finish()?;
    Ok(json!(entries))
}
