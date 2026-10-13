use kernel_core::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, Q};
use kernel_core::point::verify_points;
use kernel_core::proof::{Block, Certificate, Claim, End, Objective, PointClaim, PointWitness, Ref, Request};
use kernel_core::verify::{verify_request, Limits};
use num_bigint::BigInt;

fn q(s: &str) -> Q { parse_q(s).unwrap() }
fn expr(c: &str, terms: &[(u32, &str)]) -> Expr {
    Expr { constant:q(c), terms:terms.iter().map(|(i,c)|(*i,q(c))).collect() }
}
fn model(n: usize) -> Model {
    Model { name:"image".into(), vars:(0..n).map(|i|Var {
        name:format!("x{i}"), integer:true, lower:Some(q("0")), upper:Some(q("1")),
    }).collect(), rows:vec![], objective:Expr::zero() }
}
fn request(claim: PointClaim, values: Vec<Q>) -> (Certificate, Request) {
    (Certificate { points:vec![PointWitness {claim:claim.clone(),values,refutation:None}],
        ..Certificate::default() },
     Request {points:vec![claim], ..Request::default()})
}
fn fixture() -> (Model, Model, Certificate, Request) {
    let mut source=model(2);
    source.rows.push(Row {name:"sum".into(),expr:expr("0",&[(0,"1"),(1,"1")]),
        lower:Some(q("1")),upper:Some(q("1"))});
    let mut target=model(1);
    target.rows.push(Row {name:"fixed".into(),expr:Expr::var(0),
        lower:Some(q("0")),upper:Some(q("0"))});
    let (cert, req)=request(PointClaim::ImageExclusion {point_in_target:false,
        map:vec![expr("1/3",&[(0,"1/3")])]},vec![q("1/2"),q("1/2")]);
    (source,target,cert,req)
}

#[test]
fn complete_lp_point_and_affine_image_without_inclusion_claim() {
    let (source,target,cert,req)=fixture();
    assert!(req.claims.is_empty());
    let stats=verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap();
    assert_eq!(stats.points,1);
    // Source integrality is intentionally relaxed. The claim is about LPs.
    assert!(source.vars.iter().all(|v|v.integer));
    let mut source=source.clone();source.objective=expr("1000",&[(0,"-1")]);
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok());
}

#[test]
fn direction_and_map_are_bound_to_the_actual_models_and_caller() {
    let (source,target,cert,req)=fixture();
    let mut bad=cert.clone();
    let PointClaim::ImageExclusion {point_in_target,..}=&mut bad.points[0].claim else {panic!()};
    *point_in_target=true;
    assert!(verify_request(&source,&target,&bad,&req,&Limits::default()).unwrap_err().contains("contract"));
    let mut reverse=req.clone();reverse.points[0]=bad.points[0].claim.clone();
    assert!(verify_request(&target,&source,&bad,&reverse,&Limits::default()).is_ok());
    assert!(verify_request(&source,&target,&bad,&reverse,&Limits::default()).is_err());
    let mut bad=cert.clone();
    let PointClaim::ImageExclusion {map,..}=&mut bad.points[0].claim else {panic!()};
    map[0]=Expr::zero();
    assert!(verify_request(&source,&target,&bad,&req,&Limits::default()).unwrap_err().contains("contract"));
    let mut weaker=req;weaker.points[0]=bad.points[0].claim.clone();
    assert!(verify_request(&source,&target,&bad,&weaker,&Limits::default()).unwrap_err().contains("violates no actual"));
}

#[test]
fn full_source_bounds_and_rows_are_required() {
    let (source,target,cert,req)=fixture();
    for values in [vec![q("-1"),q("2")],vec![q("1/2"),q("0")]] {
        let mut bad=cert.clone();bad.points[0].values=values;
        assert!(verify_request(&source,&target,&bad,&req,&Limits::default()).unwrap_err().contains("not LP feasible"));
    }
    for values in [vec![q("1/2")],vec![q("1/2"),q("1/2"),q("0")]] {
        let mut bad=cert.clone();bad.points[0].values=values;
        assert!(verify_request(&source,&target,&bad,&req,&Limits::default()).unwrap_err().contains("point dimension"));
    }
}

