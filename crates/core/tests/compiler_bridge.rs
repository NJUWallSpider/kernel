//! Direct JSON compilation is byte-for-byte the frozen codec, and obligation
//! planning uses the verifier's order without altering its work accounting.
use kernel_core::{api, codec, compiler, model::{parse_q, Expr, Model, Row, Var}, proof::*, verify::{self, Limits}};
use serde_json::json;
use std::{fs, path::{Path, PathBuf}, process::Command, sync::atomic::{AtomicUsize, Ordering}};

fn root() -> PathBuf { Path::new(env!("CARGO_MANIFEST_DIR")).join("../..") }
fn vector(name: &str) -> Vec<u8> { fs::read(root().join("tests/vectors").join(name)).unwrap() }
fn model(name: &str) -> Model { codec::decode_model(&vector(&format!("{name}.mcm"))).unwrap() }
fn request(cert: &Certificate) -> Request {
    Request {claims:cert.claims.clone(), points:cert.points.iter().map(|w|w.claim.clone()).collect(),
        bijections:cert.bijections.iter().map(|w|w.claim.clone()).collect(),
        improvements:cert.improvements.iter().map(|w|w.claim.clone()).collect()}
}

#[test]
fn direct_json_matches_independent_vectors_in_every_wire_version() {
    for (version,name) in [
        (1,"identity-ordinary"),(2,"identity-local-v2"),(3,"identity-plotkin-v3"),
        (4,"flow-v4"),(5,"interval-v5"),(6,"fiber-v6"),(7,"menu-v7"),
        (8,"signed-v8"),(9,"level-v9"),(10,"contract-v10"),
    ] {
        let bytes=vector(&format!("{name}.rpx"));
        let cert=codec::decode_certificate(&bytes).unwrap();
        let text=serde_json::to_string(&cert).unwrap();
        assert_eq!(compiler::parse_certificate_json(&text).unwrap(),cert);
        let encoded=api::compile_certificate_json(&text).unwrap();
        assert_eq!(u16::from_le_bytes([encoded[4],encoded[5]]),version,"{name}");
        assert_eq!(encoded,bytes,"{name}");
    }
}

#[test]
fn shared_return_walk_preserves_frozen_work_and_obligation_counts() {
    // Captured with the pre-refactor verifier on the independent wire vectors.
    for (name,input,output,work,obligations,substitution_terms) in [
        ("identity-ordinary","identity","identity",96,12,4),
        ("identity-local-v2","identity","identity",118,12,4),
        ("identity-plotkin-v3","identity","identity",40,6,1),
        ("flow-v4","identity","flow-target",207,7,3),
        ("interval-v5","identity","flow-target",243,8,4),
        ("fiber-v6","fiber-source","identity",133,3,0),
        ("menu-v7","identity","identity",481,12,3),
        ("signed-v8","signed-source","signed-target",577,13,10),
        ("level-v9","level-source","level-target",158,16,5),
        ("contract-v10","contract-v10-source","contract-v10-target",41,9,0),
    ] {
        let cert=codec::decode_certificate(&vector(&format!("{name}.rpx"))).unwrap();
        let stats=verify::verify_request(&model(input),&model(output),&cert,&request(&cert),&Limits::default()).unwrap();
        assert_eq!((stats.work,stats.obligations,stats.substitution_terms),(work,obligations,substitution_terms),"{name}");
    }
}

#[test]
fn malformed_raw_json_and_wire_invalid_objects_are_rejected() {
    let cert=codec::decode_certificate(&vector("identity-ordinary.rpx")).unwrap();
    let good=serde_json::to_value(&cert).unwrap();
    let mut unknown=good.clone();unknown["proof_search"]=json!(true);
    let mut float=good.clone();float["blocks"][0]["end"]["Return"]["map"][0]["constant"]=json!(0.0);
    let mut denominator=good.clone();denominator["blocks"][0]["end"]["Return"]["map"][0]["constant"]=json!("1/0");
    let mut unsorted=good.clone();unsorted["blocks"][0]["end"]["Return"]["map"][0]["terms"]=json!([[1,"1"],[0,"1"]]);
    let mut mismatch=good.clone();mismatch["blocks"]=json!([]);
    for bad in [unknown,float,denominator,unsorted,mismatch] {
        assert_eq!(api::compile_certificate_json(&bad.to_string()).unwrap_err().status(),api::Status::Invalid);
    }
    for bad in ["{", "RPA 1\n{\"claims\":[],\"blocks\":[]}", "{\"claims\":[],\"claims\":[],\"blocks\":[]}"] {
        assert_eq!(api::compile_certificate_json(bad).unwrap_err().status(),api::Status::Invalid);
    }
    let mut block=json!({"steps":[],"end":{"Return":{"map":[],"checks":[]}}});
    for _ in 0..70{block=json!({"steps":[],"end":{"IntervalLift":{"intervals":[],"body":block}}});}
    let nested=json!({"claims":[],"blocks":[block]}).to_string();
    assert_eq!(api::compile_certificate_json(&nested).unwrap_err().status(),api::Status::ResourceLimit);
}

