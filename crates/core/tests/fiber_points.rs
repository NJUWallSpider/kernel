use kernel_core::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, Q};
use kernel_core::point::verify_points;
use kernel_core::proof::*;
use kernel_core::verify::{verify_request, Limits};
use num_bigint::BigInt;
use num_traits::{Signed, Zero};
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn expr(c: &str, terms: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(c),
        terms: terms.iter().map(|(i, c)| (*i, q(c))).collect(),
    }
}
fn model(n: usize) -> Model {
    Model {
        name: "fiber".into(),
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
fn claim() -> Claim {
    Claim {input_halfspace:None,input_objective_level:None,
        reverse: false,
        input_integers: false,
        output_integers: false,
        objective: Objective::None,
        projection: vec![],
        affine_projection: vec![],
        inverse: None,
        input_objective_lower: None,
    }
}
fn contradiction() -> Block {
    Block {
        steps: vec![Step::Lin {
            id: 0,
            kind: Kind::Eq,
            constant: q("0"),
            terms: vec![(Ref::RowEq(0), q("1")), (Ref::RowEq(1), q("-1"))],
        }],
        end: End::Absurd {
            fact: Ref::Local(0),
        },
    }
}
fn fixture() -> (Model, Model, Certificate, Request) {
    let source = model(2);
    let target = model(2); // x1 is an unobserved input degree of freedom.
    let mut c = claim();
    c.projection = vec![(0, 0)];
    c.affine_projection = vec![(expr("1", &[(0, "1")]), Expr::var(1))];
    let point = PointClaim::FiberStrictness { inclusion_claim: 0 };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![c.clone()],
        points: vec![point.clone()],
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims: vec![c],
        blocks: vec![Block {
            steps: vec![],
            end: End::Return {
                map: vec![Expr::var(0), expr("1", &[(0, "1")])],
                checks: vec![Ref::Exact, Ref::Exact],
            },
        }],
        points: vec![PointWitness {
            claim: point,
            values: vec![q("0"), q("2")],
            refutation: Some(contradiction()),
        }],
    };
    (source, target, cert, request)
}

#[test]
fn noninjective_input_fiber_checks_coordinate_and_affine_observations_together() {
    let (source, target, cert, request) = fixture();
    let stats = verify_request(&source, &target, &cert, &request, &Limits::default()).unwrap();
    assert_eq!(stats.points, 1);
    let mut bad = cert.clone();
    bad.points[0].values[1] = q("1");
    assert!(verify_request(&source, &target, &bad, &request, &Limits::default()).is_err());
    // Omitting an observation from the certificate cannot weaken the caller.
    let mut bad = cert.clone();
    bad.claims[0].affine_projection.clear();
    assert!(verify_request(&source, &target, &bad, &request, &Limits::default()).is_err());
    // Even for a caller requesting that weaker contract, the missing equality
    // cannot be supplied by a reference to the old second fiber row.
    let mut weaker = request.clone();
    weaker.claims = bad.claims.clone();
    assert!(verify_points(&source, &target, &bad, &weaker, &Limits::default()).is_err());
}

#[test]
fn valid_separator_never_bypasses_inclusion_or_output_point_feasibility() {
    let (source, mut target, mut cert, request) = fixture();
    if let End::Return { map, .. } = &mut cert.blocks[0].end {
        map[1].constant = q("2");
    }
    assert!(verify_points(&source, &target, &cert, &request, &Limits::default()).is_ok());
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_err());
    target.vars[1].upper = Some(q("1"));
    assert!(
        verify_points(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("not feasible")
    );
    let (_, _, mut cert, request) = fixture();
    cert.points[0].values.pop();
    assert!(
        verify_points(&source, &model(2), &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("dimension")
    );
}

#[test]
fn reverse_direction_and_affine_output_constants_are_exact() {
    let (source, target, mut cert, mut request) = fixture();
    cert.claims[0].reverse = true;
    request.claims = cert.claims.clone();
    assert!(verify_request(&target, &source, &cert, &request, &Limits::default()).is_ok());
    // Both a(x) and b(y) contain constants; the fiber retains the complete a.
    let mut source = model(2);
    source.vars[0].upper = Some(q("0"));
    let target = model(2);
    let mut c = claim();
    c.affine_projection = vec![(expr("2", &[(0, "3")]), expr("5", &[(0, "-2")]))];
    let point = PointClaim::FiberStrictness { inclusion_claim: 0 };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![c.clone()],
        points: vec![point.clone()],
    };
    let proof = Block {
        steps: vec![Step::Lin {
            id: 0,
            kind: Kind::Le,
            constant: q("0"),
            terms: vec![(Ref::VarUpper(0), q("3")), (Ref::RowEq(0), q("-1"))],
        }],
        end: End::Absurd {
            fact: Ref::Local(0),
        },
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims: vec![c],
        blocks: vec![],
        points: vec![PointWitness {
            claim: point,
            values: vec![q("1"), q("0")],
            refutation: Some(proof),
        }],
    };
    assert!(verify_points(&source, &target, &cert, &request, &Limits::default()).is_ok());
}

#[test]
fn empty_observation_strictness_requires_an_actually_empty_input() {
    let mut source = model(0);
    source.rows.push(Row {
        name: "empty".into(),
        expr: expr("1", &[]),
        lower: None,
        upper: Some(q("0")),
    });
    let target = model(0);
    let point = PointClaim::FiberStrictness { inclusion_claim: 0 };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![claim()],
        points: vec![point.clone()],
    };
    let absurd = Block {
        steps: vec![],
        end: End::Absurd {
            fact: Ref::RowUpper(0),
        },
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims: request.claims.clone(),
        blocks: vec![absurd.clone()],
        points: vec![PointWitness {
            claim: point,
            values: vec![],
            refutation: Some(absurd),
        }],
    };
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_ok());
    source.rows[0].expr.constant = q("0");
    assert!(verify_points(&source, &target, &cert, &request, &Limits::default()).is_err());
}

