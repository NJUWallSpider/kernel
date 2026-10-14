//! Deterministic source rendering of the existing proof object's serde shape.
//!
//! This is deliberately a presentation layer: expression canonicality is
//! checked before using mathematical notation, while linear-proof terms keep
//! their original order, multiplicity and even zero coefficients.

use crate::model::{Q, parse_q};
use num_traits::{One, Signed, Zero};
use serde_json::{Map, Value};

const LINE_WIDTH: usize = 100;
const MIN_RUN: usize = 4;

pub(super) fn format_value(value: &Value) -> Result<String, String> {
    let object = value
        .as_object()
        .ok_or_else(|| invalid("expected certificate record"))?;
    let mut formatter = Formatter {
        output: String::new(),
    };
    formatter.record(object, Some("certificate"), 0)?;
    Ok(formatter.output)
}

fn invalid(message: &str) -> String {
    format!("INVALID RPA source output: {message}")
}

fn append(output: &mut String, text: &str) -> Result<(), String> {
    let length = output
        .len()
        .checked_add(text.len())
        .filter(|length| *length <= super::MAX_SOURCE_BYTES)
        .ok_or_else(|| "RESOURCE_LIMIT RPA source output bytes".to_string())?;
    output
        .try_reserve(length - output.len())
        .map_err(|_| "RESOURCE_LIMIT RPA source output allocation".to_string())?;
    output.push_str(text);
    Ok(())
}

fn scalar(value: &Value) -> Result<Q, String> {
    let text = value
        .as_str()
        .ok_or_else(|| invalid("expected exact scalar string"))?;
    let rational = parse_q(text).map_err(|error| {
        if error.contains("RESOURCE_LIMIT") {
            error
        } else {
            invalid(&format!("invalid exact scalar: {error}"))
        }
    })?;
    if rational.to_string() != text {
        return Err(invalid("noncanonical exact scalar"));
    }
    Ok(rational)
}

fn id(value: &Value) -> Result<u32, String> {
    value
        .as_u64()
        .and_then(|number| u32::try_from(number).ok())
        .ok_or_else(|| invalid("expected unsigned 32-bit ID"))
}

fn is_variant(name: &str) -> bool {
    matches!(
        name,
        "Lin"
            | "Round"
            | "Drop"
            | "EqPair"
            | "Cases"
            | "Plotkin"
            | "Witness"
            | "Absurd"
            | "SubflowLift"
            | "ImproveReturn"
            | "PositiveRefutation"
            | "SignedLift"
            | "MenuLift"
            | "IntervalLift"
            | "FlowLift"
            | "Return"
            | "Split"
            | "Constant"
            | "Predicate"
            | "ImageExclusion"
            | "Feasible"
            | "Strictness"
            | "FiberStrictness"
    )
}

fn variant_record<'a>(
    name: &str,
    value: &'a Value,
) -> Result<Option<&'a Map<String, Value>>, String> {
    // Absurd is both a derivation's reference newtype and a block-ending
    // record. Its serde payload distinguishes those two forms exactly.
    if matches!(name, "Witness" | "Absurd") && reference(value)?.is_some() {
        Ok(None)
    } else {
        Ok(value.as_object())
    }
}

fn reference(value: &Value) -> Result<Option<String>, String> {
    if value.as_str() == Some("Exact") {
        return Ok(Some("exact".into()));
    }
    let Some(object) = value.as_object().filter(|object| object.len() == 1) else {
        return Ok(None);
    };
    let (name, number) = object.iter().next().unwrap();
    let label = match name.as_str() {
        "VarLower" => "lower",
        "VarUpper" => "upper",
        "VarInt" => "integer",
        "RowLower" => "row_lower",
        "RowUpper" => "row_upper",
        "RowEq" => "row_eq",
        "Local" => "local",
        "Assumption" => "assumption",
        _ => return Ok(None),
    };
    let number = id(number)?;
    let source = if name == "Local" {
        format!("f{number}")
    } else if name.starts_with("Var") {
        format!("{label}(x{number})")
    } else {
        format!("{label}({number})")
    };
    Ok(Some(source))
}

