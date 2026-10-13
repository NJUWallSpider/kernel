//! Structured diagnostics: best-effort `Location` fields on the error path.
//!
//! Every fixture is built in code. These tests pin the documented field
//! semantics and, above all, that diagnostics never change an error string, an
//! acceptance decision or the returned `Statistics`.
use kernel_core::model::{Expr, Model, Q, Row, Var};
use kernel_core::point::{verify_points, verify_points_with_diagnostics};
use kernel_core::proof::*;
use kernel_core::verify::{
    verify, verify_injectivity, verify_injectivity_with_diagnostics, verify_lp_refutation,
    verify_lp_refutation_with_diagnostics, verify_request, verify_request_with_diagnostics,
    verify_with_diagnostics, Diagnostics, Limits, Location,
};
use serde_json::json;

fn q(n: i64) -> Q {
    Q::from_integer(n.into())
}
fn e(constant: i64, terms: &[(u32, i64)]) -> Expr {
    Expr { constant: q(constant), terms: terms.iter().map(|(i, a)| (*i, q(*a))).collect() }
}
fn lin(id: u32, terms: Vec<(Ref, Q)>) -> Step {
    Step::Lin { id, kind: Kind::Le, constant: q(0), terms }
}
fn witness(steps: Vec<Step>, fact: Ref) -> Box<Derivation> {
    Box::new(Derivation { steps, end: DerivationEnd::Witness(fact) })
}
fn cl() -> Claim {
    Claim {
        input_halfspace: None,
        input_objective_level: None,
        affine_projection: vec![],
        input_objective_lower: None,
        reverse: false,
        input_integers: true,
        output_integers: true,
        objective: Objective::None,
        projection: vec![(0, 0), (1, 1)],
        inverse: None,
    }
}

/// Two-variable fixture with a non-trivial local `Cases` proof (V2 style).
fn models() -> (Model, Model) {
    let vars = vec![
        Var { name: "x".into(), integer: true, lower: Some(q(0)), upper: Some(q(1)) },
        Var { name: "y".into(), integer: false, lower: Some(q(0)), upper: Some(q(1)) },
    ];
    let source = Model {
        name: "source".into(),
        vars: vars.clone(),
        rows: vec![
            Row { name: "yx".into(), expr: e(0, &[(0, -1), (1, 1)]), lower: None, upper: Some(q(0)) },
            Row { name: "lower_product".into(), expr: e(0, &[(0, 2), (1, -1)]), lower: None, upper: Some(q(1)) },
        ],
        objective: e(0, &[]),
    };
    let target = Model {
        name: "target".into(),
        vars,
        rows: vec![Row { name: "alias".into(), expr: e(0, &[(0, -1), (1, 1)]), lower: Some(q(0)), upper: Some(q(0)) }],
        objective: e(0, &[]),
    };
    (source, target)
}

/// The root `End::Return` emits eight obligations in this exact order:
/// 0 x>=lower, 1 x<=upper, 2 INT(x), 3 y>=lower, 4 y<=upper, 5 alias equality,
/// 6 projection x, 7 projection y.
fn certificate() -> Certificate {
    let left = witness(
        vec![
            lin(10, vec![(Ref::Assumption(0), q(1)), (Ref::VarLower(1), q(1))]),
            Step::EqPair { id: 11, positive: Ref::RowUpper(0), negative: Ref::Local(10) },
        ],
        Ref::Local(11),
    );
    let right = witness(
        vec![
            lin(20, vec![(Ref::Assumption(0), q(1)), (Ref::RowUpper(1), q(1))]),
            Step::EqPair { id: 21, positive: Ref::RowUpper(0), negative: Ref::Local(20) },
        ],
        Ref::Local(21),
    );
    let step = Step::Cases(Box::new(CasesStep {
        id: 100,
        kind: Kind::Eq,
        expression: e(0, &[(0, -1), (1, 1)]),
        split: e(0, &[(0, 1)]),
        integer: Some(Ref::VarInt(0)),
        left,
        right,
    }));
    Certificate {
        improvements: vec![],
        bijections: vec![],
        points: vec![],
        claims: vec![cl()],
        blocks: vec![Block {
            steps: vec![step],
            end: End::Return {
                map: vec![e(0, &[(0, 1)]), e(0, &[(1, 1)])],
                checks: vec![
                    Ref::VarLower(0),
                    Ref::VarUpper(0),
                    Ref::VarInt(0),
                    Ref::VarLower(1),
                    Ref::VarUpper(1),
                    Ref::Local(100),
                    Ref::Exact,
                    Ref::Exact,
                ],
            },
        }],
    }
}
fn request() -> Request {
    Request { improvements: vec![], bijections: vec![], claims: vec![cl()], points: vec![] }
}

