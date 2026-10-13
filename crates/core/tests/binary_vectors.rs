//! Files produced by tests/vectors/generate_vectors.py, independently of Rust.
use kernel_core::{codec, proof::{Claim, Objective}, verify::{verify, Limits}};

fn requested(inverse: bool) -> Vec<Claim> {
    [false,true].into_iter().map(|reverse| Claim {input_halfspace:None,input_objective_level:None, affine_projection:vec![], input_objective_lower:None, reverse, input_integers:true, output_integers:true, objective:Objective::Equal, projection:vec![(0,0)], inverse:if inverse {Some(u32::from(!reverse))} else {None} }).collect()
}

#[test]
fn independently_encoded_models_and_certificates_verify() {
    let model=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    for (bytes, inverse) in [
        (include_bytes!("../../../tests/vectors/identity-ordinary.rpx").as_slice(),true),
        (include_bytes!("../../../tests/vectors/identity-nested.rpx").as_slice(),false),
        (include_bytes!("../../../tests/vectors/identity-local-v2.rpx").as_slice(),true),
    ] {
        let cert=codec::decode_certificate(bytes).unwrap();
        verify(&model,&model,&cert,&requested(inverse),&Limits::default()).unwrap();
        assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
    }
    assert_eq!(codec::encode_model(&model).unwrap(),include_bytes!("../../../tests/vectors/identity.mcm"));
}

#[test]
fn malformed_vectors_reject_for_the_documented_rule() {
    for (bytes, expected) in [
        (include_bytes!("../../../tests/vectors/invalid-unknown-step.rpx").as_slice(),"unknown step"),
        (include_bytes!("../../../tests/vectors/invalid-unknown-theorem.rpx").as_slice(),"unknown step"),
        (include_bytes!("../../../tests/vectors/invalid-reserved.rpx").as_slice(),"reserved"),
        (include_bytes!("../../../tests/vectors/invalid-trailing.rpx").as_slice(),"trailing"),
        (include_bytes!("../../../tests/vectors/invalid-truncated.rpx").as_slice(),"truncated"),
        (include_bytes!("../../../tests/vectors/resource-count.rpx").as_slice(),"RESOURCE_LIMIT"),
        (include_bytes!("../../../tests/vectors/invalid-v2-downgrade.rpx").as_slice(),"V2 step in V1"),
        (include_bytes!("../../../tests/vectors/invalid-v3-step-v2.rpx").as_slice(),"V3 step in older"),
        (include_bytes!("../../../tests/vectors/invalid-v3-point-tag.rpx").as_slice(),"V6 point in older"),
        (include_bytes!("../../../tests/vectors/invalid-v4-terminal-v3.rpx").as_slice(),"V4 terminal in older"),
        (include_bytes!("../../../tests/vectors/invalid-v5-terminal-v4.rpx").as_slice(),"V5 terminal in older"),
        (include_bytes!("../../../tests/vectors/invalid-v6-point-v5.rpx").as_slice(),"V6 point in older"),
    ] {
        assert!(codec::decode_certificate(bytes).unwrap_err().contains(expected),"{expected}");
    }
    let empty=codec::decode_certificate(include_bytes!("../../../tests/vectors/empty-syntax.rpx")).unwrap();
    let m=codec::decode_model(include_bytes!("../../../tests/vectors/empty.mcm")).unwrap();
    assert!(verify(&m,&m,&empty,&[],&Limits::default()).is_err());
}

#[test]
fn independently_encoded_v3_theorem_bound_and_point_verify(){
    use kernel_core::{proof::{PointClaim,Request},model::parse_q,verify::verify_request};
    let model=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let bytes=include_bytes!("../../../tests/vectors/identity-plotkin-v3.rpx");
    let cert=codec::decode_certificate(bytes).unwrap();
    let mut claim=requested(false).remove(0);claim.input_objective_lower=Some(parse_q("3").unwrap());
    let request=Request { improvements:vec![], bijections:vec![],claims:vec![claim],points:vec![PointClaim::Feasible{target:false,integers:true,objective:Some(parse_q("17/5").unwrap())}]};
    verify_request(&model,&model,&cert,&request,&Limits::default()).unwrap();
    assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
    // Point syntax is never skipped merely because a proof block already exists.
    for n in 0..bytes.len(){let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err());}
}

#[test]
fn independently_encoded_joint_flow_extension_verifies(){
    let source=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let target=codec::decode_model(include_bytes!("../../../tests/vectors/flow-target.mcm")).unwrap();
    let bytes=include_bytes!("../../../tests/vectors/flow-v4.rpx");
    let cert=codec::decode_certificate(bytes).unwrap();let request=vec![requested(false).remove(0)];
    let statistics=verify(&source,&target,&cert,&request,&Limits::default()).unwrap();
    assert_eq!((statistics.flow_generated_variables,statistics.flow_generated_rows),(1,2));
    assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
}

#[test]
fn independently_encoded_interval_and_affine_observation_verify(){
    use kernel_core::model::Expr;
    let source=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let target=codec::decode_model(include_bytes!("../../../tests/vectors/flow-target.mcm")).unwrap();
    let bytes=include_bytes!("../../../tests/vectors/interval-v5.rpx");let cert=codec::decode_certificate(bytes).unwrap();
    let mut claim=requested(false).remove(0);claim.affine_projection=vec![(Expr::var(0),Expr::var(1))];
    let stats=verify(&source,&target,&cert,&[claim],&Limits::default()).unwrap();
    assert_eq!((stats.interval_generated_variables,stats.interval_generated_rows),(1,2));
    assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
}

#[test]
fn independently_encoded_fiber_refutation_verifies(){
    use kernel_core::{proof::{PointClaim,Request},verify::verify_request};
    let source=codec::decode_model(include_bytes!("../../../tests/vectors/fiber-source.mcm")).unwrap();
    let target=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let bytes=include_bytes!("../../../tests/vectors/fiber-v6.rpx");let cert=codec::decode_certificate(bytes).unwrap();
    let mut claim=requested(false).remove(0);claim.input_integers=false;claim.output_integers=false;claim.objective=Objective::None;
    let request=Request { improvements:vec![], bijections:vec![],claims:vec![claim],points:vec![PointClaim::FiberStrictness{inclusion_claim:0}]};
    verify_request(&source,&target,&cert,&request,&Limits::default()).unwrap();assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
}