/// Write one signed summand without combining or discarding any terms.
fn summand(output: &mut String, coefficient: &Q, factor: Option<&str>) -> Result<(), String> {
    let negative = coefficient.is_negative();
    if output.is_empty() {
        if negative {
            append(output, "-")?;
        }
    } else {
        append(output, if negative { " - " } else { " + " })?;
    }
    let magnitude = coefficient.abs();
    if let Some(factor) = factor {
        if !magnitude.is_one() {
            append(output, &magnitude.to_string())?;
            append(output, "*")?;
        }
        append(output, factor)?;
    } else {
        append(output, &magnitude.to_string())?;
    }
    Ok(())
}

fn expression(object: &Map<String, Value>) -> Result<Option<String>, String> {
    if object.len() != 2 || !object.contains_key("constant") || !object.contains_key("terms") {
        return Ok(None);
    }
    let constant = scalar(&object["constant"])?;
    let terms = object["terms"]
        .as_array()
        .ok_or_else(|| invalid("expected expression terms"))?;
    let mut math = String::new();
    if !constant.is_zero() || terms.is_empty() {
        summand(&mut math, &constant, None)?;
    }
    let mut previous = None;
    for term in terms {
        let pair = term
            .as_array()
            .filter(|pair| pair.len() == 2)
            .ok_or_else(|| invalid("expected expression coordinate/coefficient pair"))?;
        let coordinate = id(&pair[0])?;
        let coefficient = scalar(&pair[1])?;
        if coefficient.is_zero() || previous.is_some_and(|previous| previous >= coordinate) {
            return Err(invalid("noncanonical expression terms"));
        }
        previous = Some(coordinate);
        summand(&mut math, &coefficient, Some(&format!("x{coordinate}")))?;
    }
    let mut output = String::from("expr(");
    append(&mut output, &math)?;
    append(&mut output, ")")?;
    Ok(Some(output))
}

fn has_fields(object: &Map<String, Value>, fields: &[&str]) -> bool {
    object.len() == fields.len() && fields.iter().all(|field| object.contains_key(*field))
}

fn proof_step(object: &Map<String, Value>) -> Result<Option<String>, String> {
    if object.len() != 1 {
        return Ok(None);
    }
    let (name, value) = object.iter().next().unwrap();
    let Some(payload) = value.as_object() else {
        return Ok(None);
    };
    match name.as_str() {
        "Lin" if has_fields(payload, &["id", "kind", "constant", "terms"]) => {
            let kind = match payload["kind"].as_str() {
                Some("Eq") => "eq",
                Some("Le") => "le",
                Some("Int") => "int",
                _ => return Err(invalid("unknown linear proof kind")),
            };
            let mut output = format!("lin.{kind}(f{}, ", id(&payload["id"])?);
            let constant = scalar(&payload["constant"])?;
            let terms = payload["terms"]
                .as_array()
                .ok_or_else(|| invalid("expected linear proof terms"))?;
            let mut math = String::new();
            for term in terms {
                let pair = term
                    .as_array()
                    .filter(|pair| pair.len() == 2)
                    .ok_or_else(|| invalid("expected reference/coefficient pair"))?;
                let fact =
                    reference(&pair[0])?.ok_or_else(|| invalid("expected proof reference"))?;
                summand(&mut math, &scalar(&pair[1])?, Some(&fact))?;
            }
            if !constant.is_zero() || terms.is_empty() {
                summand(&mut math, &constant, None)?;
            }
            append(&mut output, &math)?;
            append(&mut output, ")")?;
            Ok(Some(output))
        }
        "Round" if has_fields(payload, &["id", "le", "integer"]) => {
            let le = reference(&payload["le"])?
                .ok_or_else(|| invalid("expected rounding inequality reference"))?;
            let integer = reference(&payload["integer"])?
                .ok_or_else(|| invalid("expected rounding integer reference"))?;
            Ok(Some(format!(
                "round(f{}, {le}, {integer})",
                id(&payload["id"])?
            )))
        }
        "Drop" if has_fields(payload, &["ids"]) => {
            let ids = payload["ids"]
                .as_array()
                .ok_or_else(|| invalid("expected dropped IDs"))?;
            let mut output = String::from("drop(");
            for (index, value) in ids.iter().enumerate() {
                if index > 0 {
                    append(&mut output, ", ")?;
                }
                append(&mut output, &format!("f{}", id(value)?))?;
            }
            append(&mut output, ")")?;
            Ok(Some(output))
        }
        _ => Ok(None),
    }
}

