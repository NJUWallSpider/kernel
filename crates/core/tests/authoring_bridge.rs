//! Authoring is an unchecked scope preview. Every premise remains parent-scope
//! evidence, and malformed/trivial references are handled by the real verifier.
use kernel_core::{authoring, codec, model::{self, Expr, Model, parse_q}, proof::*, verify::{self, Limits}};
use serde_json::{Value, json};

fn identity_claim() -> Claim {
    Claim{reverse:false,input_integers:true,output_integers:true,objective:Objective::Equal,
        projection:vec![],affine_projection:vec![],inverse:None,input_objective_lower:None,
        input_objective_level:None,input_halfspace:None}
}
fn identity_block(model:&Model) -> Block {
    let mut checks=Vec::new();
    for (i,v) in model.vars.iter().enumerate() {
        if v.lower.is_some(){checks.push(Ref::VarLower(i as u32));}
        if v.upper.is_some(){checks.push(Ref::VarUpper(i as u32));}
        if v.integer{checks.push(Ref::VarInt(i as u32));}
    }
    for (i,r) in model.rows.iter().enumerate() {
        if r.lower.is_some() && r.lower==r.upper {checks.push(Ref::RowEq(i as u32));}
        else {
            if r.lower.is_some(){checks.push(Ref::RowLower(i as u32));}
            if r.upper.is_some(){checks.push(Ref::RowUpper(i as u32));}
        }
    }
    checks.push(Ref::Exact);
    Block{steps:vec![],end:End::Return{map:(0..model.vars.len()).map(|i|Expr::var(i as u32)).collect(),checks}}
}
fn fixtures() -> Vec<(Model,End)> {
    let identity=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let signed=codec::decode_model(include_bytes!("../../../tests/vectors/signed-source.mcm")).unwrap();
    let mut items=Vec::new();
    for (input,bytes) in [
        (identity.clone(),include_bytes!("../../../tests/vectors/flow-v4.rpx").as_slice()),
        (identity.clone(),include_bytes!("../../../tests/vectors/interval-v5.rpx").as_slice()),
        (identity.clone(),include_bytes!("../../../tests/vectors/menu-v7.rpx").as_slice()),
        (signed,include_bytes!("../../../tests/vectors/signed-v8.rpx").as_slice()),
    ] {
        let cert=codec::decode_certificate(bytes).unwrap();
        let end=cert.blocks.into_iter().find(|b|!matches!(b.end,End::Return{..})).unwrap().end;
        items.push((input,end));
    }
    items.push((identity,End::SubflowLift{witness:SubflowWitness{nodes:1,arcs:vec![(0,0)],
        groups:vec![SubflowGroup{source:0,demands:vec![],flows:vec![Expr::var(0)],
            nonnegative:vec![Ref::VarLower(0)],balances:vec![Ref::Exact]}]},
        body:Box::new(Block{steps:vec![],end:End::Absurd{fact:Ref::Exact}})}));
    items
}
fn preparation(input:&Model,end:&End)->(Value,Model) {
    let limits=Limits::default();
    match end {
        End::IntervalLift{intervals,..} => (json!({"Interval":intervals}),kernel_core::interval::prepare_unchecked_extension(input,intervals,&limits).unwrap().model),
        End::MenuLift{menus,..} => (json!({"Menu":menus}),kernel_core::menu::prepare_unchecked_extension(input,menus,&limits).unwrap().model),
        End::SignedLift{decompositions,..} => (json!({"Signed":decompositions}),kernel_core::signed::prepare_unchecked_extension(input,decompositions,&limits).unwrap().model),
        End::FlowLift{witness,..} => (json!({"Flow":witness}),kernel_core::flow::prepare_unchecked_extension(input,witness,&limits).unwrap().model),
        End::SubflowLift{witness,..} => (json!({"Subflow":witness}),kernel_core::subflow::prepare_unchecked_extension(input,witness,&limits).unwrap().model),
        _=>panic!(),
    }
}
fn body_mut(end:&mut End)->&mut Box<Block> {
    match end {
        End::IntervalLift{body,..}|End::MenuLift{body,..}|End::SignedLift{body,..}
            |End::FlowLift{body,..}|End::SubflowLift{body,..}=>body,
        _=>panic!(),
    }
}
fn first_check_mut(end:&mut End)->&mut Ref {
    match end {
        End::IntervalLift{intervals,..}=>&mut intervals[0].checks[0],
        End::MenuLift{menus,..}=>&mut menus[0].checks[0],
        End::SignedLift{decompositions,..}=>&mut decompositions[0].checks[0],
        End::FlowLift{witness,..}=>&mut witness.groups[0].nonnegative[0],
        End::SubflowLift{witness,..}=>&mut witness.groups[0].nonnegative[0],
        _=>panic!(),
    }
}
fn verify_end(input:&Model,output:&Model,end:End)->Result<verify::Statistics,String> {
    let claim=identity_claim();
    let cert=Certificate{claims:vec![claim.clone()],blocks:vec![Block{steps:vec![],end}],..Certificate::default()};
    // Exercise the same direct JSON and binary decode boundary as Python callers.
    let bytes=kernel_core::compiler::compile_certificate_json(&serde_json::to_string(&cert).unwrap()).unwrap();
    let decoded=codec::decode_certificate(&bytes).unwrap();
    verify::verify_request(input,output,&decoded,&Request{claims:vec![claim],..Request::default()},&Limits::default())
}