#[test]
fn compilation_does_not_accept_a_mathematically_invalid_proof() {
    let mut cert=codec::decode_certificate(&vector("identity-ordinary.rpx")).unwrap();
    let End::Return{checks,..}=&mut cert.blocks[0].end else {panic!()};
    checks[0]=Ref::Exact;
    let encoded=api::compile_certificate_json(&serde_json::to_string(&cert).unwrap()).unwrap();
    let decoded=codec::decode_certificate(&encoded).unwrap();
    assert!(verify::verify_request(&model("identity"),&model("identity"),&decoded,&request(&cert),&Limits::default()).unwrap_err().contains("non-tautological exact"));
}

fn fixture() -> (Model,Claim) {
    let m=Model{name:"scope".into(),vars:vec![Var{name:"x".into(),integer:true,lower:Some(parse_q("0").unwrap()),upper:Some(parse_q("1").unwrap())}],
        rows:vec![Row{name:"eq".into(),expr:Expr::var(0),lower:Some(parse_q("1").unwrap()),upper:Some(parse_q("1").unwrap())},
            Row{name:"range".into(),expr:Expr::var(0),lower:Some(parse_q("0").unwrap()),upper:Some(parse_q("1").unwrap())}],objective:Expr::var(0)};
    let c=Claim{reverse:false,input_integers:true,output_integers:true,objective:Objective::Equal,projection:vec![(0,0)],
        affine_projection:vec![(Expr::var(0),Expr::var(0))],inverse:Some(1),input_objective_lower:Some(parse_q("0").unwrap()),
        input_objective_level:None,input_halfspace:None};(m,c)
}

