//! Independent semantic attacks against the public API, beyond wire parsing.
use crate::model::{Expr, Model, Q, Row, Var, MAX_Q_BITS};
use crate::proof::{Block, Certificate, End, Kind, Ref, Step};
use crate::verify::{verify, check_block, Limits};
use num_bigint::BigInt;
use num_traits::{One, Zero};

fn q(n: i64, d: i64) -> Q { Q::new(n.into(), d.into()) }
fn c(n: i64) -> Expr { Expr { constant: q(n, 1), terms: vec![] } }
fn x() -> Expr { Expr { constant: q(0, 1), terms: vec![(0, q(1, 1))] } }
fn empty() -> Model { Model { name: "M".into(), vars: vec![], rows: vec![], objective: c(0) } }
fn variable(integer: bool, lower: Option<Q>, upper: Option<Q>) -> Model {
    Model { vars: vec![Var { name: "x".into(), integer, lower, upper }], ..empty() }
}
// Zero-objective rule fixtures explicitly discharge the fixed final objective.
fn leaf(map: Vec<Expr>, mut checks: Vec<Ref>) -> Block { checks.push(Ref::Exact); Block { steps: vec![], end: End::Return { map, checks } } }
fn with_steps(steps: Vec<Step>, end: End) -> Block { Block { steps, end } }
fn run(source: &Model, target: &Model, block: Block) -> Result<(), String> {
    check_block(source, target, &block, &Limits::default()).map(|_| ())
}
fn lin(id: u32, kind: Kind, constant: Q, terms: Vec<(Ref, Q)>) -> Step { Step::Lin { id, kind, constant, terms } }

#[test]
fn integer_and_binary_domains_cannot_be_assumed() {
    let continuous = variable(false, Some(q(0, 1)), Some(q(1, 1)));
    let integer = variable(true, Some(q(0, 1)), Some(q(1, 1)));
    assert!(run(&continuous, &integer, leaf(vec![x()], vec![Ref::VarLower(0), Ref::VarUpper(0), Ref::Exact])).is_err());
    let free_integer = variable(true, None, None);
    assert!(run(&free_integer, &integer, leaf(vec![x()], vec![Ref::Exact, Ref::Exact, Ref::VarInt(0)])).is_err());
    let wrong = with_steps(vec![lin(0, Kind::Int, q(0, 1), vec![(Ref::VarInt(0), q(1, 2))])], End::Return { map: vec![x()], checks: vec![Ref::Local(0), Ref::Exact] });
    assert!(run(&free_integer, &free_integer, wrong).is_err());
}

#[test]
fn equality_transfer_to_integer_is_sound_and_exact() {
    let mut source = variable(false, None, None);
    source.rows.push(Row { name: "fix".into(), expr: x(), lower: Some(q(0,1)), upper: Some(q(0,1)) });
    let target = variable(true, None, Some(q(0,1)));
    // EQ(x) proves both x <= 0 and x integer, since x is exactly zero.
    assert!(run(&source, &target, leaf(vec![x()], vec![Ref::RowEq(0), Ref::RowEq(0)])).is_ok());
    source.rows[0].lower = Some(q(1, 1)); source.rows[0].upper = Some(q(1, 1));
    let target = variable(true, None, None);
    // EQ(x-1) alone has the wrong expression for INT(x).
    assert!(run(&source, &target, leaf(vec![x()], vec![Ref::RowEq(0)])).is_err());
    let block = with_steps(vec![lin(0, Kind::Int, q(1, 1), vec![(Ref::RowEq(0), q(1, 1))])], End::Return { map: vec![x()], checks: vec![Ref::Local(0), Ref::Exact] });
    assert!(run(&source, &target, block).is_ok());
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
        assert!(run(&source, &target, with_steps(vec![step], End::Return { map: vec![], checks: vec![Ref::Exact] })).is_err());
    }
}

