//! V2 local case reasoning: one jointly valid proposition, no mapped outputs.
use kernel_core::{codec, model::{Expr,Model,Q,Row,Var}, proof::*, rpa, verify::{verify,Limits}};

fn q(n:i64)->Q{Q::from_integer(n.into())}
fn e(constant:i64,terms:&[(u32,i64)])->Expr{Expr{constant:q(constant),terms:terms.iter().map(|(i,a)|(*i,q(*a))).collect()}}
fn cl()->Claim{Claim{input_halfspace:None,input_objective_level:None, affine_projection:vec![], input_objective_lower:None,reverse:false,input_integers:true,output_integers:true,objective:Objective::None,projection:vec![(0,0),(1,1)],inverse:None}}
fn lin(id:u32,terms:Vec<(Ref,Q)>)->Step{Step::Lin{id,kind:Kind::Le,constant:q(0),terms}}
fn witness(steps:Vec<Step>,fact:Ref)->Box<Derivation>{Box::new(Derivation{steps,end:DerivationEnd::Witness(fact)})}
fn models()->(Model,Model){
    let vars=vec![Var{name:"x".into(),integer:true,lower:Some(q(0)),upper:Some(q(1))},Var{name:"y".into(),integer:false,lower:Some(q(0)),upper:Some(q(1))}];
    let source=Model{name:"source".into(),vars:vars.clone(),rows:vec![Row{name:"yx".into(),expr:e(0,&[(0,-1),(1,1)]),lower:None,upper:Some(q(0))},Row{name:"lower_product".into(),expr:e(0,&[(0,2),(1,-1)]),lower:None,upper:Some(q(1))}],objective:e(0,&[])};
    let target=Model{name:"target".into(),vars,rows:vec![Row{name:"alias".into(),expr:e(0,&[(0,-1),(1,1)]),lower:Some(q(0)),upper:Some(q(0))}],objective:e(0,&[])};
    (source,target)
}
fn certificate()->Certificate{
    let left=witness(vec![lin(10,vec![(Ref::Assumption(0),q(1)),(Ref::VarLower(1),q(1))]),Step::EqPair{id:11,positive:Ref::RowUpper(0),negative:Ref::Local(10)}],Ref::Local(11));
    let right=witness(vec![lin(20,vec![(Ref::Assumption(0),q(1)),(Ref::RowUpper(1),q(1))]),Step::EqPair{id:21,positive:Ref::RowUpper(0),negative:Ref::Local(20)}],Ref::Local(21));
    let step=Step::Cases(Box::new(CasesStep{id:100,kind:Kind::Eq,expression:e(0,&[(0,-1),(1,1)]),split:e(0,&[(0,1)]),integer:Some(Ref::VarInt(0)),left,right}));
    Certificate { improvements:vec![], bijections:vec![], points:vec![],claims:vec![cl()],blocks:vec![Block{steps:vec![step],end:End::Return{map:vec![e(0,&[(0,1)]),e(0,&[(1,1)])],checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::VarInt(0),Ref::VarLower(1),Ref::VarUpper(1),Ref::Local(100),Ref::Exact,Ref::Exact]}}]}
}
fn verify_case(c:&Certificate)->Result<(),String>{let(s,t)=models();verify(&s,&t,c,&[cl()],&Limits::default()).map(|_|())}

#[test]
fn binary_product_alias_is_proved_without_branching_the_output_map(){
    let c=certificate();verify_case(&c).unwrap();
    let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&[2,0]);assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 2\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
    // Independent rational grid: source forces y=x for binary x. In the LP,
    // x=1/2,y=0 satisfies the two source rows but violates the alias.
    for x in [q(0),q(1)]{for n in 0..=4{let y=Q::new(n.into(),4.into());let feasible=y<=x && &x*q(2)-&y<=q(1);if feasible{assert_eq!(x,y);}}}
    let x=Q::new(1.into(),2.into());let y=q(0);assert!(y<=x && &x*q(2)-&y<=q(1) && x!=y);
}

#[test]
fn both_branches_must_prove_the_same_parent_proposition(){
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{expression,..}=case.as_mut();*expression=e(1,&[]);}
    assert!(verify_case(&c).is_err());
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{right,..}=case.as_mut();right.end=DerivationEnd::Witness(Ref::RowUpper(0));}
    assert!(verify_case(&c).is_err()); // LE does not prove the required EQ.
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{integer,..}=case.as_mut();*integer=None;}
    assert!(verify_case(&c).is_err()); // Sign split's right guard is weaker.
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{right,..}=case.as_mut();right.end=DerivationEnd::Absurd(Ref::RowUpper(0));}
    assert!(verify_case(&c).is_err()); // A variable inequality is not contradiction.
}

#[test]
fn child_facts_cannot_escape_or_become_sibling_premises(){
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{right,..}=case.as_mut();right.steps.clear();right.end=DerivationEnd::Witness(Ref::Local(11));}
    assert!(verify_case(&c).is_err());
    let mut c=certificate();
    c.blocks[0].steps.push(Step::Lin{id:200,kind:Kind::Eq,constant:q(0),terms:vec![(Ref::Local(11),q(1))]});
    assert!(verify_case(&c).is_err());
    let mut c=certificate();
    if let Step::Cases(case)=&mut c.blocks[0].steps[0]{let CasesStep{left,..}=case.as_mut();left.steps.push(Step::Drop{ids:vec![11]});}
    assert!(verify_case(&c).is_err());
}

