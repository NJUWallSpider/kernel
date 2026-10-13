//! Test-only independent Fraction vectors for the isolated arithmetic prototype.
use super::Accumulator;
use crate::model::{Expr, Q, check_q};
use num_bigint::BigInt;
use num_traits::{One, Zero};
use serde_json::Value;

fn oracle() -> Value {
    serde_json::from_str(include_str!("../../../tests/vectors/rational_shortcuts_oracle.json")).unwrap()
}
fn scalar(value: &Value) -> Q {
    let parts = value.as_array().unwrap();
    let read = |v: &Value| BigInt::parse_bytes(v.as_str().unwrap().as_bytes(), 16).unwrap();
    Q::new_raw(read(&parts[0]), read(&parts[1]))
}
fn expr(value: &Value) -> Expr {
    Expr {
        constant: scalar(&value["constant"]),
        terms: value["terms"].as_array().unwrap().iter().map(|term| {
            (term[0].as_u64().unwrap() as u32, scalar(&term[1]))
        }).collect(),
    }
}
fn compare(result: Result<Expr, String>, case: &Value) {
    let name = case["name"].as_str().unwrap();
    if case["status"] == "OK" {
        assert_eq!(result.unwrap_or_else(|e| panic!("{name}: {e}")), expr(&case["expected"]), "{name}");
    } else {
        let error = result.expect_err(name);
        assert!(error.starts_with("RESOURCE_LIMIT"), "{name}: {error}");
    }
}

#[test]
fn fraction_scaled_vectors() {
    let data = oracle();
    let cases = data["scaled"].as_array().unwrap();
    assert_eq!(cases.len(), 779);
    for case in cases {
        compare(expr(&case["expr"]).scaled(&scalar(&case["scale"])), case);
    }
}

#[test]
fn fraction_accumulator_vectors() {
    let data = oracle();
    let cases = data["accumulators"].as_array().unwrap();
    assert_eq!(cases.len(), 429);
    for case in cases {
        let mut acc = Accumulator::new(scalar(&case["initial"]));
        let result = (|| {
            for add in case["adds"].as_array().unwrap() {
                acc.add(&expr(&add["expr"]), &scalar(&add["scale"]))?;
            }
            acc.finish()
        })();
        compare(result, case);
    }
}

#[test]
fn independent_raw_canonicality_and_bit_boundaries() {
    let data = oracle();
    let cases = data["raw"].as_array().unwrap();
    assert_eq!(cases.len(), 20);
    for (index, case) in cases.iter().enumerate() {
        let result = check_q(&scalar(&case["value"]));
        match case["status"].as_str().unwrap() {
            "OK" => assert!(result.is_ok(), "raw {index}: {result:?}"),
            "RESOURCE_LIMIT" => assert!(result.unwrap_err().starts_with("RESOURCE_LIMIT")),
            "INVALID" => assert!(result.is_err(), "raw {index} accepted"),
            _ => unreachable!(),
        }
    }
}

#[test]
fn shortcuts_cannot_bypass_public_malformed_expression_validation() {
    for bad in [Q::new_raw(2.into(),4.into()),Q::new_raw(1.into(),0.into()),
                Q::new_raw(1.into(),(-1).into()),Q::new_raw(0.into(),2.into())] {
        for scale in [Q::zero(),Q::one(),-Q::one()] {
            assert!(Expr {constant:bad.clone(),terms:vec![]}.scaled(&scale).is_err());
            assert!(Expr {constant:Q::zero(),terms:vec![(0,bad.clone())]}.scaled(&scale).is_err());
        }
    }
    let valid = Expr::var(0);
    for scale in [Q::new_raw(2.into(),2.into()), Q::new_raw((-2).into(),2.into())] {
        assert!(valid.scaled(&scale).is_err());
        assert!(Accumulator::new(Q::zero()).add(&valid,&scale).is_err());
    }
}

#[test]
fn vacant_zero_and_exact_cancellation_leave_no_sparse_entry() {
    let mut acc = Accumulator::new(Q::zero());
    let e = Expr {constant:Q::zero(),terms:vec![(19,Q::new(7.into(),11.into()))]};
    acc.add(&e,&Q::one()).unwrap();
    assert_eq!(acc.terms.len(),1);
    acc.add(&e,&(-Q::one())).unwrap();
    assert!(acc.terms.is_empty());
    // Private helper normally receives validated sparse expressions; still check
    // a zero product cannot create a retained zero term in a vacant bucket.
    acc.add(&Expr{constant:Q::zero(),terms:vec![(21,Q::zero())]},&Q::one()).unwrap();
    assert_eq!(acc.finish().unwrap(),Expr::zero());
}