#[test]
fn mapping_and_other_witness_live_facts_do_not_enter_refutations() {
    let (source, target, mut cert, mut request) = fixture();
    cert.points.push(cert.points[0].clone());
    request.points.push(request.points[0].clone());
    cert.points[1].refutation = Some(Block {
        steps: vec![],
        end: End::Absurd {
            fact: Ref::Local(0),
        },
    });
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_err());
    let mut source = model(0);
    source.rows.push(Row {
        name: "empty".into(),
        expr: expr("1", &[]),
        lower: None,
        upper: Some(q("0")),
    });
    let point = PointClaim::FiberStrictness { inclusion_claim: 0 };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![claim()],
        points: vec![point.clone()],
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims: request.claims.clone(),
        blocks: vec![Block {
            steps: vec![Step::Lin {
                id: 77,
                kind: Kind::Le,
                constant: q("0"),
                terms: vec![(Ref::RowUpper(0), q("1"))],
            }],
            end: End::Absurd {
                fact: Ref::Local(77),
            },
        }],
        points: vec![PointWitness {
            claim: point,
            values: vec![],
            refutation: Some(Block {
                steps: vec![],
                end: End::Absurd {
                    fact: Ref::Local(77),
                },
            }),
        }],
    };
    assert!(verify_request(&source, &model(0), &cert, &request, &Limits::default()).is_err());
}

