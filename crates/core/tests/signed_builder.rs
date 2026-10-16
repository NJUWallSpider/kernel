use crate::{model::{parse_q,Expr,Model,Q,Var,MAX_Q_BITS},proof::{Kind,Ref,SignedWitness},signed::prepare_unchecked_extension,verify::Limits};
use num_bigint::BigInt;
use serde::Deserialize;
fn q(s:&str)->Q{parse_q(s).unwrap()}
fn e(c:&str,t:&[(u32,&str)])->Expr{Expr{constant:q(c),terms:t.iter().map(|(i,c)|(*i,q(c))).collect()}}
fn model(n:usize)->Model{Model{name:"signed_oracle".into(),vars:(0..n).map(|i|Var{name:format!("x{i}"),integer:false,lower:None,upper:None}).collect(),rows:vec![],objective:Expr::zero()}}
fn w(c:&str,f:Expr,z:Expr)->SignedWitness{SignedWitness{capacity:q(c),flow:f,activation:z,checks:(0..5).map(Ref::Local).collect()}}
fn eval(e:&Expr,x:&[Q])->Q{e.terms.iter().fold(e.constant.clone(),|s,(i,c)|s+c*&x[*i as usize])}
fn feasible(m:&Model,x:&[Q])->bool{x.len()==m.vars.len()&&m.vars.iter().zip(x).all(|(v,x)|(!v.integer||x.is_integer())&&v.lower.as_ref().is_none_or(|l|x>=l)&&v.upper.as_ref().is_none_or(|u|x<=u))&&m.rows.iter().all(|r|{let v=eval(&r.expr,x);r.lower.as_ref().is_none_or(|l|&v>=l)&&r.upper.as_ref().is_none_or(|u|&v<=u)})}
#[test]fn exact_five_premises_and_four_joint_rows_with_affine_constants(){
 let m=model(2);let x=prepare_unchecked_extension(&m,&[w("2/7",e("1/3",&[(0,"2")]),e("-1/5",&[(0,"-1"),(1,"3")]))],&Limits::default()).unwrap();
 let wanted=[e("1/5",&[(0,"1"),(1,"-3")]),e("-6/5",&[(0,"-1"),(1,"3")]),e("-1/5",&[(0,"-1"),(1,"3")]),e("41/105",&[(0,"16/7"),(1,"-6/7")]),e("-29/105",&[(0,"-12/7"),(1,"-6/7")])];
 for (i,p) in x.premises.iter().enumerate(){assert_eq!(p.expression,wanted[i]);assert_eq!(p.reference,Ref::Local(i as u32));assert_eq!(p.kind,if i==2{Kind::Int}else{Kind::Le});}
 assert_eq!(x.model.vars.len(),6);assert_eq!(x.model.rows.len(),4);
 assert_eq!(x.model.rows[0].expr,e("-1/3",&[(0,"-2"),(2,"1"),(3,"-1")]));
 assert_eq!(x.model.rows[1].expr,e("1/5",&[(0,"1"),(1,"-3"),(4,"1"),(5,"1")]));
 assert_eq!(x.model.rows[2].expr,e("0",&[(2,"1"),(4,"-2/7")]));assert_eq!(x.model.rows[3].expr,e("0",&[(3,"1"),(5,"-2/7")]));
 assert!(x.model.vars[2..4].iter().all(|v|!v.integer&&v.lower==Some(q("0"))&&v.upper.is_none()));assert!(x.model.vars[4..].iter().all(|v|v.integer&&v.lower==Some(q("0"))&&v.upper==Some(q("1"))));
 assert_eq!(x.model.vars[..2],m.vars);assert_eq!(x.model.objective,m.objective);
}
#[derive(Deserialize)]struct Case{capacity:String,flow:Expr,activation:Expr,source:Vec<String>,joint:Vec<String>,f:String,z:String}
#[derive(Deserialize)]struct Item{capacity:String,flow:Expr,activation:Expr}
#[derive(Deserialize)]struct Batch{source:Vec<String>,witnesses:Vec<Item>,joint:Vec<String>}
#[derive(Deserialize)]struct Oracle{cases:Vec<Case>,batches:Vec<Batch>}
#[test]fn independent_fraction_construction_boundaries_and_simultaneous_batches(){
 let o:Oracle=serde_json::from_str(include_str!("../../../tests/vectors/signed_oracle.json")).unwrap();assert_eq!(o.cases.len(),72);assert_eq!(o.batches.len(),6);
 for c in o.cases{let x=prepare_unchecked_extension(&model(2),&[w(&c.capacity,c.flow.clone(),c.activation.clone())],&Limits::default()).unwrap();let old=c.source.iter().map(|x|q(x)).collect::<Vec<_>>();assert_eq!(eval(&c.flow,&old),q(&c.f));assert_eq!(eval(&c.activation,&old),q(&c.z));for p in &x.premises{let v=eval(&p.expression,&old);assert!(if p.kind==Kind::Int{v.is_integer()}else{v<=q("0")});}let joint=c.joint.iter().map(|x|q(x)).collect::<Vec<_>>();assert!(feasible(&x.model,&joint));if c.z=="1"{assert_eq!(joint[4].clone()+&joint[5],q("1"));}}
 for c in o.batches{let ws=c.witnesses.into_iter().map(|d|w(&d.capacity,d.flow,d.activation)).collect::<Vec<_>>();let m=model(c.source.len());let x=prepare_unchecked_extension(&m,&ws,&Limits::default()).unwrap();assert!(feasible(&x.model,&c.joint.iter().map(|s|q(s)).collect::<Vec<_>>()));assert_eq!(x.model.vars[..m.vars.len()],m.vars);}
}
#[test]fn zero_capacity_active_zero_and_false_premises_are_distinct(){
 for z in ["0","1"]{let x=prepare_unchecked_extension(&model(0),&[w("0",Expr::zero(),e(z,&[]))],&Limits::default()).unwrap();assert_eq!(x.statistics.generated_terms,6);assert!(feasible(&x.model,&[q("0"),q("0"),q(z),q("0")]));assert_eq!(feasible(&x.model,&[q("0"),q("0"),q("0"),q("0")]),z=="0");}
 for (f,z) in [("1","0"),("3","1"),("-3","1"),("0","1/2"),("0","2"),("0","-1")]{let x=prepare_unchecked_extension(&model(0),&[w("2",e(f,&[]),e(z,&[]))],&Limits::default()).unwrap();assert!(x.premises.iter().any(|p|if p.kind==Kind::Int{!p.expression.constant.is_integer()}else{p.expression.constant>q("0")}));}
}
#[test]fn structural_middle_witness_dimensions_and_canonical_arithmetic_are_checked(){
 let m=model(1);let valid=w("2",Expr::zero(),Expr::var(0));
 for what in 0..6{let mut bad=valid.clone();match what{0=>{bad.checks.pop();},1=>bad.checks.push(Ref::Exact),2=>bad.capacity=q("-1"),3=>bad.flow=Expr::var(1),4=>bad.activation.terms.push((0,q("1"))),_=>bad.capacity=Q::new_raw(2.into(),2.into())}assert!(prepare_unchecked_extension(&m,&[valid.clone(),bad,valid.clone()],&Limits::default()).is_err());}
 let mut overflow=valid.clone();overflow.capacity=Q::from_integer(BigInt::from(1)<<((MAX_Q_BITS-1)as usize));overflow.activation=e("2",&[]);assert!(prepare_unchecked_extension(&m,&[overflow],&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
 let mut upper=valid.clone();upper.activation.constant=-Q::from_integer((BigInt::from(1)<<(MAX_Q_BITS as usize))-1);assert!(prepare_unchecked_extension(&m,&[upper],&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
 let full=prepare_unchecked_extension(&m,&[valid.clone()],&Limits::default()).unwrap();assert!(prepare_unchecked_extension(&m,&[valid],&Limits{work:full.statistics.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
#[test]fn generated_names_cannot_collide_and_empty_extension_preserves_input(){
 let mut m=model(3);m.vars[0].name="$rpx_signed_var_3".into();m.vars[1].name="$rpx_signed_var_4".into();let x=prepare_unchecked_extension(&m,&[w("0",Expr::zero(),Expr::zero())],&Limits::default()).unwrap();x.model.validate().unwrap();assert_eq!(x.model.vars[3].name,"$rpx_signed_var_5");let y=prepare_unchecked_extension(&m,&[],&Limits::default()).unwrap();assert_eq!(m,y.model);assert_eq!(y.statistics.generated_variables,0);
}
