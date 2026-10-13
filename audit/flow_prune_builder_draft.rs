use kernel_core::flow_prune::prepare_unchecked_extension;
use kernel_core::model::{parse_q, Expr, Model, Q, MAX_Q_BITS};
use kernel_core::proof::{FlowGroup, FlowWitness, Kind, Ref};
use kernel_core::verify::Limits;
use num_bigint::BigInt;
use serde::Deserialize;

fn q(s: &str) -> Q { parse_q(s).unwrap() }
fn input(n:usize)->Model { Model {name:"prune-input".into(),vars:(0..n).map(|i|kernel_core::model::Var{name:format!("x{i}"),integer:false,lower:Some(q("0")),upper:None}).collect(),rows:vec![],objective:Expr::zero()} }
fn basic()->FlowWitness {FlowWitness{nodes:2,arcs:vec![(0,1)],groups:vec![FlowGroup{source:0,commodities:vec![(1,q("1"))],flows:vec![Expr::var(0)],nonnegative:vec![Ref::VarLower(0)],balances:vec![Ref::Exact,Ref::Exact]}]}}
fn eval(e:&Expr,values:&[Q])->Q {e.terms.iter().fold(e.constant.clone(),|sum,(i,c)|sum+c*&values[*i as usize])}
fn feasible(m:&Model,values:&[Q])->bool {m.vars.iter().zip(values).all(|(v,x)|v.lower.as_ref().map_or(true,|l|x>=l)&&v.upper.as_ref().map_or(true,|u|x<=u)) && m.rows.iter().all(|r|{let x=eval(&r.expr,values);r.lower.as_ref().map_or(true,|l|&x>=l)&&r.upper.as_ref().map_or(true,|u|&x<=u)})}

#[derive(Deserialize)]struct Corpus{cases:Vec<Case>}
#[derive(Deserialize)]struct Case{nodes:u32,arcs:Vec<(u32,u32)>,source:u32,commodities:Vec<(u32,String)>,flows:Vec<String>,kept:Vec<String>,bound:String}

#[test]
fn independent_fraction_constructions_cover_all_generated_rows() {
    let corpus:Corpus=serde_json::from_str(include_str!("../../../tests/vectors/flow_prune_oracle.json")).unwrap();
    assert_eq!(corpus.cases.len(),244);
    for case in corpus.cases {
        let old=input(case.arcs.len());let values:Vec<_>=case.flows.iter().map(|v|q(v)).collect();
        let witness=FlowWitness{nodes:case.nodes,arcs:case.arcs.clone(),groups:vec![FlowGroup{source:case.source,commodities:case.commodities.iter().map(|(i,d)|(*i,q(d))).collect(),flows:(0..values.len()).map(|i|Expr::var(i as u32)).collect(),nonnegative:vec![Ref::Exact;values.len()],balances:vec![Ref::Exact;case.nodes as usize]}]};
        let prepared=prepare_unchecked_extension(&old,&witness,&Limits::default()).unwrap();
        for premise in &prepared.premises {let x=eval(&premise.expression,&values);assert!(if premise.kind==Kind::Le{x<=q("0")}else{x==q("0")});}
        let mut extended_values=values.clone();extended_values.extend(case.kept.iter().map(|v|q(v)));assert!(feasible(&prepared.model,&extended_values));
        assert_eq!(&prepared.model.vars[..old.vars.len()],old.vars.as_slice());assert_eq!(prepared.model.objective,old.objective);
        assert_eq!(prepared.statistics.generated_variables,case.arcs.len() as u64);assert_eq!(prepared.statistics.generated_rows,case.arcs.len() as u64+case.nodes as u64);
        for v in &prepared.model.vars[old.vars.len()..]{assert!(!v.integer);assert_eq!(v.lower,Some(q("0")));assert_eq!(v.upper,Some(q(&case.bound)));}
    }
}

#[test]
fn preparation_does_not_prove_references_or_false_balances() {
    let old=input(1);let prepared=prepare_unchecked_extension(&old,&basic(),&Limits::default()).unwrap();
    assert!(prepared.premises.iter().any(|p|p.kind==Kind::Eq&&eval(&p.expression,&[q("2")])!=q("0")));
    assert!(!feasible(&prepared.model,&[q("0"),q("1")]),"subflow constraint is required");
    assert!(!feasible(&prepared.model,&[q("2"),q("2")]),"total-demand upper bound is required");
    assert!(feasible(&prepared.model,&[q("2"),q("1")]),"conditional extension alone must not certify wrong input balance");
}

#[test]
fn malformed_structure_and_new_scope_expressions_reject() {
    let old=input(1);
    for mutate in [|w:&mut FlowWitness|w.groups[0].nonnegative.clear(),|w:&mut FlowWitness|w.groups[0].balances.pop().map(|_|()).unwrap(),|w:&mut FlowWitness|w.arcs[0].1=2,|w:&mut FlowWitness|w.groups[0].source=2,|w:&mut FlowWitness|w.groups[0].commodities[0].0=2,|w:&mut FlowWitness|w.groups[0].commodities[0].1=q("-1"),|w:&mut FlowWitness|w.groups[0].flows[0]=Expr::var(1)] {let mut w=basic();mutate(&mut w);assert!(prepare_unchecked_extension(&old,&w,&Limits::default()).unwrap_err().starts_with("INVALID"));}
    let mut w=basic();w.groups[0].commodities[0].1=Q::new_raw(BigInt::from(2),BigInt::from(2));assert!(prepare_unchecked_extension(&old,&w,&Limits::default()).unwrap_err().starts_with("INVALID"));
}

#[test]
fn work_dimensions_and_total_demand_intermediates_are_bounded() {
    let old=input(1);let mut limits=Limits::default();limits.work=0;assert!(prepare_unchecked_extension(&old,&basic(),&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut w=basic();w.nodes=u32::MAX;assert!(prepare_unchecked_extension(&old,&w,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let huge=Q::from_integer(BigInt::from(1)<<((MAX_Q_BITS-1) as usize));let w=FlowWitness{nodes:1,arcs:vec![],groups:vec![FlowGroup{source:0,commodities:vec![(0,huge.clone()),(0,huge)],flows:vec![],nonnegative:vec![],balances:vec![Ref::Exact]}]};
    assert!(prepare_unchecked_extension(&input(0),&w,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn shared_old_flows_multiple_groups_constants_and_prefix_names() {
    let mut old=input(1);old.vars[0].name="$rpx_prune_var_1".into();old.objective=Expr{constant:q("2/7"),terms:vec![(0,q("3/5"))]};
    let mut w=basic();w.groups[0].flows[0]=Expr{constant:q("1/3"),terms:vec![(0,q("1"))]};w.groups[0].commodities[0].1=q("4/3");w.groups.push(w.groups[0].clone());
    let prepared=prepare_unchecked_extension(&old,&w,&Limits::default()).unwrap();prepared.model.validate().unwrap();assert_eq!(prepared.model.objective,old.objective);assert_ne!(prepared.model.vars[1].name,old.vars[0].name);assert!(feasible(&prepared.model,&[q("1"),q("4/3"),q("4/3")]));assert_eq!(prepared.premises.len(),6);
}