fn empty() -> Model {
    Model { name: "empty".into(), vars: vec![], rows: vec![], objective: e(0, &[]) }
}
fn empty_claim() -> Claim {
    let mut c = cl();
    c.projection.clear();
    c
}

/// One non-integer variable; the claim's `input_objective_lower` adds a third
/// obligation after `x>=lower` and `x<=upper`, so a block emits exactly three.
fn single() -> Model {
    Model {
        name: "single".into(),
        vars: vec![Var { name: "x".into(), integer: false, lower: Some(q(0)), upper: Some(q(1)) }],
        rows: vec![],
        objective: e(0, &[]),
    }
}
fn bounded_claim() -> Claim {
    let mut c = cl();
    c.projection.clear();
    c.input_objective_lower = Some(q(0));
    c
}
/// First claim passes, second fails at its third (and last) obligation.
fn bounded_certificate() -> Certificate {
    let claim = bounded_claim();
    let map = vec![e(0, &[(0, 1)])];
    let good = Block {
        steps: vec![],
        end: End::Return { map: map.clone(), checks: vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::Exact] },
    };
    let bad = Block {
        steps: vec![],
        end: End::Return { map, checks: vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::Local(999)] },
    };
    Certificate {
        improvements: vec![],
        bijections: vec![],
        points: vec![],
        claims: vec![claim.clone(), claim.clone()],
        blocks: vec![good, bad],
    }
}

#[test]
fn terminal_obligation_failure_reports_block_and_obligation() {
    let (source, target) = models();
    let mut cert = certificate();
    let End::Return { checks, .. } = &mut cert.blocks[0].end else { panic!() };
    checks[3] = Ref::Local(999);
    let plain = verify_request(&source, &target, &cert, &request(), &Limits::default()).unwrap_err();
    let mut diag = Diagnostics::default();
    let error =
        verify_request_with_diagnostics(&source, &target, &cert, &request(), &Limits::default(), &mut diag)
            .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type; obligation 3");
    assert_eq!(diag.location.claim, Some(0));
    assert_eq!(diag.location.block, Some(0));
    assert_eq!(diag.location.obligation, Some(3));
    assert_eq!(diag.location.step, None);
    assert_eq!(diag.location.point, None);
}

#[test]
fn step_failure_reports_the_failing_step_index() {
    let model = empty();
    let claim = empty_claim();
    let block = Block {
        steps: vec![
            Step::Lin { id: 1, kind: Kind::Le, constant: q(0), terms: vec![] },
            Step::Lin { id: 2, kind: Kind::Le, constant: q(0), terms: vec![(Ref::Local(999), q(1))] },
        ],
        end: End::Return { map: vec![], checks: vec![] },
    };
    let cert = Certificate { improvements: vec![], bijections: vec![], points: vec![], claims: vec![claim.clone()], blocks: vec![block] };
    let request = Request { improvements: vec![], bijections: vec![], claims: vec![claim], points: vec![] };
    let plain = verify_request(&model, &model, &cert, &request, &Limits::default()).unwrap_err();
    let mut diag = Diagnostics::default();
    let error =
        verify_request_with_diagnostics(&model, &model, &cert, &request, &Limits::default(), &mut diag)
            .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type");
    assert_eq!(diag.location.claim, Some(0));
    assert_eq!(diag.location.block, Some(0));
    assert_eq!(diag.location.step, Some(1));
    assert_eq!(diag.location.obligation, None);
    assert_eq!(diag.location.point, None);
}