fn atom(value: &Value) -> Result<Option<String>, String> {
    if let Some(source) = reference(value)? {
        return Ok(Some(source));
    }
    match value {
        Value::Null => Ok(Some("null".into())),
        Value::Bool(boolean) => Ok(Some(boolean.to_string())),
        Value::Number(number) => Ok(Some(number.to_string())),
        Value::String(text) => {
            if matches!(
                text.as_str(),
                "None" | "Equal" | "NonIncreasing" | "Le" | "Eq" | "Int"
            ) {
                return Ok(Some(text.clone()));
            }
            if parse_q(text).is_ok()
                || (!text.is_empty()
                    && text
                        .bytes()
                        .all(|byte| byte.is_ascii_digit() || matches!(byte, b'+' | b'-' | b'/')))
            {
                scalar(value)?;
                return Ok(Some(format!("q({text})")));
            }
            Ok(Some(
                serde_json::to_string(text).map_err(|error| invalid(&error.to_string()))?,
            ))
        }
        Value::Object(object) => {
            if let Some(source) = expression(object)? {
                return Ok(Some(source));
            }
            proof_step(object)
        }
        Value::Array(_) => Ok(None),
    }
}

// Field priority follows proof structure instead of serde_json's lexical map
// order. Unknown future fields retain a deterministic lexical order afterward.
fn ordered_fields(object: &Map<String, Value>) -> Vec<(&str, &Value)> {
    const ORDER: &[&str] = &[
        "claims",
        "blocks",
        "improvements",
        "bijections",
        "points",
        "claim",
        "block",
        "injectivity",
        "values",
        "refutation",
        "reverse",
        "input_integers",
        "output_integers",
        "objective",
        "projection",
        "affine_projection",
        "inverse",
        "input_objective_lower",
        "input_objective_level",
        "input_halfspace",
        "target",
        "integers",
        "positive",
        "point_in_target",
        "inclusion_claim",
        "forward_claim",
        "reverse_claim",
        "steps",
        "end",
        "id",
        "kind",
        "constant",
        "terms",
        "expression",
        "split",
        "integer",
        "le",
        "positive",
        "negative",
        "ids",
        "bits",
        "distance",
        "variables",
        "cliques",
        "map",
        "checks",
        "margin",
        "fact",
        "witness",
        "intervals",
        "menus",
        "decompositions",
        "body",
        "nodes",
        "arcs",
        "groups",
        "source",
        "commodities",
        "demands",
        "flows",
        "nonnegative",
        "balances",
        "lower",
        "upper",
        "maximum_index",
        "capacity",
        "flow",
        "activation",
        "index",
        "left",
        "right",
    ];
    let mut fields: Vec<_> = object
        .iter()
        .map(|(name, value)| (name.as_str(), value))
        .collect();
    if fields
        .iter()
        .all(|(name, _)| name.contains('.') || name.contains('['))
    {
        let family = |name: &str| {
            [
                "variable[",
                "row[",
                "objective.",
                "projection[",
                "affine_projection[",
                "inverse.coordinate[",
                "inverse.objective_level",
                "input.objective_lower",
                "bijection[",
                "injectivity.coordinate[",
            ]
            .iter()
            .position(|prefix| name.starts_with(prefix))
            .unwrap_or(10)
        };
        fields.sort_by(|(left, _), (right, _)| {
            family(left)
                .cmp(&family(right))
                .then_with(|| left.cmp(right))
        });
        return fields;
    }
    fields.sort_by(|(left, _), (right, _)| {
        let priority = |name: &str| {
            ORDER
                .iter()
                .position(|field| *field == name)
                .unwrap_or(ORDER.len())
        };
        priority(left)
            .cmp(&priority(right))
            .then_with(|| left.cmp(right))
    });
    fields
}

