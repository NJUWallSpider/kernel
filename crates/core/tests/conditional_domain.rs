//! Caller-bound affine restrictions are conditional propositions, not new facts
//! about every feasible input or an unchecked assertion about the optimal face.
use kernel_core::{codec, model::{Expr, Model, Q, Var}, proof::*, rpa,
    verify::{verify_request, Limits, Statistics}};

fn q(n: i64) -> Q { Q::from_integer(n.into()) }
fn e(c: i64, terms: &[(u32, i64)]) -> Expr {
    Expr { constant: q(c), terms: terms.iter().map(|&(i,v)|(i,q(v))).collect() }
}
fn claim(reverse: bool) -> Claim {
    Claim { reverse, input_integers: false, output_integers: false,
        objective: Objective::Equal, projection: vec![(0,0)], affine_projection: vec![],
        inverse: None, input_objective_lower: None, input_objective_level: None,
        input_halfspace: None }
}
fn request(c: &Certificate) -> Request {
    Request { claims: c.claims.clone(), points: c.points.iter().map(|p|p.claim.clone()).collect(),
        improvements: c.improvements.iter().map(|p|p.claim.clone()).collect(),
        bijections: c.bijections.iter().map(|p|p.claim.clone()).collect() }
}
fn check(s: &Model, t: &Model, c: &Certificate) -> Result<Statistics,String> {
    verify_request(s,t,c,&request(c),&Limits::default())
}
fn fixture() -> (Model, Model, Certificate) {
    let s=Model { name:"source".into(), vars:vec![Var {name:"x".into(),integer:false,
        lower:Some(q(0)),upper:Some(q(2))}],rows:vec![],objective:e(7,&[(0,1)]) };
    let mut t=s.clone(); t.name="target".into(); t.vars[0].upper=Some(q(0));
    let mut cl=claim(false); cl.input_halfspace=Some(Expr::var(0));
    let b=Block { steps:vec![], end:End::Return { map:vec![Expr::var(0)],
        checks:vec![Ref::VarLower(0),Ref::RowUpper(0),Ref::Exact,Ref::Exact] } };
    (s,t,Certificate {claims:vec![cl],blocks:vec![b],..Certificate::default()})
}

#[test]
fn conditional_identity_and_original_request_binding() {
    let (s,t,c)=fixture(); let stats=check(&s,&t,&c).unwrap(); assert_eq!(stats.obligations,4);
    let r=request(&c);
    for predicate in [None,Some(e(-1,&[(0,1)])),Some(e(0,&[(0,-1)]))] {
        let mut bad=c.clone(); bad.claims[0].input_halfspace=predicate;
        assert!(verify_request(&s,&t,&bad,&r,&Limits::default()).is_err());
        assert!(check(&s,&t,&bad).is_err());
    }
    let bytes=codec::encode_certificate(&c).unwrap(); assert_eq!(&bytes[4..6],&10u16.to_le_bytes());
    assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap(); assert_eq!(rpa::assemble(&text).unwrap(),c);
    for v in 1..10 { assert!(rpa::assemble(&text.replacen("RPA 10",&format!("RPA {v}"),1)).is_err()); }
}

#[test]
fn affine_constants_scales_and_fractional_continuous_domains() {
    // Exact integer cross-products, independent of the verifier's rational
    // evaluation, check the interval membership for every generated fixture.
    for a in 1..=7i64 { for n in 0..=6i64 { for d in 3..=7i64 {
        let (s,mut t,mut c)=fixture(); let cut=Q::new(n.into(),d.into());
        t.vars[0].upper=Some(cut.clone());
        c.claims[0].input_halfspace=Some(Expr {constant:-q(a)*&cut,terms:vec![(0,q(a))]});
        c.blocks[0].steps=vec![Step::Lin{id:0,kind:Kind::Le,constant:q(0),
            terms:vec![(Ref::RowUpper(0),Q::new(1.into(),a.into()))]}];
        if let End::Return{checks,..}=&mut c.blocks[0].end {checks[1]=Ref::Local(0);}
        check(&s,&t,&c).unwrap();
        for p in 0..=20i128 {
            let in_restricted=p<=20 && i128::from(a)*(p*i128::from(d)-10*i128::from(n))<=0;
            let in_target=p*i128::from(d)<=10*i128::from(n);
            assert_eq!(in_restricted,in_target);
        }
    } } }
    let (mut s,mut t,mut c)=fixture(); s.vars[0].integer=true;t.vars[0].integer=true;
    c.claims[0].input_halfspace=Some(Expr {constant:Q::new((-1).into(),2.into()),terms:vec![(0,q(1))]});
    t.vars[0].upper=Some(Q::new(1.into(),2.into()));
    check(&s,&t,&c).unwrap(); // Both declared integers are relaxed by LP mode.
    c.claims[0].output_integers=true;
    if let End::Return{checks,..}=&mut c.blocks[0].end {checks.insert(2,Ref::VarInt(0));}
    assert!(check(&s,&t,&c).is_err());
}

#[test]
fn restriction_is_not_a_global_fact_or_an_attainment_statement() {
    let (s,t,mut c)=fixture(); c.claims[0].input_halfspace=Some(e(1,&[]));
    c.blocks[0]=Block {steps:vec![],end:End::Absurd{fact:Ref::RowUpper(0)}};
    check(&s,&t,&c).unwrap(); // The restricted set is empty, the original is not.
    c.points.push(PointWitness { claim:PointClaim::Feasible{target:false,integers:false,
        objective:Some(q(9))},values:vec![q(2)],refutation:None });
    check(&s,&t,&c).unwrap();
    c.claims.push(claim(false));c.blocks.push(c.blocks[0].clone());
    assert!(check(&s,&t,&c).is_err()); // No domain-row leak to the next direction.
}