#[test]
fn failing_second_claim_identifies_its_index() {
    let (source, target) = (single(), single());
    let cert = bounded_certificate();
    let request =
        Request { improvements: vec![], bijections: vec![], claims: cert.claims.clone(), points: vec![] };
    let plain = verify_request(&source, &target, &cert, &request, &Limits::default()).unwrap_err();
    let mut diag = Diagnostics::default();
    let error =
        verify_request_with_diagnostics(&source, &target, &cert, &request, &Limits::default(), &mut diag)
            .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type; obligation 2");
    assert_eq!(diag.location.claim, Some(1));
    assert_eq!(diag.location.block, Some(1));
    assert_eq!(diag.location.obligation, Some(2));
    assert_eq!(diag.location.step, None);
    assert_eq!(diag.location.point, None);
}

#[test]
fn claim_slice_entry_point_reports_the_failing_index() {
    let (source, target) = (single(), single());
    let cert = bounded_certificate();
    let claims = cert.claims.clone();
    let plain = verify(&source, &target, &cert, &claims, &Limits::default()).unwrap_err();
    let mut diag = Diagnostics::default();
    let error = verify_with_diagnostics(&source, &target, &cert, &claims, &Limits::default(), &mut diag)
        .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type; obligation 2");
    assert_eq!(diag.location.claim, Some(1));
    assert_eq!(diag.location.block, Some(1));
    assert_eq!(diag.location.obligation, Some(2));
}

#[test]
fn point_witness_failure_reports_point_index() {
    let (source, target) = models();
    let claim = PointClaim::Feasible { target: false, integers: false, objective: None };
    let cert = Certificate {
        improvements: vec![],
        bijections: vec![],
        claims: vec![],
        blocks: vec![],
        points: vec![
            PointWitness { claim: claim.clone(), values: vec![q(0), q(0)], refutation: None },
            PointWitness { claim: claim.clone(), values: vec![q(0), q(5)], refutation: None },
        ],
    };
    let request =
        Request { improvements: vec![], bijections: vec![], claims: vec![], points: vec![claim.clone(), claim] };
    let plain = verify_request(&source, &target, &cert, &request, &Limits::default()).unwrap_err();
    assert_eq!(plain, "INVALID point: infeasible point (witness 1)");
    // Through the request entry point every earlier phase is cleared first.
    let mut diag = Diagnostics::default();
    let error =
        verify_request_with_diagnostics(&source, &target, &cert, &request, &Limits::default(), &mut diag)
            .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(diag.location.point, Some(1));
    assert_eq!(diag.location.claim, None);
    assert_eq!(diag.location.block, None);
    assert_eq!(diag.location.step, None);
    assert_eq!(diag.location.obligation, None);
    // Called directly, the fields this entry point never learns are untouched.
    let mut diag = Diagnostics { location: Location { claim: Some(4), block: Some(2), ..Location::default() } };
    assert_eq!(
        verify_points_with_diagnostics(&source, &target, &cert, &request, &Limits::default(), &mut diag)
            .unwrap_err(),
        plain
    );
    assert_eq!(diag.location.point, Some(1));
    assert_eq!(diag.location.claim, Some(4));
    assert_eq!(diag.location.block, Some(2));
    assert_eq!(verify_points(&source, &target, &cert, &request, &Limits::default()).unwrap_err(), plain);
}