fn empty()->Model{Model{name:"empty".into(),vars:vec![],rows:vec![],objective:e(0,&[])}}
fn empty_claim()->Claim{let mut c=cl();c.projection.clear();c}
fn zero_cases(id:u32,left:Box<Derivation>,right:Box<Derivation>)->Step{Step::Cases(Box::new(CasesStep{id,kind:Kind::Eq,expression:e(0,&[]),split:e(0,&[]),integer:None,left,right}))}
fn empty_cert(steps:Vec<Step>)->Certificate{Certificate { improvements:vec![], bijections:vec![], points:vec![],claims:vec![empty_claim()],blocks:vec![Block{steps,end:End::Return{map:vec![],checks:vec![]}}]}}
fn verify_empty(c:&Certificate)->Result<(),String>{verify(&empty(),&empty(),c,&[empty_claim()],&Limits::default()).map(|_|())}

#[test]
fn local_drops_are_transactional_and_parent_export_is_fresh(){
    let parent=Step::Lin{id:1,kind:Kind::Eq,constant:q(0),terms:vec![]};
    let cases=zero_cases(2,witness(vec![Step::Drop{ids:vec![1]}],Ref::Exact),witness(vec![],Ref::Local(1)));
    let after=Step::Lin{id:3,kind:Kind::Eq,constant:q(0),terms:vec![(Ref::Local(1),q(1)),(Ref::Local(2),q(1))]};
    verify_empty(&empty_cert(vec![parent.clone(),cases,after])).unwrap();
    let overwrite=zero_cases(1,witness(vec![],Ref::Exact),witness(vec![],Ref::Exact));
    assert!(verify_empty(&empty_cert(vec![parent,overwrite])).is_err());
}

#[test]
fn eq_pair_requires_opposite_le_propositions(){
    for (kind,negative_constant) in [(Kind::Int,0),(Kind::Eq,0),(Kind::Le,-1)]{
        let c=empty_cert(vec![Step::Lin{id:0,kind,constant:q(0),terms:vec![]},Step::Lin{id:1,kind:Kind::Le,constant:q(negative_constant),terms:vec![]},Step::EqPair{id:2,positive:Ref::Local(0),negative:Ref::Local(1)}]);
        assert!(verify_empty(&c).is_err());
    }
}

#[test]
fn local_contradiction_closes_only_its_covered_branch(){
    let left=witness(vec![],Ref::Exact);
    let right=Box::new(Derivation{steps:vec![],end:DerivationEnd::Absurd(Ref::Assumption(0))});
    let mut step=zero_cases(1,left,right);
    if let Step::Cases(case)=&mut step{let CasesStep{split,integer,..}=case.as_mut();*split=e(0,&[]);*integer=Some(Ref::Local(0));}
    // Constant INT(0) split: left 0<=0, right 1<=0. Right is empty.
    let c=empty_cert(vec![Step::Lin{id:0,kind:Kind::Int,constant:q(0),terms:vec![]},step]);
    verify_empty(&c).unwrap();
    let mut bad=c.clone();if let Step::Cases(case)=&mut bad.blocks[0].steps[1]{let CasesStep{left,..}=case.as_mut();left.end=DerivationEnd::Absurd(Ref::Assumption(0));}
    assert!(verify_empty(&bad).is_err());
}

#[test]
fn version_one_rejects_new_logic_and_v1_fixture_stays_identical(){
    let mut bytes=codec::encode_certificate(&certificate()).unwrap();bytes[4]=1;
    assert!(codec::decode_certificate(&bytes).unwrap_err().contains("V2 step in V1"));
    let text=rpa::disassemble(&certificate()).unwrap().replacen("RPA 2\n","RPA 1\n",1);
    assert!(rpa::assemble(&text).unwrap_err().contains("version"));
    let original=include_bytes!("../../../tests/vectors/identity-ordinary.rpx");
    assert_eq!(codec::encode_certificate(&codec::decode_certificate(original).unwrap()).unwrap(),original);
}

#[test]
fn local_recursion_obeys_shared_depth_and_work_limits(){
    let inner=zero_cases(2,witness(vec![],Ref::Exact),witness(vec![],Ref::Exact));
    let outer=zero_cases(3,witness(vec![inner],Ref::Local(2)),witness(vec![],Ref::Exact));
    let c=empty_cert(vec![outer]);
    let limits=Limits{depth:2,..Limits::default()};
    assert!(verify(&empty(),&empty(),&c,&[empty_claim()],&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let limits=Limits{work:1,..Limits::default()};
    assert!(verify(&empty(),&empty(),&c,&[empty_claim()],&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut nested=zero_cases(1,witness(vec![],Ref::Exact),witness(vec![],Ref::Exact));
    for i in 2..=65{nested=zero_cases(i,witness(vec![nested],Ref::Local(i-1)),witness(vec![],Ref::Exact));}
    assert!(codec::encode_certificate(&empty_cert(vec![nested])).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn v2_decoder_truncation_and_nested_mutations_are_total(){
    let bytes=codec::encode_certificate(&certificate()).unwrap();
    for n in 16..bytes.len(){let mut b=bytes[..n].to_vec();b[8..16].copy_from_slice(&(n as u64).to_le_bytes());assert!(codec::decode_certificate(&b).is_err());}
    for i in 16..bytes.len(){for v in [0,1,127,128,254,255]{let mut b=bytes.clone();b[i]=v;if let Ok(c)=codec::decode_certificate(&b){assert_eq!(codec::encode_certificate(&c).unwrap(),b);}}}
}
