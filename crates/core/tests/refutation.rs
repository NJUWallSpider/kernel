use kernel_core::{codec,model::{Expr,Model,Q,Var},proof::*,rpa,verify::{verify_lp_refutation,Limits}};
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn e(n:i64)->Expr{Expr{constant:q(n),terms:vec![]}}
fn model()->Model{Model{name:"empty_lp".into(),vars:vec![Var{name:"x".into(),integer:true,lower:Some(q(1)),upper:Some(q(0))}],rows:vec![],objective:e(0)}}
fn contradiction()->Block{Block{steps:vec![Step::Lin{id:0,kind:Kind::Le,constant:q(0),terms:vec![(Ref::VarLower(0),q(1)),(Ref::VarUpper(0),q(1))]}],end:End::Absurd{fact:Ref::Local(0)}}}
#[test]fn refutation_is_lp_only_and_requires_a_checked_contradiction(){
    verify_lp_refutation(&model(),&contradiction(),&Limits::default()).unwrap();
    let mut bad=contradiction();if let Step::Lin{terms,..}=&mut bad.steps[0]{terms.pop();}assert!(verify_lp_refutation(&model(),&bad,&Limits::default()).is_err());
    let mut b=contradiction();b.steps.insert(0,Step::Lin{id:8,kind:Kind::Int,constant:q(0),terms:vec![(Ref::VarInt(0),q(1))]});assert!(verify_lp_refutation(&model(),&b,&Limits::default()).is_err());
}
#[test]fn return_and_existence_endpoints_cannot_refute_even_an_empty_model(){
    for end in [End::Return{map:vec![],checks:vec![]},End::IntervalLift{intervals:vec![],body:Box::new(contradiction())},End::FlowLift{witness:FlowWitness{nodes:1,arcs:vec![],groups:vec![]},body:Box::new(contradiction())}]{let block=Block{steps:vec![],end};assert!(verify_lp_refutation(&model(),&block,&Limits::default()).unwrap_err().contains("only Absurd/Split"));}
}
#[test]fn refutation_all_branches_are_checked_and_siblings_are_isolated(){
    let good=Block{steps:vec![],end:End::Split{expression:Expr::var(0),integer:None,left:Box::new(contradiction()),right:Box::new(contradiction())}};verify_lp_refutation(&model(),&good,&Limits::default()).unwrap();
    let mut bad=good.clone();if let End::Split{right,..}=&mut bad.end{right.steps.clear();}assert!(verify_lp_refutation(&model(),&bad,&Limits::default()).is_err());
    let mut bad=good.clone();if let End::Split{right,..}=&mut bad.end{right.end=End::Return{map:vec![],checks:vec![]};}assert!(verify_lp_refutation(&model(),&bad,&Limits::default()).is_err());
    assert!(verify_lp_refutation(&model(),&good,&Limits{depth:1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
#[test]fn local_cases_may_derive_refutation_but_state_never_leaks_between_calls(){
    let d=Derivation{steps:contradiction().steps,end:DerivationEnd::Witness(Ref::Local(0))};
    let block=Block{steps:vec![Step::Cases(Box::new(CasesStep{id:2,kind:Kind::Le,expression:e(1),split:Expr::var(0),integer:None,left:Box::new(d.clone()),right:Box::new(d)}))],end:End::Absurd{fact:Ref::Local(2)}};
    let stats=verify_lp_refutation(&model(),&block,&Limits::default()).unwrap();assert_eq!(stats.branches,1);
    let leak=Block{steps:vec![],end:End::Absurd{fact:Ref::Local(2)}};assert!(verify_lp_refutation(&model(),&leak,&Limits::default()).is_err());
    assert!(verify_lp_refutation(&model(),&block,&Limits{work:stats.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
#[test]fn v6_point_refutation_wire_depth_and_versions_are_checked(){
    let c=Certificate { improvements:vec![], bijections:vec![],claims:vec![],blocks:vec![],points:vec![PointWitness{claim:PointClaim::FiberStrictness{inclusion_claim:0},values:vec![q(0)],refutation:Some(contradiction())}]};
    let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&6u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);let text=rpa::disassemble(&c).unwrap();assert_eq!(rpa::assemble(&text).unwrap(),c);
    for version in [1u16,2,3,4,5]{let mut b=bytes.clone();b[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&b).is_err());assert!(rpa::assemble(&text.replacen("RPA 6",&format!("RPA {version}"),1)).is_err());}
    for n in 0..bytes.len(){let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err());}
    for i in 16..bytes.len(){for value in [0,1,127,255]{let mut b=bytes.clone();b[i]=value;if let Ok(decoded)=codec::decode_certificate(&b){if let Some(block)=decoded.points.first().and_then(|p|p.refutation.as_ref()){let _=verify_lp_refutation(&model(),block,&Limits::default());}}}}
    let mut deep=contradiction();for _ in 0..64{deep=Block{steps:vec![],end:End::Split{expression:e(0),integer:None,left:Box::new(deep),right:Box::new(contradiction())}};}
    let mut bad=c.clone();bad.points[0].refutation=Some(deep);assert!(codec::encode_certificate(&bad).unwrap_err().starts_with("RESOURCE_LIMIT"));
    // Even an unsupported endpoint must be inspected for version/depth discovery.
    let mut c=c; c.points[0].refutation=Some(Block{steps:vec![],end:End::IntervalLift{intervals:vec![],body:Box::new(contradiction())}});assert_eq!(codec::certificate_version(&c).unwrap(),6);
}
