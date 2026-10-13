use kernel_core::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, Q};
use kernel_core::point::verify_points;
use kernel_core::proof::{
    Block, Certificate, Claim, End, Objective, PointClaim, PointWitness, Ref, Request,
};
use kernel_core::verify::Limits;
use num_bigint::BigInt;
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn model(n: usize) -> Model {
    Model {
        name: "points".into(),
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
fn expr(constant: &str, terms: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(constant),
        terms: terms.iter().map(|(i, c)| (*i, q(c))).collect(),
    }
}
fn feasible(target: bool, integers: bool, objective: Option<&str>) -> PointClaim {
    PointClaim::Feasible {
        target,
        integers,
        objective: objective.map(q),
    }
}
fn claim(n: usize) -> Claim {
    Claim {input_halfspace:None,input_objective_level:None, affine_projection:vec![],
        reverse: false,
        input_integers: false,
        output_integers: false,
        objective: Objective::None,
        projection: (0..n as u32).map(|i| (i, i)).collect(),
        inverse: None,
        input_objective_lower: None,
    }
}
fn certificate(claims: Vec<Claim>, points: Vec<(PointClaim, Vec<Q>)>) -> (Certificate, Request) {
    let requested = Request { improvements:vec![], bijections:vec![],
        claims: claims.clone(),
        points: points.iter().map(|(p, _)| p.clone()).collect(),
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims,
        blocks: vec![],
        points: points
            .into_iter()
            .map(|(claim, values)| PointWitness {refutation:None, claim, values })
            .collect(),
    };
    (cert, requested)
}
fn check(
    source: &Model,
    target: &Model,
    claims: Vec<Claim>,
    point: PointClaim,
    values: &[&str],
) -> Result<kernel_core::point::PointStatistics, String> {
    let (cert, request) = certificate(claims, vec![(point, values.iter().map(|v| q(v)).collect())]);
    verify_points(source, target, &cert, &request, &Limits::default())
}

#[test]
fn feasible_checks_one_common_point_and_all_bounds_rows() {
    let mut m = model(2);
    m.vars[0].lower = Some(q("0"));
    m.vars[0].upper = Some(q("2"));
    m.vars[1].lower = Some(q("-1"));
    m.vars[1].upper = Some(q("2"));
    m.rows.push(Row {
        name: "sum".into(),
        expr: expr("1/7", &[(0, "1"), (1, "1")]),
        lower: Some(q("8/7")),
        upper: Some(q("8/7")),
    });
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, None),
        &["1/3", "2/3"]
    )
    .is_ok());
    for values in [["1/3", "1/3"], ["3", "-2"], ["-1", "2"]] {
        assert!(check(&m, &m, vec![], feasible(false, false, None), &values).is_err());
    }
    assert!(check(&m, &m, vec![], feasible(false, false, None), &["1"])
        .unwrap_err()
        .contains("dimension"));
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, None),
        &["1", "0", "0"]
    )
    .unwrap_err()
    .contains("dimension"));
}

#[test]
fn domain_flag_only_requires_declared_integer_variables() {
    let mut m = model(2);
    m.vars[0].integer = true;
    m.vars[0].lower = Some(q("0"));
    m.vars[0].upper = Some(q("1"));
    assert!(check(&m, &m, vec![], feasible(false, true, None), &["1", "1/2"]).is_ok());
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, None),
        &["1/2", "1/2"]
    )
    .is_ok());
    assert!(check(&m, &m, vec![], feasible(false, true, None), &["1/2", "1/2"]).is_err());
    // A binary witness must satisfy both implicit bounds even in the LP domain.
    assert!(check(&m, &m, vec![], feasible(false, false, None), &["2", "0"]).is_err());
}

#[test]
fn objective_uses_exact_normalized_sense_and_constant() {
    let m =
        kernel_core::lp::parse_lp("Maximize\n obj: 2 x - 3/7\nSubject To\nBounds\n x free\nEnd\n")
            .unwrap();
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, Some("-5/21")),
        &["1/3"]
    )
    .is_ok());
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, Some("5/21")),
        &["1/3"]
    )
    .is_err());
    assert!(check(
        &m,
        &m,
        vec![],
        feasible(false, false, Some("-2/3")),
        &["1/3"]
    )
    .is_err());
    assert!(check(&m, &m, vec![], feasible(false, false, None), &["1/3"]).is_ok());
}

