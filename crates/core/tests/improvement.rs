use kernel_core::{codec,model::{Expr,Model,Q,Row,Var},proof::*,rpa,verify::{self,Limits}};
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn e(c:i64,terms:&[(u32,i64)])->Expr{Expr{constant:q(c),terms:terms.iter().map(|&(i,c)|(i,q(c))).collect()}}
fn model(integer:bool)->Model{Model{name:"improvement".into(),vars:vec![Var{name:"x".into(),integer,lower:Some(q(0)),upper:None}],rows:vec![],objective:e(7,&[(0,1)])}}
fn fixture(integer:bool)->(Model,Certificate,Request){
    let m=model(integer);let claim=ImprovementClaim{target:false,integers:integer,positive:Expr::var(0)};
    let block=Block{steps:vec![],end:End::ImproveReturn{map:vec![Expr::zero()],checks:vec![Ref::Exact;if integer{3}else{2}],margin:ImprovementMargin::Predicate(q(1))}};
    let c=Certificate{improvements:vec![ImprovementWitness{claim:claim.clone(),block}],..Certificate::default()};
    let r=Request{improvements:vec![claim],..Request::default()};(m,c,r)
}
fn check(m:&Model,c:&Certificate,r:&Request)->Result<verify::Statistics,String>{verify::verify_request(m,m,c,r,&Limits::default())}

#[test]
fn strict_predicate_margin_all_positive_rationals_and_objective_offsets(){
    for integer in [false,true]{let(m,c,r)=fixture(integer);let s=check(&m,&c,&r).unwrap();assert_eq!(s.improvements,1);assert_eq!(s.obligations,if integer{3}else{2});}
    // A continuous improvement can have arbitrarily small savings. A positive
    // predicate margin must not silently become a uniform positive constant.
    let(mut m,mut c,r)=fixture(false);m.objective=e(-19,&[(0,1)]);
    let half=Q::new(1.into(),2.into());let map=Expr{constant:q(0),terms:vec![(0,half.clone())]};
    c.improvements[0].block=Block{steps:vec![Step::Lin{id:0,kind:Kind::Le,constant:q(0),terms:vec![(Ref::VarLower(0),half.clone())]}],end:End::ImproveReturn{map:vec![map],checks:vec![Ref::Local(0),Ref::Exact],margin:ImprovementMargin::Predicate(half.clone())}};
    check(&m,&c,&r).unwrap();
    for n in 1..31{for d in 1..37{let x=Q::new(n.into(),d.into());let y=&x*&half;assert!(y>=q(0));assert!(&y+&half*&x==x);assert!(y<x);}}
}

#[test]
fn strict_boundary_requires_positive_refutation_or_full_improvement(){
    let(m,mut c,r)=fixture(true);
    c.improvements[0].block=Block{steps:vec![],end:End::Split{expression:Expr::var(0),integer:Some(Ref::VarInt(0)),
        left:Box::new(Block{steps:vec![],end:End::PositiveRefutation{fact:Ref::Assumption(1)}}),
        right:Box::new(Block{steps:vec![],end:End::ImproveReturn{map:vec![Expr::zero()],checks:vec![Ref::Exact,Ref::Exact,Ref::Assumption(1)],margin:ImprovementMargin::Constant(q(1))}})}};
    check(&m,&c,&r).unwrap();
    let mut bad=c.clone();if let End::Split{right,..}=&mut bad.improvements[0].block.end{if let End::ImproveReturn{checks,..}=&mut right.end{checks[2]=Ref::Assumption(0);}}
    assert!(check(&m,&bad,&r).is_err());
    let mut bad=c.clone();if let End::Split{integer,..}=&mut bad.improvements[0].block.end{*integer=None;}
    assert!(check(&m,&bad,&r).is_err());
    let mut bad=c.clone();if let End::Split{left,..}=&mut bad.improvements[0].block.end{left.end=End::Absurd{fact:Ref::Assumption(1)};}
    assert!(check(&m,&bad,&r).is_err());
}

#[test]
fn no_attainment_boundedness_or_nonempty_strict_domain_is_assumed(){
    let(mut m,mut c,mut r)=fixture(false);m.vars[0].lower=None;
    r.improvements[0].positive=e(1,&[]);c.improvements[0].claim=r.improvements[0].clone();
    c.improvements[0].block.end=End::ImproveReturn{map:vec![e(-1,&[(0,1)])],checks:vec![Ref::Exact],margin:ImprovementMargin::Constant(q(1))};
    check(&m,&c,&r).unwrap(); // Unbounded model; no optimizer is silently assumed.
    for constant in [-1,0]{r.improvements[0].positive=e(constant,&[]);c.improvements[0].claim=r.improvements[0].clone();c.improvements[0].block.end=End::PositiveRefutation{fact:Ref::Exact};check(&m,&c,&r).unwrap();}
    r.improvements[0].positive=e(1,&[]);c.improvements[0].claim=r.improvements[0].clone();assert!(check(&m,&c,&r).is_err());
    // Empty actual source also validates the universal statement, via a real contradiction.
    m.vars[0].lower=Some(q(1));m.vars[0].upper=Some(q(0));
    c.improvements[0].block=Block{steps:vec![Step::Lin{id:0,kind:Kind::Le,constant:q(0),terms:vec![(Ref::VarLower(0),q(1)),(Ref::VarUpper(0),q(1))]}],end:End::Absurd{fact:Ref::Local(0)}};
    check(&m,&c,&r).unwrap();
}

