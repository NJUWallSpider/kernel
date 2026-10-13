use kernel_core::interval::prepare_unchecked_extension;
use kernel_core::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, MAX_ROWS, Q};
use kernel_core::point::verify_points;
use kernel_core::proof::{
    Certificate, IntervalWitness, Kind, PointClaim, PointWitness, Ref, Request,
};
use kernel_core::verify::Limits;
use num_bigint::BigInt;
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn expr(c: &str, terms: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(c),
        terms: terms.iter().map(|(i, v)| (*i, q(v))).collect(),
    }
}
fn model(n: usize) -> Model {
    Model {
        name: "interval-builder".into(),
        vars: (0..n)
            .map(|i| Var {
                name: format!("x{i}"),
                integer: false,
                lower: None,
                upper: None,
            })
            .collect(),
        rows: vec![],
        objective: Expr::zero(),
    }
}
fn eval(e: &Expr, values: &[Q]) -> Q {
    e.terms.iter().fold(e.constant.clone(), |sum, (i, c)| {
        sum + c * &values[*i as usize]
    })
}
fn witness(lower: Vec<Expr>, upper: Vec<Expr>) -> IntervalWitness {
    let count = lower.len() * upper.len();
    IntervalWitness {
        lower,
        upper,
        checks: (0..count as u32).map(Ref::Local).collect(),
    }
}
fn point(model: &Model, values: Vec<Q>) -> Result<(), String> {
    let claim = PointClaim::Feasible {
        target: false,
        integers: true,
        objective: None,
    };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![],
        points: vec![claim.clone()],
    };
    let certificate = Certificate { improvements:vec![], bijections:vec![],
        claims: vec![],
        blocks: vec![],
        points: vec![PointWitness {refutation:None, claim, values }],
    };
    verify_points(model, model, &certificate, &request, &Limits::default()).map(|_| ())
}

#[test]
fn every_lower_major_pair_and_generated_row_sign_is_explicit() {
    let input = model(1);
    let intervals = vec![witness(
        vec![expr("1", &[(0, "2")]), expr("-2", &[(0, "3")])],
        vec![
            expr("4", &[(0, "-1")]),
            expr("8", &[(0, "1")]),
            expr("7", &[]),
        ],
    )];
    let result = prepare_unchecked_extension(&input, &intervals, &Limits::default()).unwrap();
    assert_eq!(result.premises.len(), 6);
    for (i, expected) in ["0", "-6", "-4", "-2", "-8", "-6"].into_iter().enumerate() {
        assert_eq!(result.premises[i].kind, Kind::Le);
        assert_eq!(result.premises[i].reference, Ref::Local(i as u32));
        assert_eq!(eval(&result.premises[i].expression, &[q("1")]), q(expected));
    }
    assert_eq!(result.model.rows.len(), 5);
    for (i, row) in result.model.rows.iter().enumerate() {
        assert_eq!(row.lower, if i < 2 { Some(q("0")) } else { None });
        assert_eq!(row.upper, if i >= 2 { Some(q("0")) } else { None });
    }
    assert_eq!(
        result.model.rows[0].expr,
        expr("-1", &[(0, "-2"), (1, "1")])
    );
    assert_eq!(result.model.rows[2].expr, expr("-4", &[(0, "1"), (1, "1")]));
    assert!(point(&result.model, vec![q("1"), q("3")]).is_ok());
    assert!(point(&result.model, vec![q("1"), q("4")]).is_err());
}

#[test]
fn free_one_sided_and_empty_family_are_total_extensions() {
    let input = model(0);
    let intervals = vec![
        witness(vec![], vec![]),
        witness(vec![expr("2/3", &[]), expr("1/3", &[])], vec![]),
        witness(vec![], vec![expr("-2/7", &[]), expr("3/7", &[])]),
    ];
    let result = prepare_unchecked_extension(&input, &intervals, &Limits::default()).unwrap();
    assert!(result.premises.is_empty());
    assert_eq!(result.model.vars.len(), 3);
    assert_eq!(result.model.rows.len(), 4);
    assert!(result
        .model
        .vars
        .iter()
        .all(|v| !v.integer && v.lower.is_none() && v.upper.is_none()));
    assert!(point(&result.model, vec![q("0"), q("2/3"), q("-2/7")]).is_ok());
    assert!(point(&result.model, vec![q("99"), q("1/3"), q("-2/7")]).is_err());
    assert!(point(&result.model, vec![q("-99"), q("2/3"), q("3/7")]).is_err());
    let identity = prepare_unchecked_extension(&input, &[], &Limits::default()).unwrap();
    assert_eq!(identity.model, input);
    assert!(identity.premises.is_empty());
}

#[test]
fn unchecked_preparation_does_not_claim_false_pair_is_proved() {
    let input = model(0);
    let intervals = vec![witness(vec![expr("1", &[])], vec![expr("0", &[])])];
    let result = prepare_unchecked_extension(&input, &intervals, &Limits::default()).unwrap();
    assert_eq!(result.premises[0].expression, expr("1", &[]));
    assert!(point(&result.model, vec![q("0")]).is_err());
    assert!(point(&result.model, vec![q("1")]).is_err());
}