#[test]
fn selected_model_is_actual_source_or_target() {
    let mut source = model(1);
    let mut target = model(1);
    source.vars[0].upper = Some(q("0"));
    target.vars[0].lower = Some(q("1"));
    source.objective = expr("3", &[]);
    target.objective = expr("4", &[]);
    assert!(check(
        &source,
        &target,
        vec![],
        feasible(true, false, Some("4")),
        &["1"]
    )
    .is_ok());
    assert!(check(
        &source,
        &target,
        vec![],
        feasible(false, false, None),
        &["1"]
    )
    .is_err());
    assert!(check(
        &source,
        &target,
        vec![],
        feasible(false, false, Some("3")),
        &["0"]
    )
    .is_ok());
    assert!(check(
        &source,
        &target,
        vec![],
        feasible(true, false, None),
        &["0"]
    )
    .is_err());
}

#[test]
fn zero_dimension_constants_and_inconsistent_bounds() {
    let mut m = model(0);
    m.objective = expr("17/19", &[]);
    assert!(check(&m, &m, vec![], feasible(false, true, Some("17/19")), &[]).is_ok());
    m.rows.push(Row {
        name: "constant".into(),
        expr: expr("1", &[]),
        lower: None,
        upper: Some(q("0")),
    });
    assert!(check(&m, &m, vec![], feasible(false, false, None), &[]).is_err());
    let mut n = model(1);
    n.vars[0].lower = Some(q("2"));
    n.vars[0].upper = Some(q("1"));
    for value in ["0", "1", "3/2", "2", "3"] {
        assert!(check(&n, &n, vec![], feasible(false, false, None), &[value]).is_err());
    }
}

#[test]
fn strictness_requires_actual_output_feasibility_and_input_violation() {
    let mut source = model(1);
    let mut target = model(1);
    source.vars[0].upper = Some(q("0"));
    target.vars[0].upper = Some(q("1"));
    let point = PointClaim::Strictness { inclusion_claim: 0 };
    assert!(check(&source, &target, vec![claim(1)], point.clone(), &["1"]).is_ok());
    assert!(
        check(&source, &target, vec![claim(1)], point.clone(), &["0"])
            .unwrap_err()
            .contains("violates no actual")
    );
    assert!(
        check(&source, &target, vec![claim(1)], point.clone(), &["2"])
            .unwrap_err()
            .contains("not feasible")
    );
    // Objective disagreement and integer disagreement are not LP separation.
    source.vars[0].integer = true;
    source.objective = expr("11", &[]);
    target.objective = expr("12", &[]);
    source.vars[0].upper = Some(q("1"));
    assert!(check(&source, &target, vec![claim(1)], point, &["1/2"]).is_err());
}

#[test]
fn strictness_row_violation_and_permuted_complete_projection() {
    let mut source = model(2);
    let mut target = model(2);
    source.rows.push(Row {
        name: "sum".into(),
        expr: expr("1/7", &[(0, "1"), (1, "2")]),
        lower: None,
        upper: Some(q("22/7")),
    });
    target.vars[0].upper = Some(q("2"));
    target.vars[1].upper = Some(q("3"));
    let mut c = claim(2);
    c.projection = vec![(0, 1), (1, 0)];
    let p = PointClaim::Strictness { inclusion_claim: 0 };
    // Output (2,0) reconstructs input (0,2), violating 1/7+0+4 <= 22/7.
    assert!(check(&source, &target, vec![c.clone()], p.clone(), &["2", "0"]).is_ok());
    // Output (0,2) reconstructs input (2,0), which satisfies the input row.
    assert!(check(&source, &target, vec![c], p, &["0", "2"]).is_err());
}

#[test]
fn strictness_reverse_direction_and_zero_dimension() {
    let mut source = model(1);
    let mut target = model(1);
    source.vars[0].upper = Some(q("2"));
    target.vars[0].upper = Some(q("1"));
    let mut c = claim(1);
    c.reverse = true;
    assert!(check(
        &source,
        &target,
        vec![c],
        PointClaim::Strictness { inclusion_claim: 0 },
        &["2"]
    )
    .is_ok());
    let mut input = model(0);
    let output = model(0);
    input.rows.push(Row {
        name: "empty".into(),
        expr: expr("1", &[]),
        lower: None,
        upper: Some(q("0")),
    });
    assert!(check(
        &input,
        &output,
        vec![claim(0)],
        PointClaim::Strictness { inclusion_claim: 0 },
        &[]
    )
    .is_ok());
}

#[test]
fn strictness_rejects_partial_duplicate_and_out_of_range_projections() {
    let mut source = model(2);
    let target = model(2);
    source.vars[0].upper = Some(q("0"));
    for projection in [
        vec![(0, 0)],
        vec![(0, 0), (0, 1)],
        vec![(0, 0), (1, 0)],
        vec![(0, 0), (1, 2)],
        vec![(0, 0), (2, 1)],
    ] {
        let mut c = claim(2);
        c.projection = projection;
        assert!(check(
            &source,
            &target,
            vec![c],
            PointClaim::Strictness { inclusion_claim: 0 },
            &["1", "1"]
        )
        .is_err());
    }
    assert!(check(
        &source,
        &model(3),
        vec![claim(2)],
        PointClaim::Strictness { inclusion_claim: 0 },
        &["1", "1", "1"]
    )
    .is_err());
    assert!(check(
        &source,
        &target,
        vec![claim(2)],
        PointClaim::Strictness { inclusion_claim: 0 },
        &["1"]
    )
    .is_err());
}