#[test]
fn all_five_extension_previews_preserve_prefixes_and_verify_only_with_parent_premises() {
    for (input,mut end) in fixtures() {
        let (spec,target)=preparation(&input,&end);
        let preview=authoring::prepare_extension_json(&input,&spec.to_string(),&Limits::default()).unwrap();
        assert_eq!(preview["model"],model::to_json(&target));
        assert_eq!(&target.vars[..input.vars.len()],input.vars.as_slice());
        assert_eq!(&target.rows[..input.rows.len()],input.rows.as_slice());
        assert_eq!(target.objective,input.objective);
        for premise in preview["premises"].as_array().unwrap() {
            let expr:Expr=serde_json::from_value(premise["expression"].clone()).unwrap();
            expr.validate(input.vars.len()).unwrap();
        }
        *body_mut(&mut end)=Box::new(identity_block(&target));
        verify_end(&input,&target,end.clone()).unwrap();
        // Structural preparation intentionally preserves an untrusted reference
        // to a newly appended variable; the old-scope verifier rejects it.
        *first_check_mut(&mut end)=Ref::VarLower(input.vars.len() as u32);
        let (bad_spec,_)=preparation(&input,&end);
        let bad_preview=authoring::prepare_extension_json(&input,&bad_spec.to_string(),&Limits::default()).unwrap();
        assert_eq!(bad_preview["premises"][0]["reference"],json!({"VarLower":input.vars.len()}));
        assert!(verify_end(&input,&target,end).unwrap_err().contains("fact reference"));
    }
}

#[test]
fn false_premise_preview_and_exact_tautology_do_not_create_evidence() {
    let input=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let witness=IntervalWitness{lower:vec![Expr::zero()],upper:vec![Expr{constant:parse_q("-1").unwrap(),terms:vec![]}],checks:vec![Ref::Exact]};
    let spec=json!({"Interval":[witness.clone()]});
    let preview=authoring::prepare_extension_json(&input,&spec.to_string(),&Limits::default()).unwrap();
    assert_eq!(preview["premises"][0],json!({"kind":"Le","expression":{"constant":"1","terms":[]},"reference":"Exact"}));
    let target=kernel_core::interval::prepare_unchecked_extension(&input,&[witness.clone()],&Limits::default()).unwrap().model;
    let end=End::IntervalLift{intervals:vec![witness],body:Box::new(identity_block(&target))};
    assert!(verify_end(&input,&target,end).unwrap_err().contains("non-tautological exact"));
    let tautology=json!({"Interval":[{"lower":[Expr::zero()],"upper":[Expr::zero()],"checks":["Exact"]}]});
    let preview=authoring::prepare_extension_json(&input,&tautology.to_string(),&Limits::default()).unwrap();
    assert_eq!(preview["premises"][0]["expression"],serde_json::to_value(Expr::zero()).unwrap());
}

#[test]
fn schema_parent_dimensions_premise_counts_and_limits_stay_strict() {
    let input=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let valid=json!({"Interval":[{"lower":[Expr::zero()],"upper":[Expr::zero()],"checks":["Exact"]}]});
    for spec in [
        json!({"Interval":[],"trust_solver":true}),
        json!({"Interval":[{"lower":[Expr::var(1)],"upper":[Expr::zero()],"checks":["Exact"]}]}),
        json!({"Interval":[{"lower":[Expr::zero()],"upper":[Expr::zero()],"checks":[]}]}),
        json!({"Interval":[{"lower":[Expr::zero()],"upper":[Expr::zero()],"checks":["TrustSolver"]}]}),
        json!({"Signed":[{"capacity":2.0,"flow":Expr::zero(),"activation":Expr::zero(),"checks":vec!["Exact";5]}]}),
    ] {assert!(authoring::prepare_extension_json(&input,&spec.to_string(),&Limits::default()).is_err());}
    assert!(authoring::prepare_extension_json(&input,&valid.to_string(),&Limits{work:0,..Limits::default()}).unwrap_err().message().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn restricted_preview_orders_level_then_halfspace_without_fabricating_premise_refs() {
    let input=codec::decode_model(include_bytes!("../../../tests/vectors/identity.mcm")).unwrap();
    let level=parse_q("17/5").unwrap();let halfspace=Expr::var(0);
    let spec=json!({"Restricted":{"level":"17/5","halfspace":halfspace}});
    let preview=authoring::prepare_extension_json(&input,&spec.to_string(),&Limits::default()).unwrap();
    let expected=kernel_core::level::prepare_restricted_domain(&input,Some(&level),Some(&halfspace),&Limits::default()).unwrap();
    assert_eq!(preview["model"],model::to_json(&expected.model));
    assert_eq!(preview["premises"],json!([]));
    assert_eq!(preview["equality_row"],input.rows.len());
    assert_eq!(expected.model.rows.len(),input.rows.len()+2);
    assert_eq!(expected.model.rows[input.rows.len()+1].expr,halfspace);
}
