use kernel_core::{model::{Expr,Model,Var,Row,parse_q},proof::*,verify::{verify,Limits}};
use serde::Deserialize;
#[derive(Deserialize)]struct Oracle{numbers:Vec<[String;3]>,linear:Vec<[String;5]>,rounds:Vec<[String;2]>}
#[test]fn independent_fraction_oracle_4000_vectors(){
 let data:Oracle=serde_json::from_str(include_str!("../../../tests/vectors/exact_oracle.json")).unwrap();
 for [text,n,d] in data.numbers {let q=parse_q(&text).unwrap();assert_eq!(q.numer().to_string(),n);assert_eq!(q.denom().to_string(),d);}
 for [a,b,c,n,d] in data.linear {let mut x=Expr{constant:parse_q(&a).unwrap(),terms:vec![(0,parse_q(&a).unwrap())]};let y=Expr{constant:parse_q(&b).unwrap(),terms:vec![(0,parse_q(&b).unwrap())]};x.add_scaled(&y,&parse_q(&c).unwrap()).unwrap();assert_eq!(x.constant.numer().to_string(),n);assert_eq!(x.constant.denom().to_string(),d);assert_eq!(x.terms[0].1,x.constant);}
 for [d,ceil] in data.rounds {
   let q=parse_q(&d).unwrap();let expected=parse_q(&ceil).unwrap();
   let s=Model{name:"oracle".into(),vars:vec![Var{name:"x".into(),integer:true,lower:None,upper:None}],rows:vec![Row{name:"r".into(),expr:Expr::var(0),lower:None,upper:Some(-q)}],objective:Expr::zero()};let mut t=s.clone();t.rows[0].upper=Some(-expected);
   let claim=Claim{input_halfspace:None,input_objective_level:None, affine_projection:vec![], input_objective_lower:None,reverse:false,input_integers:true,output_integers:true,objective:Objective::Equal,projection:vec![],inverse:None};
   let cert=Certificate { improvements:vec![], bijections:vec![], points:vec![],claims:vec![claim],blocks:vec![Block{steps:vec![Step::Round{id:0,le:Ref::RowUpper(0),integer:Ref::VarInt(0)}],end:End::Return{map:vec![Expr::var(0)],checks:vec![Ref::Exact,Ref::Local(0),Ref::Exact]}}]};
   assert!(verify(&s,&t,&cert,&cert.claims,&Limits::default()).is_ok());
   t.rows[0].upper.as_mut().map(|v|*v-=parse_q("1").unwrap());assert!(verify(&s,&t,&cert,&cert.claims,&Limits::default()).is_err());
 }
}