#[test]
fn strictness_rejects_non_lp_inclusion_and_bad_claim_index() {
    let source = model(1);
    let target = model(1);
    for (input, output) in [(true, false), (false, true), (true, true)] {
        let mut c = claim(1);
        c.input_integers = input;
        c.output_integers = output;
        assert!(check(
            &source,
            &target,
            vec![c],
            PointClaim::Strictness { inclusion_claim: 0 },
            &["1"]
        )
        .unwrap_err()
        .contains("LP-to-LP"));
    }
    assert!(check(
        &source,
        &target,
        vec![claim(1)],
        PointClaim::Strictness { inclusion_claim: 1 },
        &["1"]
    )
    .unwrap_err()
    .contains("index"));
}

#[test]
fn requested_contract_cannot_be_changed_omitted_or_reordered() {
    let m = model(1);
    let (mut cert, request) = certificate(
        vec![],
        vec![
            (feasible(false, true, Some("0")), vec![q("1")]),
            (feasible(true, false, None), vec![q("2")]),
        ],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default()).is_ok());
    cert.points.swap(0, 1);
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default())
        .unwrap_err()
        .contains("contract"));
    cert.points.swap(0, 1);
    cert.points.pop();
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default()).is_err());
    cert.points[0].claim = feasible(false, false, None);
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default()).is_err());
}

#[test]
fn canonical_rationals_are_checked_before_early_feasibility_exit() {
    let mut m = model(2);
    m.vars[0].upper = Some(q("0"));
    let (cert, request) = certificate(
        vec![],
        vec![(
            feasible(false, false, None),
            vec![q("1"), Q::new_raw(2.into(), 2.into())],
        )],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default())
        .unwrap_err()
        .contains("rational"));
    let (cert, request) = certificate(
        vec![],
        vec![(
            PointClaim::Feasible {
                target: false,
                integers: false,
                objective: Some(Q::new_raw(1.into(), (-1).into())),
            },
            vec![q("0"), q("0")],
        )],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default()).is_err());
}

#[test]
fn arithmetic_checks_product_partial_sum_and_input_bit_limits() {
    let large = Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize - 1));
    let mut m = model(1);
    m.objective = Expr {
        constant: q("0"),
        terms: vec![(0, large.clone())],
    };
    let (cert, request) = certificate(
        vec![],
        vec![(feasible(false, false, Some("0")), vec![q("2")])],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default())
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
    m.objective = Expr {
        constant: large.clone(),
        terms: vec![(0, large.clone())],
    };
    let (cert, request) = certificate(
        vec![],
        vec![(feasible(false, false, Some("0")), vec![q("1")])],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default())
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
    m.objective = Expr::zero();
    let (cert, request) = certificate(
        vec![],
        vec![(feasible(false, false, None), vec![large * q("2")])],
    );
    assert!(verify_points(&m, &m, &cert, &request, &Limits::default())
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
}