#[test]
fn output_must_violate_an_actual_bound_or_row_not_just_integrality() {
    let (source,mut target,cert,req)=fixture();
    target.rows.clear();
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap_err().contains("violates no actual"));
    target.vars[0].lower=Some(q("2/3"));
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok());
    target.vars[0].lower=Some(q("0"));target.vars[0].upper=Some(q("1/3"));
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok());
    target.vars[0].upper=Some(q("1/2"));
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_err());
}

#[test]
fn every_image_coordinate_and_expression_is_validated() {
    let (source,mut target,cert,_)=fixture();target.vars.push(Var {
        name:"extra".into(),integer:false,lower:None,upper:None,
    });
    let malformed=[vec![],vec![Expr::zero()],vec![Expr::zero();3],
        vec![Expr::var(0),Expr::var(2)],
        vec![Expr::var(0),expr("0",&[(1,"1"),(0,"1")])],
        vec![Expr::var(0),expr("0",&[(0,"1"),(0,"1")])],
        vec![Expr::var(0),expr("0",&[(0,"0")])]];
    for map in malformed {
        let (bad,req)=request(PointClaim::ImageExclusion {point_in_target:false,map},cert.points[0].values.clone());
        // First image coordinate already violates fixed=0; malformed trailing
        // expressions must nevertheless be rejected, never skipped.
        assert!(verify_request(&source,&target,&bad,&req,&Limits::default()).is_err());
    }
    let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,
        map:vec![Expr::var(0),expr("3/7",&[])]},cert.points[0].values.clone());
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok());
}

#[test]
fn no_refutation_is_accepted_for_image_exclusion() {
    let (source,target,mut cert,req)=fixture();
    cert.points[0].refutation=Some(Block {steps:vec![],end:End::Absurd {fact:Ref::Exact}});
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap_err().contains("surplus point refutation"));
}

