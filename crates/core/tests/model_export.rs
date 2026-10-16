//! Canonical model JSON export: shape, scalar vocabulary, and round-trip
//! fidelity of `model::to_json`. Fixtures are built in code, never read from
//! `cases/`, and the reader here is local to the test on purpose: it re-reads
//! the export with `parse_q` instead of trusting any production deserializer.

use crate::codec::encode_model;
use crate::model::{parse_q, to_json, Expr, Model, Row, Var, Q};
use num_bigint::BigInt;
use num_traits::One;
use serde_json::Value;

fn q(n: i64, d: i64) -> Q {
    Q::new(n.into(), d.into())
}

/// A model that exercises every documented edge: an unbounded side, negative
/// rationals, integers, a non-integer rational, an empty expression, rows, and
/// a rational far outside f64 range.
fn fixture() -> Model {
    // 2^4000 + 1 over 3: 1205 numerator digits, ~956 denominator digits, both
    // exact and both far beyond f64 precision.
    let big = Q::new(BigInt::one() << 4000u32, BigInt::from(3));
    Model {
        name: "fixture model".into(),
        vars: vec![
            Var {
                name: "x_frac".into(),
                integer: false,
                lower: Some(q(-1, 3)),
                upper: Some(q(2, 3)),
            },
            Var {
                name: "x_unbounded".into(),
                integer: false,
                lower: None,
                upper: None,
            },
            Var {
                name: "x_int".into(),
                integer: true,
                lower: Some(q(-3, 1)),
                upper: Some(q(2, 1)),
            },
            Var {
                name: "x_big".into(),
                integer: false,
                lower: Some(big.clone()),
                upper: None,
            },
            Var {
                name: "x_zero".into(),
                integer: true,
                lower: Some(q(0, 1)),
                upper: Some(q(0, 1)),
            },
        ],
        rows: vec![
            Row {
                name: "r_empty".into(),
                expr: Expr::zero(),
                lower: None,
                upper: Some(q(5, 4)),
            },
            Row {
                name: "r_terms".into(),
                expr: Expr {
                    constant: q(0, 1),
                    terms: vec![(0, q(-3, 2)), (3, big.clone())],
                },
                lower: Some(q(1, 1)),
                upper: None,
            },
        ],
        objective: Expr {
            constant: big,
            terms: vec![(2, q(1, 1))],
        },
    }
}

fn field<'a>(value: &'a Value, key: &str) -> &'a Value {
    value
        .get(key)
        .unwrap_or_else(|| panic!("export is missing key {key:?}: {value}"))
}

fn scalar(value: &Value) -> Q {
    parse_q(
        value
            .as_str()
            .unwrap_or_else(|| panic!("scalar is not a string: {value}")),
    )
    .expect("exported scalar is not in parse_q vocabulary")
}

fn option_scalar(value: &Value) -> Option<Q> {
    if value.is_null() {
        None
    } else {
        Some(scalar(value))
    }
}

fn read_expr(value: &Value) -> Expr {
    Expr {
        constant: scalar(field(value, "constant")),
        terms: field(value, "terms")
            .as_array()
            .expect("terms is not an array")
            .iter()
            .map(|pair| {
                let pair = pair.as_array().expect("term is not a pair");
                assert_eq!(pair.len(), 2, "term pair arity");
                let id = pair[0].as_u64().expect("term index is not an integer");
                (u32::try_from(id).expect("term index fits u32"), scalar(&pair[1]))
            })
            .collect(),
    }
}

/// Test-local reader: `model::to_json` output back into a `Model`, using only
/// `parse_q` for scalars.
fn read_model(value: &Value) -> Model {
    let vars = field(value, "variables")
        .as_array()
        .expect("variables is not an array")
        .iter()
        .map(|v| Var {
            name: field(v, "name").as_str().expect("name is not a string").into(),
            integer: field(v, "integer").as_bool().expect("integer flag"),
            lower: option_scalar(field(v, "lower")),
            upper: option_scalar(field(v, "upper")),
        })
        .collect();
    let rows = field(value, "rows")
        .as_array()
        .expect("rows is not an array")
        .iter()
        .map(|r| Row {
            name: field(r, "name").as_str().expect("name is not a string").into(),
            expr: read_expr(field(r, "expr")),
            lower: option_scalar(field(r, "lower")),
            upper: option_scalar(field(r, "upper")),
        })
        .collect();
    Model {
        name: field(value, "name").as_str().expect("name is not a string").into(),
        vars,
        rows,
        objective: read_expr(field(value, "objective")),
    }
}

