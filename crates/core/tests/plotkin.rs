use crate::{codec,model::{Expr,Model,Q,Row,Var},proof::*,rpa,verify::{check_block,Limits}};
use num_traits::Zero;
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn setup(bits:u32,distance:u32)->(Model,Model,Block){
    let n=1usize<<bits;
    let vars=(0..n).map(|i|Var{name:format!("x{i}"),integer:true,lower:Some(q(0)),upper:Some(q(1))}).collect();
    let mut rows=vec![];
    for i in 0..n{for j in i+1..n{if (i^j).count_ones()<distance{rows.push(Row{name:format!("c{i}_{j}"),expr:Expr{constant:q(0),terms:vec![(i as u32,q(1)),(j as u32,q(1))]},lower:None,upper:Some(q(1))});}}}
    let source=Model{name:"cube".into(),vars,rows,objective:Expr::zero()};
    let bound=(2*distance/(2*distance-bits)) as i64;
    let mut target=source.clone();target.name="cut".into();target.rows.push(Row{name:"bound".into(),expr:Expr{constant:q(0),terms:(0..n).map(|i|(i as u32,q(1))).collect()},lower:None,upper:Some(q(bound))});
    let mut checks=vec![];for i in 0..n as u32{checks.extend([Ref::VarLower(i),Ref::VarUpper(i),Ref::VarInt(i)]);}for i in 0..source.rows.len() as u32{checks.push(Ref::RowUpper(i));}checks.extend([Ref::Local(0),Ref::Exact]);
    let block=Block{steps:vec![Step::Plotkin{id:0,bits,distance,variables:(0..n as u32).map(|i|(i,i as u64)).collect(),cliques:(0..source.rows.len() as u32).map(Ref::RowUpper).collect()}],end:End::Return{map:(0..n as u32).map(Expr::var).collect(),checks}};
    (source,target,block)
}
fn check(s:&Model,t:&Model,b:&Block)->Result<crate::verify::Statistics,String>{check_block(s,t,b,&Limits::default())}
fn bad(s:&Model,t:&Model,b:&Block){let e=check(s,t,b).unwrap_err();assert!(e.starts_with("INVALID"),"{e}");}
#[test]fn plotkin_matches_independent_exhaustive_binary_sets_and_permutations(){
    for (bits,distance) in [(1,1),(2,2),(3,2),(3,3),(4,3)]{
        let (s,t,mut c)=setup(bits,distance);check(&s,&t,&c).unwrap();
        let n=s.vars.len();let bound=2*distance/(2*distance-bits);
        // An independent finite-set oracle evaluates original row supports directly.
        for mask in 0..1u64<<n{if s.rows.iter().all(|r|r.expr.terms.iter().filter(|(i,_)|mask&(1u64<<i)!=0).count()<=1){assert!(mask.count_ones()<=bound);}}
        if let Step::Plotkin{variables,cliques,..}=&mut c.steps[0]{variables.reverse();for (_,label) in variables{*label^=(1u64<<bits)-1;}cliques.reverse();}
        check(&s,&t,&c).unwrap();
    }
}
#[test]fn plotkin_all_domain_label_and_parameter_premises_are_binding(){
    let (s,t,c)=setup(3,2);
    for change in 0..7{
        let mut source=s.clone();let mut cert=c.clone();
        match change{
            0=>source.vars[0].integer=false,
            1=>source.vars[0].lower=None,
            2=>source.vars[0].lower=Some(q(-1)),
            3=>source.vars[0].upper=None,
            4=>source.vars[0].upper=Some(q(2)),
            5=>{if let Step::Plotkin{variables,..}=&mut cert.steps[0]{variables[0].1=8;}},
            _=>{if let Step::Plotkin{variables,..}=&mut cert.steps[0]{variables[0].0=1;}},
        }
        let e=check(&source,&t,&cert).unwrap_err();assert!(e.contains("Plotkin"),"{change}: {e}");
    }
    for (bits,distance) in [(0,1),(65,64),(3,1),(3,0),(3,65)]{let mut c=c.clone();if let Step::Plotkin{bits:b,distance:d,..}=&mut c.steps[0]{*b=bits;*d=distance;}bad(&s,&t,&c);}
}
#[test]fn every_close_pair_and_every_clique_term_is_checked(){
    let (s,t,c)=setup(3,2);
    let mut broken=c.clone();if let Step::Plotkin{cliques,..}=&mut broken.steps[0]{cliques.remove(5);}assert!(check(&s,&t,&broken).unwrap_err().contains("close pair"));
    for change in 0..4{
        let mut source=s.clone();
        match change{0=>source.rows[5].upper=Some(q(2)),1=>source.rows[5].expr.terms[0].1=q(2),2=>source.rows[5].expr.terms[0].1=q(-1),_=>source.rows[5].upper=None}
        bad(&source,&t,&c);
    }
    // A negative extra coordinate could mask two selected ones; this row cannot be a clique witness.
    let mut source=s.clone();source.vars.push(Var{name:"padding".into(),integer:false,lower:Some(q(-1)),upper:None});source.rows[5].expr.terms.push((8,q(1)));
    assert!(check(&source,&t,&c).unwrap_err().contains("nonnegative domain"));
    source.vars[8].lower=Some(q(0));
    let empty=Model{name:"empty".into(),vars:vec![],rows:vec![],objective:Expr{constant:q(0),terms:vec![]}};
    let mut only=c.clone();only.end=End::Return{map:vec![],checks:vec![Ref::Exact]};check(&source,&empty,&only).unwrap();
    // Duplicate labels are legal only when their resulting distance-zero pair is also covered.
    let mut cert=c.clone();if let Step::Plotkin{variables,..}=&mut cert.steps[0]{variables[7].1=0;}assert!(check(&s,&t,&cert).unwrap_err().contains("close pair"));
}
#[test]fn checked_local_cliques_are_allowed_and_dead_references_reject(){
    let (s,t,mut c)=setup(3,2);
    if let Step::Plotkin{cliques,..}=&mut c.steps[0]{cliques[0]=Ref::Local(12);}
    c.steps.insert(0,Step::Lin{id:12,kind:Kind::Le,constant:q(0),terms:vec![(Ref::RowUpper(0),q(1))]});
    check(&s,&t,&c).unwrap();c.steps.insert(1,Step::Drop{ids:vec![12]});bad(&s,&t,&c);
}
#[test]fn plotkin_inside_cases_exports_only_its_common_fact(){
    let (s,t,mut c)=setup(3,2);
    let theorem=c.steps.remove(0);
    let expr=Expr{constant:q(-4),terms:(0..8).map(|i|(i,q(1))).collect()};
    let child=Derivation{steps:vec![theorem],end:DerivationEnd::Witness(Ref::Local(0))};
    c.steps.push(Step::Cases(Box::new(CasesStep{id:0,kind:Kind::Le,expression:expr,split:Expr{constant:Q::zero(),terms:vec![]},integer:None,left:Box::new(child.clone()),right:Box::new(child)})));
    check(&s,&t,&c).unwrap();
    let cert=Certificate{forward:c.clone(),reverse:c};let bytes=codec::encode_certificate(&cert).unwrap();assert_eq!(bytes[4],11);assert_eq!(rpa::assemble(&rpa::disassemble(&cert).unwrap()).unwrap(),cert);
}