#[test]
fn root_contract_and_return_modes_cannot_be_weakened(){
    let(m,c,r)=fixture(false);
    for mutation in 0..6{let mut bad=c.clone();match mutation{
        0=>bad.improvements[0].claim.positive=e(-1,&[(0,1)]),
        1=>bad.improvements[0].claim.target=true,
        2=>bad.improvements[0].claim.integers=true,
        3=>bad.improvements.clear(),
        4=>bad.improvements.push(bad.improvements[0].clone()),
        _=>bad.improvements[0].block.end=End::Return{map:vec![Expr::zero()],checks:vec![Ref::Exact,Ref::Exact]},
    };assert!(check(&m,&bad,&r).is_err(),"mutation {mutation}");}
    let claim=Claim{reverse:false,input_integers:false,output_integers:false,objective:Objective::None,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None,input_objective_level:None,input_halfspace:None};
    for end in [c.improvements[0].block.end.clone(),End::PositiveRefutation{fact:Ref::VarLower(0)}]{
        let bad=Certificate{claims:vec![claim.clone()],blocks:vec![Block{steps:vec![],end}],..Certificate::default()};
        assert!(verify::verify(&m,&m,&bad,&[claim.clone()],&Limits::default()).is_err());
        assert!(verify::verify_lp_refutation(&m,&bad.blocks[0],&Limits::default()).is_err());
    }
    let mut bad=r.clone();bad.improvements[0].positive=Expr::var(1);let mut cert=c.clone();cert.improvements[0].claim=bad.improvements[0].clone();assert!(check(&m,&cert,&bad).is_err());
}

#[test]
fn nonpositive_margins_missing_domains_rows_and_changed_objectives_reject(){
    let(m,c,r)=fixture(true);
    for margin in [ImprovementMargin::Constant(q(0)),ImprovementMargin::Constant(q(-1)),ImprovementMargin::Predicate(q(0)),ImprovementMargin::Predicate(q(-1))]{
        let mut bad=c.clone();if let End::ImproveReturn{margin:x,..}=&mut bad.improvements[0].block.end{*x=margin;}assert!(check(&m,&bad,&r).is_err());
    }
    for count in [0,1,2,4]{let mut bad=c.clone();if let End::ImproveReturn{checks,..}=&mut bad.improvements[0].block.end{*checks=vec![Ref::Exact;count];}assert!(check(&m,&bad,&r).is_err());}
    let mut bad=c.clone();if let End::ImproveReturn{map,..}=&mut bad.improvements[0].block.end{map.clear();}assert!(check(&m,&bad,&r).is_err());
    let mut wrong=m.clone();wrong.rows.push(Row{name:"x_at_least_one".into(),expr:Expr::var(0),lower:Some(q(1)),upper:None});assert!(check(&wrong,&c,&r).is_err());
    let mut wrong=m.clone();wrong.objective=e(7,&[(0,-1)]);assert!(check(&wrong,&c,&r).is_err());
    let mut bad=c.clone();if let End::ImproveReturn{map,..}=&mut bad.improvements[0].block.end{*map=vec![Expr{constant:Q::new(1.into(),2.into()),terms:vec![]}];}assert!(check(&m,&bad,&r).is_err());
}

#[test]
fn old_scope_predicate_survives_joint_interval_without_new_coordinate_capture(){
    let(m,mut c,r)=fixture(false);let body=c.improvements[0].block.clone();
    c.improvements[0].block=Block{steps:vec![],end:End::IntervalLift{intervals:vec![IntervalWitness{lower:vec![Expr::zero()],upper:vec![Expr::var(0)],checks:vec![Ref::VarLower(0)]}],body:Box::new(body)}};
    check(&m,&c,&r).unwrap();
    let mut bad=c.clone();bad.improvements[0].claim.positive=Expr::var(1);let mut req=r.clone();req.improvements[0]=bad.improvements[0].claim.clone();assert!(check(&m,&bad,&req).is_err());
}

#[test]
fn request_budget_is_shared_and_exact_boundary_is_preserved(){
    let(m,mut c,mut r)=fixture(false);c.improvements.push(c.improvements[0].clone());r.improvements.push(r.improvements[0].clone());
    let stats=check(&m,&c,&r).unwrap();assert_eq!(stats.improvements,2);
    for (work,valid) in [(stats.work,true),(stats.work-1,false),(0,false)]{assert_eq!(verify::verify_request(&m,&m,&c,&r,&Limits{work,..Limits::default()}).is_ok(),valid);}
    assert!(verify::verify_request(&m,&m,&c,&r,&Limits{depth:0,..Limits::default()}).is_err());
}

#[test]
fn draft_wire_roundtrip_downgrade_truncation_unknown_fields(){
    let(m,c,r)=fixture(false);let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&10u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 10\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
    check(&m,&codec::decode_certificate(&bytes).unwrap(),&r).unwrap();
    for version in 1u16..10{let mut bad=bytes.clone();bad[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&bad).is_err());assert!(rpa::assemble(&text.replacen("RPA 10",&format!("RPA {version}"),1)).is_err());}
    for n in 0..bytes.len(){let mut bad=bytes[..n].to_vec();if n>=16{bad[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&bad).is_err(),"truncation {n}");}
    let mut value=serde_json::to_value(&c).unwrap();value["improvements"][0]["claim"]["unchecked_positive"]=true.into();assert!(rpa::assemble(&format!("RPA 10\n{value}")).is_err());
    let mut value=serde_json::to_value(&r).unwrap();value["improvements"][0]["unused"]=true.into();assert!(rpa::parse_request(&value.to_string()).is_err());
}