#[test]
fn refutation_failure_reports_step_and_leaves_claim_point_block() {
    let block = Block {
        steps: vec![
            lin(1, vec![]),
            Step::Lin { id: 2, kind: Kind::Le, constant: q(0), terms: vec![(Ref::RowUpper(0), q(1))] },
        ],
        end: End::Absurd { fact: Ref::Local(2) },
    };
    let plain = verify_lp_refutation(&empty(), &block, &Limits::default()).unwrap_err();
    let mut diag = Diagnostics { location: Location { claim: Some(4), point: Some(7), block: Some(2), ..Location::default() } };
    let error =
        verify_lp_refutation_with_diagnostics(&empty(), &block, &Limits::default(), &mut diag).unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type");
    assert_eq!(diag.location.step, Some(1));
    assert_eq!(diag.location.obligation, None);
    assert_eq!(diag.location.claim, Some(4));
    assert_eq!(diag.location.point, Some(7));
    assert_eq!(diag.location.block, Some(2));
}

#[test]
fn injectivity_equality_failure_reports_obligation() {
    let model = single();
    let map = [Expr::var(0)];
    let proof = EqualityProof { steps: vec![lin(5, vec![])], checks: vec![Ref::Local(999)] };
    let plain = verify_injectivity(&model, &model, &map, false, &proof, &Limits::default()).unwrap_err();
    let mut diag = Diagnostics::default();
    let error = verify_injectivity_with_diagnostics(&model, &model, &map, false, &proof, &Limits::default(), &mut diag)
        .unwrap_err();
    assert_eq!(error, plain);
    assert_eq!(error, "INVALID fact reference or type");
    assert_eq!(diag.location.obligation, Some(0));
    assert_eq!(diag.location.step, None);
    assert_eq!(diag.location.claim, None);
    assert_eq!(diag.location.block, None);
    assert_eq!(diag.location.point, None);
}

#[test]
fn diagnostics_never_change_an_error_result() {
    let (source, target) = models();
    let mut obligation = certificate();
    let End::Return { checks, .. } = &mut obligation.blocks[0].end else { panic!() };
    checks[3] = Ref::Local(999);
    let mut step = certificate();
    step.blocks[0].steps.insert(
        0,
        Step::Lin { id: 900, kind: Kind::Le, constant: q(0), terms: vec![(Ref::Assumption(7), q(1))] },
    );
    let mut contract = certificate();
    contract.points.push(PointWitness {
        claim: PointClaim::Feasible { target: false, integers: false, objective: None },
        values: vec![q(0), q(0)],
        refutation: None,
    });
    for cert in [obligation, step, contract] {
        let plain = verify_request(&source, &target, &cert, &request(), &Limits::default());
        assert!(plain.is_err());
        let mut diag = Diagnostics::default();
        let reported =
            verify_request_with_diagnostics(&source, &target, &cert, &request(), &Limits::default(), &mut diag);
        assert_eq!(plain, reported);
    }
}

#[test]
fn valid_fixture_returns_identical_statistics() {
    let (source, target) = models();
    let cert = certificate();
    let plain = verify_request(&source, &target, &cert, &request(), &Limits::default()).unwrap();
    let mut diag = Diagnostics::default();
    let reported =
        verify_request_with_diagnostics(&source, &target, &cert, &request(), &Limits::default(), &mut diag)
            .unwrap();
    assert_eq!(plain, reported);
    assert_eq!(plain.obligations, 8);
    assert_eq!(plain.branches, 1);
    assert!(plain.work > 0);
    // Success values are documented as not load-bearing: the last phase reset
    // leaves nothing reported for a request without points or improvements.
    assert_eq!(diag.location, Location::default());
}

#[test]
fn location_serialization_omits_unknown_fields() {
    assert_eq!(serde_json::to_value(Location::default()).unwrap(), json!({}));
    let location = Location { claim: Some(0), obligation: Some(3), ..Location::default() };
    assert_eq!(serde_json::to_value(location).unwrap(), json!({"claim": 0, "obligation": 3}));
    assert_eq!(
        serde_json::to_value(Diagnostics { location }).unwrap(),
        json!({"location": {"claim": 0, "obligation": 3}})
    );
}