#[test]
fn sibling_facts_do_not_leak_and_parent_drop_is_private() {
    let source = variable(false, None, None);
    let target = variable(false, Some(q(0,1)), None);
    let left = with_steps(vec![lin(7, Kind::Le, q(0,1), vec![])], End::Return { map: vec![c(0)], checks: vec![Ref::Local(7), Ref::Exact] });
    let right = leaf(vec![c(0)], vec![Ref::Local(7)]);
    let split = Block { steps: vec![], end: End::Split { expression: x(), integer: None, left: Box::new(left), right: Box::new(right) } };
    assert!(run(&source, &target, split).is_err());

    let left = with_steps(vec![Step::Drop { ids: vec![7] }], End::Return { map: vec![c(0)], checks: vec![Ref::Exact, Ref::Exact] });
    let right = leaf(vec![c(0)], vec![Ref::Local(7)]);
    let split = Block { steps: vec![lin(7, Kind::Le, q(0,1), vec![])], end: End::Split { expression: x(), integer: None, left: Box::new(left), right: Box::new(right) } };
    assert!(run(&source, &target, split).is_ok());
}

#[test]
fn dead_live_duplicate_and_redefined_registers() {
    let target = variable(false, Some(q(0,1)), None);
    let end = End::Return { map: vec![c(0)], checks: vec![Ref::Local(7), Ref::Exact] };
    let definition = lin(7, Kind::Le, q(0,1), vec![]);
    assert!(run(&empty(), &target, with_steps(vec![definition.clone(), Step::Drop { ids: vec![7] }], end.clone())).is_err());
    assert!(run(&empty(), &target, with_steps(vec![definition.clone(), definition.clone()], end.clone())).is_err());
    assert!(run(&empty(), &target, with_steps(vec![definition.clone(), Step::Drop { ids: vec![7,7] }], end.clone())).is_err());
    // The kernel permits register reuse only after a fresh checked derivation.
    assert!(run(&empty(), &target, with_steps(vec![definition.clone(), Step::Drop { ids: vec![7] }, definition], end)).is_ok());
}

#[test]
fn every_leaf_needs_every_output_obligation() {
    let source = variable(false, None, None);
    let target = variable(false, Some(q(0,1)), Some(q(1,1)));
    let split = Block { steps: vec![], end: End::Split { expression: x(), integer: None, left: Box::new(leaf(vec![c(0)], vec![Ref::Exact, Ref::Exact])), right: Box::new(leaf(vec![c(0)], vec![Ref::Exact])) } };
    assert!(run(&source, &target, split).is_err());
    assert!(run(&empty(), &variable(false,None,None), leaf(vec![], vec![])).is_err());
    assert!(run(&empty(), &target, leaf(vec![c(0)], vec![Ref::Exact, Ref::Exact, Ref::Exact])).is_err());
    let mut target = empty(); target.rows.push(Row { name: "impossible".into(), expr: c(1), lower: None, upper: Some(q(0,1)) });
    assert!(run(&empty(), &target, leaf(vec![], vec![])).is_err());
    assert!(run(&empty(), &target, leaf(vec![], vec![Ref::Exact])).is_err());
}







#[test]
fn empty_domain_closure_is_directional() {
    let source = variable(false,Some(q(1,1)),Some(q(0,1)));
    let target = variable(false,Some(q(0,1)),Some(q(1,1)));
    let contradiction=with_steps(vec![lin(0,Kind::Le,q(0,1),vec![(Ref::VarLower(0),q(1,1)),(Ref::VarUpper(0),q(1,1))])],End::Absurd{fact:Ref::Local(0)});
    assert!(run(&source,&target,contradiction.clone()).is_ok());
    let cert=Certificate { forward:contradiction, reverse:leaf(vec![x()],vec![Ref::VarLower(0),Ref::VarUpper(0)]) };
    assert!(verify(&source,&target,&cert,&Limits::default()).is_err());
    assert!(run(&empty(),&empty(),with_steps(vec![lin(0,Kind::Int,q(0,1),vec![])],End::Absurd{fact:Ref::Local(0)})).is_err());
}

#[test]
fn negative_rounding_matches_mathematical_floor_and_ceil() {
    for (numerator,denominator,expected_floor) in [(-1,2,-1),(-3,2,-2),(7,3,2),(-6,3,-2)] {
        let source=variable(true,None,Some(q(numerator,denominator)));
        let target=variable(true,None,Some(q(expected_floor,1)));
        let block=with_steps(vec![Step::Round{id:0,le:Ref::VarUpper(0),integer:Ref::VarInt(0)}],End::Return{map:vec![x()],checks: vec![Ref::Local(0),Ref::VarInt(0), Ref::Exact]});
        assert!(run(&source,&target,block).is_ok());
    }
    let source=variable(true,Some(q(-3,2)),None);
    let target=variable(true,Some(q(-1,1)),None);
    let block=with_steps(vec![lin(0,Kind::Int,q(0,1),vec![(Ref::VarInt(0),q(-1,1))]),Step::Round{id:1,le:Ref::VarLower(0),integer:Ref::Local(0)}],End::Return{map:vec![x()],checks: vec![Ref::Local(1),Ref::VarInt(0), Ref::Exact]});
    assert!(run(&source,&target,block).is_ok());
}

