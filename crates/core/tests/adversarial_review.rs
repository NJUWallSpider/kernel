//! Independent semantic attacks against the public API, beyond wire parsing.
use kernel_core::model::{Expr, Model, Q, Row, Var, MAX_Q_BITS};
use kernel_core::proof::{Block, Certificate, Claim, End, Kind, Objective, Ref, Step};
use kernel_core::verify::{verify, Limits};
use num_bigint::BigInt;
use num_traits::{One, Zero};

fn q(n: i64, d: i64) -> Q { Q::new(n.into(), d.into()) }
fn c(n: i64) -> Expr { Expr { constant: q(n, 1), terms: vec![] } }
fn x() -> Expr { Expr { constant: q(0, 1), terms: vec![(0, q(1, 1))] } }
fn empty() -> Model { Model { name: "M".into(), vars: vec![], rows: vec![], objective: c(0) } }
fn variable(integer: bool, lower: Option<Q>, upper: Option<Q>) -> Model {
    Model { vars: vec![Var { name: "x".into(), integer, lower, upper }], ..empty() }
}
fn claim() -> Claim { Claim {input_halfspace:None,input_objective_level:None, affine_projection:vec![], input_objective_lower:None, reverse: false, input_integers: true, output_integers: true, objective: Objective::None, projection: vec![], inverse: None } }
fn leaf(map: Vec<Expr>, checks: Vec<Ref>) -> Block { Block { steps: vec![], end: End::Return { map, checks } } }
fn with_steps(steps: Vec<Step>, end: End) -> Block { Block { steps, end } }
fn run(source: &Model, target: &Model, cl: Claim, block: Block) -> Result<(), String> {
    let cert = Certificate { improvements:vec![], bijections:vec![], points:vec![], claims: vec![cl.clone()], blocks: vec![block] };
    verify(source, target, &cert, &[cl], &Limits::default()).map(|_| ())
}
fn lin(id: u32, kind: Kind, constant: Q, terms: Vec<(Ref, Q)>) -> Step { Step::Lin { id, kind, constant, terms } }

#[test]
fn integer_and_binary_domains_cannot_be_assumed() {
    let continuous = variable(false, Some(q(0, 1)), Some(q(1, 1)));
    let integer = variable(true, Some(q(0, 1)), Some(q(1, 1)));
    assert!(run(&continuous, &integer, claim(), leaf(vec![x()], vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::Exact])).is_err());
    let mut relaxed = claim(); relaxed.input_integers = false;
    assert!(run(&integer, &integer, relaxed, leaf(vec![x()], vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::VarInt(0)])).is_err());
    let free_integer = variable(true, None, None);
    assert!(run(&free_integer, &integer, claim(), leaf(vec![x()], vec![Ref::Exact, Ref::Exact, Ref::VarInt(0)])).is_err());
    let wrong = with_steps(vec![lin(0, Kind::Int, q(0, 1), vec![(Ref::VarInt(0), q(1, 2))])], End::Return { map: vec![x()], checks: vec![Ref::Local(0)] });
    assert!(run(&free_integer, &free_integer, claim(), wrong).is_err());
}

#[test]
fn equality_transfer_to_integer_is_sound_and_exact() {
    let mut source = variable(false, None, None);
    source.rows.push(Row { name: "fix".into(), expr: x(), lower: Some(q(0,1)), upper: Some(q(0,1)) });
    let target = variable(true, None, Some(q(0,1)));
    // EQ(x) proves both x <= 0 and x integer, since x is exactly zero.
    assert!(run(&source, &target, claim(), leaf(vec![x()], vec![Ref::RowEq(0), Ref::RowEq(0)])).is_ok());
    source.rows[0].lower = Some(q(1, 1)); source.rows[0].upper = Some(q(1, 1));
    let target = variable(true, None, None);
    // EQ(x-1) alone has the wrong expression for INT(x).
    assert!(run(&source, &target, claim(), leaf(vec![x()], vec![Ref::RowEq(0)])).is_err());
    let block = with_steps(vec![lin(0, Kind::Int, q(1, 1), vec![(Ref::RowEq(0), q(1, 1))])], End::Return { map: vec![x()], checks: vec![Ref::Local(0)] });
    assert!(run(&source, &target, claim(), block).is_ok());
}

