use kernel_compiler_core::model::{Identifier, Model};
use kernel_compiler_core::proof::{ProofCore, kind_name};
use kernel_core::model::{Expr, Q, Var};
use kernel_core::proof::{Kind, Ref};
use kernel_core::verify::Limits;

fn model() -> Model {
    Model::new(
        "m".into(),
        vec![Var {
            name: "x".into(),
            integer: false,
            lower: Some(Q::from_integer(0.into())),
            upper: Some(Q::from_integer(1.into())),
        }],
        Vec::new(),
        Expr::zero(),
    )
    .unwrap()
}

#[test]
fn expression_and_model_bounds_are_exact() {
    let x = kernel_compiler_core::expr::canonical(
        Q::from_integer(0.into()),
        [
            (0, Q::new(1.into(), 3.into())),
            (0, Q::new(2.into(), 3.into())),
        ],
    )
    .unwrap();
    assert_eq!(x, Expr::var(0));
    let model = model();
    assert_eq!(
        model.fact("VarLower", &Identifier::Index(0)).unwrap().1,
        Expr {
            constant: Q::from_integer(0.into()),
            terms: vec![(0, Q::from_integer((-1).into()))]
        }
    );
    assert_eq!(
        model
            .fact("VarUpper", &Identifier::Name("x".into()))
            .unwrap()
            .1,
        Expr {
            constant: Q::from_integer((-1).into()),
            terms: vec![(0, Q::from_integer(1.into()))]
        }
    );
}

#[test]
fn native_completion_and_rpa_compilation_verify() {
    let model = model();
    let mut proof = ProofCore::new(model.clone(), model).unwrap();
    proof
        .complete(
            proof.forward,
            &[Expr::var(0)],
            &[],
            true,
            &Limits::default(),
        )
        .unwrap();
    proof
        .complete(
            proof.reverse,
            &[Expr::var(0)],
            &[],
            true,
            &Limits::default(),
        )
        .unwrap();
    let compiled = proof.compile(&Limits::default()).unwrap();
    assert!(compiled.rpa.starts_with("RPA 12\n"));
    assert!(!compiled.rpx.is_empty());
    let stats = proof.verify(&Limits::default()).unwrap();
    assert_eq!(stats.obligations, 6);
    assert_eq!(
        compiled.certificate.forward.end,
        kernel_core::proof::End::Return {
            map: vec![Expr::var(0)],
            checks: vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::Exact],
        }
    );
}

#[test]
fn completion_reports_undischarged_obligations() {
    let model = model();
    let target = model
        .with_bounds(
            0,
            Some(Some(Q::from_integer(0.into()))),
            Some(Some(Q::from_integer(0.into()))),
        )
        .unwrap();
    let mut proof = ProofCore::new(model, target).unwrap();
    let error = proof
        .complete(
            proof.forward,
            &[Expr::var(0)],
            &[],
            true,
            &Limits::default(),
        )
        .unwrap_err();
    assert!(error.contains("undischarged"));
}

#[test]
fn kinds_have_stable_names() {
    assert_eq!(kind_name(Kind::Le), "Le");
    assert_eq!(kind_name(Kind::Eq), "Eq");
    assert_eq!(kind_name(Kind::Int), "Int");
}
