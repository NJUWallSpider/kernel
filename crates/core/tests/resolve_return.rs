//! Untrusted exact-reuse resolution produces compact witness lists, while the
//! Kernel still executes and validates every actual fact reference.
use kernel_core::{codec, compiler, model::{Expr, Model}, proof::*, verify::{self, Limits}};
use serde_json::{Value, json};
use std::{fs, path::{Path, PathBuf}, process::Command};

fn source()->Model {codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap()}
fn claim(integers:bool)->Claim {Claim{reverse:false,input_integers:integers,output_integers:integers,
    objective:Objective::Equal,projection:vec![],affine_projection:vec![],inverse:None,
    input_objective_lower:None,input_objective_level:None,input_halfspace:None}}
fn specification(claim:&Claim,map:&[Expr])->Value {json!({"plan":{"claim":claim,"map":map},"facts":[],"assignments":[],"auto":true})}
fn resolve(input:&Model,output:&Model,spec:&Value)->compiler::ResolveResult {
    compiler::resolve_return_json(input,output,&spec.to_string(),&Limits::default()).unwrap()
}
fn verify_resolved(input:&Model,output:&Model,claim:Claim,map:Vec<Expr>,resolved:compiler::ResolveResult,steps:Vec<Step>)->Result<verify::Statistics,String>{
    let cert=Certificate{claims:vec![claim.clone()],blocks:vec![Block{steps,end:End::Return{map,checks:resolved.checks.into_iter().map(Option::unwrap).collect()}}],..Certificate::default()};
    let encoded=compiler::compile_certificate_json(&serde_json::to_string(&cert).unwrap())?;
    verify::verify_request(input,output,&codec::decode_certificate(&encoded)?,&Request{claims:vec![claim],..Request::default()},&Limits::default())
}

#[test]
fn native_base_reuse_and_tautologies_verify_with_complete_inverse_contracts() {
    let model=source();
    let original=codec::decode_certificate(include_bytes!("../../../tests/vectors/identity-ordinary.rpx")).unwrap();
    let maps=vec![Expr::var(0)];let mut blocks=Vec::new();
    for c in &original.claims {
        let spec=json!({"plan":{"claim":c,"map":maps,"inverse_map":maps}});
        let resolved=resolve(&model,&model,&spec);
        assert_eq!(resolved.obligations,6);assert!(resolved.missing.is_empty());
        assert_eq!(resolved.checks,vec![Some(Ref::VarLower(0)),Some(Ref::VarUpper(0)),Some(Ref::Exact),Some(Ref::Exact),Some(Ref::Exact),Some(Ref::Exact)]);
        blocks.push(Block{steps:vec![],end:End::Return{map:maps.clone(),checks:resolved.checks.into_iter().map(Option::unwrap).collect()}});
    }
    let cert=Certificate{claims:original.claims.clone(),blocks,..Certificate::default()};
    verify::verify_request(&model,&model,&cert,&Request{claims:cert.claims.clone(),..Request::default()},&Limits::default()).unwrap();
}

#[test]
fn missing_goals_are_the_identical_ordered_kernel_plan_and_never_scaled_or_searched() {
    let model=source();let c=claim(true);let map=[Expr::var(0)];
    let mut spec=specification(&c,&map);spec["auto"]=json!(false);
    let result=resolve(&model,&model,&spec);
    let plan=compiler::parse_return_plan_json(&spec["plan"].to_string()).unwrap();
    let expected=compiler::plan_return(&model,&model,&plan,&Limits::default()).unwrap();
    assert_eq!(result.checks,vec![None;4]);
    for (i,item) in result.missing.iter().enumerate(){assert_eq!(item.index,i);assert_eq!(item.obligation,expected[i]);}
    let mut stronger=model.clone();stronger.vars[0].upper=Some(kernel_core::model::parse_q("2").unwrap());
    let mut spec=specification(&c,&map);
    // A caller-supplied proposition equal to twice the desired goal is not reused.
    spec["facts"]=json!([{"kind":"Le","expression":{"constant":"-2","terms":[[0,"2"]]},"reference":{"Local":77}}]);
    let result=resolve(&stronger,&model,&spec);assert_eq!(result.missing.len(),1);
    assert_eq!(result.missing[0].index,1);assert_eq!(result.checks[1],None);
}