#[test]
fn invalid_linear_premises_are_checked_even_at_zero_weight() {
    let source = variable(false, Some(q(0,1)), None);
    let target = empty();
    for step in [
        lin(0, Kind::Le, q(0,1), vec![(Ref::VarLower(0), q(-1,1))]),
        lin(0, Kind::Eq, q(0,1), vec![(Ref::VarLower(0), q(1,1))]),
        lin(0, Kind::Int, q(0,1), vec![(Ref::VarLower(0), q(1,1))]),
        lin(0, Kind::Le, q(0,1), vec![(Ref::Local(999), q(0,1))]),
        lin(0, Kind::Le, q(1,1), vec![]),
        lin(0, Kind::Eq, q(-1,1), vec![]),
        lin(0, Kind::Int, q(1,2), vec![]),
    ] {
        assert!(run(&source, &target, claim(), with_steps(vec![step], End::Return { map: vec![], checks: vec![] })).is_err());
    }
}

#[test]
fn sibling_facts_do_not_leak_and_parent_drop_is_private() {
    let source = variable(false, None, None);
    let target = variable(false, Some(q(0,1)), None);
    let left = with_steps(vec![lin(7, Kind::Le, q(0,1), vec![])], End::Return { map: vec![c(0)], checks: vec![Ref::Local(7)] });
    let right = leaf(vec![c(0)], vec![Ref::Local(7)]);
    let split = Block { steps: vec![], end: End::Split { expression: x(), integer: None, left: Box::new(left), right: Box::new(right) } };
    assert!(run(&source, &target, claim(), split).is_err());

    let left = with_steps(vec![Step::Drop { ids: vec![7] }], End::Return { map: vec![c(0)], checks: vec![Ref::Exact] });
    let right = leaf(vec![c(0)], vec![Ref::Local(7)]);
    let split = Block { steps: vec![lin(7, Kind::Le, q(0,1), vec![])], end: End::Split { expression: x(), integer: None, left: Box::new(left), right: Box::new(right) } };
    assert!(run(&source, &target, claim(), split).is_ok());
}

#[test]
fn dead_live_duplicate_and_redefined_registers() {
    let target = variable(false, Some(q(0,1)), None);
    let end = End::Return { map: vec![c(0)], checks: vec![Ref::Local(7)] };
    let definition = lin(7, Kind::Le, q(0,1), vec![]);
    assert!(run(&empty(), &target, claim(), with_steps(vec![definition.clone(), Step::Drop { ids: vec![7] }], end.clone())).is_err());
    assert!(run(&empty(), &target, claim(), with_steps(vec![definition.clone(), definition.clone()], end.clone())).is_err());
    assert!(run(&empty(), &target, claim(), with_steps(vec![definition.clone(), Step::Drop { ids: vec![7,7] }], end.clone())).is_err());
    // V1 explicitly permits register reuse only after a fresh checked derivation.
    assert!(run(&empty(), &target, claim(), with_steps(vec![definition.clone(), Step::Drop { ids: vec![7] }, definition], end)).is_ok());
}

#[test]
fn every_leaf_needs_every_output_obligation() {
    let source = variable(false, None, None);
    let target = variable(false, Some(q(0,1)), Some(q(1,1)));
    let split = Block { steps: vec![], end: End::Split { expression: x(), integer: None, left: Box::new(leaf(vec![c(0)], vec![Ref::Exact, Ref::Exact])), right: Box::new(leaf(vec![c(0)], vec![Ref::Exact])) } };
    assert!(run(&source, &target, claim(), split).is_err());
    assert!(run(&empty(), &variable(false,None,None), claim(), leaf(vec![], vec![])).is_err());
    assert!(run(&empty(), &target, claim(), leaf(vec![c(0)], vec![Ref::Exact, Ref::Exact, Ref::Exact])).is_err());
    let mut target = empty(); target.rows.push(Row { name: "impossible".into(), expr: c(1), lower: None, upper: Some(q(0,1)) });
    assert!(run(&empty(), &target, claim(), leaf(vec![], vec![])).is_err());
    assert!(run(&empty(), &target, claim(), leaf(vec![], vec![Ref::Exact])).is_err());
}

#[test]
fn objective_constant_and_requested_contract_are_binding() {
    let mut source = empty(); source.objective = c(5);
    let mut target = empty(); target.objective = c(7);
    let mut cl = claim(); cl.objective = Objective::Equal;
    assert!(run(&source, &target, cl.clone(), leaf(vec![], vec![Ref::Exact])).is_err());
    cl.objective = Objective::NonIncreasing;
    assert!(run(&source, &target, cl.clone(), leaf(vec![], vec![Ref::Exact])).is_err());
    target.objective = c(3);
    assert!(run(&source, &target, cl.clone(), leaf(vec![], vec![Ref::Exact])).is_ok());
    let cert = Certificate { improvements:vec![], bijections:vec![], points:vec![], claims: vec![claim()], blocks: vec![leaf(vec![], vec![])] };
    assert!(verify(&source,&target,&cert,&[cl],&Limits::default()).is_err());
    assert!(verify(&source,&target,&Certificate { improvements:vec![], bijections:vec![], points:vec![], claims:vec![],blocks:vec![] },&[],&Limits::default()).is_err());
}

