use kernel_core::{codec,model::{Expr,Model,Q,Row,Var},proof::*,rpa,verify::{verify,verify_request,verify_injectivity,verify_lp_refutation,Limits}};
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn e(c:i64,t:&[(u32,i64)])->Expr{Expr{constant:q(c),terms:t.iter().map(|(i,n)|(*i,q(*n))).collect()}}
fn v(name:&str)->Var{Var{name:name.into(),integer:true,lower:Some(q(0)),upper:Some(q(1))}}
fn lin(id:u32,kind:Kind,terms:Vec<(Ref,i64)>)->Step{Step::Lin{id,kind,constant:q(0),terms:terms.into_iter().map(|(r,n)|(r,q(n))).collect()}}
fn claim(reverse:bool)->Claim{Claim{input_halfspace:None,input_objective_level:None,reverse,input_integers:true,output_integers:true,objective:Objective::Equal,projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None}}
fn example()->(Model,Model,Certificate,Request){
    let s=Model{name:"optional_options".into(),vars:vec![v("z0"),v("z1")],rows:vec![Row{name:"packing".into(),expr:e(0,&[(0,1),(1,1)]),lower:None,upper:Some(q(1))}],objective:e(0,&[(0,3),(1,5)])};
    let t=Model{name:"menu".into(),vars:vec![v("activation"),v("index")],rows:vec![Row{name:"inactive_index_zero".into(),expr:e(0,&[(0,-1),(1,1)]),lower:None,upper:Some(q(0))}],objective:e(0,&[(0,3),(1,2)])};
    let forward=Block{steps:vec![lin(0,Kind::Le,vec![(Ref::VarLower(0),1),(Ref::VarLower(1),1)])],end:End::Return{map:vec![e(0,&[(0,1),(1,1)]),Expr::var(1)],checks:vec![Ref::Local(0),Ref::RowUpper(0),Ref::Exact,Ref::VarLower(1),Ref::VarUpper(1),Ref::Exact,Ref::VarLower(0),Ref::Exact]}};
    let body=Block{steps:vec![lin(0,Kind::Le,vec![(Ref::RowEq(1),1),(Ref::VarUpper(0),1)]),lin(1,Kind::Eq,vec![(Ref::RowEq(1),3),(Ref::RowEq(2),2)])],end:End::Return{map:vec![Expr::var(2),Expr::var(3)],checks:vec![Ref::VarLower(2),Ref::VarUpper(2),Ref::VarInt(2),Ref::VarLower(3),Ref::VarUpper(3),Ref::VarInt(3),Ref::Local(0),Ref::Local(1),Ref::RowEq(1),Ref::RowEq(2)]}};
    let menu=MenuWitness{maximum_index:1,activation:Expr::var(0),index:Expr::var(1),checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::VarInt(0),Ref::VarLower(1),Ref::RowUpper(0),Ref::VarInt(1)]};
    let pair=BijectionClaim{forward_claim:0,reverse_claim:1};
    let witness=BijectionWitness{claim:pair.clone(),injectivity:EqualityProof{steps:vec![lin(0,Kind::Eq,vec![(Ref::RowEq(2),1),(Ref::RowEq(3),-1)])],checks:vec![Ref::Local(0),Ref::RowEq(3)]}};
    let request=Request{improvements:vec![], claims:vec![claim(false),claim(true)],points:vec![],bijections:vec![pair]};
    let cert=Certificate{improvements:vec![], claims:request.claims.clone(),blocks:vec![forward,Block{steps:vec![],end:End::MenuLift{menus:vec![menu],body:Box::new(body)}}],points:vec![],bijections:vec![witness]};(s,t,cert,request)
}
fn check(s:&Model,t:&Model,c:&Certificate,r:&Request)->Result<kernel_core::verify::Statistics,String>{verify_request(s,t,c,r,&Limits::default())}
fn menu_mut(c:&mut Certificate)->(&mut Vec<MenuWitness>,&mut Block){let End::MenuLift{menus,body}=&mut c.blocks[1].end else{panic!()};(menus,body)}
#[test]fn optional_menu_complete_bijection_and_exact_old_version_roundtrips(){
    let(s,t,c,r)=example();let stats=check(&s,&t,&c,&r).unwrap();assert_eq!(stats.bijections,1);assert_eq!(stats.injectivity_coordinates,2);assert_eq!(stats.menu_generated_variables,2);assert_eq!(stats.menu_generated_rows,2);
    assert!(verify(&s,&t,&c,&c.claims,&Limits::default()).is_err());
    let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&7u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap();assert_eq!(rpa::assemble(&text).unwrap(),c);
    for version in 1..7{assert!(rpa::assemble(&text.replacen("RPA 7",&format!("RPA {version}"),1)).is_err());let mut b=bytes.clone();b[4..6].copy_from_slice(&(version as u16).to_le_bytes());assert!(codec::decode_certificate(&b).is_err());}
    for path in ["identity-ordinary.rpx","identity-nested.rpx","identity-local-v2.rpx","identity-plotkin-v3.rpx","flow-v4.rpx","interval-v5.rpx","fiber-v6.rpx"]{let p=format!("../../tests/vectors/{path}");let b=std::fs::read(&p).unwrap();{assert_eq!(codec::encode_certificate(&codec::decode_certificate(&b).unwrap()).unwrap(),b,"{path}");}}
}
#[test]fn every_menu_premise_and_parent_scope_is_required(){
    let(s,t,c,r)=example();
    for i in 0..6{let mut bad=c.clone();menu_mut(&mut bad).0[0].checks[i]=if i==2||i==5{Ref::RowUpper(0)}else{Ref::Exact};assert!(check(&s,&t,&bad,&r).is_err(),"premise {i}");}
    for i in 0..6{let mut bad=c.clone();menu_mut(&mut bad).0[0].checks.remove(i);assert!(check(&s,&t,&bad,&r).is_err());}
    let mut bad=c.clone();menu_mut(&mut bad).0[0].checks[2]=Ref::VarInt(2);assert!(check(&s,&t,&bad,&r).is_err());
    let mut bad=c.clone();menu_mut(&mut bad).0[0].activation=Expr::var(2);assert!(check(&s,&t,&bad,&r).is_err());
    let mut bad=c.clone();menu_mut(&mut bad).0[0].maximum_index=0;assert!(check(&s,&t,&bad,&r).is_err());
    let mut bad=c.clone();bad.claims.remove(0);bad.blocks.remove(0);bad.bijections.clear();bad.claims[0].input_integers=false;let request=Request{improvements:vec![], claims:bad.claims.clone(),points:vec![],bijections:vec![]};assert!(check(&s,&t,&bad,&request).unwrap_err().contains("integer input mode"));
    let empty=Model{name:"empty".into(),vars:vec![],rows:vec![],objective:e(0,&[])};assert!(verify_lp_refutation(&empty,&c.blocks[1],&Limits::default()).unwrap_err().contains("only Absurd/Split"));
}
#[test]fn pair_is_bound_to_caller_indices_modes_and_actual_forward_map(){
    let(s,t,c,r)=example();
    let mut request=r.clone();request.bijections.clear();assert!(check(&s,&t,&c,&request).is_err());
    for pair in [BijectionClaim{forward_claim:0,reverse_claim:0},BijectionClaim{forward_claim:5,reverse_claim:1},BijectionClaim{forward_claim:1,reverse_claim:0}]{let mut bad=c.clone();let mut request=r.clone();bad.bijections[0].claim=pair.clone();request.bijections[0]=pair;assert!(check(&s,&t,&bad,&request).is_err());}
    let mut bad=c.clone();let mut request=r.clone();bad.bijections.push(bad.bijections[0].clone());request.bijections.push(request.bijections[0].clone());assert!(check(&s,&t,&bad,&request).is_err());
    let mut bad=c.clone();let mut request=r.clone();bad.claims[1].reverse=false;request.claims=bad.claims.clone();assert!(check(&s,&t,&bad,&request).is_err());
    let mut bad=c.clone();let mut request=r.clone();bad.claims[1].output_integers=false;request.claims=bad.claims.clone();assert!(check(&s,&t,&bad,&request).is_err());
    let mut bad=c.clone();if let End::Return{map,..}=&mut bad.blocks[0].end{map.swap(0,1);}assert!(check(&s,&t,&bad,&r).is_err());
    let mut bad=c.clone();let mut request=r.clone();bad.claims[1].inverse=Some(0);request.claims=bad.claims.clone();assert!(check(&s,&t,&bad,&request).unwrap_err().contains("inverse requires affine"));
}
#[test]fn compositions_checked_after_nested_extensions_and_on_every_branch(){
    let(s,t,c,r)=example();let mut branched=c.clone();let reverse=c.blocks[1].clone();branched.blocks[1]=Block{steps:vec![],end:End::Split{expression:e(0,&[]),integer:None,left:Box::new(reverse.clone()),right:Box::new(reverse)}};assert_eq!(check(&s,&t,&branched,&r).unwrap().menu_lifts,2);
    let End::Split{right,..}=&mut branched.blocks[1].end else{panic!()};let End::MenuLift{body,..}=&mut right.end else{panic!()};let End::Return{checks,..}=&mut body.end else{panic!()};checks.pop();assert!(check(&s,&t,&branched,&r).is_err());
    let mut nested=c.clone();let (menus,body)=menu_mut(&mut nested);*body=Block{steps:vec![],end:End::MenuLift{menus:menus.clone(),body:Box::new(body.clone())}};assert_eq!(check(&s,&t,&nested,&r).unwrap().menu_lifts,2);
    let mut bad=c.clone();let (_,body)=menu_mut(&mut bad);let End::Return{checks,..}=&mut body.end else{panic!()};let n=checks.len();checks[n-2]=Ref::Exact;assert!(check(&s,&t,&bad,&r).is_err());
}
#[test]fn no_free_coordinate_or_fresh_proof_register_can_escape_injectivity(){
    let(mut s,t,mut c,r)=example();s.vars.push(Var{name:"forgotten".into(),integer:false,lower:None,upper:None});let(_,body)=menu_mut(&mut c);let End::Return{map,..}=&mut body.end else{panic!()};map.push(e(0,&[]));c.bijections[0].injectivity.checks.push(Ref::Exact);assert!(check(&s,&t,&c,&r).is_err());
    let(s,t,c,r)=example();let mut bad=c.clone();bad.bijections[0].injectivity.steps.clear();assert!(check(&s,&t,&bad,&r).is_err());
    for change in 0..3{let mut bad=c.clone();match change{0=>{bad.bijections[0].injectivity.checks.pop();},1=>bad.bijections[0].injectivity.checks.push(Ref::Exact),_=>bad.bijections[0].injectivity.checks[0]=Ref::Assumption(0)}assert!(check(&s,&t,&bad,&r).is_err());}
    let End::Return{map,..}=&c.blocks[0].end else{panic!()};let p=&c.bijections[0].injectivity;verify_injectivity(&s,&t,map,false,p,&Limits::default()).unwrap(); // K1 map is injective even on its relaxation.
    let mut bad=p.clone();bad.steps.insert(0,lin(99,Kind::Int,vec![(Ref::VarInt(0),1)]));assert!(verify_injectivity(&s,&t,map,false,&bad,&Limits::default()).is_err());
}
#[test]fn ordinary_body_still_checks_every_actual_output_obligation(){
    let(s,t,c,r)=example();
    for what in 0..5{let mut bad=c.clone();let (_,body)=menu_mut(&mut bad);let End::Return{map,checks}=&mut body.end else{panic!()};match what{0=>{map.pop();},1=>map[1]=map[0].clone(),2=>checks[2]=Ref::Exact,3=>checks[6]=Ref::Exact,_=>checks[7]=Ref::Exact}if what==2{assert!(check(&s,&t,&bad,&r).is_ok());}else{assert!(check(&s,&t,&bad,&r).is_err(),"{what}");}}
    let mut bads=s.clone();bads.rows[0].upper=Some(q(0));assert!(check(&bads,&t,&c,&r).is_err());
    let mut bads=s.clone();bads.objective.constant=q(1);assert!(check(&bads,&t,&c,&r).is_err());
}
#[test]fn v7_resources_and_unreachable_payloads_are_checked(){
    let(s,t,c,r)=example();let stats=check(&s,&t,&c,&r).unwrap();
    for limits in [Limits{work:stats.work-1,..Limits::default()},Limits{depth:1,..Limits::default()},Limits{live_facts:0,..Limits::default()}]{assert!(verify_request(&s,&t,&c,&r,&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));}
    let mut big=c.clone();menu_mut(&mut big).0[0].maximum_index=u32::MAX;assert!(check(&s,&t,&big,&r).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let bytes=codec::encode_certificate(&c).unwrap();for n in 0..bytes.len(){let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err());}
    let mut extra=bytes.clone();extra.push(0);let len=extra.len() as u64;extra[8..16].copy_from_slice(&len.to_le_bytes());assert!(codec::decode_certificate(&extra).is_err());
    let mut bad=c.clone();let mut d=Derivation{steps:vec![],end:DerivationEnd::Witness(Ref::Exact)};for i in 0..64{d=Derivation{steps:vec![Step::Cases(Box::new(CasesStep{id:i,kind:Kind::Eq,expression:e(0,&[]),split:e(0,&[]),integer:None,left:Box::new(d),right:Box::new(Derivation{steps:vec![],end:DerivationEnd::Witness(Ref::Exact)})}))],end:DerivationEnd::Witness(Ref::Exact)};}bad.bijections[0].injectivity.steps=d.steps;assert!(codec::certificate_version(&bad).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut unknown=serde_json::to_value(&c).unwrap();unknown["bijections"][0]["injectivity"]["unused"]=true.into();assert!(rpa::assemble(&format!("RPA 7\n{unknown}")).is_err());
}
#[test]fn menu_then_interval_and_flow_keep_original_composition_prefix(){
    let(s,t,c,r)=example();
    let mut interval=c.clone();let (_,body)=menu_mut(&mut interval);*body=Block{steps:vec![],end:End::IntervalLift{intervals:vec![IntervalWitness{lower:vec![Expr::var(0)],upper:vec![Expr::var(0)],checks:vec![Ref::Exact]}],body:Box::new(body.clone())}};assert_eq!(check(&s,&t,&interval,&r).unwrap().interval_generated_variables,1);
    let mut flow=c.clone();let (_,body)=menu_mut(&mut flow);*body=Block{steps:vec![],end:End::FlowLift{witness:FlowWitness{nodes:1,arcs:vec![(0,0)],groups:vec![FlowGroup{source:0,commodities:vec![(0,q(0))],flows:vec![Expr::var(0)],nonnegative:vec![Ref::VarLower(0)],balances:vec![Ref::Exact]}]},body:Box::new(body.clone())}};assert_eq!(check(&s,&t,&flow,&r).unwrap().flow_generated_variables,1);
}
#[test]fn affine_constants_cancel_only_in_paired_domain_not_in_composition(){
    let m=Model{name:"free_real".into(),vars:vec![Var{name:"x".into(),integer:false,lower:None,upper:None}],rows:vec![],objective:e(0,&[])};
    let mut f=claim(false);f.input_integers=false;f.output_integers=false;let mut g=f.clone();g.reverse=true;
    let pair=BijectionClaim{forward_claim:0,reverse_claim:1};let request=Request{improvements:vec![], claims:vec![f,g],points:vec![],bijections:vec![pair.clone()]};
    let mut c=Certificate{improvements:vec![], claims:request.claims.clone(),points:vec![],bijections:vec![BijectionWitness{claim:pair,injectivity:EqualityProof{steps:vec![],checks:vec![Ref::RowEq(0)]}}],blocks:vec![Block{steps:vec![],end:End::Return{map:vec![e(2,&[(0,1)])],checks:vec![Ref::Exact]}},Block{steps:vec![],end:End::Return{map:vec![e(-2,&[(0,1)])],checks:vec![Ref::Exact,Ref::Exact]}}]};
    check(&m,&m,&c,&request).unwrap();let End::Return{map,..}=&mut c.blocks[0].end else{panic!()};map[0].constant=q(3);assert!(check(&m,&m,&c,&request).unwrap_err().contains("non-tautological"));
}
#[test]fn several_pair_contracts_append_all_compositions_and_prove_fresh_goals(){
    let(s,t,mut c,mut r)=example();c.claims.push(c.claims[0].clone());r.claims=c.claims.clone();c.blocks.push(c.blocks[0].clone());let mut pair=c.bijections[0].clone();pair.claim.forward_claim=2;c.bijections.push(pair.clone());r.bijections.push(pair.claim);let(_,body)=menu_mut(&mut c);let End::Return{checks,..}=&mut body.end else{panic!()};checks.extend([Ref::RowEq(1),Ref::RowEq(2)]);assert_eq!(check(&s,&t,&c,&r).unwrap().bijections,2);
    c.bijections[1].injectivity.steps.clear();assert!(check(&s,&t,&c,&r).is_err());
}
#[test]fn independent_v7_singleton_bytes_and_systematic_mutations(){
    let model=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();let bytes=include_bytes!("../../../tests/vectors/menu-v7.rpx");let c=codec::decode_certificate(bytes).unwrap();assert_eq!(codec::encode_certificate(&c).unwrap(),bytes);let r=Request{improvements:vec![], claims:c.claims.clone(),points:vec![],bijections:vec![BijectionClaim{forward_claim:0,reverse_claim:1}]};let stats=check(&model,&model,&c,&r).unwrap();assert_eq!(stats.menu_generated_variables,1);assert_eq!(stats.menu_generated_rows,2);
    assert!(codec::decode_certificate(include_bytes!("../../../tests/vectors/invalid-v7-terminal-v6.rpx")).is_err());assert!(codec::decode_certificate(include_bytes!("../../../tests/vectors/invalid-v7-count.rpx")).unwrap_err().starts_with("RESOURCE_LIMIT"));
    for i in 16..bytes.len(){for b in [0,1,127,255]{let mut changed=bytes.to_vec();changed[i]=b;if let Ok(decoded)=codec::decode_certificate(&changed){let _=check(&model,&model,&decoded,&r);}}}
    let mut bad=c.clone();bad.bijections.clear();bad.points.push(PointWitness{claim:PointClaim::FiberStrictness{inclusion_claim:0},values:vec![q(0)],refutation:Some(c.blocks[1].clone())});assert_eq!(codec::certificate_version(&bad).unwrap(),7);
}