#[test]
fn original_coordinates_are_validated_even_before_vacuous_execution() {
    let (s,t,c)=fixture();
    for bad_expr in [Expr::var(1),e(1,&[(0,1),(0,1)]),e(1,&[(0,0)])] {
        let mut bad=c.clone();bad.claims[0].input_halfspace=Some(bad_expr);
        bad.blocks[0].end=End::Absurd{fact:Ref::RowUpper(0)};
        assert!(check(&s,&t,&bad).is_err());
    }
    let mut bad=c.clone(); bad.claims[0].input_halfspace=Some(Expr::var(1));
    bad.blocks[0]=Block {steps:vec![],end:End::IntervalLift {intervals:vec![IntervalWitness {
        lower:vec![Expr::zero()],upper:vec![Expr::zero()],checks:vec![Ref::Exact]}],
        body:Box::new(c.blocks[0].clone())}};
    assert!(check(&s,&t,&bad).is_err()); // Future lift coordinates cannot be captured.
}

#[test]
fn objective_level_then_halfspace_rows_survive_lifts_and_share_budget() {
    let (s,t,mut c)=fixture(); c.claims[0].input_objective_level=Some(q(7));
    if let End::Return{checks,..}=&mut c.blocks[0].end {checks[1]=Ref::RowUpper(1);}
    let body=c.blocks[0].clone(); c.blocks[0]=Block{steps:vec![],end:End::IntervalLift {
        intervals:vec![],body:Box::new(body)}};
    let stats=check(&s,&t,&c).unwrap();assert_eq!(stats.objective_level_domains,1);
    assert!(verify_request(&s,&t,&c,&request(&c),&Limits{work:stats.work-1,..Limits::default()})
        .unwrap_err().starts_with("RESOURCE_LIMIT"));
    c.claims[0].input_objective_level=None;
    assert!(check(&s,&t,&c).is_err());
}

#[test]
fn whole_model_contracts_and_legacy_inverse_do_not_inherit_conditional_domains() {
    let (s,t,c)=fixture();
    for point in [PointClaim::Strictness{inclusion_claim:0},PointClaim::FiberStrictness{inclusion_claim:0}] {
        let mut bad=c.clone(); bad.points.push(PointWitness{claim:point,values:vec![],refutation:None});
        assert!(check(&s,&t,&bad).unwrap_err().contains("unrestricted"));
        assert!(kernel_core::point::verify_points(&s,&t,&bad,&request(&bad),&Limits::default()).is_err());
    }
    let mut bad=c.clone();bad.claims.push(claim(true));bad.blocks.push(c.blocks[0].clone());
    bad.bijections.push(BijectionWitness { claim:BijectionClaim{forward_claim:0,reverse_claim:1},
        injectivity:EqualityProof{steps:vec![],checks:vec![]} });
    assert!(check(&s,&t,&bad).unwrap_err().contains("unrestricted"));
    bad.bijections.clear();
    for i in 0..2 {let mut b=bad.clone();b.claims[i].inverse=Some((1-i) as u32);
        assert!(check(&s,&t,&b).unwrap_err().contains("inverse"));}
}

#[test]
fn strict_improvement_plus_explicit_conditional_projection_on_optimal_face() {
    let s=Model{name:"source".into(),vars:vec![
        Var{name:"retained".into(),integer:true,lower:Some(q(0)),upper:Some(q(1))},
        Var{name:"terminal".into(),integer:false,lower:Some(q(0)),upper:None}],
        rows:vec![],objective:e(5,&[(0,1),(1,1)])};
    let t=Model{name:"target".into(),vars:vec![s.vars[0].clone()],rows:vec![],objective:e(5,&[(0,1)])};
    let mut forward=claim(false);forward.input_integers=true;forward.output_integers=true;
    forward.input_halfspace=Some(Expr::var(1));
    let mut reverse=claim(true);reverse.input_integers=true;reverse.output_integers=true;
    let improvement=ImprovementClaim{target:false,integers:true,positive:Expr::var(1)};
    let mut c=Certificate{claims:vec![forward,reverse],blocks:vec![
        Block{steps:vec![Step::EqPair{id:0,positive:Ref::RowUpper(0),negative:Ref::VarLower(1)},
            Step::Lin{id:1,kind:Kind::Eq,constant:q(0),terms:vec![(Ref::Local(0),q(-1))]}],
            end:End::Return{map:vec![Expr::var(0)],checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::VarInt(0),Ref::Local(1),Ref::Exact]}},
        Block{steps:vec![],end:End::Return{map:vec![Expr::var(0),Expr::zero()],checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::VarInt(0),Ref::Exact,Ref::Exact,Ref::Exact]}}
        ],improvements:vec![ImprovementWitness{claim:improvement,block:Block{steps:vec![],
            end:End::ImproveReturn{map:vec![Expr::var(0),Expr::zero()],checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::VarInt(0),Ref::Exact,Ref::Exact],margin:ImprovementMargin::Predicate(q(1))}}}],..Certificate::default()};
    assert_eq!(check(&s,&t,&c).unwrap().improvements,1);
    // Changing the retained map is not permitted by a mere equal optimum value.
    if let End::Return{map,..}=&mut c.blocks[0].end {map[0]=Expr::zero();}
    assert!(check(&s,&t,&c).is_err());
}