fn keys(value: &Value) -> Vec<String> {
    value
        .as_object()
        .expect("object")
        .keys()
        .cloned()
        .collect()
}

#[test]
fn round_trip_rebuilds_identical_model_and_encoding() {
    let model = fixture();
    let exported = to_json(&model);
    let rebuilt = read_model(&exported);
    // Exact value fidelity, including vector order, term order, and every
    // unbounded side.
    assert_eq!(rebuilt, model);
    // The rebuilt model encodes to the identical canonical bytes.
    assert_eq!(
        encode_model(&rebuilt).expect("rebuilt model encodes"),
        encode_model(&model).expect("fixture model encodes")
    );
}

#[test]
fn exported_shape_is_exactly_canonical() {
    let model = fixture();
    let exported = to_json(&model);

    // `serde_json::Value` is backed by a BTreeMap in this build, so an object's
    // key order is deterministic and sorted. The set is exactly the canonical
    // model: no key here can depend on hash iteration.
    assert_eq!(
        keys(&exported),
        ["name", "objective", "rows", "variables"]
    );
    assert_eq!(field(&exported, "name"), "fixture model");

    let variables = field(&exported, "variables").as_array().expect("variables");
    assert_eq!(variables.len(), model.vars.len());
    for (value, var) in variables.iter().zip(&model.vars) {
        assert_eq!(keys(value), ["integer", "lower", "name", "upper"]);
        assert_eq!(field(value, "name"), var.name.as_str());
        assert_eq!(field(value, "integer").as_bool(), Some(var.integer));
        assert_eq!(*field(value, "lower"), scalar_or_null(&var.lower));
        assert_eq!(*field(value, "upper"), scalar_or_null(&var.upper));
    }

    let rows = field(&exported, "rows").as_array().expect("rows");
    assert_eq!(rows.len(), model.rows.len());
    for (value, row) in rows.iter().zip(&model.rows) {
        assert_eq!(keys(value), ["expr", "lower", "name", "upper"]);
        assert_eq!(field(value, "name"), row.name.as_str());
    }

    let objective = field(&exported, "objective");
    assert_eq!(keys(objective), ["constant", "terms"]);
    assert_eq!(field(objective, "terms").as_array().map(Vec::len), Some(1));

    // Scalar leaves must be strings or null; no rational may leak out as a
    // number, a decimal, or a nested pair array.
    assert_scalar_leaves(&variables.iter().collect::<Vec<_>>());
    assert_scalar_leaves(&rows.iter().collect::<Vec<_>>());
    assert_scalar_leaves(&[objective]);
}

/// Walks the export and requires every leaf to be a string (a `parse_q`
/// scalar), a boolean, a count, or null. A rational emitted as a JSON number or
/// as a nested pair array fails here.
fn assert_scalar_leaves(nodes: &[&Value]) {
    for node in nodes {
        match node {
            Value::Object(map) => {
                for (key, value) in map {
                    match key.as_str() {
                        "constant" | "lower" | "upper" => match value {
                            Value::String(_) | Value::Null => {}
                            other => panic!("{key} is not a scalar string or null: {other}"),
                        },
                        _ => assert_scalar_leaves(&[value]),
                    }
                }
            }
            Value::Array(items) => assert_scalar_leaves(&items.iter().collect::<Vec<_>>()),
            Value::String(_) | Value::Bool(_) | Value::Number(_) | Value::Null => {}
        }
    }
}

fn scalar_or_null(side: &Option<Q>) -> Value {
    match side {
        None => Value::Null,
        Some(value) => Value::String(value.to_string()),
    }
}

