//! Independent adversarial review of the V10 strict-improvement contract.
use kernel_core::{model::{Expr,Model,Q,Var},proof::*,verify::{verify_request,Limits}};
fn q(n:i64)->Q { Q::from_integer(n.into()) }
fn e(c:i64,terms:&[(u32,i64)])->Expr {
    Expr {constant:q(c),terms:terms.iter().filter(|(_,v)|*v!=0).map(|&(i,v)|(i,q(v))).collect()}
}
fn model(integer:bool)->Model {
    Model {name:"independent".into(),vars:(0..2).map(|i|Var {name:format!("x{i}"),
        integer,lower:Some(q(0)),upper:Some(q(1))}).collect(),rows:vec![],objective:e(7,&[(0,2),(1,3)])}
}
fn cert(claim:ImprovementClaim,block:Block)->(Certificate,Request) {
    (Certificate {improvements:vec![ImprovementWitness {claim:claim.clone(),block}],..Certificate::default()},
     Request {improvements:vec![claim],..Request::default()})
}

#[test]
fn finite_domain_oracle_checks_1000_complete_improvement_certificates() {
    let mut accepted=0;
    for integer in [false,true] {for a in -2..=2 {for b in -2..=2 {for c in -2..=2 {for r in 0..=1 {for s in 0..=1 {
        let m=model(integer);let mut terms=vec![];
        let mut constant=2*r+3*s+c;
        for (i,coefficient) in [(0,a-2),(1,b-3)] {
            if coefficient>0 {terms.push((Ref::VarUpper(i),q(coefficient)));constant+=coefficient;}
            else if coefficient<0 {terms.push((Ref::VarLower(i),q(-coefficient)));}
        }
        let mut checks=vec![Ref::Exact;if integer {6}else{4}];checks.push(Ref::Local(0));
        let claim=ImprovementClaim {target:false,integers:integer,positive:e(c,&[(0,a),(1,b)])};
        let block=Block {steps:vec![Step::Lin {id:0,kind:Kind::Le,constant:q(constant),terms}],
            end:End::ImproveReturn {map:vec![e(r,&[]),e(s,&[])],checks,margin:ImprovementMargin::Predicate(q(1))}};
        let (cert,req)=cert(claim,block);
        let success=verify_request(&m,&m,&cert,&req,&Limits::default()).is_ok();
        assert_eq!(success,constant<=0,"certificate a={a} b={b} c={c} r={r} s={s} integer={integer}");
        if success {
            accepted+=1;
            // Independent scaled-integer point arithmetic. For MI this
            // exhausts the entire four-point actual domain; LP samples25
            // exact fractions, including strict-boundary and zero points.
            let denominator=if integer {1}else{4};
            for x in 0..=denominator {for y in 0..=denominator {
                if a*x+b*y+c*denominator>0 {
                    assert!((2*r+3*s)*denominator<2*x+3*y);
                }
            }}
        }
    }}}}}}
    assert!(accepted>0);
}

#[test]
fn chosen_side_uses_its_actual_objective_not_the_other_model() {
    let source=model(false);let mut target=source.clone();target.objective=e(-11,&[(0,-2),(1,-3)]);
    let claim=ImprovementClaim {target:true,integers:false,positive:e(5,&[(0,-2),(1,-3)])};
    let block=Block {steps:vec![],end:End::ImproveReturn {map:vec![e(1,&[]),e(1,&[])],
        checks:vec![Ref::Exact;5],margin:ImprovementMargin::Predicate(q(1))}};
    let (cert,req)=cert(claim,block);
    verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap();
    assert!(verify_request(&target,&source,&cert,&req,&Limits::default()).is_err());
}

#[test]
fn boundary_refutation_cannot_close_a_different_positive_predicate() {
    let m=model(true);
    let claim=ImprovementClaim {target:false,integers:true,positive:e(0,&[(0,1),(1,1)])};
    let leaf=Block {steps:vec![],end:End::PositiveRefutation {fact:Ref::Assumption(1)}};
    let block=Block {steps:vec![],end:End::Split {expression:Expr::var(0),integer:Some(Ref::VarInt(0)),
        left:Box::new(leaf.clone()),right:Box::new(leaf)}};
    let (cert,req)=cert(claim,block);
    // The left branch contains x0=0,x1=1, where the root predicate is positive.
    assert!(verify_request(&m,&m,&cert,&req,&Limits::default()).is_err());
}