#[test]
fn scalar_limits_apply_to_every_map_expression_and_intermediate_product() {
    let mut source=model(1);source.vars[0].lower=None;source.vars[0].upper=None;
    let mut target=model(2);target.vars[0].upper=Some(q("0"));
    let big=Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize-1));
    let map=vec![expr("1",&[]),Expr {constant:q("0"),terms:vec![(0,big.clone())]}];
    let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,map},vec![big]);
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let oversized=Q::from_integer(BigInt::from(1u8) << MAX_Q_BITS as usize);
    for map in [vec![expr("1",&[]),Expr {constant:oversized.clone(),terms:vec![]}],
        vec![expr("1",&[]),Expr {constant:q("0"),terms:vec![(0,oversized)]}]] {
        let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,map},vec![q("0")]);
        assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
    }
    let big=Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize-1));
    let mut source=model(2);
    for v in &mut source.vars {v.lower=None;v.upper=None;}
    let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,
        map:vec![expr("1",&[]),Expr {constant:big.clone(),terms:vec![(0,big.clone()),(1,-big)]}]},
        vec![q("1"),q("2")]);
    // The second complete image coordinate ends at zero, but an oversized
    // intermediate sum cannot be hidden by its later exact cancellation.
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn request_wide_work_budget_includes_validation_mapping_and_all_points() {
    let (source,target,cert,req)=fixture();
    let used=verify_points(&source,&target,&cert,&req,&Limits::default()).unwrap().work;
    let mut limits=Limits::default();limits.work=used;
    assert!(verify_points(&source,&target,&cert,&req,&limits).is_ok());
    limits.work=used-1;
    assert!(verify_points(&source,&target,&cert,&req,&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut pair=cert.clone();pair.points.push(cert.points[0].clone());
    let mut request=req.clone();request.points.push(req.points[0].clone());
    limits.work=used;
    assert!(verify_points(&source,&target,&pair,&request,&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    limits.work=used*2;
    assert!(verify_points(&source,&target,&pair,&request,&limits).is_ok());
}

#[test]
fn zero_dimensional_models_still_require_real_source_feasibility_and_target_violation() {
    let source=model(0);let mut target=model(0);
    target.rows.push(Row {name:"impossible".into(),expr:expr("1",&[]),lower:None,upper:Some(q("0"))});
    let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,map:vec![]},vec![]);
    assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok());
    assert!(verify_request(&source,&source,&cert,&req,&Limits::default()).is_err());
    assert!(verify_request(&target,&target,&cert,&req,&Limits::default()).unwrap_err().contains("not LP feasible"));
}

#[test]
fn image_point_and_directional_proof_share_the_same_request_budget() {
    let source=model(0);let mut target=model(0);
    target.rows.push(Row {name:"impossible".into(),expr:expr("1",&[]),lower:None,upper:Some(q("0"))});
    let (mut cert,mut req)=request(PointClaim::ImageExclusion {point_in_target:false,map:vec![]},vec![]);
    let claim=Claim {reverse:true,input_integers:false,output_integers:false,
        objective:Objective::None,projection:vec![],affine_projection:vec![],inverse:None,
        input_objective_lower:None,input_objective_level:None,input_halfspace:None};
    cert.claims.push(claim.clone());req.claims.push(claim);
    cert.blocks.push(Block {steps:vec![],end:End::Absurd {fact:Ref::RowUpper(0)}});
    let used=verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap().work;
    let point_only=verify_points(&source,&target,&cert,&req,&Limits::default()).unwrap().work;
    assert!(used>point_only);
    let mut limits=Limits::default();limits.work=used;
    assert!(verify_request(&source,&target,&cert,&req,&limits).is_ok());
    limits.work=used-1;
    assert!(verify_request(&source,&target,&cert,&req,&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn small_exact_grid_agrees_with_independent_integer_scaled_predicate() {
    let mut source=model(2);
    source.rows.push(Row {name:"sum".into(),expr:expr("0",&[(0,"1"),(1,"1")]),lower:None,upper:Some(q("1"))});
    let mut target=model(1);target.vars[0].upper=Some(q("2/3"));
    for x in -1..=3 {for y in -1..=3 {for constant in -1..=1 {for a in -2..=2 {for b in -2..=2 {
        // x,y represent numerators over2. Image is (constant+a*x+b*y)/6.
        let image_numerator=constant+a*x+b*y;
        let expected=(0..=2).contains(&x)&&(0..=2).contains(&y)&&x+y<=2
            && !(0..=4).contains(&image_numerator);
        let map=vec![Expr {constant:q(&format!("{constant}/6")),terms:[(0,a),(1,b)].into_iter()
            .filter(|(_,c)|*c!=0).map(|(i,c)|(i,q(&format!("{c}/3")))).collect()}];
        let (cert,req)=request(PointClaim::ImageExclusion {point_in_target:false,map},
            vec![q(&format!("{x}/2")),q(&format!("{y}/2"))]);
        assert_eq!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_ok(),expected,
            "x={x}/2 y={y}/2 constant={constant}/6 a={a}/3 b={b}/3");
    }}}}}
}

#[test]
fn draft_v10_roundtrip_rejects_downgrades_and_truncation() {
    use kernel_core::{codec,rpa};
    let (source,target,cert,req)=fixture();
    let bytes=codec::encode_certificate(&cert).unwrap();
    assert_eq!(&bytes[4..6],&10u16.to_le_bytes());
    let decoded=codec::decode_certificate(&bytes).unwrap();
    assert_eq!(decoded,cert);
    verify_request(&source,&target,&decoded,&req,&Limits::default()).unwrap();
    let text=rpa::disassemble(&cert).unwrap();
    assert!(text.starts_with("RPA 10\n"));
    assert_eq!(rpa::assemble(&text).unwrap(),cert);
    assert_eq!(rpa::parse_request(&serde_json::to_string(&req).unwrap()).unwrap(),req);
    for version in 1u16..10 {
        let mut bad=bytes.clone();bad[4..6].copy_from_slice(&version.to_le_bytes());
        assert!(codec::decode_certificate(&bad).is_err());
        assert!(rpa::assemble(&text.replacen("RPA 10",&format!("RPA {version}"),1)).is_err());
    }
    for n in 0..bytes.len() {
        let mut bad=bytes[..n].to_vec();
        if n>=16 {bad[8..16].copy_from_slice(&(n as u64).to_le_bytes());}
        assert!(codec::decode_certificate(&bad).is_err());
    }
}
