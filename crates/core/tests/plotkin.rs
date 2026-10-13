use kernel_core::{codec,model::{Expr,Model,Q,Row,Var},proof::*,rpa,verify::{verify,verify_request,Limits}};
use num_traits::Zero;
fn q(n:i64)->Q{Q::from_integer(n.into())}
fn setup(bits:u32,distance:u32)->(Model,Model,Certificate){
    let n=1usize<<bits;
    let vars=(0..n).map(|i|Var{name:format!("x{i}"),integer:true,lower:Some(q(0)),upper:Some(q(1))}).collect();
    let mut rows=vec![];
    for i in 0..n{for j in i+1..n{if (i^j).count_ones()<distance{rows.push(Row{name:format!("c{i}_{j}"),expr:Expr{constant:q(0),terms:vec![(i as u32,q(1)),(j as u32,q(1))]},lower:None,upper:Some(q(1))});}}}
    let source=Model{name:"cube".into(),vars,rows,objective:Expr{constant:q(0),terms:(0..n).map(|i|(i as u32,q(-1))).collect()}};
    let bound=(2*distance/(2*distance-bits)) as i64;
    let mut target=source.clone();target.name="cut".into();target.rows.push(Row{name:"bound".into(),expr:Expr{constant:q(0),terms:(0..n).map(|i|(i as u32,q(1))).collect()},lower:None,upper:Some(q(bound))});
    let claim=Claim{input_halfspace:None,input_objective_level:None, affine_projection:vec![],reverse:false,input_integers:true,output_integers:true,objective:Objective::Equal,projection:vec![],inverse:None,input_objective_lower:Some(q(-bound))};
    let mut checks=vec![];for i in 0..n as u32{checks.extend([Ref::VarLower(i),Ref::VarUpper(i),Ref::VarInt(i)]);}for i in 0..source.rows.len() as u32{checks.push(Ref::RowUpper(i));}checks.extend([Ref::Local(0),Ref::Exact,Ref::Local(0)]);
    let cert=Certificate { improvements:vec![], bijections:vec![],claims:vec![claim],blocks:vec![Block{steps:vec![Step::Plotkin{id:0,bits,distance,variables:(0..n as u32).map(|i|(i,i as u64)).collect(),cliques:(0..source.rows.len() as u32).map(Ref::RowUpper).collect()}],end:End::Return{map:(0..n as u32).map(Expr::var).collect(),checks}}],points:vec![]};
    (source,target,cert)
}
fn check(s:&Model,t:&Model,c:&Certificate)->Result<kernel_core::verify::Statistics,String>{verify(s,t,c,&c.claims,&Limits::default())}
fn bad(s:&Model,t:&Model,c:&Certificate){let e=check(s,t,c).unwrap_err();assert!(e.starts_with("INVALID"),"{e}");}
#[test]fn plotkin_matches_independent_exhaustive_binary_sets_and_permutations(){
    for (bits,distance) in [(1,1),(2,2),(3,2),(3,3),(4,3)]{
        let (s,t,mut c)=setup(bits,distance);check(&s,&t,&c).unwrap();
        let n=s.vars.len();let bound=2*distance/(2*distance-bits);
        // An independent finite-set oracle evaluates original row supports directly.
        for mask in 0..1u64<<n{if s.rows.iter().all(|r|r.expr.terms.iter().filter(|(i,_)|mask&(1u64<<i)!=0).count()<=1){assert!(mask.count_ones()<=bound);}}
        if let Step::Plotkin{variables,cliques,..}=&mut c.blocks[0].steps[0]{variables.reverse();for (_,label) in variables{*label^=(1u64<<bits)-1;}cliques.reverse();}
        check(&s,&t,&c).unwrap();
    }
}
#[test]fn plotkin_all_domain_label_and_parameter_premises_are_binding(){
    let (s,t,c)=setup(3,2);
    for change in 0..8{
        let mut source=s.clone();let mut cert=c.clone();
        match change{
            0=>source.vars[0].integer=false,
            1=>source.vars[0].lower=None,
            2=>source.vars[0].lower=Some(q(-1)),
            3=>source.vars[0].upper=None,
            4=>source.vars[0].upper=Some(q(2)),
            5=>cert.claims[0].input_integers=false,
            6=>{if let Step::Plotkin{variables,..}=&mut cert.blocks[0].steps[0]{variables[0].1=8;}},
            _=>{if let Step::Plotkin{variables,..}=&mut cert.blocks[0].steps[0]{variables[0].0=1;}},
        }
        let e=check(&source,&t,&cert).unwrap_err();assert!(e.contains("Plotkin"),"{change}: {e}");
    }
    for (bits,distance) in [(0,1),(65,64),(3,1),(3,0),(3,65)]{let mut c=c.clone();if let Step::Plotkin{bits:b,distance:d,..}=&mut c.blocks[0].steps[0]{*b=bits;*d=distance;}bad(&s,&t,&c);}
}
#[test]fn every_close_pair_and_every_clique_term_is_checked(){
    let (s,t,c)=setup(3,2);
    let mut broken=c.clone();if let Step::Plotkin{cliques,..}=&mut broken.blocks[0].steps[0]{cliques.remove(5);}assert!(check(&s,&t,&broken).unwrap_err().contains("close pair"));
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
    let mut only=c.clone();only.claims[0].objective=Objective::None;only.claims[0].input_objective_lower=None;only.blocks[0].end=End::Return{map:vec![],checks:vec![]};check(&source,&empty,&only).unwrap();
    // Duplicate labels are legal only when their resulting distance-zero pair is also covered.
    let mut cert=c.clone();if let Step::Plotkin{variables,..}=&mut cert.blocks[0].steps[0]{variables[7].1=0;}assert!(check(&s,&t,&cert).unwrap_err().contains("close pair"));
}
#[test]fn checked_local_cliques_are_allowed_and_dead_references_reject(){
    let (s,t,mut c)=setup(3,2);
    if let Step::Plotkin{cliques,..}=&mut c.blocks[0].steps[0]{cliques[0]=Ref::Local(12);}
    c.blocks[0].steps.insert(0,Step::Lin{id:12,kind:Kind::Le,constant:q(0),terms:vec![(Ref::RowUpper(0),q(1))]});
    check(&s,&t,&c).unwrap();c.blocks[0].steps.insert(1,Step::Drop{ids:vec![12]});bad(&s,&t,&c);
}
#[test]fn global_objective_lower_is_exact_requested_and_last(){
    let (s,t,c)=setup(3,2);let mut badc=c.clone();badc.claims[0].input_objective_lower=Some(q(-3));bad(&s,&t,&badc);
    assert!(verify(&s,&t,&badc,&c.claims,&Limits::default()).unwrap_err().contains("contract mismatch"));
    let mut c=c.clone();if let End::Return{checks,..}=&mut c.blocks[0].end{checks.pop();}assert!(check(&s,&t,&c).unwrap_err().contains("missing obligation"));
    let mut c=c.clone();c.claims[0].input_objective_lower=Some(Q::new_raw(2.into(),4.into()));assert!(check(&s,&t,&c).unwrap_err().contains("canonical"));
}
#[test]fn v3_wire_text_and_legacy_request_compatibility(){
    let (s,t,c)=setup(3,2);let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&3u16.to_le_bytes());
    assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 3\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
    for version in [1u16,2]{assert!(rpa::assemble(&text.replacen("RPA 3",&format!("RPA {version}"),1)).is_err());let mut b=bytes.clone();b[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&b).is_err());}
    let requested=rpa::parse_request(&serde_json::to_string(&c.claims).unwrap()).unwrap();assert!(requested.points.is_empty());verify_request(&s,&t,&c,&requested,&Limits::default()).unwrap();
    let before=include_bytes!("../../../tests/vectors/identity-local-v2.rpx");assert_eq!(codec::encode_certificate(&codec::decode_certificate(before).unwrap()).unwrap(),before);
    let before=include_bytes!("../../../tests/vectors/identity-ordinary.rpx");assert_eq!(codec::encode_certificate(&codec::decode_certificate(before).unwrap()).unwrap(),before);
}
#[test]fn plotkin_inside_cases_requires_version_three(){
    let (s,t,mut c)=setup(3,2);c.claims[0].input_objective_lower=None;if let End::Return{checks,..}=&mut c.blocks[0].end{checks.pop();}
    let theorem=c.blocks[0].steps.remove(0);
    let expr=Expr{constant:q(-4),terms:(0..8).map(|i|(i,q(1))).collect()};
    let child=Derivation{steps:vec![theorem],end:DerivationEnd::Witness(Ref::Local(0))};
    c.blocks[0].steps.push(Step::Cases(Box::new(CasesStep{id:0,kind:Kind::Le,expression:expr,split:Expr{constant:Q::zero(),terms:vec![]},integer:None,left:Box::new(child.clone()),right:Box::new(child)})));
    assert_eq!(codec::certificate_version(&c).unwrap(),3);check(&s,&t,&c).unwrap();assert_eq!(rpa::assemble(&rpa::disassemble(&c).unwrap()).unwrap(),c);
}
#[test]fn v3_truncation_mutation_and_work_limits_are_total(){
    let (s,t,c)=setup(2,2);let bytes=codec::encode_certificate(&c).unwrap();
    for n in 0..bytes.len(){let mut truncated=bytes[..n].to_vec();if n>=16{truncated[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&truncated).is_err(),"{n}");}
    for i in 16..bytes.len(){for value in [0,1,127,255]{let mut mutated=bytes.clone();mutated[i]=value;if let Ok(decoded)=codec::decode_certificate(&mutated){let _=check(&s,&t,&decoded);}}}
    let stats=check(&s,&t,&c).unwrap();assert_eq!(stats.plotkin_pairs,6);
    assert!(verify(&s,&t,&c,&c.claims,&Limits{work:stats.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut c=c.clone();if let Step::Plotkin{variables,..}=&mut c.blocks[0].steps[0]{*variables=vec![(0,0);1_000_000];}
    assert!(check(&s,&t,&c).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
#[test]fn full_width_labels_and_empty_selected_set_are_defined(){
    let source=Model{name:"wide".into(),vars:vec![Var{name:"a".into(),integer:true,lower:Some(q(0)),upper:Some(q(1))},Var{name:"b".into(),integer:true,lower:Some(q(0)),upper:Some(q(1))}],rows:vec![],objective:Expr{constant:q(0),terms:vec![]}};
    let target=Model{name:"empty".into(),vars:vec![],rows:vec![],objective:Expr{constant:q(0),terms:vec![]}};
    let claim=Claim{input_halfspace:None,input_objective_level:None, affine_projection:vec![],reverse:false,input_integers:true,output_integers:false,objective:Objective::None,projection:vec![],inverse:None,input_objective_lower:None};
    for variables in [vec![],vec![(0,0),(1,u64::MAX)]]{let c=Certificate { improvements:vec![], bijections:vec![],claims:vec![claim.clone()],blocks:vec![Block{steps:vec![Step::Plotkin{id:0,bits:64,distance:33,variables,cliques:vec![]}],end:End::Return{map:vec![],checks:vec![]}}],points:vec![]};check(&source,&target,&c).unwrap();}
}

#[test]fn request_resource_errors_preserve_their_category(){
    let text=format!(r#"{{"claims":[],"points":[{{"Feasible":{{"target":false,"integers":false,"objective":"{}"}}}}]}}"#,"9".repeat(4097));
    assert!(rpa::parse_request(&text).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