#[test]
fn planning_exposes_complete_ordered_formulas_and_origins() {
    let (m,c)=fixture();
    let map=[Expr::var(0)];
    let level=parse_q("1").unwrap();
    let planned=verify::plan_return_obligations(&m,&m,&c,&map,Some(&map),Some(&level),&[&map],&Limits::default()).unwrap();
    let labels:Vec<_>=planned.iter().map(|o|o.origin.kind.as_str()).collect();
    assert_eq!(labels,["variable.lower","variable.upper","variable.integer","row.equal","row.lower","row.upper",
        "objective.equal","projection","affine_projection","inverse.coordinate","inverse.objective_level","input.objective_lower","bijection.coordinate"]);
    assert_eq!(planned[0].expression,json_expr("0",vec![(0,"-1")]));
    assert_eq!(planned[1].expression,json_expr("-1",vec![(0,"1")]));
    assert_eq!(planned[2].kind,Kind::Int);
    assert_eq!(planned[3].expression,json_expr("-1",vec![(0,"1")]));
    for i in [6,7,8,9,12]{assert_eq!(planned[i].expression,Expr::zero());}
    assert_eq!(planned[10].expression,json_expr("-1",vec![(0,"1")]));
    assert_eq!(planned[11].expression,json_expr("0",vec![(0,"-1")]));
    assert_eq!(planned[0].origin.name.as_deref(),Some("x"));
    assert_eq!(planned[3].origin.name.as_deref(),Some("eq"));
    assert_eq!(planned[12].origin.group,Some(0));
    let serialized=serde_json::to_value(&planned).unwrap();
    assert_eq!(serialized[6]["origin"],json!({"kind":"objective.equal"}));
    let bad=verify::plan_return_obligations(&m,&m,&c,&[],Some(&map),None,&[],&Limits::default()).unwrap_err();
    assert!(bad.contains("incomplete mapping"));
    let limits=Limits{work:0,..Limits::default()};
    assert!(verify::plan_return_obligations(&m,&m,&c,&map,Some(&map),None,&[],&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
}
fn json_expr(constant:&str,terms:Vec<(u32,&str)>)->Expr {
    Expr{constant:parse_q(constant).unwrap(),terms:terms.into_iter().map(|(i,q)|(i,parse_q(q).unwrap())).collect()}
}

#[test]
fn improvement_planning_uses_root_predicate_and_the_shared_margin_formula() {
    let m=Model{name:"improve".into(),vars:vec![Var{name:"x".into(),integer:false,
        lower:Some(parse_q("0").unwrap()),upper:None}],rows:vec![],objective:Expr::var(0)};
    let ordinary=json!({"reverse":false,"input_integers":false,"output_integers":false,
        "objective":"NonIncreasing","projection":[],"inverse":null});
    let positive=Expr::var(0);
    let spec=json!({"claim":ordinary,"map":[Expr::zero()],"improvement":{
        "claim":{"target":false,"integers":false,"positive":positive},"margin":{"Predicate":"1"}}});
    let plan=compiler::parse_return_plan_json(&spec.to_string()).unwrap();
    let goals=compiler::plan_return(&m,&m,&plan,&Limits::default()).unwrap();
    assert_eq!(goals.len(),2);assert_eq!(goals[0].expression,Expr::zero());
    assert_eq!(goals[1].expression,Expr::zero());
    assert_eq!(goals[1].origin.kind,"objective.non_increasing");
    let claim=ImprovementClaim{target:false,integers:false,positive};
    let cert=Certificate{improvements:vec![ImprovementWitness{claim:claim.clone(),block:Block{steps:vec![],
        end:End::ImproveReturn{map:vec![Expr::zero()],checks:vec![Ref::Exact;goals.len()],margin:ImprovementMargin::Predicate(parse_q("1").unwrap())}}}],..Certificate::default()};
    verify::verify_request(&m,&m,&cert,&request(&cert),&Limits::default()).unwrap();
    let mut constant=spec.clone();constant["improvement"]["margin"]=json!({"Constant":"1/2"});
    let goals=compiler::plan_return(&m,&m,&compiler::parse_return_plan_json(&constant.to_string()).unwrap(),&Limits::default()).unwrap();
    assert_eq!(goals[1].expression,json_expr("1/2",vec![(0,"-1")]));
    for bad in ["0","-1"] {
        let mut spec=spec.clone();spec["improvement"]["margin"]=json!({"Predicate":bad});
        assert!(compiler::plan_return(&m,&m,&compiler::parse_return_plan_json(&spec.to_string()).unwrap(),&Limits::default()).unwrap_err().contains("strictly positive"));
    }
    let mut wrong=spec.clone();wrong["claim"]["objective"]=json!("Equal");
    assert!(compiler::plan_return(&m,&m,&compiler::parse_return_plan_json(&wrong.to_string()).unwrap(),&Limits::default()).unwrap_err().contains("improvement claim context"));
    let mut other=m.clone();other.vars[0].lower=Some(parse_q("-1").unwrap());
    assert!(compiler::plan_return(&m,&other,&plan,&Limits::default()).unwrap_err().contains("improvement model context"));
    // Joint extension scopes keep the immutable root positive predicate.
    let ext=kernel_core::interval::prepare_unchecked_extension(&m,&[IntervalWitness{lower:vec![],upper:vec![],checks:vec![]}],&Limits::default()).unwrap();
    assert_eq!(compiler::plan_return(&ext.model,&m,&plan,&Limits::default()).unwrap().len(),2);
    let mut captured=spec.clone();captured["improvement"]["claim"]["positive"]=serde_json::to_value(Expr::var(1)).unwrap();
    assert!(compiler::plan_return(&ext.model,&m,&compiler::parse_return_plan_json(&captured.to_string()).unwrap(),&Limits::default()).is_err());
}

#[test]
fn injectivity_bridge_returns_the_complete_kernel_domain_and_fresh_goals() {
    let input=model("identity");let output=model("identity");
    let map=[json_expr("3",vec![(0,"2")])];
    let spec=json!({"map":map}).to_string();
    let prepared=compiler::prepare_injectivity_json(&input,&output,&spec,&Limits::default()).unwrap();
    let domain=kernel_core::injectivity::prepare_domain(&input,&output,&map,&Limits::default()).unwrap();
    assert_eq!(prepared,json!({"model":kernel_core::model::to_json(&domain.model),
        "equalities":domain.equalities,"statistics":domain.statistics}));
    assert_eq!(prepared["equalities"],json!([json_expr("0",vec![(0,"1"),(1,"-1")])]));
    // Constant forward maps still prepare, because construction proves nothing.
    let noninjective=compiler::prepare_injectivity_json(&input,&output,&json!({"map":[Expr::zero()]}).to_string(),&Limits::default()).unwrap();
    assert_eq!(noninjective["equalities"].as_array().unwrap().len(),1);
    for bad in [json!({"map":[]}),json!({"map":map,"proof_search":true}),json!({"map":[Expr::var(1)]})] {
        assert!(compiler::prepare_injectivity_json(&input,&output,&bad.to_string(),&Limits::default()).is_err());
    }
    let limits=Limits{work:0,..Limits::default()};
    assert!(compiler::prepare_injectivity_json(&input,&output,&spec,&limits).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let dir=Temp::new();let spec_path=dir.0.join("spec.json");let result_path=dir.0.join("domain.json");
    fs::write(&spec_path,spec).unwrap();let mcm=root().join("tests/vectors/identity.mcm");
    let result=Command::new(env!("CARGO_BIN_EXE_rpx")).arg("prepare-injectivity").arg(&mcm).arg(&mcm).arg(&spec_path).arg(&result_path).output().unwrap();
    assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stdout));
    let report:serde_json::Value=serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["status"],"PREPARED");assert_eq!(report["equalities"],1);
    assert_eq!(serde_json::from_slice::<serde_json::Value>(&fs::read(result_path).unwrap()).unwrap(),prepared);
}