#[test]
fn projection_cannot_be_omitted_or_replaced_by_feasibility() {
    let source = variable(false, Some(q(0,1)), Some(q(1,1)));
    let mut cl = claim(); cl.projection = vec![(0,0)];
    assert!(run(&source,&source,cl.clone(),leaf(vec![c(0)],vec![Ref::Exact,Ref::Exact,Ref::Exact])).is_err());
    assert!(run(&source,&source,cl.clone(),leaf(vec![x()],vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::Exact])).is_ok());
    cl.projection.push((0,0));
    assert!(run(&source,&source,cl,leaf(vec![x()],vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::Exact,Ref::Exact])).is_err());
}

#[test]
fn inverse_compositions_reject_two_collapsing_maps() {
    let source = variable(false, Some(q(0,1)), Some(q(1,1)));
    let mut a=claim(); a.inverse=Some(1);
    let mut b=claim(); b.reverse=true; b.inverse=Some(0);
    let good=leaf(vec![x()],vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::Exact]);
    let claims=vec![a,b];
    let mut cert=Certificate { improvements:vec![], bijections:vec![], points:vec![], claims:claims.clone(),blocks:vec![good.clone(),good] };
    assert!(verify(&source,&source,&cert,&claims,&Limits::default()).is_ok());
    cert.blocks=vec![leaf(vec![c(0)],vec![Ref::Exact,Ref::Exact,Ref::Exact]);2];
    assert!(verify(&source,&source,&cert,&claims,&Limits::default()).is_err());
    let mut bad=claims.clone(); bad[0].inverse=Some(0); cert.claims=bad.clone();
    assert!(verify(&source,&source,&cert,&bad,&Limits::default()).is_err());
    let mut bad=claims.clone(); bad[1].input_integers=false; cert.claims=bad.clone();
    assert!(verify(&source,&source,&cert,&bad,&Limits::default()).is_err());
}

#[test]
fn empty_domain_closure_is_directional() {
    let source = variable(false,Some(q(1,1)),Some(q(0,1)));
    let target = variable(false,Some(q(0,1)),Some(q(1,1)));
    let contradiction=with_steps(vec![lin(0,Kind::Le,q(0,1),vec![(Ref::VarLower(0),q(1,1)),(Ref::VarUpper(0),q(1,1))])],End::Absurd{fact:Ref::Local(0)});
    assert!(run(&source,&target,claim(),contradiction.clone()).is_ok());
    let mut rev=claim();rev.reverse=true;
    let claims=vec![claim(),rev];
    let cert=Certificate { improvements:vec![], bijections:vec![], points:vec![], claims:claims.clone(),blocks:vec![contradiction,leaf(vec![x()],vec![Ref::VarLower(0),Ref::VarUpper(0)])] };
    assert!(verify(&source,&target,&cert,&claims,&Limits::default()).is_err());
    assert!(run(&empty(),&empty(),claim(),with_steps(vec![lin(0,Kind::Int,q(0,1),vec![])],End::Absurd{fact:Ref::Local(0)})).is_err());
}

#[test]
fn negative_rounding_matches_mathematical_floor_and_ceil() {
    for (numerator,denominator,expected_floor) in [(-1,2,-1),(-3,2,-2),(7,3,2),(-6,3,-2)] {
        let source=variable(true,None,Some(q(numerator,denominator)));
        let target=variable(true,None,Some(q(expected_floor,1)));
        let block=with_steps(vec![Step::Round{id:0,le:Ref::VarUpper(0),integer:Ref::VarInt(0)}],End::Return{map:vec![x()],checks:vec![Ref::Local(0),Ref::VarInt(0)]});
        assert!(run(&source,&target,claim(),block).is_ok());
    }
    let source=variable(true,Some(q(-3,2)),None);
    let target=variable(true,Some(q(-1,1)),None);
    let block=with_steps(vec![lin(0,Kind::Int,q(0,1),vec![(Ref::VarInt(0),q(-1,1))]),Step::Round{id:1,le:Ref::VarLower(0),integer:Ref::Local(0)}],End::Return{map:vec![x()],checks:vec![Ref::Local(1),Ref::VarInt(0)]});
    assert!(run(&source,&target,claim(),block).is_ok());
}