#[test]
fn terms_are_index_scalar_pairs_and_empty_expression_is_empty() {
    let exported = to_json(&fixture());
    let rows = field(&exported, "rows").as_array().expect("rows");

    let empty = field(&rows[0], "expr");
    assert_eq!(field(empty, "constant"), "0");
    assert_eq!(field(empty, "terms").as_array().map(Vec::len), Some(0));

    let terms = field(&rows[1], "expr").get("terms").unwrap();
    assert_eq!(terms, &serde_json::json!([[0, "-3/2"], [3, (BigInt::one() << 4000u32).to_string() + "/3"]]));
}

#[test]
fn scalars_use_parse_q_vocabulary_families() {
    let exported = to_json(&fixture());
    let variables = field(&exported, "variables").as_array().expect("variables");

    // non-integer rational (negative): displayed as a signed fraction
    assert_eq!(
        field(&variables[0], "lower").as_str().map(parse_q),
        Some(Ok(q(-1, 3)))
    );
    // integer: displayed as a plain signed integer, no denominator
    assert_eq!(field(&variables[2], "lower").as_str(), Some("-3"));
    // zero is not null and not a decimal
    assert_eq!(field(&variables[4], "upper").as_str(), Some("0"));
    // rational far beyond f64: numerator and denominator both exact
    let big_text = field(&variables[3], "lower").as_str().expect("large scalar");
    assert!(big_text.ends_with("/3"), "{big_text}");
    let big_numer = big_text.strip_suffix("/3").expect("fraction");
    // 2^4000 + 1 needs exactly 1205 decimal digits.
    assert_eq!(big_numer.len(), 1205);
    assert_eq!(
        big_numer.parse::<BigInt>().expect("exact digits"),
        BigInt::one() << 4000u32
    );
    assert_eq!(parse_q(big_text), Ok(Q::new(BigInt::one() << 4000u32, BigInt::from(3))));
}

#[test]
fn unbounded_sides_are_json_null() {
    let exported = to_json(&fixture());
    let variables = field(&exported, "variables").as_array().expect("variables");
    assert!(field(&variables[1], "lower").is_null());
    assert!(field(&variables[1], "upper").is_null());
    let rows = field(&exported, "rows").as_array().expect("rows");
    assert!(field(&rows[0], "lower").is_null());
    assert!(field(&rows[1], "upper").is_null());
}

#[test]
fn export_is_pure_and_does_not_require_validation() {
    let model = fixture();
    let first = to_json(&model);
    let second = to_json(&model);
    assert_eq!(first, second);
    // The exact bytes are stable too, so no key or leaf depends on hash
    // iteration between calls.
    assert_eq!(
        serde_json::to_string(&first).expect("value serializes"),
        serde_json::to_string(&second).expect("value serializes")
    );
    // NOTE: no assertion here compares against `serde_json::to_value(&model)`.
    // The model's derived `Serialize` emits `Option<Q>` bounds with the default
    // num-rational representation (nested pair arrays), so it is not a canonical
    // oracle; `to_json` is the only canonical scalar form.

    // Names the binary codec rejects still export faithfully: `to_json` never
    // consults `Model::validate`.
    let unvalidated = Model {
        name: String::new(),
        vars: Vec::new(),
        rows: Vec::new(),
        objective: Expr::zero(),
    };
    let exported = to_json(&unvalidated);
    assert_eq!(field(&exported, "name"), "");
    assert_eq!(read_model(&exported), unvalidated);
    assert!(encode_model(&unvalidated).is_err());
}

#[test]
fn non_ascii_names_survive_the_export() {
    let model = Model {
        name: "caf\u{e9} modèle".into(),
        vars: vec![Var {
            name: "\u{3b1}α".into(),
            integer: false,
            lower: None,
            upper: Some(q(7, 2)),
        }],
        rows: Vec::new(),
        objective: Expr::zero(),
    };
    let exported = to_json(&model);
    let var = &field(&exported, "variables").as_array().expect("variables")[0];
    assert_eq!(field(var, "name"), "\u{3b1}α");
    assert_eq!(read_model(&exported), model);
    // The wire codec deliberately restricts names to ASCII; the export does not
    // silently inherit that restriction.
    assert!(encode_model(&model).is_err());
}
