//! Signed-coordinate lifting through one joint bounded interval choice.
use kernel_core::{codec,model::{Expr,Model,Q,Var},proof::*,rpa,verify::{verify,Limits}};
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn e(c:i64,ts:&[(u32,i64)])->Expr{Expr{constant:q(c),terms:ts.iter().map(|(i,n)|(*i,q(*n))).collect()}}
fn fixture()->(Model,Model,Certificate){
    let s=Model{name:"signed".into(),vars:vec![Var{name:"x".into(),integer:false,lower:Some(q(-1)),upper:Some(q(1))}],rows:vec![],objective:e(5,&[(0,2)])};
    let t=Model{name:"parts".into(),vars:["positive","negative"].iter().map(|name|Var{name:(*name).into(),integer:false,lower:Some(q(0)),upper:Some(q(1))}).collect(),rows:vec![],objective:e(5,&[(0,2),(1,-2)])};
    let claim=Claim{input_halfspace:None,input_objective_level:None,reverse:false,input_integers:false,output_integers:false,objective:Objective::Equal,projection:vec![],affine_projection:vec![(Expr::var(0),e(0,&[(0,1),(1,-1)]))],inverse:None,input_objective_lower:None};
    let interval=IntervalWitness{lower:vec![e(0,&[]),Expr::var(0)],upper:vec![e(1,&[]),e(1,&[(0,1)])],checks:vec![Ref::Exact,Ref::VarLower(0),Ref::VarUpper(0),Ref::Exact]};
    let body=Block{steps:vec![],end:End::Return{map:vec![Expr::var(1),e(0,&[(0,-1),(1,1)])],checks:vec![Ref::RowLower(0),Ref::RowUpper(2),Ref::RowLower(1),Ref::RowUpper(3),Ref::Exact,Ref::Exact]}};
    let c=Certificate { improvements:vec![], bijections:vec![],claims:vec![claim],blocks:vec![Block{steps:vec![],end:End::IntervalLift{intervals:vec![interval],body:Box::new(body)}}],points:vec![]};(s,t,c)
}
fn check(s:&Model,t:&Model,c:&Certificate)->Result<kernel_core::verify::Statistics,String>{verify(s,t,c,&c.claims,&Limits::default())}
#[test]fn signed_affine_observation_and_pointwise_objective_are_preserved(){
    let (s,t,c)=fixture();let stats=check(&s,&t,&c).unwrap();assert_eq!((stats.interval_lifts,stats.interval_generated_variables,stats.interval_generated_rows),(1,1,4));
    let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&5u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 5\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
}
#[test]fn every_interval_pair_and_parent_scope_reference_is_checked(){
    let (s,t,c)=fixture();
    for change in 0..8{let mut c=c.clone();if let End::IntervalLift{intervals,..}=&mut c.blocks[0].end{let i=&mut intervals[0];match change{
        0=>{i.checks.remove(1);},
        1=>{i.checks.push(Ref::Exact);},
        2=>i.checks.swap(1,2),
        3=>i.checks[1]=Ref::RowLower(0),
        4=>i.upper[1]=e(-2,&[(0,1)]),
        5=>i.lower[1]=Expr::var(1),
        6=>i.checks[2]=Ref::Exact,
        _=>i.lower[0].constant=Q::new_raw(2.into(),4.into()),
    }}assert!(check(&s,&t,&c).is_err(),"{change}");}
}
#[test]fn original_affine_dimensions_and_claim_order_are_binding(){
    let (s,t,c)=fixture();
    for change in 0..4{let mut c=c.clone();match change{
        0=>c.claims[0].affine_projection[0].0=Expr::var(1),
        1=>c.claims[0].affine_projection[0].1=Expr::var(2),
        2=>c.claims[0].affine_projection[0].1=e(0,&[(0,1),(1,1)]),
        _=>c.claims[0].affine_projection[0].0=e(1,&[(0,1)]),
    }assert!(check(&s,&t,&c).is_err(),"{change}");}
    let mut weakened=c.clone();weakened.claims[0].affine_projection.clear();assert!(verify(&s,&t,&weakened,&c.claims,&Limits::default()).unwrap_err().contains("contract mismatch"));
    // Removing an observation still leaves a surplus witness; adding one needs its own check.
    assert!(check(&s,&t,&weakened).unwrap_err().contains("surplus"));
    let mut extra=c.clone();let observation=extra.claims[0].affine_projection[0].clone();extra.claims[0].affine_projection.push(observation);assert!(check(&s,&t,&extra).unwrap_err().contains("missing obligation"));
}
#[test]fn free_real_choices_do_not_prove_integer_or_coupled_outputs(){
    let (s,t,c)=fixture();let mut target=t.clone();target.vars[0].integer=true;let mut cert=c.clone();cert.claims[0].output_integers=true;assert!(check(&s,&target,&cert).is_err());
    let mut target=t.clone();target.rows.push(kernel_core::model::Row{name:"coupling".into(),expr:e(0,&[(0,1),(1,1)]),lower:Some(q(1)),upper:Some(q(1))});assert!(check(&s,&target,&c).is_err());
    let mut target=t.clone();target.objective.terms[1].1=q(-1);assert!(check(&s,&target,&c).is_err());
}
#[test]fn one_sided_empty_and_multiple_choices_have_one_common_extension(){
    let (s,_,mut c)=fixture();c.claims[0].objective=Objective::None;c.claims[0].affine_projection.clear();
    let target=Model{name:"choices".into(),vars:(0..4).map(|i|Var{name:format!("z{i}"),integer:false,lower:None,upper:None}).collect(),rows:vec![],objective:e(0,&[])};
    let intervals=vec![IntervalWitness{lower:vec![],upper:vec![],checks:vec![]},IntervalWitness{lower:vec![e(2,&[])],upper:vec![],checks:vec![]},IntervalWitness{lower:vec![],upper:vec![e(-2,&[])],checks:vec![]},IntervalWitness{lower:vec![e(-1,&[])],upper:vec![e(1,&[])],checks:vec![Ref::Exact]}];
    c.blocks[0].end=End::IntervalLift{intervals,body:Box::new(Block{steps:vec![],end:End::Return{map:(1..5).map(Expr::var).collect(),checks:vec![]}})};
    let stats=check(&s,&target,&c).unwrap();assert_eq!((stats.interval_generated_variables,stats.interval_generated_rows),(4,4));
}
#[test]fn interval_scope_inverse_and_nested_depth_are_explicit(){
    let (s,t,mut c)=fixture();let left=c.blocks[0].clone();let right=if let End::IntervalLift{body,..}=&left.end{(**body).clone()}else{unreachable!()};c.blocks[0]=Block{steps:vec![],end:End::Split{expression:e(0,&[]),integer:None,left:Box::new(left),right:Box::new(right)}};assert!(check(&s,&t,&c).is_err());
    let (_,_,mut c)=fixture();let mut rev=c.claims[0].clone();rev.reverse=true;rev.affine_projection.clear();c.claims[0].inverse=Some(1);c.claims.push(rev);c.blocks.push(Block{steps:vec![],end:End::Return{map:vec![e(0,&[(0,1),(1,-1)])],checks:vec![]}});assert!(check(&s,&t,&c).unwrap_err().contains("inverse requires affine"));
    let (_,_,mut c)=fixture();if let End::IntervalLift{body,..}=&mut c.blocks[0].end{let final_body=(**body).clone();*body=Box::new(Block{steps:vec![],end:End::IntervalLift{intervals:vec![IntervalWitness{lower:vec![Expr::var(1)],upper:vec![Expr::var(1)],checks:vec![Ref::Exact]}],body:Box::new(final_body)}});}
    assert_eq!(check(&s,&t,&c).unwrap().interval_lifts,2);assert!(verify(&s,&t,&c,&c.claims,&Limits{depth:2,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
#[test]fn affine_observation_alone_requires_v5_and_old_bytes_stay_unchanged(){
    let (s,_,mut c)=fixture();c.blocks[0]=Block{steps:vec![],end:End::Return{map:vec![Expr::var(0)],checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::Exact,Ref::Exact]}};c.claims[0].affine_projection=vec![(e(7,&[(0,2)]),e(7,&[(0,2)]))];check(&s,&s,&c).unwrap();assert_eq!(codec::certificate_version(&c).unwrap(),5);
    let mut flow=codec::decode_certificate(include_bytes!("../../../tests/vectors/flow-v4.rpx")).unwrap();flow.claims[0].affine_projection=vec![(Expr::var(0),Expr::var(0))];assert_eq!(codec::certificate_version(&flow).unwrap(),5);
    for bytes in [include_bytes!("../../../tests/vectors/identity-ordinary.rpx").as_slice(),include_bytes!("../../../tests/vectors/identity-local-v2.rpx").as_slice(),include_bytes!("../../../tests/vectors/identity-plotkin-v3.rpx").as_slice(),include_bytes!("../../../tests/vectors/flow-v4.rpx").as_slice()]{assert_eq!(codec::encode_certificate(&codec::decode_certificate(bytes).unwrap()).unwrap(),bytes);}
}
#[test]fn interval_wire_mutations_versions_truncations_and_work_limits(){
    let (s,t,c)=fixture();let bytes=codec::encode_certificate(&c).unwrap();let text=rpa::disassemble(&c).unwrap();
    for version in [1u16,2,3,4]{let mut b=bytes.clone();b[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&b).is_err());assert!(rpa::assemble(&text.replacen("RPA 5",&format!("RPA {version}"),1)).is_err());}
    for n in 0..bytes.len(){let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err());}
    for i in 16..bytes.len(){for v in [0,1,127,255]{let mut b=bytes.clone();b[i]=v;if let Ok(decoded)=codec::decode_certificate(&b){let _=check(&s,&t,&decoded);}}}
    let stats=check(&s,&t,&c).unwrap();assert!(verify(&s,&t,&c,&c.claims,&Limits{work:stats.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