enum Segment<'a> {
    Value(&'a Value),
    Macro(String),
    Repeat(usize, &'a Value),
}

fn identity_coordinate(value: &Value) -> Option<u32> {
    let object = value.as_object()?;
    if object.len() != 2 || object.get("constant")?.as_str()? != "0" {
        return None;
    }
    let terms = object.get("terms")?.as_array()?;
    let pair = terms.first()?.as_array()?;
    if terms.len() != 1 || pair.len() != 2 || pair[1].as_str()? != "1" {
        return None;
    }
    id(&pair[0]).ok()
}

fn numeric_pair(value: &Value) -> Option<(u32, u32)> {
    let pair = value.as_array().filter(|pair| pair.len() == 2)?;
    Some((id(&pair[0]).ok()?, id(&pair[1]).ok()?))
}

fn run_length<T: Copy + PartialEq>(
    values: &[Value],
    start: usize,
    first: T,
    read: impl Fn(&Value) -> Option<T>,
    advance: impl Fn(T, usize) -> Option<T>,
) -> usize {
    values[start..]
        .iter()
        .enumerate()
        .take_while(|(offset, value)| {
            advance(first, *offset).is_some_and(|expected| read(value) == Some(expected))
        })
        .count()
}

fn segment(values: &[Value], index: usize) -> (usize, Segment<'_>) {
    let value = &values[index];
    let advance = |start: u32, offset: usize| {
        u32::try_from(offset)
            .ok()
            .and_then(|offset| start.checked_add(offset))
    };
    if let Some(start) = identity_coordinate(value) {
        let count = run_length(values, index, start, identity_coordinate, advance);
        if count >= MIN_RUN {
            return (count, Segment::Macro(format!("identity({start}, {count})")));
        }
    }
    if let Ok(start) = id(value) {
        let count = run_length(values, index, start, |value| id(value).ok(), advance);
        if count >= MIN_RUN {
            return (count, Segment::Macro(format!("range({start}, {count})")));
        }
    }
    if let Some((input, output)) = numeric_pair(value) {
        let count = run_length(
            values,
            index,
            (input, output),
            numeric_pair,
            |(input, output), offset| Some((advance(input, offset)?, advance(output, offset)?)),
        );
        if count >= MIN_RUN {
            return (
                count,
                Segment::Macro(format!("pairs({input}, {output}, {count})")),
            );
        }
    }
    let count = values[index..]
        .iter()
        .take_while(|candidate| *candidate == value)
        .count();
    if count >= MIN_RUN {
        return (count, Segment::Repeat(count, value));
    }
    (1, Segment::Value(value))
}

fn push_inline(output: &mut String, text: &str, width: usize) -> bool {
    if output.len().saturating_add(text.len()) > width {
        return false;
    }
    output.push_str(text);
    true
}

fn inline(value: &Value, depth: usize, width: usize) -> Result<Option<String>, String> {
    if depth > super::MAX_SOURCE_DEPTH {
        return Err("RESOURCE_LIMIT RPA source output nesting".into());
    }
    if let Some(source) = atom(value)? {
        return Ok((source.len() <= width).then_some(source));
    }
    let mut output = String::new();
    match value {
        Value::Array(values) => {
            if !push_inline(&mut output, "[", width) {
                return Ok(None);
            }
            let mut index = 0;
            while index < values.len() {
                if index > 0 && !push_inline(&mut output, ", ", width) {
                    return Ok(None);
                }
                let (count, item) = segment(values, index);
                let item = inline_segment(&item, depth + 1, width.saturating_sub(output.len()))?;
                let Some(item) = item else {
                    return Ok(None);
                };
                if !push_inline(&mut output, &item, width) {
                    return Ok(None);
                }
                index += count;
            }
            if !push_inline(&mut output, "]", width) {
                return Ok(None);
            }
        }
        Value::Object(object) => {
            if object.len() == 1 {
                let (name, value) = object.iter().next().unwrap();
                if is_variant(name) {
                    if let Some(record) = variant_record(name, value)? {
                        return inline_record(record, Some(name), depth, width);
                    }
                    let Some(value) =
                        inline(value, depth + 1, width.saturating_sub(name.len() + 2))?
                    else {
                        return Ok(None);
                    };
                    let source = format!("{name}({value})");
                    return Ok((source.len() <= width).then_some(source));
                }
            }
            return inline_record(object, None, depth, width);
        }
        _ => unreachable!("all literals are atoms"),
    }
    Ok(Some(output))
}

fn inline_segment(
    segment: &Segment<'_>,
    depth: usize,
    width: usize,
) -> Result<Option<String>, String> {
    match segment {
        Segment::Value(value) => inline(value, depth, width),
        Segment::Macro(source) => Ok((source.len() <= width).then(|| source.clone())),
        Segment::Repeat(count, value) => {
            let prefix = format!("repeat({count}, ");
            let Some(value) = inline(value, depth, width.saturating_sub(prefix.len() + 1))? else {
                return Ok(None);
            };
            let source = format!("{prefix}{value})");
            Ok((source.len() <= width).then_some(source))
        }
    }
}

fn inline_record(
    object: &Map<String, Value>,
    tag: Option<&str>,
    depth: usize,
    width: usize,
) -> Result<Option<String>, String> {
    // Show each named proof obligation on its own line, including small sets.
    if object.get("checks").is_some_and(Value::is_object)
        || object
            .keys()
            .any(|key| key.contains('.') || key.contains('['))
    {
        return Ok(None);
    }
    let mut output = tag.map_or_else(String::new, |tag| format!("{tag} "));
    if !push_inline(&mut output, "{", width) {
        return Ok(None);
    }
    if !object.is_empty() && !push_inline(&mut output, " ", width) {
        return Ok(None);
    }
    for (index, (name, value)) in ordered_fields(object).into_iter().enumerate() {
        if index > 0 && !push_inline(&mut output, ", ", width) {
            return Ok(None);
        }
        if !push_inline(&mut output, name, width) || !push_inline(&mut output, ": ", width) {
            return Ok(None);
        }
        let Some(value) = inline(value, depth + 1, width.saturating_sub(output.len()))? else {
            return Ok(None);
        };
        if !push_inline(&mut output, &value, width) {
            return Ok(None);
        }
    }
    if !object.is_empty() && !push_inline(&mut output, " ", width) {
        return Ok(None);
    }
    if !push_inline(&mut output, "}", width) {
        return Ok(None);
    }
    Ok(Some(output))
}

struct Formatter {
    output: String,
}

impl Formatter {
    fn text(&mut self, text: &str) -> Result<(), String> {
        append(&mut self.output, text)
    }

    fn newline(&mut self, depth: usize) -> Result<(), String> {
        self.text("\n")?;
        self.text(&"  ".repeat(depth))
    }

    fn value(&mut self, value: &Value, depth: usize) -> Result<(), String> {
        if depth > super::MAX_SOURCE_DEPTH {
            return Err("RESOURCE_LIMIT RPA source output nesting".into());
        }
        let width = LINE_WIDTH.saturating_sub(depth.saturating_mul(2));
        if let Some(source) = inline(value, depth, width)? {
            return self.text(&source);
        }
        // Exact affine expressions and proof instructions may exceed the soft
        // line width; they remain one complete, unambiguous source expression.
        if let Some(source) = atom(value)? {
            return self.text(&source);
        }
        match value {
            Value::Array(values) => {
                self.text("[")?;
                let mut index = 0;
                while index < values.len() {
                    self.newline(depth + 1)?;
                    let (count, item) = segment(values, index);
                    self.item(&item, depth + 1)?;
                    self.text(",")?;
                    index += count;
                }
                self.newline(depth)?;
                self.text("]")
            }
            Value::Object(object) => {
                if object.len() == 1 {
                    let (name, value) = object.iter().next().unwrap();
                    if is_variant(name) {
                        if let Some(record) = variant_record(name, value)? {
                            return self.record(record, Some(name), depth);
                        }
                        self.text(name)?;
                        self.text("(")?;
                        self.value(value, depth + 1)?;
                        return self.text(")");
                    }
                }
                self.record(object, None, depth)
            }
            _ => unreachable!("all literals are atoms"),
        }
    }

    fn item(&mut self, item: &Segment<'_>, depth: usize) -> Result<(), String> {
        match item {
            Segment::Value(value) => self.value(value, depth),
            Segment::Macro(source) => self.text(source),
            Segment::Repeat(count, value) => {
                self.text(&format!("repeat({count}, "))?;
                self.value(value, depth)?;
                self.text(")")
            }
        }
    }

    fn record(
        &mut self,
        object: &Map<String, Value>,
        tag: Option<&str>,
        depth: usize,
    ) -> Result<(), String> {
        if depth > super::MAX_SOURCE_DEPTH {
            return Err("RESOURCE_LIMIT RPA source output nesting".into());
        }
        if let Some(tag) = tag {
            self.text(tag)?;
            self.text(" ")?;
        }
        self.text("{")?;
        for (name, value) in ordered_fields(object) {
            self.newline(depth + 1)?;
            self.text(name)?;
            self.text(if name == "checks" && value.is_object() {
                " "
            } else {
                ": "
            })?;
            self.value(value, depth + 1)?;
            self.text(",")?;
        }
        if !object.is_empty() {
            self.newline(depth)?;
        }
        self.text("}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn renders_math_and_preserves_linear_proof_term_order() {
        let certificate = json!({"claims": [], "blocks": [{"steps": [
            {"Lin": {"id": 7, "kind": "Eq", "constant": "1/3", "terms": [
                [{"RowEq": 0}, "-1"], [{"VarLower": 0}, "2"], [{"RowEq": 0}, "0"]
            ]}}, {"Round": {"id": 8, "le": {"Local": 7}, "integer": {"VarInt": 0}}},
            {"Drop": {"ids": [7, 8]}}
        ], "end": {"Return": {"map": [{"constant": "1", "terms": [[0, "-2"]]}], "checks": ["Exact"]}}}]});
        let source = format_value(&certificate).unwrap();
        assert!(source.starts_with("certificate {\n  claims: []"));
        assert!(source.contains("lin.eq(f7, -row_eq(0) + 2*lower(x0) + 0*row_eq(0) + 1/3)"));
        assert!(source.contains("round(f8, f7, integer(x0))"));
        assert!(source.contains("drop(f7, f8)"));
        assert!(source.contains("expr(1 - 2*x0)"));
    }

    #[test]
    fn rejects_expression_data_that_math_notation_would_normalize() {
        for terms in [
            json!([[0, "0"]]),
            json!([[0, "1"], [0, "2"]]),
            json!([[2, "1"], [1, "1"]]),
        ] {
            assert!(
                format_value(&json!({"claims": [], "blocks": [{"constant": "0", "terms": terms}]}))
                    .is_err()
            );
        }
    }

    #[test]
    fn compresses_exact_runs_without_consuming_neighboring_data() {
        let certificate = json!({"claims": [{"projection": [[2, 3], [3, 4], [4, 5], [5, 6], [9, 8]]}], "blocks": [{
            "steps": [], "end": {"Return": {"map": [
                {"constant": "0", "terms": [[4, "1"]]}, {"constant": "0", "terms": [[5, "1"]]},
                {"constant": "0", "terms": [[6, "1"]]}, {"constant": "0", "terms": [[7, "1"]]}
            ], "checks": ["Exact", "Exact", "Exact", "Exact", {"Local": 5}]}}
        }], "other": [3, 4, 5, 6, 9]});
        let source = format_value(&certificate).unwrap();
        assert!(source.contains("[pairs(2, 3, 4), [9, 8]]"));
        assert!(source.contains("[identity(4, 4)]"));
        assert!(source.contains("[repeat(4, exact), f5]"));
        assert!(source.contains("[range(3, 4), 9]"));
    }
}