#[test]
fn work_budget_is_shared_across_points_and_counts_coefficient_visits() {
    let mut m = model(2);
    m.objective = expr("1/2", &[(0, "2"), (1, "3")]);
    let (cert, request) = certificate(
        vec![],
        vec![
            (feasible(false, false, Some("11/2")), vec![q("1"), q("1")]),
            (feasible(false, false, Some("11/2")), vec![q("1"), q("1")]),
        ],
    );
    let stats = verify_points(&m, &m, &cert, &request, &Limits::default()).unwrap();
    assert_eq!(stats.points, 2);
    assert_eq!(stats.coefficient_terms, 4);
    assert_eq!(stats.work, 20);
    let limits = Limits {
        work: 19,
        ..Limits::default()
    };
    assert!(verify_points(&m, &m, &cert, &request, &limits)
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
    let limits = Limits {
        work: 20,
        ..Limits::default()
    };
    assert!(verify_points(&m, &m, &cert, &request, &limits).is_ok());
}

#[test]
fn strictness_does_not_bypass_the_mapping_proof_in_full_verifier() {
    let mut source = model(1);
    let mut target = model(1);
    source.vars[0].upper = Some(q("0"));
    target.vars[0].upper = Some(q("1"));
    let (mut cert, request) = certificate(
        vec![claim(1)],
        vec![(PointClaim::Strictness { inclusion_claim: 0 }, vec![q("1")])],
    );
    // Separation succeeds locally, but the full request still needs a valid map.
    assert!(verify_points(&source, &target, &cert, &request, &Limits::default()).is_ok());
    cert.blocks.push(Block {
        steps: vec![],
        end: End::Return {
            map: vec![Expr::var(0)],
            checks: vec![Ref::Exact, Ref::Exact],
        },
    });
    assert!(kernel_core::verify::verify_request(
        &source,
        &target,
        &cert,
        &request,
        &Limits::default()
    )
    .is_err());
}

#[test]
fn full_request_proves_strictness_and_applies_one_shared_work_limit() {
    let mut source = model(2);
    source.rows.push(Row {
        name: "cap".into(),
        expr: expr("1/7", &[(0, "1"), (1, "2")]),
        lower: None,
        upper: Some(q("22/7")),
    });
    let target = model(2);
    let mut c = claim(2);
    c.projection = vec![(0, 1), (1, 0)];
    let (mut cert, request) = certificate(
        vec![c],
        vec![(
            PointClaim::Strictness { inclusion_claim: 0 },
            vec![q("2"), q("0")],
        )],
    );
    cert.blocks.push(Block {
        steps: vec![],
        end: End::Return {
            map: vec![Expr::var(1), Expr::var(0)],
            checks: vec![Ref::Exact, Ref::Exact],
        },
    });
    let stats =
        kernel_core::verify::verify_request(&source, &target, &cert, &request, &Limits::default())
            .unwrap();
    assert_eq!(stats.points, 1);
    let limits = Limits {
        work: stats.work - 1,
        ..Limits::default()
    };
    assert!(
        kernel_core::verify::verify_request(&source, &target, &cert, &request, &limits)
            .unwrap_err()
            .contains("RESOURCE_LIMIT")
    );
    let limits = Limits {
        work: stats.work,
        ..Limits::default()
    };
    assert!(
        kernel_core::verify::verify_request(&source, &target, &cert, &request, &limits).is_ok()
    );
}

#[test]
fn full_request_supports_feasibility_without_mapping_claims() {
    let mut m = model(1);
    m.objective = expr("1/11", &[(0, "-1/7")]);
    let (cert, request) = certificate(
        vec![],
        vec![(feasible(false, false, Some("-4/77")), vec![q("1")])],
    );
    let stats =
        kernel_core::verify::verify_request(&m, &m, &cert, &request, &Limits::default()).unwrap();
    assert_eq!(stats.points, 1);
}

#[derive(Deserialize)]
struct OracleModel {
    vars: Vec<OracleVar>,
    rows: Vec<OracleRow>,
    objective: Expr,
}
#[derive(Deserialize)]
struct OracleVar {
    integer: bool,
    lower: Option<String>,
    upper: Option<String>,
}
#[derive(Deserialize)]
struct OracleRow {
    expr: Expr,
    lower: Option<String>,
    upper: Option<String>,
}
impl OracleModel {
    fn into_model(self) -> Model {
        Model {
            name: "point-oracle".into(),
            vars: self
                .vars
                .into_iter()
                .enumerate()
                .map(|(i, v)| Var {
                    name: format!("v{i}"),
                    integer: v.integer,
                    lower: v.lower.map(|s| q(&s)),
                    upper: v.upper.map(|s| q(&s)),
                })
                .collect(),
            rows: self
                .rows
                .into_iter()
                .enumerate()
                .map(|(i, r)| Row {
                    name: format!("r{i}"),
                    expr: r.expr,
                    lower: r.lower.map(|s| q(&s)),
                    upper: r.upper.map(|s| q(&s)),
                })
                .collect(),
            objective: self.objective,
        }
    }
}
#[derive(Deserialize)]
struct OracleCase {
    source: OracleModel,
    target: OracleModel,
    claims: Vec<Claim>,
    point: PointWitness,
    accept: bool,
}
#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<OracleCase>,
}

#[test]
fn independent_fraction_point_oracle_480_vectors() {
    let data: Oracle =
        serde_json::from_str(include_str!("../../../tests/vectors/point_oracle.json")).unwrap();
    assert_eq!(data.seed, 0x505433);
    assert_eq!(data.cases.len(), 480);
    for (i, case) in data.cases.into_iter().enumerate() {
        let source = case.source.into_model();
        let target = case.target.into_model();
        let request = Request { improvements:vec![], bijections:vec![],
            claims: case.claims.clone(),
            points: vec![case.point.claim.clone()],
        };
        let cert = Certificate { improvements:vec![], bijections:vec![],
            claims: case.claims,
            blocks: vec![],
            points: vec![case.point],
        };
        let result = verify_points(&source, &target, &cert, &request, &Limits::default());
        assert_eq!(result.is_ok(), case.accept, "oracle case {i}: {result:?}");
    }
}