#[test]
fn bounds_cannot_reference_any_new_coordinate_or_malformed_rational() {
    let input = model(1);
    let base = witness(vec![Expr::var(0)], vec![Expr::var(0)]);
    let mut invalid = Vec::new();
    let mut w = base.clone();
    w.lower[0] = Expr::var(1);
    invalid.push(w);
    let mut w = base.clone();
    w.upper[0] = Expr::var(2);
    invalid.push(w);
    let mut w = base.clone();
    w.lower[0].constant = Q::new_raw(2.into(), 2.into());
    invalid.push(w);
    let mut w = base.clone();
    w.upper[0].terms[0].1 = Q::new_raw(1.into(), 0.into());
    invalid.push(w);
    let mut w = base.clone();
    w.upper[0].terms = vec![(0, q("0"))];
    invalid.push(w);
    let mut w = base.clone();
    w.checks.clear();
    invalid.push(w);
    let mut w = base.clone();
    w.checks.push(Ref::Exact);
    invalid.push(w);
    for (i, w) in invalid.into_iter().enumerate() {
        assert!(
            prepare_unchecked_extension(&input, &[base.clone(), w], &Limits::default()).is_err(),
            "mutation {i}"
        );
    }
}

#[test]
fn original_prefix_objective_domains_and_colliding_names_are_preserved() {
    let mut input = model(1);
    input.vars[0].name = "$rpx_interval_var_1".into();
    input.vars[0].integer = true;
    input.vars[0].lower = Some(q("-3"));
    input.vars[0].upper = Some(q("7"));
    input.rows.push(Row {
        name: "$rpx_interval_row_1".into(),
        expr: expr("2", &[(0, "1")]),
        lower: None,
        upper: Some(q("5")),
    });
    input.objective = expr("7/13", &[(0, "-1/11")]);
    let result = prepare_unchecked_extension(
        &input,
        &[witness(vec![Expr::var(0)], vec![])],
        &Limits::default(),
    )
    .unwrap();
    assert_eq!(result.model.name, input.name);
    assert_eq!(result.model.objective, input.objective);
    assert_eq!(result.model.vars[0], input.vars[0]);
    assert_eq!(result.model.rows[0], input.rows[0]);
    assert_ne!(result.model.vars[1].name, input.vars[0].name);
    assert_ne!(result.model.rows[1].name, input.rows[0].name);
    result.model.validate().unwrap();
}

#[test]
fn pair_product_work_and_scalar_intermediates_are_bounded() {
    let input = model(1);
    let intervals = vec![witness(vec![Expr::var(0)], vec![Expr::var(0)])];
    let result = prepare_unchecked_extension(&input, &intervals, &Limits::default()).unwrap();
    assert!(prepare_unchecked_extension(
        &input,
        &intervals,
        &Limits {
            work: result.statistics.work - 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
    assert!(prepare_unchecked_extension(
        &input,
        &intervals,
        &Limits {
            work: result.statistics.work,
            ..Limits::default()
        }
    )
    .is_ok());
    let many = vec![Expr::zero(); 1500];
    let checks = vec![Ref::Exact; 1500 * 1500];
    assert!(checks.len() > MAX_ROWS);
    let interval = IntervalWitness {
        lower: many.clone(),
        upper: many,
        checks,
    };
    assert!(
        prepare_unchecked_extension(&input, &[interval], &Limits::default())
            .unwrap_err()
            .contains("RESOURCE_LIMIT")
    );
    let big = Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize - 1));
    for constant in [false, true] {
        let lower = if constant {
            Expr {
                constant: big.clone(),
                terms: vec![],
            }
        } else {
            Expr {
                constant: q("0"),
                terms: vec![(0, big.clone())],
            }
        };
        let upper = if constant {
            Expr {
                constant: -&big,
                terms: vec![],
            }
        } else {
            Expr {
                constant: q("0"),
                terms: vec![(0, -&big)],
            }
        };
        assert!(prepare_unchecked_extension(
            &input,
            &[witness(vec![lower], vec![upper])],
            &Limits::default()
        )
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
    }
}

#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    input: Vec<String>,
    intervals: Vec<Bounds>,
    accept: bool,
    constructed: Vec<String>,
}
#[derive(Deserialize)]
struct Bounds {
    lower: Vec<Expr>,
    upper: Vec<Expr>,
    pair_values: Vec<String>,
}

#[test]
fn independent_fraction_interval_oracle_241_vectors() {
    let data: Oracle =
        serde_json::from_str(include_str!("../../../tests/vectors/interval_oracle.json")).unwrap();
    assert_eq!(data.seed, 0x494e5456);
    assert_eq!(data.cases.len(), 241);
    let mut accepted = 0;
    for (case_index, case) in data.cases.into_iter().enumerate() {
        let input = model(case.input.len());
        let intervals = case
            .intervals
            .iter()
            .map(|b| witness(b.lower.clone(), b.upper.clone()))
            .collect::<Vec<_>>();
        let result = prepare_unchecked_extension(&input, &intervals, &Limits::default()).unwrap();
        let old: Vec<Q> = case.input.iter().map(|s| q(s)).collect();
        let expected = case
            .intervals
            .iter()
            .flat_map(|b| b.pair_values.iter())
            .collect::<Vec<_>>();
        assert_eq!(expected.len(), result.premises.len());
        let mut valid = true;
        for (premise, expected) in result.premises.iter().zip(expected) {
            let value = eval(&premise.expression, &old);
            assert_eq!(value, q(expected), "case {case_index}");
            valid &= value <= q("0");
        }
        assert_eq!(valid, case.accept, "case {case_index}");
        let mut values = old;
        values.extend(case.constructed.iter().map(|s| q(s)));
        assert_eq!(
            point(&result.model, values).is_ok(),
            case.accept,
            "case {case_index}"
        );
        accepted += usize::from(case.accept);
    }
    assert_eq!(accepted, 121);
}