#[test]
fn named_and_index_assignments_reuse_visible_facts_but_fake_local_cannot_verify() {
    let mut input=source();input.vars[0].upper=Some(kernel_core::model::parse_q("10").unwrap());
    let mut output=input.clone();output.vars[0].upper=Some(kernel_core::model::parse_q("2").unwrap());
    let c=claim(true);let map=[Expr::var(0)];let mut spec=specification(&c,&map);
    let fake=json!({"kind":"Le","expression":{"constant":"-2","terms":[[0,"1"]]},"reference":{"Local":9}});
    spec["facts"]=json!([fake]);let resolved=resolve(&input,&output,&spec);
    assert!(resolved.missing.is_empty());assert_eq!(resolved.checks[1],Some(Ref::Local(9)));
    assert!(verify_resolved(&input,&output,c.clone(),map.to_vec(),resolved,vec![]).unwrap_err().contains("fact reference"));
    // Actual step9 proves x-10<=0; fabricated metadata still cannot claim x-2<=0.
    let resolved=resolve(&input,&output,&spec);
    let steps=vec![Step::Lin{id:9,kind:Kind::Le,constant:kernel_core::model::parse_q("0").unwrap(),terms:vec![(Ref::VarUpper(0),kernel_core::model::parse_q("1").unwrap())]}];
    assert!(verify_resolved(&input,&output,c,map.to_vec(),resolved,steps).unwrap_err().contains("obligation mismatch"));
    let model=source();let c=claim(true);let mut spec=specification(&c,&map);spec["auto"]=json!(false);
    spec["assignments"]=json!([
        {"label":"variable.lower[x]","fact":{"kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0}}},
        {"index":1,"fact":{"kind":"Le","expression":{"constant":"-1","terms":[[0,"1"]]},"reference":{"VarUpper":0}}},
        {"index":2,"fact":"Exact"},{"label":"objective.equal","fact":"Exact"}]);
    let result=resolve(&model,&model,&spec);assert!(result.missing.is_empty());
    verify_resolved(&model,&model,c,map.to_vec(),result,vec![]).unwrap();
}

#[test]
fn unknown_duplicate_and_mismatched_assignments_are_explicitly_invalid() {
    let model=source();let c=claim(true);let map=[Expr::var(0)];let good=specification(&c,&map);
    let fact=json!({"kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0}});
    for assignments in [
        json!([{"label":"typo","fact":"Exact"}]),json!([{"index":99,"fact":"Exact"}]),
        json!([{"index":0,"label":"variable.lower[x]","fact":fact}]),
        json!([{"index":0,"fact":fact},{"label":"variable.lower[x]","fact":fact}]),
        json!([{"index":0,"fact":"Exact"}]),
        json!([{"index":0,"fact":{"kind":"Eq","expression":Expr::zero(),"reference":{"Local":0}}}]),
        json!([{"index":0,"fact":{"kind":"Le","expression":Expr::zero(),"reference":{"VarLower":0}}}]),
    ] {
        let mut spec=good.clone();spec["assignments"]=assignments;
        assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).unwrap_err().starts_with("INVALID"));
    }
    for reference in [json!({"VarLower":0}),json!("Exact")] {
        let mut spec=good.clone();spec["facts"]=json!([{"kind":"Le","expression":Expr::zero(),"reference":reference}]);
        assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).is_err());
    }
    let mut spec=good;spec["facts"]=json!([{"kind":"Le","expression":Expr::var(1),"reference":{"Assumption":0}}]);
    assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).is_err());
}