#[test]
fn sibling_facts_do_not_leak_and_only_refutation_endpoints_are_allowed() {
    let (source, target, mut cert, request) = fixture();
    let proof = Block {
        steps: vec![],
        end: End::Split {
            expression: Expr::zero(),
            integer: None,
            left: Box::new(contradiction()),
            right: Box::new(contradiction()),
        },
    };
    cert.points[0].refutation = Some(proof.clone());
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_ok());
    if let Some(Block {
        end: End::Split { right, .. },
        ..
    }) = &mut cert.points[0].refutation
    {
        right.steps.clear();
    }
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_err());
    cert.points[0].refutation = Some(Block {
        steps: vec![],
        end: End::Return {
            map: vec![],
            checks: vec![],
        },
    });
    assert!(
        verify_request(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("refutation")
    );
    cert.points[0].refutation = Some(Block {
        steps: vec![],
        end: End::IntervalLift {
            intervals: vec![],
            body: Box::new(contradiction()),
        },
    });
    assert!(
        verify_request(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("refutation")
    );
    cert.points[0].refutation = Some(proof);
    assert!(verify_request(
        &source,
        &target,
        &cert,
        &request,
        &Limits {
            depth: 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
}

#[test]
fn integer_declarations_cannot_refute_a_nonempty_lp_fiber() {
    let mut source = model(1);
    source.vars[0].integer = true;
    source.vars[0].lower = Some(q("1/2"));
    source.vars[0].upper = Some(q("1/2"));
    let target = model(0);
    let p = PointClaim::FiberStrictness { inclusion_claim: 0 };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![claim()],
        points: vec![p.clone()],
    };
    let proof = Block {
        steps: vec![Step::Lin {
            id: 0,
            kind: Kind::Int,
            constant: q("0"),
            terms: vec![(Ref::VarInt(0), q("1"))],
        }],
        end: End::Absurd {
            fact: Ref::Local(0),
        },
    };
    let cert = Certificate { improvements:vec![], bijections:vec![],
        claims: request.claims.clone(),
        blocks: vec![Block {
            steps: vec![],
            end: End::Return {
                map: vec![],
                checks: vec![],
            },
        }],
        points: vec![PointWitness {
            claim: p,
            values: vec![],
            refutation: Some(proof),
        }],
    };
    assert!(verify_request(&source, &target, &cert, &request, &Limits::default()).is_err());
}

#[test]
fn missing_surplus_and_wrong_index_refutations_reject() {
    let (source, target, mut cert, mut request) = fixture();
    cert.points[0].refutation = None;
    assert!(
        verify_request(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("missing")
    );
    cert.points[0].refutation = Some(contradiction());
    for variant in [
        PointClaim::Feasible {
            target: true,
            integers: false,
            objective: None,
        },
        PointClaim::Strictness { inclusion_claim: 0 },
    ] {
        cert.points[0].claim = variant.clone();
        request.points[0] = variant;
        assert!(
            verify_points(&source, &target, &cert, &request, &Limits::default())
                .unwrap_err()
                .contains("surplus")
        );
    }
    cert.points[0].claim = PointClaim::FiberStrictness { inclusion_claim: 1 };
    request.points[0] = cert.points[0].claim.clone();
    assert!(
        verify_points(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("index")
    );
}

#[test]
fn original_observation_dimensions_lp_modes_and_evaluation_budget_are_checked() {
    let (source, target, cert, request) = fixture();
    for change in 0..5 {
        let mut cert = cert.clone();
        let mut request = request.clone();
        match change {
            0 => cert.claims[0].projection[0].0 = 2,
            1 => cert.claims[0].projection[0].1 = 2,
            2 => cert.claims[0].affine_projection[0].0 = Expr::var(2),
            3 => cert.claims[0].input_integers = true,
            _ => cert.claims[0].output_integers = true,
        };
        request.claims = cert.claims.clone();
        assert!(
            verify_points(&source, &target, &cert, &request, &Limits::default()).is_err(),
            "{change}"
        );
    }
    let mut cert = cert.clone();
    let mut request = request.clone();
    let big = Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize - 1));
    cert.claims[0].affine_projection[0].1 = Expr {
        constant: q("0"),
        terms: vec![(1, big)],
    };
    request.claims = cert.claims.clone();
    assert!(
        verify_points(&source, &target, &cert, &request, &Limits::default())
            .unwrap_err()
            .contains("RESOURCE_LIMIT")
    );
}

#[test]
fn complete_mapping_point_fiber_and_refutation_share_one_work_budget() {
    let (source, target, cert, request) = fixture();
    let stats = verify_request(&source, &target, &cert, &request, &Limits::default()).unwrap();
    assert!(verify_request(
        &source,
        &target,
        &cert,
        &request,
        &Limits {
            work: stats.work - 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
    assert!(verify_request(
        &source,
        &target,
        &cert,
        &request,
        &Limits {
            work: stats.work,
            ..Limits::default()
        }
    )
    .is_ok());
}

#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    lower: Vec<String>,
    upper: Vec<String>,
    coefficients: Vec<String>,
    constant: String,
    minimum: String,
    maximum: String,
    output_lower: String,
    output_upper: String,
    point: String,
    direction: String,
    strict: bool,
}

#[test]
fn independent_fraction_box_projection_oracle_120_cases() {
    let data: Oracle =
        serde_json::from_str(include_str!("../../../tests/vectors/fiber_oracle.json")).unwrap();
    assert_eq!(data.seed, 0x46494252);
    assert_eq!(data.cases.len(), 120);
    for (case_index, case) in data.cases.into_iter().enumerate() {
        let mut source = model(case.lower.len());
        let mut coefficients = Vec::new();
        let mut low_terms = Vec::new();
        let mut high_terms = Vec::new();
        for i in 0..source.vars.len() {
            source.vars[i].lower = Some(q(&case.lower[i]));
            source.vars[i].upper = Some(q(&case.upper[i]));
            let c = q(&case.coefficients[i]);
            if !c.is_zero() {
                coefficients.push((i as u32, c.clone()));
                let (low, high) = if c.is_positive() {
                    (Ref::VarLower(i as u32), Ref::VarUpper(i as u32))
                } else {
                    (Ref::VarUpper(i as u32), Ref::VarLower(i as u32))
                };
                low_terms.push((low, c.abs()));
                high_terms.push((high, c.abs()));
            }
        }
        let observation = Expr {
            constant: q(&case.constant),
            terms: coefficients,
        };
        let mut target = model(1);
        target.vars[0].lower = Some(q(&case.output_lower));
        target.vars[0].upper = Some(q(&case.output_upper));
        let mut c = claim();
        c.affine_projection = vec![(observation.clone(), Expr::var(0))];
        let p = PointClaim::FiberStrictness { inclusion_claim: 0 };
        let request = Request { improvements:vec![], bijections:vec![],
            claims: vec![c.clone()],
            points: vec![p.clone()],
        };
        let mapping = Block {
            steps: vec![
                Step::Lin {
                    id: 0,
                    kind: Kind::Le,
                    constant: q(&case.output_lower) - q(&case.minimum),
                    terms: low_terms.clone(),
                },
                Step::Lin {
                    id: 1,
                    kind: Kind::Le,
                    constant: q(&case.maximum) - q(&case.output_upper),
                    terms: high_terms.clone(),
                },
            ],
            end: End::Return {
                map: vec![observation],
                checks: vec![Ref::Local(0), Ref::Local(1), Ref::Exact],
            },
        };
        let mut contradiction_terms = if case.direction == "upper" {
            high_terms
        } else {
            low_terms
        };
        contradiction_terms.push((
            Ref::RowEq(0),
            if case.direction == "upper" {
                q("-1")
            } else {
                q("1")
            },
        ));
        let refutation = Block {
            steps: vec![Step::Lin {
                id: 0,
                kind: Kind::Le,
                constant: q("0"),
                terms: contradiction_terms,
            }],
            end: End::Absurd {
                fact: Ref::Local(0),
            },
        };
        let cert = Certificate { improvements:vec![], bijections:vec![],
            claims: vec![c],
            blocks: vec![mapping],
            points: vec![PointWitness {
                claim: p,
                values: vec![q(&case.point)],
                refutation: Some(refutation),
            }],
        };
        let result = verify_request(&source, &target, &cert, &request, &Limits::default());
        assert_eq!(result.is_ok(), case.strict, "case {case_index}: {result:?}");
    }
}