#[test]
fn malformed_public_values_and_resource_arithmetic_cannot_accept() {
    for bad in [Q::new_raw(1.into(),0.into()),Q::new_raw(2.into(),4.into()),Q::new_raw(1.into(),(-2).into())] {
        let block=with_steps(vec![lin(0,Kind::Eq,bad,vec![])],End::Return{map:vec![],checks: vec![Ref::Exact]});
        assert!(run(&empty(),&empty(),block).is_err());
    }
    let big=Q::from_integer(BigInt::one() << (MAX_Q_BITS-1) as usize);
    let mut source=empty();
    source.rows.push(Row{name:"huge".into(),expr:Expr{constant:big.clone(),terms:vec![]},lower:None,upper:Some(-big)});
    let block=Block{steps:vec![],end:End::Absurd{fact:Ref::RowUpper(0)}};
    let result=run(&source,&empty(),block);
    assert!(result.unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn all_branch_assumptions_belong_to_one_path() {
    let source=variable(false,None,None);
    let target=variable(false,None,Some(q(0,1)));
    // A sign split cannot establish x<=0 in its x>=0 branch by reusing
    // the left assumption. The single current assumption is -x<=0 there.
    let split=Block{steps:vec![],end:End::Split{expression:x(),integer:None,left:Box::new(leaf(vec![x()],vec![Ref::Assumption(0)])),right:Box::new(leaf(vec![x()],vec![Ref::Assumption(0)]))}};
    assert!(run(&source,&target,split).is_err());
    let split=Block{steps:vec![],end:End::Split{expression:x(),integer:Some(Ref::VarInt(0)),left:Box::new(leaf(vec![c(0)],vec![Ref::Exact])),right:Box::new(leaf(vec![c(0)],vec![Ref::Exact]))}};
    assert!(run(&source,&target,split).is_err());
    // Joint map: neither selecting a valid value for each variable separately
    // nor separate local facts can excuse a violated relation between them.
    let mut target=variable(false,None,None);target.vars.push(Var{name:"y".into(),integer:false,lower:None,upper:None});
    target.rows.push(Row{name:"same".into(),expr:Expr{constant:Q::zero(),terms:vec![(0,Q::one()),(1,-Q::one())]},lower:Some(Q::zero()),upper:Some(Q::zero())});
    assert!(run(&empty(),&target,leaf(vec![c(0),c(1)],vec![Ref::Exact])).is_err());
}

#[test]
fn rounding_and_integer_split_bound_every_intermediate() {
    let big=Q::from_integer((BigInt::one() << MAX_Q_BITS as usize)-BigInt::one());
    let block=with_steps(vec![lin(0,Kind::Le,-big.clone(),vec![]),lin(1,Kind::Int,big.clone(),vec![]),Step::Round{id:2,le:Ref::Local(0),integer:Ref::Local(1)}],End::Return{map:vec![],checks: vec![Ref::Exact]});
    assert!(run(&empty(),&empty(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let block=with_steps(vec![lin(0,Kind::Int,-big.clone(),vec![])],End::Split{expression:Expr{constant:-big,terms:vec![]},integer:Some(Ref::Local(0)),left:Box::new(leaf(vec![],vec![])),right:Box::new(leaf(vec![],vec![]))});
    assert!(run(&empty(),&empty(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn accumulator_constant_product_is_bounded_before_cancellation(){
    let big=Q::from_integer(BigInt::one() << (MAX_Q_BITS-1) as usize);
    let source=variable(false,Some(big.clone()),None);
    // 2*big exceeds the temporary budget; (-big)+2*big fits again. Both
    // acceptance and rejection are mathematically sound, but the documented
    // resource policy requires checking the product before cancellation.
    let block=with_steps(vec![lin(0,Kind::Le,-big,vec![(Ref::VarLower(0),q(2,1))])],End::Return{map:vec![],checks: vec![Ref::Exact]});
    assert!(run(&source,&empty(),block).unwrap_err().starts_with("RESOURCE_LIMIT"));
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