#[test]
fn malformed_public_values_and_resource_arithmetic_cannot_accept() {
    for bad in [Q::new_raw(1.into(),0.into()),Q::new_raw(2.into(),4.into()),Q::new_raw(1.into(),(-2).into())] {
        let block=with_steps(vec![lin(0,Kind::Eq,bad,vec![])],End::Return{map:vec![],checks:vec![]});
        assert!(run(&empty(),&empty(),claim(),block).is_err());
    }
    let big=Q::from_integer(BigInt::one() << (MAX_Q_BITS-1) as usize);
    let mut source=empty();
    source.rows.push(Row{name:"huge".into(),expr:Expr{constant:big.clone(),terms:vec![]},lower:None,upper:Some(-big)});
    let block=Block{steps:vec![],end:End::Absurd{fact:Ref::RowUpper(0)}};
    let result=run(&source,&empty(),claim(),block);
    assert!(result.unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn all_branch_assumptions_belong_to_one_path() {
    let source=variable(false,None,None);
    let target=variable(false,None,Some(q(0,1)));
    // A sign split cannot establish x<=0 in its x>=0 branch by reusing
    // the left assumption. The single current assumption is -x<=0 there.
    let split=Block{steps:vec![],end:End::Split{expression:x(),integer:None,left:Box::new(leaf(vec![x()],vec![Ref::Assumption(0)])),right:Box::new(leaf(vec![x()],vec![Ref::Assumption(0)]))}};
    assert!(run(&source,&target,claim(),split).is_err());
    let split=Block{steps:vec![],end:End::Split{expression:x(),integer:Some(Ref::VarInt(0)),left:Box::new(leaf(vec![c(0)],vec![Ref::Exact])),right:Box::new(leaf(vec![c(0)],vec![Ref::Exact]))}};
    assert!(run(&source,&target,claim(),split).is_err());
    // Joint map: neither selecting a valid value for each variable separately
    // nor separate local facts can excuse a violated relation between them.
    let mut target=variable(false,None,None);target.vars.push(Var{name:"y".into(),integer:false,lower:None,upper:None});
    target.rows.push(Row{name:"same".into(),expr:Expr{constant:Q::zero(),terms:vec![(0,Q::one()),(1,-Q::one())]},lower:Some(Q::zero()),upper:Some(Q::zero())});
    assert!(run(&empty(),&target,claim(),leaf(vec![c(0),c(1)],vec![Ref::Exact])).is_err());
}

#[test]
fn rounding_and_integer_split_bound_every_intermediate() {
    let big=Q::from_integer((BigInt::one() << MAX_Q_BITS as usize)-BigInt::one());
    let block=with_steps(vec![lin(0,Kind::Le,-big.clone(),vec![]),lin(1,Kind::Int,big.clone(),vec![]),Step::Round{id:2,le:Ref::Local(0),integer:Ref::Local(1)}],End::Return{map:vec![],checks:vec![]});
    assert!(run(&empty(),&empty(),claim(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let block=with_steps(vec![lin(0,Kind::Int,-big.clone(),vec![])],End::Split{expression:Expr{constant:-big,terms:vec![]},integer:Some(Ref::Local(0)),left:Box::new(leaf(vec![],vec![])),right:Box::new(leaf(vec![],vec![]))});
    assert!(run(&empty(),&empty(),claim(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn accumulator_constant_product_is_bounded_before_cancellation(){
    let big=Q::from_integer(BigInt::one() << (MAX_Q_BITS-1) as usize);
    let source=variable(false,Some(big.clone()),None);
    // 2*big exceeds the temporary budget; (-big)+2*big fits again. Both
    // acceptance and rejection are mathematically sound, but the documented
    // resource policy requires checking the product before cancellation.
    let block=with_steps(vec![lin(0,Kind::Le,-big,vec![(Ref::VarLower(0),q(2,1))])],End::Return{map:vec![],checks:vec![]});
    assert!(run(&source,&empty(),claim(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn public_expression_addition_bounds_the_temporary_constant_product(){
    let big=Q::from_integer(BigInt::one() << (MAX_Q_BITS-1) as usize);
    let mut sum=Expr{constant:-big.clone(),terms:vec![]};
    let other=Expr{constant:big,terms:vec![]};
    // The public helper must apply the same intermediate-value budget as the
    // verifier accumulator: 2*big is over budget even though the sum fits.
    assert!(sum.add_scaled(&other,&q(2,1)).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