#[test]
fn assignment_json_keeps_strict_nested_fields_types_and_scalar_limits() {
    let model=source();let c=claim(true);let map=[Expr::var(0)];
    let good=specification(&c,&map);let plan=good["plan"].to_string();
    // The fact union must parse the object directly: JSON Value buffering
    // would silently keep the last duplicate key in these nested objects.
    for fact in [
        r#"{"kind":"Le","kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0}}"#,
        r#"{"kind":"Le","expression":{"constant":"0","constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0}}"#,
        r#"{"kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0},"reference":{"VarLower":0}}"#,
        r#"{"kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0},"unknown":0}"#,
        r#"{"kind":"Le","expression":{"constant":0.0,"terms":[[0,"-1"]]},"reference":{"VarLower":0}}"#,
    ] {
        let text=format!(r#"{{"plan":{plan},"assignments":[{{"index":0,"fact":{fact}}}]}}"#);
        let error=compiler::resolve_return_json(&model,&model,&text,&Limits::default()).unwrap_err();
        assert!(error.starts_with("INVALID"),"{error}");
    }
    for assignments in [
        json!([{"fact":"Exact"}]),json!([{"index":-1,"fact":"Exact"}]),
        json!([{"index":0.5,"fact":"Exact"}]),json!([{"index":false,"fact":"Exact"}]),
        json!([{"label":0,"fact":"Exact"}]),json!([{"index":0}]),
        json!([{"index":0,"fact":null}]),json!([{"index":0,"fact":false}]),
        json!([{"index":0,"fact":[]}]),json!([{"index":0,"fact":"exact"}]),
        json!([{"index":2,"fact":"Exact"},{"index":2,"fact":"Exact"}]),
        json!([{"label":"objective.equal","fact":"Exact"},{"label":"objective.equal","fact":"Exact"}]),
    ] {
        let mut spec=good.clone();spec["assignments"]=assignments;
        let error=compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).unwrap_err();
        assert!(error.starts_with("INVALID"),"{error}");
    }
    let oversized="9".repeat((kernel_core::model::MAX_Q_BITS as usize*30_103)/100_000+2);
    let text=format!(r#"{{"plan":{plan},"assignments":[{{"index":0,"fact":{{"kind":"Le","expression":{{"constant":"{oversized}","terms":[]}},"reference":{{"Local":0}}}}}}]}}"#);
    assert!(compiler::resolve_return_json(&model,&model,&text,&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn derived_wide_fact_metadata_reuses_the_same_real_proof_and_kernel_rechecks_it() {
    let mut input=source();input.vars[0].integer=false;input.vars[0].upper=Some(kernel_core::model::parse_q("0").unwrap());
    let coefficient=kernel_core::model::parse_q(&format!("1{}","0".repeat(3000))).unwrap();
    let square=&coefficient*&coefficient;
    assert_eq!(square.to_string().len(),6001);kernel_core::model::check_q(&square).unwrap();
    let mut output=input.clone();output.vars[0].name="y".into();
    output.rows.push(kernel_core::model::Row{name:"scaled".into(),expr:Expr::var(0).scaled(&coefficient).unwrap(),
        lower:None,upper:Some(kernel_core::model::parse_q("0").unwrap())});
    let mut c=claim(false);c.objective=Objective::None;let map=vec![Expr::var(0).scaled(&coefficient).unwrap()];
    let steps=vec![
        Step::Lin{id:0,kind:Kind::Le,constant:kernel_core::model::parse_q("0").unwrap(),terms:vec![(Ref::VarLower(0),coefficient.clone())]},
        Step::Lin{id:1,kind:Kind::Le,constant:kernel_core::model::parse_q("0").unwrap(),terms:vec![(Ref::VarUpper(0),coefficient.clone())]},
        Step::Lin{id:2,kind:Kind::Le,constant:kernel_core::model::parse_q("0").unwrap(),terms:vec![(Ref::Local(1),coefficient.clone())]}];
    let expected=vec![Ref::Local(0),Ref::Local(1),Ref::Local(2)];
    // Only the individual 3001-digit multiplier/map/model scalars are encoded;
    // the 6001-digit derived expression is an internal exact Kernel fact.
    let raw=Certificate{claims:vec![c.clone()],blocks:vec![Block{steps:steps.clone(),
        end:End::Return{map:map.clone(),checks:expected.clone()}}],..Certificate::default()};
    let bytes=compiler::compile_certificate_json(&serde_json::to_string(&raw).unwrap()).unwrap();
    let raw_stats=verify::verify_request(&input,&output,&codec::decode_certificate(&bytes).unwrap(),
        &Request{claims:vec![c.clone()],..Request::default()},&Limits::default()).unwrap();
    assert_eq!(raw_stats.work,41);
    let expressions=[Expr::var(0).scaled(&(-&coefficient)).unwrap(),map[0].clone(),Expr::var(0).scaled(&square).unwrap()];
    let facts:Vec<_>=expressions.iter().zip(&expected).map(|(expression,reference)|json!({"kind":"Le","expression":expression,"reference":reference})).collect();
    let mut spec=specification(&c,&map);spec["facts"]=json!(facts);
    let result=resolve(&input,&output,&spec);assert!(result.missing.is_empty());
    assert_eq!(result.checks,expected.iter().cloned().map(Some).collect::<Vec<_>>());
    assert_eq!(verify_resolved(&input,&output,c.clone(),map.clone(),result,steps.clone()).unwrap(),raw_stats);
    // The explicit typed-assignment union uses the same bounded metadata parser.
    spec["auto"]=json!(false);spec["facts"]=json!([]);
    spec["assignments"]=json!(facts.iter().enumerate().map(|(index,fact)|json!({"index":index,"fact":fact})).collect::<Vec<_>>());
    let result=resolve(&input,&output,&spec);assert!(result.missing.is_empty());
    assert_eq!(verify_resolved(&input,&output,c.clone(),map.clone(),result,steps.clone()).unwrap(),raw_stats);
    // Metadata is still not proof: removing the second multiplication leaves
    // Local2 unavailable to the actual verifier.
    let result=resolve(&input,&output,&spec);
    assert!(verify_resolved(&input,&output,c,map,result,steps[..2].to_vec()).is_err());
    // Actual map/proof scalar policy did not widen alongside fact metadata.
    let mut wider_map=spec.clone();wider_map["plan"]["map"][0]=json!(expressions[2]);
    assert!(compiler::resolve_return_json(&input,&output,&wider_map.to_string(),&Limits::default()).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let mut wider_proof=serde_json::to_value(&raw).unwrap();wider_proof["blocks"][0]["steps"][2]["Lin"]["terms"][0][1]=json!(square.to_string());
    assert!(compiler::compile_certificate_json(&wider_proof.to_string()).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn authoring_metadata_intermediate_bits_are_bounded_and_malformed_values_stay_invalid() {
    let largest=(num_bigint::BigInt::from(1u8)<<kernel_core::model::MAX_Q_BITS as usize)-1u8;
    let excessive=&largest+1u8;
    let decode=|scalar:&str|serde_json::from_value::<compiler::AuthoringFact>(json!({
        "kind":"Eq","expression":{"constant":scalar,"terms":[]},"reference":{"Local":0}}));
    let fact=decode(&largest.to_string()).unwrap();assert_eq!(fact.expression.constant.numer().bits(),kernel_core::model::MAX_Q_BITS);
    let fraction=decode(&format!("1/{largest}")).unwrap();assert_eq!(fraction.expression.constant.denom().bits(),kernel_core::model::MAX_Q_BITS);
    for scalar in [excessive.to_string(),format!("1/{excessive}"),format!("{excessive}/{excessive}"),"9".repeat(19730),"9".repeat(39462)] {
        assert!(decode(&scalar).unwrap_err().to_string().contains("RESOURCE_LIMIT"));
    }
    for scalar in ["1/0","NaN"," 0","-","+","1/2/3","1/"] {assert!(decode(scalar).is_err());}
    // Existing exact decimal/scientific and fraction normalization stay valid.
    for scalar in ["0.25","1e-2","-2/-4"] {assert!(decode(scalar).is_ok());}
    assert!(decode(&format!("{largest}/0")).is_err());
}

#[test]
fn exact_reuse_respects_lp_domain_unavailable_bounds_and_canonical_terms() {
    let model=source();let c=claim(false);let map=[Expr::var(0)];let good=specification(&c,&map);
    let mut spec=good.clone();spec["assignments"]=json!([{"index":0,"fact":{"kind":"Int","expression":Expr::var(0),"reference":{"VarInt":0}}}]);
    assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).unwrap_err().contains("unavailable source-model reference"));
    let mut unbounded=model.clone();unbounded.vars[0].lower=None;
    let mut spec=good.clone();spec["assignments"]=json!([{"index":0,"fact":{"kind":"Le","expression":{"constant":"0","terms":[[0,"-1"]]},"reference":{"VarLower":0}}}]);
    assert!(compiler::resolve_return_json(&unbounded,&model,&spec.to_string(),&Limits::default()).unwrap_err().contains("unavailable source-model reference"));
    for terms in [json!([[0,"1"],[0,"-1"]]),json!([[0,"0"]]),json!([[1,"1"]])] {
        let mut spec=good.clone();spec["facts"]=json!([{"kind":"Eq","expression":{"constant":"0","terms":terms},"reference":{"Local":0}}]);
        assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&Limits::default()).is_err());
    }
}

#[test]
fn streaming_full_contract_order_and_group_labels_match_materialized_kernel_plan() {
    let mut model=source();model.vars[0].name="x[0]#1".into();model.objective=Expr::var(0);
    model.rows=vec![
        kernel_core::model::Row{name:"equal".into(),expr:Expr::var(0),lower:Some(kernel_core::model::parse_q("1").unwrap()),upper:Some(kernel_core::model::parse_q("1").unwrap())},
        kernel_core::model::Row{name:"range".into(),expr:Expr::var(0),lower:Some(kernel_core::model::parse_q("0").unwrap()),upper:Some(kernel_core::model::parse_q("1").unwrap())}];
    let mut c=claim(true);c.projection=vec![(0,0)];c.affine_projection=vec![(Expr::var(0),Expr::var(0))];
    c.inverse=Some(1);c.input_objective_lower=Some(kernel_core::model::parse_q("0").unwrap());
    let map=[Expr::var(0)];let mut spec=json!({"plan":{"claim":c,"map":map,"inverse_map":map,"inverse_level":"1","compositions":[map,map]},"auto":false});
    let plan=compiler::parse_return_plan_json(&spec["plan"].to_string()).unwrap();
    let expected=compiler::plan_return(&model,&model,&plan,&Limits::default()).unwrap();
    let result=resolve(&model,&model,&spec);assert_eq!(result.obligations,14);assert_eq!(result.missing.len(),14);
    for (i,item) in result.missing.iter().enumerate(){assert_eq!(item.index,i);assert_eq!(item.obligation,expected[i]);}
    // Python's label uses a name before an index and then appends #group.
    // These explicit assignments cover both compositions despite punctuation
    // in the model name, without an index or expression guessing convention.
    spec["auto"]=json!(true);spec["assignments"]=json!([
        {"label":"bijection.coordinate[x[0]#1]#0","fact":"Exact"},
        {"label":"bijection.coordinate[x[0]#1]#1","fact":"Exact"}]);
    let result=resolve(&model,&model,&spec);assert!(result.missing.is_empty());
    assert_eq!(&result.checks[12..],&[Some(Ref::Exact),Some(Ref::Exact)]);
    assert_eq!(result.checks[10],Some(Ref::RowEq(0)));
    let limited=Limits{work:0,..Limits::default()};
    assert!(compiler::resolve_return_json(&model,&model,&spec.to_string(),&limited).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn eq_fact_reuses_le_and_int_goals_and_improvement_margin_retains_root_context() {
    let mut model=source();let output=model.clone();model.vars[0].upper=Some(kernel_core::model::parse_q("2").unwrap());
    let c=claim(true);let map=[Expr::var(0)];let mut spec=specification(&c,&map);
    spec["facts"]=json!([{"kind":"Eq","expression":{"constant":"-1","terms":[[0,"1"]]},"reference":{"Assumption":0}}]);
    let result=resolve(&model,&output,&spec);assert_eq!(result.checks[1],Some(Ref::Assumption(0)));
    let mut continuous=model.clone();continuous.vars[0].integer=false;
    continuous.rows.push(kernel_core::model::Row{name:"zero".into(),expr:Expr::var(0),lower:Some(kernel_core::model::parse_q("0").unwrap()),upper:Some(kernel_core::model::parse_q("0").unwrap())});
    let mut integral=continuous.clone();integral.vars[0].integer=true;
    let mut int_claim=claim(false);int_claim.output_integers=true;
    let result=resolve(&continuous,&integral,&specification(&int_claim,&map));
    assert_eq!(result.checks[2],Some(Ref::RowEq(0)));
    verify_resolved(&continuous,&integral,int_claim,map.to_vec(),result,vec![]).unwrap();
    let mut model=model;model.objective=Expr::var(0);model.vars[0].integer=false;
    let mut c=claim(false);c.objective=Objective::NonIncreasing;
    let spec=json!({"plan":{"claim":c,"map":[Expr::zero()],"improvement":{"claim":{"target":false,"integers":false,"positive":Expr::var(0)},"margin":{"Predicate":"1"}}}});
    let result=resolve(&model,&model,&spec);assert!(result.missing.is_empty());assert_eq!(result.checks,vec![Some(Ref::Exact);3]);
}

#[test]
fn cli_returns_compact_checks_without_materializing_resolved_goal_json() {
    let c=claim(true);let spec=specification(&c,&[Expr::var(0)]);
    let temp=std::env::temp_dir().join(format!("rpx-resolve-{}",std::process::id()));fs::create_dir_all(&temp).unwrap();
    let spec_path=temp.join("spec.json");let output=temp.join("checks.json");fs::write(&spec_path,spec.to_string()).unwrap();
    let mcm:PathBuf=Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/vectors/identity.mcm");
    let run=Command::new(env!("CARGO_BIN_EXE_rpx")).arg("resolve-return").arg(&mcm).arg(&mcm).arg(&spec_path).arg(&output).output().unwrap();
    assert!(run.status.success(),"{}",String::from_utf8_lossy(&run.stdout));
    let value:Value=serde_json::from_slice(&fs::read(&output).unwrap()).unwrap();
    assert_eq!(value["obligations"],4);assert_eq!(value["missing"],json!([]));assert_eq!(value["unknown_assignments"],json!([]));
    assert_eq!(value["checks"],json!([{"VarLower":0},{"VarUpper":0},"Exact","Exact"]));
    fs::remove_dir_all(temp).unwrap();
}
