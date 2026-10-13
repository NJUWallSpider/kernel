//! Complete-model integration attacks for the joint existential flow extension.
use kernel_core::{codec,model::{Expr,Model,Q,Row,Var},proof::*,rpa,verify::{verify,Limits}};
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn expr(c:i64,terms:&[(u32,i64)])->Expr{Expr{constant:q(c),terms:terms.iter().map(|(i,n)|(*i,q(*n))).collect()}}
fn row(name:&str,e:Expr,rhs:i64)->Row{Row{name:name.into(),expr:e,lower:Some(q(rhs)),upper:Some(q(rhs))}}
fn variable(name:&str)->Var{Var{name:name.into(),integer:false,lower:Some(q(0)),upper:None}}
fn fixture()->(Model,Model,Certificate){
    // Arc 0 is a demanded path; arc 1 a sink self-loop; arc 2 a
    // disconnected self-loop. Arbitrary nonnegative circulation is retained.
    let source=Model{name:"aggregated".into(),vars:vec![variable("f0"),variable("f1"),variable("f2")],rows:vec![row("demand",expr(0,&[(0,1)]),2)],objective:expr(7,&[(0,1),(1,3),(2,5)])};
    let mut target=source.clone();target.name="joint".into();for k in 0..2{for e in 0..3{target.vars.push(variable(&format!("z{k}_{e}")));}}
    for k in 0..2{let v=3+3*k;target.rows.extend([row(&format!("c{k}s"),expr(0,&[(v,1)]),1),row(&format!("c{k}t"),expr(0,&[(v,-1)]),-1),row(&format!("c{k}z"),expr(0,&[]),0)]);}
    for a in 0..3{target.rows.push(row(&format!("arc{a}"),expr(0,&[(a,-1),(3+a,1),(6+a,1)]),0));}
    target.objective=expr(7,&[(3,1),(4,3),(5,5),(6,1),(7,3),(8,5)]);
    let claim=Claim{input_halfspace:None,input_objective_level:None, affine_projection:vec![],reverse:false,input_integers:false,output_integers:false,objective:Objective::Equal,projection:vec![(0,0),(1,1),(2,2)],inverse:None,input_objective_lower:None};
    let mut checks=(0..9).map(Ref::VarLower).collect::<Vec<_>>();checks.extend((0..10).map(Ref::RowEq));checks.extend([Ref::Local(100),Ref::Exact,Ref::Exact,Ref::Exact]);
    let child=Block{steps:vec![Step::Lin{id:100,kind:Kind::Eq,constant:q(0),terms:vec![(Ref::RowEq(7),q(1)),(Ref::RowEq(8),q(3)),(Ref::RowEq(9),q(5))]}],end:End::Return{map:(0..9).map(Expr::var).collect(),checks}};
    let witness=FlowWitness{nodes:3,arcs:vec![(0,1),(1,1),(2,2)],groups:vec![FlowGroup{source:0,commodities:vec![(1,q(1)),(1,q(1))],flows:(0..3).map(Expr::var).collect(),nonnegative:(0..3).map(Ref::VarLower).collect(),balances:vec![Ref::RowEq(0),Ref::Local(0),Ref::Exact]}]};
    let cert=Certificate { improvements:vec![], bijections:vec![],claims:vec![claim],blocks:vec![Block{steps:vec![Step::Lin{id:0,kind:Kind::Eq,constant:q(0),terms:vec![(Ref::RowEq(0),q(-1))]}],end:End::FlowLift{witness,body:Box::new(child)}}],points:vec![]};
    (source,target,cert)
}
fn check(s:&Model,t:&Model,c:&Certificate)->Result<kernel_core::verify::Statistics,String>{verify(s,t,c,&c.claims,&Limits::default())}
#[test]fn joint_lift_preserves_all_arcs_circulations_and_objective(){
    let (s,t,c)=fixture();let stats=check(&s,&t,&c).unwrap();assert_eq!((stats.flow_lifts,stats.flow_generated_variables,stats.flow_generated_rows),(1,6,9));assert!(stats.flow_generated_terms>0);
    let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&4u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 4\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
}
#[test]fn every_flow_premise_uses_pre_extension_scope(){
    let (s,t,c)=fixture();
    for change in 0..9{let mut cert=c.clone();if let End::FlowLift{witness,..}=&mut cert.blocks[0].end{let g=&mut witness.groups[0];match change{
        0=>g.nonnegative[1]=Ref::VarLower(3),
        1=>g.balances[1]=Ref::RowEq(2),
        2=>{g.balances.pop();},
        3=>{g.nonnegative.remove(1);},
        4=>g.flows[1]=Expr::var(3),
        5=>g.source=1,
        6=>g.commodities[0].1=q(2),
        7=>g.commodities[0].1=q(-1),
        _=>{g.commodities.clear();},
    }}assert!(check(&s,&t,&cert).is_err(),"{change}");}
}
#[test]fn target_constraints_integrality_and_common_objective_are_not_bypassed(){
    let (s,t,c)=fixture();
    for change in 0..5{let mut target=t.clone();let mut cert=c.clone();match change{
        0=>target.vars[3].upper=Some(q(0)),
        1=>target.objective.terms[0].1=q(2),
        2=>target.rows[9].upper=Some(q(1)),
        3=>{target.vars[3].integer=true;cert.claims[0].output_integers=true;},
        _=>target.rows.push(row("unproved",expr(0,&[(4,1)]),0)),
    }assert!(check(&s,&target,&cert).is_err(),"{change}");}
    // Projection remains tied to original input coordinates, not new witnesses.
    let mut cert=c.clone();cert.claims[0].projection.push((3,3));assert!(check(&s,&t,&cert).unwrap_err().contains("projection"));
}
#[test]fn child_extension_does_not_escape_to_sibling_and_inverse_is_rejected(){
    let (s,t,mut c)=fixture();let left=c.blocks[0].clone();
    let right=if let End::FlowLift{body,..}=&left.end{(**body).clone()}else{unreachable!()};
    c.blocks[0]=Block{steps:vec![],end:End::Split{expression:expr(0,&[]),integer:None,left:Box::new(left),right:Box::new(right)}};
    assert!(check(&s,&t,&c).is_err());
    let (_,_,mut c)=fixture();let mut reverse=c.claims[0].clone();reverse.reverse=true;reverse.projection.clear();c.claims[0].inverse=Some(1);c.claims.push(reverse);c.blocks.push(Block{steps:vec![],end:End::Return{map:(0..3).map(Expr::var).collect(),checks:vec![]}});
    assert!(check(&s,&t,&c).unwrap_err().contains("inverse requires affine"));
}
#[test]fn flow_graph_dimensions_resource_and_versions_are_checked(){
    let (s,t,c)=fixture();
    for change in 0..4{let mut c=c.clone();if let End::FlowLift{witness,..}=&mut c.blocks[0].end{match change{0=>witness.nodes=0,1=>witness.arcs[1].1=3,2=>{witness.arcs.pop();},_=>witness.groups[0].commodities[0].0=3}}assert!(check(&s,&t,&c).is_err());}
    let stats=check(&s,&t,&c).unwrap();assert!(verify(&s,&t,&c,&c.claims,&Limits{work:stats.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
    assert!(verify(&s,&t,&c,&c.claims,&Limits{depth:1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let bytes=codec::encode_certificate(&c).unwrap();let text=rpa::disassemble(&c).unwrap();for version in [1u16,2,3]{let mut b=bytes.clone();b[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&b).is_err());assert!(rpa::assemble(&text.replacen("RPA 4",&format!("RPA {version}"),1)).is_err());}
    for n in 0..bytes.len(){let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err(),"{n}");}
    for i in 16..bytes.len(){for value in [0,1,127,255]{let mut b=bytes.clone();b[i]=value;if let Ok(decoded)=codec::decode_certificate(&b){let _=check(&s,&t,&decoded);}}}
}
#[test]fn nested_lifts_preserve_old_witness_coordinates_and_objective(){
    let (s,t,mut c)=fixture();
    if let End::FlowLift{witness,body}=&mut c.blocks[0].end{
        let final_body=(**body).clone();
        *body=Box::new(Block{steps:vec![],end:End::FlowLift{witness:witness.clone(),body:Box::new(final_body)}});
    }
    let stats=check(&s,&t,&c).unwrap();assert_eq!((stats.flow_lifts,stats.flow_generated_variables,stats.flow_generated_rows),(2,12,18));
    assert!(verify(&s,&t,&c,&c.claims,&Limits{depth:2,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
    assert_eq!(codec::decode_certificate(&codec::encode_certificate(&c).unwrap()).unwrap(),c);
}