static SEQUENCE:AtomicUsize=AtomicUsize::new(0);
struct Temp(PathBuf);
impl Temp {fn new()->Self {let p=std::env::temp_dir().join(format!("rpx-compiler-{}-{}",std::process::id(),SEQUENCE.fetch_add(1,Ordering::Relaxed)));fs::create_dir_all(&p).unwrap();Self(p)}}
impl Drop for Temp {fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}

#[test]
fn cli_compiles_and_plans_without_an_rpa_intermediate() {
    let dir=Temp::new();
    let cert=codec::decode_certificate(&vector("identity-ordinary.rpx")).unwrap();
    let input=dir.0.join("certificate.json");let output=dir.0.join("proof.rpx");
    fs::write(&input,serde_json::to_string(&cert).unwrap()).unwrap();
    let result=Command::new(env!("CARGO_BIN_EXE_rpx")).args(["compile"]).arg(&input).arg(&output).output().unwrap();
    assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stdout));
    let report:serde_json::Value=serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["status"],"COMPILED");assert_eq!(report["version"],1);
    assert_eq!(fs::read(&output).unwrap(),vector("identity-ordinary.rpx"));
    let End::Return{map,..}=&cert.blocks[0].end else{panic!()};
    let End::Return{map:inverse,..}=&cert.blocks[1].end else{panic!()};
    let plan=dir.0.join("plan.json");let obligations=dir.0.join("obligations.json");
    fs::write(&plan,json!({"claim":cert.claims[0],"map":map,"inverse_map":inverse}).to_string()).unwrap();
    let mcm=root().join("tests/vectors/identity.mcm");
    let result=Command::new(env!("CARGO_BIN_EXE_rpx")).arg("plan-return").arg(&mcm).arg(&mcm).arg(&plan).arg(&obligations).output().unwrap();
    assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stdout));
    let report:serde_json::Value=serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["status"],"PLANNED");assert_eq!(report["obligations"],6);
    let entries:serde_json::Value=serde_json::from_slice(&fs::read(&obligations).unwrap()).unwrap();
    assert_eq!(entries[0]["origin"],json!({"kind":"variable.lower","index":0,"name":"x"}));
    // A schema error leaves an existing output intact.
    fs::write(&input,"{\"claims\":[],\"blocks\":[],\"unexpected\":true}").unwrap();
    let result=Command::new(env!("CARGO_BIN_EXE_rpx")).arg("compile").arg(&input).arg(&output).output().unwrap();
    assert_eq!(result.status.code(),Some(2));
    assert_eq!(fs::read(output).unwrap(),vector("identity-ordinary.rpx"));
}
